"""B1.7-P0 explanation surface lock enforcer tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _script_path() -> Path:
    return _repo_root() / "scripts" / "ci" / "enforce_b17_p0_explanation_surface_lock.py"


def test_b17_p0_enforcer_passes_repo_baseline() -> None:
    result = subprocess.run(
        [sys.executable, str(_script_path())],
        cwd=_repo_root(),
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "result=PASS" in result.stdout


def test_b17_p0_enforcer_negative_control_synthetic_regression() -> None:
    result = subprocess.run(
        [sys.executable, str(_script_path()), "--simulate-regression"],
        cwd=_repo_root(),
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "synthetic_regression" in (result.stdout + result.stderr)


def test_b17_p0_enforcer_negative_control_detects_canonical_route_drift(tmp_path: Path) -> None:
    original_contract_path = (
        _repo_root()
        / "contracts-internal"
        / "governance"
        / "b17_p0_explanation_surface_lock.main.json"
    )
    contract = json.loads(original_contract_path.read_text(encoding="utf-8"))
    contract["canonical_explanation_surface"]["path"] = "/api/v1/explain/{entity_type}/{entity_id}"

    mutated_contract = tmp_path / "b17_p0_explanation_surface_lock.regression.json"
    mutated_contract.write_text(json.dumps(contract, indent=2), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(_script_path()),
            "--contract-file",
            str(mutated_contract),
        ],
        cwd=_repo_root(),
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "canonical_path_mismatch" in (result.stdout + result.stderr)


def test_b17_p0_enforcer_negative_control_detects_skip_allowlist_regression(tmp_path: Path) -> None:
    skip_file = _repo_root() / "tests" / "contract" / "semantics_skip_allowlist.yaml"
    payload = yaml.safe_load(skip_file.read_text(encoding="utf-8")) or {}
    payload.setdefault("bundles", {})["llm-explanations.bundled.yaml"] = "regression"

    mutated_skip = tmp_path / "semantics_skip_allowlist.regression.yaml"
    mutated_skip.write_text(yaml.safe_dump(payload, sort_keys=True), encoding="utf-8")

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
    assert "governed_bundle_present_in_explicit_skip_allowlist" in (
        result.stdout + result.stderr
    )
