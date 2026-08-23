"""B2.5-P13 C9: the feature-authority producer, measured against real PostgreSQL.

The producer answers exactly one question -- how wide is this source snapshot --
and these proofs are about that question and no other. They check that the four
widths are the widths of the data, that a width beyond its governed cap is
reported as a floor rather than a count, that membership and window are the ones
the source contract already defines, and that an authority is never written for
a snapshot the producer did not itself observe.

What they deliberately do not check is whether any of those widths is *enough*.
That belongs to ``b24-eligibility-v1``, and a proof here that asserted a minimum
would be the first step toward a second opinion about data quality with nothing
versioning it.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

from app.bayesian.feature_cardinality import (
    BOUNDED_CARDINALITY_POLICY,
    DIMENSION_CAPS,
    compute_source_window_cardinality,
    produce_source_window_feature_authority,
)
from app.bayesian.model_identity import active_identity
from app.core.secrets import get_database_url
from app.db.dsn import to_sync_postgres_dsn


pytestmark = pytest.mark.skipif(
    os.getenv("SKELDIR_B25_P13_C9_DB_PROOF") != "1",
    reason="B2.5-P13 C9 cardinality physics proofs are opt-in locally",
)

ACTIVE = active_identity()
DAY = datetime(2026, 10, 5, tzinfo=timezone.utc)
WINDOW_START = DAY
WINDOW_END = DAY + timedelta(days=20)
INSIDE = DAY + timedelta(hours=6)
OUTSIDE = DAY - timedelta(days=3)


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
            "n": f"c9-{label}-{tenant_id.hex[:8]}",
            "h": uuid.uuid4().hex,
            "e": f"c9-{tenant_id.hex[:8]}@example.invalid",
        },
    )
    _bind(conn, tenant_id)
    return tenant_id


def _seed_row(
    conn,
    tenant_id,
    *,
    index: int,
    channel: str,
    campaign: str,
    provider: str,
    currency: str,
    occurred_at: datetime,
    verdict_status: str = "matched_confirmed",
    event_status: str = "processed",
    event_type: str = "conversion",
) -> None:
    """One complete settlement: event, verdict and revenue event.

    Every membership-bearing column is a parameter, because several of these
    proofs turn on what happens when a row is present in the window but is not
    a member of the snapshot.
    """

    event_id = uuid.uuid4()
    verdict_id = uuid.uuid4()
    amount = 30_000 + index
    conn.execute(
        text(
            "INSERT INTO public.channel_taxonomy (code, family, is_paid,"
            " display_name, state) VALUES (:c, 'b25_p13_c9', true, :d, 'active')"
            " ON CONFLICT (code) DO NOTHING"
        ),
        {"c": channel, "d": f"C9 {index}"},
    )
    conn.execute(
        text(
            "INSERT INTO public.attribution_events (id, tenant_id, occurred_at,"
            " correlation_id, session_id, revenue_cents, raw_payload,"
            " idempotency_key, event_type, channel, campaign_id,"
            " conversion_value_cents, currency, event_timestamp, processed_at,"
            " processing_status) VALUES (:e, :t, :at, :corr, :sess, :amt,"
            " CAST(:payload AS jsonb), :key, :etype, :ch, :camp, :amt, :cur,"
            " :at, :at, :estatus)"
        ),
        {
            "e": str(event_id),
            "t": str(tenant_id),
            "at": occurred_at,
            "corr": str(uuid.uuid4()),
            "sess": str(uuid.uuid4()),
            "amt": amount,
            "payload": json.dumps({"source": "b25_p13_c9"}),
            "key": f"c9:{tenant_id.hex[:8]}:{index}",
            "etype": event_type,
            "ch": channel,
            "camp": campaign,
            "cur": currency,
            "estatus": event_status,
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
            " :prov, :ref, :pev, :ref, :vstatus, 'high', :amt, :amt, :cur,"
            " :at, :at, :amt, :amt, :amt, 0, 0, 'exact')"
        ),
        {
            "v": str(verdict_id),
            "t": str(tenant_id),
            "e": str(event_id),
            "prov": provider,
            "ref": f"c9-order-{tenant_id.hex[:8]}-{index:04d}",
            "pev": f"c9-event-{tenant_id.hex[:8]}-{index:04d}",
            "vstatus": verdict_status,
            "amt": amount,
            "cur": currency,
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
            " is_gross_capture_correction) VALUES (:t, :v, :prov, :pev, :ref,"
            " :ref, 'payment_capture', :cur, :at, :amt, 1, false)"
        ),
        {
            "t": str(tenant_id),
            "v": str(verdict_id),
            "prov": provider,
            "pev": f"c9-capture-{tenant_id.hex[:8]}-{index:04d}",
            "ref": f"c9-order-{tenant_id.hex[:8]}-{index:04d}",
            "cur": currency,
            "at": occurred_at,
            "amt": amount,
        },
    )


def _measure(tenant_id) -> dict:
    """Run the producer's measurement, without persisting anything."""

    from app.bayesian.source_snapshot import compute_source_snapshot_hash
    from app.db.session import AsyncSessionLocal, get_session

    async def go() -> dict:
        async with AsyncSessionLocal() as snapshot_session:
            snapshot = await compute_source_snapshot_hash(
                snapshot_session,
                tenant_id=tenant_id,
                model_type=ACTIVE.model_type,
                model_version=ACTIVE.model_version,
                source_window_start=WINDOW_START,
                source_window_end=WINDOW_END,
            )
        async with get_session(tenant_id) as session:
            cardinality = await compute_source_window_cardinality(
                session,
                tenant_id=tenant_id,
                source_window_start=WINDOW_START,
                source_window_end=WINDOW_END,
                preflight=snapshot.preflight,
                source_snapshot_hash=snapshot.source_snapshot_hash,
            )
        return {
            "counts": cardinality.counts(),
            "policy": cardinality.cardinality_policy,
            "hash": snapshot.source_snapshot_hash,
            "overflowed": {
                item.dimension: item.overflowed
                for item in (
                    cardinality.channel,
                    cardinality.currency,
                    cardinality.provider,
                    cardinality.campaign_or_feature,
                )
            },
        }

    return asyncio.run(go())


