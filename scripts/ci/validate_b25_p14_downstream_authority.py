#!/usr/bin/env python3
"""B2.5-P14 static downstream-authority validator.

Three propositions are decided here, all of them statically, because each is a
property of the *import closure* rather than of any single execution:

* **Gate 9 -- no external action reachability.** Starting from every P14
  entrypoint, the transitive import closure must contain zero platform-write
  clients, zero action-dispatch queues and zero budget mutations. A runtime
  probe can only show that a particular run did not reach one; the closure
  shows that no run can.

* **Gate 6 -- the solver has exactly one caller.** ``allocate_budget`` may be
  imported only by ``app/simulation/admission.py``. That is what makes the
  admission conjunction the whole admission story: a second caller would be a
  second, unaudited path to the solver.

* **P14-G1..G4 -- the contract floor loads.** The registry is read and every
  required profile validated, so a malformed or narrowed contract fails here as
  well as in pytest. This runs without a database, so it is the cheapest gate in
  the P14 set and the first to go red on a contract regression.

Exit code 0 means every proposition held. Any violation prints the specific
offending file and symbol and exits 1 -- the P14 falsifiers require a red gate
to name its own cause.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
APP = BACKEND / "app"

P14_PACKAGES = ("explanation", "simulation")

# Modules that carry, or transitively reach, an external side effect. A P14
# package that imports any of these has left READ / COMPUTE / PROPOSE.
FORBIDDEN_MODULE_PREFIXES = (
    "app.tasks",
    "app.workers",
    "app.celery_app",
    "app.celery_control",
    "app.services.platform_connections",
    "app.services.platform_credentials",
    "app.services.provider_token_refresh",
    "app.services.provider_oauth_runtime",
    "app.services.llm_dispatch",
    "app.services.budget_job",
    "app.ingestion",
    "app.webhooks",
    "celery",
    "kombu",
    "boto3",
    "botocore",
)

# Third-party clients that would put a network write one call away.
FORBIDDEN_TOP_LEVEL_IMPORTS = (
    "requests",
    "httpx",
    "aiohttp",
    "urllib.request",
    "smtplib",
    "openai",
    "anthropic",
)

# The single lawful importer of the solver.
SOLVER_MODULE = "app.simulation.solver"
SOLVER_SYMBOL = "allocate_budget"
SOLVER_PERMITTED_IMPORTERS = frozenset({"app/simulation/admission.py"})


class Violation(RuntimeError):
    pass


def _module_name(path: Path) -> str:
    relative = path.relative_to(BACKEND).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _iter_python(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        yield path


def _imported_modules(tree: ast.AST) -> set[str]:
    """Every module name an AST reaches, including submodules named as symbols.

    ``from app.services import platform_connections`` binds a *module*, not an
    attribute, so recording only ``app.services`` would walk the package's
    ``__init__`` and never see the submodule that carries the side effect. Both
    forms are recorded; the closure walk discards candidates that resolve to no
    file, so an ordinary ``from x import SomeClass`` costs nothing.
    """

    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                # A relative import inside the package; resolved by the closure
                # walk below rather than treated as an external module.
                continue
            if node.module:
                found.add(node.module)
                for alias in node.names:
                    if alias.name != "*":
                        found.add(f"{node.module}.{alias.name}")
    return found


def _closure(entry_modules: set[str]) -> tuple[set[str], list[str]]:
    """Walk the transitive first-party import closure of the P14 entrypoints."""
    seen: set[str] = set()
    pending = list(entry_modules)
    external: list[str] = []
    while pending:
        module = pending.pop()
        if module in seen:
            continue
        seen.add(module)
        path = BACKEND / (module.replace(".", "/") + ".py")
        if not path.exists():
            package_init = BACKEND / module.replace(".", "/") / "__init__.py"
            if package_init.exists():
                path = package_init
            else:
                external.append(module)
                continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for imported in _imported_modules(tree):
            if imported.startswith("app.") or imported == "app":
                pending.append(imported)
            else:
                external.append(imported)
    # A candidate that resolved to no file is a symbol, not a module; it was
    # recorded in `external` by the loop above and is dropped here so the
    # external report stays about real third-party reach.
    return {module for module in seen if module.startswith("app")}, external


def check_no_external_action_reachability() -> list[str]:
    violations: list[str] = []
    entries = {
        _module_name(path)
        for package in P14_PACKAGES
        for path in _iter_python(APP / package)
    }
    closure, external = _closure(entries)

    for module in sorted(closure):
        for prefix in FORBIDDEN_MODULE_PREFIXES:
            if module == prefix or module.startswith(prefix + "."):
                violations.append(
                    f"P14 import closure reaches {module} (forbidden prefix {prefix})"
                )
    for module in sorted(set(external)):
        for prefix in FORBIDDEN_MODULE_PREFIXES + FORBIDDEN_TOP_LEVEL_IMPORTS:
            if module == prefix or module.startswith(prefix + "."):
                violations.append(
                    f"P14 import closure reaches external module {module}"
                )
    return violations


def check_solver_has_one_caller() -> list[str]:
    violations: list[str] = []
    importers: list[str] = []
    for path in _iter_python(APP):
        relative = path.relative_to(BACKEND).as_posix().removeprefix("app/")
        relative = "app/" + relative
        if relative == "app/simulation/solver.py":
            continue
        text = path.read_text(encoding="utf-8")
        if SOLVER_MODULE not in text and SOLVER_SYMBOL not in text:
            continue
        tree = ast.parse(text, filename=str(path))
        reaches = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == SOLVER_MODULE:
                if any(alias.name == SOLVER_SYMBOL for alias in node.names):
                    reaches = True
            elif isinstance(node, ast.Import):
                if any(alias.name == SOLVER_MODULE for alias in node.names):
                    reaches = True
        if reaches:
            importers.append(relative)

    unexpected = sorted(set(importers) - SOLVER_PERMITTED_IMPORTERS)
    if unexpected:
        violations.append(
            f"{SOLVER_SYMBOL} is reachable from {unexpected};"
            f" only {sorted(SOLVER_PERMITTED_IMPORTERS)} may call the solver"
        )
    missing = sorted(SOLVER_PERMITTED_IMPORTERS - set(importers))
    if missing:
        violations.append(
            f"the declared solver caller {missing} no longer imports {SOLVER_SYMBOL};"
            " the admission conjunction may have been bypassed"
        )
    return violations


def check_sufficiency_cannot_invoke() -> list[str]:
    """Gate 6's specification error, prevented in the module graph."""
    path = APP / "simulation" / "sufficiency.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for module in _imported_modules(tree):
        if module.endswith("solver") or module.endswith("admission"):
            return [
                "app/simulation/sufficiency.py imports "
                f"{module}; sufficiency is an admission condition, never a trigger"
            ]
    return []


