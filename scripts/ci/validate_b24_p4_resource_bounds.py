#!/usr/bin/env python3
"""Validate B2.4-P4 preflight resource and graph bounds."""

from __future__ import annotations

import argparse
import ast
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BAYESIAN_PACKAGE = Path("backend/app/bayesian")
RESOURCE_BOUNDS = BAYESIAN_PACKAGE / "resource_bounds.py"
INPUT_PROFILE = BAYESIAN_PACKAGE / "input_profile.py"
DESIGN_ENVELOPE = BAYESIAN_PACKAGE / "design_matrix_envelope.py"
GRAPH_ENVELOPE = BAYESIAN_PACKAGE / "graph_complexity_envelope.py"
MODEL_FAMILY_CONTRACT = BAYESIAN_PACKAGE / "model_family_contract.py"
ELIGIBILITY = BAYESIAN_PACKAGE / "eligibility.py"
FEATURE_AUTHORITY = BAYESIAN_PACKAGE / "feature_authority.py"
AUTHORITY_LIVENESS = BAYESIAN_PACKAGE / "authority_liveness.py"
PROFILING_LEASE = BAYESIAN_PACKAGE / "profiling_lease.py"
SNAPSHOT_SUPERSESSION = BAYESIAN_PACKAGE / "snapshot_supersession.py"
CARDINALITY_DB_WORK = BAYESIAN_PACKAGE / "cardinality_db_work.py"
PREFLIGHT_LEASE = BAYESIAN_PACKAGE / "preflight_lease.py"
RESOURCE_PROFILE = BAYESIAN_PACKAGE / "resource_profile.py"
FIT_PLANNER = BAYESIAN_PACKAGE / "fit_planner.py"
FIT_CLAIM = BAYESIAN_PACKAGE / "fit_claim.py"
DISPATCH_OUTBOX = BAYESIAN_PACKAGE / "dispatch_outbox.py"
REPOSITORY = BAYESIAN_PACKAGE / "repository.py"
ENUMS = BAYESIAN_PACKAGE / "enums.py"
MODELS = BAYESIAN_PACKAGE / "models.py"
TASKS_BAYESIAN = Path("backend/app/tasks/bayesian.py")
B24_GATE_WORKFLOW = Path(".github/workflows/b2_4-gate-dry-run.yml")
P4_MIGRATION = Path(
    "alembic/versions/007_skeldir_foundation/202605231200_b24_p4_resource_bounds.py"
)
P4_FEATURE_CARDINALITY_MIGRATION = Path(
    "alembic/versions/007_skeldir_foundation/202605241200_b24_p4_feature_cardinality_indexes.py"
)
P4_CARDINALITY_EARLY_STOP_MIGRATION = Path(
    "alembic/versions/007_skeldir_foundation/202605241430_b24_p4_cardinality_early_stop_indexes.py"
)
P4_FEATURE_AUTHORITY_MIGRATION = Path(
    "alembic/versions/007_skeldir_foundation/202605251200_b24_p4_feature_authority.py"
)
P4_AUTHORITY_LIVENESS_MIGRATION = Path(
    "alembic/versions/007_skeldir_foundation/202605251430_b24_p4_authority_liveness.py"
)
P4_SUPERSESSION_PROFILING_MIGRATION = Path(
    "alembic/versions/007_skeldir_foundation/202605251800_b24_p4_supersession_profiling_lease.py"
)
P4_ATOMIC_DOMINANCE_MIGRATION = Path(
    "alembic/versions/007_skeldir_foundation/202605261200_b24_p4_atomic_dominance_canonical_profiling.py"
)
P4_STRICT_PURGE_MIGRATION = Path(
    "alembic/versions/007_skeldir_foundation/202605271200_b24_p4_strict_profiling_purge.py"
)
CANONICAL_SCHEMA = Path("db/schema/canonical_schema.sql")
CANONICAL_SCHEMA_YAML = Path("db/schema/canonical_schema.yaml")
P4_TESTS = Path("backend/tests/test_b24_p4_resource_bounds.py")
P4_RUNTIME_TESTS = Path("backend/tests/test_b24_p4_postgres_runtime.py")

REQUIRED_FILES = {
    RESOURCE_BOUNDS,
    INPUT_PROFILE,
    DESIGN_ENVELOPE,
    GRAPH_ENVELOPE,
    MODEL_FAMILY_CONTRACT,
    ELIGIBILITY,
    FEATURE_AUTHORITY,
    AUTHORITY_LIVENESS,
    PROFILING_LEASE,
    SNAPSHOT_SUPERSESSION,
    CARDINALITY_DB_WORK,
    PREFLIGHT_LEASE,
    RESOURCE_PROFILE,
    P4_MIGRATION,
    P4_FEATURE_CARDINALITY_MIGRATION,
    P4_CARDINALITY_EARLY_STOP_MIGRATION,
    P4_FEATURE_AUTHORITY_MIGRATION,
    P4_AUTHORITY_LIVENESS_MIGRATION,
    P4_SUPERSESSION_PROFILING_MIGRATION,
    P4_ATOMIC_DOMINANCE_MIGRATION,
    P4_STRICT_PURGE_MIGRATION,
}

REQUIRED_CAP_NAMES = {
    "B24_RESOURCE_POLICY_VERSION",
    "B24_MAX_SOURCE_ROWS",
    "B24_MAX_TOUCHPOINTS",
    "B24_MAX_CONVERSIONS",
    "B24_MAX_CHANNELS",
    "B24_MAX_CURRENCIES",
    "B24_MAX_PROVIDERS",
    "B24_MAX_CAMPAIGNS_OR_FEATURE_KEYS",
    "B24_MAX_WINDOW_DAYS",
    "B24_MAX_DESIGN_MATRIX_CELLS",
    "B24_MAX_TENSOR_ELEMENTS",
    "B24_MAX_TENSOR_RANK",
    "B24_MAX_INPUT_MEMORY_MB",
    "B24_MEMORY_ESTIMATE_SAFETY_FACTOR",
    "B24_MAX_GRAPH_NODES_ESTIMATE",
    "B24_MAX_RANDOM_VARIABLES_ESTIMATE",
    "B24_MAX_HIERARCHICAL_GROUPS",
    "B24_MAX_LEVELS_PER_HIERARCHY",
    "B24_MAX_PLATE_SIZE",
    "B24_MAX_PARAMETER_COUNT",
    "B24_MAX_TRANSFORM_OPS_ESTIMATE",
    "B24_MAX_LOGP_TERMS_ESTIMATE",
    "B24_MAX_COMPILATION_MEMORY_MB_ESTIMATE",
    "B24_GRAPH_COMPLEXITY_SAFETY_FACTOR",
    "B24_DISTINCT_CARDINALITY_POLICY",
    "B24_DB_WORK_BUDGET_POLICY",
    "B24_MAX_CARDINALITY_PLAN_ROWS",
    "B24_MAX_CARDINALITY_PLAN_SHARED_BUFFERS",
    "B24_MAX_CARDINALITY_PLAN_TEMP_BLOCKS",
    "B24_MAX_CARDINALITY_PLAN_SORT_NODES",
    "B24_MAX_CARDINALITY_PLAN_HASHAGGREGATE_NODES",
    "B24_MAX_CARDINALITY_PLAN_SEQ_SCAN_NODES",
    "B24_MAX_CARDINALITY_PLAN_BITMAP_HEAP_SCAN_NODES",
    "B24_MAX_CARDINALITY_PLAN_EXECUTION_MS",
    "B24_MAX_CARDINALITY_PLAN_PLANNING_MS",
    "B24_CARDINALITY_PLAN_WORK_MEM",
}

ZERO_ALLOWED_INT_FIELDS = {
    "max_cardinality_plan_temp_blocks",
    "max_cardinality_plan_sort_nodes",
    "max_cardinality_plan_hashaggregate_nodes",
    "max_cardinality_plan_seq_scan_nodes",
    "max_cardinality_plan_bitmap_heap_scan_nodes",
}

P4_FALLBACK_REASONS = {
    "input_too_large",
    "feature_width_exceeded",
    "source_window_too_large",
    "memory_bound_exceeded",
    "graph_complexity_exceeded",
    "parameter_count_exceeded",
    "hierarchy_width_exceeded",
    "compilation_memory_bound_exceeded",
    "cardinality_authority_missing",
    "cardinality_authority_stale",
    "cardinality_authority_mismatch",
    "cardinality_authority_timeout",
    "cardinality_authority_build_failed",
    "source_profile_unavailable",
}