# ---------------------------------------------------------------------------
# The four widths are the widths of the data.
# ---------------------------------------------------------------------------
def test_c9_cardinality_is_the_shape_of_the_snapshot() -> None:
    """Exact widths below every cap, across all four governed dimensions."""

    engine = _migration_engine()
    try:
        with engine.begin() as conn:
            tenant_id = _new_tenant(conn, "shape")
            # 12 settlements: 4 channels, 3 campaigns, 2 providers, 2 currencies.
            for index in range(12):
                _seed_row(
                    conn,
                    tenant_id,
                    index=index,
                    channel=f"c9_channel_{index % 4}",
                    campaign=f"c9-campaign-{index % 3}",
                    provider=f"c9prov{index % 2}",
                    currency="USD" if index % 2 == 0 else "EUR",
                    occurred_at=INSIDE + timedelta(minutes=index),
                )
    finally:
        engine.dispose()

    measured = _measure(tenant_id)
    assert measured["counts"] == {
        "channel_count": 4,
        "currency_count": 2,
        "provider_count": 2,
        "campaign_or_feature_count": 3,
    }, measured
    assert measured["policy"] == BOUNDED_CARDINALITY_POLICY
    assert not any(measured["overflowed"].values()), measured


def test_c9_provider_cardinality_unions_both_governed_relations() -> None:
    """A provider seen only in revenue events still counts.

    The contract names two relations for this dimension. Walking only one would
    under-report a provider that settles without a verdict transition inside the
    window, and the under-report would look exactly like a correct answer.
    """

    engine = _migration_engine()
    try:
        with engine.begin() as conn:
            tenant_id = _new_tenant(conn, "union")
            for index in range(4):
                _seed_row(
                    conn,
                    tenant_id,
                    index=index,
                    channel="c9_union_channel",
                    campaign="c9-union-campaign",
                    provider="shared_provider",
                    currency="USD",
                    occurred_at=INSIDE + timedelta(minutes=index),
                )
            # One revenue event whose provider appears nowhere else.
            conn.execute(
                text(
                    "INSERT INTO public.b23_revenue_events (tenant_id,"
                    " match_verdict_id, provider,"
                    " provider_native_event_reference,"
                    " provider_native_commerce_reference,"
                    " canonical_commerce_reference, event_type, currency_code,"
                    " event_occurred_at, captured_amount_minor, net_effect_sign,"
                    " is_gross_capture_correction) SELECT :t, v.id,"
                    " 'revenue_only_provider', :pev, :ref, :ref,"
                    " 'payment_capture', 'USD', :at, 4200, 1, false"
                    " FROM public.b23_match_verdicts v"
                    " WHERE v.tenant_id = :t LIMIT 1"
                ),
                {
                    "t": str(tenant_id),
                    "pev": f"c9-revonly-{tenant_id.hex[:8]}",
                    "ref": f"c9-revonly-order-{tenant_id.hex[:8]}",
                    "at": INSIDE + timedelta(hours=1),
                },
            )
    finally:
        engine.dispose()

    measured = _measure(tenant_id)
    assert measured["counts"]["provider_count"] == 2, measured


