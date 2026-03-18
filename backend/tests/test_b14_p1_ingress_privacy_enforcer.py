"""B1.4-P1 ingress privacy enforcer tests."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _script_path() -> Path:
    return _repo_root() / "scripts" / "ci" / "enforce_b14_p1_ingress_privacy.py"


def test_b14_p1_enforcer_passes_repo_baseline() -> None:
    result = subprocess.run(
        [sys.executable, str(_script_path())],
        cwd=_repo_root(),
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "result=PASS" in result.stdout


def test_b14_p1_enforcer_negative_control_contract_regression(tmp_path: Path) -> None:
    regression_contract = tmp_path / "regression_internal_contract.yaml"
    regression_contract.write_text(
        "components:\n"
        "  schemas:\n"
        "    InternalIngressStorage:\n"
        "      type: object\n"
        "      properties:\n"
        "        email:\n"
        "          type: string\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(_script_path()),
            "--additional-contract-file",
            str(regression_contract),
        ],
        cwd=_repo_root(),
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "internal_contract_pii_key" in (result.stdout + result.stderr)


def test_b14_p1_enforcer_negative_control_synthetic_regression() -> None:
    result = subprocess.run(
        [sys.executable, str(_script_path()), "--simulate-regression"],
        cwd=_repo_root(),
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "synthetic_regression" in (result.stdout + result.stderr)
