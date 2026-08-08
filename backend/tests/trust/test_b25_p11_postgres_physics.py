"""Real-PostgreSQL system-physics proofs for B2.5-P11 exports."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from uuid import UUID, uuid4

import psutil
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import trust_export
from app.core.secrets import get_database_url, get_migration_database_url
from app.db.dsn import to_asyncpg_postgres_dsn
from app.trust.key_registry import TrustKeyRegistry, TrustSigningKey
from app.trust.machine_auth import MachineCallerContext
from app.trust.machine_identity import AgentScope
from app.trust.source_adapters import query_match_verdict_sources


pytestmark = pytest.mark.skipif(
    os.getenv("SKELDIR_B25_P11_POSTGRES_PROOF") != "1",
    reason="B2.5-P11 PostgreSQL physics proofs are opt-in for local runs",
)


def _registry() -> TrustKeyRegistry:
    private = Ed25519PrivateKey.from_private_bytes(
        hashlib.sha256(b"b25-p11-postgres-proof-key").digest()
    )
    return TrustKeyRegistry(
        (
            TrustSigningKey(
                kid="kid:b25-p11-postgres-proof",
                algorithm="ed25519",
                public_key=private.public_key(),
                private_key=private,
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
            "name": f"B25 P11 {label} {tenant_id}",
            "api_key_hash": f"b25-p11-{label}-{tenant_id}",
            "notification_email": f"b25-p11-{label}@example.invalid",
        },
    )


async def _seed_verdicts(
    connection,
    *,
    tenant_id: UUID,
    count: int,
    namespace: str,
) -> list[UUID]:
    await connection.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )
    rows = (
        await connection.execute(
            text(
                """
                INSERT INTO public.b23_match_verdicts (
                    tenant_id, provider, canonical_commerce_reference,
                    provider_native_event_reference,
                    provider_native_commerce_reference, status, match_quality,
                    attributed_amount_minor, verified_amount_minor, currency_code,
                    pending_since, last_transition_at, created_at, updated_at,
                    canonical_expected_gross_amount_minor,
                    canonical_captured_gross_amount_minor,
                    canonical_net_verified_amount_minor, discrepancy_amount_minor,
                    discrepancy_ratio_bps, discrepancy_band
                )
                SELECT
                    :tenant_id, 'stripe', :namespace || '-order-' || ordinal,
                    :namespace || '-event-' || ordinal,
                    :namespace || '-commerce-' || ordinal,
                    'pending', 'high', 10000, 10000, 'USD',
                    now(), now(), now(), now(),
                    10000, 10000, 10000, 0, 0, 'exact'
                FROM generate_series(1, :row_count) AS ordinal
                RETURNING id
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "namespace": namespace,
                "row_count": count,
            },
        )
    ).all()
    return [UUID(str(row[0])) for row in rows]


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


def _caller(tenant_id: UUID) -> MachineCallerContext:
    return MachineCallerContext(
        agent_client_id=uuid4(),
        tenant_id=tenant_id,
        audience="b25-p11-postgres-proof",
        scopes=frozenset({AgentScope.EXPORT_CREATE_LIMITED}),
        nonce_value="nonce-0123456789abcdef",
        request_identity_hash="sha256:" + "7" * 64,
    )


def _headers(tenant_id: UUID, index: int) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-machine-token-value",
        "X-Tenant-ID": str(tenant_id),
        "X-Trust-Nonce": f"p11-postgres-nonce-{index:016d}",
        "X-Correlation-ID": str(uuid4()),
        "X-Idempotency-Key": f"p11-postgres-proof-{index}-{uuid4()}",
    }


async def _snapshot(connection, tenant_id: UUID) -> dict[str, int]:
    await connection.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )
    return {
        table: int(
            await connection.scalar(
                text(
                    f"SELECT count(*) FROM public.{table} WHERE tenant_id = :tenant_id"
                ),
                {"tenant_id": str(tenant_id)},
            )
        )
        for table in (
            "b23_match_verdicts",
            "attribution_allocations",
            "trust_access_log",
            "trust_envelope_issuance_log",
        )
    }


