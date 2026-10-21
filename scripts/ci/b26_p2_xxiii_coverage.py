#!/usr/bin/env python3
"""B2.6-P2 Corrective XXIII effect-coverage registry (extends XXII).

XXII_COVERED_SURFACES remains the predecessor baseline. XXIII adds the
authority-universe and coherent-snapshot read surfaces, and removes the
trigger function's default PUBLIC EXECUTE surface:

- ``b26_p2_authority_universe()`` exposes the database-minted UUID that
  binds a signed witness to one deployment universe. Covered by the
  foreign-universe refusal and the in-image universe-binding cells.
- ``b26_p2_read_history_snapshot(bigint)`` returns state, prefix digest,
  violations, universe, and the prior anchor under one statement
  snapshot. Covered by the observer growth proof and the mixed-checkpoint
  falsifiers.
- ``b26_p2_enforce_verdict_money_authority()`` is a trigger function; it
  carries no runtime EXECUTE grant because trigger invocation does not
  require one. Covered by the worker authority refusal cells.

The governing topology proof loads XXIII_COVERED_SURFACES; UNTESTED>0
fails coverage.
"""

from __future__ import annotations

import importlib.util as _ilu
import sys as _sys
from pathlib import Path as _Path


def _load_xxii_surfaces() -> frozenset:
    """Load the predecessor registry by file location, never by package."""
    here = _Path(__file__).resolve().parent
    spec = _ilu.spec_from_file_location(
        "b26_p2_xxii_coverage_xxiii_ns", str(here / "b26_p2_xxii_coverage.py")
    )
    assert spec is not None and spec.loader is not None
    module = _ilu.module_from_spec(spec)
    _sys.modules["b26_p2_xxii_coverage_xxiii_ns"] = module
    spec.loader.exec_module(module)
    return frozenset(module.XXII_COVERED_SURFACES)


_XXII = _load_xxii_surfaces()

_XXIII_NEW = frozenset(
    {
        # Deployment authority universe (read-only; fail-closed).
        "app_user:EXECUTE:b26_p2_authority_universe",
        "app_worker:EXECUTE:b26_p2_authority_universe",
        "app_beat:EXECUTE:b26_p2_authority_universe",
        "app_trust_issuer:EXECUTE:b26_p2_authority_universe",
        # Coherent history snapshot (read-only; fail-closed).
        "app_user:EXECUTE:b26_p2_read_history_snapshot",
        "app_worker:EXECUTE:b26_p2_read_history_snapshot",
        "app_beat:EXECUTE:b26_p2_read_history_snapshot",
        "app_trust_issuer:EXECUTE:b26_p2_read_history_snapshot",
    }
)

XXIII_COVERED_SURFACES: frozenset[str] = _XXII | _XXIII_NEW

__all__ = ("XXIII_COVERED_SURFACES",)
