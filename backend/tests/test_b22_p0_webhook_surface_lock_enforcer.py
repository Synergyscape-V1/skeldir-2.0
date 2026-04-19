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
CONTRACT_SCOPE_FILE = REPO_ROOT / "backend" / "app" / "config" / "contract_scope.yaml"
TYPEGEN_SCRIPT = REPO_ROOT / "scripts" / "contracts" / "generate_frontend_types.sh"
BUNDLE_SCRIPT = REPO_ROOT / "scripts" / "contracts" / "bundle.sh"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ENFORCER), *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_b22_p0_webhook_surface_lock_enforcer_passes_repo_state() -> None:
    status, violations = run_enforcement(
        repo_root=REPO_ROOT,
        declared_surface_contract=DECLARED_SURFACE_CONTRACT,
        semantics_skip_allowlist=SEMANTICS_SKIP_ALLOWLIST,
        ci_workflow=CI_WORKFLOW,
        route_fidelity_test=ROUTE_FIDELITY_TEST,
        contract_scope_file=CONTRACT_SCOPE_FILE,
        typegen_script=TYPEGEN_SCRIPT,
        bundle_script=BUNDLE_SCRIPT,
    )
    assert status == 0, f"unexpected enforcement violations: {violations}"


def test_b22_p0_webhook_surface_lock_enforcer_negative_control_forced_regression() -> None:
    proc = _run("--simulate-regression")
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

    proc = _run("--ci-workflow", str(mutated_workflow))
    assert proc.returncode != 0
    assert "ci_missing_webhook_surface_lock_token" in (proc.stdout + proc.stderr)


def test_b22_p0_webhook_surface_lock_enforcer_negative_control_declared_surface_broadened(
    tmp_path: Path,
) -> None:
    payload = json.loads(DECLARED_SURFACE_CONTRACT.read_text(encoding="utf-8"))
    payload["public_operations"].append(
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

    proc = _run("--declared-surface-contract", str(mutated_contract))
    assert proc.returncode != 0
    assert "declared_public_surface_contains_unexpected" in (proc.stdout + proc.stderr)


def test_b22_p0_webhook_surface_lock_enforcer_negative_control_alias_promoted_public(
    tmp_path: Path,
) -> None:
    payload = json.loads(DECLARED_SURFACE_CONTRACT.read_text(encoding="utf-8"))
    payload["public_operations"] = [
        op
        for op in payload["public_operations"]
        if op["path"] != "/api/webhooks/stripe/payment_intent/succeeded"
    ]
    payload["public_operations"].append(
        {
            "method": "POST",
            "path": "/api/webhooks/stripe/payment_intent_succeeded",
            "provider": "stripe",
            "source_contract": "api-contracts/openapi/v1/webhooks/stripe.yaml",
            "bundle": "api-contracts/dist/openapi/v1/webhooks.stripe.bundled.yaml",
            "generated_type": "frontend/src/types/api/webhooks-stripe.ts",
        }
    )
    payload["runtime_transport_aliases"] = []

    mutated_contract = tmp_path / "b22.alias.regression.contract.json"
    mutated_contract.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    proc = _run("--declared-surface-contract", str(mutated_contract))
    assert proc.returncode != 0
    assert "declared_public_surface_missing_expected" in (proc.stdout + proc.stderr)
    assert "declared_public_surface_contains_unexpected" in (proc.stdout + proc.stderr)


def test_b22_p0_webhook_surface_lock_enforcer_negative_control_contract_scope_alias_allowlist_drift(
    tmp_path: Path,
) -> None:
    payload = yaml.safe_load(CONTRACT_SCOPE_FILE.read_text(encoding="utf-8")) or {}
    payload["runtime_transport_only_allowlist"] = []

    mutated_scope = tmp_path / "contract_scope.regression.yaml"
    mutated_scope.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    proc = _run("--contract-scope-file", str(mutated_scope))
    assert proc.returncode != 0
    assert "contract_scope_runtime_transport_only_allowlist_missing_expected" in (
        proc.stdout + proc.stderr
    )


def test_b22_p0_webhook_surface_lock_enforcer_negative_control_semantics_allowlist_webhook_bypass(
    tmp_path: Path,
) -> None:
    payload = yaml.safe_load(SEMANTICS_SKIP_ALLOWLIST.read_text(encoding="utf-8")) or {}
    payload.setdefault("bundles", {})["webhooks.shopify.bundled.yaml"] = "regression"
    mutated_allowlist = tmp_path / "semantics.regression.yaml"
    mutated_allowlist.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    proc = _run("--semantics-skip-allowlist", str(mutated_allowlist))
    assert proc.returncode != 0
    assert "semantics_skip_allowlist_contains_webhook_bundles:webhooks.shopify.bundled.yaml" in (
        proc.stdout + proc.stderr
    )