@pytest.mark.asyncio
async def test_postgres_two_tenant_bounded_plan_and_read_only_snapshot() -> None:
    tenant_a = uuid4()
    tenant_b = uuid4()
    migration_engine = create_async_engine(
        to_asyncpg_postgres_dsn(get_migration_database_url())
    )
    runtime_engine = create_async_engine(to_asyncpg_postgres_dsn(get_database_url()))
    sessions = async_sessionmaker(runtime_engine, expire_on_commit=False)
    try:
        async with migration_engine.begin() as connection:
            await _insert_tenant(connection, tenant_a, "tenant-a")
            await _insert_tenant(connection, tenant_b, "tenant-b")
            ids_a = await _seed_verdicts(
                connection,
                tenant_id=tenant_a,
                count=2,
                namespace="tenant-a",
            )
            ids_b = await _seed_verdicts(
                connection,
                tenant_id=tenant_b,
                count=2,
                namespace="tenant-b",
            )
            before = await _snapshot(connection, tenant_a)

        refs = [
            f"urn:skeldir:match_verdict:{ids_a[0]}",
            f"urn:skeldir:match_verdict:{ids_b[0]}",
        ]
        async with sessions() as session:
            await session.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_a)},
            )
            isolated = await query_match_verdict_sources(
                session,
                tenant_id=tenant_a,
                subject_refs=refs,
                row_limit=3,
            )
            plan = await session.scalar(
                text(
                    """
                    EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
                    SELECT id FROM public.b23_match_verdicts
                    WHERE tenant_id = :tenant_id
                      AND id = ANY(CAST(:verdict_ids AS uuid[]))
                    ORDER BY updated_at ASC, id ASC
                    LIMIT 3
                    """
                ),
                {
                    "tenant_id": str(tenant_a),
                    "verdict_ids": [str(ids_a[0]), str(ids_b[0])],
                },
            )
        assert [row.id for row in isolated] == [ids_a[0]]

        async with migration_engine.begin() as connection:
            await _seed_verdicts(
                connection,
                tenant_id=tenant_a,
                count=5_000,
                namespace="unrelated",
            )
            await connection.execute(text("ANALYZE public.b23_match_verdicts"))

        async with sessions() as session:
            await session.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_a)},
            )
            grown_plan = await session.scalar(
                text(
                    """
                    EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
                    SELECT id FROM public.b23_match_verdicts
                    WHERE tenant_id = :tenant_id
                      AND id = ANY(CAST(:verdict_ids AS uuid[]))
                    ORDER BY updated_at ASC, id ASC
                    LIMIT 3
                    """
                ),
                {
                    "tenant_id": str(tenant_a),
                    "verdict_ids": [str(ids_a[0]), str(ids_b[0])],
                },
            )
        assert "Seq Scan" not in str(grown_plan)
        initial_root = plan[0]["Plan"]
        grown_root = grown_plan[0]["Plan"]
        initial_blocks = initial_root.get("Shared Hit Blocks", 0) + initial_root.get(
            "Shared Read Blocks", 0
        )
        grown_blocks = grown_root.get("Shared Hit Blocks", 0) + grown_root.get(
            "Shared Read Blocks", 0
        )
        assert grown_blocks <= initial_blocks + 32

        caller_a = _caller(tenant_a)
        app = FastAPI()
        app.include_router(trust_export.router, prefix="/api")

        async def session_a():
            async with sessions() as session:
                await session.begin()
                await session.execute(
                    text(
                        "SELECT set_config('app.current_tenant_id', :tenant_id, true)"
                    ),
                    {"tenant_id": str(tenant_a)},
                )
                try:
                    yield session
                finally:
                    await session.rollback()

        async def trusted_a() -> MachineCallerContext:
            return caller_a

        async def registry() -> TrustKeyRegistry:
            return _registry()

        app.dependency_overrides[trust_export.get_machine_export_db_session] = session_a
        app.dependency_overrides[trust_export.require_export_tenant_context] = trusted_a
        app.dependency_overrides[trust_export.get_runtime_signing_registry] = registry
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            accepted = await client.post(
                "/api/trust/v1/exports/match-verdicts",
                headers=_headers(tenant_a, 1),
                json={"subject_refs": [refs[0]]},
            )
            wrong_tenant = await client.post(
                "/api/trust/v1/exports/match-verdicts",
                headers=_headers(tenant_a, 2),
                json={"subject_refs": [refs[1]]},
            )
        assert accepted.status_code == 200, accepted.text
        assert wrong_tenant.status_code == 422
        assert str(tenant_a) not in accepted.text
        assert str(tenant_b) not in accepted.text + wrong_tenant.text

        async with migration_engine.begin() as connection:
            after = await _snapshot(connection, tenant_a)
        assert after["b23_match_verdicts"] == before["b23_match_verdicts"] + 5_000
        assert after["attribution_allocations"] == before["attribution_allocations"]
        assert after["trust_access_log"] == before["trust_access_log"] + 1
        assert (
            after["trust_envelope_issuance_log"]
            == before["trust_envelope_issuance_log"] + 1
        )
    finally:
        await _delete_tenant(migration_engine, tenant_a)
        await _delete_tenant(migration_engine, tenant_b)
        await runtime_engine.dispose()
        await migration_engine.dispose()


