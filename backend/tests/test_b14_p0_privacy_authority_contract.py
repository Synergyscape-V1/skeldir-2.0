from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "ci" / "enforce_b14_p0_privacy_authority.py"
AUTHORITY = REPO_ROOT / "contracts-internal" / "governance" / "b14_p0_privacy_authority.main.json"
REQUIRED_CHECKS = REPO_ROOT / "contracts-internal" / "governance" / "b03_phase2_required_status_checks.main.json"
WEBHOOKS = REPO_ROOT / "backend" / "app" / "api" / "webhooks.py"


def _run(extra_args: list[str] | None = None) -> subprocess.CompletedProcess[str]:
    args = [sys.executable, str(SCRIPT)]
    if extra_args:
        args.extend(extra_args)
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=REPO_ROOT,
    )


def test_b14_p0_privacy_authority_gate_passes_repo_state() -> None:
    result = _run()
    assert result.returncode == 0, result.stdout + "\n" + result.stderr


def test_b14_p0_negative_control_detects_missing_proxy_identity_list(tmp_path: Path) -> None:
    payload = json.loads(AUTHORITY.read_text(encoding="utf-8"))
    payload["banned_proxy_identifier_keys"] = []
    artifact_copy = tmp_path / "authority.json"
    artifact_copy.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    result = _run(["--authority-artifact", str(artifact_copy)])
    assert result.returncode != 0
    combined = f"{result.stdout}\n{result.stderr}"
    assert "banned_proxy_identifier_keys" in combined


def test_b14_p0_negative_control_detects_missing_required_context(tmp_path: Path) -> None:
    payload = json.loads(REQUIRED_CHECKS.read_text(encoding="utf-8"))
    payload["required_contexts"] = [
        value
        for value in payload.get("required_contexts", [])
        if value != "B1.4 P0 Privacy Authority Lock"
    ]
    checks_copy = tmp_path / "required_checks.json"
    checks_copy.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    result = _run(["--required-checks-contract", str(checks_copy)])
    assert result.returncode != 0
    combined = f"{result.stdout}\n{result.stderr}"
    assert "missing context: B1.4 P0 Privacy Authority Lock" in combined


def test_b14_p0_negative_control_detects_deterministic_session_derivation(tmp_path: Path) -> None:
    mutated = WEBHOOKS.read_text(encoding="utf-8").replace(
        "str(generate_privacy_session_id())",
        "str(uuid5(NAMESPACE_URL, f\"stripe:{payload.id}\"))",
        1,
    )
    webhooks_copy = tmp_path / "webhooks.py"
    webhooks_copy.write_text(mutated, encoding="utf-8")

    result = _run(["--webhooks-file", str(webhooks_copy)])
    assert result.returncode != 0
    combined = f"{result.stdout}\n{result.stderr}"
    assert "must not derive session ids deterministically" in combined

