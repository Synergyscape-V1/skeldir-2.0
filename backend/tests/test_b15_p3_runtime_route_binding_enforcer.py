"""B1.5-P3 runtime route binding enforcer tests."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _script_path() -> Path:
    return _repo_root() / "scripts" / "ci" / "enforce_b15_p3_runtime_route_binding.py"


def test_b15_p3_enforcer_passes_repo_baseline() -> None:
    result = subprocess.run(
        [sys.executable, str(_script_path())],
        cwd=_repo_root(),
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "result=PASS" in result.stdout


def test_b15_p3_enforcer_negative_control_synthetic_regression() -> None:
    result = subprocess.run(
        [sys.executable, str(_script_path()), "--simulate-regression"],
        cwd=_repo_root(),
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "synthetic_regression" in (result.stdout + result.stderr)


def test_b15_p3_enforcer_negative_control_skip_allowlist_regression(tmp_path: Path) -> None:
    original_skip_text = (
        _repo_root() / "tests" / "contract" / "semantics_skip_allowlist.yaml"
    ).read_text(encoding="utf-8")
    original_skip = yaml.safe_load(original_skip_text) or {}
    bundles = original_skip.get("bundles")
    if not isinstance(bundles, dict):
        bundles = {}
    bundles["llm-investigations.bundled.yaml"] = "regression"
    original_skip["bundles"] = bundles
    mutated_skip = tmp_path / "semantics_skip_allowlist.regression.yaml"
    mutated_skip.write_text(yaml.safe_dump(original_skip, sort_keys=False), encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(_script_path()),
            "--semantics-skip-file",
            str(mutated_skip),
        ],
        cwd=_repo_root(),
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "semantics_allowlist_still_skips_bundle" in (result.stdout + result.stderr)


def test_b15_p3_enforcer_negative_control_heavy_status_projection(tmp_path: Path) -> None:
    original_service = (
        _repo_root() / "backend" / "app" / "services" / "investigation.py"
    ).read_text(encoding="utf-8")
    mutated_service = tmp_path / "investigation.regression.py"
    mutated_text = original_service.replace(
        "                    cancelled_at,\n                    failure_code,",
        "                    cancelled_at,\n                    result,\n                    failure_code,",
        1,
    )
    mutated_service.write_text(
        mutated_text,
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            sys.executable,
            str(_script_path()),
            "--investigation-service-file",
            str(mutated_service),
        ],
        cwd=_repo_root(),
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "investigation_projection_hydrates_result_payload" in (
        result.stdout + result.stderr
    )
