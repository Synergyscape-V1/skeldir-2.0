from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.celery_app import celery_app
from app.core.secrets import get_database_url
from app.db.session import AsyncSessionLocal
from app.services.auth_revocation import denylist_access_token
from app.tasks.authority import AUTHORITY_ENVELOPE_HEADER, SessionAuthorityEnvelope


def _wait_for_worker_ready(lines: list[str], proc: subprocess.Popen[str], timeout_s: float = 90.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if any("ready." in line for line in lines):
            return
        if proc.poll() is not None:
            raise RuntimeError("Celery worker exited before ready signal")
        time.sleep(0.2)
    raise RuntimeError("Timed out waiting for Celery worker readiness")


def _start_worker() -> tuple[subprocess.Popen[str], list[str]]:
    backend_dir = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(backend_dir.parent)
    env["TESTING"] = "1"
    env["SKELDIR_TEST_TASKS"] = "1"
    env["PROMETHEUS_MULTIPROC_DIR"] = tempfile.mkdtemp(prefix="b12_p7_prom_")
    # Keep subprocess worker aligned with this test process runtime/broker identity.
    env["DATABASE_URL"] = get_database_url()
    env["CELERY_BROKER_URL"] = str(celery_app.conf.broker_url)
    env["CELERY_RESULT_BACKEND"] = str(celery_app.conf.result_backend)

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
    _wait_for_worker_ready(lines, proc)
    return proc, lines


@pytest.mark.asyncio
async def test_revoked_session_envelope_is_blocked_before_worker_side_effect(test_tenant) -> None:
    user_id = uuid4()
    jti = uuid4()
    issued_at_epoch = int(datetime.now(timezone.utc).timestamp())

    result = celery_app.send_task(
        "app.tasks.observability_test.auth_envelope_probe",
        queue="housekeeping",
        kwargs={
            "correlation_id": str(uuid4()),
        },
        headers={
            AUTHORITY_ENVELOPE_HEADER: SessionAuthorityEnvelope(
                tenant_id=test_tenant,
                user_id=user_id,
                jti=jti,
                iat=issued_at_epoch,
            ).model_dump(mode="json")
        },
    )

    async with AsyncSessionLocal() as session:
        async with session.begin():
                await denylist_access_token(
                    session,
                    tenant_id=test_tenant,
                    user_id=user_id,
                    jti=jti,
                    expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                    reason="b12_p7_runtime_revoke_after_enqueue",
                )

    worker_proc, _lines = _start_worker()
    try:
        with pytest.raises(Exception, match="auth envelope revoked"):
            result.get(timeout=60, propagate=True)
    finally:
        worker_proc.terminate()
        try:
            worker_proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            worker_proc.kill()
            worker_proc.wait(timeout=20)

    async with AsyncSessionLocal() as session:
        row = (
            await session.execute(
                text(
                    """
                    SELECT count(*)::int
                    FROM public.worker_side_effects
                    WHERE tenant_id = :tenant_id
                      AND task_id = :task_id
                    """
                ),
                {"tenant_id": str(test_tenant), "task_id": str(result.id)},
            )
        ).scalar_one()
    assert row == 0
