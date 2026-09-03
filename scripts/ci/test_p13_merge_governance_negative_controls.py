#!/usr/bin/env python3
"""Negative controls for the P13 merge-governance validator.

Corrective XX, Exit Gate XX2-E active falsifier: "detach one load-bearing lane
from mandatory pre-merge adjudication -> governance validator RED."

A validator that only ever passes proves nothing. Each control below detaches
exactly one clause of the conjunction the validator enforces, asserts it goes
red, then restores the clause and asserts it goes green again. If a clause is
ever weakened into a no-op, its control fails.

Run:  python scripts/ci/test_p13_merge_governance_negative_controls.py
"""

from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "ci"))

import yaml  # noqa: E402

from validate_p13_merge_governance import (  # noqa: E402
    CONTRACT_KEY,
    CONTRACT_RELATIVE,
    validate,
)


CONFORMING_WORKFLOW = {
    "name": "R-lane",
    "on": {
        "workflow_dispatch": None,
        "pull_request": None,
        "merge_group": None,
        "push": {"branches": ["main"], "paths": ["backend/**"]},
    },
    "jobs": {
        "r-lane": {
            "name": "R Lane Physics",
            "runs-on": "ubuntu-latest",
            "steps": [{"run": "echo physics"}],
        }
    },
}

CONFORMING_CONTRACT = {
    "contract_id": "test",
    "repository": "example/repo",
    "branch": "main",
    "required_contexts": ["R Lane Physics"],
    CONTRACT_KEY: {
        "lanes": {
            "r-lane": {
                "workflow": ".github/workflows/r-lane.yml",
                "required_context": "R Lane Physics",
            }
        }
    },
}


def _build(root: Path, workflow: dict, contract: dict) -> None:
    workflows = root / ".github" / "workflows"
    workflows.mkdir(parents=True, exist_ok=True)
    (workflows / "r-lane.yml").write_text(
        yaml.safe_dump(workflow, sort_keys=False), encoding="utf-8"
    )
    contract_path = root / CONTRACT_RELATIVE
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    contract_path.write_text(json.dumps(contract, indent=2), encoding="utf-8")


def _expect(root: Path, *, red: bool, label: str) -> bool:
    failures = validate(root)
    actually_red = bool(failures)
    if actually_red != red:
        expected = "RED" if red else "GREEN"
        observed = "RED" if actually_red else "GREEN"
        print(f"FAIL {label}: expected {expected}, observed {observed} {failures}")
        return False
    detail = f" ({failures[0]})" if failures else ""
    print(f"OK   {label}: {'RED' if red else 'GREEN'}{detail}")
    return True


def _case_missing_pre_merge_event(root: Path) -> bool:
    """The historical state: push-only physics."""

    workflow = copy.deepcopy(CONFORMING_WORKFLOW)
    del workflow["on"]["pull_request"]
    _build(root, workflow, CONFORMING_CONTRACT)
    return _expect(root, red=True, label="pull_request trigger removed")


def _case_missing_merge_group(root: Path) -> bool:
    workflow = copy.deepcopy(CONFORMING_WORKFLOW)
    del workflow["on"]["merge_group"]
    _build(root, workflow, CONFORMING_CONTRACT)
    return _expect(root, red=True, label="merge_group trigger removed")


def _case_pre_merge_path_filter(root: Path) -> bool:
    """A paths filter is how a required context silently declines to run."""

    workflow = copy.deepcopy(CONFORMING_WORKFLOW)
    workflow["on"]["pull_request"] = {"paths": ["backend/**"]}
    _build(root, workflow, CONFORMING_CONTRACT)
    return _expect(root, red=True, label="pull_request narrowed by paths")


def _case_conditional_job(root: Path) -> bool:
    """A job gated to push:main is green-by-skip on a PR."""

    workflow = copy.deepcopy(CONFORMING_WORKFLOW)
    workflow["jobs"]["r-lane"]["if"] = "github.ref == 'refs/heads/main'"
    _build(root, workflow, CONFORMING_CONTRACT)
    return _expect(root, red=True, label="publishing job made conditional")


def _case_context_detached_from_contract(root: Path) -> bool:
    """The lane runs pre-merge but GitHub is never asked to block on it."""

    contract = copy.deepcopy(CONFORMING_CONTRACT)
    contract["required_contexts"] = []
    _build(root, CONFORMING_WORKFLOW, contract)
    return _expect(root, red=True, label="required context detached")


def _case_renamed_job(root: Path) -> bool:
    """A renamed job orphans the required context: it can never report."""

    workflow = copy.deepcopy(CONFORMING_WORKFLOW)
    workflow["jobs"]["r-lane"]["name"] = "R Lane Physics (renamed)"
    _build(root, workflow, CONFORMING_CONTRACT)
    return _expect(root, red=True, label="publishing job renamed")


CASES = (
    _case_missing_pre_merge_event,
    _case_missing_merge_group,
    _case_pre_merge_path_filter,
    _case_conditional_job,
    _case_context_detached_from_contract,
    _case_renamed_job,
)


def main() -> int:
    ok = True
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        _build(root, CONFORMING_WORKFLOW, CONFORMING_CONTRACT)
        ok &= _expect(root, red=False, label="baseline conforming lane")
        for case in CASES:
            ok &= case(root)
            # Exact restoration must return the validator to green.
            _build(root, CONFORMING_WORKFLOW, CONFORMING_CONTRACT)
            ok &= _expect(root, red=False, label=f"restored after {case.__name__}")

    if not ok:
        print("P13 merge-governance negative controls FAILED", file=sys.stderr)
        return 1
    print("P13 merge-governance negative controls: guard is non-vacuous")
    return 0


if __name__ == "__main__":
    sys.exit(main())
