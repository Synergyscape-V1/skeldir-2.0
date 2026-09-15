"""B2.6-P2 canonical scope, rail, and normalization consequence battery.

Governing law: exactly one reachable B2.6 normalization authority
(``app.finance_reconciliation.scope_authority``) deterministically maps
every reconciliation candidate to exactly one of SUPPORTED_AND_IN_SCOPE,
SUPPORTED_BUT_UNRESOLVED, EXPLICITLY_EXCLUDED, or INVALID_OR_REFUSED with
canonical tenant, provider, rail, currency, window, and scope-policy
version. No candidate vanishes; normalization never alters money (no
amount path exists); B2.3 coverage stays sovereign at 76000/80000 = 95.00
with unsupported evidence explicitly excluded yet visible.

Every expectation below is hard-coded evidence data, never derived from
the modules under proof.
"""

from __future__ import annotations

import inspect
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest

from app.finance_reconciliation.scope_authority import (
    B26_P2_SCOPE_POLICY_VERSION,
    DISPOSITION_EXPLICITLY_EXCLUDED,
    DISPOSITION_INVALID_OR_REFUSED,
    DISPOSITION_SUPPORTED_AND_IN_SCOPE,
    DISPOSITION_SUPPORTED_BUT_UNRESOLVED,
    GOVERNED_P2_DISPOSITIONS,
    CanonicalScopeClassification,
    ScopeAuthorityError,
    assert_aggregate_scope_supported,
    classify_candidate,
    load_b26_p2_scope_policy,
    normalize_currency,
    normalize_provider,
    normalize_provider_set,
    normalize_rail,
    scope_policy_identity,
    validate_window,
)

WINDOW_START = datetime(2026, 1, 1, tzinfo=timezone.utc)
WINDOW_END = datetime(2026, 2, 1, tzinfo=timezone.utc)
OCCURRED = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
OUTSIDE_BEFORE = datetime(2025, 12, 31, 23, 59, tzinfo=timezone.utc)
OUTSIDE_MARCH = datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
async def _fresh_engines_per_test():
    yield
    from app.db.session import b23_engine
    from app.db.session import engine as app_engine

    await b23_engine.dispose()
    await app_engine.dispose()


def _admin_dsn() -> str:
    dsn = os.environ.get("MIGRATION_DATABASE_URL", "").strip()
    if not dsn:
        pytest.skip("P2 DB cells need MIGRATION_DATABASE_URL")
    return dsn


def _auth_token(tenant_id: UUID) -> str:
    from app.security.auth import mint_internal_jwt  # noqa: PLC0415

    return mint_internal_jwt(
        tenant_id=tenant_id,
        user_id=uuid.uuid4(),
        expires_in_seconds=300,
    )


def _scope_kwargs() -> dict[str, Any]:
    return {
        "window_start": WINDOW_START,
        "window_end": WINDOW_END,
        "supported_platforms": ["stripe"],
        "currency_code": "USD",
    }


# ---------------------------------------------------------------------------
# P2 pure: disposition exhaustiveness (all four reachable, exactly one each).
# ---------------------------------------------------------------------------


def test_p2_all_four_dispositions_reachable_and_exclusive() -> None:
    tenant = uuid.uuid4()
    kwargs: dict[str, Any] = {
        "tenant_id": tenant,
        "window_start": WINDOW_START,
        "window_end": WINDOW_END,
        "scope_policy_version": B26_P2_SCOPE_POLICY_VERSION,
    }
    in_scope = classify_candidate(
        provider_raw="stripe",
        currency_raw="USD",
        event_time=OCCURRED,
        source_reference="ord-1",
        **kwargs,
    )
    assert in_scope.disposition == DISPOSITION_SUPPORTED_AND_IN_SCOPE
    unresolved = classify_candidate(
        provider_raw="stripe",
        currency_raw="USD",
        event_time=OCCURRED,
        source_reference=None,
        **kwargs,
    )
    assert unresolved.disposition == DISPOSITION_SUPPORTED_BUT_UNRESOLVED
    excluded = classify_candidate(
        provider_raw="square",
        currency_raw="USD",
        event_time=OCCURRED,
        source_reference="ord-9",
        **kwargs,
    )
    assert excluded.disposition == DISPOSITION_EXPLICITLY_EXCLUDED
    assert excluded.provider == "square"
    assert excluded.rail == "square"
    with pytest.raises(ScopeAuthorityError):
        classify_candidate(
            provider_raw="stripe",
            currency_raw="USD",
            event_time=OCCURRED,
            source_reference="ord-1",
            tenant_id="not-a-uuid",
            window_start=WINDOW_START,
            window_end=WINDOW_END,
            scope_policy_version=B26_P2_SCOPE_POLICY_VERSION,
        )
    assert GOVERNED_P2_DISPOSITIONS == frozenset(
        {
            DISPOSITION_SUPPORTED_AND_IN_SCOPE,
            DISPOSITION_SUPPORTED_BUT_UNRESOLVED,
            DISPOSITION_EXPLICITLY_EXCLUDED,
            DISPOSITION_INVALID_OR_REFUSED,
        }
    )


