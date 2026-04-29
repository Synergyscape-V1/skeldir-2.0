from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ENFORCER = REPO_ROOT / "scripts" / "ci" / "enforce_b23_p1_schema_authority_lock.py"
CONTRACT = REPO_ROOT / "contracts-internal" / "governance" / "b23_p1_schema_authority_lock.main.json"
MIGRATION = (
    REPO_ROOT
    / "alembic"
    / "versions"
    / "007_skeldir_foundation"
    / "202604291200_b23_p1_schema_authority_lock.py"
)
CANONICAL_SCHEMA = REPO_ROOT / "db" / "schema" / "canonical_schema.sql"
TIMING_CONSTANTS = REPO_ROOT / "backend" / "app" / "revenue_verification" / "timing_constants.py"
REVERSIBILITY_SCRIPT = REPO_ROOT / "scripts" / "ci" / "verify_b23_p1_migration_reversibility.py"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"

_SPEC = importlib.util.spec_from_file_location("b23_p1_enforcer_module", ENFORCER)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
run_enforcement = _MODULE.run_enforcement


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ENFORCER), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_b23_p1_schema_authority_enforcer_passes_repo_state() -> None:
    status, violations = run_enforcement(
        repo_root=REPO_ROOT,
        contract_file=CONTRACT,
        ci_workflow_file=CI_WORKFLOW,
        migration_file=MIGRATION,
        canonical_schema_file=CANONICAL_SCHEMA,
        timing_constants_module=TIMING_CONSTANTS,
        reversibility_script_file=REVERSIBILITY_SCRIPT,
    )
    assert status == 0, f"unexpected violations: {violations}"


def test_b23_p1_schema_authority_enforcer_negative_control_forced_regression() -> None:
    result = _run("--simulate-regression")
    assert result.returncode != 0
    assert "synthetic_regression=forced_failure_path" in (result.stdout + result.stderr)


def test_negative_control_remove_one_match_status(tmp_path: Path) -> None:
    mutated = tmp_path / "migration.remove_status.py"
    mutated.write_text(
        MIGRATION.read_text(encoding="utf-8").replace(
            "'adjusted',",
            "",
            1,
        ),
        encoding="utf-8",
    )
    result = _run("--migration-file", str(mutated))
    assert result.returncode != 0
    assert "match_status_constraint_missing:adjusted" in (result.stdout + result.stderr)


def test_negative_control_add_undocumented_match_status(tmp_path: Path) -> None:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    payload["match_verdict"]["statuses"].append("matched_shadow")
    mutated = tmp_path / "contract.extra_status.json"
    mutated.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    result = _run("--contract-file", str(mutated))
    assert result.returncode != 0
    assert "match_status_constraint_missing:matched_shadow" in (result.stdout + result.stderr)


def test_negative_control_remove_match_quality_constraint(tmp_path: Path) -> None:
    mutated = tmp_path / "migration.remove_quality.py"
    mutated.write_text(
        MIGRATION.read_text(encoding="utf-8").replace(
            "CONSTRAINT ck_b23_match_verdicts_match_quality",
            "CONSTRAINT ck_b23_match_verdicts_match_quality_removed",
            1,
        ),
        encoding="utf-8",
    )
    result = _run("--migration-file", str(mutated))
    assert result.returncode != 0
    assert "migration_missing_match_quality_constraint" in (result.stdout + result.stderr)


def test_negative_control_remove_reversal_event(tmp_path: Path) -> None:
    mutated = tmp_path / "migration.remove_reversal.py"
    mutated.write_text(
        MIGRATION.read_text(encoding="utf-8").replace(
            "'reversal'",
            "'reversal_removed'",
            1,
        ),
        encoding="utf-8",
    )
    result = _run("--migration-file", str(mutated))
    assert result.returncode != 0
    assert "revenue_event_type_constraint_missing:reversal" in (result.stdout + result.stderr)


def test_negative_control_missing_webhook_ingestion_column(tmp_path: Path) -> None:
    mutated = tmp_path / "migration.remove_webhook_column.py"
    mutated.write_text(
        MIGRATION.read_text(encoding="utf-8").replace(
            "failure_reason text NULL,",
            "failure_reason_removed text NULL,",
            1,
        ),
        encoding="utf-8",
    )
    result = _run("--migration-file", str(mutated))
    assert result.returncode != 0
    assert "migration_missing_webhook_log_column:failure_reason" in (result.stdout + result.stderr)


def test_negative_control_timing_constant_value_mismatch(tmp_path: Path) -> None:
    mutated = tmp_path / "timing_constants.regression.py"
    mutated.write_text(
        TIMING_CONSTANTS.read_text(encoding="utf-8").replace(
            "timedelta(days=30)",
            "timedelta(days=31)",
            1,
        ),
        encoding="utf-8",
    )
    result = _run("--timing-constants-module", str(mutated))
    assert result.returncode != 0
    assert "timing_constant_value_mismatch:REFUND_REOPENING_WINDOW" in (
        result.stdout + result.stderr
    )


def test_negative_control_canonical_schema_omits_p1_table(tmp_path: Path) -> None:
    mutated = tmp_path / "canonical_schema.regression.sql"
    mutated.write_text(
        CANONICAL_SCHEMA.read_text(encoding="utf-8").replace(
            "CREATE TABLE public.b23_revenue_events (",
            "CREATE TABLE public.b23_revenue_events_removed (",
            1,
        ),
        encoding="utf-8",
    )
    result = _run("--canonical-schema-file", str(mutated))
    assert result.returncode != 0
    assert "canonical_schema_missing_table_token:CREATE TABLE public.b23_revenue_events (" in (
        result.stdout + result.stderr
    )


def test_negative_control_missing_rls_policy(tmp_path: Path) -> None:
    mutated = tmp_path / "migration.rls_policy.regression.py"
    mutated.write_text(
        MIGRATION.read_text(encoding="utf-8").replace(
            "tenant_isolation_policy_b23_revenue_events",
            "tenant_isolation_policy_b23_revenue_events_removed",
            10,
        ),
        encoding="utf-8",
    )
    result = _run("--migration-file", str(mutated))
    assert result.returncode != 0
    assert "migration_missing_rls_policy:tenant_isolation_policy_b23_revenue_events" in (
        result.stdout + result.stderr
    )
