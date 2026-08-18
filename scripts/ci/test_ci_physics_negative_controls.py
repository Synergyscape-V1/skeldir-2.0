#!/usr/bin/env python3
"""Negative controls for the CI physics guard.

A guard that passes is worthless unless it also fails. Each control below builds
a synthetic workflow tree that violates exactly one rule and asserts the guard
rejects it, then repairs the violation and asserts the guard accepts it. If a
rule is ever weakened into a no-op, the matching control goes red.

Run:  python scripts/ci/test_ci_physics_negative_controls.py
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GUARD = REPO / "scripts" / "ci" / "validate_ci_physics.py"

CONFORMING = """\
name: Example
on:
  merge_group:
  pull_request:
concurrency:
  group: ${{ github.workflow }}-${{ github.event_name }}-${{ github.event.pull_request.number || github.run_id }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}
jobs:
  a:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
      - run: pip install -r requirements.txt
"""


def run_guard(tree: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(GUARD)],
        cwd=tree,
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout + proc.stderr


def build(tmp: Path, content: str, contract: str | None = None) -> Path:
    wf = tmp / ".github" / "workflows"
    if wf.exists():
        shutil.rmtree(wf)
    wf.mkdir(parents=True)
    (wf / "example.yml").write_text(content, encoding="utf-8")
    gov = tmp / "contracts-internal" / "governance"
    if gov.exists():
        shutil.rmtree(tmp / "contracts-internal")
    if contract is not None:
        gov.mkdir(parents=True)
        # The required-contexts rule looks this file up by name; the pinned-edge
        # rule rglobs every JSON, so one file serves both fixtures.
        (gov / "b03_phase2_required_status_checks.main.json").write_text(
            contract, encoding="utf-8"
        )
    return tmp


# --- controls -------------------------------------------------------------

NO_CONCURRENCY = CONFORMING.replace(
    """concurrency:
  group: ${{ github.workflow }}-${{ github.event_name }}-${{ github.event.pull_request.number || github.run_id }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}
""",
    "",
)

UNCONDITIONAL_CANCEL = CONFORMING.replace(
    "cancel-in-progress: ${{ github.event_name == 'pull_request' }}",
    "cancel-in-progress: true",
)

NO_MERGE_GROUP = CONFORMING.replace("  merge_group:\n", "")

# pull_request and pull_request_target both fire for the same PR and yield the
# same pull_request.number. Without github.event_name in the group they share it
# and cancel each other - which cancelled three required contexts on PR #653, and
# a cancelled required context blocks the merge exactly like a failing one.
GROUP_WITHOUT_EVENT = CONFORMING.replace(
    "${{ github.workflow }}-${{ github.event_name }}-", "${{ github.workflow }}-"
)

# A job that installs dependencies but caches nothing burns the shared budget.
NO_CACHE = CONFORMING.replace("          cache: 'pip'\n", "")

# The inverse, and the failure that turned a green job red on PR #651: a cache
# key on a job that installs nothing. setup-*'s post-run save step fails outright
# because the cache directory was never created.
CACHE_WITHOUT_INSTALL = CONFORMING.replace(
    "      - run: pip install -r requirements.txt\n", ""
)

FANOUT_BARRIER = """\
name: Example
on:
  merge_group:
  pull_request:
concurrency:
  group: ${{ github.workflow }}-${{ github.event_name }}-${{ github.event.pull_request.number || github.run_id }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}
jobs:
  gate:
    runs-on: ubuntu-latest
    steps:
      - run: echo "transfers nothing"
""" + "".join(
    f"""  leaf{i}:
    runs-on: ubuntu-latest
    needs: [gate]
    steps:
      - run: echo hi
"""
    for i in range(6)
)

# The same fan-out is legitimate once the hub actually hands state downstream.
FANOUT_WITH_OUTPUTS = FANOUT_BARRIER.replace(
    """  gate:
    runs-on: ubuntu-latest
    steps:
      - run: echo "transfers nothing"
""",
    """  gate:
    runs-on: ubuntu-latest
    outputs:
      token: ${{ steps.mk.outputs.token }}
    steps:
      - id: mk
        run: echo "token=abc" >> "$GITHUB_OUTPUT"
""",
)

EXEMPTED = NO_CACHE.replace(
    "name: Example",
    "# physics-exempt: cache - synthetic fixture, no real dependency install\nname: Example",
)

# Gate 6: a future phase inherits the topology by existing. This is the workflow
# a B3 phase would add - the guard discovers it by glob and enforces every rule
# against it with no edit to the guard, this harness, or any registry.
B3_PHASE_NONCONFORMING = """\
name: B3-P0 Example Phase Gate
on:
  pull_request:
jobs:
  b3-p0-proof:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pytest backend/tests/b3/test_p0.py
