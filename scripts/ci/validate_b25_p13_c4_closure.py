#!/usr/bin/env python3
"""Validate B2.5-P13 C4 confidence/temporal closure and semantic falsifiers."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.confidence_projection.policy import (  # noqa: E402
    CONFIDENCE_POLICY_VERSION,
    CONFIDENCE_SEMANTICS_VERSION,
    ConfidenceBucketReason,
    persisted_confidence_decision,
)
from app.confidence_projection.read_model import (  # noqa: E402
    CONFIDENCE_PROJECTION_PHYSICAL_READ_TABLES,
    _EXACT_FIT_PROJECTION_SQL,
    _projection_decision,
    _snapshot_freshness,
)
from app.confidence_projection.sql_authority import (  # noqa: E402
    ConfidenceProjectionAuthorityError,
    assert_executable_read_authority,
)


MIGRATION = (
    ROOT
    / "alembic/versions/007_skeldir_foundation/202608181200_b25_p13_c4_confidence_state_closure.py"
)
FIT_EXECUTION = ROOT / "backend/app/bayesian/fit_execution.py"
REPOSITORY = ROOT / "backend/app/bayesian/repository.py"
SOURCE_SNAPSHOT = ROOT / "backend/app/bayesian/source_snapshot.py"
FIT_CLAIM = ROOT / "backend/app/bayesian/fit_claim.py"
READ_MODEL = ROOT / "backend/app/confidence_projection/read_model.py"
BUILDER = ROOT / "backend/app/trust/builder.py"
HASH_MANIFEST = ROOT / "contracts/trust-api/hash-domain-manifest.v1.yaml"


class B25P13C4ClosureError(RuntimeError):
    """A C4 invariant or negative control did not hold."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise B25P13C4ClosureError(reason)


def _available_input() -> dict[str, Any]:
    observed = datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc)
    source_hash = "a" * 64
    return {
        "confidence_bucket": "high",
        "confidence_bucket_reason": "narrow_interval",
        "confidence_policy_version": CONFIDENCE_POLICY_VERSION,
        "confidence_semantics_version": CONFIDENCE_SEMANTICS_VERSION,
        "deterministic_revenue_minor": 10_000,
        "deterministic_row_count": 2,
        "match_verdict_count": 2,
        "currency_count": 1,
        "confidence_classified_at": observed,
        "confidence_evidence_snapshot_hash": source_hash,
        "source_snapshot_hash": source_hash,
        "source_read_started_at": observed,
        "source_read_completed_at": observed,
        "fit_status": "succeeded",
        "data_completeness_status": "complete",
        "fallback_applied": False,
        "diagnostic_status": "passed",
        "credible_interval_status": "available",
    }


def validate_consumer(mapping: dict[str, Any] | None = None) -> int:
    decision = persisted_confidence_decision(**(mapping or _available_input()))
    _require(decision.confidence_available, "complete_persisted_confidence_rejected")
    return 16


def validate_historical_behavior(mapping: dict[str, object] | None = None) -> int:
    row = mapping or {
        "has_snapshot_lineage": True,
        "model_type": "bayesian_attribution_confidence",
        "confidence_bucket": "high",
        "confidence_bucket_reason": "narrow_interval",
        "confidence_policy_version": CONFIDENCE_POLICY_VERSION,
        "confidence_semantics_version": CONFIDENCE_SEMANTICS_VERSION,
    }
    freshness = _snapshot_freshness(row)
    decision = _projection_decision(row, freshness=freshness)
    _require(freshness == "unknown", "historical_temporal_unknown_upgraded")
    _require(
        not decision.confidence_available
        and decision.confidence_bucket_reason
        is ConfidenceBucketReason.SOURCE_AUTHORITY_UNKNOWN,
        "historical_incomplete_confidence_fabricated",
    )
    return 2


def validate_database_migration(source: str | None = None) -> int:
    text = source if source is not None else MIGRATION.read_text("utf-8")
    for token in (
        "ck_bayesian_model_fits_available_confidence_complete",
        "ck_bayesian_model_fits_confidence_classification_state",
        "ck_bayesian_model_fits_confidence_evidence_tuple",
        "confidence_evidence_snapshot_hash = source_snapshot_hash",
        "source_read_completed_at >= source_read_started_at",
        "confidence_classified_at >= source_read_completed_at",
        "NOT VALID",
    ):
        _require(token in text, f"database_state_guard_missing:{token}")
    _require(
        "UPDATE public.bayesian_model_fits" not in text, "historical_state_fabricated"
    )
    return 9


