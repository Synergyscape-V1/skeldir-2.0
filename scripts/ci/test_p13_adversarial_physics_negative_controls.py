#!/usr/bin/env python3
"""Negative controls for the P13 adversarial-physics adjudicator.

The adjudicator exists because GitHub treats a `skipped` check-run as
satisfying a branch rule. A guard written for that reason is worthless unless it
demonstrably refuses each way a lane can fail to have proved anything: absent,
skipped, neutral, cancelled, timed out, or outright failed. Each control below
feeds one such observation and requires a refusal, then feeds the success case
and requires acceptance.

Run:  python scripts/ci/test_p13_adversarial_physics_negative_controls.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "ci"))

import adjudicate_p13_adversarial_physics as adjudicator  # noqa: E402


def _run(observation: dict[str, dict[str, str]], event_name: str) -> int:
    """Adjudicate against a synthetic check-run observation."""

    original = adjudicator._check_runs
    adjudicator._check_runs = lambda repository, sha, token: observation  # type: ignore[assignment]
    try:
        return adjudicator.adjudicate(
            repository="example/repo",
            sha="deadbeef",
            token="synthetic",
            event_name=event_name,
            wait_seconds=0,
            poll_seconds=0,
        )
    finally:
        adjudicator._check_runs = original  # type: ignore[assignment]


def _all_green() -> dict[str, dict[str, str]]:
    return {
        context: {"status": "completed", "conclusion": "success"}
        for context in adjudicator._declared_lanes().values()
    }


def _expect(label: str, observation: dict, *, refused: bool, event: str = "pull_request") -> bool:
    code = _run(observation, event)
    actually_refused = code != 0
    if actually_refused != refused:
        expected = "REFUSED" if refused else "ACCEPTED"
        observed = "REFUSED" if actually_refused else "ACCEPTED"
        print(f"FAIL {label}: expected {expected}, observed {observed}")
        return False
    print(f"OK   {label}: {'REFUSED' if refused else 'ACCEPTED'}")
    return True


def main() -> int:
    lanes = sorted(adjudicator._declared_lanes().values())
    if not lanes:
        print("FAIL: no adversarial lanes are declared in the contract", file=sys.stderr)
        return 1
    print(f"declared lanes: {lanes}")

    ok = True
    ok &= _expect("baseline, every lane success", _all_green(), refused=False)

    victim = lanes[0]

    for conclusion in ("skipped", "neutral", "cancelled", "timed_out", "failure"):
        observation = _all_green()
        observation[victim] = {"status": "completed", "conclusion": conclusion}
        ok &= _expect(f"{victim} concluded {conclusion}", observation, refused=True)
        ok &= _expect(
            f"restored after {conclusion}", _all_green(), refused=False
        )

    observation = _all_green()
    del observation[victim]
    ok &= _expect(f"{victim} never reported", observation, refused=True)
    ok &= _expect("restored after absence", _all_green(), refused=False)

    observation = _all_green()
    observation[victim] = {"status": "in_progress", "conclusion": None}
    ok &= _expect(
        f"{victim} still running when the wait expires", observation, refused=True
    )
    ok &= _expect("restored after pending", _all_green(), refused=False)

    # Post-merge the lanes carry path filters, so absence there is lawful and
    # the adjudicator observes rather than asserts. If that ever became an
    # assertion, main would be unable to report on an unrelated change.
    observation = _all_green()
    del observation[victim]
    ok &= _expect(
        f"{victim} absent on push is observed, not refused",
        observation,
        refused=False,
        event="push",
    )

    if not ok:
        print("P13 adversarial-physics negative controls FAILED", file=sys.stderr)
        return 1
    print("P13 adversarial-physics negative controls: adjudicator is non-vacuous")
    return 0


if __name__ == "__main__":
    sys.exit(main())
