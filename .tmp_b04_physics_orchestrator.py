import asyncio
import hashlib
import hmac
import json
import os
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any
import statistics
import traceback

import asyncpg
import httpx
import requests
import psutil

ROOT = Path(r"c:\Users\ayewhy\II SKELDIR II")
BACKEND = ROOT / "backend"
BASE = "http://127.0.0.1:8020"
ADMIN_DSN = "postgresql://postgres:postgres@127.0.0.1:5432/r3_b04_phase3"
TENANT_HEADER = "X-Skeldir-Tenant-Key"
UVICORN_LOG = ROOT / ".tmp_b04_physics_uvicorn.log"
UVICORN_ERR = ROOT / ".tmp_b04_physics_uvicorn.err.log"


def sign(body: bytes, secret: str) -> str:
    ts = int(time.time())
    payload = f"{ts}.{body.decode()}".encode()
    sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


async def seed_tenant() -> tuple[str, str]:
    conn = await asyncpg.connect(ADMIN_DSN)
    try:
        tid = uuid.uuid5(uuid.NAMESPACE_URL, "physics-tenant")
        api_key = f"physics_{tid}"
        api_hash = hashlib.sha256(api_key.encode()).hexdigest()
        secret = "physics_stripe_secret"
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
            "Physics Tenant",
            "physics@test.invalid",
            "s",
            secret,
            "p",
            "w",
        )
        return api_key, secret
    finally:
        await conn.close()


async def get_postgres_max_connections() -> int:
    conn = await asyncpg.connect(ADMIN_DSN)
    try:
        val = await conn.fetchval("SHOW max_connections")
        return int(val)
    finally:
        await conn.close()


async def wait_ready(timeout_s: int = 90) -> None:
    async with httpx.AsyncClient() as client:
        start = time.perf_counter()
        while time.perf_counter() - start < timeout_s:
            try:
                r = await client.get(f"{BASE}/health/ready", timeout=2)
                if r.status_code == 200:
                    return
            except Exception:
                pass
            await asyncio.sleep(1)
    raise RuntimeError("uvicorn readiness timeout")


async def bench_async_get(path: str, n: int, conc: int, keepalive: int) -> dict:
    sem = asyncio.Semaphore(conc)
    limits = httpx.Limits(max_connections=conc, max_keepalive_connections=keepalive)
    async with httpx.AsyncClient(limits=limits) as client:
        latencies_ms: list[float] = []

        async def one(i: int) -> int:
            async with sem:
                headers = {"Connection": "close"} if keepalive == 0 else {}
                t1 = time.perf_counter()
                r = await client.get(BASE + path, headers=headers, timeout=10)
                latencies_ms.append((time.perf_counter() - t1) * 1000.0)
                return r.status_code

        t0 = time.perf_counter()
        codes = await asyncio.gather(*[one(i) for i in range(n)])
        dt = time.perf_counter() - t0
    return {
        "path": path,
        "n": n,
        "conc": conc,
        "keepalive": keepalive,
        "seconds": round(dt, 4),
        "rps": round(n / dt, 2),
        "non200": sum(1 for c in codes if c != 200),
        "lat_ms_p50": round(statistics.quantiles(latencies_ms, n=100)[49], 2) if latencies_ms else 0.0,
        "lat_ms_p95": round(statistics.quantiles(latencies_ms, n=100)[94], 2) if latencies_ms else 0.0,
        "lat_ms_p99": round(statistics.quantiles(latencies_ms, n=100)[98], 2) if latencies_ms else 0.0,
    }


def bench_sync_get(path: str, n: int) -> dict:
    t0 = time.perf_counter()
    bad = 0
    for _ in range(n):
        r = requests.get(BASE + path, timeout=10)
        if r.status_code != 200:
            bad += 1
    dt = time.perf_counter() - t0
    return {
        "path": path,
        "n": n,
        "mode": "sync_loop",
        "seconds": round(dt, 4),
        "rps": round(n / dt, 2),
        "non200": bad,
    }


