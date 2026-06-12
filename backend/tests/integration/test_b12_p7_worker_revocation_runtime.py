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

WORKER_QUEUE = "housekeeping"
PREFORK_CHILD_COUNT = 2
_PREFORK_PROTOCOL_ERROR_PATTERNS = (
    "revocation_listener_error",
    "decryption failed or bad record mac",
    "sslv3 alert bad record mac",
    "protocol violation",
    "lost synchronization",
)


def _wait_for_worker_ready(lines: list[str], proc: subprocess.Popen[str], timeout_s: float = 90.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if any("ready." in line for line in lines):
            return
        if proc.poll() is not None:
            raise RuntimeError("Celery worker exited before ready signal")
        time.sleep(0.2)
    raise RuntimeError("Timed out waiting for Celery worker readiness")


def _session_headers(*, tenant_id, user_id, jti, iat: int) -> dict[str, object]:
    return {
        AUTHORITY_ENVELOPE_HEADER: SessionAuthorityEnvelope(
            tenant_id=tenant_id,
            user_id=user_id,
            jti=jti,
            iat=iat,
        ).model_dump(mode="json")
    }


def _start_worker(*, pool: str = "prefork", concurrency: int = PREFORK_CHILD_COUNT) -> tuple[subprocess.Popen[str], list[str]]:
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
        pool,
        "-c",
        str(concurrency),
        "-Q",
        WORKER_QUEUE,
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


def _stop_worker(proc: subprocess.Popen[str]) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=20)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=20)


def _assert_no_prefork_protocol_errors(lines: list[str]) -> None:
    lower_lines = "\n".join(lines).lower()
    matched = [pattern for pattern in _PREFORK_PROTOCOL_ERROR_PATTERNS if pattern in lower_lines]
    assert not matched, f"worker logs contain prefork/listener protocol errors: {matched}"


def _send_revocation_runtime_control_batch(
    *,
    batch_size: int,
    sleep_seconds: float,
    reset_lookup_counter: bool,
) -> list[dict]:
    results = [
        celery_app.send_task(
            "app.tasks.observability_test.revocation_runtime_control",
            queue=WORKER_QUEUE,
            kwargs={
                "sleep_seconds": sleep_seconds,
                "reset_lookup_counter": reset_lookup_counter,
            },
        )
        for _ in range(batch_size)
    ]
    return [result.get(timeout=120, propagate=True) for result in results]


def _send_revocation_runtime_probe_batch(
    *,
    tenant_id,
    user_id,
    jti,
    iat: int,
    batch_size: int,
    sleep_seconds: float,
) -> list[dict]:
    results = [
        celery_app.send_task(
            "app.tasks.observability_test.revocation_runtime_probe",
            queue=WORKER_QUEUE,
            kwargs={
                "correlation_id": str(uuid4()),
                "sleep_seconds": sleep_seconds,
            },
            headers=_session_headers(
                tenant_id=tenant_id,
                user_id=user_id,
                jti=jti,
                iat=iat,
            ),
        )
        for _ in range(batch_size)
    ]
    return [result.get(timeout=120, propagate=True) for result in results]


def _capture_lookup_counts_for_pids(required_pids: set[int]) -> dict[int, int]:
    counts: dict[int, int] = {}
    deadline = time.time() + 60
    while time.time() < deadline and required_pids - counts.keys():
        payloads = _send_revocation_runtime_control_batch(
            batch_size=8,
            sleep_seconds=0.02,
            reset_lookup_counter=False,
        )
        for payload in payloads:
            pid = int(payload["worker_pid"])
            if pid not in required_pids:
                continue
            counts[pid] = max(counts.get(pid, 0), int(payload["revocation_db_lookups"]))
            assert bool(payload["listener_alive"]) is True
            assert int(payload["listener_pid"]) == pid
    assert required_pids.issubset(counts.keys()), f"missing lookup counters for prefork pids: {required_pids} vs {set(counts)}"
    return counts


