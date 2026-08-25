"""C10 claim-time policy and natural fresh-dispatch runtime proofs."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import NullPool

from app.bayesian.dispatch_authority import (
    BAYESIAN_FIT_EXECUTION_TASK,
    dispatch_payload_hash,
    fail_dispatch_terminal_sync,
)
from app.bayesian.dispatch_outbox import DispatchOutboxRow, RecoveryOutboxRow
from app.bayesian.fit_execution import (
    _build_sampler_input,
    _load_fit_for_execution,
    _mark_fit_failure,
    _replan_superseded_policy_bundle,
)
from app.bayesian.enums import FallbackReason, FitStatus
from app.bayesian.inference_profile import B24_INFERENCE_PROFILE
from app.bayesian.model_spec import B24_P6_MODEL_TYPE, B24_P6_MODEL_VERSION
from app.bayesian.source_snapshot import P6SourceObservedInput
from app.core.queues import QUEUE_BAYESIAN, QUEUE_BAYESIAN_PUBLISHER
from app.core.secrets import get_database_url
from app.db.dsn import to_sync_postgres_dsn
from tests.test_b24_p9_postgres_runtime import (
    END,
    ROOT,
    START,
    _beat_env,
    _claim_test_dispatch_lease,
    _max_broker_message_id,
    _set_tenant_context,
    _terminate_worker,
    _wait_for_broker_task_messages,
    _wait_for_log,
    _wait_for_probe_event_matching,
    _worker_env,
)


pytestmark = pytest.mark.skipif(
    os.getenv("SKELDIR_B25_P13_C10_DB_PROOF") != "1",
    reason="B2.5-P13 C10 PostgreSQL/broker proof is opt-in locally",
)

PUBLISHER_BEAT_ENTRY = "b24-fit-dispatch-publisher"


def test_c10_production_schedule_contains_fresh_dispatch_publisher() -> None:
    """The live proof depends on a production Beat entry, not direct `.run()`."""

    from app.tasks.bayesian_publisher import DISPATCH_PUBLISHER_TASK_NAME
    from app.tasks.beat_schedule import build_beat_schedule

    schedule = build_beat_schedule()
    assert schedule[PUBLISHER_BEAT_ENTRY]["task"] == DISPATCH_PUBLISHER_TASK_NAME
    assert (
        schedule[PUBLISHER_BEAT_ENTRY]["options"]["queue"] == QUEUE_BAYESIAN_PUBLISHER
    )


def test_c10_initial_and_recovery_payload_authority_are_equivalent() -> None:
    """Initial and recovery wake-ups carry identical secret-free authority."""

    tenant_id = uuid4()
    fit_id = uuid4()
    attempt_id = uuid4()
    payload_hash = dispatch_payload_hash(fit_id=fit_id)
    initial = DispatchOutboxRow(
        id=uuid4(),
        tenant_id=tenant_id,
        fit_id=fit_id,
        task_name=BAYESIAN_FIT_EXECUTION_TASK,
        attempt_id=attempt_id,
        payload_hash=payload_hash,
        recovery_generation=0,
        assigned_worker_generation="generation-1",
        attempt_count=1,
        max_attempts=5,
    )
    recovery = RecoveryOutboxRow(
        id=uuid4(),
        tenant_id=tenant_id,
        dispatch_id=initial.id,
        fit_id=fit_id,
        task_name=BAYESIAN_FIT_EXECUTION_TASK,
        attempt_id=attempt_id,
        payload_hash=payload_hash,
        recovery_generation=1,
        publish_attempt_count=1,
    )
    assert set(initial.queue_payload) == set(recovery.queue_payload)
    assert {
        key: value
        for key, value in initial.queue_payload.items()
        if key != "recovery_generation"
    } == {
        key: value
        for key, value in recovery.queue_payload.items()
        if key != "recovery_generation"
    }
    assert "tenant_id" not in initial.queue_payload
    assert "lease_capability" not in initial.queue_payload


def _worker_engine():
    return create_engine(
        to_sync_postgres_dsn(get_database_url()),
        poolclass=NullPool,
        future=True,
    )


def _seed_old_policy_fit(engine, *, tenant_id: UUID, fit_id: UUID) -> None:
    with engine.begin() as conn:
        _set_tenant_context(conn, tenant_id)
        conn.execute(
            text(
                """
                INSERT INTO public.bayesian_model_fits (
                    tenant_id, id, model_type, model_version,
                    source_window_start, source_window_end, source_snapshot_hash,
                    source_read_started_at, source_read_completed_at,
                    status, eligibility_status, data_completeness_status,
                    fallback_applied, max_runtime_seconds, max_samples, max_cores,
                    inference_profile_version, runtime_policy_version,
                    sampling_policy_version, policy_bundle_hash,
                    authorized_chains, authorized_posterior_draws_total
                ) VALUES (
                    :tenant_id, :fit_id, :model_type, :model_version,
                    :window_start, :window_end, :snapshot_hash, now(), now(),
                    'queued', 'eligible', 'complete', false, 60, 160, 1,
                    'p13-c10-old-profile', 'p13-c10-old-runtime',
                    'p13-c10-old-sampling', :old_bundle_hash, 1, 80
                )
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "fit_id": str(fit_id),
                "model_type": B24_P6_MODEL_TYPE,
                "model_version": B24_P6_MODEL_VERSION,
                "window_start": START,
                "window_end": END,
                "snapshot_hash": "a" * 64,
                "old_bundle_hash": "1" * 64,
            },
        )


