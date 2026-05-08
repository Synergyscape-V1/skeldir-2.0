from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ENFORCER = REPO_ROOT / "scripts" / "ci" / "enforce_b23_p6_end_to_end_closure.py"
CONTRACT = (
    REPO_ROOT
    / "contracts-internal"
    / "governance"
    / "b23_p6_end_to_end_closure.main.json"
)
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"

_SPEC = importlib.util.spec_from_file_location("b23_p6_enforcer_module", ENFORCER)
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)


def test_b23_p6_end_to_end_closure_enforcer_passes_repo_state() -> None:
    status, violations = _MODULE.run_enforcement(
        repo_root=REPO_ROOT,
        contract_file=CONTRACT,
        workflow_file=WORKFLOW,
        simulate_regression=False,
    )
    assert status == 0, violations


def test_b23_p6_end_to_end_closure_enforcer_negative_control_forced_regression() -> (
    None
):
    status, violations = _MODULE.run_enforcement(
        repo_root=REPO_ROOT,
        contract_file=CONTRACT,
        workflow_file=WORKFLOW,
        simulate_regression=True,
    )
    assert status != 0
    assert any("runtime_required_token_missing" in item for item in violations)
    assert any(
        "verification_coverage_spec_token_missing" in item for item in violations
    )


def test_negative_control_direct_status_update_fails(monkeypatch) -> None:
    original_read_text = _MODULE._read_text
    runtime_path = REPO_ROOT / "backend" / "tests" / "test_b23_p6_end_to_end_closure.py"

    def mutated_read_text(path: Path) -> str:
        text = original_read_text(path)
        if Path(path) == runtime_path:
            return text + "\n# regression sentinel: SET status = 'matched_confirmed'\n"
        return text

    monkeypatch.setattr(_MODULE, "_read_text", mutated_read_text)
    status, violations = _MODULE.run_enforcement(
        repo_root=REPO_ROOT,
        contract_file=CONTRACT,
        workflow_file=WORKFLOW,
        simulate_regression=False,
    )
    assert status != 0
    assert "runtime_direct_status_update_detected" in violations


def test_negative_control_direct_match_call_fails(monkeypatch) -> None:
    original_read_text = _MODULE._read_text
    runtime_path = REPO_ROOT / "backend" / "tests" / "test_b23_p6_end_to_end_closure.py"

    def mutated_read_text(path: Path) -> str:
        text = original_read_text(path)
        if Path(path) == runtime_path:
            return text + "\n# regression: await execute_b23_batch_match_engine(\n"
        return text

    monkeypatch.setattr(_MODULE, "_read_text", mutated_read_text)
    status, violations = _MODULE.run_enforcement(
        repo_root=REPO_ROOT,
        contract_file=CONTRACT,
        workflow_file=WORKFLOW,
        simulate_regression=False,
    )
    assert status != 0
    assert "runtime_direct_match_call_detected" in violations


def test_negative_control_test_body_manual_apply_async_fails(monkeypatch) -> None:
    original_read_text = _MODULE._read_text
    runtime_path = REPO_ROOT / "backend" / "tests" / "test_b23_p6_end_to_end_closure.py"

    def mutated_read_text(path: Path) -> str:
        text = original_read_text(path)
        if Path(path) == runtime_path:
            return text + "\n# regression: execute_b23_batch_match_engine_task.apply_async\n"
        return text

    monkeypatch.setattr(_MODULE, "_read_text", mutated_read_text)
    status, violations = _MODULE.run_enforcement(
        repo_root=REPO_ROOT,
        contract_file=CONTRACT,
        workflow_file=WORKFLOW,
        simulate_regression=False,
    )
    assert status != 0
    assert "runtime_test_body_manual_b23_apply_async_detected" in violations


def test_negative_control_manual_dispatcher_cranking_fails(monkeypatch) -> None:
    original_read_text = _MODULE._read_text
    runtime_path = REPO_ROOT / "backend" / "tests" / "test_b23_p6_end_to_end_closure.py"

    def mutated_read_text(path: Path) -> str:
        text = original_read_text(path)
        if Path(path) == runtime_path:
            return text + "\n# regression: run_outbox_dispatcher_once()\n"
        return text

    monkeypatch.setattr(_MODULE, "_read_text", mutated_read_text)
    status, violations = _MODULE.run_enforcement(
        repo_root=REPO_ROOT,
        contract_file=CONTRACT,
        workflow_file=WORKFLOW,
        simulate_regression=False,
    )
    assert status != 0
    assert any(
        item == "runtime_manual_intermediate_cranking_detected:run_outbox_dispatcher"
        or item == "runtime_manual_intermediate_cranking_detected:run_outbox_dispatcher_once"
        for item in violations
    )