# ---------------------------------------------------------------------------
# Beyond the cap, the number stops being a count.
# ---------------------------------------------------------------------------
def test_c9_overflow_is_reported_as_cap_plus_one_not_as_a_count() -> None:
    """Twenty providers against a cap of sixteen must report seventeen.

    This is the difference between the adjudicated bounded policy and an
    ordinary ``COUNT(DISTINCT ...)``. Reporting twenty would mean the producer
    had walked every key to learn something the resource policy discards the
    moment it exceeds the cap. Reporting seventeen says exactly what the policy
    needs -- more than the cap -- and says nothing it does not.
    """

    cap = DIMENSION_CAPS["provider"]
    engine = _migration_engine()
    try:
        with engine.begin() as conn:
            tenant_id = _new_tenant(conn, "overflow")
            for index in range(cap + 4):
                _seed_row(
                    conn,
                    tenant_id,
                    index=index,
                    channel="c9_overflow_channel",
                    campaign="c9-overflow-campaign",
                    provider=f"c9prov{index:03d}",
                    currency="USD",
                    occurred_at=INSIDE + timedelta(minutes=index),
                )
    finally:
        engine.dispose()

    measured = _measure(tenant_id)
    assert measured["counts"]["provider_count"] == cap + 1, measured
    assert measured["overflowed"]["provider"] is True, measured
    # And the dimensions that did not overflow are still exact.
    assert measured["counts"]["channel_count"] == 1, measured
    assert measured["overflowed"]["channel"] is False, measured


def test_c9_currency_overflow_follows_the_same_reporting_rule() -> None:
    """A dimension read from the P2 authority is bounded the same way."""

    cap = DIMENSION_CAPS["currency"]
    codes = [
        "USD", "EUR", "GBP", "JPY", "CAD", "AUD", "CHF", "SEK",
        "NOK", "DKK", "NZD", "SGD",
    ]
    assert len(codes) > cap
    engine = _migration_engine()
    try:
        with engine.begin() as conn:
            tenant_id = _new_tenant(conn, "currency")
            for index, code in enumerate(codes):
                _seed_row(
                    conn,
                    tenant_id,
                    index=index,
                    channel="c9_currency_channel",
                    campaign="c9-currency-campaign",
                    provider="c9prov",
                    currency=code,
                    occurred_at=INSIDE + timedelta(minutes=index),
                )
    finally:
        engine.dispose()

    measured = _measure(tenant_id)
    assert measured["counts"]["currency_count"] == cap + 1, measured
    assert measured["overflowed"]["currency"] is True, measured


# ---------------------------------------------------------------------------
# Membership and window are the contract's, not the producer's.
# ---------------------------------------------------------------------------
def test_c9_non_member_rows_do_not_widen_the_snapshot() -> None:
    """Rows inside the window but outside the snapshot must not be measured.

    A provisional verdict and an unprocessed event are both real rows in the
    window. Neither is in the snapshot the fit will read, so neither may
    contribute a provider, a channel or a campaign to the width of it.
    """

    engine = _migration_engine()
    try:
        with engine.begin() as conn:
            tenant_id = _new_tenant(conn, "member")
            for index in range(3):
                _seed_row(
                    conn,
                    tenant_id,
                    index=index,
                    channel="c9_member_channel",
                    campaign="c9-member-campaign",
                    provider="member_provider",
                    currency="USD",
                    occurred_at=INSIDE + timedelta(minutes=index),
                )
            # Present, inside the window, and not a member on any dimension.
            _seed_row(
                conn,
                tenant_id,
                index=90,
                channel="c9_intruder_channel",
                campaign="c9-intruder-campaign",
                provider="intruder_provider",
                currency="USD",
                occurred_at=INSIDE + timedelta(hours=2),
                verdict_status="matched_provisional",
                event_status="pending",
                event_type="pageview",
            )
    finally:
        engine.dispose()

    measured = _measure(tenant_id)
    # The intruder's revenue event IS a member, so its provider counts; its
    # channel and campaign come from a non-member attribution event and must not.
    assert measured["counts"]["channel_count"] == 1, measured
    assert measured["counts"]["campaign_or_feature_count"] == 1, measured