@pytest.mark.asyncio
async def test_postgres_maximum_export_resource_envelope() -> None:
    tenant_id = uuid4()
    migration_engine = create_async_engine(
        to_asyncpg_postgres_dsn(get_migration_database_url())
    )
    runtime_engine = create_async_engine(
        to_asyncpg_postgres_dsn(get_database_url()),
        pool_size=8,
        max_overflow=0,
    )
    sessions = async_sessionmaker(runtime_engine, expire_on_commit=False)
    process = psutil.Process()
    rss_before = process.memory_info().rss
    try:
        async with migration_engine.begin() as connection:
            await _insert_tenant(connection, tenant_id, "resource")
            verdict_ids = await _seed_verdicts(
                connection,
                tenant_id=tenant_id,
                count=50,
                namespace="resource",
            )
        refs = [f"urn:skeldir:match_verdict:{value}" for value in verdict_ids]
        caller = _caller(tenant_id)
        app = FastAPI()
        app.include_router(trust_export.router, prefix="/api")

        async def session_dependency():
            async with sessions() as session:
                await session.begin()
                await session.execute(
                    text(
                        "SELECT set_config('app.current_tenant_id', :tenant_id, true)"
                    ),
                    {"tenant_id": str(tenant_id)},
                )
                try:
                    yield session
                finally:
                    await session.rollback()

        async def trusted() -> MachineCallerContext:
            return caller

        async def registry() -> TrustKeyRegistry:
            return _registry()

        app.dependency_overrides[trust_export.get_machine_export_db_session] = (
            session_dependency
        )
        app.dependency_overrides[trust_export.require_export_tenant_context] = trusted
        app.dependency_overrides[trust_export.get_runtime_signing_registry] = registry

        payload = {"subject_refs": refs}
        request_bytes = len(json.dumps(payload, separators=(",", ":")).encode())
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:

            async def request(index: int):
                started = time.perf_counter()
                response = await client.post(
                    "/api/trust/v1/exports/match-verdicts",
                    headers=_headers(tenant_id, index + 10),
                    json=payload,
                )
                return response, (time.perf_counter() - started) * 1000

            results = await asyncio.wait_for(
                asyncio.gather(*(request(index) for index in range(2))),
                timeout=10,
            )
        responses = [value[0] for value in results]
        latencies = [value[1] for value in results]
        response_bytes = [len(value.content) for value in responses]
        metrics = {
            "accepted_refs": len(refs),
            "artifact_bytes": response_bytes,
            "concurrency": trust_export.MAX_CONCURRENT_EXPORT_EXECUTIONS,
            "evaluated_per_request": trust_export.MAX_EVALUATED_EXPORT_REFS,
            "handler_deadline_ms": int(
                trust_export.EXPORT_HANDLER_DEADLINE_SECONDS * 1000
            ),
            "latency_max_ms": max(latencies),
            "request_bytes": request_bytes,
            "response_amplification_max": max(response_bytes) / request_bytes,
            "rss_delta_bytes": process.memory_info().rss - rss_before,
            "seeded_history_rows": len(verdict_ids),
        }
        print("P11_RESOURCE_METRICS=" + json.dumps(metrics, sort_keys=True))
        assert all(response.status_code == 200 for response in responses)
        assert all(len(response.json()["envelopes"]) == 2 for response in responses)
        assert all(
            len(response.content) <= trust_export.MAX_EXPORT_ARTIFACT_BYTES
            for response in responses
        )
        assert max(latencies) <= trust_export.EXPORT_HANDLER_DEADLINE_SECONDS * 1000
        assert runtime_engine.pool.checkedout() == 0
    finally:
        await _delete_tenant(migration_engine, tenant_id)
        await runtime_engine.dispose()
        await migration_engine.dispose()
