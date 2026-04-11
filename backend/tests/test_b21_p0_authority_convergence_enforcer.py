from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from scripts.ci.enforce_b21_p0_authority_convergence import run_enforcement


REPO_ROOT = Path(__file__).resolve().parents[2]
ENFORCER = REPO_ROOT / "scripts" / "ci" / "enforce_b21_p0_authority_convergence.py"


def test_b21_p0_authority_convergence_enforcer_passes_on_repo_state():
    status, violations = run_enforcement(repo_root=REPO_ROOT)
    assert status == 0, f"unexpected authority convergence violations: {violations}"


def test_b21_p0_authority_convergence_enforcer_negative_control_non_vacuous():
    proc = subprocess.run(
        [sys.executable, str(ENFORCER), "--simulate-regression"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode != 0
    combined = f"{proc.stdout}\n{proc.stderr}"
    assert "synthetic_regression=forced_failure_path" in combined
