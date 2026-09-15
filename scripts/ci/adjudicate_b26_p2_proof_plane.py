#!/usr/bin/env python3
"""Adjudicate B2.6-P2 scope-authority evidence cells (subordinate artifact)."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

import yaml  # type: ignore[import-untyped]


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
REQUIREMENTS = REPO_ROOT / "contracts/reconciliation/b2.6/p2-proof-requirements.v1.yaml"


class AdjudicationError(RuntimeError):
    """A P2 proof cell is absent, stale, malformed, or bound to the wrong run."""


def _canonical_json(document: Mapping[str, Any]) -> bytes:
    return json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _git(*args: str) -> str:
    return subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _migration_head() -> str:
    output = subprocess.run(
        (sys.executable, "-m", "alembic", "heads"),
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    heads = {
        match.group(1)
        for line in output.splitlines()
        if (match := re.match(r"^([0-9a-f]+)\b", line.strip()))
    }
    if len(heads) != 1:
        raise AdjudicationError(f"expected_one_migration_head:{sorted(heads)}")
    return next(iter(heads))


def _scope_policy_identity() -> dict[str, str]:
    sys.path.insert(0, str(BACKEND))
    from app.finance_reconciliation.scope_authority import (  # noqa: PLC0415
        scope_policy_identity,
    )

    return scope_policy_identity().__dict__


def _load_cells(root: Path) -> dict[str, dict[str, Any]]:
    cells: dict[str, dict[str, Any]] = {}
    for path in sorted(root.rglob("*.json")):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise AdjudicationError(f"malformed_artifact:{path}:{exc}") from exc
        if not isinstance(document, dict) or "gate_id" not in document:
            raise AdjudicationError(f"unrecognized_artifact:{path}")
        gate_id = str(document["gate_id"])
        if not gate_id.startswith("B26-P2-"):
            continue
        if gate_id in cells:
            raise AdjudicationError(f"duplicate_gate_artifact:{gate_id}")
        document["_path"] = path.as_posix()
        cells[gate_id] = document
    return cells


def adjudicate(
    *,
    artifact_root: Path,
    candidate_sha: str,
    candidate_tree: str,
    event_type: str,
    run_id: str,
    workflow: str,
) -> dict[str, Any]:
    requirements = yaml.safe_load(REQUIREMENTS.read_text(encoding="utf-8"))
    required_cells = {cell["gate_id"]: cell for cell in requirements["required_cells"]}
    observed = _load_cells(artifact_root)
    missing = sorted(set(required_cells) - set(observed))
    if missing:
        raise AdjudicationError(f"proof_cell_census_mismatch:missing={missing}")
    contract = _scope_policy_identity()
    migration = _migration_head()
    accepted_fields = set(requirements["required_identity_fields"])
    hashes: dict[str, str] = {}
    for gate_id in sorted(observed):
        if gate_id not in required_cells:
            continue
        expected = required_cells[gate_id]
        cell = observed[gate_id]
        absent_fields = sorted(accepted_fields - set(cell))
        if absent_fields:
            raise AdjudicationError(f"proof_cell_fields_missing:{gate_id}:{absent_fields}")
        if cell["phase"] != requirements["phase"]:
            raise AdjudicationError(f"proof_cell_phase_mismatch:{gate_id}")
        if cell["producer"] != expected["producer"]:
            raise AdjudicationError(f"proof_cell_producer_mismatch:{gate_id}")
        if cell["scenario_id"] != expected["scenario_id"]:
            raise AdjudicationError(f"proof_cell_scenario_mismatch:{gate_id}")
        if cell["falsifier_id"] != expected["falsifier_id"]:
            raise AdjudicationError(f"proof_cell_falsifier_mismatch:{gate_id}")
        if cell["status"] != requirements["accepted_status"]:
            raise AdjudicationError(f"proof_cell_not_pass:{gate_id}:{cell['status']}")
        if cell["candidate_sha"] != candidate_sha:
            raise AdjudicationError(f"proof_cell_candidate_sha_mismatch:{gate_id}")
        if cell["candidate_tree"] != candidate_tree:
            raise AdjudicationError(f"proof_cell_candidate_tree_mismatch:{gate_id}")
        if cell["contract_version"] != contract["scope_policy_version"]:
            raise AdjudicationError(f"proof_cell_contract_version_mismatch:{gate_id}")
        if cell["contract_hash"] != contract["source_sha256"]:
            raise AdjudicationError(f"proof_cell_contract_hash_mismatch:{gate_id}")
        if cell["migration_head"] != migration:
            raise AdjudicationError(f"proof_cell_migration_head_mismatch:{gate_id}")
        if cell["event_type"] != event_type:
            raise AdjudicationError(f"proof_cell_event_mismatch:{gate_id}")
        if cell["event_type"] not in requirements["accepted_events"]:
            raise AdjudicationError(f"proof_cell_event_not_accepted:{gate_id}")
        if str(cell["run_id"]) != str(run_id):
            raise AdjudicationError(f"proof_cell_run_id_mismatch:{gate_id}")
        if cell["workflow"] != workflow:
            raise AdjudicationError(f"proof_cell_workflow_mismatch:{gate_id}")
        claimed_hash = cell["artifact_hash"]
        unhashed = {
            key: value for key, value in cell.items() if key not in {"artifact_hash", "_path"}
        }
        actual_hash = hashlib.sha256(_canonical_json(unhashed)).hexdigest()
        if claimed_hash != actual_hash:
            raise AdjudicationError(f"proof_cell_artifact_hash_mismatch:{gate_id}")
        hashes[gate_id] = actual_hash
    capsule: dict[str, Any] = {
        "phase": requirements["phase"],
        "status": "PASS",
        "candidate_sha": candidate_sha,
        "candidate_tree": candidate_tree,
        "contract_version": contract["scope_policy_version"],
        "contract_hash": contract["source_sha256"],
        "migration_head": migration,
        "workflow": workflow,
        "event_type": event_type,
        "run_id": run_id,
        "artifact_hashes": hashes,
    }
    capsule["capsule_hash"] = hashlib.sha256(_canonical_json(capsule)).hexdigest()
    return capsule


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", required=True, type=Path)
    parser.add_argument("--candidate-sha", default=os.environ.get("B26_CANDIDATE_SHA"))
    parser.add_argument("--candidate-tree")
    parser.add_argument("--event-type", default=os.environ.get("GITHUB_EVENT_NAME"))
    parser.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID"))
    parser.add_argument("--workflow", default=os.environ.get("GITHUB_WORKFLOW"))
    parser.add_argument("--capsule-out", type=Path)
    args = parser.parse_args()
    sha = args.candidate_sha or _git("rev-parse", "HEAD")
    tree = args.candidate_tree or _git("rev-parse", "HEAD^{tree}")
    if sha != _git("rev-parse", "HEAD") or tree != _git("rev-parse", "HEAD^{tree}"):
        print("B26_P2_PROOF_PLANE_FAIL candidate_checkout_identity_mismatch")
        return 1
    try:
        capsule = adjudicate(
            artifact_root=args.artifact_root,
            candidate_sha=sha,
            candidate_tree=tree,
            event_type=str(args.event_type),
            run_id=str(args.run_id),
            workflow=str(args.workflow),
        )
    except AdjudicationError as exc:
        print(f"B26_P2_PROOF_PLANE_FAIL {exc}")
        return 1
    if args.capsule_out:
        args.capsule_out.parent.mkdir(parents=True, exist_ok=True)
        args.capsule_out.write_text(
            json.dumps(capsule, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print("B26_P2_PROOF_PLANE_PASS")
    print(json.dumps(capsule, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
