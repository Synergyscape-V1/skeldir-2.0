"""C6 PostgreSQL physics proofs for worker authority and planner reachability."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from celery import signals
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import create_async_engine

from app.bayesian.dirty_marker import append_dirty_event
from app.bayesian.fit_planner import MAX_WAIT_SECONDS, QUIET_PERIOD_SECONDS
from app.bayesian.feature_authority import (
    FeatureAuthorityStatus,
    SourceWindowFeatureAuthority,
    upsert_source_window_feature_authority,
)
from app.bayesian.input_contract import MIN_SPARSE_PRIVACY_FLOOR
from app.bayesian.model_spec import B24_P6_MODEL_TYPE, B24_P6_MODEL_VERSION
from app.bayesian.resource_bounds import B24_RESOURCE_POLICY_VERSION
from app.bayesian.source_snapshot import compute_source_snapshot_hash
from app.core.secrets import get_database_url
from app.db.dsn import to_asyncpg_postgres_dsn, to_sync_postgres_dsn
from app.db.session import AsyncSessionLocal, get_session
from app.tasks.bayesian import FIT_PLANNER_TASK_NAME, plan_due_fit_intents


pytestmark = pytest.mark.skipif(
    os.getenv("SKELDIR_B25_P13_C6_DB_PROOF") != "1",
    reason="B2.5-P13 C6 PostgreSQL physics proofs are opt-in locally",
)

START = datetime(2026, 7, 1, tzinfo=timezone.utc)
END = START + timedelta(days=31)


def _app_url() -> str:
    return (
        make_url(get_database_url())
        .set(username="app_user", password="app_user")
        .render_as_string(hide_password=False)
    )


def _sync_engine(url: str):
    return create_engine(to_sync_postgres_dsn(url), pool_pre_ping=True)


def _has_execute(conn, signature: str) -> bool:
    return bool(
        conn.scalar(
            text("SELECT has_function_privilege(current_user, :sig, 'EXECUTE')"),
            {"sig": signature},
        )
    )


def test_c6_worker_authority_is_not_reachable_from_tenant_runtime() -> None:
    """Effective grants and actual calls both deny worker authority to app_user."""

    worker_engine = _sync_engine(get_database_url())
    app_engine = _sync_engine(_app_url())
    register_sig = (
        "public.b24_register_worker_process_authority"
        "(text,integer,integer,text,text,integer)"
    )
    claim_sig = (
        "public.b24_claim_fit_dispatch"
        "(uuid,uuid,text,uuid,text,text,integer,text,integer,integer)"
    )
    planner_sig = "public.b24_due_fit_planner_tenants(text,integer)"
    try:
        with app_engine.connect() as conn:
            assert conn.scalar(text("SELECT current_user")) == "app_user"
            assert not _has_execute(conn, register_sig)
            assert not _has_execute(conn, claim_sig)
            assert not _has_execute(conn, planner_sig)
            assert not conn.scalar(
                text(
                    "SELECT has_table_privilege(current_user, "
                    "'public.bayesian_model_fits', 'INSERT')"
                )
            )
            assert not conn.scalar(
                text(
                    "SELECT has_table_privilege(current_user, "
                    "'public.b24_fit_dispatch_outbox', 'UPDATE')"
                )
            )
            with pytest.raises(ProgrammingError, match="permission denied"):
                conn.execute(
                    text(
                        "SELECT public.b24_register_worker_process_authority("
                        ":generation, 9911, 1, :fingerprint, :token, 60)"
                    ),
                    {
                        "generation": f"c6-denied-{uuid4().hex}",
                        "fingerprint": "a" * 64,
                        "token": f"c6-denied-token-{uuid4().hex}",
                    },
                )
            conn.rollback()
            conn.execute(text("SET ROLE app_ro"))
            assert not _has_execute(conn, register_sig)
            assert not _has_execute(conn, claim_sig)
            assert not _has_execute(conn, planner_sig)
        with worker_engine.connect() as conn:
            assert conn.scalar(text("SELECT current_user")) == "app_worker"
            assert not conn.scalar(
                text("SELECT has_schema_privilege(current_user, 'public', 'CREATE')")
            )
            assert conn.scalar(
                text(
                    "SELECT has_table_privilege(current_user, "
                    "'public.b24_fit_planner_wakeups', 'INSERT')"
                )
            )
            trigger_function = conn.execute(
                text(
                    "SELECT proc.proname, pg_get_userbyid(proc.proowner) "
                    "FROM pg_trigger trigger "
                    "JOIN pg_proc proc ON proc.oid = trigger.tgfoid "
                    "WHERE trigger.tgrelid = "
                    "'public.b24_dirty_events'::regclass "
                    "AND trigger.tgname = 'trg_b24_signal_fit_planner_wakeup'"
                )
            ).one()
            assert tuple(trigger_function) == (
                "b24_signal_fit_planner_wakeup_coalesced",
                "app_worker",
            )
            wakeup_rls = conn.execute(
                text(
                    "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
                    "WHERE oid = 'public.b24_fit_planner_wakeups'::regclass"
                )
            ).one()
            assert tuple(wakeup_rls) == (True, True)
            planner_owners = conn.execute(
                text(
                    "SELECT pg_get_userbyid(proowner) FROM pg_proc WHERE oid IN ("
                    "'public.b24_due_fit_planner_tenants(text,integer)'::regprocedure,"
                    "'public.b24_complete_fit_planner_wakeup"
                    "(uuid,text,bigint,boolean,integer,integer)'"
                    "::regprocedure)"
                )
            ).scalars()
            assert set(planner_owners) == {"app_worker"}
            assert _has_execute(conn, register_sig)
            assert _has_execute(conn, claim_sig)
            assert _has_execute(conn, planner_sig)
            assert conn.scalar(
                text(
                    "SELECT has_table_privilege(current_user, "
                    "'public.bayesian_model_fits', 'INSERT')"
                )
            )
            assert conn.scalar(
                text(
                    "SELECT has_table_privilege(current_user, "
                    "'public.b24_fit_dispatch_outbox', 'UPDATE')"
                )
            )
    finally:
        app_engine.dispose()
        worker_engine.dispose()


@pytest.mark.asyncio
async def test_c6_pending_wakeup_coalesces_and_leased_wakeup_is_invalidated() -> None:
    """Pending signals avoid hot-row writes; leased signals remain replay-safe."""

    tenant_id = uuid4()
    suffix = uuid4().hex[:8]
    worker_engine = _sync_engine(get_database_url())
    app_engine = create_async_engine(
        to_asyncpg_postgres_dsn(_app_url()), future=True, pool_pre_ping=True
    )

    async def append_signal(source_event_id: str, observed_at: datetime) -> None:
        async with app_engine.begin() as conn:
            await conn.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant, true)"),
                {"tenant": str(tenant_id)},
            )
            await append_dirty_event(
                conn,
                tenant_id=tenant_id,
                source_window_start=START,
                source_window_end=END,
                dirty_reason="b25_p13_c6_wakeup_coalescing",
                source_family="attribution_events",
                source_event_id=source_event_id,
                observed_at=observed_at,
            )

    try:
        with worker_engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO public.tenants (
                        id, name, api_key_hash, notification_email
                    ) VALUES (:tenant, :name, :api_hash, :email)
                    """
                ),
                {
                    "tenant": str(tenant_id),
                    "name": f"P13 C6 coalescing {suffix}",
                    "api_hash": f"p13-c6-coalescing-{suffix}",
                    "email": f"p13-c6-coalescing-{suffix}@example.invalid",
                },
            )

        first_observed = START - timedelta(days=30)
        await append_signal("pending-1", first_observed)
        await append_signal("pending-2", first_observed + timedelta(seconds=1))

        with worker_engine.begin() as conn:
            pending = conn.execute(
                text(
                    """
                    SELECT wakeup_revision, status, lease_owner, observed_at
                    FROM public.b24_fit_planner_wakeups
                    WHERE tenant_id = :tenant
                    """
                ),
                {"tenant": str(tenant_id)},
            ).one()
            assert pending.wakeup_revision == 1
            assert pending.status == "pending"
            assert pending.lease_owner is None
            assert pending.observed_at == first_observed

            leased = conn.execute(
                text(
                    "SELECT tenant_id, wakeup_revision FROM "
                    "public.b24_due_fit_planner_tenants(:owner, 100)"
                ),
                {"owner": f"coalescing-{suffix}"},
            ).all()
            assert (tenant_id, 1) in {
                (UUID(str(row.tenant_id)), int(row.wakeup_revision)) for row in leased
            }

        await append_signal(
            "leased-invalidation", first_observed + timedelta(seconds=2)
        )

        with worker_engine.begin() as conn:
            invalidated = conn.execute(
                text(
                    """
                    SELECT wakeup_revision, status, lease_owner, lease_expires_at
                    FROM public.b24_fit_planner_wakeups
                    WHERE tenant_id = :tenant
                    """
                ),
                {"tenant": str(tenant_id)},
            ).one()
            assert tuple(invalidated) == (2, "pending", None, None)
            conn.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant, false)"),
                {"tenant": str(tenant_id)},
            )
            stale_ack = conn.scalar(
                text(
                    "SELECT public.b24_complete_fit_planner_wakeup("
                    ":tenant, :owner, 1, true, :quiet, :max_wait)"
                ),
                {
                    "tenant": str(tenant_id),
                    "owner": f"coalescing-{suffix}",
                    "quiet": QUIET_PERIOD_SECONDS,
                    "max_wait": MAX_WAIT_SECONDS,
                },
            )
            # C7: acknowledgement returns the obligation's disposition. A stale
            # revision may never delete the newer wakeup.
            assert stale_ack == "stale_revision", stale_ack

        await append_signal("pending-3", first_observed + timedelta(seconds=3))
        with worker_engine.begin() as conn:
            assert (
                conn.scalar(
                    text(
                        "SELECT wakeup_revision FROM public.b24_fit_planner_wakeups "
                        "WHERE tenant_id = :tenant"
                    ),
                    {"tenant": str(tenant_id)},
                )
                == 2
            )
    finally:
        with worker_engine.begin() as conn:
            conn.execute(
                text(
                    "DELETE FROM public.b24_fit_planner_wakeups "
                    "WHERE tenant_id = :tenant"
                ),
                {"tenant": str(tenant_id)},
            )
        await app_engine.dispose()
        worker_engine.dispose()


