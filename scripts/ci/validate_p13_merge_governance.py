#!/usr/bin/env python3
"""B2.5-P13 Corrective XX, Gate XX2-E: adversarial physics must block a merge.

The defect this exists to prevent already happened once. PR #697 carried the
early-validation DLQ escape through the ALLGREEN merge queue at 09:20:30Z; the
`R2: Data-Truth Hardening` run that caught it started at 09:20:33Z — three
seconds after the code was already on protected main. R2/R3/R4/R6/R7 declared
only `workflow_dispatch` and `push: [main]`, so they were structurally incapable
of blocking anything. Both independent audits called this dispositive.

Adding `pull_request:` to those workflows is necessary and not sufficient. A
lane blocks a merge only when the whole conjunction holds:

    the workflow runs on pull_request AND on merge_group
    AND those events carry no filter that can decline to run
    AND the job publishing the required context exists and is unconditional
    AND that context name is in the required-status-check contract

The last clause is bound to live GitHub state by
`validate_live_branch_protection.py`, which compares the same contract file
against the real branch-protection API and is itself a required context. This
script owns the first four, which are structural properties of the YAML and so
can be checked on any checkout, including one that has no token.

Run:  python scripts/ci/validate_p13_merge_governance.py [--verbose]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml


CONTRACT_RELATIVE = (
    "contracts-internal/governance/b03_phase2_required_status_checks.main.json"
)
CONTRACT_KEY = "p13_merge_blocking_physics"

# A required context that can decline to run is a required context that never
# blocks: GitHub treats "never reported" as pending, and the merge queue's
# check-response timeout eventually gives up rather than refusing the merge.
FORBIDDEN_EVENT_FILTERS = ("paths", "paths-ignore", "branches", "branches-ignore")

REQUIRED_PRE_MERGE_EVENTS = ("pull_request", "merge_group")


class GovernanceError(RuntimeError):
    pass


def _load_contract(root: Path) -> dict[str, Any]:
    path = root / CONTRACT_RELATIVE
    if not path.is_file():
        raise GovernanceError(f"missing governance contract: {CONTRACT_RELATIVE}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data.get("required_contexts"), list):
        raise GovernanceError("contract missing required_contexts")
    declared = data.get(CONTRACT_KEY)
    if not isinstance(declared, dict) or not declared.get("lanes"):
        raise GovernanceError(
            f"contract missing {CONTRACT_KEY}.lanes: the load-bearing pre-merge"
            " physics must be declared, not inferred from workflow filenames"
        )
    return data


def _load_workflow(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    if not path.is_file():
        raise GovernanceError(f"declared lane workflow is missing: {relative}")
    # PyYAML resolves the bare key `on` to the boolean True (YAML 1.1).
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise GovernanceError(f"{relative} is not a workflow mapping")
    return document


def _triggers(document: dict[str, Any]) -> dict[str, Any]:
    for key in ("on", True):
        if key in document:
            raw = document[key]
            break
    else:
        return {}
    if isinstance(raw, str):
        return {raw: None}
    if isinstance(raw, list):
        return {item: None for item in raw}
    if isinstance(raw, dict):
        return raw
    return {}


def _check_lane(root: Path, name: str, lane: dict[str, Any], contract: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    workflow_relative = lane.get("workflow")
    context = lane.get("required_context")
    if not workflow_relative or not context:
        return [f"{name}: lane declaration needs 'workflow' and 'required_context'"]

    document = _load_workflow(root, workflow_relative)
    triggers = _triggers(document)

    for event in REQUIRED_PRE_MERGE_EVENTS:
        if event not in triggers:
            failures.append(
                f"{name}: {workflow_relative} does not run on '{event}', so it"
                " cannot adjudicate a candidate before it reaches main"
            )
            continue
        filters = triggers.get(event)
        if isinstance(filters, dict):
            present = [key for key in FORBIDDEN_EVENT_FILTERS if key in filters]
            if present:
                failures.append(
                    f"{name}: {workflow_relative} filters '{event}' by {present};"
                    " a required context that can skip never blocks a merge"
                )

    jobs = document.get("jobs")
    if not isinstance(jobs, dict):
        failures.append(f"{name}: {workflow_relative} declares no jobs")
        return failures

    owning = [
        (job_id, job)
        for job_id, job in jobs.items()
        if isinstance(job, dict) and job.get("name") == context
    ]
    if not owning:
        published = sorted(
            str(job.get("name") or job_id)
            for job_id, job in jobs.items()
            if isinstance(job, dict)
        )
        failures.append(
            f"{name}: no job in {workflow_relative} publishes the required"
            f" context {context!r}; it publishes {published}"
        )
    for job_id, job in owning:
        if "if" in job:
            failures.append(
                f"{name}: job {job_id!r} publishing {context!r} is conditional"
                f" (if: {job['if']!r}); a skipped required context is not a"
                " passed one, and the merge queue will wait on it forever"
            )

    if context not in contract["required_contexts"]:
        failures.append(
            f"{name}: {context!r} is not in required_contexts, so GitHub is not"
            " asked to block on it"
        )
    return failures


def validate(root: Path, *, verbose: bool = False) -> list[str]:
    contract = _load_contract(root)
    lanes = contract[CONTRACT_KEY]["lanes"]
    failures: list[str] = []
    for name, lane in sorted(lanes.items()):
        lane_failures = _check_lane(root, name, lane, contract)
        failures.extend(lane_failures)
        if verbose and not lane_failures:
            print(
                f"OK  {name}: {lane['required_context']} is mandatory pre-merge"
            )
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    try:
        failures = validate(root, verbose=args.verbose)
    except GovernanceError as exc:
        print(f"P13 MERGE GOVERNANCE ERROR: {exc}", file=sys.stderr)
        return 2
    if failures:
        print("P13 MERGE GOVERNANCE FAIL", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1
    print("P13 merge governance: every declared load-bearing lane blocks a merge")
    return 0


if __name__ == "__main__":
    sys.exit(main())
