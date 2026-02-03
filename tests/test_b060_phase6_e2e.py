import asyncio
import json
import math
import os
import time
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import httpx
import jwt
import psycopg2
import pytest

API_BASE_URL = os.getenv("B060_PHASE6_API_BASE_URL", "http://127.0.0.1:8000")
MOCK_BASE_URL = os.getenv("B060_PHASE6_MOCK_BASE_URL", "http://127.0.0.1:8080")
ADMIN_DB_URL = os.getenv(
    "B060_PHASE6_ADMIN_DATABASE_URL",
    "postgresql://skeldir:skeldir_e2e@127.0.0.1:5432/skeldir_e2e",
)

JWT_SECRET = os.getenv("B060_PHASE6_JWT_SECRET", "e2e-secret")
JWT_ALGORITHM = os.getenv("B060_PHASE6_JWT_ALGORITHM", "HS256")
JWT_ISSUER = os.getenv("B060_PHASE6_JWT_ISSUER", "https://issuer.skeldir.test")
JWT_AUDIENCE = os.getenv("B060_PHASE6_JWT_AUDIENCE", "skeldir-api")

TENANT_A = UUID("00000000-0000-0000-0000-0000000000a1")
TENANT_B = UUID("00000000-0000-0000-0000-0000000000b1")

CACHE_KEY = "realtime_revenue:shared:v1"

pytestmark = pytest.mark.asyncio


