import json
import os
import signal
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import create_engine, text

from app.celery_app import celery_app
from app.core.secrets import get_database_url, get_migration_database_url
from app.schemas.llm_payloads import LLMTaskPayload
from app.services.llm_dispatch import enqueue_llm_task


@dataclass(frozen=True)
class _RuntimeProofConfig:
    runtime_sync_url: str
    runtime_async_url: str
    migration_sync_url: str
    artifact_dir: Path
    canary_secret: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is required for B0.7-P2 runtime proof")
    return value


def _runtime_sync_db_url() -> str:
    explicit = os.getenv("B07_P2_RUNTIME_DATABASE_URL")
    if explicit:
        return explicit
    runtime_url = get_database_url()
    if runtime_url.startswith("postgresql+asyncpg://"):
        return runtime_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return runtime_url


def _runtime_async_db_url(runtime_sync: str) -> str:
    if runtime_sync.startswith("postgresql+asyncpg://"):
        return runtime_sync
    return runtime_sync.replace("postgresql://", "postgresql+asyncpg://", 1)


def _migration_sync_db_url() -> str:
    return get_migration_database_url()


def _artifact_dir() -> Path:
    explicit = os.getenv("B07_P2_ARTIFACT_DIR")
    if explicit:
        path = Path(explicit)
    else:
        path = _repo_root() / "artifacts" / "b07-p2"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _wait_for_output(lines: list[str], substring: str, timeout_s: float) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if any(substring in line for line in lines):
            return
        time.sleep(0.2)
    raise RuntimeError(f"Timed out waiting for worker output containing {substring!r}")


def _start_worker(env: dict[str, str], log_path: Path) -> tuple[subprocess.Popen[str], list[str]]:
    backend_dir = _repo_root() / "backend"
    prom_dir = Path(tempfile.mkdtemp(prefix="b07_p2_prom_"))
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
        "housekeeping,llm",
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
    log_fp = log_path.open("w", encoding="utf-8")

    def _reader() -> None:
        if proc.stdout is None:
            return
        for line in proc.stdout:
            clean = line.rstrip()
            lines.append(clean)
            log_fp.write(clean + "\n")
            log_fp.flush()
        log_fp.close()

    threading.Thread(target=_reader, name="b07-p2-worker-reader", daemon=True).start()
    _wait_for_output(lines, "ready.", timeout_s=60)
    return proc, lines


def _stop_process(proc: subprocess.Popen[str]) -> None:
    proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)


def _with_engine(runtime_db_url: str):
    return create_engine(runtime_db_url)


def _required_columns(engine, table_name: str) -> set[str]:
    query = text(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = :table_name
          AND is_nullable = 'NO'
          AND column_default IS NULL
          AND (is_identity IS NULL OR is_identity = 'NO')
        """
    )
    with engine.begin() as conn:
        result = conn.execute(query, {"table_name": table_name})
    return set(result.scalars().all())


def _seed_tenant(runtime_db_url: str, tenant_id: UUID) -> None:
    engine = _with_engine(runtime_db_url)
    required = _required_columns(engine, "tenants")
    now = datetime.now(timezone.utc)
    payload = {
        "id": str(tenant_id),
        "name": f"B07 P2 Tenant {tenant_id.hex[:8]}",
        "api_key_hash": f"hash_{tenant_id.hex[:16]}",
        "notification_email": f"{tenant_id.hex[:8]}@test.invalid",
        "shopify_webhook_secret": "test_secret",
        "created_at": now,
        "updated_at": now,
    }
    insert_cols = []
    for col in required:
        if col not in payload:
            raise RuntimeError(f"Missing payload value for required tenants column '{col}'")
        insert_cols.append(col)
    if "id" not in insert_cols:
        insert_cols.insert(0, "id")
    if "name" not in insert_cols:
        insert_cols.append("name")

    placeholders = ", ".join(f":{col}" for col in insert_cols)
    # RAW_SQL_ALLOWLIST: deterministic test-only tenant seed for runtime-chain proof.
    sql = text(
        f"INSERT INTO tenants ({', '.join(insert_cols)}) VALUES ({placeholders})"
    )
    with engine.begin() as conn:
        conn.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
            {"tenant_id": str(tenant_id)},
        )
        conn.execute(sql, payload)


def _fetch_llm_api_call(
    runtime_db_url: str,
    tenant_id: UUID,
    user_id: UUID,
    request_id: str,
    endpoint: str,
) -> Optional[dict[str, Any]]:
    engine = _with_engine(runtime_db_url)
    with engine.begin() as conn:
        conn.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
            {"tenant_id": str(tenant_id)},
        )
        conn.execute(
            text("SELECT set_config('app.current_user_id', :user_id, false)"),
            {"user_id": str(user_id)},
        )
        row = conn.execute(
            text(
                """
                SELECT tenant_id, user_id, provider, status, distillation_eligible, endpoint, request_id
                FROM public.llm_api_calls
                WHERE tenant_id = :tenant_id
                  AND request_id = :request_id
                  AND endpoint = :endpoint
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "request_id": request_id,
                "endpoint": endpoint,
            },
        ).mappings().first()
        return dict(row) if row else None


