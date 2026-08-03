"""Real-PostgreSQL system-physics proofs for B2.5-P10 corrective closure."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import statistics
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import psutil
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import trust_api
from app.core.secrets import get_database_url, get_migration_database_url
from app.db.dsn import to_asyncpg_postgres_dsn
from app.trust.key_registry import TrustKeyRegistry, TrustSigningKey
from app.trust.machine_auth import MachineCallerContext, _check_rate_limit
from app.trust.machine_identity import AgentScope
from app.trust.reason_codes import ReasonCode
from app.trust.source_adapters import query_match_verdict_sources
from app.trust.tenant_security import (
    TenantContextMissingException,
    assert_authenticated_tenant_context,
    record_tenant_context_failure_durable,
)

pytestmark = pytest.mark.skipif(
    os.getenv("SKELDIR_B25_P10_POSTGRES_PROOF") != "1",
    reason="B2.5-P10 PostgreSQL physics proofs are opt-in for local runs",
)


def _registry() -> TrustKeyRegistry:
    private_key = Ed25519PrivateKey.from_private_bytes(
        hashlib.sha256(b"b25-p10-corrective-wire-key").digest()
    )
    return TrustKeyRegistry(
        (
            TrustSigningKey(
                kid="kid:b25-p10-corrective-wire",
                algorithm="ed25519",
                public_key=private_key.public_key(),
                private_key=private_key,
                state="active",
                valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
        )
    )


async def _insert_tenant(connection, tenant_id: UUID, label: str) -> None:
    await connection.execute(
        text(
            """
            INSERT INTO public.tenants (id, name, api_key_hash, notification_email)
            VALUES (:tenant_id, :name, :api_key_hash, :notification_email)
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "name": f"B25 P10 {label} {tenant_id}",
            "api_key_hash": f"b25-p10-{label}-{tenant_id}",
            "notification_email": f"b25-p10-{label}@example.invalid",
        },
    )


