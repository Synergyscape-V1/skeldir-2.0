"""C19 PostgreSQL proofs for allocation-verdict semantic authority."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from app.db.dsn import to_sync_postgres_dsn


pytestmark = pytest.mark.skipif(
    os.getenv("SKELDIR_B25_P13_C19_DB_PROOF") != "1",
    reason="B2.5-P13 C19 PostgreSQL physics proofs are opt-in locally",
)


def _engine(url: str):
    return create_engine(to_sync_postgres_dsn(url), pool_pre_ping=True, future=True)


def _bind(conn, tenant_id) -> None:
    conn.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant, false)"),
        {"tenant": str(tenant_id)},
    )


def test_c19_verdict_transition_atomically_projects_allocation_verification() -> None:
    migration_url = os.environ["MIGRATION_DATABASE_URL"]
    worker_url = os.environ.get("B23_DATABASE_URL") or os.environ["DATABASE_URL"]
    migration_engine = _engine(migration_url)
    worker_engine = _engine(worker_url)
    tenant_id = uuid4()
    event_id = uuid4()
    verdict_id = uuid4()
    allocation_id = uuid4()
    occurred_at = datetime.now(timezone.utc) - timedelta(days=3)
    transitioned_at = datetime.now(timezone.utc)

    try:
        with migration_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO public.tenants (id, name, api_key_hash, notification_email) "
                    "VALUES (:tenant, :name, :hash, :email)"
                ),
                {
                    "tenant": str(tenant_id),
                    "name": f"c19-{tenant_id.hex[:8]}",
                    "hash": uuid4().hex,
                    "email": f"c19-{tenant_id.hex[:8]}@example.invalid",
                },
            )

        with worker_engine.begin() as conn:
            _bind(conn, tenant_id)
            conn.execute(
                text(
                    """
                    INSERT INTO public.attribution_events (
                        id, tenant_id, occurred_at, correlation_id, session_id,
                        revenue_cents, raw_payload, idempotency_key, event_type,
                        channel, conversion_value_cents, currency,
                        event_timestamp, processed_at, processing_status
                    ) VALUES (
                        :event, :tenant, :at, :correlation, :session,
                        12000, '{}'::jsonb, :idempotency, 'purchase',
                        'direct', 12000, 'USD', :at, :at, 'pending'
                    )
                    """
                ),
                {
                    "event": str(event_id),
                    "tenant": str(tenant_id),
                    "at": occurred_at,
                    "correlation": str(uuid4()),
                    "session": str(uuid4()),
                    "idempotency": f"c19:{uuid4().hex}",
                },
            )
            conn.execute(
                text(
                    """
                    INSERT INTO public.b23_match_verdicts (
                        id, tenant_id, attribution_event_id, provider,
                        canonical_commerce_reference,
                        provider_native_event_reference,
                        provider_native_commerce_reference, status, match_quality,
                        attributed_amount_minor, verified_amount_minor,
                        currency_code, pending_since, provisional_expires_at,
                        last_transition_at,
                        canonical_expected_gross_amount_minor,
                        canonical_captured_gross_amount_minor,
                        canonical_net_verified_amount_minor,
                        discrepancy_amount_minor, discrepancy_ratio_bps,
                        discrepancy_band
                    ) VALUES (
                        :verdict, :tenant, :event, 'stripe', :commerce,
                        :provider_event, :commerce, 'matched_provisional', 'high',
                        12000, 12000, 'USD', :at, :at, :at,
                        12000, 12000, 12000, 0, 0, 'exact'
                    )
                    """
                ),
                {
                    "verdict": str(verdict_id),
                    "tenant": str(tenant_id),
                    "event": str(event_id),
                    "commerce": f"pi_c19_{uuid4().hex}",
                    "provider_event": f"evt_c19_{uuid4().hex}",
                    "at": occurred_at,
                },
            )
            conn.execute(
                text(
                    """
                    INSERT INTO public.attribution_allocations (
                        id, tenant_id, event_id, channel_code,
                        allocated_revenue_cents, allocation_ratio, model_version,
                        model_type, confidence_score, verified,
                        verification_source, verification_timestamp
                    ) VALUES (
                        :allocation, :tenant, :event, 'direct',
                        12000, 1.0, 'c19', 'last_touch', 1.0, true,
                        'caller_fabricated', :at
                    )
                    """
                ),
                {
                    "allocation": str(allocation_id),
                    "tenant": str(tenant_id),
                    "event": str(event_id),
                    "at": occurred_at,
                },
            )
            before = conn.execute(
                text(
                    "SELECT verified, verification_source, verification_timestamp "
                    "FROM public.attribution_allocations WHERE id = :allocation"
                ),
                {"allocation": str(allocation_id)},
            ).one()
            assert tuple(before) == (False, None, None)

            conn.execute(
                text(
                    """
                    UPDATE public.b23_match_verdicts
                       SET status = 'matched_confirmed',
                           confirmed_at = :at,
                           last_transition_at = :at,
                           updated_at = :at
                     WHERE id = :verdict
                    """
                ),
                {"verdict": str(verdict_id), "at": transitioned_at},
            )
            after = conn.execute(
                text(
                    "SELECT verified, verification_source, verification_timestamp "
                    "FROM public.attribution_allocations WHERE id = :allocation"
                ),
                {"allocation": str(allocation_id)},
            ).one()
            assert tuple(after) == (True, "b23_match_verdict", transitioned_at)
            dirty_windows = conn.execute(
                text(
                    """
                    SELECT DISTINCT source_window_start, source_window_end
                    FROM public.b24_dirty_events
                    WHERE tenant_id = :tenant
                      AND dirty_reason IN (
                        'attribution_allocations_financial_event_changed',
                        'b23_match_verdicts_financial_event_changed'
                      )
                    """
                ),
                {"tenant": str(tenant_id)},
            ).all()
            assert dirty_windows
            expected_start = occurred_at.replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            assert all(row[0] == expected_start for row in dirty_windows)
            assert all(row[1] == expected_start + timedelta(days=1) for row in dirty_windows)

        other_tenant = uuid4()
        with migration_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO public.tenants (id, name, api_key_hash, notification_email) "
                    "VALUES (:tenant, :name, :hash, :email)"
                ),
                {
                    "tenant": str(other_tenant),
                    "name": f"c19-other-{other_tenant.hex[:8]}",
                    "hash": uuid4().hex,
                    "email": f"c19-other-{other_tenant.hex[:8]}@example.invalid",
                },
            )
        with worker_engine.begin() as conn:
            _bind(conn, other_tenant)
            assert conn.scalar(
                text(
                    "SELECT count(*) FROM public.attribution_allocations "
                    "WHERE id = :allocation"
                ),
                {"allocation": str(allocation_id)},
            ) == 0
    finally:
        # The proof runs only against a disposable database. Retaining the rows
        # avoids exercising tenant teardown semantics, which are orthogonal to
        # the verified-allocation invariant being measured here.
        worker_engine.dispose()
        migration_engine.dispose()
