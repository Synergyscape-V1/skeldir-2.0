#!/usr/bin/env python3
"""B2.6-P2 Corrective XXI effect-coverage registry (extends XVIII).

XVIII_COVERED_SURFACES remains the predecessor baseline (unchanged file).
XXI changes the reachable universe itself:

- the release-bound minting ABI
  ``b26_p2_authenticate_ingress_atomic_v2(uuid,text*7,timestamptz,
  boolean,timestamptz,timestamptz)`` and
  ``b26_p2_attest_provenance_evidence_v2(uuid,text*3,timestamptz,
  boolean,timestamptz,timestamptz)``: the v1 signatures no longer exist,
  so previously built executables fail overload resolution before any
  state changes. EXECUTE belongs to app_ingress alone. Covered by the
  XXI composition gate V1 (v1 absent with undefined-function refusal,
  v2 honest mint conducts end to end), V2 (lifecycle refused at the
  DB seam without Python), the dual-path attester proof (atomic-path
  re-attestation succeeds; legacy recorder path still refuses with
  provenance_promotion_refused), and the NC battery.
- the owner-context history-continuity read
  ``b26_p2_read_history_continuity()``: STABLE, read-only, SECURITY
  DEFINER exposing exactly the global (count, tip) the beat
  observation records; EXECUTE granted to the Trust-issuance readers
  (app_user, app_worker) which hold no direct ledger rights. It mints
  nothing (answers only) and is fail-closed (permission model
  unchanged for writers). Covered by the XXI composition gate V4
  (real builder degrades/refuses through this read) and the
  least-privilege probe (direct ledger read refused for app_user
  while the DEFINER read succeeds).
- the owner-context beat observation entry
  ``b26_p2_observe_history_integrity()``: EXECUTE granted to the B2.3
  worker executor (app_worker) alone; authorship is the caller's
  session_user, unforgeable in-session. Covered by the XXI
  composition gate V4/V8 (worker observation succeeds, beat
  authorship unforgeable, truncate/rewrite contradiction detected).

The governing topology proof loads XXI_COVERED_SURFACES; UNTESTED>0
fails coverage.
"""

from __future__ import annotations

import importlib.util as _ilu
import sys as _sys
from pathlib import Path as _Path


def _load_xviii_surfaces() -> frozenset:
    """Load the predecessor registry by file location, never by package.

    The topology/in-image provers load coverage registries through a
    spec-loader with an unpredictable sys.path (script dir only, no
    package context). A package import here would fail exactly where
    the predecessor file itself loads fine, silently demoting this
    registry to its predecessor. File-location loading behaves
    identically in every context; the predecessor's own imports
    execute as they always do.
    """
    here = _Path(__file__).resolve().parent
    spec = _ilu.spec_from_file_location(
        "b26_p2_xviii_coverage_xxi_ns", str(here / "b26_p2_xviii_coverage.py")
    )
    assert spec is not None and spec.loader is not None
    module = _ilu.module_from_spec(spec)
    _sys.modules["b26_p2_xviii_coverage_xxi_ns"] = module
    spec.loader.exec_module(module)
    return frozenset(module.XVIII_COVERED_SURFACES)


_XVIII = _load_xviii_surfaces()

_XXI_NEW = frozenset(
    {
        # Release-bound minting ABI (fail-closed version fence).
        "app_ingress:EXECUTE:b26_p2_authenticate_ingress_atomic_v2",
        "app_ingress:EXECUTE:b26_p2_attest_provenance_evidence_v2",
        # Owner-context history continuity (read-only; fail-closed).
        "app_user:EXECUTE:b26_p2_read_history_continuity",
        "app_worker:EXECUTE:b26_p2_read_history_continuity",
        "app_worker:EXECUTE:b26_p2_observe_history_integrity",
    }
)

XXI_COVERED_SURFACES: frozenset[str] = _XVIII | _XXI_NEW

__all__ = ("XXI_COVERED_SURFACES",)
