"""Unit contract for the Phase 8 pg_stat split probe's pure functions.

The probe is observation-only; these tests pin its arithmetic (delta split
between first and last sample) so the artefact's headline cannot silently
miscarry if the sampler is later refactored.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_probe_module():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "phase8" / "pg_stat_probe.py"
    spec = importlib.util.spec_from_file_location("phase8_pg_stat_probe", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_PROBE = _load_probe_module()


def _row(qid: str, calls: int, ms: float, rows: int = 0, toplevel: bool = True):
    return {
        "qid": qid,
        "calls": calls,
        "ms": ms,
        "rows": rows,
        "toplevel": toplevel,
        "q": f"SELECT {qid}",
    }


def test_delta_split_differences_first_and_last() -> None:
    first = [_row("a", 10, 100.0), _row("b", 5, 50.0)]
    last = [_row("a", 30, 400.0), _row("b", 5, 50.0), _row("c", 2, 20.0)]
    out = _PROBE._delta_split(first, last)
    by_qid = {row["qid"]: row for row in out}
    assert by_qid["a"]["calls"] == 20
    assert by_qid["a"]["total_exec_ms"] == 300.0
    assert by_qid["a"]["mean_exec_ms"] == 15.0
    assert by_qid["c"]["calls"] == 2
    assert by_qid["c"]["total_exec_ms"] == 20.0
    assert "b" not in by_qid


def test_delta_split_sorted_desc_and_limited() -> None:
    first = [_row("x", 0, 0.0)]
    last = [_row("x", 1, 1.0), _row("y", 9, 900.0), _row("z", 4, 400.0)]
    out = _PROBE._delta_split(first, last, limit=2)
    assert [row["qid"] for row in out] == ["y", "z"]


def test_delta_split_without_samples_is_empty() -> None:
    assert _PROBE._delta_split(None, None) == []
    assert _PROBE._delta_split([], []) == []


def test_delta_split_zero_delta_row_excluded() -> None:
    first = [_row("same", 7, 70.0)]
    last = [_row("same", 7, 70.0)]
    assert _PROBE._delta_split(first, last) == []


def test_delta_split_negative_measurement_excluded() -> None:
    first = [_row("neg", 7, 70.0)]
    last = [_row("neg", 7, 69.0)]
    out = _PROBE._delta_split(first, last)
    assert out == []
