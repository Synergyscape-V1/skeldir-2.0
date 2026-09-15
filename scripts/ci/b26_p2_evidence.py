#!/usr/bin/env python3
"""Shared producer-side evidence-cell construction for B2.6-P2."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
PHASE = "B2.6-P2"


class EvidenceError(RuntimeError):
    """Raised when exact candidate evidence cannot be constructed."""


def canonical_json(document: Mapping[str, Any]) -> bytes:
    return json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _run(*command: str) -> str:
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def git_identity() -> tuple[str, str]:
    return _run("git", "rev-parse", "HEAD"), _run("git", "rev-parse", "HEAD^{tree}")


def migration_head() -> str:
    output = _run(sys.executable, "-m", "alembic", "heads")
    heads = {
        match.group(1)
        for line in output.splitlines()
        if (match := re.match(r"^([0-9a-f]+)\b", line.strip()))
    }
    if len(heads) != 1:
        raise EvidenceError(f"b26_p2_expected_one_migration_head:{sorted(heads)}")
    return next(iter(heads))


def scope_policy_identity() -> dict[str, str]:
    sys.path.insert(0, str(BACKEND))
    from app.finance_reconciliation.scope_authority import (  # noqa: PLC0415
        scope_policy_identity as identity,
    )

    return identity().__dict__


def build_evidence_cell(
    *,
    gate_id: str,
    producer: str,
    scenario_id: str,
    falsifier_id: str,
    details: Mapping[str, Any],
    status: str = "PASS",
    event_type: str | None = None,
    run_id: str | None = None,
    workflow: str | None = None,
) -> dict[str, Any]:
    sha, tree = git_identity()
    expected_sha = os.environ.get("B26_CANDIDATE_SHA", sha).strip()
    if expected_sha != sha:
        raise EvidenceError(
            f"b26_p2_checkout_candidate_mismatch:expected={expected_sha}:actual={sha}"
        )
    contract = scope_policy_identity()
    payload: dict[str, Any] = {
        "gate_id": gate_id,
        "phase": PHASE,
        "contract_version": contract["scope_policy_version"],
        "contract_hash": contract["source_sha256"],
        "candidate_sha": sha,
        "candidate_tree": tree,
        "migration_head": migration_head(),
        "producer": producer,
        "workflow": workflow or os.environ.get("GITHUB_WORKFLOW", "local"),
        "event_type": event_type
        or os.environ.get("B26_EVENT_TYPE")
        or os.environ.get("GITHUB_EVENT_NAME", "local"),
        "run_id": run_id or os.environ.get("GITHUB_RUN_ID", "local"),
        "scenario_id": scenario_id,
        "falsifier_id": falsifier_id,
        "status": status,
        "details": dict(details),
    }
    payload["artifact_hash"] = hashlib.sha256(canonical_json(payload)).hexdigest()
    return payload


def write_evidence_cell(path: Path, **kwargs: Any) -> dict[str, Any]:
    cell = build_evidence_cell(**kwargs)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cell, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return cell
