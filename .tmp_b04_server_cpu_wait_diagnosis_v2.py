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
BASE = "http://127.0.0.1:8070"
ADMIN_DSN = "postgresql://postgres:postgres@127.0.0.1:5432/r3_b04_phase3"
TENANT_HEADER = "X-Skeldir-Tenant-Key"
OUT = ROOT / ".tmp_b04_server_cpu_wait_diagnosis_v2.log"


def sign(body: bytes, secret: str) -> str:
    ts = int(time.time())
    payload = f"{ts}.{body.decode()}".encode()
    sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


async def seed_tenant() -> tuple[str, str]:
    conn = await asyncpg.connect(ADMIN_DSN)
    try:
        tid = uuid.uuid5(uuid.NAMESPACE_URL, "b04-server-cpu-waits-v2")
        api_key = f"b04_server_v2_{tid}"
        api_hash = hashlib.sha256(api_key.encode()).hexdigest()
        secret = "b04_server_v2_secret"
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
            str(tid), api_hash, "B04 Server CPU V2", "b04_server_v2@test.invalid", "s", secret, "p", "w"
        )
        return api_key, secret
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
    raise RuntimeError("server readiness timeout")


def _worker_processes(master_pid: int) -> list[psutil.Process]:
    try:
        master = psutil.Process(master_pid)
    except psutil.Error:
        return []
    workers: list[psutil.Process] = []
    for child in master.children(recursive=True):
        try:
            if child.is_running():
                workers.append(child)
        except psutil.Error:
            continue
    return workers


