from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from uuid import uuid4

import pytest


# Align with existing Celery/Postgres defaults used across the backend test suite.
DEFAULT_SYNC_DSN = os.environ.get("TEST_SYNC_DSN", "postgresql://app_user:app_user@localhost:5432/skeldir_validation")
DEFAULT_ASYNC_DSN = os.environ.get(
    "TEST_ASYNC_DSN", "postgresql+asyncpg://app_user:app_user@localhost:5432/skeldir_validation"
)
os.environ.setdefault("DATABASE_URL", DEFAULT_ASYNC_DSN)
os.environ.setdefault("CELERY_BROKER_URL", f"sqla+{DEFAULT_SYNC_DSN}")
os.environ.setdefault("CELERY_RESULT_BACKEND", f"db+{DEFAULT_SYNC_DSN}")


from app.celery_app import celery_app  # noqa: E402


REQUIRED_KEYS = {"tenant_id", "correlation_id", "task_name", "queue_name", "status", "error_type"}
ALLOWED_KEYS = REQUIRED_KEYS | {"task_id", "duration_ms", "retry", "retries", "exc_message_trunc"}
TEST_QUEUE = "b0566_runtime"


def _start_worker(*, tmp_path: Path) -> tuple[subprocess.Popen[str], list[str]]:
    backend_dir = Path(__file__).resolve().parents[1]
    multiproc_dir = tmp_path / "prom_multiproc"
    multiproc_dir.mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    env.update(
        {
            "PYTHONPATH": str(backend_dir.parent),
            "PROMETHEUS_MULTIPROC_DIR": str(multiproc_dir),
            "SKELDIR_TEST_TASKS": "1",
        }
    )

    pool = "prefork" if os.name != "nt" else "solo"
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
        "1",
        "-Q",
        TEST_QUEUE,
        "--without-gossip",
        "--without-mingle",
        "--without-heartbeat",
        "--loglevel=INFO",
    ]

    proc: subprocess.Popen[str] = subprocess.Popen(  # noqa: S603
        cmd,
        cwd=str(backend_dir),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    lines: list[str] = []

    def _reader() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            lines.append(line.rstrip("\n"))

    threading.Thread(target=_reader, name="celery-worker-stdout-reader", daemon=True).start()
    return proc, lines


def _wait_for_substring(lines: list[str], substring: str, *, timeout_s: float = 60.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if any(substring in line for line in lines):
            return
        time.sleep(0.1)
    raise AssertionError(f"Timed out waiting for worker output containing {substring!r}")


def _parse_lifecycle_records(lines: list[str]) -> list[dict]:
    records: list[dict] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        start = line.find("{")
        if start == -1:
            continue
        candidate = line[start:]
        end = candidate.rfind("}")
        if end == -1:
            continue
        candidate = candidate[: end + 1]
        try:
            obj = json.loads(candidate)
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        if REQUIRED_KEYS.issubset(obj.keys()) and obj.get("status") in {"started", "success", "failure"}:
            records.append(obj)
    return records


def _wait_for_lifecycle_records(
    lines: list[str],
    *,
    predicate,
    timeout_s: float = 60.0,
) -> list[dict]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        records = [r for r in _parse_lifecycle_records(lines) if predicate(r)]
        if records:
            return records
        time.sleep(0.1)
    raise AssertionError("Timed out waiting for lifecycle records to match predicate")


def test_b0566_worker_runtime_emits_canonical_lifecycle_logs(tmp_path: Path):
    assert celery_app.conf.task_always_eager is False, "Runtime proof requires eager mode disabled"

    proc, lines = _start_worker(tmp_path=tmp_path)
    try:
        _wait_for_substring(lines, "ready.", timeout_s=90.0)

        tenant_id = "00000000-0000-0000-0000-000000000000"
        correlation_success = str(uuid4())
        correlation_failure = str(uuid4())

        ok = celery_app.send_task(
            "app.tasks.observability_test.success",
            queue=TEST_QUEUE,
            kwargs={"tenant_id": tenant_id, "correlation_id": correlation_success},
        )
        fail = celery_app.send_task(
            "app.tasks.observability_test.failure",
            queue=TEST_QUEUE,
            kwargs={"tenant_id": tenant_id, "correlation_id": correlation_failure},
        )

        ok_records = _wait_for_lifecycle_records(
            lines,
            predicate=lambda r: r.get("task_id") == ok.id and r.get("status") == "success",
            timeout_s=60.0,
        )
        fail_records = _wait_for_lifecycle_records(
            lines,
            predicate=lambda r: r.get("task_id") == fail.id and r.get("status") == "failure",
            timeout_s=60.0,
        )

        ok_rec = ok_records[-1]
        fail_rec = fail_records[-1]

        for rec in (ok_rec, fail_rec):
            assert set(rec.keys()).issubset(ALLOWED_KEYS)
            assert REQUIRED_KEYS.issubset(rec.keys())
            assert rec["tenant_id"] == tenant_id
            assert rec["queue_name"] == TEST_QUEUE
            assert isinstance(rec.get("task_name"), str) and rec["task_name"]
            assert isinstance(rec.get("correlation_id"), str) and rec["correlation_id"]
            assert "args" not in rec and "kwargs" not in rec and "payload" not in rec

        assert ok_rec["status"] == "success"
        assert ok_rec.get("error_type") in (None, "")
        assert isinstance(ok_rec.get("duration_ms"), int)

        assert fail_rec["status"] == "failure"
        assert fail_rec["correlation_id"] == correlation_failure
        assert isinstance(fail_rec.get("error_type"), str) and fail_rec["error_type"]
        assert "traceback" not in fail_rec
        assert isinstance(fail_rec.get("duration_ms"), int)
        assert isinstance(fail_rec.get("exc_message_trunc"), str) and len(fail_rec["exc_message_trunc"]) <= 300

        # Guardrail: lifecycle output must not serialize task inputs or sensitive keys.
        lifecycle_lines = [json.dumps(r, sort_keys=True) for r in _parse_lifecycle_records(lines)]
        joined = "\n".join(lifecycle_lines)
        for forbidden in ("args", "kwargs", "payload", "Authorization", "token", "secret"):
            assert forbidden not in joined
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()
