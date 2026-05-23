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
CANONICAL_SCHEMA = Path("db/schema/canonical_schema.sql")

REQUIRED_FILES = {
    RESOURCE_BOUNDS,
    INPUT_PROFILE,
    DESIGN_ENVELOPE,
    GRAPH_ENVELOPE,
    PREFLIGHT_LEASE,
    RESOURCE_PROFILE,
    P4_MIGRATION,
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
    _require(
        re.search(r":\s*int\s*=\s*0\b", text) is None,
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
    _require("preflight_lease = await acquire_preflight_lease" in plan_text, "preflight lease acquisition missing")
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
    _require('status="suppressed"' in text, "loser planners must exit/suppress before P2/P4")


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
    key_func = text[text.find("def preflight_lease_id") : text.find("async def acquire_preflight_lease")]
    _require("source_snapshot_hash" not in key_func, "preflight lease key includes source_snapshot_hash")


def validate_resource_profile(root: Path) -> None:
    input_text = _read(root, INPUT_PROFILE)
    design_text = _read(root, DESIGN_ENVELOPE)
    graph_text = _read(root, GRAPH_ENVELOPE)
    profile_text = _read(root, RESOURCE_PROFILE)
    combined = "\n".join([input_text, design_text, graph_text, profile_text])
    for token in FORBIDDEN_MATERIALIZATION_TOKENS:
        _require(token.lower() not in combined.lower(), f"forbidden allocation/materialization: {token}")
    _require("GROUP BY" not in input_text or "LIMIT" not in input_text, "unproven GROUP BY LIMIT forbidden")
    _require("COUNT(DISTINCT" not in input_text.upper(), "unbounded exact COUNT(DISTINCT) forbidden in P4 profile")
    _require("estimated_design_matrix_cells" in design_text, "design matrix cell estimate missing")
    _require("estimated_tensor_shape" in design_text, "tensor shape estimate missing")
    _require("estimated_input_memory_bytes" in design_text, "input memory estimate missing")
    _require("estimated_symbolic_nodes" in graph_text, "graph node estimate missing")
    _require("estimated_random_variables" in graph_text, "random variable estimate missing")
    _require("estimated_parameter_count" in graph_text, "parameter estimate missing")
    for reason in P4_FALLBACK_REASONS:
        _require(reason.upper() in profile_text or reason in profile_text, f"profile missing fallback reason: {reason}")


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
        _require(marker in repo, f"resource fallback persistence missing marker: {marker}")
    _require("INSERT INTO public.b24_fit_dispatch_outbox" not in repo, "resource fallback creates dispatch outbox")
    outbox = _read(root, DISPATCH_OUTBOX)
    _require(
        "status IN ('pending', 'failed_retryable', 'stale_recovered')" in outbox,
        "dispatcher must select only dispatchable statuses",
    )


def validate_schema_surface(root: Path) -> None:
    migration = _read(root, P4_MIGRATION)
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


def validate_scope(root: Path) -> None:
    scan_paths = REQUIRED_FILES | {FIT_PLANNER, FIT_CLAIM, DISPATCH_OUTBOX, REPOSITORY}
    for path in scan_paths:
        text = _read(root, path)
        lowered = text.lower()
        for token in FORBIDDEN_SCOPE_TOKENS:
            _require(token.lower() not in lowered, f"P4 scope violation in {path.as_posix()}: {token}")
    planner_claim_dispatch = _read(root, FIT_PLANNER) + _read(root, FIT_CLAIM) + _read(root, DISPATCH_OUTBOX)
    for mutation in (
        "UPDATE public.attribution_events",
        "UPDATE public.attribution_allocations",
        "UPDATE public.b23_match_verdicts",
        "UPDATE public.b23_revenue_events",
        "INSERT INTO public.attribution_events",
        "INSERT INTO public.b23_match_verdicts",
    ):
        _require(mutation not in planner_claim_dispatch, f"P4 mutates deterministic truth: {mutation}")


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
                _read(root, RESOURCE_BOUNDS).replace("max_source_rows: int = 250_000", "max_source_rows: int = 0", 1),
            ),
            "cap",
        ),
        (
            "group_by_limit",
            lambda: validate_resource_profile_texts(
                root,
                _read(root, INPUT_PROFILE) + "\nSELECT channel FROM source GROUP BY channel LIMIT 129\n",
            ),
            "GROUP BY LIMIT",
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
            "forbidden_import",
            lambda: validate_scope_text(root, _read(root, RESOURCE_PROFILE) + "\nimport pymc\n"),
            "scope",
        ),
    )
    for name, runner, expected in controls:
        try:
            runner()
        except ValidationError as exc:
            _require(expected.lower() in str(exc).lower(), f"{name} failed for wrong reason: {exc}")
        else:
            raise ValidationError(f"negative control did not fail: {name}")


def validate_resource_profile_texts(root: Path, input_text: str) -> None:
    design_text = _read(root, DESIGN_ENVELOPE)
    graph_text = _read(root, GRAPH_ENVELOPE)
    profile_text = _read(root, RESOURCE_PROFILE)
    combined = "\n".join([input_text, design_text, graph_text, profile_text])
    for token in FORBIDDEN_MATERIALIZATION_TOKENS:
        _require(token.lower() not in combined.lower(), f"forbidden allocation/materialization: {token}")
    _require(
        re.search(r"GROUP\s+BY[\s\S]{0,120}\bLIMIT\b", input_text, re.IGNORECASE) is None,
        "unproven GROUP BY LIMIT forbidden",
    )


def validate_scope_text(root: Path, injected_text: str) -> None:
    for token in FORBIDDEN_SCOPE_TOKENS:
        _require(token.lower() not in injected_text.lower(), f"P4 scope violation: {token}")
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
