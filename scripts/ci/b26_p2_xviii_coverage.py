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

import importlib.util as _ilu
import sys as _sys
from pathlib import Path as _Path


def _load_xiv_surfaces() -> frozenset:
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
        "b26_p2_xiv_coverage_xviii_ns", str(here / "b26_p2_xiv_coverage.py")
    )
    assert spec is not None and spec.loader is not None
    module = _ilu.module_from_spec(spec)
    _sys.modules["b26_p2_xiv_coverage_xviii_ns"] = module
    spec.loader.exec_module(module)
    return frozenset(module.XIV_COVERED_SURFACES)


_XIV = _load_xiv_surfaces()

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