async def bench_webhook_unique(n: int, conc: int, api_key: str, secret: str) -> dict:
    sem = asyncio.Semaphore(conc)
    limits = httpx.Limits(max_connections=conc, max_keepalive_connections=conc)
    url = BASE + "/api/webhooks/stripe/payment_intent/succeeded"
    async with httpx.AsyncClient(limits=limits) as client:
        latencies_ms: list[float] = []

        async def one(i: int) -> int:
            async with sem:
                key = str(uuid.uuid5(uuid.NAMESPACE_URL, f"physics-key-{i}"))
                body = {
                    "id": f"evt_{i}",
                    "type": "payment_intent.succeeded",
                    "created": int(time.time()),
                    "data": {"object": {"id": f"pi_{i}", "amount": 1234, "currency": "usd", "status": "succeeded"}},
                }
                b = json.dumps(body, separators=(",", ":"), sort_keys=True).encode()
                headers = {
                    "Content-Type": "application/json",
                    TENANT_HEADER: api_key,
                    "X-Idempotency-Key": key,
                    "Stripe-Signature": sign(b, secret),
                    "X-Correlation-ID": str(uuid.uuid4()),
                }
                t1 = time.perf_counter()
                r = await client.post(url, content=b, headers=headers, timeout=10)
                latencies_ms.append((time.perf_counter() - t1) * 1000.0)
                return r.status_code

        t0 = time.perf_counter()
        codes = await asyncio.gather(*[one(i) for i in range(n)])
        dt = time.perf_counter() - t0
    return {
        "path": "/api/webhooks/stripe/payment_intent/succeeded",
        "n": n,
        "conc": conc,
        "seconds": round(dt, 4),
        "rps": round(n / dt, 2),
        "non200": sum(1 for c in codes if c != 200),
        "lat_ms_p50": round(statistics.quantiles(latencies_ms, n=100)[49], 2) if latencies_ms else 0.0,
        "lat_ms_p95": round(statistics.quantiles(latencies_ms, n=100)[94], 2) if latencies_ms else 0.0,
        "lat_ms_p99": round(statistics.quantiles(latencies_ms, n=100)[98], 2) if latencies_ms else 0.0,
    }

async def sample_db_activity(stop_flag: dict[str, bool], out: list[dict[str, Any]]) -> None:
    conn = await asyncpg.connect(ADMIN_DSN)
    try:
        while not stop_flag["stop"]:
            row = await conn.fetchrow(
                """
                SELECT
                  count(*) FILTER (WHERE usename = 'app_user') AS app_user_total,
                  count(*) FILTER (WHERE usename = 'app_user' AND state = 'active') AS app_user_active,
                  count(*) FILTER (WHERE usename = 'app_user' AND state = 'idle') AS app_user_idle
                FROM pg_stat_activity
                WHERE datname = 'r3_b04_phase3'
                """
            )
            waits = await conn.fetch(
                """
                SELECT
                  COALESCE(wait_event_type, 'None') AS wait_event_type,
                  COALESCE(wait_event, 'None') AS wait_event,
                  COUNT(*) AS cnt
                FROM pg_stat_activity
                WHERE datname = 'r3_b04_phase3' AND usename = 'app_user'
                GROUP BY 1,2
                """
            )
            wait_buckets: dict[str, int] = {}
            for w in waits:
                key = f"{w['wait_event_type']}:{w['wait_event']}"
                wait_buckets[key] = int(w["cnt"])
            out.append(
                {
                    "t": time.perf_counter(),
                    "app_user_total": int(row["app_user_total"]),
                    "app_user_active": int(row["app_user_active"]),
                    "app_user_idle": int(row["app_user_idle"]),
                    "wait_buckets": wait_buckets,
                }
            )
            await asyncio.sleep(0.2)
    finally:
        await conn.close()


async def run_with_telemetry(coro):
    stop_flag = {"stop": False}
    db_samples: list[dict[str, Any]] = []
    cpu_samples: list[dict[str, Any]] = []
    proc = psutil.Process(os.getpid())
    proc.cpu_percent(interval=None)

    async def sample_cpu():
        while not stop_flag["stop"]:
            cpu_samples.append(
                {
                    "t": time.perf_counter(),
                    "process_cpu_percent": proc.cpu_percent(interval=None),
                    "system_cpu_percent": psutil.cpu_percent(interval=None),
                }
            )
            await asyncio.sleep(0.2)

    db_task = asyncio.create_task(sample_db_activity(stop_flag, db_samples))
    cpu_task = asyncio.create_task(sample_cpu())
    t0 = time.perf_counter()
    result = await coro
    elapsed = time.perf_counter() - t0
    stop_flag["stop"] = True
    await asyncio.gather(db_task, cpu_task, return_exceptions=True)

    peak_total = max((x["app_user_total"] for x in db_samples), default=0)
    peak_active = max((x["app_user_active"] for x in db_samples), default=0)
    peak_idle = max((x["app_user_idle"] for x in db_samples), default=0)
    max_wait_buckets: dict[str, int] = {}
    for s in db_samples:
        for key, val in s.get("wait_buckets", {}).items():
            if val > max_wait_buckets.get(key, 0):
                max_wait_buckets[key] = val
    top_wait_buckets = dict(
        sorted(max_wait_buckets.items(), key=lambda kv: kv[1], reverse=True)[:8]
    )
    peak_proc_cpu = max((x["process_cpu_percent"] for x in cpu_samples), default=0.0)
    peak_sys_cpu = max((x["system_cpu_percent"] for x in cpu_samples), default=0.0)
    avg_proc_cpu = round(
        sum(x["process_cpu_percent"] for x in cpu_samples) / len(cpu_samples), 2
    ) if cpu_samples else 0.0
    avg_sys_cpu = round(
        sum(x["system_cpu_percent"] for x in cpu_samples) / len(cpu_samples), 2
    ) if cpu_samples else 0.0

    result["telemetry"] = {
        "elapsed_seconds": round(elapsed, 4),
        "samples": len(db_samples),
        "db_peak_app_user_total": peak_total,
        "db_peak_app_user_active": peak_active,
        "db_peak_app_user_idle": peak_idle,
        "db_wait_buckets_peak": top_wait_buckets,
        "cpu_peak_process_percent": peak_proc_cpu,
        "cpu_avg_process_percent": avg_proc_cpu,
        "cpu_peak_system_percent": peak_sys_cpu,
        "cpu_avg_system_percent": avg_sys_cpu,
    }
    return result


