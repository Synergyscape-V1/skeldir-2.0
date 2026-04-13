#!/usr/bin/env python3
"""B2.1-P1 semantic/replay lock enforcement."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
TASK_FILE = "backend/app/tasks/attribution.py"
SEMANTICS_FILE = "backend/app/attribution/semantics.py"
RUNTIME_PROOF_FILE = "backend/tests/integration/test_b21_p1_semantic_replay_runtime.py"
WORKFLOW_FILE = ".github/workflows/ci.yml"
REQUIRED_CHECKS_FILE = "contracts-internal/governance/b03_phase2_required_status_checks.main.json"
REQUIRED_CONTEXT = "B2.1-P1 Semantic Replay Lock"


def _resolve(repo_root: Path, raw: str) -> Path:
    value = Path(raw)
    if value.is_absolute():
        return value
    return (repo_root / value).resolve()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(_read_text(path))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON payload must be an object: {path}")
    return payload


def run_enforcement(
    *,
    repo_root: Path,
    task_file: Path,
    semantics_file: Path,
    runtime_proof_file: Path,
    workflow_file: Path,
    required_checks_file: Path,
) -> tuple[int, list[str]]:
    violations: list[str] = []

    required_files = (
        task_file,
        semantics_file,
        runtime_proof_file,
        workflow_file,
        required_checks_file,
    )
    for file_path in required_files:
        if not file_path.exists():
            violations.append(f"missing_required_file:{file_path}")
    if violations:
        return 1, violations

    task_text = _read_text(task_file)
    semantics_text = _read_text(semantics_file)
    runtime_text = _read_text(runtime_proof_file)
    workflow_text = _read_text(workflow_file)
    required_checks = _read_json(required_checks_file)

    required_semantics_tokens = (
        "ATTRIBUTION_SEMANTICS_VERSION = \"b2.1-p1-v1\"",
        "DETERMINISTIC_DEFAULT_LOOKBACK_DAYS = 30",
        "TOUCHPOINT_EVENT_TYPES",
        "CONVERSION_EVENT_TYPES",
        "class AttributionInputRow",
        "class AttributionOutputRow",
        "class DeterministicReplayIdentity",
        "replay_event_created_ceiling",
    )
    for token in required_semantics_tokens:
        if token not in semantics_text:
            violations.append(f"semantics_missing_token:{token}")

    required_task_tokens = (
        "normalize_lookback_days(",
        "ATTRIBUTION_DETERMINISTIC_DEFAULT_LOOKBACK_DAYS",
        "compute_effective_replay_window(",
        "lower(trim(e.event_type)) = ANY(:conversion_event_types)",
        "sa.issued_at < :replay_window_end",
        "sa.expires_at > :replay_window_start",
        "e.created_at <= :replay_event_created_ceiling",
        "replay_identity = DeterministicReplayIdentity(",
        "replay_event_created_ceiling=datetime.now(timezone.utc)",
        "job_model_version = replay_identity.job_model_version()",
        "model_version=job_model_version",
    )
    for token in required_task_tokens:
        if token not in task_text:
            violations.append(f"task_missing_token:{token}")

    forbidden_task_tokens = (
        "sa.expires_at > :authority_now",
    )
    for token in forbidden_task_tokens:
        if token in task_text:
            violations.append(f"task_forbidden_token_present:{token}")

    required_runtime_tokens = (
        "test_b21_p1_runtime_conversion_taxonomy_excludes_touchpoint_rows",
        "test_b21_p1_runtime_historical_replay_uses_persisted_session_facts_not_wall_clock",
        "test_b21_p1_runtime_default_30_day_lookback_and_replay_identity_partitioning",
        "test_b21_p1_runtime_replay_identity_freezes_late_arriving_historical_events",
        "lookback_days=90",
        "job_model_version",
        "replay_event_created_ceiling",
    )
    for token in required_runtime_tokens:
        if token not in runtime_text:
            violations.append(f"runtime_proof_missing_token:{token}")

    required_workflow_tokens = (
        "Enforce B2.1-P1 semantic replay lock",
        "Run B2.1-P1 semantic replay lock negative controls",
        "name: B2.1-P1 Semantic Replay Lock",
        "Run B2.1-P1 runtime semantic replay proofs",
        "pytest backend/tests/integration/test_b21_p1_semantic_replay_runtime.py -q",
    )
    for token in required_workflow_tokens:
        if token not in workflow_text:
            violations.append(f"workflow_missing_token:{token}")

    required_contexts = required_checks.get("required_contexts", [])
    if not isinstance(required_contexts, list):
        violations.append("required_checks_required_contexts_invalid")
    elif REQUIRED_CONTEXT not in required_contexts:
        violations.append("required_checks_missing_b21_p1_context")

    return (1 if violations else 0), violations


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Enforce B2.1-P1 canonical semantic replay lock."
    )
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--task-file", default=TASK_FILE)
    parser.add_argument("--semantics-file", default=SEMANTICS_FILE)
    parser.add_argument("--runtime-proof-file", default=RUNTIME_PROOF_FILE)
    parser.add_argument("--workflow-file", default=WORKFLOW_FILE)
    parser.add_argument("--required-checks-file", default=REQUIRED_CHECKS_FILE)
    parser.add_argument("--simulate-regression", action="store_true")
    args = parser.parse_args(argv[1:])

    if args.simulate_regression:
        sys.stdout.write(
            "b21_p1_semantic_replay_lock_enforcer\n"
            "result=FAIL\n"
            "synthetic_regression=forced_failure_path\n"
        )
        return 1

    repo_root = _resolve(REPO_ROOT, args.repo_root)
    status, violations = run_enforcement(
        repo_root=repo_root,
        task_file=_resolve(repo_root, args.task_file),
        semantics_file=_resolve(repo_root, args.semantics_file),
        runtime_proof_file=_resolve(repo_root, args.runtime_proof_file),
        workflow_file=_resolve(repo_root, args.workflow_file),
        required_checks_file=_resolve(repo_root, args.required_checks_file),
    )
    lines = ["b21_p1_semantic_replay_lock_enforcer"]
    if status != 0:
        lines.append("result=FAIL")
        lines.extend(violations)
    else:
        lines.append("result=PASS")
        lines.append("enforcement=canonical_input_semantics_and_replay_identity_locked")
    sys.stdout.write("\n".join(lines) + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
