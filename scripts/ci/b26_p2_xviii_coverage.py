#!/usr/bin/env python3
"""B2.6-P2 Corrective XVIII effect-coverage registry (extends XIV).

XIV_COVERED_SURFACES remains the predecessor baseline (unchanged file).
XVIII changes the reachable universe itself:

- the central current-authority predicate
  ``b26_p2_ingress_has_current_authority(uuid)``: STABLE, read-only,
  SECURITY DEFINER; EXECUTE granted to runtime reader roles. It mints
  nothing (answers only) and is fail-closed (UNKNOWN/missing/demoted
  rows answer FALSE for every role). Covered by the XVIII physics
  role matrix (every granted role executes it against demoted and
  current rows) and the NC battery.

The governing topology proof loads XVIII_COVERED_SURFACES; UNTESTED>0
fails coverage.
"""

from __future__ import annotations

try:
    from scripts.ci.b26_p2_xiv_coverage import (
        XIV_COVERED_SURFACES as _XIV,
    )  # noqa: PLC0415
except ImportError:
    from b26_p2_xiv_coverage import XIV_COVERED_SURFACES as _XIV  # noqa: PLC0415

_XVIII_NEW = frozenset(
    {
        # Central current-authority predicate (read-only; fail-closed).
        "app_user:EXECUTE:b26_p2_ingress_has_current_authority",
        "app_ingress:EXECUTE:b26_p2_ingress_has_current_authority",
        "app_worker:EXECUTE:b26_p2_ingress_has_current_authority",
        "app_relay:EXECUTE:b26_p2_ingress_has_current_authority",
        "app_beat:EXECUTE:b26_p2_ingress_has_current_authority",
        "app_dispatch_publisher:EXECUTE:b26_p2_ingress_has_current_authority",
        "app_trust_issuer:EXECUTE:b26_p2_ingress_has_current_authority",
        "app_trust_signer:EXECUTE:b26_p2_ingress_has_current_authority",
    }
)

XVIII_COVERED_SURFACES: frozenset[str] = _XIV | _XVIII_NEW

__all__ = ("XVIII_COVERED_SURFACES",)