async def sample_db(stop: dict[str, bool], out: list[dict[str, Any]]):
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
                SELECT COALESCE(wait_event_type,'None') as wait_event_type,
                       COALESCE(wait_event,'None') as wait_event,
                       count(*) as cnt
                FROM pg_stat_activity
                WHERE datname='r3_b04_phase3' AND usename='app_user'
                GROUP BY 1,2
                """
            )
            wb = {f"{w['wait_event_type']}:{w['wait_event']}": int(w['cnt']) for w in waits}
            out.append(
                {
                    "t": time.perf_counter(),
                    "app_total": int(row["app_total"]),
                    "app_active": int(row["app_active"]),
                    "app_idle": int(row["app_idle"]),
                    "wait_buckets": wb,
                }
            )
            await asyncio.sleep(0.2)
    finally:
        await conn.close()


def _cpu_time_snapshot(pids: list[int]) -> dict[int, float]:
    snap: dict[int, float] = {}
    for pid in pids:
        try:
            p = psutil.Process(pid)
            t = p.cpu_times()
            snap[pid] = float(t.user + t.system)
        except psutil.Error:
            continue
    return snap


async def run_with_telemetry(coro, master_pid: int):
    stop = {"stop": False}
    db_samples: list[dict[str, Any]] = []

    client_proc = psutil.Process(os.getpid())
    client_proc.cpu_percent(interval=None)

    client_cpu_samples: list[float] = []
    worker_cpu_samples: list[float] = []

    workers = _worker_processes(master_pid)
    worker_pids = [w.pid for w in workers]
    prev_t = time.perf_counter()
    prev_snap = _cpu_time_snapshot(worker_pids)

    async def sample_cpu():
        nonlocal prev_t, prev_snap, worker_pids
        while not stop["stop"]:
            client_cpu_samples.append(client_proc.cpu_percent(interval=None))

            current_workers = _worker_processes(master_pid)
            current_pids = [w.pid for w in current_workers]
            if set(current_pids) != set(worker_pids):
                worker_pids = current_pids
                prev_t = time.perf_counter()
                prev_snap = _cpu_time_snapshot(worker_pids)
                worker_cpu_samples.append(0.0)
                await asyncio.sleep(0.2)
                continue

            now_t = time.perf_counter()
            now_snap = _cpu_time_snapshot(worker_pids)
            dt = max(now_t - prev_t, 1e-6)
            cpu_time_delta = 0.0
            for pid in worker_pids:
                if pid in prev_snap and pid in now_snap:
                    cpu_time_delta += max(0.0, now_snap[pid] - prev_snap[pid])
            worker_cpu_samples.append((cpu_time_delta / dt) * 100.0)
            prev_t = now_t
            prev_snap = now_snap
            await asyncio.sleep(0.2)

    db_task = asyncio.create_task(sample_db(stop, db_samples))
    cpu_task = asyncio.create_task(sample_cpu())

    t0 = time.perf_counter()
    result = await coro
    elapsed = time.perf_counter() - t0

    stop["stop"] = True
    await asyncio.gather(db_task, cpu_task, return_exceptions=True)

    max_wait: dict[str, int] = {}
    for s in db_samples:
        for k, v in s["wait_buckets"].items():
            if v > max_wait.get(k, 0):
                max_wait[k] = v

    result["telemetry"] = {
        "elapsed_seconds": round(elapsed, 4),
        "samples": len(db_samples),
        "db_peak_app_user_total": max((s["app_total"] for s in db_samples), default=0),
        "db_peak_app_user_active": max((s["app_active"] for s in db_samples), default=0),
        "db_peak_app_user_idle": max((s["app_idle"] for s in db_samples), default=0),
        "db_wait_buckets_peak": dict(sorted(max_wait.items(), key=lambda kv: kv[1], reverse=True)[:10]),
        "db_wait_ClientRead_peak": max_wait.get("Client:ClientRead", 0),
        "db_wait_IO_XactSync_peak": max_wait.get("IO:XactSync", 0),
        "db_wait_Lock_tuple_peak": max_wait.get("Lock:tuple", 0),
        "db_wait_Lock_transactionid_peak": max_wait.get("Lock:transactionid", 0),
        "client_cpu_avg_percent": round(sum(client_cpu_samples) / len(client_cpu_samples), 2) if client_cpu_samples else 0.0,
        "client_cpu_peak_percent": round(max(client_cpu_samples), 2) if client_cpu_samples else 0.0,
        "server_workers_cpu_avg_percent": round(sum(worker_cpu_samples) / len(worker_cpu_samples), 2) if worker_cpu_samples else 0.0,
        "server_workers_cpu_peak_percent": round(max(worker_cpu_samples), 2) if worker_cpu_samples else 0.0,
        "worker_pid_count": len(worker_pids),
    }
    return result


async def bench_health_live(n: int, conc: int):
    sem = asyncio.Semaphore(conc)
    limits = httpx.Limits(max_connections=conc, max_keepalive_connections=conc)
    lat = []
    async with httpx.AsyncClient(limits=limits) as c:
        async def one(_i: int):
            async with sem:
                t = time.perf_counter()
                r = await c.get(BASE + "/health/live", timeout=30)
                lat.append((time.perf_counter() - t) * 1000)
                return r.status_code
        t0 = time.perf_counter()
        codes = await asyncio.gather(*[one(i) for i in range(n)])
        dt = time.perf_counter() - t0
    q = statistics.quantiles(lat, n=100) if len(lat) >= 100 else [0] * 99
    return {
        "phase": "health_live_keepalive",
        "n": n,
        "conc": conc,
        "seconds": round(dt, 4),
        "rps": round(n / dt, 2),
        "non200": sum(1 for c in codes if c != 200),
        "lat_ms_p50": round(q[49], 2) if q[49] else 0.0,
        "lat_ms_p95": round(q[94], 2) if q[94] else 0.0,
        "lat_ms_p99": round(q[98], 2) if q[98] else 0.0,
    }


async def bench_webhook_unique(n: int, conc: int, api_key: str, secret: str):
    sem = asyncio.Semaphore(conc)
    limits = httpx.Limits(max_connections=conc, max_keepalive_connections=conc)
    url = BASE + "/api/webhooks/stripe/payment_intent/succeeded"
    lat = []
    timeouts = 0
    req_err = 0

    async with httpx.AsyncClient(limits=limits) as c:
        async def one(i: int):
            nonlocal timeouts, req_err
            async with sem:
                key = str(uuid.uuid5(uuid.NAMESPACE_URL, f"b04-server-v2-key-{i}"))
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
                    timeouts += 1
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
        "phase": "webhook_unique_keepalive",
        "n": n,
        "conc": conc,
        "seconds": round(dt, 4),
        "rps_ok": round(ok / dt, 2),
        "ok_200": ok,
        "non200": non200,
        "timeouts": timeouts,
        "request_errors": req_err,
        "lat_ms_p50": round(q[49], 2) if q[49] else 0.0,
        "lat_ms_p95": round(q[94], 2) if q[94] else 0.0,
        "lat_ms_p99": round(q[98], 2) if q[98] else 0.0,
    }


def main():
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

    cmd = [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8070", "--workers", "2", "--no-access-log"]
    proc = subprocess.Popen(cmd, cwd=str(BACKEND), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        asyncio.run(wait_ready())
        api_key, secret = asyncio.run(seed_tenant())

        health = asyncio.run(run_with_telemetry(bench_health_live(2000, 200), proc.pid))
        webhook = asyncio.run(run_with_telemetry(bench_webhook_unique(1200, 120, api_key, secret), proc.pid))

        out = {
            "runtime": {
                "uvicorn_workers": 2,
                "database_pool_size": 20,
                "database_max_overflow": 0,
                "database_pool_timeout_seconds": 3,
                "database_pool_total_cap": 30,
                "health_client_concurrency": 200,
                "webhook_client_concurrency": 120,
            },
            "results": [health, webhook],
        }
        OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
        print("B04_SERVER_CPU_WAIT_DIAG_V2_BEGIN")
        print(json.dumps(out, indent=2))
        print("B04_SERVER_CPU_WAIT_DIAG_V2_END")
    finally:
        try:
            proc.send_signal(signal.CTRL_BREAK_EVENT)
            proc.wait(timeout=10)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    main()
