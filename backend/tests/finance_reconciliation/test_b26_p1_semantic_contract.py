from __future__ import annotations

from decimal import Decimal

from app.finance_reconciliation.semantic_contract import (
    B26_DISCREPANCY_TAXONOMY_V1,
    B26_P1_CONTRACT_VERSION,
    B26_P1_SUPERSEDES_VERSION,
    B26_REQUIRED_DISCREPANCY_REASONS,
    B26_SUCCESSOR_STATUS_NONE,
    load_b26_p1_semantic_contract,
    semantic_contract_identity,
)
from app.revenue_verification.verification_coverage import (
    VerificationCoverageAggregate,
    compute_verification_coverage,
)


def test_b26_p1_contract_is_content_addressed_and_authority_only() -> None:
    contract = load_b26_p1_semantic_contract()
    identity = semantic_contract_identity()

    assert identity.contract_version == B26_P1_CONTRACT_VERSION
    assert len(identity.source_sha256) == 64
    assert len(identity.semantic_sha256) == 64
    assert contract["authority_kind"] == "semantic_constitution_not_financial_result"
    assert contract["projection_doctrine"]["trust_envelope"]["fields_created_in_P1"] is False


def test_b26_p1_golden_vector_uses_inherited_b23_metric() -> None:
    from datetime import datetime, timezone
    from uuid import UUID

    aggregate = VerificationCoverageAggregate(
        tenant_id=UUID("11111111-1111-1111-1111-111111111111"),
        currency_code="USD",
        window_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        window_end=datetime(2026, 2, 1, tzinfo=timezone.utc),
        matched_webhook_revenue_minor=76000,
        connected_platform_revenue_minor=80000,
    )

    result = compute_verification_coverage(aggregate)

    assert result.coverage_percent == Decimal("95.00")
    assert result.denominator_connected_platform_revenue_minor == 80000


def test_b26_p1_provisional_coverage_is_not_confirmation() -> None:
    contract = load_b26_p1_semantic_contract()
    provisional = contract["truth_status"]["matched_provisional"]

    assert provisional["participates_in_coverage_numerator"] is True
    assert provisional["finance_truth_status"] == "provisional"
    assert provisional["may_be_relabelled_confirmed"] is False


def test_b26_p1_discrepancy_taxonomy_is_machine_governed() -> None:
    contract = load_b26_p1_semantic_contract()
    discrepancy = contract["finance_discrepancy_reasons"]

    assert discrepancy["taxonomy_version"] == B26_DISCREPANCY_TAXONOMY_V1
    assert set(discrepancy["required_reasons"]) == set(B26_REQUIRED_DISCREPANCY_REASONS)
    assert len(discrepancy["required_reasons"]) == 8
    # Governed additive slot is empty at P1 closure; baseline alone is law.
    assert discrepancy["additional_governed_reasons"] == []
    # Collapsed category must stay empty so no consumer mistakes it for authority.
    assert contract["required_reconciliation_reasons"] == []
    # Separated ontologies preserve the superseded nine meanings without collapse.
    assert set(contract["truth_state_vocabulary"]) == {
        "matched_confirmed",
        "matched_provisional",
        "adjusted_confirmed",
    }
    assert set(contract["scope_dispositions"]) == {
        "supported_unresolved",
        "unsupported_provider_excluded",
        "unsupported_currency_excluded",
        "outside_governed_window_excluded",
        "source_identity_unresolved",
        "authority_unavailable",
    }


def test_b26_p1_tenant_and_seam_are_sensed() -> None:
    contract = load_b26_p1_semantic_contract()
    tenant = contract["tenant_identifier_policy"]

    assert tenant["durable_state"] == "tenant_scoped"
    assert tenant["external_raw_tenant_id"] == "forbidden"
    assert set(contract["future_insertion_seam"]) == {
        "B2.3_deterministic_verdict_and_coverage_authority",
        "future_B2.6_deterministic_reconciliation_projection_boundary",
        "future_finance_projection",
        "future_B2.6_TrustEnvelope_projection",
    }


