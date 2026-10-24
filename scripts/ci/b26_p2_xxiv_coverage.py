#!/usr/bin/env python3
"""B2.6-P2 Corrective XXIV effect-coverage registry (extends XXIII).

XXIII_COVERED_SURFACES remains the predecessor baseline. XXIV adds the
source-money conservation reader grant to the B2.3 worker principal. The
reader is STABLE, read-only, and returns a governed violation list; it
cannot author verdict money. The grant is exercised by the worker
conservation-read falsifier in the finance reconciliation battery.

The governing topology proof loads XXIV_COVERED_SURFACES; UNTESTED>0
fails coverage.
"""

from __future__ import annotations

import importlib.util as _ilu
import sys as _sys
from pathlib import Path as _Path


def _load_xxiii_surfaces() -> frozenset:
    """Load the predecessor registry by file location, never by package."""
    here = _Path(__file__).resolve().parent
    spec = _ilu.spec_from_file_location(
        "b26_p2_xxiii_coverage_xxiv_ns", str(here / "b26_p2_xxiii_coverage.py")
    )
    assert spec is not None and spec.loader is not None
    module = _ilu.module_from_spec(spec)
    _sys.modules["b26_p2_xxiii_coverage_xxiv_ns"] = module
    spec.loader.exec_module(module)
    return frozenset(module.XXIII_COVERED_SURFACES)


_XXIII = _load_xxiii_surfaces()

_XXIV_NEW = frozenset(
    {
        # The B2.3 worker reads conservation violations for its own
        # tenant/verdict; SELECT-only, no money authorship.
        "app_worker:EXECUTE:b26_p2_verify_source_money_conservation",
    }
)

XXIV_COVERED_SURFACES: frozenset[str] = _XXIII | _XXIV_NEW

__all__ = ("XXIV_COVERED_SURFACES",)
