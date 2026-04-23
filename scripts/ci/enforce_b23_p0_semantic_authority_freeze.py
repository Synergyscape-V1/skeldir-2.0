#!/usr/bin/env python3
"""B2.3-P0 semantic authority freeze enforcer."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
GOVERNANCE_CONTRACT = (
    "contracts-internal/governance/b23_p0_semantic_authority_freeze.main.json"
)
SEMANTIC_AUTHORITY_FILE = "backend/app/revenue_verification/semantic_authority.py"
EVENT_SERVICE_FILE = "backend/app/ingestion/event_service.py"
RUNTIME_PROOF_FILE = "backend/tests/test_b23_p0_semantic_authority.py"
ENFORCER_PROOF_FILE = "backend/tests/test_b23_p0_semantic_authority_freeze_enforcer.py"
CI_WORKFLOW_FILE = ".github/workflows/ci.yml"


def _resolve(repo_root: Path, raw: str) -> Path:
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate
    return (repo_root / candidate).resolve()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(_read_text(path))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON payload must be an object: {path}")
    return payload


def _git_ref_exists(repo_root: Path, ref: str) -> bool:
    proc = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", ref],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    return proc.returncode == 0


def _git_try_fetch_main(repo_root: Path) -> None:
    subprocess.run(
        ["git", "fetch", "--quiet", "origin", "main", "--depth=1"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )


def _validate_baseline_ancestry(repo_root: Path, violations: list[str]) -> None:
    refs_to_try = ("origin/main", "main")
    if not any(_git_ref_exists(repo_root, ref) for ref in refs_to_try):
        _git_try_fetch_main(repo_root)

    seen_ref = False
    for ref in refs_to_try:
        if not _git_ref_exists(repo_root, ref):
            continue
        seen_ref = True
        proc = subprocess.run(
            ["git", "merge-base", "--is-ancestor", ref, "HEAD"],
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode == 0:
            return
    if seen_ref:
        violations.append("baseline_authority_main_ancestor_check_failed")
    else:
        violations.append("baseline_authority_main_ref_unavailable")


def _validate_contract(contract: dict[str, Any], violations: list[str]) -> None:
    if contract.get("contract_id") != "b23.p0.semantic_authority_freeze.main":
        violations.append("contract_id_mismatch")
    if contract.get("branch") != "main":
        violations.append("contract_branch_mismatch")
    if contract.get("phase") != "B2.3-P0":
        violations.append("contract_phase_mismatch")

    baseline_authority = contract.get("baseline_authority")
    if not isinstance(baseline_authority, dict):
        violations.append("contract_baseline_authority_invalid")
    else:
        if baseline_authority.get("authoritative_branch") != "main":
            violations.append("contract_authoritative_branch_mismatch")
        if baseline_authority.get("require_main_ancestor_for_semantic_work") is not True:
            violations.append("contract_main_ancestor_requirement_missing")

    shared_identity = contract.get("shared_identity_canonicalization")
    if not isinstance(shared_identity, dict):
        violations.append("contract_shared_identity_invalid")
    else:
        precedence = tuple(shared_identity.get("precedence_order", []))
        expected_precedence = (
            "normalized_commerce_reference",
            "provider_native_commerce_reference",
            "strict_order_id",
        )
        if precedence != expected_precedence:
            violations.append("contract_precedence_order_mismatch")
        if shared_identity.get("canonicalization_failure_state") != "canonicalization_failed_explicit":
            violations.append("contract_canonicalization_failure_state_mismatch")

    delayed_arrival = contract.get("privacy_safe_delayed_arrival")
    if not isinstance(delayed_arrival, dict):
        violations.append("contract_privacy_safe_delayed_arrival_invalid")
    else:
        forbidden = set(delayed_arrival.get("forbidden_mechanisms", []))
        expected_forbidden = {
            "extend_attribution_session_window",
            "cross_session_identity_reconstruction",
            "persist_pii_for_matching",
            "persist_reversible_user_linked_hashes",
            "privacy_ambiguous_shadow_identity_graph",
        }
        if forbidden != expected_forbidden:
            violations.append("contract_forbidden_delayed_arrival_mechanisms_mismatch")
        if delayed_arrival.get("allowed_topology") != "durable_tenant_scoped_non_pii_commerce_identity_substrate":
            violations.append("contract_allowed_topology_mismatch")
        if (
            delayed_arrival.get("delayed_arrival_policy")
            != "match_via_durable_commerce_identity_else_explicit_unmatched_or_unsupported"
        ):
            violations.append("contract_delayed_arrival_policy_mismatch")

    financial_truth = contract.get("financial_truth_semantics")
    if not isinstance(financial_truth, dict):
        violations.append("contract_financial_truth_semantics_invalid")
    else:
        if financial_truth.get("amount_basis") != "verified_captured_amount_minor_units":
            violations.append("contract_amount_basis_mismatch")
        if financial_truth.get("currency_stance") != "same_currency_only_cross_currency_unsupported":
            violations.append("contract_currency_stance_mismatch")
        unsupported_adjustments = set(financial_truth.get("unsupported_payment_adjustments", []))
        expected_unsupported_adjustments = {
            "refund",
            "partial_capture",
            "split_payment",
            "provider_adjustment",
        }
        if unsupported_adjustments != expected_unsupported_adjustments:
            violations.append("contract_unsupported_payment_adjustments_mismatch")

    boundary = contract.get("b23_b21_boundary")
    if not isinstance(boundary, dict):
        violations.append("contract_b23_b21_boundary_invalid")
    else:
        if boundary.get("b23_scope") != "verified_revenue_truth_at_order_conversion_grain":
            violations.append("contract_boundary_scope_mismatch")
        if boundary.get("b23_must_not_allocate_attribution") is not True:
            violations.append("contract_boundary_allocation_forbidden_mismatch")

    verdict_taxonomy = set(contract.get("verdict_taxonomy", []))
    expected_verdict_taxonomy = {
        "matched",
        "flagged",
        "severe",
        "unmatched",
        "unsupported",
        "canonicalization_failed",
    }
    if verdict_taxonomy != expected_verdict_taxonomy:
        violations.append("contract_verdict_taxonomy_mismatch")

    discrepancy_taxonomy = set(contract.get("discrepancy_taxonomy", []))
    expected_discrepancy_taxonomy = {
        "exact",
        "within_tolerance",
        "over_tolerance",
        "severe_gap",
        "unsupported",
        "identity_failure",
    }
    if discrepancy_taxonomy != expected_discrepancy_taxonomy:
        violations.append("contract_discrepancy_taxonomy_mismatch")

    false_authority_exclusions = set(contract.get("false_authority_exclusions", []))
    expected_false_authority_exclusions = {
        "revenue_ledger.state",
        "revenue_ledger.discrepancy_bps",
        "reconciliation_runs.state",
        "RevenueReconciliationService",
        "/api/reconciliation/status",
        "/api/reconciliation/platform/{platform_id}",
    }
    if false_authority_exclusions != expected_false_authority_exclusions:
        violations.append("contract_false_authority_exclusions_mismatch")

    performance_authority = contract.get("performance_authority")
    if not isinstance(performance_authority, dict):
        violations.append("contract_performance_authority_invalid")
    else:
        if int(performance_authority.get("kernel_1000_orders_max_seconds", -1)) != 5:
            violations.append("contract_performance_kernel_threshold_mismatch")
        if int(performance_authority.get("report_1000_orders_max_seconds", -1)) != 10:
            violations.append("contract_performance_report_threshold_mismatch")


def _validate_semantic_authority_file(path: Path, violations: list[str]) -> None:
    text = _read_text(path)
    required_tokens = (
        "B23_P0_SEMANTIC_AUTHORITY_VERSION = \"b2.3-p0-v1\"",
        "B23_PRECEDENCE_ORDER = (",
        "FORBIDDEN_DELAYED_ARRIVAL_STRATEGIES = frozenset(",
        "ALLOWED_DELAYED_ARRIVAL_TOPOLOGY = (",
        "DELAYED_ARRIVAL_POLICY = (",
        "B23_AMOUNT_BASIS = \"verified_captured_amount_minor_units\"",
        "B23_CURRENCY_STANCE = \"same_currency_only_cross_currency_unsupported\"",
        "UNSUPPORTED_PAYMENT_ADJUSTMENTS = frozenset(",
        "B23_FORBIDDEN_FALSE_AUTHORITIES = frozenset(",
        "class B23Verdict(str, Enum):",
        "class B23DiscrepancyClass(str, Enum):",
        "def canonicalize_verified_commerce_reference(",
        "def canonicalize_attribution_commerce_reference(",
        "def resolve_canonical_match_key(",
        "def validate_delayed_arrival_strategy(",
        "def validate_delayed_arrival_topology(",
        "def assert_b23_boundary_not_allocation(",
        "def assert_b23_authority_source(",
        "def map_b23_verdict_for_downstream(",
        "def map_b23_discrepancy_for_downstream(",
        "def load_b23_p0_semantic_authority_contract(",
        "B23_P0_PERFORMANCE_AUTHORITY = B23PerformanceAuthority(",
    )
    for token in required_tokens:
        if token not in text:
            violations.append(f"semantic_authority_missing_token:{token}")

    shared_call_token = "return canonicalize_commerce_reference("
    if text.count(shared_call_token) < 2:
        violations.append("semantic_authority_dual_side_shared_canonicalizer_missing")


def _validate_runtime_proof_file(path: Path, violations: list[str]) -> None:
    text = _read_text(path)
    required_tests = (
        "test_b23_p0_contract_load_is_authoritative",
        "test_b23_p0_dual_sided_canonicalization_converges_decorated_variants",
        "test_b23_p0_precedence_order_is_deterministic",
        "test_b23_p0_canonicalization_failure_state_is_explicit",
        "test_b23_p0_illegal_delayed_arrival_strategies_fail_closed",
        "test_b23_p0_only_allowed_delayed_arrival_topology_is_accepted",
        "test_b23_p0_amount_currency_and_adjustment_stance_is_frozen",
        "test_b23_p0_boundary_law_blocks_allocation_inside_b23",
        "test_b23_p0_false_authority_sources_are_rejected",
        "test_b23_p0_downstream_mapping_is_typed_and_deterministic",
    )
    for token in required_tests:
        if token not in text:
            violations.append(f"runtime_proof_missing_test:{token}")


def _validate_event_service_file(path: Path, violations: list[str]) -> None:
    text = _read_text(path)
    required_tokens = (
        "canonicalize_attribution_commerce_reference(",
        "resolve_canonical_match_key(",
        "Webhook identity canonicalization failed under B2.3-P0 authority policy.",
    )
    for token in required_tokens:
        if token not in text:
            violations.append(f"event_service_missing_b23_token:{token}")


def _validate_ci_workflow(
    *,
    workflow_file: Path,
    contract: dict[str, Any],
    violations: list[str],
) -> None:
    text = _read_text(workflow_file)
    required_tokens = (
        "Enforce B2.3-P0 semantic authority freeze",
        "python scripts/ci/enforce_b23_p0_semantic_authority_freeze.py",
        "Run B2.3-P0 semantic authority freeze negative controls",
        "pytest backend/tests/test_b23_p0_semantic_authority_freeze_enforcer.py -q",
        "Run B2.3-P0 semantic authority runtime proofs",
        "pytest backend/tests/test_b23_p0_semantic_authority.py -q",
    )
    for token in required_tokens:
        if token not in text:
            violations.append(f"workflow_missing_token:{token}")

    required_ci_wiring = contract.get("required_ci_wiring", [])
    if not isinstance(required_ci_wiring, list):
        violations.append("contract_required_ci_wiring_invalid")
        return
    for command in required_ci_wiring:
        normalized = str(command).strip()
        if normalized and normalized not in text:
            violations.append(f"workflow_missing_contract_ci_wiring_token:{normalized}")


def _validate_enforcer_proof_file(path: Path, violations: list[str]) -> None:
    text = _read_text(path)
    required_tokens = (
        "test_b23_p0_semantic_authority_freeze_enforcer_passes_repo_state",
        "test_b23_p0_semantic_authority_freeze_enforcer_negative_control_forced_regression",
    )
    for token in required_tokens:
        if token not in text:
            violations.append(f"enforcer_proof_missing_token:{token}")


def run_enforcement(
    *,
    repo_root: Path,
    governance_contract_file: Path,
    semantic_authority_file: Path,
    event_service_file: Path,
    runtime_proof_file: Path,
    enforcer_proof_file: Path,
    ci_workflow_file: Path,
    skip_baseline_git_check: bool = False,
) -> tuple[int, list[str]]:
    violations: list[str] = []
    required_files = (
        governance_contract_file,
        semantic_authority_file,
        event_service_file,
        runtime_proof_file,
        enforcer_proof_file,
        ci_workflow_file,
    )
    for path in required_files:
        if not path.exists():
            violations.append(f"missing_required_file:{path}")
    if violations:
        return 1, violations

    contract = _read_json(governance_contract_file)
    _validate_contract(contract, violations)
    _validate_semantic_authority_file(semantic_authority_file, violations)
    _validate_event_service_file(event_service_file, violations)
    _validate_runtime_proof_file(runtime_proof_file, violations)
    _validate_enforcer_proof_file(enforcer_proof_file, violations)
    _validate_ci_workflow(
        workflow_file=ci_workflow_file,
        contract=contract,
        violations=violations,
    )
    if not skip_baseline_git_check:
        _validate_baseline_ancestry(repo_root, violations)

    return (1 if violations else 0), violations


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Enforce B2.3-P0 baseline convergence and semantic authority freeze."
    )
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--governance-contract-file", default=GOVERNANCE_CONTRACT)
    parser.add_argument("--semantic-authority-file", default=SEMANTIC_AUTHORITY_FILE)
    parser.add_argument("--event-service-file", default=EVENT_SERVICE_FILE)
    parser.add_argument("--runtime-proof-file", default=RUNTIME_PROOF_FILE)
    parser.add_argument("--enforcer-proof-file", default=ENFORCER_PROOF_FILE)
    parser.add_argument("--ci-workflow-file", default=CI_WORKFLOW_FILE)
    parser.add_argument("--skip-baseline-git-check", action="store_true")
    parser.add_argument("--simulate-regression", action="store_true")
    parser.add_argument("--simulate-baseline-drift", action="store_true")
    args = parser.parse_args(argv[1:])

    if args.simulate_regression:
        sys.stdout.write(
            "b23_p0_semantic_authority_freeze_enforcer\n"
            "result=FAIL\n"
            "synthetic_regression=forced_failure_path\n"
        )
        return 1

    if args.simulate_baseline_drift:
        sys.stdout.write(
            "b23_p0_semantic_authority_freeze_enforcer\n"
            "result=FAIL\n"
            "baseline_authority_main_ancestor_check_failed\n"
        )
        return 1

    repo_root = _resolve(REPO_ROOT, args.repo_root)
    status, violations = run_enforcement(
        repo_root=repo_root,
        governance_contract_file=_resolve(repo_root, args.governance_contract_file),
        semantic_authority_file=_resolve(repo_root, args.semantic_authority_file),
        event_service_file=_resolve(repo_root, args.event_service_file),
        runtime_proof_file=_resolve(repo_root, args.runtime_proof_file),
        enforcer_proof_file=_resolve(repo_root, args.enforcer_proof_file),
        ci_workflow_file=_resolve(repo_root, args.ci_workflow_file),
        skip_baseline_git_check=bool(args.skip_baseline_git_check),
    )

    lines = ["b23_p0_semantic_authority_freeze_enforcer"]
    if status != 0:
        lines.append("result=FAIL")
        lines.extend(violations)
    else:
        lines.append("result=PASS")
        lines.append("enforcement=baseline_convergence_and_semantic_authority_fail_closed")
    sys.stdout.write("\n".join(lines) + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