def test_p2_supported_scope_carries_canonical_identity() -> None:
    tenant = uuid.uuid4()
    verdict = classify_candidate(
        tenant_id=tenant,
        provider_raw=" Stripe ",
        currency_raw="usd",
        event_time=OCCURRED,
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        scope_policy_version=B26_P2_SCOPE_POLICY_VERSION,
        source_reference="ord-7",
    )
    assert verdict.tenant_id == tenant
    assert verdict.provider == "stripe"
    assert verdict.rail == "stripe"
    assert verdict.currency_code == "USD"
    assert verdict.window_start == WINDOW_START
    assert verdict.window_end == WINDOW_END
    assert verdict.scope_policy_version == B26_P2_SCOPE_POLICY_VERSION
    assert verdict.reason == "supported_in_scope"
    assert isinstance(verdict, CanonicalScopeClassification)


def test_p2_blank_source_reference_is_unresolved_not_in_scope() -> None:
    tenant = uuid.uuid4()
    for blank in (None, "", "   "):
        verdict = classify_candidate(
            tenant_id=tenant,
            provider_raw="stripe",
            currency_raw="USD",
            event_time=OCCURRED,
            window_start=WINDOW_START,
            window_end=WINDOW_END,
            scope_policy_version=B26_P2_SCOPE_POLICY_VERSION,
            source_reference=blank,
        )
        assert verdict.disposition == DISPOSITION_SUPPORTED_BUT_UNRESOLVED
        assert verdict.reason == "source_identity_unresolved"


# ---------------------------------------------------------------------------
# P2 pure: half-open window determinism (boundary proof).
# ---------------------------------------------------------------------------


def test_p2_window_half_open_boundaries() -> None:
    tenant = uuid.uuid4()
    base: dict[str, Any] = {
        "tenant_id": tenant,
        "provider_raw": "stripe",
        "currency_raw": "USD",
        "window_start": WINDOW_START,
        "window_end": WINDOW_END,
        "scope_policy_version": B26_P2_SCOPE_POLICY_VERSION,
        "source_reference": "ord-1",
    }
    assert (
        classify_candidate(event_time=WINDOW_START, **base).disposition
        == DISPOSITION_SUPPORTED_AND_IN_SCOPE
    )
    epsilon_before_end = WINDOW_END - timedelta(microseconds=1)
    assert (
        classify_candidate(event_time=epsilon_before_end, **base).disposition
        == DISPOSITION_SUPPORTED_AND_IN_SCOPE
    )
    assert (
        classify_candidate(event_time=WINDOW_END, **base).disposition
        == DISPOSITION_EXPLICITLY_EXCLUDED
    )
    assert (
        classify_candidate(event_time=WINDOW_END, **base).reason
        == "outside_governed_window_excluded"
    )
    assert (
        classify_candidate(event_time=OUTSIDE_BEFORE, **base).disposition
        == DISPOSITION_EXPLICITLY_EXCLUDED
    )
    with pytest.raises(ScopeAuthorityError):
        classify_candidate(
            tenant_id=tenant,
            provider_raw="stripe",
            currency_raw="USD",
            event_time=OCCURRED,
            window_start=WINDOW_END,
            window_end=WINDOW_START,
            scope_policy_version=B26_P2_SCOPE_POLICY_VERSION,
            source_reference="ord-1",
        )


def test_p2_naive_event_time_and_window_refused() -> None:
    tenant = uuid.uuid4()
    naive = datetime(2026, 1, 15, 12, 0)
    with pytest.raises(ScopeAuthorityError):
        classify_candidate(
            tenant_id=tenant,
            provider_raw="stripe",
            currency_raw="USD",
            event_time=naive,
            window_start=WINDOW_START,
            window_end=WINDOW_END,
            scope_policy_version=B26_P2_SCOPE_POLICY_VERSION,
            source_reference="ord-1",
        )
    with pytest.raises(ScopeAuthorityError):
        validate_window(naive, WINDOW_END)