FORBIDDEN_SCOPE_TOKENS = {
    "pymc",
    "pytensor",
    "arviz",
    "pm.Model",
    "pm.sample",
    "hdi",
    "APIRouter",
    "include_router",
    "app.llm",
    "openai",
    "anthropic",
}

FORBIDDEN_MATERIALIZATION_TOKENS = {
    "fetchall",
    ".all()",
    "list(rows)",
    "pandas",
    "DataFrame",
    "np.empty",
    "np.zeros",
    "sys.getsizeof",
    "pm.Model",
    "pytensor",
}

EARLY_STOP_INDEXES = (
    "idx_b24_p4_attribution_events_channel_early_stop",
    "idx_b24_p4_attribution_events_campaign_early_stop",
    "idx_b24_p4_match_verdicts_provider_early_stop",
    "idx_b24_p4_revenue_events_provider_early_stop",
)


class ValidationError(RuntimeError):
    pass


def _read(root: Path, path: Path) -> str:
    full = root / path
    if not full.exists():
        raise ValidationError(f"missing required file: {path.as_posix()}")
    return full.read_text(encoding="utf-8", errors="replace")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def validate_policy(root: Path, text: str | None = None) -> None:
    text = text if text is not None else _read(root, RESOURCE_BOUNDS)
    tree = ast.parse(text, filename=RESOURCE_BOUNDS.as_posix())
    for cap in REQUIRED_CAP_NAMES:
        _require(cap in text, f"missing policy cap: {cap}")
    assignments: dict[str, object] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    try:
                        assignments[target.id] = ast.literal_eval(node.value)
                    except (ValueError, SyntaxError):
                        continue
    _require("B24_RESOURCE_POLICY_VERSION" in text, "policy version missing")
    _require("B24ResourcePolicy" in text, "single authoritative policy object missing")
    for match in re.finditer(r"(?P<field>\w+):\s*int\s*=\s*0\b", text):
        _require(
            match.group("field") in ZERO_ALLOWED_INT_FIELDS,
            "invalid zero/negative cap: dataclass cap",
        )
    for name, value in assignments.items():
        if name.startswith("B24_MAX_") and isinstance(value, int):
            _require(value > 0, f"invalid zero/negative cap: {name}")


def validate_preflight_order(root: Path, text: str | None = None) -> None:
    text = text if text is not None else _read(root, FIT_PLANNER)
    plan_start = text.find("async def plan_candidate")
    _require(plan_start >= 0, "plan_candidate missing")
    plan_text = text[plan_start:]
    _require(
        "preflight_lease = await acquire_preflight_lease" in plan_text,
        "preflight lease acquisition missing",
    )
    _require("terminalize_preflight_lease" in text, "preflight terminalization missing")
    _require(
        plan_text.find("preflight_lease = await acquire_preflight_lease")
        < plan_text.find("snapshot = await compute_source_snapshot_hash"),
        "P2 source snapshot runs before P4 preflight lease",
    )
    _require(
        plan_text.find("snapshot = await compute_source_snapshot_hash")
        < plan_text.find("evaluate_source_snapshot_resource_bounds")
        < plan_text.find("claim_fit_for_snapshot"),
        "resource profile must run before claim/dispatch",
    )
    _require("if not preflight_lease.acquired" in text, "loser branch missing")
    _require(
        'status="suppressed"' in text, "loser planners must exit/suppress before P2/P4"
    )


def validate_preflight_lease(root: Path, text: str | None = None) -> None:
    text = text if text is not None else _read(root, PREFLIGHT_LEASE)
    for token in (
        "b24_active_execution_leases",
        "source_snapshot_hash",
        "ON CONFLICT DO NOTHING",
        "FOR UPDATE",
        "leased_until",
        "stale_recovered_at",
        "DELETE FROM public.b24_active_execution_leases",
    ):
        _require(token in text, f"preflight lease missing semantic: {token}")
    key_func = text[
        text.find("def preflight_lease_id") : text.find(
            "async def acquire_preflight_lease"
        )
    ]
    _require(
        "source_snapshot_hash" not in key_func,
        "preflight lease key includes source_snapshot_hash",
    )


def validate_resource_profile(root: Path) -> None:
    input_text = _read(root, INPUT_PROFILE)
    eligibility_text = _read(root, ELIGIBILITY)
    authority_text = _read(root, FEATURE_AUTHORITY)
    design_text = _read(root, DESIGN_ENVELOPE)
    graph_text = _read(root, GRAPH_ENVELOPE)
    contract_text = _read(root, MODEL_FAMILY_CONTRACT)
    profile_text = _read(root, RESOURCE_PROFILE)
    db_work_text = _read(root, CARDINALITY_DB_WORK)
    tests_text = _read(root, P4_TESTS)
    combined = "\n".join(
        [
            input_text,
            eligibility_text,
            authority_text,
            design_text,
            graph_text,
            contract_text,
            profile_text,
            db_work_text,
        ]
    )
    for token in FORBIDDEN_MATERIALIZATION_TOKENS:
        _require(
            token.lower() not in combined.lower(),
            f"forbidden allocation/materialization: {token}",
        )
    _require(
        re.search(r"COUNT\s*\(\s*DISTINCT\b", eligibility_text, re.IGNORECASE) is None,
        "unbounded exact COUNT(DISTINCT) forbidden in live P4 eligibility cardinality",
    )
    _require(
        re.search(r"GROUP\s+BY\s+[^\n;/]*\s+LIMIT\b", eligibility_text, re.IGNORECASE)
        is None,
        "unproven GROUP BY LIMIT forbidden in live P4 eligibility cardinality",
    )
    _require(
        re.search(r"\bUNION\b(?!\s+ALL)", eligibility_text, re.IGNORECASE) is None,
        "provider/campaign cardinality must not use UNION deduplication",
    )
    for forbidden in (
        "campaign_feature_keys",
        "provider_keys",
        "candidate.campaign_id >",
        "candidate.provider >",
    ):
        _require(
            forbidden not in eligibility_text,
            f"raw-source cardinality discovery forbidden: {forbidden}",
        )
    for required in (
        "b24_source_window_feature_authority",
        "source_snapshot_hash = :source_snapshot_hash",
        "FeatureAuthorityUnavailable",
        "CARDINALITY_AUTHORITY_MISSING",
        "CARDINALITY_AUTHORITY_STALE",
        "CARDINALITY_AUTHORITY_MISMATCH",
        "authority.freshness_status != FeatureAuthorityStatus.FRESH",
        "authority.policy_version != B24_FEATURE_AUTHORITY_POLICY_VERSION",
        "UPSERT_SOURCE_WINDOW_FEATURE_AUTHORITY_SQL",
    ):
        _require(required in authority_text, f"feature authority missing: {required}")
    for forbidden in (
        "public.attribution_events",
        "public.b23_match_verdicts",
        "public.b23_revenue_events",
        "COUNT(DISTINCT",
        "GROUP BY",
    ):
        _require(
            forbidden.lower() not in authority_text.lower(),
            f"feature authority must not discover raw source cardinality: {forbidden}",
        )
    _require(
        re.search(r"provider_count\s*=\s*0\b", input_text) is None,
        "silent zero provider_count placeholder forbidden",
    )
    _require(
        re.search(r"campaign_or_feature_count\s*=\s*0\b", input_text) is None,
        "silent zero campaign_or_feature_count placeholder forbidden",
    )
    for required in (
        "B24_MODEL_FAMILY_DIMENSION_CONTRACT",
        "PROVIDER_DIMENSION",
        "CAMPAIGN_OR_FEATURE_DIMENSION",
        "assert_profiled_dimensions_cover_model",
        "assert_candidate_dimensions_allowed_for_graph_build",
    ):
        _require(
            required in contract_text,
            f"model-family dimension contract missing: {required}",
        )
    for required in (
        "feature_authority.provider_count",
        "feature_authority.campaign_or_feature_count",
        "feature_authority.channel_count",
        "feature_authority.currency_count",
        "cardinality_profiled_dimensions",
    ):
        _require(
            required in input_text,
            f"feature authority profile missing: {required}",
        )
    for required in (
        "CardinalityPlanEvidence",
        "validate_cardinality_plan_evidence",
        "ANALYZE",
        "BUFFERS",
        "VERBOSE",
        "SETTINGS",
        "work_mem",
        "hashaggregate_nodes",
        "sort_nodes",
        "seq_scan_nodes",
        "bitmap_heap_scan_nodes",
        "temp_blocks_read_or_written",
    ):
        _require(
            required in db_work_text,
            f"cardinality DB-work budget validation missing: {required}",
        )
    _require(
        "estimated_design_matrix_cells" in design_text,
        "design matrix cell estimate missing",
    )
    _require("estimated_tensor_shape" in design_text, "tensor shape estimate missing")
    _require(
        "estimated_input_memory_bytes" in design_text, "input memory estimate missing"
    )
    _require(
        "profile.provider_count + profile.campaign_or_feature_count" in design_text,
        "active provider/campaign dimensions missing from tensor shape",
    )
    _require("estimated_symbolic_nodes" in graph_text, "graph node estimate missing")
    _require(
        "estimated_random_variables" in graph_text, "random variable estimate missing"
    )
    _require("estimated_parameter_count" in graph_text, "parameter estimate missing")
    for required in (
        "profile.provider_count",
        "profile.campaign_or_feature_count",
        "live_feature_width",
        "estimated_compilation_memory_bytes",
    ):
        _require(
            required in graph_text,
            f"graph formula missing active feature coupling: {required}",
        )
    for required_test in (
        "test_b24_p4_provider_count_not_silently_zero",
        "test_b24_p4_campaign_or_feature_count_not_silently_zero",
        "test_b24_p4_live_campaign_count_above_cap_fallback_feature_width_exceeded",
        "test_b24_p4_live_provider_count_above_cap_fallback_feature_width_exceeded",
        "test_b24_p4_low_channel_high_campaign_count_fails_feature_width",
        "test_b24_p4_high_sparse_feature_count_fails_graph_complexity_even_with_low_rows",
        "test_b24_p4_p5_cannot_use_unprofiled_campaign_dimension",
        "test_b24_p4_p5_cannot_use_unprofiled_provider_dimension",
        "test_b24_p4_forced_profile_values_do_not_replace_live_path_proof",
        "test_b24_p4_no_raw_source_recursive_cardinality_in_planner",
        "test_b24_p4_uses_source_window_feature_vocabulary_or_rollup",
        "test_b24_p4_feature_authority_keyed_by_source_snapshot_hash",
        "test_b24_p4_missing_feature_authority_fails_closed",
        "test_b24_p4_stale_feature_authority_fails_closed",
        "test_b24_p4_mismatched_source_snapshot_authority_fails_closed",
        "test_b24_p4_async_campaign_arrival_after_rollup_blocks_approval",
        "test_b24_p4_rollup_lag_creates_non_dispatchable_state",
        "test_b24_p4_campaign_cardinality_does_not_use_plain_count_distinct",
        "test_b24_p4_provider_cardinality_does_not_use_plain_count_distinct",
        "test_b24_p4_campaign_cardinality_uses_rollup_vocabulary_or_true_early_stop",
        "test_b24_p4_provider_cardinality_uses_rollup_vocabulary_or_true_early_stop",
        "test_b24_p4_tiny_fixture_explain_is_not_sufficient",
        "test_b24_p4_exact_distinct_with_partial_index_is_not_sufficient",
        "test_b24_p4_cardinality_plan_rejects_hashaggregate_over_large_slice",
        "test_b24_p4_cardinality_plan_rejects_sort_over_large_slice",
        "test_b24_p4_cardinality_plan_rejects_large_seq_scan_or_bitmap_heap_scan",
        "test_b24_p4_cardinality_plan_rejects_temp_spill",
        "test_b24_p4_cardinality_plan_enforces_buffers_budget",
        "test_b24_p4_eligibility_validator_rejects_count_distinct_regression",
        "test_b24_p4_cardinality_fix_preserves_no_pii_no_identity_no_raw_payload",
    ):
        _require(
            required_test in tests_text,
            f"missing live cardinality regression test: {required_test}",
        )
    for reason in P4_FALLBACK_REASONS:
        _require(
            reason.upper() in profile_text or reason in profile_text,
            f"profile missing fallback reason: {reason}",
        )


