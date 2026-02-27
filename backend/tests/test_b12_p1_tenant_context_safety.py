from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.celery_app import celery_app
from app.db import session as db_session


def _build_async_database_url_and_args() -> tuple[str, dict]:
    raw_url = os.environ["DATABASE_URL"]
    parsed = urlsplit(raw_url)
    query_params = dict(parse_qsl(parsed.query))
    query_params.pop("sslmode", None)
    query_params.pop("channel_binding", None)
    sanitized = urlunsplit(parsed._replace(query=urlencode(query_params)))
    if sanitized.startswith("postgresql://"):
        sanitized = sanitized.replace("postgresql://", "postgresql+asyncpg://", 1)
    return sanitized, {}


def _wait_for_worker_ready(lines: list[str], proc: subprocess.Popen[str], timeout_s: float = 60.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if any("ready." in line for line in lines):
            return
        if proc.poll() is not None:
            raise RuntimeError("Celery worker exited before ready signal")
        time.sleep(0.2)
    raise RuntimeError("Timed out waiting for Celery worker readiness")


@pytest_asyncio.fixture
async def pooled_session_override(monkeypatch: pytest.MonkeyPatch):
    url, connect_args = _build_async_database_url_and_args()
    engine = create_async_engine(
        url,
        connect_args=connect_args,
        pool_pre_ping=True,
        pool_size=1,
        max_overflow=0,
    )
    session_local = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(db_session, "AsyncSessionLocal", session_local)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_api_transaction_local_guc_ordering_and_no_pool_bleed(pooled_session_override):
    statements: list[str] = []

    def _capture_sql(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        statements.append(statement)

    event.listen(pooled_session_override.sync_engine, "before_cursor_execute", _capture_sql)
    try:
        tenant_a, user_a = uuid4(), uuid4()
        tenant_b, user_b = uuid4(), uuid4()

        async def _run_request(tenant_id, user_id):
            async with db_session.get_session(tenant_id=tenant_id, user_id=user_id) as session:
                tenant = await session.execute(text("SELECT current_setting('app.current_tenant_id', true)"))
                user = await session.execute(text("SELECT current_setting('app.current_user_id', true)"))
                pid = await session.execute(text("SELECT pg_backend_pid()"))
                return str(tenant.scalar()), str(user.scalar()), int(pid.scalar())

        start_a = len(statements)
        observed_tenant_a, observed_user_a, pid_a = await _run_request(tenant_a, user_a)
        sql_a = statements[start_a:]
        set_idx_a = next(i for i, s in enumerate(sql_a) if "set_config('app.current_tenant_id'" in s)
        read_idx_a = next(i for i, s in enumerate(sql_a) if "current_setting('app.current_tenant_id'" in s)

        async with db_session.AsyncSessionLocal() as raw_session:
            leak_check = await raw_session.execute(text("SELECT current_setting('app.current_tenant_id', true)"))
            leak_pid = await raw_session.execute(text("SELECT pg_backend_pid()"))
            leaked_value = leak_check.scalar()
            pid_between = int(leak_pid.scalar())

        start_b = len(statements)
        observed_tenant_b, observed_user_b, pid_b = await _run_request(tenant_b, user_b)
        sql_b = statements[start_b:]
        set_idx_b = next(i for i, s in enumerate(sql_b) if "set_config('app.current_tenant_id'" in s)
        read_idx_b = next(i for i, s in enumerate(sql_b) if "current_setting('app.current_tenant_id'" in s)

        assert observed_tenant_a == str(tenant_a)
        assert observed_user_a == str(user_a)
        assert observed_tenant_b == str(tenant_b)
        assert observed_user_b == str(user_b)
        assert leaked_value in (None, "")
        assert set_idx_a < read_idx_a
        assert set_idx_b < read_idx_b
        assert pid_a == pid_between == pid_b
    finally:
        event.remove(pooled_session_override.sync_engine, "before_cursor_execute", _capture_sql)


def test_worker_real_process_pool_reuse_no_bleed_and_tenant_envelope_required():
    assert celery_app.conf.task_always_eager is False

    backend_dir = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(backend_dir.parent)
    env["TESTING"] = "1"
    env["SKELDIR_TEST_TASKS"] = "1"
    env["DATABASE_FORCE_POOLING"] = "1"
    env["DATABASE_POOL_SIZE"] = "1"
    env["DATABASE_MAX_OVERFLOW"] = "0"
    env["PROMETHEUS_MULTIPROC_DIR"] = tempfile.mkdtemp(prefix="b12_p1_prom_")

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
        "-Q",
        "housekeeping",
        "--without-gossip",
        "--without-mingle",
        "--without-heartbeat",
        "--loglevel=INFO",
    ]
    proc = subprocess.Popen(
        cmd,
        cwd=backend_dir,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    lines: list[str] = []

    def _reader() -> None:
        if proc.stdout is None:
            return
        for line in proc.stdout:
            lines.append(line.rstrip("\n"))

    threading.Thread(target=_reader, daemon=True).start()

    try:
        _wait_for_worker_ready(lines, proc, timeout_s=90.0)
        tenant_a, user_a = uuid4(), uuid4()
        tenant_b, user_b = uuid4(), uuid4()

        result_a = celery_app.send_task(
            "app.tasks.observability_test.tenant_context_probe",
            queue="housekeeping",
            kwargs={"tenant_id": str(tenant_a), "user_id": str(user_a)},
        ).get(timeout=60, propagate=True)
        result_b = celery_app.send_task(
            "app.tasks.observability_test.tenant_context_probe",
            queue="housekeeping",
            kwargs={"tenant_id": str(tenant_b), "user_id": str(user_b)},
        ).get(timeout=60, propagate=True)

        assert result_a["tenant"] == str(tenant_a)
        assert result_a["user"] == str(user_a)
        assert result_b["tenant"] == str(tenant_b)
        assert result_b["user"] == str(user_b)
        assert result_a["backend_pid"] == result_b["backend_pid"]

        missing_tenant = celery_app.send_task(
            "app.tasks.observability_test.tenant_context_probe",
            queue="housekeeping",
            kwargs={"user_id": str(uuid4())},
        )
        with pytest.raises(Exception, match="tenant_id is required"):
            missing_tenant.get(timeout=60, propagate=True)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=20)
