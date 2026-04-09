"""B1.7-P4 strategy-closure enforcer tests."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _script_path() -> Path:
    return _repo_root() / "scripts" / "ci" / "enforce_b17_p4_strategy_closure.py"


def _run_enforcer(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_script_path()), *args],
        cwd=_repo_root(),
        check=False,
        capture_output=True,
        text=True,
    )


def test_b17_p4_enforcer_passes_repo_baseline() -> None:
    result = _run_enforcer()
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "result=PASS" in result.stdout


def test_b17_p4_enforcer_negative_control_synthetic_regression() -> None:
    result = _run_enforcer("--simulate-regression")
    assert result.returncode != 0
    assert "synthetic_regression" in (result.stdout + result.stderr)


def test_b17_p4_enforcer_negative_control_detects_missing_p4_lock(tmp_path: Path) -> None:
    source_file = _repo_root() / "api-contracts" / "openapi" / "v1" / "attribution.yaml"
    payload = yaml.safe_load(source_file.read_text(encoding="utf-8")) or {}
    operation = payload["paths"]["/api/attribution/explain/{entity_type}/{entity_id}"]["get"]
    operation.pop("x-skeldir-b17-p4", None)
    mutated_source = tmp_path / "attribution.regression.yaml"
    mutated_source.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    result = _run_enforcer("--source-contract-file", str(mutated_source))
    assert result.returncode != 0
    assert "source_missing_b17_p4_lock" in (result.stdout + result.stderr)


def test_b17_p4_enforcer_negative_control_detects_missing_pr_trigger_on_benchmark_workflow(
    tmp_path: Path,
) -> None:
    benchmark_workflow = (
        _repo_root() / ".github" / "workflows" / "b17-p4-mixed-workload-benchmark.yml"
    )
    payload = yaml.safe_load(benchmark_workflow.read_text(encoding="utf-8")) or {}
    triggers = payload.setdefault("on", {})
    triggers.pop("pull_request", None)
    mutated_workflow = tmp_path / "b17-p4-benchmark.regression.yml"
    mutated_workflow.write_text(
        yaml.safe_dump(payload, sort_keys=False),
        encoding="utf-8",
    )

    result = _run_enforcer("--benchmark-workflow-file", str(mutated_workflow))
    assert result.returncode != 0
    assert "benchmark_workflow_missing_pull_request_main_trigger" in (
        result.stdout + result.stderr
    )