def validate_fallback_persistence(root: Path) -> None:
    repo = _read(root, REPOSITORY)
    for marker in (
        "upsert_resource_fallback_from_snapshot",
        "sampling_started_at = NULL",
        "last_fit_at = NULL",
        "runtime_seconds = NULL",
        "artifact_ref = NULL",
        "artifact_hash = NULL",
    ):
        _require(
            marker in repo, f"resource fallback persistence missing marker: {marker}"
        )
    _require(
        "INSERT INTO public.b24_fit_dispatch_outbox" not in repo,
        "resource fallback creates dispatch outbox",
    )
    outbox = _read(root, DISPATCH_OUTBOX)
    _require(
        "status IN ('pending', 'failed_retryable', 'stale_recovered')" in outbox,
        "dispatcher must select only dispatchable statuses",
    )


def validate_authority_liveness(root: Path) -> None:
    validate_authority_liveness_texts(root)


def validate_authority_liveness_texts(
    root: Path,
    *,
    planner_text: str | None = None,
    liveness_text: str | None = None,
    feature_authority_text: str | None = None,
    repository_text: str | None = None,
    tests_text: str | None = None,
    migration_text: str | None = None,
) -> None:
    planner = planner_text if planner_text is not None else _read(root, FIT_PLANNER)
    liveness = (
        liveness_text if liveness_text is not None else _read(root, AUTHORITY_LIVENESS)
    )
    feature_authority = (
        feature_authority_text
        if feature_authority_text is not None
        else _read(root, FEATURE_AUTHORITY)
    )
    repository = (
        repository_text if repository_text is not None else _read(root, REPOSITORY)
    )
    tests = tests_text if tests_text is not None else _read(root, P4_TESTS)
    migration = (
        migration_text
        if migration_text is not None
        else _read(root, P4_AUTHORITY_LIVENESS_MIGRATION)
    )
    authority_branch_start = planner.find("except FeatureAuthorityUnavailable")
    authority_branch_end = planner.find("assert feature_authority is not None")
    _require(authority_branch_start >= 0, "authority unavailable branch missing")
    _require(
        authority_branch_end > authority_branch_start, "authority branch malformed"
    )
    authority_branch = planner[authority_branch_start:authority_branch_end]
    for token in (
        "request_feature_authority_build",
        "mark_authority_waiting_dirty_events",
        "AuthorityBuildStatus.TIMEOUT",
        "AuthorityBuildStatus.BUILD_FAILED",
    ):
        _require(token in authority_branch, f"authority-yield branch missing: {token}")
    first_yield_path = authority_branch[
        : authority_branch.find("AuthorityBuildStatus.TIMEOUT")
    ]
    _require(
        'status="fallback_only"' not in first_yield_path,
        "missing/stale/mismatched authority must not become fallback_only before retry exhaustion",
    )
    _require(
        "upsert_feature_authority_fallback_from_snapshot" not in first_yield_path,
        "authority dependency yield must not persist fallback before retry exhaustion",
    )
    _require(
        "claim_fit_for_snapshot" not in authority_branch,
        "authority-yield path must not claim fit",
    )
    _require(
        "INSERT INTO public.b24_fit_dispatch_outbox" not in liveness + repository,
        "authority-yield path must not create dispatch outbox",
    )
    for token in (
        "b24_feature_authority_build_requests",
        "source_snapshot_hash",
        "retry_count",
        "retry_after_at",
        "max_retries",
        "authority_waiting",
        "authority_retry_ready",
        "cardinality_authority_timeout",
        "cardinality_authority_build_failed",
    ):
        _require(
            token in liveness and token in migration,
            f"authority liveness missing: {token}",
        )
    _require(
        "AUTHORITY_LIVENESS_POLICY_VERSION" in liveness,
        "authority liveness policy version missing",
    )
    _require(
        "AND source_snapshot_hash = :source_snapshot_hash" in liveness,
        "reactivation must be source_snapshot_hash scoped",
    )
    for token in (
        "reactivate_planner_for_feature_authority",
        "feature_authority_fresh",
        "INSERT INTO public.b24_dirty_events",
        "status IN (",
        "authority_completed",
    ):
        _require(token in liveness, f"planner reactivation missing: {token}")
    _require(
        "reactivate_planner_for_feature_authority" in feature_authority,
        "feature authority completion must reactivate planner",
    )
    _require(
        "sweep_authority_waiting_requests" in liveness,
        "stale authority wait must have bounded sweeper hook",
    )
    _require(
        planner.count("status IN ('pending', 'authority_retry_ready')") >= 2,
        "authority retry must re-enter normal dirty-event planner lease path",
    )
    _require(
        "preflight_lease = await acquire_preflight_lease" in planner,
        "authority retry must preserve P3/P4 preflight leasing",
    )
    for required_test in (
        "test_b24_p4_missing_authority_yields_transient_state_not_fallback_only",
        "test_b24_p4_stale_authority_yields_transient_state_not_fallback_only",
        "test_b24_p4_mismatched_authority_yields_transient_state_not_fallback_only",
        "test_b24_p4_authority_yield_creates_no_dispatchable_outbox",
        "test_b24_p4_authority_yield_does_not_claim_fit",
        "test_b24_p4_authority_yield_preserves_retry_intent",
        "test_b24_p4_authority_build_request_is_created_idempotently",
        "test_b24_p4_authority_completion_reactivates_planner",
        "test_b24_p4_stale_wait_retries_without_new_webhook",
        "test_b24_p4_reactivation_is_source_snapshot_scoped",
        "test_b24_p4_reactivation_is_idempotent",
        "test_b24_p4_reactivation_respects_p3_preflight_lock",
        "test_b24_p4_reactivation_respects_active_execution_lock",
        "test_b24_p4_authority_wait_retry_budget_terminalizes_safely",
        "test_b24_p4_authority_timeout_is_distinct_from_fallback_only",
        "test_b24_p4_fresh_authority_after_yield_runs_feature_width_check",
        "test_b24_p4_fresh_authority_after_yield_runs_graph_complexity_check",
        "test_b24_p4_validator_rejects_authority_missing_to_fallback_only",
        "test_b24_p4_validator_rejects_stale_wait_without_reactivation",
        "test_b24_p4_validator_rejects_reactivation_without_source_snapshot_hash",
        "test_b24_p4_validator_rejects_authority_retry_bypassing_p3_locks",
    ):
        _require(
            required_test in tests, f"missing authority liveness test: {required_test}"
        )