# ---------------------------------------------------------------------------
# P2 pure: currency and rail non-silence plus legacy non-promotion.
# ---------------------------------------------------------------------------


def test_p2_wrong_currency_is_explicit_exclusion_not_silence() -> None:
    tenant = uuid.uuid4()
    verdict = classify_candidate(
        tenant_id=tenant,
        provider_raw="stripe",
        currency_raw="EUR",
        event_time=OCCURRED,
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        scope_policy_version=B26_P2_SCOPE_POLICY_VERSION,
        source_reference="ord-eur",
    )
    assert verdict.disposition == DISPOSITION_EXPLICITLY_EXCLUDED
    assert verdict.reason == "unsupported_currency_excluded"
    assert verdict.currency_code == "EUR"


def test_p2_unsupported_rail_is_explicit_exclusion() -> None:
    tenant = uuid.uuid4()
    verdict = classify_candidate(
        tenant_id=tenant,
        provider_raw="square",
        currency_raw="USD",
        event_time=OCCURRED,
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        scope_policy_version=B26_P2_SCOPE_POLICY_VERSION,
        source_reference="ord-sq",
    )
    assert verdict.disposition == DISPOSITION_EXPLICITLY_EXCLUDED
    assert verdict.reason == "unsupported_provider_excluded"


@pytest.mark.parametrize(
    "legacy",
    ["woo", "woo_commerce", "facebook", "meta", "google", "google_ads", "tiktok"],
)
def test_p2_legacy_names_never_promote_to_supported(legacy: str) -> None:
    tenant = uuid.uuid4()
    verdict = classify_candidate(
        tenant_id=tenant,
        provider_raw=legacy,
        currency_raw="USD",
        event_time=OCCURRED,
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        scope_policy_version=B26_P2_SCOPE_POLICY_VERSION,
        source_reference="ord-legacy",
    )
    assert verdict.disposition == DISPOSITION_EXPLICITLY_EXCLUDED


@pytest.mark.parametrize("bad", [None, "", "   ", 42, ["stripe"], {"p": "stripe"}])
def test_p2_malformed_provider_shape_is_invalid_not_excluded(bad: Any) -> None:
    tenant = uuid.uuid4()
    with pytest.raises(ScopeAuthorityError):
        classify_candidate(
            tenant_id=tenant,
            provider_raw=bad,
            currency_raw="USD",
            event_time=OCCURRED,
            window_start=WINDOW_START,
            window_end=WINDOW_END,
            scope_policy_version=B26_P2_SCOPE_POLICY_VERSION,
            source_reference="ord-1",
        )


def test_p2_exclusion_priority_is_provider_then_currency_then_window() -> None:
    tenant = uuid.uuid4()
    verdict = classify_candidate(
        tenant_id=tenant,
        provider_raw="square",
        currency_raw="EUR",
        event_time=OUTSIDE_MARCH,
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        scope_policy_version=B26_P2_SCOPE_POLICY_VERSION,
        source_reference="ord-multi",
    )
    assert verdict.reason == "unsupported_provider_excluded"


# ---------------------------------------------------------------------------
# P2 pure: tenant and policy-version fail-hard, replay stability.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_tenant", [None, "", "   ", "not-a-uuid", 42, ["x"], {"t": 1}]
)
def test_p2_malformed_tenant_is_invalid(bad_tenant: Any) -> None:
    with pytest.raises(ScopeAuthorityError):
        classify_candidate(
            tenant_id=bad_tenant,
            provider_raw="stripe",
            currency_raw="USD",
            event_time=OCCURRED,
            window_start=WINDOW_START,
            window_end=WINDOW_END,
            scope_policy_version=B26_P2_SCOPE_POLICY_VERSION,
            source_reference="ord-1",
        )


def test_p2_wrong_policy_version_refused() -> None:
    with pytest.raises(ScopeAuthorityError):
        classify_candidate(
            tenant_id=uuid.uuid4(),
            provider_raw="stripe",
            currency_raw="USD",
            event_time=OCCURRED,
            window_start=WINDOW_START,
            window_end=WINDOW_END,
            scope_policy_version="b2.6-p2-scope-policy-v0",
            source_reference="ord-1",
        )


