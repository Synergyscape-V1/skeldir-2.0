import os
import sys
import time
import subprocess
import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
import httpx
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.engine.url import make_url

# B0.5.2: Set env BEFORE importing app modules
# H1 fix: Align credentials with CI provisioning (app_user:app_user, not skeldir:skeldir_ci_validation)
DEFAULT_SYNC_DSN = os.environ.get("TEST_SYNC_DSN", "postgresql://app_user:app_user@localhost:5432/skeldir_validation")
DEFAULT_ASYNC_DSN = os.environ.get("TEST_ASYNC_DSN", "postgresql+asyncpg://app_user:app_user@localhost:5432/skeldir_validation")
os.environ.setdefault("DATABASE_URL", DEFAULT_ASYNC_DSN)
os.environ.setdefault("CELERY_BROKER_URL", f"sqla+{DEFAULT_SYNC_DSN}")
os.environ.setdefault("CELERY_RESULT_BACKEND", f"db+{DEFAULT_SYNC_DSN}")
os.environ.setdefault("CELERY_METRICS_PORT", os.environ.get("CELERY_METRICS_PORT", "9546"))
os.environ.setdefault("CELERY_METRICS_ADDR", "127.0.0.1")

from app.celery_app import celery_app, _build_broker_url, _build_result_backend  # noqa: E402
from app.tasks.housekeeping import ping  # noqa: E402
from app.tasks.maintenance import scan_for_pii_contamination_task  # noqa: E402
from app.tasks.llm import llm_routing_worker  # noqa: E402
from app.main import app  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.observability.logging_config import configure_logging  # noqa: E402


def _wait_for_worker(timeout: int = 60) -> None:
    """
    Wait for worker readiness using data-plane task execution.

    Control-plane ping (celery_app.control.ping) is unsupported by Kombu's
    SQLAlchemy transport over Postgres - it returns [] even when the worker
    is operational. Use data-plane task round-trip as readiness proof instead.
    """
    import logging

    logger = logging.getLogger(__name__)
    broker = celery_app.conf.broker_url
    backend = celery_app.conf.result_backend
    queues = [q.name for q in celery_app.conf.task_queues or []]
    logger.warning(
        "[readiness-debug] broker=%s result_backend=%s queues=%s app=%s",
        broker,
        backend,
        queues,
        celery_app.main,
    )

    async def _result_row_exists(task_id: str) -> bool:
        async with engine.begin() as conn:
            row = await conn.execute(
                text(
                    "SELECT status FROM celery_taskmeta WHERE task_id = :tid"
                ),
                {"tid": task_id},
            )
            rec = row.first()
            return bool(rec)

    deadline = time.time() + timeout
    last_exc: Exception | None = None
    while time.time() < deadline:
        try:
            # Data-plane readiness: enqueue task to housekeeping queue
            result = ping.delay()
            logger.warning("[readiness-debug] published ping task_id=%s", result.id)
            # Block until task completes or 10s timeout
            result.get(timeout=10)
            logger.warning(
                "[readiness-debug] ping task_id=%s completed via result backend", result.id
            )
            # Success: worker consumed from broker and persisted to result backend
            return
        except Exception as exc:
            last_exc = exc
            # Worker not ready yet, retry after checking DB for persisted result
            try:
                if asyncio.run(_result_row_exists(result.id)):
                    logger.warning(
                        "[readiness-debug] ping task_id=%s persisted despite get() error (%s); treating as ready",
                        result.id,
                        exc,
                    )
                    return
            except Exception as db_exc:
                logger.warning(
                    "[readiness-debug] DB probe failed for task_id=%s: %s",
                    result.id,
                    db_exc,
                )
            logger.warning("[readiness-debug] ping attempt failed (%s); retrying...", exc)
        time.sleep(2)
    raise RuntimeError(
        f"Celery worker not ready: data-plane task execution failed (last_error={last_exc}, broker={broker}, backend={backend})"
    )


