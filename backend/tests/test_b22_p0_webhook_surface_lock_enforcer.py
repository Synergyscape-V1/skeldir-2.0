from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

from scripts.ci.enforce_b22_p0_webhook_surface_lock import run_enforcement


REPO_ROOT = Path(__file__).resolve().parents[2]
ENFORCER = REPO_ROOT / "scripts" / "ci" / "enforce_b22_p0_webhook_surface_lock.py"
DECLARED_SURFACE_CONTRACT = (
    REPO_ROOT
    / "contracts-internal"
    / "governance"
    / "b22_p0_declared_webhook_surface.main.json"
)
SEMANTICS_SKIP_ALLOWLIST = REPO_ROOT / "tests" / "contract" / "semantics_skip_allowlist.yaml"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
ROUTE_FIDELITY_TEST = REPO_ROOT / "tests" / "contract" / "test_route_fidelity.py"
TYPEGEN_SCRIPT = REPO_ROOT / "scripts" / "contracts" / "generate_frontend_types.sh"
BUNDLE_SCRIPT = REPO_ROOT / "scripts" / "contracts" / "bundle.sh"


def test_b22_p0_webhook_surface_lock_enforcer_passes_repo_state() -> None:
    status, violations = run_enforcement(
        repo_root=REPO_ROOT,
        declared_surface_contract=DECLARED_SURFACE_CONTRACT,
        semantics_skip_allowlist=SEMANTICS_SKIP_ALLOWLIST,
        ci_workflow=CI_WORKFLOW,
        route_fidelity_test=ROUTE_FIDELITY_TEST,
        typegen_script=TYPEGEN_SCRIPT,
        bundle_script=BUNDLE_SCRIPT,
    )
    assert status == 0, f"unexpected enforcement violations: {violations}"


def test_b22_p0_webhook_surface_lock_enforcer_negative_control_forced_regression() -> None:
    proc = subprocess.run(
        [sys.executable, str(ENFORCER), "--simulate-regression"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode != 0
    assert "synthetic_regression=forced_failure_path" in (proc.stdout + proc.stderr)


def test_b22_p0_webhook_surface_lock_enforcer_negative_control_ci_wiring_missing(
    tmp_path: Path,
) -> None:
    mutated_workflow = tmp_path / "ci.regression.yml"
    mutated_workflow.write_text(
        CI_WORKFLOW.read_text(encoding="utf-8").replace(
            "python scripts/ci/enforce_b22_p0_webhook_surface_lock.py",
            "python scripts/ci/enforce_b22_p0_regressed.py",
            1,
        ),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            sys.executable,
            str(ENFORCER),
            "--ci-workflow",
            str(mutated_workflow),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode != 0
    assert "ci_missing_webhook_surface_lock_token" in (proc.stdout + proc.stderr)


def test_b22_p0_webhook_surface_lock_enforcer_negative_control_declared_surface_drift(
    tmp_path: Path,
) -> None:
    payload = json.loads(DECLARED_SURFACE_CONTRACT.read_text(encoding="utf-8"))
    payload["operations"].append(
        {
            "method": "POST",
            "path": "/api/webhooks/shopify/orders/paid",
            "provider": "shopify",
            "source_contract": "api-contracts/openapi/v1/webhooks/shopify.yaml",
            "bundle": "api-contracts/dist/openapi/v1/webhooks.shopify.bundled.yaml",
            "generated_type": "frontend/src/types/api/webhooks-shopify.ts",
        }
    )
    mutated_contract = tmp_path / "b22.regression.contract.json"
    mutated_contract.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    proc = subprocess.run(
        [
            sys.executable,
            str(ENFORCER),
            "--declared-surface-contract",
            str(mutated_contract),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode != 0
    assert "runtime_routes_missing_declared" in (proc.stdout + proc.stderr)


def test_b22_p0_webhook_surface_lock_enforcer_negative_control_semantics_allowlist_webhook_bypass(
    tmp_path: Path,
) -> None:
    payload = yaml.safe_load(SEMANTICS_SKIP_ALLOWLIST.read_text(encoding="utf-8")) or {}
    payload.setdefault("bundles", {})["webhooks.shopify.bundled.yaml"] = "regression"
    mutated_allowlist = tmp_path / "semantics.regression.yaml"
    mutated_allowlist.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    proc = subprocess.run(
        [
            sys.executable,
            str(ENFORCER),
            "--semantics-skip-allowlist",
            str(mutated_allowlist),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode != 0
    assert "semantics_skip_allowlist_contains_webhook_bundles:webhooks.shopify.bundled.yaml" in (
        proc.stdout + proc.stderr
    )
