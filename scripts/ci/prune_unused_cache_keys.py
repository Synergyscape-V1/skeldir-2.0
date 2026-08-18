#!/usr/bin/env python3
"""Remove `cache:` keys from setup steps in jobs that install nothing. Dry run unless --apply.

actions/setup-python and setup-node fail their post-run cache-save step when the
cache directory was never created, so a blanket `cache:` turns a green job red.
This prunes the keys that should not have been added, using the same
"does this job install?" test the guard enforces.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _workflow_physics import CACHE_KEY, job_installs, job_spans, owning_job  # noqa: E402

WORKFLOWS = Path(".github/workflows")
APPLY = "--apply" in sys.argv
SETUP_RE = re.compile(r"^\s*-?\s*uses:\s*actions/setup-(python|node)@v\d+\s*$")


def prune(path: Path) -> tuple[str, list[str]]:
    src = path.read_text(encoding="utf-8")
    lines = src.split("\n")
    spans = job_spans(lines)
    drop: set[int] = set()
    notes: list[str] = []

    for i, line in enumerate(lines):
        m = SETUP_RE.match(line)
        if not m:
            continue
        tool = m.group(1)
        own = owning_job(spans, i)
        if own is None:
            continue
        jid, start, end = own
        if job_installs(lines, start, end, tool):
            continue
        # Walk this step's `with:` block and drop the cache key we added.
        for j in range(i + 1, min(i + 14, len(lines))):
            if re.match(r"^\s*-\s+\S", lines[j]):
                break  # next step
            if re.match(rf"^\s*cache:\s*'{CACHE_KEY[tool]}'\s*$", lines[j]):
                drop.add(j)
                notes.append(f"{path.name}: job `{jid}` installs no {tool} deps -> dropped cache key")
                break
    if not drop:
        return src, []
    return "\n".join(l for k, l in enumerate(lines) if k not in drop), notes


def main() -> int:
    total = 0
    for path in sorted(WORKFLOWS.glob("*.yml")):
        new, notes = prune(path)
        if not notes:
            continue
        try:
            yaml.safe_load(new)
        except yaml.YAMLError as exc:
            print(f"  SKIP {path.name}: transform produced invalid YAML - {exc}")
            continue
        for n in notes:
            print(f"  {n}")
        total += len(notes)
        if APPLY:
            path.write_text(new, encoding="utf-8")
    print(f"\n{'APPLIED' if APPLY else 'DRY RUN - nothing written'}\n  cache keys pruned: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
