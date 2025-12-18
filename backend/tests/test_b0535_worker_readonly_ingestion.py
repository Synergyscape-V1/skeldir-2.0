import uuid
from typing import List

import pytest
from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine, set_tenant_guc


async def _set_worker_context(conn, tenant_id):
    await set_tenant_guc(conn, tenant_id, local=True)
    await conn.execute(text("SELECT set_config('app.execution_context', 'worker', true)"))
    # Gate 0 proof: same role/session path as worker (uses DATABASE_URL user)
    current_user = await conn.scalar(text("SELECT current_user"))
    assert current_user == settings.DATABASE_URL.username


async def _seed_channel(conn):
    await conn.execute(
        text(
            """
            INSERT INTO channel_taxonomy (code, name, created_at, updated_at)
            VALUES ('direct', 'Direct', now(), now())
            ON CONFLICT (code) DO NOTHING
            """
        )
    )


async def _insert_attribution_event(conn, tenant_id) -> uuid.UUID:
    await _seed_channel(conn)
    res = await conn.execute(
        text(
            """
            INSERT INTO attribution_events (
                id,
                tenant_id,
                occurred_at,
                external_event_id,
                correlation_id,
                session_id,
                revenue_cents,
                raw_payload,
                idempotency_key,
                event_type,
                channel,
                campaign_id,
                conversion_value_cents,
                currency,
                event_timestamp,
                processing_status,
                retry_count
            ) VALUES (
                gen_random_uuid(),
                :tenant_id,
                now(),
                'ext',
                gen_random_uuid(),
                gen_random_uuid(),
                0,
                '{}'::jsonb,
                :idempotency_key,
                'conversion',
                'direct',
                NULL,
                NULL,
                'USD',
                now(),
                'pending',
                0
            )
            RETURNING id
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "idempotency_key": f"idem-{uuid.uuid4()}",
        },
    )
    return res.scalar_one()


async def _insert_dead_event(conn, tenant_id) -> uuid.UUID:
    res = await conn.execute(
        text(
            """
            INSERT INTO dead_events (
                id,
                tenant_id,
                source,
                error_code,
                error_detail,
                raw_payload,
                event_type,
                error_type,
                error_message,
                retry_count,
                remediation_status
            ) VALUES (
                gen_random_uuid(),
                :tenant_id,
                'test-source',
                'VALIDATION_ERROR',
                '{}'::jsonb,
                '{}'::jsonb,
                'conversion',
                'validation_error',
                'test message',
                0,
                'pending'
            )
            RETURNING id
            """
        ),
        {"tenant_id": str(tenant_id)},
    )
    return res.scalar_one()


async def _assert_worker_blocked(conn, sql: str, params: dict):
    with pytest.raises(Exception) as excinfo:
        await conn.execute(text(sql), params)
    message = str(excinfo.value)
    expected_tokens = [
        "ingestion tables are read-only in worker context",
        "append-only",
    ]
    assert any(token in message for token in expected_tokens), message


async def _expect_blocked(tenant_id, sql: str, params: dict):
    async with engine.begin() as conn:
        await _set_worker_context(conn, tenant_id)
        await _assert_worker_blocked(conn, sql, params)


@pytest.mark.asyncio
@pytest.mark.usefixtures("test_tenant")
async def test_worker_context_blocks_attribution_events_mutation(test_tenant):
    tenant_id = test_tenant

    async with engine.begin() as conn:
        # Baseline row inserted outside worker context (ingestion/API path)
        await set_tenant_guc(conn, tenant_id, local=True)
        event_id = await _insert_attribution_event(conn, tenant_id)

    await _expect_blocked(
        tenant_id,
        """
        INSERT INTO attribution_events (id, tenant_id, occurred_at, external_event_id, correlation_id, session_id,
                                        revenue_cents, raw_payload, idempotency_key, event_type, channel,
                                        campaign_id, conversion_value_cents, currency, event_timestamp, processing_status, retry_count)
        VALUES (gen_random_uuid(), :tenant_id, now(), 'ext', gen_random_uuid(), gen_random_uuid(),
                0, '{}'::jsonb, :idempotency_key, 'conversion', 'direct', NULL, NULL, 'USD', now(), 'pending', 0)
        """,
        {"tenant_id": str(tenant_id), "idempotency_key": f"idem-{uuid.uuid4()}"},
    )
    await _expect_blocked(
        tenant_id,
        "UPDATE attribution_events SET revenue_cents = revenue_cents + 1 WHERE id = :event_id",
        {"event_id": str(event_id)},
    )
    await _expect_blocked(
        tenant_id,
        "DELETE FROM attribution_events WHERE id = :event_id",
        {"event_id": str(event_id)},
    )


@pytest.mark.asyncio
@pytest.mark.usefixtures("test_tenant")
async def test_worker_context_blocks_dead_events_mutation(test_tenant):
    tenant_id = test_tenant

    async with engine.begin() as conn:
        await set_tenant_guc(conn, tenant_id, local=True)
        dead_id = await _insert_dead_event(conn, tenant_id)

    await _expect_blocked(
        tenant_id,
        """
        INSERT INTO dead_events (id, tenant_id, source, error_code, error_detail, raw_payload, event_type, error_type, error_message, retry_count, remediation_status)
        VALUES (gen_random_uuid(), :tenant_id, 'test-source', 'VALIDATION_ERROR', '{}'::jsonb, '{}'::jsonb, 'conversion', 'validation_error', 'test insert block', 0, 'pending')
        """,
        {"tenant_id": str(tenant_id)},
    )
    await _expect_blocked(
        tenant_id,
        "UPDATE dead_events SET retry_count = retry_count + 1 WHERE id = :dead_id",
        {"dead_id": str(dead_id)},
    )
    await _expect_blocked(
        tenant_id,
        "DELETE FROM dead_events WHERE id = :dead_id",
        {"dead_id": str(dead_id)},
    )


def _read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read().lower()


def test_static_posture_no_worker_writes_to_ingestion_tables():
    import pathlib

    target_paths: List[str] = []
    for root in ("backend/app/tasks", "backend/app/workers"):
        for path in pathlib.Path(root).rglob("*.py"):
            target_paths.append(str(path))

    patterns = [
        "insert into attribution_events",
        "update attribution_events",
        "delete from attribution_events",
        "insert into dead_events",
        "update dead_events",
        "delete from dead_events",
    ]

    offending = []
    for path in target_paths:
        content = _read_file(path)
        for pattern in patterns:
            if pattern in content:
                offending.append((path, pattern))

    assert not offending, f"Worker code contains ingestion-table writes: {offending}"
