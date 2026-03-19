"""B1.4-P1 ingress privacy enforcer tests."""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _script_path() -> Path:
    return _repo_root() / "scripts" / "ci" / "enforce_b14_p1_ingress_privacy.py"


def _load_enforcer_module():
    spec = importlib.util.spec_from_file_location(
        "b14_p1_enforcer_module", _script_path()
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def test_b14_p1_enforcer_negative_control_dead_event_raw_payload_model_validate(
    tmp_path: Path,
) -> None:
    module = _load_enforcer_module()

    regression_source = tmp_path / "regression_dead_event_consumer.py"
    regression_source.write_text(
        "from pydantic import BaseModel\n"
        "class X(BaseModel):\n"
        "    a: str\n"
        "def f(dead_event):\n"
        "    return X.model_validate(dead_event.raw_payload)\n",
        encoding="utf-8",
    )

    original_requirements = module.SOURCE_REQUIREMENTS
    original_forbidden = module.SOURCE_FORBIDDEN_PATTERNS
    original_contracts = module.INTERNAL_CONTRACT_FILES
    try:
        module.SOURCE_REQUIREMENTS = ()
        module.SOURCE_FORBIDDEN_PATTERNS = (
            (
                regression_source,
                re.compile(r"model_validate\(\s*dead_event\.raw_payload"),
            ),
        )
        module.INTERNAL_CONTRACT_FILES = ()
        status, violations = module.run_enforcement([])
    finally:
        module.SOURCE_REQUIREMENTS = original_requirements
        module.SOURCE_FORBIDDEN_PATTERNS = original_forbidden
        module.INTERNAL_CONTRACT_FILES = original_contracts

    assert status != 0
    assert any("forbidden_pattern_detected" in item for item in violations)