def _observed_input(tenant_id: UUID) -> P6SourceObservedInput:
    return P6SourceObservedInput(
        tenant_id=tenant_id,
        model_type=B24_P6_MODEL_TYPE,
        model_version=B24_P6_MODEL_VERSION,
        source_window_start=START,
        source_window_end=END,
        source_snapshot_hash="a" * 64,
        observed_signal=[0.15],
        observed_signal_version="b24-p6-source-observed-v1",
        streamed_chunk_count=1,
        streamed_source_row_count=1,
        source_amount_minor_total=100,
        deterministic_revenue_minor=100,
        deterministic_revenue_row_count=1,
        deterministic_match_verdict_count=1,
        deterministic_currency_count=1,
        resource_policy_version="b24-p4-resource-policy-v1",
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_c10_claimed_p1_is_explicitly_replanned_to_p2_before_compute(
    test_tenant_pair,
) -> None:
    """A queued old-policy fit records a fenced replan before sampler input."""

    tenant_id, _ = test_tenant_pair
    fit_id = uuid4()
    engine = _worker_engine()
    try:
        _seed_old_policy_fit(engine, tenant_id=tenant_id, fit_id=fit_id)

        # The policy tuple is worker authority, not mutable planner bookkeeping.
        with engine.begin() as conn:
            _set_tenant_context(conn, tenant_id)
            with pytest.raises(
                DBAPIError, match="b24_policy_replan_evidence_incomplete"
            ):
                conn.execute(
                    text(
                        "UPDATE public.bayesian_model_fits "
                        "SET policy_bundle_hash = :bundle "
                        "WHERE tenant_id = :tenant_id AND id = :fit_id"
                    ),
                    {
                        "bundle": B24_INFERENCE_PROFILE.policy_bundle_hash(),
                        "tenant_id": str(tenant_id),
                        "fit_id": str(fit_id),
                    },
                )

        with engine.begin() as conn:
            lease = _claim_test_dispatch_lease(
                conn,
                tenant_id=tenant_id,
                fit_id=fit_id,
                generation_id=f"p13-c10-replan-{uuid4().hex[:12]}",
                assignment_reason="p13_c10_policy_transition",
            )
            row = _load_fit_for_execution(
                conn,
                tenant_id=tenant_id,
                fit_id=fit_id,
                dispatch_lease=lease,
            )
            assert row is not None and row["policy_bundle_hash"] == "1" * 64
            replanned = _replan_superseded_policy_bundle(
                conn, tenant_id=tenant_id, fit_id=fit_id
            )
            assert replanned is not None
            row.update(replanned)
            sampler_input = _build_sampler_input(
                row,
                execution_id=f"p13-c10-{uuid4().hex}",
                observed_input=_observed_input(tenant_id),
            )

        assert replanned["superseded_policy_bundle_hash"] == "1" * 64
        assert (
            replanned["policy_bundle_hash"]
            == B24_INFERENCE_PROFILE.policy_bundle_hash()
        )
        assert replanned["policy_replanned_at"] is not None
        assert replanned["policy_replan_count"] == 1
        assert (
            sampler_input["max_samples"] == B24_INFERENCE_PROFILE.total_chain_iterations
        )
        assert sampler_input["max_cores"] == B24_INFERENCE_PROFILE.cores

        # A runtime/profile authority rejection is terminal, typed, and cannot
        # be disguised later by restating any persisted policy identity.
        with engine.begin() as conn:
            _mark_fit_failure(
                conn,
                tenant_id=tenant_id,
                fit_id=fit_id,
                status=FitStatus.FAILED,
                fallback_reason=FallbackReason.POLICY_REJECTED,
                dispatch_lease=lease,
            )
            fail_dispatch_terminal_sync(
                conn,
                lease=lease,
                reason=FallbackReason.POLICY_REJECTED.value,
            )
        with engine.begin() as conn:
            _set_tenant_context(conn, tenant_id)
            terminal = (
                conn.execute(
                    text(
                        "SELECT status, fallback_reason, confidence_bucket "
                        "FROM public.bayesian_model_fits "
                        "WHERE tenant_id = :tenant_id AND id = :fit_id"
                    ),
                    {"tenant_id": str(tenant_id), "fit_id": str(fit_id)},
                )
                .mappings()
                .one()
            )
            assert terminal == {
                "status": "failed",
                "fallback_reason": "policy_rejected",
                "confidence_bucket": "unavailable",
            }
            for column, hostile_value in (
                ("inference_profile_version", "'tampered-profile'"),
                ("runtime_policy_version", "'tampered-runtime'"),
                ("sampling_policy_version", "'tampered-sampling'"),
                ("diagnostic_policy_version", "'tampered-diagnostic'"),
                ("policy_bundle_hash", "repeat('f', 64)"),
                ("authorized_chains", "2"),
                ("authorized_posterior_draws_total", "2000"),
                ("superseded_policy_bundle_hash", "repeat('e', 64)"),
                ("policy_replanned_at", "now() + interval '1 hour'"),
                ("policy_replan_count", "2"),
            ):
                # Two governed guards can answer here, and which one does
                # depends on whether the column is also execution-authority
                # governed. diagnostic_policy_version is: it is stamped at claim
                # time with the rest of the policy bundle, so the C5 dispatch
                # fence sees the write first and refuses it before terminal
                # immutability is consulted. Both are correct refusals of the
                # same mutation, and pinning one of them would be pinning
                # trigger ordering rather than the property.
                #
                # The property is asserted directly instead: the mutation is
                # refused by a named governed guard, and the stored value is
                # unchanged afterwards.
                with pytest.raises(
                    DBAPIError,
                    match=(
                        "b24_terminal_fit_truth_immutable"
                        "|b24_dispatch_fence_rejected"
                        "|b24_policy_provenance_sampling_immutable"
                    ),
                ):
                    with conn.begin_nested():
                        conn.execute(
                            text(
                                "UPDATE public.bayesian_model_fits "
                                f"SET {column} = {hostile_value} "
                                "WHERE tenant_id = :tenant_id AND id = :fit_id"
                            ),
                            {"tenant_id": str(tenant_id), "fit_id": str(fit_id)},
                        )
                survived = (
                    conn.execute(
                        text(
                            f"SELECT {column} AS value "
                            "FROM public.bayesian_model_fits "
                            "WHERE tenant_id = :tenant_id AND id = :fit_id"
                        ),
                        {"tenant_id": str(tenant_id), "fit_id": str(fit_id)},
                    )
                    .mappings()
                    .one()
                )
                assert str(survived["value"]) not in {
                    "tampered-profile",
                    "tampered-runtime",
                    "tampered-sampling",
                    "tampered-diagnostic",
                    "f" * 64,
                    "e" * 64,
                }, (column, survived)
    finally:
        engine.dispose()


def _seed_fresh_dispatch(
    engine, *, tenant_id: UUID, fit_id: UUID, dispatch_id: UUID
) -> None:
    attempt_id = uuid4()
    with engine.begin() as conn:
        _set_tenant_context(conn, tenant_id)
        conn.execute(
            text(
                """
                INSERT INTO public.bayesian_model_fits (
                    tenant_id, id, model_type, model_version,
                    source_window_start, source_window_end, source_snapshot_hash,
                    source_read_started_at, source_read_completed_at,
                    status, eligibility_status, data_completeness_status,
                    fallback_applied, max_runtime_seconds, max_samples, max_cores,
                    inference_profile_version, runtime_policy_version,
                    sampling_policy_version, policy_bundle_hash,
                    authorized_chains, authorized_posterior_draws_total
                ) VALUES (
                    :tenant_id, :fit_id, :model_type, :model_version,
                    :window_start, :window_end, :snapshot_hash, now(), now(),
                    'queued', 'eligible', 'complete', false,
                    :runtime, :samples, :cores, :profile_version,
                    :runtime_version, :sampling_version, :bundle_hash,
                    :chains, :draws
                )
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "fit_id": str(fit_id),
                "model_type": B24_P6_MODEL_TYPE,
                "model_version": B24_P6_MODEL_VERSION,
                "window_start": START,
                "window_end": END,
                "snapshot_hash": "b" * 64,
                "runtime": B24_INFERENCE_PROFILE.fit_execution_budget_seconds,
                "samples": B24_INFERENCE_PROFILE.total_chain_iterations,
                "cores": B24_INFERENCE_PROFILE.cores,
                "profile_version": B24_INFERENCE_PROFILE.profile_version,
                "runtime_version": B24_INFERENCE_PROFILE.runtime_policy_version,
                "sampling_version": B24_INFERENCE_PROFILE.sampling_policy_version,
                "bundle_hash": B24_INFERENCE_PROFILE.policy_bundle_hash(),
                "chains": B24_INFERENCE_PROFILE.chains,
                "draws": B24_INFERENCE_PROFILE.posterior_draws_total,
            },
        )
        conn.execute(
            text(
                """
                INSERT INTO public.b24_fit_dispatch_outbox (
                    tenant_id, id, fit_id, dispatch_key, task_name, attempt_id,
                    payload_hash, status, next_attempt_at, next_recovery_at
                ) VALUES (
                    :tenant_id, :dispatch_id, :fit_id, :dispatch_key,
                    :task_name, :attempt_id, :payload_hash,
                    'pending', now(), now() + interval '1 hour'
                )
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "dispatch_id": str(dispatch_id),
                "fit_id": str(fit_id),
                "dispatch_key": f"p13-c10:{tenant_id}:{fit_id}",
                "task_name": BAYESIAN_FIT_EXECUTION_TASK,
                "attempt_id": str(attempt_id),
                "payload_hash": dispatch_payload_hash(fit_id=fit_id),
            },
        )


def test_c10_publisher_authority_cannot_be_self_asserted_by_app_user(
    test_tenant_pair,
) -> None:
    """The publisher GUC is effective only for the dedicated worker login."""

    tenant_id, _ = test_tenant_pair
    fit_id = uuid4()
    dispatch_id = uuid4()
    worker_engine = _worker_engine()
    runtime_url = make_url(to_sync_postgres_dsn(get_database_url())).set(
        username="app_user", password="app_user"
    )
    user_engine = create_engine(runtime_url, poolclass=NullPool, future=True)
    try:
        _seed_fresh_dispatch(
            worker_engine,
            tenant_id=tenant_id,
            fit_id=fit_id,
            dispatch_id=dispatch_id,
        )
        with user_engine.begin() as conn:
            conn.execute(
                text(
                    "SELECT set_config('app.b24_initial_dispatch_publisher', 'on', true)"
                )
            )
            visible = conn.execute(
                text(
                    "SELECT count(*) FROM public.b24_fit_dispatch_outbox "
                    "WHERE id = :dispatch_id"
                ),
                {"dispatch_id": str(dispatch_id)},
            ).scalar_one()
            assert visible == 0
    finally:
        user_engine.dispose()
        worker_engine.dispose()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_c10_live_beat_broker_worker_delivers_fresh_dispatch(
    test_tenant_pair,
    tmp_path: Path,
) -> None:
    """Beat -> publisher task -> broker wake-up -> real Bayesian worker."""

    from app.celery_app import celery_app
    from app.tasks.bayesian_publisher import DISPATCH_PUBLISHER_TASK_NAME

    tenant_id, _ = test_tenant_pair
    fit_id = uuid4()
    dispatch_id = uuid4()
    engine = _worker_engine()
    _seed_fresh_dispatch(
        engine, tenant_id=tenant_id, fit_id=fit_id, dispatch_id=dispatch_id
    )

    original_eager = celery_app.conf.task_always_eager
    celery_app.conf.task_always_eager = False
    worker_log = tmp_path / "c10_dispatch_worker.log"
    publisher_log = tmp_path / "c10_dispatch_publisher.log"
    beat_log = tmp_path / "c10_dispatch_beat.log"
    probe_log = tmp_path / "c10_dispatch_probe.jsonl"
    beat_schedule_db = tmp_path / "c10_celerybeat-schedule"
    worker_env = _worker_env(include_bayesian_tasks=True, log_path=probe_log)
    worker_env["B24_BAYESIAN_WORKSPACE_ROOT"] = str(tmp_path / "workspaces")
    worker_env["B24_PYTENSOR_ROOT"] = str(tmp_path / "compiledirs")
    publisher_env = _worker_env(include_bayesian_tasks=False, log_path=probe_log)
    publisher_url = os.environ["B24_DISPATCH_PUBLISHER_DATABASE_URL"]
    publisher_env["SKELDIR_CELERY_WORKER_ROLE"] = "bayesian_publisher"
    publisher_env.pop("SKELDIR_CELERY_INCLUDE_BAYESIAN_TASKS", None)
    publisher_env["DATABASE_URL"] = publisher_url
    publisher_env["B24_DISPATCH_PUBLISHER_DATABASE_URL"] = publisher_url
    publisher_env["CELERY_BROKER_URL"] = f"sqla+{publisher_url}"
    publisher_env["CELERY_RESULT_BACKEND"] = f"db+{publisher_url}"
    beat_env = _beat_env(log_path=probe_log, disable_recovery_schedule=True)
    beat_env["B24_FIT_PLANNER_INTERVAL_SECONDS"] = "1"
    beat_env["SKELDIR_B24_DISABLE_FIT_PLANNER_JOB"] = "1"
    beat_env.pop("SKELDIR_B24_DISABLE_FIT_DISPATCH_PUBLISHER_JOB", None)

    worker_handle = worker_log.open("w", encoding="utf-8", buffering=1)
    publisher_handle = publisher_log.open("w", encoding="utf-8", buffering=1)
    beat_handle = beat_log.open("w", encoding="utf-8", buffering=1)
    worker_process: subprocess.Popen[str] | None = None
    publisher_process: subprocess.Popen[str] | None = None
    beat_process: subprocess.Popen[str] | None = None
    try:
        baseline = _max_broker_message_id(engine)
        beat_process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "celery",
                "-A",
                "app.celery_app.celery_app",
                "beat",
                "--loglevel=INFO",
                "--pidfile=",
                "--schedule",
                str(beat_schedule_db),
            ],
            cwd=ROOT / "backend",
            env=beat_env,
            text=True,
            stdout=beat_handle,
            stderr=subprocess.STDOUT,
        )
        emitted = _wait_for_log(beat_log, PUBLISHER_BEAT_ENTRY, timeout_s=90)
        assert beat_process.poll() is None, emitted
        assert DISPATCH_PUBLISHER_TASK_NAME in emitted, emitted
        _wait_for_broker_task_messages(
            engine,
            task_name=DISPATCH_PUBLISHER_TASK_NAME,
            queue_name=QUEUE_BAYESIAN_PUBLISHER,
            after_message_id=baseline,
            timeout_s=60,
        )

        # Non-vacuity interval: Beat and broker alone cannot move the outbox.
        with engine.begin() as conn:
            _set_tenant_context(conn, tenant_id)
            assert (
                conn.execute(
                    text(
                        "SELECT status FROM public.b24_fit_dispatch_outbox "
                        "WHERE tenant_id = :tenant_id AND id = :dispatch_id"
                    ),
                    {"tenant_id": str(tenant_id), "dispatch_id": str(dispatch_id)},
                ).scalar_one()
                == "pending"
            )

        publisher_process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "celery",
                "-A",
                "app.celery_app.celery_app",
                "worker",
                "-P",
                "solo",
                "-c",
                "1",
                "-Q",
                QUEUE_BAYESIAN_PUBLISHER,
                "--loglevel=INFO",
                "--without-gossip",
                "--without-mingle",
                "--without-heartbeat",
            ],
            cwd=ROOT / "backend",
            env=publisher_env,
            text=True,
            stdout=publisher_handle,
            stderr=subprocess.STDOUT,
        )
        publisher_ready = _wait_for_log(publisher_log, " ready", timeout_s=120)
        assert publisher_process.poll() is None, publisher_ready
        published = _wait_for_probe_event_matching(
            probe_log,
            "bayesian_fresh_dispatch_published",
            predicate=lambda event: str(fit_id) in event.get("fit_ids", []),
            timeout_s=120,
        )
        assert str(dispatch_id) in published["dispatch_ids"], published

        worker_process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "celery",
                "-A",
                "app.celery_app.celery_app",
                "worker",
                "-P",
                "solo",
                "-c",
                "1",
                "-Q",
                QUEUE_BAYESIAN,
                "--loglevel=INFO",
                "--without-gossip",
                "--without-mingle",
                "--without-heartbeat",
            ],
            cwd=ROOT / "backend",
            env=worker_env,
            text=True,
            stdout=worker_handle,
            stderr=subprocess.STDOUT,
        )
        ready = _wait_for_log(worker_log, " ready", timeout_s=120)
        assert worker_process.poll() is None, ready
        executed = _wait_for_probe_event_matching(
            probe_log,
            "bayesian_fit_intent_executed",
            predicate=lambda event: event.get("fit_id") == str(fit_id),
            timeout_s=120,
        )
        assert executed["dispatch_id"] == str(dispatch_id), executed
    finally:
        celery_app.conf.task_always_eager = original_eager
        for process in (beat_process, publisher_process, worker_process):
            if process is not None:
                _terminate_worker(process)
        beat_handle.close()
        publisher_handle.close()
        worker_handle.close()
        engine.dispose()
