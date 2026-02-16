import asyncio
import hashlib
import hmac
import json
import os
import signal
import statistics
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import asyncpg
import httpx
import psutil

ROOT = Path(r"c:\Users\ayewhy\II SKELDIR II")
BACKEND = ROOT / "backend"
BASE = "http://127.0.0.1:8040"
ADMIN_DSN = "postgresql://postgres:postgres@127.0.0.1:5432/r3_b04_phase3"
TENANT_HEADER = "X-Skeldir-Tenant-Key"
OUT_LOG = ROOT / ".tmp_b04_differential_diagnosis.log"


def sign(body: bytes, secret: str) -> str:
    ts = int(time.time())
    payload = f"{ts}.{body.decode()}".encode()
    sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


async def seed_tenant() -> tuple[str, str, str]:
    conn = await asyncpg.connect(ADMIN_DSN)
    try:
        tid = uuid.uuid5(uuid.NAMESPACE_URL, "b04-diff-tenant")
        api_key = f"b04_diff_{tid}"
        api_hash = hashlib.sha256(api_key.encode()).hexdigest()
        secret = "b04_diff_stripe_secret"
        await conn.execute(
            """
            INSERT INTO tenants (
              id, api_key_hash, name, notification_email,
              shopify_webhook_secret, stripe_webhook_secret,
              paypal_webhook_secret, woocommerce_webhook_secret,
              created_at, updated_at
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,NOW(),NOW())
            ON CONFLICT (id) DO NOTHING
            """,
            str(tid),
            api_hash,
            "B04 Differential Tenant",
            "b04_diff@test.invalid",
            "s",
            secret,
            "p",
            "w",
        )
        return str(tid), api_key, secret
    finally:
        await conn.close()


async def pg_runtime_info() -> dict[str, Any]:
    conn = await asyncpg.connect(ADMIN_DSN)
    try:
        max_conn = int(await conn.fetchval("show max_connections"))
        version = await conn.fetchval("show server_version")
        return {"postgres_max_connections": max_conn, "server_version": str(version)}
    finally:
        await conn.close()


async def wait_ready(timeout_s: int = 90):
    async with httpx.AsyncClient() as c:
        start = time.perf_counter()
        while time.perf_counter() - start < timeout_s:
            try:
                r = await c.get(BASE + "/health/live", timeout=3)
                if r.status_code == 200:
                    return
            except Exception:
                pass
            await asyncio.sleep(0.5)
    raise RuntimeError("uvicorn did not become ready")


async def sample_db(stop: dict[str, bool], out: list[dict[str, Any]]) -> None:
    conn = await asyncpg.connect(ADMIN_DSN)
    try:
        while not stop["stop"]:
            row = await conn.fetchrow(
                """
                SELECT
                  count(*) FILTER (WHERE usename='app_user') as app_total,
                  count(*) FILTER (WHERE usename='app_user' AND state='active') as app_active,
                  count(*) FILTER (WHERE usename='app_user' AND state='idle') as app_idle
                FROM pg_stat_activity
                WHERE datname='r3_b04_phase3'
                """
            )
            waits = await conn.fetch(
                """
                SELECT
                  COALESCE(wait_event_type,'None') as wait_event_type,
                  COALESCE(wait_event,'None') as wait_event,
                  count(*) as cnt
                FROM pg_stat_activity
                WHERE datname='r3_b04_phase3' AND usename='app_user'
                GROUP BY 1,2
                """
            )
            wait_buckets: dict[str, int] = {}
            for w in waits:
                wait_buckets[f"{w['wait_event_type']}:{w['wait_event']}"] = int(w["cnt"])
            out.append(
                {
                    "t": time.perf_counter(),
                    "app_total": int(row["app_total"]),
                    "app_active": int(row["app_active"]),
                    "app_idle": int(row["app_idle"]),
                    "wait_buckets": wait_buckets,
                }
            )
            await asyncio.sleep(0.2)
    finally:
        await conn.close()


