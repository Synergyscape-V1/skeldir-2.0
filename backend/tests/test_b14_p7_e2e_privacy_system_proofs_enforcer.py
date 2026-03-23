"""B1.4-P7 final E2E privacy system proof enforcer tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "ci" / "enforce_b14_p7_e2e_privacy_system_proofs.py"
REQUIRED_CHECKS = (
    REPO_ROOT / "contracts-internal" / "governance" / "b03_phase2_required_status_checks.main.json"
)


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


def test_b14_p7_enforcer_passes_repo_state() -> None:
    result = _run()
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "final E2E gate passed" in result.stdout


def test_b14_p7_negative_control_detects_missing_required_context(tmp_path: Path) -> None:
    payload = json.loads(REQUIRED_CHECKS.read_text(encoding="utf-8"))
    payload["required_contexts"] = [
        value for value in payload.get("required_contexts", []) if value != "B1.4 P7 E2E Privacy System Proofs"
    ]
    checks_copy = tmp_path / "required_checks.json"
    checks_copy.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    result = _run(["--required-checks-contract", str(checks_copy)])
    assert result.returncode != 0
    assert "missing context: B1.4 P7 E2E Privacy System Proofs" in (result.stdout + result.stderr)


def test_b14_p7_negative_control_runtime_artifacts_incomplete(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    junit_xml = artifacts_dir / "junit.xml"
    junit_xml.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<testsuite tests="2" skipped="0" failures="0" errors="0">
  <testcase classname="p7" name="test_b14_p7_composed_runtime_privacy_contract_holds_end_to_end"></testcase>
  <testcase classname="p7" name="test_b14_p7_negative_controls_and_tenant_fail_closed_guards"></testcase>
</testsuite>
""",
        encoding="utf-8",
    )
    (artifacts_dir / "p7_composed_runtime_report.json").write_text(
        json.dumps(
            {
                "pii_stripped_before_storage": True,
                "session_expiry_24h_enforced": True,
                "cross_session_reconstruction_blocked": True,
                "attribution_session_scoped": True,
                "raw_events_older_than_90d_expired": True,
                "deletion_deterministic": True,
                "export_privacy_safe": True,
                "log_redaction_effective": True,
                "artifact_no_leak_scan_passed": True,
                "tenant_isolation_fail_closed": True,
                "prior_phase_preservation_p0_to_p6": True,
            }
        ),
        encoding="utf-8",
    )
    result = _run(
        [
            "--require-runtime-execution",
            "--junit-xml",
            str(junit_xml),
            "--artifacts-dir",
            str(artifacts_dir),
        ]
    )
    assert result.returncode != 0
    assert "missing runtime proof artifact" in (result.stdout + result.stderr)


def test_b14_p7_negative_control_simulate_regression() -> None:
    result = _run(["--simulate-regression"])
    assert result.returncode != 0
    assert "synthetic regression" in (result.stdout + result.stderr)
