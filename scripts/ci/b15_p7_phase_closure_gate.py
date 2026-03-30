#!/usr/bin/env python3
"""Machine gate for B1.5-P7 technical-vs-full phase closure."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _read_status(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _pass(lines: list[str]) -> int:
    print("b15_p7_phase_closure_gate")
    print("result=PASS")
    for line in lines:
        print(line)
    return 0


def _fail(lines: list[str]) -> int:
    print("b15_p7_phase_closure_gate")
    print("result=FAIL")
    for line in lines:
        print(line)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="B1.5-P7 phase closure gate.")
    parser.add_argument(
        "--mode",
        required=True,
        choices=("technical", "full-phase"),
        help="technical: allow pending_human_execution; full-phase: require validated_by_humans 8/10.",
    )
    parser.add_argument(
        "--status-file",
        default="docs/forensics/evidence/b15_p7/mental_model_study/status.json",
    )
    args = parser.parse_args()

    status_path = Path(args.status_file)
    if not status_path.exists():
        return _fail([f"status_file_missing:{status_path}"])

    status = _read_status(status_path)
    study_status = str(status.get("study_status", "")).strip()

    if args.mode == "technical":
        if study_status not in {"pending_human_execution", "validated_by_humans"}:
            return _fail([f"invalid_study_status:{study_status}"])
        if study_status == "pending_human_execution":
            if int(status.get("participants_completed", -1)) != 0:
                return _fail(["pending_study_requires_zero_completed_participants"])
            if bool(status.get("result_claim_present", True)):
                return _fail(["pending_study_cannot_claim_success"])
            return _pass(
                [
                    "gate_mode=technical",
                    "phase_state=open_pending_human_execution",
                ]
            )
        completed = int(status.get("participants_completed", 0))
        understood = int(status.get("understood_async_review_count", 0))
        if completed < 10 or understood < 8:
            return _fail(["validated_status_below_eight_of_ten_threshold"])
        return _pass(
            [
                "gate_mode=technical",
                "phase_state=validated_by_humans",
            ]
        )

    if study_status != "validated_by_humans":
        return _fail(
            [
                f"deploy_blocked_study_status:{study_status}",
                "requires_validated_by_humans_for_full_phase_closure",
            ]
        )

    completed = int(status.get("participants_completed", 0))
    understood = int(status.get("understood_async_review_count", 0))
    if completed < 10 or understood < 8:
        return _fail(
            [
                "deploy_blocked_insufficient_human_validation",
                f"participants_completed={completed}",
                f"understood_async_review_count={understood}",
            ]
        )
    if bool(status.get("full_phase_closure_claim_present", False)) is False:
        return _fail(["deploy_blocked_full_phase_closure_claim_not_asserted"])

    return _pass(
        [
            "gate_mode=full-phase",
            "phase_state=validated_and_closable",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
