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
