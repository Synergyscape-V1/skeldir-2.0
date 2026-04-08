"""B1.7-P6 adjudication-plane enforcer tests."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _script_path() -> Path:
    return _repo_root() / "scripts" / "ci" / "enforce_b17_p6_adjudication_plane.py"


def _run_enforcer(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_script_path()), *args],
        cwd=_repo_root(),
        check=False,
        capture_output=True,
        text=True,
    )


def test_b17_p6_plane_enforcer_passes_repo_baseline() -> None:
    result = _run_enforcer()
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "result=PASS" in result.stdout


def test_b17_p6_plane_enforcer_negative_control_synthetic_regression() -> None:
    result = _run_enforcer("--simulate-regression")
    assert result.returncode != 0
    assert "synthetic_regression" in (result.stdout + result.stderr)


def test_b17_p6_plane_enforcer_detects_missing_ci_p6_runtime_step(tmp_path: Path) -> None:
    source = _repo_root() / ".github" / "workflows" / "ci.yml"
    text = source.read_text(encoding="utf-8")
    mutated_text = text.replace(
        "pytest backend/tests/test_b17_p6_end_to_end_runtime.py -q",
        "pytest backend/tests/test_removed_p6_end_to_end_runtime.py -q",
    )
    mutated = tmp_path / "ci.regression.yml"
    mutated.write_text(mutated_text, encoding="utf-8")

    result = _run_enforcer("--ci-workflow-file", str(mutated))
    assert result.returncode != 0
    assert "ci_missing_required_token:test_b17_p6_end_to_end_runtime.py" in (
        result.stdout + result.stderr
    )


def test_b17_p6_plane_enforcer_detects_missing_main_push_benchmark_trigger(
    tmp_path: Path,
) -> None:
    source = _repo_root() / ".github" / "workflows" / "b17-p4-mixed-workload-benchmark.yml"
    text = source.read_text(encoding="utf-8")
    mutated_text = text.replace("branches: [main]", "branches: [develop]")
    mutated = tmp_path / "benchmark.regression.yml"
    mutated.write_text(mutated_text, encoding="utf-8")

    result = _run_enforcer("--benchmark-workflow-file", str(mutated))
    assert result.returncode != 0
    assert "benchmark_missing_push_main_trigger" in (result.stdout + result.stderr)
