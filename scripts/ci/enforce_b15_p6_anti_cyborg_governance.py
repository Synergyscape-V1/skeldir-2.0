#!/usr/bin/env python3
"""B1.5-P6 anti-cyborg governance lock and realtime exception fencing."""

from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]


def _resolve(repo_root: Path, raw: str) -> Path:
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate
    return (repo_root / candidate).resolve()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_rel(path_text: str) -> str:
    return path_text.replace("\\", "/")


def _parse_iso_date(raw: str) -> date | None:
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _run_graph_guard(
    *,
    repo_root: Path,
    graph_script_file: Path,
    matrix_file: Path,
    registry_file: Path,
    tsconfig_file: Path,
) -> tuple[int, list[dict[str, Any]], str]:
    command = [
        "node",
        str(graph_script_file),
        "--repo-root",
        str(repo_root),
        "--matrix-file",
        str(matrix_file),
        "--registry-file",
        str(registry_file),
        "--tsconfig-file",
        str(tsconfig_file),
    ]
    result = subprocess.run(
        command,
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        details = (result.stdout or "") + "\n" + (result.stderr or "")
        return 1, [], f"graph_guard_execution_failed:{details.strip()}"
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return 1, [], f"graph_guard_invalid_json:{exc}"
    violations = payload.get("violations", [])
    if not isinstance(violations, list):
        return 1, [], "graph_guard_invalid_violations_shape"
    normalized_violations = [
        item for item in violations if isinstance(item, dict)
    ]
    return 0, normalized_violations, ""


def _validate_override_entry(entry: dict[str, Any], *, today: date) -> list[str]:
    issues: list[str] = []
    override_id = str(entry.get("override_id", "")).strip()
    if not override_id:
        issues.append("override_missing_override_id")
    if str(entry.get("status", "")).strip() != "active":
        issues.append(f"override_not_active:{override_id or 'unknown'}")
    ticket = str(entry.get("ticket", "")).strip()
    if not ticket:
        issues.append(f"override_missing_ticket:{override_id or 'unknown'}")
    approved_by = entry.get("approved_by")
    if not isinstance(approved_by, list) or not approved_by:
        issues.append(f"override_missing_approved_by:{override_id or 'unknown'}")

    expires_raw = str(entry.get("expires_on", "")).strip()
    expires_on = _parse_iso_date(expires_raw)
    if expires_on is None:
        issues.append(f"override_invalid_expires_on:{override_id or 'unknown'}")
    elif expires_on < today:
        issues.append(f"override_expired:{override_id or 'unknown'}:{expires_raw}")

    globs = entry.get("decision_surface_globs")
    if not isinstance(globs, list) or not globs:
        issues.append(f"override_missing_decision_surface_globs:{override_id or 'unknown'}")

    violation_ids = entry.get("allowed_violation_ids")
    if not isinstance(violation_ids, list) or not violation_ids:
        issues.append(f"override_missing_allowed_violation_ids:{override_id or 'unknown'}")

    justification = str(entry.get("justification", "")).strip()
    if not justification:
        issues.append(f"override_missing_justification:{override_id or 'unknown'}")

    return issues


def _violation_id(violation: dict[str, Any]) -> str:
    violation_type = str(violation.get("type", ""))
    if violation_type == "forbidden_signature":
        return str(violation.get("signature_id", ""))
    if violation_type == "realtime_import_fence":
        return f"import_fence:{violation.get('exception_id', '')}"
    if violation_type == "contract_violation":
        return str(violation.get("violation_id", ""))
    return ""


def _override_matches_violation(
    *,
    override: dict[str, Any],
    violation: dict[str, Any],
) -> bool:
    violation_id = _violation_id(violation)
    if not violation_id:
        return False

    allowed_ids = [str(item) for item in override.get("allowed_violation_ids", [])]
    if violation_id not in allowed_ids:
        return False

    violation_file = _normalize_rel(str(violation.get("file", "")))
    patterns = [_normalize_rel(str(item)) for item in override.get("decision_surface_globs", [])]
    if not patterns:
        return False
    return any(fnmatch.fnmatch(violation_file, pattern) for pattern in patterns)


def run_enforcement(
    *,
    repo_root: Path,
    registry_file: Path,
    matrix_file: Path,
    overrides_file: Path,
    graph_script_file: Path,
    tsconfig_file: Path,
) -> tuple[int, list[str]]:
    violations: list[str] = []
    required_files = (
        registry_file,
        matrix_file,
        overrides_file,
        graph_script_file,
        tsconfig_file,
    )
    missing = [path for path in required_files if not path.exists()]
    if missing:
        return 1, [f"missing_file:{path}" for path in missing]

    registry = _read_json(registry_file)
    matrix = _read_json(matrix_file)
    overrides = _read_json(overrides_file)

    if registry.get("phase") != "B1.5-P6":
        violations.append("registry_invalid_phase")
    if matrix.get("phase") != "B1.5-P6":
        violations.append("matrix_invalid_phase")
    if overrides.get("phase") != "B1.5-P6":
        violations.append("overrides_invalid_phase")

    if not overrides.get("deny_by_default", False):
        violations.append("overrides_deny_by_default_must_be_true")

    exception_rows = registry.get("exceptions")
    if not isinstance(exception_rows, list) or not exception_rows:
        violations.append("registry_missing_exceptions")
        return 1, violations

    exception_ids: set[str] = set()
    for row in exception_rows:
        if not isinstance(row, dict):
            violations.append("registry_exception_row_not_object")
            continue
        exception_id = str(row.get("exception_id", "")).strip()
        if not exception_id:
            violations.append("registry_exception_missing_id")
            continue
        exception_ids.add(exception_id)
        if row.get("allowed_for_b15_decision_surfaces", True):
            violations.append(f"registry_exception_allowed_for_b15_true:{exception_id}")
        surface_files = row.get("exception_surface_files")
        if not isinstance(surface_files, list) or not surface_files:
            violations.append(f"registry_exception_missing_surface_files:{exception_id}")
            continue
        for raw_surface in surface_files:
            surface_path = _resolve(repo_root, str(raw_surface))
            if not surface_path.exists():
                violations.append(
                    f"registry_exception_surface_missing:{exception_id}:{raw_surface}"
                )

    signature_rows = matrix.get("forbidden_signatures")
    if not isinstance(signature_rows, list) or not signature_rows:
        violations.append("matrix_missing_forbidden_signatures")
    else:
        for row in signature_rows:
            if not isinstance(row, dict):
                violations.append("matrix_signature_row_not_object")
                continue
            signature_id = str(row.get("signature_id", "")).strip()
            kind = str(row.get("kind", "")).strip()
            match = str(row.get("match", "")).strip()
            if not signature_id:
                violations.append("matrix_signature_missing_id")
            if not kind:
                violations.append(f"matrix_signature_missing_kind:{signature_id}")
            if not match:
                violations.append(f"matrix_signature_missing_match:{signature_id}")

    decision_roots = matrix.get("decision_surface_roots")
    decision_files = matrix.get("decision_surface_files")
    if not isinstance(decision_roots, list) or not isinstance(decision_files, list):
        violations.append("matrix_decision_surface_shape_invalid")
    elif not decision_roots and not decision_files:
        violations.append("matrix_decision_surfaces_empty")

    baseline_approvals = overrides.get("baseline_exception_approvals")
    if not isinstance(baseline_approvals, list) or not baseline_approvals:
        violations.append("overrides_missing_baseline_exception_approvals")
    else:
        baseline_ids = {
            str(item.get("exception_id", "")).strip()
            for item in baseline_approvals
            if isinstance(item, dict)
        }
        if baseline_ids != exception_ids:
            violations.append("overrides_baseline_exception_alignment_mismatch")

    today = date.today()
    active_overrides = overrides.get("active_overrides", [])
    if not isinstance(active_overrides, list):
        violations.append("overrides_active_overrides_not_list")
        active_overrides = []
    for item in active_overrides:
        if not isinstance(item, dict):
            violations.append("override_row_not_object")
            continue
        violations.extend(_validate_override_entry(item, today=today))

    if violations:
        return 1, violations

    graph_status, graph_violations, graph_error = _run_graph_guard(
        repo_root=repo_root,
        graph_script_file=graph_script_file,
        matrix_file=matrix_file,
        registry_file=registry_file,
        tsconfig_file=tsconfig_file,
    )
    if graph_status != 0:
        return 1, [graph_error]

    unresolved: list[str] = []
    overrides_used: list[str] = []
    for graph_violation in graph_violations:
        violation_type = str(graph_violation.get("type", ""))
        violation_id = _violation_id(graph_violation)
        if violation_type == "contract_violation":
            unresolved.append(
                f"graph_contract_violation:{violation_id}:{graph_violation.get('file', '')}"
            )
            continue

        matched_override = False
        for override in active_overrides:
            if not isinstance(override, dict):
                continue
            if _override_matches_violation(override=override, violation=graph_violation):
                matched_override = True
                overrides_used.append(str(override.get("override_id", "unknown")))
                break
        if not matched_override:
            unresolved.append(
                "deny_by_default_blocked:"
                f"{violation_id}:"
                f"{graph_violation.get('file', '')}:"
                f"{violation_type}"
            )

    if unresolved:
        return 1, unresolved

    return 0, sorted(set(f"override_applied:{item}" for item in overrides_used))


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="B1.5-P6 anti-cyborg governance lock enforcer"
    )
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument(
        "--registry-file",
        default="contracts-internal/governance/b15_p6_realtime_exception_registry.main.json",
    )
    parser.add_argument(
        "--matrix-file",
        default="contracts-internal/governance/b15_p6_prohibited_signature_matrix.main.json",
    )
    parser.add_argument(
        "--overrides-file",
        default="contracts-internal/governance/b15_p6_escalation_overrides.main.json",
    )
    parser.add_argument(
        "--graph-script-file",
        default="frontend/scripts/b15_p6_graph_guard.mjs",
    )
    parser.add_argument(
        "--tsconfig-file",
        default="frontend/tsconfig.json",
    )
    parser.add_argument("--simulate-regression", action="store_true")
    args = parser.parse_args(argv[1:])

    if args.simulate_regression:
        sys.stdout.write(
            "b15_p6_anti_cyborg_governance_enforcer\n"
            "result=FAIL\n"
            "synthetic_regression=forced_failure_path\n"
        )
        return 1

    repo_root = _resolve(REPO_ROOT, args.repo_root)
    status, details = run_enforcement(
        repo_root=repo_root,
        registry_file=_resolve(repo_root, args.registry_file),
        matrix_file=_resolve(repo_root, args.matrix_file),
        overrides_file=_resolve(repo_root, args.overrides_file),
        graph_script_file=_resolve(repo_root, args.graph_script_file),
        tsconfig_file=_resolve(repo_root, args.tsconfig_file),
    )

    lines = ["b15_p6_anti_cyborg_governance_enforcer"]
    if status != 0:
        lines.append("result=FAIL")
        lines.extend(details)
    else:
        lines.append("result=PASS")
        lines.append("enforcement=anti_cyborg_governance_lock_verified")
        lines.extend(details)
    sys.stdout.write("\n".join(lines) + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
