"""C8 behavioural proofs that source causality reaches the signed boundary.

C7 proved a source change creates a durable obligation. Independent audit then
showed the obligation could never reach the thing it was supposed to protect:
the triggers emitted ``('mmm', 'b24-p3-orchestration-v1')`` while the Trust
confidence read model projects only ``'bayesian_attribution_confidence'`` and
joined dirty evidence on exact model *and* exact window equality. Every proof in
the tree stopped on one side of that join or the other, so a green tree
coexisted with a severed chain.

These tests assert across the join. Each one begins with a real mutation of a
canonical B2.4 source relation and ends at the freshness verdict the Trust read
model actually computes -- the same SQL, not a paraphrase of it.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.bayesian.model_identity import (
    MODEL_IDENTITY_REGISTRY,
    ModelIdentityError,
    active_identity,
    assert_producible,
    registered_model_types,
    trust_eligible_model_types,
)
from app.confidence_projection.read_model import SUPPORTED_CONFIDENCE_MODEL_TYPES
from app.core.secrets import get_database_url
from app.db.dsn import to_sync_postgres_dsn


pytestmark = pytest.mark.skipif(
    os.getenv("SKELDIR_B25_P13_C8_DB_PROOF") != "1",
    reason="B2.5-P13 C8 identity/window physics proofs are opt-in locally",
)

ACTIVE = active_identity()
DAY = datetime(2026, 7, 15, tzinfo=timezone.utc)
CHANGE_AT = DAY + timedelta(hours=10)

# The freshness verdict, lifted verbatim from
# confidence_projection/read_model.py::_EXACT_FIT_PROJECTION_SQL. If the read
# model's predicate changes without this changing, the C8 gate turns red -- the
# two are bound by validate_staleness_predicate_is_overlap_based.
_FRESHNESS_SQL = """
    SELECT
      EXISTS (
        SELECT 1 FROM public.b24_dirty_events dirty
        WHERE dirty.tenant_id = f.tenant_id
          AND dirty.model_type = f.model_type
          AND public.b24_source_windows_overlap(
                dirty.source_window_start, dirty.source_window_end,
                f.source_window_start, f.source_window_end)
          AND dirty.observed_at > COALESCE(f.source_read_started_at, f.created_at)
          AND dirty.source_snapshot_hash IS DISTINCT FROM f.source_snapshot_hash
      ) AS has_later_dirty_evidence
    FROM public.bayesian_model_fits f
    WHERE f.id = :fit AND f.tenant_id = :tenant
