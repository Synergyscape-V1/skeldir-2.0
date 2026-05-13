#!/usr/bin/env python3
"""Static validator for M2 test feedback loop and database topology authority."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]

REQUIRED_DOCS = [
    "docs/testing.md",
    "docs/testing_db_topology.md",
    "docs/testing_append_only_isolation.md",
    "docs/testing_celery_modes.md",
    "docs/testing_topology_url_authority.md",
    "docs/testing_b24_persistence_readiness.md",
    "docs/maintainability/m2_completion_record.md",
]

REQUIRED_MARKERS = [
    "unit_pure",
    "db_invariant",
    "integration_db_direct",
    "integration_db_pooler",
    "governance",
    "e2e",
    "slow",
    "celery_eager",
    "celery_worker",
    "append_only_sensitive",
    "rls_guc_sensitive",
    "fail_visible_tenant_context",
    "b23_representative",
    "b24_persistence_readiness",
    "requires_external_db",
]

REQUIRED_MAKE_TARGETS = [
    "test-unit-pure",
    "test-db-invariant",
    "test-db-direct",
    "test-db-pooler",
    "test-fail-visible-tenant-context",
    "test-celery-eager",
    "test-celery-worker",
    "test-broker-topology",
    "test-b23-representative",
    "test-b24-persistence-readiness",
    "test-governance",
    "test-e2e",
    "test-external-db-smoke",
    "test",
]

REQUIRED_FILES = [
    "docker-compose.test.yml",
    "scripts/ci/validate_m2_test_feedback_loop.py",
    "scripts/ci/run_m2_test_feedback_loop.sh",
    "scripts/testing/assert_topology_urls.py",
    "scripts/testing/create_test_template_db.sh",
    "scripts/testing/create_disposable_test_db.sh",
    ".github/workflows/m2-test-feedback-loop.yml",
]

EXTERNAL_PATTERNS = (
    "neon.tech",
    "rds.amazonaws.com",
    "supabase.co",
    "Sk3ld1r_App_Pr0d_2025",
    "npg_ETLZ7UxM3obe",
)

PROHIBITED_PHASE_PATTERNS = (
    r"pymc",
    r"pymc-marketing",
    r"pymc_marketing",
    r"arviz",
    r"az\.rhat",
    r"az\.ess\b",
    r"pm\.Model",
    r"pm\.sample",
)

PROHIBITED_PRODUCTION_SURFACES = (
    "backend/app/llm/provider_boundary.py",
    "backend/app/revenue_verification/match_engine_kernel.py",
    "backend/app/revenue_verification/semantic_authority.py",
    "backend/app/revenue_verification/state_transitions.py",
    "backend/app/revenue_verification/batch_engine.py",
)


@dataclass
class Result:
    rows: list[tuple[str, bool, str]]

    def add(self, name: str, ok: bool, detail: str = "") -> None:
        self.rows.append((name, ok, detail))

    @property
    def ok(self) -> bool:
        return all(ok for _, ok, _ in self.rows)

    def report(self) -> str:
        lines = []
        for name, ok, detail in self.rows:
            status = "PASS" if ok else "FAIL"
            suffix = f" - {detail}" if detail else ""
            lines.append(f"[{status}] {name}{suffix}")
        return "\n".join(lines)


def read(path: str) -> str:
    full = REPO_ROOT / path
    if not full.exists():
        return ""
    return full.read_text(encoding="utf-8", errors="replace")


def iter_files(*roots: str) -> list[Path]:
    paths: list[Path] = []
    for root in roots:
        base = REPO_ROOT / root
        if not base.exists():
            continue
        if base.is_file():
            paths.append(base)
            continue
        for path in base.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".py", ".sh", ".yml", ".yaml", ".ini", ".md"}:
                paths.append(path)
    return paths


def rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, text=True, capture_output=True, timeout=60)


def changed_files(baseline_sha: str | None) -> list[str]:
    if not baseline_sha:
        return []
    proc = git(["diff", "--name-only", f"{baseline_sha}...HEAD"])
    if proc.returncode != 0:
        proc = git(["diff", "--name-only", baseline_sha, "HEAD"])
    return [line.strip().replace("\\", "/") for line in proc.stdout.splitlines() if line.strip()]


def check_required(result: Result) -> None:
    for path in [*REQUIRED_DOCS, *REQUIRED_FILES]:
        full = REPO_ROOT / path
        result.add(f"required artifact exists: {path}", full.exists() and full.stat().st_size > 0)


def check_markers(result: Result) -> None:
    pytest_ini = read("pytest.ini")
    for marker in REQUIRED_MARKERS:
        result.add(f"pytest marker configured: {marker}", re.search(rf"^\s*{marker}\s*:", pytest_ini, re.M) is not None)
    test_text = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in iter_files("backend/tests", "tests"))
    for marker in REQUIRED_MARKERS:
        if marker in {"requires_external_db", "slow", "e2e"}:
            continue
        result.add(f"pytest marker used: {marker}", f"mark.{marker}" in test_text or f"-m \"{marker}" in read("scripts/ci/run_m2_test_feedback_loop.sh"))


def check_makefile(result: Result) -> None:
    makefile = read("Makefile")
    for target in REQUIRED_MAKE_TARGETS:
        result.add(f"Makefile target exists: {target}", re.search(rf"^{re.escape(target)}:", makefile, re.M) is not None)
    result.add("make test runs safe default only", "run_m2_test_feedback_loop.sh default" in makefile)
    result.add("external DB smoke target is explicit", "run_m2_test_feedback_loop.sh external-db-smoke" in makefile)


def check_external_urls(result: Result) -> None:
    offenders: list[str] = []
    dsn_pattern = re.compile(
        r"postgres(?:ql)?(?:\+asyncpg)?://[^\"'\s]+(?:neon\.tech|rds\.amazonaws\.com|supabase\.co|amazonaws\.com|Sk3ld1r_App_Pr0d_2025|npg_ETLZ7UxM3obe)",
        re.I,
    )
    for path in iter_files("backend/tests", "tests"):
        text = path.read_text(encoding="utf-8", errors="replace")
        if dsn_pattern.search(text):
            offenders.append(rel(path))
    result.add("default test paths contain no hardcoded external DB URLs", not offenders, ", ".join(offenders[:10]))


def check_docs(result: Result) -> None:
    authority = read("docs/testing_topology_url_authority.md")
    for token in [
        "DATABASE_URL",
        "DIRECT_DATABASE_URL",
        "POOLED_DATABASE_URL",
        "TEST_DATABASE_URL",
        "TEST_DIRECT_DATABASE_URL",
        "TEST_POOLED_DATABASE_URL",
        "ALEMBIC_DATABASE_URL",
        "EXTERNAL_DATABASE_URL",
        "CELERY_BROKER_URL",
        "CELERY_RESULT_BACKEND",
    ]:
        result.add(f"topology matrix documents {token}", token in authority)
    result.add("B2.4 readiness doc records explicit blocker or table", "bayesian_model_fits" in read("docs/testing_b24_persistence_readiness.md"))
    result.add("append-only isolation doc forbids protected deletion", "DELETE FROM attribution_events" in read("docs/testing_append_only_isolation.md"))
    result.add("celery modes doc distinguishes eager/worker", "celery_eager" in read("docs/testing_celery_modes.md") and "celery_worker" in read("docs/testing_celery_modes.md"))


def check_pooler_and_broker(result: Result) -> None:
    compose = read("docker-compose.test.yml")
    result.add("pooler profile present", "pgbouncer" in compose.lower() and "transaction" in compose.lower())
    result.add("pooler exposes local port", "6432" in compose)
    result.add("broker remains Postgres-backed", "CELERY_BROKER_URL" in read("scripts/ci/run_m2_test_feedback_loop.sh") and "sqla+" in read("scripts/ci/run_m2_test_feedback_loop.sh"))
    result.add("broker negative control exists", "--expect-rejection" in read("scripts/ci/run_m2_test_feedback_loop.sh"))


def check_append_only_static(result: Result) -> None:
    offenders: list[str] = []
    pattern = re.compile(r"(DELETE\s+FROM\s+attribution_events|TRUNCATE\s+(TABLE\s+)?attribution_events)", re.I)
    for path in iter_files("backend/tests", "tests"):
        text = path.read_text(encoding="utf-8", errors="replace")
        active_lines = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            active_lines.append(line)
        active_text = "\n".join(active_lines)
        if pattern.search(active_text) and "M2_APPEND_ONLY_DISPOSABLE_CONTEXT" not in text and "xfail(" not in text:
            offenders.append(rel(path))
    result.add("protected truth-table deletion is classified or quarantined", not offenders, ", ".join(offenders[:10]))


def check_skeletons(result: Result) -> None:
    offenders: list[str] = []
    for path in iter_files("backend/tests", "tests"):
        text = path.read_text(encoding="utf-8", errors="replace")
        if ("placeholder structure" in text or "Import actual app" in text or "TODO: Implement actual" in text) and "xfail(" not in text:
            offenders.append(rel(path))
    result.add("skeleton/vacuous tests are quarantined", not offenders, ", ".join(offenders[:10]))


def check_b24_guard(result: Result) -> None:
    implementation_text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in iter_files("backend/app", "backend/requirements.txt", "pyproject.toml", "package.json")
        if "validate_m2_test_feedback_loop.py" not in rel(path)
    )
    implementation_violations = [
        pattern for pattern in PROHIBITED_PHASE_PATTERNS if re.search(pattern, implementation_text, re.I)
    ]
    result.add("B2.4 implementation dependencies/markers absent from runtime paths", not implementation_violations, ", ".join(implementation_violations))
    readiness = read("docs/testing_b24_persistence_readiness.md")
    result.add(
        "B2.4 absent substrate is explicitly blocked",
        "M2_BLOCKED_BY_UNCONFIRMED_B24_PERSISTENCE_SUBSTRATE" in readiness or "bayesian_model_fits exists" in readiness,
    )


def check_workflow(result: Result) -> None:
    workflow = read(".github/workflows/m2-test-feedback-loop.yml")
    for token in [
        "pull_request",
        "push",
        "run_m1_onboarding_bootstrap.sh",
        "validate_m2_test_feedback_loop.py",
        "test-unit-pure",
        "test-db-invariant",
        "test-db-direct",
        "test-db-pooler",
        "test-fail-visible-tenant-context",
        "test-broker-topology",
        "test-b23-representative",
        "test-b24-persistence-readiness",
    ]:
        result.add(f"M2 workflow includes {token}", token in workflow)


def check_phase_diff(result: Result, baseline_sha: str | None, local_dev: bool) -> None:
    if local_dev:
        result.add("phase diff boundary", True, "skipped in --local-dev")
        return
    changed = changed_files(baseline_sha)
    touched = [path for path in changed if path in PROHIBITED_PRODUCTION_SURFACES]
    result.add("M2 diff avoids B2.3/provider-boundary semantic surfaces", not touched, ", ".join(touched))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-sha")
    parser.add_argument("--local-dev", action="store_true")
    parser.add_argument("--check-skeletons-only", action="store_true")
    args = parser.parse_args()

    result = Result([])
    if args.check_skeletons_only:
        check_skeletons(result)
    else:
        check_required(result)
        check_markers(result)
        check_makefile(result)
        check_external_urls(result)
        check_docs(result)
        check_pooler_and_broker(result)
        check_append_only_static(result)
        check_skeletons(result)
        check_b24_guard(result)
        check_workflow(result)
        check_phase_diff(result, args.baseline_sha, args.local_dev)

    print("M2 TEST FEEDBACK LOOP VALIDATOR")
    print(result.report())
    print(f"VERDICT: {'M2_STATIC_VALID' if result.ok else 'M2_STATIC_INVALID'}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