def validate_snapshot_supersession(root: Path) -> None:
    validate_snapshot_supersession_texts(root)


def validate_snapshot_supersession_texts(
    root: Path,
    *,
    planner_text: str | None = None,
    liveness_text: str | None = None,
    profiling_text: str | None = None,
    supersession_text: str | None = None,
    fit_claim_text: str | None = None,
    models_text: str | None = None,
    migration_text: str | None = None,
    tests_text: str | None = None,
) -> None:
    planner = planner_text if planner_text is not None else _read(root, FIT_PLANNER)
    liveness = (
        liveness_text if liveness_text is not None else _read(root, AUTHORITY_LIVENESS)
    )
    profiling = (
        profiling_text if profiling_text is not None else _read(root, PROFILING_LEASE)
    )
    supersession = (
        supersession_text
        if supersession_text is not None
        else _read(root, SNAPSHOT_SUPERSESSION)
    )
    fit_claim = fit_claim_text if fit_claim_text is not None else _read(root, FIT_CLAIM)
    models = models_text if models_text is not None else _read(root, MODELS)
    atomic_migration = _read(root, P4_ATOMIC_DOMINANCE_MIGRATION)
    migration = (
        migration_text
        if migration_text is not None
        else _read(root, P4_SUPERSESSION_PROFILING_MIGRATION) + "\n" + atomic_migration
    )
    tests = tests_text if tests_text is not None else _read(root, P4_TESTS)

    for token in (
        "newer_active_execution_owner",
        "newer_fit_claimed_dispatched_or_completed",
        "newer_dispatch_outbox_visible",
        "authority_retry_superseded",
        "fit.status IN ('queued', 'running', 'succeeded')",
        "outbox.status IN ('pending', 'dispatching', 'dispatched')",
    ):
        _require(
            token in planner + supersession, f"snapshot supersession missing: {token}"
        )
    _require(
        "check_snapshot_supersession" in planner,
        "supersession check missing from planner",
    )
    _require(
        "SERIALIZABLE" not in fit_claim,
        "SERIALIZABLE is not allowed as the primary supersession mechanism",
    )
    _require(
        "newer_dominant_snapshot" in fit_claim,
        "ON CONFLICT mutual exclusion cannot replace DB-boundary dominance",
    )
    for token in (
        "locked_execution_lane AS",
        "FOR UPDATE",
        "newer_dominant_snapshot AS",
        "claimable_execution_lane AS",
        "claimed_fit AS",
        "dispatchable_outbox AS",
        "activated_execution_lane AS",
        "source_snapshot_superseded",
        "AND NOT EXISTS (SELECT 1 FROM newer_dominant_snapshot)",
    ):
        _require(token in fit_claim, f"atomic dominance missing: {token}")
    _require(
        fit_claim.find("newer_dominant_snapshot AS")
        < fit_claim.find("claimed_fit AS")
        < fit_claim.find("dispatchable_outbox AS"),
        "ON CONFLICT mutual exclusion cannot replace DB-boundary dominance",
    )
    _require(
        "assert_snapshot_artifact_not_regressing_current_output" in supersession
        and "TrustEnvelope current output" in supersession,
        "artifact non-regression guard missing",
    )
    _require(
        "B24_P5_OUTPUT_NON_REGRESSION_ENTRY_GATE" in supersession,
        "artifact non-regression P5 entry gate missing",
    )
    _require(
        "source_snapshot_hash IS NOT DISTINCT FROM dirty.source_snapshot_hash"
        in planner
        and "source_snapshot_hash IS NOT DISTINCT FROM :source_snapshot_hash"
        in planner,
        "Hash A / Hash B dirty lifecycles must remain source_snapshot_hash scoped",
    )
    _require(
        planner.find("load_source_window_feature_authority")
        < planner.find("snapshot = await compute_source_snapshot_hash"),
        "frozen Hash A retry must validate authority before latest P2 recompute",
    )

    for token in (
        "b24_feature_authority_build_outbox",
        "queued_dispatch AS",
        "FEATURE_AUTHORITY_BUILD_TASK",
        "FEATURE_AUTHORITY_DISPATCH_TASK",
        "POST_COMMIT_DISPATCH_SESSION_KEY",
        "after_commit",
        "publish_feature_authority_dispatch",
        "dispatch_feature_authority_build_by_key",
        "dispatch_due_feature_authority_builds",
        "FOR UPDATE SKIP LOCKED",
        "idx_b24_feature_authority_build_outbox_due",
    ):
        _require(
            token in liveness + models + migration, f"build dispatch missing: {token}"
        )
    _require(
        "ON CONFLICT" in liveness and "dispatch_key" in liveness,
        "build dispatch must be idempotent and transactionally coordinated",
    )
    for token in (
        "NORMAL_DISPATCH_DEADLINE_MS",
        "RECOVERY_ORPHAN_THRESHOLD_MS",
        "MAX_DISPATCH_ATTEMPTS",
        "DISPATCH_RETRY_BACKOFF_MS",
        "created_at <= now() - (:recovery_orphan_threshold_ms * interval '1 millisecond')",
        "status IN ('failed_retryable', 'stale_recovered')",
    ):
        _require(token in liveness, f"recovery-only sweeper boundary missing: {token}")

    for token in (
        "b24_active_execution_leases",
        "canonical P3 active-execution substrate",
        "PROFILING_LEASE_POLICY_VERSION",
        "ProfilingLeaseStatus",
        "terminalize_profiling_lease",
        "PROFILE_REJECTED",
        "PROFILE_PASSED",
        "PROFILE_SUPERSEDED",
        "PROFILE_FAILED",
    ):
        _require(
            token in planner + profiling + models + migration,
            f"profiling lease missing: {token}",
        )
    _require(
        "acquire_profiling_lease" in planner,
        "profiling lease acquisition missing from planner",
    )
    _require("ON CONFLICT" in profiling, "one profiler conflict guard missing")
    conflict_key = profiling[
        profiling.find("ON CONFLICT (") : profiling.find("DO UPDATE SET")
    ]
    _require(
        "source_snapshot_hash" not in conflict_key,
        "one profiler per tenant/model/window requires hash-free conflict key",
    )
    _require(
        "INSERT INTO public.b24_p4_profiling_leases" not in profiling
        and "UPDATE public.b24_p4_profiling_leases" not in profiling,
        "split-brain profiling table cannot be the active owner",
    )
    plan_text = planner[planner.find("async def plan_candidate") :]
    _require(
        plan_text.find("acquire_profiling_lease")
        < plan_text.find("evaluate_source_snapshot_resource_bounds"),
        "profiling lease must be acquired before P4 envelope math",
    )
    _require(
        "if not profiling_lease.acquired" in planner,
        "duplicate profiler losers must exit before profiling",
    )
    _require(
        "terminalize_profiling_lease" in planner,
        "profiling lease cleanup missing",
    )
    for required_test in (
        "test_b24_p4_hash_a_retry_superseded_if_hash_b_already_dispatched",
        "test_b24_p4_hash_a_retry_superseded_if_hash_b_already_completed",
        "test_b24_p4_hash_a_cannot_overwrite_hash_b_artifacts",
        "test_b24_p4_output_non_regression_is_production_wired_or_p5_entry_gated",
        "test_b24_p4_newer_snapshot_dominates_older_authority_retry",
        "test_b24_p4_supersession_claim_is_atomic_under_concurrent_hash_a_hash_b",
        "test_b24_p4_python_precheck_pause_cannot_allow_stale_hash_a_claim",
        "test_b24_p4_db_rejects_hash_a_claim_if_hash_b_wins_between_check_and_commit",
        "test_b24_p4_serializable_only_supersession_solution_rejected",
        "test_b24_p4_on_conflict_active_execution_is_not_chronological_dominance",
        "test_b24_p4_newer_hash_b_wins_even_if_older_hash_a_reaches_insert_first",
        "test_b24_p4_superseded_hash_a_creates_no_dispatchable_outbox",
        "test_b24_p4_hash_a_hash_b_lifecycles_remain_separate",
        "test_b24_p4_missing_authority_creates_build_request_and_dispatch_signal",
        "test_b24_p4_build_request_dispatch_uses_transactional_outbox_or_bounded_sweeper",
        "test_b24_p4_build_request_dispatch_is_idempotent",
        "test_b24_p4_build_request_not_left_unclaimed_without_dispatcher",
        "test_b24_p4_build_dispatch_has_latency_budget",
        "test_b24_p4_only_one_planner_profiles_same_frozen_hash",
        "test_b24_p4_window_level_profiling_ownership_blocks_multi_hash_fanout",
        "test_b24_p4_hash_scoped_profiling_lease_alone_is_rejected",
        "test_b24_p4_duplicate_hashes_do_not_profile_same_window_concurrently",
        "test_b24_p4_profiling_ownership_uses_or_coordinates_with_canonical_active_execution_lane",
        "test_b24_p4_rejects_split_brain_between_profiling_and_active_execution",
        "test_b24_p4_profiling_ownership_acquired_before_authority_validation",
        "test_b24_p4_profiling_ownership_acquired_before_envelope_math",
        "test_b24_p4_duplicate_feature_authority_fresh_events_do_not_duplicate_p4_profiling",
        "test_b24_p4_profiling_lease_required_before_p4_envelope",
        "test_b24_p4_profiling_lease_released_on_authority_failure",
        "test_b24_p4_profiling_lease_released_on_resource_rejection",
        "test_b24_p4_profiling_lease_released_on_supersession",
        "test_b24_p4_profiling_lease_released_on_exception",
        "test_b24_p4_profiling_lease_transitions_safely_to_claim_path",
        "test_b24_p4_validator_rejects_missing_snapshot_supersession",
        "test_b24_p4_validator_rejects_hash_a_overwriting_hash_b",
        "test_b24_p4_validator_rejects_build_request_without_dispatch",
        "test_b24_p4_validator_rejects_p4_profiling_without_lease",
        "test_b24_p4_validator_rejects_duplicate_p4_profiling",
        "test_b24_p4_validator_rejects_python_only_supersession",
        "test_b24_p4_validator_rejects_serializable_only_supersession",
        "test_b24_p4_validator_rejects_on_conflict_as_dominance",
        "test_b24_p4_validator_rejects_unbounded_hash_scoped_profiling_fanout",
        "test_b24_p4_validator_rejects_passive_polling_as_primary_build_trigger",
    ):
        _require(
            required_test in tests,
            f"missing supersession/profiling lease test: {required_test}",
        )


