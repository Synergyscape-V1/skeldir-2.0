#!/usr/bin/env python3
"""Enforce B2.3-P6 end-to-end closure and downstream-readiness governance."""

from __future__ import annotations

import argparse
import inspect
import importlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_FILE = "contracts-internal/governance/b23_p6_end_to_end_closure.main.json"
WORKFLOW_FILE = ".github/workflows/ci.yml"


def _resolve(repo_root: Path, raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    return (repo_root / path).resolve()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(_read_text(path))
    if not isinstance(payload, dict):
        raise ValueError(f"json_payload_not_object:{path}")
    return payload


def _contains_all(text: str, tokens: list[str]) -> list[str]:
    return [token for token in tokens if token not in text]


def _validate_runtime_proof(
    *, contract: dict[str, Any], test_text: str, violations: list[str]
) -> None:
    runtime = contract["runtime_proof"]
    missing = _contains_all(test_text, list(runtime["required_tokens"]))
    violations.extend(f"runtime_required_token_missing:{token}" for token in missing)

    for token in runtime["forbidden_tokens"]:
        if token in test_text:
            violations.append(f"runtime_forbidden_token_present:{token}")
    if "SET\n                    status" in test_text or "SET status" in test_text:
        violations.append("runtime_direct_status_update_detected")
    if "monkeypatch" in test_text and "datetime" in test_text:
        violations.append("runtime_python_time_monkeypatch_detected")
    if "time.sleep(" in test_text:
        violations.append("runtime_blind_sleep_detected")
    if "await execute_b23_batch_match_engine(" in test_text:
        violations.append("runtime_direct_match_call_detected")

    required_test_names = (
        "test_b23_p6_signed_webhook_to_confirmed_api_downstream_closure",
        "test_b23_p6_matched_states_require_attribution_fk_at_db_layer",
        "test_b23_p6_exception_records_remain_base_table",
        "test_b23_p6_verification_coverage_callable_is_deterministic_and_bounded",
    )
    for test_name in required_test_names:
        if f"def {test_name}" not in test_text:
            violations.append(f"runtime_required_test_missing:{test_name}")


def _validate_database_constraint(
    *,
    contract: dict[str, Any],
    canonical_text: str,
    migration_text: str,
    violations: list[str],
) -> None:
    constraint = contract["database_constraints"]["matched_attribution_fk_constraint"]
    if constraint not in canonical_text:
        violations.append(
            f"matched_attribution_fk_constraint_missing_canonical:{constraint}"
        )
    if constraint not in migration_text:
        violations.append(
            f"matched_attribution_fk_constraint_missing_migration:{constraint}"
        )
    for status_value in contract["database_constraints"]["matched_states"]:
        if status_value not in canonical_text or status_value not in migration_text:
            violations.append(
                f"matched_state_missing_from_fk_constraint:{status_value}"
            )
    if "attribution_event_id IS NOT NULL" not in canonical_text:
        violations.append("matched_attribution_fk_not_database_enforced")


def _validate_verification_coverage(
    *, repo_root: Path, contract: dict[str, Any], spec_text: str, violations: list[str]
) -> None:
    required_spec_tokens = (
        "VERIFICATION_COVERAGE",
        "Numerator",
        "Denominator",
        "connected-platform",
        "unsupported",
        "Tenant scope",
        "half-open",
        "integer minor units",
        "ROUND_HALF_UP",
        "Zero denominator",
        "95.00%",
        "not `76%`",
    )
    for token in required_spec_tokens:
        if token not in spec_text:
            violations.append(f"verification_coverage_spec_token_missing:{token}")

    coverage_path = (
        repo_root
        / "backend"
        / "app"
        / "revenue_verification"
        / "verification_coverage.py"
    )
    coverage_text = _read_text(coverage_path)
    aggregate_tokens = (
        "VerificationCoverageAggregate",
        "fetch_verification_coverage_aggregate",
        "SUM(",
        "tenant_id = :tenant_id",
        "occurred_at >= :window_start",
        "occurred_at < :window_end",
        "provider IN :supported_platforms",
        "currency_code = :currency_code",
        "matched_webhook_revenue_minor",
        "connected_platform_revenue_minor",
    )
    for token in aggregate_tokens:
        if token not in coverage_text:
            violations.append(f"verification_coverage_aggregate_token_missing:{token}")
    forbidden_query_tokens = (
        "SELECT *",
        "fetch_matched_webhook_revenue_rows",
        "for row in rows",
        "Iterable[VerificationCoverageRevenue]",
        "VerificationCoverageRevenue",
        "external_api",
        "llm",
    )
    for token in forbidden_query_tokens:
        if token in coverage_text:
            violations.append(f"verification_coverage_forbidden_token_present:{token}")

    backend_path = str(repo_root / "backend")
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)
    os.environ.setdefault(
        "DATABASE_URL", "postgresql://app_user:app_user@127.0.0.1:5432/skeldir"
    )
    os.environ.setdefault("AUTH_JWT_SECRET", "b23-p6-local-enforcer")
    module = importlib.import_module(
        contract["verification_coverage"]["callable_module"]
    )
    callable_name = contract["verification_coverage"]["callable_name"]
    governed_name = contract["verification_coverage"]["governed_object_name"]
    if not callable(getattr(module, callable_name, None)):
        violations.append(f"verification_coverage_callable_missing:{callable_name}")
        return
    governed = getattr(module, governed_name, None)
    if governed is None or not callable(getattr(governed, "compute", None)):
        violations.append(
            f"verification_coverage_governed_object_missing:{governed_name}.compute"
        )
        return
    aggregate_fetcher = getattr(
        module, contract["verification_coverage"]["aggregate_fetcher_name"], None
    )
    if not callable(aggregate_fetcher):
        violations.append("verification_coverage_aggregate_fetcher_missing")
        return
    aggregate_source = inspect.getsource(aggregate_fetcher)
    for token in aggregate_tokens:
        if token not in aggregate_source and token != "VerificationCoverageAggregate":
            violations.append(f"verification_coverage_fetcher_token_missing:{token}")

    tenant_id = uuid4()
    now = datetime.now(timezone.utc)
    aggregate_type = getattr(module, "VerificationCoverageAggregate")
    result = getattr(module, callable_name)(
        aggregate_type(
            tenant_id=tenant_id,
            currency_code="USD",
            window_start=now - timedelta(minutes=1),
            window_end=now + timedelta(minutes=1),
            matched_webhook_revenue_minor=76000,
            connected_platform_revenue_minor=80000,
        )
    )
    expected = Decimal(contract["verification_coverage"]["example_expected_percent"])
    if result.coverage_percent != expected:
        violations.append(
            f"verification_coverage_example_failed:{result.coverage_percent}!={expected}"
        )
    if result.denominator_connected_platform_revenue_minor != 80000:
        violations.append(
            "verification_coverage_denominator_not_connected_platform_only"
        )
    if result.numerator_matched_webhook_revenue_minor != 76000:
        violations.append("verification_coverage_numerator_not_matched_webhook_only")
    zero = governed.compute(
        aggregate_type(
            tenant_id=tenant_id,
            currency_code="USD",
            window_start=now - timedelta(minutes=1),
            window_end=now + timedelta(minutes=1),
            matched_webhook_revenue_minor=0,
            connected_platform_revenue_minor=0,
        )
    )
    if zero.coverage_percent != Decimal("0.00") or not zero.zero_denominator:
        violations.append("verification_coverage_zero_denominator_contract_failed")