"""

# A governance contract may pin a job's needs for audit reasons unrelated to
# dataflow (B1.5-P7 does). The fan-out rule must discount those, or it would
# demand the removal of an edge another gate demands be present.
PIN_CONTRACT = json.dumps(
    {
        "contract_id": "example.pin",
        "required_ci_job": {"job_id": "leaf0", "job_name": "leaf0", "needs": ["gate"]},
    }
)

CONTROLS: list[tuple[str, str, bool, str]] = [
    # (label, workflow content, expect_pass, substring expected in output when failing)
    ("conforming baseline", CONFORMING, True, ""),
    (
        "newly added B3 phase workflow is enforced automatically",
        B3_PHASE_NONCONFORMING,
        False,
        "no `concurrency:` block",
    ),
    ("missing concurrency block", NO_CONCURRENCY, False, "no `concurrency:` block"),
    ("unconditional cancel-in-progress", UNCONDITIONAL_CANCEL, False, "unconditional"),
    ("missing merge_group trigger", NO_MERGE_GROUP, False, "not on merge_group"),
    ("setup-python that installs but does not cache", NO_CACHE, False, "no `cache:"),
    (
        "cache key on a job that installs nothing",
        CACHE_WITHOUT_INSTALL,
        False,
        "post-run cache-save step fails",
    ),
    ("fan-out barrier with no dataflow", FANOUT_BARRIER, False, "transfers no data"),
    ("same fan-out, but declares outputs", FANOUT_WITH_OUTPUTS, True, ""),
    ("violation with an in-file exemption", EXEMPTED, True, ""),
    (
        "concurrency group missing github.event_name",
        GROUP_WITHOUT_EVENT,
        False,
        "does not include",
    ),
]


# A required context whose workflow does not fire on merge_group can never
# report against the speculative merge commit, so the queue entry waits until it
# times out. The symptom reads as "the queue is broken", not "that workflow is
# missing a trigger", which is why this is checked explicitly.
QUEUE_CTX_CONTRACT = json.dumps({"required_contexts": ["Example"]})

# Same contract, but the workflow producing the context has no merge_group.
NO_MG_BUT_REQUIRED = NO_MERGE_GROUP


# (label, content, expect_pass, needle, contract-or-None)
EXTRA_CONTROLS: list[tuple[str, str, bool, str, str | None]] = [
    (
        "fan-out barrier stays rejected when nothing pins it",
        FANOUT_BARRIER,
        False,
        "transfers no data",
        None,
    ),
    (
        "same barrier is accepted once a contract pins the edge",
        FANOUT_BARRIER,
        True,
        "",
        PIN_CONTRACT,
    ),
    (
        "required context whose workflow cannot report to the merge queue",
        NO_MG_BUT_REQUIRED,
        False,
        "can never arrive",
        QUEUE_CTX_CONTRACT,
    ),
    (
        "same context, once its workflow fires on merge_group",
        CONFORMING,
        True,
        "",
        QUEUE_CTX_CONTRACT,
    ),
]


def main() -> int:
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for label, content, expect_pass, needle in CONTROLS:
            build(tmp, content)
            code, out = run_guard(tmp)
            passed = code == 0
            if passed != expect_pass:
                failures.append(
                    f"{label}: expected guard to {'PASS' if expect_pass else 'FAIL'}, "
                    f"but it {'passed' if passed else 'failed'}\n{out}"
                )
                continue
            if not expect_pass and needle and needle not in out:
                failures.append(
                    f"{label}: guard failed as expected but the message did not "
                    f"mention {needle!r}. A rule may be failing for the wrong reason.\n{out}"
                )
                continue
            verb = "accepts" if expect_pass else "rejects"
            print(f"  ok  guard {verb}: {label}")

        for label, content, expect_pass, needle, contract in EXTRA_CONTROLS:
            build(tmp, content, contract)
            code, out = run_guard(tmp)
            passed = code == 0
            if passed != expect_pass:
                failures.append(
                    f"{label}: expected guard to {'PASS' if expect_pass else 'FAIL'}, "
                    f"but it {'passed' if passed else 'failed'}\n{out}"
                )
                continue
            if not expect_pass and needle and needle not in out:
                failures.append(
                    f"{label}: failed but the message did not mention {needle!r}\n{out}"
                )
                continue
            print(f"  ok  guard {'accepts' if expect_pass else 'rejects'}: {label}")

    total = len(CONTROLS) + len(EXTRA_CONTROLS)
    print(f"\nnegative controls: {total - len(failures)}/{total} passed")
    if failures:
        print("\nNON-VACUITY BROKEN - the guard is not enforcing what it claims:\n")
        for f in failures:
            print(f"  {f}\n")
        return 1
    print("the guard fails when the protected property is violated, and only then")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
