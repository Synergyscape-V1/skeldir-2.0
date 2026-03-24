#!/usr/bin/env python3
"""B1.5-P0 authority/scope/invariant enforcement.

This enforcer provides present-tense governance checks for B1.5-P0:
- Artifact coherence (authority lock, scope lock, invariant lock, phase-start marker).
- Non-vacuous realtime import fence for B1.5 decision surfaces.

The checks are intentionally narrow and manifest-driven.
"""

from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_NAME = "scripts/ci/enforce_b15_p0_authority_scope_invariants.py"
KNOWN_ENFORCED_NOW = {
    "b15_p0_artifact_coherence_check",
    "b15_p0_realtime_import_fence",
}
IMPORT_RE = re.compile(r"^\s*import(?:[\s\w{},*]+from\s+)?['\"]([^'\"]+)['\"]")
DYNAMIC_IMPORT_RE = re.compile(r"import\(\s*['\"]([^'\"]+)['\"]\s*\)")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_path(repo_root: Path, raw: str) -> Path:
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate
    return (repo_root / candidate).resolve()


def _expand_surface_glob(repo_root: Path, pattern: str) -> list[Path]:
    candidate = Path(pattern)
    if candidate.is_absolute():
        pattern_text = str(candidate)
    else:
        pattern_text = str((repo_root / candidate).resolve())

    matches = [Path(p).resolve() for p in glob.glob(pattern_text, recursive=True)]
    if matches:
        return sorted({p for p in matches if p.is_file()})

    candidate_resolved = _resolve_path(repo_root, pattern)
    if candidate_resolved.exists() and candidate_resolved.is_file():
        return [candidate_resolved]
    return []


