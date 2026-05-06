from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


P1_FILES = (
    ".github/workflows/ci.yml",
    "contracts-internal/governance/b23_p1_schema_authority_lock.main.json",
    "alembic/versions/007_skeldir_foundation/202604291200_b23_p1_schema_authority_lock.py",
    "alembic/versions/007_skeldir_foundation/202604301030_b23_p1_followup_lifecycle_operands.py",
    "db/schema/canonical_schema.sql",
    "backend/app/revenue_verification/timing_constants.py",
    "scripts/ci/verify_b23_p1_migration_reversibility.py",
)
P2_FILES = (
    ".github/workflows/ci.yml",
    "contracts-internal/governance/b23_p2_match_engine_kernel.main.json",
    "backend/app/revenue_verification/extraction_registry.py",
    "backend/app/revenue_verification/match_engine_kernel.py",
    "backend/app/revenue_verification/failure_boundary.py",
    "backend/app/api/webhooks.py",
    "backend/tests/test_b23_p2_match_engine_kernel.py",
    "backend/tests/test_b23_p2_match_engine_kernel_enforcer.py",
)
P3_FILES = (
    ".github/workflows/ci.yml",
    "contracts-internal/governance/b23_p3_verdict_persistence.main.json",
    "alembic/versions/007_skeldir_foundation/202605051200_b23_p3_verdict_persistence_authority.py",
    "db/schema/canonical_schema.sql",
    "backend/app/revenue_verification/match_engine_kernel.py",
    "backend/app/revenue_verification/state_transitions.py",
    "backend/app/tasks/revenue_verification.py",
    "backend/app/tasks/beat_schedule.py",
    "backend/app/celery_app.py",
    "backend/app/api/revenue_verification.py",
    "backend/app/schemas/revenue_verification.py",
    "api-contracts/openapi/v1/reconciliation.yaml",
    "frontend/src/types/api/reconciliation.ts",
    "backend/tests/test_b23_p3_verdict_persistence.py",
    "backend/tests/test_b23_p3_verdict_persistence_enforcer.py",
)
P4_FILES = (
    ".github/workflows/ci.yml",
    "contracts-internal/governance/b23_p4_queue_performance.main.json",
    "backend/app/core/queues.py",
    "backend/app/celery_app.py",
    "backend/app/tasks/revenue_verification.py",
    "backend/app/tasks/beat_schedule.py",
    "backend/app/db/session.py",
    "backend/app/core/config.py",
    "backend/app/revenue_verification/batch_engine.py",
    "alembic/versions/007_skeldir_foundation/202605061200_b23_p4_queue_performance_indexes.py",
    "db/schema/canonical_schema.sql",
    "Procfile",
    "do" + "cker-compose.e2e.yml",
    "docs/ops/b23_p4/sql/01_rolling_24h_match_rate_by_tenant.sql",
    "docs/ops/b23_p4/sql/02_dlq_depth.sql",
    "docs/ops/b23_p4/sql/03_webhook_ingestion_failure_count_by_platform.sql",
    "backend/tests/test_b23_p4_queue_performance.py",
    "backend/tests/test_b23_p4_queue_performance_enforcer.py",
)


def _copy_fixture(tmp_path: Path, files: tuple[str, ...]) -> Path:
    fixture = tmp_path / "repo"
    for relative in files:
        source = REPO_ROOT / relative
        target = fixture / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return fixture


def _replace(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, f"mutation target missing: {path}: {old[:80]}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def _replace_all(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, f"mutation target missing: {path}: {old[:80]}"
    path.write_text(text.replace(old, new), encoding="utf-8")


def _run(script: str, fixture: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / script), "--repo-root", str(fixture)],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def _assert_correct_then_mutated_fails(
    tmp_path: Path,
    *,
    files: tuple[str, ...],
    script: str,
    mutate,
    expected: str,
) -> None:
    good = _copy_fixture(tmp_path / "good", files)
    good_result = _run(script, good)
    assert good_result.returncode == 0, good_result.stdout

    bad = _copy_fixture(tmp_path / "bad", files)
    mutate(bad)
    bad_result = _run(script, bad)
    assert bad_result.returncode != 0, bad_result.stdout
    assert expected in bad_result.stdout

    restored = _copy_fixture(tmp_path / "restored", files)
    restored_result = _run(script, restored)
    assert restored_result.returncode == 0, restored_result.stdout


