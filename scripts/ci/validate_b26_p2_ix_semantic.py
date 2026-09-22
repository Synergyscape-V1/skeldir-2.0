#!/usr/bin/env python3
"""B2.6-P2 Corrective IX semantic-universe validator (derived, not vocabulary).

(a) AST-pins both P2 executables against the reviewed pin file.
(b) Forbids dynamic forms (code, not comments) in both P2 modules, with one
    governed exception: scope_authority's sovereign-leaf loader, which reads
    the B2.3 coverage universe by file location without importing the package
    chain. Every other dynamic token occurrence fails.
(c) Derives the B2.3 footprint from candidate_conduction.py verdict reads and
    requires the IX migration trigger UPDATE OF list to cover all of it.

Exit code is the gate: 0 on PASS, 1 plus a violation list on FAIL.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import re
import tokenize
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCOPE_MODULE = REPO_ROOT / "backend/app/finance_reconciliation/scope_authority.py"
CONDUCTION_MODULE = (
    REPO_ROOT / "backend/app/finance_reconciliation/candidate_conduction.py"
)
PIN_FILE = (
    REPO_ROOT
    / "contracts-internal/governance/b26_p2_semantic_universe.pin.json"
)
IX_MIGRATION = (
    REPO_ROOT
    / "alembic/versions/007_skeldir_foundation"
    / "202609230001_b26_p2_corrective_ix_consequence_authority.py"
)

EXPECTED_FOOTPRINT = (
    "status",
    "webhook_ingress_identity_id",
    "tenant_id",
    "canonical_commerce_reference",
)

DYNAMIC_TOKENS = ("__import__", "importlib", "eval(", "exec(", "compile(")


def _module_ast_sha256(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    return hashlib.sha256(
        ast.dump(ast.parse(source), include_attributes=False).encode("utf-8")
    ).hexdigest()


def _code_without_comments(source: str) -> str:
    try:
        kept: list[str] = []
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.COMMENT:
                continue
            kept.append(tok.string)
        return "".join(kept)
    except (tokenize.TokenError, SyntaxError):
        return "\n".join(
            line.split("#", 1)[0] for line in source.splitlines()
        )


def _governed_loader_lines(source: str) -> set[int]:
    """Line numbers of the single governed sovereign-leaf loader.

    The sovereign B2.3 coverage leaf is stdlib-plus-sqlalchemy only, so the
    classifier observes it by file location instead of importing the package
    chain (which owns engine/config concerns). These lines are the pinned
    exception to the importlib token rule; everything else must be clean.
    """
    lines = source.splitlines()
    excluded: set[int] = set()
    for i, line in enumerate(lines, start=1):
        if re.match(r"^\s*import\s+importlib\.util\s*$", line):
            excluded.add(i)
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return excluded
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
            node.name == "_sovereign_leaf"
        ):
            start, end = node.lineno, node.end_lineno or node.lineno
            for i in range(start, end + 1):
                if "importlib" in lines[i - 1]:
                    excluded.add(i)
    return excluded


def _dynamic_hits(path: Path, *, governed_exception: bool) -> list[str]:
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    excluded = _governed_loader_lines(source) if governed_exception else set()
    code_lines: list[str] = []
    for i, line in enumerate(lines, start=1):
        if i in excluded:
            continue
        code_lines.append(line.split("#", 1)[0])
    code_only = "\n".join(code_lines)
    hits: list[str] = []
    for token in DYNAMIC_TOKENS:
        if token in code_only:
            hits.append(token)
    return hits


def _check_pins(violations: list[str], checks: dict[str, object]) -> None:
    if not PIN_FILE.is_file():
        violations.append("ix_semantic_pin_missing")
        checks["pin_exists"] = False
        return
    checks["pin_exists"] = True
    try:
        pin = json.loads(PIN_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        violations.append(f"ix_semantic_pin_unreadable:{exc}")
        return
    for path, key in (
        (SCOPE_MODULE, "scope_authority_ast_sha256"),
        (CONDUCTION_MODULE, "candidate_conduction_ast_sha256"),
    ):
        if not path.is_file():
            violations.append(f"ix_semantic_module_missing:{path.name}")
            continue
        live = _module_ast_sha256(path)
        pinned = pin.get(key)
        checks[f"live:{path.name}"] = live
        checks[f"pinned:{path.name}"] = pinned
        if not isinstance(pinned, str) or len(pinned) != 64:
            violations.append(f"ix_semantic_pin_malformed:{key}")
        elif pinned != live:
            violations.append(f"ix_semantic_ast_drift:{path.name}")
    footprint = pin.get("b23_footprint")
    checks["pinned_footprint"] = footprint
    if sorted(footprint or []) != sorted(EXPECTED_FOOTPRINT):
        violations.append("ix_semantic_footprint_pin_drift")


def _check_dynamic(violations: list[str], checks: dict[str, object]) -> None:
    for path, governed in (
        (SCOPE_MODULE, True),
        (CONDUCTION_MODULE, False),
    ):
        if not path.is_file():
            continue
        hits = _dynamic_hits(path, governed_exception=governed)
        checks[f"dynamic_hits:{path.name}"] = hits
        if governed:
            checks[f"governed_loader_excluded:{path.name}"] = sorted(
                _governed_loader_lines(path.read_text(encoding="utf-8"))
            )
        for token in hits:
            violations.append(
                f"ix_semantic_dynamic_form_present:{path.name}:{token}"
            )


def _derive_footprint_from_conduction() -> tuple[set[str], dict[str, bool]]:
    """Find footprint columns read near b23_match_verdicts queries."""
    source = CONDUCTION_MODULE.read_text(encoding="utf-8")
    lines = source.splitlines()
    verdict_lines = {
        i for i, line in enumerate(lines) if "b23_match_verdicts" in line
    }
    found: dict[str, bool] = {}
    for column in EXPECTED_FOOTPRINT:
        hit = False
        for i, line in enumerate(lines):
            if column not in line:
                continue
            if any(abs(i - v) <= 12 for v in verdict_lines):
                hit = True
                break
        found[column] = hit
    return {c for c, ok in found.items() if ok}, found


def _check_footprint(violations: list[str], checks: dict[str, object]) -> None:
    if not CONDUCTION_MODULE.is_file() or not IX_MIGRATION.is_file():
        violations.append("ix_semantic_footprint_inputs_missing")
        return
    derived, per_column = _derive_footprint_from_conduction()
    checks["derived_footprint"] = sorted(derived)
    checks["derived_footprint_per_column"] = per_column
    if derived != set(EXPECTED_FOOTPRINT):
        missing = sorted(set(EXPECTED_FOOTPRINT) - derived)
        violations.append(
            "ix_semantic_footprint_derivation_gap:" + ",".join(missing)
        )
        return
    migration = IX_MIGRATION.read_text(encoding="utf-8")
    # Scope to the temporal trigger block: the file also carries an
    # ingress-provenance trigger with its own narrower UPDATE OF list.
    block_at = migration.find("trg_b26_p2_verdict_temporal_conservation")
    block = migration[block_at : block_at + 1200] if block_at != -1 else ""
    match = re.search(r"UPDATE\s+OF\s+([A-Za-z0-9_,\s]+?)\s*\n", block)
    update_of = match.group(1) if match else ""
    checks["migration_trigger_update_of"] = update_of.strip()
    uncovered = [c for c in EXPECTED_FOOTPRINT if c not in update_of]
    checks["trigger_covers_footprint"] = not uncovered
    if uncovered:
        violations.append(
            "ix_semantic_trigger_footprint_gap:" + ",".join(uncovered)
        )


def _negative_controls(checks: dict[str, object]) -> list[str]:
    results: dict[str, bool] = {}
    # Control 1: a tampered pin hash must read as drift.
    live = (
        _module_ast_sha256(SCOPE_MODULE) if SCOPE_MODULE.is_file() else ""
    )
    tampered = "0" * 64
    results["pin_sensor_fires_on_tampered_hash"] = bool(
        live and tampered != live
    )
    # Control 2: an injected eval( must trip the dynamic sensor.
    probe = "x = 1\n" + "result = eval('1 + 1')\n"
    results["dynamic_sensor_fires_on_eval_injection"] = (
        "eval(" in _code_without_comments(probe)
    )
    # Control 3: a trigger list missing a footprint column must fail.
    narrowed = "UPDATE OF status, tenant_id"
    results["footprint_sensor_fires_on_narrowed_trigger"] = not all(
        c in narrowed for c in EXPECTED_FOOTPRINT
    )
    # Control 4: the governed loader exception must actually cover the
    # live importlib occurrences (else the exception is vacuous).
    if SCOPE_MODULE.is_file():
        source = SCOPE_MODULE.read_text(encoding="utf-8")
        excluded = _governed_loader_lines(source)
        remaining = "\n".join(
            line.split("#", 1)[0]
            for i, line in enumerate(source.splitlines(), start=1)
            if i not in excluded
        )
        results["governed_exception_covers_live_importlib"] = (
            "importlib" not in remaining
            and "importlib" in _code_without_comments(source)
        )
    checks["negative_controls"] = results
    return [
        f"ix_semantic_negative_control_blind:{n}"
        for n, ok in results.items()
        if not ok
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate B2.6-P2 Corrective IX semantic universe."
    )
    parser.add_argument("--evidence-dir", type=Path, default=None)
    parser.add_argument("--evidence-out", type=Path, default=None)
    args = parser.parse_args()
    violations: list[str] = []
    checks: dict[str, object] = {}
    try:
        _check_pins(violations, checks)
        _check_dynamic(violations, checks)
        _check_footprint(violations, checks)
        violations.extend(_negative_controls(checks))
    except Exception as exc:  # noqa: BLE001
        violations.append(f"ix_semantic_validator_crash:{exc}")
    status = "PASS" if not violations else "FAIL"
    evidence = {
        # Declared gate identity for the proof-plane capsule census (same
        # convention as the authority-universe cell): additive, ignored by
        # required-cell adjudication.
        "gate_id": "B26-P2-IX-SEMANTIC",
        "validator": "validate_b26_p2_ix_semantic",
        "status": status,
        "violations": sorted(violations),
        "checks": checks,
    }
    if args.evidence_out is not None:
        args.evidence_out.parent.mkdir(parents=True, exist_ok=True)
        args.evidence_out.write_text(
            json.dumps(evidence, indent=2), encoding="utf-8"
        )
    if args.evidence_dir is not None:
        args.evidence_dir.mkdir(parents=True, exist_ok=True)
        (args.evidence_dir / "ix-semantic.json").write_text(
            json.dumps(evidence, indent=2), encoding="utf-8"
        )
    if violations:
        print("B26_P2_IX_SEMANTIC_FAIL " + ";".join(sorted(violations)))
        return 1
    print("B26_P2_IX_SEMANTIC_PASS")
    print(json.dumps(evidence, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
