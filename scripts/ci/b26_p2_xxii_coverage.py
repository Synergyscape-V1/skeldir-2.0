#!/usr/bin/env python3
"""B2.6-P2 Corrective XXII effect-coverage registry (extends XXI).

XXI_COVERED_SURFACES remains the predecessor baseline. XXII adds only
read-only, non-minting DEFINER surfaces plus trigger-enforced chronology:

- ``b26_p2_read_history_witness_state()`` exposes the global ledger
  (count, tip_seq, tip_hash) to the beat observer. Covered by the XXII
  witness probe: the observer signs exactly this state, and a coherent
  owner rewrite of the tip is refused by the signed journal.
- ``b26_p2_read_history_entry_hash(bigint)`` lets the observer verify the
  signed journal prefix entry-by-entry without direct ledger rights.
  Covered by the prefix-divergence and shrink falsifiers.
- ``b26_p2_read_history_violations()`` returns the concatenated
  protection/continuity violations. Covered by the observer's refusal to
  sign while any violation exists.
- ``b26_p2_verify_source_money_conservation(uuid, uuid)`` reads the
  verdict, its authenticated ingress, and its ledger continuation and
  RETURNS one violation per incoherence. Covered by the four live
  conservation cells (clean, initial-not-source, ledger-not-current,
  chain-discontinuous).
- ``trg_b26_p2_observation_chronology`` and
  ``trg_b26_p2_ingress_event_chronology`` refuse future-dated observation
  and provider instants at the table. Covered by the future-observation
  and future-ingress falsifiers.

The governing topology proof loads XXII_COVERED_SURFACES; UNTESTED>0
fails coverage.
"""

from __future__ import annotations

import importlib.util as _ilu
import sys as _sys
from pathlib import Path as _Path


def _load_xxi_surfaces() -> frozenset:
    """Load the predecessor registry by file location, never by package."""
    here = _Path(__file__).resolve().parent
    spec = _ilu.spec_from_file_location(
        "b26_p2_xxi_coverage_xxii_ns", str(here / "b26_p2_xxi_coverage.py")
    )
    assert spec is not None and spec.loader is not None
    module = _ilu.module_from_spec(spec)
    _sys.modules["b26_p2_xxi_coverage_xxii_ns"] = module
    spec.loader.exec_module(module)
    return frozenset(module.XXI_COVERED_SURFACES)


_XXI = _load_xxi_surfaces()

_XXII_NEW = frozenset(
    {
        # Signed-witness state readers (read-only; fail-closed).
        "app_user:EXECUTE:b26_p2_read_history_witness_state",
        "app_worker:EXECUTE:b26_p2_read_history_witness_state",
        "app_beat:EXECUTE:b26_p2_read_history_witness_state",
        "app_user:EXECUTE:b26_p2_read_history_prefix_digest",
        "app_worker:EXECUTE:b26_p2_read_history_prefix_digest",
        "app_beat:EXECUTE:b26_p2_read_history_prefix_digest",
        "app_user:EXECUTE:b26_p2_read_history_entry_hash",
        "app_worker:EXECUTE:b26_p2_read_history_entry_hash",
        "app_beat:EXECUTE:b26_p2_read_history_entry_hash",
        "app_user:EXECUTE:b26_p2_read_history_violations",
        "app_worker:EXECUTE:b26_p2_read_history_violations",
        "app_beat:EXECUTE:b26_p2_read_history_violations",
        # Source-to-money conservation oracle (read-only; agrees only).
        "app_user:EXECUTE:b26_p2_verify_source_money_conservation",
        "app_trust_issuer:EXECUTE:b26_p2_verify_source_money_conservation",
    }
)

XXII_COVERED_SURFACES: frozenset[str] = _XXI | _XXII_NEW

__all__ = ("XXII_COVERED_SURFACES",)
