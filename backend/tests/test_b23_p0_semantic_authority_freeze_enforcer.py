from __future__ import annotations

import json
import importlib.util
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ENFORCER = REPO_ROOT / "scripts" / "ci" / "enforce_b23_p0_semantic_authority_freeze.py"
_SPEC = importlib.util.spec_from_file_location("b23_p0_enforcer_module", ENFORCER)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
run_enforcement = _MODULE.run_enforcement

GOVERNANCE_CONTRACT = (
    REPO_ROOT / "contracts-internal" / "governance" / "b23_p0_semantic_authority_freeze.main.json"
)
SEMANTIC_AUTHORITY_FILE = REPO_ROOT / "backend" / "app" / "revenue_verification" / "semantic_authority.py"
EVENT_SERVICE_FILE = REPO_ROOT / "backend" / "app" / "ingestion" / "event_service.py"
RUNTIME_PROOF_FILE = REPO_ROOT / "backend" / "tests" / "test_b23_p0_semantic_authority.py"
ENFORCER_PROOF_FILE = (
    REPO_ROOT / "backend" / "tests" / "test_b23_p0_semantic_authority_freeze_enforcer.py"
)
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
TOPOLOGY_MODEL_FILE = REPO_ROOT / "backend" / "app" / "models" / "attribution_commerce_identity.py"
TOPOLOGY_PERSISTENCE_FILE = REPO_ROOT / "backend" / "app" / "privacy" / "durable_commerce_identity.py"
TOPOLOGY_SCHEMA_PROOF_FILE = (
    REPO_ROOT
    / "alembic"
    / "versions"
    / "007_skeldir_foundation"
    / "202604231130_b23_p0_durable_commerce_identity_substrate.py"
)


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ENFORCER), *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_b23_p0_semantic_authority_freeze_enforcer_passes_repo_state() -> None:
    status, violations = run_enforcement(
        repo_root=REPO_ROOT,
        governance_contract_file=GOVERNANCE_CONTRACT,
        semantic_authority_file=SEMANTIC_AUTHORITY_FILE,
        event_service_file=EVENT_SERVICE_FILE,
        runtime_proof_file=RUNTIME_PROOF_FILE,
        enforcer_proof_file=ENFORCER_PROOF_FILE,
        ci_workflow_file=CI_WORKFLOW,
        topology_model_file=TOPOLOGY_MODEL_FILE,
        topology_persistence_file=TOPOLOGY_PERSISTENCE_FILE,
        topology_schema_proof_file=TOPOLOGY_SCHEMA_PROOF_FILE,
    )
    assert status == 0, f"unexpected B2.3-P0 enforcement violations: {violations}"


def test_b23_p0_semantic_authority_freeze_enforcer_negative_control_forced_regression() -> None:
    proc = _run("--simulate-regression")
    assert proc.returncode != 0
    assert "synthetic_regression=forced_failure_path" in (proc.stdout + proc.stderr)


def test_b23_p0_semantic_authority_freeze_enforcer_negative_control_baseline_drift() -> None:
    proc = _run("--simulate-baseline-drift")
    assert proc.returncode != 0
    assert "baseline_authority_main_ancestor_check_failed" in (proc.stdout + proc.stderr)


def test_b23_p0_semantic_authority_freeze_enforcer_negative_control_ci_wiring_missing(
    tmp_path: Path,
) -> None:
    mutated_workflow = tmp_path / "ci.regression.yml"
    mutated_workflow.write_text(
        CI_WORKFLOW.read_text(encoding="utf-8").replace(
            "python scripts/ci/enforce_b23_p0_semantic_authority_freeze.py",
            "python scripts/ci/enforce_b23_p0_semantic_authority_drifted.py",
            1,
        ),
        encoding="utf-8",
    )

    proc = _run("--ci-workflow-file", str(mutated_workflow))
    assert proc.returncode != 0
    assert "workflow_missing_token:python scripts/ci/enforce_b23_p0_semantic_authority_freeze.py" in (
        proc.stdout + proc.stderr
    )