def validate_schema_surface(
    root: Path,
    *,
    canonical_text: str | None = None,
    canonical_yaml_text: str | None = None,
    models_text: str | None = None,
    strict_purge_migration_text: str | None = None,
) -> None:
    feature_migration = _read(root, P4_FEATURE_CARDINALITY_MIGRATION)
    early_stop_migration = _read(root, P4_CARDINALITY_EARLY_STOP_MIGRATION)
    feature_authority_migration = _read(root, P4_FEATURE_AUTHORITY_MIGRATION)
    authority_liveness_migration = _read(root, P4_AUTHORITY_LIVENESS_MIGRATION)
    supersession_migration = _read(root, P4_SUPERSESSION_PROFILING_MIGRATION)
    atomic_migration = _read(root, P4_ATOMIC_DOMINANCE_MIGRATION)
    strict_purge_migration = (
        strict_purge_migration_text
        if strict_purge_migration_text is not None
        else _read(root, P4_STRICT_PURGE_MIGRATION)
    )
    tests = _read(root, P4_TESTS)
    p4_migration_text = "\n".join(
        [
            feature_authority_migration,
            authority_liveness_migration,
            supersession_migration,
            atomic_migration,
            strict_purge_migration,
        ]
    )
    canonical = (
        canonical_text if canonical_text is not None else _read(root, CANONICAL_SCHEMA)
    )
    canonical_yaml = (
        canonical_yaml_text
        if canonical_yaml_text is not None
        else _read(root, CANONICAL_SCHEMA_YAML)
    )
    enums = _read(root, ENUMS)
    models = models_text if models_text is not None else _read(root, MODELS)
    production_text = "\n".join(
        _read(root, path)
        for path in (
            FIT_PLANNER,
            PROFILING_LEASE,
            AUTHORITY_LIVENESS,
            FIT_CLAIM,
            DISPATCH_OUTBOX,
            REPOSITORY,
        )
    )
    authority_dependency_reasons = {
        "cardinality_authority_missing",
        "cardinality_authority_stale",
        "cardinality_authority_mismatch",
    }
    authority_terminal_reasons = {
        "cardinality_authority_timeout",
        "cardinality_authority_build_failed",
    }
    for reason in P4_FALLBACK_REASONS:
        required_surfaces = [
            ("canonical schema", canonical),
            ("enums", enums),
            ("models", models),
        ]
        if reason in authority_dependency_reasons:
            required_surfaces.append(
                ("feature authority migration", feature_authority_migration)
            )
        if reason in authority_dependency_reasons | authority_terminal_reasons:
            required_surfaces.append(
                ("authority liveness migration", authority_liveness_migration)
            )
        for label, text in required_surfaces:
            _require(reason in text, f"{label} missing P4 fallback reason: {reason}")
    for token in (
        "b24_source_window_feature_authority",
        "b24_feature_authority_build_requests",
        "source_snapshot_hash",
        "freshness_status",
        "authority_waiting",
        "authority_retry_ready",
        "cardinality_authority_timeout",
        "idx_b24_feature_authority_tenant_model_window",
        "idx_b24_feature_authority_build_requests_due",
        "tenant_isolation_policy_b24_source_window_feature_authority",
        "tenant_isolation_policy_b24_feature_authority_build_requests",
        "b24_feature_authority_build_outbox",
        "authority_retry_superseded",
        "idx_b24_feature_authority_build_outbox_due",
        "idx_b24_active_execution_canonical_profiling",
        "tenant_isolation_policy_b24_feature_authority_build_outbox",
    ):
        _require(token in canonical, f"feature authority schema missing: {token}")
        if (
            token.startswith("b24_")
            or token.startswith("idx_")
            or token.startswith("tenant_")
        ):
            _require(
                token in p4_migration_text,
                f"migration missing feature authority schema: {token}",
            )
    for prohibited in (
        "b24_p4_profiling_leases",
        "B24P4ProfilingLease",
        "idx_b24_p4_profiling_leases_active",
        "tenant_isolation_policy_b24_p4_profiling_leases",
    ):
        _require(
            prohibited not in canonical,
            f"deprecated profiling table remains in canonical schema: {prohibited}",
        )
        _require(
            prohibited not in canonical_yaml,
            f"deprecated profiling table remains in canonical yaml: {prohibited}",
        )
        _require(
            prohibited not in models,
            f"deprecated profiling table remains in ORM models: {prohibited}",
        )
        _require(
            prohibited not in production_text,
            f"deprecated profiling table remains in production code: {prohibited}",
        )
    _require(
        "to_regclass('public.b24_p4_profiling_leases')" in strict_purge_migration,
        "strict purge migration missing precondition check",
    )
    upgrade_text = strict_purge_migration[
        strict_purge_migration.find("def upgrade") : strict_purge_migration.find(
            "def downgrade"
        )
    ]
    _require(
        "RAISE EXCEPTION 'Expected public.b24_p4_profiling_leases to exist before corrective purge'"
        in upgrade_text,
        "strict purge migration missing loud drift failure",
    )
    _require(
        "DROP TABLE IF EXISTS public.b24_p4_profiling_leases" not in upgrade_text,
        "strict purge migration must not use DROP TABLE IF EXISTS in upgrade",
    )
    _require(
        "DROP TABLE public.b24_p4_profiling_leases" in upgrade_text,
        "strict purge migration missing authoritative DROP TABLE",
    )
    for required_test in (
        "test_b24_p4_deprecated_profiling_table_absent_from_runtime_head_schema",
        "test_b24_p4_deprecated_profiling_table_absent_from_canonical_schema",
        "test_b24_p4_deprecated_profiling_orm_model_removed",
        "test_b24_p4_strict_purge_migration_rejects_unexpected_missing_table",
        "test_b24_p4_validator_rejects_b24_p4_profiling_leases_in_canonical_schema",
        "test_b24_p4_validator_rejects_production_reference_to_deprecated_profiling_table",
        "test_b24_p4_authority_build_dispatch_has_post_commit_causal_trigger",
        "test_b24_p4_build_feature_authority_task_exists_and_is_registered",
        "test_b24_p4_normal_dispatch_happens_with_sweeper_disabled",
        "test_b24_p4_recovery_threshold_constants_are_defined",
        "test_b24_p4_sweeper_ignores_fresh_queued_outbox_rows",
        "test_b24_p4_sweeper_claims_only_orphaned_rows_after_threshold",
        "test_b24_p4_post_commit_dispatch_failure_marks_retryable_row",
    ):
        _require(
            required_test in tests,
            f"missing strict purge/dispatch test: {required_test}",
        )
    for index_name in (
        "idx_b24_p4_attribution_events_campaign_cardinality",
        "idx_b24_p4_match_verdicts_provider_cardinality",
        "idx_b24_p4_revenue_events_provider_cardinality",
    ):
        _require(
            index_name in canonical,
            f"canonical schema missing P4 cardinality index: {index_name}",
        )
        _require(
            index_name in feature_migration,
            f"migration missing P4 cardinality index: {index_name}",
        )
    for index_name in EARLY_STOP_INDEXES:
        _require(
            index_name in canonical,
            f"canonical schema missing P4 early-stop index: {index_name}",
        )
        _require(
            index_name in early_stop_migration,
            f"migration missing P4 early-stop index: {index_name}",
        )


