import uuid
from typing import List

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.core.secrets import get_database_url
from app.db.session import engine, set_tenant_guc


async def _set_worker_context(conn, tenant_id):
    await set_tenant_guc(conn, tenant_id, local=True)
    await conn.execute(text("SELECT set_config('app.execution_context', 'worker', true)"))
    # Gate 0 proof: same role/session path as worker (uses DATABASE_URL user)
    current_user = await conn.scalar(text("SELECT current_user"))
    expected_user = make_url(get_database_url()).username
    assert current_user == expected_user


async def _table_exists(conn, table_name: str) -> bool:
    result = await conn.scalar(
        text(
            "SELECT to_regclass(:table_name) IS NOT NULL",
        ),
        {"table_name": table_name},
    )
    return bool(result)


async def _get_columns(conn, table_name: str) -> set[str]:
    res = await conn.execute(
        text(
            "SELECT column_name FROM information_schema.columns WHERE table_name = :table_name"
        ),
        {"table_name": table_name},
    )
    return {row[0] for row in res}


async def _seed_channel(conn):
    if not await _table_exists(conn, "channel_taxonomy"):
        return
    await conn.execute(
        text(
            """
            INSERT INTO channel_taxonomy (code, name, created_at, updated_at)
            VALUES ('direct', 'Direct', now(), now())
            ON CONFLICT (code) DO NOTHING
            """
        )
    )


ATTRIBUTION_COL_VALUES = {
    "id": "gen_random_uuid()",
    "tenant_id": ":tenant_id",
    "occurred_at": "now()",
    "external_event_id": "'ext'",
    "correlation_id": "gen_random_uuid()",
    "session_id": "gen_random_uuid()",
    "revenue_cents": "0",
    "raw_payload": "'{}'::jsonb",
    "idempotency_key": ":idempotency_key",
    "event_type": "'conversion'",
    "channel": "'direct'",
    "campaign_id": "NULL",
    "conversion_value_cents": "NULL",
    "currency": "'USD'",
    "event_timestamp": "now()",
    "processing_status": "'pending'",
    "retry_count": "0",
}


DEAD_EVENTS_COL_VALUES = {
    "id": "gen_random_uuid()",
    "tenant_id": ":tenant_id",
    "ingested_at": "now()",
    "source": "'test-source'",
    "error_code": "'VALIDATION_ERROR'",
    "error_detail": "'{}'::jsonb",
    "raw_payload": "'{}'::jsonb",
    "correlation_id": "gen_random_uuid()",
    "external_event_id": "'ext'",
    "event_type": "'conversion'",
    "error_type": "'validation_error'",
    "error_message": "'test message'",
    "retry_count": "0",
    "last_retry_at": "NULL",
    "remediation_status": "'pending'",
    "remediation_notes": "NULL",
    "resolved_at": "NULL",
}


async def _build_insert_sql(
    conn, table_name: str, col_values: dict[str, str], params: dict, *, returning: bool = False
) -> tuple[str, dict]:
    cols = await _get_columns(conn, table_name)
    insert_cols: List[str] = []
    values: List[str] = []
    for col in col_values:
        if col in cols:
            insert_cols.append(col)
            values.append(col_values[col])

    sql = f"""
        INSERT INTO {table_name} ({', '.join(insert_cols)})
        VALUES ({', '.join(values)})
    """
    if returning:
        sql = f"{sql} RETURNING id"
    return sql, params


async def _build_dead_events_update_sql(conn) -> str:
    cols = await _get_columns(conn, "dead_events")
    update_candidates = [
        ("retry_count", "COALESCE(retry_count, 0) + 1"),
        ("error_code", "'UPDATED_CODE'"),
        ("error_message", "'updated message'"),
        ("raw_payload", "'{\"patched\": true}'::jsonb"),
    ]

    for col, expr in update_candidates:
        if col in cols:
            return f"UPDATE dead_events SET {col} = {expr} WHERE id = :dead_id"

    raise AssertionError("No updatable columns available in dead_events for update guard test")


async def _insert_attribution_event(conn, tenant_id) -> uuid.UUID:
    await _seed_channel(conn)

    params = {
        "tenant_id": str(tenant_id),
        "idempotency_key": f"idem-{uuid.uuid4()}",
    }

    sql, params = await _build_insert_sql(
        conn,
        "attribution_events",
        ATTRIBUTION_COL_VALUES,
        params,
        returning=True,
    )
    res = await conn.execute(
        text(sql),
        params,
    )
    return res.scalar_one()


async def _insert_dead_event(conn, tenant_id) -> uuid.UUID:
    params = {"tenant_id": str(tenant_id)}

    sql, params = await _build_insert_sql(
        conn,
        "dead_events",
        DEAD_EVENTS_COL_VALUES,
        params,
        returning=True,
    )
    res = await conn.execute(
        text(sql),
        params,
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
        insert_sql, insert_params = await _build_insert_sql(
            conn,
            "attribution_events",
            ATTRIBUTION_COL_VALUES,
            {"tenant_id": str(tenant_id), "idempotency_key": f"idem-{uuid.uuid4()}"},
        )

    async with engine.begin() as conn:
        # Baseline row inserted outside worker context (ingestion/API path)
        await set_tenant_guc(conn, tenant_id, local=True)
        event_id = await _insert_attribution_event(conn, tenant_id)

    await _expect_blocked(tenant_id, insert_sql, insert_params)
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
        insert_sql, insert_params = await _build_insert_sql(
            conn,
            "dead_events",
            DEAD_EVENTS_COL_VALUES,
            {"tenant_id": str(tenant_id)},
        )
        update_sql = await _build_dead_events_update_sql(conn)

    async with engine.begin() as conn:
        await set_tenant_guc(conn, tenant_id, local=True)
        dead_id = await _insert_dead_event(conn, tenant_id)

    await _expect_blocked(tenant_id, insert_sql, insert_params)
    await _expect_blocked(
        tenant_id,
        update_sql,
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
        # RAW_SQL_ALLOWLIST: static pattern list for worker write detection (not executed)
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
