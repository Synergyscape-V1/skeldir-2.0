"""B2.6-P2 Corrective VIII deployed conduction-health probe
(Corrective IX: scheduler liveness separated from evaluation freshness).

Shipping consumer for the independent conduction signal
(GET /health/b26-p2-conduction): exits 0 only when the endpoint is
reachable AND reports no required action AND the evaluator heartbeat is
present for every tenant AND the scheduler heartbeat is present for
every tenant. Any other outcome (unreachable, 503,
action_required, evaluator absence, scheduler absence) exits nonzero
with a machine-readable line, so container healthchecks and platform
alerting can consume P2 degradation automatically instead of leaving a
JSON field unread.

Separation law (IX): scheduler_alive (scheduler_absent_total == 0)
is scheduler liveness; evaluation_fresh (evaluator_absent_total == 0)
is evaluation freshness. evaluation_fresh != scheduler_alive: each is
checked independently and each fails the probe on its own.

Evaluates the SHIPPING observer path end to end (API process + database +
evaluator + scheduler), never the heartbeat tables directly: a forged
timestamp without a genuine evaluation still leaves action_required
true through the counts the API recomputes live.
"""

from __future__ import annotations

import argparse
import json
import urllib.request


def evaluate(payload: dict) -> tuple[bool, str]:
    """Pure decision law over one decoded conduction-health payload."""
    if not isinstance(payload, dict):
        return False, "undecodable_payload"
    status = str(payload.get("status", ""))
    if status == "unavailable":
        return False, "threshold_out_of_bounds"
    action_required = bool(payload.get("action_required", False))
    evaluator_absent = int(payload.get("evaluator_absent_total", 0) or 0)
    scheduler_absent = int(payload.get("scheduler_absent_total", 0) or 0)
    pending_actionable = int(payload.get("pending_actionable_total", 0) or 0)
    stale = int(
        payload.get(
            "stale_unconducted_count",
            payload.get("stale_unconducted_total", payload.get("stale_total", 0)),
        )
        or 0
    )
    quarantine = int(
        payload.get("quarantine_count", payload.get("quarantine_total", 0)) or 0
    )
    if scheduler_absent > 0:
        return False, f"scheduler_absent_total={scheduler_absent}"
    if evaluator_absent > 0:
        return False, f"evaluator_absent_total={evaluator_absent}"
    if action_required or pending_actionable > 0 or stale > 0 or quarantine > 0:
        return (
            False,
            f"action_required pending_actionable={pending_actionable}"
            f" stale={stale} quarantine={quarantine}",
        )
    if status not in ("ok", "stale_unconducted"):
        return False, f"unexpected_status={status}"
    return True, "healthy"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=10)
    args = parser.parse_args()
    try:
        with urllib.request.urlopen(args.url, timeout=args.timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"B26_P2_PROBE_UNREACHABLE error={exc}")
        return 1
    healthy, reason = evaluate(payload)
    if healthy:
        print(f"B26_P2_PROBE_HEALTHY {reason}")
        return 0
    print(f"B26_P2_PROBE_DEGRADED {reason}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