async def run_with_telemetry(coro):
    stop = {"stop": False}
    db_samples: list[dict[str, Any]] = []
    cpu_samples: list[dict[str, Any]] = []
    proc = psutil.Process(os.getpid())
    proc.cpu_percent(interval=None)

    async def sample_cpu():
        while not stop["stop"]:
            cpu_samples.append(
                {
                    "t": time.perf_counter(),
                    "proc_cpu": proc.cpu_percent(interval=None),
                    "sys_cpu": psutil.cpu_percent(interval=None),
                }
            )
            await asyncio.sleep(0.2)

    t_db = asyncio.create_task(sample_db(stop, db_samples))
    t_cpu = asyncio.create_task(sample_cpu())
    t0 = time.perf_counter()
    result = await coro
    elapsed = time.perf_counter() - t0
    stop["stop"] = True
    await asyncio.gather(t_db, t_cpu, return_exceptions=True)

    peak_total = max((s["app_total"] for s in db_samples), default=0)
    peak_active = max((s["app_active"] for s in db_samples), default=0)
    peak_idle = max((s["app_idle"] for s in db_samples), default=0)

    max_wait: dict[str, int] = {}
    for s in db_samples:
        for k, v in s["wait_buckets"].items():
            if v > max_wait.get(k, 0):
                max_wait[k] = v

    def bucket(name: str) -> int:
        return max_wait.get(name, 0)

    top_wait = dict(sorted(max_wait.items(), key=lambda kv: kv[1], reverse=True)[:12])

    avg_proc_cpu = round(sum(x["proc_cpu"] for x in cpu_samples) / len(cpu_samples), 2) if cpu_samples else 0.0
    avg_sys_cpu = round(sum(x["sys_cpu"] for x in cpu_samples) / len(cpu_samples), 2) if cpu_samples else 0.0
    peak_proc_cpu = max((x["proc_cpu"] for x in cpu_samples), default=0.0)
    peak_sys_cpu = max((x["sys_cpu"] for x in cpu_samples), default=0.0)

    result["telemetry"] = {
        "elapsed_seconds": round(elapsed, 4),
        "samples": len(db_samples),
        "db_peak_app_user_total": peak_total,
        "db_peak_app_user_active": peak_active,
        "db_peak_app_user_idle": peak_idle,
        "db_wait_buckets_peak": top_wait,
        "db_wait_IO_XactSync_peak": bucket("IO:XactSync"),
        "db_wait_Lock_tuple_peak": bucket("Lock:tuple"),
        "db_wait_Lock_transactionid_peak": bucket("Lock:transactionid"),
        "db_wait_ClientRead_peak": bucket("Client:ClientRead"),
        "cpu_peak_process_percent": peak_proc_cpu,
        "cpu_avg_process_percent": avg_proc_cpu,
        "cpu_peak_system_percent": peak_sys_cpu,
        "cpu_avg_system_percent": avg_sys_cpu,
    }
    return result


async def bench_ready(n: int, conc: int, keepalive: int) -> dict[str, Any]:
    sem = asyncio.Semaphore(conc)
    limits = httpx.Limits(max_connections=conc, max_keepalive_connections=keepalive)
    lat: list[float] = []
    timeout_count = 0
    req_err = 0

    async with httpx.AsyncClient(limits=limits) as c:
        async def one(i: int):
            nonlocal timeout_count, req_err
            async with sem:
                headers = {"Connection": "close"} if keepalive == 0 else {}
                t = time.perf_counter()
                try:
                    r = await c.get(BASE + "/health/ready", headers=headers, timeout=30)
                    lat.append((time.perf_counter() - t) * 1000)
                    return r.status_code
                except httpx.TimeoutException:
                    timeout_count += 1
                    return "timeout"
                except httpx.RequestError:
                    req_err += 1
                    return "request_error"

        t0 = time.perf_counter()
        codes = await asyncio.gather(*[one(i) for i in range(n)])
        dt = time.perf_counter() - t0

    q = statistics.quantiles(lat, n=100) if len(lat) >= 100 else [0] * 99
    ok = sum(1 for c in codes if isinstance(c, int) and c == 200)
    non200 = sum(1 for c in codes if isinstance(c, int) and c != 200)
    return {
        "n": n,
        "conc": conc,
        "keepalive": keepalive,
        "seconds": round(dt, 4),
        "rps_ok": round(ok / dt, 2),
        "ok_200": ok,
        "non200": non200,
        "timeouts": timeout_count,
        "request_errors": req_err,
        "lat_ms_p50": round(q[49], 2) if q[49] else 0.0,
        "lat_ms_p95": round(q[94], 2) if q[94] else 0.0,
        "lat_ms_p99": round(q[98], 2) if q[98] else 0.0,
    }


