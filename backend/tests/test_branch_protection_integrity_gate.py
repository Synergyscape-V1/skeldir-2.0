from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "ci" / "enforce_branch_protection_integrity.py"
CONTRACT = REPO_ROOT / "contracts-internal" / "governance" / "main_branch_protection_integrity.main.json"


def _run_with_payload(tmp_path: Path, payload: dict) -> subprocess.CompletedProcess[str]:
    protection_path = tmp_path / "protection.json"
    protection_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--contract-file",
            str(CONTRACT),
            "--protection-json",
            str(protection_path),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _baseline_payload() -> dict:
    return {
        "required_pull_request_reviews": {
            "required_approving_review_count": 1,
            "require_code_owner_reviews": True,
            "bypass_pull_request_allowances": {
                "users": [],
                "teams": [],
                "apps": [],
            },
        },
        "enforce_admins": {"enabled": True},
    }


def test_branch_protection_integrity_gate_passes_compliant_payload(tmp_path: Path) -> None:
    result = _run_with_payload(tmp_path, _baseline_payload())
    assert result.returncode == 0, result.stdout + "\n" + result.stderr


def test_branch_protection_integrity_gate_fails_zero_approval_negative_control(tmp_path: Path) -> None:
    payload = _baseline_payload()
    payload["required_pull_request_reviews"]["required_approving_review_count"] = 0
    result = _run_with_payload(tmp_path, payload)
    assert result.returncode != 0
    combined = f"{result.stdout}\n{result.stderr}"
    assert "required_approving_review_count must be >=" in combined

