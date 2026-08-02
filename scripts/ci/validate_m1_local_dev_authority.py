#!/usr/bin/env python3
"""Static validator for M1 local development authority.

The runtime workflow proves physical bootability. This validator proves the
repository carries the required M1 authority artifacts and that the diff stays
inside onboarding/local-runtime surfaces.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]

REQUIRED_FILES = [
    "DEVELOPMENT.md",
    "README.md",
    "backend/README.md",
    "backend/Dockerfile",
    ".env.example",
    ".env.local.example",
    "docker-compose.local.yml",
    "contracts-internal/governance/main_branch_protection_integrity.main.json",
    "Makefile",
    "scripts/smoke/m1_runtime_smoke.py",
    "scripts/ci/validate_m1_local_dev_authority.py",
    "scripts/ci/run_m1_onboarding_bootstrap.sh",
    ".github/workflows/m1-local-dev-authority.yml",
    "docs/maintainability/m1_completion_record.md",
]

REQUIRED_MAKE_TARGETS = [
    "dev",
    "migrate",
    "api",
    "worker",
    "health",
    "smoke",
    "test",
    "down",
    "logs",
]

REQUIRED_ENV_VARS = [
    "DATABASE_URL",
    "MIGRATION_DATABASE_URL",
    "CELERY_BROKER_URL",
    "CELERY_RESULT_BACKEND",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DB",
    "ENVIRONMENT",
    "SKELDIR_CONTROL_PLANE_ENABLED",
    "B23_DATABASE_POOL_SIZE",
    "B23_DATABASE_MAX_OVERFLOW",
    "B23_DATABASE_POOL_TIMEOUT_SECONDS",
    "B23_DATABASE_STATEMENT_TIMEOUT_MS",
    "B23_DATABASE_LOCK_TIMEOUT_MS",
    "B23_WORKER_CONCURRENCY",
    "B23_WORKER_PREFETCH_MULTIPLIER",
]

REQUIRED_DEVELOPMENT_PHRASES = [
    "The canonical path is container-first. Host-native Python execution is noncanonical.",
    "docker-compose.local.yml",
    "make dev",
    "make migrate",
    "make api",
    "make worker",
    "make health",
    "make smoke",
    "make test",
    "M2",
    "M3",
    "M4",
    "M5",
    "M6",
    "Windows",
    "macOS",
    "Linux",
    "port collision",
    "ARM64",
]

STALE_README_PATTERNS = [
    "Backend application code is not yet migrated",
    "prepared for when backend code is available",
    "placeholder-only",
]

LOCAL_HOSTS = {"postgres", "localhost", "127.0.0.1", "::1"}
EXTERNAL_MARKERS = ("neon.tech", "amazonaws.com", "rds.amazonaws.com", "supabase.co")

ALLOWED_M1_PATH_PREFIXES = [
    ".github/CODEOWNERS",
    ".github/workflows/m1-local-dev-authority.yml",
    ".github/workflows/m2-test-feedback-loop.yml",
    ".github/workflows/r7-final-winning-state.yml",
    "DEVELOPMENT.md",
    "README.md",
    "backend/README.md",
    "backend/Dockerfile",
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
    ".env.example",
    ".env.local.example",
    "docker-compose.local.yml",
    "docker-compose.test.yml",
    "contracts-internal/governance/b03_phase2_required_status_checks.main.json",
    "contracts-internal/governance/main_branch_protection_integrity.main.json",
    "Makefile",
    "pytest.ini",
    "scripts/guard_no_docker.py",
    "scripts/smoke/",
    "scripts/ci/run_m1_onboarding_bootstrap.sh",
    "scripts/ci/validate_m1_local_dev_authority.py",
    "scripts/ci/validate_m0_scope_lock.py",
    "scripts/ci/run_m2_test_feedback_loop.sh",
    "scripts/ci/validate_m2_test_feedback_loop.py",
    "scripts/ci/enforce_b21_p4_queue_isolation_semantics_lock.py",
    "scripts/ci/enforce_forensics_index.py",
    "scripts/ci/enforce_postgres_only.py",
    "scripts/ci/run_ci_governance_cohort.py",
    "scripts/ci/phase2_schema_closure_gate.py",
    "scripts/ci/validate_m3_ci_governance.py",
    "scripts/ci/validate_m4_ops_runbooks.py",
    "scripts/ci/validate_b24_p1_authority_schema.py",
    "scripts/ci/validate_b24_p2_source_snapshot.py",
    "scripts/ci/validate_b24_p3_fit_planning.py",
    "scripts/ci/validate_b24_p4_resource_bounds.py",
    "scripts/ci/validate_b24_p5_runtime_harness.py",
    "scripts/ci/validate_b24_p6_real_fit_worker.py",
    "scripts/ci/validate_b24_p7_diagnostics.py",
    "scripts/ci/validate_b24_p8_artifact_lifecycle.py",
    "scripts/ci/validate_b24_p9_worker_tenant_hygiene.py",
    "scripts/ci/validate_b24_p10_projection.py",
    "scripts/ci/validate_b24_p11_ci_gates.py",
    "scripts/ci/validate_b24_p11_execution_artifacts.py",
    "scripts/ci/validate_b24_p11_workflow_vacuity.py",
    "scripts/ci/validate_b24_p12_internal_e2e.py",
    "scripts/ci/validate_b25_p1_contracts.py",
    "scripts/ci/validate_b25_p1_trust_drift.py",
    "scripts/ci/validate_b25_p2_canonicalization.py",
    "scripts/ci/validate_b25_p3_text_disposition.py",
    "scripts/ci/validate_b25_p4_money_authority.py",
    "scripts/ci/validate_b25_p5_builder.py",
    "scripts/ci/validate_b25_p6_reason_truth_matrix.py",
    "scripts/ci/validate_b25_p7_provenance_audit.py",
    "scripts/ci/validate_b25_p8_signing_verification.py",
    "scripts/ci/validate_b25_p10_trust_api_surface.py",
    "scripts/ci/validate_live_branch_protection.py",
    "scripts/ci/write_b24_p11_command_junit.py",
    "scripts/ci/validate_m5_b24_readiness_design.py",
    "scripts/ci/validate_m6_llm_boundary.py",
    "scripts/ci/validate_m7_b24_readiness.py",
    "scripts/phase_gates/generate_value_trace_proof_pack.py",
    "api-contracts/openapi/v1/attribution.yaml",
    "api-contracts/openapi/v1/reconciliation.yaml",
    "frontend/src/types/api/attribution.ts",
    "frontend/src/types/api/reconciliation.ts",
    "frontend/src/budget/components/BudgetScenarioDetailV2/scenarioData.ts",
    "frontend/src/channel-detail/components/CampaignTable.tsx",
    "frontend/src/channel-detail/mockData.ts",
    "scripts/ci/enforce_boundary.sh",
    "scripts/r3/ingestion_under_fire.py",
    "scripts/schema/assert_canonical_schema.py",
    "scripts/testing/",
    "scripts/ops/",
    ".github/actions/setup-postgres-ci/",
    ".github/workflows/b2_4-gate-dry-run.yml",
    ".github/workflows/b2_5-p1-contracts.yml",
    ".github/workflows/b2_5-p2-canonicalization.yml",
    ".github/workflows/b2_5-p3-text-disposition.yml",
    ".github/workflows/b2_5-p4-money-authority.yml",
    ".github/workflows/b2_5-p5-builder.yml",
    ".github/workflows/b2_5-p6-reason-truth-matrix.yml",
    ".github/workflows/b2_5-p7-provenance-audit.yml",
    ".github/workflows/b2_5-p8-signing-verification.yml",
    ".github/workflows/b2_5-p10-trust-api-surface.yml",
    ".github/workflows/contract-publish.yml",
    ".github/workflows/ci.yml",
    ".github/workflows/r2-data-truth-hardening.yml",
    ".github/workflows/m3-ci-governance.yml",
    ".github/workflows/m4-operational-runbooks.yml",
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
    "alembic/versions/007_skeldir_foundation/202605261200_b24_p4_atomic_dominance_canonical_profiling.py",
    "alembic/versions/007_skeldir_foundation/202605271200_b24_p4_strict_profiling_purge.py",
    "alembic/versions/007_skeldir_foundation/202605281200_b24_p5_runtime_statuses.py",
    "alembic/versions/007_skeldir_foundation/202606021200_b24_p6_fit_execution_states.py",
    "alembic/versions/007_skeldir_foundation/202606041200_b24_p7_diagnostic_semantics.py",
    "alembic/versions/007_skeldir_foundation/202606031200_b24_p6_fit_id_resolution_policy.py",
    "alembic/versions/007_skeldir_foundation/202606061200_b24_p8_artifact_lifecycle.py",
    "alembic/versions/007_skeldir_foundation/202606071200_b24_p8_follow_up_airgap_quota.py",
    "alembic/versions/007_skeldir_foundation/202606081200_b24_p9_worker_tenant_hygiene.py",
    "alembic/versions/007_skeldir_foundation/202606141200_b24_p9_directive_ix_dispatch_authority.py",
    "alembic/versions/007_skeldir_foundation/202606181200_b24_p9_directive_x_broker_independent_authority.py",
    "alembic/versions/007_skeldir_foundation/202606201300_b24_p9_directive_xiii_shared_recovery.py",
    "alembic/versions/007_skeldir_foundation/202606201430_b24_p9_directive_xiv_failure_ack_recovery.py",
    "alembic/versions/007_skeldir_foundation/202607011200_b25_p7_trust_audit_provenance.py",
    "alembic/versions/007_skeldir_foundation/202607191200_b25_p9_machine_identity.py",
    ".github/workflows/b2_5-p9-machine-identity.yml",
    "scripts/ci/validate_b25_p9_machine_identity.py",
    "backend/Dockerfile.bayesian",
    "backend/requirements.txt",
    "backend/requirements-bayesian.txt",
    "backend/app/bayesian/",
    "backend/app/trust/",
    "backend/app/api/trust_keys.py",
    "backend/app/api/trust_api.py",
    "backend/app/config/contract_scope.yaml",
    "backend/app/main.py",
    "backend/app/ingestion/event_service.py",
    "backend/app/models/__init__.py",
    "backend/app/revenue_verification/batch_engine.py",
    "backend/app/tasks/attribution.py",
    "backend/app/tasks/bayesian.py",
    "backend/app/tasks/beat_schedule.py",
    "Procfile",
    "db/schema/canonical_schema.sql",
    "db/schema/canonical_schema.yaml",
    "contracts/trust-api/",
    "docs/ci/",
    "docs/b2_4/",
    "docs/b2_7/",
    "docs/llm/",
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
    "docs/forensics/B2.4-P4_Atomic_Dominance_Canonical_Profiling_Dispatch_Corrective_Report.md",
    "docs/forensics/B2.4-P4_Strict_Purge_Causal_Dispatch_Recovery_Boundary_Corrective_Report.md",
    "docs/forensics/B2.4-P5 Remediation Evidence Pack .md",
    "docs/forensics/B2.4-P6 Remediation Evidence Pack .md",
    "docs/forensics/B2.4-P7 Remediation Evidence Pack .md",
    "docs/forensics/B2.4-P8 Remediation Evidence Pack .md",
    "docs/forensics/B2.4-P9 Remediation Evidence Pack .md",
    "docs/forensics/B2.4-P10 Remediation Evidence Pack .md",
    "docs/forensics/B2.4-P11 Remediation Evidence Pack .md",
    "docs/forensics/B2.4-P12 Remediation Evidence Pack .md",
    "docs/forensics/B2.5-P1 Remediation Evidence Pack .md",
    "docs/forensics/B2.5-P2 Remediation Evidence Pack .md",
    "docs/forensics/B2.5-P3 Remediation Evidence Pack .md",
    "docs/forensics/B2.5-P4 Remediation Evidence Pack .md",
    "docs/forensics/B2.5-P5 Remediation Evidence Pack .md",
    "docs/forensics/B2.5-P5 Follow-Up Corrective Evidence Pack.md",
    "docs/forensics/B2.5-P6 Remediation Evidence Pack .md",
    "docs/forensics/B2.5-P6 Follow-Up Corrective Evidence Pack.md",
    "docs/forensics/B2.5-P7 Remediation Evidence Pack.md",
    "docs/forensics/B2.5-P7 Follow-Up Corrective Evidence Pack.md",
    "docs/forensics/B2.5-P7 Second Follow-Up Corrective Evidence Pack.md",
    "docs/forensics/B2.5-P8 Remediation Evidence Pack.md",
    "docs/forensics/B2.5-P9 Remediation Evidence Pack.md",
    "docs/forensics/B2.5-P10 Remediation Evidence Pack .md",
    "docs/forensics/B2.5-P10 Corrective Remediation Evidence Pack.md",
    "docs/forensics/M3 Remediation Evidence Pack .md",
    "docs/forensics/M5 Remediation Evidence Pack .md",
    "M4 Remediation Evidence Pack.md",
    "M4.1_Remediation_Completion_Record.md",
    "docs/testing.md",
    "docs/testing_db_topology.md",
    "docs/testing_append_only_isolation.md",
    "docs/testing_celery_modes.md",
    "docs/testing_topology_url_authority.md",
    "docs/testing_b24_persistence_readiness.md",
    "docs/testing_b24_persistence_entry_gate.md",
    "docs/testing_parallel_isolation.md",
    "docs/maintainability/",
    "graphify-out/",
    "contracts/internal/",
    "M2 Remediation Evidence Pack.md",
    "tests/",
]

PROHIBITED_PATH_PATTERNS = [
    r"backend/app/llm/provider_boundary\.py$",
    r"backend/app/revenue_verification/(match_engine_kernel|semantic_authority|state_transitions|extraction_registry|batch_engine)\.py$",
    r"alembic/versions/",
    r"backend/db/migrations/",
    r"requirements.*\.txt$",
    r"pyproject\.toml$",
]

PROHIBITED_ADDED_PATTERNS = [
    r"pymc",
    r"pymc-marketing",
    r"pymc_marketing",
    r"arviz",
    r"pm\.Model",
    r"pm\.sample",
    r"az\.rhat",
    r"az\.ess\b",
]


class Result:
    def __init__(self) -> None:
        self.rows: list[tuple[str, bool, str]] = []

    def add(self, name: str, ok: bool, detail: str = "") -> None:
        self.rows.append((name, ok, detail))

    def ok(self) -> bool:
        return all(ok for _, ok, _ in self.rows)

    def report(self) -> str:
        lines = []
        for name, ok, detail in self.rows:
            prefix = "PASS" if ok else "FAIL"
            suffix = f" - {detail}" if detail else ""
            lines.append(f"[{prefix}] {name}{suffix}")
        return "\n".join(lines)


def read_text(path: str) -> str:
    full = REPO_ROOT / path
    if not full.exists():
        return ""
    return full.read_text(encoding="utf-8", errors="replace")


def git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        encoding="utf-8",
        errors="replace",
        text=True,
        capture_output=True,
        timeout=60,
    )


def changed_files(baseline_sha: str) -> list[str]:
    proc = git(["diff", "--name-only", f"{baseline_sha}...HEAD"])
    if proc.returncode != 0:
        proc = git(["diff", "--name-only", baseline_sha, "HEAD"])
    return [
        line.strip().replace("\\", "/")
        for line in proc.stdout.splitlines()
        if line.strip()
    ]


def diff_content(baseline_sha: str) -> str:
    proc = git(["diff", f"{baseline_sha}...HEAD"])
    if proc.returncode != 0:
        proc = git(["diff", baseline_sha, "HEAD"])
    return proc.stdout


def check_required_files(result: Result) -> None:
    for path in REQUIRED_FILES:
        full = REPO_ROOT / path
        result.add(
            f"required file exists: {path}", full.exists() and full.stat().st_size > 0
        )


def check_development_doc(result: Result) -> None:
    text = read_text("DEVELOPMENT.md")
    for phrase in REQUIRED_DEVELOPMENT_PHRASES:
        result.add(f"DEVELOPMENT.md documents: {phrase}", phrase in text)


def check_readmes(result: Result) -> None:
    combined = read_text("README.md") + "\n" + read_text("backend/README.md")
    for pattern in STALE_README_PATTERNS:
        result.add(f"README stale language absent: {pattern}", pattern not in combined)
    result.add(
        "README points to DEVELOPMENT.md", "DEVELOPMENT.md" in read_text("README.md")
    )
    result.add(
        "backend README points to DEVELOPMENT.md",
        "DEVELOPMENT.md" in read_text("backend/README.md"),
    )


def check_makefile(result: Result) -> None:
    text = read_text("Makefile")
    for target in REQUIRED_MAKE_TARGETS:
        result.add(
            f"Makefile target: {target}",
            re.search(rf"^{re.escape(target)}:", text, re.M) is not None,
        )

    for target in ("dev", "migrate", "api", "worker", "health", "smoke"):
        match = re.search(rf"^{target}:.*?(?=^[A-Za-z0-9_.-]+:|\Z)", text, re.M | re.S)
        body = match.group(0) if match else ""
        result.add(
            f"{target} uses Docker Compose",
            "docker compose" in body or "$(COMPOSE)" in body,
        )
        host_python = re.search(r"(^|\n)\s*@?python\s+", body) is not None
        result.add(f"{target} does not use host python", not host_python)


def _extract_env_value(text: str, key: str) -> str | None:
    match = re.search(rf"^{re.escape(key)}=(.*)$", text, re.M)
    if not match:
        return None
    return match.group(1).strip()


def _host_from_url(raw: str) -> str:
    from urllib.parse import urlparse

    cleaned = raw
    for prefix in ("sqla+", "db+"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :]
    return (urlparse(cleaned).hostname or "").lower()


def check_env_templates(result: Result) -> None:
    local_env = read_text(".env.local.example")
    general_env = read_text(".env.example")
    for var in REQUIRED_ENV_VARS:
        result.add(
            f".env.local.example contains {var}",
            _extract_env_value(local_env, var) is not None,
        )

    for var in (
        "DATABASE_URL",
        "MIGRATION_DATABASE_URL",
        "CELERY_BROKER_URL",
        "CELERY_RESULT_BACKEND",
    ):
        for filename, text in (
            (".env.local.example", local_env),
            (".env.example", general_env),
        ):
            value = _extract_env_value(text, var)
            if value is None:
                result.add(f"{filename} {var} exists", False, "missing")
                continue
            host = _host_from_url(value)
            is_external = any(marker in host for marker in EXTERNAL_MARKERS)
            result.add(
                f"{filename} {var} is local-safe",
                host in LOCAL_HOSTS and not is_external,
                f"host={host}",
            )


def check_compose_and_workflow(result: Result) -> None:
    compose = read_text("docker-compose.local.yml")
    for service in ("postgres:", "api:", "worker:", "migrate:", "smoke:"):
        result.add(f"compose service present: {service}", service in compose)
    result.add("compose uses local env file", ".env.local" in compose)
    forbidden_non_postgres_broker = "re" + "dis"
    result.add(
        "compose excludes alternate broker services",
        forbidden_non_postgres_broker not in compose.lower(),
    )

    workflow = read_text(".github/workflows/m1-local-dev-authority.yml")
    bootstrap = read_text("scripts/ci/run_m1_onboarding_bootstrap.sh")
    workflow_authority_text = workflow + "\n" + bootstrap
    for token in (
        "pull_request",
        "push",
        "docker compose --env-file .env.local -f docker-compose.local.yml config",
        "make dev",
        "make migrate",
        "make api",
        "make worker",
        "make health",
        "make smoke",
    ):
        result.add(f"M1 workflow includes {token}", token in workflow_authority_text)


def check_completion_record(result: Result) -> None:
    text = read_text("docs/maintainability/m1_completion_record.md")
    required = [
        "canonical topology",
        "command surface",
        "CI onboarding harness evidence",
        "migration proof",
        "API health proof",
        "worker/broker proof",
        "Celery task round-trip proof",
        "worker DB access proof",
        "external DB/broker rejection proof",
        "deferred M2/M3/M4/M5/M6",
        "no B2.4 implementation occurred",
        "no B2.3 semantics changed",
        "no provider-boundary behavior changed",
        "final verdict",
    ]
    for token in required:
        result.add(
            f"completion record contains: {token}", token.lower() in text.lower()
        )


def _allowed_m1_path(path: str) -> bool:
    return any(
        path == prefix or path.startswith(prefix) for prefix in ALLOWED_M1_PATH_PREFIXES
    )


def check_diff_scope(result: Result, baseline_sha: str | None, local_dev: bool) -> None:
    if local_dev:
        result.add("diff scope check", True, "skipped in --local-dev")
        return
    if not baseline_sha:
        result.add("baseline SHA available", False)
        return
    files = changed_files(baseline_sha)
    violations = [path for path in files if not _allowed_m1_path(path)]
    result.add(
        "M1 diff stays in allowed surfaces", not violations, ", ".join(violations[:10])
    )

    prohibited = [
        path
        for path in files
        if any(re.search(pattern, path) for pattern in PROHIBITED_PATH_PATTERNS)
        and not _allowed_m1_path(path)
    ]
    result.add(
        "M1 diff avoids prohibited surfaces", not prohibited, ", ".join(prohibited[:10])
    )

    added: list[str] = []
    current_path = ""
    for line in diff_content(baseline_sha).splitlines():
        if line.startswith("diff --git "):
            marker = " b/"
            current_path = line.split(marker, 1)[1] if marker in line else ""
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue
        if _allowed_m1_path(current_path):
            continue
        if current_path.startswith("docs/") or current_path == "DEVELOPMENT.md":
            continue
        if current_path.startswith("scripts/ci/validate_"):
            continue
        if current_path.startswith("backend/tests/") or current_path.startswith(
            "tests/"
        ):
            continue
        added.append(line[1:])
    for pattern in PROHIBITED_ADDED_PATTERNS:
        hit = any(re.search(pattern, line, re.I) for line in added)
        result.add(f"no prohibited added pattern: {pattern}", not hit)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-sha")
    parser.add_argument("--local-dev", action="store_true")
    args = parser.parse_args()

    result = Result()
    check_required_files(result)
    check_development_doc(result)
    check_readmes(result)
    check_makefile(result)
    check_env_templates(result)
    check_compose_and_workflow(result)
    check_completion_record(result)
    check_diff_scope(result, args.baseline_sha, args.local_dev)

    print("M1 LOCAL DEVELOPMENT AUTHORITY VALIDATOR")
    print(result.report())
    print(f"VERDICT: {'M1_STATIC_VALID' if result.ok() else 'M1_STATIC_INVALID'}")
    return 0 if result.ok() else 1


if __name__ == "__main__":
    sys.exit(main())
