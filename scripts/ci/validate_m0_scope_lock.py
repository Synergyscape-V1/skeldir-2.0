#!/usr/bin/env python3
"""Policy-as-code validator for the M0 maintainability scope lock.

The validator intentionally stays narrow: it proves that M0 governance
artifacts are present, internally consistent, stale blocked-state language is
absent, branch-protection evidence is recorded, and the corrective diff does
not implement B2.4 or reopen prohibited B2.3/provider-boundary surfaces.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

M0_BASELINE_PATH = REPO_ROOT / "docs" / "maintainability" / "m0_baseline.md"
M0_SCOPE_LOCK_PATH = REPO_ROOT / "docs" / "maintainability" / "m0_scope_lock.md"
M0_ISSUE_REGISTER_PATH = (
    REPO_ROOT / "docs" / "maintainability" / "maintainability_issue_register.yaml"
)
M0_COMPLETION_RECORD_PATH = (
    REPO_ROOT / "docs" / "maintainability" / "m0_completion_record.md"
)
CODEOWNERS_PATH = REPO_ROOT / ".github" / "CODEOWNERS"

CANONICAL_ARTIFACT = "docs/maintainability/m0_completion_record.md"
M0_JOB_NAME = "m0-maintainability-scope-lock"

REQUIRED_ARTIFACTS = [
    M0_BASELINE_PATH,
    M0_SCOPE_LOCK_PATH,
    M0_ISSUE_REGISTER_PATH,
    M0_COMPLETION_RECORD_PATH,
]

REQUIRED_BASELINE_FIELDS = [
    "primary branch",
    "primary branch head",
    "remote",
    "m0 baseline sha",
    "m0 ci workflow",
    "m0 ci job name",
    "required for merge",
    "final clean-state confirmation",
    "b2.4 implementation is unauthorized",
    "post-b2.3 and pre-b2.4",
    "b2.3 semantics are closed",
]

REQUIRED_SCOPE_LOCK_PHRASES = [
    "b2.4 implementation prohibition",
    "b2.3 semantic reopening prohibition",
    "provider-boundary behavior-change prohibition",
    "broad ci refactor prohibition",
    CANONICAL_ARTIFACT,
    "required ci status",
    M0_JOB_NAME,
]

REQUIRED_SOURCES = {"Nicholas", "Trey", "George", "Synthesized"}

REQUIRED_CATEGORIES = {
    "local_development",
    "stale_documentation",
    "ci_sprawl",
    "ci_enforcement_insertion_risk",
    "hardcoded_external_db",
    "db_topology",
    "append_only_test_isolation",
    "ops_runbooks",
    "b24_substrate",
    "llm_provider_boundary",
    "repo_hygiene",
    "dependency_drift",
    "m0_policy_enforcement",
}

REQUIRED_ISSUE_FIELDS = [
    "id",
    "source",
    "title",
    "evidence",
    "severity",
    "phase_disposition",
    "b24_entry_blocking",
    "affected_substrate",
    "rationale",
    "owner_phase",
    "deferred_reason",
    "validation_expectation",
]

REQUIRED_REPORT_PHRASES = [
    "final verdict: m0_pass",
    "required for main: yes",
    "required status context: m0-maintainability-scope-lock",
    "branch protection evidence",
    "fresh checkout git status --short",
    "clean",
    "canonical completion artifact",
    CANONICAL_ARTIFACT,
    "validator governance protection",
    "no b2.4 implementation occurred",
    "no b2.3 semantic modules changed",
    "no provider-boundary behavior changed",
]

REQUIRED_CODEOWNER_PATHS = [
    "scripts/ci/validate_m0_scope_lock.py",
    ".github/workflows/m0-maintainability-scope-lock.yml",
    "contracts-internal/governance/b03_phase2_required_status_checks.main.json",
    "docs/maintainability/m0_scope_lock.md",
    "docs/maintainability/maintainability_issue_register.yaml",
]

B24_DEPENDENCY_PATTERNS = [
    r"pymc",
    r"pymc-marketing",
    r"pymc_marketing",
    r"arviz",
]

B24_CODE_PATTERNS = [
    r"pm\.Model",
    r"pm\.sample",
    r"az\.rhat",
    r"az\.ess\b",
    r"az\.summary",
]

PROHIBITED_SURFACE_PATTERNS = [
    r"provider_boundary\.py$",
    r"match_engine_kernel\.py$",
    r"semantic_authority\.py$",
    r"state_transitions\.py$",
    r"extraction_registry\.py$",
    r"batch_engine\.py$",
    r"(^|/)migrations?(/|$)",
    r"requirements.*\.txt$",
    r"pyproject\.toml$",
    r"setup\.(py|cfg)$",
    r"Pipfile$",
]

ALLOWED_M0_PATHS = [
    "docs/maintainability/",
    "docs/testing.md",
    "docs/testing_db_topology.md",
    "docs/testing_append_only_isolation.md",
    "docs/testing_celery_modes.md",
    "docs/testing_topology_url_authority.md",
    "docs/testing_b24_persistence_readiness.md",
    "docs/testing_b24_persistence_entry_gate.md",
    "docs/testing_parallel_isolation.md",
    "docs/b2_4/",
    "docs/b2_7/",
    "docs/llm/",
    "M2 Remediation Evidence Pack.md",
    "scripts/ci/validate_m0_scope_lock.py",
    "scripts/ci/validate_m1_local_dev_authority.py",
    "scripts/ci/run_m1_onboarding_bootstrap.sh",
    "scripts/ci/validate_m2_test_feedback_loop.py",
    "scripts/ci/run_m2_test_feedback_loop.sh",
    "scripts/ci/validate_m3_ci_governance.py",
    "scripts/ci/validate_m4_ops_runbooks.py",
    "scripts/ci/validate_m5_b24_readiness_design.py",
    "scripts/ci/validate_m6_llm_boundary.py",
    "scripts/ci/validate_m7_b24_readiness.py",
    "scripts/ci/run_ci_governance_cohort.py",
    "scripts/phase_gates/generate_value_trace_proof_pack.py",
    "scripts/smoke/",
    "scripts/ops/",
    "scripts/testing/",
    ".github/workflows/m0-maintainability-scope-lock.yml",
    ".github/workflows/m1-local-dev-authority.yml",
    ".github/workflows/m2-test-feedback-loop.yml",
    ".github/workflows/m3-ci-governance.yml",
    ".github/workflows/m4-operational-runbooks.yml",
    ".github/workflows/b2_4-gate-dry-run.yml",
    ".github/workflows/ci.yml",
    ".github/workflows/r2-data-truth-hardening.yml",
    ".github/actions/setup-postgres-ci/",
    "alembic/versions/007_skeldir_foundation/202605201200_b24_p1_authority_schema.py",
    "alembic/versions/007_skeldir_foundation/202605201430_b24_p1_corrective_authority_closure.py",
    "alembic/versions/007_skeldir_foundation/202605211200_b24_p1_partitioned_authority_schema.py",
    "alembic/versions/007_skeldir_foundation/202605211430_b24_p2_sparse_fallback_reasons.py",
    "alembic/versions/007_skeldir_foundation/202605221200_b24_p2_source_stream_safety_indexes.py",
    "alembic/versions/007_skeldir_foundation/202605221430_b24_p3_fit_planning_outbox.py",
    "alembic/versions/007_skeldir_foundation/202605231200_b24_p4_resource_bounds.py",
    "alembic/versions/007_skeldir_foundation/202605241200_b24_p4_feature_cardinality_indexes.py",
    "alembic/versions/007_skeldir_foundation/202605241430_b24_p4_cardinality_early_stop_indexes.py",
    "alembic/versions/007_skeldir_foundation/202605251200_b24_p4_feature_authority.py",
    "alembic/versions/007_skeldir_foundation/202605251430_b24_p4_authority_liveness.py",
    "alembic/versions/007_skeldir_foundation/202605251800_b24_p4_supersession_profiling_lease.py",
    "backend/app/bayesian/",
    "backend/app/ingestion/event_service.py",
    "backend/app/models/__init__.py",
    "backend/app/revenue_verification/batch_engine.py",
    "backend/app/tasks/attribution.py",
    "backend/app/tasks/bayesian.py",
    "docs/ci/",
    "docs/ops/",
    "docs/forensics/INDEX.md",
    "docs/forensics/B2.4-P Remediation Evidence Pack .md",
    "docs/forensics/B2.4-P1 Remediation Evidence Pack .md",
    "docs/forensics/B2.4-P1_Authority_Corrective_Closure_Report.md",
    "docs/forensics/B2.4-P1_Partitioned_Authority_Schema_Corrective_Report.md",
    "docs/forensics/B2.4-P1_Authority_Schema_RLS_Module_Transition_Completion_Report.md",
    "docs/forensics/B2.4-P2_Deterministic_Input_Contract_Source_Snapshot_Completion_Report.md",
    "docs/forensics/B2.4-P2_Source_Safety_and_Sparse_Privacy_Corrective_Report.md",
    "docs/forensics/B2.4-P3_Fit_Planning_Debounced_Atomic_Claim_Dispatch_Outbox_Completion_Report.md",
    "docs/forensics/B2.4-P4_Input_Cardinality_Memory_Graph_Envelope_PreGraph_Resource_Controls_Completion_Report.md",
    "docs/forensics/B2.4-P4_Live_Feature_Cardinality_Graph_Envelope_Corrective_Report.md",
    "docs/forensics/B2.4-P4_Bounded_Cardinality_DB_Work_Corrective_Report.md",
    "docs/forensics/B2.4-P4_Source_Window_Feature_Authority_Corrective_Report.md",
    "docs/forensics/B2.4-P4_Authority_Transient_Yield_Reactivation_Corrective_Report.md",
    "docs/forensics/B2.4-P4_Snapshot_Supersession_Build_Dispatch_Profiling_Lease_Corrective_Report.md",
    "docs/forensics/M3 Remediation Evidence Pack .md",
    "docs/forensics/M5 Remediation Evidence Pack .md",
    "db/schema/canonical_schema.sql",
    "db/schema/canonical_schema.yaml",
    "scripts/ci/validate_b24_p1_authority_schema.py",
    "scripts/ci/validate_b24_p2_source_snapshot.py",
    "scripts/ci/validate_b24_p3_fit_planning.py",
    "scripts/ci/validate_b24_p4_resource_bounds.py",
    "scripts/ci/phase2_schema_closure_gate.py",
    "scripts/schema/assert_canonical_schema.py",
    "M4 Remediation Evidence Pack.md",
    "M4.1_Remediation_Completion_Record.md",
    ".github/workflows/r7-final-winning-state.yml",
    "scripts/r3/ingestion_under_fire.py",
    "contracts-internal/governance/b03_phase2_required_status_checks.main.json",
    "contracts/internal/",
    ".github/CODEOWNERS",
    "DEVELOPMENT.md",
    "README.md",
    "backend/README.md",
    "backend/Dockerfile",
    ".env.example",
    ".env.local.example",
    "docker-compose.local.yml",
    "docker-compose.test.yml",
    "contracts-internal/governance/main_branch_protection_integrity.main.json",
    "Makefile",
    "pytest.ini",
    "backend/app/db/session.py",
    "backend/app/tasks/enqueue.py",
    "backend/app/tasks/observability_test.py",
    "backend/apply_pii_trigger_fix.py",
    "backend/check_channels.py",
    "backend/check_revenue_ledger.py",
    "backend/check_role_rls_bypass.py",
    "backend/check_tenants_schema.py",
    "backend/check_trigger.py",
    "backend/investigate_pii_trigger.py",
    "backend/run_tests_with_trigger_fix.py",
    "backend/test_rls_context.py",
    "backend/test_rls_direct.py",
    "backend/validate_b042.py",
    "backend/validate_schema_simple.py",
    "backend/verify_rls_config.py",
    "backend/tests/",
    "tests/",
    "scripts/guard_no_docker.py",
]


class ValidationResult:
    """Collect pass/fail results for all checks."""

    def __init__(self) -> None:
        self.checks: list[tuple[str, bool, str]] = []

    def add(self, name: str, passed: bool, detail: str = "") -> None:
        self.checks.append((name, passed, detail))

    def passed(self) -> bool:
        return all(ok for _, ok, _ in self.checks)

    def report(self) -> str:
        lines = []
        for name, ok, detail in self.checks:
            status = "PASS" if ok else "FAIL"
            line = f"  [{status}] {name}"
            if detail:
                line += f" - {detail}"
            lines.append(line)
        total = len(self.checks)
        passed = sum(1 for _, ok, _ in self.checks if ok)
        lines.append("")
        lines.append(f"  Total: {total} | Passed: {passed} | Failed: {total - passed}")
        return "\n".join(lines)


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _read_lower(path: Path) -> str:
    return _read_text(path).lower()


def _git(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=timeout,
    )


def _git_diff_names(baseline_sha: str) -> list[str]:
    result = _git(["diff", "--name-only", f"{baseline_sha}...HEAD"])
    if result.returncode != 0:
        result = _git(["diff", "--name-only", baseline_sha, "HEAD"])
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _git_diff_content(baseline_sha: str) -> str:
    result = _git(["diff", f"{baseline_sha}...HEAD"], timeout=60)
    if result.returncode != 0:
        result = _git(["diff", baseline_sha, "HEAD"], timeout=60)
    return result.stdout


def _extract_baseline_sha_from_artifact() -> str | None:
    match = re.search(r"M0_BASELINE_SHA=([a-f0-9]{40})", _read_text(M0_BASELINE_PATH))
    return match.group(1) if match else None


def _is_governance_path(filepath: str) -> bool:
    return any(filepath.startswith(allowed) for allowed in ALLOWED_M0_PATHS)


def _filter_diff_exclude_governance(diff_content: str) -> str:
    filtered_lines: list[str] = []
    in_governance_file = False

    for line in diff_content.splitlines():
        if line.startswith("diff --git "):
            parts = line.split(" b/")
            filepath = parts[-1] if len(parts) >= 2 else ""
            in_governance_file = _is_governance_path(filepath)
        if not in_governance_file:
            filtered_lines.append(line)

    return "\n".join(filtered_lines)


def check_artifacts_exist(result: ValidationResult) -> None:
    for path in REQUIRED_ARTIFACTS:
        exists = path.exists() and path.stat().st_size > 0
        result.add(
            f"Artifact exists: {path.relative_to(REPO_ROOT)}",
            exists,
        )


def check_baseline_fields(result: ValidationResult) -> None:
    content = _read_lower(M0_BASELINE_PATH)
    if not content:
        result.add("Baseline readable", False, "m0_baseline.md is missing or empty")
        return

    for field in REQUIRED_BASELINE_FIELDS:
        result.add(f"Baseline field: {field}", field in content)

    stale_markers = [
        "**status:** pending",
        "pending admin action",
    ]
    stale_clean_state = re.search(
        r"final clean-state confirmation\s*:?\s*(?:\*\*status:\*\*\s*)?pending",
        content,
    )
    result.add(
        "Baseline has no stale pending/admin language",
        stale_clean_state is None
        and not any(marker in content for marker in stale_markers),
    )
    result.add(
        "Baseline references canonical validation artifact",
        CANONICAL_ARTIFACT in content,
    )


def check_scope_lock_prohibitions(result: ValidationResult) -> None:
    content = _read_lower(M0_SCOPE_LOCK_PATH)
    if not content:
        result.add("Scope lock readable", False, "m0_scope_lock.md is missing or empty")
        return

    for phrase in REQUIRED_SCOPE_LOCK_PHRASES:
        result.add(f"Scope lock contains: {phrase}", phrase.lower() in content)


def check_canonical_artifact_consistency(result: ValidationResult) -> None:
    baseline = _read_lower(M0_BASELINE_PATH)
    scope_lock = _read_lower(M0_SCOPE_LOCK_PATH)
    completion_record = _read_lower(M0_COMPLETION_RECORD_PATH)

    result.add(
        "Canonical completion artifact is required", M0_COMPLETION_RECORD_PATH.exists()
    )
    result.add(
        "Baseline uses canonical completion path", CANONICAL_ARTIFACT in baseline
    )
    result.add(
        "Scope lock uses canonical completion path", CANONICAL_ARTIFACT in scope_lock
    )
    result.add(
        "Completion record self-identifies canonical path",
        CANONICAL_ARTIFACT in completion_record,
    )
    result.add(
        "Completion record claims canonical status",
        "canonical completion artifact" in completion_record
        and "m0_completion_record.md" in completion_record,
    )


def check_validation_report(result: ValidationResult) -> None:
    content = _read_lower(M0_COMPLETION_RECORD_PATH)
    if not content:
        result.add(
            "Completion record readable",
            False,
            "canonical artifact is missing or empty",
        )
        return

    for phrase in REQUIRED_REPORT_PHRASES:
        result.add(f"Completion record contains: {phrase}", phrase in content)

    blocked_verdicts = [
        "m0_blocked_by_unenforced_validator",
        "m0_blocked_by_artifact_inconsistency",
        "m0_blocked_by_incomplete_clean_baseline_evidence",
        "m0_blocked_by_validator_staleness_gap",
        "m0_blocked_by_validator_governance_bypass",
        "m0_blocked_by_feature_contamination",
        "m0_blocked_by_primary_branch_not_green",
    ]
    result.add(
        "Completion record has no blocked final verdict",
        not any(verdict in content for verdict in blocked_verdicts),
    )


def check_codeowners(result: ValidationResult) -> None:
    content = _read_text(CODEOWNERS_PATH)
    if not content:
        result.add("CODEOWNERS present", False, ".github/CODEOWNERS is missing")
        return

    for path in REQUIRED_CODEOWNER_PATHS:
        result.add(f"CODEOWNERS protects {path}", path in content)


def check_issue_register(result: ValidationResult) -> None:
    content = _read_text(M0_ISSUE_REGISTER_PATH)
    if not content:
        result.add(
            "Issue register readable", False, "issue register is missing or empty"
        )
        return

    for source in REQUIRED_SOURCES:
        result.add(
            f"Issue register covers source: {source}", f"source: {source}" in content
        )

    for category in REQUIRED_CATEGORIES:
        result.add(
            f"Issue register covers category: {category}",
            f"affected_substrate: {category}" in content,
        )

    result.add(
        "Issue register has B2.4-entry blockers", "b24_entry_blocking: true" in content
    )

    null_deferred_reasons = 0
    for issue_block in content.split("  - id:")[1:]:
        if "phase_disposition: deferred" in issue_block:
            if (
                "deferred_reason: null" in issue_block
                or "deferred_reason:" not in issue_block
            ):
                null_deferred_reasons += 1
    result.add(
        "Deferred issues have reasons",
        null_deferred_reasons == 0,
        (
            f"{null_deferred_reasons} deferred issues lack reasons"
            if null_deferred_reasons
            else ""
        ),
    )

    for field in REQUIRED_ISSUE_FIELDS:
        result.add(f"Issue register field present: {field}", f"{field}:" in content)

    result.add(
        "MIR-032 expects required CI status check",
        M0_JOB_NAME in content and "required CI status check" in content,
    )


def _added_lines_for_dependency_files(diff_content: str) -> list[str]:
    added_lines: list[str] = []
    current_path = ""
    dependency_path_pattern = re.compile(
        r"(^|/)(requirements.*\.txt|pyproject\.toml|setup\.(py|cfg)|Pipfile)$",
        re.IGNORECASE,
    )
    for line in diff_content.splitlines():
        if line.startswith("diff --git "):
            marker = " b/"
            current_path = line.split(marker, 1)[1] if marker in line else ""
            continue
        if not current_path or not dependency_path_pattern.search(current_path):
            continue
        if line.startswith("+") and not line.startswith("+++"):
            added_lines.append(line)
    return added_lines


def check_b24_contamination_dependencies(
    result: ValidationResult, diff_content: str
) -> None:
    added_lines = _added_lines_for_dependency_files(diff_content)
    for pattern in B24_DEPENDENCY_PATTERNS:
        found = any(re.search(pattern, line.lower()) for line in added_lines)
        result.add(f"No B2.4 dependency addition: {pattern}", not found)


def check_b24_contamination_code(result: ValidationResult, diff_content: str) -> None:
    added_lines: list[str] = []
    current_path = ""
    for line in diff_content.splitlines():
        if line.startswith("diff --git "):
            marker = " b/"
            current_path = line.split(marker, 1)[1] if marker in line else ""
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue
        if (
            current_path.startswith("docs/")
            or current_path.startswith("scripts/ci/")
            or current_path.startswith("backend/tests/")
            or current_path.startswith("tests/")
        ):
            continue
        added_lines.append(line)
    for pattern in B24_CODE_PATTERNS:
        found = any(re.search(pattern, line) for line in added_lines)
        result.add(f"No B2.4 code pattern: {pattern}", not found)


def check_allowed_change_surface(
    result: ValidationResult, changed_files: list[str]
) -> None:
    violations = [
        filepath for filepath in changed_files if not _is_governance_path(filepath)
    ]
    result.add(
        "M0 changes within allowed surface",
        not violations,
        f"Violations: {', '.join(violations[:5])}" if violations else "",
    )


def check_no_prohibited_surface_changes(
    result: ValidationResult, changed_files: list[str]
) -> None:
    violations = [
        filepath
        for filepath in changed_files
        if any(re.search(pattern, filepath) for pattern in PROHIBITED_SURFACE_PATTERNS)
        and not _is_governance_path(filepath)
    ]
    result.add(
        "No prohibited B2.3/provider/dependency/migration surfaces changed",
        not violations,
        f"Violations: {', '.join(violations[:5])}" if violations else "",
    )


def check_no_ci_gate_removal(result: ValidationResult, diff_content: str) -> None:
    removed_lines = [
        line
        for line in diff_content.splitlines()
        if line.startswith("-") and not line.startswith("---")
    ]
    suspicious = [
        line.strip()[:120]
        for line in removed_lines
        if any(
            keyword in line.lower()
            for keyword in [
                "required_status_checks",
                "required: true",
                "status_check",
                "branch_protection",
            ]
        )
    ]
    result.add(
        "No CI gate removal detected",
        not suspicious,
        f"Suspicious: {suspicious[:3]}" if suspicious else "",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="M0 Scope Lock Validator")
    parser.add_argument(
        "--baseline-sha", help="Override baseline SHA for diff comparison"
    )
    parser.add_argument(
        "--local-dev",
        action="store_true",
        help="Skip diff-based checks. Artifact staleness checks still run.",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("  M0 SCOPE LOCK VALIDATOR")
    print("  Pre-B2.4 Maintainability Stabilization")
    print("=" * 70)
    print()

    result = ValidationResult()

    print("-- Artifact Checks --")
    check_artifacts_exist(result)
    check_baseline_fields(result)
    check_scope_lock_prohibitions(result)
    check_canonical_artifact_consistency(result)
    check_validation_report(result)
    check_codeowners(result)
    check_issue_register(result)

    if args.local_dev:
        print("-- Repository-State Checks (SKIPPED: --local-dev) --")
        result.add("Repository-state checks", True, "Skipped in local-dev mode")
    else:
        print("-- Repository-State Checks --")
        baseline_sha = args.baseline_sha or _extract_baseline_sha_from_artifact()
        if baseline_sha is None:
            result.add(
                "Baseline SHA available",
                False,
                "Cannot determine baseline SHA from artifact or --baseline-sha",
            )
        else:
            result.add("Baseline SHA available", True, baseline_sha[:12])
            changed_files = _git_diff_names(baseline_sha)
            diff_content = _git_diff_content(baseline_sha)
            result.add("Diff available", True, f"{len(changed_files)} files changed")
            check_allowed_change_surface(result, changed_files)
            check_no_prohibited_surface_changes(result, changed_files)
            nongovernance_diff = _filter_diff_exclude_governance(diff_content)
            check_b24_contamination_dependencies(result, nongovernance_diff)
            check_b24_contamination_code(result, nongovernance_diff)
            check_no_ci_gate_removal(result, nongovernance_diff)

    print()
    print("-- Results --")
    print(result.report())
    print()

    if result.passed():
        print("  VERDICT: M0_SCOPE_LOCK_VALID")
        return 0

    print("  VERDICT: M0_SCOPE_LOCK_INVALID")
    return 1


if __name__ == "__main__":
    sys.exit(main())