def test_p2_replay_stable_across_invocation_case_and_timezone() -> None:
    tenant = uuid.uuid4()
    first = classify_candidate(
        tenant_id=tenant,
        provider_raw="stripe",
        currency_raw="USD",
        event_time=OCCURRED,
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        scope_policy_version=B26_P2_SCOPE_POLICY_VERSION,
        source_reference="ord-1",
    )
    second = classify_candidate(
        tenant_id=str(tenant),
        provider_raw=" STRIPE ",
        currency_raw=" usd ",
        event_time=OCCURRED,
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        scope_policy_version=B26_P2_SCOPE_POLICY_VERSION,
        source_reference="ord-1",
    )
    assert first == second
    plus_two = timezone(timedelta(hours=2))
    same_instant = datetime(2026, 1, 15, 14, 0, tzinfo=plus_two)
    third = classify_candidate(
        tenant_id=tenant,
        provider_raw="stripe",
        currency_raw="USD",
        event_time=same_instant,
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        scope_policy_version=B26_P2_SCOPE_POLICY_VERSION,
        source_reference="ord-1",
    )
    assert third == first


def test_p2_normalization_never_touches_money_by_construction() -> None:
    parameters = inspect.signature(classify_candidate).parameters
    for forbidden in ("amount", "money", "cents", "minor", "percent", "price"):
        assert forbidden not in parameters
        assert forbidden not in {p.lower() for p in parameters}
    fields = set(CanonicalScopeClassification.__dataclass_fields__)
    for forbidden in ("amount", "money", "cents", "minor", "percent"):
        assert not any(forbidden in name for name in fields)


def test_p2_single_b26_provider_set_normalization() -> None:
    from app.finance_reconciliation import coverage_authority as ca

    assert normalize_provider_set(None) == ("paypal", "shopify", "stripe", "woocommerce")
    assert normalize_provider_set([" STRIPE ", "stripe"]) == ("stripe",)
    assert ca._normalize_platforms(None) == normalize_provider_set(None)
    assert ca._normalize_platforms(["stripe"]) == ("stripe",)
    with pytest.raises(Exception):
        ca._normalize_platforms(["square"])
    with pytest.raises(Exception):
        normalize_provider_set([])


def test_p2_aggregate_scope_coherence_gate() -> None:
    tenant = uuid.uuid4()
    results = assert_aggregate_scope_supported(
        tenant_id=tenant,
        supported_platforms=["stripe", "shopify"],
        currency_code="USD",
        window_start=WINDOW_START,
        window_end=WINDOW_END,
    )
    assert tuple(v.provider for v in results) == ("shopify", "stripe")
    assert all(
        v.disposition == DISPOSITION_SUPPORTED_AND_IN_SCOPE for v in results
    )
    with pytest.raises(ScopeAuthorityError):
        assert_aggregate_scope_supported(
            tenant_id=tenant,
            supported_platforms=["stripe", "square"],
            currency_code="USD",
            window_start=WINDOW_START,
            window_end=WINDOW_END,
        )


def test_p2_scope_policy_identity_pinned() -> None:
    identity = scope_policy_identity()
    assert identity.phase == "B2.6-P2"
    assert identity.scope_policy_version == B26_P2_SCOPE_POLICY_VERSION
    assert len(identity.source_sha256) == 64
    assert len(identity.semantic_sha256) == 64
    document = load_b26_p2_scope_policy()
    assert document["scope_policy_version"] == B26_P2_SCOPE_POLICY_VERSION
    assert set(document["dispositions"]) == set(GOVERNED_P2_DISPOSITIONS)


def test_p2_normalize_helpers_match_classifier() -> None:
    assert normalize_provider(" Stripe ") == "stripe"
    assert normalize_rail("stripe") == "stripe"
    assert normalize_currency("usd") == "USD"
    with pytest.raises(ScopeAuthorityError):
        normalize_provider("square")
    with pytest.raises(ScopeAuthorityError):
        normalize_currency("EUR")


# ---------------------------------------------------------------------------
# P2 DB: natural B2.3 state conducts into P2 with conserved 95.00.
# ---------------------------------------------------------------------------


