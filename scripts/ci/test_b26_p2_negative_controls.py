#!/usr/bin/env python3
"""B2.6-P2 pristine -> defect RED -> exact restore -> GREEN battery."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
VALIDATOR = ROOT / "scripts/ci/validate_b26_p2_scope_authority.py"
MUTATOR = ROOT / "scripts/ci/_b26_p2_controlled_defect.py"
SCOPE_MODULE = ROOT / "backend/app/finance_reconciliation/scope_authority.py"
CONDUCTION_MODULE = ROOT / "backend/app/finance_reconciliation/candidate_conduction.py"
SCOPE_CONTRACT = ROOT / "contracts/reconciliation/b2.6/scope-policy.v1.yaml"
SINK_MODULE = ROOT / "backend/app/finance_reconciliation/canonical_sink.py"
WEBHOOK_MODULE = ROOT / "backend/app/api/webhooks.py"
B23_TASK_MODULE = ROOT / "backend/app/tasks/revenue_verification.py"
PROBE_FILES = (
    ROOT / "backend/app/finance_reconciliation/_p2_nc_probe_alias.py",
    ROOT / "backend/app/finance_reconciliation/_p2_nc_probe_sql.py",
    ROOT / "backend/app/finance_reconciliation/_p2_nc_probe_serializer.py",
)

# (defect name, expected RED substring, class)
CONTROLS: tuple[tuple[str, str, str], ...] = (
    ("p2_second_alias_dict", "p2_second_normalization_authority", "same-primitive"),
    ("p2_sql_case_normalizer", "p2_second_normalization_authority", "alternate-primitive"),
    ("p2_serializer_reinterpretation", "p2_second_normalization_authority", "out-of-vocabulary"),
    ("p2_unsupported_promotion", "p2_vector_unsupported_rail_not_excluded", "same-primitive"),
    ("p2_currency_silent_promotion", "p2_vector_wrong_currency_not_excluded", "same-primitive"),
    ("p2_window_closed_end", "p2_vector_window_end_not_exclusive", "out-of-vocabulary"),
    ("p2_tenant_guc_bypass", "p2_impure_authority_token", "alternate-primitive"),
    ("p2_nondeterministic_identity", "p2_nondeterministic_token", "alternate-primitive"),
    ("p2_reverse_write", "p2_persisted_predicate_token", "alternate-primitive"),
    ("p2_contract_universe_widening", "p2_canonical_provider_universe_drift", "same-primitive"),
    ("p2_scope_policy_version_drift", "p2_scope_policy_version_drift", "same-primitive"),
    ("p2_live_wiring_removal", "p2_live_wiring_absent_from_executor", "alternate-primitive"),
    ("p2_sink_conduction_removal", "p2_conduction_absent_from_executor", "alternate-primitive"),
    ("p2_webhook_phase_violation", "p2_webhook_phase_boundary_violated", "out-of-vocabulary"),
    ("p2_b23_task_conduction_removal", "p2_conduction_absent_from_b23_task", "alternate-primitive"),
    ("p2_conduction_prefilter", "p2_conduction_prefilter", "out-of-vocabulary"),
    ("p2_refusal_law_removal", "p2_refusal_representation_drift", "same-primitive"),
)


def _run_validator() -> tuple[int, str]:
    completed = subprocess.run(
        (sys.executable, str(VALIDATOR)),
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return completed.returncode, (completed.stdout + completed.stderr)


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


TRACKED_DEFECT_FILES = (
    ROOT / "backend/app/finance_reconciliation/scope_authority.py",
    ROOT / "backend/app/finance_reconciliation/candidate_conduction.py",
    ROOT / "contracts/reconciliation/b2.6/scope-policy.v1.yaml",
    ROOT / "backend/app/finance_reconciliation/canonical_sink.py",
    ROOT / "backend/app/api/webhooks.py",
    ROOT / "backend/app/tasks/revenue_verification.py",
)


def _snapshot() -> dict[Path, bytes]:
    return {path: path.read_bytes() for path in TRACKED_DEFECT_FILES}


def _restore_snapshot(snapshot: dict[Path, bytes]) -> None:
    for probe in PROBE_FILES:
        if probe.exists():
            probe.unlink()
    for path, data in snapshot.items():
        path.write_bytes(data)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-out", type=Path, default=None)
    args = parser.parse_args()
    ledger: list[dict[str, str]] = []

    code, out = _run_validator()
    if code != 0:
        print(f"B26_P2_NEGATIVE_CONTROLS_FAIL pristine_not_green:{out[-2000:]}")
        return 1
    pristine = {
        "scope_module": _hash(SCOPE_MODULE),
        "conduction_module": _hash(CONDUCTION_MODULE),
        "scope_contract": _hash(SCOPE_CONTRACT),
        "sink_module": _hash(SINK_MODULE),
        "webhook_module": _hash(WEBHOOK_MODULE),
        "b23_task_module": _hash(B23_TASK_MODULE),
    }
    pristine_snapshot = _snapshot()

    for name, expected, primitive in CONTROLS:
        applied = subprocess.run(
            (sys.executable, str(MUTATOR), name),
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if applied.returncode != 0:
            _restore_snapshot(pristine_snapshot)
            print(f"B26_P2_NEGATIVE_CONTROLS_FAIL {name}_apply_failed:{applied.stderr[-500:]}")
            return 1
        code, out = _run_validator()
        if code == 0 or expected not in out:
            _restore_snapshot(pristine_snapshot)
            print(
                f"B26_P2_NEGATIVE_CONTROLS_FAIL {name}_not_red:"
                f"expected={expected}:out={out[-2000:]}"
            )
            return 1
        _restore_snapshot(pristine_snapshot)
        for probe in PROBE_FILES:
            if probe.exists():
                print(f"B26_P2_NEGATIVE_CONTROLS_FAIL {name}_probe_not_removed")
                return 1
        code, out = _run_validator()
        if code != 0:
            print(f"B26_P2_NEGATIVE_CONTROLS_FAIL {name}_restore_not_green:{out[-2000:]}")
            return 1
        ledger.append({"control": name, "primitive": primitive, "red": expected})

    restored = {
        "scope_module": _hash(SCOPE_MODULE),
        "conduction_module": _hash(CONDUCTION_MODULE),
        "scope_contract": _hash(SCOPE_CONTRACT),
        "sink_module": _hash(SINK_MODULE),
        "webhook_module": _hash(WEBHOOK_MODULE),
        "b23_task_module": _hash(B23_TASK_MODULE),
    }
    if restored != pristine:
        print("B26_P2_NEGATIVE_CONTROLS_FAIL restoration_hash_mismatch")
        return 1
    # Only P2-intended working-tree changes may remain (none for probes).
    for probe in PROBE_FILES:
        if probe.exists():
            print("B26_P2_NEGATIVE_CONTROLS_FAIL probe_file_remains")
            return 1
    if args.evidence_out is not None:
        from scripts.ci.b26_p2_evidence import write_evidence_cell  # noqa: PLC0415

        write_evidence_cell(
            args.evidence_out,
            gate_id="B26-P2-G10-NEGATIVE-CONTROLS",
            producer="b26-p2-static-authority",
            scenario_id="red-restore-green-ledger",
            falsifier_id="p2-12-control-battery",
            details={"controls": ledger, "control_count": len(ledger)},
        )
    print(f"B26_P2_NEGATIVE_CONTROLS_PASS {len(ledger)}/{len(CONTROLS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