def test_b26_p1_authority_classes_distinguish_permanent_from_closure() -> None:
    contract = load_b26_p1_semantic_contract()
    classes = contract["authority_classes"]

    assert classes["finance_discrepancy_reasons"] == "PERMANENT_MACHINE_ENFORCED"
    assert classes["tenant_identifier_policy"] == "PERMANENT_MACHINE_ENFORCED"
    assert classes["future_insertion_seam"] == "PERMANENT_MACHINE_ENFORCED"
    assert classes["migration_authority.expected_single_head"] == "PHASE_LOCAL_CLOSURE_FACT"
    assert classes["closure_snapshot"] == "PHASE_LOCAL_CLOSURE_FACT"
    assert classes["coverage_authority.denominator.definition"] == "DOCUMENTATION_ONLY"
    assert classes["successor_product_authorization"] == "PERMANENT_MACHINE_ENFORCED"
    assert classes["supersession"] == "DOCUMENTATION_ONLY"
    snapshot = contract["closure_snapshot"]
    assert snapshot["p1_closure_migration_head"] == "202609072001"


def test_b26_p1_version_identity_is_unambiguous() -> None:
    contract = load_b26_p1_semantic_contract()

    assert B26_P1_CONTRACT_VERSION == "b2.6-p1-semantic-authority-v5"
    assert contract["contract_version"] == B26_P1_CONTRACT_VERSION
    supersession = contract["supersession"]
    assert supersession["supersedes"] == B26_P1_SUPERSEDES_VERSION
    assert supersession["supersedes"] != B26_P1_CONTRACT_VERSION
    assert isinstance(supersession["reason"], str) and supersession["reason"]
    assert contract["closure_snapshot"]["p1_closure_contract_version"] == (
        B26_P1_CONTRACT_VERSION
    )


def test_b26_p1_successor_product_gate_defaults_to_closure() -> None:
    contract = load_b26_p1_semantic_contract()
    successor = contract["successor_product_authorization"]

    assert successor["status"] == B26_SUCCESSOR_STATUS_NONE
    assert successor["authorized_machinery"] == []


def _b26_p1_test_aggregate_and_result():
    from datetime import datetime, timezone
    from uuid import UUID

    from app.revenue_verification.verification_coverage import (
        VerificationCoverageAggregate,
        compute_verification_coverage,
    )

    aggregate = VerificationCoverageAggregate(
        tenant_id=UUID("11111111-1111-1111-1111-111111111111"),
        currency_code="USD",
        window_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        window_end=datetime(2026, 2, 1, tzinfo=timezone.utc),
        matched_webhook_revenue_minor=76000,
        connected_platform_revenue_minor=80000,
    )
    return aggregate, compute_verification_coverage(aggregate)


def test_b26_p1_canonical_admission_seam_is_declared() -> None:
    contract = load_b26_p1_semantic_contract()
    seam = contract["coverage_authority"]["canonical_admission_seam"]

    assert seam["module"] == "app.finance_reconciliation.coverage_authority"
    assert seam["law"] == "only_sovereign_rederivation_may_be_canonical"
    assert (
        seam["provenance_model"]
        == "scope_only_sovereign_rederivation_no_transferable_token"
    )
    assert (
        seam["admitter_behavior"]
        == "always_refuses_caller_observation_fail_closed"
    )
    assert (
        seam["resolver"]
        == "app.finance_reconciliation.coverage_authority.resolve_canonical_coverage"
    )
    # Corrective V executable authority: tenant unity, owned capability,
    # framework-owned final fields, re-derive-on-read at every boundary.
    assert (
        seam["tenant_authority_mode"]
        == "transaction_bound_db_tenant_equals_scope_tenant"
    )
    assert (
        seam["database_capability_mode"]
        == "framework_owned_governed_session_factory_only"
    )
    assert (
        seam["sink_framework"]
        == "app.finance_reconciliation.canonical_sink.execute_governed_sink"
    )
    assert (
        seam["final_field_owner"]
        == "canonical_sink_framework_post_callback_materialization"
    )
    assert (
        seam["provenance_law"]
        == "re_derive_on_read_at_every_canonical_boundary"
    )
    assert contract["authority_classes"]["coverage_authority.canonical_admission_seam"] == (
        "PERMANENT_MACHINE_ENFORCED"
    )