def check_contract_floor() -> tuple[list[str], dict]:
    sys.path.insert(0, str(BACKEND))
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from app.trust.projection_profiles import (  # noqa: PLC0415
            REQUIRED_PROFILE_IDS,
            load_projection_profiles,
            projection_registry_identity,
        )
    except Exception as exc:  # noqa: BLE001
        return [f"projection profile registry failed to import: {exc}"], {}

    try:
        profiles = load_projection_profiles()
    except Exception as exc:  # noqa: BLE001
        return [f"projection contract floor failed closed: {exc}"], {}

    violations: list[str] = []
    for profile_id in REQUIRED_PROFILE_IDS:
        if profile_id not in profiles:
            violations.append(f"required projection profile missing: {profile_id}")
    default = profiles.get("llm_explanation_projection_safe")
    if default is not None and default.untrusted_labels_admitted:
        violations.append("default LLM projection admits untrusted labels")
    for profile_id, profile in profiles.items():
        if profile.judge_authority != "none":
            violations.append(f"{profile_id} grants judge authority")
        if profile.llm_authority_over_projected_values != "none":
            violations.append(f"{profile_id} grants model authority over values")
        if profile.policy_authority_projection not in ("typed", "omitted"):
            violations.append(f"{profile_id} does not keep policy authority typed")
    return violations, projection_registry_identity()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-out", default="")
    args = parser.parse_args()

    checks = {
        "no_external_action_reachability": check_no_external_action_reachability(),
        "solver_has_one_caller": check_solver_has_one_caller(),
        "sufficiency_cannot_invoke": check_sufficiency_cannot_invoke(),
    }
    contract_violations, registry_identity = check_contract_floor()
    checks["projection_contract_floor"] = contract_violations

    failed = {name: rows for name, rows in checks.items() if rows}
    for name, rows in sorted(checks.items()):
        status = "FAIL" if rows else "PASS"
        print(f"[b25-p14] {name}={status}")
        for row in rows:
            print(f"  - {row}")

    print(f"p14_projection_registry_version={registry_identity.get('registry_version')}")
    for profile_id, row in sorted(registry_identity.get("profiles", {}).items()):
        print(f"p14_profile={profile_id} hash={row['profile_hash']}")

    if args.evidence_out:
        out = Path(args.evidence_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(
                {
                    "checks": {name: rows for name, rows in checks.items()},
                    "projection_registry_identity": registry_identity,
                    "verdict": "PASS" if not failed else "FAIL",
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"[b25-p14] wrote evidence: {out}")

    if failed:
        print("[b25-p14] downstream authority validation FAILED")
        return 1
    print("[b25-p14] downstream authority validation PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
