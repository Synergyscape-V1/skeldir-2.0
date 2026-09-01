"""B2.5-P13 C9: work that has become impossible stops being retried.

A feature-authority request names one exact source snapshot. The producer
refuses to write anything when the source has already moved -- correctly, since
measuring a state it cannot observe is how a hybrid authority gets created. But
refusing is only half an answer. The other half is what happens to the request.

It was parked with a sixty-second retry, unconditionally. That conflates two
situations a scheduler must tell apart:

    not yet          a writer is mid-flight; the hash will match shortly
    never again      the snapshot has been superseded; those bytes are gone

The first resolves on its own. The second does not resolve at any horizon, and
re-queuing it every minute is churn against a question that already has a
permanent answer. Nothing in the system distinguished them, so an obsolete
request would be retried for the life of the deployment.

These proofs run the real ``build_feature_authority`` task against real source
mutations and observe the request's own lifecycle over several horizons.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

from app.bayesian.model_identity import active_identity
from app.core.secrets import get_database_url
from app.db.dsn import to_sync_postgres_dsn


pytestmark = pytest.mark.skipif(
    os.getenv("SKELDIR_B25_P13_C9_DB_PROOF") != "1",
    reason="B2.5-P13 C9 supersession proofs are opt-in locally",
)

ACTIVE = active_identity()
DAY = datetime(2027, 1, 4, tzinfo=timezone.utc)
WINDOW_START = DAY
WINDOW_END = DAY + timedelta(days=20)


def _engine(url: str | None = None):
    return create_engine(
        to_sync_postgres_dsn(url or get_database_url()),
        pool_pre_ping=True,
        future=True,
    )


def _migration_engine():
    return _engine(os.environ.get("MIGRATION_DATABASE_URL"))


def _bind(conn, tenant_id) -> None:
    conn.execute(
        text("SELECT set_config('app.current_tenant_id', :t, false)"),
        {"t": str(tenant_id)},
    )


def _new_tenant(conn, label: str):
    tenant_id = uuid.uuid4()
    conn.execute(
        text(
            "INSERT INTO public.tenants (id, name, api_key_hash,"
            " notification_email) VALUES (:t, :n, :h, :e)"
        ),
        {
            "t": str(tenant_id),
            "n": f"c9-supersede-{label}-{tenant_id.hex[:8]}",
            "h": uuid.uuid4().hex,
            "e": f"c9s-{tenant_id.hex[:8]}@example.invalid",
        },
    )
    _bind(conn, tenant_id)
    return tenant_id


def _seed_settlement(conn, tenant_id, *, index: int, occurred_at: datetime) -> None:
    event_id = uuid.uuid4()
    verdict_id = uuid.uuid4()
    channel = f"c9s_channel_{index:03d}"
    amount = 50_000 + index
    conn.execute(
        text(
            "INSERT INTO public.channel_taxonomy (code, family, is_paid,"
            " display_name, state) VALUES (:c, 'b25_p13_c9s', true, :d, 'active')"
            " ON CONFLICT (code) DO NOTHING"
        ),
        {"c": channel, "d": f"C9S {index}"},
    )
    conn.execute(
        text(
            "INSERT INTO public.attribution_events (id, tenant_id, occurred_at,"
            " correlation_id, session_id, revenue_cents, raw_payload,"
            " idempotency_key, event_type, channel, campaign_id,"
            " conversion_value_cents, currency, event_timestamp, processed_at,"
            " processing_status) VALUES (:e, :t, :at, :corr, :sess, :amt,"
            " CAST(:payload AS jsonb), :key, 'conversion', :ch, :camp, :amt,"
            " 'USD', :at, :at, 'processed')"
        ),
        {
            "e": str(event_id),
            "t": str(tenant_id),
            "at": occurred_at,
            "corr": str(uuid.uuid4()),
            "sess": str(uuid.uuid4()),
            "amt": amount,
            "payload": json.dumps({"source": "b25_p13_c9_supersession"}),
            "key": f"c9s:{tenant_id.hex[:8]}:{index}",
            "ch": channel,
            "camp": f"c9s-campaign-{index:03d}",
        },
    )
    # C19 derives B2.4 source membership from verified allocation lineage, so a
    # settlement without one produces the insufficient-data sentinel hash rather
    # than a content hash -- and two sentinels are equal, which would make a
    # supersession proof vacuous. Seeded unverified; the verdict projects it.
    conn.execute(
        text(
            "INSERT INTO public.attribution_allocations (id, tenant_id,"
            " event_id, channel_code, allocated_revenue_cents,"
            " allocation_ratio, model_version, model_type, confidence_score,"
            " verified) VALUES (:a, :t, :e, :ch, :amt, 1.0,"
            " 'b25-p13-c9-supersession-v1', 'last_touch', 1.0, false)"
        ),
        {
            "a": str(uuid.uuid4()),
            "t": str(tenant_id),
            "e": str(event_id),
            "ch": channel,
            "amt": amount,
        },
    )
    conn.execute(
        text(
            "INSERT INTO public.b23_match_verdicts (id, tenant_id,"
            " attribution_event_id, provider, canonical_commerce_reference,"
            " provider_native_event_reference,"
            " provider_native_commerce_reference, status, match_quality,"
            " attributed_amount_minor, verified_amount_minor, currency_code,"
            " confirmed_at, last_transition_at,"
            " canonical_expected_gross_amount_minor,"
            " canonical_captured_gross_amount_minor,"
            " canonical_net_verified_amount_minor, discrepancy_amount_minor,"
            " discrepancy_ratio_bps, discrepancy_band) VALUES (:v, :t, :e,"
            " 'stripe', :ref, :pev, :ref, 'matched_confirmed', 'high', :amt,"
            " :amt, 'USD', :at, :at, :amt, :amt, :amt, 0, 0, 'exact')"
        ),
        {
            "v": str(verdict_id),
            "t": str(tenant_id),
            "e": str(event_id),
            "ref": f"c9s-order-{tenant_id.hex[:8]}-{index:04d}",
            "pev": f"c9s-event-{tenant_id.hex[:8]}-{index:04d}",
            "amt": amount,
            "at": occurred_at,
        },
    )
    conn.execute(
        text(
            "INSERT INTO public.b23_revenue_events (tenant_id, match_verdict_id,"
            " provider, provider_native_event_reference,"
            " provider_native_commerce_reference, canonical_commerce_reference,"
            " event_type, currency_code, event_occurred_at,"
            " captured_amount_minor, net_effect_sign,"
            " is_gross_capture_correction) VALUES (:t, :v, 'stripe', :pev, :ref,"
            " :ref, 'payment_capture', 'USD', :at, :amt, 1, false)"
        ),
        {
            "t": str(tenant_id),
            "v": str(verdict_id),
            "pev": f"c9s-capture-{tenant_id.hex[:8]}-{index:04d}",
            "ref": f"c9s-order-{tenant_id.hex[:8]}-{index:04d}",
            "at": occurred_at,
            "amt": amount,
        },
    )


def _observed_hash(tenant_id) -> str:
    from app.bayesian.feature_cardinality import (
        measure_source_window_within_one_snapshot,
    )

    async def go() -> str:
        snapshot, _ = await measure_source_window_within_one_snapshot(
            tenant_id=tenant_id,
            model_type=ACTIVE.model_type,
            model_version=ACTIVE.model_version,
            source_window_start=WINDOW_START,
            source_window_end=WINDOW_END,
        )
        return snapshot.source_snapshot_hash

    return asyncio.run(go())


def _open_request(conn, tenant_id, source_hash: str, *, max_retries: int) -> None:
    conn.execute(
        text(
            "INSERT INTO public.b24_feature_authority_build_requests (tenant_id,"
            " model_type, model_version, source_window_start, source_window_end,"
            " source_snapshot_hash, status, authority_reason, retry_count,"
            " max_retries, requested_at, policy_version, created_at, updated_at)"
            " VALUES (:t, :mt, :mv, :ws, :we, :h, 'authority_build_requested',"
            " 'cardinality_authority_missing', 0, :mr, now(),"
            " 'b24-resource-policy-v1', now(), now())"
        ),
        {
            "t": str(tenant_id),
            "mt": ACTIVE.model_type,
            "mv": ACTIVE.model_version,
            "ws": WINDOW_START,
            "we": WINDOW_END,
            "h": source_hash,
            "mr": max_retries,
        },
    )
    conn.execute(
        text(
            "INSERT INTO public.b24_dirty_events (tenant_id, model_type,"
            " model_version, source_window_start, source_window_end,"
            " source_snapshot_hash, dirty_reason, source_family, observed_at,"
            " status) VALUES (:t, :mt, :mv, :ws, :we, :h, 'c9_supersession',"
            " 'b23_revenue_events', now() - interval '600 seconds',"
            " 'authority_waiting')"
        ),
        {
            "t": str(tenant_id),
            "mt": ACTIVE.model_type,
            "mv": ACTIVE.model_version,
            "ws": WINDOW_START,
            "we": WINDOW_END,
            "h": source_hash,
        },
    )


def _build(tenant_id, source_hash: str) -> dict:
    """Run the real build task body for one requested snapshot."""

    import app.tasks.bayesian as tasks
    from app.bayesian.worker_boot_probe import (
        bayesian_worker_boot_topology_probe_has_passed,
    )
    from celery import signals

    if not bayesian_worker_boot_topology_probe_has_passed():
        signals.worker_init.send(sender="b25-p13-c9-supersession-proof")

    return tasks.build_feature_authority.run(
        tenant_id=str(tenant_id),
        model_type=ACTIVE.model_type,
        model_version=ACTIVE.model_version,
        source_window_start=WINDOW_START.isoformat(),
        source_window_end=WINDOW_END.isoformat(),
        source_snapshot_hash=source_hash,
    )


def _request_state(tenant_id, source_hash: str) -> dict:
    engine = _engine()
    try:
        with engine.connect() as conn:
            _bind(conn, tenant_id)
            row = conn.execute(
                text(
                    "SELECT status, retry_count, max_retries,"
                    " retry_after_at IS NOT NULL AS scheduled, terminal_reason"
                    " FROM public.b24_feature_authority_build_requests"
                    " WHERE tenant_id = :t AND source_snapshot_hash = :h"
                ),
                {"t": str(tenant_id), "h": source_hash},
            ).mappings().one()
            dirty = conn.execute(
                text(
                    "SELECT status, count(*) AS n FROM public.b24_dirty_events"
                    " WHERE tenant_id = :t AND source_snapshot_hash = :h"
                    " GROUP BY status"
                ),
                {"t": str(tenant_id), "h": source_hash},
            ).mappings().all()
    finally:
        engine.dispose()
    return {**dict(row), "dirty": {r["status"]: r["n"] for r in dirty}}


def test_c9_a_request_for_a_superseded_snapshot_terminates_rather_than_retrying() -> (
    None
):
    """S0 is requested, the source becomes S1, and S0 must stop being work.

    The request is driven through as many real build cycles as its own
    ``max_retries`` allows. Each early cycle must leave it retryable -- a hash
    that does not match yet is a legitimate reason to wait. The last one must
    make it terminal, with the retry schedule cleared and the dirty evidence
    that was waiting on it released, so nothing continues to reference a
    request that can never complete.
    """

    engine = _migration_engine()
    try:
        with engine.begin() as conn:
            tenant_id = _new_tenant(conn, "obsolete")
            for index in range(24):
                _seed_settlement(
                    conn,
                    tenant_id,
                    index=index,
                    occurred_at=WINDOW_START
                    + timedelta(days=index % 20, hours=1 + index % 5),
                )
    finally:
        engine.dispose()

    s0 = _observed_hash(tenant_id)

    max_retries = 3
    engine = _migration_engine()
    try:
        with engine.begin() as conn:
            _bind(conn, tenant_id)
            _open_request(conn, tenant_id, s0, max_retries=max_retries)
            # The source moves. S0 now describes bytes that no longer exist.
            _seed_settlement(
                conn,
                tenant_id,
                index=900,
                occurred_at=WINDOW_START + timedelta(days=2, hours=7),
            )
    finally:
        engine.dispose()

    s1 = _observed_hash(tenant_id)
    assert s1 != s0, "the source did not actually move; the test proves nothing"

    # Early cycles: still retryable, because "not yet" is a real answer.
    for cycle in range(max_retries - 1):
        _build(tenant_id, s0)
        state = _request_state(tenant_id, s0)
        assert state["status"] == "authority_waiting", (cycle, state)
        assert state["scheduled"] is True, (cycle, state)
        assert state["retry_count"] == cycle + 1, (cycle, state)

    # The horizon is reached and the request stops being runnable.
    _build(tenant_id, s0)
    state = _request_state(tenant_id, s0)
    assert state["status"] == "authority_superseded", state
    assert state["scheduled"] is False, (
        "a terminated request is still carrying a retry schedule"
    )
    assert state["terminal_reason"] == "source_snapshot_superseded", state
    assert state["dirty"] == {"authority_retry_superseded": 1}, state

    # And it stays terminal: further cycles neither revive it nor re-arm it.
    for _ in range(3):
        _build(tenant_id, s0)
        again = _request_state(tenant_id, s0)
        assert again["status"] == "authority_superseded", again
        assert again["scheduled"] is False, again
        assert again["retry_count"] == state["retry_count"], (
            "a terminated request is still accumulating retries"
        )


def test_c9_a_request_for_the_current_snapshot_still_completes() -> None:
    """Supersession must not swallow work that is merely new.

    The bounded-retry path is only correct if a request naming the snapshot
    that actually exists still succeeds on its first cycle. Otherwise the
    remediation would have traded infinite retry for silent starvation.
    """

    engine = _migration_engine()
    try:
        with engine.begin() as conn:
            tenant_id = _new_tenant(conn, "current")
            for index in range(24):
                _seed_settlement(
                    conn,
                    tenant_id,
                    index=index,
                    occurred_at=WINDOW_START
                    + timedelta(days=index % 20, hours=2 + index % 4),
                )
    finally:
        engine.dispose()

    current = _observed_hash(tenant_id)
    engine = _migration_engine()
    try:
        with engine.begin() as conn:
            _bind(conn, tenant_id)
            _open_request(conn, tenant_id, current, max_retries=3)
    finally:
        engine.dispose()

    result = _build(tenant_id, current)
    assert result["status"] == "authority_completed", result

    state = _request_state(tenant_id, current)
    assert state["status"] == "authority_completed", state
    assert state["retry_count"] == 0, (
        "a request that succeeded immediately was charged a retry"
    )

    app_engine = _engine()
    try:
        with app_engine.connect() as conn:
            _bind(conn, tenant_id)
            authority = conn.execute(
                text(
                    "SELECT freshness_status, source_snapshot_hash FROM"
                    " public.b24_source_window_feature_authority"
                    " WHERE tenant_id = :t"
                ),
                {"t": str(tenant_id)},
            ).mappings().one()
    finally:
        app_engine.dispose()
    assert authority["freshness_status"] == "fresh", dict(authority)
    assert authority["source_snapshot_hash"] == current, dict(authority)