async def _seed_real_financial_source_change(tenant_id: UUID, suffix: str) -> None:
    """Use the runtime identity and production dirty marker to create stimulus."""

    app_engine = create_async_engine(
        to_asyncpg_postgres_dsn(_app_url()), future=True, pool_pre_ping=True
    )
    row_count = MIN_SPARSE_PRIVACY_FLOOR + 4
    try:
        async with app_engine.begin() as conn:
            await conn.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant, true)"),
                {"tenant": str(tenant_id)},
            )
            for index in range(row_count):
                channel = f"c6_{suffix}_{index:02d}"
                event_id = uuid4()
                verdict_id = uuid4()
                occurred_at = START + timedelta(days=index, seconds=index)
                amount_minor = 10_000 + index
                await conn.execute(
                    text(
                        """
                        INSERT INTO public.channel_taxonomy (
                            code, family, is_paid, display_name, state
                        ) VALUES (:channel, 'b25_p13_c6', true, :label, 'active')
                        ON CONFLICT (code) DO NOTHING
                        """
                    ),
                    {"channel": channel, "label": f"C6 {suffix} {index}"},
                )
                await conn.execute(
                    text(
                        """
                        INSERT INTO public.attribution_events (
                            id, tenant_id, occurred_at, correlation_id, session_id,
                            revenue_cents, raw_payload, idempotency_key, event_type,
                            channel, campaign_id, conversion_value_cents, currency,
                            event_timestamp, processed_at, processing_status
                        ) VALUES (
                            :event_id, :tenant, :occurred_at, :correlation_id,
                            :session_id, :amount, CAST(:payload AS jsonb), :key,
                            'conversion', :channel, :campaign, :amount, 'USD',
                            :occurred_at, :occurred_at, 'processed'
                        )
                        """
                    ),
                    {
                        "event_id": str(event_id),
                        "tenant": str(tenant_id),
                        "occurred_at": occurred_at,
                        "correlation_id": str(uuid4()),
                        "session_id": str(uuid4()),
                        "amount": amount_minor,
                        "payload": json.dumps({"source": "c6_planner_journey"}),
                        "key": f"c6:{suffix}:{index}",
                        "channel": channel,
                        "campaign": f"c6-campaign-{suffix}-{index:02d}",
                    },
                )
                await conn.execute(
                    text(
                        """
                        INSERT INTO public.b23_match_verdicts (
                            id, tenant_id, attribution_event_id, provider,
                            canonical_commerce_reference,
                            provider_native_event_reference,
                            provider_native_commerce_reference, status, match_quality,
                            attributed_amount_minor, verified_amount_minor,
                            currency_code, confirmed_at, last_transition_at,
                            canonical_expected_gross_amount_minor,
                            canonical_captured_gross_amount_minor,
                            canonical_net_verified_amount_minor,
                            discrepancy_amount_minor, discrepancy_ratio_bps,
                            discrepancy_band
                        ) VALUES (
                            :verdict, :tenant, :event, 'stripe', :commerce,
                            :provider_event, :commerce, 'matched_confirmed', 'high',
                            :amount, :amount, 'USD', :occurred_at, :occurred_at,
                            :amount, :amount, :amount, 0, 0, 'exact'
                        )
                        """
                    ),
                    {
                        "verdict": str(verdict_id),
                        "tenant": str(tenant_id),
                        "event": str(event_id),
                        "commerce": f"c6-order-{suffix}-{index:02d}",
                        "provider_event": f"c6-event-{suffix}-{index:02d}",
                        "amount": amount_minor,
                        "occurred_at": occurred_at,
                    },
                )
                await conn.execute(
                    text(
                        """
                        INSERT INTO public.b23_revenue_events (
                            tenant_id, match_verdict_id, provider,
                            provider_native_event_reference,
                            provider_native_commerce_reference,
                            canonical_commerce_reference, event_type, currency_code,
                            event_occurred_at, captured_amount_minor,
                            net_effect_sign, is_gross_capture_correction
                        ) VALUES (
                            :tenant, :verdict, 'stripe', :provider_event,
                            :commerce, :commerce, 'payment_capture', 'USD',
                            :occurred_at, :amount, 1, false
                        )
                        """
                    ),
                    {
                        "tenant": str(tenant_id),
                        "verdict": str(verdict_id),
                        "provider_event": f"c6-capture-{suffix}-{index:02d}",
                        "commerce": f"c6-order-{suffix}-{index:02d}",
                        "occurred_at": occurred_at,
                        "amount": amount_minor,
                    },
                )
            await append_dirty_event(
                conn,
                tenant_id=tenant_id,
                source_window_start=START,
                source_window_end=END,
                dirty_reason="b25_p13_c6_financial_source_change",
                source_family="b23_revenue_events",
                source_event_id=f"c6-source-change-{suffix}",
                model_type=B24_P6_MODEL_TYPE,
                model_version=B24_P6_MODEL_VERSION,
                observed_at=datetime.now(timezone.utc) - timedelta(minutes=20),
            )
    finally:
        await app_engine.dispose()