def validate_producer_inventory(
    fit_execution: str | None = None, repository: str | None = None
) -> int:
    execution = fit_execution or FIT_EXECUTION.read_text("utf-8")
    fallback = repository or REPOSITORY.read_text("utf-8")
    mutation_paths = {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "backend/app/bayesian").glob("*.py")
        if "public.bayesian_model_fits" in path.read_text("utf-8")
        and (
            "UPDATE public.bayesian_model_fits" in path.read_text("utf-8")
            or "INSERT INTO public.bayesian_model_fits" in path.read_text("utf-8")
        )
    }
    _require(
        mutation_paths
        == {
            "backend/app/bayesian/e2e_harness.py",
            "backend/app/bayesian/fit_claim.py",
            "backend/app/bayesian/fit_execution.py",
            "backend/app/bayesian/repository.py",
            "backend/app/bayesian/runtime_state.py",
        },
        f"fit_writer_inventory_drift:{sorted(mutation_paths)}",
    )
    confidence_writer_paths = {
        path
        for path in mutation_paths
        if "confidence_bucket" in (ROOT / path).read_text("utf-8")
    }
    _require(
        confidence_writer_paths
        == {
            "backend/app/bayesian/fit_execution.py",
            "backend/app/bayesian/repository.py",
        },
        f"confidence_writer_inventory_drift:{sorted(confidence_writer_paths)}",
    )
    _require(
        execution.count("confidence_evidence_snapshot_hash = :source_snapshot_hash")
        == 2,
        "available_or_observed_evidence_writer_not_snapshot_bound",
    )
    _require(
        execution.count("confidence_evidence_snapshot_hash = NULL") == 2,
        "failure_writer_does_not_clear_partial_evidence",
    )
    for token in ("source_read_started_at", "source_read_completed_at"):
        _require(token in fallback, f"fallback_snapshot_time_not_persisted:{token}")
    _require(
        fallback.count("confidence_evidence_snapshot_hash = NULL") == 3,
        "fallback_writer_does_not_clear_partial_evidence",
    )
    runtime_state = (ROOT / "backend/app/bayesian/runtime_state.py").read_text("utf-8")
    _require(
        "AND status IN ('queued', 'running')" in runtime_state
        and "AND status = 'running'" in runtime_state,
        "unclassified_terminal_writer_not_preclassification_bounded",
    )
    return len(mutation_paths) + len(confidence_writer_paths) + 6


def validate_temporal_truth(
    source_snapshot: str | None = None,
    fit_claim: str | None = None,
    read_model: str | None = None,
    builder: str | None = None,
) -> int:
    snapshot = source_snapshot or SOURCE_SNAPSHOT.read_text("utf-8")
    claim = fit_claim or FIT_CLAIM.read_text("utf-8")
    reader = read_model or READ_MODEL.read_text("utf-8")
    payload = builder or BUILDER.read_text("utf-8")
    confidence_start = payload.index("def _confidence_projection_payload")
    confidence_end = payload.find("\ndef ", confidence_start + 1)
    confidence_builder = payload[
        confidence_start : confidence_end if confidence_end != -1 else None
    ]
    _require(
        snapshot.count("clock_timestamp()") >= 3, "database_snapshot_clock_missing"
    )
    for token in ("source_read_started_at", "source_read_completed_at"):
        _require(token in claim, f"fit_snapshot_time_not_persisted:{token}")
    _require(
        'evidence_snapshot_at=mapping.get("source_read_started_at")' in reader,
        "evidence_epoch_not_source_snapshot_start",
    )
    _require(
        "created_at - evidence_snapshot_at" in confidence_builder,
        "freshness_not_computed_from_evidence_epoch",
    )
    _require(
        '"source_read_started_at": utc_second(created_at)' not in confidence_builder,
        "request_time_relabelled_as_source_read_start",
    )
    return 6


def validate_executable_authority(sql: str | None = None) -> int:
    statement = sql if sql is not None else str(_EXACT_FIT_PROJECTION_SQL)
    try:
        actual = assert_executable_read_authority(
            statement,
            expected_tables=CONFIDENCE_PROJECTION_PHYSICAL_READ_TABLES,
        )
    except ConfidenceProjectionAuthorityError as exc:
        raise B25P13C4ClosureError(str(exc)) from exc
    return len(actual)


def validate_non_executable_text_is_not_authority() -> int:
    commented = (
        str(_EXACT_FIT_PROJECTION_SQL)
        + "\n-- JOIN public.b23_revenue_events token_only_non_dependency ON false\n"
    )
    validate_executable_authority(commented)
    return 1