def test_b23_p0_semantic_authority_freeze_enforcer_negative_control_precedence_drift(
    tmp_path: Path,
) -> None:
    payload = json.loads(GOVERNANCE_CONTRACT.read_text(encoding="utf-8"))
    payload["shared_identity_canonicalization"]["precedence_order"] = [
        "provider_native_commerce_reference",
        "normalized_commerce_reference",
        "strict_order_id",
    ]
    mutated = tmp_path / "b23_p0.contract.regression.json"
    mutated.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    proc = _run("--governance-contract-file", str(mutated))
    assert proc.returncode != 0
    assert "contract_precedence_order_mismatch" in (proc.stdout + proc.stderr)


def test_b23_p0_semantic_authority_freeze_enforcer_negative_control_dual_side_divergence(
    tmp_path: Path,
) -> None:
    mutated_semantics = tmp_path / "semantic_authority.regression.py"
    mutated_semantics.write_text(
        SEMANTIC_AUTHORITY_FILE.read_text(encoding="utf-8").replace(
            "def canonicalize_attribution_commerce_reference(",
            "def canonicalize_attribution_commerce_reference_regressed(",
            1,
        ),
        encoding="utf-8",
    )

    proc = _run("--semantic-authority-file", str(mutated_semantics))
    assert proc.returncode != 0
    assert (
        "semantic_authority_missing_token:def canonicalize_attribution_commerce_reference(" in (
            proc.stdout + proc.stderr
        )
    )


def test_b23_p0_semantic_authority_freeze_enforcer_negative_control_topology_contract_mismatch(
    tmp_path: Path,
) -> None:
    payload = json.loads(GOVERNANCE_CONTRACT.read_text(encoding="utf-8"))
    payload["privacy_safe_delayed_arrival"]["topology_schema_binding"]["table"] = "shadow_identity_graph"
    mutated = tmp_path / "b23_p0.contract.topology_mismatch.json"
    mutated.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    proc = _run("--governance-contract-file", str(mutated))
    assert proc.returncode != 0
    assert "contract_topology_table_mismatch" in (proc.stdout + proc.stderr)


def test_b23_p0_semantic_authority_freeze_enforcer_negative_control_topology_schema_absent(
    tmp_path: Path,
) -> None:
    mutated_schema = tmp_path / "topology_schema.regression.py"
    mutated_schema.write_text(
        TOPOLOGY_SCHEMA_PROOF_FILE.read_text(encoding="utf-8").replace(
            "CREATE TABLE public.attribution_commerce_identities",
            "CREATE TABLE public.attribution_commerce_identities_shadow",
            1,
        ),
        encoding="utf-8",
    )

    proc = _run("--topology-schema-proof-file", str(mutated_schema))
    assert proc.returncode != 0
    assert "topology_schema_missing_token:CREATE TABLE public.attribution_commerce_identities (" in (
        proc.stdout + proc.stderr
    )


def test_b23_p0_semantic_authority_freeze_enforcer_negative_control_typed_boundary_failure(
    tmp_path: Path,
) -> None:
    payload = json.loads(GOVERNANCE_CONTRACT.read_text(encoding="utf-8"))
    payload["typed_boundary_adjudication"]["required_enforcer"] = "scripts/ci/does_not_exist.py"
    mutated = tmp_path / "b23_p0.contract.typed_boundary_mismatch.json"
    mutated.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    proc = _run("--governance-contract-file", str(mutated))
    assert proc.returncode != 0
    assert "typed_boundary_conflict_live_or_unadjudicated" in (proc.stdout + proc.stderr)


def test_b23_p0_semantic_authority_freeze_enforcer_negative_control_threshold_drift(
    tmp_path: Path,
) -> None:
    payload = json.loads(GOVERNANCE_CONTRACT.read_text(encoding="utf-8"))
    payload["performance_authority"]["kernel_1000_orders_max_seconds"] = 9
    mutated = tmp_path / "b23_p0.contract.threshold_drift.json"
    mutated.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    proc = _run("--governance-contract-file", str(mutated))
    assert proc.returncode != 0
    assert "contract_performance_kernel_threshold_mismatch" in (proc.stdout + proc.stderr)
