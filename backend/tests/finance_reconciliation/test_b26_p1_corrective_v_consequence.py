"""B2.6-P1 Corrective-V consequence proof battery (cells V-1 through V-7).

Every cell proves a user-visible canonical consequence, never helper
representation: pristine GREEN, one consequence-bearing mutation RED,
exact restore GREEN. Hardcoded expectations never call production
computation to establish truth. Database cells seed minimal physical
B2.3 fixtures (single matched row plus unmatched filler) and assert
against hardcoded integer legs and percentages.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import text

from app.finance_reconciliation.class_sweep import (
    GOVERNED_SINKS,
    decoy_percent,
    plan,
    ratio_for,
)
from app.finance_reconciliation.canonical_sink import (
    AUTHORITATIVE_FIELD_NAMES,
    SINK_REGISTRY,
    FinalCanonicalOutput,
    FinalFieldSubstitutionError,
    UnregisteredSinkError,
    _project_external_fields,
    authorize_successor_persistence,
    deregister_successor_persistence,
    execute_governed_sink,
    executor_signature_has_no_session_capability,
    is_canonical_output,
    register_successor_persistence,
    reject_authoritative_adjunct,
    require_registered_sink,
    to_canonical_external,
)
from app.finance_reconciliation.coverage_authority import (
    CanonicalCoverageAuthorityError,
    independent_coverage_percent,
    resolve_canonical_coverage,
)
from app.finance_reconciliation.semantic_contract import B26_P1_CONTRACT_VERSION
from app.finance_reconciliation.tenant_authority import (
    GOVERNED_CANONICAL_PRINCIPALS,
    CanonicalPrincipalError,
    MissingTenantAuthorityError,
    TenantAuthorityMismatchError,
    assert_tenant_authority,
)
from app.trust.refusal import tenant_hash

WINDOW_START = datetime(2026, 1, 1, tzinfo=timezone.utc)
WINDOW_END = datetime(2026, 2, 1, tzinfo=timezone.utc)
OCCURRED = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)

HOLDOUT_SEEDS = (902611, 770317, 5550197)


@pytest.fixture(autouse=True)
async def _fresh_engines_per_test():
    """Dispose pooled connections after each test (Windows loop hygiene).

    Module engines are process-global while each async test runs on its
    own event loop; disposing after every test guarantees the next test
    never inherits a connection bound to a closed loop.
    """
    yield
    from app.db.session import b23_engine
    from app.db.session import engine as app_engine

    await b23_engine.dispose()
    await app_engine.dispose()


def _admin_dsn() -> str:
    dsn = os.environ.get("MIGRATION_DATABASE_URL", "").strip()
    if not dsn:
        raise RuntimeError(
            "Corrective-V consequence battery needs MIGRATION_DATABASE_URL"
            " for physical fixture seeding."
        )
    return dsn


def _seed_ratio_tenant(matched: int, connected: int, tag: str) -> UUID:
    """Seed one tenant with matched/(connected-matched) physical legs."""
    import psycopg2

    assert matched <= connected
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
                    f"b26v-{tag}",
                    uuid.uuid4().hex,
                    f"b26v-{tag}@example.invalid",
                ),
            )
            cur.execute(
                "INSERT INTO public.channel_taxonomy (code, family, is_paid,"
                " display_name, state) VALUES ('b26v_channel', 'b26v', true,"
                " 'B26V', 'active') ON CONFLICT (code) DO NOTHING"
            )
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(tenant_id),),
            )

            def leg(order: str, amount: int, verdict: bool) -> None:
                event_id = uuid.uuid4()
                cur.execute(
                    "INSERT INTO public.attribution_events (id, tenant_id,"
                    " occurred_at, correlation_id, session_id, revenue_cents,"
                    " raw_payload, idempotency_key, event_type, channel,"
                    " campaign_id, conversion_value_cents, currency,"
                    " event_timestamp, processed_at, processing_status)"
                    " VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s,"
                    " 'conversion', 'b26v_channel', 'b26v-campaign', %s,"
                    " 'USD', %s, %s, 'processed')",
                    (
                        str(event_id),
                        str(tenant_id),
                        OCCURRED,
                        str(uuid.uuid4()),
                        str(uuid.uuid4()),
                        amount,
                        json.dumps({"order_id": order}),
                        f"b26v:{tag}:{order}",
                        amount,
                        OCCURRED,
                        OCCURRED,
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
                    " VALUES (%s, %s, %s, 'stripe', %s, %s,"
                    " 'order_reference', %s, %s, 'USD', %s, %s,"
                    " 'authenticity_verified')",
                    (
                        str(identity_id),
                        str(tenant_id),
                        str(event_id),
                        f"b26v-ingress-{tag}-{order}",
                        f"b26v-order-{tag}-{order}",
                        f"b26v-order-{tag}-{order}",
                        amount,
                        OCCURRED,
                        f"b26v-ingress:{tag}:{order}",
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
                        " VALUES (%s, %s, %s, %s, 'stripe', %s, %s, %s,"
                        " 'matched_confirmed', 'high', %s, %s, 'USD', %s,"
                        " %s, %s, %s, 0, 0, 'exact')",
                        (
                            str(uuid.uuid4()),
                            str(tenant_id),
                            str(event_id),
                            str(identity_id),
                            f"b26v-order-{tag}-{order}",
                            f"b26v-event-{tag}-{order}",
                            f"b26v-order-{tag}-{order}",
                            amount,
                            amount,
                            OCCURRED,
                            amount,
                            amount,
                            amount,
                        ),
                    )

            leg("matched", matched, True)
            if connected - matched > 0:
                leg("filler", connected - matched, False)
    finally:
        conn.close()
    return tenant_id


def _seed_empty_tenant(tag: str) -> UUID:
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
                    f"b26v-{tag}",
                    uuid.uuid4().hex,
                    f"b26v-{tag}@example.invalid",
                ),
            )
    finally:
        conn.close()
    return tenant_id


def _scope(tenant_id: UUID) -> dict[str, Any]:
    return {
        "tenant_id": tenant_id,
        "window_start": WINDOW_START,
        "window_end": WINDOW_END,
        "supported_platforms": ["stripe"],
        "currency_code": "USD",
    }


# ---------------------------------------------------------------------------
# V-7 (pure part): independent mathematics under a pinned context.
# ---------------------------------------------------------------------------


def test_v7_math_oracle_pinned_and_independent() -> None:
    from decimal import getcontext

    assert independent_coverage_percent(76000, 80000) == (Decimal("95.00"), False)
    assert independent_coverage_percent(0, 0) == (Decimal("0.00"), True)
    assert independent_coverage_percent(1, 6) == (Decimal("16.67"), False)
    previous = getcontext().prec
    getcontext().prec = 2
    try:
        assert independent_coverage_percent(76000, 80000) == (
            Decimal("95.00"),
            False,
        )
        assert independent_coverage_percent(1, 6) == (Decimal("16.67"), False)
    finally:
        getcontext().prec = previous
    with pytest.raises(CanonicalCoverageAuthorityError):
        independent_coverage_percent(80001, 80000)


# ---------------------------------------------------------------------------
# V-4 (pure part): executable sink identity.
# ---------------------------------------------------------------------------


def test_v4_sink_registry_is_executable_not_declarative() -> None:
    assert set(SINK_REGISTRY) == set(GOVERNED_SINKS)
    for sink_id in GOVERNED_SINKS:
        registration = require_registered_sink(sink_id)
        assert registration.contract_version == B26_P1_CONTRACT_VERSION
        assert registration.required_runtime_proof_ids
        module_name, _, attribute = registration.implementation.rpartition(".")
        import importlib

        assert callable(getattr(importlib.import_module(module_name), attribute))
    with pytest.raises(UnregisteredSinkError):
        require_registered_sink("neutral_analytics_helper")
    assert executor_signature_has_no_session_capability() is True


# ---------------------------------------------------------------------------
# V-2/V-3 (pure part): final-field ownership guard.
# ---------------------------------------------------------------------------


def test_v2_final_field_guard_refuses_substitution() -> None:
    assert reject_authoritative_adjunct(None) == {}
    assert reject_authoritative_adjunct({"note": "lawful adjunct"}) == {
        "note": "lawful adjunct"
    }
    for key in sorted(AUTHORITATIVE_FIELD_NAMES):
        with pytest.raises(FinalFieldSubstitutionError):
            reject_authoritative_adjunct({key: "substitute"})
    with pytest.raises(FinalFieldSubstitutionError):
        reject_authoritative_adjunct({"tenant_label": "raw"})
    with pytest.raises(FinalFieldSubstitutionError):
        reject_authoritative_adjunct(["not-a-mapping"])  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# V-6: successor provenance constitution.
# ---------------------------------------------------------------------------


def test_v6_successor_provenance_law_is_machine_enforced() -> None:
    with pytest.raises(Exception):
        authorize_successor_persistence("no_such_successor_registration")
    with pytest.raises(Exception):
        register_successor_persistence(
            registration_id="v6_probe_invalid",
            provenance_mode="anything",
            required_runtime_proof_ids=("V-6",),
        )
    with pytest.raises(Exception):
        register_successor_persistence(
            registration_id="v6_probe_empty_proofs",
            provenance_mode="RE_DERIVE_ON_READ",
            required_runtime_proof_ids=(),
        )
    register_successor_persistence(
        registration_id="v6_probe_valid",
        provenance_mode="DURABLE_SOURCE_BINDING",
        required_runtime_proof_ids=("V-6",),
    )
    try:
        assert authorize_successor_persistence("v6_probe_valid") is True
    finally:
        deregister_successor_persistence("v6_probe_valid")
    with pytest.raises(Exception):
        authorize_successor_persistence("v6_probe_valid")


# ---------------------------------------------------------------------------
# V-7 (pure part): external projection carries hash only; direct builds are
# non-canonical.
# ---------------------------------------------------------------------------


def test_v7_external_projection_hash_only_and_direct_build_noncanonical() -> None:
    tenant_id = UUID("11111111-1111-1111-1111-111111111111")
    direct = FinalCanonicalOutput(
        authority="canonical_B2.6_financial_truth",
        sink_id="future_finance_projection",
        contract_version=B26_P1_CONTRACT_VERSION,
        tenant_id_hash=tenant_hash(tenant_id),
        currency_code="USD",
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        supported_platforms=("stripe",),
        matched_minor=76000,
        connected_minor=80000,
        coverage_percent=Decimal("95.00"),
        zero_denominator=False,
        provenance_mode="RE_DERIVE_ON_READ",
        sovereign_producer="probe",
        provenance_nonce="unissued",
        adjunct_json="{}",
    )
    assert is_canonical_output(direct) is False
    rendered = _project_external_fields(direct)
    assert "tenant_id" not in rendered
    assert rendered["tenant_id_hash"] == tenant_hash(tenant_id)
    with pytest.raises(Exception):
        to_canonical_external(direct)


# ---------------------------------------------------------------------------
# V-1: tenant authority unity (TA-01 through TA-10).
# ---------------------------------------------------------------------------


async def test_v1_lawful_scope_is_green_with_governed_zero_preserved() -> None:
    tenant_a = _seed_ratio_tenant(76000, 80000, "v1-lawful")
    from app.db.session import get_b23_session

    async with get_b23_session(tenant_a) as session:
        coverage = await resolve_canonical_coverage(session, **_scope(tenant_a))
    assert coverage.aggregate.matched_webhook_revenue_minor == 76000
    assert coverage.aggregate.connected_platform_revenue_minor == 80000
    assert coverage.result.coverage_percent == Decimal("95.00")

    tenant_e = _seed_empty_tenant("v1-empty")
    async with get_b23_session(tenant_e) as session:
        empty = await resolve_canonical_coverage(session, **_scope(tenant_e))
    assert empty.aggregate.matched_webhook_revenue_minor == 0
    assert empty.aggregate.connected_platform_revenue_minor == 0
    assert empty.result.coverage_percent == Decimal("0.00")
    assert empty.result.zero_denominator is True


async def test_v1_mismatch_missing_and_foreign_scope_are_red_not_zero() -> None:
    tenant_a = _seed_ratio_tenant(76000, 80000, "v1-mismatch-a")
    tenant_b = _seed_ratio_tenant(9000, 9000, "v1-mismatch-b")
    from app.db.session import B23AsyncSessionLocal, get_b23_session

    async with get_b23_session(tenant_a) as session:
        with pytest.raises(TenantAuthorityMismatchError):
            await resolve_canonical_coverage(session, **_scope(tenant_b))
    async with B23AsyncSessionLocal() as session:
        with pytest.raises(MissingTenantAuthorityError):
            await resolve_canonical_coverage(session, **_scope(tenant_a))
    async with get_b23_session(tenant_a) as session:
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :t, false)"),
            {"t": str(tenant_b)},
        )
        with pytest.raises(TenantAuthorityMismatchError):
            await resolve_canonical_coverage(session, **_scope(tenant_a))


async def test_v1_connection_reuse_carries_no_stale_authority() -> None:
    tenant_a = _seed_ratio_tenant(76000, 80000, "v1-reuse-a")
    tenant_b = _seed_ratio_tenant(9000, 9000, "v1-reuse-b")
    from app.db.session import get_b23_session

    async with get_b23_session(tenant_a) as session:
        first = await resolve_canonical_coverage(session, **_scope(tenant_a))
    async with get_b23_session(tenant_b) as session:
        second = await resolve_canonical_coverage(session, **_scope(tenant_b))
    assert (
        first.aggregate.matched_webhook_revenue_minor,
        first.result.coverage_percent,
    ) == (
        76000,
        Decimal("95.00"),
    )
    assert (
        second.aggregate.matched_webhook_revenue_minor,
        second.result.coverage_percent,
    ) == (9000, Decimal("100.00"))


async def test_v1_nongoverned_principal_is_red() -> None:
    tenant_a = _seed_ratio_tenant(76000, 80000, "v1-principal")
    assert GOVERNED_CANONICAL_PRINCIPALS == frozenset({"app_user", "app_worker"})
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(
        _admin_dsn().replace("postgresql://", "postgresql+asyncpg://")
    )
    try:
        maker = async_sessionmaker(bind=engine, expire_on_commit=False)
        async with maker() as session:
            await session.execute(
                text("SELECT set_config('app.current_tenant_id', :t, true)"),
                {"t": str(tenant_a)},
            )
            with pytest.raises(CanonicalPrincipalError):
                await resolve_canonical_coverage(session, **_scope(tenant_a))
    finally:
        await engine.dispose()


async def test_v1_stub_session_authority_is_observed_not_trusted() -> None:
    class StubResult:
        def mappings(self) -> Any:
            return self

        def one(self) -> dict[str, Any]:
            return {
                "principal": "app_user",
                "database_name": "skeldir",
                "tenant_guc": str(UUID("22222222-2222-2222-2222-222222222222")),
            }

    class StubSession:
        async def execute(self, *args: Any, **kwargs: Any) -> StubResult:
            return StubResult()

    with pytest.raises(TenantAuthorityMismatchError):
        await assert_tenant_authority(
            StubSession(),  # type: ignore[arg-type]
            UUID("11111111-1111-1111-1111-111111111111"),
        )

    class WorkerResult(StubResult):
        def one(self) -> dict[str, Any]:
            return {
                "principal": "app_worker",
                "database_name": "skeldir",
                "tenant_guc": "11111111-1111-1111-1111-111111111111",
            }

    class WorkerSession(StubSession):
        async def execute(self, *args: Any, **kwargs: Any) -> WorkerResult:
            return WorkerResult()

    authority = await assert_tenant_authority(
        WorkerSession(),  # type: ignore[arg-type]
        UUID("11111111-1111-1111-1111-111111111111"),
    )
    assert authority["principal"] == "app_worker"


# ---------------------------------------------------------------------------
# V-2: final output depends on the sovereign result (sentinel + binding).
# ---------------------------------------------------------------------------


async def test_v2_framework_output_is_sovereign_result() -> None:
    tenant_a = _seed_ratio_tenant(76000, 80000, "v2-sovereign")
    output = await execute_governed_sink(
        "future_finance_projection", **_scope(tenant_a)
    )
    assert output.matched_minor == 76000
    assert output.connected_minor == 80000
    assert output.coverage_percent == Decimal("95.00")
    assert output.zero_denominator is False
    assert is_canonical_output(output) is True
    external = to_canonical_external(output)
    assert "tenant_id" not in external
    assert external["tenant_id_hash"] == tenant_hash(tenant_a)


async def test_v2_nonce_reuse_across_content_is_noncanonical() -> None:
    tenant_a = _seed_ratio_tenant(76000, 80000, "v2-binding")
    output = await execute_governed_sink(
        "future_finance_projection", **_scope(tenant_a)
    )
    forged = FinalCanonicalOutput(
        authority=output.authority,
        sink_id=output.sink_id,
        contract_version=output.contract_version,
        tenant_id_hash=output.tenant_id_hash,
        currency_code=output.currency_code,
        window_start=output.window_start,
        window_end=output.window_end,
        supported_platforms=output.supported_platforms,
        matched_minor=50000,
        connected_minor=100000,
        coverage_percent=Decimal("50.00"),
        zero_denominator=False,
        provenance_mode=output.provenance_mode,
        sovereign_producer=output.sovereign_producer,
        provenance_nonce=output.provenance_nonce,
        adjunct_json=output.adjunct_json,
    )
    assert is_canonical_output(forged) is False


# ---------------------------------------------------------------------------
# V-3: resolver-decoy battery (RD-01 through RD-07 directions).
# ---------------------------------------------------------------------------


async def test_v3_lawful_sink_with_benign_adjunct_is_green() -> None:
    tenant_a = _seed_ratio_tenant(76000, 80000, "v3-lawful")
    output = await execute_governed_sink(
        "future_finance_projection",
        **_scope(tenant_a),
        adjunct_provider=lambda context: {"note": "lawful adjunct"},
    )
    assert output.coverage_percent == Decimal("95.00")
    assert is_canonical_output(output) is True


@pytest.mark.parametrize(
    "hostile",
    [
        {"coverage_percent": "11.11"},
        {"matched_minor": 50000, "connected_minor": 100000},
        {"coverage_percent": "95.00"},
        {"zero_denominator": True},
        {"tenant_id": "11111111-1111-1111-1111-111111111111"},
        {"sink_id": "future_finance_projection"},
    ],
)
async def test_v3_decoy_substitution_is_red(hostile: dict[str, Any]) -> None:
    tenant_a = _seed_ratio_tenant(
        76000, 80000, f"v3-decoy-{abs(hash(str(sorted(hostile)))) % 100000}"
    )
    with pytest.raises(FinalFieldSubstitutionError):
        await execute_governed_sink(
            "future_finance_projection",
            **_scope(tenant_a),
            adjunct_provider=lambda context: dict(hostile),
        )


@pytest.mark.parametrize(
    "origin", ["llm", "b24", "b213", "legacy", "caller", "network"]
)
async def test_v3_adjacent_domain_decoy_is_red(origin: str) -> None:
    tenant_a = _seed_ratio_tenant(76000, 80000, f"v3-{origin}")
    with pytest.raises(FinalFieldSubstitutionError):
        await execute_governed_sink(
            "future_finance_projection",
            **_scope(tenant_a),
            adjunct_provider=lambda context: {
                "coverage_percent": Decimal("37.13"),
                f"{origin}_note": "origin label cannot confer authority",
            },
        )


# ---------------------------------------------------------------------------
# V-4: unregistered emitter non-authority; analytics stays lawful.
# ---------------------------------------------------------------------------


async def test_v4_unregistered_emitter_is_noncanonical() -> None:
    tenant_a = _seed_ratio_tenant(76000, 80000, "v4-unregistered")
    with pytest.raises(UnregisteredSinkError):
        await execute_governed_sink("neutral_analytics_helper", **_scope(tenant_a))

    def neutral_analytics_ratio(matched: int, connected: int) -> str:
        percent, _ = independent_coverage_percent(matched, connected)
        return str(percent)

    assert neutral_analytics_ratio(37130, 100000) == "37.13"
    assert is_canonical_output({"coverage_percent": "95.00"}) is False
    assert is_canonical_output("95.00") is False


# ---------------------------------------------------------------------------
# V-5/V-7: caller/serialized state cannot determine canonical output.
# ---------------------------------------------------------------------------


async def test_v5_caller_serialized_state_is_ignored() -> None:
    tenant_a = _seed_ratio_tenant(76000, 80000, "v5-serialized")
    caller_claim = {
        "matched_minor": 50000,
        "connected_minor": 100000,
        "coverage_percent": "50.00",
        "tenant_id": str(tenant_a),
    }
    caller_json = json.dumps(caller_claim)
    output = await execute_governed_sink(
        "future_finance_projection", **_scope(tenant_a)
    )
    assert output.matched_minor == 76000
    assert output.coverage_percent == Decimal("95.00")
    assert output.coverage_percent != Decimal(
        json.loads(caller_json)["coverage_percent"]
    )
    with pytest.raises(FinalFieldSubstitutionError):
        await execute_governed_sink(
            "future_finance_projection",
            **_scope(tenant_a),
            adjunct_provider=lambda context: dict(json.loads(caller_json)),
        )


# ---------------------------------------------------------------------------
# V-1..V-5 holdout class sweep: three previously unused seeds.
# ---------------------------------------------------------------------------


async def _run_holdout(seed: int) -> dict[str, Any]:
    sweep = plan(seed)
    matched, connected, expected = ratio_for(sweep)
    tenant = _seed_ratio_tenant(matched, connected, sweep.tenant_tag)
    other = _seed_empty_tenant(f"{sweep.tenant_tag}-other")

    output = await execute_governed_sink(sweep.sink_id, **_scope(tenant))
    assert output.matched_minor == matched
    assert output.connected_minor == connected
    assert output.coverage_percent == Decimal(expected)
    assert is_canonical_output(output) is True

    hostile_value = decoy_percent(sweep)
    for origin in sweep.decoy_origins:
        with pytest.raises(FinalFieldSubstitutionError):
            await execute_governed_sink(
                sweep.sink_id,
                **_scope(tenant),
                adjunct_provider=lambda context, o=origin: {
                    "coverage_percent": hostile_value,
                    f"{o}_marker": "holdout",
                },
            )

    from app.db.session import get_b23_session

    async with get_b23_session(tenant) as session:
        with pytest.raises(TenantAuthorityMismatchError):
            await resolve_canonical_coverage(session, **_scope(other))
    with pytest.raises(UnregisteredSinkError):
        await execute_governed_sink("holdout_unregistered_sink", **_scope(tenant))

    registration_id = f"holdout_successor_{seed}"
    register_successor_persistence(
        registration_id=registration_id,
        provenance_mode="RE_DERIVE_ON_READ",
        required_runtime_proof_ids=("V-6",),
    )
    try:
        assert authorize_successor_persistence(registration_id) is True
    finally:
        deregister_successor_persistence(registration_id)
    return {"seed": seed, "ratio": expected, "sink": sweep.sink_id}


async def test_b26_p1_holdout_sweep_902611() -> None:
    assert (await _run_holdout(902611))["seed"] == 902611


async def test_b26_p1_holdout_sweep_770317() -> None:
    assert (await _run_holdout(770317))["seed"] == 770317


async def test_b26_p1_holdout_sweep_5550197() -> None:
    assert (await _run_holdout(5550197))["seed"] == 5550197
