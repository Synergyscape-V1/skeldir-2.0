#!/usr/bin/env python3
"""B2.6-P1 pristine -> defect RED -> exact restore -> GREEN battery."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
VALIDATOR = ROOT / "scripts/ci/validate_b26_p1_authority.py"
MUTATOR = ROOT / "scripts/ci/_b26_p1_controlled_defect.py"
CONTRACT = ROOT / "contracts/reconciliation/b2.6/semantic-authority.v1.yaml"
SEMANTIC_MODULE = ROOT / "backend/app/finance_reconciliation/semantic_contract.py"
COVERAGE_AUTHORITY_MODULE = ROOT / "backend/app/finance_reconciliation/coverage_authority.py"
CANONICAL_SINK_MODULE = ROOT / "backend/app/finance_reconciliation/canonical_sink.py"
PROOF_MANIFEST_MODULE = ROOT / "backend/app/finance_reconciliation/proof_manifest.py"
WORKFLOW = ROOT / ".github/workflows/b2_6-p1-finance-reconciliation-adjudication.yml"

STATIC_CONTROLS = (
    ("mandatory_semantic_element", CONTRACT, "semantic_contract_refused"),
    ("coverage_authority_reference", CONTRACT, "semantic_contract_refused"),
    ("legacy_false_authority_import", SEMANTIC_MODULE, "b26_false_authority_import"),
    ("ontological_authority", CONTRACT, "semantic_contract_refused"),
    ("workflow_execution_identity", WORKFLOW, "b26_required_context_event_identity_ambiguous"),
    ("reason_identity_substitution", CONTRACT, "semantic_contract_refused"),
    ("discrepancy_member_removal", CONTRACT, "semantic_contract_refused"),
    ("tenant_policy_weakening", CONTRACT, "semantic_contract_refused"),
    ("insertion_seam_corruption", CONTRACT, "semantic_contract_refused"),
    ("discrepancy_addition_without_version_bump", CONTRACT, "semantic_contract_refused"),
    ("unclassified_normative_field", CONTRACT, "b26_p1_unclassified_normative_field"),
    ("dynamic_legacy_import", SEMANTIC_MODULE, "b26_dynamic_false_authority_import"),
    (
        "legacy_network_client_in_canonical_surface",
        SEMANTIC_MODULE,
        "b26_legacy_network_client_in_canonical_surface",
    ),
    (
        "legacy_route_reference_in_canonical_surface",
        COVERAGE_AUTHORITY_MODULE,
        "b26_legacy_route_reference_in_canonical_surface",
    ),
    (
        "unregistered_coverage_origin",
        SEMANTIC_MODULE,
        "b26_unregistered_coverage_origin",
    ),
    (
        "tenant_authority_bypass",
        COVERAGE_AUTHORITY_MODULE,
        "coverage_tenant_authority_not_enforced",
    ),
    (
        "session_capability_injection",
        CANONICAL_SINK_MODULE,
        "canonical_executor_accepts_session_capability",
    ),
    (
        "final_field_override_permit",
        CANONICAL_SINK_MODULE,
        "canonical_adjunct_guard_not_enforced",
    ),
    (
        "successor_provenance_omission",
        CONTRACT,
        "semantic_contract_refused",
    ),
    (
        "unregistered_canonical_output",
        SEMANTIC_MODULE,
        "b26_unregistered_canonical_output",
    ),
    (
        "caller_tenant_injection",
        CANONICAL_SINK_MODULE,
        "canonical_executor_tenant_not_auth_bound",
    ),
    (
        "arbitrary_callback_injection",
        CANONICAL_SINK_MODULE,
        "canonical_executor_tenant_not_auth_bound",
    ),
    (
        "duplicate_sink_permit",
        CANONICAL_SINK_MODULE,
        "canonical_sink_duplicate_not_refused",
    ),
    (
        "successor_authorize_permit",
        CANONICAL_SINK_MODULE,
        "successor_provenance_law_not_enforced:authorize",
    ),
    (
        "fake_proof_tolerance",
        PROOF_MANIFEST_MODULE,
        "proof_manifest_required_set_not_enforced",
    ),
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _run(*command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _validator() -> subprocess.CompletedProcess[str]:
    return _run(sys.executable, str(VALIDATOR))


def _proof_identity_control() -> dict[str, Any]:
    from scripts.ci.adjudicate_b26_p1_proof_plane import (  # noqa: PLC0415
        AdjudicationError,
        adjudicate,
    )
    from scripts.ci.b26_p1_evidence import (  # noqa: PLC0415
        canonical_json,
        git_identity,
        write_evidence_cell,
    )

    sha, tree = git_identity()
    workflow = "B2.6-P1 Contract Authority, Semantic Freeze and Proof Plane"
    event = "pull_request"
    run_id = "negative-control-local"
    specs: tuple[tuple[str, str, str, str, dict[str, Any]], ...] = (
        (
            "B26-P1-G4-SEMANTIC-AUTHORITY",
            "b26-p1-static-authority",
            "semantic-authority-pristine",
            "B26-P1-NC-01-through-04",
            {},
        ),
        (
            "B26-P1-G8-EXECUTION-IDENTITY",
            "b26-p1-static-authority",
            "governing-workflow-pristine",
            "B26-P1-NC-05",
            {},
        ),
        (
            "B26-P1-G9-NEGATIVE-CONTROLS",
            "b26-p1-static-authority",
            "red-restore-green-ledger",
            "B26-P1-NC-01-through-06",
            {},
        ),
        (
            "B26-P1-G3-G10-CONTAINER-EQUIVALENCE",
            "b26-p1-container-equivalence",
            "candidate-production-image",
            "B26-P1-NC-07",
            {},
        ),
        (
            "B26-P1-G1-G2-INHERITED-PHYSICS",
            "b26-p1-inherited-conduction",
            "b25-p13-context-robust-production-closure",
            "inherited-C19-C20-C21-negative-controls",
            {
                "source_event": event,
                "source_sha": sha,
                "required_jobs": {
                    "B2.5-P13 C19 Context-Robust Production Closure": "success",
                    "B2.5-P13 C20 Verdict Authority Conservation": "success",
                    "B2.5-P13 C21 Freshness and Issuance Authority Conservation": "success",
                    "B2.5-P14 Downstream Projection Safety": "success",
                },
            },
        ),
    )
    with tempfile.TemporaryDirectory(prefix="b26-p1-proof-") as directory:
        root = Path(directory)
        for gate, producer, scenario, falsifier, details in specs:
            write_evidence_cell(
                root / f"{gate}.json",
                gate_id=gate,
                producer=producer,
                scenario_id=scenario,
                falsifier_id=falsifier,
                details=details,
                event_type=event,
                run_id=run_id,
                workflow=workflow,
            )
        adjudicate(
            artifact_root=root,
            candidate_sha=sha,
            candidate_tree=tree,
            event_type=event,
            run_id=run_id,
            workflow=workflow,
        )
        target = root / "B26-P1-G4-SEMANTIC-AUTHORITY.json"
        pristine = target.read_bytes()
        cell = json.loads(pristine)
        cell["candidate_sha"] = "0" * 40
        unhashed = {key: value for key, value in cell.items() if key != "artifact_hash"}
        cell["artifact_hash"] = hashlib.sha256(canonical_json(unhashed)).hexdigest()
        target.write_text(json.dumps(cell, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        try:
            adjudicate(
                artifact_root=root,
                candidate_sha=sha,
                candidate_tree=tree,
                event_type=event,
                run_id=run_id,
                workflow=workflow,
            )
        except AdjudicationError as exc:
            observed_red = str(exc)
        else:
            raise RuntimeError("proof_identity_control_did_not_turn_red")
        target.write_bytes(pristine)
        adjudicate(
            artifact_root=root,
            candidate_sha=sha,
            candidate_tree=tree,
            event_type=event,
            run_id=run_id,
            workflow=workflow,
        )
    return {
        "control": "proof_candidate_identity",
        "pristine_hash": _sha(pristine),
        "observed_red": observed_red,
        "restoration_hash": _sha(pristine),
        "restored_green": True,
    }


def _proof_required_additional_cell_control() -> dict[str, Any]:
    """Prove governed proof growth is required, not merely tolerated (LG-05).

    Registers a synthetic next-phase REQUIRED cell in a patched manifest copy,
    then shows: present+valid GREEN, omitted RED, restored GREEN, and
    unregistered extra evidence RED (SW-17 direction).
    """
    import yaml  # type: ignore[import-untyped]  # noqa: PLC0415

    import scripts.ci.adjudicate_b26_p1_proof_plane as proof_plane  # noqa: PLC0415
    from scripts.ci.adjudicate_b26_p1_proof_plane import (  # noqa: PLC0415
        AdjudicationError,
        adjudicate,
    )
    from scripts.ci.b26_p1_evidence import (  # noqa: PLC0415
        canonical_json,
        git_identity,
        write_evidence_cell,
    )

    sha, tree = git_identity()
    workflow = "B2.6-P1 Contract Authority, Semantic Freeze and Proof Plane"
    event = "pull_request"
    run_id = "negative-control-local-required-cell"
    manifest = yaml.safe_load(proof_plane.REQUIREMENTS.read_text(encoding="utf-8"))
    simulated = {
        "gate_id": "B26-P2-SIM-REQUIRED",
        "producer": "b26-p2-simulated",
        "scenario_id": "simulated-next-phase-evidence",
        "falsifier_id": "B26-P2-SIM-FALSIFIER",
        "required": True,
    }
    manifest.setdefault("additional_accepted_cells", []).append(simulated)
    with tempfile.TemporaryDirectory(prefix="b26-p1-proof-req-") as directory:
        manifest_path = Path(directory) / "proof-requirements.sim.yaml"
        manifest_path.write_text(
            yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
        )
        previous = proof_plane.REQUIREMENTS
        proof_plane.REQUIREMENTS = manifest_path
        try:
            with tempfile.TemporaryDirectory(prefix="b26-p1-cells-") as cell_dir:
                root = Path(cell_dir)
                for cell in manifest["required_cells"]:
                    details: dict[str, Any] = {}
                    if cell["gate_id"] == "B26-P1-G1-G2-INHERITED-PHYSICS":
                        details = {
                            "source_event": event,
                            "source_sha": sha,
                            "required_jobs": {
                                "B2.5-P13 C19 Context-Robust Production Closure": "success",
                                "B2.5-P13 C20 Verdict Authority Conservation": "success",
                                "B2.5-P13 C21 Freshness and Issuance Authority Conservation": "success",
                                "B2.5-P14 Downstream Projection Safety": "success",
                            },
                        }
                    write_evidence_cell(
                        root / f"{cell['gate_id']}.json",
                        gate_id=cell["gate_id"],
                        producer=cell["producer"],
                        scenario_id=cell["scenario_id"],
                        falsifier_id=cell["falsifier_id"],
                        details=details,
                        event_type=event,
                        run_id=run_id,
                        workflow=workflow,
                    )
                # Omitted required P2 cell must RED.
                try:
                    adjudicate(
                        artifact_root=root,
                        candidate_sha=sha,
                        candidate_tree=tree,
                        event_type=event,
                        run_id=run_id,
                        workflow=workflow,
                    )
                except AdjudicationError as exc:
                    observed_red = str(exc)
                    if "missing_required_additional" not in observed_red:
                        raise RuntimeError(
                            f"required_cell_omission_wrong_reason:{observed_red}"
                        )
                else:
                    raise RuntimeError("required_cell_omission_did_not_turn_red")
                # Unregistered extra evidence must RED (SW-17 direction).
                write_evidence_cell(
                    root / "B26-P2-SIM-UNREGISTERED.json",
                    gate_id="B26-P2-SIM-UNREGISTERED",
                    producer="b26-p2-simulated",
                    scenario_id="simulated-next-phase-evidence",
                    falsifier_id="B26-P2-SIM-FALSIFIER",
                    details={},
                    event_type=event,
                    run_id=run_id,
                    workflow=workflow,
                )
                try:
                    adjudicate(
                        artifact_root=root,
                        candidate_sha=sha,
                        candidate_tree=tree,
                        event_type=event,
                        run_id=run_id,
                        workflow=workflow,
                    )
                except AdjudicationError as exc:
                    if "unexpected" not in str(exc):
                        raise RuntimeError(
                            f"unregistered_cell_wrong_reason:{exc}"
                        )
                else:
                    raise RuntimeError("unregistered_cell_did_not_turn_red")
                (root / "B26-P2-SIM-UNREGISTERED.json").unlink()
                # Present correct required P2 cell must GREEN.
                write_evidence_cell(
                    root / "B26-P2-SIM-REQUIRED.json",
                    gate_id="B26-P2-SIM-REQUIRED",
                    producer="b26-p2-simulated",
                    scenario_id="simulated-next-phase-evidence",
                    falsifier_id="B26-P2-SIM-FALSIFIER",
                    details={},
                    event_type=event,
                    run_id=run_id,
                    workflow=workflow,
                )
                adjudicate(
                    artifact_root=root,
                    candidate_sha=sha,
                    candidate_tree=tree,
                    event_type=event,
                    run_id=run_id,
                    workflow=workflow,
                )
        finally:
            proof_plane.REQUIREMENTS = previous
    void = hashlib.sha256(canonical_json({"control": "proof_required"})).hexdigest()
    return {
        "control": "proof_required_additional_cell",
        "pristine_hash": void,
        "observed_red": observed_red,
        "restoration_hash": void,
        "restored_green": True,
    }


def run_battery() -> list[dict[str, Any]]:
    pristine = _validator()
    if pristine.returncode != 0:
        raise RuntimeError(f"pristine_validator_red:{pristine.stdout}{pristine.stderr}")
    ledger: list[dict[str, Any]] = []
    for defect, target, expected_red in STATIC_CONTROLS:
        original = target.read_bytes()
        pristine_hash = _sha(original)
        try:
            applied = _run(sys.executable, str(MUTATOR), "apply", defect)
            if applied.returncode != 0:
                raise RuntimeError(f"mutator_failed:{defect}:{applied.stdout}{applied.stderr}")
            red = _validator()
            red_text = red.stdout + red.stderr
            if red.returncode == 0 or expected_red not in red_text:
                raise RuntimeError(f"control_did_not_red:{defect}:{red_text}")
        finally:
            target.write_bytes(original)
        if _sha(target.read_bytes()) != pristine_hash:
            raise RuntimeError(f"restore_hash_mismatch:{defect}")
        green = _validator()
        if green.returncode != 0:
            raise RuntimeError(f"restore_not_green:{defect}:{green.stdout}{green.stderr}")
        ledger.append(
            {
                "control": defect,
                "pristine_hash": pristine_hash,
                "observed_red": expected_red,
                "restoration_hash": _sha(target.read_bytes()),
                "restored_green": True,
            }
        )
    ledger.append(_proof_identity_control())
    ledger.append(_proof_required_additional_cell_control())
    return ledger


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-out", type=Path)
    args = parser.parse_args()
    try:
        ledger = run_battery()
    except RuntimeError as exc:
        print(f"B26_P1_NEGATIVE_CONTROLS_FAIL {exc}")
        return 1
    if args.evidence_out:
        from scripts.ci.b26_p1_evidence import write_evidence_cell  # noqa: PLC0415

        write_evidence_cell(
            args.evidence_out,
            gate_id="B26-P1-G9-NEGATIVE-CONTROLS",
            producer="b26-p1-static-authority",
            scenario_id="red-restore-green-ledger",
            falsifier_id="B26-P1-NC-01-through-06",
            details={"controls": ledger, "control_count": len(ledger)},
        )
    print("B26_P1_NEGATIVE_CONTROLS_PASS")
    print(json.dumps(ledger, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
