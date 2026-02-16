from __future__ import annotations

from pathlib import Path

from scripts.phase8.run_phase8_closure_pack import _eg85_gate_name
from scripts.phase8.run_phase8_closure_pack import _summary_filename_for_authority


def test_ci_subset_cannot_emit_authoritative_eg85_label() -> None:
    assert _eg85_gate_name("ci_subset") == "eg8_5_ci_sanity"
    assert "authority" not in _eg85_gate_name("ci_subset")
    assert _summary_filename_for_authority("ci_subset") == "phase8_gate_summary_ci_subset.json"


def test_full_physics_uses_authoritative_eg85_label() -> None:
    assert _eg85_gate_name("full_physics") == "eg8_5_composed_ingestion_perf_authority"
    assert _summary_filename_for_authority("full_physics") == "phase8_gate_summary_full_physics.json"


def test_authority_summary_filename_is_json() -> None:
    assert Path(_summary_filename_for_authority("ci_subset")).suffix == ".json"
    assert Path(_summary_filename_for_authority("full_physics")).suffix == ".json"
