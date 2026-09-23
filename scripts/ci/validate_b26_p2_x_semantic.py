#!/usr/bin/env python3
"""B2.6-P2 Corrective X transitive semantic-universe validator.

Builds the P2 semantic universe from the actual production entrypoint
(backend/app/tasks/revenue_verification.py) by AST import-graph
traversal -- not from a remembered file list -- and proves:

1. UNIVERSE CLOSURE: every module reachable from the entrypoint is in
   the governed manifest; a new helper/module on the derivation path
   is RED until governed.
2. TEMPORAL CO-DERIVATION: the B2.3 footprint (verdict columns actually
   read) is derived from code and must be covered by the temporal
   trigger's UPDATE OF list. A new B2.3 field read without trigger
   coverage is RED automatically.
3. DYNAMIC-FORM DISCLOSURE: dynamic/indirect dependency forms
   (eval/exec/compile/__import__/importlib/getattr-variable/globals/
   locals) must be declared in the manifest; an undeclared occurrence
   is RED. No string-token adjacency lists: AST nodes adjudicate.
4. TRUTH-PATH IMPORT BAN: the frozen pure-Python law library's
   classify/normalize surface must not be imported by truth-path
   modules (the single SQL authority governs). A truth-path import of
   those names is RED.

--generate writes the derived manifest for review (the manifest
acknowledges drift; effect proof carries authority). Without
--generate, derived-vs-manifest mismatch is RED.

Exit code is the gate: 0 on PASS, 1 plus a violation list on FAIL.
"""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_APP = REPO_ROOT / "backend" / "app"
ENTRYPOINT = BACKEND_APP / "tasks" / "revenue_verification.py"
MANIFEST_PATH = (
    REPO_ROOT
    / "contracts-internal"
    / "governance"
    / "b26_p2_x_semantic_universe.pin.json"
)

# Truth-path modules that must never import the frozen pure-Python
# classify/normalize surface (single SQL authority governs them).
TRUTH_PATH_MODULES = {
    "app.finance_reconciliation.candidate_conduction",
    "app.finance_reconciliation.conduction_state",
    "app.finance_reconciliation.canonical_sink",
    "app.finance_reconciliation.dispatch_authority",
    "app.tasks.revenue_verification",
}
BANNED_PURE_SEMANTIC_NAMES = {
    "classify_candidate",
    "normalize_provider",
    "normalize_currency",
    "normalize_rail",
    "normalize_provider_set",
    "assert_aggregate_scope_supported",
}

# AST-adjudicated dynamic forms. Each occurrence must be declared in
# the manifest with its governing justification.
_DYNAMIC_CHECKS: tuple[tuple[str, object], ...] = ()


def _module_of(path: Path) -> str:
    rel = path.relative_to(BACKEND_APP.parent).with_suffix("")
    return ".".join(rel.parts)


def _path_of(module: str) -> Path | None:
    rel = module.split(".")
    if not rel or rel[0] != "app":
        return None
    base = BACKEND_APP.joinpath(*rel[1:])
    candidate = base.with_suffix(".py")
    if candidate.is_file():
        return candidate
    init = base / "__init__.py"
    if init.is_file():
        return init
    return None


def _imports_of(tree: ast.AST, module: str) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "app" or alias.name.startswith("app."):
                    found.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                parts = module.split(".")
                base = parts[: len(parts) - node.level + 1] if node.level > 1 else parts[:-1]
                prefix = ".".join(base)
                if node.module:
                    found.add(f"{prefix}.{node.module}")
                    for alias in node.names:
                        if alias.name != "*":
                            found.add(f"{prefix}.{node.module}.{alias.name}")
                else:
                    for alias in node.names:
                        found.add(f"{prefix}.{alias.name}")
            elif node.module == "app" or (node.module or "").startswith("app."):
                found.add(node.module or "app")
                # from P import submodule: the package edge alone hides
                # the real dependency. Record submodule candidates too;
                # unresolvable ones are dropped by the graph builder.
                for alias in node.names:
                    if alias.name != "*":
                        found.add(f"{node.module}.{alias.name}")
    return found


def _build_universe() -> tuple[set[str], dict[str, list[str]]]:
    modules: set[str] = set()
    edges: dict[str, list[str]] = {}
    entry = _module_of(ENTRYPOINT)
    frontier = [entry]
    while frontier:
        module = frontier.pop()
        if module in modules:
            continue
        path = _path_of(module)
        if path is None:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        modules.add(module)
        deps = sorted(
            dep
            for dep in _imports_of(tree, module)
            if _path_of(dep) is not None
        )
        edges[module] = deps
        frontier.extend(dep for dep in deps if dep not in modules)
    return modules, edges


