from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ENFORCER = REPO_ROOT / "scripts" / "ci" / "enforce_b23_p3_verdict_persistence.py"
CONTRACT = (
    REPO_ROOT / "contracts-internal" / "governance" / "b23_p3_verdict_persistence.main.json"
)
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"

_SPEC = importlib.util.spec_from_file_location("b23_p3_enforcer_module", ENFORCER)
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)


def test_b23_p3_verdict_persistence_enforcer_passes_repo_state() -> None:
    status, violations = _MODULE.run_enforcement(
        repo_root=REPO_ROOT,
        contract_file=CONTRACT,
        workflow_file=WORKFLOW,
        simulate_regression=False,
    )
    assert status == 0, violations


def test_b23_p3_verdict_persistence_enforcer_negative_control_forced_regression() -> None:
    status, violations = _MODULE.run_enforcement(
        repo_root=REPO_ROOT,
        contract_file=CONTRACT,
        workflow_file=WORKFLOW,
        simulate_regression=True,
    )
    assert status != 0
    assert "synthetic_regression=forced_failure_path" in violations


def test_negative_control_net_operand_in_canonical_discrepancy_constraint(monkeypatch) -> None:
    original_read_text = _MODULE._read_text
    canonical_path = REPO_ROOT / "db" / "schema" / "canonical_schema.sql"

    def mutated_read_text(path: Path) -> str:
        text = original_read_text(path)
        if Path(path) == canonical_path:
            return text.replace(
                (
                    "abs((canonical_expected_gross_amount_minor - "
                    "canonical_captured_gross_amount_minor))"
                ),
                (
                    "(canonical_expected_gross_amount_minor - "
                    "canonical_net_verified_amount_minor)"
                ),
            )
        return text

    monkeypatch.setattr(_MODULE, "_read_text", mutated_read_text)
    status, violations = _MODULE.run_enforcement(
        repo_root=REPO_ROOT,
        contract_file=CONTRACT,
        workflow_file=WORKFLOW,
        simulate_regression=False,
    )
    assert status != 0
    assert "canonical_discrepancy_constraint_uses_net_verified" in violations


def test_negative_control_operation_id_drift_fails(monkeypatch) -> None:
    original_read_yaml = _MODULE._read_yaml

    def mutated_read_yaml(path: Path):
        payload = original_read_yaml(path)
        payload["paths"]["/api/reconciliation/match-verdicts/{verdict_id}"]["get"][
            "operationId"
        ] = "getCollapsedMatchedVerdict"
        return payload

    monkeypatch.setattr(_MODULE, "_read_yaml", mutated_read_yaml)
    status, violations = _MODULE.run_enforcement(
        repo_root=REPO_ROOT,
        contract_file=CONTRACT,
        workflow_file=WORKFLOW,
        simulate_regression=False,
    )
    assert status != 0
    assert any(v.startswith("openapi_operation_id_mismatch") for v in violations)


def test_negative_control_response_model_extra_ignore_fails(monkeypatch) -> None:
    original_read_text = _MODULE._read_text
    schema_path = REPO_ROOT / "backend" / "app" / "schemas" / "revenue_verification.py"

    def mutated_read_text(path: Path) -> str:
        text = original_read_text(path)
        if Path(path) == schema_path:
            return text.replace('ConfigDict(extra="forbid")', 'ConfigDict(extra="ignore")', 1)
        return text

    monkeypatch.setattr(_MODULE, "_read_text", mutated_read_text)
    status, violations = _MODULE.run_enforcement(
        repo_root=REPO_ROOT,
        contract_file=CONTRACT,
        workflow_file=WORKFLOW,
        simulate_regression=False,
    )
    assert status != 0
    assert any(v.startswith("strict_response_model_forbidden_token") for v in violations)


def test_negative_control_frontend_enum_drift_fails(monkeypatch) -> None:
    original_read_text = _MODULE._read_text
    frontend_path = REPO_ROOT / "frontend" / "src" / "types" / "api" / "reconciliation.ts"

    def mutated_read_text(path: Path) -> str:
        text = original_read_text(path)
        if Path(path) == frontend_path:
            return text.replace("matched_provisional", "matched")
        return text

    monkeypatch.setattr(_MODULE, "_read_text", mutated_read_text)
    status, violations = _MODULE.run_enforcement(
        repo_root=REPO_ROOT,
        contract_file=CONTRACT,
        workflow_file=WORKFLOW,
        simulate_regression=False,
    )
    assert status != 0
    assert "frontend_status_enum_missing:matched_provisional" in violations