def main() -> int:
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": "backend",
            "TENANT_API_KEY_HEADER": TENANT_HEADER,
            "DATABASE_URL": "postgresql://app_user:app_user@127.0.0.1:5432/r3_b04_phase3",
            "MIGRATION_DATABASE_URL": "postgresql://postgres:postgres@127.0.0.1:5432/r3_b04_phase3",
            "DATABASE_POOL_SIZE": "20",
            "DATABASE_MAX_OVERFLOW": "0",
            "DATABASE_POOL_TIMEOUT_SECONDS": "3",
            "DATABASE_POOL_TOTAL_CAP": "30",
            "INGESTION_FOLLOWUP_TASKS_ENABLED": "false",
        }
    )

    uvicorn_cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8020",
        "--workers",
        "2",
        "--no-access-log",
    ]

    UVICORN_LOG.write_text("", encoding="utf-8")
    UVICORN_ERR.write_text("", encoding="utf-8")
    stdout_f = open(UVICORN_LOG, "ab", buffering=0)
    stderr_f = open(UVICORN_ERR, "ab", buffering=0)
    proc = subprocess.Popen(uvicorn_cmd, cwd=str(BACKEND), env=env, stdout=stdout_f, stderr=stderr_f)
    try:
        asyncio.run(wait_ready())
        api_key, secret = asyncio.run(seed_tenant())
        max_connections = asyncio.run(get_postgres_max_connections())

        out: list[dict[str, Any]] = []

        phases = [
            ("async_keepalive_health_live", lambda: run_with_telemetry(bench_async_get("/health/live", 3000, 300, 300))),
            ("async_connection_close_health_live", lambda: run_with_telemetry(bench_async_get("/health/live", 1200, 150, 0))),
            ("async_keepalive_health_ready", lambda: run_with_telemetry(bench_async_get("/health/ready", 800, 80, 80))),
            ("async_keepalive_webhook_unique", lambda: run_with_telemetry(bench_webhook_unique(800, 80, api_key, secret))),
        ]

        for name, phase_coro_factory in phases:
            print(f"phase: {name}", flush=True)
            try:
                phase_result = asyncio.run(asyncio.wait_for(phase_coro_factory(), timeout=420))
                phase_result["phase"] = name
                out.append(phase_result)
            except Exception as exc:  # noqa: BLE001
                out.append(
                    {
                        "phase": name,
                        "error": str(exc),
                        "traceback": traceback.format_exc(limit=3),
                    }
                )

        print("phase: sync_loop_health_live", flush=True)
        out.append(bench_sync_get("/health/live", 400))

        print("PHYSICS_RESULTS_BEGIN")
        print(
            json.dumps(
                {
                    "runtime": {
                        "database_pool_size": int(env["DATABASE_POOL_SIZE"]),
                        "database_max_overflow": int(env["DATABASE_MAX_OVERFLOW"]),
                        "uvicorn_workers": 2,
                        "postgres_max_connections": int(max_connections),
                    },
                    "results": out,
                },
                indent=2,
            )
        )
        print("PHYSICS_RESULTS_END")
        return 0
    finally:
        stdout_f.close()
        stderr_f.close()
        try:
            proc.send_signal(signal.CTRL_BREAK_EVENT)
            proc.wait(timeout=10)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