def _copy_p5_structural_fixture(tmp_path: Path) -> Path:
    fixture = tmp_path / "repo"
    manifest_path = "contracts-internal/governance/b23_p5_composite_proof.main.json"
    pytest_manifest_path = "contracts-internal/governance/b23_p5_pytest_suite.main.json"
    manifest = json.loads((REPO_ROOT / manifest_path).read_text(encoding="utf-8"))
    pytest_manifest = json.loads((REPO_ROOT / pytest_manifest_path).read_text(encoding="utf-8"))
    files = {
        manifest_path,
        pytest_manifest_path,
        ".github/workflows/ci.yml",
        manifest["p0_preservation"]["semantic_authority_contract"],
        manifest["branch_protection"]["verifier"],
        "scripts/ci/enforce_b23_p5_composite_proof.py",
    }
    for gate in manifest["required_phase_enforcers"]:
        files.add(gate["command"][1])
    for suite in manifest["required_pytest_suites"]:
        files.add(suite["path"])
    for entry in pytest_manifest["required_test_files"]:
        files.add(entry["path"])
    for relative in files:
        source = REPO_ROOT / relative
        target = fixture / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return fixture


def test_p1_remove_match_verdict_status_value_fails(tmp_path: Path) -> None:
    def mutate(root: Path) -> None:
        _replace(root / "db/schema/canonical_schema.sql", "'matched_confirmed'::character varying, ", "")
        _replace(
            root / "alembic/versions/007_skeldir_foundation/202604291200_b23_p1_schema_authority_lock.py",
            "                        'matched_confirmed',\n",
            "",
        )

    _assert_correct_then_mutated_fails(
        tmp_path,
        files=P1_FILES,
        script="scripts/ci/enforce_b23_p1_schema_authority_lock.py",
        mutate=mutate,
        expected="match_status_constraint_missing:matched_confirmed",
    )


def test_p1_remove_exception_resolution_code_constraint_fails(tmp_path: Path) -> None:
    def mutate(root: Path) -> None:
        _replace(
            root / "db/schema/canonical_schema.sql",
            "ck_b23_exception_records_resolution_code_required",
            "ck_b23_exception_records_resolution_code_removed",
        )

    _assert_correct_then_mutated_fails(
        tmp_path,
        files=P1_FILES,
        script="scripts/ci/enforce_b23_p1_schema_authority_lock.py",
        mutate=mutate,
        expected="named_constraint_missing:ck_b23_exception_records_resolution_code_required",
    )


def test_p1_remove_revenue_event_type_fails(tmp_path: Path) -> None:
    def mutate(root: Path) -> None:
        _replace(root / "db/schema/canonical_schema.sql", "'chargeback_lost'::character varying, ", "")
        _replace(
            root / "alembic/versions/007_skeldir_foundation/202604291200_b23_p1_schema_authority_lock.py",
            "                        'chargeback_lost',\n",
            "",
        )

    _assert_correct_then_mutated_fails(
        tmp_path,
        files=P1_FILES,
        script="scripts/ci/enforce_b23_p1_schema_authority_lock.py",
        mutate=mutate,
        expected="revenue_event_type_constraint_missing:chargeback_lost",
    )


