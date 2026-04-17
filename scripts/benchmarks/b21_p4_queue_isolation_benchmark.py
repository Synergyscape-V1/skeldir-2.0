#!/usr/bin/env python3
"""B2.1-P4 queue-isolation benchmark harness (real Celery queue-to-commit path)."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text

from app.celery_app import celery_app
from app.core.queues import QUEUE_ATTRIBUTION, QUEUE_BAYESIAN
from app.core.secrets import get_database_url
from app.main import app
from app.security.auth import AuthContext, get_auth_context
from app.tasks.authority import (
    AUTHORITY_ENVELOPE_HEADER,
    SystemAuthorityEnvelope,
    authority_envelope_payload,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class WorkerHandle:
    role: str
    queue_spec: str
    log_path: Path
    proc: subprocess.Popen[str]
    lines: list[str]
    _thread: threading.Thread
    _stream: Any

    def stop(self) -> None:
        if self.proc.poll() is None:
            self.proc.send_signal(signal.SIGTERM)
            try:
                self.proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=20)
        if self._stream is not None:
            try:
                self._stream.close()
            except Exception:
                pass


def _normalize_sync_database_url(value: str) -> str:
    if value.startswith("postgresql+asyncpg://"):
        return value.replace("postgresql+asyncpg://", "postgresql://", 1)
    return value


def _runtime_async_database_url() -> str:
    value = get_database_url()
    if value.startswith("postgresql://"):
        return value.replace("postgresql://", "postgresql+asyncpg://", 1)
    return value


def _runtime_sync_database_url() -> str:
    return _normalize_sync_database_url(_runtime_async_database_url())


def _celery_worker_env(*, async_url: str, sync_url: str) -> dict[str, str]:
    env = os.environ.copy()
    env["DATABASE_URL"] = async_url
    env["CELERY_BROKER_URL"] = f"sqla+{sync_url}"
    env["CELERY_RESULT_BACKEND"] = f"db+{sync_url}"
    env.setdefault("TESTING", "1")
    env.setdefault("CONTRACT_TESTING", "0")
    env.setdefault("ENVIRONMENT", "test")
    return env


def _wait_for_worker_ready(
    proc: subprocess.Popen[str], lines: list[str], timeout_s: float = 90.0
) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if any("ready." in line for line in lines):
            return
        if proc.poll() is not None:
            raise RuntimeError("Celery worker exited before readiness")
        time.sleep(0.2)
    raise RuntimeError("Timed out waiting for Celery worker readiness")


def _start_worker(
    *, role: str, queue_spec: str, env: dict[str, str], artifact_dir: Path
) -> WorkerHandle:
    backend_dir = REPO_ROOT / "backend"
    log_path = artifact_dir / f"{role}.worker.log"
    stream = log_path.open("w", encoding="utf-8")
    lines: list[str] = []
    worker_env = dict(env)
    prom_dir = (artifact_dir / "prometheus_multiproc" / role).resolve()
    prom_dir.mkdir(parents=True, exist_ok=True)
    worker_env["PROMETHEUS_MULTIPROC_DIR"] = str(prom_dir)
    cmd = [
        "celery",
        "-A",
        "app.celery_app.celery_app",
        "worker",
        "--hostname",
        f"b21p4-{role}@%h",
        "-P",
        "solo",
        "--concurrency",
        "1",
        "--prefetch-multiplier",
        "1",
        "--queues",
        queue_spec,
        "--loglevel",
        "INFO",
    ]
    proc = subprocess.Popen(
        cmd,
        cwd=str(backend_dir),
        env=worker_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    def _reader() -> None:
        if proc.stdout is None:
            return
        for raw in proc.stdout:
            line = raw.rstrip("\n")
            lines.append(line)
            stream.write(line + "\n")
            stream.flush()

    thread = threading.Thread(
        target=_reader, name=f"b21p4-{role}-worker-reader", daemon=True
    )
    thread.start()
    _wait_for_worker_ready(proc, lines)
    return WorkerHandle(
        role=role,
        queue_spec=queue_spec,
        log_path=log_path,
        proc=proc,
        lines=lines,
        _thread=thread,
        _stream=stream,
    )


def _assert_runtime_tables(sync_url: str) -> None:
    engine = create_engine(sync_url)
    required_tables = (
        "tenants",
        "channel_taxonomy",
        "session_authority",
        "attribution_events",
        "attribution_recompute_jobs",
        "attribution_allocations",
    )
    with engine.begin() as conn:
        for name in required_tables:
            present = conn.execute(
                text("SELECT to_regclass(:table_name)"),
                {"table_name": f"public.{name}"},
            ).scalar_one()
            if present is None:
                raise RuntimeError(f"benchmark requires table public.{name}")
    engine.dispose()


def _set_tenant_context(conn: Any, *, tenant_id: UUID) -> None:
    conn.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )


def _insert_tenant(conn: Any, *, tenant_id: UUID) -> None:
    columns = set(
        conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'tenants'"
            )
        ).scalars()
    )
    insert_cols = ["id", "name"]
    params = {
        "id": str(tenant_id),
        "name": f"B21 P4 Tenant {tenant_id.hex[:8]}",
        "api_key_hash": f"b21-p4-hash-{tenant_id.hex[:16]}",
        "notification_email": f"b21-p4-{tenant_id.hex[:8]}@example.invalid",
    }
    if "api_key_hash" in columns:
        insert_cols.append("api_key_hash")
    if "notification_email" in columns:
        insert_cols.append("notification_email")
    values = ", ".join(f":{col}" for col in insert_cols)
    conn.execute(
        text(
            f"INSERT INTO tenants ({', '.join(insert_cols)}) VALUES ({values}) ON CONFLICT (id) DO NOTHING"
        ),
        params,
    )


def _seed_channel_taxonomy(conn: Any, *, channels: list[str]) -> None:
    for channel in channels:
        conn.execute(
            text(
                """
                INSERT INTO channel_taxonomy (code, family, is_paid, display_name, is_active, state)
                VALUES (:code, 'b21_p4', false, :display_name, true, 'active')
                ON CONFLICT (code) DO NOTHING
                """
            ),
            {
                "code": channel,
                "display_name": channel.replace("_", " ").title(),
            },
        )


def _seed_session_authority(
    conn: Any,
    *,
    tenant_id: UUID,
    session_id: UUID,
    issued_at: datetime,
    expires_at: datetime,
) -> None:
    conn.execute(
        text(
            """
            INSERT INTO session_authority (
                id,
                tenant_id,
                session_id,
                issued_at,
                expires_at,
                last_seen_at,
                invalidated_at,
                invalidation_reason,
                issued_by,
                created_at,
                updated_at
            ) VALUES (
                :id,
                :tenant_id,
                :session_id,
                :issued_at,
                :expires_at,
                :last_seen_at,
                NULL,
                NULL,
                'b21_p4_benchmark',
                :created_at,
                :updated_at
            )
            ON CONFLICT (tenant_id, session_id)
            DO UPDATE SET
                issued_at = EXCLUDED.issued_at,
                expires_at = EXCLUDED.expires_at,
                last_seen_at = EXCLUDED.last_seen_at,
                invalidated_at = NULL,
                invalidation_reason = NULL,
                updated_at = EXCLUDED.updated_at
            """
        ),
        {
            "id": str(
                uuid5(
                    NAMESPACE_URL, f"b21_p4:session_authority:{tenant_id}:{session_id}"
                )
            ),
            "tenant_id": str(tenant_id),
            "session_id": str(session_id),
            "issued_at": issued_at,
            "expires_at": expires_at,
            "last_seen_at": issued_at + timedelta(minutes=1),
            "created_at": issued_at,
            "updated_at": issued_at,
        },
    )


def _event_rows(
    *,
    tenant_id: UUID,
    session_id: UUID,
    window_start: datetime,
    total_events: int,
    channels: list[str],
) -> list[dict[str, Any]]:
    if total_events < 2 or total_events % 2 != 0:
        raise ValueError("total_events must be an even integer >= 2")

    rows: list[dict[str, Any]] = []
    conversions = total_events // 2
    for idx in range(conversions):
        channel = channels[idx % len(channels)]
        touch_at = window_start + timedelta(seconds=idx * 2)
        conversion_at = touch_at + timedelta(seconds=1)

        touch_event_id = uuid5(NAMESPACE_URL, f"b21_p4:touch:{tenant_id}:{idx}")
        conversion_event_id = uuid5(
            NAMESPACE_URL, f"b21_p4:conversion:{tenant_id}:{idx}"
        )

        touch_payload = {
            "id": str(touch_event_id),
            "tenant_id": str(tenant_id),
            "occurred_at": touch_at,
            "external_event_id": f"touch-{touch_event_id.hex[:16]}",
            "correlation_id": str(
                uuid5(NAMESPACE_URL, f"b21_p4:touch:corr:{tenant_id}:{idx}")
            ),
            "session_id": str(session_id),
            "revenue_cents": 0,
            "raw_payload": json.dumps(
                {"global_idempotency_hash": touch_event_id.hex.ljust(64, "0")[:64]}
            ),
            "idempotency_key": f"b21-p4-touch-{tenant_id.hex[:8]}-{idx}",
            "event_type": "ad_click",
            "channel": channel,
            "campaign_id": "cmp-b21-p4",
            "conversion_value_cents": 0,
            "event_timestamp": touch_at,
            "processed_at": touch_at + timedelta(milliseconds=500),
            "created_at": touch_at,
            "updated_at": touch_at,
        }
        conversion_payload = {
            "id": str(conversion_event_id),
            "tenant_id": str(tenant_id),
            "occurred_at": conversion_at,
            "external_event_id": f"conv-{conversion_event_id.hex[:16]}",
            "correlation_id": str(
                uuid5(NAMESPACE_URL, f"b21_p4:conv:corr:{tenant_id}:{idx}")
            ),
            "session_id": str(session_id),
            "revenue_cents": 100,
            "raw_payload": json.dumps(
                {"global_idempotency_hash": conversion_event_id.hex.ljust(64, "0")[:64]}
            ),
            "idempotency_key": f"b21-p4-conv-{tenant_id.hex[:8]}-{idx}",
            "event_type": "purchase",
            "channel": channel,
            "campaign_id": "cmp-b21-p4",
            "conversion_value_cents": 100,
            "event_timestamp": conversion_at,
            "processed_at": conversion_at + timedelta(milliseconds=500),
            "created_at": conversion_at,
            "updated_at": conversion_at,
        }
        rows.append(touch_payload)
        rows.append(conversion_payload)
    return rows


def _seed_fixture(
    *,
    sync_url: str,
    tenant_id: UUID,
    session_id: UUID,
    window_start: datetime,
    window_end: datetime,
    total_events: int,
    channels: list[str],
) -> None:
    engine = create_engine(sync_url)
    event_insert = text(
        """
        INSERT INTO attribution_events (
            id,
            tenant_id,
            occurred_at,
            external_event_id,
            correlation_id,
            session_id,
            revenue_cents,
            raw_payload,
            idempotency_key,
            event_type,
            channel,
            campaign_id,
            conversion_value_cents,
            currency,
            event_timestamp,
            processed_at,
            processing_status,
            retry_count,
            created_at,
            updated_at
        ) VALUES (
            :id,
            :tenant_id,
            :occurred_at,
            :external_event_id,
            :correlation_id,
            :session_id,
            :revenue_cents,
            CAST(:raw_payload AS jsonb),
            :idempotency_key,
            :event_type,
            :channel,
            :campaign_id,
            :conversion_value_cents,
            'USD',
            :event_timestamp,
            :processed_at,
            'processed',
            0,
            :created_at,
            :updated_at
        )
        ON CONFLICT (tenant_id, idempotency_key) DO NOTHING
        """
    )

    rows = _event_rows(
        tenant_id=tenant_id,
        session_id=session_id,
        window_start=window_start,
        total_events=total_events,
        channels=channels,
    )

    with engine.begin() as conn:
        conn.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
            {"tenant_id": str(tenant_id)},
        )
        _insert_tenant(conn, tenant_id=tenant_id)
        _seed_channel_taxonomy(conn, channels=channels)
        _seed_session_authority(
            conn,
            tenant_id=tenant_id,
            session_id=session_id,
            issued_at=window_start - timedelta(hours=1),
            expires_at=window_end + timedelta(hours=2),
        )

        chunk_size = 1000
        for index in range(0, len(rows), chunk_size):
            conn.execute(event_insert, rows[index : index + chunk_size])

    engine.dispose()


async def _read_path_probe(
    *,
    sync_url: str,
    tenant_id: UUID,
    recompute_job_id: UUID,
    model_type: str,
) -> dict[str, Any]:
    engine = create_engine(sync_url)
    with engine.begin() as conn:
        _set_tenant_context(conn, tenant_id=tenant_id)
        before = (
            conn.execute(
                text(
                    """
                SELECT
                    COUNT(*)::bigint AS row_count,
                    COALESCE(SUM(run_count), 0)::bigint AS run_count_sum
                FROM attribution_recompute_jobs
                WHERE tenant_id = :tenant_id
                """
                ),
                {"tenant_id": str(tenant_id)},
            )
            .mappings()
            .one()
        )

    now_epoch = int(datetime.now(timezone.utc).timestamp())
    auth = AuthContext(
        tenant_id=tenant_id,
        user_id=uuid5(NAMESPACE_URL, f"b21_p4:user:{tenant_id}"),
        jti=uuid4(),
        issued_at_epoch=now_epoch,
        subject=str(uuid5(NAMESPACE_URL, f"b21_p4:subject:{tenant_id}")),
        issuer="https://issuer.skeldir.test",
        audience="skeldir-api",
        claims={"role": "viewer", "roles": ["viewer"], "scopes": ["viewer"]},
    )

    async def _override_auth_context() -> AuthContext:
        return auth

    app.dependency_overrides[get_auth_context] = _override_auth_context
    response_payload: dict[str, Any] = {}
    status_code = 0
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.get(
                "/api/attribution/channels",
                params={
                    "model_type": model_type,
                    "recompute_job_id": str(recompute_job_id),
                },
                headers={"X-Correlation-ID": str(uuid4())},
            )
            status_code = int(response.status_code)
            try:
                response_payload = response.json()
            except Exception:
                response_payload = {"non_json_body": response.text}
    finally:
        app.dependency_overrides.pop(get_auth_context, None)

    with engine.begin() as conn:
        _set_tenant_context(conn, tenant_id=tenant_id)
        after = (
            conn.execute(
                text(
                    """
                SELECT
                    COUNT(*)::bigint AS row_count,
                    COALESCE(SUM(run_count), 0)::bigint AS run_count_sum
                FROM attribution_recompute_jobs
                WHERE tenant_id = :tenant_id
                """
                ),
                {"tenant_id": str(tenant_id)},
            )
            .mappings()
            .one()
        )
    engine.dispose()

    before_rows = int(before["row_count"])
    before_runs = int(before["run_count_sum"])
    after_rows = int(after["row_count"])
    after_runs = int(after["run_count_sum"])
    recompute_mutation_detected = (after_rows != before_rows) or (
        after_runs != before_runs
    )

    return {
        "endpoint": "/api/attribution/channels",
        "status_code": status_code,
        "projection_recompute_job_id": str(
            response_payload.get("projection", {}).get("recompute_job_id", "")
        ),
        "recompute_row_count_before": before_rows,
        "recompute_row_count_after": after_rows,
        "run_count_before": before_runs,
        "run_count_after": after_runs,
        "recompute_mutation_detected": recompute_mutation_detected,
    }


def _active_queues_snapshot(timeout_s: float = 10.0) -> dict[str, Any]:
    inspect = celery_app.control.inspect(timeout=timeout_s)
    payload = inspect.active_queues() or {}
    normalized: dict[str, Any] = {}
    for worker_name, queues in payload.items():
        if not isinstance(queues, list):
            normalized[str(worker_name)] = queues
            continue
        normalized[str(worker_name)] = [
            {
                "name": str(item.get("name")),
                "routing_key": str(item.get("routing_key")),
            }
            for item in queues
            if isinstance(item, dict)
        ]
    return normalized


def _runtime_benchmark(
    *,
    output_path: Path,
    artifact_dir: Path,
    event_count: int,
    threshold_seconds: float,
    topology_mode: str,
    contention_mode: str,
    contention_duration_seconds: int,
) -> dict[str, Any]:
    async_url = _runtime_async_database_url()
    sync_url = _runtime_sync_database_url()

    _assert_runtime_tables(sync_url)

    tenant_id = uuid5(NAMESPACE_URL, f"b21_p4:tenant:{uuid4()}")
    session_id = uuid5(NAMESPACE_URL, f"b21_p4:session:{tenant_id}")
    window_start = datetime.now(timezone.utc) - timedelta(hours=2)
    window_end = window_start + timedelta(hours=4)
    channels = ["email", "google_search_paid", "direct"]

    _seed_fixture(
        sync_url=sync_url,
        tenant_id=tenant_id,
        session_id=session_id,
        window_start=window_start,
        window_end=window_end,
        total_events=event_count,
        channels=channels,
    )

    worker_env = _celery_worker_env(async_url=async_url, sync_url=sync_url)
    handles: list[WorkerHandle] = []

    try:
        if topology_mode == "isolated":
            handles.append(
                _start_worker(
                    role="deterministic",
                    queue_spec=QUEUE_ATTRIBUTION,
                    env=worker_env,
                    artifact_dir=artifact_dir,
                )
            )
            handles.append(
                _start_worker(
                    role="bayesian",
                    queue_spec=QUEUE_BAYESIAN,
                    env=worker_env,
                    artifact_dir=artifact_dir,
                )
            )
        elif topology_mode == "corouted_shared_worker":
            handles.append(
                _start_worker(
                    role="shared",
                    queue_spec=f"{QUEUE_ATTRIBUTION},{QUEUE_BAYESIAN}",
                    env=worker_env,
                    artifact_dir=artifact_dir,
                )
            )
        else:
            raise ValueError(f"unsupported topology_mode: {topology_mode}")

        active_queues = _active_queues_snapshot()

        bayes_task_id = f"b21-p4-bayes-{uuid4().hex[:10]}"
        bayes_kwargs: dict[str, Any] = {
            "tenant_id": str(tenant_id),
            "correlation_id": str(uuid4()),
        }
        if contention_mode == "real":
            bayes_task_name = "app.tasks.bayesian.run_resource_contention"
            bayes_kwargs.update(
                {
                    "run_seconds": int(contention_duration_seconds),
                    "cpu_cycles_per_iteration": 25000,
                    "db_round_trips_per_iteration": 3,
                }
            )
        elif contention_mode == "fake_sleep":
            bayes_task_name = "app.tasks.bayesian.run_mcmc_inference"
            bayes_kwargs.update(
                {
                    "run_seconds": int(contention_duration_seconds),
                    "continue_after_soft_timeout": False,
                }
            )
        else:
            raise ValueError(f"unsupported contention_mode: {contention_mode}")

        bayes_async_result = celery_app.send_task(
            bayes_task_name,
            kwargs=bayes_kwargs,
            task_id=bayes_task_id,
            queue=QUEUE_BAYESIAN,
        )

        time.sleep(0.3)

        deterministic_task_id = f"b21-p4-attr-{uuid4().hex[:10]}"
        deterministic_headers = {
            AUTHORITY_ENVELOPE_HEADER: authority_envelope_payload(
                SystemAuthorityEnvelope(tenant_id=tenant_id)
            )
        }
        deterministic_kwargs = {
            "window_start": window_start.isoformat().replace("+00:00", "Z"),
            "window_end": window_end.isoformat().replace("+00:00", "Z"),
            "session_id": str(session_id),
            "correlation_id": str(uuid4()),
            "model_version": "b21_p4_queue_isolation_benchmark",
            "model_type": "deterministic_baseline",
            "lookback_days": 30,
        }

        stopwatch_started_at = time.perf_counter()
        deterministic_async_result = celery_app.send_task(
            "app.tasks.attribution.recompute_window",
            kwargs=deterministic_kwargs,
            headers=deterministic_headers,
            task_id=deterministic_task_id,
            queue=QUEUE_ATTRIBUTION,
        )
        deterministic_payload = deterministic_async_result.get(timeout=240)

        job_id = UUID(str(deterministic_payload["job_id"]))
        runtime_engine = create_engine(sync_url)
        with runtime_engine.begin() as conn:
            _set_tenant_context(conn, tenant_id=tenant_id)
            job_row = (
                conn.execute(
                    text(
                        """
                    SELECT status, run_count, finished_at
                    FROM attribution_recompute_jobs
                    WHERE tenant_id = :tenant_id
                      AND id = :job_id
                    """
                    ),
                    {"tenant_id": str(tenant_id), "job_id": str(job_id)},
                )
                .mappings()
                .first()
            )
            allocation_count = int(
                conn.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM attribution_allocations
                        WHERE tenant_id = :tenant_id
                          AND recompute_job_id = :job_id
                        """
                    ),
                    {"tenant_id": str(tenant_id), "job_id": str(job_id)},
                ).scalar_one()
            )
        runtime_engine.dispose()

        stopwatch_elapsed_seconds = time.perf_counter() - stopwatch_started_at

        bayes_result_payload: dict[str, Any] = {}
        bayes_error = ""
        try:
            bayes_result_payload = bayes_async_result.get(timeout=240)
        except Exception as exc:  # pragma: no cover
            bayes_error = f"{exc.__class__.__name__}:{exc}"

        read_path_payload = asyncio.run(
            _read_path_probe(
                sync_url=sync_url,
                tenant_id=tenant_id,
                recompute_job_id=job_id,
                model_type="deterministic_baseline",
            )
        )

        summary: dict[str, Any] = {
            "schema_version": "b21_p4_queue_isolation_benchmark.v1",
            "mode": "measure",
            "topology_mode": topology_mode,
            "contention_mode": contention_mode,
            "timing_boundary": "enqueue_to_durable_commit",
            "dispatch_mode": "celery_send_task",
            "task_always_eager": bool(celery_app.conf.task_always_eager),
            "broker_url": str(celery_app.conf.broker_url),
            "result_backend": str(celery_app.conf.result_backend),
            "event_count": int(event_count),
            "threshold_seconds": float(threshold_seconds),
            "deterministic": {
                "task_name": "app.tasks.attribution.recompute_window",
                "task_id": deterministic_task_id,
                "elapsed_seconds": stopwatch_elapsed_seconds,
                "job_id": str(job_id),
                "job_status": str((job_row or {}).get("status", "")),
                "job_run_count": int((job_row or {}).get("run_count", 0)),
                "job_finished_at": str((job_row or {}).get("finished_at", "")),
                "allocation_count": allocation_count,
                "result_payload": deterministic_payload,
            },
            "contention": {
                "task_name": bayes_task_name,
                "task_id": bayes_task_id,
                "result": bayes_result_payload,
                "error": bayes_error,
            },
            "read_path": read_path_payload,
            "topology": {
                "worker_queue_specs": [
                    {
                        "role": handle.role,
                        "queues": handle.queue_spec,
                        "log_path": str(handle.log_path),
                    }
                    for handle in handles
                ],
                "active_queues": active_queues,
            },
            "adjudication_hints": {
                "isolated_sla_pass": stopwatch_elapsed_seconds
                < float(threshold_seconds),
                "recompute_commit_verified": bool(
                    job_row and str(job_row.get("status", "")).lower() == "succeeded"
                ),
                "read_path_recompute_free": not bool(
                    read_path_payload["recompute_mutation_detected"]
                ),
            },
        }

        output_path.write_text(
            json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
        )
        return summary
    finally:
        for handle in handles:
            handle.stop()


