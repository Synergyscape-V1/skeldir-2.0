from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from app.bayesian.api_projection import (
    build_b24_confidence_projection_query,
    build_projection_models,
)
from app.bayesian.confidence_policy import (
    CONFIDENCE_POLICY_VERSION,
    CONFIDENCE_SEMANTICS_VERSION,
    ConfidenceBucket,
    ConfidenceBucketReason,
    classify_confidence,
    persisted_confidence_decision,
)


ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "scripts/ci/validate_b24_p10_projection.py"


def test_b24_p10_persisted_classification_is_version_and_semantics_bound() -> None:
    valid = persisted_confidence_decision(
        confidence_bucket="high",
        confidence_bucket_reason="narrow_interval",
        confidence_policy_version=CONFIDENCE_POLICY_VERSION,
        confidence_semantics_version=CONFIDENCE_SEMANTICS_VERSION,
    )
    assert valid.confidence_available is True
    assert valid.confidence_bucket is ConfidenceBucket.HIGH

    stale_semantics = persisted_confidence_decision(
        confidence_bucket="high",
        confidence_bucket_reason="narrow_interval",
        confidence_policy_version=CONFIDENCE_POLICY_VERSION,
        confidence_semantics_version="mutated-semantics",
    )
    assert stale_semantics.confidence_available is False
    assert stale_semantics.confidence_bucket_reason is (
        ConfidenceBucketReason.PERSISTED_CLASSIFICATION_INVALID
    )


def test_b24_p10_multi_currency_is_typed_unavailable() -> None:
    decision = classify_confidence(
        {
            **_base_row(),
            "currency_count": 2,
        }
    )
    assert decision.confidence_available is False
    assert decision.confidence_bucket_reason is (
        ConfidenceBucketReason.MULTI_CURRENCY_UNSUPPORTED
    )


