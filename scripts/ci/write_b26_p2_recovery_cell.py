#!/usr/bin/env python3
"""Bind the three recovery controls and the signed result into one proof cell."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from b26_p2_evidence import write_evidence_cell

MODES = ("omit-restore", "tamper-signature", "restore-failure", "positive")


def mode_projection(record: dict) -> dict:
    return {
        "passed": record["passed"],
        "mode": record.get("mode"),
        "baseline": record.get("baseline"),
        "initial_subject": record.get("initial_subject"),
        "manual_observer": record.get("manual_observer"),
        "baseline_signed": record.get("baseline_signed"),
        "baseline_authority": record.get("baseline_authority"),
        "baseline_source_authority": record.get("baseline_source_authority"),
        "fault": record.get("fault"),
        "restored_baseline": record.get("restored_baseline"),
        "restored_authority": record.get("restored_authority"),
        "restored_source_authority": record.get("restored_source_authority"),
        "restoration_observation": record.get("restoration_observation"),
        "restoration_observed_at": record.get("restoration_observed_at"),
        "restoration_semantic_authority": record.get(
            "restoration_semantic_authority"
        ),
        "amendment_admission_started_at": record.get(
            "amendment_admission_started_at"
        ),
        "amendment_admitted_at": record.get("amendment_admitted_at"),
        "causal_progression": record.get("causal_progression"),
        "causal_history": record.get("causal_history"),
        "final_signed": record.get("final_signed"),
        "final_authority": record.get("final_authority"),
        "final_source_authority": record.get("final_source_authority"),
        "final_observation": record.get("final_observation"),
        "final_observed_at": record.get("final_observed_at"),
        "witness_public_key": record.get("witness_public_key"),
        "require_signature_verification": record.get(
            "require_signature_verification"
        ),
        "trust_jwks": record.get("trust_jwks"),
        "artifact": record.get("artifact"),
        "observed": record.get("observed"),
        "compensation": record.get("compensation"),
        "readers": record.get("readers"),
        "custody": record.get("custody"),
        "amendment": record.get("amendment"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    records = {}
    for mode in MODES:
        path = args.evidence_dir / f"xxv-r0034-recovery-{mode}-20261102.json"
        records[mode] = json.loads(path.read_text(encoding="utf-8"))
    if not all(record.get("passed") is True for record in records.values()):
        raise SystemExit("recovery_control_not_passed")
    commits = {
        str((record.get("artifact") or {}).get("commit_sha") or "")
        for record in records.values()
    }
    if len(commits) != 1 or "" in commits:
        raise SystemExit(f"recovery_artifact_identity_mismatch:{sorted(commits)}")
    positive = records["positive"]
    restoration_authority = positive.get("restoration_semantic_authority") or {}
    causal_progression = positive.get("causal_progression") or {}
    if restoration_authority.get("established") is not True:
        raise SystemExit("restoration_semantic_authority_not_established")
    if causal_progression.get("established") is not True:
        raise SystemExit("final_causal_progression_not_established")
    details = {
        "proof_kind": "retained_execution_observations",
        "modes": {
            mode: mode_projection(record)
            for mode, record in records.items()
        },
        "retained_execution_observations": {
            "baseline_signed": positive.get("baseline_signed"),
            "restored_baseline": positive.get("restored_baseline"),
            "final_signed": positive.get("final_signed"),
            "baseline_authority": positive.get("baseline_authority"),
            "baseline_source_authority": positive.get(
                "baseline_source_authority"
            ),
            "restored_authority": positive.get("restored_authority"),
            "restored_source_authority": positive.get(
                "restored_source_authority"
            ),
            "final_authority": positive.get("final_authority"),
            "final_source_authority": positive.get(
                "final_source_authority"
            ),
            "restoration_observation": positive.get(
                "restoration_observation"
            ),
            "final_observation": positive.get("final_observation"),
            "witness_public_key": positive.get("witness_public_key"),
            "require_signature_verification": positive.get(
                "require_signature_verification"
            ),
            "trust_jwks": positive.get("trust_jwks"),
            "artifact": positive.get("artifact"),
        },
        "financial_history_commitment": {
            "causal_history": positive.get("causal_history"),
            "source_attestation_public_key": (
                positive.get("causal_history") or {}
            ).get("source_attestation_public_key"),
            "signed_witness": causal_progression.get("signed_witness"),
            "expected_provider": causal_progression.get("expected_provider"),
            "expected_match": causal_progression.get("expected_match"),
            "expected_webhook": causal_progression.get("expected_webhook"),
        },
        "causal_order": {
            "restoration_observed_at": positive.get(
                "restoration_observed_at"
            ),
            "amendment_admission_started_at": positive.get(
                "amendment_admission_started_at"
            ),
            "amendment_admitted_at": positive.get(
                "amendment_admitted_at"
            ),
            "accepted_transition_at": causal_progression.get(
                "accepted_transition_at"
            ),
            "final_observation": positive.get("final_observation"),
            "final_observed_at": positive.get("final_observed_at"),
            "final_created_at": (
                (positive.get("final_signed") or {}).get("artifact") or {}
            ).get("created_at"),
            "signed_precision": "second",
            "ledger_precision": "microsecond",
        },
        "artifact_commit": next(iter(commits)),
        "runtime_identity": positive.get("artifact"),
        "signed_artifact": positive.get("readers", {})
        .get("trust", {})
        .get("artifact"),
        "public_verification_basis": positive.get("readers", {}).get(
            "trust_verify"
        ),
        "public_key_registry": (
            (positive.get("final_signed") or {}).get("public_key_basis")
        ),
        "restored_baseline": positive.get("restored_baseline"),
        "restoration_semantic_authority": restoration_authority,
        "causal_progression": causal_progression,
        "causal_history": positive.get("causal_history"),
        "signed_amount_minor": positive.get("readers", {})
        .get("trust", {})
        .get("verified_revenue_minor"),
        "signed_currency": positive.get("readers", {})
        .get("trust", {})
        .get("currency"),
    }
    write_evidence_cell(
        args.out,
        gate_id="B26-P2-G13-RECOVERY-ACCEPTANCE",
        producer="b26-p2-xxv-recovery",
        scenario_id="signed-custody-restore-progression",
        falsifier_id="omitted-restoration-tampered-signature-restore-failure",
        details=details,
        status="PASS",
    )
    print(f"B26_P2_RECOVERY_CELL_WRITTEN {args.out}")

    authority_out = args.out.with_name("restoration-semantic-authority.json")
    write_evidence_cell(
        authority_out,
        gate_id="B26-P2-G13-RESTORATION-SEMANTIC-AUTHORITY",
        producer="b26-p2-xxv-recovery",
        scenario_id="signed-custody-restoration-semantic-authority",
        falsifier_id="changed-lineage-changed-completeness-changed-observation-time",
        details={
            "proof_kind": "restoration_and_history_authority",
            "baseline_signed": positive.get("baseline_signed"),
            "restored_baseline": positive.get("restored_baseline"),
            "baseline_authority": positive.get("baseline_authority"),
            "restored_authority": positive.get("restored_authority"),
            "final_authority": positive.get("final_authority"),
            "restored_observation": positive.get("restoration_observation"),
            "final_observation": positive.get("final_observation"),
            "restoration_semantic_authority": restoration_authority,
            "financial_history_commitment": details[
                "financial_history_commitment"
            ],
        },
        status="PASS",
    )
    print(f"B26_P2_RESTORATION_SEMANTIC_CELL_WRITTEN {authority_out}")

    causal_out = args.out.with_name("final-causal-progression.json")
    write_evidence_cell(
        causal_out,
        gate_id="B26-P2-G13-FINAL-CAUSAL-PROGRESSION",
        producer="b26-p2-xxv-recovery",
        scenario_id="signed-post-amendment-causal-progression",
        falsifier_id="fabricated-history-fabricated-order-missing-transition",
        details={
            "proof_kind": "causal_order",
            "final_signed": positive.get("final_signed"),
            "final_observation": positive.get("final_observation"),
            "causal_history": positive.get("causal_history"),
            "causal_progression": causal_progression,
            "causal_order": details["causal_order"],
            "financial_history_commitment": details[
                "financial_history_commitment"
            ],
        },
        status="PASS",
    )
    print(f"B26_P2_CAUSAL_PROGRESSION_CELL_WRITTEN {causal_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
