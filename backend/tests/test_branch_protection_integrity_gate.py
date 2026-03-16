from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "ci" / "enforce_branch_protection_integrity.py"
CONTRACT = REPO_ROOT / "contracts-internal" / "governance" / "main_branch_protection_integrity.main.json"


def _review_policy_contract() -> dict:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    review_policy = contract.get("review_policy")
    assert isinstance(review_policy, dict)
    return review_policy


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
    review_policy = _review_policy_contract()
    return {
        "required_pull_request_reviews": {
            "required_approving_review_count": int(
                review_policy.get("required_approving_review_count_min", 0)
            ),
            "require_code_owner_reviews": bool(review_policy.get("require_code_owner_reviews", False)),
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


def test_branch_protection_integrity_gate_fails_bypass_allowance_negative_control(tmp_path: Path) -> None:
    payload = _baseline_payload()
    payload["required_pull_request_reviews"]["bypass_pull_request_allowances"]["users"] = [
        {"login": "forbidden-bypass"}
    ]
    result = _run_with_payload(tmp_path, payload)
    assert result.returncode != 0
    combined = f"{result.stdout}\n{result.stderr}"
    assert "bypass_pull_request_allowances must be empty" in combined
