#!/usr/bin/env python3
"""Remove `needs:` edges that order jobs without transferring data. Dry run unless --apply.

`checkout` and `validate-contracts` between them gate 108 of the 69 jobs in
ci.yml, but neither uploads an artifact nor declares an output, and ci.yml
contains no `download-artifact` call at all. Every job checks the repository out
for itself. The edges are therefore pure ordering constraints, and under a hard
concurrency cap they serialise an otherwise flat workload into tiers, each
boundary costing a dispatch round trip.

Both jobs are kept and both remain required status checks; only the ordering
constraint goes. The three jobs that genuinely read `needs.<job>.result` keep
their edges, and this script derives that set from the file rather than
hard-coding it, so it stays correct as jobs are added.

Re-introduction is prevented by .github/workflows/ci-physics-guard.yml, which
fails the build on any high-fan-in job that transfers no data.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

CI = Path(".github/workflows/ci.yml")
APPLY = "--apply" in sys.argv
BARRIERS = ("checkout", "validate-contracts")


def contract_pinned_jobs(jobs: dict) -> set[str]:
    """Job ids whose `needs:` some governance artefact pins.

    The repository states this invariant in two different shapes, and a topology
    change has to honour both:

      1. JSON, as ``required_ci_job.needs`` (B1.5-P7).
      2. A literal ``needs: [...]`` token asserted inside an enforcer script
         (B2.1-P6, B2.2-P5, B2.2-P6).

    Shape 2 is matched by resolving the token's dependency list back to the job
    that declares it, so this keeps working if a job is renamed.
    """
    import json

    pinned: set[str] = set()

    for path in sorted(Path("contracts-internal").rglob("*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(doc, dict):
            job = doc.get("required_ci_job")
            if isinstance(job, dict) and job.get("job_id") and job.get("needs"):
                pinned.add(str(job["job_id"]))

    token_re = re.compile(r'"(needs: \[[^"]*)"((?:\s*\n\s*"[^"]*")*)', re.M)
    for path in sorted(Path("scripts/ci").glob("enforce_*.py")):
        src = path.read_text(encoding="utf-8", errors="replace")
        for m in token_re.finditer(src):
            token = m.group(1) + "".join(re.findall(r'"([^"]*)"', m.group(2) or ""))
            if "]" not in token:
                continue
            deps = {d.strip() for d in token[token.index("[") + 1 : token.index("]")].split(",") if d.strip()}
            for jid, body in jobs.items():
                cur = body.get("needs") or []
                if isinstance(cur, str):
                    cur = [cur]
                # The job whose non-barrier deps match the pinned token.
                if deps - set(BARRIERS) == set(cur) - set(BARRIERS) and deps - set(BARRIERS):
                    pinned.add(jid)
    return pinned


def job_owner_map(lines: list[str]) -> list[tuple[int, str]]:
    return [
        (i, m.group(1))
        for i, line in enumerate(lines)
        if (m := re.match(r"^  ([A-Za-z0-9_-]+):\s*$", line))
    ]


def owner_of(starts: list[tuple[int, str]], idx: int) -> str | None:
    current = None
    for i, jid in starts:
        if i <= idx:
            current = jid
        else:
            break
    return current


def main() -> int:
    src = CI.read_text(encoding="utf-8")
    lines = src.split("\n")
    starts = job_owner_map(lines)

    # Jobs that read needs.<barrier>.result consume real state and keep their edges.
    keep: set[str] = set()
    for i, line in enumerate(lines):
        if any(f"needs.{b}." in line for b in BARRIERS):
            if (own := owner_of(starts, i)) is not None:
                keep.add(own)
    print(f"data-consuming jobs (edges preserved): {sorted(keep)}")

    # A governance contract may pin a job's needs for audit reasons that have
    # nothing to do with dataflow. B1.5-P7 does exactly this, and its enforcer
    # failed the build when these edges were stripped - correctly. Contracted
    # ordering outranks the throughput argument, and reading it from the
    # contracts keeps that true as phases add their own.
    contracted = contract_pinned_jobs()
    if contracted:
        print(f"contract-pinned jobs (edges preserved): {sorted(contracted)}\n")
    keep |= contracted

    out: list[str] = []
    removed = 0
    touched: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^(\s{4})needs:\s*(.*)$", line)
        if not m:
            out.append(line)
            i += 1
            continue

        indent, inline = m.group(1), m.group(2).strip()
        job = owner_of(starts, i)
        block_end = i + 1

        if inline.startswith("["):
            raw = inline
            while "]" not in raw and block_end < len(lines):
                raw += " " + lines[block_end].strip()
                block_end += 1
            body = raw[raw.index("[") + 1 : raw.rindex("]")]
            deps = [d.strip() for d in body.split(",") if d.strip()]
        elif inline:
            # A scalar dep may carry a trailing comment: `needs: checkout  # why`
            deps = [inline.split("#", 1)[0].strip()]
        else:
            deps = []
            while block_end < len(lines):
                dm = re.match(rf"^{indent}  -\s*([A-Za-z0-9_-]+)\s*$", lines[block_end])
                if not dm:
                    break
                deps.append(dm.group(1))
                block_end += 1

        if job in keep:
            out.extend(lines[i:block_end])
            i = block_end
            continue

        kept = [d for d in deps if d not in BARRIERS]
        dropped = len(deps) - len(kept)
        if dropped:
            removed += dropped
            touched.append(f"{job}: -{dropped} ({', '.join(d for d in deps if d in BARRIERS)})")
        if kept:
            out.append(f"{indent}needs: [{', '.join(kept)}]")
        elif not dropped:
            out.extend(lines[i:block_end])
        # else: every dep was a barrier, so the needs: key disappears entirely
        i = block_end

    result = "\n".join(out)

    doc = yaml.safe_load(result)
    jobs = doc["jobs"]
    for jid, body in jobs.items():
        for dep in body.get("needs", []) or []:
            if dep not in jobs:
                print(f"ERROR: {jid} needs unknown job {dep}")
                return 1
    for jid in keep:
        if not set(jobs[jid].get("needs", []) or []) & set(BARRIERS):
            print(f"ERROR: {jid} lost an edge it consumes")
            return 1
    for barrier in BARRIERS:
        if barrier not in jobs:
            print(f"ERROR: {barrier} job was deleted - it must be kept")
            return 1

    depth_before = sum(1 for b in yaml.safe_load(src)["jobs"].values() if b.get("needs"))
    depth_after = sum(1 for b in jobs.values() if b.get("needs"))
    print("\n".join(f"  {t}" for t in touched[:6]))
    print(f"  ... {len(touched)} jobs touched\n")
    print(f"edges removed          : {removed}")
    print(f"jobs with any needs    : {depth_before} -> {depth_after}")
    print(f"jobs now unblocked at t0: {sum(1 for b in jobs.values() if not b.get('needs'))} of {len(jobs)}")
    print(f"\n{'APPLIED' if APPLY else 'DRY RUN - nothing written'}")
    if APPLY:
        CI.write_text(result, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