async def _seed_verdicts(
    connection,
    *,
    tenant_id: UUID,
    count: int,
    base_time: datetime,
    event_namespace: str = "",
) -> list[tuple[UUID, datetime]]:
    await connection.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )
    rows = (
        await connection.execute(
            text(
                """
                INSERT INTO public.b23_match_verdicts (
                    tenant_id,
                    provider,
                    canonical_commerce_reference,
                    provider_native_event_reference,
                    provider_native_commerce_reference,
                    status,
                    match_quality,
                    attributed_amount_minor,
                    verified_amount_minor,
                    currency_code,
                    pending_since,
                    last_transition_at,
                    created_at,
                    updated_at,
                    canonical_expected_gross_amount_minor,
                    canonical_captured_gross_amount_minor,
                    canonical_net_verified_amount_minor,
                    discrepancy_amount_minor,
                    discrepancy_ratio_bps,
                    discrepancy_band
                )
                SELECT
                    :tenant_id,
                    'stripe',
                    'order-' || ordinal,
                    :event_prefix || ordinal,
                    'commerce-' || ordinal,
                    'pending',
                    'high',
                    10000,
                    10000,
                    'USD',
                    CAST(:base_time AS timestamptz) + ordinal * interval '1 hour',
                    CAST(:base_time AS timestamptz) + ordinal * interval '1 hour',
                    CAST(:base_time AS timestamptz) + ordinal * interval '1 hour',
                    CAST(:base_time AS timestamptz) + ordinal * interval '1 hour',
                    10000,
                    10000,
                    10000,
                    0,
                    0,
                    'exact'
                FROM generate_series(1, :row_count) AS ordinal
                RETURNING id, updated_at
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "event_prefix": (
                    f"evt-{tenant_id}-{event_namespace}-"
                    if event_namespace
                    else f"evt-{tenant_id}-"
                ),
                "base_time": base_time,
                "row_count": count,
            },
        )
    ).all()
    return [(UUID(str(row[0])), row[1]) for row in rows]


async def _insert_agent_client(connection, tenant_id: UUID, client_id: UUID) -> None:
    await connection.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )
    await connection.execute(
        text(
            """
            INSERT INTO public.agent_clients (
                id, tenant_id, client_name, client_display_hash, audience, status
            ) VALUES (
                :client_id, :tenant_id, :client_name,
                :client_display_hash, :audience, 'active'
            )
            """
        ),
        {
            "client_id": str(client_id),
            "tenant_id": str(tenant_id),
            "client_name": f"p10-client-{client_id}",
            "client_display_hash": "sha256:" + "a" * 64,
            "audience": "b25-p10-postgres-proof",
        },
    )


async def _delete_tenant(engine, tenant_id: UUID) -> None:
    async with engine.begin() as connection:
        await connection.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
            {"tenant_id": str(tenant_id)},
        )
        await connection.execute(
            text("DELETE FROM public.tenants WHERE id = :tenant_id"),
            {"tenant_id": str(tenant_id)},
        )


def _request(caller: MachineCallerContext, method: str = "GET") -> SimpleNamespace:
    return SimpleNamespace(
        headers={
            "X-Tenant-ID": str(caller.tenant_id),
            "X-Correlation-ID": str(uuid4()),
        },
        state=SimpleNamespace(),
        scope={},
        method=method,
    )


def _caller(tenant_id: UUID, client_id: UUID | None = None) -> MachineCallerContext:
    return MachineCallerContext(
        agent_client_id=client_id or uuid4(),
        tenant_id=tenant_id,
        audience="b25-p10-postgres-proof",
        scopes=frozenset({AgentScope.ENVELOPE_READ, AgentScope.ENVELOPE_VERIFY}),
        nonce_value="nonce-0123456789abcdef",
        request_identity_hash="sha256:" + "2" * 64,
    )


@pytest.mark.asyncio
async def test_postgres_temporal_authority_bounded_plan_and_large_history() -> None:
    tenant_id = uuid4()
    migration_engine = create_async_engine(
        to_asyncpg_postgres_dsn(get_migration_database_url())
    )
    runtime_engine = create_async_engine(to_asyncpg_postgres_dsn(get_database_url()))
    base_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    try:
        async with migration_engine.begin() as connection:
            await _insert_tenant(connection, tenant_id, "chronology")
            seeded = await _seed_verdicts(
                connection,
                tenant_id=tenant_id,
                count=5002,
                base_time=base_time,
            )

        selected_ids = [row[0] for row in seeded[:2]]
        after = base_time
        before = base_time + timedelta(hours=3)

        async def explain_exact_page(connection):
            return await connection.scalar(
                text(
                    """
                    EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
                    SELECT id
                    FROM public.b23_match_verdicts
                    WHERE tenant_id = :tenant_id
                      AND id = ANY(CAST(:verdict_ids AS uuid[]))
                      AND updated_at >= :updated_at_after
                      AND updated_at <= :updated_at_before
                    ORDER BY updated_at ASC, id ASC
                    LIMIT 2
                    """
                ),
                {
                    "tenant_id": str(tenant_id),
                    "verdict_ids": [str(value) for value in selected_ids],
                    "updated_at_after": after,
                    "updated_at_before": before,
                },
            )

        async with runtime_engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )
            rows = await query_match_verdict_sources(
                connection,
                tenant_id=tenant_id,
                subject_refs=[
                    f"urn:skeldir:match_verdict:{verdict_id}"
                    for verdict_id in selected_ids
                ],
                updated_at_after=after,
                updated_at_before=before,
                row_limit=trust_api.MAX_EVALUATED_REFS_PER_PAGE,
            )
            plan_before_growth = await explain_exact_page(connection)

        async with migration_engine.begin() as connection:
            unrelated = await _seed_verdicts(
                connection,
                tenant_id=tenant_id,
                count=5000,
                base_time=base_time + timedelta(days=365),
                event_namespace="unrelated",
            )
            await connection.execute(text("ANALYZE public.b23_match_verdicts"))

        async with runtime_engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )
            plan_after_growth = await explain_exact_page(connection)

        assert len(seeded) == 5002 > 2500 * trust_api.MAX_EVALUATED_REFS_PER_PAGE
        assert len(unrelated) == 5000
        assert rows
        assert all(after <= row.updated_at <= before for row in rows)
        assert len(rows) <= trust_api.MAX_EVALUATED_REFS_PER_PAGE
        before_document = plan_before_growth[0]
        document = plan_after_growth[0]
        query_plan = document["Plan"]
        assert query_plan["Actual Rows"] <= trust_api.MAX_EVALUATED_REFS_PER_PAGE
        assert document["Execution Time"] < 1000
        assert "Offset" not in str(document)
        assert "Seq Scan" not in str(document)
        before_plan = before_document["Plan"]
        before_blocks = before_plan.get("Shared Hit Blocks", 0) + before_plan.get(
            "Shared Read Blocks", 0
        )
        after_blocks = query_plan.get("Shared Hit Blocks", 0) + query_plan.get(
            "Shared Read Blocks", 0
        )
        assert after_blocks <= before_blocks + 32
    finally:
        await _delete_tenant(migration_engine, tenant_id)
        await runtime_engine.dispose()
        await migration_engine.dispose()


@pytest.mark.asyncio
async def test_postgres_tenant_failure_audit_survives_caller_rollback() -> None:
    tenant_id = uuid4()
    caller = _caller(tenant_id)
    correlation_id = str(uuid4())
    migration_engine = create_async_engine(
        to_asyncpg_postgres_dsn(get_migration_database_url())
    )
    runtime_engine = create_async_engine(to_asyncpg_postgres_dsn(get_database_url()))
    try:
        async with migration_engine.begin() as connection:
            await _insert_tenant(connection, tenant_id, "tenant-audit")

        async with runtime_engine.connect() as caller_connection:
            transaction = await caller_connection.begin()
            await caller_connection.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )
            exc = TenantContextMissingException(
                tenant_id=tenant_id,
                agent_client_id=caller.agent_client_id,
                correlation_identity=correlation_id,
                route_template="/api/trust/v1/envelopes/query",
                method="POST",
            )
            await record_tenant_context_failure_durable(exc)
            await transaction.rollback()

        async with runtime_engine.begin() as observer:
            await observer.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )
            row = (
                await observer.execute(
                    text(
                        """
                        SELECT event_type, reason_code, subject_type
                        FROM public.trust_access_log
                        WHERE tenant_id = :tenant_id
                          AND reason_code = 'tenant_context_missing'
                        """
                    ),
                    {"tenant_id": str(tenant_id)},
                )
            ).one()
        assert row[0] == "scope_denial"
        assert row[1] == ReasonCode.TENANT_CONTEXT_MISSING.value
        assert "post_auth_transaction_rls_assertion" in row[2]
    finally:
        await _delete_tenant(migration_engine, tenant_id)
        await runtime_engine.dispose()
        await migration_engine.dispose()


@pytest.mark.asyncio
async def test_postgres_pool_a_b_a_concurrent_rollback_and_cancellation_isolation() -> (
    None
):
    tenant_a = uuid4()
    tenant_b = uuid4()
    engine = create_async_engine(
        to_asyncpg_postgres_dsn(get_database_url()),
        pool_size=2,
        max_overflow=0,
    )
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def assert_bound(tenant_id: UUID, *, rollback: bool = False) -> None:
        caller = _caller(tenant_id)
        async with sessions() as session:
            await session.begin()
            await session.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )
            assert (
                await assert_authenticated_tenant_context(
                    _request(caller), session, caller
                )
                is caller
            )
            if rollback:
                await session.rollback()
            else:
                await session.commit()

    async def assert_unbound_checkout() -> None:
        async with engine.connect() as connection:
            value = await connection.scalar(
                text("SELECT current_setting('app.current_tenant_id', true)")
            )
            assert value in {None, ""}

    async def cancelled_request() -> None:
        async with sessions() as session:
            await session.begin()
            await session.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_a)},
            )
            await asyncio.sleep(60)

    try:
        await assert_bound(tenant_a)
        await assert_unbound_checkout()
        await assert_bound(tenant_b, rollback=True)
        await assert_unbound_checkout()
        await assert_bound(tenant_a)
        await asyncio.gather(
            *(
                assert_bound(tenant_a if index % 2 == 0 else tenant_b)
                for index in range(20)
            )
        )
        task = asyncio.create_task(cancelled_request())
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await assert_unbound_checkout()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_postgres_rate_timezone_boundary_and_quota_durability() -> None:
    tenant_id = uuid4()
    timezone_client = uuid4()
    boundary_client = uuid4()
    quota_clients = {
        stage: uuid4() for stage in ("builder", "signing", "audit", "serialization")
    }
    migration_engine = create_async_engine(
        to_asyncpg_postgres_dsn(get_migration_database_url())
    )
    runtime_engine = create_async_engine(
        to_asyncpg_postgres_dsn(get_database_url()),
        pool_size=20,
        max_overflow=20,
    )
    sessions = async_sessionmaker(runtime_engine, expire_on_commit=False)
    bucket_time = datetime(2026, 8, 2, 17, 0, 30, tzinfo=timezone.utc)
    try:
        async with migration_engine.begin() as connection:
            await _insert_tenant(connection, tenant_id, "rate-physics")
            for client_id in (
                timezone_client,
                boundary_client,
                *quota_clients.values(),
            ):
                await _insert_agent_client(connection, tenant_id, client_id)

        for session_timezone in ("UTC", "America/Chicago", "Asia/Tokyo"):
            async with sessions() as session:
                await session.execute(
                    text(
                        "SELECT set_config('app.current_tenant_id', :tenant_id, true)"
                    ),
                    {"tenant_id": str(tenant_id)},
                )
                await session.execute(
                    text("SELECT set_config('TimeZone', :timezone, true)"),
                    {"timezone": session_timezone},
                )
                assert await _check_rate_limit(
                    session,
                    tenant_id=tenant_id,
                    agent_client_id=timezone_client,
                    at_time=bucket_time,
                )

        limit = 10
        before = datetime(2026, 8, 2, 17, 0, 59, 999999, tzinfo=timezone.utc)
        after = datetime(2026, 8, 2, 17, 1, 0, 1, tzinfo=timezone.utc)
        latencies_ms: list[float] = []

        async def boundary_attempt(at_time: datetime) -> bool:
            started = time.perf_counter()
            async with sessions() as session:
                await session.execute(
                    text(
                        "SELECT set_config('app.current_tenant_id', :tenant_id, true)"
                    ),
                    {"tenant_id": str(tenant_id)},
                )
                admitted = await _check_rate_limit(
                    session,
                    tenant_id=tenant_id,
                    agent_client_id=boundary_client,
                    request_limit=limit,
                    at_time=at_time,
                )
            latencies_ms.append((time.perf_counter() - started) * 1000)
            return admitted

        boundary_results = await asyncio.wait_for(
            asyncio.gather(
                *(boundary_attempt(before) for _ in range(limit)),
                *(boundary_attempt(after) for _ in range(limit)),
            ),
            timeout=30,
        )

        for failure_stage, quota_client in quota_clients.items():
            async with sessions() as session:
                await session.execute(
                    text(
                        "SELECT set_config('app.current_tenant_id', :tenant_id, true)"
                    ),
                    {"tenant_id": str(tenant_id)},
                )
                assert await _check_rate_limit(
                    session,
                    tenant_id=tenant_id,
                    agent_client_id=quota_client,
                    at_time=bucket_time,
                )
                await session.begin()
                try:
                    raise RuntimeError(f"forced_{failure_stage}_failure")
                except RuntimeError:
                    await session.rollback()

        async with migration_engine.begin() as observer:
            await observer.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )
            rows = (
                await observer.execute(
                    text(
                        """
                        SELECT
                            agent_client_id,
                            EXTRACT(EPOCH FROM window_started_at)::bigint,
                            EXTRACT(EPOCH FROM window_ended_at)::bigint,
                            request_count
                        FROM public.trust_rate_limit_state
                        WHERE tenant_id = :tenant_id
                        ORDER BY agent_client_id, window_started_at
                        """
                    ),
                    {"tenant_id": str(tenant_id)},
                )
            ).all()

        timezone_rows = [row for row in rows if UUID(str(row[0])) == timezone_client]
        boundary_rows = [row for row in rows if UUID(str(row[0])) == boundary_client]
        quota_rows = {
            stage: [row for row in rows if UUID(str(row[0])) == client_id]
            for stage, client_id in quota_clients.items()
        }
        expected_start = int(bucket_time.timestamp()) // 60 * 60
        assert timezone_rows == [
            (timezone_client, expected_start, expected_start + 60, 3)
        ]
        assert [row[3] for row in boundary_rows] == [limit, limit]
        assert all(stage_rows[0][3] == 1 for stage_rows in quota_rows.values())
        assert sum(boundary_results) == 2 * limit
        assert max(latencies_ms) < 5000
        assert statistics.quantiles(latencies_ms, n=100)[94] < 5000
    finally:
        await _delete_tenant(migration_engine, tenant_id)
        await runtime_engine.dispose()
        await migration_engine.dispose()


@pytest.mark.asyncio
async def test_postgres_maximum_query_resource_envelope(monkeypatch) -> None:
    tenant_id = uuid4()
    caller = _caller(tenant_id)
    migration_engine = create_async_engine(
        to_asyncpg_postgres_dsn(get_migration_database_url())
    )
    runtime_engine = create_async_engine(
        to_asyncpg_postgres_dsn(get_database_url()),
        pool_size=8,
        max_overflow=0,
    )
    runtime_sessions = async_sessionmaker(runtime_engine, expire_on_commit=False)
    process = psutil.Process()
    process_id = process.pid
    base_time = datetime(2026, 7, 1, tzinfo=timezone.utc)
    try:
        async with migration_engine.begin() as connection:
            await _insert_tenant(connection, tenant_id, "resource")
            seeded = await _seed_verdicts(
                connection,
                tenant_id=tenant_id,
                count=200,
                base_time=base_time,
            )
        refs = [f"urn:skeldir:match_verdict:{row[0]}" for row in seeded[:50]]

        audit_latencies_ms: list[float] = []
        signing_latencies_ms: list[float] = []
        original_audit = trust_api.build_unsigned_trust_envelope_with_audit
        original_sign = trust_api.sign_trust_envelope

        async def measured_audit(*args, **kwargs):
            started = time.perf_counter()
            try:
                return await original_audit(*args, **kwargs)
            finally:
                audit_latencies_ms.append((time.perf_counter() - started) * 1000)

        def measured_sign(*args, **kwargs):
            started = time.perf_counter()
            try:
                return original_sign(*args, **kwargs)
            finally:
                signing_latencies_ms.append((time.perf_counter() - started) * 1000)

        monkeypatch.setattr(
            trust_api,
            "build_unsigned_trust_envelope_with_audit",
            measured_audit,
        )
        monkeypatch.setattr(trust_api, "sign_trust_envelope", measured_sign)

        app = FastAPI()
        app.include_router(trust_api.router, prefix="/api")
        connection_hold_ms: list[float] = []
        pool_acquire_ms: list[float] = []

        async def session_dependency():
            dependency_started = time.perf_counter()
            async with runtime_sessions() as session:
                await session.begin()
                await session.execute(
                    text(
                        "SELECT set_config('app.current_tenant_id', :tenant_id, true)"
                    ),
                    {"tenant_id": str(tenant_id)},
                )
                pool_acquire_ms.append(
                    (time.perf_counter() - dependency_started) * 1000
                )
                try:
                    yield session
                finally:
                    if session.in_transaction():
                        await session.rollback()
                    connection_hold_ms.append(
                        (time.perf_counter() - dependency_started) * 1000
                    )

        async def trusted() -> MachineCallerContext:
            return caller

        async def signing_registry() -> TrustKeyRegistry:
            return _registry()

        app.dependency_overrides[trust_api.get_machine_db_session] = session_dependency
        app.dependency_overrides[trust_api.require_envelope_read_tenant_context] = (
            trusted
        )
        app.dependency_overrides[trust_api.get_runtime_signing_registry] = (
            signing_registry
        )

        payload = {"subject_types": ["match_verdict"], "subject_refs": refs}
        stop_sampling = asyncio.Event()
        rss_samples = [process.memory_info().rss]
        allocation_samples = [process.memory_full_info().uss]
        event_loop_delays_ms: list[float] = []
        process_swap_before = getattr(process.memory_full_info(), "swap", 0)

        async def sampler() -> None:
            interval = 0.05
            expected = time.perf_counter() + interval
            while not stop_sampling.is_set():
                await asyncio.sleep(interval)
                observed = time.perf_counter()
                event_loop_delays_ms.append(max(0.0, (observed - expected) * 1000))
                expected = observed + interval
                rss_samples.append(process.memory_info().rss)
                allocation_samples.append(process.memory_full_info().uss)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            monitor = asyncio.create_task(sampler())

            async def request(index: int):
                headers = {
                    "Authorization": "Bearer test-machine-token-value",
                    "X-Tenant-ID": str(tenant_id),
                    "X-Trust-Nonce": f"resource-nonce-{index:016d}",
                    "X-Correlation-ID": str(uuid4()),
                    "X-Idempotency-Key": f"resource-proof-{index}-{uuid4()}",
                }
                started = time.perf_counter()
                response = await client.post(
                    "/api/trust/v1/envelopes/query",
                    headers=headers,
                    json=payload,
                )
                return response, (time.perf_counter() - started) * 1000

            results = await asyncio.wait_for(
                asyncio.gather(*(request(index) for index in range(2))),
                timeout=15,
            )
            stop_sampling.set()
            await monitor

        responses = [item[0] for item in results]
        latencies = [item[1] for item in results]
        memory_limit = int(
            os.getenv("B25_P10_WORKER_MEMORY_LIMIT_BYTES", str(512 * 1024 * 1024))
        )
        request_bytes = len(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        response_bytes = [len(response.content) for response in responses]
        peak_rss_bytes = max(rss_samples)
        p95_request_ms = max(latencies)
        p99_request_ms = max(latencies)
        five_xx_count = sum(500 <= response.status_code < 600 for response in responses)
        process_swap_after = getattr(process.memory_full_info(), "swap", 0)
        metrics = {
            "concurrency": trust_api.MAX_CONCURRENT_QUERY_REQUESTS,
            "returned_per_request": trust_api.MAX_RETURNED_OUTCOMES,
            "seeded_history_rows": len(seeded),
            "request_bytes": request_bytes,
            "response_bytes": response_bytes,
            "response_amplification_max": max(response_bytes) / request_bytes,
            "peak_rss_bytes": peak_rss_bytes,
            "peak_private_allocation_bytes": max(allocation_samples),
            "worker_memory_limit_bytes": memory_limit,
            "peak_rss_fraction": peak_rss_bytes / memory_limit,
            "event_loop_delay_max_ms": max(event_loop_delays_ms, default=0.0),
            "pool_acquire_max_ms": max(pool_acquire_ms),
            "connection_hold_max_ms": max(connection_hold_ms),
            "build_audit_max_ms": max(audit_latencies_ms),
            "signing_max_ms": max(signing_latencies_ms),
            "p95_request_ms": p95_request_ms,
            "p99_request_ms": p99_request_ms,
            "five_xx_count": five_xx_count,
            "timeout_count": 0,
            "pid_before": process_id,
            "pid_after": process.pid,
            "swap_delta_bytes": process_swap_after - process_swap_before,
        }
        print("P10_RESOURCE_METRICS=" + json.dumps(metrics, sort_keys=True))
        assert len(seeded) == 200 > trust_api.MAX_RETURNED_OUTCOMES
        assert all(response.status_code == 200 for response in responses)
        assert all(
            len(response.json()["envelopes"]) == trust_api.MAX_RETURNED_OUTCOMES
            for response in responses
        )
        assert all(
            len(response.content) <= trust_api.MAX_AGGREGATE_RESPONSE_BYTES
            for response in responses
        )
        assert peak_rss_bytes <= int(memory_limit * 0.70)
        assert max(allocation_samples) <= int(memory_limit * 0.70)
        assert p95_request_ms <= 5_000
        assert p99_request_ms <= 10_000
        assert max(event_loop_delays_ms, default=0.0) < 5_000
        assert max(pool_acquire_ms) < 5_000
        assert max(connection_hold_ms) <= 5_000
        assert max(response_bytes) / request_bytes < 100
        assert five_xx_count == 0
        assert process.pid == process_id
        assert process_swap_after - process_swap_before <= 1024 * 1024
        assert runtime_engine.pool.checkedout() == 0
    finally:
        await _delete_tenant(migration_engine, tenant_id)
        await runtime_engine.dispose()
        await migration_engine.dispose()