def test_b26_p1_unregistered_coverage_origin_is_refused() -> None:
    import pytest

    from app.finance_reconciliation.coverage_authority import (
        CanonicalCoverageAuthorityError,
        CanonicalVerificationCoverage,
        admit_canonical_verification_coverage,
    )

    aggregate, result = _b26_p1_test_aggregate_and_result()

    # Numerically correct but unregistered: plain numbers, ratios, dicts.
    for candidate in (
        9500,
        "95.00",
        {"coverage_percent": "95.00"},
        (76000 * 10000) // 80000,
    ):
        with pytest.raises(CanonicalCoverageAuthorityError):
            admit_canonical_verification_coverage(candidate)

    # Corrective IV: there is no transferable token. Even a same-type
    # instance with sovereign field values and correct mathematics is a
    # caller observation and is always refused. Authority is obtained only
    # by resolving scope through the sovereign boundary.
    forged = CanonicalVerificationCoverage(
        aggregate=aggregate,
        result=result,
        producer="app.revenue_verification.verification_coverage."
        "fetch_verification_coverage_aggregate"
        "+app.revenue_verification.verification_coverage."
        "VERIFICATION_COVERAGE.compute",
        supported_platforms=("paypal", "shopify", "stripe", "woocommerce"),
    )
    assert not hasattr(forged, "_sealed")
    with pytest.raises(CanonicalCoverageAuthorityError):
        admit_canonical_verification_coverage(forged)


def test_b26_p1_canonical_scope_mismatch_is_refused() -> None:
    import pytest

    from datetime import datetime, timezone
    from uuid import UUID

    from app.finance_reconciliation.coverage_authority import (
        CanonicalCoverageAuthorityError,
        CanonicalVerificationCoverage,
        admit_canonical_verification_coverage,
        require_canonical_scope,
    )

    aggregate, result = _b26_p1_test_aggregate_and_result()
    platforms = ("paypal", "shopify", "stripe", "woocommerce")
    coherent = CanonicalVerificationCoverage(
        aggregate=aggregate,
        result=result,
        producer="app.revenue_verification.verification_coverage."
        "fetch_verification_coverage_aggregate"
        "+app.revenue_verification.verification_coverage."
        "VERIFICATION_COVERAGE.compute",
        supported_platforms=platforms,
    )

    # No caller observation is admissible, however coherent.
    with pytest.raises(CanonicalCoverageAuthorityError):
        admit_canonical_verification_coverage(coherent)

    # Scope coherence reports scope/math coherence only; it is necessary but
    # not sufficient for provenance. Coherent scope with correct mathematics
    # reports coherence here (provenance still requires sovereign resolve).
    assert (
        require_canonical_scope(
            coherent,
            tenant_id=UUID("11111111-1111-1111-1111-111111111111"),
            currency_code="USD",
            window_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
            window_end=datetime(2026, 2, 1, tzinfo=timezone.utc),
            supported_platforms=list(platforms),
        )
        is coherent
    )

    # Same digits, foreign tenant scope: refused.
    with pytest.raises(CanonicalCoverageAuthorityError):
        require_canonical_scope(
            coherent,
            tenant_id=UUID("22222222-2222-2222-2222-222222222222"),
            currency_code="USD",
            window_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
            window_end=datetime(2026, 2, 1, tzinfo=timezone.utc),
            supported_platforms=list(platforms),
        )

    # Diagnostic copies are explicitly non-authoritative and refused.
    from app.finance_reconciliation.coverage_authority import to_diagnostic_dict

    with pytest.raises(CanonicalCoverageAuthorityError):
        admit_canonical_verification_coverage(to_diagnostic_dict(coherent))


def test_b26_p1_legacy_quarantine_is_declared_and_enforced() -> None:
    import pytest

    from app.finance_reconciliation.legacy_quarantine import (
        LEGACY_NON_AUTHORITATIVE_MODULES,
        LEGACY_NON_AUTHORITATIVE_ROUTE_PATHS,
        LEGACY_QUARANTINE_STATUS,
        LegacyAuthorityError,
        is_canonical_b26_authority,
        mark_legacy_diagnostic,
        refuse_legacy_as_canonical,
    )

    contract = load_b26_p1_semantic_contract()
    quarantine = contract["legacy_authority_quarantine"]

    assert quarantine["status"] == LEGACY_QUARANTINE_STATUS == (
        "compatibility_only_non_authoritative"
    )
    assert set(quarantine["route_paths"]) == set(LEGACY_NON_AUTHORITATIVE_ROUTE_PATHS)
    assert set(quarantine["modules"]) == set(LEGACY_NON_AUTHORITATIVE_MODULES)
    assert quarantine["canonical_admission"] == "refused"

    with pytest.raises(LegacyAuthorityError):
        refuse_legacy_as_canonical({"revenue_verified": 1})
    assert is_canonical_b26_authority({"revenue_verified": 1}) is False
    diagnostic = mark_legacy_diagnostic({"revenue_verified": 1})
    assert diagnostic["authority"] == "non_authoritative_legacy_diagnostic"
    assert is_canonical_b26_authority(diagnostic) is False


