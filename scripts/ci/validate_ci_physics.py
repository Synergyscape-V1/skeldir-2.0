#!/usr/bin/env python3
"""Fail the build when a workflow drifts out of the throughput topology.

The topology documented in docs/ci/CI_TOPOLOGY_PHYSICS.md only stays true if
something enforces it. Without this guard a future phase can silently
reintroduce the pathology it removed - a workflow with no concurrency group
that lets abandoned commits burn runner slots, an uncached toolchain, or a
fan-out barrier that reserialises the graph - and nothing turns red.

Every rule below is a structural property of the YAML. None enumerates a path,
a module or a test name, so a new phase inherits all of them by existing; there
is no registry to update and nothing to rot.

A workflow opts out by carrying, anywhere in the file:

    # physics-exempt: <rule> - <reason>

The exemption lives in the workflow it applies to, so it is visible in review
and travels with the file. Valid rules: concurrency, merge_group, cache, fanout.

Usage:  python scripts/ci/validate_ci_physics.py [--verbose]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

WORKFLOWS = Path(".github/workflows")
VERBOSE = "--verbose" in sys.argv

# A job depended on by more than this many jobs is a fan-out barrier. It is only
# legitimate if it actually hands state to its dependents.
MAX_FANIN_WITHOUT_DATAFLOW = 5


def exempt(src: str, rule: str) -> str | None:
    m = re.search(rf"physics-exempt:\s*{re.escape(rule)}\b[ \-]*(.*)", src)
    return (m.group(1).strip() or "no reason given") if m else None


def triggers(doc: dict) -> dict:
    # YAML parses a bare `on:` key as the boolean True.
    raw = doc.get("on", doc.get(True, {}))
    if isinstance(raw, str):
        return {raw: None}
    if isinstance(raw, list):
        return {k: None for k in raw}
    return raw or {}


def norm_needs(body: dict) -> list[str]:
    n = body.get("needs") or []
    return [n] if isinstance(n, str) else list(n)


def check_workflow(path: Path) -> list[str]:
    src = path.read_text(encoding="utf-8")
    try:
        doc = yaml.safe_load(src)
    except yaml.YAMLError as exc:
        return [f"{path.name}: unparseable YAML - {exc}"]
    if not isinstance(doc, dict):
        return []

    fails: list[str] = []
    trig = triggers(doc)
    on_pr = "pull_request" in trig or "pull_request_target" in trig

    # --- rule: concurrency -------------------------------------------------
    if on_pr:
        reason = exempt(src, "concurrency")
        conc = doc.get("concurrency")
        if conc is None and reason is None:
            fails.append(
                f"{path.name}: has a pull_request trigger but no `concurrency:` block. "
                f"Abandoned commits will hold runner slots. Add the standard block or "
                f"`# physics-exempt: concurrency - <reason>`."
            )
        elif isinstance(conc, dict):
            cip = str(conc.get("cancel-in-progress", "")).strip()
            # Cancelling must be conditional on the event, never unconditional true,
            # or a push / merge_group audit run could be killed mid-proof.
            if cip.lower() == "true" and reason is None:
                fails.append(
                    f"{path.name}: `cancel-in-progress: true` is unconditional and can "
                    f"cancel a push or merge_group run. Gate it on "
                    f"github.event_name == 'pull_request'."
                )

    # --- rule: merge_group -------------------------------------------------
    if on_pr and "merge_group" not in trig and exempt(src, "merge_group") is None:
        fails.append(
            f"{path.name}: runs on pull_request but not on merge_group, so the merge "
            f"queue would not run it against the exact merge commit. Add `merge_group:` "
            f"or `# physics-exempt: merge_group - <reason>`."
        )

    # --- rule: cache -------------------------------------------------------
    if exempt(src, "cache") is None:
        for tool, key in (("python", "pip"), ("node", "npm")):
            pattern = re.compile(
                rf"uses:\s*actions/setup-{tool}@v\d+\s*\n(?P<body>(?:[ \t]+\S.*\n|[ \t]*\n)*)"
            )
            for m in pattern.finditer(src):
                if "cache:" not in m.group("body"):
                    line = src[: m.start()].count("\n") + 1
                    fails.append(
                        f"{path.name}:{line}: setup-{tool} without `cache: '{key}'`. "
                        f"Uncached installs burn the shared runner budget."
                    )

    # --- rule: fanout ------------------------------------------------------
    if exempt(src, "fanout") is None:
        jobs = doc.get("jobs") or {}
        fanin: dict[str, int] = {}
        for body in jobs.values():
            if not isinstance(body, dict):
                continue
            for dep in norm_needs(body):
                fanin[dep] = fanin.get(dep, 0) + 1
        for jid, count in sorted(fanin.items()):
            if count <= MAX_FANIN_WITHOUT_DATAFLOW:
                continue
            body = jobs.get(jid)
            if not isinstance(body, dict):
                continue
            declares_outputs = bool(body.get("outputs"))
            # Only an artifact that someone downloads counts as real dataflow.
            uploads = "upload-artifact" in yaml.safe_dump(body)
            consumed = "download-artifact" in src
            if not declares_outputs and not (uploads and consumed):
                fails.append(
                    f"{path.name}: job `{jid}` gates {count} jobs but transfers no data "
                    f"(no `outputs:`, no artifact consumed downstream). That is an "
                    f"ordering barrier: it serialises the graph and costs a dispatch "
                    f"round trip per tier. Keep the job and its required status check, "
                    f"but drop the `needs:` edges."
                )
    return fails


def main() -> int:
    files = sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml"))
    if not files:
        print("no workflow files found", file=sys.stderr)
        return 1

    all_fails: list[str] = []
    for path in files:
        fails = check_workflow(path)
        all_fails.extend(fails)
        if VERBOSE and not fails:
            print(f"  ok  {path.name}")

    print(f"\nCI physics guard: checked {len(files)} workflows")
    if all_fails:
        print(f"\n{len(all_fails)} violation(s):\n")
        for f in all_fails:
            print(f"  FAIL  {f}\n")
        print(
            "These rules keep CI throughput sub-linear in concurrent PRs.\n"
            "See docs/ci/CI_TOPOLOGY_PHYSICS.md for the measurements behind them."
        )
        return 1

    print("all workflows conform to the throughput topology")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
