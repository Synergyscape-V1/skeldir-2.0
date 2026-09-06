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
and travels with the file. Valid rules: concurrency, merge_group, cache, fanout,
advisory-merge-group, advisory-pr-paths.

Rules merge_group/advisory-merge-group/advisory-pr-paths distinguish REQUIRED
lanes (produce >=1 context from the required-status-checks contract, matrix
stems included) from ADVISORY lanes (produce none):
- required lanes MUST fire on merge_group (rules merge_group + coverage);
- advisory lanes MUST NOT occupy merge_group burst (rule advisory-merge-group)
  and MUST declare pull_request paths (rule advisory-pr-paths), so advisory
  execution is risk-selected while merge authority stays total.

Usage:  python scripts/ci/validate_ci_physics.py [--verbose]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _workflow_physics import (  # noqa: E402
    CACHE_KEY,
    contract_pinned_jobs,
    job_installs,
    job_spans,
    owning_job,
)

WORKFLOWS = Path(".github/workflows")
VERBOSE = "--verbose" in sys.argv

CONTRACT = Path("contracts-internal/governance/b03_phase2_required_status_checks.main.json")

# A job depended on by more than this many jobs is a fan-out barrier. It is only
# legitimate if it actually hands state to its dependents.
MAX_FANIN_WITHOUT_DATAFLOW = 5