@pytest.mark.skipif(sys.platform == "win32", reason="Celery prefork proof requires fork-capable OS")
@pytest.mark.asyncio
async def test_prefork_revocation_runtime_is_process_local_and_zero_io_after_warmup(test_tenant) -> None:
    worker_proc, lines = _start_worker(pool="prefork", concurrency=PREFORK_CHILD_COUNT)
    try:
        user_id = uuid4()
        jti = uuid4()
        issued_at_epoch = int(datetime.now(timezone.utc).timestamp())

        reset_seen_pids: set[int] = set()
        deadline = time.time() + 90
        while time.time() < deadline and len(reset_seen_pids) < PREFORK_CHILD_COUNT:
            payloads = _send_revocation_runtime_control_batch(
                batch_size=10,
                sleep_seconds=0.05,
                reset_lookup_counter=True,
            )
            for payload in payloads:
                pid = int(payload["worker_pid"])
                reset_seen_pids.add(pid)
                assert bool(payload["listener_alive"]) is True
                assert int(payload["listener_pid"]) == pid
                assert int(payload["listener_conn_fd"]) >= 0
        assert len(reset_seen_pids) >= PREFORK_CHILD_COUNT, f"expected >= {PREFORK_CHILD_COUNT} worker children, saw {sorted(reset_seen_pids)}"

        warmup_seen_pids: set[int] = set()
        warmup_counts: dict[int, int] = {}
        deadline = time.time() + 90
        while time.time() < deadline and len(warmup_seen_pids) < PREFORK_CHILD_COUNT:
            payloads = _send_revocation_runtime_probe_batch(
                tenant_id=test_tenant,
                user_id=user_id,
                jti=jti,
                iat=issued_at_epoch,
                batch_size=12,
                sleep_seconds=0.05,
            )
            for payload in payloads:
                pid = int(payload["worker_pid"])
                warmup_seen_pids.add(pid)
                warmup_counts[pid] = max(warmup_counts.get(pid, 0), int(payload["revocation_db_lookups"]))
                assert payload["tenant"] == str(test_tenant)
                assert payload["user"] == str(user_id)
                assert bool(payload["listener_alive"]) is True
                assert int(payload["listener_pid"]) == pid
        assert len(warmup_seen_pids) >= PREFORK_CHILD_COUNT, f"warmup did not reach all prefork children: {sorted(warmup_seen_pids)}"
        for pid in warmup_seen_pids:
            assert warmup_counts[pid] >= 1, f"expected warmup DB lookup for worker pid={pid}"

        required_pids = set(sorted(list(warmup_seen_pids))[:PREFORK_CHILD_COUNT])
        baseline_counts = _capture_lookup_counts_for_pids(required_pids)

        steady_payloads = _send_revocation_runtime_probe_batch(
            tenant_id=test_tenant,
            user_id=user_id,
            jti=jti,
            iat=issued_at_epoch,
            batch_size=40,
            sleep_seconds=0.05,
        )
        steady_seen_pids = {int(payload["worker_pid"]) for payload in steady_payloads}
        assert required_pids.issubset(steady_seen_pids), f"steady-state batch did not execute on all required prefork children: {required_pids} vs {steady_seen_pids}"
        for payload in steady_payloads:
            pid = int(payload["worker_pid"])
            assert bool(payload["listener_alive"]) is True
            assert int(payload["listener_pid"]) == pid

        post_counts = _capture_lookup_counts_for_pids(required_pids)
        assert post_counts == baseline_counts, f"revocation hot path performed DB reads in steady-state: baseline={baseline_counts}, post={post_counts}"

        async with AsyncSessionLocal() as session:
            async with session.begin():
                await denylist_access_token(
                    session,
                    tenant_id=test_tenant,
                    user_id=user_id,
                    jti=jti,
                    expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                    reason="b12_p7_prefork_notify_delivery",
                )

        time.sleep(1.0)
        revoked_results = [
            celery_app.send_task(
                "app.tasks.observability_test.auth_envelope_probe",
                queue=WORKER_QUEUE,
                kwargs={"correlation_id": str(uuid4())},
                headers=_session_headers(
                    tenant_id=test_tenant,
                    user_id=user_id,
                    jti=jti,
                    iat=issued_at_epoch,
                ),
            )
            for _ in range(12)
        ]
        for result in revoked_results:
            with pytest.raises(Exception, match="auth envelope revoked"):
                result.get(timeout=120, propagate=True)

        after_revoke_counts = _capture_lookup_counts_for_pids(required_pids)
        assert after_revoke_counts == post_counts, (
            "revoked-session checks hit DB in prefork steady-state; expected LISTEN/NOTIFY cache-only path"
        )

        effect_key = f"revocation-probe:{jti}"
        async with AsyncSessionLocal() as session:
            row = (
                await session.execute(
                    text(
                        """
                        SELECT count(*)::int
                        FROM public.worker_side_effects
                        WHERE tenant_id = :tenant_id
                          AND effect_key = :effect_key
                        """
                    ),
                    {"tenant_id": str(test_tenant), "effect_key": effect_key},
                )
            ).scalar_one()
        assert row == 0
    finally:
        _stop_worker(worker_proc)

    _assert_no_prefork_protocol_errors(lines)


@pytest.mark.skipif(sys.platform == "win32", reason="Celery prefork proof requires fork-capable OS")
@pytest.mark.asyncio
async def test_prefork_revoked_session_envelope_is_blocked_before_worker_side_effect(test_tenant) -> None:
    user_id = uuid4()
    jti = uuid4()
    issued_at_epoch = int(datetime.now(timezone.utc).timestamp())

    result = celery_app.send_task(
        "app.tasks.observability_test.auth_envelope_probe",
        queue=WORKER_QUEUE,
        kwargs={
            "correlation_id": str(uuid4()),
        },
        headers=_session_headers(
            tenant_id=test_tenant,
            user_id=user_id,
            jti=jti,
            iat=issued_at_epoch,
        ),
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

    worker_proc, lines = _start_worker(pool="prefork", concurrency=PREFORK_CHILD_COUNT)
    try:
        with pytest.raises(Exception, match="auth envelope revoked"):
            result.get(timeout=60, propagate=True)
    finally:
        _stop_worker(worker_proc)

    _assert_no_prefork_protocol_errors(lines)

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
