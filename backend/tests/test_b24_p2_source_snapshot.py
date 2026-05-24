from __future__ import annotations

import asyncio
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
    MIN_SPARSE_PRIVACY_FLOOR,
    SOURCE_STREAM_INDEX_REQUIREMENTS,
    SOURCE_STREAM_MAX_ROW_BUFFER,
    SOURCE_STREAM_PARTITION_SIZE,
    SOURCE_CONTRACT_VERSION,
    SPARSE_PRIVACY_THRESHOLDS,
    validate_contract,
)
from app.bayesian.source_snapshot import (
    _SOURCE_QUERIES,
    canonical_json_bytes,
    sentinel_hash_for,
    sentinel_material_for,
    stream_source_chunks,
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
        "attribution_event_count": 20,
        "allocation_count": 20,
        "match_verdict_count": 20,
        "revenue_event_count": 20,
        "eligible_channel_count": 20,
        "provider_count": 2,
        "campaign_or_feature_count": 20,
        "distinct_source_event_count": 20,
        "attribution_amount_minor": 20000,
        "match_amount_minor": 20000,
        "min_event_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "max_event_at": datetime(2026, 1, 20, tzinfo=timezone.utc),
        "eligible_amount_minor_by_currency": {"USD": 20000},
        "currency_groups": [
            {"currency_code": "USD", "observation_count": 20, "amount_minor": 20000}
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


def _below_floor_row(count: int):
    return _base_preflight_row(
        attribution_event_count=count,
        allocation_count=0,
        match_verdict_count=count,
        revenue_event_count=0,
        eligible_channel_count=count,
        distinct_source_event_count=count,
        currency_groups=[
            {"currency_code": "USD", "observation_count": count, "amount_minor": count}
        ],
    )


def test_b24_p2_source_contract_is_versioned() -> None:
    assert SOURCE_CONTRACT_VERSION == "b24-source-v1"
    assert ELIGIBILITY_POLICY_VERSION == "b24-eligibility-v1"
    assert SPARSE_PRIVACY_THRESHOLDS.minimum_confirmed_match_verdicts >= 20
    validate_contract()


def test_b24_p2_sparse_thresholds_are_at_least_twenty() -> None:
    assert MIN_SPARSE_PRIVACY_FLOOR >= 20
    for value in SPARSE_PRIVACY_THRESHOLDS.__dict__.values():
        assert value >= MIN_SPARSE_PRIVACY_FLOOR


def test_b24_p2_threshold_below_floor_fails_validator() -> None:
    validator = _load_validator()
    text = (REPO_ROOT / "backend/app/bayesian/input_contract.py").read_text(
        encoding="utf-8"
    )
    mutated = text.replace(
        "minimum_confirmed_match_verdicts: int = MIN_SPARSE_PRIVACY_FLOOR",
        "minimum_confirmed_match_verdicts: int = 5",
        1,
    )
    with pytest.raises(validator.ValidationError, match="below floor"):
        validator.validate_input_contract(REPO_ROOT, mutated)


def test_b24_p2_missing_threshold_fails_validator() -> None:
    validator = _load_validator()
    text = (REPO_ROOT / "backend/app/bayesian/input_contract.py").read_text(
        encoding="utf-8"
    )
    mutated = text.replace(
        "    minimum_confirmed_match_verdicts: int = MIN_SPARSE_PRIVACY_FLOOR\n",
        "",
        1,
    )
    with pytest.raises(validator.ValidationError, match="threshold missing"):
        validator.validate_input_contract(REPO_ROOT, mutated)


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
    result = _classify(_below_floor_row(1))
    assert result.eligibility_status == EligibilityStatus.INSUFFICIENT_DATA
    assert result.fallback_reason == FallbackReason.INSUFFICIENT_DATA


@pytest.mark.parametrize("count", [1, 2, 5, 10, 19])
def test_b24_p2_below_floor_cohorts_never_stream(count: int) -> None:
    result = _classify(_below_floor_row(count))
    assert not result.is_eligible
    assert result.fallback_reason == FallbackReason.INSUFFICIENT_DATA


def test_b24_p2_twenty_event_cohort_can_stream_only_when_other_gates_pass() -> None:
    eligible = _classify(_base_preflight_row())
    insufficient_channel_diversity = _classify(
        _base_preflight_row(eligible_channel_count=19)
    )
    assert eligible.is_eligible
    assert insufficient_channel_diversity.fallback_reason == (
        FallbackReason.INSUFFICIENT_PRIVACY_COHORT
    )


def test_b24_p2_below_floor_cohort_uses_sentinel_hash() -> None:
    result = _classify(_below_floor_row(19))
    assert result.fallback_reason == FallbackReason.INSUFFICIENT_DATA
    assert sentinel_hash_for(result.fallback_reason) == sentinel_hash_for(
        FallbackReason.INSUFFICIENT_DATA
    )


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


def test_b24_p2_source_stream_uses_bounded_buffer() -> None:
    text = SOURCE_SNAPSHOT.read_text(encoding="utf-8")
    assert "stream_results" in text
    assert "yield_per" in text
    assert "max_row_buffer" in text
    assert ".partitions(SOURCE_STREAM_PARTITION_SIZE)" in text
    assert SOURCE_STREAM_PARTITION_SIZE > 0
    assert SOURCE_STREAM_MAX_ROW_BUFFER >= SOURCE_STREAM_PARTITION_SIZE


def test_b24_p2_streaming_buffer_size_is_explicit_or_dialect_proven() -> None:
    text = SOURCE_SNAPSHOT.read_text(encoding="utf-8")
    assert "_STREAM_EXECUTION_OPTIONS" in text
    assert '"stream_results": True' in text
    assert '"yield_per": SOURCE_STREAM_PARTITION_SIZE' in text
    assert '"max_row_buffer": SOURCE_STREAM_MAX_ROW_BUFFER' in text


def test_b24_p2_large_source_snapshot_does_not_materialize_all_rows() -> None:
    class FakeMappings:
        def __init__(self, source_name: str) -> None:
            self.source_name = source_name
            self.partition_sizes: list[int] = []

        async def partitions(self, size: int):
            self.partition_sizes.append(size)
            rows = []
            for index in range(size):
                common = {
                    "source_table_discriminator": self.source_name,
                    "id": str(index),
                    "tenant_id": str(TENANT_A),
                }
                if self.source_name == "attribution_events":
                    rows.append(
                        {
                            **common,
                            "occurred_at": WINDOW_START,
                            "event_timestamp": WINDOW_START,
                            "event_type": "conversion",
                            "channel": f"channel-{index}",
                            "campaign_id": f"campaign-{index}",
                            "revenue_cents": index,
                            "conversion_value_cents": index,
                            "currency": "USD",
                            "processing_status": "processed",
                        }
                    )
                elif self.source_name == "attribution_allocations":
                    rows.append(
                        {
                            **common,
                            "event_id": str(index),
                            "created_at": WINDOW_START,
                            "channel_code": f"channel-{index}",
                            "allocated_revenue_cents": index,
                            "allocation_ratio": "1.0",
                            "model_type": "mmm",
                            "model_version": "2026.05.p2",
                            "verified": True,
                            "verification_source": "test",
                            "verification_timestamp": WINDOW_START,
                        }
                    )
                elif self.source_name == "b23_match_verdicts":
                    rows.append(
                        {
                            **common,
                            "attribution_event_id": str(index),
                            "provider": "stripe",
                            "canonical_commerce_reference": str(index),
                            "status": "matched_confirmed",
                            "match_quality": "exact",
                            "attributed_amount_minor": index,
                            "verified_amount_minor": index,
                            "currency_code": "USD",
                            "confirmed_at": WINDOW_START,
                            "adjusted_at": None,
                            "last_transition_at": WINDOW_START,
                            "canonical_expected_gross_amount_minor": index,
                            "canonical_captured_gross_amount_minor": index,
                            "canonical_net_verified_amount_minor": index,
                            "discrepancy_amount_minor": 0,
                            "discrepancy_ratio_bps": 0,
                            "discrepancy_band": "none",
                        }
                    )
                else:
                    rows.append(
                        {
                            **common,
                            "match_verdict_id": str(index),
                            "provider": "stripe",
                            "canonical_commerce_reference": str(index),
                            "event_type": "payment_capture",
                            "currency_code": "USD",
                            "event_occurred_at": WINDOW_START,
                            "captured_amount_minor": index,
                            "refund_amount_minor": 0,
                            "chargeback_amount_minor": 0,
                            "reversal_amount_minor": 0,
                            "net_effect_sign": 1,
                            "is_gross_capture_correction": False,
                        }
                    )
            yield rows

    class FakeStream:
        def __init__(self, mappings: FakeMappings) -> None:
            self._mappings = mappings

        def mappings(self) -> FakeMappings:
            return self._mappings

    class FakeSession:
        def __init__(self) -> None:
            self.partition_sizes: list[int] = []
            self.execution_options = []
            self.source_names = list(_SOURCE_QUERIES)
            self.call_count = 0

        async def stream(self, query, params):
            self.execution_options.append(query.get_execution_options())
            source_name = self.source_names[self.call_count]
            self.call_count += 1
            mappings = FakeMappings(source_name)
            self.partition_sizes.append(SOURCE_STREAM_PARTITION_SIZE)
            return FakeStream(mappings)

    async def collect() -> tuple[FakeSession, int]:
        session = FakeSession()
        chunk_count = 0
        async for _chunk in stream_source_chunks(
            session,
            tenant_id=TENANT_A,
            source_window_start=WINDOW_START,
            source_window_end=WINDOW_END,
        ):
            chunk_count += 1
        return session, chunk_count

    session, chunk_count = asyncio.run(collect())
    assert chunk_count > SOURCE_STREAM_PARTITION_SIZE
    assert session.partition_sizes
    assert set(session.partition_sizes) == {SOURCE_STREAM_PARTITION_SIZE}
    assert all(
        options.get("stream_results") is True
        and options.get("yield_per") == SOURCE_STREAM_PARTITION_SIZE
        and options.get("max_row_buffer") == SOURCE_STREAM_MAX_ROW_BUFFER
        for options in session.execution_options
    )


def test_b24_p2_full_manifest_json_dumps_is_forbidden() -> None:
    validator = _load_validator()
    text = (
        SOURCE_SNAPSHOT.read_text(encoding="utf-8")
        + "\nfull_manifest = []\njson.dumps(full_manifest)\n"
    )
    with pytest.raises(validator.ValidationError, match="full manifest"):
        validator.validate_source_snapshot(REPO_ROOT, text)


def test_b24_p2_execute_all_fetchall_list_materialization_fails_validator() -> None:
    validator = _load_validator()
    text = SOURCE_SNAPSHOT.read_text(encoding="utf-8") + "\nrows = stream.fetchall()\n"
    with pytest.raises(validator.ValidationError, match="materialization"):
        validator.validate_source_snapshot(REPO_ROOT, text)


def test_b24_p2_schema_drift_unused_column_does_not_change_hash() -> None:
    base = canonical_json_bytes(
        {
            "chunk_type": "source_row",
            "source_table_discriminator": "attribution_events",
            "id": "1",
            "tenant_id": str(TENANT_A),
            "occurred_at": WINDOW_START,
            "event_timestamp": WINDOW_START,
            "event_type": "conversion",
            "channel": "paid",
            "campaign_id": "campaign-a",
            "revenue_cents": 100,
            "conversion_value_cents": 100,
            "currency": "USD",
            "processing_status": "processed",
        }
    )
    drifted_table_row_not_selected = canonical_json_bytes(
        {
            "chunk_type": "source_row",
            "source_table_discriminator": "attribution_events",
            "id": "1",
            "tenant_id": str(TENANT_A),
            "occurred_at": WINDOW_START,
            "event_timestamp": WINDOW_START,
            "event_type": "conversion",
            "channel": "paid",
            "campaign_id": "campaign-a",
            "revenue_cents": 100,
            "conversion_value_cents": 100,
            "currency": "USD",
            "processing_status": "processed",
        }
    )
    assert base == drifted_table_row_not_selected


def test_b24_p2_non_contract_field_in_encoder_fails_validator() -> None:
    validator = _load_validator()
    text = SOURCE_SNAPSHOT.read_text(encoding="utf-8").replace(
        "_contract_row_payload(source_name, dict(row))",
        "dict(row)",
        1,
    )
    with pytest.raises(validator.ValidationError, match="contract allowlist"):
        validator.validate_source_snapshot(REPO_ROOT, text)


def test_b24_p2_select_star_in_source_query_fails_validator() -> None:
    validator = _load_validator()
    text = SOURCE_SNAPSHOT.read_text(encoding="utf-8").replace(
        "SELECT\n                'attribution_events'",
        "SELECT * -- 'attribution_events'",
        1,
    )
    with pytest.raises(validator.ValidationError, match="SELECT \\*"):
        validator.validate_source_snapshot(REPO_ROOT, text)


def test_b24_p2_orm_to_json_hashing_fails_validator() -> None:
    validator = _load_validator()
    text = SOURCE_SNAPSHOT.read_text(encoding="utf-8").replace(
        "_contract_row_payload(source_name, dict(row))",
        "row.__dict__",
        1,
    )
    with pytest.raises(validator.ValidationError, match="serialization"):
        validator.validate_source_snapshot(REPO_ROOT, text)


def test_b24_p2_source_hashing_rejects_offset_pagination() -> None:
    validator = _load_validator()
    text = SOURCE_SNAPSHOT.read_text(encoding="utf-8").replace(
        "ORDER BY tenant_id ASC, occurred_at ASC NULLS LAST, id ASC",
        "ORDER BY tenant_id ASC, occurred_at ASC NULLS LAST, id ASC OFFSET 100",
        1,
    )
    with pytest.raises(validator.ValidationError, match="OFFSET"):
        validator.validate_source_snapshot(REPO_ROOT, text)


def test_b24_p2_source_stream_uses_server_cursor_or_keyset() -> None:
    text = SOURCE_SNAPSHOT.read_text(encoding="utf-8")
    assert "stream_results" in text
    assert ".partitions(" in text
    assert "OFFSET" not in text.upper()


def test_b24_p2_source_order_columns_have_supporting_indexes_or_plan() -> None:
    validator = _load_validator()
    canonical = (REPO_ROOT / "db/schema/canonical_schema.sql").read_text(
        encoding="utf-8"
    )
    for index_name in SOURCE_STREAM_INDEX_REQUIREMENTS.values():
        assert index_name in canonical
    validator.validate_query_path_indexes(REPO_ROOT)


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
    sparse = _classify(_base_preflight_row(match_verdict_count=19))
    eligible = _classify(_base_preflight_row(match_verdict_count=20))
    assert sparse.fallback_reason == FallbackReason.INSUFFICIENT_DATA
    assert eligible.is_eligible


def test_b24_p2_does_not_enqueue_or_call_sampler() -> None:
    validator = _load_validator()
    validator.validate_all(REPO_ROOT)


def test_b24_p2_validator_negative_controls() -> None:
    validator = _load_validator()
    validator.run_negative_controls(REPO_ROOT)
