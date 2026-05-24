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
CARDINALITY_DB_WORK = BAYESIAN_PACKAGE / "cardinality_db_work.py"
PREFLIGHT_LEASE = BAYESIAN_PACKAGE / "preflight_lease.py"
RESOURCE_PROFILE = BAYESIAN_PACKAGE / "resource_profile.py"
FIT_PLANNER = BAYESIAN_PACKAGE / "fit_planner.py"
FIT_CLAIM = BAYESIAN_PACKAGE / "fit_claim.py"
DISPATCH_OUTBOX = BAYESIAN_PACKAGE / "dispatch_outbox.py"
REPOSITORY = BAYESIAN_PACKAGE / "repository.py"
ENUMS = BAYESIAN_PACKAGE / "enums.py"
MODELS = BAYESIAN_PACKAGE / "models.py"
P4_MIGRATION = Path(
    "alembic/versions/007_skeldir_foundation/202605231200_b24_p4_resource_bounds.py"
)
P4_FEATURE_CARDINALITY_MIGRATION = Path(
    "alembic/versions/007_skeldir_foundation/202605241200_b24_p4_feature_cardinality_indexes.py"
)
P4_CARDINALITY_EARLY_STOP_MIGRATION = Path(
    "alembic/versions/007_skeldir_foundation/202605241430_b24_p4_cardinality_early_stop_indexes.py"
)
CANONICAL_SCHEMA = Path("db/schema/canonical_schema.sql")
P4_TESTS = Path("backend/tests/test_b24_p4_resource_bounds.py")

REQUIRED_FILES = {
    RESOURCE_BOUNDS,
    INPUT_PROFILE,
    DESIGN_ENVELOPE,
    GRAPH_ENVELOPE,
    MODEL_FAMILY_CONTRACT,
    ELIGIBILITY,
    CARDINALITY_DB_WORK,
    PREFLIGHT_LEASE,
    RESOURCE_PROFILE,
    P4_MIGRATION,
    P4_FEATURE_CARDINALITY_MIGRATION,
    P4_CARDINALITY_EARLY_STOP_MIGRATION,
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
    for required in (
        "WITH RECURSIVE",
        "CROSS JOIN LATERAL",
        "channel_cap_plus_one",
        "provider_cap_plus_one",
        "campaign_feature_cap_plus_one",
        "candidate.campaign_id > campaign_feature_keys.feature_key",
        "candidate.provider > provider_keys.provider_key",
    ):
        _require(
            required in eligibility_text,
            f"true next-key early-stop cardinality missing: {required}",
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
        "preflight.provider_count",
        "preflight.campaign_or_feature_count",
        "cardinality_profiled_dimensions",
        *EARLY_STOP_INDEXES,
        "true_next_key_early_stop_cap_plus_one_v1",
    ):
        _require(
            required in input_text,
            f"live feature cardinality profile missing: {required}",
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


def validate_schema_surface(root: Path) -> None:
    migration = _read(root, P4_MIGRATION)
    feature_migration = _read(root, P4_FEATURE_CARDINALITY_MIGRATION)
    early_stop_migration = _read(root, P4_CARDINALITY_EARLY_STOP_MIGRATION)
    canonical = _read(root, CANONICAL_SCHEMA)
    enums = _read(root, ENUMS)
    models = _read(root, MODELS)
    for reason in P4_FALLBACK_REASONS:
        for label, text in (
            ("migration", migration),
            ("canonical schema", canonical),
            ("enums", enums),
            ("models", models),
        ):
            _require(reason in text, f"{label} missing P4 fallback reason: {reason}")
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


def validate_scope(root: Path) -> None:
    scan_paths = REQUIRED_FILES | {FIT_PLANNER, FIT_CLAIM, DISPATCH_OUTBOX, REPOSITORY}
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
    validate_schema_surface(root)
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
            "missing_early_stop",
            lambda: validate_resource_profile_module_texts(
                root,
                input_text=_read(root, INPUT_PROFILE),
                eligibility_text=_read(root, ELIGIBILITY).replace(
                    "WITH RECURSIVE", "WITH", 1
                ),
                design_text=_read(root, DESIGN_ENVELOPE),
                graph_text=_read(root, GRAPH_ENVELOPE),
            ),
            "early-stop",
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
            "partial_index_only_proof",
            lambda: validate_resource_profile_module_texts(
                root,
                input_text=_read(root, INPUT_PROFILE).replace(
                    "true_next_key_early_stop_cap_plus_one_v1",
                    "partial_index_only_v1",
                    1,
                ),
                eligibility_text=_read(root, ELIGIBILITY),
                design_text=_read(root, DESIGN_ENVELOPE),
                graph_text=_read(root, GRAPH_ENVELOPE),
            ),
            "true_next_key",
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
                    "provider_count=int(preflight.provider_count)",
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
                    "campaign_or_feature_count=int(preflight.campaign_or_feature_count)",
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
    db_work_text: str | None = None,
) -> None:
    profile_text = _read(root, RESOURCE_PROFILE)
    contract_text = _read(root, MODEL_FAMILY_CONTRACT)
    db_work_text = (
        db_work_text if db_work_text is not None else _read(root, CARDINALITY_DB_WORK)
    )
    combined = "\n".join(
        [
            input_text,
            eligibility_text,
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
    _require(
        "WITH RECURSIVE" in eligibility_text
        and "CROSS JOIN LATERAL" in eligibility_text
        and "campaign_feature_cap_plus_one" in eligibility_text
        and "provider_cap_plus_one" in eligibility_text,
        "true next-key early-stop cardinality missing",
    )
    _require(
        "true_next_key_early_stop_cap_plus_one_v1" in input_text,
        "true_next_key policy proof missing",
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
        "preflight.provider_count",
        "preflight.campaign_or_feature_count",
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
