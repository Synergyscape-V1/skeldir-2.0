from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ENFORCER = REPO_ROOT / "scripts" / "ci" / "enforce_b23_p1_schema_authority_lock.py"
CONTRACT = (
    REPO_ROOT
    / "contracts-internal"
    / "governance"
    / "b23_p1_schema_authority_lock.main.json"
)
BASE_MIGRATION = (
    REPO_ROOT
    / "alembic"
    / "versions"
    / "007_skeldir_foundation"
    / "202604291200_b23_p1_schema_authority_lock.py"
)
CORRECTIVE_MIGRATION = (
    REPO_ROOT
    / "alembic"
    / "versions"
    / "007_skeldir_foundation"
    / "202604301030_b23_p1_followup_lifecycle_operands.py"
)
CANONICAL_SCHEMA = REPO_ROOT / "db" / "schema" / "canonical_schema.sql"
TIMING_CONSTANTS = (
    REPO_ROOT / "backend" / "app" / "revenue_verification" / "timing_constants.py"
)
REVERSIBILITY_SCRIPT = (
    REPO_ROOT / "scripts" / "ci" / "verify_b23_p1_migration_reversibility.py"
)
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"

_SPEC = importlib.util.spec_from_file_location("b23_p1_enforcer_module", ENFORCER)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
run_enforcement = _MODULE.run_enforcement


def _replace_once(pattern: str, replacement: str, text: str) -> str:
    mutated, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    assert count == 1
    return mutated


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
        base_migration_file=BASE_MIGRATION,
        corrective_migration_file=CORRECTIVE_MIGRATION,
        canonical_schema_file=CANONICAL_SCHEMA,
        timing_constants_module=TIMING_CONSTANTS,
        reversibility_script_file=REVERSIBILITY_SCRIPT,
    )
    assert status == 0, f"unexpected violations: {violations}"


def test_b23_p1_schema_authority_enforcer_negative_control_forced_regression() -> None:
    result = _run("--simulate-regression")
    assert result.returncode != 0
    assert "synthetic_regression=forced_failure_path" in (result.stdout + result.stderr)


def test_negative_control_remove_lifecycle_requirements_section(tmp_path: Path) -> None:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    payload.pop("lifecycle_requirements")
    mutated = tmp_path / "contract.no_lifecycle.json"
    mutated.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    result = _run("--contract-file", str(mutated))
    assert result.returncode != 0
    assert "contract_missing_or_invalid_section:lifecycle_requirements" in (
        result.stdout + result.stderr
    )


def test_negative_control_comment_only_lifecycle_mechanism(tmp_path: Path) -> None:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    payload["lifecycle_requirements"]["mechanism"] = "comment_only_lifecycle"
    mutated = tmp_path / "contract.comment_only_lifecycle.json"
    mutated.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    result = _run("--contract-file", str(mutated))
    assert result.returncode != 0
    assert "lifecycle_mechanism_mismatch" in (result.stdout + result.stderr)


def test_negative_control_missing_one_table_lifecycle_spec(tmp_path: Path) -> None:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    payload["lifecycle_requirements"]["tables"].pop("b23_revenue_events")
    mutated = tmp_path / "contract.lifecycle_table_missing.json"
    mutated.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    result = _run("--contract-file", str(mutated))
    assert result.returncode != 0
    assert "lifecycle_table_spec_missing:b23_revenue_events" in (
        result.stdout + result.stderr
    )


def test_negative_control_external_worker_as_lifecycle_mechanism(
    tmp_path: Path,
) -> None:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    payload["lifecycle_requirements"]["mechanism"] = "external_worker_primary_cleanup"
    mutated = tmp_path / "contract.external_worker_lifecycle.json"
    mutated.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    result = _run("--contract-file", str(mutated))
    assert result.returncode != 0
    assert "lifecycle_mechanism_mismatch" in (result.stdout + result.stderr)


