"""C8 real scheduler-transport proof for the B2.4 fit planner.

C7 recorded this gate as PARTIAL and said so plainly: the planner proof invoked
the registered task through ``.run()``, which proves task logic and registration
but not delivery. Both independent audits made it the dispositive finding.

The transport substrate already existed -- the B2.4-P9 live-Beat harness runs a
real ``celery beat``, a real non-memory broker and a real ``celery worker -Q
bayesian`` subprocess, and proves the recovery reconciler travels that path. What
was missing was one line of causal binding: the reconciler's Beat entry and the
planner's Beat entry are declared separately, with their own interval, their own
``expires`` computation and their own ``kwargs`` payload, so a proof of one is
architecturally adjacent to but not evidence for the other.

This module closes that binding for ``b24-fit-planner`` specifically, and it
does so with a negative interval: Beat and broker running with no Bayesian
worker must leave the durable obligation untouched, and starting the worker must
advance it. Without that interval, a passing test cannot distinguish transport
from a planner that happened to run some other way.
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from app.bayesian.model_identity import active_identity
from app.core.queues import QUEUE_BAYESIAN
from app.core.secrets import get_database_url
from app.db.dsn import to_sync_postgres_dsn
from app.tasks.bayesian import FIT_PLANNER_TASK_NAME
from tests.test_b24_p9_postgres_runtime import (
    _beat_env,
    _max_broker_message_id,
    _read_log,
    _terminate_worker,
    _wait_for_broker_task_messages,
    _wait_for_log,
    _wait_for_probe_event,
    _worker_env,
)


pytestmark = pytest.mark.skipif(
    os.getenv("SKELDIR_B25_P13_C8_TRANSPORT_PROOF") != "1",
    reason="B2.5-P13 C8 live transport proof is opt-in locally",
)

ROOT = Path(__file__).resolve().parents[3]
PLANNER_BEAT_ENTRY = "b24-fit-planner"
_ACTIVE = active_identity()


def _worker_engine():
    """The wake-up ledger is readable only by the worker identity (FORCE RLS)."""

    return create_engine(
        to_sync_postgres_dsn(get_database_url()), pool_pre_ping=True, future=True
    )


def _seed_engine():
    """Seeding tenants requires the migration principal, not the worker login."""

    url = os.environ.get("MIGRATION_DATABASE_URL") or get_database_url()
    return create_engine(to_sync_postgres_dsn(url), pool_pre_ping=True, future=True)


def _seed_due_obligation(engine) -> uuid.UUID:
    """One tenant with a debounce-mature dirty event and its durable wake-up.

    Seeded through the ordinary dirty-event path so the wake-up is produced by
    the production trigger rather than written directly.
    """

    tenant_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO public.tenants (id, name, api_key_hash,"
                " notification_email) VALUES (:id, :name, :hash, :email)"
            ),
            {
                "id": str(tenant_id),
                "name": f"c8-transport-{tenant_id.hex[:8]}",
                "hash": uuid.uuid4().hex,
                "email": f"c8-{tenant_id.hex[:8]}@example.test",
            },
        )
        conn.execute(
            text("SELECT set_config('app.current_tenant_id', :t, false)"),
            {"t": str(tenant_id)},
        )
        conn.execute(
            text(
                "INSERT INTO public.b24_dirty_events (tenant_id, model_type,"
                " model_version, source_window_start, source_window_end,"
                " dirty_reason, source_family, observed_at, status) VALUES"
                " (:t, :mt, :mv, timestamptz '2026-07-01',"
                " timestamptz '2026-07-02', 'c8_transport_probe',"
                " 'b23_revenue_events', now() - interval '600 seconds', 'pending')"
            ),
            {
                "t": str(tenant_id),
                "mt": _ACTIVE.model_type,
                "mv": _ACTIVE.model_version,
            },
        )
    return tenant_id


def _wakeup_state(engine, tenant_id: uuid.UUID):
    with engine.connect() as conn:
        return conn.execute(
            text(
                "SELECT status, lease_owner IS NOT NULL AS leased"
                " FROM public.b24_fit_planner_wakeups WHERE tenant_id = :t"
            ),
            {"t": str(tenant_id)},
        ).all()



def test_c8_live_beat_broker_worker_delivers_fit_planner(tmp_path) -> None:
    """Beat -> broker -> bayesian queue -> Bayesian worker -> planner, observed.

    Every edge is asserted from an artefact only that edge can produce: the Beat
    scheduler log for emission, broker rows for routing, and a probe record
    written from inside the task body for execution and database identity.
    """

    from app.celery_app import celery_app

    engine = _worker_engine()
    seed_engine = _seed_engine()
    original_eager = celery_app.conf.task_always_eager
    celery_app.conf.task_always_eager = False

    worker_log = tmp_path / "c8_planner_worker.log"
    beat_log = tmp_path / "c8_planner_beat.log"
    probe_log = tmp_path / "c8_planner_probe.jsonl"
    beat_schedule_db = tmp_path / "c8_celerybeat-schedule"

    worker_env = _worker_env(include_bayesian_tasks=True, log_path=probe_log)
    worker_env["B24_BAYESIAN_WORKSPACE_ROOT"] = str(tmp_path / "workspaces")
    worker_env["B24_PYTENSOR_ROOT"] = str(tmp_path / "compiledirs")

    # Beat must emit the planner entry quickly, and must NOT emit the sibling
    # reconciler -- otherwise a green result could be inherited from the entry
    # that was already proven rather than earned by this one.
    beat_env = _beat_env(log_path=probe_log, disable_recovery_schedule=True)
    beat_env["B24_FIT_PLANNER_INTERVAL_SECONDS"] = "1"
    beat_env["B24_FIT_PLANNER_TENANT_BATCH_SIZE"] = "5"
    beat_env["B24_FIT_PLANNER_CANDIDATE_LIMIT"] = "5"
    beat_env.pop("SKELDIR_B24_DISABLE_FIT_PLANNER_JOB", None)

    worker_handle = worker_log.open("w", encoding="utf-8", buffering=1)
    beat_handle = beat_log.open("w", encoding="utf-8", buffering=1)
    worker_process: subprocess.Popen[str] | None = None
    beat_process: subprocess.Popen[str] | None = None

    try:
        broker_url = str(celery_app.conf.broker_url)
        assert "postgresql://" in broker_url, broker_url
        assert "memory://" not in broker_url, broker_url
        assert celery_app.conf.task_always_eager is False

        tenant_id = _seed_due_obligation(seed_engine)
        seeded = _wakeup_state(engine, tenant_id)
        assert len(seeded) == 1 and seeded[0][0] == "pending", seeded

        # --- Beat + broker, deliberately WITHOUT a Bayesian worker ------------
        baseline_message_id = _max_broker_message_id(engine)
        beat_process = subprocess.Popen(
            [
                sys.executable, "-m", "celery",
                "-A", "app.celery_app.celery_app", "beat",
                "--loglevel=INFO", "--pidfile=",
                "--schedule", str(beat_schedule_db),
            ],
            cwd=ROOT / "backend",
            env=beat_env,
            text=True,
            stdout=beat_handle,
            stderr=subprocess.STDOUT,
        )
        emission_log = _wait_for_log(beat_log, PLANNER_BEAT_ENTRY, timeout_s=90)
        beat_handle.flush()
        assert beat_process.poll() is None, emission_log
        assert PLANNER_BEAT_ENTRY in emission_log, emission_log
        assert FIT_PLANNER_TASK_NAME in emission_log, emission_log

        planner_messages = _wait_for_broker_task_messages(
            engine,
            task_name=FIT_PLANNER_TASK_NAME,
            queue_name=QUEUE_BAYESIAN,
            after_message_id=baseline_message_id,
            timeout_s=60,
        )
        assert planner_messages, "Beat emitted no planner message onto the broker"
        assert {str(row["queue_name"]) for row in planner_messages} == {QUEUE_BAYESIAN}

        # The negative interval. Messages are on the broker and nothing consumes
        # them, so the durable obligation must not move.
        undelivered = _wakeup_state(engine, tenant_id)
        assert undelivered and undelivered[0][0] == "pending", undelivered
        assert not probe_log.exists() or "b24_fit_planner_beat_delivery" not in (
            _read_log(probe_log)
        ), "planner executed with no Bayesian worker running"

        # --- Start the Bayesian worker; the same obligation must advance ------
        worker_process = subprocess.Popen(
            [
                sys.executable, "-m", "celery",
                "-A", "app.celery_app.celery_app", "worker",
                "-P", "solo", "-c", "1", "-Q", QUEUE_BAYESIAN,
                "--loglevel=INFO",
                "--without-gossip", "--without-mingle", "--without-heartbeat",
            ],
            cwd=ROOT / "backend",
            env=worker_env,
            text=True,
            stdout=worker_handle,
            stderr=subprocess.STDOUT,
        )
        ready_log = _wait_for_log(worker_log, " ready", timeout_s=120)
        worker_handle.flush()
        assert worker_process.poll() is None, ready_log
        assert f".> {QUEUE_BAYESIAN}" in ready_log, ready_log

        delivery = _wait_for_probe_event(
            probe_log, "b24_fit_planner_beat_delivery", timeout_s=120
        )
        # Only the task body can write this, and only a worker holding the
        # dedicated login can have produced it: b24_due_fit_planner_tenants
        # raises unless session_user is app_worker.
        assert delivery["task_name"] == FIT_PLANNER_TASK_NAME
        assert delivery["database_user"] == "app_worker", delivery
        assert delivery["status"] == "completed"
        assert str(delivery["delivery_info"]).find(QUEUE_BAYESIAN) >= 0, delivery
    finally:
        celery_app.conf.task_always_eager = original_eager
        for process in (beat_process, worker_process):
            if process is not None:
                _terminate_worker(process)
        beat_handle.close()
        worker_handle.close()
        engine.dispose()
        seed_engine.dispose()