def test_p2_add_unsupported_platform_without_extractor_fails(tmp_path: Path) -> None:
    def mutate(root: Path) -> None:
        contract = root / "contracts-internal/governance/b23_p2_match_engine_kernel.main.json"
        payload = json.loads(contract.read_text(encoding="utf-8"))
        payload["platform_keyed_extraction_registry"]["providers"].append("square")
        contract.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    _assert_correct_then_mutated_fails(
        tmp_path,
        files=P2_FILES,
        script="scripts/ci/enforce_b23_p2_match_engine_kernel.py",
        mutate=mutate,
        expected="extractor_registry_missing:square",
    )


def test_p2_change_stripe_extraction_to_net_amount_fails(tmp_path: Path) -> None:
    def mutate(root: Path) -> None:
        _replace(
            root / "backend/app/revenue_verification/extraction_registry.py",
            "amount_minor=int(payload.gross_captured_minor)",
            "amount_minor=int(payload.net_after_fees_minor)",
        )

    _assert_correct_then_mutated_fails(
        tmp_path,
        files=P2_FILES,
        script="scripts/ci/enforce_b23_p2_match_engine_kernel.py",
        mutate=mutate,
        expected="stripe_net_after_fees_used_as_canonical_amount",
    )


def test_p2_hardcode_arrival_window_literal_fails(tmp_path: Path) -> None:
    def mutate(root: Path) -> None:
        _replace(
            root / "backend/app/revenue_verification/match_engine_kernel.py",
            "conversion_to_event_delta <= WEBHOOK_ARRIVAL_WINDOW",
            "conversion_to_event_delta <= timedelta(minutes=30)",
        )

    _assert_correct_then_mutated_fails(
        tmp_path,
        files=P2_FILES,
        script="scripts/ci/enforce_b23_p2_match_engine_kernel.py",
        mutate=mutate,
        expected="kernel_hardcoded_arrival_window_literal_detected",
    )


def test_p2_arrival_guard_runtime_negative_control_is_manifested() -> None:
    manifest = json.loads((REPO_ROOT / "contracts-internal/governance/b23_p5_pytest_suite.main.json").read_text(encoding="utf-8"))
    p2_runtime = [
        entry for entry in manifest["required_test_files"]
        if entry["path"] == "backend/tests/test_b23_p2_match_engine_kernel.py"
    ][0]
    assert "arrival_window_guard" in p2_runtime["gate_classes"]


def test_p2_reachable_llm_call_from_match_path_fails(tmp_path: Path) -> None:
    def mutate(root: Path) -> None:
        path = root / "backend/app/revenue_verification/match_engine_kernel.py"
        text = path.read_text(encoding="utf-8")
        provider = "open" + "ai"
        text = text.replace(
            "from sqlalchemy import text\n",
            f"from sqlalchemy import text\nimport {provider}\n",
            1,
        )
        text = text.replace(
            "extracted = extract_revenue_from_typed_input(match_input.verified_revenue_input)",
            f"{provider}.res" + "ponses.create(model='gpt-4.1-mini', input='forbidden')\n"
            "    extracted = extract_revenue_from_typed_input(match_input.verified_revenue_input)",
            1,
        )
        path.write_text(text, encoding="utf-8")

    _assert_correct_then_mutated_fails(
        tmp_path,
        files=P2_FILES,
        script="scripts/ci/enforce_b23_p2_match_engine_kernel.py",
        mutate=mutate,
        expected="kernel_forbidden_token_present:import " + ("open" + "ai"),
    )


def test_p2_remove_refund_chargeback_handler_registration_fails(tmp_path: Path) -> None:
    def mutate(root: Path) -> None:
        _replace(root / "backend/app/revenue_verification/match_engine_kernel.py", '        "chargeback_lost",\n', "")

    _assert_correct_then_mutated_fails(
        tmp_path,
        files=P2_FILES,
        script="scripts/ci/enforce_b23_p2_match_engine_kernel.py",
        mutate=mutate,
        expected="post_capture_handler_coverage_missing:stripe:chargeback_lost",
    )


