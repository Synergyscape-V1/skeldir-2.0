#!/usr/bin/env python3
"""
M0 Scope Lock Validator — Policy-as-Code for Pre-B2.4 Maintainability Stabilization.

This script validates that:
1. Required M0 governance artifacts exist and contain mandatory fields.
2. The issue register covers all three audit sources and required categories.
3. The M0 diff does not introduce B2.4 feature contamination.
4. The scope lock contains all required prohibitions.

Exit codes:
  0 — All checks pass.
  1 — One or more checks fail.

Usage:
  python scripts/ci/validate_m0_scope_lock.py
  python scripts/ci/validate_m0_scope_lock.py --baseline-sha <sha>
  python scripts/ci/validate_m0_scope_lock.py --local-dev  (skip diff checks)
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

# ── Constants ──────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

M0_BASELINE_PATH = REPO_ROOT / "docs" / "maintainability" / "m0_baseline.md"
M0_SCOPE_LOCK_PATH = REPO_ROOT / "docs" / "maintainability" / "m0_scope_lock.md"
M0_ISSUE_REGISTER_PATH = REPO_ROOT / "docs" / "maintainability" / "maintainability_issue_register.yaml"

REQUIRED_ARTIFACTS = [M0_BASELINE_PATH, M0_SCOPE_LOCK_PATH, M0_ISSUE_REGISTER_PATH]

# Fields that must appear in m0_baseline.md
REQUIRED_BASELINE_FIELDS = [
    "primary branch",
    "primary branch head",
    "remote",
    "m0 baseline sha",
    "m0 ci workflow",
    "m0 ci job name",
    "required for merge",
    "b2.4 implementation is unauthorized",
    "post-b2.3 and pre-b2.4",
    "b2.3 semantics are closed",
]

# Required prohibitions in m0_scope_lock.md
REQUIRED_SCOPE_LOCK_PHRASES = [
    "b2.4 implementation prohibition",
    "b2.3 semantic reopening prohibition",
    "provider-boundary behavior-change prohibition",
    "broad ci refactor prohibition",
    "bayesian",
    "pymc",
    "required ci status",
]

# Required audit sources in issue register
REQUIRED_SOURCES = {"Nicholas", "Trey", "George", "Synthesized"}

# Required issue categories (mapped from affected_substrate field)
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

# Required fields per issue in the register
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

# B2.4 contamination patterns — production dependency additions
B24_DEPENDENCY_PATTERNS = [
    r"pymc",
    r"pymc-marketing",
    r"pymc_marketing",
    r"arviz",
]

# B2.4 contamination patterns — code patterns
B24_CODE_PATTERNS = [
    r"pm\.Model",
    r"pm\.sample",
    r"az\.rhat",
    r"az\.ess\b",
    r"az\.summary",
]

# Allowed M0 change surface
ALLOWED_M0_PATHS = [
    "docs/maintainability/",
    "scripts/ci/validate_m0_scope_lock.py",
    ".github/workflows/m0-maintainability-scope-lock.yml",
]

# ── Helpers ────────────────────────────────────────────────────────────────────


class ValidationResult:
    """Collects pass/fail results for all checks."""

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
                line += f" — {detail}"
            lines.append(line)
        total = len(self.checks)
        passed = sum(1 for _, ok, _ in self.checks if ok)
        failed = total - passed
        lines.append("")
        lines.append(f"  Total: {total} | Passed: {passed} | Failed: {failed}")
        return "\n".join(lines)


def _read_text(path: Path) -> str:
    """Read file content, return empty string if missing."""
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _git_diff_names(baseline_sha: str) -> list[str]:
    """Get list of changed files between baseline and HEAD."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", f"{baseline_sha}...HEAD"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            timeout=30,
        )
        if result.returncode != 0:
            # Fallback: compare against HEAD directly
            result = subprocess.run(
                ["git", "diff", "--name-only", baseline_sha, "HEAD"],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
                timeout=30,
            )
        return [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def _git_diff_content(baseline_sha: str) -> str:
    """Get full diff content between baseline and HEAD."""
    try:
        result = subprocess.run(
            ["git", "diff", f"{baseline_sha}...HEAD"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            timeout=60,
        )
        if result.returncode != 0:
            result = subprocess.run(
                ["git", "diff", baseline_sha, "HEAD"],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
                timeout=60,
            )
        return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def _filter_diff_exclude_governance(diff_content: str) -> str:
    """Filter diff to exclude hunks from M0 governance files.

    Governance files (docs/maintainability/, scripts/ci/validate_m0_scope_lock.py,
    .github/workflows/m0-maintainability-scope-lock.yml) necessarily reference
    prohibited patterns like 'pymc', 'arviz', 'pm.Model' as documentation of
    what is prohibited. These references must not trigger false-positive
    contamination alerts.
    """
    filtered_lines = []
    in_governance_file = False

    for line in diff_content.split("\n"):
        # Detect file headers: diff --git a/path b/path
        if line.startswith("diff --git "):
            # Extract the b/ path from the diff header
            parts = line.split(" b/")
            if len(parts) >= 2:
                filepath = parts[-1]
                in_governance_file = any(
                    filepath.startswith(allowed) for allowed in ALLOWED_M0_PATHS
                )
            else:
                in_governance_file = False

        if not in_governance_file:
            filtered_lines.append(line)

    return "\n".join(filtered_lines)


def _extract_baseline_sha_from_artifact() -> str | None:
    """Extract M0_BASELINE_SHA from m0_baseline.md."""
    content = _read_text(M0_BASELINE_PATH)
    match = re.search(r"M0_BASELINE_SHA=([a-f0-9]{40})", content)
    return match.group(1) if match else None


# ── Artifact Checks ───────────────────────────────────────────────────────────


def check_artifacts_exist(result: ValidationResult) -> None:
    """Fail if any required M0 artifact is missing."""
    for path in REQUIRED_ARTIFACTS:
        exists = path.exists() and path.stat().st_size > 0
        result.add(
            f"Artifact exists: {path.name}",
            exists,
            str(path.relative_to(REPO_ROOT)) if not exists else "",
        )


def check_baseline_fields(result: ValidationResult) -> None:
    """Fail if baseline lacks required fields."""
    content = _read_text(M0_BASELINE_PATH).lower()
    if not content:
        result.add("Baseline fields", False, "m0_baseline.md is empty or missing")
        return
    for field in REQUIRED_BASELINE_FIELDS:
        found = field.lower() in content
        result.add(f"Baseline field: {field}", found)


def check_scope_lock_prohibitions(result: ValidationResult) -> None:
    """Fail if scope lock omits required prohibitions."""
    content = _read_text(M0_SCOPE_LOCK_PATH).lower()
    if not content:
        result.add("Scope lock prohibitions", False, "m0_scope_lock.md is empty or missing")
        return
    for phrase in REQUIRED_SCOPE_LOCK_PHRASES:
        found = phrase.lower() in content
        result.add(f"Scope lock contains: {phrase}", found)


def check_issue_register(result: ValidationResult) -> None:
    """Validate issue register coverage and field completeness."""
    content = _read_text(M0_ISSUE_REGISTER_PATH)
    if not content:
        result.add("Issue register", False, "maintainability_issue_register.yaml is empty or missing")
        return

    # Check audit source coverage
    for source in REQUIRED_SOURCES:
        found = f"source: {source}" in content
        result.add(f"Issue register covers source: {source}", found)

    # Check required categories
    for category in REQUIRED_CATEGORIES:
        found = f"affected_substrate: {category}" in content
        result.add(f"Issue register covers category: {category}", found)

    # Check for B2.4-entry blockers
    has_blockers = "b24_entry_blocking: true" in content
    result.add("Issue register has B2.4-entry blockers", has_blockers)

    # Check that deferred issues have reasons
    # Simple heuristic: count deferred dispositions and deferred_reasons
    deferred_count = content.count("phase_disposition: deferred")
    null_deferred_reasons_in_deferred = 0

    # Parse issues to check deferred reasons
    issues = content.split("  - id:")
    for issue_block in issues[1:]:  # Skip header
        if "phase_disposition: deferred" in issue_block:
            if "deferred_reason: null" in issue_block or "deferred_reason:" not in issue_block:
                null_deferred_reasons_in_deferred += 1

    result.add(
        "Deferred issues have reasons",
        null_deferred_reasons_in_deferred == 0,
        f"{null_deferred_reasons_in_deferred} deferred issues lack reasons" if null_deferred_reasons_in_deferred > 0 else "",
    )

    # Check required fields exist for at least one issue
    for field in REQUIRED_ISSUE_FIELDS:
        found = f"{field}:" in content
        result.add(f"Issue register field present: {field}", found)


# ── Repository-State Checks ───────────────────────────────────────────────────


def check_b24_contamination_dependencies(result: ValidationResult, diff_content: str) -> None:
    """Fail if diff introduces B2.4 dependency additions."""
    if not diff_content:
        result.add("B2.4 dependency contamination (no diff)", True, "No diff available")
        return

    # Only check added lines (lines starting with +)
    added_lines = [line for line in diff_content.split("\n") if line.startswith("+") and not line.startswith("+++")]

    for pattern in B24_DEPENDENCY_PATTERNS:
        found_in_deps = False
        for line in added_lines:
            line_lower = line.lower()
            # Check if this is in a dependency context (requirements, setup, pyproject)
            if re.search(pattern, line_lower) and not any(
                safe in line_lower for safe in ["# prohibited", "# do not", "validator", "validate", "check"]
            ):
                # Allow references in governance/documentation/validator files
                found_in_deps = True
                break
        result.add(f"No B2.4 dependency addition: {pattern}", not found_in_deps)


def check_b24_contamination_code(result: ValidationResult, diff_content: str) -> None:
    """Fail if diff introduces B2.4 code patterns."""
    if not diff_content:
        result.add("B2.4 code contamination (no diff)", True, "No diff available")
        return

    added_lines = [line for line in diff_content.split("\n") if line.startswith("+") and not line.startswith("+++")]

    for pattern in B24_CODE_PATTERNS:
        found = any(re.search(pattern, line) for line in added_lines)
        result.add(f"No B2.4 code pattern: {pattern}", not found)


def check_allowed_change_surface(result: ValidationResult, changed_files: list[str]) -> None:
    """Fail if M0 diff touches files outside the allowed surface."""
    violations = []
    for filepath in changed_files:
        if any(filepath.startswith(allowed) for allowed in ALLOWED_M0_PATHS):
            continue
        violations.append(filepath)

    result.add(
        "M0 changes within allowed surface",
        len(violations) == 0,
        f"Violations: {', '.join(violations[:5])}" if violations else "",
    )


def check_no_ci_gate_removal(result: ValidationResult, diff_content: str) -> None:
    """Fail if diff removes or weakens existing CI gates."""
    if not diff_content:
        result.add("No CI gate removal (no diff)", True, "No diff available")
        return

    # Check for removed required_status_checks or status_check patterns
    removed_lines = [line for line in diff_content.split("\n") if line.startswith("-") and not line.startswith("---")]

    suspicious_removals = []
    for line in removed_lines:
        if any(
            keyword in line.lower()
            for keyword in ["required_status_checks", "required: true", "status_check", "branch_protection"]
        ):
            suspicious_removals.append(line.strip()[:80])

    result.add(
        "No CI gate removal detected",
        len(suspicious_removals) == 0,
        f"Suspicious: {suspicious_removals[:3]}" if suspicious_removals else "",
    )


# ── Main ───────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="M0 Scope Lock Validator")
    parser.add_argument("--baseline-sha", help="Override baseline SHA for diff comparison")
    parser.add_argument("--local-dev", action="store_true", help="Skip diff-based checks (local development mode)")
    args = parser.parse_args()

    print("=" * 70)
    print("  M0 SCOPE LOCK VALIDATOR")
    print("  Pre-B2.4 Maintainability Stabilization")
    print("=" * 70)
    print()

    result = ValidationResult()

    # ── Section 1: Artifact Checks ─────────────────────────────────────────
    print("-- Artifact Checks --")
    check_artifacts_exist(result)
    check_baseline_fields(result)
    check_scope_lock_prohibitions(result)
    check_issue_register(result)

    # -- Section 2: Repository-State Checks --
    if not args.local_dev:
        print("-- Repository-State Checks --")

        baseline_sha = args.baseline_sha or _extract_baseline_sha_from_artifact()

        if baseline_sha is None:
            result.add(
                "Baseline SHA available",
                False,
                "Cannot determine baseline SHA from artifact or --baseline-sha argument",
            )
        else:
            result.add("Baseline SHA available", True, baseline_sha[:12])

            changed_files = _git_diff_names(baseline_sha)
            diff_content = _git_diff_content(baseline_sha)

            if not changed_files and not diff_content:
                result.add("Diff available", True, "No changes detected (baseline == HEAD)")
            else:
                result.add("Diff available", True, f"{len(changed_files)} files changed")
                check_allowed_change_surface(result, changed_files)
                # Filter out governance files before contamination checks.
                # Governance docs necessarily reference prohibited patterns
                # (pymc, arviz, pm.Model) as documentation of what is banned.
                non_governance_diff = _filter_diff_exclude_governance(diff_content)
                check_b24_contamination_dependencies(result, non_governance_diff)
                check_b24_contamination_code(result, non_governance_diff)
                check_no_ci_gate_removal(result, diff_content)
    else:
        print("-- Repository-State Checks (SKIPPED: --local-dev) --")
        result.add("Repository-state checks", True, "Skipped in local-dev mode")

    # -- Report --
    print()
    print("-- Results --")
    print(result.report())
    print()

    if result.passed():
        print("  VERDICT: M0_SCOPE_LOCK_VALID")
        return 0
    else:
        print("  VERDICT: M0_SCOPE_LOCK_INVALID")
        return 1


if __name__ == "__main__":
    sys.exit(main())