def _integrity_report(*, output_path: Path) -> dict[str, Any]:
    routes = celery_app.conf.task_routes
    route_attr = (
        routes.get("app.tasks.attribution.*", {}) if isinstance(routes, dict) else {}
    )
    route_bayes = (
        routes.get("app.tasks.bayesian.*", {}) if isinstance(routes, dict) else {}
    )
    report = {
        "schema_version": "b21_p4_queue_isolation_benchmark.v1",
        "mode": "integrity",
        "task_always_eager": bool(celery_app.conf.task_always_eager),
        "broker_url": str(celery_app.conf.broker_url),
        "result_backend": str(celery_app.conf.result_backend),
        "routes": {
            "app.tasks.attribution.*": route_attr,
            "app.tasks.bayesian.*": route_bayes,
        },
    }
    output_path.write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    return report


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="B2.1-P4 queue isolation benchmark harness"
    )
    parser.add_argument("--mode", choices=("integrity", "measure"), required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--artifact-dir", default="artifacts/b21_p4_benchmark")
    parser.add_argument("--event-count", type=int, default=10000)
    parser.add_argument("--threshold-seconds", type=float, default=5.0)
    parser.add_argument(
        "--topology-mode",
        choices=("isolated", "corouted_shared_worker"),
        default="isolated",
    )
    parser.add_argument(
        "--contention-mode",
        choices=("real", "fake_sleep"),
        default="real",
    )
    parser.add_argument("--contention-duration-seconds", type=int, default=7)
    args = parser.parse_args(argv[1:])

    output_path = (REPO_ROOT / args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_dir = (REPO_ROOT / args.artifact_dir).resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)

    try:
        if args.mode == "integrity":
            _integrity_report(output_path=output_path)
            return 0

        _runtime_benchmark(
            output_path=output_path,
            artifact_dir=artifact_dir,
            event_count=int(args.event_count),
            threshold_seconds=float(args.threshold_seconds),
            topology_mode=str(args.topology_mode),
            contention_mode=str(args.contention_mode),
            contention_duration_seconds=int(args.contention_duration_seconds),
        )
        return 0
    except Exception as exc:  # pragma: no cover
        payload = {
            "schema_version": "b21_p4_queue_isolation_benchmark.v1",
            "mode": args.mode,
            "result": "FAIL",
            "error_class": exc.__class__.__name__,
            "error": str(exc),
        }
        output_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main(list(os.sys.argv)))