def test_c9_rows_outside_the_window_do_not_widen_the_snapshot() -> None:
    """The window is half-open and belongs to the source contract."""

    engine = _migration_engine()
    try:
        with engine.begin() as conn:
            tenant_id = _new_tenant(conn, "window")
            for index in range(3):
                _seed_row(
                    conn,
                    tenant_id,
                    index=index,
                    channel="c9_inside_channel",
                    campaign="c9-inside-campaign",
                    provider="inside_provider",
                    currency="USD",
                    occurred_at=INSIDE + timedelta(minutes=index),
                )
            _seed_row(
                conn,
                tenant_id,
                index=91,
                channel="c9_before_channel",
                campaign="c9-before-campaign",
                provider="before_provider",
                currency="USD",
                occurred_at=OUTSIDE,
            )
            _seed_row(
                conn,
                tenant_id,
                index=92,
                channel="c9_boundary_channel",
                campaign="c9-boundary-campaign",
                provider="boundary_provider",
                currency="USD",
                occurred_at=WINDOW_END,
            )
    finally:
        engine.dispose()

    measured = _measure(tenant_id)
    assert measured["counts"] == {
        "channel_count": 1,
        "currency_count": 1,
        "provider_count": 1,
        "campaign_or_feature_count": 1,
    }, measured


# ---------------------------------------------------------------------------
# Freshness is snapshot identity.
# ---------------------------------------------------------------------------
def test_c9_authority_is_never_written_for_an_unobserved_snapshot() -> None:
    """A request about bytes that have changed gets no authority at all.

    This is what replaces a TTL. The producer re-hashes the source and writes
    only when the hash it observes is the hash the request named. Anything else
    would be asserting a width for data the producer never read.
    """

    engine = _migration_engine()
    try:
        with engine.begin() as conn:
            tenant_id = _new_tenant(conn, "fresh")
            for index in range(4):
                _seed_row(
                    conn,
                    tenant_id,
                    index=index,
                    channel=f"c9_fresh_channel_{index}",
                    campaign=f"c9-fresh-campaign-{index}",
                    provider="fresh_provider",
                    currency="USD",
                    occurred_at=INSIDE + timedelta(minutes=index),
                )
    finally:
        engine.dispose()

    observed = _measure(tenant_id)

    async def produce(expected_hash: str):
        return await produce_source_window_feature_authority(
            tenant_id=tenant_id,
            model_type=ACTIVE.model_type,
            model_version=ACTIVE.model_version,
            source_window_start=WINDOW_START,
            source_window_end=WINDOW_END,
            expected_source_snapshot_hash=expected_hash,
        )

    assert asyncio.run(produce("0" * 64)) is None
    app_engine = _engine()
    try:
        with app_engine.connect() as conn:
            _bind(conn, tenant_id)
            written = conn.execute(
                text(
                    "SELECT count(*) FROM"
                    " public.b24_source_window_feature_authority"
                    " WHERE tenant_id = :t"
                ),
                {"t": str(tenant_id)},
            ).scalar_one()
        assert written == 0, "an authority was written for an unobserved snapshot"

        authority = asyncio.run(produce(observed["hash"]))
        assert authority is not None
        assert authority.source_snapshot_hash == observed["hash"]
        assert authority.freshness_status.value == "fresh"
        assert authority.channel_count == observed["counts"]["channel_count"]
        assert authority.provider_count == observed["counts"]["provider_count"]
    finally:
        app_engine.dispose()


def test_c9_producing_twice_for_one_snapshot_is_idempotent() -> None:
    """Re-running the producer must not accumulate rival widths."""

    engine = _migration_engine()
    try:
        with engine.begin() as conn:
            tenant_id = _new_tenant(conn, "idem")
            for index in range(5):
                _seed_row(
                    conn,
                    tenant_id,
                    index=index,
                    channel=f"c9_idem_channel_{index}",
                    campaign="c9-idem-campaign",
                    provider="idem_provider",
                    currency="USD",
                    occurred_at=INSIDE + timedelta(minutes=index),
                )
    finally:
        engine.dispose()

    observed = _measure(tenant_id)

    async def produce():
        return await produce_source_window_feature_authority(
            tenant_id=tenant_id,
            model_type=ACTIVE.model_type,
            model_version=ACTIVE.model_version,
            source_window_start=WINDOW_START,
            source_window_end=WINDOW_END,
            expected_source_snapshot_hash=observed["hash"],
        )

    first = asyncio.run(produce())
    second = asyncio.run(produce())
    assert first is not None and second is not None
    assert first.channel_count == second.channel_count

    app_engine = _engine()
    try:
        with app_engine.connect() as conn:
            _bind(conn, tenant_id)
            rows = conn.execute(
                text(
                    "SELECT count(*) FROM"
                    " public.b24_source_window_feature_authority"
                    " WHERE tenant_id = :t AND source_snapshot_hash = :h"
                ),
                {"t": str(tenant_id), "h": observed["hash"]},
            ).scalar_one()
        assert rows == 1, rows
    finally:
        app_engine.dispose()