def _seed_p2_universe(tag: str) -> dict[str, Any]:
    """Seed golden 76000/80000 plus square/EUR/outside-window distractors."""
    import psycopg2

    tenant_id = uuid.uuid4()
    conn = psycopg2.connect(_admin_dsn())
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO public.tenants (id, name, api_key_hash,"
                " notification_email) VALUES (%s, %s, %s, %s)",
                (
                    str(tenant_id),
                    f"b26p2-{tag}",
                    uuid.uuid4().hex,
                    f"b26p2-{tag}@example.invalid",
                ),
            )
            cur.execute(
                "INSERT INTO public.channel_taxonomy (code, family, is_paid,"
                " display_name, state) VALUES ('b26p2_channel', 'b26p2', true,"
                " 'B26P2', 'active') ON CONFLICT (code) DO NOTHING"
            )
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(tenant_id),),
            )

            def leg(
                order: str,
                amount: int,
                verdict: bool,
                provider: str = "stripe",
                currency: str = "USD",
                occurred: datetime = OCCURRED,
            ) -> UUID:
                event_id = uuid.uuid4()
                cur.execute(
                    "INSERT INTO public.attribution_events (id, tenant_id,"
                    " occurred_at, correlation_id, session_id, revenue_cents,"
                    " raw_payload, idempotency_key, event_type, channel,"
                    " campaign_id, conversion_value_cents, currency,"
                    " event_timestamp, processed_at, processing_status)"
                    " VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s,"
                    " 'conversion', 'b26p2_channel', 'b26p2-campaign', %s,"
                    " %s, %s, %s, 'processed')",
                    (
                        str(event_id),
                        str(tenant_id),
                        occurred,
                        str(uuid.uuid4()),
                        str(uuid.uuid4()),
                        amount,
                        json.dumps({"order_id": order}),
                        f"b26p2:{tag}:{provider}:{currency}:{order}",
                        amount,
                        currency,
                        occurred,
                        occurred,
                    ),
                )
                identity_id = uuid.uuid4()
                cur.execute(
                    "INSERT INTO public.webhook_ingress_identities (id,"
                    " tenant_id, event_id, provider,"
                    " provider_native_event_reference,"
                    " provider_native_commerce_reference,"
                    " normalized_commerce_reference_kind,"
                    " normalized_commerce_reference_value,"
                    " verified_amount_minor, verified_amount_currency,"
                    " event_timestamp, idempotency_key,"
                    " verified_commerce_ingress_state)"
                    " VALUES (%s, %s, %s, %s, %s, %s,"
                    " 'order_reference', %s, %s, %s, %s, %s,"
                    " 'authenticity_verified')",
                    (
                        str(identity_id),
                        str(tenant_id),
                        str(event_id),
                        provider,
                        f"b26p2-ingress-{tag}-{order}",
                        f"b26p2-order-{tag}-{order}",
                        f"b26p2-order-{tag}-{order}",
                        amount,
                        currency,
                        occurred,
                        f"b26p2-ingress:{tag}:{provider}:{order}",
                    ),
                )
                if verdict:
                    cur.execute(
                        "INSERT INTO public.b23_match_verdicts (id, tenant_id,"
                        " attribution_event_id,"
                        " webhook_ingress_identity_id, provider,"
                        " canonical_commerce_reference,"
                        " provider_native_event_reference,"
                        " provider_native_commerce_reference, status,"
                        " match_quality, attributed_amount_minor,"
                        " verified_amount_minor, currency_code,"
                        " last_transition_at,"
                        " canonical_expected_gross_amount_minor,"
                        " canonical_captured_gross_amount_minor,"
                        " canonical_net_verified_amount_minor,"
                        " discrepancy_amount_minor, discrepancy_ratio_bps,"
                        " discrepancy_band)"
                        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s,"
                        " 'matched_confirmed', 'high', %s, %s, %s, %s,"
                        " %s, %s, %s, 0, 0, 'exact')",
                        (
                            str(uuid.uuid4()),
                            str(tenant_id),
                            str(event_id),
                            str(identity_id),
                            provider,
                            f"b26p2-order-{tag}-{order}",
                            f"b26p2-event-{tag}-{order}",
                            f"b26p2-order-{tag}-{order}",
                            amount,
                            amount,
                            currency,
                            occurred,
                            amount,
                            amount,
                            amount,
                        ),
                    )
                return identity_id

            leg("matched", 76000, True)
            leg("filler", 4000, False)
            leg("square-distractor", 20000, True, provider="square")
            leg("eur-distractor", 5000, False, currency="EUR")
            leg("march-distractor", 9000, False, occurred=OUTSIDE_MARCH)
    finally:
        conn.close()
    return {"tenant_id": tenant_id}