def test_p3_remove_transition_task_registration_fails(tmp_path: Path) -> None:
    def mutate(root: Path) -> None:
        _replace(
            root / "backend/app/tasks/revenue_verification.py",
            "app.tasks.revenue_verification.transition_stale_provisional_to_confirmed_all_tenants",
            "app.tasks.revenue_verification.transition_stale_provisional_removed",
        )

    _assert_correct_then_mutated_fails(
        tmp_path,
        files=P3_FILES,
        script="scripts/ci/enforce_b23_p3_verdict_persistence.py",
        mutate=mutate,
        expected="transition_task_missing:app.tasks.revenue_verification.transition_stale_provisional_to_confirmed_all_tenants",
    )


def test_p3_remove_flagged_alert_exception_creation_fails(tmp_path: Path) -> None:
    def mutate(root: Path) -> None:
        _replace_all(root / "backend/app/revenue_verification/match_engine_kernel.py", "reconcile_b23_attribution_exception_lifecycle", "exception_lifecycle_removed")

    _assert_correct_then_mutated_fails(
        tmp_path,
        files=P3_FILES,
        script="scripts/ci/enforce_b23_p3_verdict_persistence.py",
        mutate=mutate,
        expected="kernel_basis_token_missing:reconcile_b23_attribution_exception_lifecycle",
    )


def test_p3_collapse_provisional_confirmed_statuses_fails(tmp_path: Path) -> None:
    def mutate(root: Path) -> None:
        _replace_all(root / "frontend/src/types/api/reconciliation.ts", "matched_provisional", "matched")

    _assert_correct_then_mutated_fails(
        tmp_path,
        files=P3_FILES,
        script="scripts/ci/enforce_b23_p3_verdict_persistence.py",
        mutate=mutate,
        expected="frontend_status_enum_missing:matched_provisional",
    )


def test_p4_route_b23_task_to_default_queue_fails(tmp_path: Path) -> None:
    def mutate(root: Path) -> None:
        _replace(root / "backend/app/celery_app.py", "'queue': QUEUE_B23_MATCH_ENGINE", "'queue': 'default'")

    _assert_correct_then_mutated_fails(
        tmp_path,
        files=P4_FILES,
        script="scripts/ci/enforce_b23_p4_queue_performance.py",
        mutate=mutate,
        expected="b23_task_route_not_isolated",
    )


def test_p4_worker_consumes_llm_queue_fails(tmp_path: Path) -> None:
    def mutate(root: Path) -> None:
        _replace(root / "Procfile", "--queues=b23_match_engine", "--queues=b23_match_engine,llm")

    _assert_correct_then_mutated_fails(
        tmp_path,
        files=P4_FILES,
        script="scripts/ci/enforce_b23_p4_queue_performance.py",
        mutate=mutate,
        expected="b23_worker_forbidden_queue_overlap",
    )


def test_p4_remove_dedicated_db_pool_fails(tmp_path: Path) -> None:
    def mutate(root: Path) -> None:
        _replace_all(root / "backend/app/db/session.py", "b23_engine", "shared_engine_removed")

    _assert_correct_then_mutated_fails(
        tmp_path,
        files=P4_FILES,
        script="scripts/ci/enforce_b23_p4_queue_performance.py",
        mutate=mutate,
        expected="b23_db_pool_token_missing:b23_engine",
    )


def test_p4_benchmark_scope_fixture_insert_inside_timed_region_fails(tmp_path: Path) -> None:
    def mutate(root: Path) -> None:
        _replace(
            root / "backend/tests/test_b23_p4_queue_performance.py",
            "event.listen(b23_engine.sync_engine, \"before_cursor_execute\", count_statement)",
            "event.listen(b23_engine.sync_engine, \"before_cursor_execute\", count_statement)\n    await _seed_b23_p4_benchmark_data(tenant_a)",
        )

    _assert_correct_then_mutated_fails(
        tmp_path,
        files=P4_FILES,
        script="scripts/ci/enforce_b23_p4_queue_performance.py",
        mutate=mutate,
        expected="benchmark_seed_inside_timed_region",
    )


