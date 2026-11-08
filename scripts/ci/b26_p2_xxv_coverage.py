#!/usr/bin/env python3
"""B2.6-P2 Corrective XXV effect-coverage registry (extends XXIV).

XXIV_COVERED_SURFACES remains the predecessor baseline. XXV adds the
authentication-root authority-universe read used by the ingress credential
when it binds a source-money attestation to the deployment universe. The
reader is STABLE, read-only, and fail-closed; it cannot author money,
attestations, verdicts, or history.

The governing topology and in-image proofs load XXV_COVERED_SURFACES;
UNTESTED>0 fails coverage.
"""

from __future__ import annotations

import importlib.util as _ilu
import sys as _sys
from pathlib import Path as _Path


def _load_xxiv_surfaces() -> frozenset:
    """Load the predecessor registry by file location, never by package."""
    here = _Path(__file__).resolve().parent
    spec = _ilu.spec_from_file_location(
        "b26_p2_xxiv_coverage_xxv_ns", str(here / "b26_p2_xxiv_coverage.py")
    )
    assert spec is not None and spec.loader is not None
    module = _ilu.module_from_spec(spec)
    _sys.modules["b26_p2_xxiv_coverage_xxv_ns"] = module
    spec.loader.exec_module(module)
    return frozenset(module.XXIV_COVERED_SURFACES)


_XXIV = _load_xxiv_surfaces()

_XXV_NEW = frozenset(
    {
        # The ingress root reads the database-minted deployment universe
        # before signing the source-money attestation. Read-only.
        "app_ingress:EXECUTE:b26_p2_authority_universe",
        # XXV post-capture adjustments: the root signs separate adjustment
        # evidence; runtime readers verify it. Creation-source authority is
        # unchanged.
        "app_ingress:INSERT:b26_p2_adjustment_evidence",
        "app_ingress:SELECT:b26_p2_adjustment_evidence",
        "app_ingress:INSERT:b26_p2_adjustment_attestation",
        "app_ingress:SELECT:b26_p2_adjustment_attestation",
        "app_ingress:EXECUTE:b26_p2_current_verdict_for_adjustment",
        # Auth-root-only governed lift of a pre-XXV demotion after a signed
        # source attestation exists. No runtime principal receives it.
        "app_ingress:EXECUTE:b26_p2_lift_pre_xxv_demotion",
        "app_user:SELECT:b26_p2_adjustment_evidence",
        "app_worker:SELECT:b26_p2_adjustment_evidence",
        "app_trust_issuer:SELECT:b26_p2_adjustment_evidence",
        "app_ro:SELECT:b26_p2_adjustment_evidence",
        "app_relay:SELECT:b26_p2_adjustment_evidence",
        "app_user:SELECT:b26_p2_adjustment_attestation",
        "app_worker:SELECT:b26_p2_adjustment_attestation",
        "app_trust_issuer:SELECT:b26_p2_adjustment_attestation",
        "app_ro:SELECT:b26_p2_adjustment_attestation",
        "app_relay:SELECT:b26_p2_adjustment_attestation",
    }
)

XXV_COVERED_SURFACES: frozenset[str] = _XXIV | _XXV_NEW

__all__ = ("XXV_COVERED_SURFACES",)
