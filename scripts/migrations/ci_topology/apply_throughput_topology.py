#!/usr/bin/env python3
"""Apply the CI throughput topology to every workflow. Dry run unless --apply.

Three mechanical transforms, all structural properties of the YAML rather than
enumerations of paths, modules or test names, so new phases inherit them with
no edit to this script:

  L1  concurrency group + PR-scoped cancel-in-progress
  L3  native dependency caching on setup-python / setup-node
  L4  merge_group trigger wherever pull_request already fires

A workflow opts out of any rule by carrying the marker comment
``physics-exempt: <rule>`` with a reason. The exemption lives in the file it
applies to, so it travels with the workflow and is visible in review; there is
no central list to rot.

Verified by .github/workflows/ci-physics-guard.yml, which fails the build if a
workflow drifts out of compliance.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ci"))
from _workflow_physics import CACHE_KEY, job_installs, job_spans, owning_job  # noqa: E402

WORKFLOWS = Path(".github/workflows")
APPLY = "--apply" in sys.argv

# Group is per-PR on pull_request events so a new push supersedes the old run.
# On push and merge_group it falls back to run_id, which is unique per run, so
# those runs are never cancelled and never queued behind one another. The
# cancel-in-progress expression is belt-and-braces on top of that.
CONCURRENCY_BLOCK = (
    "concurrency:\n"
    "  # PR events: one live run per workflow per PR - a new push supersedes the old.\n"
    "  # push / merge_group: run_id is unique, so those runs are never cancelled\n"
    "  # and never queued. The audit proof on an exact SHA always runs to completion.\n"
    "  group: ${{ github.workflow }}-${{ github.event.pull_request.number || github.run_id }}\n"
    "  cancel-in-progress: ${{ github.event_name == 'pull_request' }}\n"
    "\n"
)


def exempt(src: str, rule: str) -> bool:
    return re.search(rf"physics-exempt:\s*{re.escape(rule)}\b", src) is not None


def add_concurrency(src: str) -> tuple[str, bool]:
    if re.search(r"^concurrency:", src, re.M) or exempt(src, "concurrency"):
        return src, False
    m = re.search(r"^on:.*?(?=^\S)", src, re.M | re.S)
    if not m:
        return src, False
    return src[: m.end()] + CONCURRENCY_BLOCK + src[m.end():], True


def add_merge_group(src: str) -> tuple[str, bool]:
    # Match the trigger key, not the bare word - the concurrency comment
    # inserted above mentions merge_group in prose.
    if re.search(r"^\s{2}merge_group:", src, re.M) or exempt(src, "merge_group"):
        return src, False
    m = re.search(r"^on:\s*\n", src, re.M)
    if not m or not re.search(r"^\s{2}pull_request:", src, re.M):
        return src, False
    return src[: m.end()] + "  merge_group:\n" + src[m.end():], True


def add_cache(src: str) -> tuple[str, int]:
    """Append a cache key to setup-python / setup-node in jobs that install deps.

    Only jobs that install anything get a key: setup-*'s post-run cache-save
    step fails outright when the cache directory was never created.
    """
    if exempt(src, "cache"):
        return src, 0
    added = 0
    out: list[str] = []
    lines = src.split("\n")
    spans = job_spans(lines)
    i = 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        m = re.match(r"^(\s*)-?\s*uses: actions/setup-(python|node)@v\d+\s*$", line)
        if not m:
            i += 1
            continue
        tool = m.group(2)
        own = owning_job(spans, i)
        if own is None or not job_installs(lines, own[1], own[2], tool):
            i += 1
            continue
        # Consume the adjacent `with:` block, if any, tracking its indentation.
        j = i + 1
        with_indent = None
        body: list[str] = []
        while j < len(lines):
            nxt = lines[j]
            if with_indent is None:
                wm = re.match(r"^(\s*)with:\s*$", nxt)
                if wm:
                    with_indent = wm.group(1)
                    body.append(nxt)
                    j += 1
                    continue
                break
            if nxt.strip() and not nxt.startswith(with_indent + "  "):
                break
            body.append(nxt)
            j += 1
        if with_indent is None:
            i += 1
            continue
        if any(re.match(r"^\s*cache:", b) for b in body):
            out.extend(body)
            i = j
            continue
        # Trailing blank lines belong after the key we are about to insert.
        while body and not body[-1].strip():
            body.pop()
            j -= 1
        body.append(f"{with_indent}  cache: '{CACHE_KEY[tool]}'")
        out.extend(body)
        added += 1
        i = j
    return "\n".join(out), added


def main() -> int:
    totals = {"files": 0, "concurrency": 0, "merge_group": 0, "cache": 0}
    broken: list[str] = []

    for path in sorted(WORKFLOWS.glob("*.yml")):
        original = path.read_text(encoding="utf-8")
        src, c_conc = add_concurrency(original)
        src, c_mg = add_merge_group(src)
        src, c_cache = add_cache(src)
        if src == original:
            continue

        try:
            yaml.safe_load(src)
        except yaml.YAMLError as exc:
            broken.append(f"{path.name}: {exc}")
            continue

        totals["files"] += 1
        totals["concurrency"] += int(c_conc)
        totals["merge_group"] += int(c_mg)
        totals["cache"] += c_cache
        print(
            f"  {path.name:<52} concurrency={'+' if c_conc else '.'}"
            f" merge_group={'+' if c_mg else '.'} cache=+{c_cache}"
        )
        if APPLY:
            path.write_text(src, encoding="utf-8")

    print(f"\n{'APPLIED' if APPLY else 'DRY RUN - nothing written'}")
    for key, value in totals.items():
        print(f"  {key:<12}: {value}")

    if broken:
        print("\nYAML INVALID AFTER TRANSFORM - not written:")
        for entry in broken:
            print(f"  {entry}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