def test_p4_replace_microbatch_with_n_plus_one_loop_fails(tmp_path: Path) -> None:
    def mutate(root: Path) -> None:
        path = root / "backend/app/revenue_verification/batch_engine.py"
        path.write_text(path.read_text(encoding="utf-8") + "\n# regression sentinel: for match_input in rows\n", encoding="utf-8")

    _assert_correct_then_mutated_fails(
        tmp_path,
        files=P4_FILES,
        script="scripts/ci/enforce_b23_p4_queue_performance.py",
        mutate=mutate,
        expected="batch_forbidden_token_present:for match_input in",
    )


def test_p4_remove_telemetry_sql_index_fails(tmp_path: Path) -> None:
    def mutate(root: Path) -> None:
        _replace(root / "db/schema/canonical_schema.sql", "idx_b23_p4_match_rate_tenant_transition_status", "idx_b23_p4_match_rate_removed")

    _assert_correct_then_mutated_fails(
        tmp_path,
        files=P4_FILES,
        script="scripts/ci/enforce_b23_p4_queue_performance.py",
        mutate=mutate,
        expected="telemetry_index_missing:idx_b23_p4_match_rate_tenant_transition_status",
    )


def test_frontend_generated_type_drift_fails(tmp_path: Path) -> None:
    def mutate(root: Path) -> None:
        _replace_all(root / "frontend/src/types/api/reconciliation.ts", "matched_confirmed", "matched")

    _assert_correct_then_mutated_fails(
        tmp_path,
        files=P3_FILES,
        script="scripts/ci/enforce_b23_p3_verdict_persistence.py",
        mutate=mutate,
        expected="frontend_status_enum_missing:matched_confirmed",
    )


def test_manifest_required_runtime_proof_self_exemption_fails(tmp_path: Path) -> None:
    manifest = json.loads((REPO_ROOT / "contracts-internal/governance/b23_p5_composite_proof.main.json").read_text(encoding="utf-8"))
    manifest["skip_policy"]["exempt_from_skip_failure"] = ["p4_runtime_benchmark"]
    bad_manifest = tmp_path / "bad_manifest.json"
    summary = tmp_path / "summary.json"
    bad_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/ci/enforce_b23_p5_composite_proof.py"),
            "--manifest-file",
            str(bad_manifest),
            "--summary-file",
            str(summary),
            "--structural-only",
        ],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert result.returncode != 0, result.stdout
    assert "required_proof_self_exemption_forbidden:p4_runtime_benchmark" in result.stdout


def test_branch_protection_missing_composite_check_fails(tmp_path: Path) -> None:
    protection = {
        "required_status_checks": {
            "strict": True,
            "contexts": ["Contract Semantic Drift Gate"],
            "checks": [],
        }
    }
    fixture = tmp_path / "branch_protection.json"
    fixture.write_text(json.dumps(protection), encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/ci/verify_b23_p5_branch_protection.py"),
            "--branch-protection-response-file",
            str(fixture),
        ],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert result.returncode != 0, result.stdout
    assert "required_check_missing_from_branch_protection:B2.3 Composite Proof Harness" in result.stdout


def test_p0_contract_version_regression_fails(tmp_path: Path) -> None:
    fixture = _copy_p5_structural_fixture(tmp_path)
    p0_contract = fixture / "contracts-internal/governance/b23_p0_semantic_authority_freeze.main.json"
    payload = json.loads(p0_contract.read_text(encoding="utf-8"))
    payload["contract_version"] = "9.9.9"
    p0_contract.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/ci/enforce_b23_p5_composite_proof.py"),
            "--repo-root",
            str(fixture),
            "--structural-only",
        ],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert result.returncode != 0, result.stdout
    assert "p0_contract_version_regression:9.9.9!=1.2.0" in result.stdout
