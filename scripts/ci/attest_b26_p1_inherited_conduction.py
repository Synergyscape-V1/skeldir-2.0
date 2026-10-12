#!/usr/bin/env python3
"""Attest the exact-SHA independent B2.5 C19/C20/C21 preservation proof."""

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


SOURCE_CONTEXT = "B2.5-P13 E2E Trust Closure"
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
SOURCE_WORKFLOW_PATH = ".github/workflows/b2_5-p13-e2e-trust-closure.yml"
REQUIRED_JOBS = (
    "B2.5-P13 C19 Context-Robust Production Closure",
    "B2.5-P13 C20 Verdict Authority Conservation",
    "B2.5-P13 C21 Freshness and Issuance Authority Conservation",
    "B2.5-P14 Downstream Projection Safety",
)


class AttestationError(RuntimeError):
    """The exact candidate lacks a successful independent inherited proof."""


def _get(url: str, token: str) -> Any:
    request = urllib.request.Request(url)
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("X-GitHub-Api-Version", "2022-11-28")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError) as exc:
        raise AttestationError(f"github_query_failed:{exc}") from exc


def _all_check_runs(*, repository: str, sha: str, token: str) -> list[dict[str, Any]]:
    """Return every check run for the candidate, not only GitHub's first page."""
    checks: list[dict[str, Any]] = []
    page = 1
    while True:
        payload = _get(
            f"https://api.github.com/repos/{repository}/commits/{sha}/check-runs"
            f"?per_page=100&page={page}",
            token,
        )
        batch = payload.get("check_runs", [])
        if not isinstance(batch, list):
            raise AttestationError("github_check_runs_shape_invalid")
        checks.extend(batch)
        if len(batch) < 100:
            return checks
        page += 1


def _check_source_evidence(
    *, repository: str, sha: str, event: str, token: str
) -> tuple[dict[str, Any] | None, dict[str, str] | None, str]:
    """Probe one (sha, event) pair for successful source evidence.

    Returns (run, required, last). run/required are None when the pair
    currently carries no successful evidence; last names the reason.
    """
    last = "source_context_missing"
    checks = _all_check_runs(repository=repository, sha=sha, token=token)
    candidates = [check for check in checks if check.get("name") == SOURCE_CONTEXT]
    for check in candidates:
        details_url = str(check.get("details_url", ""))
        marker = "/actions/runs/"
        if marker not in details_url:
            continue
        run_id = details_url.split(marker, 1)[1].split("/", 1)[0]
        run = _get(
            f"https://api.github.com/repos/{repository}/actions/runs/{run_id}", token
        )
        if run.get("head_sha") != sha or run.get("event") != event:
            continue
        if not str(run.get("path", "")).startswith(SOURCE_WORKFLOW_PATH):
            continue
        if check.get("status") != "completed" or check.get("conclusion") != "success":
            last = (
                f"source_context_not_success:status={check.get('status')}:"
                f"conclusion={check.get('conclusion')}"
            )
            continue
        jobs_payload = _get(
            f"https://api.github.com/repos/{repository}/actions/runs/{run_id}/jobs?per_page=100",
            token,
        )
        jobs = {
            str(job.get("name")): str(job.get("conclusion"))
            for job in jobs_payload.get("jobs", [])
        }
        required = {name: jobs.get(name, "missing") for name in REQUIRED_JOBS}
        if any(result != "success" for result in required.values()):
            last = f"source_subordinate_not_success:{required}"
            continue
        return run, required, last
    return None, None, last


