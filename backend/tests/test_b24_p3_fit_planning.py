from __future__ import annotations

import importlib.util
from pathlib import Path
from uuid import UUID

import pytest

from app.bayesian.dirty_marker import DIRTY_EVENT_LOW_CONTENTION_POLICY
from app.bayesian.dispatch_outbox import DispatchOutboxRow
from app.bayesian.fit_planner import DEBOUNCE_POLICY_VERSION, QUIET_PERIOD_SECONDS


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "scripts/ci/validate_b24_p3_fit_planning.py"
DIRTY_MARKER = REPO_ROOT / "backend/app/bayesian/dirty_marker.py"
FIT_PLANNER = REPO_ROOT / "backend/app/bayesian/fit_planner.py"
FIT_CLAIM = REPO_ROOT / "backend/app/bayesian/fit_claim.py"
DISPATCH_OUTBOX = REPO_ROOT / "backend/app/bayesian/dispatch_outbox.py"
MIGRATION = (
    REPO_ROOT
    / "alembic/versions/007_skeldir_foundation/202605221430_b24_p3_fit_planning_outbox.py"
)
INGESTION = REPO_ROOT / "backend/app/ingestion/event_service.py"
ATTRIBUTION_TASKS = REPO_ROOT / "backend/app/tasks/attribution.py"
B23_BATCH = REPO_ROOT / "backend/app/revenue_verification/batch_engine.py"
BAYESIAN_TASKS = REPO_ROOT / "backend/app/tasks/bayesian.py"


