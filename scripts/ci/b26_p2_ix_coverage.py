#!/usr/bin/env python3
"""B2.6-P2 Corrective IX effect-coverage registry (extends VIII).

VIII_COVERED_SURFACES remains the predecessor baseline (unchanged file).
IX changes the reachable universe itself:

- the sovereign canonical-scope mirror
  (public.b26_p2_canonical_scope_identity_for_window) is EXECUTable by
  app_worker/app_user. Every lawful conduction and every PC9 forgery
  refusal exercises these EXECUTE surfaces (PC9 cells + _conduct paths).
- the scheduler-liveness function
  (public.b26_p2_record_scheduler_heartbeat) is EXECUTable by app_beat
  only. The SCH9 beat-tick cell exercises it; the SCH9 relay cell proves
  the monitored credential cannot obtain it (refusal is the coverage:
  the surface is unreachable for relay by grant absence, so no relay
  surface is registered).

The governing topology proof loads IX_COVERED_SURFACES; UNTESTED>0
fails coverage. Meaning drift (same-name body/owner/signature change) is
governed separately by the reviewed universe pin
(contracts-internal/governance/b26_p2_authority_universe.pin.json).
"""

from __future__ import annotations

try:
    from scripts.ci.b26_p2_viii_coverage import VIII_COVERED_SURFACES as _VIII  # noqa: PLC0415
except ImportError:
    from b26_p2_viii_coverage import VIII_COVERED_SURFACES as _VIII  # noqa: PLC0415

_VIII_REMOVED = frozenset(
    {
        # No VIII surface is revoked by IX; the recorder/gate keep their
        # worker EXECUTE shape (now canonically bound), and every
        # predecessor grant persists.
    }
)

_IX_NEW = frozenset(
    {
        # Canonical consequence authority (Corrective IX, Group A): the
        # worker presents a scope witness, the plane recomputes. Lawful
        # Python-derived scopes conduct; random/foreign/stale digests
        # refuse with scope_not_canonical (PC9 cells).
        "app_worker:EXECUTE:b26_p2_canonical_scope_identity_for_window",
        "app_user:EXECUTE:b26_p2_canonical_scope_identity_for_window",
        # Scheduler liveness separation (Corrective IX, Group G): only
        # the beat principal may tick scheduler health (SCH9 cells).
        "app_beat:EXECUTE:b26_p2_record_scheduler_heartbeat",
    }
)

IX_COVERED_SURFACES: frozenset[str] = (_VIII - _VIII_REMOVED) | _IX_NEW

__all__ = ("IX_COVERED_SURFACES",)
