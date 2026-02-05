from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _run_validator(path: Path) -> subprocess.CompletedProcess[str]:
    root = _repo_root()
    return subprocess.run(
        [
            sys.executable,
            str(root / "scripts/ci/validate_llm_write_contract.py"),
            str(path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=root,
    )


def test_llm_write_contract_valid_fixture_passes():
    root = _repo_root()
    contract = root / "contracts-internal/llm/b07_llm_api_calls_write_contract.json"
    res = _run_validator(contract)
    assert res.returncode == 0, res.stdout + "\n" + res.stderr


def test_llm_write_contract_invalid_fixture_fails():
    root = _repo_root()
    contract = root / "backend/tests/fixtures/b07_p0_invalid_llm_write_contract.json"
    res = _run_validator(contract)
    assert res.returncode != 0
    assert "validation failed" in (res.stdout + res.stderr).lower()
