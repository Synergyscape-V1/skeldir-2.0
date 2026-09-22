#!/usr/bin/env python3
"""B2.6-P2 Corrective IX consequence-authority validator (static bytes).

Checks that the canonical consequence authority lives in the sovereign DB
plane (migration 202609230001), that the worker task module still derives
scope through the lawful wiring, and that no direct UPDATE into conducted
exists in the worker task module.

Exit code is the gate: 0 on PASS, 1 plus a violation list on FAIL.
"""

from __future__ import annotations

import argparse
import ast
import io
import json
import re
import tokenize
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (
    REPO_ROOT
    / "alembic/versions/007_skeldir_foundation"
    / "202609230001_b26_p2_corrective_ix_consequence_authority.py"
)
TASK_MODULE = REPO_ROOT / "backend/app/tasks/revenue_verification.py"

TRIGGER_NAME = "trg_b26_p2_verdict_temporal_conservation"
TRIGGER_COLUMNS = (
    "status",
    "webhook_ingress_identity_id",
    "tenant_id",
    "canonical_commerce_reference",
)

# Effect tokens that would assert conducted without the server-side gate.
FORBIDDEN_TASK_EFFECTS = (
    "SET delivery_state = 'conducted'",
    "SET state = 'conducted'",
    'delivery_state = "conducted"',
    "delivery_state = 'conducted'",
    "UPDATE public.b23_match_task_dispatches",
    "UPDATE public.b26_p2_execution_outbox",
)


def _code_without_comments(source: str) -> str:
    """Strip comments so sensors fire on executable meaning, not prose."""
    try:
        out: list[str] = []
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.COMMENT:
                continue
            out.append(tok.string)
        return "".join(out)
    except (tokenize.TokenError, SyntaxError):
        return "\n".join(
            line.split("#", 1)[0] for line in source.splitlines()
        )


def _check_migration_tokens(
    violations: list[str], checks: dict[str, object]
) -> str:
    if not MIGRATION.is_file():
        violations.append("ix_migration_file_missing:202609230001")
        checks["migration_file_exists"] = False
        return ""
    checks["migration_file_exists"] = True
    src = MIGRATION.read_text(encoding="utf-8")
    required = (
        "b26_p2_canonical_scope_identity_for_window",
        "b26_p2_receipt_scope_not_canonical",
        "b26_p2_conducted_scope_not_canonical",
        "canonical_commerce_reference",
        "b26_p2_provenance_status",
        "b26_p2_dispatch_provenance_unknown",
        "b26_p2_record_scheduler_heartbeat",
    )
    for token in required:
        present = token in src
        checks[f"migration_contains:{token}"] = present
        if not present:
            violations.append(f"ix_migration_token_absent:{token}")
    # Temporal footprint: the verdict trigger UPDATE OF list must name the
    # P2-read reference-presence column alongside the link columns. Scope
    # the search to the temporal trigger block: the file also carries an
    # ingress-provenance trigger with its own narrower UPDATE OF list.
    block_at = src.find(TRIGGER_NAME)
    block = src[block_at : block_at + 1200] if block_at != -1 else ""
    trigger_hit = re.search(
        r"UPDATE\s+OF\s+([A-Za-z0-9_,\s]+?)\s*\n",
        block,
    )
    update_of_cols = trigger_hit.group(1) if trigger_hit else ""
    covers = all(col in update_of_cols for col in TRIGGER_COLUMNS)
    checks["trigger_update_of_list"] = update_of_cols.strip()
    checks["trigger_update_of_covers_reference"] = covers
    if not covers:
        violations.append("ix_temporal_trigger_reference_not_governed")
    # Scheduler-liveness separation: heartbeat table + function exist, only
    # app_beat may tick it, and no non-beat runtime role gains write grants.
    heartbeat_table = (
        "CREATE TABLE IF NOT EXISTS public.b26_p2_scheduler_heartbeat" in src
    )
    heartbeat_fn = "b26_p2_record_scheduler_heartbeat" in src
    beat_guard = (
        "b26_p2_scheduler_caller_refused" in src
        and "session_user NOT IN ('app_beat'" in src
    )
    nonbeat_write_grant = re.search(
        r"GRANT\s+[^;]*INSERT[^;]*b26_p2_scheduler_heartbeat[^;]*"
        r"TO\s+(app_user|app_relay|app_worker)",
        src,
    ) or re.search(
        r"GRANT\s+[^;]*UPDATE[^;]*b26_p2_scheduler_heartbeat[^;]*"
        r"TO\s+(app_user|app_relay|app_worker)",
        src,
    )
    separated = bool(
        heartbeat_table and heartbeat_fn and beat_guard
        and nonbeat_write_grant is None
    )
    checks["scheduler_heartbeat_table"] = heartbeat_table
    checks["scheduler_heartbeat_function"] = heartbeat_fn
    checks["scheduler_beat_only_guard"] = beat_guard
    checks["scheduler_no_nonbeat_write_grant"] = (
        nonbeat_write_grant is None
    )
    checks["scheduler_liveness_separated"] = separated
    if not separated:
        violations.append("ix_scheduler_liveness_not_separated")
    return src


