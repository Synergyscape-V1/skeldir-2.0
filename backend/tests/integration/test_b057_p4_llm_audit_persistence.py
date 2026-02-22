import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, text
from app.core.secrets import get_database_url


@dataclass(frozen=True)
class _TenantFixture:
    tenant_id: UUID
    api_key_hash: str
    notification_email: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is required for B0.5.7-P4 integration tests")
    return value


def _runtime_sync_db_url() -> str:
    explicit = os.getenv("B057_P4_RUNTIME_DATABASE_URL")
    if explicit:
        return explicit
    runtime_url = get_database_url()
    if runtime_url.startswith("postgresql+asyncpg://"):
        return runtime_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return runtime_url


def _seed_tenant(admin_db_url: str, label: str) -> _TenantFixture:
    tenant_id = uuid4()
    api_key_hash = f"b057_p4_hash_{label}_{tenant_id.hex[:8]}"
    notification_email = f"b057-p4-{label}-{tenant_id.hex[:8]}@example.invalid"

    engine = create_engine(admin_db_url)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO public.tenants (
                  id,
                  name,
                  api_key_hash,
                  notification_email
                )
                VALUES (
                  :id,
                  :name,
                  :api_key_hash,
                  :notification_email
                )
                """
            ),
            {
                "id": str(tenant_id),
                "name": f"B057 P4 Tenant {label}",
                "api_key_hash": api_key_hash,
                "notification_email": notification_email,
            },
        )

    return _TenantFixture(
        tenant_id=tenant_id,
        api_key_hash=api_key_hash,
        notification_email=notification_email,
    )


def _count_llm_api_calls(runtime_db_url: str, tenant_id: UUID, user_id: UUID) -> int:
    engine = create_engine(runtime_db_url)
    with engine.begin() as conn:
        conn.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
            {"tenant_id": str(tenant_id)},
        )
        conn.execute(
            text("SELECT set_config('app.current_user_id', :user_id, false)"),
            {"user_id": str(user_id)},
        )
        count = conn.execute(text("SELECT COUNT(*) FROM public.llm_api_calls")).scalar_one()
        return int(count)


def _fetch_latest_dlq_row(runtime_db_url: str, tenant_id: UUID) -> dict | None:
    engine = create_engine(runtime_db_url)
    with engine.begin() as conn:
        conn.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
            {"tenant_id": str(tenant_id)},
        )
        row = conn.execute(
            text(
                """
                SELECT task_name, error_message, tenant_id
                FROM public.worker_failed_jobs
                WHERE tenant_id = :tenant_id
                ORDER BY failed_at DESC
                LIMIT 1
                """
            ),
            {"tenant_id": str(tenant_id)},
        ).mappings().first()
        return dict(row) if row else None


def _start_worker(env: dict) -> tuple[subprocess.Popen[str], list[str]]:
    backend_dir = _repo_root() / "backend"
    prom_dir = Path(tempfile.mkdtemp(prefix="b057_p4_prom_"))
    env = dict(env)
    env.setdefault("PROMETHEUS_MULTIPROC_DIR", str(prom_dir))
    cmd = [
        "celery",
        "-A",
        "app.celery_app.celery_app",
        "worker",
        "-P",
        "solo",
        "-Q",
        "llm,housekeeping",
        "-l",
        "INFO",
    ]
    proc = subprocess.Popen(
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
        if proc.stdout is None:
            return
        for line in proc.stdout:
            lines.append(line.rstrip())

    threading.Thread(target=_reader, name="b057-p4-worker-reader", daemon=True).start()
    _wait_for_output(lines, "ready.", timeout_s=60)
    return proc, lines


def _wait_for_output(lines: list[str], substring: str, timeout_s: float) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if any(substring in line for line in lines):
            return
        time.sleep(0.2)
    raise RuntimeError(f"Timed out waiting for worker output containing {substring!r}")


def _stop_worker(proc: subprocess.Popen[str]) -> None:
    proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:  # pragma: no cover
        proc.kill()
        proc.wait(timeout=10)


def test_b057_p4_llm_stub_persists_under_runtime_identity():
    admin_db_url = _require_env("B057_P4_ADMIN_DATABASE_URL")
    runtime_db_url = _runtime_sync_db_url()

    tenant_a = _seed_tenant(admin_db_url, "A")
    tenant_b = _seed_tenant(admin_db_url, "B")
    user_id = uuid4()

    runtime_async_db_url = runtime_db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    env = os.environ.copy()
    env["DATABASE_URL"] = runtime_async_db_url
    env["CELERY_BROKER_URL"] = f"sqla+{runtime_db_url}"
    env["CELERY_RESULT_BACKEND"] = f"db+{runtime_db_url}"
    env.setdefault("ENVIRONMENT", "test")

    proc, _ = _start_worker(env)
    try:
        from app.celery_app import celery_app

        before = _count_llm_api_calls(runtime_db_url, tenant_a.tenant_id, user_id)
        result = celery_app.send_task(
            "app.tasks.llm.route",
            kwargs={
                "payload": {"stub": True},
                "tenant_id": str(tenant_a.tenant_id),
                "user_id": str(user_id),
                "correlation_id": str(uuid4()),
                "request_id": str(uuid4()),
                "max_cost_cents": 0,
            },
            queue="llm",
            routing_key="llm.task",
        )
        result.get(timeout=30)
        after = _count_llm_api_calls(runtime_db_url, tenant_a.tenant_id, user_id)
        assert after == before + 1

        cross_tenant = _count_llm_api_calls(runtime_db_url, tenant_b.tenant_id, user_id)
        assert cross_tenant == 0, "RLS failed: tenant B can see tenant A audit rows"
    finally:
        _stop_worker(proc)


def test_b057_p4_audit_failure_persists_to_worker_failed_jobs():
    runtime_db_url = _runtime_sync_db_url()

    bad_tenant_id = uuid4()
    user_id = uuid4()
    runtime_async_db_url = runtime_db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    env = os.environ.copy()
    env["DATABASE_URL"] = runtime_async_db_url
    env["CELERY_BROKER_URL"] = f"sqla+{runtime_db_url}"
    env["CELERY_RESULT_BACKEND"] = f"db+{runtime_db_url}"
    env.setdefault("ENVIRONMENT", "test")

    proc, _ = _start_worker(env)
    try:
        from app.celery_app import celery_app

        result = celery_app.send_task(
            "app.tasks.llm.route",
            kwargs={
                "payload": {"stub": True},
                "tenant_id": str(bad_tenant_id),
                "user_id": str(user_id),
                "correlation_id": str(uuid4()),
                "request_id": str(uuid4()),
                "max_cost_cents": 0,
                "retry_on_failure": False,
            },
            queue="llm",
            routing_key="llm.task",
        )
        with pytest.raises(Exception):
            result.get(timeout=30, propagate=True)

        row = _fetch_latest_dlq_row(runtime_db_url, bad_tenant_id)
        assert row is not None, "Expected worker_failed_jobs row for failed LLM audit write"
        assert row["task_name"] == "app.tasks.llm.route"
        assert row["tenant_id"] == bad_tenant_id
    finally:
        _stop_worker(proc)
