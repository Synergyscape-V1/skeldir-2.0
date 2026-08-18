"""Shared structural helpers for the CI throughput topology.

Both the applier (apply_throughput_topology.py) and the guard
(validate_ci_physics.py) need the same answer to "does this job actually
install dependencies?", so the definition lives here once. If the two ever
disagreed, the guard would demand a cache key the applier refuses to add, or
worse, accept a workflow the applier would change.
"""
from __future__ import annotations

import re

# actions/setup-python and setup-node fail their post-run cache-save step when
# the cache directory was never created:
#
#   Cache folder path is retrieved for pip but doesn't exist on disk:
#   /home/runner/.cache/pip. This likely indicates that there are no
#   dependencies to cache.
#
# So `cache:` is correct only on a setup step in a job that installs something.
# Adding it everywhere turns a green job red, which is how this was found.
INSTALL_PATTERNS = {
    "python": re.compile(
        r"""(?:
              (?:python[0-9.]*\s+-m\s+)?pip[0-9.]*\s+install
            | poetry\s+install
            | pipenv\s+(?:install|sync)
            | uv\s+(?:pip\s+install|sync)
            | pip-sync
            | -r\s+\S*requirements
        )""",
        re.X,
    ),
    "node": re.compile(
        r"""(?:
              npm\s+(?:ci|install|i)\b
            | yarn\s+(?:install|--frozen-lockfile)
            | pnpm\s+(?:install|i)\b
        )""",
        re.X,
    ),
}

CACHE_KEY = {"python": "pip", "node": "npm"}

_JOB_RE = re.compile(r"^  ([A-Za-z0-9_-]+):\s*$")


def job_spans(lines: list[str]) -> list[tuple[str, int, int]]:
    """Return (job_id, start_index, end_index) for each job block in `lines`.

    Indices are into `lines`; end is exclusive. Only the `jobs:` mapping is
    considered, so a top-level key that happens to sit at two-space indent
    elsewhere is not mistaken for a job.
    """
    try:
        jobs_at = next(i for i, line in enumerate(lines) if re.match(r"^jobs:\s*$", line))
    except StopIteration:
        return []

    starts: list[tuple[int, str]] = []
    for i in range(jobs_at + 1, len(lines)):
        line = lines[i]
        if line.strip() and not line.startswith(" ") and not line.startswith("#"):
            break  # left the jobs: mapping
        if m := _JOB_RE.match(line):
            starts.append((i, m.group(1)))

    spans: list[tuple[str, int, int]] = []
    for k, (idx, jid) in enumerate(starts):
        end = starts[k + 1][0] if k + 1 < len(starts) else len(lines)
        spans.append((jid, idx, end))
    return spans


def owning_job(spans: list[tuple[str, int, int]], line_index: int) -> tuple[str, int, int] | None:
    for jid, start, end in spans:
        if start <= line_index < end:
            return jid, start, end
    return None


def job_installs(lines: list[str], start: int, end: int, tool: str) -> bool:
    """True when the job body contains a step that installs `tool` dependencies."""
    body = "\n".join(lines[start:end])
    return bool(INSTALL_PATTERNS[tool].search(body))


BARRIER_HINTS = ("checkout", "validate-contracts")


def contract_pinned_jobs(jobs: dict | None = None) -> set[str]:
    """Job ids whose `needs:` a governance artefact pins.

    A phase may contract an ordering edge for audit reasons that have nothing to
    do with dataflow, and that outranks the throughput argument. The fan-out rule
    discounts these so the two never contradict each other: without it, a future
    phase pinning one more edge would push a hub past the threshold and the guard
    would demand the removal of an edge another gate demands be present.

    Two shapes are recognised, because the repository uses both:
      1. JSON ``required_ci_job.job_id`` with a ``needs`` list.
      2. A literal ``needs: [...]`` token asserted inside an enforcer script.
    """
    import json
    from pathlib import Path

    pinned: set[str] = set()

    contracts = Path("contracts-internal")
    if contracts.is_dir():
        for path in sorted(contracts.rglob("*.json")):
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if isinstance(doc, dict):
                job = doc.get("required_ci_job")
                if isinstance(job, dict) and job.get("job_id") and job.get("needs"):
                    pinned.add(str(job["job_id"]))

    ci_scripts = Path("scripts/ci")
    if ci_scripts.is_dir() and jobs:
        token_re = re.compile(r'"(needs: \[[^"]*)"((?:\s*\n\s*"[^"]*")*)', re.M)
        for path in sorted(ci_scripts.glob("enforce_*.py")):
            src = path.read_text(encoding="utf-8", errors="replace")
            for m in token_re.finditer(src):
                token = m.group(1) + "".join(re.findall(r'"([^"]*)"', m.group(2) or ""))
                if "]" not in token:
                    continue
                deps = {
                    d.strip()
                    for d in token[token.index("[") + 1 : token.index("]")].split(",")
                    if d.strip()
                }
                core = deps - set(BARRIER_HINTS)
                if not core:
                    continue
                # Resolve the token back to the job that declares those deps, so a
                # rename does not silently drop the pin.
                for jid, body in jobs.items():
                    if not isinstance(body, dict):
                        continue
                    cur = body.get("needs") or []
                    if isinstance(cur, str):
                        cur = [cur]
                    if core == set(cur) - set(BARRIER_HINTS):
                        pinned.add(jid)
    return pinned