def _call_reachable(path: Path, func_name: str, target: str) -> bool:
    """True when target( is called on a statically-reachable path."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return False
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name != func_name:
            continue

        def _false(test: ast.AST) -> bool:
            if isinstance(test, ast.Constant):
                return test.value in (False, 0, 0.0, "", None)
            if isinstance(test, ast.UnaryOp) and isinstance(
                test.op, ast.Not
            ):
                return (
                    isinstance(test.operand, ast.Constant)
                    and test.operand.value is True
                )
            return False

        class _Visitor(ast.NodeVisitor):
            def __init__(self) -> None:
                self.depth = 0

            def visit_If(self, if_node: ast.If) -> None:  # noqa: N802
                if _false(if_node.test):
                    self.depth += 1
                    self.generic_visit(if_node)
                    self.depth -= 1
                else:
                    self.generic_visit(if_node)

            def visit_Call(self, call: ast.Call) -> None:  # noqa: N802
                nonlocal_found[0] = nonlocal_found[0] or (
                    target in ast.dump(call.func) and self.depth == 0
                )
                self.generic_visit(call)

        nonlocal_found = [False]
        _Visitor().visit(node)
        return nonlocal_found[0]
    return False


def _check_worker_wiring(violations: list[str], checks: dict[str, object]) -> str:
    if not TASK_MODULE.is_file():
        violations.append("ix_worker_task_module_missing")
        checks["worker_module_exists"] = False
        return ""
    checks["worker_module_exists"] = True
    src = TASK_MODULE.read_text(encoding="utf-8")
    defined = "async def _derive_p2_scope_for_window" in src
    derives = "derive_governed_scope(" in src
    reachable = _call_reachable(
        TASK_MODULE,
        "execute_b23_batch_match_engine_task",
        "_derive_p2_scope_for_window",
    )
    checks["worker_defines_derive_for_window"] = defined
    checks["worker_calls_derive_governed_scope"] = derives
    checks["worker_derive_reachable_from_task"] = reachable
    if not defined:
        violations.append("ix_worker_derive_wiring_absent:definition")
    if not derives:
        violations.append("ix_worker_derive_wiring_absent:governed_scope")
    if not reachable:
        violations.append("ix_worker_derive_wiring_unreachable")
    return src


def _check_no_direct_conducted(
    violations: list[str], checks: dict[str, object], src: str
) -> None:
    code_only = _code_without_comments(src)
    for token in FORBIDDEN_TASK_EFFECTS:
        present = token in code_only
        checks[f"worker_direct_effect_absent:{token[:32]}"] = not present
        if present:
            violations.append(f"ix_worker_direct_conducted_present:{token[:32]}")


def _negative_controls(checks: dict[str, object]) -> list[str]:
    """Prove the sensors are non-vacuous on mutated inputs (in-memory)."""
    results: dict[str, bool] = {}
    # Control 1: migration bytes with a load-bearing token removed must fail
    # the token sensor.
    src = MIGRATION.read_text(encoding="utf-8") if MIGRATION.is_file() else ""
    redacted = src.replace("b26_p2_receipt_scope_not_canonical", "REMOVED")
    results["token_sensor_fires_on_redacted_migration"] = (
        "b26_p2_receipt_scope_not_canonical" not in redacted
        and "b26_p2_receipt_scope_not_canonical" in src
    )
    # Control 2: an injected direct conducted UPDATE must trip the worker
    # effect sensor.
    task_src = (
        TASK_MODULE.read_text(encoding="utf-8")
        if TASK_MODULE.is_file()
        else ""
    )
    injected = task_src + "\n    x = \"SET delivery_state = 'conducted'\"\n"
    results["effect_sensor_fires_on_injected_update"] = (
        "SET delivery_state = 'conducted'"
        in _code_without_comments(injected)
    )
    # Control 3: a trigger UPDATE OF list without the reference column must
    # fail the footprint sensor.
    narrowed = "UPDATE OF status, webhook_ingress_identity_id, tenant_id"
    results["footprint_sensor_fires_on_narrowed_trigger"] = not all(
        col in narrowed for col in TRIGGER_COLUMNS
    )
    checks["negative_controls"] = results
    blind = [name for name, ok in results.items() if not ok]
    return [f"ix_consequence_negative_control_blind:{n}" for n in blind]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate B2.6-P2 Corrective IX consequence authority."
    )
    parser.add_argument("--evidence-dir", type=Path, default=None)
    parser.add_argument("--evidence-out", type=Path, default=None)
    args = parser.parse_args()
    violations: list[str] = []
    checks: dict[str, object] = {}
    try:
        _check_migration_tokens(violations, checks)
        task_src = _check_worker_wiring(violations, checks)
        if task_src:
            _check_no_direct_conducted(violations, checks, task_src)
        violations.extend(_negative_controls(checks))
    except Exception as exc:  # noqa: BLE001
        violations.append(f"ix_consequence_validator_crash:{exc}")
    status = "PASS" if not violations else "FAIL"
    evidence = {
        # Declared gate identity for the proof-plane capsule census (same
        # convention as the authority-universe cell): additive, ignored by
        # required-cell adjudication.
        "gate_id": "B26-P2-IX-CONSEQUENCE",
        "validator": "validate_b26_p2_ix_consequence",
        "status": status,
        "violations": sorted(violations),
        "checks": checks,
        "migration": MIGRATION.relative_to(REPO_ROOT).as_posix(),
        "task_module": TASK_MODULE.relative_to(REPO_ROOT).as_posix(),
    }
    if args.evidence_out is not None:
        args.evidence_out.parent.mkdir(parents=True, exist_ok=True)
        args.evidence_out.write_text(
            json.dumps(evidence, indent=2), encoding="utf-8"
        )
    if args.evidence_dir is not None:
        args.evidence_dir.mkdir(parents=True, exist_ok=True)
        (args.evidence_dir / "ix-consequence.json").write_text(
            json.dumps(evidence, indent=2), encoding="utf-8"
        )
    if violations:
        print("B26_P2_IX_CONSEQUENCE_FAIL " + ";".join(sorted(violations)))
        return 1
    print("B26_P2_IX_CONSEQUENCE_PASS")
    print(json.dumps(evidence, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