def _load_validator():
    spec = importlib.util.spec_from_file_location(
        "validate_b24_p10_projection", VALIDATOR
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _base_row(**overrides):
    tenant_id = overrides.pop("tenant_id", uuid4())
    fit_id = overrides.pop("fit_id", uuid4())
    row = {
        "tenant_id": tenant_id,
        "currency_code": "USD",
        "deterministic_revenue_minor": 10_000,
        "deterministic_row_count": 2,
        "match_verdict_count": 2,
        "webhook_identity_count": 2,
        "source_snapshot_mismatch": False,
        "fit_id": fit_id,
        "fit_status": "succeeded",
        "model_type": "bayesian_attribution_confidence",
        "model_version": "b24-p10",
        "data_completeness_status": "complete",
        "fallback_applied": False,
        "fallback_reason": None,
        "r_hat_max": 1.0,
        "ess_min": 500.0,
        "divergence_count": 0,
        "hdi_lower": 9_600.0,
        "hdi_upper": 10_400.0,
        "credible_interval_status": "available",
        "diagnostic_status": "passed",
        "diagnostic_failure_reason": None,
        "diagnostic_policy_version": "b24-p7-diagnostic-policy-v1",
        "interval_policy_version": "b24-p7-interval-policy-v1",
        "hdi_probability": 0.95,
        "artifact_ref": f"b24://artifact/{tenant_id}/{fit_id}/posterior_summary/{'a' * 12}",
        "artifact_hash": "a" * 64,
        "artifact_lifecycle_status": "active",
        "artifact_policy_version": "b24-p8-artifact-policy-v1",
    }
    row.update(overrides)
    return row


def test_b24_p10_sql_roots_on_deterministic_left_and_left_joins_bayesian() -> None:
    sql = str(build_b24_confidence_projection_query()).lower()

    assert "with deterministic_left as" in sql
    assert "from public.b23_revenue_events revenue" in sql
    assert "left outer join latest_matching_fit" in sql
    assert "left outer join artifact_summary" in sql
    assert "left outer join mismatch_probe" in sql
    assert "fit.source_snapshot_hash = :source_snapshot_hash" in sql
    assert "where fit.status" not in sql
    assert "from public.bayesian_model_fits fit\n            where" in sql


def test_b24_p10_no_fit_preserves_deterministic_revenue() -> None:
    tenant_id = uuid4()
    projection = build_projection_models(
        [
            _base_row(
                tenant_id=tenant_id,
                fit_id=None,
                fit_status=None,
                model_type=None,
                model_version=None,
                fallback_applied=None,
                hdi_lower=None,
                hdi_upper=None,
                credible_interval_status=None,
                diagnostic_status=None,
                artifact_ref=None,
                artifact_hash=None,
            )
        ],
        source_window_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        source_window_end=datetime(2026, 1, 2, tzinfo=timezone.utc),
        source_snapshot_hash="b" * 64,
        generated_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )[0]

    assert projection.deterministic.tenant_id == tenant_id
    assert projection.deterministic.deterministic_revenue_minor == 10_000
    assert projection.confidence.confidence_available is False
    assert projection.confidence.confidence_bucket == "unavailable"
    assert projection.confidence.confidence_bucket_reason == "no_fit"
    assert projection.bayesian.credible_interval.status == "unavailable"
    assert projection.audit.deterministic_left_join_used is True
    assert projection.audit.projection_read_only is True


@pytest.mark.parametrize(
    ("lower", "upper", "bucket", "reason"),
    [
        (9_600.0, 10_400.0, "high", "narrow_interval"),
        (8_900.0, 11_100.0, "medium", "moderate_interval"),
        (7_000.0, 13_000.0, "low", "wide_interval"),
    ],
)
def test_b24_p10_backend_policy_classifies_interval_width(
    lower: float, upper: float, bucket: str, reason: str
) -> None:
    decision = classify_confidence(_base_row(hdi_lower=lower, hdi_upper=upper))

    assert decision.confidence_available is True
    assert decision.confidence_bucket == ConfidenceBucket(bucket)
    assert decision.confidence_bucket_reason == ConfidenceBucketReason(reason)
    assert decision.confidence_policy_version == CONFIDENCE_POLICY_VERSION


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        (
            {"diagnostic_status": "failed", "diagnostic_failure_reason": "bad_rhat"},
            "bad_rhat",
        ),
        (
            {"diagnostic_status": "failed", "diagnostic_failure_reason": "low_ess"},
            "low_ess",
        ),
        (
            {"diagnostic_status": "failed", "diagnostic_failure_reason": "divergence"},
            "divergence",
        ),
        (
            {
                "fit_status": "timeout",
                "fallback_applied": True,
                "fallback_reason": "timeout",
            },
            "timeout",
        ),
        (
            {
                "fit_status": "failed",
                "fallback_applied": True,
                "fallback_reason": "worker_failure",
            },
            "worker_failure",
        ),
        (
            {
                "fit_status": "fallback_only",
                "fallback_applied": True,
                "fallback_reason": "input_too_large",
            },
            "input_too_large",
        ),
        ({"source_snapshot_mismatch": True}, "source_snapshot_changed"),
        ({"artifact_lifecycle_status": "pruned"}, "artifact_pruned"),
        ({"artifact_ref": None, "artifact_hash": None}, "artifact_unavailable"),
    ],
)
def test_b24_p10_unavailable_states_are_reason_coded(overrides, reason: str) -> None:
    decision = classify_confidence(_base_row(**overrides))

    assert decision.confidence_available is False
    assert decision.confidence_bucket == ConfidenceBucket.UNAVAILABLE
    assert decision.confidence_bucket_reason.value == reason


def test_b24_p10_projection_schema_validates_converged_and_fallback_cases() -> None:
    projections = build_projection_models(
        [
            _base_row(),
            _base_row(
                fit_status="fallback_only",
                fallback_applied=True,
                fallback_reason="insufficient_data",
                diagnostic_status="unavailable",
                credible_interval_status="not_available",
                hdi_lower=None,
                hdi_upper=None,
                artifact_ref=None,
                artifact_hash=None,
            ),
        ],
        source_window_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        source_window_end=datetime(2026, 1, 2, tzinfo=timezone.utc),
        source_snapshot_hash="c" * 64,
    )

    assert projections[0].confidence.confidence_bucket == "high"
    assert projections[0].bayesian.credible_interval.unit == "minor_units"
    assert projections[0].deterministic.deterministic_revenue_minor == 10_000
    assert projections[1].confidence.confidence_bucket_reason == "insufficient_data"
    assert projections[1].bayesian.credible_interval.lower is None


def test_b24_p10_no_authority_fields_leak_from_dto() -> None:
    projection = build_projection_models(
        [_base_row()],
        source_window_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        source_window_end=datetime(2026, 1, 2, tzinfo=timezone.utc),
        source_snapshot_hash="d" * 64,
    )[0]

    payload = projection.model_dump(mode="json")
    serialized = str(payload).lower()
    for token in (
        "lease_capability",
        "process_token",
        "claim_capability",
        "broker_authority",
        "payload_bytes",
    ):
        assert token not in serialized


def test_b24_p10_static_validator_negative_controls() -> None:
    validator = _load_validator()
    validator.validate_all()
    validator.run_negative_controls()
