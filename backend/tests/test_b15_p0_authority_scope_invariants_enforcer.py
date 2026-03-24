"""B1.5-P0 authority/scope/invariant enforcer tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _script_path() -> Path:
    return _repo_root() / "scripts" / "ci" / "enforce_b15_p0_authority_scope_invariants.py"


def _scope_contract_path() -> Path:
    return _repo_root() / "contracts-internal" / "governance" / "b15_p0_scope_lock.main.json"


def test_b15_p0_enforcer_passes_repo_baseline() -> None:
    result = subprocess.run(
        [sys.executable, str(_script_path())],
        cwd=_repo_root(),
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "result=PASS" in result.stdout


def test_b15_p0_enforcer_negative_control_synthetic_regression() -> None:
    result = subprocess.run(
        [sys.executable, str(_script_path()), "--simulate-regression"],
        cwd=_repo_root(),
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "synthetic_regression" in (result.stdout + result.stderr)


def test_b15_p0_enforcer_negative_control_forbidden_realtime_import(tmp_path: Path) -> None:
    decision_file = tmp_path / "BudgetDecisionSurface.tsx"
    decision_file.write_text(
        "import { verificationWebSocket } from '@/services/verificationWebSocket';\n"
        "export const marker = verificationWebSocket;\n",
        encoding="utf-8",
    )

    scope = json.loads(_scope_contract_path().read_text(encoding="utf-8"))
    scope["decision_surface_globs"] = [str(decision_file)]
    tmp_scope = tmp_path / "scope.regression.json"
    tmp_scope.write_text(json.dumps(scope, indent=2), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(_script_path()),
            "--scope-file",
            str(tmp_scope),
        ],
        cwd=_repo_root(),
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "forbidden_realtime_import" in (result.stdout + result.stderr)