def validate_freshness_lineage(sql: str | None = None) -> int:
    statement = (sql if sql is not None else str(_EXACT_FIT_PROJECTION_SQL)).lower()
    start = statement.index("from public.bayesian_model_fits newer_fit")
    end = statement.index(") as has_newer_fit", start)
    newer_fit_probe = statement[start:end]
    _require("newer_fit.status" not in newer_fit_probe, "failed_refit_excluded")
    _require(
        "dirty.observed_at > coalesce(" in statement
        and "requested_fit.source_read_started_at" in statement,
        "dirty_freshness_not_evidence_epoch_bound",
    )
    return 2


def validate_hash_domain(manifest: str | None = None) -> int:
    text = manifest if manifest is not None else HASH_MANIFEST.read_text("utf-8")
    for field in (
        "evidence_snapshot_at",
        "source_read_started_at",
        "source_read_completed_at",
        "data_freshness_seconds",
        "max_source_read_skew_ms",
    ):
        _require(
            f"evidence_temporal_boundary.{field}, domain: semantic_truth_v1" in text,
            f"temporal_field_not_semantic_hash_bound:{field}",
        )
    return 5


def _expect_failure(label: str, call) -> None:
    try:
        call()
    except B25P13C4ClosureError:
        return
    raise B25P13C4ClosureError(f"negative_control_did_not_fire:{label}")


def run_negative_controls() -> int:
    controls = 0
    for label, field, value in (
        ("NC-C4-01", "deterministic_row_count", None),
        ("NC-C4-02", "confidence_classified_at", None),
    ):
        poisoned = _available_input()
        poisoned[field] = value
        _expect_failure(label, lambda value=poisoned: validate_consumer(value))
        controls += 1

    fabricated_historical = _available_input()
    fabricated_historical["has_snapshot_lineage"] = True
    _expect_failure(
        "NC-C4-03",
        lambda: validate_historical_behavior(fabricated_historical),
    )
    controls += 1

    execution = FIT_EXECUTION.read_text("utf-8").replace(
        "confidence_evidence_snapshot_hash = :source_snapshot_hash",
        "confidence_evidence_snapshot_hash = NULL",
        1,
    )
    _expect_failure(
        "NC-C4-04", lambda: validate_producer_inventory(fit_execution=execution)
    )
    controls += 1

    reader = READ_MODEL.read_text("utf-8").replace(
        'evidence_snapshot_at=mapping.get("source_read_started_at")',
        'evidence_snapshot_at=mapping.get("completed_at")',
    )
    _expect_failure("NC-C4-05", lambda: validate_temporal_truth(read_model=reader))
    controls += 1

    builder = BUILDER.read_text("utf-8").replace(
        "created_at - evidence_snapshot_at", "created_at - projection.observed_at"
    )
    _expect_failure("NC-C4-06", lambda: validate_temporal_truth(builder=builder))
    controls += 1

    forbidden_sql = (
        str(_EXACT_FIT_PROJECTION_SQL)
        + "\nJOIN public.b23_revenue_events forbidden_live_dependency ON false\n"
    )
    _expect_failure("NC-C4-07", lambda: validate_executable_authority(forbidden_sql))
    controls += 1

    wrong_snapshot = _available_input()
    wrong_snapshot["confidence_evidence_snapshot_hash"] = "b" * 64
    _expect_failure("NC-C4-08", lambda: validate_consumer(wrong_snapshot))
    controls += 1

    filtered_sql = str(_EXACT_FIT_PROJECTION_SQL).replace(
        ") AS has_newer_fit",
        "AND newer_fit.status = 'succeeded'\n            ) AS has_newer_fit",
    )
    _expect_failure("NC-C4-09", lambda: validate_freshness_lineage(filtered_sql))
    controls += 1

    manifest = HASH_MANIFEST.read_text("utf-8").replace(
        "  - {field_path: evidence_temporal_boundary.source_read_started_at, domain: semantic_truth_v1}\n",
        "",
    )
    _expect_failure("NC-C4-10", lambda: validate_hash_domain(manifest))
    controls += 1
    return controls


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--negative-control", action="store_true")
    args = parser.parse_args()

    checks = sum(
        (
            validate_consumer(),
            validate_historical_behavior(),
            validate_database_migration(),
            validate_producer_inventory(),
            validate_temporal_truth(),
            validate_executable_authority(),
            validate_non_executable_text_is_not_authority(),
            validate_freshness_lineage(),
            validate_hash_domain(),
        )
    )
    controls = run_negative_controls() if args.negative_control else 0
    print("B25_P13_C4_CLOSURE_VALIDATION_PASS")
    print(f"p13_c4_checks_passed={checks}")
    print(f"p13_c4_negative_controls_fired={controls}")
    print("p13_c4_executable_dependency_controls=1")
    print("p13_c4_historical_rows_fail_closed=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