def _build_token(tenant_id: UUID) -> str:
    now = int(time.time())
    payload = {
        "sub": "b060-e2e-user",
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "iat": now,
        "exp": now + 3600,
        "tenant_id": str(tenant_id),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _wait_for_db(timeout_s: int = 60) -> None:
    deadline = time.time() + timeout_s
    last_error = None
    while time.time() < deadline:
        try:
            conn = psycopg2.connect(ADMIN_DB_URL)
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
                return
            finally:
                conn.close()
        except Exception as exc:
            last_error = exc
            time.sleep(1)
    raise RuntimeError(f"DB not ready after {timeout_s}s: {last_error}")


def _wait_for_http(url: str, timeout_s: int = 60) -> None:
    deadline = time.time() + timeout_s
    last_error = None
    while time.time() < deadline:
        try:
            res = httpx.get(url, timeout=2.0)
            if res.status_code == 200:
                return
        except Exception as exc:
            last_error = exc
        time.sleep(0.5)
    raise RuntimeError(f"HTTP not ready after {timeout_s}s: {url} ({last_error})")


def _db_fetch_one(query: str, params: tuple[Any, ...]) -> Any:
    conn = psycopg2.connect(ADMIN_DB_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SET row_security = off")
            cur.execute(query, params)
            return cur.fetchone()
    finally:
        conn.close()


def _clear_cache(tenant_id: UUID) -> None:
    conn = psycopg2.connect(ADMIN_DB_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SET row_security = off")
            cur.execute(
                "DELETE FROM public.revenue_cache_entries WHERE tenant_id = %s AND cache_key = %s",
                (str(tenant_id), CACHE_KEY),
            )
            conn.commit()
    finally:
        conn.close()


def _assert_seeded() -> None:
    tenant_count = _db_fetch_one(
        "SELECT COUNT(*) FROM public.tenants WHERE id IN (%s, %s)",
        (str(TENANT_A), str(TENANT_B)),
    )[0]
    if tenant_count < 2:
        raise AssertionError("E2E seed missing; provider fetch path cannot be exercised.")

    connection_count = _db_fetch_one(
        """
        SELECT COUNT(*)
        FROM public.platform_connections
        WHERE tenant_id IN (%s, %s)
          AND status = 'active'
          AND platform IN ('stripe', 'dummy')
        """,
        (str(TENANT_A), str(TENANT_B)),
    )[0]
    if connection_count < 4:
        raise AssertionError("E2E seed missing; provider fetch path cannot be exercised.")

    credential_count = _db_fetch_one(
        """
        SELECT COUNT(*)
        FROM public.platform_credentials
        WHERE tenant_id IN (%s, %s)
          AND platform IN ('stripe', 'dummy')
        """,
        (str(TENANT_A), str(TENANT_B)),
    )[0]
    if credential_count < 4:
        raise AssertionError("E2E seed missing; provider fetch path cannot be exercised.")


async def _mock_reset_calls() -> None:
    async with httpx.AsyncClient(base_url=MOCK_BASE_URL, timeout=5.0) as client:
        await client.post("/calls/reset")


async def _mock_set_mode(mode: str, *, delay_ms: int | None = None) -> None:
    payload: dict[str, Any] = {"mode": mode}
    if delay_ms is not None:
        payload["delay_ms"] = delay_ms
    async with httpx.AsyncClient(base_url=MOCK_BASE_URL, timeout=5.0) as client:
        await client.post("/mode", json=payload)


async def _mock_calls() -> dict[str, int]:
    async with httpx.AsyncClient(base_url=MOCK_BASE_URL, timeout=5.0) as client:
        resp = await client.get("/calls")
        return resp.json()


def _fetch_cache_row(tenant_id: UUID) -> tuple[datetime, dict]:
    row = _db_fetch_one(
        """
        SELECT data_as_of, payload
        FROM public.revenue_cache_entries
        WHERE tenant_id = %s AND cache_key = %s
        """,
        (str(tenant_id), CACHE_KEY),
    )
    if not row:
        raise AssertionError("Expected cache row for seeded tenant")
    payload = row[1]
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            payload = {}
    return row[0], payload


@pytest.fixture(scope="session", autouse=True)
def _wait_for_health_and_seed_gate() -> None:
    _wait_for_db()
    _wait_for_http(f"{API_BASE_URL}/health/ready")
    _wait_for_http(f"{MOCK_BASE_URL}/health/ready")
    _assert_seeded()


async def test_00_seed_sanity_gate() -> None:
    _assert_seeded()


async def test_01_auth_boundary() -> None:
    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=10.0) as client:
        res = await client.get(
            "/api/attribution/revenue/realtime",
            headers={"X-Correlation-ID": str(uuid4())},
        )
        assert res.status_code == 401

        res = await client.get(
            "/api/attribution/revenue/realtime",
            headers={
                "X-Correlation-ID": str(uuid4()),
                "Authorization": "Bearer invalid",
            },
        )
        assert res.status_code == 401

        token = _build_token(TENANT_A)
        res = await client.get(
            "/api/attribution/revenue/realtime",
            headers={
                "X-Correlation-ID": str(uuid4()),
                "Authorization": f"Bearer {token}",
            },
        )
        assert res.status_code == 200


async def test_02_tenant_isolation_rls() -> None:
    await _mock_set_mode("success")
    await _mock_reset_calls()
    _clear_cache(TENANT_A)
    _clear_cache(TENANT_B)

    token_a = _build_token(TENANT_A)
    token_b = _build_token(TENANT_B)

    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=10.0) as client:
        res_a = await client.get(
            "/api/attribution/revenue/realtime",
            headers={
                "X-Correlation-ID": str(uuid4()),
                "Authorization": f"Bearer {token_a}",
            },
        )
        assert res_a.status_code == 200
        body_a = res_a.json()
        assert UUID(body_a["tenant_id"]) == TENANT_A

        calls = await _mock_calls()
        assert calls["stripe"] == 1

        res_b = await client.get(
            "/api/attribution/revenue/realtime",
            headers={
                "X-Correlation-ID": str(uuid4()),
                "Authorization": f"Bearer {token_b}",
            },
        )
        assert res_b.status_code == 200
        body_b = res_b.json()
        assert UUID(body_b["tenant_id"]) == TENANT_B

        calls = await _mock_calls()
        assert calls["stripe"] == 2


async def test_03_stampede_singleflight_p95_latency() -> None:
    await _mock_set_mode("success")
    await _mock_reset_calls()
    _clear_cache(TENANT_A)

    token = _build_token(TENANT_A)

    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=10.0) as client:
        async def _fetch_one() -> tuple[float, dict]:
            headers = {
                "X-Correlation-ID": str(uuid4()),
                "Authorization": f"Bearer {token}",
            }
            start = time.perf_counter()
            res = await client.get(
                "/api/attribution/revenue/realtime",
                headers=headers,
            )
            elapsed = time.perf_counter() - start
            assert res.status_code == 200
            return elapsed, res.json()

        results = await asyncio.gather(*[_fetch_one() for _ in range(10)])
    latencies = [item[0] for item in results]
    payloads = [item[1] for item in results]

    calls = await _mock_calls()
    assert calls["stripe"] == 1

    last_updated = {payload["last_updated"] for payload in payloads}
    assert len(last_updated) == 1

    latencies_sorted = sorted(latencies)
    p95_index = max(0, math.ceil(0.95 * len(latencies_sorted)) - 1)
    p95_latency = latencies_sorted[p95_index]
    assert p95_latency < 2.0