def validate_authority_build_task_and_runtime_ci(root: Path) -> None:
    validate_authority_build_task_and_runtime_ci_texts(root)


def validate_schema_surface_with_texts(
    root: Path,
    *,
    canonical_text: str | None = None,
    canonical_yaml_text: str | None = None,
    models_text: str | None = None,
    strict_purge_migration_text: str | None = None,
) -> None:
    validate_schema_surface(
        root,
        canonical_text=canonical_text,
        canonical_yaml_text=canonical_yaml_text,
        models_text=models_text,
        strict_purge_migration_text=strict_purge_migration_text,
    )


def validate_authority_build_task_and_runtime_ci_texts(
    root: Path,
    *,
    liveness_text: str | None = None,
    tasks_text: str | None = None,
    workflow_text: str | None = None,
    runtime_tests_text: str | None = None,
) -> None:
    liveness = (
        liveness_text if liveness_text is not None else _read(root, AUTHORITY_LIVENESS)
    )
    tasks = tasks_text if tasks_text is not None else _read(root, TASKS_BAYESIAN)
    workflow = (
        workflow_text if workflow_text is not None else _read(root, B24_GATE_WORKFLOW)
    )
    runtime_tests = (
        runtime_tests_text
        if runtime_tests_text is not None
        else _read(root, P4_RUNTIME_TESTS)
    )
    for token in (
        "FEATURE_AUTHORITY_DISPATCH_TASK",
        "POST_COMMIT_DISPATCH_SESSION_KEY",
        '@event.listens_for(AsyncSession.sync_session_class, "after_commit")',
        "dispatch_feature_authority_build_by_key",
        "RECOVERY_ORPHAN_THRESHOLD_MS",
        "MAX_DISPATCH_ATTEMPTS",
        "DISPATCH_RETRY_BACKOFF_MS",
    ):
        _require(token in liveness, f"authority causal dispatch missing: {token}")
    for token in (
        "name=FEATURE_AUTHORITY_DISPATCH_TASK_NAME",
        "name=FEATURE_AUTHORITY_BUILD_TASK_NAME",
        "def dispatch_feature_authority_build",
        "def build_feature_authority",
        "b24_source_window_feature_authority",
        "b24_feature_authority_build_requests",
        "b24_dirty_events",
    ):
        _require(token in tasks, f"registered authority build task missing: {token}")
    _require(
        "Celery Beat" not in liveness + tasks and "cron" not in liveness + tasks,
        "authority build dispatch must not use beat/cron as normal path",
    )
    for token in (
        "B2.4-P4 PostgreSQL Runtime Proof",
        "postgres:15-alpine",
        "alembic upgrade head",
        "test_b24_p4_postgres_runtime.py",
        "SKELDIR_B24_P4_REQUIRE_DB_PROOFS",
    ):
        _require(token in workflow, f"fresh PostgreSQL P4 CI proof missing: {token}")
    for token in (
        "test_b24_p4_runtime_deprecated_profiling_table_absent",
        "test_b24_p4_runtime_sweeper_ignores_fresh_pending_outbox",
        "test_b24_p4_runtime_sweeper_claims_retry_due_rows_only",
        "test_b24_p4_runtime_authority_build_request_outbox_and_causal_dispatch",
        "test_b24_p4_runtime_rls_force_enabled_for_p4_tables",
    ):
        _require(
            token in runtime_tests, f"fresh PostgreSQL runtime proof missing: {token}"
        )


def validate_scope(root: Path) -> None:
    scan_paths = REQUIRED_FILES | {
        FIT_PLANNER,
        FIT_CLAIM,
        DISPATCH_OUTBOX,
        REPOSITORY,
        AUTHORITY_LIVENESS,
        PROFILING_LEASE,
        SNAPSHOT_SUPERSESSION,
    }
    for path in scan_paths:
        text = _read(root, path)
        lowered = text.lower()
        for token in FORBIDDEN_SCOPE_TOKENS:
            _require(
                token.lower() not in lowered,
                f"P4 scope violation in {path.as_posix()}: {token}",
            )
    planner_claim_dispatch = (
        _read(root, FIT_PLANNER) + _read(root, FIT_CLAIM) + _read(root, DISPATCH_OUTBOX)
    )
    for mutation in (
        "UPDATE public.attribution_events",
        "UPDATE public.attribution_allocations",
        "UPDATE public.b23_match_verdicts",
        "UPDATE public.b23_revenue_events",
        "INSERT INTO public.attribution_events",
        "INSERT INTO public.b23_match_verdicts",
    ):
        _require(
            mutation not in planner_claim_dispatch,
            f"P4 mutates deterministic truth: {mutation}",
        )


def validate_all(root: Path) -> None:
    for path in REQUIRED_FILES:
        _read(root, path)
    validate_policy(root)
    validate_preflight_order(root)
    validate_preflight_lease(root)
    validate_resource_profile(root)
    validate_fallback_persistence(root)
    validate_authority_liveness(root)
    validate_snapshot_supersession(root)
    validate_schema_surface(root)
    validate_authority_build_task_and_runtime_ci(root)
    validate_scope(root)