def test_b26_p1_math_is_independently_derived_from_integer_legs() -> None:
    """MI battery (DB-less): independent oracle, never sovereign compute."""
    import pytest

    from app.finance_reconciliation.coverage_authority import (
        CanonicalCoverageAuthorityError,
        independent_coverage_percent,
    )

    # Hardcoded expectations: no production helper produces these answers.
    assert independent_coverage_percent(76000, 80000) == (Decimal("95.00"), False)
    assert independent_coverage_percent(0, 0) == (Decimal("0.00"), True)
    assert independent_coverage_percent(0, 80000) == (Decimal("0.00"), False)
    assert independent_coverage_percent(80000, 80000) == (Decimal("100.00"), False)
    # Rounding boundary (half-up): 1/6 = 16.666.. -> 16.67.
    assert independent_coverage_percent(1, 6) == (Decimal("16.67"), False)
    with pytest.raises(CanonicalCoverageAuthorityError):
        independent_coverage_percent(80001, 80000)
    with pytest.raises(CanonicalCoverageAuthorityError):
        independent_coverage_percent(-1, 80000)
    with pytest.raises(CanonicalCoverageAuthorityError):
        independent_coverage_percent(76000, -80000)


def test_b26_p1_wrong_mathematics_is_refused_at_scope_boundary() -> None:
    """MI-02/MI-07: caller percent/flag never trusted, always re-derived."""
    import pytest

    from datetime import datetime, timezone
    from uuid import UUID

    from app.finance_reconciliation.coverage_authority import (
        CanonicalCoverageAuthorityError,
        CanonicalVerificationCoverage,
        require_canonical_scope,
    )
    from app.revenue_verification.verification_coverage import (
        VerificationCoverageAggregate,
        VerificationCoverageResult,
    )

    aggregate = VerificationCoverageAggregate(
        tenant_id=UUID("11111111-1111-1111-1111-111111111111"),
        currency_code="USD",
        window_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        window_end=datetime(2026, 2, 1, tzinfo=timezone.utc),
        matched_webhook_revenue_minor=76000,
        connected_platform_revenue_minor=80000,
    )
    scope = dict(
        tenant_id=UUID("11111111-1111-1111-1111-111111111111"),
        currency_code="USD",
        window_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        window_end=datetime(2026, 2, 1, tzinfo=timezone.utc),
        supported_platforms=["paypal", "shopify", "stripe", "woocommerce"],
    )
    for bad_percent in (Decimal("76.00"), Decimal("94.99"), Decimal("95.01")):
        bad = CanonicalVerificationCoverage(
            aggregate=aggregate,
            result=VerificationCoverageResult(
                tenant_id=aggregate.tenant_id,
                currency_code="USD",
                window_start=aggregate.window_start,
                window_end=aggregate.window_end,
                numerator_matched_webhook_revenue_minor=76000,
                denominator_connected_platform_revenue_minor=80000,
                coverage_percent=bad_percent,
                zero_denominator=False,
            ),
            producer="app.revenue_verification.verification_coverage."
            "fetch_verification_coverage_aggregate"
            "+app.revenue_verification.verification_coverage."
            "VERIFICATION_COVERAGE.compute",
            supported_platforms=("paypal", "shopify", "stripe", "woocommerce"),
        )
        with pytest.raises(CanonicalCoverageAuthorityError):
            require_canonical_scope(bad, **scope)


def test_b26_p1_diagnostic_is_tenant_safe_and_non_reconstructible() -> None:
    """TE/SP battery (DB-less): hash only, rebuild refused."""
    import pytest

    from app.finance_reconciliation.coverage_authority import (
        CanonicalCoverageAuthorityError,
        admit_canonical_verification_coverage,
        to_diagnostic_dict,
    )
    from app.trust.refusal import tenant_hash

    aggregate, result = _b26_p1_test_aggregate_and_result()
    from app.finance_reconciliation.coverage_authority import (
        CanonicalVerificationCoverage,
    )

    coherent = CanonicalVerificationCoverage(
        aggregate=aggregate,
        result=result,
        producer="app.revenue_verification.verification_coverage."
        "fetch_verification_coverage_aggregate"
        "+app.revenue_verification.verification_coverage."
        "VERIFICATION_COVERAGE.compute",
        supported_platforms=("paypal", "shopify", "stripe", "woocommerce"),
    )
    rendered = to_diagnostic_dict(coherent)
    assert rendered["authority"] == "non_authoritative_diagnostic_copy"
    assert "tenant_id" not in rendered
    assert rendered["tenant_id_hash"] == tenant_hash(aggregate.tenant_id)
    # Serialized round trip cannot recreate authority.
    with pytest.raises(CanonicalCoverageAuthorityError):
        admit_canonical_verification_coverage(dict(rendered))
    import copy

    with pytest.raises(CanonicalCoverageAuthorityError):
        admit_canonical_verification_coverage(copy.deepcopy(coherent))


