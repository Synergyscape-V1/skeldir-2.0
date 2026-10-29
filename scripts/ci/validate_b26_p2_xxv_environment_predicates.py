#!/usr/bin/env python3
"""B2.6-P2 Corrective XXV: canonical-environment predicate guard.

The defect class
---------------
``app/core/config.py`` canonicalises every environment alias through
``resolve_control_plane_env`` before ``Settings`` stores it ("production" ->
"prod", "staging" -> "stage", "development" -> "dev", "test" -> "ci"/"local").
Any code that compares the *canonicalised* value against an alias literal is
therefore dead in every possible deployment.

That is not a style problem. Two such comparisons in
``backend/app/trust/builder.py`` (``settings.ENVIRONMENT == "production"``)
silently disabled the issuance-time compiled-anchor comparison and the
missing-custody refusal for the whole life of corrective XXIV, which is how
both independent audits replaced the historical verification root and deleted
the custody record while the service kept issuing signed financial envelopes.

The rule
--------
A comparison of the canonical environment value against a string literal is
refused when the literal is not a canonical environment name. Reading the RAW
``os.getenv("ENVIRONMENT")`` and matching an alias-inclusive set is allowed:
that code sees the operator's pre-canonical input on purpose.

This is an effect-level check, not a token list: it fires on any comparison
whose literal canonicalisation can never produce, no matter which module,
helper or spelling introduces it.

Usage:
    python scripts/ci/validate_b26_p2_xxv_environment_predicates.py
    python scripts/ci/validate_b26_p2_xxv_environment_predicates.py --evidence-out out.json
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_APP = REPO_ROOT / "backend" / "app"

#: The only values ``resolve_control_plane_env`` can return.
CANONICAL_ENVS = {"prod", "stage", "ci", "dev", "local"}

#: Modules that own canonicalisation itself and legitimately name aliases.
EXEMPT_RELATIVE_PATHS = {
    "core/control_plane.py",
    "core/managed_settings_contract.py",
}

GATE_ID = "B26-P2-XXV-ENV-PREDICATE"


def _canonical_value_expression(node: ast.AST) -> bool:
    """True when the expression reads the CANONICALISED environment value.

    Recognises ``settings.ENVIRONMENT``, ``self.ENVIRONMENT`` inside Settings,
    ``_read_setting("ENVIRONMENT")`` and any ``.lower()``/``.strip()``/``str()``
    wrapping of those, because the wrapping does not restore the alias.
    """
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in {"lower", "upper", "strip"}:
            return _canonical_value_expression(func.value)
        if isinstance(func, ast.Name) and func.id == "str" and node.args:
            return _canonical_value_expression(node.args[0])
        if isinstance(func, ast.Name) and func.id == "_read_setting" and node.args:
            arg = node.args[0]
            return isinstance(arg, ast.Constant) and arg.value == "ENVIRONMENT"
        return False
    if isinstance(node, ast.BoolOp):
        return any(_canonical_value_expression(value) for value in node.values)
    if isinstance(node, ast.Attribute):
        return node.attr == "ENVIRONMENT"
    return False


def _literals(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, (ast.Set, ast.List, ast.Tuple)):
        out: list[str] = []
        for element in node.elts:
            if isinstance(element, ast.Constant) and isinstance(element.value, str):
                out.append(element.value)
        return out
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Name) and func.id == "frozenset" and node.args:
            return _literals(node.args[0])
    return []


def _canonical_locals(tree: ast.AST) -> set[str]:
    """Names assigned from the canonical environment value.

    Without this a future engineer could evade an expression-shaped check by
    writing ``env = settings.ENVIRONMENT`` and comparing ``env`` to an alias,
    which is the same prohibited effect through a primitive the expression
    check does not see. Assignment propagation is deliberately module-wide and
    name-based: a false positive here costs a rename, a false negative costs a
    dead authority branch.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and _canonical_value_expression(node.value):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            if _canonical_value_expression(node.value) and isinstance(
                node.target, ast.Name
            ):
                names.add(node.target.id)
    return names


def scan() -> list[dict]:
    violations: list[dict] = []
    for path in sorted(BACKEND_APP.rglob("*.py")):
        relative = path.relative_to(BACKEND_APP).as_posix()
        if relative in EXEMPT_RELATIVE_PATHS:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:  # pragma: no cover - a parse failure is a defect
            violations.append(
                {
                    "file": f"backend/app/{relative}",
                    "line": exc.lineno or 0,
                    "reason": f"unparseable:{exc.msg}",
                }
            )
            continue
        canonical_names = _canonical_locals(tree)

        def _is_canonical(node: ast.AST) -> bool:
            if isinstance(node, ast.Name) and node.id in canonical_names:
                return True
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr in {
                    "lower",
                    "upper",
                    "strip",
                }:
                    return _is_canonical(func.value)
            if isinstance(node, ast.BoolOp):
                return any(_is_canonical(value) for value in node.values)
            return _canonical_value_expression(node)

        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare):
                continue
            sides: list[ast.AST] = [node.left, *node.comparators]
            if not any(_is_canonical(side) for side in sides):
                continue
            for side in sides:
                if _is_canonical(side):
                    continue
                for literal in _literals(side):
                    if literal.strip().lower() not in CANONICAL_ENVS:
                        violations.append(
                            {
                                "file": f"backend/app/{relative}",
                                "line": node.lineno,
                                "literal": literal,
                                "reason": (
                                    "canonical environment value compared against a"
                                    " non-canonical literal: resolve_control_plane_env"
                                    " can never produce this value, so the branch is"
                                    " unreachable in every deployment"
                                ),
                            }
                        )
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-out")
    args = parser.parse_args()

    violations = scan()
    record = {
        "gate_id": GATE_ID,
        "checked_at_utc": datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "scanned_root": "backend/app",
        "canonical_envs": sorted(CANONICAL_ENVS),
        "exempt_paths": sorted(EXEMPT_RELATIVE_PATHS),
        "violations": violations,
        "status": "PASS" if not violations else "FAIL",
    }
    if args.evidence_out:
        out = Path(args.evidence_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    if violations:
        for violation in violations:
            print(
                f"{GATE_ID}_VIOLATION {violation['file']}:{violation['line']}"
                f" literal={violation.get('literal')!r}",
                file=sys.stderr,
            )
        print(f"{GATE_ID}_FAIL violations={len(violations)}", file=sys.stderr)
        return 1
    print(f"{GATE_ID}_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
