#!/usr/bin/env python3
"""B2.6-P2 Corrective VIII effect-coverage registry (extends VII).

VII_COVERED_SURFACES remains the predecessor baseline (unchanged file).
VIII changes the reachable universe itself:

- app_worker verified-authorship is refused at the database plane
  (allowlist narrowed to the API issuer credential), but the worker
  INSERT grant persists, so the dead-end battery cells stay registered.
- app_relay direct heartbeat writes are REVOKED (no longer reachable);
  the single SECURITY DEFINER evaluation function is EXECUTable by
  app_relay/app_beat, so those EXECUTE surfaces are registered instead.

The governing topology proof loads VIII_COVERED_SURFACES; UNTESTED>0
fails coverage. Meaning drift (same-name body/owner/signature change) is
governed separately by the reviewed universe pin
(contracts-internal/governance/b26_p2_authority_universe.pin.json).
"""

from __future__ import annotations

try:
    from scripts.ci.b26_p2_vii_coverage import VII_COVERED_SURFACES as _VII  # noqa: PLC0415
except ImportError:
    from b26_p2_vii_coverage import VII_COVERED_SURFACES as _VII  # noqa: PLC0415

_VIII_REMOVED = frozenset(
    {
        "app_relay:INSERT:b26_p2_evaluator_heartbeat",
        "app_relay:INSERT:b26_p2_evaluator_heartbeat.last_tick",
        "app_relay:INSERT:b26_p2_evaluator_heartbeat.tenant_id",
        "app_relay:UPDATE:b26_p2_evaluator_heartbeat.last_tick",
        "app_relay:UPDATE:b26_p2_evaluator_heartbeat.tenant_id",
    }
)

_VIII_NEW = frozenset(
    {
        # Evaluation-bound heartbeat (Corrective VIII, Group F): the
        # monitored relay credential can only invoke the evaluation
        # function, never write heartbeat evidence directly (HB8 cells).
        "app_relay:EXECUTE:b26_p2_record_evaluator_heartbeat",
        "app_beat:EXECUTE:b26_p2_record_evaluator_heartbeat",
    }
)

VIII_COVERED_SURFACES: frozenset[str] = (_VII - _VIII_REMOVED) | _VIII_NEW

__all__ = ("VIII_COVERED_SURFACES",)