def _collect_imports(path: Path) -> list[tuple[int, str]]:
    imports: list[tuple[int, str]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        static_match = IMPORT_RE.search(line)
        if static_match:
            imports.append((line_no, static_match.group(1)))
        for dynamic_match in DYNAMIC_IMPORT_RE.finditer(line):
            imports.append((line_no, dynamic_match.group(1)))
    return imports


def _matches_pattern(import_target: str, pattern: str) -> bool:
    normalized_target = import_target.replace("\\", "/")
    normalized_pattern = pattern.replace("\\", "/")
    if normalized_target == normalized_pattern:
        return True
    tail = normalized_pattern.lstrip("./")
    return normalized_target.endswith(tail)


def run_enforcement(
    *,
    repo_root: Path,
    authority_file: Path,
    scope_file: Path,
    invariant_file: Path,
    realtime_exception_file: Path,
    phase_start_file: Path,
) -> tuple[int, list[str]]:
    violations: list[str] = []

    required_files = (
        authority_file,
        scope_file,
        invariant_file,
        realtime_exception_file,
        phase_start_file,
    )
    for required in required_files:
        if not required.exists():
            violations.append(f"missing_file:{required}")
    if violations:
        return 1, violations

    authority = _read_json(authority_file)
    scope = _read_json(scope_file)
    invariant = _read_json(invariant_file)
    realtime = _read_json(realtime_exception_file)
    phase_start = _read_json(phase_start_file)

    if authority.get("phase") != "B1.5-P0":
        violations.append("authority_invalid_phase")
    if authority.get("authoritative_branch") != "main":
        violations.append("authority_invalid_authoritative_branch")
    if authority.get("authoritative_remote") != "origin/main":
        violations.append("authority_invalid_authoritative_remote")
    if not authority.get("evidence_requirements", {}).get("must_anchor_to_main_truth", False):
        violations.append("authority_missing_main_truth_requirement")

    if authority.get("phase_start_marker_file") != "contracts-internal/governance/b15_p0_phase_start.main.json":
        violations.append("authority_phase_start_marker_mismatch")
    if scope.get("realtime_exception_contract") != "contracts-internal/governance/b15_p0_realtime_exceptions.main.json":
        violations.append("scope_realtime_exception_contract_mismatch")

    if phase_start.get("phase") != "B1.5-P0":
        violations.append("phase_start_invalid_phase")
    inherits = phase_start.get("inherits", {})
    if inherits.get("phase") != "B1.4" or inherits.get("status") != "closed":
        violations.append("phase_start_invalid_inheritance")
    if inherits.get("reopen_allowed", True):
        violations.append("phase_start_reopen_allowed_true")

    invariants = invariant.get("invariants")
    if not isinstance(invariants, list) or not invariants:
        violations.append("invariant_manifest_missing_invariants")
        return 1, violations

    invariant_ids = set()
    enforced_now_from_rows: set[str] = set()
    for item in invariants:
        if not isinstance(item, dict):
            violations.append("invariant_manifest_row_not_object")
            continue
        invariant_id = item.get("invariant_id")
        if not invariant_id:
            violations.append("invariant_missing_id")
            continue
        invariant_ids.add(invariant_id)
        if item.get("enforcement_status") == "enforced_now":
            surface = str(item.get("enforcement_surface", ""))
            if not surface:
                violations.append(f"invariant_missing_enforcement_surface:{invariant_id}")
            if "b15_p0_" not in surface:
                violations.append(f"invariant_enforced_now_surface_not_b15_p0:{invariant_id}")
            if "artifact_coherence_check" in surface:
                enforced_now_from_rows.add("b15_p0_artifact_coherence_check")
            if "realtime_import_fence" in surface:
                enforced_now_from_rows.add("b15_p0_realtime_import_fence")

    declared_enforced_now = set(invariant.get("enforced_now_checks", []))
    if not declared_enforced_now:
        violations.append("invariant_manifest_no_enforced_now_checks")
    unknown = declared_enforced_now - KNOWN_ENFORCED_NOW
    if unknown:
        violations.append(f"invariant_manifest_unknown_enforced_now:{sorted(unknown)}")
    if declared_enforced_now != enforced_now_from_rows:
        violations.append("invariant_manifest_enforced_now_mismatch")

    exceptions = realtime.get("exceptions")
    active_realtime_present = bool(realtime.get("active_realtime_substrate_present", True))
    if not isinstance(exceptions, list):
        violations.append("realtime_exception_manifest_invalid_exceptions_shape")
        return 1, violations
    if active_realtime_present and not exceptions:
        violations.append("realtime_exception_manifest_empty_with_active_realtime_true")
        return 1, violations
    if not active_realtime_present and exceptions:
        violations.append("realtime_exception_manifest_has_exceptions_while_active_realtime_false")
        return 1, violations

    forbidden_patterns: list[str] = []
    for exception in exceptions:
        if not isinstance(exception, dict):
            violations.append("realtime_exception_row_not_object")
            continue
        surface_path = exception.get("surface_path")
        if not surface_path:
            violations.append("realtime_exception_missing_surface_path")
            continue
        resolved_surface = _resolve_path(repo_root, str(surface_path))
        if not resolved_surface.exists():
            violations.append(f"realtime_exception_surface_missing:{surface_path}")
        if exception.get("allowed_for_b15_decision_surfaces", True):
            violations.append(f"realtime_exception_allowed_for_b15_true:{surface_path}")
        patterns = exception.get("forbidden_import_patterns", [])
        if not isinstance(patterns, list) or not patterns:
            violations.append(f"realtime_exception_missing_forbidden_patterns:{surface_path}")
            continue
        forbidden_patterns.extend(str(p) for p in patterns)

    scope_patterns = scope.get("forbidden_realtime_dependency_patterns", [])
    if not isinstance(scope_patterns, list) or not scope_patterns:
        violations.append("scope_missing_forbidden_realtime_dependency_patterns")
    else:
        forbidden_patterns.extend(str(p) for p in scope_patterns)

    decision_surface_globs = scope.get("decision_surface_globs", [])
    if not isinstance(decision_surface_globs, list) or not decision_surface_globs:
        violations.append("scope_missing_decision_surface_globs")
        return 1, violations

    decision_files: set[Path] = set()
    for pattern in decision_surface_globs:
        decision_files.update(_expand_surface_glob(repo_root, str(pattern)))
    if not decision_files:
        violations.append("scope_decision_surface_globs_resolved_to_zero_files")
        return 1, violations

    dedup_patterns = sorted(set(forbidden_patterns))
    for file_path in sorted(decision_files):
        for line_no, import_target in _collect_imports(file_path):
            for pattern in dedup_patterns:
                if _matches_pattern(import_target, pattern):
                    try:
                        rel = file_path.resolve().relative_to(repo_root.resolve())
                    except ValueError:
                        rel = file_path.resolve()
                    violations.append(
                        f"forbidden_realtime_import:{rel}:{line_no}:{import_target}"
                    )

    return (1 if violations else 0), violations


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="B1.5-P0 authority/scope/invariant enforcer")
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument(
        "--authority-file",
        default="contracts-internal/governance/b15_p0_authority_lock.main.json",
    )
    parser.add_argument(
        "--scope-file",
        default="contracts-internal/governance/b15_p0_scope_lock.main.json",
    )
    parser.add_argument(
        "--invariant-file",
        default="contracts-internal/governance/b15_p0_invariant_lock.main.json",
    )
    parser.add_argument(
        "--realtime-exception-file",
        default="contracts-internal/governance/b15_p0_realtime_exceptions.main.json",
    )
    parser.add_argument(
        "--phase-start-file",
        default="contracts-internal/governance/b15_p0_phase_start.main.json",
    )
    parser.add_argument("--simulate-regression", action="store_true")
    args = parser.parse_args(argv[1:])

    if args.simulate_regression:
        sys.stdout.write(
            "b15_p0_authority_scope_invariants_enforcer\n"
            "result=FAIL\n"
            "synthetic_regression=forced_failure_path\n"
        )
        return 1

    repo_root = _resolve_path(REPO_ROOT, args.repo_root)
    status, violations = run_enforcement(
        repo_root=repo_root,
        authority_file=_resolve_path(repo_root, args.authority_file),
        scope_file=_resolve_path(repo_root, args.scope_file),
        invariant_file=_resolve_path(repo_root, args.invariant_file),
        realtime_exception_file=_resolve_path(repo_root, args.realtime_exception_file),
        phase_start_file=_resolve_path(repo_root, args.phase_start_file),
    )

    lines = ["b15_p0_authority_scope_invariants_enforcer"]
    if status != 0:
        lines.append("result=FAIL")
        lines.extend(violations)
    else:
        lines.append("result=PASS")
        lines.append("enforcement=authority_scope_invariant_lock_verified")

    sys.stdout.write("\n".join(lines) + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