def _count_llm_api_calls(
    runtime_db_url: str,
    tenant_id: UUID,
    user_id: UUID,
    request_id: str,
) -> int:
    engine = _with_engine(runtime_db_url)
    with engine.begin() as conn:
        conn.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
            {"tenant_id": str(tenant_id)},
        )
        conn.execute(
            text("SELECT set_config('app.current_user_id', :user_id, false)"),
            {"user_id": str(user_id)},
        )
        count = conn.execute(
            text(
                "SELECT COUNT(*) FROM public.llm_api_calls WHERE request_id = :request_id"
            ),
            {"request_id": request_id},
        ).scalar_one()
        return int(count)


def _poll_until(
    *,
    description: str,
    timeout_s: float,
    interval_s: float,
    probe,
) -> Any:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        result = probe()
        if result:
            return result
        time.sleep(interval_s)
    raise AssertionError(f"Timeout while waiting for {description}")


def _wait_for_log_contains(path: Path, substring: str, timeout_s: float) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if path.exists():
            content = path.read_text(encoding="utf-8", errors="ignore")
            if substring in content:
                return
        time.sleep(0.2)
    raise RuntimeError(f"Timed out waiting for log content containing {substring!r}")


def _runtime_config() -> _RuntimeProofConfig:
    runtime_sync = _runtime_sync_db_url()
    runtime_async = _runtime_async_db_url(runtime_sync)
    migration_sync = _migration_sync_db_url()
    artifact_dir = _artifact_dir()
    canary = os.getenv("B07_P2_LOG_CANARY", "skeldir_test_secret_123")
    return _RuntimeProofConfig(
        runtime_sync_url=runtime_sync,
        runtime_async_url=runtime_async,
        migration_sync_url=migration_sync,
        artifact_dir=artifact_dir,
        canary_secret=canary,
    )


def test_b07_p2_runtime_llm_chain_with_redaction():
    config = _runtime_config()

    env = os.environ.copy()
    env["DATABASE_URL"] = config.runtime_async_url
    env["CELERY_BROKER_URL"] = f"sqla+{config.runtime_sync_url}"
    env["CELERY_RESULT_BACKEND"] = f"db+{config.runtime_sync_url}"
    env.setdefault("ENVIRONMENT", "test")
    env["SKELDIR_TEST_TASKS"] = "1"

    worker_log = config.artifact_dir / "worker.log"
    proof_snapshot = config.artifact_dir / "runtime_db_probe.json"
    redaction_snapshot = config.artifact_dir / "redaction_probe.json"

    worker_proc = None
    try:
        worker_proc, _ = _start_worker(env, worker_log)

        tenant_id = uuid4()
        user_id = uuid4()
        _seed_tenant(config.migration_sync_url, tenant_id)
        request_id = f"b07-p2-{tenant_id.hex[:8]}"
        endpoint = "app.tasks.llm.explanation"
        payload = LLMTaskPayload(
            tenant_id=tenant_id,
            user_id=user_id,
            correlation_id=request_id,
            request_id=request_id,
            prompt={"purpose": "b07-p2-runtime-proof"},
            max_cost_cents=0,
        )
        enqueue_llm_task("explanation", payload)

        row = _poll_until(
            description="llm_api_calls insert",
            timeout_s=60.0,
            interval_s=0.5,
            probe=lambda: (
                candidate
                if candidate is not None and candidate.get("status") != "pending"
                else None
            )
            if (
                candidate := _fetch_llm_api_call(
                    config.runtime_sync_url,
                    tenant_id,
                    user_id,
                    request_id,
                    endpoint,
                )
            )
            else None,
        )

        assert row["provider"] == "stub"
        assert row["distillation_eligible"] is False
        assert str(row["tenant_id"]) == str(tenant_id)
        assert str(row["user_id"]) == str(user_id)

        wrong_user = uuid4()
        wrong_tenant = uuid4()
        assert _count_llm_api_calls(
            config.runtime_sync_url, tenant_id, wrong_user, request_id
        ) == 0, "RLS failed: cross-user read returned data"
        assert _count_llm_api_calls(
            config.runtime_sync_url, wrong_tenant, user_id, request_id
        ) == 0, "RLS failed: cross-tenant read returned data"

        proof_snapshot.write_text(
            json.dumps(
                {
                    "tenant_id": str(tenant_id),
                    "user_id": str(user_id),
                    "request_id": request_id,
                    "endpoint": endpoint,
                    "provider": row["provider"],
                    "distillation_eligible": row["distillation_eligible"],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        celery_app.send_task(
            "app.tasks.observability_test.redaction_canary",
            queue="housekeeping",
            kwargs={"secret_value": config.canary_secret},
        )

        _wait_for_log_contains(worker_log, "LLM_PROVIDER_API_KEY=***", timeout_s=30.0)
        _wait_for_log_contains(worker_log, "Bearer ***", timeout_s=30.0)

        content = worker_log.read_text(encoding="utf-8", errors="ignore")
        redaction_snapshot.write_text(
            json.dumps(
                {
                    "canary_present": config.canary_secret in content,
                    "redacted_key_present": "LLM_PROVIDER_API_KEY=***" in content,
                    "redacted_bearer_present": "Bearer ***" in content,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        assert config.canary_secret not in content, "Redaction failed: canary secret leaked to logs"
    finally:
        if worker_proc is not None:
            _stop_process(worker_proc)