def _dynamic_forms(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return []
    forms: list[str] = []
    for node in ast.walk(tree):
        lineno = getattr(node, "lineno", 0)
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in (
                "eval", "exec", "compile", "__import__",
            ):
                forms.append(f"{func.id}():{lineno}")
            elif (
                isinstance(func, ast.Attribute)
                and func.attr == "getattr"
                and len(node.args) >= 2
                and not isinstance(node.args[1], ast.Constant)
            ):
                forms.append(f"getattr-variable:{lineno}")
            elif isinstance(func, ast.Name) and func.id in (
                "globals", "locals", "vars",
            ):
                forms.append(f"{func.id}():{lineno}")
        elif isinstance(node, ast.ImportFrom):
            if node.module == "importlib" or (node.module or "").startswith(
                "importlib."
            ):
                forms.append(f"import-importlib:{node.lineno}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "importlib" or alias.name.startswith(
                    "importlib."
                ):
                    forms.append(f"import-importlib:{node.lineno}")
    return sorted(set(forms))


def _b23_footprint(path: Path) -> set[str]:
    """Columns of b23_match_verdicts observably read by one module.

    Derived, not hardcoded, through two precise channels (no line
    windows, no bare-token noise):

    1. SELECT literals on the P2 side: string constants that mention
       b23_match_verdicts inside a SELECT, in finance_reconciliation
       modules and the worker entrypoint, are tokenized (the SELECT
       list is the read). INSERT/UPDATE literals are writes, not P2
       semantic reads, and are excluded. B2.3's own SELECTs (batch
       engine, coverage, transitions) are B2.3-phase business governed
       by B2.3 triggers and the P1 money law, not by the P2 temporal
       trigger.
    2. Qualified reads on the P2 side: subscripts/attributes on
       verdict-bound bases (verdict, verdicts, v, verdict_row) in the
       same P2-side scope.

    A new verdict column read through either channel widens this set
    and must be covered by the temporal trigger in the same change.
    """
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (OSError, SyntaxError):
        return set()
    if "b23_match_verdicts" not in source:
        return set()
    import re as _re

    verdict_like = {
        "status", "webhook_ingress_identity_id", "tenant_id",
        "canonical_commerce_reference", "currency_code", "provider",
        "match_quality", "attributed_amount_minor", "verified_amount_minor",
        "canonical_net_verified_amount_minor",
        "canonical_expected_gross_amount_minor",
        "canonical_captured_gross_amount_minor",
        "attribution_event_id", "provider_native_event_reference",
        "provider_native_commerce_reference",
        # NOTE: bare "id" is deliberately excluded (see verdict-PK rule
        # below); verdict-PK reads must use qualified form.
    }
    verdict_bases = {"verdict", "verdicts", "v", "verdict_row"}
    posix = path.as_posix().replace("\\", "/")
    p2_side = (
        posix.find("finance_reconciliation") != -1
        or path.name == "revenue_verification.py"
    )
    columns: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if (
                p2_side
                and "b23_match_verdicts" in node.value
                and ("select" in node.value.lower())
            ):
                for token in _re.findall(
                    r"[A-Za-z_][A-Za-z0-9_]*", node.value
                ):
                    if token in verdict_like:
                        columns.add(token)
        elif p2_side and isinstance(node, ast.Subscript):
            value = node.value
            if isinstance(value, ast.Name) and value.id in verdict_bases:
                sl = node.slice
                if isinstance(sl, ast.Constant) and isinstance(sl.value, str):
                    if sl.value in verdict_like:
                        columns.add(sl.value)
        elif p2_side and isinstance(node, ast.Attribute):
            value = node.value
            if isinstance(value, ast.Name) and value.id in verdict_bases:
                if node.attr in verdict_like:
                    columns.add(node.attr)
    import re as _re2

    # Verdict-PK reads are governed only on the P2 side of the
    # universe: B2.3's own PK reads (state transitions, batch engine)
    # are B2.3-phase business, not P2 semantic inputs.
    if p2_side:
        if _re2.search(r"\b(v|verdict|verdicts)\.id\b", source):
            columns.add("__verdict_pk_read__")
    return columns


def _truth_path_imports(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if (node.module or "").endswith("scope_authority"):
                for alias in node.names:
                    names.add(alias.name)
    return names


def _trigger_columns_from_migrations() -> set[str]:
    """Latest UPDATE OF column list for the verdict temporal trigger."""
    import re as _re

    alembic_dir = REPO_ROOT / "alembic"
    files = sorted(alembic_dir.rglob("*.py")) if alembic_dir.is_dir() else []
    found: set[str] = set()
    pattern = _re.compile(
        r"BEFORE INSERT OR UPDATE OF ([A-Za-z0-9_, \n]+?)\s+OR DELETE\s+ON public\.b23_match_verdicts"
    )
    for path in files:
        try:
            source = path.read_text(encoding="utf-8")
        except OSError:
            continue
        upgrade_source = source.split("\ndef downgrade")[0]
        for match in pattern.finditer(upgrade_source):
            found = {
                part.strip()
                for part in match.group(1).split(",")
                if part.strip()
            }
    return found


def _derive() -> dict[str, object]:
    modules, _edges = _build_universe()
    per_module_forms: dict[str, list[str]] = {}
    footprint: set[str] = set()
    truth_violations: dict[str, list[str]] = {}
    pk_read_modules: list[str] = []
    for module in sorted(modules):
        path = _path_of(module)
        assert path is not None
        forms = _dynamic_forms(path)
        if forms:
            per_module_forms[module] = forms
        module_footprint = _b23_footprint(path)
        if "__verdict_pk_read__" in module_footprint:
            module_footprint.discard("__verdict_pk_read__")
            pk_read_modules.append(module)
        footprint |= module_footprint
        if module in TRUTH_PATH_MODULES:
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (OSError, SyntaxError):
                continue
            bad = _truth_path_imports(tree) & BANNED_PURE_SEMANTIC_NAMES
            if bad:
                truth_violations[module] = sorted(bad)
    return {
        "entrypoint": _module_of(ENTRYPOINT),
        "modules": sorted(modules),
        "b23_footprint": sorted(footprint),
        "dynamic_forms": per_module_forms,
        "trigger_columns": sorted(_trigger_columns_from_migrations()),
        "truth_path_import_violations": truth_violations,
        "verdict_pk_read_modules": sorted(pk_read_modules),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate B2.6-P2 Corrective X semantic universe."
    )
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--evidence-dir", type=Path, default=None)
    parser.add_argument("--evidence-out", type=Path, default=None)
    args = parser.parse_args()
    violations: list[str] = []
    checks: dict[str, object] = {}
    try:
        derived = _derive()
        checks["modules_derived"] = len(derived["modules"])
        checks["footprint_derived"] = derived["b23_footprint"]
        checks["trigger_columns"] = derived["trigger_columns"]
        checks["dynamic_forms_derived"] = derived["dynamic_forms"]
        if derived["truth_path_import_violations"]:
            checks["truth_path_import_violations"] = derived[
                "truth_path_import_violations"
            ]
            for module, names in sorted(
                derived["truth_path_import_violations"].items()
            ):
                for name in names:
                    violations.append(
                        f"x_semantic_truth_path_pure_import:{module}:{name}"
                    )
        footprint = set(derived["b23_footprint"])
        trigger_cols = set(derived["trigger_columns"])
        missing = sorted(footprint - trigger_cols)
        checks["footprint_uncovered_by_trigger"] = missing
        for column in missing:
            violations.append(
                f"x_semantic_temporal_gap:b23_match_verdicts.{column}"
            )
        for module in derived.get("verdict_pk_read_modules", []):
            violations.append(f"x_semantic_verdict_pk_read:{module}")
        if args.generate:
            manifest = {
                "producer": "validate_b26_p2_x_semantic",
                "entrypoint": derived["entrypoint"],
                "modules": derived["modules"],
                "b23_footprint": derived["b23_footprint"],
                "trigger_columns": derived["trigger_columns"],
                "dynamic_forms": derived["dynamic_forms"],
            }
            MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
            MANIFEST_PATH.write_text(
                json.dumps(manifest, indent=2), encoding="utf-8"
            )
            checks["manifest_generated"] = MANIFEST_PATH.as_posix()
        else:
            if not MANIFEST_PATH.is_file():
                violations.append("x_semantic_manifest_missing")
            else:
                manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
                checks["manifest_modules"] = len(manifest.get("modules", []))
                new_modules = sorted(
                    set(derived["modules"]) - set(manifest.get("modules", []))
                )
                checks["ungoverned_modules"] = new_modules
                for module in new_modules:
                    violations.append(f"x_semantic_ungoverned_module:{module}")
                manifest_footprint = set(manifest.get("b23_footprint", []))
                new_reads = sorted(footprint - manifest_footprint)
                checks["ungoverned_reads"] = new_reads
                for column in new_reads:
                    violations.append(
                        f"x_semantic_ungoverned_read:b23_match_verdicts.{column}"
                    )
                manifest_forms = manifest.get("dynamic_forms", {})
                for module in sorted(derived["dynamic_forms"]):
                    new_forms = sorted(
                        set(derived["dynamic_forms"][module])
                        - set(manifest_forms.get(module, []))
                    )
                    checks[f"ungoverned_dynamic:{module}"] = new_forms
                    for form in new_forms:
                        violations.append(
                            f"x_semantic_undeclared_dynamic:{module}:{form}"
                        )
    except Exception as exc:  # noqa: BLE001
        violations.append(f"x_semantic_validator_crash:{exc}")
    status = "PASS" if not violations else "FAIL"
    evidence = {
        "gate_id": "B26-P2-X-SEMANTIC",
        "validator": "validate_b26_p2_x_semantic",
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
        (args.evidence_dir / "x-semantic.json").write_text(
            json.dumps(evidence, indent=2), encoding="utf-8"
        )
    if violations:
        print("B26_P2_X_SEMANTIC_FAIL " + ";".join(sorted(violations)))
        return 1
    print("B26_P2_X_SEMANTIC_PASS")
    print(json.dumps(evidence, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
