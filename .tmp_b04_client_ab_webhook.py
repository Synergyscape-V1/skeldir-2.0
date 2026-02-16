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

import httpx
import aiohttp
import asyncpg

ROOT = Path(r"c:\Users\ayewhy\II SKELDIR II")
BACKEND = ROOT / "backend"
BASE = "http://127.0.0.1:8041"
ADMIN_DSN = "postgresql://postgres:postgres@127.0.0.1:5432/r3_b04_phase3"
TENANT_HEADER = "X-Skeldir-Tenant-Key"


def sign(body: bytes, secret: str) -> str:
    ts = int(time.time())
    payload = f"{ts}.{body.decode()}".encode()
    sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


async def seed_tenant() -> tuple[str, str]:
    conn = await asyncpg.connect(ADMIN_DSN)
    try:
        tid = uuid.uuid5(uuid.NAMESPACE_URL, "b04-client-ab")
        api_key = f"b04_client_{tid}"
        api_hash = hashlib.sha256(api_key.encode()).hexdigest()
        secret = "b04_client_secret"
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
            str(tid), api_hash, "B04 Client AB", "b04_client@test.invalid", "s", secret, "p", "w"
        )
        return api_key, secret
    finally:
        await conn.close()


async def wait_ready():
    async with httpx.AsyncClient() as c:
        for _ in range(120):
            try:
                r = await c.get(BASE + "/health/live", timeout=2)
                if r.status_code == 200:
                    return
            except Exception:
                pass
            await asyncio.sleep(0.5)
    raise RuntimeError("server not ready")


def payload_for(i: int):
    key = str(uuid.uuid5(uuid.NAMESPACE_URL, f"b04-client-ab-{i}"))
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
    return key, b


async def run_httpx(n: int, conc: int, api_key: str, secret: str):
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
                key, b = payload_for(i)
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
        "client": "httpx",
        "n": n,
        "conc": conc,
        "seconds": round(dt, 4),
        "rps_ok": round(ok / dt, 2),
        "ok_200": ok,
        "non200": non200,
        "timeouts": timeouts,
        "request_errors": req_err,
        "p50_ms": round(q[49], 2) if q[49] else 0.0,
        "p95_ms": round(q[94], 2) if q[94] else 0.0,
        "p99_ms": round(q[98], 2) if q[98] else 0.0,
    }


async def run_aiohttp(n: int, conc: int, api_key: str, secret: str):
    sem = asyncio.Semaphore(conc)
    timeout = aiohttp.ClientTimeout(total=30)
    connector = aiohttp.TCPConnector(limit=conc, limit_per_host=conc, ttl_dns_cache=300, keepalive_timeout=30)
    url = BASE + "/api/webhooks/stripe/payment_intent/succeeded"
    lat = []
    timeouts = 0
    req_err = 0

    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as s:
        async def one(i: int):
            nonlocal timeouts, req_err
            async with sem:
                key, b = payload_for(i)
                headers = {
                    "Content-Type": "application/json",
                    TENANT_HEADER: api_key,
                    "X-Idempotency-Key": key,
                    "Stripe-Signature": sign(b, secret),
                    "X-Correlation-ID": str(uuid.uuid4()),
                }
                t = time.perf_counter()
                try:
                    async with s.post(url, data=b, headers=headers) as r:
                        await r.read()
                        lat.append((time.perf_counter() - t) * 1000)
                        return r.status
                except asyncio.TimeoutError:
                    timeouts += 1
                    return "timeout"
                except aiohttp.ClientError:
                    req_err += 1
                    return "request_error"

        t0 = time.perf_counter()
        codes = await asyncio.gather(*[one(i) for i in range(n)])
        dt = time.perf_counter() - t0

    q = statistics.quantiles(lat, n=100) if len(lat) >= 100 else [0] * 99
    ok = sum(1 for c in codes if isinstance(c, int) and c == 200)
    non200 = sum(1 for c in codes if isinstance(c, int) and c != 200)
    return {
        "client": "aiohttp",
        "n": n,
        "conc": conc,
        "seconds": round(dt, 4),
        "rps_ok": round(ok / dt, 2),
        "ok_200": ok,
        "non200": non200,
        "timeouts": timeouts,
        "request_errors": req_err,
        "p50_ms": round(q[49], 2) if q[49] else 0.0,
        "p95_ms": round(q[94], 2) if q[94] else 0.0,
        "p99_ms": round(q[98], 2) if q[98] else 0.0,
    }


async def main_async():
    api_key, secret = await seed_tenant()
    await wait_ready()
    h = await run_httpx(n=3000, conc=200, api_key=api_key, secret=secret)
    a = await run_aiohttp(n=3000, conc=200, api_key=api_key, secret=secret)
    out = {
        "httpx": h,
        "aiohttp": a,
        "delta_aiohttp_minus_httpx": {
            "seconds": round(a["seconds"] - h["seconds"], 4),
            "rps_ok": round(a["rps_ok"] - h["rps_ok"], 2),
            "p95_ms": round(a["p95_ms"] - h["p95_ms"], 2),
            "timeouts": a["timeouts"] - h["timeouts"],
        },
    }
    print(json.dumps(out, indent=2))


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
    cmd = [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8041", "--workers", "2", "--no-access-log"]
    proc = subprocess.Popen(cmd, cwd=str(BACKEND), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        asyncio.run(main_async())
    finally:
        try:
            proc.send_signal(signal.CTRL_BREAK_EVENT)
            proc.wait(timeout=10)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    main()
