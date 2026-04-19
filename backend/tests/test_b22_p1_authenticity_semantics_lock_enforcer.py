from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

from scripts.ci.enforce_b22_p1_authenticity_semantics_lock import run_enforcement


REPO_ROOT = Path(__file__).resolve().parents[2]
ENFORCER = REPO_ROOT / "scripts" / "ci" / "enforce_b22_p1_authenticity_semantics_lock.py"
GOVERNANCE_CONTRACT = (
    REPO_ROOT
    / "contracts-internal"
    / "governance"
    / "b22_p1_authenticity_semantics.main.json"
)
WEBHOOKS_FILE = REPO_ROOT / "backend" / "app" / "api" / "webhooks.py"
SIGNATURES_FILE = REPO_ROOT / "backend" / "app" / "webhooks" / "signatures.py"
PAYPAL_CONTRACT_FILE = REPO_ROOT / "api-contracts" / "openapi" / "v1" / "webhooks" / "paypal.yaml"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
B12_P8_TEST = REPO_ROOT / "backend" / "tests" / "test_b12_p8_error_contract_normalization.py"
B22_P1_TEST = REPO_ROOT / "backend" / "tests" / "test_b22_p1_authenticity_semantics.py"
B045_TEST = REPO_ROOT / "backend" / "tests" / "test_b045_webhooks.py"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ENFORCER), *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_b22_p1_authenticity_semantics_lock_enforcer_passes_repo_state() -> None:
    status, violations = run_enforcement(
        governance_contract=GOVERNANCE_CONTRACT,
        webhooks_file=WEBHOOKS_FILE,
        signatures_file=SIGNATURES_FILE,
        paypal_contract_file=PAYPAL_CONTRACT_FILE,
        ci_workflow=CI_WORKFLOW,
        b12_p8_test=B12_P8_TEST,
        b22_p1_test=B22_P1_TEST,
        b045_test=B045_TEST,
    )
    assert status == 0, f"unexpected enforcement violations: {violations}"


def test_b22_p1_authenticity_semantics_lock_enforcer_negative_control_forced_regression() -> None:
    proc = _run("--simulate-regression")
    assert proc.returncode != 0
    assert "synthetic_regression=forced_failure_path" in (proc.stdout + proc.stderr)


def test_b22_p1_authenticity_semantics_lock_enforcer_negative_control_ci_wiring_missing(
    tmp_path: Path,
) -> None:
    mutated_workflow = tmp_path / "ci.regression.yml"
    mutated_workflow.write_text(
        CI_WORKFLOW.read_text(encoding="utf-8").replace(
            "python scripts/ci/enforce_b22_p1_authenticity_semantics_lock.py",
            "python scripts/ci/enforce_b22_p1_regressed.py",
            1,
        ),
        encoding="utf-8",
    )

    proc = _run("--ci-workflow", str(mutated_workflow))
    assert proc.returncode != 0
    assert "ci_missing_b22_p1_token" in (proc.stdout + proc.stderr)


def test_b22_p1_authenticity_semantics_lock_enforcer_negative_control_paypal_header_not_required(
    tmp_path: Path,
) -> None:
    payload = yaml.safe_load(PAYPAL_CONTRACT_FILE.read_text(encoding="utf-8")) or {}
    parameters = (
        payload.setdefault("paths", {})
        .setdefault("/api/webhooks/paypal/sale_completed", {})
        .setdefault("post", {})
        .setdefault("parameters", [])
    )
    for param in parameters:
        if (
            isinstance(param, dict)
            and str(param.get("name", "")).upper() == "PAYPAL-TRANSMISSION-TIME"
        ):
            param["required"] = False
            break
    mutated_contract = tmp_path / "paypal.regression.yaml"
    mutated_contract.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    proc = _run("--paypal-contract-file", str(mutated_contract))
    assert proc.returncode != 0
    assert "paypal_openapi_header_not_required:PayPal-Transmission-Time" in (
        proc.stdout + proc.stderr
    )


def test_b22_p1_authenticity_semantics_lock_enforcer_negative_control_signature_regression(
    tmp_path: Path,
) -> None:
    mutated_signatures = tmp_path / "signatures.regression.py"
    mutated_signatures.write_text(
        SIGNATURES_FILE.read_text(encoding="utf-8").replace(
            "> PAYPAL_AUTH_TOLERANCE_SECONDS:",
            "> PAYPAL_AUTH_TOLERANCE_SECONDS_REGRESSED:",
            1,
        ),
        encoding="utf-8",
    )

    proc = _run("--signatures-file", str(mutated_signatures))
    assert proc.returncode != 0
    assert "signatures_paypal_missing_tolerance_constant_usage" in (
        proc.stdout + proc.stderr
    )


def test_b22_p1_authenticity_semantics_lock_enforcer_negative_control_provider_set_drift(
    tmp_path: Path,
) -> None:
    payload = json.loads(GOVERNANCE_CONTRACT.read_text(encoding="utf-8"))
    payload["providers"].pop("paypal")
    mutated_governance = tmp_path / "b22_p1.regression.contract.json"
    mutated_governance.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    proc = _run("--governance-contract", str(mutated_governance))
    assert proc.returncode != 0
    assert "contract_provider_set_mismatch" in (proc.stdout + proc.stderr)
