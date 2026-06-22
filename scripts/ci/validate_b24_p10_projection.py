#!/usr/bin/env python3
"""Validate B2.4-P10 read-only confidence projection boundaries."""

from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BAYESIAN_PACKAGE = Path("backend/app/bayesian")
API_PROJECTION = BAYESIAN_PACKAGE / "api_projection.py"
CONFIDENCE_METADATA = BAYESIAN_PACKAGE / "confidence_metadata.py"
CONFIDENCE_POLICY = BAYESIAN_PACKAGE / "confidence_policy.py"
P10_TESTS = Path("backend/tests/test_b24_p10_projection.py")
FRONTEND = Path("frontend")
API_DIR = Path("backend/app/api")
MAIN = Path("backend/app/main.py")
WORKFLOW = Path(".github/workflows/b2_4-gate-dry-run.yml")
MAKEFILE = Path("Makefile")
REGISTRY = Path("docs/ci/enforcer_registry.yaml")
REQUIRED_STATUS_CONTRACT = Path(
    "contracts-internal/governance/b03_phase2_required_status_checks.main.json"
)


class ValidationError(RuntimeError):
    pass


def _read(path: Path) -> str:
    full = ROOT / path
    if not full.exists():
        raise ValidationError(f"missing required file: {path.as_posix()}")
    return full.read_text(encoding="utf-8", errors="replace")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def _frontend_text() -> str:
    parts: list[str] = []
    for path in (ROOT / FRONTEND).rglob("*"):
        if any(part in {"node_modules", "dist", "build", ".next"} for part in path.parts):
            continue
        if path.is_file() and path.suffix in {".ts", ".tsx", ".js", ".jsx"}:
            if path.name.lower() == "nul":
                continue
            parts.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(parts)


def validate_projection_modules(
    api_text: str | None = None,
    metadata_text: str | None = None,
    policy_text: str | None = None,
) -> None:
    api = api_text if api_text is not None else _read(API_PROJECTION)
    metadata = metadata_text if metadata_text is not None else _read(CONFIDENCE_METADATA)
    policy = policy_text if policy_text is not None else _read(CONFIDENCE_POLICY)

    for token in (
        "build_b24_confidence_projection_query",
        "project_b24_confidence",
        "build_projection_models",
        "WITH deterministic_left AS",
        "FROM public.b23_revenue_events revenue",
        "LEFT OUTER JOIN latest_matching_fit",
        "LEFT OUTER JOIN artifact_summary",
        "LEFT OUTER JOIN mismatch_probe",
        "fit.source_snapshot_hash = :source_snapshot_hash",
        "WHERE fit.tenant_id = :tenant_id",
        "AND fit.source_snapshot_hash = :source_snapshot_hash",
        "source_snapshot_mismatch",
    ):
        _require(token in api, f"P10 projection missing: {token}")
    _require(
        "WHERE fit.status" not in api and "WHERE latest_matching_fit" not in api,
        "P10 projection has WHERE-collapse-prone Bayesian filter",
    )
    for forbidden in (
        "dirty_marker",
        "fit_planner",
        "fit_claim",
        "dispatch_outbox",
        "sampler",
        "tasks.bayesian",
        "send_task",
        "apply_async",
        "INSERT INTO",
        "UPDATE public.",
        "DELETE FROM",
        "pymc",
        "pytensor",
        "arviz",
        "app.llm",
        "openai",
        "anthropic",
    ):
        _require(forbidden not in api, f"P10 projection forbidden token: {forbidden}")
    for token in (
        "B24ConfidenceProjection",
        "DeterministicProjectionMetadata",
        "BayesianProjectionMetadata",
        "ConfidenceProjectionMetadata",
        "ProjectionAuditMetadata",
        "confidence_bucket",
        "confidence_bucket_reason",
        "confidence_policy_version",
        "confidence_semantics_version",
        "deterministic_revenue_minor",
        "projection_read_only",
    ):
        _require(token in metadata, f"P10 metadata missing: {token}")
    for token in (
        "CONFIDENCE_POLICY_VERSION",
        "CONFIDENCE_SEMANTICS_VERSION",
        "classify_confidence",
        "ConfidenceBucketReason",
        "NARROW_INTERVAL",
        "MODERATE_INTERVAL",
        "WIDE_INTERVAL",
        "NO_FIT",
        "SOURCE_SNAPSHOT_CHANGED",
        "ARTIFACT_UNAVAILABLE",
        "BAD_RHAT",
        "LOW_ESS",
        "DIVERGENCE",
    ):
        _require(token in policy, f"P10 policy missing: {token}")


def validate_boundary_scans(frontend_text: str | None = None) -> None:
    api_text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in (ROOT / API_DIR).glob("*.py")
    )
    main_text = _read(MAIN)
    frontend = frontend_text if frontend_text is not None else _frontend_text()

    _require("api_projection" not in api_text, "P10 projection exposed through API")
    _require("api_projection" not in main_text, "P10 projection registered in main")
    _require("b24_confidence" not in api_text.lower(), "public B2.4 route detected")
    _require(
        "confidence_bucket" not in frontend
        and "confidenceBucket" not in frontend
        and "confidence_policy_version" not in frontend
        and "confidencePolicyVersion" not in frontend,
        "frontend Bayesian confidence bucket ownership detected",
    )


