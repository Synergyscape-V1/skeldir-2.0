"""
R3 — Ingestion Under Fire (Idempotency + DLQ + PII)

Adversarial harness that drives real HTTP webhook ingestion endpoints and then
cross-checks truth in Postgres (canonical tables + DLQ) with deterministic seeds.

This script is intentionally browser-verifiable via stdout: it prints scenario
verdict blocks and post-run DB truth queries (counts + duplicates + PII scans).
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import math
import multiprocessing as mp
import os
import platform
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse
from uuid import NAMESPACE_URL, UUID, uuid5

import asyncpg
import httpx


PII_KEYS = [
    "email",
    "email_address",
    "phone",
    "phone_number",
    "ssn",
    "social_security_number",
    "ip",
    "ip_address",
    "first_name",
    "last_name",
    "full_name",
    "address",
    "street_address",
    "billing_address",
    "shipping_address",
    "receipt_email",
    "customer_email",
    "customer_phone",
]

# ---------------------------------------------------------------------------
# CPU-aware resource reservation (Phase 3 EG3.4)
# ---------------------------------------------------------------------------
_DETECTED_CORES = os.cpu_count() or 2
# Loadgen: max 2 workers; always reserve >= 2 cores for server + DB
_LOADGEN_WORKERS = max(1, min(_DETECTED_CORES - 2, 2))
# Server workers: fill remaining minus 1 reserved for DB
_SERVER_WORKERS = max(2, _DETECTED_CORES - _LOADGEN_WORKERS - 1)
_MP_START_METHOD = "spawn"


def _env(name: str, default: str | None = None) -> str:
    value = os.getenv(name)
    if value is None or value == "":
        if default is None:
            raise RuntimeError(f"Missing required env var: {name}")
        return default
    return value


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _uuid_deterministic(*parts: str) -> UUID:
    return uuid5(NAMESPACE_URL, ":".join(parts))


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def sign_stripe(body: bytes, secret: str) -> str:
    ts = int(_now_utc().timestamp())
    signed_payload = f"{ts}.{body.decode('utf-8')}".encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


@dataclass(frozen=True)
class TenantSeed:
    tenant_id: UUID
    api_key: str
    api_key_hash: str
    secrets: dict[str, str]


@dataclass(frozen=True)
class ScenarioResult:
    name: str
    passed: bool
    http_status_counts: dict[str, int]
    http_timeouts: int
    http_connection_errors: int
    db: dict[str, Any]


@dataclass(frozen=True)
class PerfGateProfile:
    name: str
    target_rps: float
    duration_s: int
    p95_max_ms: float
    enforce_no_degradation: bool = False


async def _pg_connect(database_url: str) -> asyncpg.Connection:
    return await asyncpg.connect(database_url)


async def _pg_connect_with_retry(database_url: str, *, attempts: int = 5, delay_s: float = 1.0) -> asyncpg.Connection:
    last_exc: Exception | None = None
    for _ in range(attempts):
        try:
            return await _pg_connect(database_url)
        except Exception as exc:  # noqa: BLE001 - retryable connection failures
            last_exc = exc
            await asyncio.sleep(delay_s)
    raise RuntimeError(f"Failed to connect to Postgres after {attempts} attempts: {last_exc}")

async def _set_tenant_context(conn: asyncpg.Connection, tenant_id: UUID) -> None:
    await conn.execute(
        "SELECT set_config('app.current_tenant_id', $1, false)",
        str(tenant_id),
    )


async def seed_tenant(conn: asyncpg.Connection, seed: TenantSeed) -> None:
    await conn.execute(
        """
        INSERT INTO tenants (
          id, api_key_hash, name, notification_email,
          shopify_webhook_secret, stripe_webhook_secret,
          paypal_webhook_secret, woocommerce_webhook_secret,
          created_at, updated_at
        )
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,NOW(),NOW())
        ON CONFLICT (id) DO NOTHING
        """,
        str(seed.tenant_id),
        seed.api_key_hash,
        f"R3 Tenant {str(seed.tenant_id)[:8]}",
        f"r3_{str(seed.tenant_id)[:8]}@test.invalid",
        seed.secrets["shopify"],
        seed.secrets["stripe"],
        seed.secrets["paypal"],
        seed.secrets["woocommerce"],
    )


async def seed_channel_taxonomy(conn: asyncpg.Connection) -> None:
    # Must match backend/app/ingestion/channel_normalization.get_valid_taxonomy_codes()
    rows = [
        ("unknown", "unknown", False, "Unknown"),
        ("direct", "direct", False, "Direct"),
        ("email", "email", False, "Email"),
        ("facebook_brand", "paid_social", True, "Facebook Brand"),
        ("facebook_paid", "paid_social", True, "Facebook Paid"),
        ("google_display_paid", "paid_search", True, "Google Display Paid"),
        ("google_search_paid", "paid_search", True, "Google Search Paid"),
        ("organic", "organic", False, "Organic"),
        ("referral", "referral", False, "Referral"),
        ("tiktok_paid", "paid_social", True, "TikTok Paid"),
    ]
    for code, family, is_paid, display_name in rows:
        await conn.execute(
            """
            INSERT INTO channel_taxonomy (code, family, is_paid, display_name, is_active, state, created_at)
            VALUES ($1,$2,$3,$4,TRUE,'active',NOW())
            ON CONFLICT (code) DO NOTHING
            """,
            code,
            family,
            is_paid,
            display_name,
        )


async def _http_fire(
    client: httpx.AsyncClient,
    requests: list[tuple[str, dict[str, str], bytes]],
    concurrency: int,
    timeout_s: float,
) -> tuple[dict[str, int], int, int]:
    sem = asyncio.Semaphore(concurrency)
    status_counts: dict[str, int] = {}
    timeouts = 0
    connection_errors = 0
    recovered_request_errors = 0

    async def _one(url: str, headers: dict[str, str], body: bytes) -> None:
        nonlocal timeouts, connection_errors, recovered_request_errors
        async with sem:
            transient_request_error = False
            for attempt in range(3):
                try:
                    resp = await client.post(url, content=body, headers=headers, timeout=timeout_s)
                    if 500 <= resp.status_code <= 599 and attempt < 2:
                        await asyncio.sleep(0.05 * (attempt + 1))
                        continue
                    key = str(resp.status_code)
                    status_counts[key] = status_counts.get(key, 0) + 1
                    if transient_request_error:
                        recovered_request_errors += 1
                        status_counts["request_error_recovered"] = status_counts.get("request_error_recovered", 0) + 1
                    return
                except (httpx.TimeoutException, asyncio.TimeoutError):
                    timeouts += 1
                    status_counts["timeout"] = status_counts.get("timeout", 0) + 1
                    return
                except httpx.RequestError:
                    transient_request_error = True
                    if attempt < 2:
                        await asyncio.sleep(0.05 * (attempt + 1))
                        continue
                    connection_errors += 1
                    status_counts["request_error"] = status_counts.get("request_error", 0) + 1
                    return

    await asyncio.gather(*[_one(url, headers, body) for (url, headers, body) in requests])
    return status_counts, timeouts, connection_errors


async def _http_fire_rate_controlled(
    client: httpx.AsyncClient,
    requests: list[tuple[str, dict[str, str], bytes]],
    *,
    concurrency: int,
    timeout_s: float,
    target_rps: float,
    duration_s: int,
) -> tuple[dict[str, int], int, int, list[float], float, int]:
    if not requests:
        raise RuntimeError("Rate-controlled fire requires at least one request template.")
    if target_rps <= 0:
        raise RuntimeError("target_rps must be > 0.")
    if duration_s <= 0:
        raise RuntimeError("duration_s must be > 0.")

    sem = asyncio.Semaphore(concurrency)
    status_counts: dict[str, int] = {}
    timeouts = 0
    connection_errors = 0
    latencies_ms: list[float] = []
    total_requests = max(1, int(round(target_rps * duration_s)))

    async def _one(url: str, headers: dict[str, str], body: bytes) -> None:
        nonlocal timeouts, connection_errors
        async with sem:
            transient_request_error = False
            for attempt in range(3):
                request_started = time.perf_counter()
                try:
                    resp = await client.post(url, content=body, headers=headers, timeout=timeout_s)
                    if 500 <= resp.status_code <= 599 and attempt < 2:
                        await asyncio.sleep(0.05 * (attempt + 1))
                        continue
                    latencies_ms.append((time.perf_counter() - request_started) * 1000.0)
                    key = str(resp.status_code)
                    status_counts[key] = status_counts.get(key, 0) + 1
                    if transient_request_error:
                        status_counts["request_error_recovered"] = status_counts.get("request_error_recovered", 0) + 1
                    return
                except (httpx.TimeoutException, asyncio.TimeoutError):
                    timeouts += 1
                    status_counts["timeout"] = status_counts.get("timeout", 0) + 1
                    return
                except httpx.RequestError:
                    transient_request_error = True
                    if attempt < 2:
                        await asyncio.sleep(0.05 * (attempt + 1))
                        continue
                    connection_errors += 1
                    status_counts["request_error"] = status_counts.get("request_error", 0) + 1
                    return

    started = time.perf_counter()
    tasks: list[asyncio.Task[None]] = []
    for i in range(total_requests):
        scheduled_at = started + (i / target_rps)
        delay_s = scheduled_at - time.perf_counter()
        if delay_s > 0:
            await asyncio.sleep(delay_s)
        url, headers, body = requests[i % len(requests)]
        tasks.append(asyncio.create_task(_one(url, headers, body)))

    await asyncio.gather(*tasks)
    elapsed_s = time.perf_counter() - started
    return status_counts, timeouts, connection_errors, latencies_ms, elapsed_s, total_requests


async def _wait_for_http_ready(
    client: httpx.AsyncClient,
    base_url: str,
    *,
    attempts: int = 60,
    delay_s: float = 1.0,
) -> None:
    last_status = None
    for _ in range(attempts):
        try:
            resp = await client.get(f"{base_url}/health/ready", timeout=5)
            last_status = resp.status_code
            if resp.status_code == 200:
                return
        except httpx.RequestError:
            last_status = "request_error"
        await asyncio.sleep(delay_s)
    raise RuntimeError(f"API readiness check failed; last_status={last_status}")


def _verdict_block(name: str, payload: dict[str, Any]) -> None:
    print(f"R3_VERDICT_BEGIN {name}")
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(f"R3_VERDICT_END {name}")


def _parse_int_list(csv: str) -> list[int]:
    out: list[int] = []
    for part in [p.strip() for p in csv.split(",") if p.strip()]:
        out.append(int(part))
    return out


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    if pct <= 0:
        return min(values)
    if pct >= 100:
        return max(values)
    ordered = sorted(values)
    rank = math.ceil((pct / 100.0) * len(ordered)) - 1
    rank = max(0, min(rank, len(ordered) - 1))
    return ordered[rank]


def _database_name_from_dsn(dsn: str) -> str:
    parsed = urlparse(dsn)
    path = (parsed.path or "").strip("/")
    if path:
        return path.split("/")[-1]
    # Fallback for non-standard DSNs that still include /dbname.
    if "/" in dsn:
        return dsn.split("?", 1)[0].rsplit("/", 1)[-1]
    return ""


def _http_error_count(status_counts: dict[str, int]) -> int:
    errors = 0
    for code, count in status_counts.items():
        if code == "request_error_recovered":
            continue
        if code.isdigit():
            if not (200 <= int(code) <= 299):
                errors += count
            continue
        errors += count
    return errors


def _http_observed_count(status_counts: dict[str, int]) -> int:
    observed = 0
    for code, count in status_counts.items():
        if code == "request_error_recovered":
            continue
        observed += count
    return int(observed)


async def db_count_canonical_for_key(conn: asyncpg.Connection, tenant_id: UUID, key: str) -> int:
    await _set_tenant_context(conn, tenant_id)
    return int(
        await conn.fetchval(
            "SELECT COUNT(*) FROM attribution_events WHERE tenant_id=$1 AND idempotency_key=$2",
            str(tenant_id),
            key,
        )
    )


async def db_count_dlq_for_key(conn: asyncpg.Connection, tenant_id: UUID, key: str) -> int:
    await _set_tenant_context(conn, tenant_id)
    return int(
        await conn.fetchval(
            "SELECT COUNT(*) FROM dead_events WHERE tenant_id=$1 AND raw_payload->>'idempotency_key'=$2",
            str(tenant_id),
            key,
        )
    )


async def db_count_canonical_for_keys(
    conn: asyncpg.Connection, tenant_id: UUID, keys: list[str]
) -> int:
    if not keys:
        return 0
    await _set_tenant_context(conn, tenant_id)
    return int(
        await conn.fetchval(
            "SELECT COUNT(*) FROM attribution_events WHERE tenant_id=$1 AND idempotency_key = ANY($2::text[])",
            str(tenant_id),
            keys,
        )
    )


async def db_count_dlq_for_keys(conn: asyncpg.Connection, tenant_id: UUID, keys: list[str]) -> int:
    if not keys:
        return 0
    await _set_tenant_context(conn, tenant_id)
    return int(
        await conn.fetchval(
            "SELECT COUNT(*) FROM dead_events WHERE tenant_id=$1 AND raw_payload->>'idempotency_key' = ANY($2::text[])",
            str(tenant_id),
            keys,
        )
    )


async def db_channel_for_key(conn: asyncpg.Connection, tenant_id: UUID, key: str) -> str | None:
    await _set_tenant_context(conn, tenant_id)
    row = await conn.fetchrow(
        """
        SELECT channel
        FROM attribution_events
        WHERE tenant_id=$1 AND idempotency_key=$2
        ORDER BY created_at DESC
        LIMIT 1
        """,
        str(tenant_id),
        key,
    )
    if not row:
        return None
    return str(row["channel"])


async def db_pii_key_hits_since(
    conn: asyncpg.Connection, since_utc: datetime, tenant_ids: list[UUID]
) -> dict[str, int]:
    clauses = " OR ".join([f"jsonb_path_exists(raw_payload, '$.**.{k}')" for k in PII_KEYS])
    canonical_hits = 0
    dlq_hits = 0
    for tenant_id in tenant_ids:
        await _set_tenant_context(conn, tenant_id)
        canonical_hits += int(
            await conn.fetchval(
                f"""
                SELECT COUNT(*) FROM attribution_events
                WHERE created_at >= $1 AND tenant_id = $2 AND ({clauses})
                """,
                since_utc,
                str(tenant_id),
            )
        )
        dlq_hits += int(
            await conn.fetchval(
                f"""
                SELECT COUNT(*) FROM dead_events
                WHERE ingested_at >= $1 AND tenant_id = $2 AND ({clauses})
                """,
                since_utc,
                str(tenant_id),
            )
        )
    return {
        "attribution_events_raw_payload_hits": canonical_hits,
        "dead_events_raw_payload_hits": dlq_hits,
    }


async def db_pii_key_hits_between(
    conn: asyncpg.Connection,
    start_utc: datetime,
    end_utc: datetime,
    tenant_ids: list[UUID],
) -> dict[str, int]:
    clauses = " OR ".join([f"jsonb_path_exists(raw_payload, '$.**.{k}')" for k in PII_KEYS])
    canonical_hits = 0
    dlq_hits = 0
    for tenant_id in tenant_ids:
        await _set_tenant_context(conn, tenant_id)
        canonical_hits += int(
            await conn.fetchval(
                f"""
                SELECT COUNT(*) FROM attribution_events
                WHERE created_at >= $1 AND created_at <= $2 AND tenant_id = $3 AND ({clauses})
                """,
                start_utc,
                end_utc,
                str(tenant_id),
            )
        )
        dlq_hits += int(
            await conn.fetchval(
                f"""
                SELECT COUNT(*) FROM dead_events
                WHERE ingested_at >= $1 AND ingested_at <= $2 AND tenant_id = $3 AND ({clauses})
                """,
                start_utc,
                end_utc,
                str(tenant_id),
            )
        )
    return {
        "attribution_events_raw_payload_hits": canonical_hits,
        "dead_events_raw_payload_hits": dlq_hits,
    }


async def db_window_totals(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    start_utc: datetime,
    end_utc: datetime,
) -> dict[str, int]:
    await _set_tenant_context(conn, tenant_id)
    canonical_total = int(
        await conn.fetchval(
            """
            SELECT COUNT(*) FROM attribution_events
            WHERE tenant_id = $1 AND created_at >= $2 AND created_at <= $3
            """,
            str(tenant_id),
            start_utc,
            end_utc,
        )
    )
    dlq_total = int(
        await conn.fetchval(
            """
            SELECT COUNT(*) FROM dead_events
            WHERE tenant_id = $1 AND ingested_at >= $2 AND ingested_at <= $3
            """,
            str(tenant_id),
            start_utc,
            end_utc,
        )
    )
    return {
        "window_canonical_rows": canonical_total,
        "window_dlq_rows": dlq_total,
    }


async def db_duplicate_canonical_keys_between(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    start_utc: datetime,
    end_utc: datetime,
) -> int:
    await _set_tenant_context(conn, tenant_id)
    return int(
        await conn.fetchval(
            """
            SELECT COUNT(*) FROM (
              SELECT idempotency_key
              FROM attribution_events
              WHERE tenant_id = $1
                AND created_at >= $2
                AND created_at <= $3
              GROUP BY idempotency_key
              HAVING COUNT(*) > 1
            ) duplicates
            """,
            str(tenant_id),
            start_utc,
            end_utc,
        )
    )


async def db_connection_snapshot(conn: asyncpg.Connection, database_name: str) -> dict[str, int]:
    row = await conn.fetchrow(
        """
        SELECT
          COUNT(*)::int AS total_connections,
          COUNT(*) FILTER (WHERE state = 'active')::int AS active_connections,
          COUNT(*) FILTER (
            WHERE state = 'active'
              AND wait_event_type IN ('Lock', 'LWLock', 'IO', 'IPC', 'BufferPin')
          )::int AS waiting_connections,
          COUNT(*) FILTER (WHERE usename = 'app_user')::int AS app_user_connections
        FROM pg_stat_activity
        WHERE datname = $1
        """,
        database_name,
    )
    max_connections = int(await conn.fetchval("SHOW max_connections"))
    return {
        "total_connections": int(row["total_connections"]) if row else 0,
        "active_connections": int(row["active_connections"]) if row else 0,
        "waiting_connections": int(row["waiting_connections"]) if row else 0,
        "app_user_connections": int(row["app_user_connections"]) if row else 0,
        "max_connections": max_connections,
    }


def build_stripe_payment_intent_body(
    *,
    event_id: str,
    payment_intent_id: str | None,
    amount_cents: int | None,
    currency: str | None,
    created_epoch: Any,
    include_pii: bool,
) -> bytes:
    body: dict[str, Any] = {
        "id": event_id,
        "type": "payment_intent.succeeded",
        "created": created_epoch,
        "data": {
            "object": {
                "id": payment_intent_id,
                "amount": amount_cents,
                "currency": currency,
                "status": "succeeded",
            }
        },
    }
    if include_pii:
        body["email"] = "pii_user@test.invalid"
        body["ip_address"] = "203.0.113.99"
        body["data"]["object"]["receipt_email"] = "receipt@test.invalid"
        body["data"]["object"]["billing_details"] = {"email": "bill@test.invalid", "name": "Test User"}
    return json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _make_headers_for_stripe(
    *,
    tenant_api_key_header: str,
    tenant_api_key: str,
    stripe_secret: str,
    correlation_id: UUID,
    idempotency_key: str,
    body: bytes,
) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-Correlation-ID": str(correlation_id),
        tenant_api_key_header: tenant_api_key,
        "X-Idempotency-Key": idempotency_key,
        "Stripe-Signature": sign_stripe(body, stripe_secret),
    }


def _keys_for_scenario(candidate_sha: str, scenario: str, n: int) -> list[str]:
    return [str(_uuid_deterministic("r3", candidate_sha, scenario, str(i))) for i in range(n)]


# ============================================================================
# Phase 0 - Null Benchmark (measurement validity calibration)
# ============================================================================

async def _null_stub_server_handler(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
) -> None:
    try:
        await reader.readuntil(b"\r\n\r\n")
    except (asyncio.IncompleteReadError, ConnectionResetError):
        writer.close()
        return
    writer.write(
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: application/json\r\n"
        b"Content-Length: 15\r\n"
        b"Connection: keep-alive\r\n"
        b"\r\n"
        b'{"status":"ok"}'
    )
    try:
        await writer.drain()
    except ConnectionResetError:
        pass
    writer.close()


async def run_null_benchmark_gate(
    *,
    client: httpx.AsyncClient,
    timeout_s: float,
    concurrency: int,
    target_rps: float,
    duration_s: int,
    min_rps: float,
    stub_port: int = 9999,
) -> ScenarioResult:
    server = await asyncio.start_server(_null_stub_server_handler, "127.0.0.1", stub_port)
    try:
        request_templates = [(
            f"http://127.0.0.1:{stub_port}/",
            {"Content-Type": "application/json"},
            b"{}",
        )]
        status_counts, timeouts, conn_errors, latencies_ms, elapsed_s, target_request_count = await _http_fire_rate_controlled(
            client,
            request_templates,
            concurrency=concurrency,
            timeout_s=timeout_s,
            target_rps=target_rps,
            duration_s=duration_s,
        )
    finally:
        server.close()
        await server.wait_closed()

    # Treat sub-second scheduler drift as timing jitter, not throughput regression.
    # This keeps EG3.5 stable under CI clock noise while still failing on real slowdowns.
    jitter_allowance_s = max(0.05, float(duration_s) * 0.002)
    effective_elapsed_s = elapsed_s
    if elapsed_s > 0 and elapsed_s <= (float(duration_s) + jitter_allowance_s):
        effective_elapsed_s = float(duration_s)

    achieved_rps = target_request_count / effective_elapsed_s if effective_elapsed_s > 0 else 0.0
    p50_ms = _percentile(latencies_ms, 50)
    p95_ms = _percentile(latencies_ms, 95)
    http_errors = _http_error_count(status_counts)
    observed_count = _http_observed_count(status_counts)
    measurement_valid = (
        achieved_rps >= min_rps
        and observed_count == target_request_count
        and http_errors == 0
        and timeouts == 0
        and conn_errors == 0
    )
    return ScenarioResult(
        name="EG3_5_NullBenchmark",
        passed=measurement_valid,
        http_status_counts=status_counts,
        http_timeouts=timeouts,
        http_connection_errors=conn_errors,
        db={
            "measurement_valid": measurement_valid,
            "reason": "ok" if measurement_valid else "invalid_measurement_environment",
            "duration_s": duration_s,
            "target_rps": target_rps,
            "minimum_required_rps": min_rps,
            "target_request_count": target_request_count,
            "observed_request_count": observed_count,
            "elapsed_s": round(elapsed_s, 4),
            "effective_elapsed_s": round(effective_elapsed_s, 4),
            "jitter_allowance_s": round(jitter_allowance_s, 4),
            "achieved_rps": round(achieved_rps, 3),
            "latency_p50_ms": round(p50_ms, 3) if p50_ms is not None else None,
            "latency_p95_ms": round(p95_ms, 3) if p95_ms is not None else None,
            "http_error_count": http_errors,
            "http_timeout_count": timeouts,
            "http_connection_errors": conn_errors,
            "client_stack": "httpx.AsyncClient",
            "concurrency_model": "asyncio-semaphore",
        },
    )


# ============================================================================
# Phase 1 - Legacy S8 generator infrastructure (retained for deterministic payload assembly)
# ============================================================================

@dataclass(frozen=True)
class S8WorkerConfig:
    """Compact config passed to each S8 child process (< 1KB serialised).

    Workers reconstruct request payloads internally using the existing
    deterministic helpers — no large request blobs cross the IPC boundary.
    """
    worker_id: int
    base_url: str
    tenant_api_key_header: str
    tenant_api_key: str
    stripe_secret: str
    tenant_id: str              # str(UUID) for pickle safety
    name: str                   # scenario name for key derivation
    run_start_epoch: int
    concurrency: int            # per-worker concurrency
    timeout_s: float
    # Key assignments for this worker
    replay_key: str
    replay_count: int           # this worker's share of duplicate requests
    unique_keys: list
    malformed_keys: list
    pii_keys: list


def _build_s8_requests_from_config(
    cfg: S8WorkerConfig,
) -> list[tuple[str, dict[str, str], bytes]]:
    """Reconstruct (url, headers, body) tuples from compact config.

    Uses the same deterministic helpers as the original S8 builder —
    guarantees identical payloads regardless of worker partition.
    """
    url = f"{cfg.base_url}/api/webhooks/stripe/payment_intent/succeeded"
    reqs: list[tuple[str, dict[str, str], bytes]] = []

    # Replay / duplicate requests
    if cfg.replay_count > 0:
        replay_body = build_stripe_payment_intent_body(
            event_id=f"evt_{cfg.replay_key.replace('-', '')[:16]}",
            payment_intent_id=f"pi_{cfg.replay_key.replace('-', '')[:16]}",
            amount_cents=101,
            currency="usd",
            created_epoch=cfg.run_start_epoch,
            include_pii=False,
        )
        replay_headers = _make_headers_for_stripe(
            tenant_api_key_header=cfg.tenant_api_key_header,
            tenant_api_key=cfg.tenant_api_key,
            stripe_secret=cfg.stripe_secret,
            correlation_id=_uuid_deterministic(
                "r3", cfg.name, cfg.tenant_id, cfg.replay_key
            ),
            idempotency_key=cfg.replay_key,
            body=replay_body,
        )
        for _ in range(cfg.replay_count):
            reqs.append((url, replay_headers, replay_body))

    # Unique valid requests
    for key in cfg.unique_keys:
        correlation_id = _uuid_deterministic("r3", cfg.name, cfg.tenant_id, key)
        body = build_stripe_payment_intent_body(
            event_id=f"evt_{key.replace('-', '')[:16]}",
            payment_intent_id=f"pi_{key.replace('-', '')[:16]}",
            amount_cents=111,
            currency="usd",
            created_epoch=cfg.run_start_epoch,
            include_pii=False,
        )
        headers = _make_headers_for_stripe(
            tenant_api_key_header=cfg.tenant_api_key_header,
            tenant_api_key=cfg.tenant_api_key,
            stripe_secret=cfg.stripe_secret,
            correlation_id=correlation_id,
            idempotency_key=key,
            body=body,
        )
        reqs.append((url, headers, body))

    # Malformed requests
    for key in cfg.malformed_keys:
        correlation_id = _uuid_deterministic("r3", cfg.name, cfg.tenant_id, key)
        body = build_stripe_payment_intent_body(
            event_id=f"evt_{key.replace('-', '')[:16]}",
            payment_intent_id=None,
            amount_cents=None,
            currency="usd",
            created_epoch="not_an_int",
            include_pii=False,
        )
        headers = _make_headers_for_stripe(
            tenant_api_key_header=cfg.tenant_api_key_header,
            tenant_api_key=cfg.tenant_api_key,
            stripe_secret=cfg.stripe_secret,
            correlation_id=correlation_id,
            idempotency_key=key,
            body=body,
        )
        reqs.append((url, headers, body))

    # PII requests
    for key in cfg.pii_keys:
        correlation_id = _uuid_deterministic("r3", cfg.name, cfg.tenant_id, key)
        body = build_stripe_payment_intent_body(
            event_id=f"evt_{key.replace('-', '')[:16]}",
            payment_intent_id=f"pi_{key.replace('-', '')[:16]}",
            amount_cents=131,
            currency="usd",
            created_epoch=cfg.run_start_epoch,
            include_pii=True,
        )
        headers = _make_headers_for_stripe(
            tenant_api_key_header=cfg.tenant_api_key_header,
            tenant_api_key=cfg.tenant_api_key,
            stripe_secret=cfg.stripe_secret,
            correlation_id=correlation_id,
            idempotency_key=key,
            body=body,
        )
        reqs.append((url, headers, body))

    # Deterministic shuffle (same as original S8)
    reqs.sort(
        key=lambda r: hashlib.sha256(
            r[1]["X-Idempotency-Key"].encode("utf-8")
        ).hexdigest()
    )
    return reqs


def _s8_worker_entry(
    cfg: S8WorkerConfig,
    result_queue: "mp.Queue[dict]",
) -> None:
    """S8 child process entry point.

    Builds payloads from config, fires via _http_fire, reports results.
    Runs in a *spawned* process — own GIL, own event loop, fresh interpreter.
    """

    async def _run() -> None:
        reqs = _build_s8_requests_from_config(cfg)
        limits = httpx.Limits(
            max_connections=cfg.concurrency,
            max_keepalive_connections=cfg.concurrency,
        )
        async with httpx.AsyncClient(limits=limits) as client:
            status_counts, timeouts, conn_errors = await _http_fire(
                client, reqs, concurrency=cfg.concurrency, timeout_s=cfg.timeout_s
            )
        result_queue.put({
            "worker_id": cfg.worker_id,
            "status_counts": status_counts,
            "timeouts": timeouts,
            "conn_errors": conn_errors,
        })

    asyncio.run(_run())


def _slice_list(lst: list, num_chunks: int) -> list[list]:
    """Partition a list into num_chunks roughly-equal slices."""
    if not lst:
        return [[] for _ in range(num_chunks)]
    chunk_size = len(lst) // num_chunks
    remainder = len(lst) % num_chunks
    slices: list[list] = []
    start = 0
    for i in range(num_chunks):
        end = start + chunk_size + (1 if i < remainder else 0)
        slices.append(lst[start:end])
        start = end
    return slices


def _s8_multiprocess_fire(
    configs: list[S8WorkerConfig],
) -> tuple[dict[str, int], int, int]:
    """Spawn N child processes, each running _s8_worker_entry.

    Returns aggregated (status_counts, timeouts, conn_errors).
    """
    result_queue: mp.Queue = mp.Queue()
    procs: list[mp.Process] = []
    for cfg in configs:
        p = mp.Process(target=_s8_worker_entry, args=(cfg, result_queue))
        procs.append(p)

    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=120)

    merged_status: dict[str, int] = {}
    total_timeouts = 0
    total_conn_errors = 0
    for _ in range(len(configs)):
        try:
            r = result_queue.get(timeout=5)
            for k, v in r["status_counts"].items():
                merged_status[k] = merged_status.get(k, 0) + v
            total_timeouts += r["timeouts"]
            total_conn_errors += r["conn_errors"]
        except Exception:
            # Worker crashed — count as total failure
            merged_status["worker_crash"] = merged_status.get("worker_crash", 0) + 1

    return merged_status, total_timeouts, total_conn_errors


async def scenario_s1_replay_storm(
    *,
    name: str,
    client: httpx.AsyncClient,
    base_url: str,
    tenant: TenantSeed,
    tenant_api_key_header: str,
    n: int,
    concurrency: int,
    timeout_s: float,
    run_start_utc: datetime,
    conn: asyncpg.Connection,
    idempotency_key: str,
) -> ScenarioResult:
    correlation_id = _uuid_deterministic("r3", name, str(tenant.tenant_id), idempotency_key)
    body = build_stripe_payment_intent_body(
        event_id=f"evt_{idempotency_key.replace('-', '')[:16]}",
        payment_intent_id=f"pi_{idempotency_key.replace('-', '')[:16]}",
        amount_cents=19999,
        currency="usd",
        created_epoch=int(run_start_utc.timestamp()),
        include_pii=False,
    )
    url = f"{base_url}/api/webhooks/stripe/payment_intent/succeeded"
    headers = _make_headers_for_stripe(
        tenant_api_key_header=tenant_api_key_header,
        tenant_api_key=tenant.api_key,
        stripe_secret=tenant.secrets["stripe"],
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        body=body,
    )
    reqs = [(url, headers, body) for _ in range(n)]
    status_counts, timeouts, conn_errors = await _http_fire(
        client, reqs, concurrency=concurrency, timeout_s=timeout_s
    )

    canonical = await db_count_canonical_for_key(conn, tenant.tenant_id, idempotency_key)
    dlq = await db_count_dlq_for_key(conn, tenant.tenant_id, idempotency_key)
    http_5xx = sum(v for k, v in status_counts.items() if k.isdigit() and 500 <= int(k) <= 599)

    passed = canonical == 1 and dlq == 0 and http_5xx == 0 and timeouts == 0 and conn_errors == 0
    return ScenarioResult(
        name=name,
        passed=passed,
        http_status_counts=status_counts,
        http_timeouts=timeouts,
        http_connection_errors=conn_errors,
        db={
            "CANONICAL_ROWS_FOR_KEY": canonical,
            "DLQ_ROWS_FOR_KEY": dlq,
            "HTTP_5XX_COUNT": http_5xx,
            "HTTP_TIMEOUT_COUNT": timeouts,
            "HTTP_CONNECTION_ERRORS": conn_errors,
        },
    )


async def scenario_s2_unique_storm(
    *,
    name: str,
    client: httpx.AsyncClient,
    base_url: str,
    tenant: TenantSeed,
    tenant_api_key_header: str,
    n: int,
    concurrency: int,
    timeout_s: float,
    run_start_utc: datetime,
    conn: asyncpg.Connection,
    keys: list[str],
) -> ScenarioResult:
    url = f"{base_url}/api/webhooks/stripe/payment_intent/succeeded"
    reqs: list[tuple[str, dict[str, str], bytes]] = []
    for k in keys:
        correlation_id = _uuid_deterministic("r3", name, str(tenant.tenant_id), k)
        body = build_stripe_payment_intent_body(
            event_id=f"evt_{k.replace('-', '')[:16]}",
            payment_intent_id=f"pi_{k.replace('-', '')[:16]}",
            amount_cents=100,
            currency="usd",
            created_epoch=int(run_start_utc.timestamp()),
            include_pii=False,
        )
        headers = _make_headers_for_stripe(
            tenant_api_key_header=tenant_api_key_header,
            tenant_api_key=tenant.api_key,
            stripe_secret=tenant.secrets["stripe"],
            correlation_id=correlation_id,
            idempotency_key=k,
            body=body,
        )
        reqs.append((url, headers, body))

    status_counts, timeouts, conn_errors = await _http_fire(
        client, reqs, concurrency=concurrency, timeout_s=timeout_s
    )
    canonical = await db_count_canonical_for_keys(conn, tenant.tenant_id, keys)
    dlq = await db_count_dlq_for_keys(conn, tenant.tenant_id, keys)
    http_5xx = sum(v for k, v in status_counts.items() if k.isdigit() and 500 <= int(k) <= 599)

    passed = canonical == n and dlq == 0 and http_5xx == 0 and timeouts == 0 and conn_errors == 0
    return ScenarioResult(
        name=name,
        passed=passed,
        http_status_counts=status_counts,
        http_timeouts=timeouts,
        http_connection_errors=conn_errors,
        db={
            "CANONICAL_ROWS_CREATED": canonical,
            "DLQ_ROWS_CREATED": dlq,
            "HTTP_5XX_COUNT": http_5xx,
            "HTTP_TIMEOUT_COUNT": timeouts,
            "HTTP_CONNECTION_ERRORS": conn_errors,
        },
    )


async def scenario_s3_malformed_storm(
    *,
    name: str,
    client: httpx.AsyncClient,
    base_url: str,
    tenant: TenantSeed,
    tenant_api_key_header: str,
    n: int,
    concurrency: int,
    timeout_s: float,
    run_start_utc: datetime,
    conn: asyncpg.Connection,
    keys: list[str],
) -> ScenarioResult:
    url = f"{base_url}/api/webhooks/stripe/payment_intent/succeeded"
    reqs: list[tuple[str, dict[str, str], bytes]] = []
    for k in keys:
        correlation_id = _uuid_deterministic("r3", name, str(tenant.tenant_id), k)
        body = build_stripe_payment_intent_body(
            event_id=f"evt_{k.replace('-', '')[:16]}",
            payment_intent_id=None,
            amount_cents=None,
            currency="usd",
            created_epoch="not_an_int",
            include_pii=False,
        )
        headers = _make_headers_for_stripe(
            tenant_api_key_header=tenant_api_key_header,
            tenant_api_key=tenant.api_key,
            stripe_secret=tenant.secrets["stripe"],
            correlation_id=correlation_id,
            idempotency_key=k,
            body=body,
        )
        reqs.append((url, headers, body))

    status_counts, timeouts, conn_errors = await _http_fire(
        client, reqs, concurrency=concurrency, timeout_s=timeout_s
    )
    canonical = await db_count_canonical_for_keys(conn, tenant.tenant_id, keys)
    dlq = await db_count_dlq_for_keys(conn, tenant.tenant_id, keys)
    http_5xx = sum(v for k, v in status_counts.items() if k.isdigit() and 500 <= int(k) <= 599)

    passed = canonical == 0 and dlq == n and http_5xx == 0 and timeouts == 0 and conn_errors == 0
    return ScenarioResult(
        name=name,
        passed=passed,
        http_status_counts=status_counts,
        http_timeouts=timeouts,
        http_connection_errors=conn_errors,
        db={
            "CANONICAL_ROWS_CREATED": canonical,
            "DLQ_ROWS_CREATED": dlq,
            "HTTP_5XX_COUNT": http_5xx,
            "HTTP_TIMEOUT_COUNT": timeouts,
            "HTTP_CONNECTION_ERRORS": conn_errors,
        },
    )


async def scenario_s4_pii_storm(
    *,
    name: str,
    client: httpx.AsyncClient,
    base_url: str,
    tenant: TenantSeed,
    tenant_api_key_header: str,
    n: int,
    concurrency: int,
    timeout_s: float,
    run_start_utc: datetime,
    conn: asyncpg.Connection,
    keys: list[str],
) -> ScenarioResult:
    url = f"{base_url}/api/webhooks/stripe/payment_intent/succeeded"
    reqs: list[tuple[str, dict[str, str], bytes]] = []
    for k in keys:
        correlation_id = _uuid_deterministic("r3", name, str(tenant.tenant_id), k)
        body = build_stripe_payment_intent_body(
            event_id=f"evt_{k.replace('-', '')[:16]}",
            payment_intent_id=f"pi_{k.replace('-', '')[:16]}",
            amount_cents=321,
            currency="usd",
            created_epoch=int(run_start_utc.timestamp()),
            include_pii=True,
        )
        headers = _make_headers_for_stripe(
            tenant_api_key_header=tenant_api_key_header,
            tenant_api_key=tenant.api_key,
            stripe_secret=tenant.secrets["stripe"],
            correlation_id=correlation_id,
            idempotency_key=k,
            body=body,
        )
        reqs.append((url, headers, body))

    status_counts, timeouts, conn_errors = await _http_fire(
        client, reqs, concurrency=concurrency, timeout_s=timeout_s
    )
    canonical = await db_count_canonical_for_keys(conn, tenant.tenant_id, keys)
    dlq = await db_count_dlq_for_keys(conn, tenant.tenant_id, keys)
    pii_hits = await db_pii_key_hits_since(conn, run_start_utc, [tenant.tenant_id])
    http_5xx = sum(v for k, v in status_counts.items() if k.isdigit() and 500 <= int(k) <= 599)

    passed = (
        canonical == 0
        and dlq == n
        and http_5xx == 0
        and timeouts == 0
        and conn_errors == 0
        and sum(pii_hits.values()) == 0
    )
    return ScenarioResult(
        name=name,
        passed=passed,
        http_status_counts=status_counts,
        http_timeouts=timeouts,
        http_connection_errors=conn_errors,
        db={
            "CANONICAL_ROWS_CREATED": canonical,
            "DLQ_ROWS_CREATED": dlq,
            "PII_KEY_HIT_COUNT_IN_DB": sum(pii_hits.values()),
            **pii_hits,
            "HTTP_5XX_COUNT": http_5xx,
            "HTTP_TIMEOUT_COUNT": timeouts,
            "HTTP_CONNECTION_ERRORS": conn_errors,
        },
    )


async def scenario_s5_cross_tenant_collision(
    *,
    name: str,
    client: httpx.AsyncClient,
    base_url: str,
    tenant_a: TenantSeed,
    tenant_b: TenantSeed,
    tenant_api_key_header: str,
    concurrency: int,
    timeout_s: float,
    run_start_utc: datetime,
    conn: asyncpg.Connection,
    idempotency_key: str,
) -> ScenarioResult:
    url = f"{base_url}/api/webhooks/stripe/payment_intent/succeeded"
    body = build_stripe_payment_intent_body(
        event_id=f"evt_{idempotency_key.replace('-', '')[:16]}",
        payment_intent_id=f"pi_{idempotency_key.replace('-', '')[:16]}",
        amount_cents=777,
        currency="usd",
        created_epoch=int(run_start_utc.timestamp()),
        include_pii=False,
    )
    headers_a = _make_headers_for_stripe(
        tenant_api_key_header=tenant_api_key_header,
        tenant_api_key=tenant_a.api_key,
        stripe_secret=tenant_a.secrets["stripe"],
        correlation_id=_uuid_deterministic("r3", name, "A", idempotency_key),
        idempotency_key=idempotency_key,
        body=body,
    )
    headers_b = _make_headers_for_stripe(
        tenant_api_key_header=tenant_api_key_header,
        tenant_api_key=tenant_b.api_key,
        stripe_secret=tenant_b.secrets["stripe"],
        correlation_id=_uuid_deterministic("r3", name, "B", idempotency_key),
        idempotency_key=idempotency_key,
        body=body,
    )
    reqs = [(url, headers_a, body), (url, headers_b, body)]
    status_counts, timeouts, conn_errors = await _http_fire(
        client, reqs, concurrency=concurrency, timeout_s=timeout_s
    )

    a_canonical = await db_count_canonical_for_key(conn, tenant_a.tenant_id, idempotency_key)
    b_canonical = await db_count_canonical_for_key(conn, tenant_b.tenant_id, idempotency_key)
    http_5xx = sum(v for k, v in status_counts.items() if k.isdigit() and 500 <= int(k) <= 599)

    passed = (
        a_canonical == 1
        and b_canonical == 1
        and http_5xx == 0
        and timeouts == 0
        and conn_errors == 0
    )
    return ScenarioResult(
        name=name,
        passed=passed,
        http_status_counts=status_counts,
        http_timeouts=timeouts,
        http_connection_errors=conn_errors,
        db={
            "TENANT_A_CANONICAL_ROWS_FOR_KEY": a_canonical,
            "TENANT_B_CANONICAL_ROWS_FOR_KEY": b_canonical,
            "HTTP_5XX_COUNT": http_5xx,
            "HTTP_TIMEOUT_COUNT": timeouts,
            "HTTP_CONNECTION_ERRORS": conn_errors,
        },
    )


async def scenario_s6_mixed_storm(
    *,
    name: str,
    client: httpx.AsyncClient,
    base_url: str,
    tenant: TenantSeed,
    tenant_api_key_header: str,
    n: int,
    concurrency: int,
    timeout_s: float,
    run_start_utc: datetime,
    conn: asyncpg.Connection,
    replay_key: str,
    unique_keys: list[str],
    malformed_keys: list[str],
) -> ScenarioResult:
    url = f"{base_url}/api/webhooks/stripe/payment_intent/succeeded"
    reqs: list[tuple[str, dict[str, str], bytes]] = []

    replay_body = build_stripe_payment_intent_body(
        event_id=f"evt_{replay_key.replace('-', '')[:16]}",
        payment_intent_id=f"pi_{replay_key.replace('-', '')[:16]}",
        amount_cents=123,
        currency="usd",
        created_epoch=int(run_start_utc.timestamp()),
        include_pii=False,
    )
    replay_headers = _make_headers_for_stripe(
        tenant_api_key_header=tenant_api_key_header,
        tenant_api_key=tenant.api_key,
        stripe_secret=tenant.secrets["stripe"],
        correlation_id=_uuid_deterministic("r3", name, str(tenant.tenant_id), replay_key),
        idempotency_key=replay_key,
        body=replay_body,
    )
    # MixedStorm shape: 70% replay duplicates + 30% unique + 10% malformed (intentional overlap).
    for _ in range(max(1, int(0.7 * n))):
        reqs.append((url, replay_headers, replay_body))

    for k in unique_keys:
        body = build_stripe_payment_intent_body(
            event_id=f"evt_{k.replace('-', '')[:16]}",
            payment_intent_id=f"pi_{k.replace('-', '')[:16]}",
            amount_cents=222,
            currency="usd",
            created_epoch=int(run_start_utc.timestamp()),
            include_pii=False,
        )
        headers = _make_headers_for_stripe(
            tenant_api_key_header=tenant_api_key_header,
            tenant_api_key=tenant.api_key,
            stripe_secret=tenant.secrets["stripe"],
            correlation_id=_uuid_deterministic("r3", name, str(tenant.tenant_id), k),
            idempotency_key=k,
            body=body,
        )
        reqs.append((url, headers, body))

    for k in malformed_keys:
        body = build_stripe_payment_intent_body(
            event_id=f"evt_{k.replace('-', '')[:16]}",
            payment_intent_id=None,
            amount_cents=None,
            currency="usd",
            created_epoch="not_an_int",
            include_pii=False,
        )
        headers = _make_headers_for_stripe(
            tenant_api_key_header=tenant_api_key_header,
            tenant_api_key=tenant.api_key,
            stripe_secret=tenant.secrets["stripe"],
            correlation_id=_uuid_deterministic("r3", name, str(tenant.tenant_id), k),
            idempotency_key=k,
            body=body,
        )
        reqs.append((url, headers, body))

    reqs.sort(key=lambda r: hashlib.sha256(r[1]["X-Idempotency-Key"].encode("utf-8")).hexdigest())

    status_counts, timeouts, conn_errors = await _http_fire(
        client, reqs, concurrency=concurrency, timeout_s=timeout_s
    )
    http_5xx = sum(v for k, v in status_counts.items() if k.isdigit() and 500 <= int(k) <= 599)

    replay_canonical = await db_count_canonical_for_key(conn, tenant.tenant_id, replay_key)
    unique_canonical = await db_count_canonical_for_keys(conn, tenant.tenant_id, unique_keys)
    malformed_dlq = await db_count_dlq_for_keys(conn, tenant.tenant_id, malformed_keys)

    passed = (
        replay_canonical == 1
        and unique_canonical == len(unique_keys)
        and malformed_dlq == len(malformed_keys)
        and http_5xx == 0
        and timeouts == 0
        and conn_errors == 0
    )
    return ScenarioResult(
        name=name,
        passed=passed,
        http_status_counts=status_counts,
        http_timeouts=timeouts,
        http_connection_errors=conn_errors,
        db={
            "REPLAY_CANONICAL_ROWS_FOR_KEY": replay_canonical,
            "UNIQUE_CANONICAL_ROWS_CREATED": unique_canonical,
            "MALFORMED_DLQ_ROWS_CREATED": malformed_dlq,
            "HTTP_5XX_COUNT": http_5xx,
            "HTTP_TIMEOUT_COUNT": timeouts,
            "HTTP_CONNECTION_ERRORS": conn_errors,
        },
    )


async def scenario_s7_invalid_json_dlq(
    *,
    name: str,
    client: httpx.AsyncClient,
    base_url: str,
    tenant: TenantSeed,
    tenant_api_key_header: str,
    n: int,
    concurrency: int,
    timeout_s: float,
    conn: asyncpg.Connection,
    keys: list[str],
) -> ScenarioResult:
    url = f"{base_url}/api/webhooks/stripe/payment_intent/succeeded"
    reqs: list[tuple[str, dict[str, str], bytes]] = []
    for k in keys:
        correlation_id = _uuid_deterministic("r3", name, str(tenant.tenant_id), k)
        body = f'{{"id":"evt_{k[:8]}","created":1234567890,"data":'.encode("utf-8")
        headers = _make_headers_for_stripe(
            tenant_api_key_header=tenant_api_key_header,
            tenant_api_key=tenant.api_key,
            stripe_secret=tenant.secrets["stripe"],
            correlation_id=correlation_id,
            idempotency_key=k,
            body=body,
        )
        reqs.append((url, headers, body))

    status_counts, timeouts, conn_errors = await _http_fire(
        client, reqs, concurrency=concurrency, timeout_s=timeout_s
    )
    canonical = await db_count_canonical_for_keys(conn, tenant.tenant_id, keys)
    dlq = await db_count_dlq_for_keys(conn, tenant.tenant_id, keys)
    http_5xx = sum(v for code, v in status_counts.items() if code.isdigit() and 500 <= int(code) <= 599)

    passed = canonical == 0 and dlq == n and http_5xx == 0 and timeouts == 0 and conn_errors == 0
    return ScenarioResult(
        name=name,
        passed=passed,
        http_status_counts=status_counts,
        http_timeouts=timeouts,
        http_connection_errors=conn_errors,
        db={
            "CANONICAL_ROWS_CREATED": canonical,
            "DLQ_ROWS_CREATED": dlq,
            "HTTP_5XX_COUNT": http_5xx,
            "HTTP_TIMEOUT_COUNT": timeouts,
            "HTTP_CONNECTION_ERRORS": conn_errors,
        },
    )


async def scenario_s8_perf_gate(
    *,
    profile: PerfGateProfile,
    client: httpx.AsyncClient,
    base_url: str,
    tenant: TenantSeed,
    tenant_api_key_header: str,
    concurrency: int,
    timeout_s: float,
    conn: asyncpg.Connection,
    admin_conn: asyncpg.Connection,
    runtime_database_name: str,
    candidate_sha: str,
) -> ScenarioResult:
    total_requests = max(1, int(round(profile.target_rps * profile.duration_s)))
    duplicate_count = max(1, total_requests // 4)
    malformed_count = max(1, total_requests // 10)
    pii_count = max(1, total_requests // 10)
    while duplicate_count + malformed_count + pii_count >= total_requests:
        if duplicate_count >= malformed_count and duplicate_count >= pii_count and duplicate_count > 1:
            duplicate_count -= 1
        elif malformed_count >= pii_count and malformed_count > 1:
            malformed_count -= 1
        elif pii_count > 1:
            pii_count -= 1
        else:
            break
    unique_count = total_requests - duplicate_count - malformed_count - pii_count

    replay_key = str(_uuid_deterministic("r3", candidate_sha, profile.name, "replay"))
    unique_keys = _keys_for_scenario(candidate_sha, f"{profile.name}_unique", unique_count)
    malformed_keys = _keys_for_scenario(candidate_sha, f"{profile.name}_malformed", malformed_count)
    pii_keys = _keys_for_scenario(candidate_sha, f"{profile.name}_pii", pii_count)
    all_keys = [replay_key, *unique_keys, *malformed_keys, *pii_keys]

    test_start_utc = _now_utc()
    request_templates = _build_s8_requests_from_config(
        S8WorkerConfig(
            worker_id=0,
            base_url=base_url,
            tenant_api_key_header=tenant_api_key_header,
            tenant_api_key=tenant.api_key,
            stripe_secret=tenant.secrets["stripe"],
            tenant_id=str(tenant.tenant_id),
            name=profile.name,
            run_start_epoch=int(test_start_utc.timestamp()),
            concurrency=max(1, concurrency),
            timeout_s=timeout_s,
            replay_key=replay_key,
            replay_count=duplicate_count,
            unique_keys=unique_keys,
            malformed_keys=malformed_keys,
            pii_keys=pii_keys,
        )
    )

    resource_before = await db_connection_snapshot(admin_conn, runtime_database_name)
    status_counts, timeouts, conn_errors, latency_ms, elapsed_s, target_request_count = await _http_fire_rate_controlled(
        client,
        request_templates,
        concurrency=max(1, concurrency),
        timeout_s=timeout_s,
        target_rps=profile.target_rps,
        duration_s=profile.duration_s,
    )
    test_end_utc = _now_utc()
    resource_after = await db_connection_snapshot(admin_conn, runtime_database_name)

    replay_canonical = await db_count_canonical_for_key(conn, tenant.tenant_id, replay_key)
    unique_canonical = await db_count_canonical_for_keys(conn, tenant.tenant_id, unique_keys)
    malformed_dlq = await db_count_dlq_for_keys(conn, tenant.tenant_id, malformed_keys)
    pii_dlq = await db_count_dlq_for_keys(conn, tenant.tenant_id, pii_keys)
    canonical_for_all_keys = await db_count_canonical_for_keys(conn, tenant.tenant_id, all_keys)
    dlq_for_all_keys = await db_count_dlq_for_keys(conn, tenant.tenant_id, all_keys)
    duplicate_keys = await db_duplicate_canonical_keys_between(conn, tenant.tenant_id, test_start_utc, test_end_utc)
    pii_hits = await db_pii_key_hits_between(conn, test_start_utc, test_end_utc, [tenant.tenant_id])
    window_totals = await db_window_totals(conn, tenant.tenant_id, test_start_utc, test_end_utc)

    p50_ms = _percentile(latency_ms, 50)
    p95_ms = _percentile(latency_ms, 95)
    p99_ms = _percentile(latency_ms, 99)
    observed_count = _http_observed_count(status_counts)
    achieved_rps = target_request_count / elapsed_s if elapsed_s > 0 else 0.0
    http_errors = _http_error_count(status_counts)
    error_rate = (http_errors / target_request_count) if target_request_count > 0 else 1.0

    first_half_p95 = None
    second_half_p95 = None
    no_degradation = True
    if profile.enforce_no_degradation and len(latency_ms) >= 20:
        split = len(latency_ms) // 2
        first_half_p95 = _percentile(latency_ms[:split], 95)
        second_half_p95 = _percentile(latency_ms[split:], 95)
        if first_half_p95 is not None and second_half_p95 is not None:
            no_degradation = second_half_p95 <= max(profile.p95_max_ms, first_half_p95 * 1.25)

    resource_stable = (
        resource_after["total_connections"] <= resource_after["max_connections"]
        and resource_after["waiting_connections"] <= max(2, resource_before["waiting_connections"] + 2)
    )

    expected_canonical = 1 + len(unique_keys)
    expected_dlq = len(malformed_keys) + len(pii_keys)

    passed = (
        achieved_rps >= (profile.target_rps * 0.98)
        and p95_ms is not None
        and p95_ms < profile.p95_max_ms
        and error_rate == 0.0
        and replay_canonical == 1
        and unique_canonical == len(unique_keys)
        and malformed_dlq == len(malformed_keys)
        and pii_dlq == len(pii_keys)
        and canonical_for_all_keys == expected_canonical
        and dlq_for_all_keys == expected_dlq
        and duplicate_keys == 0
        and sum(pii_hits.values()) == 0
        and observed_count == target_request_count
        and resource_stable
        and no_degradation
    )

    return ScenarioResult(
        name=profile.name,
        passed=passed,
        http_status_counts=status_counts,
        http_timeouts=timeouts,
        http_connection_errors=conn_errors,
        db={
            "duration_s": profile.duration_s,
            "target_rps": profile.target_rps,
            "target_request_count": target_request_count,
            "observed_request_count": observed_count,
            "elapsed_s": round(elapsed_s, 4),
            "achieved_rps": round(achieved_rps, 3),
            "latency_p50_ms": round(p50_ms, 3) if p50_ms is not None else None,
            "latency_p95_ms": round(p95_ms, 3) if p95_ms is not None else None,
            "latency_p99_ms": round(p99_ms, 3) if p99_ms is not None else None,
            "latency_first_half_p95_ms": round(first_half_p95, 3) if first_half_p95 is not None else None,
            "latency_second_half_p95_ms": round(second_half_p95, 3) if second_half_p95 is not None else None,
            "http_error_count": http_errors,
            "http_timeout_count": timeouts,
            "http_connection_errors": conn_errors,
            "http_error_rate_percent": round(error_rate * 100.0, 5),
            "resource_stable": resource_stable,
            "resource_snapshot_before": resource_before,
            "resource_snapshot_after": resource_after,
            "window_start_utc": test_start_utc.isoformat(),
            "window_end_utc": test_end_utc.isoformat(),
            "replay_canonical_rows_for_key": replay_canonical,
            "unique_canonical_rows_created": unique_canonical,
            "malformed_dlq_rows_created": malformed_dlq,
            "pii_dlq_rows_created": pii_dlq,
            "canonical_rows_for_all_profile_keys": canonical_for_all_keys,
            "dlq_rows_for_all_profile_keys": dlq_for_all_keys,
            "expected_canonical_rows_for_all_profile_keys": expected_canonical,
            "expected_dlq_rows_for_all_profile_keys": expected_dlq,
            "duplicate_canonical_keys_in_window": duplicate_keys,
            "pii_key_hit_count_in_db": int(sum(pii_hits.values())),
            **pii_hits,
            **window_totals,
            "no_degradation_over_time": no_degradation,
        },
    )


async def run_eg34_customer_profile_suite(
    *,
    profiles: list[PerfGateProfile],
    client: httpx.AsyncClient,
    base_url: str,
    tenant_api_key_header: str,
    concurrency: int,
    timeout_s: float,
    conn: asyncpg.Connection,
    admin_db_url: str,
    runtime_db_url: str,
    candidate_sha: str,
) -> list[ScenarioResult]:
    runtime_database_name = _database_name_from_dsn(runtime_db_url)
    if runtime_database_name == "":
        raise RuntimeError("Unable to determine runtime database name for connection snapshot probes.")

    results: list[ScenarioResult] = []
    admin_conn = await _pg_connect_with_retry(admin_db_url)
    try:
        for idx, profile in enumerate(profiles):
            tenant_id = _uuid_deterministic("r3", candidate_sha, "eg3_4", profile.name, str(idx))
            tenant_api_key = f"r3_{candidate_sha[:8]}_{profile.name}_{tenant_id}"
            tenant = TenantSeed(
                tenant_id=tenant_id,
                api_key=tenant_api_key,
                api_key_hash=_sha256_hex(tenant_api_key),
                secrets={
                    "shopify": f"eg34_shopify_{idx}_{candidate_sha[:8]}",
                    "stripe": f"eg34_stripe_{idx}_{candidate_sha[:8]}",
                    "paypal": f"eg34_paypal_{idx}_{candidate_sha[:8]}",
                    "woocommerce": f"eg34_woo_{idx}_{candidate_sha[:8]}",
                },
            )
            await seed_tenant(admin_conn, tenant)
            result = await scenario_s8_perf_gate(
                profile=profile,
                client=client,
                base_url=base_url,
                tenant=tenant,
                tenant_api_key_header=tenant_api_key_header,
                concurrency=concurrency,
                timeout_s=timeout_s,
                conn=conn,
                admin_conn=admin_conn,
                runtime_database_name=runtime_database_name,
                candidate_sha=candidate_sha,
            )
            results.append(result)
    finally:
        await admin_conn.close()
    return results


async def scenario_s9_normalization_aliases(
    *,
    name: str,
    client: httpx.AsyncClient,
    base_url: str,
    tenant: TenantSeed,
    tenant_api_key_header: str,
    timeout_s: float,
    run_start_utc: datetime,
    conn: asyncpg.Connection,
) -> ScenarioResult:
    url = f"{base_url}/api/webhooks/stripe/payment_intent/succeeded"
    key_fb = str(_uuid_deterministic("r3", name, "fb"))
    key_facebook = str(_uuid_deterministic("r3", name, "facebook"))

    def _payload(k: str, utm_source: str) -> bytes:
        body: dict[str, Any] = {
            "id": f"evt_{k.replace('-', '')[:16]}",
            "type": "payment_intent.succeeded",
            "created": int(run_start_utc.timestamp()),
            "data": {
                "object": {
                    "id": f"pi_{k.replace('-', '')[:16]}",
                    "amount": 999,
                    "currency": "usd",
                    "status": "succeeded",
                    "metadata": {
                        "vendor": "facebook_ads",
                        "utm_source": utm_source,
                        "utm_medium": "cpc",
                    },
                }
            },
        }
        return json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")

    body_fb = _payload(key_fb, "fb_ads")
    body_facebook = _payload(key_facebook, "facebook_ads")

    headers_fb = _make_headers_for_stripe(
        tenant_api_key_header=tenant_api_key_header,
        tenant_api_key=tenant.api_key,
        stripe_secret=tenant.secrets["stripe"],
        correlation_id=_uuid_deterministic("r3", name, str(tenant.tenant_id), key_fb),
        idempotency_key=key_fb,
        body=body_fb,
    )
    headers_facebook = _make_headers_for_stripe(
        tenant_api_key_header=tenant_api_key_header,
        tenant_api_key=tenant.api_key,
        stripe_secret=tenant.secrets["stripe"],
        correlation_id=_uuid_deterministic("r3", name, str(tenant.tenant_id), key_facebook),
        idempotency_key=key_facebook,
        body=body_facebook,
    )

    resp_fb = await client.post(url, content=body_fb, headers=headers_fb, timeout=timeout_s)
    resp_facebook = await client.post(
        url, content=body_facebook, headers=headers_facebook, timeout=timeout_s
    )
    status_counts = {
        str(resp_fb.status_code): 1,
        str(resp_facebook.status_code): 1,
    }

    channel_fb = await db_channel_for_key(conn, tenant.tenant_id, key_fb)
    channel_facebook = await db_channel_for_key(conn, tenant.tenant_id, key_facebook)
    passed = (
        resp_fb.status_code == 200
        and resp_facebook.status_code == 200
        and channel_fb is not None
        and channel_fb == channel_facebook
        and channel_fb == "facebook_paid"
    )
    return ScenarioResult(
        name=name,
        passed=passed,
        http_status_counts=status_counts,
        http_timeouts=0,
        http_connection_errors=0,
        db={
            "CHANNEL_FB": channel_fb,
            "CHANNEL_FACEBOOK": channel_facebook,
        },
    )


async def main() -> int:
    candidate_sha = os.getenv("CANDIDATE_SHA") or os.getenv("GITHUB_SHA")
    if not candidate_sha:
        # Local runs without a commit SHA must remain clean-room across repeated
        # executions against the same database.
        candidate_sha = f"local-{int(time.time())}"
    base_url = _env("R3_API_BASE_URL", default="http://127.0.0.1:8000")
    admin_db_url = _env("R3_ADMIN_DATABASE_URL", default=_env("MIGRATION_DATABASE_URL", default=""))
    runtime_db_url = _env("R3_RUNTIME_DATABASE_URL", default=_env("DATABASE_URL", default=""))
    tenant_api_key_header = _env("TENANT_API_KEY_HEADER", default="X-Skeldir-Tenant-Key")

    ladder = _parse_int_list(_env("R3_LADDER", default="50,250,1000"))
    concurrency = int(_env("R3_CONCURRENCY", default="200"))
    timeout_s = float(_env("R3_TIMEOUT_S", default="10"))
    ready_attempts = int(_env("R3_READY_ATTEMPTS", default="60"))
    ready_delay_s = float(_env("R3_READY_DELAY_S", default="1"))
    eg34_p95_max_ms = float(_env("R3_EG34_P95_MAX_MS", default="2000"))
    eg34_profiles = [
        PerfGateProfile(
            name="EG3_4_Test1_Month6",
            target_rps=float(_env("R3_EG34_TEST1_RPS", default="29")),
            duration_s=int(_env("R3_EG34_TEST1_DURATION_S", default="60")),
            p95_max_ms=eg34_p95_max_ms,
            enforce_no_degradation=False,
        ),
        PerfGateProfile(
            name="EG3_4_Test2_Month18",
            target_rps=float(_env("R3_EG34_TEST2_RPS", default="46")),
            duration_s=int(_env("R3_EG34_TEST2_DURATION_S", default="60")),
            p95_max_ms=eg34_p95_max_ms,
            enforce_no_degradation=False,
        ),
        PerfGateProfile(
            name="EG3_4_Test3_SustainedOps",
            target_rps=float(_env("R3_EG34_TEST3_RPS", default="5")),
            duration_s=int(_env("R3_EG34_TEST3_DURATION_S", default="300")),
            p95_max_ms=eg34_p95_max_ms,
            enforce_no_degradation=True,
        ),
    ]
    null_benchmark_enabled = _env("R3_NULL_BENCHMARK", default="1") == "1"
    null_benchmark_target_rps = float(_env("R3_NULL_BENCHMARK_TARGET_RPS", default="50"))
    null_benchmark_duration_s = int(_env("R3_NULL_BENCHMARK_DURATION_S", default="60"))
    null_benchmark_min_rps = float(
        _env("R3_NULL_BENCHMARK_MIN_RPS", default=str(null_benchmark_target_rps))
    )
    run_start_utc = _now_utc()

    if admin_db_url == "" or runtime_db_url == "":
        raise RuntimeError("R3 requires both admin and runtime DSNs for proof integrity.")
    if admin_db_url == runtime_db_url:
        raise RuntimeError("R3 requires distinct admin/runtime DSNs for proof integrity.")

    print("=== R3_ENV ===")
    print(
        json.dumps(
            {
                "candidate_sha": candidate_sha,
                "run_start_utc": run_start_utc.isoformat(),
                "base_url": base_url,
                "python": sys.version.split()[0],
                "platform": platform.platform(),
                "concurrency": concurrency,
                "timeout_s": timeout_s,
                "readiness_attempts": ready_attempts,
                "readiness_delay_s": ready_delay_s,
                "ladder": ladder,
                "eg34_profiles": [
                    {
                        "name": p.name,
                        "target_rps": p.target_rps,
                        "duration_s": p.duration_s,
                        "p95_max_ms": p.p95_max_ms,
                        "enforce_no_degradation": p.enforce_no_degradation,
                    }
                    for p in eg34_profiles
                ],
                "null_benchmark_enabled": null_benchmark_enabled,
                "null_benchmark_target_rps": null_benchmark_target_rps,
                "null_benchmark_duration_s": null_benchmark_duration_s,
                "null_benchmark_min_rps": null_benchmark_min_rps,
                "admin_dsn_distinct_from_runtime": True,
            },
            indent=2,
            sort_keys=True,
        )
    )

    print(f"R3_CPU_CORES={_DETECTED_CORES}  LOADGEN_WORKERS={_LOADGEN_WORKERS}  SERVER_WORKERS={_SERVER_WORKERS}")

    tenant_a_id = _uuid_deterministic("r3", candidate_sha, "tenant", "A")
    tenant_b_id = _uuid_deterministic("r3", candidate_sha, "tenant", "B")
    tenant_a_api_key = f"r3_{candidate_sha[:12]}_A_{tenant_a_id}"
    tenant_b_api_key = f"r3_{candidate_sha[:12]}_B_{tenant_b_id}"

    tenant_a = TenantSeed(
        tenant_id=tenant_a_id,
        api_key=tenant_a_api_key,
        api_key_hash=_sha256_hex(tenant_a_api_key),
        secrets={
            "shopify": f"r3_shopify_{candidate_sha[:12]}_A",
            "stripe": f"r3_stripe_{candidate_sha[:12]}_A",
            "paypal": f"r3_paypal_{candidate_sha[:12]}_A",
            "woocommerce": f"r3_woo_{candidate_sha[:12]}_A",
        },
    )
    tenant_b = TenantSeed(
        tenant_id=tenant_b_id,
        api_key=tenant_b_api_key,
        api_key_hash=_sha256_hex(tenant_b_api_key),
        secrets={
            "shopify": f"r3_shopify_{candidate_sha[:12]}_B",
            "stripe": f"r3_stripe_{candidate_sha[:12]}_B",
            "paypal": f"r3_paypal_{candidate_sha[:12]}_B",
            "woocommerce": f"r3_woo_{candidate_sha[:12]}_B",
        },
    )

    print("=== EG-R3-0 (Truth Anchor & Clean Room) ===")
    print(f"CANDIDATE_SHA={candidate_sha}")
    print(f"TENANT_A_ID={tenant_a.tenant_id}")
    print(f"TENANT_B_ID={tenant_b.tenant_id}")

    conn = await _pg_connect_with_retry(admin_db_url)
    try:
        await seed_channel_taxonomy(conn)
        await seed_tenant(conn, tenant_a)
        await seed_tenant(conn, tenant_b)
    finally:
        await conn.close()

    limits = httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency)
    async with httpx.AsyncClient(limits=limits) as client:
        await _wait_for_http_ready(
            client,
            base_url,
            attempts=ready_attempts,
            delay_s=ready_delay_s,
        )
        conn2 = await _pg_connect_with_retry(runtime_db_url)
        try:
            all_results: list[ScenarioResult] = []

            for n in ladder:
                print(f"=== R3_LADDER_STEP N={n} ===")

                s1_key = str(_uuid_deterministic("r3", candidate_sha, "S1", "replay_key"))
                s1 = await scenario_s1_replay_storm(
                    name=f"S1_ReplayStorm_N{n}",
                    client=client,
                    base_url=base_url,
                    tenant=tenant_a,
                    tenant_api_key_header=tenant_api_key_header,
                    n=n,
                    concurrency=concurrency,
                    timeout_s=timeout_s,
                    run_start_utc=run_start_utc,
                    conn=conn2,
                    idempotency_key=s1_key,
                )
                _verdict_block(s1.name, {"passed": s1.passed, **s1.db, "http_status_counts": s1.http_status_counts})
                all_results.append(s1)
                if not s1.passed:
                    break

                s5_key = str(_uuid_deterministic("r3", candidate_sha, "S5", "collision_key"))
                s5 = await scenario_s5_cross_tenant_collision(
                    name=f"S5_CrossTenantCollision_N{n}",
                    client=client,
                    base_url=base_url,
                    tenant_a=tenant_a,
                    tenant_b=tenant_b,
                    tenant_api_key_header=tenant_api_key_header,
                    concurrency=min(concurrency, 50),
                    timeout_s=timeout_s,
                    run_start_utc=run_start_utc,
                    conn=conn2,
                    idempotency_key=s5_key,
                )
                _verdict_block(s5.name, {"passed": s5.passed, **s5.db, "http_status_counts": s5.http_status_counts})
                all_results.append(s5)
                if not s5.passed:
                    break

                s3_keys = _keys_for_scenario(candidate_sha, f"S3_{n}", n)
                s3 = await scenario_s3_malformed_storm(
                    name=f"S3_MalformedStorm_N{n}",
                    client=client,
                    base_url=base_url,
                    tenant=tenant_a,
                    tenant_api_key_header=tenant_api_key_header,
                    n=n,
                    concurrency=min(concurrency, 100),
                    timeout_s=timeout_s,
                    run_start_utc=run_start_utc,
                    conn=conn2,
                    keys=s3_keys,
                )
                _verdict_block(s3.name, {"passed": s3.passed, **s3.db, "http_status_counts": s3.http_status_counts})
                all_results.append(s3)
                if not s3.passed:
                    break

                s7_keys = _keys_for_scenario(candidate_sha, f"S7_{n}", max(1, min(n, 50)))
                s7 = await scenario_s7_invalid_json_dlq(
                    name=f"S7_InvalidJsonDLQ_N{len(s7_keys)}",
                    client=client,
                    base_url=base_url,
                    tenant=tenant_a,
                    tenant_api_key_header=tenant_api_key_header,
                    n=len(s7_keys),
                    concurrency=min(concurrency, 100),
                    timeout_s=timeout_s,
                    conn=conn2,
                    keys=s7_keys,
                )
                _verdict_block(s7.name, {"passed": s7.passed, **s7.db, "http_status_counts": s7.http_status_counts})
                all_results.append(s7)
                if not s7.passed:
                    break

                s4_keys = _keys_for_scenario(candidate_sha, f"S4_{n}", n)
                s4 = await scenario_s4_pii_storm(
                    name=f"S4_PIIStorm_N{n}",
                    client=client,
                    base_url=base_url,
                    tenant=tenant_a,
                    tenant_api_key_header=tenant_api_key_header,
                    n=n,
                    concurrency=min(concurrency, 100),
                    timeout_s=timeout_s,
                    run_start_utc=run_start_utc,
                    conn=conn2,
                    keys=s4_keys,
                )
                _verdict_block(s4.name, {"passed": s4.passed, **s4.db, "http_status_counts": s4.http_status_counts})
                all_results.append(s4)
                if not s4.passed:
                    break

                s2_keys = _keys_for_scenario(candidate_sha, f"S2_{n}", n)
                s2 = await scenario_s2_unique_storm(
                    name=f"S2_UniqueStorm_N{n}",
                    client=client,
                    base_url=base_url,
                    tenant=tenant_a,
                    tenant_api_key_header=tenant_api_key_header,
                    n=n,
                    concurrency=min(concurrency, 100),
                    timeout_s=timeout_s,
                    run_start_utc=run_start_utc,
                    conn=conn2,
                    keys=s2_keys,
                )
                _verdict_block(s2.name, {"passed": s2.passed, **s2.db, "http_status_counts": s2.http_status_counts})
                all_results.append(s2)
                if not s2.passed:
                    break

                replay_key = str(_uuid_deterministic("r3", candidate_sha, f"S6_{n}", "replay"))
                unique_keys = _keys_for_scenario(candidate_sha, f"S6_{n}_unique", max(1, int(0.3 * n)))
                malformed_keys = _keys_for_scenario(candidate_sha, f"S6_{n}_malformed", max(1, int(0.1 * n)))
                s6 = await scenario_s6_mixed_storm(
                    name=f"S6_MixedStorm_N{n}",
                    client=client,
                    base_url=base_url,
                    tenant=tenant_a,
                    tenant_api_key_header=tenant_api_key_header,
                    n=n,
                    concurrency=concurrency,
                    timeout_s=timeout_s,
                    run_start_utc=run_start_utc,
                    conn=conn2,
                    replay_key=replay_key,
                    unique_keys=unique_keys,
                    malformed_keys=malformed_keys,
                )
                _verdict_block(s6.name, {"passed": s6.passed, **s6.db, "http_status_counts": s6.http_status_counts})
                all_results.append(s6)
                if not s6.passed:
                    break

            if all(r.passed for r in all_results):
                s9 = await scenario_s9_normalization_aliases(
                    name="S9_NormalizationAliases_fb_facebook",
                    client=client,
                    base_url=base_url,
                    tenant=tenant_a,
                    tenant_api_key_header=tenant_api_key_header,
                    timeout_s=timeout_s,
                    run_start_utc=run_start_utc,
                    conn=conn2,
                )
                _verdict_block(s9.name, {"passed": s9.passed, **s9.db, "http_status_counts": s9.http_status_counts})
                all_results.append(s9)

            if all(r.passed for r in all_results):
                if null_benchmark_enabled:
                    s_null = await run_null_benchmark_gate(
                        client=client,
                        timeout_s=timeout_s,
                        concurrency=max(1, min(concurrency, 100)),
                        target_rps=null_benchmark_target_rps,
                        duration_s=null_benchmark_duration_s,
                        min_rps=null_benchmark_min_rps,
                    )
                else:
                    s_null = ScenarioResult(
                        name="EG3_5_NullBenchmark",
                        passed=True,
                        http_status_counts={},
                        http_timeouts=0,
                        http_connection_errors=0,
                        db={
                            "measurement_valid": True,
                            "reason": "disabled_by_configuration",
                        },
                    )
                _verdict_block(s_null.name, {"passed": s_null.passed, **s_null.db, "http_status_counts": s_null.http_status_counts})
                all_results.append(s_null)

            if all(r.passed for r in all_results):
                eg34_results = await run_eg34_customer_profile_suite(
                    profiles=eg34_profiles,
                    client=client,
                    base_url=base_url,
                    tenant_api_key_header=tenant_api_key_header,
                    concurrency=concurrency,
                    timeout_s=timeout_s,
                    conn=conn2,
                    admin_db_url=admin_db_url,
                    runtime_db_url=runtime_db_url,
                    candidate_sha=candidate_sha,
                )
                for eg34 in eg34_results:
                    _verdict_block(eg34.name, {"passed": eg34.passed, **eg34.db, "http_status_counts": eg34.http_status_counts})
                    all_results.append(eg34)

            all_passed = all(r.passed for r in all_results)
            print("=== EG-R3-6 (Evidence Pack) ===")
            print(f"SCENARIOS_EXECUTED={len(all_results)}")
            print(f"ALL_SCENARIOS_PASSED={all_passed}")

            null_invalid = any(r.name == "EG3_5_NullBenchmark" and not r.passed for r in all_results)
            if null_invalid:
                print("R3_MEASUREMENT_INVALID=true")
                return 3

            return 0 if all_passed else 1
        finally:
            await conn2.close()


if __name__ == "__main__":
    mp.set_start_method(_MP_START_METHOD)
    raise SystemExit(asyncio.run(main()))