def _validate_readiness_doc(
    *, contract: dict[str, Any], readiness_text: str, violations: list[str]
) -> None:
    readiness = contract["downstream_readiness"]
    for token in readiness["required_b24_terms"]:
        if token not in readiness_text:
            violations.append(f"readiness_b24_term_missing:{token}")
    for token in readiness["required_b26_terms"]:
        if token not in readiness_text:
            violations.append(f"readiness_b26_term_missing:{token}")
    for token in readiness["required_out_of_scope_terms"]:
        if token not in readiness_text:
            violations.append(f"readiness_out_of_scope_term_missing:{token}")
    if (
        readiness.get("requires_deferral_register")
        and "Deferral Register" not in readiness_text
    ):
        violations.append("readiness_deferral_register_missing")


def _validate_workflow(
    *, contract: dict[str, Any], workflow_text: str, violations: list[str]
) -> None:
    workflow = contract["workflow"]
    for token in (
        workflow["required_job_name"],
        workflow["required_command"],
        workflow["required_runtime_test_command"],
        'SKELDIR_B23_P6_REQUIRE_DB_PROOFS: "1"',
    ):
        if token not in workflow_text:
            violations.append(f"workflow_p6_token_missing:{token}")
    preservation = contract["preservation"]
    for token in (
        preservation["p0_to_p5_enforcer"],
        preservation["branch_protection_verifier"],
        preservation["required_check_name"],
    ):
        if token not in workflow_text and token not in _read_text(
            _resolve(REPO_ROOT, preservation["p5_manifest"])
        ):
            violations.append(f"preservation_token_missing:{token}")