@pytest.mark.asyncio
async def test_c6_real_stimulus_reaches_registered_planner_and_one_dispatch() -> None:
    """Production dirty marker -> registered task -> planner -> claim/outbox."""

    tenant_id = uuid4()
    suffix = uuid4().hex[:8]
    async with AsyncSessionLocal() as session:
        await session.execute(
            text(
                """
                INSERT INTO public.tenants (id, name, api_key_hash, notification_email)
                VALUES (:tenant, :name, :api_hash, :email)
                """
            ),
            {
                "tenant": str(tenant_id),
                "name": f"P13 C6 {suffix}",
                "api_hash": f"p13-c6-{suffix}",
                "email": f"p13-c6-{suffix}@example.invalid",
            },
        )
        await session.commit()

    await _seed_real_financial_source_change(tenant_id, suffix)

    async with AsyncSessionLocal() as snapshot_session:
        snapshot = await compute_source_snapshot_hash(
            snapshot_session,
            tenant_id=tenant_id,
            model_type=B24_P6_MODEL_TYPE,
            model_version=B24_P6_MODEL_VERSION,
            source_window_start=START,
            source_window_end=END,
        )
    assert snapshot.preflight.is_eligible, snapshot.preflight

    async with get_session(tenant_id) as session:
        await upsert_source_window_feature_authority(
            session,
            authority=SourceWindowFeatureAuthority(
                tenant_id=tenant_id,
                model_type=B24_P6_MODEL_TYPE,
                model_version=B24_P6_MODEL_VERSION,
                source_window_start=START,
                source_window_end=END,
                source_snapshot_hash=snapshot.source_snapshot_hash,
                channel_count=MIN_SPARSE_PRIVACY_FLOOR + 4,
                currency_count=1,
                provider_count=1,
                campaign_or_feature_count=MIN_SPARSE_PRIVACY_FLOOR + 4,
                freshness_status=FeatureAuthorityStatus.FRESH,
                policy_version=B24_RESOURCE_POLICY_VERSION,
                computed_at=datetime.now(timezone.utc),
            ),
        )

    # Send the real Celery lifecycle signal; the same receiver gates production
    # task consumption and registers the process generation in PostgreSQL.
    signals.worker_init.send(sender="b25-p13-c6-proof")
    assert getattr(plan_due_fit_intents, "name", None) == FIT_PLANNER_TASK_NAME
    # This proof shares the workflow database with the full P13 composition
    # suite, which deliberately leaves an older pending dirty-event wakeup as
    # evidence. Exercise the real global scheduler until this stimulus is the
    # one delivered; never assume an otherwise-empty planner ledger.
    target_result = None
    for _ in range(25):
        result = plan_due_fit_intents.run(tenant_batch_size=1, candidate_limit=1)
        async with get_session(tenant_id) as delivery_session:
            target_dispatches = int(
                (
                    await delivery_session.scalar(
                        text(
                            """
                            SELECT count(*)
                            FROM public.bayesian_model_fits fit
                            JOIN public.b24_fit_dispatch_outbox outbox
                              ON outbox.tenant_id = fit.tenant_id
                             AND outbox.fit_id = fit.id
                            WHERE fit.tenant_id = :tenant
                              AND fit.source_snapshot_hash = :snapshot
                            """
                        ),
                        {
                            "tenant": str(tenant_id),
                            "snapshot": snapshot.source_snapshot_hash,
                        },
                    )
                )
                or 0
            )
        if target_dispatches == 1:
            target_result = result
            break
    # C7 reports how each planning obligation was disposed of. The five
    # production counters are unchanged; the disposition is asserted separately
    # because it is a conservation claim, not a throughput claim.
    dispositions = dict(target_result.pop("wakeup_dispositions"))
    assert target_result == {
        "status": "completed",
        "tenant_count": 1,
        "planned_count": 1,
        "dispatchable_count": 1,
        "reused_count": 0,
    }
    # The seeded financial rows invalidate their own source windows through the
    # C7 contract triggers, so unplanned work still exists for this tenant when
    # the pass completes. The obligation must therefore be conserved -- deferred
    # until its quiet period matures, or retained when already eligible -- and
    # must never be deleted while that work is outstanding.
    assert sorted(dispositions) in (["deferred"], ["retained_eligible"]), dispositions
    assert sum(dispositions.values()) == 1, dispositions

    # Replay must not mint a second dispatch for the same snapshot. It may
    # legitimately plan a different, still-outstanding window, so the invariant
    # is asserted against this snapshot's authority rather than against the
    # planner having nothing left to do.
    replay = plan_due_fit_intents.run(tenant_batch_size=1, candidate_limit=1)
    assert replay["status"] == "completed"
    async with get_session(tenant_id) as replay_session:
        replayed_dispatches = int(
            (
                await replay_session.scalar(
                    text(
                        """
                        SELECT count(*)
                        FROM public.bayesian_model_fits fit
                        JOIN public.b24_fit_dispatch_outbox outbox
                          ON outbox.tenant_id = fit.tenant_id
                         AND outbox.fit_id = fit.id
                        WHERE fit.tenant_id = :tenant
                          AND fit.source_snapshot_hash = :snapshot
                        """
                    ),
                    {
                        "tenant": str(tenant_id),
                        "snapshot": snapshot.source_snapshot_hash,
                    },
                )
            )
            or 0
        )
    assert replayed_dispatches == 1, replayed_dispatches

    async with get_session(tenant_id) as session:
        row = (
            (
                await session.execute(
                    text(
                        """
                        SELECT fit.id AS fit_id, fit.status AS fit_status,
                               outbox.id AS dispatch_id,
                               outbox.status AS dispatch_status,
                               dirty.status AS dirty_status
                        FROM public.bayesian_model_fits fit
                        JOIN public.b24_fit_dispatch_outbox outbox
                          ON outbox.tenant_id = fit.tenant_id
                         AND outbox.fit_id = fit.id
                        JOIN public.b24_dirty_events dirty
                          ON dirty.tenant_id = fit.tenant_id
                         AND dirty.model_type = fit.model_type
                         AND dirty.model_version = fit.model_version
                         AND dirty.source_window_start = fit.source_window_start
                         AND dirty.source_window_end = fit.source_window_end
                        WHERE fit.tenant_id = :tenant
                          AND fit.source_snapshot_hash = :snapshot
                        """
                    ),
                    {
                        "tenant": str(tenant_id),
                        "snapshot": snapshot.source_snapshot_hash,
                    },
                )
            )
            .mappings()
            .all()
        )
    assert len(row) == 1, row
    assert row[0]["fit_status"] == "queued", row[0]
    assert row[0]["dispatch_status"] == "pending", row[0]
    assert row[0]["dirty_status"] == "claimed", row[0]