async def test_04_cache_hit_invariance() -> None:
    await _mock_set_mode("success")
    await _mock_reset_calls()
    _clear_cache(TENANT_A)

    token = _build_token(TENANT_A)
    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=10.0) as client:
        res = await client.get(
            "/api/attribution/revenue/realtime",
            headers={
                "X-Correlation-ID": str(uuid4()),
                "Authorization": f"Bearer {token}",
            },
        )
        assert res.status_code == 200
        body_initial = res.json()
        last_updated_initial = body_initial["last_updated"]
        freshness_initial = body_initial["data_freshness_seconds"]

        await asyncio.sleep(1.2)
        res = await client.get(
            "/api/attribution/revenue/realtime",
            headers={
                "X-Correlation-ID": str(uuid4()),
                "Authorization": f"Bearer {token}",
            },
        )
        assert res.status_code == 200
        body_cached = res.json()

    calls = await _mock_calls()
    assert calls["stripe"] == 1
    assert body_cached["last_updated"] == last_updated_initial
    assert body_cached["data_freshness_seconds"] >= freshness_initial


async def test_05_failure_cooldown_semantics() -> None:
    token = _build_token(TENANT_A)
    _clear_cache(TENANT_A)

    await _mock_set_mode("success")
    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=10.0) as client:
        res = await client.get(
            "/api/attribution/revenue/realtime",
            headers={
                "X-Correlation-ID": str(uuid4()),
                "Authorization": f"Bearer {token}",
            },
        )
        assert res.status_code == 200

    data_as_of_before, payload_before = _fetch_cache_row(TENANT_A)

    await _mock_set_mode("rate_limit")
    await asyncio.sleep(3.5)

    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=10.0) as client:
        res = await client.get(
            "/api/attribution/revenue/realtime",
            headers={
                "X-Correlation-ID": str(uuid4()),
                "Authorization": f"Bearer {token}",
            },
        )

    assert res.status_code == 503
    retry_after = res.headers.get("Retry-After")
    assert retry_after == "5"

    data_as_of_after, payload_after = _fetch_cache_row(TENANT_A)
    assert data_as_of_after == data_as_of_before
    assert payload_after.get("verified") is False
    assert payload_before.get("verified") is False


async def test_06_phase5_runtime_semantics() -> None:
    await _mock_set_mode("success")
    _clear_cache(TENANT_A)
    token = _build_token(TENANT_A)

    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=10.0) as client:
        res = await client.get(
            "/api/attribution/revenue/realtime",
            headers={
                "X-Correlation-ID": str(uuid4()),
                "Authorization": f"Bearer {token}",
            },
        )

    assert res.status_code == 200
    body = res.json()
    assert body["verified"] is False
    assert body["data_freshness_seconds"] >= 0
