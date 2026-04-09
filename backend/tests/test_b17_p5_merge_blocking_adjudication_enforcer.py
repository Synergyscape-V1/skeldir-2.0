"""B1.7-P5 merge-blocking adjudication enforcer tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _script_path() -> Path:
    return _repo_root() / "scripts" / "ci" / "enforce_b17_p5_merge_blocking_adjudication.py"


def _run_enforcer(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_script_path()), *args],
        cwd=_repo_root(),
        check=False,
        capture_output=True,
        text=True,
    )


def test_b17_p5_enforcer_passes_repo_baseline() -> None:
    result = _run_enforcer()
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "result=PASS" in result.stdout


def test_b17_p5_enforcer_negative_control_synthetic_regression() -> None:
    result = _run_enforcer("--simulate-regression")
    assert result.returncode != 0
    assert "synthetic_regression" in (result.stdout + result.stderr)


def test_b17_p5_enforcer_negative_control_missing_required_context(tmp_path: Path) -> None:
    source = (
        _repo_root()
        / "contracts-internal"
        / "governance"
        / "b03_phase2_required_status_checks.main.json"
    )
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["required_contexts"] = [
        value
        for value in payload.get("required_contexts", [])
        if value != "B1.7 Explanation Runtime Adjudication"
    ]
    mutated = tmp_path / "required_checks.regression.json"
    mutated.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    result = _run_enforcer("--required-checks-contract-file", str(mutated))
    assert result.returncode != 0
    assert "required_checks_missing_b17_required_context" in (result.stdout + result.stderr)


def test_b17_p5_enforcer_negative_control_missing_required_benchmark_context(
    tmp_path: Path,
) -> None:
    source = (
        _repo_root()
        / "contracts-internal"
        / "governance"
        / "b03_phase2_required_status_checks.main.json"
    )
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["required_contexts"] = [
        value
        for value in payload.get("required_contexts", [])
        if value != "B1.7 P4 Mixed Workload Benchmark"
    ]
    mutated = tmp_path / "required_checks.benchmark.regression.json"
    mutated.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    result = _run_enforcer("--required-checks-contract-file", str(mutated))
    assert result.returncode != 0
    assert "required_checks_missing_b17_benchmark_required_context" in (
        result.stdout + result.stderr
    )


def test_b17_p5_enforcer_negative_control_detects_future_decl_only(tmp_path: Path) -> None:
    source = (
        _repo_root()
        / "contracts-internal"
        / "governance"
        / "b03_phase2_required_status_checks.main.json"
    )
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["future_required_context_declarations"] = [
        {
            "name": "B1.7 Explanation Runtime Adjudication",
            "activation_phase": "B1.7-P5",
            "source_contract": "api-contracts/openapi/v1/attribution.yaml#/paths/~1api~1attribution~1explain~1{entity_type}~1{entity_id}/get/x-skeldir-b17-p1",
        }
    ]
    mutated = tmp_path / "required_checks.future.regression.json"
    mutated.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    result = _run_enforcer("--required-checks-contract-file", str(mutated))
    assert result.returncode != 0
    assert "required_checks_b17_context_must_not_be_future_declared" in (
        result.stdout + result.stderr
    )


def test_b17_p5_enforcer_negative_control_detects_missing_ci_runtime_command(
    tmp_path: Path,
) -> None:
    source = _repo_root() / ".github" / "workflows" / "ci.yml"
    text = source.read_text(encoding="utf-8")
    mutated_text = text.replace(
        "pytest backend/tests/test_b17_p5_anti_chat_surface_runtime.py -q",
        "pytest backend/tests/test_removed_anti_chat_surface_runtime.py -q",
    )
    mutated = tmp_path / "ci.regression.yml"
    mutated.write_text(mutated_text, encoding="utf-8")

    result = _run_enforcer("--ci-workflow-file", str(mutated))
    assert result.returncode != 0
    assert (
        "ci_required_job_missing_command:test_b17_p5_anti_chat_surface_runtime.py"
        in (result.stdout + result.stderr)
    )


def test_b17_p5_enforcer_negative_control_detects_explanation_skip_allowlist_regression(
    tmp_path: Path,
) -> None:
    source = _repo_root() / "tests" / "contract" / "semantics_skip_allowlist.yaml"
    payload = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    payload.setdefault("bundles", {})["attribution.bundled.yaml"] = "regression fixture"
    mutated = tmp_path / "semantics_skip_allowlist.regression.yaml"
    mutated.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    result = _run_enforcer("--semantics-skip-allowlist-file", str(mutated))
    assert result.returncode != 0
    assert "semantics_skip_allowlist_forbidden_bundle:attribution.bundled.yaml" in (
        result.stdout + result.stderr
    )