def test_negative_control_remove_financial_operand_requirements_section(
    tmp_path: Path,
) -> None:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    payload.pop("financial_operand_requirements")
    mutated = tmp_path / "contract.no_financial_operands.json"
    mutated.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    result = _run("--contract-file", str(mutated))
    assert result.returncode != 0
    assert "contract_missing_or_invalid_section:financial_operand_requirements" in (
        result.stdout + result.stderr
    )


def test_negative_control_reintroduce_generic_amount_minor(tmp_path: Path) -> None:
    mutated = tmp_path / "canonical.generic_amount_minor.sql"
    mutated.write_text(
        CANONICAL_SCHEMA.read_text(encoding="utf-8").replace(
            "CREATE TABLE public.b23_revenue_events (\n    id uuid DEFAULT gen_random_uuid() NOT NULL,",
            "CREATE TABLE public.b23_revenue_events (\n    id uuid DEFAULT gen_random_uuid() NOT NULL,\n    amount_minor integer NOT NULL,",
            1,
        ),
        encoding="utf-8",
    )
    result = _run("--canonical-schema-file", str(mutated))
    assert result.returncode != 0
    assert "revenue_event_forbidden_generic_money_column_present:amount_minor" in (
        result.stdout + result.stderr
    )


def test_negative_control_remove_event_type_operand_semantics_constraint(
    tmp_path: Path,
) -> None:
    mutated = tmp_path / "canonical.remove_operand_constraint.sql"
    mutated.write_text(
        CANONICAL_SCHEMA.read_text(encoding="utf-8").replace(
            "ck_b23_revenue_events_operand_columns_by_event_type",
            "ck_b23_revenue_events_operand_columns_by_event_type_removed",
            1,
        ),
        encoding="utf-8",
    )
    result = _run("--canonical-schema-file", str(mutated))
    assert result.returncode != 0
    assert (
        "revenue_event_operand_constraint_missing:ck_b23_revenue_events_operand_columns_by_event_type"
        in (result.stdout + result.stderr)
    )


def test_negative_control_remove_sign_convention_constraint(tmp_path: Path) -> None:
    mutated = tmp_path / "canonical.remove_sign_constraint.sql"
    mutated.write_text(
        CANONICAL_SCHEMA.read_text(encoding="utf-8").replace(
            "ck_b23_revenue_events_net_effect_sign",
            "ck_b23_revenue_events_net_effect_sign_removed",
            1,
        ),
        encoding="utf-8",
    )
    result = _run("--canonical-schema-file", str(mutated))
    assert result.returncode != 0
    assert (
        "revenue_event_operand_constraint_missing:ck_b23_revenue_events_net_effect_sign"
        in (result.stdout + result.stderr)
    )


def test_negative_control_remove_currency_binding(tmp_path: Path) -> None:
    mutated = tmp_path / "canonical.remove_currency.sql"
    mutated.write_text(
        CANONICAL_SCHEMA.read_text(encoding="utf-8").replace(
            "currency_code character(3) NOT NULL,",
            "currency_code_removed character(3) NOT NULL,",
            1,
        ),
        encoding="utf-8",
    )
    result = _run("--canonical-schema-file", str(mutated))
    assert result.returncode != 0
    assert "revenue_event_currency_binding_missing" in (
        result.stdout + result.stderr
    ) or "match_verdict_currency_binding_missing" in (result.stdout + result.stderr)


def test_negative_control_omit_match_verdict_expected_gross_operand(
    tmp_path: Path,
) -> None:
    mutated = tmp_path / "canonical.remove_expected_gross.sql"
    mutated.write_text(
        _replace_once(
            r"^\s+canonical_expected_gross_amount_minor integer\b",
            "    canonical_expected_gross_amount_minor_removed integer",
            CANONICAL_SCHEMA.read_text(encoding="utf-8"),
        ),
        encoding="utf-8",
    )
    result = _run("--canonical-schema-file", str(mutated))
    assert result.returncode != 0
    assert (
        "match_verdict_operand_column_missing:canonical_expected_gross_amount_minor"
        in (result.stdout + result.stderr)
    )