"""

_FENCED = (
    ("public.bayesian_model_fits", "trg_b24_dispatch_fence_fits"),
    ("public.bayesian_artifacts", "trg_b24_dispatch_fence_artifacts"),
)


def _engine(url: str | None = None):
    return create_engine(
        to_sync_postgres_dsn(url or get_database_url()),
        pool_pre_ping=True,
        future=True,
    )


def _migration_engine():
    return _engine(os.environ.get("MIGRATION_DATABASE_URL"))


def _bind(conn, tenant_id):
    conn.execute(
        text("SELECT set_config('app.current_tenant_id', :t, false)"),
        {"t": str(tenant_id)},
    )


def _new_tenant(conn, label: str) -> uuid.UUID:
    tenant_id = uuid.uuid4()
    conn.execute(
        text(
            "INSERT INTO public.tenants (id, name, api_key_hash, notification_email)"
            " VALUES (:id, :name, :hash, :email)"
        ),
        {
            "id": str(tenant_id),
            "name": f"c8-{label}-{tenant_id.hex[:8]}",
            "hash": uuid.uuid4().hex,
            "email": f"c8-{tenant_id.hex[:8]}@example.test",
        },
    )
    _bind(conn, tenant_id)
    return tenant_id


def _seed_conversion(conn, tenant_id, index: int) -> uuid.UUID:
    event_id = uuid.uuid4()
    channel = f"c8_{tenant_id.hex[:6]}_{index}"
    conn.execute(
        text(
            "INSERT INTO public.channel_taxonomy (code, family, is_paid,"
            " display_name, state) VALUES (:c, 'b25_p13_c8', true, :d, 'active')"
            " ON CONFLICT (code) DO NOTHING"
        ),
        {"c": channel, "d": f"C8 {index}"},
    )
    conn.execute(
        text(
            "INSERT INTO public.attribution_events (id, tenant_id, occurred_at,"
            " correlation_id, session_id, revenue_cents, raw_payload,"
            " idempotency_key, event_type, channel, campaign_id,"
            " conversion_value_cents, currency, event_timestamp, processed_at,"
            " processing_status) VALUES (:id, :t, :at, :corr, :sess, 1000,"
            " CAST('{}' AS jsonb), :key, 'conversion', :c, 'c8-campaign', 1000,"
            " 'USD', :at, :at, 'processed')"
        ),
        {
            "id": str(event_id),
            "t": str(tenant_id),
            "at": CHANGE_AT,
            "corr": str(uuid.uuid4()),
            "sess": str(uuid.uuid4()),
            "key": f"c8:{tenant_id.hex[:8]}:{index}",
            "c": channel,
        },
    )
    return event_id


def _seed_verdict(conn, tenant_id, event_id, status: str) -> uuid.UUID:
    verdict_id = uuid.uuid4()
    reference = f"c8-order-{verdict_id.hex[:10]}"
    conn.execute(
        text(
            "INSERT INTO public.b23_match_verdicts (id, tenant_id,"
            " attribution_event_id, provider, canonical_commerce_reference,"
            " provider_native_event_reference, provider_native_commerce_reference,"
            " status, match_quality, attributed_amount_minor,"
            " verified_amount_minor, currency_code, last_transition_at,"
            " provisional_expires_at, canonical_expected_gross_amount_minor,"
            " canonical_captured_gross_amount_minor,"
            " canonical_net_verified_amount_minor, discrepancy_amount_minor,"
            " discrepancy_ratio_bps, discrepancy_band) VALUES (:id, :t, :e,"
            " 'stripe', :ref, :ev, :ref, :s, 'high', 1000, 1000, 'USD', :at, :at,"
            " 1000, 1000, 1000, 0, 0, 'exact')"
        ),
        {
            "id": str(verdict_id),
            "t": str(tenant_id),
            "e": str(event_id),
            "ref": reference,
            "ev": f"c8-ev-{verdict_id.hex[:10]}",
            "s": status,
            "at": CHANGE_AT,
        },
    )
    return verdict_id


def _seed_fit(tenant_id, *, window_start, window_end, model_type=None,
              model_version=None, snapshot_hash="a" * 64) -> uuid.UUID:
    """A terminal fit whose source read completed BEFORE any later change.

    Seeded through the migration principal with the dispatch fence suspended,
    exactly as the P13 E2E suite does. The fence is not the guard under test;
    the freshness verdict is.

    Building the pre-state means writing source rows, and those writes fire the
    production invalidation triggers, so the tenant already carries dirty
    evidence describing its own construction. That evidence is discarded here.
    Not to make the assertion easier -- it makes it strictly harder. Ordering
    setup evidence against the fit's source read would otherwise rest on which
    transaction happened to start first, a margin measured in microseconds, and
    a pass earned that way proves nothing. With the construction evidence gone,
    the only row that can ever stale this fit is one produced by the change the
    test performs after it.
    """

    fit_id = uuid.uuid4()
    engine = _migration_engine()
    try:
        with engine.begin() as conn:
            _bind(conn, tenant_id)
            conn.execute(
                text("DELETE FROM public.b24_dirty_events WHERE tenant_id = :t"),
                {"t": str(tenant_id)},
            )
            for table, trigger in _FENCED:
                conn.execute(text(f"ALTER TABLE {table} DISABLE TRIGGER {trigger}"))
            conn.execute(
                text(
                    "INSERT INTO public.bayesian_model_fits (id, tenant_id,"
                    " model_type, model_version, source_window_start,"
                    " source_window_end, source_snapshot_hash, status,"
                    " data_completeness_status, created_at, completed_at,"
                    " source_read_started_at, source_read_completed_at) VALUES"
                    " (:id, :t, :mt, :mv, :ws, :we, :h, 'succeeded', 'complete',"
                    " now(), now(), now(), now())"
                ),
                {
                    "id": str(fit_id),
                    "t": str(tenant_id),
                    "mt": model_type or ACTIVE.model_type,
                    "mv": model_version or ACTIVE.model_version,
                    "ws": window_start,
                    "we": window_end,
                    "h": snapshot_hash,
                },
            )
            for table, trigger in _FENCED:
                conn.execute(text(f"ALTER TABLE {table} ENABLE TRIGGER {trigger}"))
    finally:
        engine.dispose()
    return fit_id


def _is_stale(conn, tenant_id, fit_id) -> bool:
    _bind(conn, tenant_id)
    return bool(
        conn.execute(
            text(_FRESHNESS_SQL), {"fit": str(fit_id), "tenant": str(tenant_id)}
        ).scalar_one()
    )


def _confirm_verdict(conn, tenant_id, verdict_id) -> int:
    """The exact production transition from revenue_verification."""

    _bind(conn, tenant_id)
    result = conn.execute(
        text(
            "UPDATE public.b23_match_verdicts SET status = 'matched_confirmed',"
            " confirmed_at = now(), last_transition_at = :at, updated_at = now()"
            " WHERE tenant_id = :t AND id = :id AND status = 'matched_provisional'"
        ),
        {"t": str(tenant_id), "id": str(verdict_id), "at": CHANGE_AT},
    )
    return int(result.rowcount or 0)


# ---------------------------------------------------------------------------
# C8-B / C8-C : identity conservation across the signed boundary
# ---------------------------------------------------------------------------
def test_c8_source_change_stales_a_trust_projectable_fit() -> None:
    """The defect in one assertion: a real change must reach a projectable fit.

    Before C8 the trigger emitted a family the read model refuses, so this
    verdict stayed False no matter what changed underneath.
    """

    engine = _engine()
    try:
        with engine.begin() as conn:
            tenant_id = _new_tenant(conn, "identity")
            event_id = _seed_conversion(conn, tenant_id, 1)
            verdict_id = _seed_verdict(conn, tenant_id, event_id, "matched_provisional")

        fit_id = _seed_fit(
            tenant_id, window_start=DAY, window_end=DAY + timedelta(days=1)
        )

        with engine.begin() as conn:
            assert not _is_stale(conn, tenant_id, fit_id), (
                "fit was already stale before the mutation under test"
            )
            assert _confirm_verdict(conn, tenant_id, verdict_id) == 1

        with engine.begin() as conn:
            emitted = conn.execute(
                text(
                    "SELECT DISTINCT model_type, model_version FROM"
                    " public.b24_dirty_events WHERE tenant_id = :t"
                    # C19 split verdict invalidation onto the financial event
                    # clock and renamed the reason with it; the property under
                    # test -- the emitted identity is one Trust projects -- is
                    # unchanged.
                    " AND dirty_reason ="
                    " 'b23_match_verdicts_financial_event_changed'"
                ),
                {"t": str(tenant_id)},
            ).all()
            assert emitted == [(ACTIVE.model_type, ACTIVE.model_version)], emitted
            # The identity the trigger emits is one Trust will project.
            assert ACTIVE.model_type in SUPPORTED_CONFIDENCE_MODEL_TYPES
            assert _is_stale(conn, tenant_id, fit_id), (
                "a committed source change left the affected Trust fit current"
            )
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# C8-D : window dependency is overlap, at every supported shape
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "label,window_start,window_end",
    [
        ("same_day", DAY, DAY + timedelta(days=1)),
        ("thirty_day", DAY - timedelta(days=14), DAY + timedelta(days=16)),
        ("non_midnight", DAY + timedelta(hours=6), DAY + timedelta(hours=18)),
        ("boundary_open", DAY + timedelta(hours=10), DAY + timedelta(days=2)),
    ],
)
def test_c8_source_change_stales_every_supported_window_shape(
    label, window_start, window_end
) -> None:
    """A change inside a fit's window stales it whatever that window's shape.

    Equality could only ever stale a fit whose window was exactly the trigger's
    day bucket, so two of three production dirty producers -- both of which
    forward arbitrary caller windows -- could not invalidate anything.
    """

    engine = _engine()
    try:
        with engine.begin() as conn:
            tenant_id = _new_tenant(conn, f"window-{label}")
            event_id = _seed_conversion(conn, tenant_id, 1)
            verdict_id = _seed_verdict(conn, tenant_id, event_id, "matched_provisional")

        fit_id = _seed_fit(tenant_id, window_start=window_start, window_end=window_end)

        with engine.begin() as conn:
            assert not _is_stale(conn, tenant_id, fit_id)
            assert _confirm_verdict(conn, tenant_id, verdict_id) == 1

        with engine.begin() as conn:
            assert _is_stale(conn, tenant_id, fit_id), (
                f"{label} fit remained current after a change inside its window"
            )
    finally:
        engine.dispose()


def test_c8_change_outside_the_window_does_not_stale() -> None:
    """Overlap must be precise. Over-invalidation is debt, not correctness."""

    engine = _engine()
    try:
        with engine.begin() as conn:
            tenant_id = _new_tenant(conn, "disjoint")
            event_id = _seed_conversion(conn, tenant_id, 1)
            verdict_id = _seed_verdict(conn, tenant_id, event_id, "matched_provisional")

        # A fit over a window that does not contain CHANGE_AT at all.
        fit_id = _seed_fit(
            tenant_id,
            window_start=DAY + timedelta(days=30),
            window_end=DAY + timedelta(days=31),
        )

        with engine.begin() as conn:
            assert _confirm_verdict(conn, tenant_id, verdict_id) == 1

        with engine.begin() as conn:
            assert not _is_stale(conn, tenant_id, fit_id), (
                "a disjoint source change staled an unaffected fit"
            )
    finally:
        engine.dispose()


def test_c8_window_overlap_relation_is_half_open() -> None:
    """The affected-fit relation matches the source query's [start, end) range."""

    engine = _engine()
    try:
        with engine.connect() as conn:
            def overlaps(a0, a1, b0, b1):
                return bool(
                    conn.execute(
                        text(
                            "SELECT public.b24_source_windows_overlap"
                            "(:a0, :a1, :b0, :b1)"
                        ),
                        {"a0": a0, "a1": a1, "b0": b0, "b1": b1},
                    ).scalar_one()
                )

            d0, d1, d2 = DAY, DAY + timedelta(days=1), DAY + timedelta(days=2)
            assert overlaps(d0, d1, d0, d1)          # identical
            assert overlaps(d0, d1, d0 - timedelta(days=5), d2)  # contained
            assert overlaps(d0, d2, d1, d2)          # partial
            assert not overlaps(d0, d1, d1, d2)      # abutting, half-open
            assert not overlaps(d1, d2, d0, d1)      # abutting, other side
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# C8-B : model identity is registered authority, not a default parameter
# ---------------------------------------------------------------------------
def test_c8_unregistered_model_identity_cannot_be_stored() -> None:
    """The database refuses a family the registry does not declare."""

    engine = _engine()
    try:
        with engine.begin() as conn:
            tenant_id = _new_tenant(conn, "registry")

        connection = engine.connect()
        transaction = connection.begin()
        try:
            _bind(connection, tenant_id)
            with pytest.raises((IntegrityError, DBAPIError)) as excinfo:
                connection.execute(
                    text(
                        "INSERT INTO public.b24_dirty_events (tenant_id,"
                        " model_type, model_version, source_window_start,"
                        " source_window_end, dirty_reason, source_family,"
                        " observed_at, status) VALUES (:t, 'invented_family',"
                        " 'v1', :ws, :we, 'c8_probe', 'b23_revenue_events',"
                        " now(), 'pending')"
                    ),
                    {
                        "t": str(tenant_id),
                        "ws": DAY,
                        "we": DAY + timedelta(days=1),
                    },
                )
            assert "registered_model_type" in str(excinfo.value)
        finally:
            transaction.rollback()
            connection.close()

        # Every registered family remains storable, including the retired one:
        # historical rows stay legal and are never rewritten.
        for model_type in registered_model_types():
            connection = engine.connect()
            transaction = connection.begin()
            try:
                _bind(connection, tenant_id)
                connection.execute(
                    text(
                        "INSERT INTO public.b24_dirty_events (tenant_id,"
                        " model_type, model_version, source_window_start,"
                        " source_window_end, dirty_reason, source_family,"
                        " observed_at, status) VALUES (:t, :mt, 'v1', :ws, :we,"
                        " 'c8_probe', 'b23_revenue_events', now(), 'pending')"
                    ),
                    {
                        "t": str(tenant_id),
                        "mt": model_type,
                        "ws": DAY,
                        "we": DAY + timedelta(days=1),
                    },
                )
            finally:
                transaction.rollback()
                connection.close()
    finally:
        engine.dispose()


def test_c8_retired_identity_cannot_be_newly_produced() -> None:
    """Readable is not producible. A retired family fails closed at production."""

    assert_producible(ACTIVE.model_type, ACTIVE.model_version)

    retired = [item for item in MODEL_IDENTITY_REGISTRY if not item.is_active]
    assert retired, "the registry must name the retired identity explicitly"
    for identity in retired:
        with pytest.raises(ModelIdentityError):
            assert_producible(identity.model_type, identity.model_version)
        assert identity.model_type not in trust_eligible_model_types()

    with pytest.raises(ModelIdentityError):
        assert_producible("never_registered", "v1")
    # A registered family with the wrong pipeline version is also refused.
    with pytest.raises(ModelIdentityError):
        assert_producible(ACTIVE.model_type, "some-other-version")