def test_negative_control_missing_production_enqueue_fails(monkeypatch) -> None:
    original_read_text = _MODULE._read_text
    production_path = REPO_ROOT / "backend" / "app" / "api" / "webhooks.py"

    def mutated_read_text(path: Path) -> str:
        text = original_read_text(path)
        if Path(path) == production_path:
            return text.replace(
                "execute_b23_batch_match_engine_task.apply_async",
                "execute_b23_batch_match_engine_task.not_enqueued",
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
    assert any(
        item.startswith("production_dispatch_token_missing:")
        for item in violations
    )


def test_negative_control_production_enqueue_without_lineage_fails(monkeypatch) -> None:
    original_read_text = _MODULE._read_text
    production_path = REPO_ROOT / "backend" / "app" / "api" / "webhooks.py"

    def mutated_read_text(path: Path) -> str:
        text = original_read_text(path)
        if Path(path) == production_path:
            return text.replace("provider_native_event_reference", "provider_event_removed")
        return text

    monkeypatch.setattr(_MODULE, "_read_text", mutated_read_text)
    status, violations = _MODULE.run_enforcement(
        repo_root=REPO_ROOT,
        contract_file=CONTRACT,
        workflow_file=WORKFLOW,
        simulate_regression=False,
    )
    assert status != 0
    assert any(
        "production_dispatch_token_missing:provider_native_event_reference" in item
        for item in violations
    )


def test_negative_control_webhook_response_infrastructure_leak_fails(
    monkeypatch,
) -> None:
    original_read_text = _MODULE._read_text
    production_path = REPO_ROOT / "backend" / "app" / "api" / "webhooks.py"

    def mutated_read_text(path: Path) -> str:
        text = original_read_text(path)
        if Path(path) == production_path:
            return text.replace(
                "class WebhookResponse(BaseModel):\n    status: str",
                "class WebhookResponse(BaseModel):\n    status: str\n    task_id: str | None = None",
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
    assert "webhook_response_infrastructure_leak_field:task_id" in violations


def test_negative_control_fake_orchestrator_dependency_override_fails(
    monkeypatch,
) -> None:
    original_read_text = _MODULE._read_text
    runtime_path = REPO_ROOT / "backend" / "tests" / "test_b23_p6_end_to_end_closure.py"

    def mutated_read_text(path: Path) -> str:
        text = original_read_text(path)
        if Path(path) == runtime_path:
            return (
                text
                + "\n# regression: app.dependency_overrides[_dispatch_b23_match_task_from_persisted_ingress] = fake\n"
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
    assert any(
        item.startswith("production_dispatch_forbidden_test_origin:")
        or item.startswith("runtime_manual_intermediate_cranking_detected:")
        for item in violations
    )


def test_negative_control_eager_mode_only_proof_fails(monkeypatch) -> None:
    original_read_text = _MODULE._read_text
    runtime_path = REPO_ROOT / "backend" / "tests" / "test_b23_p6_end_to_end_closure.py"

    def mutated_read_text(path: Path) -> str:
        text = original_read_text(path)
        if Path(path) == runtime_path:
            return text.replace(
                "celery_app.conf.task_always_eager = False",
                "celery_app.conf.task_always_eager = True",
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
    assert any("runtime_required_token_missing" in item for item in violations)


def test_negative_control_default_queue_proof_fails(monkeypatch) -> None:
    original_read_text = _MODULE._read_text
    runtime_path = REPO_ROOT / "backend" / "tests" / "test_b23_p6_end_to_end_closure.py"

    def mutated_read_text(path: Path) -> str:
        text = original_read_text(path)
        if Path(path) == runtime_path:
            return text.replace("QUEUE_B23_MATCH_ENGINE", '"default"')
        return text

    monkeypatch.setattr(_MODULE, "_read_text", mutated_read_text)
    status, violations = _MODULE.run_enforcement(
        repo_root=REPO_ROOT,
        contract_file=CONTRACT,
        workflow_file=WORKFLOW,
        simulate_regression=False,
    )
    assert status != 0
    assert any(
        "runtime_required_token_missing:QUEUE_B23_MATCH_ENGINE" in item
        for item in violations
    )


def test_negative_control_blind_sleep_synchronization_fails(monkeypatch) -> None:
    original_read_text = _MODULE._read_text
    runtime_path = REPO_ROOT / "backend" / "tests" / "test_b23_p6_end_to_end_closure.py"

    def mutated_read_text(path: Path) -> str:
        text = original_read_text(path)
        if Path(path) == runtime_path:
            return text + "\n# regression sentinel: time.sleep(5)\n"
        return text

    monkeypatch.setattr(_MODULE, "_read_text", mutated_read_text)
    status, violations = _MODULE.run_enforcement(
        repo_root=REPO_ROOT,
        contract_file=CONTRACT,
        workflow_file=WORKFLOW,
        simulate_regression=False,
    )
    assert status != 0
    assert "runtime_blind_sleep_detected" in violations


def test_negative_control_missing_matched_fk_constraint_fails(monkeypatch) -> None:
    original_read_text = _MODULE._read_text
    canonical_path = REPO_ROOT / "db" / "schema" / "canonical_schema.sql"

    def mutated_read_text(path: Path) -> str:
        text = original_read_text(path)
        if Path(path) == canonical_path:
            return text.replace(
                "ck_b23_match_verdicts_matched_requires_attribution_event",
                "ck_b23_match_verdicts_matched_requires_attribution_removed",
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
    assert any(
        item.startswith("matched_attribution_fk_constraint_missing")
        for item in violations
    )


def test_negative_control_bare_string_verification_coverage_fails(monkeypatch) -> None:
    import app.revenue_verification.verification_coverage as coverage_module

    monkeypatch.setattr(
        coverage_module, "VERIFICATION_COVERAGE", "VERIFICATION_COVERAGE"
    )
    status, violations = _MODULE.run_enforcement(
        repo_root=REPO_ROOT,
        contract_file=CONTRACT,
        workflow_file=WORKFLOW,
        simulate_regression=False,
    )
    assert status != 0
    assert any(
        "verification_coverage_governed_object_missing" in item for item in violations
    )


def test_negative_control_missing_aggregate_tenant_predicate_fails(monkeypatch) -> None:
    original_read_text = _MODULE._read_text
    coverage_path = (
        REPO_ROOT
        / "backend"
        / "app"
        / "revenue_verification"
        / "verification_coverage.py"
    )

    def mutated_read_text(path: Path) -> str:
        text = original_read_text(path)
        if Path(path) == coverage_path:
            return text.replace("tenant_id = :tenant_id", "tenant_id IS NOT NULL")
        return text

    monkeypatch.setattr(_MODULE, "_read_text", mutated_read_text)
    status, violations = _MODULE.run_enforcement(
        repo_root=REPO_ROOT,
        contract_file=CONTRACT,
        workflow_file=WORKFLOW,
        simulate_regression=False,
    )
    assert status != 0
    assert any(
        "verification_coverage_aggregate_token_missing:tenant_id = :tenant_id" in item
        for item in violations
    )


def test_negative_control_raw_row_coverage_query_fails(monkeypatch) -> None:
    original_read_text = _MODULE._read_text
    coverage_path = (
        REPO_ROOT
        / "backend"
        / "app"
        / "revenue_verification"
        / "verification_coverage.py"
    )

    def mutated_read_text(path: Path) -> str:
        text = original_read_text(path)
        if Path(path) == coverage_path:
            return text + "\n# regression sentinel: SELECT * FROM raw revenue rows\n"
        return text

    monkeypatch.setattr(_MODULE, "_read_text", mutated_read_text)
    status, violations = _MODULE.run_enforcement(
        repo_root=REPO_ROOT,
        contract_file=CONTRACT,
        workflow_file=WORKFLOW,
        simulate_regression=False,
    )
    assert status != 0
    assert "verification_coverage_forbidden_token_present:SELECT *" in violations


def test_negative_control_missing_downstream_readiness_doc_fails(monkeypatch) -> None:
    original_exists = Path.exists
    readiness_path = REPO_ROOT / "docs" / "readiness" / "b23_downstream_readiness.md"

    def mutated_exists(path: Path) -> bool:
        if Path(path) == readiness_path:
            return False
        return original_exists(path)

    monkeypatch.setattr(Path, "exists", mutated_exists)
    status, violations = _MODULE.run_enforcement(
        repo_root=REPO_ROOT,
        contract_file=CONTRACT,
        workflow_file=WORKFLOW,
        simulate_regression=False,
    )
    assert status != 0
    assert any(
        "required_artifact_missing:downstream_readiness_doc" in item
        for item in violations
    )
