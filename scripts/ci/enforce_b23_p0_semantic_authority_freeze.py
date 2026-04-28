#!/usr/bin/env python3
"""B2.3-P0 semantic authority freeze enforcer."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
GOVERNANCE_CONTRACT = (
    "contracts-internal/governance/b23_p0_semantic_authority_freeze.main.json"
)
SEMANTIC_AUTHORITY_FILE = "backend/app/revenue_verification/semantic_authority.py"
EVENT_SERVICE_FILE = "backend/app/ingestion/event_service.py"
RUNTIME_PROOF_FILE = "backend/tests/test_b23_p0_semantic_authority.py"
ENFORCER_PROOF_FILE = "backend/tests/test_b23_p0_semantic_authority_freeze_enforcer.py"
CI_WORKFLOW_FILE = ".github/workflows/ci.yml"
DEPLOY_WORKFLOW_FILE = ".github/workflows/schema-deploy-production.yml"
TOPOLOGY_MODEL_FILE = "backend/app/models/attribution_commerce_identity.py"
TOPOLOGY_PERSISTENCE_FILE = "backend/app/privacy/durable_commerce_identity.py"
TOPOLOGY_SCHEMA_PROOF_FILE = (
    "alembic/versions/007_skeldir_foundation/202604231130_b23_p0_durable_commerce_identity_substrate.py"
)
TOPOLOGY_LIFECYCLE_SCHEMA_PROOF_FILE = (
    "alembic/versions/007_skeldir_foundation/202604241815_b23_p0_activity_independent_identity_lifecycle.py"
)


def _resolve(repo_root: Path, raw: str) -> Path:
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate
    return (repo_root / candidate).resolve()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(_read_text(path))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON payload must be an object: {path}")
    return payload


def _load_module_from_file(path: Path, module_name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module from {path}")
    sys.modules.pop(module_name, None)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _run_python_script(repo_root: Path, script_path: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, script_path],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )


def _git_ref_exists(repo_root: Path, ref: str) -> bool:
    proc = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", ref],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    return proc.returncode == 0


def _git_try_fetch_main(repo_root: Path) -> None:
    subprocess.run(
        ["git", "fetch", "--quiet", "origin", "main", "--depth=1"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )


def _git_try_fetch_ref(repo_root: Path, ref: str) -> None:
    subprocess.run(
        ["git", "fetch", "--quiet", "origin", ref, "--depth=1"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )


def _git_is_shallow_repository(repo_root: Path) -> bool:
    proc = subprocess.run(
        ["git", "rev-parse", "--is-shallow-repository"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def _git_try_unshallow(repo_root: Path) -> None:
    proc = subprocess.run(
        ["git", "fetch", "--quiet", "--unshallow", "origin"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode == 0:
        return
    subprocess.run(
        ["git", "fetch", "--quiet", "--deepen=500", "origin", "main"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )


def _git_is_ancestor(repo_root: Path, ancestor: str, descendant: str = "HEAD") -> bool:
    proc = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    return proc.returncode == 0


def _read_pull_request_base_sha() -> str | None:
    event_path = os.getenv("GITHUB_EVENT_PATH")
    if not event_path:
        return None
    try:
        payload = json.loads(Path(event_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    pull_request = payload.get("pull_request")
    if not isinstance(pull_request, dict):
        return None
    base = pull_request.get("base")
    if not isinstance(base, dict):
        return None
    sha = base.get("sha")
    if isinstance(sha, str) and sha.strip():
        return sha.strip()
    return None


def _main_ref_ancestor_check(repo_root: Path, refs_to_try: tuple[str, ...]) -> tuple[bool, bool]:
    seen_ref = False
    for ref in refs_to_try:
        if not _git_ref_exists(repo_root, ref):
            continue
        seen_ref = True
        if _git_is_ancestor(repo_root, ref):
            return True, True
    return False, seen_ref


def _validate_baseline_ancestry(repo_root: Path, violations: list[str]) -> None:
    pr_base_sha = _read_pull_request_base_sha()
    if pr_base_sha:
        if not _git_ref_exists(repo_root, pr_base_sha):
            _git_try_fetch_ref(repo_root, pr_base_sha)
        if _git_is_ancestor(repo_root, pr_base_sha):
            return
        if _git_is_shallow_repository(repo_root):
            _git_try_unshallow(repo_root)
            if not _git_ref_exists(repo_root, pr_base_sha):
                _git_try_fetch_ref(repo_root, pr_base_sha)
            if _git_is_ancestor(repo_root, pr_base_sha):
                return
        violations.append("baseline_authority_main_ancestor_check_failed")
        return

    refs_to_try = ("origin/main", "main")
    if not any(_git_ref_exists(repo_root, ref) for ref in refs_to_try):
        _git_try_fetch_main(repo_root)

    matched, seen_ref = _main_ref_ancestor_check(repo_root, refs_to_try)
    if matched:
        return

    if seen_ref and _git_is_shallow_repository(repo_root):
        _git_try_unshallow(repo_root)
        if not any(_git_ref_exists(repo_root, ref) for ref in refs_to_try):
            _git_try_fetch_main(repo_root)
        matched, seen_ref = _main_ref_ancestor_check(repo_root, refs_to_try)
        if matched:
            return

    if seen_ref:
        violations.append("baseline_authority_main_ancestor_check_failed")
    else:
        violations.append("baseline_authority_main_ref_unavailable")


def _validate_contract(
    *,
    contract: dict[str, Any],
    semantic_module: ModuleType,
    violations: list[str],
) -> None:
    if contract.get("contract_id") != "b23.p0.semantic_authority_freeze.main":
        violations.append("contract_id_mismatch")
    if contract.get("branch") != "main":
        violations.append("contract_branch_mismatch")
    if contract.get("phase") != "B2.3-P0":
        violations.append("contract_phase_mismatch")

    baseline_authority = contract.get("baseline_authority")
    if not isinstance(baseline_authority, dict):
        violations.append("contract_baseline_authority_invalid")
    else:
        if baseline_authority.get("authoritative_branch") != "main":
            violations.append("contract_authoritative_branch_mismatch")
        if baseline_authority.get("require_main_ancestor_for_semantic_work") is not True:
            violations.append("contract_main_ancestor_requirement_missing")

    shared_identity = contract.get("shared_identity_canonicalization")
    if not isinstance(shared_identity, dict):
        violations.append("contract_shared_identity_invalid")
    else:
        precedence = tuple(shared_identity.get("precedence_order", []))
        if precedence != tuple(semantic_module.B23_PRECEDENCE_ORDER):
            violations.append("contract_precedence_order_mismatch")
        if (
            shared_identity.get("canonicalization_failure_state")
            != semantic_module.CanonicalizationStatus.CANONICALIZATION_FAILED.value
        ):
            violations.append("contract_canonicalization_failure_state_mismatch")

    delayed_arrival = contract.get("privacy_safe_delayed_arrival")
    if not isinstance(delayed_arrival, dict):
        violations.append("contract_privacy_safe_delayed_arrival_invalid")
    else:
        forbidden = set(delayed_arrival.get("forbidden_mechanisms", []))
        if forbidden != set(semantic_module.FORBIDDEN_DELAYED_ARRIVAL_STRATEGIES):
            violations.append("contract_forbidden_delayed_arrival_mechanisms_mismatch")
        if delayed_arrival.get("allowed_topology") != semantic_module.ALLOWED_DELAYED_ARRIVAL_TOPOLOGY:
            violations.append("contract_allowed_topology_mismatch")
        if delayed_arrival.get("delayed_arrival_policy") != semantic_module.DELAYED_ARRIVAL_POLICY:
            violations.append("contract_delayed_arrival_policy_mismatch")

        topology_binding = delayed_arrival.get("topology_schema_binding")
        if not isinstance(topology_binding, dict):
            violations.append("contract_topology_schema_binding_invalid")
        else:
            if topology_binding.get("table") != semantic_module.ALLOWED_DELAYED_ARRIVAL_TOPOLOGY_TABLE:
                violations.append("contract_topology_table_mismatch")
            if set(topology_binding.get("required_columns", [])) != set(
                semantic_module.ALLOWED_DELAYED_ARRIVAL_REQUIRED_COLUMNS
            ):
                violations.append("contract_topology_required_columns_mismatch")
            if set(topology_binding.get("forbidden_columns", [])) != set(
                semantic_module.ALLOWED_DELAYED_ARRIVAL_FORBIDDEN_COLUMNS
            ):
                violations.append("contract_topology_forbidden_columns_mismatch")
            if topology_binding.get("requires_rls") is not True:
                violations.append("contract_topology_requires_rls_mismatch")

        lifecycle_binding = delayed_arrival.get("lifecycle_binding")
        if not isinstance(lifecycle_binding, dict):
            violations.append("contract_topology_lifecycle_binding_invalid")
        else:
            if int(lifecycle_binding.get("retention_days", -1)) != int(
                semantic_module.ALLOWED_DELAYED_ARRIVAL_RETENTION_DAYS
            ):
                violations.append("contract_topology_lifecycle_retention_days_mismatch")
            if lifecycle_binding.get("db_pruning_mode") != (
                semantic_module.ALLOWED_DELAYED_ARRIVAL_LIFECYCLE_MODE
            ):
                violations.append("contract_topology_lifecycle_mode_mismatch")
            if lifecycle_binding.get("pruning_function") != (
                semantic_module.ALLOWED_DELAYED_ARRIVAL_LIFECYCLE_FUNCTION
            ):
                violations.append("contract_topology_lifecycle_pruning_function_mismatch")
            if lifecycle_binding.get("pruning_trigger") != (
                semantic_module.ALLOWED_DELAYED_ARRIVAL_LIFECYCLE_TRIGGER
            ):
                violations.append("contract_topology_lifecycle_pruning_trigger_mismatch")
            if lifecycle_binding.get("pruning_schedule") != (
                semantic_module.ALLOWED_DELAYED_ARRIVAL_LIFECYCLE_SCHEDULE
            ):
                violations.append("contract_topology_lifecycle_pruning_schedule_mismatch")
            if lifecycle_binding.get("pruning_job_name") != (
                semantic_module.ALLOWED_DELAYED_ARRIVAL_LIFECYCLE_JOB_NAME
            ):
                violations.append("contract_topology_lifecycle_pruning_job_name_mismatch")
            if int(lifecycle_binding.get("prune_batch_size", -1)) != int(
                semantic_module.ALLOWED_DELAYED_ARRIVAL_PRUNE_BATCH_SIZE
            ):
                violations.append("contract_topology_lifecycle_prune_batch_size_mismatch")
            if bool(lifecycle_binding.get("activity_independent_enforcement")) is not bool(
                semantic_module.ALLOWED_DELAYED_ARRIVAL_ACTIVITY_INDEPENDENT_ENFORCEMENT
            ):
                violations.append("contract_topology_lifecycle_activity_independence_mismatch")

    financial_truth = contract.get("financial_truth_semantics")
    if not isinstance(financial_truth, dict):
        violations.append("contract_financial_truth_semantics_invalid")
    else:
        if financial_truth.get("amount_basis") != semantic_module.B23_AMOUNT_BASIS:
            violations.append("contract_amount_basis_mismatch")
        if financial_truth.get("currency_stance") != semantic_module.B23_CURRENCY_STANCE:
            violations.append("contract_currency_stance_mismatch")
        if set(financial_truth.get("unsupported_payment_adjustments", [])) != set(
            semantic_module.UNSUPPORTED_PAYMENT_ADJUSTMENTS
        ):
            violations.append("contract_unsupported_payment_adjustments_mismatch")

    boundary = contract.get("b23_b21_boundary")
    if not isinstance(boundary, dict):
        violations.append("contract_b23_b21_boundary_invalid")
    else:
        if boundary.get("b23_scope") != "verified_revenue_truth_at_order_conversion_grain":
            violations.append("contract_boundary_scope_mismatch")
        if boundary.get("b23_must_not_allocate_attribution") is not True:
            violations.append("contract_boundary_allocation_forbidden_mismatch")

    verdict_taxonomy = set(contract.get("verdict_taxonomy", []))
    expected_verdict_taxonomy = {member.value for member in semantic_module.B23Verdict}
    if verdict_taxonomy != expected_verdict_taxonomy:
        violations.append("contract_verdict_taxonomy_mismatch")

    discrepancy_taxonomy = set(contract.get("discrepancy_taxonomy", []))
    expected_discrepancy_taxonomy = {member.value for member in semantic_module.B23DiscrepancyClass}
    if discrepancy_taxonomy != expected_discrepancy_taxonomy:
        violations.append("contract_discrepancy_taxonomy_mismatch")

    if set(contract.get("false_authority_exclusions", [])) != set(
        semantic_module.B23_FORBIDDEN_FALSE_AUTHORITIES
    ):
        violations.append("contract_false_authority_exclusions_mismatch")

    downstream_mapping = contract.get("downstream_mapping")
    if not isinstance(downstream_mapping, dict):
        violations.append("contract_downstream_mapping_invalid")
    else:
        if downstream_mapping.get("strategy") != "typed_deterministic_mapping_only":
            violations.append("contract_downstream_mapping_strategy_mismatch")
        if downstream_mapping.get("ad_hoc_free_form_translation_forbidden") is not True:
            violations.append("contract_downstream_mapping_freeform_forbidden_mismatch")
        if downstream_mapping.get("pre_dispatch_validation_required") is not True:
            violations.append("contract_downstream_mapping_pre_dispatch_validation_missing")

    performance_authority = contract.get("performance_authority")
    if not isinstance(performance_authority, dict):
        violations.append("contract_performance_authority_invalid")
    else:
        runtime_thresholds = dict(semantic_module.get_b23_p0_performance_thresholds())
        if int(performance_authority.get("kernel_1000_orders_max_seconds", -1)) != int(
            runtime_thresholds.get("kernel_1000_orders_max_seconds", -1)
        ):
            violations.append("contract_performance_kernel_threshold_mismatch")
        if int(performance_authority.get("report_1000_orders_max_seconds", -1)) != int(
            runtime_thresholds.get("report_1000_orders_max_seconds", -1)
        ):
            violations.append("contract_performance_report_threshold_mismatch")

    typed_boundary = contract.get("typed_boundary_adjudication")
    if not isinstance(typed_boundary, dict):
        violations.append("contract_typed_boundary_adjudication_invalid")
    else:
        if typed_boundary.get("required_enforcer") != "scripts/ci/enforce_b15_p4_mock_sdk_boundary.py":
            violations.append("contract_typed_boundary_enforcer_mismatch")
        if typed_boundary.get("required_ci_job") != "b15-p4-mock-sdk-typed-boundary":
            violations.append("contract_typed_boundary_ci_job_mismatch")
        if typed_boundary.get("required_route_spec_alignment_enforcer") != (
            "scripts/ci/enforce_b15_p3_runtime_route_binding.py"
        ):
            violations.append("contract_typed_boundary_route_spec_enforcer_mismatch")
        if typed_boundary.get("required_route_spec_alignment_ci_job") != (
            "b15-p3-runtime-route-binding"
        ):
            violations.append("contract_typed_boundary_route_spec_ci_job_mismatch")
        if typed_boundary.get("required_native_source_alignment_enforcer") != (
            "scripts/ci/enforce_b23_p0_typed_boundary_source_alignment.py"
        ):
            violations.append("contract_typed_boundary_native_source_alignment_enforcer_mismatch")
        if typed_boundary.get("expected_status") != "mainline_clean_no_live_conflict":
            violations.append("contract_typed_boundary_status_mismatch")


def _validate_semantic_authority_file(path: Path, violations: list[str]) -> None:
    text = _read_text(path)
    required_tokens = (
        "B23_P0_SEMANTIC_AUTHORITY_VERSION = \"b2.3-p0-v1\"",
        "B23_PRECEDENCE_ORDER = (",
        "FORBIDDEN_DELAYED_ARRIVAL_STRATEGIES = frozenset(",
        "ALLOWED_DELAYED_ARRIVAL_TOPOLOGY = (",
        "ALLOWED_DELAYED_ARRIVAL_TOPOLOGY_TABLE = \"attribution_commerce_identities\"",
        "ALLOWED_DELAYED_ARRIVAL_RETENTION_DAYS = 90",
        "ALLOWED_DELAYED_ARRIVAL_LIFECYCLE_MODE = \"database_scheduled_pruning\"",
        "ALLOWED_DELAYED_ARRIVAL_LIFECYCLE_FUNCTION = \"fn_b23_p0_prune_attribution_commerce_identities\"",
        "ALLOWED_DELAYED_ARRIVAL_LIFECYCLE_TRIGGER = \"trg_b23_p0_prune_attribution_commerce_identities\"",
        "ALLOWED_DELAYED_ARRIVAL_LIFECYCLE_SCHEDULE = \"0 * * * *\"",
        "ALLOWED_DELAYED_ARRIVAL_LIFECYCLE_JOB_NAME = \"b23_p0_prune_attribution_commerce_identities_hourly\"",
        "ALLOWED_DELAYED_ARRIVAL_PRUNE_BATCH_SIZE = 1000",
        "ALLOWED_DELAYED_ARRIVAL_ACTIVITY_INDEPENDENT_ENFORCEMENT = True",
        "ALLOWED_DELAYED_ARRIVAL_REQUIRED_COLUMNS = frozenset(",
        "ALLOWED_DELAYED_ARRIVAL_FORBIDDEN_COLUMNS = frozenset(",
        "DELAYED_ARRIVAL_POLICY = (",
        "B23_AMOUNT_BASIS = \"verified_captured_amount_minor_units\"",
        "B23_CURRENCY_STANCE = \"same_currency_only_cross_currency_unsupported\"",
        "UNSUPPORTED_PAYMENT_ADJUSTMENTS = frozenset(",
        "B23_FORBIDDEN_FALSE_AUTHORITIES = frozenset(",
        "class B23Verdict(str, Enum):",
        "class B23DiscrepancyClass(str, Enum):",
        "class B23DownstreamSemanticProjection(BaseModel):",
        "def canonicalize_verified_commerce_reference(",
        "def canonicalize_attribution_commerce_reference(",
        "def resolve_canonical_match_key(",
        "def validate_delayed_arrival_strategy(",
        "def validate_delayed_arrival_topology(",
        "def validate_delayed_arrival_topology_binding(",
        "def validate_delayed_arrival_lifecycle_binding(",
        "def assert_b23_boundary_not_allocation(",
        "def assert_b23_authority_source(",
        "def map_b23_verdict_for_downstream(",
        "def map_b23_discrepancy_for_downstream(",
        "def build_validated_downstream_projection(",
        "def validate_downstream_projection_payload(",
        "def load_b23_p0_semantic_authority_contract(",
        "B23_P0_PERFORMANCE_AUTHORITY = B23PerformanceAuthority(",
        "def get_b23_p0_performance_thresholds() -> Mapping[str, int]:",
    )
    for token in required_tokens:
        if token not in text:
            violations.append(f"semantic_authority_missing_token:{token}")

    shared_call_token = "return canonicalize_commerce_reference("
    if text.count(shared_call_token) < 2:
        violations.append("semantic_authority_dual_side_shared_canonicalizer_missing")


def _validate_topology_model_file(path: Path, violations: list[str]) -> None:
    text = _read_text(path)
    required_tokens = (
        "class AttributionCommerceIdentity(Base, TenantMixin):",
        "__tablename__ = \"attribution_commerce_identities\"",
        "attribution_event_id",
        "canonical_commerce_reference",
        "uq_attr_commerce_identity_tenant_provider_reference",
        "ck_attr_commerce_identity_observed_time_order",
    )
    for token in required_tokens:
        if token not in text:
            violations.append(f"topology_model_missing_token:{token}")

    forbidden_tokens = ("session_id", "user_id", "email", "ip_address")
    for token in forbidden_tokens:
        if token in text:
            violations.append(f"topology_model_contains_forbidden_identity_column:{token}")


def _validate_topology_persistence_file(path: Path, violations: list[str]) -> None:
    text = _read_text(path)
    required_tokens = (
        "def upsert_durable_commerce_identity_link(",
        "insert(AttributionCommerceIdentity)",
        ".on_conflict_do_update(",
        "canonical_commerce_reference",
        "attribution_event_id",
    )
    for token in required_tokens:
        if token not in text:
            violations.append(f"topology_persistence_missing_token:{token}")


def _validate_topology_schema_file(
    *,
    path: Path,
    contract: dict[str, Any],
    violations: list[str],
) -> None:
    text = _read_text(path)
    delayed_arrival = contract.get("privacy_safe_delayed_arrival", {})
    topology_binding = delayed_arrival.get("topology_schema_binding", {})
    expected_table = str(topology_binding.get("table") or "").strip()
    if not expected_table:
        violations.append("contract_topology_table_missing")
        return

    required_tokens = (
        f"CREATE TABLE public.{expected_table} (",
        "tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE",
        "attribution_event_id uuid NOT NULL REFERENCES public.attribution_events(id) ON DELETE CASCADE",
        "provider varchar(32) NOT NULL",
        "canonical_commerce_reference varchar(255) NOT NULL",
        "ALTER TABLE public.attribution_commerce_identities ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE ONLY public.attribution_commerce_identities FORCE ROW LEVEL SECURITY",
        "CREATE POLICY tenant_isolation_policy_attribution_commerce_identities",
        "uq_attr_commerce_identity_tenant_provider_reference",
    )
    for token in required_tokens:
        if token not in text:
            violations.append(f"topology_schema_missing_token:{token}")

    for column in topology_binding.get("required_columns", []):
        normalized = str(column).strip()
        if normalized and normalized not in text:
            violations.append(f"topology_schema_missing_required_column:{normalized}")

    for column in topology_binding.get("forbidden_columns", []):
        normalized = str(column).strip()
        if not normalized:
            continue
        if normalized in text:
            violations.append(f"topology_schema_contains_forbidden_column:{normalized}")


def _validate_topology_lifecycle_schema_file(path: Path, violations: list[str]) -> None:
    text = _read_text(path)
    required_tokens = (
        "CREATE EXTENSION IF NOT EXISTS pg_cron",
        "current_setting('skeldir.require_pg_cron', true)",
        "skeldir.require_pg_cron",
        "missing_extension:pg_cron",
        "missing_schema:cron",
        "skipping scheduled lifecycle registration",
        "CREATE OR REPLACE FUNCTION public.fn_b23_p0_prune_attribution_commerce_identities_trigger()",
        "SECURITY DEFINER",
        "SET search_path = public",
        "to_regnamespace('cron')",
        "cron.schedule(",
        "b23_p0_prune_attribution_commerce_identities_hourly",
        "0 * * * *",
        "cron.unschedule(existing_job_id)",
        "SELECT public.fn_b23_p0_prune_attribution_commerce_identities(1000);",
        "SELECT public.fn_b23_p0_prune_attribution_commerce_identities(500000)",
    )
    for token in required_tokens:
        if token not in text:
            violations.append(f"topology_lifecycle_schema_missing_token:{token}")


def _validate_runtime_proof_file(path: Path, violations: list[str]) -> None:
    text = _read_text(path)
    required_tests = (
        "test_b23_p0_contract_load_is_authoritative",
        "test_b23_p0_dual_sided_canonicalization_converges_decorated_variants",
        "test_b23_p0_precedence_order_is_deterministic",
        "test_b23_p0_canonicalization_failure_state_is_explicit",
        "test_b23_p0_illegal_delayed_arrival_strategies_fail_closed",
        "test_b23_p0_only_allowed_delayed_arrival_topology_is_accepted",
        "test_b23_p0_delayed_arrival_topology_binding_is_schema_anchored",
        "test_b23_p0_delayed_arrival_lifecycle_binding_is_bounded_and_database_native",
        "test_b23_p0_amount_currency_and_adjustment_stance_is_frozen",
        "test_b23_p0_boundary_law_blocks_allocation_inside_b23",
        "test_b23_p0_false_authority_sources_are_rejected",
        "test_b23_p0_b06_false_authority_surfaces_are_rejected",
        "test_b23_p0_downstream_mapping_is_typed_and_deterministic",
        "test_b23_p0_downstream_mapping_payload_requires_pre_dispatch_validation",
        "test_b23_p0_performance_thresholds_are_contract_aligned",
    )
    for token in required_tests:
        if token not in text:
            violations.append(f"runtime_proof_missing_test:{token}")


def _validate_event_service_file(path: Path, violations: list[str]) -> None:
    text = _read_text(path)
    required_tokens = (
        "canonicalize_attribution_commerce_reference(",
        "resolve_canonical_match_key(",
        "upsert_durable_commerce_identity_link(",
        "Webhook identity canonicalization failed under B2.3-P0 authority policy.",
        "B2.3-P0 delayed-arrival commerce identity substrate is unavailable",
    )
    for token in required_tokens:
        if token not in text:
            violations.append(f"event_service_missing_b23_token:{token}")


def _validate_ci_workflow(
    *,
    workflow_file: Path,
    contract: dict[str, Any],
    violations: list[str],
) -> None:
    text = _read_text(workflow_file)
    required_tokens = (
        "Enforce B2.3-P0 semantic authority freeze",
        "python scripts/ci/enforce_b23_p0_semantic_authority_freeze.py",
        "Run B2.3-P0 semantic authority freeze negative controls",
        "pytest backend/tests/test_b23_p0_semantic_authority_freeze_enforcer.py -q",
        "Run B2.3-P0 semantic authority runtime proofs",
        "pytest backend/tests/test_b23_p0_semantic_authority.py -q",
        "b15-p3-runtime-route-binding:",
        "python scripts/ci/enforce_b15_p3_runtime_route_binding.py",
        "b15-p4-mock-sdk-typed-boundary:",
        "python scripts/ci/enforce_b15_p4_mock_sdk_boundary.py",
    )
    for token in required_tokens:
        if token not in text:
            violations.append(f"workflow_missing_token:{token}")

    required_ci_wiring = contract.get("required_ci_wiring", [])
    if not isinstance(required_ci_wiring, list):
        violations.append("contract_required_ci_wiring_invalid")
        return
    for command in required_ci_wiring:
        normalized = str(command).strip()
        if normalized and normalized not in text:
            violations.append(f"workflow_missing_contract_ci_wiring_token:{normalized}")


def _validate_deploy_workflow(path: Path, violations: list[str]) -> None:
    text = _read_text(path)
    required_tokens = (
        "python scripts/ci/b15_p7_phase_closure_gate.py",
        "--mode technical",
        "Guard Neon control-plane secrets (fail closed when missing)",
        "GH_NEON_API_KEY: ${{ secrets.NEON_API_KEY }} # b23_p0_governed_secret_source",
        "GH_NEON_PROJECT_ID: ${{ vars.NEON_PROJECT_ID }}",
        "GH_PLATFORM_TOKEN_ENCRYPTION_KEY: ${{ secrets.PLATFORM_TOKEN_ENCRYPTION_KEY }} # b23_p0_governed_secret_source",
        "GH_PLATFORM_TOKEN_KEY_ID: ${{ vars.PLATFORM_TOKEN_KEY_ID }}",
        "get_secret_manager_payload()",
        "if [ -n \"${secret_binary}\" ] && [ \"${secret_binary}\" != \"null\" ]; then",
        "decoded_binary=$(echo \"${secret_binary}\" | base64 --decode 2>/dev/null || true)",
        "/skeldir/${SKELDIR_ENV}/secret/database/migration-url",
        "/skeldir/${SKELDIR_ENV}/secret/database/runtime-url",
        "resolve_secret_manager_database_dsn_value()",
        "if ! is_localhost_database_dsn \"${normalized}\"; then",
        "NEON_MIGRATION_DATABASE_URL=$(resolve_secret_manager_database_dsn_value",
        "NEON_DATABASE_URL=$(resolve_secret_manager_database_dsn_value",
        "Missing required Neon control-plane values for governed production deploy.",
        "Missing required platform encryption material for governed production deploy migrations.",
        "Unable to resolve Neon connection URI for governed production deploy.",
        "exit 1",
        "alembic upgrade head",
        "Verify B2.3-P0 delayed-arrival lifecycle substrate in Neon production",
        "missing_table:public.attribution_commerce_identities",
        "missing_index:public.idx_attr_commerce_identity_last_observed",
        "missing_function:public.fn_b23_p0_prune_attribution_commerce_identities",
        "missing_trigger:public.trg_b23_p0_prune_attribution_commerce_identities",
        "missing_extension:pg_cron",
        "missing_cron_job:b23_p0_prune_attribution_commerce_identities_hourly",
    )
    for token in required_tokens:
        if token not in text:
            violations.append(f"deploy_workflow_missing_token:{token}")


def _validate_typed_boundary_adjudication(
    *,
    repo_root: Path,
    contract: dict[str, Any],
    violations: list[str],
) -> None:
    typed_boundary = contract.get("typed_boundary_adjudication")
    if not isinstance(typed_boundary, dict):
        violations.append("typed_boundary_adjudication_missing")
        return

    enforcer = str(typed_boundary.get("required_enforcer") or "").strip()
    if not enforcer:
        violations.append("typed_boundary_required_enforcer_missing")
        return

    route_spec_enforcer = str(
        typed_boundary.get("required_route_spec_alignment_enforcer") or ""
    ).strip()
    if not route_spec_enforcer:
        violations.append("typed_boundary_required_route_spec_enforcer_missing")
        return
    native_source_alignment_enforcer = str(
        typed_boundary.get("required_native_source_alignment_enforcer") or ""
    ).strip()
    if not native_source_alignment_enforcer:
        violations.append("typed_boundary_required_native_source_alignment_enforcer_missing")
        return

    proc = _run_python_script(repo_root, native_source_alignment_enforcer)
    if proc.returncode != 0:
        violations.append("typed_boundary_native_source_alignment_conflict_live_or_unadjudicated")
    proc = _run_python_script(repo_root, route_spec_enforcer)
    if proc.returncode != 0:
        violations.append("typed_boundary_source_alignment_conflict_live_or_unadjudicated")
    proc = _run_python_script(repo_root, enforcer)
    if proc.returncode != 0:
        violations.append("typed_boundary_conflict_live_or_unadjudicated")


def _validate_enforcer_proof_file(path: Path, violations: list[str]) -> None:
    text = _read_text(path)
    required_tokens = (
        "test_b23_p0_semantic_authority_freeze_enforcer_passes_repo_state",
        "test_b23_p0_semantic_authority_freeze_enforcer_negative_control_forced_regression",
        "test_b23_p0_semantic_authority_freeze_enforcer_negative_control_deploy_runtime_proof_missing",
        "test_b23_p0_semantic_authority_freeze_enforcer_negative_control_topology_contract_mismatch",
        "test_b23_p0_semantic_authority_freeze_enforcer_negative_control_topology_schema_absent",
        "test_b23_p0_semantic_authority_freeze_enforcer_negative_control_lifecycle_schema_absent",
        "test_b23_p0_semantic_authority_freeze_enforcer_negative_control_typed_boundary_failure",
        "test_b23_p0_semantic_authority_freeze_enforcer_negative_control_typed_boundary_route_spec_alignment_failure",
        "test_b23_p0_semantic_authority_freeze_enforcer_negative_control_typed_boundary_native_source_alignment_failure",
        "test_b23_p0_semantic_authority_freeze_enforcer_negative_control_threshold_drift",
    )
    for token in required_tokens:
        if token not in text:
            violations.append(f"enforcer_proof_missing_token:{token}")


def run_enforcement(
    *,
    repo_root: Path,
    governance_contract_file: Path,
    semantic_authority_file: Path,
    event_service_file: Path,
    runtime_proof_file: Path,
    enforcer_proof_file: Path,
    ci_workflow_file: Path,
    deploy_workflow_file: Path,
    topology_model_file: Path,
    topology_persistence_file: Path,
    topology_schema_proof_file: Path,
    topology_lifecycle_schema_proof_file: Path,
    skip_baseline_git_check: bool = False,
    skip_typed_boundary_execution: bool = False,
) -> tuple[int, list[str]]:
    violations: list[str] = []
    required_files = (
        governance_contract_file,
        semantic_authority_file,
        event_service_file,
        runtime_proof_file,
        enforcer_proof_file,
        ci_workflow_file,
        deploy_workflow_file,
        topology_model_file,
        topology_persistence_file,
        topology_schema_proof_file,
        topology_lifecycle_schema_proof_file,
    )
    for path in required_files:
        if not path.exists():
            violations.append(f"missing_required_file:{path}")
    if violations:
        return 1, violations

    contract = _read_json(governance_contract_file)
    semantic_module = _load_module_from_file(semantic_authority_file, "b23_p0_semantic_authority")
    _validate_contract(contract=contract, semantic_module=semantic_module, violations=violations)
    _validate_semantic_authority_file(semantic_authority_file, violations)
    _validate_topology_model_file(topology_model_file, violations)
    _validate_topology_persistence_file(topology_persistence_file, violations)
    _validate_topology_schema_file(
        path=topology_schema_proof_file,
        contract=contract,
        violations=violations,
    )
    _validate_topology_lifecycle_schema_file(topology_lifecycle_schema_proof_file, violations)
    _validate_event_service_file(event_service_file, violations)
    _validate_runtime_proof_file(runtime_proof_file, violations)
    _validate_enforcer_proof_file(enforcer_proof_file, violations)
    _validate_ci_workflow(
        workflow_file=ci_workflow_file,
        contract=contract,
        violations=violations,
    )
    _validate_deploy_workflow(deploy_workflow_file, violations)
    if not skip_typed_boundary_execution:
        _validate_typed_boundary_adjudication(
            repo_root=repo_root,
            contract=contract,
            violations=violations,
        )
    if not skip_baseline_git_check:
        _validate_baseline_ancestry(repo_root, violations)

    return (1 if violations else 0), violations


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Enforce B2.3-P0 baseline convergence and semantic authority freeze."
    )
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--governance-contract-file", default=GOVERNANCE_CONTRACT)
    parser.add_argument("--semantic-authority-file", default=SEMANTIC_AUTHORITY_FILE)
    parser.add_argument("--event-service-file", default=EVENT_SERVICE_FILE)
    parser.add_argument("--runtime-proof-file", default=RUNTIME_PROOF_FILE)
    parser.add_argument("--enforcer-proof-file", default=ENFORCER_PROOF_FILE)
    parser.add_argument("--ci-workflow-file", default=CI_WORKFLOW_FILE)
    parser.add_argument("--deploy-workflow-file", default=DEPLOY_WORKFLOW_FILE)
    parser.add_argument("--topology-model-file", default=TOPOLOGY_MODEL_FILE)
    parser.add_argument("--topology-persistence-file", default=TOPOLOGY_PERSISTENCE_FILE)
    parser.add_argument("--topology-schema-proof-file", default=TOPOLOGY_SCHEMA_PROOF_FILE)
    parser.add_argument(
        "--topology-lifecycle-schema-proof-file",
        default=TOPOLOGY_LIFECYCLE_SCHEMA_PROOF_FILE,
    )
    parser.add_argument("--skip-baseline-git-check", action="store_true")
    parser.add_argument("--skip-typed-boundary-execution", action="store_true")
    parser.add_argument("--simulate-regression", action="store_true")
    parser.add_argument("--simulate-baseline-drift", action="store_true")
    args = parser.parse_args(argv[1:])

    if args.simulate_regression:
        sys.stdout.write(
            "b23_p0_semantic_authority_freeze_enforcer\n"
            "result=FAIL\n"
            "synthetic_regression=forced_failure_path\n"
        )
        return 1

    if args.simulate_baseline_drift:
        sys.stdout.write(
            "b23_p0_semantic_authority_freeze_enforcer\n"
            "result=FAIL\n"
            "baseline_authority_main_ancestor_check_failed\n"
        )
        return 1

    repo_root = _resolve(REPO_ROOT, args.repo_root)
    status, violations = run_enforcement(
        repo_root=repo_root,
        governance_contract_file=_resolve(repo_root, args.governance_contract_file),
        semantic_authority_file=_resolve(repo_root, args.semantic_authority_file),
        event_service_file=_resolve(repo_root, args.event_service_file),
        runtime_proof_file=_resolve(repo_root, args.runtime_proof_file),
        enforcer_proof_file=_resolve(repo_root, args.enforcer_proof_file),
        ci_workflow_file=_resolve(repo_root, args.ci_workflow_file),
        deploy_workflow_file=_resolve(repo_root, args.deploy_workflow_file),
        topology_model_file=_resolve(repo_root, args.topology_model_file),
        topology_persistence_file=_resolve(repo_root, args.topology_persistence_file),
        topology_schema_proof_file=_resolve(repo_root, args.topology_schema_proof_file),
        topology_lifecycle_schema_proof_file=_resolve(
            repo_root, args.topology_lifecycle_schema_proof_file
        ),
        skip_baseline_git_check=bool(args.skip_baseline_git_check),
        skip_typed_boundary_execution=bool(args.skip_typed_boundary_execution),
    )

    lines = ["b23_p0_semantic_authority_freeze_enforcer"]
    if status != 0:
        lines.append("result=FAIL")
        lines.extend(violations)
    else:
        lines.append("result=PASS")
        lines.append("enforcement=baseline_convergence_and_semantic_authority_fail_closed")
    sys.stdout.write("\n".join(lines) + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
