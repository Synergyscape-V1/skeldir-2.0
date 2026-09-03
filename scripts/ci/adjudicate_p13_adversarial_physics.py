#!/usr/bin/env python3
"""B2.5-P13 Corrective XX: adjudicate that the adversarial lanes actually ran.

Branch protection asks GitHub whether a named context is green. That is not the
same question as "did the adversarial proof execute". A workflow can report a
context as ``skipped`` or ``neutral``, and GitHub will treat the branch rule as
satisfied — which is precisely the automatic NOT-COMPLETE condition the phase
directive names: *"required context is green because the real adversarial job
skipped"*.

This adjudicator asks the stronger question directly, against the check-runs
API for the exact SHA under adjudication:

    for every declared load-bearing lane
        a check-run with that exact name exists for this SHA
        AND its status is completed
        AND its conclusion is exactly "success"

`skipped`, `neutral`, `cancelled`, `timed_out`, `action_required` and a missing
check-run are all refusals. The lanes run concurrently with this job, so it
waits for them, bounded, and fails closed if the bound is reached.

It replaces `R7 Final Winning State` as the merge blocker. R7 aggregates the
same four proofs by re-running them sequentially against one PostgreSQL server,
with each phase on its own freshly created database — co-tenancy, not state
conduction — so it adds resource-soak coverage rather than a distinct truth. Its
harness produced three different non-product failures in four pre-merge runs; a
financial-truth gate cannot rest on that. The compositional proof that *does*
carry state between processes is `B2.5-P13 E2E Trust Closure`, which remains
required.

On `push` this reports what it observes without asserting: the lanes carry path
filters on push, so absence there is lawful. Pre-merge, absence is a refusal.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "contracts-internal/governance/b03_phase2_required_status_checks.main.json"
CONTRACT_KEY = "p13_merge_blocking_physics"

ACCEPTED_CONCLUSION = "success"
PRE_MERGE_EVENTS = {"pull_request", "pull_request_target", "merge_group"}


class AdjudicationError(RuntimeError):
    pass


def _declared_lanes() -> dict[str, str]:
    data = json.loads(CONTRACT.read_text(encoding="utf-8"))
    lanes = data.get(CONTRACT_KEY, {}).get("lanes")
    if not isinstance(lanes, dict) or not lanes:
        raise AdjudicationError(f"contract missing {CONTRACT_KEY}.lanes")
    resolved: dict[str, str] = {}
    for name, lane in lanes.items():
        context = lane.get("required_context")
        if not context:
            raise AdjudicationError(f"lane {name} declares no required_context")
        # The adjudicator cannot adjudicate itself.
        if lane.get("adjudicator"):
            continue
        resolved[name] = str(context)
    return resolved


def _check_runs(repository: str, sha: str, token: str) -> dict[str, dict[str, Any]]:
    observed: dict[str, dict[str, Any]] = {}
    page = 1
    while True:
        url = (
            f"https://api.github.com/repos/{repository}/commits/{sha}"
            f"/check-runs?per_page=100&page={page}"
        )
        request = urllib.request.Request(url)
        request.add_header("Authorization", f"Bearer {token}")
        request.add_header("Accept", "application/vnd.github+json")
        request.add_header("X-GitHub-Api-Version", "2022-11-28")
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError) as exc:
            raise AdjudicationError(f"check-runs query failed: {exc}") from exc
        runs = payload.get("check_runs", [])
        for run in runs:
            name = str(run.get("name"))
            previous = observed.get(name)
            # Keep the most decisive report for a name: a completed success wins
            # over a rerun still in progress.
            if previous is None or (
                previous.get("conclusion") != ACCEPTED_CONCLUSION
                and run.get("conclusion") == ACCEPTED_CONCLUSION
            ):
                observed[name] = run
        if len(runs) < 100:
            break
        page += 1
    return observed


def adjudicate(
    *,
    repository: str,
    sha: str,
    token: str,
    event_name: str,
    wait_seconds: int,
    poll_seconds: int,
) -> int:
    lanes = _declared_lanes()
    enforcing = event_name in PRE_MERGE_EVENTS
    print(f"p13_adversarial_physics_adjudication sha={sha} event={event_name}")
    print(f"enforcing={'yes' if enforcing else 'no (post-merge observation)'}")
    for name, context in sorted(lanes.items()):
        print(f"  declared lane {name} -> {context!r}")

    deadline = time.monotonic() + wait_seconds
    while True:
        observed = _check_runs(repository, sha, token)
        verdicts: dict[str, str] = {}
        for context in lanes.values():
            run = observed.get(context)
            if run is None:
                verdicts[context] = "absent"
            elif run.get("status") != "completed":
                verdicts[context] = f"pending:{run.get('status')}"
            else:
                verdicts[context] = str(run.get("conclusion"))
        # A query against the wrong SHA looks identical to "no lane ran". Say
        # how many check-runs were visible at all so the two cannot be
        # confused in a log.
        print(f"  check_runs_visible_on_sha={len(observed)}")
        unsettled = [c for c, v in verdicts.items() if v.startswith("pending")]
        if enforcing:
            unsettled += [c for c, v in verdicts.items() if v == "absent"]
        if not unsettled or time.monotonic() >= deadline:
            break
        print(f"  waiting on {sorted(set(unsettled))}")
        time.sleep(poll_seconds)

    print("adjudication:")
    for context, verdict in sorted(verdicts.items()):
        print(f"  {context} = {verdict}")

    if not enforcing:
        print("P13_ADVERSARIAL_PHYSICS_OBSERVED (not enforcing on this event)")
        return 0

    refused = sorted(
        f"{context}={verdict}"
        for context, verdict in verdicts.items()
        if verdict != ACCEPTED_CONCLUSION
    )
    if refused:
        print("P13_ADVERSARIAL_PHYSICS_ADJUDICATION_FAIL", file=sys.stderr)
        for item in refused:
            print(f"  refused: {item}", file=sys.stderr)
        print(
            "  a skipped, absent or failed lane is not a passed one: the phase"
            " requires the adversarial proof to have executed",
            file=sys.stderr,
        )
        return 1
    print("P13_ADVERSARIAL_PHYSICS_ADJUDICATION_PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", default=os.getenv("GITHUB_REPOSITORY", ""))
    parser.add_argument("--sha", default=os.getenv("GITHUB_SHA", ""))
    parser.add_argument("--event-name", default=os.getenv("GITHUB_EVENT_NAME", "local"))
    parser.add_argument("--wait-seconds", type=int, default=2400)
    parser.add_argument("--poll-seconds", type=int, default=30)
    parser.add_argument("--list-lanes", action="store_true")
    args = parser.parse_args()

    try:
        if args.list_lanes:
            for name, context in sorted(_declared_lanes().items()):
                print(f"{name}\t{context}")
            return 0
        token = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN") or ""
        if not (args.repository and args.sha and token):
            raise AdjudicationError(
                "repository, sha and a GH_TOKEN/GITHUB_TOKEN credential are required"
            )
        return adjudicate(
            repository=args.repository,
            sha=args.sha,
            token=token,
            event_name=args.event_name,
            wait_seconds=args.wait_seconds,
            poll_seconds=args.poll_seconds,
        )
    except AdjudicationError as exc:
        print(f"P13_ADVERSARIAL_PHYSICS_ADJUDICATION_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
