from __future__ import annotations

from app.revenue_verification.semantic_authority import (
    ALLOWED_DELAYED_ARRIVAL_TOPOLOGY,
    B23_AMOUNT_BASIS,
    B23_CURRENCY_STANCE,
    B23DiscrepancyClass,
    B23_P0_PERFORMANCE_AUTHORITY,
    B23_PRECEDENCE_ORDER,
    B23Verdict,
    CanonicalizationStatus,
    PaymentAdjustmentSupport,
    assert_b23_authority_source,
    assert_b23_boundary_not_allocation,
    canonicalize_attribution_commerce_reference,
    canonicalize_verified_commerce_reference,
    classify_payment_adjustment_support,
    load_b23_p0_semantic_authority_contract,
    map_b23_discrepancy_for_downstream,
    map_b23_verdict_for_downstream,
    resolve_canonical_match_key,
    validate_delayed_arrival_strategy,
    validate_delayed_arrival_topology,
)


def test_b23_p0_contract_load_is_authoritative() -> None:
    contract = load_b23_p0_semantic_authority_contract()
    assert contract.contract_id == "b23.p0.semantic_authority_freeze.main"
    assert contract.branch == "main"
    assert contract.phase == "B2.3-P0"
    assert tuple(contract.shared_identity_canonicalization.precedence_order) == B23_PRECEDENCE_ORDER
    assert contract.financial_truth_semantics.amount_basis == B23_AMOUNT_BASIS
    assert contract.financial_truth_semantics.currency_stance == B23_CURRENCY_STANCE


def test_b23_p0_dual_sided_canonicalization_converges_decorated_variants() -> None:
    variants = ("#1004", "1004", "shopify_1004", "TX-1004", "tx_1004")
    verified = {
        canonicalize_verified_commerce_reference(
            provider="shopify",
            raw_reference=value,
        ).canonical_reference
        for value in variants
    }
    attribution = {
        canonicalize_attribution_commerce_reference(
            provider="shopify",
            raw_reference=value,
        ).canonical_reference
        for value in variants
    }
    assert verified == {"1004"}
    assert attribution == {"1004"}


def test_b23_p0_precedence_order_is_deterministic() -> None:
    result = resolve_canonical_match_key(
        provider="shopify",
        normalized_commerce_reference="#1004",
        provider_native_commerce_reference="TX-1004",
        strict_order_id="1004",
    )
    assert result.status is CanonicalizationStatus.CANONICALIZED
    assert result.canonical_reference == "1004"
    assert result.source_field == "normalized_commerce_reference"


def test_b23_p0_canonicalization_failure_state_is_explicit() -> None:
    result = canonicalize_verified_commerce_reference(provider="shopify", raw_reference="---")
    assert result.status is CanonicalizationStatus.CANONICALIZATION_FAILED
    assert result.canonical_reference is None
    assert "canonicalization_failed_explicit" in result.reason_code


def test_b23_p0_illegal_delayed_arrival_strategies_fail_closed() -> None:
    illegal = (
        "extend_attribution_session_window",
        "cross_session_identity_reconstruction",
        "persist_pii_for_matching",
        "persist_reversible_user_linked_hashes",
        "privacy_ambiguous_shadow_identity_graph",
    )
    for strategy in illegal:
        try:
            validate_delayed_arrival_strategy(strategy)
        except ValueError as exc:
            assert strategy in str(exc)
        else:
            raise AssertionError(f"expected fail-closed rejection for strategy {strategy}")


def test_b23_p0_only_allowed_delayed_arrival_topology_is_accepted() -> None:
    validate_delayed_arrival_topology(ALLOWED_DELAYED_ARRIVAL_TOPOLOGY)
    try:
        validate_delayed_arrival_topology("session_replay_table")
    except ValueError as exc:
        assert ALLOWED_DELAYED_ARRIVAL_TOPOLOGY in str(exc)
    else:
        raise AssertionError("expected topology validation to fail for unsupported topology")


def test_b23_p0_amount_currency_and_adjustment_stance_is_frozen() -> None:
    assert B23_AMOUNT_BASIS == "verified_captured_amount_minor_units"
    assert B23_CURRENCY_STANCE == "same_currency_only_cross_currency_unsupported"
    assert classify_payment_adjustment_support("refund") is PaymentAdjustmentSupport.UNSUPPORTED
    assert classify_payment_adjustment_support("partial_capture") is PaymentAdjustmentSupport.UNSUPPORTED
    assert classify_payment_adjustment_support("none") is PaymentAdjustmentSupport.SUPPORTED


def test_b23_p0_boundary_law_blocks_allocation_inside_b23() -> None:
    assert_b23_boundary_not_allocation(requests_allocation=False)
    try:
        assert_b23_boundary_not_allocation(requests_allocation=True)
    except ValueError as exc:
        assert "B2.1/B2.5 perform attribution allocation" in str(exc)
    else:
        raise AssertionError("expected boundary violation when requests_allocation=True")


def test_b23_p0_false_authority_sources_are_rejected() -> None:
    for source in (
        "revenue_ledger.state",
        "RevenueReconciliationService",
        "/api/reconciliation/status",
    ):
        try:
            assert_b23_authority_source(source)
        except ValueError as exc:
            assert source in str(exc)
        else:
            raise AssertionError(f"expected false-authority rejection for source={source}")


def test_b23_p0_downstream_mapping_is_typed_and_deterministic() -> None:
    assert map_b23_verdict_for_downstream(B23Verdict.MATCHED) == "b23.verdict.matched"
    assert map_b23_verdict_for_downstream(B23Verdict.CANONICALIZATION_FAILED) == (
        "b23.verdict.canonicalization_failed"
    )
    assert map_b23_discrepancy_for_downstream(B23DiscrepancyClass.EXACT) == (
        "b23.discrepancy.exact"
    )
    assert map_b23_discrepancy_for_downstream(B23DiscrepancyClass.IDENTITY_FAILURE) == (
        "b23.discrepancy.identity_failure"
    )


def test_b23_p0_performance_authority_is_explicit() -> None:
    assert B23_P0_PERFORMANCE_AUTHORITY.kernel_1000_orders_max_seconds == 5
    assert B23_P0_PERFORMANCE_AUTHORITY.report_1000_orders_max_seconds == 10