@pytest.fixture(scope="session")
def celery_worker_proc():
    """
    Spawn a real Celery worker (solo) for broker/result backend validation.
    """
    backend_dir = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(backend_dir.parent)
    env.setdefault("CELERY_METRICS_PORT", os.environ["CELERY_METRICS_PORT"])
    env.setdefault("CELERY_METRICS_ADDR", os.environ["CELERY_METRICS_ADDR"])
    cmd = [
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
        "--loglevel=INFO",
    ]
    proc = subprocess.Popen(
        cmd,
        cwd=backend_dir,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        _wait_for_worker()
        yield proc
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_celery_config_uses_postgres_sqla():
    broker = _build_broker_url()
    backend = _build_result_backend()
    assert broker.startswith("sqla+postgresql"), broker
    assert backend.startswith("db+postgresql"), backend
    assert "redis" not in broker and "redis" not in backend
    assert "amqp" not in broker and "amqp" not in backend


@pytest.mark.asyncio
async def test_ping_task_runs_and_persists_result(celery_worker_proc):
    result = ping.delay()
    payload = result.get(timeout=30)
    assert payload["status"] == "ok"
    expected_user = make_url(os.environ["CELERY_RESULT_BACKEND"].replace("db+", "")).username
    assert payload["db_user"] == expected_user

    async with engine.begin() as conn:
        row = await conn.execute(
            text("SELECT task_id, status FROM celery_taskmeta WHERE task_id = :tid"),
            {"tid": result.id},
        )
        data = row.first()
    assert data is not None
    assert data.status == "SUCCESS"

    # Metrics served from worker HTTP server
    metrics_port = os.environ["CELERY_METRICS_PORT"]
    metrics_resp = httpx.get(f"http://127.0.0.1:{metrics_port}/metrics", timeout=10.0)
    assert metrics_resp.status_code == 200
    assert "celery_task_success_total" in metrics_resp.text

    health_resp = httpx.get(f"http://127.0.0.1:{metrics_port}/health", timeout=10.0)
    assert health_resp.status_code == 200
    health_body = health_resp.json()
    assert health_body.get("broker") == "ok"
    assert health_body.get("database") == "ok"


@pytest.mark.asyncio
async def test_metrics_exposed_via_fastapi(monkeypatch):
    original = celery_app.conf.task_always_eager
    celery_app.conf.task_always_eager = True
    try:
        ping.delay()
        with pytest.raises(ValueError):
            ping.delay(fail=True).get(propagate=True)
    finally:
        celery_app.conf.task_always_eager = original

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/metrics")

    text_body = resp.text
    assert "celery_task_started_total" in text_body
    assert "celery_task_success_total" in text_body
    assert "celery_task_failure_total" in text_body
    assert "celery_task_duration_seconds_bucket" in text_body


def test_worker_logs_are_structured(caplog):
    configure_logging()
    celery_app.conf.task_always_eager = True
    caplog.set_level("INFO")
    ping.delay()
    with pytest.raises(ValueError):
        ping.delay(fail=True).get(propagate=True)

    parsed = []
    for record in caplog.records:
        try:
            parsed.append(json.loads(record.message))
        except Exception:
            continue
    names = {p.get("task_name") for p in parsed if isinstance(p, dict)}
    assert "app.tasks.housekeeping.ping" in names


def test_registered_tasks_include_stubs():
    registered = set(celery_app.tasks.keys())
    assert "app.tasks.housekeeping.ping" in registered
    assert "app.tasks.maintenance.refresh_all_materialized_views" in registered
    assert "app.tasks.llm.route" in registered
    assert "app.tasks.llm.explanation" in registered
    assert "app.tasks.llm.investigation" in registered
    assert "app.tasks.llm.budget_optimization" in registered


def test_tenant_task_enforces_and_sets_guc():
    original = celery_app.conf.task_always_eager
    celery_app.conf.task_always_eager = True
    try:
        tenant_id = uuid4()
        result = scan_for_pii_contamination_task.delay(tenant_id=str(tenant_id)).get(timeout=10)
        assert result["status"] == "ok"
        assert UUID(result["guc"]) == tenant_id

        with pytest.raises(ValueError):
            llm_routing_worker.delay(payload={}).get(timeout=5)
    finally:
        celery_app.conf.task_always_eager = original
