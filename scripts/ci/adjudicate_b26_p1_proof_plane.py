#!/usr/bin/env python3
"""Independently adjudicate content-addressed B2.6-P1 evidence cells."""

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
REQUIREMENTS = REPO_ROOT / "contracts/reconciliation/b2.6/proof-requirements.v1.yaml"


class AdjudicationError(RuntimeError):
    """A proof cell is absent, stale, malformed, or bound to the wrong run."""


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


def _contract_identity() -> dict[str, str]:
    sys.path.insert(0, str(BACKEND))
    from app.finance_reconciliation.semantic_contract import (  # noqa: PLC0415
        semantic_contract_identity,
    )

    return semantic_contract_identity().__dict__


def _load_cells(root: Path) -> dict[str, dict[str, Any]]:
    cells: dict[str, dict[str, Any]] = {}
    for path in sorted(root.rglob("*.json")):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AdjudicationError(f"malformed_artifact:{path}:{exc}") from exc
        if not isinstance(document, dict) or "gate_id" not in document:
            raise AdjudicationError(f"unrecognized_artifact:{path}")
        gate_id = str(document["gate_id"])
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
    additional_cells = {
        cell["gate_id"]: cell
        for cell in requirements.get("additional_accepted_cells", [])
        if isinstance(cell, dict) and "gate_id" in cell
    }
    registered_cells = {**required_cells, **additional_cells}
    observed = _load_cells(artifact_root)
    # Governed extension law (Corrective II-2): permanent P1 cells stay
    # mandatory, and an additional cell registered with `required: true`
    # becomes mandatory for the current phase. Missing either is RED;
    # unregistered evidence is RED (fail-closed).
    required_additional = sorted(
        gate_id
        for gate_id, cell in additional_cells.items()
        if cell.get("required") is True
    )
    missing = sorted(set(required_cells) - set(observed))
    missing_required_additional = sorted(set(required_additional) - set(observed))
    if missing or missing_required_additional:
        raise AdjudicationError(
            f"proof_cell_census_mismatch:missing={missing}:"
            f"missing_required_additional={missing_required_additional}:unexpected=[]"
        )
    unregistered = sorted(set(observed) - set(registered_cells))
    if unregistered:
        raise AdjudicationError(
            f"proof_cell_census_mismatch:missing=[]:unexpected={unregistered}"
        )

    contract = _contract_identity()
    migration = _migration_head()
    accepted_fields = set(requirements["required_identity_fields"])
    hashes: dict[str, str] = {}
    for gate_id in sorted(observed):
        expected = registered_cells[gate_id]
        cell = observed[gate_id]
        absent_fields = sorted(accepted_fields - set(cell))
        if absent_fields:
            raise AdjudicationError(
                f"proof_cell_fields_missing:{gate_id}:{absent_fields}"
            )
        if cell["phase"] != requirements["phase"]:
            raise AdjudicationError(f"proof_cell_phase_mismatch:{gate_id}")
        if "producer" in expected and cell["producer"] != expected["producer"]:
            raise AdjudicationError(f"proof_cell_producer_mismatch:{gate_id}")
        if "scenario_id" in expected and cell["scenario_id"] != expected["scenario_id"]:
            raise AdjudicationError(f"proof_cell_scenario_mismatch:{gate_id}")
        if (
            "falsifier_id" in expected
            and cell["falsifier_id"] != expected["falsifier_id"]
        ):
            raise AdjudicationError(f"proof_cell_falsifier_mismatch:{gate_id}")
        if cell["status"] != requirements["accepted_status"]:
            raise AdjudicationError(f"proof_cell_not_pass:{gate_id}:{cell['status']}")
        if cell["candidate_sha"] != candidate_sha:
            raise AdjudicationError(f"proof_cell_candidate_sha_mismatch:{gate_id}")
        if cell["candidate_tree"] != candidate_tree:
            raise AdjudicationError(f"proof_cell_candidate_tree_mismatch:{gate_id}")
        if cell["contract_version"] != contract["contract_version"]:
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
            key: value
            for key, value in cell.items()
            if key not in {"artifact_hash", "_path"}
        }
        actual_hash = hashlib.sha256(_canonical_json(unhashed)).hexdigest()
        if claimed_hash != actual_hash:
            raise AdjudicationError(f"proof_cell_artifact_hash_mismatch:{gate_id}")
        hashes[gate_id] = actual_hash

    inherited = observed["B26-P1-G1-G2-INHERITED-PHYSICS"]["details"]
    required_jobs = inherited.get("required_jobs", {})
    if set(required_jobs) != set(requirements["required_inherited_jobs"]):
        raise AdjudicationError("inherited_physics_subordinate_job_census_mismatch")
    if any(value != "success" for value in required_jobs.values()):
        raise AdjudicationError("inherited_physics_subordinate_job_not_success")
    via = str(inherited.get("source_via", "direct-same-sha"))
    if via.startswith("merge-tip-tree-identical:"):
        # The attester emits this marker only after API-verified merge-tree
        # == PR-tip-tree equality, so the tip's pull_request run is evidence
        # about byte-identical bytes. Accept it only when the evidence cell
        # itself names this candidate (candidate_sha binding preserved) and
        # only for this marker (no other exception applies).
        if inherited.get("candidate_sha") != candidate_sha:
            raise AdjudicationError("inherited_physics_candidate_identity_mismatch")
    else:
        if inherited.get("source_event") != event_type:
            raise AdjudicationError("inherited_physics_event_identity_mismatch")
        if inherited.get("source_sha") != candidate_sha:
            raise AdjudicationError("inherited_physics_candidate_identity_mismatch")

    capsule: dict[str, Any] = {
        "phase": requirements["phase"],
        "status": "PASS",
        "candidate_sha": candidate_sha,
        "candidate_tree": candidate_tree,
        "contract_version": contract["contract_version"],
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
        print("B26_P1_PROOF_PLANE_FAIL candidate_checkout_identity_mismatch")
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
        print(f"B26_P1_PROOF_PLANE_FAIL {exc}")
        return 1
    if args.capsule_out:
        args.capsule_out.parent.mkdir(parents=True, exist_ok=True)
        args.capsule_out.write_text(
            json.dumps(capsule, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print("B26_P1_PROOF_PLANE_PASS")
    print(json.dumps(capsule, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
