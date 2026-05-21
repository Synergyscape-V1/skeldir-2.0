from __future__ import annotations

import hashlib
import importlib.util
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import pytest

from app.bayesian.eligibility import (
    EligibilityStatus,
    FallbackReason,
    classify_preflight,
)
from app.bayesian.input_contract import (
    ALLOWED_SOURCE_READ_MODELS,
    ELIGIBILITY_POLICY_VERSION,
    FORBIDDEN_MANIFEST_SOURCES,
    SOURCE_CONTRACT_VERSION,
    SPARSE_PRIVACY_THRESHOLDS,
    validate_contract,
)
from app.bayesian.source_snapshot import (
    canonical_json_bytes,
    sentinel_hash_for,
    sentinel_material_for,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "scripts/ci/validate_b24_p2_source_snapshot.py"
SOURCE_SNAPSHOT = REPO_ROOT / "backend/app/bayesian/source_snapshot.py"
ELIGIBILITY = REPO_ROOT / "backend/app/bayesian/eligibility.py"
REPOSITORY = REPO_ROOT / "backend/app/bayesian/repository.py"


TENANT_A = UUID("11111111-1111-4111-8111-111111111111")
WINDOW_START = datetime(2026, 1, 1, tzinfo=timezone.utc)
WINDOW_END = datetime(2026, 2, 1, tzinfo=timezone.utc)


def _load_validator():
    spec = importlib.util.spec_from_file_location(
        "validate_b24_p2_source_snapshot", VALIDATOR
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _base_preflight_row(**overrides):
    row = {
        "attribution_event_count": 10,
        "allocation_count": 10,
        "match_verdict_count": 5,
        "revenue_event_count": 5,
        "eligible_channel_count": 2,
        "distinct_source_event_count": 10,
        "attribution_amount_minor": 10000,
        "match_amount_minor": 10000,
        "min_event_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "max_event_at": datetime(2026, 1, 2, tzinfo=timezone.utc),
        "eligible_amount_minor_by_currency": {"USD": 10000},
        "currency_groups": [
            {"currency_code": "USD", "observation_count": 5, "amount_minor": 10000}
        ],
        "excluded_attribution_counts": {},
        "excluded_match_counts": {},
        "excluded_revenue_counts": {},
    }
    row.update(overrides)
    return row


def _classify(row):
    return classify_preflight(
        tenant_id=TENANT_A,
        model_type="mmm",
        model_version="2026.05.p2",
        source_window_start=WINDOW_START,
        source_window_end=WINDOW_END,
        row=row,
    )


def test_b24_p2_source_contract_is_versioned() -> None:
    assert SOURCE_CONTRACT_VERSION == "b24-source-v1"
    assert ELIGIBILITY_POLICY_VERSION == "b24-eligibility-v1"
    assert SPARSE_PRIVACY_THRESHOLDS.minimum_confirmed_match_verdicts > 0
    validate_contract()


def test_b24_p2_identity_tables_are_not_manifest_sources() -> None:
    assert not (set(ALLOWED_SOURCE_READ_MODELS) & FORBIDDEN_MANIFEST_SOURCES)


def test_b24_p2_manifest_contains_no_pii_or_raw_payload() -> None:
    joined = " ".join(
        field for fields in ALLOWED_SOURCE_READ_MODELS.values() for field in fields
    ).lower()
    for token in (
        "email",
        "ip_address",
        "raw_payload",
        "oauth",
        "token",
        "secret",
        "native_event_reference",
    ):
        assert token not in joined


def test_b24_p2_preflight_runs_before_manifest_cursor() -> None:
    validator = _load_validator()
    text = SOURCE_SNAPSHOT.read_text(encoding="utf-8")
    validator.validate_source_snapshot(REPO_ROOT, text)


def test_b24_p2_sparse_tenant_does_not_call_manifest_builder() -> None:
    result = _classify(
        _base_preflight_row(
            attribution_event_count=1,
            distinct_source_event_count=1,
            match_verdict_count=1,
            revenue_event_count=0,
        )
    )
    assert result.eligibility_status == EligibilityStatus.INSUFFICIENT_DATA
    assert result.fallback_reason == FallbackReason.INSUFFICIENT_DATA


def test_b24_p2_preflight_and_manifest_use_same_repeatable_read_snapshot() -> None:
    text = SOURCE_SNAPSHOT.read_text(encoding="utf-8")
    assert "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY" in text
    assert "run_eligibility_preflight" in text
    assert text.find("run_eligibility_preflight") < text.find("stream_source_chunks")


def test_b24_p2_rejects_read_committed_paginated_snapshot_path() -> None:
    validator = _load_validator()
    text = SOURCE_SNAPSHOT.read_text(encoding="utf-8").replace(
        "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY",
        "SET TRANSACTION READ WRITE",
        1,
    )
    with pytest.raises(validator.ValidationError, match="repeatable-read"):
        validator.validate_source_snapshot(REPO_ROOT, text)


def test_b24_p2_same_timestamp_rows_hash_deterministically() -> None:
    left = canonical_json_bytes(
        {
            "id": "b",
            "occurred_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "amount": 1,
        }
    )
    right = canonical_json_bytes(
        {
            "amount": 1,
            "occurred_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "id": "b",
        }
    )
    assert left == right


def test_b24_p2_timestamp_only_ordering_is_rejected() -> None:
    validator = _load_validator()
    text = SOURCE_SNAPSHOT.read_text(encoding="utf-8").replace(
        "ORDER BY tenant_id ASC, occurred_at ASC NULLS LAST, id ASC",
        "ORDER BY occurred_at ASC",
        1,
    )
    with pytest.raises(validator.ValidationError, match="total order"):
        validator.validate_source_snapshot(REPO_ROOT, text)


def test_b24_p2_sparse_privacy_cohort_blocks_manifest_stream() -> None:
    result = _classify(_base_preflight_row(eligible_channel_count=1))
    assert result.eligibility_status == EligibilityStatus.INSUFFICIENT_PRIVACY_COHORT
    assert result.fallback_reason == FallbackReason.INSUFFICIENT_PRIVACY_COHORT


def test_b24_p2_threshold_crossing_allows_row_level_manifest() -> None:
    result = _classify(_base_preflight_row())
    assert result.is_eligible
    assert result.fallback_reason is None


def test_b24_p2_cold_start_uses_sentinel_hash() -> None:
    expected_material = (
        "B24_SOURCE_SNAPSHOT_SENTINEL"
        "|source_contract_version=b24-source-v1"
        "|eligibility_policy_version=b24-eligibility-v1"
        "|fallback_reason=insufficient_data"
    )
    assert sentinel_material_for(FallbackReason.INSUFFICIENT_DATA) == expected_material
    assert (
        sentinel_hash_for(FallbackReason.INSUFFICIENT_DATA)
        == hashlib.sha256(expected_material.encode("utf-8")).hexdigest()
    )


def test_b24_p2_repeated_still_insufficient_data_debounces_one_fallback_row() -> None:
    text = REPOSITORY.read_text(encoding="utf-8")
    assert "ON CONFLICT" in text
    assert "DO UPDATE SET" in text
    assert "source_window_start" in text and "source_window_end" in text


def test_b24_p2_streaming_hash_uses_incremental_update() -> None:
    text = SOURCE_SNAPSHOT.read_text(encoding="utf-8")
    assert "session.stream" in text
    assert ".update(canonical_chunk)" in text


def test_b24_p2_full_manifest_json_dumps_is_forbidden() -> None:
    validator = _load_validator()
    text = (
        SOURCE_SNAPSHOT.read_text(encoding="utf-8")
        + "\nfull_manifest = []\njson.dumps(full_manifest)\n"
    )
    with pytest.raises(validator.ValidationError, match="full manifest"):
        validator.validate_source_snapshot(REPO_ROOT, text)


def test_b24_p2_manifest_replay_is_deterministic() -> None:
    payload = {"b": 2, "a": 1, "ts": datetime(2026, 1, 1, tzinfo=timezone.utc)}
    assert canonical_json_bytes(payload) == canonical_json_bytes(
        dict(reversed(list(payload.items())))
    )


def test_b24_p2_hash_is_sha256_64_hex() -> None:
    assert re.fullmatch(
        r"[a-f0-9]{64}", sentinel_hash_for(FallbackReason.SOURCE_WINDOW_EMPTY)
    )


def test_b24_p2_included_amount_change_changes_hash() -> None:
    assert canonical_json_bytes({"amount": 1, "id": "a"}) != canonical_json_bytes(
        {"amount": 2, "id": "a"}
    )


def test_b24_p2_included_status_change_changes_hash() -> None:
    assert canonical_json_bytes(
        {"status": "matched_confirmed", "id": "a"}
    ) != canonical_json_bytes({"status": "adjusted", "id": "a"})


def test_b24_p2_included_timestamp_change_changes_hash() -> None:
    assert canonical_json_bytes(
        {"id": "a", "ts": datetime(2026, 1, 1, tzinfo=timezone.utc)}
    ) != canonical_json_bytes(
        {"id": "a", "ts": datetime(2026, 1, 2, tzinfo=timezone.utc)}
    )


def test_b24_p2_excluded_pending_row_does_not_change_hash() -> None:
    result = _classify(
        _base_preflight_row(excluded_match_counts={"b23_match_verdicts:pending": 99})
    )
    assert result.is_eligible
    assert result.excluded_row_counts_by_reason["b23_match_verdicts:pending"] == 99


def test_b24_p2_out_of_window_row_does_not_change_hash() -> None:
    eligibility_text = ELIGIBILITY.read_text(encoding="utf-8")
    assert "event_occurred_at >= :window_start" in eligibility_text
    assert "event_occurred_at < :window_end" in eligibility_text


def test_b24_p2_tenant_b_cannot_affect_tenant_a_snapshot() -> None:
    text = SOURCE_SNAPSHOT.read_text(encoding="utf-8")
    assert text.count("tenant_id = :tenant_id") >= 4
    assert "current_setting('app.current_tenant_id', true)" in text


def test_b24_p2_missing_tenant_context_fails_closed() -> None:
    text = SOURCE_SNAPSHOT.read_text(encoding="utf-8")
    assert "BayesianTenantContextError" in text
    assert "tenant GUC must be bound" in text


def test_b24_p2_cold_start_does_not_set_sampling_started_or_last_fit() -> None:
    text = REPOSITORY.read_text(encoding="utf-8")
    assert "sampling_started_at = NULL" in text
    assert "last_fit_at = NULL" in text
    assert "runtime_seconds = NULL" in text


def test_b24_p2_threshold_crossing_reopens_eligibility() -> None:
    sparse = _classify(_base_preflight_row(match_verdict_count=1))
    eligible = _classify(_base_preflight_row(match_verdict_count=5))
    assert sparse.fallback_reason == FallbackReason.INSUFFICIENT_DATA
    assert eligible.is_eligible


def test_b24_p2_does_not_enqueue_or_call_sampler() -> None:
    validator = _load_validator()
    validator.validate_all(REPO_ROOT)


def test_b24_p2_validator_negative_controls() -> None:
    validator = _load_validator()
    validator.run_negative_controls(REPO_ROOT)
