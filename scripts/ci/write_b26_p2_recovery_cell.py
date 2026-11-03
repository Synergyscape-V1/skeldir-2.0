#!/usr/bin/env python3
"""Bind the three recovery controls and the signed result into one proof cell."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from b26_p2_evidence import write_evidence_cell

MODES = ("omit-restore", "tamper-signature", "restore-failure", "positive")


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
        "modes": {
            mode: {
                "passed": record["passed"],
                "baseline": record.get("baseline"),
                "baseline_signed": record.get("baseline_signed"),
                "fault": record.get("fault"),
                "restored_baseline": record.get("restored_baseline"),
                "restoration_semantic_authority": record.get(
                    "restoration_semantic_authority"
                ),
                "causal_progression": record.get("causal_progression"),
                "causal_history": record.get("causal_history"),
                "final_signed": record.get("final_signed"),
                "observed": record.get("observed"),
                "compensation": record.get("compensation"),
                "readers": record.get("readers"),
                "custody": record.get("custody"),
                "amendment": record.get("amendment"),
            }
            for mode, record in records.items()
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
            "baseline_signed": positive.get("baseline_signed"),
            "restored_baseline": positive.get("restored_baseline"),
            "restoration_semantic_authority": restoration_authority,
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
            "final_signed": positive.get("final_signed"),
            "causal_history": positive.get("causal_history"),
            "causal_progression": causal_progression,
        },
        status="PASS",
    )
    print(f"B26_P2_CAUSAL_PROGRESSION_CELL_WRITTEN {causal_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