async def test_p2_db_natural_conduction_conserves_95_with_explicit_exclusions() -> None:
    from app.finance_reconciliation.canonical_sink import execute_governed_sink

    universe = _seed_p2_universe("conduct")
    tenant_id = universe["tenant_id"]
    output = await execute_governed_sink(
        "future_finance_projection",
        auth_token=_auth_token(tenant_id),
        **_scope_kwargs(),
    )
    assert output.matched_minor == 76000
    assert output.connected_minor == 80000
    assert output.coverage_percent == Decimal("95.00")
    assert output.zero_denominator is False

    import psycopg2

    conn = psycopg2.connect(_admin_dsn())
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(tenant_id),),
            )
            cur.execute(
                "SELECT provider, verified_amount_currency, event_timestamp"
                " FROM public.webhook_ingress_identities"
                " WHERE tenant_id = %s"
                " ORDER BY verified_amount_minor DESC",
                (str(tenant_id),),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    by_provider = {row[0]: row for row in rows}
    lawful = by_provider["stripe"]
    verdict = classify_candidate(
        tenant_id=tenant_id,
        provider_raw=lawful[0],
        currency_raw=lawful[1],
        event_time=lawful[2],
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        scope_policy_version=B26_P2_SCOPE_POLICY_VERSION,
        source_reference="b26p2-lawful",
    )
    assert verdict.disposition == DISPOSITION_SUPPORTED_AND_IN_SCOPE
    assert verdict.provider == "stripe"
    square = by_provider["square"]
    square_verdict = classify_candidate(
        tenant_id=tenant_id,
        provider_raw=square[0],
        currency_raw=square[1],
        event_time=square[2],
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        scope_policy_version=B26_P2_SCOPE_POLICY_VERSION,
        source_reference="b26p2-square",
    )
    assert square_verdict.disposition == DISPOSITION_EXPLICITLY_EXCLUDED
    assert square_verdict.reason == "unsupported_provider_excluded"


async def test_p2_db_currency_and_window_distractors_explicit() -> None:
    universe = _seed_p2_universe("distract")
    tenant_id = universe["tenant_id"]

    import psycopg2

    conn = psycopg2.connect(_admin_dsn())
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(tenant_id),),
            )
            cur.execute(
                "SELECT provider, verified_amount_currency, event_timestamp"
                " FROM public.webhook_ingress_identities"
                " WHERE tenant_id = %s AND verified_amount_currency = 'EUR'",
                (str(tenant_id),),
            )
            eur_row = cur.fetchone()
            cur.execute(
                "SELECT provider, verified_amount_currency, event_timestamp"
                " FROM public.webhook_ingress_identities"
                " WHERE tenant_id = %s AND event_timestamp >= %s",
                (str(tenant_id), datetime(2026, 3, 1, tzinfo=timezone.utc)),
            )
            march_row = cur.fetchone()
    finally:
        conn.close()
    assert eur_row is not None and march_row is not None
    eur_verdict = classify_candidate(
        tenant_id=tenant_id,
        provider_raw=eur_row[0],
        currency_raw=eur_row[1],
        event_time=eur_row[2],
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        scope_policy_version=B26_P2_SCOPE_POLICY_VERSION,
        source_reference="b26p2-eur",
    )
    assert eur_verdict.disposition == DISPOSITION_EXPLICITLY_EXCLUDED
    assert eur_verdict.reason == "unsupported_currency_excluded"
    march_verdict = classify_candidate(
        tenant_id=tenant_id,
        provider_raw=march_row[0],
        currency_raw=march_row[1],
        event_time=march_row[2],
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        scope_policy_version=B26_P2_SCOPE_POLICY_VERSION,
        source_reference="b26p2-march",
    )
    assert march_verdict.disposition == DISPOSITION_EXPLICITLY_EXCLUDED
    assert march_verdict.reason == "outside_governed_window_excluded"


async def test_p2_db_ghost_tenant_refuses_through_p2_wiring() -> None:
    from app.finance_reconciliation.canonical_sink import execute_governed_sink
    from app.finance_reconciliation.tenant_authority import UnknownTenantError

    ghost = uuid.uuid4()
    with pytest.raises(UnknownTenantError):
        await execute_governed_sink(
            "future_finance_projection",
            auth_token=_auth_token(ghost),
            **_scope_kwargs(),
        )