def _merge_tip_fallback(
    *, repository: str, sha: str, token: str
) -> tuple[dict[str, Any] | None, dict[str, str] | None, str, str]:
    """Accept PR-tip evidence when the merge introduced zero bytes.

    A metadata-only merge to main (e.g. a pin-only closeout) is skipped by
    the source workflow's push path filter, so no same-SHA push check can
    ever arrive. When the merge commit's tree is byte-identical to its
    second parent's tree (the PR tip, verified via the API commit objects,
    not assumed), the tip's pull_request source evidence is evidence about
    identical bytes and is strictly as strong. Returns
    (run, required, last, via); via is "" when no fallback applies.
    """
    try:
        commit = _get(f"https://api.github.com/repos/{repository}/commits/{sha}", token)
    except AttestationError as exc:
        return None, None, f"fallback_commit_unreadable:{exc}", ""
    parents = commit.get("parents", [])
    if not isinstance(parents, list) or len(parents) < 2:
        return None, None, "fallback_not_a_merge", ""
    tip_sha = str(parents[1].get("sha", ""))
    if not tip_sha:
        return None, None, "fallback_tip_sha_missing", ""
    try:
        tip = _get(
            f"https://api.github.com/repos/{repository}/commits/{tip_sha}", token
        )
    except AttestationError as exc:
        return None, None, f"fallback_tip_unreadable:{exc}", ""
    try:
        merge_tree = commit["commit"]["tree"]["sha"]
        tip_tree = tip["commit"]["tree"]["sha"]
    except (KeyError, TypeError):
        return None, None, "fallback_tree_shape_invalid", ""
    if merge_tree != tip_tree:
        return None, None, "fallback_tree_differs", ""
    run, required, last = _check_source_evidence(
        repository=repository, sha=tip_sha, event="pull_request", token=token
    )
    if run is None or required is None:
        return None, None, f"fallback_tip_no_evidence:{last}", ""
    via = f"merge-tip-tree-identical:{tip_sha[:12]}"
    return run, required, last, via


def _source_run(
    *,
    repository: str,
    sha: str,
    event: str,
    token: str,
    wait_seconds: int,
    poll_seconds: int,
) -> tuple[dict[str, Any], dict[str, str]]:
    deadline = time.monotonic() + wait_seconds
    last = "source_context_missing"
    via = ""
    while True:
        run, required, last = _check_source_evidence(
            repository=repository, sha=sha, event=event, token=token
        )
        if run is not None and required is not None:
            if via:
                required = dict(required)
                required["_source_via"] = via
            return run, required
        # Primary evidence absent. On a push landing, a tree-identical
        # merge tip's pull_request evidence closes the wait immediately
        # instead of idling until the deadline for a check that the push
        # path filter guarantees will never arrive.
        if event == "push":
            fb_run, fb_required, fb_last, fb_via = _merge_tip_fallback(
                repository=repository, sha=sha, token=token
            )
            if fb_run is not None and fb_required is not None:
                fb_required = dict(fb_required)
                fb_required["_source_via"] = fb_via
                return fb_run, fb_required
            if fb_last not in ("fallback_not_a_merge", "fallback_tree_differs"):
                last = f"{last};{fb_last}"
        if time.monotonic() >= deadline:
            raise AttestationError(last)
        print(f"B26_P1_INHERITED_WAIT {last}", flush=True)
        time.sleep(poll_seconds)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--sha", default=os.environ.get("B26_CANDIDATE_SHA"))
    parser.add_argument("--event", default=os.environ.get("GITHUB_EVENT_NAME"))
    parser.add_argument("--token", default=os.environ.get("GH_TOKEN"))
    parser.add_argument("--wait-seconds", type=int, default=2400)
    parser.add_argument("--poll-seconds", type=int, default=30)
    parser.add_argument("--evidence-out", required=True, type=Path)
    args = parser.parse_args()
    if not all((args.repository, args.sha, args.event, args.token)):
        print("B26_P1_INHERITED_ATTESTATION_FAIL missing_required_argument")
        return 1
    try:
        run, required = _source_run(
            repository=args.repository,
            sha=args.sha,
            event=args.event,
            token=args.token,
            wait_seconds=args.wait_seconds,
            poll_seconds=args.poll_seconds,
        )
    except AttestationError as exc:
        print(f"B26_P1_INHERITED_ATTESTATION_FAIL {exc}")
        return 1
    via = str(required.pop("_source_via", "direct-same-sha"))
    details = {
        "source_context": SOURCE_CONTEXT,
        "source_workflow": SOURCE_WORKFLOW_PATH,
        "source_run_id": str(run["id"]),
        "source_run_url": run["html_url"],
        "source_event": run["event"],
        "source_sha": run["head_sha"],
        "candidate_sha": args.sha,
        "source_via": via,
        "required_jobs": required,
    }
    from scripts.ci.b26_p1_evidence import write_evidence_cell  # noqa: PLC0415

    write_evidence_cell(
        args.evidence_out,
        gate_id="B26-P1-G1-G2-INHERITED-PHYSICS",
        producer="b26-p1-inherited-conduction",
        scenario_id="b25-p13-context-robust-production-closure",
        falsifier_id="inherited-C19-C20-C21-negative-controls",
        details=details,
    )
    print("B26_P1_INHERITED_ATTESTATION_PASS")
    print(json.dumps(details, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