def test_b26_p1_canonical_sinks_are_positively_governed() -> None:
    import pytest

    from app.finance_reconciliation.coverage_authority import (
        CanonicalCoverageAuthorityError,
        is_governed_canonical_sink,
        require_governed_canonical_sink,
    )

    assert is_governed_canonical_sink(
        "future_B2.6_deterministic_reconciliation_projection_boundary"
    )
    assert is_governed_canonical_sink("future_finance_projection")
    assert is_governed_canonical_sink("future_B2.6_TrustEnvelope_projection")
    assert not is_governed_canonical_sink("neutral_analytics_helper")
    with pytest.raises(CanonicalCoverageAuthorityError):
        require_governed_canonical_sink("neutral_analytics_helper")


def test_b26_p1_canonical_sink_framework_is_declared() -> None:
    contract = load_b26_p1_semantic_contract()
    framework = contract["canonical_sink_framework"]

    assert (
        framework["module"] == "app.finance_reconciliation.canonical_sink"
    )
    assert (
        framework["executor"]
        == "app.finance_reconciliation.canonical_sink.execute_governed_sink"
    )
    assert (
        framework["final_output_type"]
        == "app.finance_reconciliation.canonical_sink.FinalCanonicalOutput"
    )
    assert set(framework["governed_sink_ids"]) == {
        "future_B2.6_deterministic_reconciliation_projection_boundary",
        "future_finance_projection",
        "future_B2.6_TrustEnvelope_projection",
    }
    assert framework["provenance_mode"] == "RE_DERIVE_ON_READ"
    assert set(framework["governed_principals"]) == {"app_user", "app_worker"}
    assert contract["authority_classes"]["canonical_sink_framework"] == (
        "PERMANENT_MACHINE_ENFORCED"
    )

    law = contract["successor_provenance_law"]
    assert law["status"] == "provenance_mode_required_no_persistence_in_P1"
    assert set(law["allowed_modes"]) == {
        "RE_DERIVE_ON_READ",
        "DURABLE_SOURCE_BINDING",
    }
    assert contract["authority_classes"]["successor_provenance_law"] == (
        "PERMANENT_MACHINE_ENFORCED"
    )


def test_b26_p1_canonical_sinks_are_executably_registered() -> None:
    from app.finance_reconciliation.canonical_sink import (
        SINK_REGISTRY,
        executor_signature_has_no_session_capability,
        require_registered_sink,
    )

    assert set(SINK_REGISTRY) == {
        "future_B2.6_deterministic_reconciliation_projection_boundary",
        "future_finance_projection",
        "future_B2.6_TrustEnvelope_projection",
    }
    for sink_id in SINK_REGISTRY:
        registration = require_registered_sink(sink_id)
        assert registration.contract_version == B26_P1_CONTRACT_VERSION
        assert registration.required_runtime_proof_ids
    # Session injection is structurally impossible: the executor takes no
    # session/engine/factory capability parameter at all.
    assert executor_signature_has_no_session_capability() is True


def test_b26_p1_migration_graph_is_alembic_native() -> None:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts" / "ci"))
    from validate_b26_p1_authority import (  # noqa: PLC0415
        _native_revision_graph,
    )

    from alembic.config import Config  # noqa: PLC0415
    from alembic.script import ScriptDirectory  # noqa: PLC0415

    repo_root = Path(__file__).resolve().parents[3]
    script = ScriptDirectory.from_config(Config(str(repo_root / "alembic.ini")))
    native_revisions = {revision.revision for revision in script.walk_revisions()}

    graph, heads = _native_revision_graph()

    # P1 observes exactly Alembic's configured universe: triple-quoted
    # legal syntax is present, excluded-directory files are absent.
    assert set(graph) == native_revisions
    assert "202512151410" in graph
    assert "202511171000" not in graph
    assert heads == set(script.get_heads()) == {"202609072001"}
