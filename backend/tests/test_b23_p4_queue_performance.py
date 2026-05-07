from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import event, text

from app.celery_app import celery_app
from app.core.config import settings
from app.core.queues import QUEUE_B23_MATCH_ENGINE
from app.db.session import b23_engine, engine, get_b23_session
from app.revenue_verification.batch_engine import (
    B23_BATCH_MATCH_BACKGROUND_CARDINALITY,
    B23_BATCH_MATCH_CHUNK_SIZE,
    B23_BATCH_MATCH_PERFORMANCE_THRESHOLD_SECONDS,
    execute_b23_batch_match_engine,
)
from app.tasks.beat_schedule import build_beat_schedule


REPO_ROOT = Path(__file__).resolve().parents[2]
TELEMETRY_SQL_DIR = REPO_ROOT / "docs" / "ops" / "b23_p4" / "sql"


def _require_authoritative_db_proofs() -> bool:
    return os.getenv("SKELDIR_B23_P4_REQUIRE_DB_PROOFS", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _db_skip_or_fail(message: str) -> None:
    if _require_authoritative_db_proofs():
        pytest.fail(message)
    pytest.skip(message)


async def _assert_table_exists(table_name: str) -> None:
    try:
        async with engine.connect() as conn:
            regclass = (
                await conn.execute(
                    text("SELECT to_regclass(:qualified_name)"),
                    {"qualified_name": f"public.{table_name}"},
                )
            ).scalar_one_or_none()
    except Exception as exc:  # pragma: no cover
        _db_skip_or_fail(f"B2.3-P4 runtime proof DB is unreachable: {exc}")
    if regclass is None:
        _db_skip_or_fail(f"B2.3-P4 runtime proof table is missing: {table_name}")


async def _seed_b23_p4_benchmark_data(tenant_id: UUID) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    window_start = now - timedelta(hours=1)
    window_end = now + timedelta(hours=1)
    async with engine.begin() as conn:
        await conn.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
            {"tenant_id": str(tenant_id)},
        )
        await conn.execute(
            text(
                """
                INSERT INTO public.channel_taxonomy (
                    code,
                    family,
                    is_paid,
                    display_name,
                    is_active,
                    state
                )
                VALUES (
                    'paid_search',
                    'paid',
                    true,
                    'Paid Search',
                    true,
                    'active'
                )
                ON CONFLICT (code) DO NOTHING
                """
            )
        )
        await conn.execute(
            text(
                """
                WITH inserted_attribution AS (
                    INSERT INTO public.attribution_events (
                        tenant_id,
                        occurred_at,
                        session_id,
                        revenue_cents,
                        raw_payload,
                        idempotency_key,
                        event_type,
                        channel,
                        conversion_value_cents,
                        currency,
                        event_timestamp,
                        processing_status
                    )
                    SELECT
                        CAST(:tenant_id AS uuid),
                        CAST(:now_utc AS timestamptz) - (gs * interval '1 second'),
                        gen_random_uuid(),
                        10000 + gs,
                        jsonb_build_object('order_id', 'b23-p4-order-' || gs::text),
                        'b23-p4-attribution-' || CAST(:tenant_id AS text) || '-' || gs::text,
                        'conversion',
                        'paid_search',
                        10000 + gs,
                        'USD',
                        CAST(:now_utc AS timestamptz) - (gs * interval '1 second'),
                        'processed'
                    FROM generate_series(1, 1000) AS gs
                    RETURNING
                        id,
                        tenant_id,
                        raw_payload ->> 'order_id' AS order_ref,
                        conversion_value_cents,
                        event_timestamp
                ),
                inserted_identity AS (
                    INSERT INTO public.attribution_commerce_identities (
                        tenant_id,
                        attribution_event_id,
                        provider,
                        canonical_commerce_reference,
                        source,
                        first_observed_at,
                        last_observed_at
                    )
                    SELECT
                        tenant_id,
                        id,
                        'stripe',
                        order_ref,
                        'b23_p4_benchmark',
                        event_timestamp,
                        event_timestamp
                    FROM inserted_attribution
                    ON CONFLICT (tenant_id, provider, canonical_commerce_reference)
                    DO UPDATE SET
                        attribution_event_id = EXCLUDED.attribution_event_id,
                        last_observed_at = EXCLUDED.last_observed_at,
                        updated_at = now()
                    RETURNING tenant_id, attribution_event_id
                )
                INSERT INTO public.webhook_ingress_identities (
                    tenant_id,
                    event_id,
                    provider,
                    provider_native_event_reference,
                    provider_native_commerce_reference,
                    normalized_commerce_reference_kind,
                    normalized_commerce_reference_value,
                    verified_amount_minor,
                    verified_amount_currency,
                    verified_amount_scale,
                    event_timestamp,
                    idempotency_key,
                    verified_commerce_ingress_state,
                    verified_at
                )
                SELECT
                    tenant_id,
                    id,
                    'stripe',
                    'b23-p4-webhook-' || order_ref,
                    'pi-' || order_ref,
                    'order_id',
                    order_ref,
                    conversion_value_cents,
                    'USD',
                    2,
                    event_timestamp + interval '30 seconds',
                    'b23-p4-webhook-' || CAST(:tenant_id AS text) || '-' || order_ref,
                    'authenticity_verified',
                    CAST(:now_utc AS timestamptz)
                FROM inserted_attribution
                """
            ),
            {"tenant_id": str(tenant_id), "now_utc": now},
        )
        await conn.execute(
            text(
                """
                WITH historical_attribution AS (
                    INSERT INTO public.attribution_events (
                        tenant_id,
                        occurred_at,
                        session_id,
                        revenue_cents,
                        raw_payload,
                        idempotency_key,
                        event_type,
                        channel,
                        conversion_value_cents,
                        currency,
                        event_timestamp,
                        processing_status
                    )
                    SELECT
                        CAST(:tenant_id AS uuid),
                        CAST(:now_utc AS timestamptz) - interval '7 days',
                        gen_random_uuid(),
                        10000,
                        jsonb_build_object('order_id', 'historical-' || gs::text),
                        'b23-p4-historical-attribution-' || CAST(:tenant_id AS text) || '-' || gs::text,
                        'conversion',
                        'paid_search',
                        10000,
                        'USD',
                        CAST(:now_utc AS timestamptz) - interval '7 days',
                        'processed'
                    FROM generate_series(1, :background_rows) AS gs
                    WHERE gs % 5 <> 0
                    RETURNING id, raw_payload ->> 'order_id' AS order_ref
                ),
                historical_rows AS (
                    SELECT
                        gs,
                        'historical-' || gs::text AS order_ref,
                        CASE
                            WHEN gs % 5 = 0 THEN NULL
                            ELSE (
                                SELECT id
                                FROM historical_attribution ha
                                WHERE ha.order_ref = 'historical-' || gs::text
                            )
                        END AS attribution_event_id
                    FROM generate_series(1, :background_rows) AS gs
                )
                INSERT INTO public.b23_match_verdicts (
                    tenant_id,
                    attribution_event_id,
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
                    CAST(:tenant_id AS uuid),
                    attribution_event_id,
                    'stripe',
                    order_ref,
                    'historical-event-' || gs::text,
                    'historical-commerce-' || gs::text,
                    CASE WHEN gs % 5 = 0 THEN 'unmatched' ELSE 'matched_confirmed' END,
                    'high',
                    10000,
                    10000,
                    'USD',
                    CAST(:now_utc AS timestamptz) - interval '7 days',
                    CAST(:now_utc AS timestamptz) - interval '7 days',
                    CAST(:now_utc AS timestamptz) - interval '7 days',
                    CAST(:now_utc AS timestamptz) - interval '7 days',
                    10000,
                    10000,
                    10000,
                    0,
                    0,
                    'exact'
                FROM historical_rows
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "now_utc": now,
                "background_rows": B23_BATCH_MATCH_BACKGROUND_CARDINALITY,
            },
        )
        await conn.execute(
            text(
                """
                INSERT INTO public.b23_webhook_ingestion_logs (
                    tenant_id,
                    provider,
                    provider_native_event_reference,
                    ingestion_status,
                    failure_reason,
                    received_at
                )
                SELECT
                    CAST(:tenant_id AS uuid),
                    CASE WHEN gs % 2 = 0 THEN 'stripe' ELSE 'shopify' END,
                    'failed-webhook-' || gs::text,
                    'failed',
                    'signature_invalid',
                    CAST(:now_utc AS timestamptz) - (gs * interval '1 second')
                FROM generate_series(1, 1000) AS gs
                """
            ),
            {"tenant_id": str(tenant_id), "now_utc": now},
        )
        await conn.execute(
            text(
                """
                INSERT INTO public.worker_failed_jobs (
                    id,
                    task_id,
                    task_name,
                    queue,
                    worker,
                    task_args,
                    task_kwargs,
                    tenant_id,
                    error_type,
                    exception_class,
                    error_message,
                    retry_count,
                    status,
                    failed_at
                )
                SELECT
                    gen_random_uuid(),
                    'b23-p4-dlq-' || gs::text,
                    'app.tasks.revenue_verification.execute_b23_batch_match_engine',
                    'b23_match_engine',
                    'test-worker',
                    '[]'::jsonb,
                    '{}'::jsonb,
                    CAST(:tenant_id AS uuid),
                    'application_error',
                    'RuntimeError',
                    'synthetic runtime proof row',
                    0,
                    'pending',
                    CAST(:now_utc AS timestamptz) - (gs * interval '1 second')
                FROM generate_series(1, 1000) AS gs
                """
            ),
            {"tenant_id": str(tenant_id), "now_utc": now},
        )
        for table_name in (
            "attribution_events",
            "attribution_commerce_identities",
            "webhook_ingress_identities",
            "b23_match_verdicts",
            "b23_webhook_ingestion_logs",
            "worker_failed_jobs",
        ):
            await conn.execute(text(f"ANALYZE public.{table_name}"))
    return window_start, window_end


async def _explain(sql: str, params: dict[str, object]) -> str:
    async with engine.connect() as conn:
        if "tenant_id" in params:
            await conn.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(params["tenant_id"])},
            )
        await conn.execute(text("SET LOCAL plan_cache_mode = force_custom_plan"))
        result = await conn.execute(text(f"EXPLAIN (ANALYZE, BUFFERS) {sql}"), params)
        return "\n".join(str(row[0]) for row in result.fetchall())


def test_b23_p4_tasks_route_to_dedicated_queue_and_beat_preserves_transitions() -> None:
    routes = celery_app.conf.task_routes
    assert routes["app.tasks.revenue_verification.*"]["queue"] == QUEUE_B23_MATCH_ENGINE
    assert routes["app.tasks.llm.*"]["queue"] != QUEUE_B23_MATCH_ENGINE
    assert routes["app.tasks.bayesian.*"]["queue"] != QUEUE_B23_MATCH_ENGINE
    assert routes["app.tasks.attribution.*"]["queue"] != QUEUE_B23_MATCH_ENGINE

    schedule = build_beat_schedule()
    assert (
        schedule["b23-p3-pending-to-unmatched-transition"]["task"]
        == "app.tasks.revenue_verification.transition_stale_pending_to_unmatched_all_tenants"
    )
    assert (
        schedule["b23-p3-provisional-to-confirmed-transition"]["task"]
        == "app.tasks.revenue_verification.transition_stale_provisional_to_confirmed_all_tenants"
    )


@pytest.mark.asyncio(loop_scope="module")
async def test_b23_p4_dedicated_pool_acquires_under_adjacent_pool_pressure(
    test_tenant_pair,
) -> None:
    await _assert_table_exists("b23_match_verdicts")
    tenant_a, _ = test_tenant_pair
    held_connections = []
    try:
        for _ in range(settings.DATABASE_POOL_SIZE):
            held_connections.append(await engine.connect())
        started = time.perf_counter()
        async with get_b23_session(tenant_a) as session:
            assert (await session.execute(text("SELECT 1"))).scalar_one() == 1
        elapsed = time.perf_counter() - started
        assert elapsed < settings.B23_DATABASE_POOL_TIMEOUT_SECONDS
    finally:
        for conn in held_connections:
            await conn.close()


@pytest.mark.asyncio(loop_scope="module")
async def test_b23_p4_batch_processes_1000_prearrived_records_with_bounded_queries(
    test_tenant_pair,
) -> None:
    await _assert_table_exists("webhook_ingress_identities")
    await _assert_table_exists("b23_match_verdicts")
    tenant_a, _ = test_tenant_pair
    window_start, window_end = await _seed_b23_p4_benchmark_data(tenant_a)

    statement_count = 0

    def count_statement(*args, **kwargs) -> None:
        nonlocal statement_count
        statement_count += 1

    event.listen(b23_engine.sync_engine, "before_cursor_execute", count_statement)
    try:
        result = await execute_b23_batch_match_engine(
            tenant_id=tenant_a,
            window_start=window_start,
            window_end=window_end,
            chunk_size=B23_BATCH_MATCH_CHUNK_SIZE,
            max_records=1000,
        )
    finally:
        event.remove(b23_engine.sync_engine, "before_cursor_execute", count_statement)

    assert result.processed_count == 1000
    assert result.chunk_count == 2
    assert result.duration_seconds < B23_BATCH_MATCH_PERFORMANCE_THRESHOLD_SECONDS
    assert statement_count <= result.query_count_ceiling

    async with get_b23_session(tenant_a) as session:
        verdict_count = (
            await session.execute(
                text(
                    """
                    SELECT count(*)
                    FROM public.b23_match_verdicts
                    WHERE tenant_id = :tenant_id
                      AND provider_native_event_reference LIKE 'b23-p4-webhook-%'
                      AND status = 'matched_provisional'
                    """
                ),
                {"tenant_id": str(tenant_a)},
            )
        ).scalar_one()
    assert int(verdict_count) == 1000

    second = await execute_b23_batch_match_engine(
        tenant_id=tenant_a,
        window_start=window_start,
        window_end=window_end,
        chunk_size=B23_BATCH_MATCH_CHUNK_SIZE,
        max_records=1000,
    )
    assert second.processed_count == 0


@pytest.mark.asyncio(loop_scope="module")
async def test_b23_p4_plan_evidence_uses_p4_access_paths(test_tenant_pair) -> None:
    await _assert_table_exists("b23_match_verdicts")
    await _assert_table_exists("webhook_ingress_identities")
    tenant_a, _ = test_tenant_pair
    await _seed_b23_p4_benchmark_data(tenant_a)
    candidate_plan = await _explain(
        """
        WITH eligible_webhooks AS MATERIALIZED (
            SELECT
                wi.id,
                wi.tenant_id,
                wi.provider,
                wi.normalized_commerce_reference_value,
                wi.event_timestamp
            FROM public.webhook_ingress_identities wi
            WHERE wi.tenant_id = :tenant_id
              AND wi.verified_commerce_ingress_state = 'authenticity_verified'
              AND wi.event_timestamp >= now() - interval '2 hours'
            ORDER BY wi.event_timestamp ASC, wi.id ASC
            LIMIT 100
        )
        SELECT wi.id
        FROM eligible_webhooks wi
        JOIN LATERAL (
            SELECT aci.tenant_id, aci.attribution_event_id
            FROM public.attribution_commerce_identities aci
            WHERE aci.tenant_id = wi.tenant_id
              AND aci.provider = wi.provider
              AND aci.canonical_commerce_reference = wi.normalized_commerce_reference_value
            LIMIT 1
        ) aci ON true
        JOIN public.attribution_events ae
          ON ae.tenant_id = aci.tenant_id
         AND ae.id = aci.attribution_event_id
        ORDER BY wi.event_timestamp ASC, wi.id ASC
        """,
        {"tenant_id": str(tenant_a)},
    )
    assert "idx_attr_commerce_identity_tenant_provider_reference" in candidate_plan
    assert (
        "idx_b23_p4_webhook_identity_claim" in candidate_plan
        or "idx_webhook_ingress_identities_tenant_provider_created" in candidate_plan
        or "idx_webhook_ingress_identities_tenant_verified_state" in candidate_plan
    )


@pytest.mark.asyncio(loop_scope="module")
async def test_b23_p4_canonical_sql_telemetry_executes_and_is_plan_safe(
    test_tenant_pair,
) -> None:
    await _assert_table_exists("b23_match_verdicts")
    await _assert_table_exists("webhook_ingress_identities")
    tenant_a, _ = test_tenant_pair
    await _seed_b23_p4_benchmark_data(tenant_a)

    telemetry_expectations = {
        "01_rolling_24h_match_rate_by_tenant.sql": (
            "idx_b23_p4_match_rate_tenant_transition_status",
            "idx_b23_match_verdicts_tenant_status_transition",
            "idx_b23_match_verdicts_tenant_state_timestamps",
        ),
        "02_dlq_depth.sql": (
            "idx_b23_p4_worker_dlq_open_status_failed_at",
            "idx_worker_failed_jobs_status",
            "ix_public_celery_task_failures_tenant_id",
        ),
        "03_webhook_ingestion_failure_count_by_platform.sql": (
            "idx_b23_p4_webhook_failure_tenant_platform_time",
            "idx_b23_webhook_ingestion_logs_tenant_status_received",
            "idx_b23_webhook_ingestion_logs_tenant_provider_received",
        ),
    }
    async with get_b23_session(tenant_a) as session:
        for filename in telemetry_expectations:
            sql = (
                (TELEMETRY_SQL_DIR / filename)
                .read_text(encoding="utf-8")
                .strip()
                .rstrip(";")
            )
            result = await session.execute(text(sql), {"tenant_id": str(tenant_a)})
            rows = result.fetchall()
            if filename == "02_dlq_depth.sql":
                assert rows[0][0] is not None
            else:
                assert rows is not None

    for filename, accepted_indexes in telemetry_expectations.items():
        sql = (
            (TELEMETRY_SQL_DIR / filename)
            .read_text(encoding="utf-8")
            .strip()
            .rstrip(";")
        )
        plan = await _explain(sql, {"tenant_id": str(tenant_a)})
        assert any(index_name in plan for index_name in accepted_indexes), (
            f"{filename} did not use an accepted B2.3-P4 telemetry index "
            f"{accepted_indexes}. Plan:\n{plan}"
        )


def test_b23_p4_write_aware_index_strategy_is_not_bare_timestamp() -> None:
    migration_text = (
        REPO_ROOT
        / "alembic"
        / "versions"
        / "007_skeldir_foundation"
        / "202605061200_b23_p4_queue_performance_indexes.py"
    ).read_text(encoding="utf-8")
    assert "WHERE status IN ('pending', 'in_progress')" in migration_text
    assert "WHERE ingestion_status = 'failed'" in migration_text
    assert "WHERE raw_payload ? 'order_id'" in migration_text
    assert (
        "ON public.b23_webhook_ingestion_logs (\n                received_at"
        not in migration_text
    )
