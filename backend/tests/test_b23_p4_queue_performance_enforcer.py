from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ENFORCER = REPO_ROOT / "scripts" / "ci" / "enforce_b23_p4_queue_performance.py"
CONTRACT = (
    REPO_ROOT / "contracts-internal" / "governance" / "b23_p4_queue_performance.main.json"
)
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"

_SPEC = importlib.util.spec_from_file_location("b23_p4_enforcer_module", ENFORCER)
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)


def test_b23_p4_queue_performance_enforcer_passes_repo_state() -> None:
    status, violations = _MODULE.run_enforcement(
        repo_root=REPO_ROOT,
        contract_file=CONTRACT,
        workflow_file=WORKFLOW,
        simulate_regression=False,
    )
    assert status == 0, violations


def test_b23_p4_queue_performance_enforcer_forced_negative_control() -> None:
    status, violations = _MODULE.run_enforcement(
        repo_root=REPO_ROOT,
        contract_file=CONTRACT,
        workflow_file=WORKFLOW,
        simulate_regression=True,
    )
    assert status != 0
    assert "synthetic_regression=forced_failure_path" in violations


def test_negative_control_missing_b23_route_fails(monkeypatch) -> None:
    original_read_text = _MODULE._read_text
    celery_path = REPO_ROOT / "backend" / "app" / "celery_app.py"

    def mutated_read_text(path: Path) -> str:
        text = original_read_text(path)
        if Path(path) == celery_path:
            return text.replace("QUEUE_B23_MATCH_ENGINE", "QUEUE_MAINTENANCE")
        return text

    monkeypatch.setattr(_MODULE, "_read_text", mutated_read_text)
    status, violations = _MODULE.run_enforcement(
        repo_root=REPO_ROOT,
        contract_file=CONTRACT,
        workflow_file=WORKFLOW,
        simulate_regression=False,
    )
    assert status != 0
    assert "b23_task_route_not_isolated" in violations


def test_negative_control_worker_queue_overlap_fails(monkeypatch) -> None:
    original_read_text = _MODULE._read_text
    procfile = REPO_ROOT / "Procfile"

    def mutated_read_text(path: Path) -> str:
        text = original_read_text(path)
        if Path(path) == procfile:
            return text.replace("--queues=b23_match_engine", "--queues=b23_match_engine,llm")
        return text

    monkeypatch.setattr(_MODULE, "_read_text", mutated_read_text)
    status, violations = _MODULE.run_enforcement(
        repo_root=REPO_ROOT,
        contract_file=CONTRACT,
        workflow_file=WORKFLOW,
        simulate_regression=False,
    )
    assert status != 0
    assert any(v.startswith("b23_worker_forbidden_queue_overlap:") for v in violations)


def test_negative_control_missing_dedicated_pool_fails(monkeypatch) -> None:
    original_read_text = _MODULE._read_text
    session_path = REPO_ROOT / "backend" / "app" / "db" / "session.py"

    def mutated_read_text(path: Path) -> str:
        text = original_read_text(path)
        if Path(path) == session_path:
            return text.replace("b23_engine", "shared_engine_removed")
        return text

    monkeypatch.setattr(_MODULE, "_read_text", mutated_read_text)
    status, violations = _MODULE.run_enforcement(
        repo_root=REPO_ROOT,
        contract_file=CONTRACT,
        workflow_file=WORKFLOW,
        simulate_regression=False,
    )
    assert status != 0
    assert "b23_db_pool_token_missing:b23_engine" in violations


def test_negative_control_n_plus_one_batch_token_fails(monkeypatch) -> None:
    original_read_text = _MODULE._read_text
    batch_path = REPO_ROOT / "backend" / "app" / "revenue_verification" / "batch_engine.py"

    def mutated_read_text(path: Path) -> str:
        text = original_read_text(path)
        if Path(path) == batch_path:
            return text + "\n# regression sentinel: for match_input in rows\n"
        return text

    monkeypatch.setattr(_MODULE, "_read_text", mutated_read_text)
    status, violations = _MODULE.run_enforcement(
        repo_root=REPO_ROOT,
        contract_file=CONTRACT,
        workflow_file=WORKFLOW,
        simulate_regression=False,
    )
    assert status != 0
    assert "batch_forbidden_token_present:for match_input in" in violations


def test_negative_control_missing_telemetry_index_fails(monkeypatch) -> None:
    original_read_text = _MODULE._read_text
    schema_path = REPO_ROOT / "db" / "schema" / "canonical_schema.sql"

    def mutated_read_text(path: Path) -> str:
        text = original_read_text(path)
        if Path(path) == schema_path:
            return text.replace("idx_b23_p4_match_rate_tenant_transition_status", "")
        return text

    monkeypatch.setattr(_MODULE, "_read_text", mutated_read_text)
    status, violations = _MODULE.run_enforcement(
        repo_root=REPO_ROOT,
        contract_file=CONTRACT,
        workflow_file=WORKFLOW,
        simulate_regression=False,
    )
    assert status != 0
    assert "telemetry_index_missing:idx_b23_p4_match_rate_tenant_transition_status" in violations