async def bench_webhook_unique(n: int, conc: int, api_key: str, secret: str) -> dict[str, Any]:
    sem = asyncio.Semaphore(conc)
    limits = httpx.Limits(max_connections=conc, max_keepalive_connections=conc)
    lat: list[float] = []
    timeout_count = 0
    req_err = 0
    url = BASE + "/api/webhooks/stripe/payment_intent/succeeded"

    async with httpx.AsyncClient(limits=limits) as c:
        async def one(i: int):
            nonlocal timeout_count, req_err
            async with sem:
                key = str(uuid.uuid5(uuid.NAMESPACE_URL, f"b04-diff-key-{i}"))
                body = {
                    "id": f"evt_{i}",
                    "type": "payment_intent.succeeded",
                    "created": int(time.time()),
                    "data": {
                        "object": {
                            "id": f"pi_{i}",
                            "amount": 1234,
                            "currency": "usd",
                            "status": "succeeded",
                            "metadata": {
                                "vendor": "facebook_ads",
                                "utm_source": "fb" if i % 2 == 0 else "facebook",
                                "utm_medium": "cpc",
                            },
                        }
                    },
                }
                b = json.dumps(body, separators=(",", ":"), sort_keys=True).encode()
                headers = {
                    "Content-Type": "application/json",
                    TENANT_HEADER: api_key,
                    "X-Idempotency-Key": key,
                    "Stripe-Signature": sign(b, secret),
                    "X-Correlation-ID": str(uuid.uuid4()),
                }
                t = time.perf_counter()
                try:
                    r = await c.post(url, content=b, headers=headers, timeout=30)
                    lat.append((time.perf_counter() - t) * 1000)
                    return r.status_code
                except httpx.TimeoutException:
                    timeout_count += 1
                    return "timeout"
                except httpx.RequestError:
                    req_err += 1
                    return "request_error"

        t0 = time.perf_counter()
        codes = await asyncio.gather(*[one(i) for i in range(n)])
        dt = time.perf_counter() - t0

    q = statistics.quantiles(lat, n=100) if len(lat) >= 100 else [0] * 99
    ok = sum(1 for c in codes if isinstance(c, int) and c == 200)
    non200 = sum(1 for c in codes if isinstance(c, int) and c != 200)
    return {
        "n": n,
        "conc": conc,
        "seconds": round(dt, 4),
        "rps_ok": round(ok / dt, 2),
        "ok_200": ok,
        "non200": non200,
        "timeouts": timeout_count,
        "request_errors": req_err,
        "lat_ms_p50": round(q[49], 2) if q[49] else 0.0,
        "lat_ms_p95": round(q[94], 2) if q[94] else 0.0,
        "lat_ms_p99": round(q[98], 2) if q[98] else 0.0,
    }


def main() -> int:
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": "backend",
            "DATABASE_URL": "postgresql://app_user:app_user@127.0.0.1:5432/r3_b04_phase3",
            "MIGRATION_DATABASE_URL": "postgresql://postgres:postgres@127.0.0.1:5432/r3_b04_phase3",
            "DATABASE_POOL_SIZE": "20",
            "DATABASE_MAX_OVERFLOW": "0",
            "DATABASE_POOL_TIMEOUT_SECONDS": "3",
            "DATABASE_POOL_TOTAL_CAP": "30",
            "INGESTION_FOLLOWUP_TASKS_ENABLED": "false",
        }
    )

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8040",
        "--workers",
        "2",
        "--no-access-log",
    ]

    proc = subprocess.Popen(cmd, cwd=str(BACKEND), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        asyncio.run(wait_ready())
        tenant_id, api_key, secret = asyncio.run(seed_tenant())
        runtime = asyncio.run(pg_runtime_info())

        keep = asyncio.run(run_with_telemetry(bench_ready(n=1200, conc=120, keepalive=120)))
        keep["phase"] = "ready_keepalive"

        close = asyncio.run(run_with_telemetry(bench_ready(n=1200, conc=120, keepalive=0)))
        close["phase"] = "ready_connection_close"

        webhook = asyncio.run(run_with_telemetry(bench_webhook_unique(n=3000, conc=200, api_key=api_key, secret=secret)))
        webhook["phase"] = "webhook_unique_keepalive"

        out = {
            "runtime": {
                **runtime,
                "database_pool_size": int(env["DATABASE_POOL_SIZE"]),
                "database_max_overflow": int(env["DATABASE_MAX_OVERFLOW"]),
                "database_pool_timeout_seconds": float(env["DATABASE_POOL_TIMEOUT_SECONDS"]),
                "database_pool_total_cap": int(env["DATABASE_POOL_TOTAL_CAP"]),
                "uvicorn_workers": 2,
                "tenant_id": tenant_id,
            },
            "results": [keep, close, webhook],
            "delta_ready_close_minus_keepalive": {
                "seconds": round(close["seconds"] - keep["seconds"], 4),
                "rps_ok": round(close["rps_ok"] - keep["rps_ok"], 2),
                "timeouts": close["timeouts"] - keep["timeouts"],
                "p95_ms": round(close["lat_ms_p95"] - keep["lat_ms_p95"], 2),
            },
        }

        OUT_LOG.write_text(json.dumps(out, indent=2), encoding="utf-8")
        print("B04_DIFFERENTIAL_DIAGNOSIS_BEGIN")
        print(json.dumps(out, indent=2))
        print("B04_DIFFERENTIAL_DIAGNOSIS_END")
        return 0
    finally:
        try:
            proc.send_signal(signal.CTRL_BREAK_EVENT)
            proc.wait(timeout=10)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