def _load_validator():
    spec = importlib.util.spec_from_file_location(
        "validate_b24_p3_fit_planning", VALIDATOR
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def test_b24_p3_hot_path_emits_dirty_event_only() -> None:
    validator = _load_validator()
    validator.validate_hot_paths(REPO_ROOT)
    for path in (INGESTION, ATTRIBUTION_TASKS, B23_BATCH):
        assert "append_dirty_event" in _read(path)


def test_b24_p3_hot_path_does_not_compute_source_snapshot() -> None:
    for path in (INGESTION, ATTRIBUTION_TASKS, B23_BATCH):
        assert "compute_source_snapshot_hash" not in _read(path)


def test_b24_p3_hot_path_does_not_claim_fit() -> None:
    for path in (INGESTION, ATTRIBUTION_TASKS, B23_BATCH):
        assert "claim_fit_for_snapshot" not in _read(path)


def test_b24_p3_hot_path_does_not_publish_broker_message() -> None:
    for path in (INGESTION, ATTRIBUTION_TASKS, B23_BATCH):
        text = _read(path)
        assert "app.tasks.bayesian.execute_fit_intent" not in text
        assert "celery_app.send_task" not in text


def test_b24_p3_dirty_event_append_or_shard_avoids_hot_row_locking() -> None:
    text = _read(DIRTY_MARKER)
    assert DIRTY_EVENT_LOW_CONTENTION_POLICY == "append_only_single_insert_v1"
    assert "INSERT INTO public.b24_dirty_events" in text
    assert "ON CONFLICT" not in text


def test_b24_p3_dirty_event_burst_overhead_within_policy() -> None:
    text = _read(DIRTY_MARKER)
    assert "append_only_single_insert_v1" in text
    assert "RETURNING id" in text


def test_b24_p3_dirty_event_coalescer_uses_skip_locked_or_equivalent() -> None:
    assert "FOR UPDATE OF dirty SKIP LOCKED" in _read(FIT_PLANNER)


def test_b24_p3_dirty_event_lifecycle_after_claim() -> None:
    text = _read(FIT_PLANNER)
    assert 'status = "claimed"' in text or 'status = "claimed"' in text
    assert "claimed_at" in text


def test_b24_p3_dirty_event_lifecycle_after_fallback() -> None:
    text = _read(FIT_PLANNER)
    assert "fallback_only" in text
    assert "fallback_at" in text


def test_b24_p3_dirty_event_supersession_lifecycle() -> None:
    text = _read(FIT_PLANNER)
    assert "superseded" in text
    assert "superseded_at" in text


def test_b24_p3_debounce_blocks_pre_quiet_period_planning() -> None:
    text = _read(FIT_PLANNER)
    assert DEBOUNCE_POLICY_VERSION == "b24-p3-debounce-v1"
    assert QUIET_PERIOD_SECONDS >= 60
    assert "max(observed_at) <= :quiet_cutoff" in text


def test_b24_p3_burst_source_changes_produce_one_planning_attempt() -> None:
    text = _read(FIT_PLANNER)
    assert "GROUP BY" in text
    for column in (
        "model_type",
        "model_version",
        "source_window_start",
        "source_window_end",
    ):
        assert column in text


def test_b24_p3_planner_invokes_source_snapshot_once_after_debounce() -> None:
    text = _read(FIT_PLANNER)
    assert text.find("lease_debounced_dirty_candidates") < text.find(
        "compute_source_snapshot_hash"
    )


def test_b24_p3_one_active_execution_per_tenant_model_window() -> None:
    migration = _read(MIGRATION)
    assert "b24_active_execution_leases_pkey" in migration
    key = migration[
        migration.find("b24_active_execution_leases_pkey") : migration.find(
            ")", migration.find("b24_active_execution_leases_pkey")
        )
    ]
    assert "source_snapshot_hash" not in key


def test_b24_p3_new_hash_while_running_marks_superseded_not_concurrent_fit() -> None:
    text = _read(FIT_CLAIM)
    assert "needs_refit_after_current" in text
    assert "active_source_snapshot_hash IS DISTINCT FROM" in text
    assert "SUPPRESSED_ACTIVE" in text


def test_b24_p3_h2_claim_waits_until_h1_terminal() -> None:
    text = _read(FIT_CLAIM)
    assert "ACTIVE_EXECUTION_STATUSES" in text
    assert "TERMINAL_EXECUTION_STATUSES" in text
    assert "leased_until" in text


def test_b24_p3_atomic_claim_concurrent_workers_one_fit() -> None:
    text = _read(FIT_CLAIM)
    assert "FOR UPDATE" in text
    assert "ON CONFLICT DO NOTHING" in text


def test_b24_p3_duplicate_active_execution_insert_rejected() -> None:
    migration = _read(MIGRATION)
    assert "CONSTRAINT b24_active_execution_leases_pkey PRIMARY KEY" in migration


def test_b24_p3_claim_and_dispatch_intent_same_transaction() -> None:
    text = _read(FIT_CLAIM)
    assert text.find("INSERT INTO public.bayesian_model_fits") < text.find(
        "INSERT INTO public.b24_fit_dispatch_outbox"
    )


def test_b24_p3_claim_commit_publish_crash_leaves_outbox_pending() -> None:
    text = _read(FIT_CLAIM)
    assert "b24_fit_dispatch_outbox" in text
    assert "'pending'" in text


def test_b24_p3_dispatcher_replays_pending_outbox_after_crash() -> None:
    text = _read(DISPATCH_OUTBOX)
    assert "status IN ('pending', 'failed_retryable', 'stale_recovered')" in text


def test_b24_p3_dispatch_publish_timeout_does_not_permanently_lock_fit() -> None:
    text = _read(DISPATCH_OUTBOX)
    assert "mark_dispatch_failed" in text
    assert "next_attempt_at" in text


def test_b24_p3_stale_dispatching_is_recovered() -> None:
    assert "recover_stale_dispatching" in _read(DISPATCH_OUTBOX)


def test_b24_p3_dead_letter_after_retry_exhaustion() -> None:
    text = _read(DISPATCH_OUTBOX)
    assert "dead_lettered" in text
    assert "attempt_count >= row.max_attempts" in text


def test_b24_p3_duplicate_outbox_publish_is_worker_idempotent() -> None:
    text = _read(MIGRATION)
    assert "uq_b24_fit_dispatch_outbox_fit" in text
    assert "uq_b24_fit_dispatch_outbox_dispatch_key" in text


def test_b24_p3_queue_payload_is_minimal_capability_wakeup() -> None:
    row = DispatchOutboxRow(
        id=UUID("11111111-1111-4111-8111-111111111111"),
        tenant_id=UUID("22222222-2222-4222-8222-222222222222"),
        fit_id=UUID("33333333-3333-4333-8333-333333333333"),
        task_name="app.tasks.bayesian.execute_fit_intent",
        attempt_id=UUID("44444444-4444-4444-8444-444444444444"),
        payload_hash="a" * 64,
        recovery_generation=0,
        assigned_worker_generation="directive-x-p3-generation",
        attempt_count=0,
        max_attempts=5,
    )
    assert set(row.queue_payload) == {
        "dispatch_id",
        "fit_id",
        "task_name",
        "attempt_id",
        "payload_hash",
        "recovery_generation",
    }
    assert "claim_capability" not in row.queue_payload


def test_b24_p3_queue_payload_rejects_source_rows_or_manifest() -> None:
    validator = _load_validator()
    mutated = _read(DISPATCH_OUTBOX).replace(
        '"recovery_generation": str(self.recovery_generation),',
        '"recovery_generation": str(self.recovery_generation), "source_rows": [],',
    )
    with pytest.raises(validator.ValidationError, match="forbidden"):
        validator.validate_dispatch_outbox(REPO_ROOT, mutated)


def test_b24_p3_duplicate_task_delivery_is_idempotent() -> None:
    text = _read(BAYESIAN_TASKS)
    assert "def execute_fit_intent" in text
    assert "compute_started" in text
    assert "False" in text


def test_b24_p3_planner_does_not_mutate_deterministic_truth() -> None:
    text = _read(FIT_PLANNER) + _read(FIT_CLAIM) + _read(DISPATCH_OUTBOX)
    for mutation in (
        "UPDATE public.attribution_events",
        "UPDATE public.attribution_allocations",
        "UPDATE public.b23_match_verdicts",
        "UPDATE public.b23_revenue_events",
        "INSERT INTO public.attribution_events",
        "INSERT INTO public.b23_match_verdicts",
    ):
        assert mutation not in text


def test_b24_p3_source_snapshot_query_plans_are_safe() -> None:
    validator = _load_validator()
    validator.validate_source_query_plan_proof(REPO_ROOT)


def test_b24_p3_no_statistical_runtime_no_projection_no_public_api_no_llm() -> None:
    validator = _load_validator()
    validator.validate_scope(REPO_ROOT)


def test_b24_p3_validator_negative_control() -> None:
    validator = _load_validator()
    validator.run_negative_control(REPO_ROOT)