def load_required_contexts() -> set[str] | None:
    """Required contexts from the in-repo governance contract.

    Returns None when the contract is missing or unparseable. Callers treat
    None as "authority unreadable" and fail closed: every pull_request workflow
    is assumed required, so missing merge_group still fails. An unreadable
    contract must never silently excuse a lane from merge authority.
    """
    import json

    try:
        doc = json.loads(CONTRACT.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    contexts = doc.get("required_contexts", [])
    return set(contexts) if isinstance(contexts, list) else set()


def produced_names(doc: dict) -> set[str]:
    """Every check-run name a workflow file can emit (workflow + job names)."""
    names: set[str] = set()
    if doc.get("name"):
        names.add(str(doc["name"]))
    for jid, body in (doc.get("jobs") or {}).items():
        names.add(str(jid))
        if isinstance(body, dict) and body.get("name"):
            names.add(str(body["name"]))
    return names


def produces_required(doc: dict, contexts: set[str] | None) -> tuple[bool, list[str]]:
    """Whether the workflow produces >=1 required context.

    Matrix-expanded names (e.g. "Phase Gates (B0.3)") never appear literally in
    YAML, so a context also matches via its stem ("Phase Gates"). When contexts
    is None (contract unreadable) the workflow is treated as required: fail
    closed, never silently advisory.
    """
    names = produced_names(doc)
    if contexts is None:
        return True, []
    matched = [c for c in contexts if c in names]
    if not matched:
        stems = {c.split(" (")[0] for c in contexts if " (" in c}
        matched = [c for c in contexts if c.split(" (")[0] in names and c.split(" (")[0] in stems]
        # Also match when the stem itself is a declared name.
        stem_hits = [s for s in stems if s in names]
        matched = sorted(set(matched) | {c for c in contexts for s in stem_hits if c.startswith(s + " (") or c == s})
    return (len(matched) > 0), sorted(set(matched))


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


def check_workflow(path: Path, contexts: set[str] | None = None) -> list[str]:
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
    is_required, _matched = produces_required(doc, contexts)

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
            # A workflow that can cancel must key its group on the event too.
            # pull_request and pull_request_target both fire for the same PR and
            # yield the same pull_request.number, so without the event in the group
            # the two runs share it and cancel each other. That cancelled three
            # required contexts on PR #653, and a cancelled required context blocks
            # the merge exactly like a failing one.
            group = str(conc.get("group", ""))
            if (
                cip.lower() != "false"
                and "github.event_name" not in group
                and reason is None
            ):
                fails.append(
                    f"{path.name}: concurrency group `{group}` does not include "
                    f"`github.event_name`, but the workflow can cancel in progress. "
                    f"pull_request and pull_request_target fire for the same PR and "
                    f"would share this group, cancelling each other."
                )

    # --- rule: merge_group (REQUIRED lanes) ---------------------------------
    # Only lanes that produce merge-blocking contexts must fire on merge_group.
    # Advisory lanes are forbidden there by advisory-merge-group below; the two
    # rules together give exactly-one burst membership per lane class.
    if (
        on_pr
        and is_required
        and "merge_group" not in trig
        and exempt(src, "merge_group") is None
    ):
        fails.append(
            f"{path.name}: runs on pull_request and produces a required context but "
            f"not on merge_group, so the merge queue would not run it against the "
            f"exact merge commit. Add `merge_group:` or "
            f"`# physics-exempt: merge_group - <reason>`."
        )

    # --- rule: advisory-merge-group (ADVISORY lanes) ---------------------------
    # A lane that produces zero required contexts purchases no merge information:
    # the queue adjudicates it to nothing. Firing it there anyway holds one of 20
    # shared slots per run while the required lanes it accompanies sit queued.
    if (
        "merge_group" in trig
        and not is_required
        and exempt(src, "advisory-merge-group") is None
    ):
        fails.append(
            f"{path.name}: produces no required context but fires on merge_group, "
            f"occupying merge-queue burst while adjudicating nothing. Remove "
            f"`merge_group:` (keep push/schedule/dispatch for post-merge forensics) "
            f"or `# physics-exempt: advisory-merge-group - <reason>`."
        )

    # --- rule: advisory-pr-paths (ADVISORY lanes) ------------------------------
    # An advisory lane that fires unconditionally on every pull_request taxes
    # every change for the benefit of none in particular. It must declare
    # pull_request paths scoping it to its owned surface (including its own
    # workflow file, docs/ci and the governance contract when CI-infra edits
    # must exercise it), or exempt with a universality reason. Required lanes
    # stay unfiltered: a path-filtered required check that never reports blocks
    # its PR forever (P12 precedent).
    if on_pr and not is_required and exempt(src, "advisory-pr-paths") is None:
        pr_block = trig.get("pull_request")
        has_paths = isinstance(pr_block, dict) and "paths" in (pr_block or {})
        prt_block = trig.get("pull_request_target")
        has_prt_paths = isinstance(prt_block, dict) and "paths" in (prt_block or {})
        needs_paths = ("pull_request" in trig and not has_paths) or (
            "pull_request_target" in trig and not has_prt_paths
        )
        if needs_paths:
            fails.append(
                f"{path.name}: produces no required context but fires on "
                f"pull_request without `paths:`, taxing every PR. Scope it to its "
                f"owned surface (including its own workflow file so CI-infra edits "
                f"still exercise it) or "
                f"`# physics-exempt: advisory-pr-paths - <reason>`."
            )

    # --- rule: cache -------------------------------------------------------
    # Only jobs that actually install dependencies need a cache key. Adding one
    # to a job that installs nothing makes setup-*'s post-run cache-save step
    # fail, because the cache directory was never created.
    if exempt(src, "cache") is None:
        lines = src.split("\n")
        spans = job_spans(lines)
        for i, line in enumerate(lines):
            m = re.match(r"^\s*-?\s*uses:\s*actions/setup-(python|node)@v\d+\s*$", line)
            if not m:
                continue
            tool = m.group(1)
            own = owning_job(spans, i)
            if own is None:
                continue
            jid, start, end = own
            installs = job_installs(lines, start, end, tool)
            # The step's own `with:` block, bounded by the next step.
            block: list[str] = []
            for j in range(i + 1, min(i + 14, len(lines))):
                if re.match(r"^\s*-\s+\S", lines[j]):
                    break
                block.append(lines[j])
            has_cache = any(re.match(r"^\s*cache:", b) for b in block)
            if installs and not has_cache:
                fails.append(
                    f"{path.name}:{i + 1}: job `{jid}` installs {tool} dependencies but "
                    f"setup-{tool} has no `cache: '{CACHE_KEY[tool]}'`. Uncached installs "
                    f"burn the shared runner budget."
                )
            elif not installs and has_cache:
                fails.append(
                    f"{path.name}:{i + 1}: job `{jid}` installs no {tool} dependencies but "
                    f"setup-{tool} sets `cache:`. The post-run cache-save step fails when "
                    f"the cache directory was never created. Remove the key."
                )

    # --- rule: fanout ------------------------------------------------------
    if exempt(src, "fanout") is None:
        jobs = doc.get("jobs") or {}
        # An edge a governance contract pins is not a throughput decision, so it
        # must not count toward the fan-out budget. Without this, a future phase
        # pinning one more edge would push a hub past the threshold and this rule
        # would demand the removal of an edge another gate demands be present -
        # two governance rules in direct contradiction.
        pinned = contract_pinned_jobs(jobs)
        fanin: dict[str, int] = {}
        for jid, body in jobs.items():
            if not isinstance(body, dict) or jid in pinned:
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


def check_merge_queue_coverage(files: list[Path]) -> list[str]:
    """Every required context must be produced by a workflow that fires on merge_group.

    A merge queue only merges once every required context reports against the
    speculative merge commit. A required context whose workflow does not fire on
    merge_group can never report there, so the entry sits in the queue until it
    times out - and the symptom reads as "the queue is broken", not "that workflow
    is missing a trigger". The repository has already been bitten by this shape of
    defect: b2_5-p13-e2e-trust-closure.yml records a path-filtered required check
    blocking PRs forever, found in P12 and again across P8-P11.

    Rule 2 checks this per workflow; this checks the set of contexts the branch is
    actually protected by, read from the in-repo contract so it works offline and
    on a PR-scoped token.
    """
    import json

    if not CONTRACT.exists():
        return []
    try:
        contexts = json.loads(CONTRACT.read_text(encoding="utf-8")).get("required_contexts", [])
    except (json.JSONDecodeError, OSError):
        return []

    index: dict[str, dict] = {}
    for path in files:
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue
        if not isinstance(doc, dict):
            continue
        names = {str(doc["name"])} if doc.get("name") else set()
        for jid, body in (doc.get("jobs") or {}).items():
            names.add(str(jid))
            if isinstance(body, dict) and body.get("name"):
                names.add(str(body["name"]))
        index[path.name] = {"names": names, "mg": "merge_group" in triggers(doc)}

    fails: list[str] = []
    for ctx in contexts:
        owners = [n for n, d in index.items() if ctx in d["names"]]
        if not owners:
            # Matrix-expanded names like "Phase Gates (B0.3)" never appear literally.
            stem = ctx.split(" (")[0]
            owners = [n for n, d in index.items() if stem in d["names"]]
        if not owners:
            fails.append(
                f"required context `{ctx}` is produced by no workflow. It can never report, "
                f"so it blocks every PR and every merge-queue entry indefinitely."
            )
        elif not any(index[n]["mg"] for n in owners):
            fails.append(
                f"required context `{ctx}` is produced by {', '.join(owners)}, which does not "
                f"fire on merge_group. The merge queue would wait for a status that can never "
                f"arrive. Add `merge_group:` to that workflow."
            )
    return fails


def main() -> int:
    files = sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml"))
    if not files:
        print("no workflow files found", file=sys.stderr)
        return 1

    contexts = load_required_contexts()
    all_fails: list[str] = check_merge_queue_coverage(files)
    for path in files:
        fails = check_workflow(path, contexts)
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