def run_negative_control(root: Path) -> None:
    controls = (
        (
            "missing_preflight_before_source",
            lambda: validate_preflight_order(
                root,
                _read(root, FIT_PLANNER).replace(
                    "preflight_lease = await acquire_preflight_lease",
                    "preflight_lease = await late_preflight_lease",
                    1,
                ),
            ),
            "preflight",
        ),
        (
            "zero_cap",
            lambda: validate_policy(
                root,
                _read(root, RESOURCE_BOUNDS).replace(
                    "max_source_rows: int = 250_000", "max_source_rows: int = 0", 1
                ),
            ),
            "cap",
        ),
        (
            "group_by_limit",
            lambda: validate_resource_profile_texts(
                root,
                _read(root, INPUT_PROFILE)
                + "\nSELECT channel FROM source GROUP BY channel LIMIT 129\n",
            ),
            "GROUP BY LIMIT",
        ),
        (
            "eligibility_count_distinct",
            lambda: validate_resource_profile_module_texts(
                root,
                input_text=_read(root, INPUT_PROFILE),
                eligibility_text=_read(root, ELIGIBILITY)
                + "\nSELECT count(DISTINCT campaign_id) FROM public.attribution_events\n",
                design_text=_read(root, DESIGN_ENVELOPE),
                graph_text=_read(root, GRAPH_ENVELOPE),
            ),
            "COUNT(DISTINCT",
        ),
        (
            "eligibility_group_by_limit",
            lambda: validate_resource_profile_module_texts(
                root,
                input_text=_read(root, INPUT_PROFILE),
                eligibility_text=_read(root, ELIGIBILITY)
                + "\nSELECT campaign_id FROM public.attribution_events GROUP BY campaign_id LIMIT 2049\n",
                design_text=_read(root, DESIGN_ENVELOPE),
                graph_text=_read(root, GRAPH_ENVELOPE),
            ),
            "GROUP BY LIMIT",
        ),
        (
            "provider_union_dedup",
            lambda: validate_resource_profile_module_texts(
                root,
                input_text=_read(root, INPUT_PROFILE),
                eligibility_text=_read(root, ELIGIBILITY).replace(
                    "UNION ALL", "UNION", 1
                ),
                design_text=_read(root, DESIGN_ENVELOPE),
                graph_text=_read(root, GRAPH_ENVELOPE),
            ),
            "UNION deduplication",
        ),
        (
            "raw_source_recursive_cardinality",
            lambda: validate_resource_profile_module_texts(
                root,
                input_text=_read(root, INPUT_PROFILE),
                eligibility_text=_read(root, ELIGIBILITY)
                + "\ncampaign_feature_keys AS (SELECT campaign_id FROM public.attribution_events)\n",
                design_text=_read(root, DESIGN_ENVELOPE),
                graph_text=_read(root, GRAPH_ENVELOPE),
            ),
            "raw-source",
        ),
        (
            "tiny_fixture_only_proof",
            lambda: validate_resource_profile_module_texts(
                root,
                input_text=_read(root, INPUT_PROFILE),
                eligibility_text=_read(root, ELIGIBILITY),
                design_text=_read(root, DESIGN_ENVELOPE),
                graph_text=_read(root, GRAPH_ENVELOPE),
                db_work_text=_read(root, CARDINALITY_DB_WORK).replace(
                    "SETTINGS", "TINY_FIXTURE_ONLY", 1
                ),
            ),
            "SETTINGS",
        ),
        (
            "raw_source_feature_authority",
            lambda: validate_resource_profile_module_texts(
                root,
                input_text=_read(root, INPUT_PROFILE),
                eligibility_text=_read(root, ELIGIBILITY),
                authority_text=_read(root, FEATURE_AUTHORITY)
                + "\nSELECT provider FROM public.b23_revenue_events\n",
                design_text=_read(root, DESIGN_ENVELOPE),
                graph_text=_read(root, GRAPH_ENVELOPE),
            ),
            "raw source",
        ),
        (
            "stale_authority_approval",
            lambda: validate_resource_profile_module_texts(
                root,
                input_text=_read(root, INPUT_PROFILE),
                eligibility_text=_read(root, ELIGIBILITY),
                authority_text=_read(root, FEATURE_AUTHORITY).replace(
                    "authority.freshness_status != FeatureAuthorityStatus.FRESH",
                    "False",
                ),
                design_text=_read(root, DESIGN_ENVELOPE),
                graph_text=_read(root, GRAPH_ENVELOPE),
            ),
            "stale authority",
        ),
        (
            "partial_index_only_proof",
            lambda: validate_resource_profile_module_texts(
                root,
                input_text=_read(root, INPUT_PROFILE).replace(
                    "feature_authority.provider_count",
                    "preflight.provider_count",
                    1,
                ),
                eligibility_text=_read(root, ELIGIBILITY),
                design_text=_read(root, DESIGN_ENVELOPE),
                graph_text=_read(root, GRAPH_ENVELOPE),
            ),
            "feature_authority",
        ),
        (
            "dummy_allocation",
            lambda: validate_resource_profile_texts(
                root,
                _read(root, INPUT_PROFILE) + "\nnp.zeros((10, 10))\n",
            ),
            "allocation",
        ),
        (
            "silent_provider_zero",
            lambda: validate_resource_profile_texts(
                root,
                _read(root, INPUT_PROFILE).replace(
                    "provider_count=int(feature_authority.provider_count)",
                    "provider_count=0",
                    1,
                ),
            ),
            "silent zero",
        ),
        (
            "silent_campaign_zero",
            lambda: validate_resource_profile_texts(
                root,
                _read(root, INPUT_PROFILE).replace(
                    "campaign_or_feature_count=int(feature_authority.campaign_or_feature_count)",
                    "campaign_or_feature_count=0",
                    1,
                ),
            ),
            "silent zero",
        ),
        (
            "missing_graph_feature_coupling",
            lambda: validate_resource_profile_module_texts(
                root,
                input_text=_read(root, INPUT_PROFILE),
                eligibility_text=_read(root, ELIGIBILITY),
                design_text=_read(root, DESIGN_ENVELOPE),
                graph_text=_read(root, GRAPH_ENVELOPE).replace(
                    "live_feature_width",
                    "ignored_feature_width",
                ),
            ),
            "graph formula",
        ),
        (
            "authority_missing_to_fallback_only",
            lambda: validate_authority_liveness_texts(
                root,
                planner_text=_read(root, FIT_PLANNER).replace(
                    "await mark_authority_waiting_dirty_events",
                    'mark_dirty_events_for_candidate  # status="fallback_only"',
                    1,
                ),
            ),
            "authority-yield",
        ),
        (
            "stale_wait_without_reactivation",
            lambda: validate_authority_liveness_texts(
                root,
                liveness_text=_read(root, AUTHORITY_LIVENESS).replace(
                    "def sweep_authority_waiting_requests",
                    "def missing_sweeper",
                    1,
                ),
            ),
            "sweeper",
        ),
        (
            "reactivation_without_source_snapshot_hash",
            lambda: validate_authority_liveness_texts(
                root,
                liveness_text=_read(root, AUTHORITY_LIVENESS).replace(
                    "AND source_snapshot_hash = :source_snapshot_hash",
                    "",
                ),
            ),
            "source_snapshot_hash",
        ),
        (
            "authority_retry_bypassing_p3_locks",
            lambda: validate_authority_liveness_texts(
                root,
                planner_text=_read(root, FIT_PLANNER).replace(
                    "status IN ('pending', 'authority_retry_ready')",
                    "status = 'pending'",
                    1,
                ),
            ),
            "normal dirty-event",
        ),
        (
            "missing_snapshot_supersession",
            lambda: validate_snapshot_supersession_texts(
                root,
                planner_text=_read(root, FIT_PLANNER).replace(
                    "check_snapshot_supersession",
                    "missing_snapshot_supersession",
                ),
            ),
            "supersession",
        ),
        (
            "hash_a_overwrites_hash_b",
            lambda: validate_snapshot_supersession_texts(
                root,
                supersession_text=_read(root, SNAPSHOT_SUPERSESSION).replace(
                    "assert_snapshot_artifact_not_regressing_current_output",
                    "allow_snapshot_artifact_regression",
                ),
            ),
            "artifact",
        ),
        (
            "build_request_without_dispatch",
            lambda: validate_snapshot_supersession_texts(
                root,
                liveness_text=_read(root, AUTHORITY_LIVENESS).replace(
                    "queued_dispatch AS",
                    "missing_dispatch AS",
                    1,
                ),
            ),
            "build dispatch",
        ),
        (
            "p4_profiling_without_lease",
            lambda: validate_snapshot_supersession_texts(
                root,
                planner_text=_read(root, FIT_PLANNER).replace(
                    "acquire_profiling_lease",
                    "missing_profiling_lease",
                ),
            ),
            "profiling lease",
        ),
        (
            "duplicate_p4_profiling",
            lambda: validate_snapshot_supersession_texts(
                root,
                profiling_text=_read(root, PROFILING_LEASE).replace(
                    "source_window_end\n                    )",
                    "source_window_end,\n                        source_snapshot_hash\n                    )",
                    1,
                ),
            ),
            "one profiler",
        ),
        (
            "python_only_supersession",
            lambda: validate_snapshot_supersession_texts(
                root,
                fit_claim_text=_read(root, FIT_CLAIM).replace(
                    "locked_execution_lane",
                    "python_precheck_only",
                ),
            ),
            "atomic dominance",
        ),
        (
            "serializable_only_supersession",
            lambda: validate_snapshot_supersession_texts(
                root,
                fit_claim_text=_read(root, FIT_CLAIM).replace(
                    "locked_execution_lane",
                    "SERIALIZABLE",
                ),
            ),
            "serializable",
        ),
        (
            "on_conflict_as_dominance",
            lambda: validate_snapshot_supersession_texts(
                root,
                fit_claim_text=_read(root, FIT_CLAIM).replace(
                    "newer_dominant_snapshot",
                    "ON CONFLICT",
                ),
            ),
            "on conflict",
        ),
        (
            "unbounded_hash_scoped_profiling_fanout",
            lambda: validate_snapshot_supersession_texts(
                root,
                profiling_text=_read(root, PROFILING_LEASE).replace(
                    "source_window_end\n                    )",
                    "source_window_end,\n                        source_snapshot_hash\n                    )",
                    1,
                ),
            ),
            "one profiler",
        ),
        (
            "passive_polling_as_primary_build_trigger",
            lambda: validate_snapshot_supersession_texts(
                root,
                liveness_text=_read(root, AUTHORITY_LIVENESS).replace(
                    "queued_dispatch AS",
                    "sweeper_only AS",
                    1,
                ),
            ),
            "build dispatch",
        ),
        (
            "deprecated_profiling_table_in_canonical_schema",
            lambda: validate_schema_surface_with_texts(
                root,
                canonical_text=_read(root, CANONICAL_SCHEMA)
                + "\nCREATE TABLE public.b24_p4_profiling_leases (tenant_id uuid);\n",
            ),
            "deprecated profiling",
        ),
        (
            "deprecated_profiling_model",
            lambda: validate_schema_surface_with_texts(
                root,
                models_text=_read(root, MODELS) + "\nclass B24P4ProfilingLease: pass\n",
            ),
            "deprecated profiling",
        ),
        (
            "strict_purge_if_exists",
            lambda: validate_schema_surface_with_texts(
                root,
                strict_purge_migration_text=_read(
                    root, P4_STRICT_PURGE_MIGRATION
                ).replace(
                    "DROP TABLE public.b24_p4_profiling_leases",
                    "DROP TABLE IF EXISTS public.b24_p4_profiling_leases",
                    1,
                ),
            ),
            "IF EXISTS",
        ),
        (
            "missing_post_commit_dispatch",
            lambda: validate_authority_build_task_and_runtime_ci_texts(
                root,
                liveness_text=_read(root, AUTHORITY_LIVENESS).replace(
                    '@event.listens_for(AsyncSession.sync_session_class, "after_commit")',
                    "manual_polling",
                    1,
                ),
            ),
            "causal dispatch",
        ),
        (
            "missing_registered_build_task",
            lambda: validate_authority_build_task_and_runtime_ci_texts(
                root,
                tasks_text=_read(root, TASKS_BAYESIAN).replace(
                    "def build_feature_authority",
                    "def missing_build_feature_authority",
                    1,
                ),
            ),
            "build task",
        ),
        (
            "fresh_pending_sweeper",
            lambda: validate_snapshot_supersession_texts(
                root,
                liveness_text=_read(root, AUTHORITY_LIVENESS).replace(
                    "OR created_at <= now() - (:recovery_orphan_threshold_ms * interval '1 millisecond')",
                    "OR true",
                    1,
                ),
            ),
            "recovery-only",
        ),
        (
            "forbidden_import",
            lambda: validate_scope_text(
                root, _read(root, RESOURCE_PROFILE) + "\nimport pymc\n"
            ),
            "scope",
        ),
    )
    for name, runner, expected in controls:
        try:
            runner()
        except ValidationError as exc:
            _require(
                expected.lower() in str(exc).lower(),
                f"{name} failed for wrong reason: {exc}",
            )
        else:
            raise ValidationError(f"negative control did not fail: {name}")