def test_negative_control_omit_match_verdict_captured_gross_operand(
    tmp_path: Path,
) -> None:
    mutated = tmp_path / "canonical.remove_captured_gross.sql"
    mutated.write_text(
        _replace_once(
            r"^\s+canonical_captured_gross_amount_minor integer\b",
            "    canonical_captured_gross_amount_minor_removed integer",
            CANONICAL_SCHEMA.read_text(encoding="utf-8"),
        ),
        encoding="utf-8",
    )
    result = _run("--canonical-schema-file", str(mutated))
    assert result.returncode != 0
    assert (
        "match_verdict_operand_column_missing:canonical_captured_gross_amount_minor"
        in (result.stdout + result.stderr)
    )


def test_negative_control_omit_match_verdict_net_verified_operand(
    tmp_path: Path,
) -> None:
    mutated = tmp_path / "canonical.remove_net_verified.sql"
    mutated.write_text(
        CANONICAL_SCHEMA.read_text(encoding="utf-8").replace(
            "canonical_net_verified_amount_minor integer NOT NULL,",
            "canonical_net_verified_amount_minor_removed integer NOT NULL,",
            1,
        ),
        encoding="utf-8",
    )
    result = _run("--canonical-schema-file", str(mutated))
    assert result.returncode != 0
    assert (
        "match_verdict_operand_column_missing:canonical_net_verified_amount_minor"
        in (result.stdout + result.stderr)
    )


def test_negative_control_omit_discrepancy_amount(tmp_path: Path) -> None:
    mutated = tmp_path / "canonical.remove_discrepancy_amount.sql"
    mutated.write_text(
        CANONICAL_SCHEMA.read_text(encoding="utf-8").replace(
            "discrepancy_amount_minor integer NOT NULL,",
            "discrepancy_amount_minor_removed integer NOT NULL,",
            1,
        ),
        encoding="utf-8",
    )
    result = _run("--canonical-schema-file", str(mutated))
    assert result.returncode != 0
    assert "discrepancy_column_missing:discrepancy_amount_minor" in (
        result.stdout + result.stderr
    )


def test_negative_control_omit_discrepancy_ratio(tmp_path: Path) -> None:
    mutated = tmp_path / "canonical.remove_discrepancy_ratio.sql"
    mutated.write_text(
        CANONICAL_SCHEMA.read_text(encoding="utf-8").replace(
            "discrepancy_ratio_bps integer NOT NULL,",
            "discrepancy_ratio_bps_removed integer NOT NULL,",
            1,
        ),
        encoding="utf-8",
    )
    result = _run("--canonical-schema-file", str(mutated))
    assert result.returncode != 0
    assert "discrepancy_column_missing:discrepancy_ratio_bps" in (
        result.stdout + result.stderr
    )


def test_negative_control_remove_discrepancy_index(tmp_path: Path) -> None:
    mutated = tmp_path / "canonical.remove_discrepancy_index.sql"
    mutated.write_text(
        CANONICAL_SCHEMA.read_text(encoding="utf-8").replace(
            "CREATE INDEX idx_b23_match_verdicts_tenant_discrepancy_ratio_bps",
            "CREATE INDEX idx_b23_match_verdicts_tenant_discrepancy_ratio_bps_removed",
            1,
        ),
        encoding="utf-8",
    )
    result = _run("--canonical-schema-file", str(mutated))
    assert result.returncode != 0
    assert (
        "discrepancy_index_missing:idx_b23_match_verdicts_tenant_discrepancy_ratio_bps"
        in (result.stdout + result.stderr)
    )


def test_negative_control_omit_p2_write_surface_destination(tmp_path: Path) -> None:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    payload["p2_write_surface_requirements"]["discrepancy_ratio_bps"][
        "destination"
    ] = ""
    mutated = tmp_path / "contract.p2_destination_missing.json"
    mutated.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    result = _run("--contract-file", str(mutated))
    assert result.returncode != 0
    assert "p2_write_surface_destination_invalid:discrepancy_ratio_bps" in (
        result.stdout + result.stderr
    )