def _validate_scope(
    repo_root: Path, contract: dict[str, Any], violations: list[str]
) -> None:
    tracked_text_paths = [
        _resolve(
            repo_root, "backend/app/revenue_verification/verification_coverage.py"
        ),
        _resolve(repo_root, contract["downstream_readiness"]["doc_path"]),
        _resolve(repo_root, contract["verification_coverage"]["spec_path"]),
    ]
    combined = "\n".join(
        _read_text(path) for path in tracked_text_paths if path.exists()
    ).lower()
    forbidden_scope = {str(item).lower() for item in contract["forbidden_scope"]}
    implementation_forbidden = (
        "pymc",
        "bayesian convergence",
        "vendor normalization engine",
    )
    for token in implementation_forbidden:
        if token in combined and "out of scope" not in combined:
            violations.append(f"forbidden_scope_implemented:{token}")
    for token in forbidden_scope:
        if token not in " ".join(
            str(item).lower() for item in contract["forbidden_scope"]
        ):
            violations.append(f"forbidden_scope_contract_missing:{token}")


def run_enforcement(
    *,
    repo_root: Path,
    contract_file: Path,
    workflow_file: Path,
    simulate_regression: bool = False,
) -> tuple[int, list[str]]:
    contract = _read_json(contract_file)
    violations: list[str] = []
    if contract.get("contract_id") != "b23.p6.end_to_end_closure.main":
        violations.append("contract_id_mismatch")
    if contract.get("phase") != "B2.3-P6":
        violations.append("contract_phase_mismatch")

    runtime_path = _resolve(repo_root, contract["runtime_proof"]["test_path"])
    canonical_path = _resolve(
        repo_root, contract["database_constraints"]["canonical_schema"]
    )
    migration_path = _resolve(repo_root, contract["database_constraints"]["migration"])
    spec_path = _resolve(repo_root, contract["verification_coverage"]["spec_path"])
    readiness_path = _resolve(repo_root, contract["downstream_readiness"]["doc_path"])

    for path_name, path in (
        ("runtime_test", runtime_path),
        ("canonical_schema", canonical_path),
        ("migration", migration_path),
        ("verification_coverage_spec", spec_path),
        ("downstream_readiness_doc", readiness_path),
        ("workflow", workflow_file),
    ):
        if not path.exists():
            violations.append(f"required_artifact_missing:{path_name}:{path}")

    if not violations:
        runtime_text = _read_text(runtime_path)
        canonical_text = _read_text(canonical_path)
        migration_text = _read_text(migration_path)
        spec_text = _read_text(spec_path)
        readiness_text = _read_text(readiness_path)
        workflow_text = _read_text(workflow_file)
        if simulate_regression:
            runtime_text = runtime_text.replace(
                "invalid_status == 401", "invalid_status == 200"
            )
            spec_text = spec_text.replace("95.00%", "76.00%")

        _validate_runtime_proof(
            contract=contract, test_text=runtime_text, violations=violations
        )
        _validate_database_constraint(
            contract=contract,
            canonical_text=canonical_text,
            migration_text=migration_text,
            violations=violations,
        )
        _validate_verification_coverage(
            repo_root=repo_root,
            contract=contract,
            spec_text=spec_text,
            violations=violations,
        )
        _validate_readiness_doc(
            contract=contract, readiness_text=readiness_text, violations=violations
        )
        _validate_workflow(
            contract=contract, workflow_text=workflow_text, violations=violations
        )
        _validate_scope(repo_root, contract, violations)

    if simulate_regression and not violations:
        violations.append("synthetic_regression_not_detected")
    return (0 if not violations else 1), violations


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--contract-file", default=CONTRACT_FILE)
    parser.add_argument("--workflow-file", default=WORKFLOW_FILE)
    parser.add_argument("--simulate-regression", action="store_true")
    args = parser.parse_args(argv[1:])

    repo_root = _resolve(REPO_ROOT, args.repo_root)
    status, violations = run_enforcement(
        repo_root=repo_root,
        contract_file=_resolve(repo_root, args.contract_file),
        workflow_file=_resolve(repo_root, args.workflow_file),
        simulate_regression=args.simulate_regression,
    )
    print(
        json.dumps(
            {"status": "PASS" if status == 0 else "FAIL", "violations": violations},
            sort_keys=True,
        )
    )
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
