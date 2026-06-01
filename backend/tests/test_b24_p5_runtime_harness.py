from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

import pytest

from app.bayesian.runtime_policy import apply_native_runtime_environment, build_runtime_policy
from app.bayesian.sampler_supervisor import run_supervised_sampler, synthetic_blocking_child_command


ROOT = Path(__file__).resolve().parents[2]
RUNTIME_STATE = ROOT / "backend/app/bayesian/runtime_state.py"
RUNTIME_PROBE = ROOT / "backend/app/bayesian/runtime_probe.py"


def test_b24_p5_thread_budget_rejects_oversubscription(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("B24_BAYESIAN_WORKER_CONCURRENCY", "4")
    monkeypatch.setenv("B24_PYMC_CORES", "4")
    monkeypatch.setenv("B24_BLAS_TOTAL_THREADS", "4")
    monkeypatch.setenv("B24_BAYESIAN_CPU_BUDGET", "2")
    with pytest.raises(RuntimeError, match="thread budget"):
        build_runtime_policy()


def test_b24_p5_timeout_hierarchy_is_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("B24_SAMPLER_SUPERVISOR_DEADLINE_S", "300")
    monkeypatch.setenv("BAYESIAN_TASK_SOFT_TIME_LIMIT_S", "270")
    monkeypatch.setenv("BAYESIAN_TASK_TIME_LIMIT_S", "360")
    with pytest.raises(RuntimeError, match="timeout hierarchy"):
        build_runtime_policy()


def test_b24_p5_runtime_sets_thread_caps_and_compiledir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("B24_PYTENSOR_COMPILEDIR", str(tmp_path / "compiledir"))
    monkeypatch.setenv("B24_BLAS_TOTAL_THREADS", "1")
    policy = apply_native_runtime_environment()
    assert Path(policy.compiledir).exists()
    assert os.environ["OMP_NUM_THREADS"] == "1"
    assert os.environ["OPENBLAS_NUM_THREADS"] == "1"
    assert "base_compiledir=" in os.environ["PYTENSOR_FLAGS"]


def test_b24_p5_supervisor_kills_blocking_child(monkeypatch: pytest.MonkeyPatch) -> None:
    pythonpath = str(ROOT / "backend")
    monkeypatch.setenv("PYTHONPATH", pythonpath)
    result = run_supervised_sampler(synthetic_blocking_child_command(seconds=30), deadline_seconds=0.5)
    assert result.status == "timeout"
    assert result.killed_by_supervisor is True
    assert result.orphan_reaped is True


def test_b24_p5_runtime_state_writes_only_bayesian_table() -> None:
    text = RUNTIME_STATE.read_text(encoding="utf-8")
    assert "UPDATE public.bayesian_model_fits" in text
    assert "set_config('app.current_tenant_id'" in text
    assert "WHERE tenant_id = :tenant_id" in text
    forbidden = (
        "UPDATE public.attribution_events",
        "UPDATE public.attribution_allocations",
        "UPDATE public.b23_match_verdicts",
        "UPDATE public.b23_revenue_events",
        "INSERT INTO public.attribution_events",
        "INSERT INTO public.b23_match_verdicts",
    )
    for token in forbidden:
        assert token not in text


def test_b24_p5_probe_does_not_import_pymc_before_env_caps() -> None:
    tree = ast.parse(RUNTIME_PROBE.read_text(encoding="utf-8"))
    top_level_imports = {
        alias.name
        for node in tree.body
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert "pymc" not in top_level_imports
    text = RUNTIME_PROBE.read_text(encoding="utf-8")
    assert text.find("apply_native_runtime_environment") < text.find("import pymc as pm")


def test_b24_p5_runtime_probe_module_loads_without_science_stack() -> None:
    module = __import__("app.bayesian.runtime_probe", fromlist=["COMMANDS"])
    assert "tiny-benchmark" in module.COMMANDS