def validate_resource_profile_texts(root: Path, input_text: str) -> None:
    eligibility_text = _read(root, ELIGIBILITY)
    design_text = _read(root, DESIGN_ENVELOPE)
    graph_text = _read(root, GRAPH_ENVELOPE)
    validate_resource_profile_module_texts(
        root,
        input_text=input_text,
        eligibility_text=eligibility_text,
        design_text=design_text,
        graph_text=graph_text,
    )


def validate_resource_profile_module_texts(
    root: Path,
    *,
    input_text: str,
    eligibility_text: str,
    design_text: str,
    graph_text: str,
    authority_text: str | None = None,
    db_work_text: str | None = None,
) -> None:
    profile_text = _read(root, RESOURCE_PROFILE)
    contract_text = _read(root, MODEL_FAMILY_CONTRACT)
    authority_text = (
        authority_text if authority_text is not None else _read(root, FEATURE_AUTHORITY)
    )
    db_work_text = (
        db_work_text if db_work_text is not None else _read(root, CARDINALITY_DB_WORK)
    )
    combined = "\n".join(
        [
            input_text,
            eligibility_text,
            authority_text,
            design_text,
            graph_text,
            contract_text,
            profile_text,
            db_work_text,
        ]
    )
    for token in FORBIDDEN_MATERIALIZATION_TOKENS:
        _require(
            token.lower() not in combined.lower(),
            f"forbidden allocation/materialization: {token}",
        )
    _require(
        re.search(r"GROUP\s+BY\s+[^\n;/]*\s+LIMIT\b", input_text, re.IGNORECASE)
        is None,
        "unproven GROUP BY LIMIT forbidden",
    )
    _require(
        re.search(r"COUNT\s*\(\s*DISTINCT\b", eligibility_text, re.IGNORECASE) is None,
        "unbounded exact COUNT(DISTINCT) forbidden in live P4 eligibility cardinality",
    )
    _require(
        re.search(r"GROUP\s+BY\s+[^\n;/]*\s+LIMIT\b", eligibility_text, re.IGNORECASE)
        is None,
        "unproven GROUP BY LIMIT forbidden in live P4 eligibility cardinality",
    )
    _require(
        re.search(r"\bUNION\b(?!\s+ALL)", eligibility_text, re.IGNORECASE) is None,
        "provider/campaign cardinality must not use UNION deduplication",
    )
    for forbidden in (
        "campaign_feature_keys",
        "provider_keys",
        "candidate.campaign_id >",
        "candidate.provider >",
    ):
        _require(
            forbidden not in eligibility_text,
            f"raw-source cardinality discovery forbidden: {forbidden}",
        )
    _require(
        "b24_source_window_feature_authority" in authority_text
        and "source_snapshot_hash = :source_snapshot_hash" in authority_text,
        "source-window feature authority missing",
    )
    _require(
        "authority.freshness_status != FeatureAuthorityStatus.FRESH" in authority_text,
        "stale authority fail-closed check missing",
    )
    for forbidden in (
        "public.attribution_events",
        "public.b23_match_verdicts",
        "public.b23_revenue_events",
        "COUNT(DISTINCT",
        "GROUP BY",
    ):
        _require(
            forbidden.lower() not in authority_text.lower(),
            f"feature authority must not discover raw source cardinality: {forbidden}",
        )
    for required in ("ANALYZE", "BUFFERS", "VERBOSE", "SETTINGS", "work_mem"):
        _require(
            required in db_work_text,
            f"cardinality DB-work proof validation missing: {required}",
        )
    _require(
        re.search(r"provider_count\s*=\s*0\b", input_text) is None,
        "silent zero provider_count placeholder forbidden",
    )
    _require(
        re.search(r"campaign_or_feature_count\s*=\s*0\b", input_text) is None,
        "silent zero campaign_or_feature_count placeholder forbidden",
    )
    for required in (
        "feature_authority.provider_count",
        "feature_authority.campaign_or_feature_count",
        "cardinality_profiled_dimensions",
    ):
        _require(
            required in input_text,
            f"live feature cardinality profile missing: {required}",
        )
    _require(
        "profile.provider_count + profile.campaign_or_feature_count" in design_text,
        "active provider/campaign dimensions missing from tensor shape",
    )
    for required in (
        "profile.provider_count",
        "profile.campaign_or_feature_count",
        "live_feature_width",
    ):
        _require(
            required in graph_text,
            f"graph formula missing active feature coupling: {required}",
        )


def validate_scope_text(root: Path, injected_text: str) -> None:
    for token in FORBIDDEN_SCOPE_TOKENS:
        _require(
            token.lower() not in injected_text.lower(), f"P4 scope violation: {token}"
        )
    validate_scope(root)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--negative-control", action="store_true")
    args = parser.parse_args()
    try:
        validate_all(ROOT)
        if args.negative_control:
            run_negative_control(ROOT)
    except ValidationError as exc:
        print(f"B24_P4_RESOURCE_BOUNDS_VALIDATION_FAIL: {exc}")
        return 1
    print("B24_P4_RESOURCE_BOUNDS_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