def validate_tests_and_ci(
    tests_text: str | None = None,
    workflow_text: str | None = None,
    makefile_text: str | None = None,
    registry_text: str | None = None,
    required_status_text: str | None = None,
) -> None:
    tests = tests_text if tests_text is not None else _read(P10_TESTS)
    workflow = workflow_text if workflow_text is not None else _read(WORKFLOW)
    makefile = makefile_text if makefile_text is not None else _read(MAKEFILE)
    registry = registry_text if registry_text is not None else _read(REGISTRY)
    required_status = (
        required_status_text
        if required_status_text is not None
        else _read(REQUIRED_STATUS_CONTRACT)
    )
    for token in (
        "test_b24_p10_sql_roots_on_deterministic_left_and_left_joins_bayesian",
        "test_b24_p10_no_fit_preserves_deterministic_revenue",
        "test_b24_p10_backend_policy_classifies_interval_width",
        "test_b24_p10_unavailable_states_are_reason_coded",
        "test_b24_p10_static_validator_negative_controls",
    ):
        _require(token in tests, f"P10 tests missing: {token}")
    for token in (
        "validate-b24-p10-projection",
        "validate_b24_p10_projection.py --negative-control",
    ):
        _require(token in makefile, f"P10 Makefile target missing: {token}")
        _require(token in registry, f"P10 registry entry missing: {token}")
    for token in (
        "B2.4-P10 Read-Only Projection Proof",
        "pytest backend/tests/test_b24_p10_projection.py",
        "make validate-b24-p10-projection",
    ):
        _require(token in workflow, f"P10 workflow wiring missing: {token}")
    _require(
        "B2.4-P10 Read-Only Projection Proof" in required_status,
        "P10 required status context missing",
    )


def validate_all() -> None:
    validate_projection_modules()
    validate_boundary_scans()
    validate_tests_and_ci()


def run_negative_controls() -> None:
    api = _read(API_PROJECTION)
    metadata = _read(CONFIDENCE_METADATA)
    policy = _read(CONFIDENCE_POLICY)
    tests = _read(P10_TESTS)
    workflow = _read(WORKFLOW)
    makefile = _read(MAKEFILE)
    registry = _read(REGISTRY)
    required_status = _read(REQUIRED_STATUS_CONTRACT)
    controls = (
        (
            "left_join_removed",
            lambda: validate_projection_modules(api_text=api.replace("LEFT OUTER JOIN latest_matching_fit", "INNER JOIN latest_matching_fit")),
            "LEFT OUTER JOIN latest_matching_fit",
        ),
        (
            "where_collapse_added",
            lambda: validate_projection_modules(api_text=api + "\nWHERE fit.status = 'succeeded'\n"),
            "WHERE-collapse",
        ),
        (
            "compute_trigger_added",
            lambda: validate_projection_modules(api_text=api + "\nfrom app.bayesian.fit_planner import plan_fit\n"),
            "fit_planner",
        ),
        (
            "celery_enqueue_added",
            lambda: validate_projection_modules(api_text=api + "\nsession.app.send_task('x')\n"),
            "send_task",
        ),
        (
            "sampler_import_added",
            lambda: validate_projection_modules(api_text=api + "\nfrom app.bayesian import sampler_child\n"),
            "sampler",
        ),
        (
            "llm_import_added",
            lambda: validate_projection_modules(api_text=api + "\nfrom app.llm import provider_boundary\n"),
            "app.llm",
        ),
        (
            "bucket_field_removed",
            lambda: validate_projection_modules(metadata_text=metadata.replace("confidence_bucket_reason", "confidence_reason_removed")),
            "confidence_bucket_reason",
        ),
        (
            "policy_version_removed",
            lambda: validate_projection_modules(policy_text=policy.replace("CONFIDENCE_POLICY_VERSION", "CONFIDENCE_VERSION_REMOVED")),
            "CONFIDENCE_POLICY_VERSION",
        ),
        (
            "frontend_threshold_added",
            lambda: validate_boundary_scans(frontend_text="const confidenceBucket = intervalWidth < 0.1 ? 'high' : 'low';"),
            "frontend",
        ),
        (
            "no_fit_test_removed",
            lambda: validate_tests_and_ci(tests_text=tests.replace("test_b24_p10_no_fit_preserves_deterministic_revenue", "test_removed")),
            "no_fit",
        ),
        (
            "workflow_context_removed",
            lambda: validate_tests_and_ci(workflow_text=workflow.replace("B2.4-P10 Read-Only Projection Proof", "B2.4-P10 Missing Proof")),
            "workflow",
        ),
        (
            "make_target_removed",
            lambda: validate_tests_and_ci(makefile_text=makefile.replace("validate-b24-p10-projection", "validate-b24-p10-removed")),
            "Makefile",
        ),
        (
            "registry_removed",
            lambda: validate_tests_and_ci(registry_text=registry.replace("validate-b24-p10-projection", "validate-b24-p10-removed")),
            "registry",
        ),
        (
            "required_status_removed",
            lambda: validate_tests_and_ci(required_status_text=required_status.replace("B2.4-P10 Read-Only Projection Proof", "B2.4-P10 Missing Proof")),
            "required status",
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--negative-control", action="store_true")
    args = parser.parse_args()
    try:
        validate_all()
        if args.negative_control:
            run_negative_controls()
    except ValidationError as exc:
        print(f"B24_P10_PROJECTION_VALIDATION_FAIL: {exc}")
        return 1
    print("B24_P10_PROJECTION_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
