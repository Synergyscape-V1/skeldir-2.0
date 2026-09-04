#!/usr/bin/env python3
"""Apply one B2.5-P14 controlled defect to the working tree.

The P14 negative controls have to modify *real governing state*: the actual
simulation service, the actual explanation service, the actual projection
registry. Inlining those mutations as heredocs inside a workflow makes them
invisible to review and impossible to run locally, so they live here as named,
single-purpose transformations.

Each mutation asserts its own anchor before writing. A control that silently
became a no-op because the code moved would produce a green gate that measured
nothing -- which is the exact failure mode the P14 falsifiers exist to rule out.
The caller restores the pristine file afterwards and checks ``git diff
--exit-code``, so nothing here needs an undo path.

Usage::

    python scripts/ci/_b25_p14_controlled_defect.py apply <defect-name>
    python scripts/ci/_b25_p14_controlled_defect.py list
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
SIMULATION_SERVICE = REPO_ROOT / "backend/app/simulation/service.py"
EXPLANATION_SERVICE = REPO_ROOT / "backend/app/explanation/service.py"
PROFILE_REGISTRY = REPO_ROOT / "contracts/trust-api/projection-profiles.v1.yaml"

DEFAULT_LLM_PROFILE_ID = "llm_explanation_projection_safe"


def _replace_once(path: Path, anchor: str, replacement: str, *, what: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(anchor) != 1:
        raise SystemExit(
            f"controlled defect '{what}' cannot be applied: the anchor "
            f"{anchor!r} appears {text.count(anchor)} times in {path.name}. "
            "The control must be repaired rather than allowed to no-op."
        )
    path.write_text(text.replace(anchor, replacement, 1), encoding="utf-8")


def platform_write() -> None:
    """Gate 9: put a platform-write client one import away from B2.8."""
    _replace_once(
        SIMULATION_SERVICE,
        "import uuid\n",
        "import uuid\n\nfrom app.services import platform_connections  # NC-P14-01\n",
        what="platform_write",
    )


def second_solver_caller() -> None:
    """Gate 6: give the solver a caller outside the admission conjunction."""
    _replace_once(
        EXPLANATION_SERVICE,
        "from typing import Any, Mapping",
        "from typing import Any, Mapping\n\n"
        "from app.simulation.solver import allocate_budget  # NC-P14-02",
        what="second_solver_caller",
    )


def _load_registry() -> dict:
    return yaml.safe_load(PROFILE_REGISTRY.read_text(encoding="utf-8"))


def _write_registry(document: dict) -> None:
    PROFILE_REGISTRY.write_text(
        yaml.safe_dump(document, sort_keys=False), encoding="utf-8"
    )


def remove_required_profile() -> None:
    """P14-G1: delete one of the four required projection profiles."""
    document = _load_registry()
    before = len(document["profiles"])
    document["profiles"] = [
        profile
        for profile in document["profiles"]
        if profile["profile_id"] != "optimization_projection_safe"
    ]
    if len(document["profiles"]) != before - 1:
        raise SystemExit(
            "controlled defect 'remove_required_profile' cannot be applied: "
            "optimization_projection_safe was already absent"
        )
    _write_registry(document)


def untrusted_label_in_llm_profile() -> None:
    """P14-G2: seat a provider-controlled label in the default LLM projection."""
    document = _load_registry()
    for profile in document["profiles"]:
        if profile["profile_id"] == DEFAULT_LLM_PROFILE_ID:
            profile["fields"].append(
                {
                    "path": "untrusted_display_data.display_text",
                    "position": "display_only",
                    "trust_class": "untrusted_display_label",
                }
            )
            _write_registry(document)
            return
    raise SystemExit(
        "controlled defect 'untrusted_label_in_llm_profile' cannot be applied: "
        f"{DEFAULT_LLM_PROFILE_ID} is missing from the registry"
    )


DEFECTS = {
    "platform_write": platform_write,
    "second_solver_caller": second_solver_caller,
    "remove_required_profile": remove_required_profile,
    "untrusted_label_in_llm_profile": untrusted_label_in_llm_profile,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("apply", "list"))
    parser.add_argument("defect", nargs="?")
    args = parser.parse_args()

    if args.action == "list":
        for name in sorted(DEFECTS):
            print(name)
        return 0

    if not args.defect:
        parser.error("apply requires a defect name")
    try:
        mutation = DEFECTS[args.defect]
    except KeyError:
        parser.error(f"unknown defect {args.defect!r}; known: {sorted(DEFECTS)}")
    mutation()
    print(f"[b25-p14] applied controlled defect: {args.defect}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