def test_negative_control_invalid_p2_write_surface_classification(
    tmp_path: Path,
) -> None:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    payload["p2_write_surface_requirements"]["discrepancy_amount_minor"][
        "classification"
    ] = "requires_new_migration"
    mutated = tmp_path / "contract.p2_classification_invalid.json"
    mutated.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    result = _run("--contract-file", str(mutated))
    assert result.returncode != 0
    assert (
        "p2_write_surface_classification_invalid:discrepancy_amount_minor:requires_new_migration"
        in (result.stdout + result.stderr)
    )


def test_negative_control_remove_named_check_constraint(tmp_path: Path) -> None:
    mutated = tmp_path / "canonical.remove_named_check.sql"
    mutated.write_text(
        CANONICAL_SCHEMA.read_text(encoding="utf-8").replace(
            "ck_b23_match_verdicts_discrepancy_ratio_consistency",
            "ck_b23_match_verdicts_discrepancy_ratio_consistency_removed",
            1,
        ),
        encoding="utf-8",
    )
    result = _run("--canonical-schema-file", str(mutated))
    assert result.returncode != 0
    assert (
        "named_constraint_missing:ck_b23_match_verdicts_discrepancy_ratio_consistency"
        in (result.stdout + result.stderr)
    )


def test_negative_control_remove_named_index(tmp_path: Path) -> None:
    mutated = tmp_path / "canonical.remove_named_index.sql"
    mutated.write_text(
        _replace_once(
            r"^CREATE INDEX idx_b23_revenue_events_tenant_event_effect_sign\b",
            "CREATE INDEX idx_b23_revenue_events_tenant_event_effect_sign_removed",
            CANONICAL_SCHEMA.read_text(encoding="utf-8"),
        ),
        encoding="utf-8",
    )
    result = _run("--canonical-schema-file", str(mutated))
    assert result.returncode != 0
    assert "named_index_missing:idx_b23_revenue_events_tenant_event_effect_sign" in (
        result.stdout + result.stderr
    )


def test_negative_control_remove_named_policy(tmp_path: Path) -> None:
    mutated = tmp_path / "canonical.remove_named_policy.sql"
    mutated.write_text(
        _replace_once(
            r"^CREATE POLICY tenant_isolation_policy_b23_revenue_events\b",
            "CREATE POLICY tenant_isolation_policy_b23_revenue_events_removed",
            CANONICAL_SCHEMA.read_text(encoding="utf-8"),
        ),
        encoding="utf-8",
    )
    result = _run("--canonical-schema-file", str(mutated))
    assert result.returncode != 0
    assert "named_policy_missing:tenant_isolation_policy_b23_revenue_events" in (
        result.stdout + result.stderr
    )


def test_negative_control_remove_named_lifecycle_job(tmp_path: Path) -> None:
    mutated = tmp_path / "migration.remove_lifecycle_job.py"
    mutated.write_text(
        CORRECTIVE_MIGRATION.read_text(encoding="utf-8").replace(
            "b23_p1_apply_lifecycle_daily",
            "b23_p1_apply_lifecycle_daily_removed",
            20,
        ),
        encoding="utf-8",
    )
    result = _run("--corrective-migration-file", str(mutated))
    assert result.returncode != 0
    assert "named_job_missing:b23_p1_apply_lifecycle_daily" in (
        result.stdout + result.stderr
    )


def test_negative_control_regress_existing_p1_match_quality_constraint(
    tmp_path: Path,
) -> None:
    mutated = tmp_path / "migration.remove_match_quality.py"
    mutated.write_text(
        BASE_MIGRATION.read_text(encoding="utf-8").replace(
            "CONSTRAINT ck_b23_match_verdicts_match_quality",
            "CONSTRAINT ck_b23_match_verdicts_match_quality_removed",
            1,
        ),
        encoding="utf-8",
    )
    result = _run("--base-migration-file", str(mutated))
    assert result.returncode != 0
    assert "base_migration_missing_match_quality_constraint" in (
        result.stdout + result.stderr
    )
