from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import create_engine, text

from app.celery_app import celery_app
from app.core.secrets import get_database_url
from app.schemas.llm_payloads import LLMTaskPayload
from app.services.llm_dispatch import enqueue_llm_task

_ENDPOINT_BY_TASK = {
    "route": "app.tasks.llm.route",
    "explanation": "app.tasks.llm.explanation",
    "investigation": "app.tasks.llm.investigation",
    "budget_optimization": "app.tasks.llm.budget_optimization",
}


@dataclass(frozen=True)
class _RuntimeConfig:
    runtime_sync_url: str
    runtime_async_url: str
    artifact_dir: Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _runtime_sync_db_url() -> str:
    explicit = os.getenv("B07_P4_RUNTIME_DATABASE_URL")
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


def _artifact_dir() -> Path:
    explicit = os.getenv("B07_P4_ARTIFACT_DIR")
    if explicit:
        path = Path(explicit)
    else:
        path = _repo_root() / "artifacts" / "b07-p4"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _config() -> _RuntimeConfig:
    runtime_sync = _runtime_sync_db_url()
    return _RuntimeConfig(
        runtime_sync_url=runtime_sync,
        runtime_async_url=_runtime_async_db_url(runtime_sync),
        artifact_dir=_artifact_dir(),
    )


def _engine(runtime_db_url: str):
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
    engine = _engine(runtime_db_url)
    required = _required_columns(engine, "tenants")
    now = datetime.now(timezone.utc)
    payload = {
        "id": str(tenant_id),
        "name": f"B07 P4 Tenant {tenant_id.hex[:8]}",
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
    # RAW_SQL_ALLOWLIST: deterministic tenant seed for B0.7 P4 operational readiness integration proof.
    stmt = text(f"INSERT INTO tenants ({', '.join(insert_cols)}) VALUES ({placeholders})")
    with engine.begin() as conn:
        conn.execute(text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"), {"tenant_id": str(tenant_id)})
        conn.execute(stmt, payload)


def _seed_hourly_shutoff(runtime_db_url: str, tenant_id: UUID, user_id: UUID, reason: str) -> None:
    engine = _engine(runtime_db_url)
    now = datetime.now(timezone.utc)
    hour_start = now.replace(minute=0, second=0, microsecond=0)
    disabled_until = now + timedelta(minutes=30)
    with engine.begin() as conn:
        conn.execute(text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"), {"tenant_id": str(tenant_id)})
        conn.execute(text("SELECT set_config('app.current_user_id', :user_id, false)"), {"user_id": str(user_id)})
        conn.execute(
            text(
                """
                INSERT INTO llm_hourly_shutoff_state (
                    id,
                    tenant_id,
                    user_id,
                    hour_start,
                    is_shutoff,
                    reason,
                    threshold_cents,
                    total_cost_cents,
                    total_calls,
                    disabled_until,
                    updated_at
                )
                VALUES (
                    gen_random_uuid(),
                    :tenant_id,
                    :user_id,
                    :hour_start,
                    true,
                    :reason,
                    1,
                    1,
                    1,
                    :disabled_until,
                    now()
                )
                ON CONFLICT (tenant_id, user_id, hour_start)
                DO UPDATE SET
                    is_shutoff = true,
                    reason = EXCLUDED.reason,
                    threshold_cents = EXCLUDED.threshold_cents,
                    total_cost_cents = EXCLUDED.total_cost_cents,
                    total_calls = EXCLUDED.total_calls,
                    disabled_until = EXCLUDED.disabled_until,
                    updated_at = now()
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "user_id": str(user_id),
                "hour_start": hour_start,
                "reason": reason,
                "disabled_until": disabled_until,
            },
        )


def _dispatch(task_name: str, payload: LLMTaskPayload) -> dict[str, Any]:
    async_result = enqueue_llm_task(task_name, payload)
    result = async_result.get(timeout=120)
    if not isinstance(result, dict):
        raise AssertionError(f"Expected dict result for {task_name}, got {type(result).__name__}")
    return result


def _wait_for_row(runtime_db_url: str, tenant_id: UUID, user_id: UUID, endpoint: str, request_id: str) -> dict[str, Any]:
    engine = _engine(runtime_db_url)
    deadline = time.time() + 60.0
    while time.time() < deadline:
        with engine.begin() as conn:
            conn.execute(text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"), {"tenant_id": str(tenant_id)})
            conn.execute(text("SELECT set_config('app.current_user_id', :user_id, false)"), {"user_id": str(user_id)})
            row = conn.execute(
                text(
                    """
                    SELECT
                        id,
                        tenant_id,
                        user_id,
                        endpoint,
                        request_id,
                        provider,
                        status,
                        block_reason,
                        failure_reason,
                        provider_attempted,
                        was_cached,
                        distillation_eligible,
                        budget_reservation_cents,
                        budget_settled_cents,
                        response_metadata_ref,
                        reasoning_trace_ref,
                        request_metadata_ref,
                        breaker_state
                    FROM llm_api_calls
                    WHERE tenant_id = :tenant_id
                      AND user_id = :user_id
                      AND endpoint = :endpoint
                      AND request_id = :request_id
                    """
                ),
                {
                    "tenant_id": str(tenant_id),
                    "user_id": str(user_id),
                    "endpoint": endpoint,
                    "request_id": request_id,
                },
            ).mappings().first()
            if row is not None and row["status"] != "pending":
                return dict(row)
        time.sleep(0.5)
    raise AssertionError(f"Timed out waiting for llm_api_calls row endpoint={endpoint} request_id={request_id}")


def _count_calls(runtime_db_url: str, tenant_id: UUID, user_id: UUID, endpoint: str, request_id: str) -> int:
    engine = _engine(runtime_db_url)
    with engine.begin() as conn:
        conn.execute(text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"), {"tenant_id": str(tenant_id)})
        conn.execute(text("SELECT set_config('app.current_user_id', :user_id, false)"), {"user_id": str(user_id)})
        return int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM llm_api_calls
                    WHERE tenant_id = :tenant_id
                      AND user_id = :user_id
                      AND endpoint = :endpoint
                      AND request_id = :request_id
                    """
                ),
                {
                    "tenant_id": str(tenant_id),
                    "user_id": str(user_id),
                    "endpoint": endpoint,
                    "request_id": request_id,
                },
            ).scalar_one()
        )


def _visible_count_for_identity(
    runtime_db_url: str,
    *,
    guc_tenant_id: UUID,
    guc_user_id: UUID,
    target_request_id: str,
) -> int:
    engine = _engine(runtime_db_url)
    with engine.begin() as conn:
        conn.execute(text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"), {"tenant_id": str(guc_tenant_id)})
        conn.execute(text("SELECT set_config('app.current_user_id', :user_id, false)"), {"user_id": str(guc_user_id)})
        return int(
            conn.execute(
                text("SELECT COUNT(*) FROM llm_api_calls WHERE request_id = :request_id"),
                {"request_id": target_request_id},
            ).scalar_one()
        )


def _assert_investigation_exists(runtime_db_url: str, tenant_id: UUID, request_id: str) -> None:
    engine = _engine(runtime_db_url)
    with engine.begin() as conn:
        conn.execute(text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"), {"tenant_id": str(tenant_id)})
        count = int(
            conn.execute(
                text("SELECT COUNT(*) FROM investigations WHERE tenant_id = :tenant_id AND query = :query"),
                {"tenant_id": str(tenant_id), "query": f"provider:{request_id}"},
            ).scalar_one()
        )
    assert count == 1


def _assert_budget_job_exists(runtime_db_url: str, tenant_id: UUID, request_id: str) -> None:
    engine = _engine(runtime_db_url)
    with engine.begin() as conn:
        conn.execute(text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"), {"tenant_id": str(tenant_id)})
        count = int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM budget_optimization_jobs
                    WHERE tenant_id = :tenant_id
                      AND recommendations->>'request_id' = :request_id
                    """
                ),
                {"tenant_id": str(tenant_id), "request_id": request_id},
            ).scalar_one()
        )
    assert count == 1


def _payload(
    *,
    tenant_id: UUID,
    user_id: UUID,
    request_id: str,
    prompt: dict[str, Any],
    max_cost_cents: int = 10,
) -> LLMTaskPayload:
    return LLMTaskPayload(
        tenant_id=tenant_id,
        user_id=user_id,
        correlation_id=request_id,
        request_id=request_id,
        prompt=prompt,
        max_cost_cents=max_cost_cents,
    )


def test_b07_p4_full_chain_runtime_and_operational_invariants() -> None:
    cfg = _config()
    assert celery_app.conf.task_always_eager is False, "E2E runtime proof requires real worker consumption"

    tenant_id = uuid4()
    user_primary = uuid4()
    user_breaker = uuid4()
    user_shutoff = uuid4()

    _seed_tenant(cfg.runtime_sync_url, tenant_id)

    task_rows: dict[str, dict[str, Any]] = {}

    for task_name in ("route", "explanation", "investigation", "budget_optimization"):
        request_id = f"b07-p4-{task_name}-{uuid4().hex[:10]}"
        result = _dispatch(
            task_name,
            _payload(
                tenant_id=tenant_id,
                user_id=user_primary,
                request_id=request_id,
                prompt={"simulated_output_text": f"{task_name}-ok", "cache_enabled": False, "model": "stub:model"},
                max_cost_cents=9,
            ),
        )
        assert result["status"] == "accepted"
        endpoint = _ENDPOINT_BY_TASK[task_name]
        row = _wait_for_row(cfg.runtime_sync_url, tenant_id, user_primary, endpoint, request_id)
        assert row["status"] == "success"
        assert row["provider"] == "stub"
        assert row["provider_attempted"] is True
        task_rows[task_name] = row

        if task_name == "investigation":
            _assert_investigation_exists(cfg.runtime_sync_url, tenant_id, request_id)
        if task_name == "budget_optimization":
            _assert_budget_job_exists(cfg.runtime_sync_url, tenant_id, request_id)

    cache_prompt = {
        "simulated_output_text": "cache-seed",
        "cache_enabled": True,
        "cache_watermark": 17,
        "model": "stub:model",
    }
    cache_req_1 = f"b07-p4-cache-a-{uuid4().hex[:8]}"
    cache_req_2 = f"b07-p4-cache-b-{uuid4().hex[:8]}"

    first_cache = _dispatch(
        "explanation",
        _payload(
            tenant_id=tenant_id,
            user_id=user_primary,
            request_id=cache_req_1,
            prompt=cache_prompt,
            max_cost_cents=8,
        ),
    )
    assert first_cache["status"] == "accepted"
    second_cache = _dispatch(
        "explanation",
        _payload(
            tenant_id=tenant_id,
            user_id=user_primary,
            request_id=cache_req_2,
            prompt=cache_prompt,
            max_cost_cents=8,
        ),
    )
    assert second_cache["status"] == "accepted"

    cache_row = _wait_for_row(
        cfg.runtime_sync_url,
        tenant_id,
        user_primary,
        _ENDPOINT_BY_TASK["explanation"],
        cache_req_2,
    )
    assert cache_row["was_cached"] is True
    assert cache_row["provider_attempted"] is False

    duplicate_req = f"b07-p4-idempotent-{uuid4().hex[:8]}"
    first_dup = _dispatch(
        "explanation",
        _payload(
            tenant_id=tenant_id,
            user_id=user_primary,
            request_id=duplicate_req,
            prompt={"simulated_output_text": "dup", "cache_enabled": False},
            max_cost_cents=4,
        ),
    )
    second_dup = _dispatch(
        "explanation",
        _payload(
            tenant_id=tenant_id,
            user_id=user_primary,
            request_id=duplicate_req,
            prompt={"simulated_output_text": "dup", "cache_enabled": False},
            max_cost_cents=4,
        ),
    )
    assert first_dup["api_call_id"] == second_dup["api_call_id"]
    assert (
        _count_calls(
            cfg.runtime_sync_url,
            tenant_id,
            user_primary,
            _ENDPOINT_BY_TASK["explanation"],
            duplicate_req,
        )
        == 1
    )

    for _ in range(3):
        failed_req = f"b07-p4-breaker-fail-{uuid4().hex[:8]}"
        failed_result = _dispatch(
            "explanation",
            _payload(
                tenant_id=tenant_id,
                user_id=user_breaker,
                request_id=failed_req,
                prompt={"raise_error": True, "cache_enabled": False},
                max_cost_cents=6,
            ),
        )
        assert failed_result["status"] == "failed"

    blocked_req = f"b07-p4-breaker-block-{uuid4().hex[:8]}"
    blocked_result = _dispatch(
        "explanation",
        _payload(
            tenant_id=tenant_id,
            user_id=user_breaker,
            request_id=blocked_req,
            prompt={"simulated_output_text": "should-block", "cache_enabled": False},
            max_cost_cents=6,
        ),
    )
    assert blocked_result["status"] == "blocked"
    assert blocked_result["blocked_reason"] == "breaker_open"
    blocked_row = _wait_for_row(
        cfg.runtime_sync_url,
        tenant_id,
        user_breaker,
        _ENDPOINT_BY_TASK["explanation"],
        blocked_req,
    )
    assert blocked_row["provider_attempted"] is False

    kill_req = f"b07-p4-kill-switch-{uuid4().hex[:8]}"
    kill_result = _dispatch(
        "explanation",
        _payload(
            tenant_id=tenant_id,
            user_id=user_primary,
            request_id=kill_req,
            prompt={"kill_switch": True, "simulated_output_text": "no-provider"},
            max_cost_cents=5,
        ),
    )
    assert kill_result["status"] == "blocked"
    assert kill_result["blocked_reason"] == "provider_kill_switch"
    kill_row = _wait_for_row(
        cfg.runtime_sync_url,
        tenant_id,
        user_primary,
        _ENDPOINT_BY_TASK["explanation"],
        kill_req,
    )
    assert kill_row["provider_attempted"] is False

    _seed_hourly_shutoff(cfg.runtime_sync_url, tenant_id, user_shutoff, "manual_emergency_shutoff")
    shutoff_req = f"b07-p4-shutoff-{uuid4().hex[:8]}"
    shutoff_result = _dispatch(
        "explanation",
        _payload(
            tenant_id=tenant_id,
            user_id=user_shutoff,
            request_id=shutoff_req,
            prompt={"simulated_output_text": "blocked-hourly", "cache_enabled": False},
            max_cost_cents=3,
        ),
    )
    assert shutoff_result["status"] == "blocked"
    shutoff_row = _wait_for_row(
        cfg.runtime_sync_url,
        tenant_id,
        user_shutoff,
        _ENDPOINT_BY_TASK["explanation"],
        shutoff_req,
    )
    assert shutoff_row["provider_attempted"] is False

    success_row = task_rows["explanation"]
    assert success_row["reasoning_trace_ref"] is not None
    assert isinstance(success_row["reasoning_trace_ref"], dict)
    response_meta = success_row["response_metadata_ref"] or {}
    assert response_meta.get("boundary_id") == "b07_p3_aisuite_chokepoint"

    vis_ok = _visible_count_for_identity(
        cfg.runtime_sync_url,
        guc_tenant_id=tenant_id,
        guc_user_id=user_primary,
        target_request_id=cache_req_1,
    )
    vis_wrong_user = _visible_count_for_identity(
        cfg.runtime_sync_url,
        guc_tenant_id=tenant_id,
        guc_user_id=uuid4(),
        target_request_id=cache_req_1,
    )
    vis_wrong_tenant = _visible_count_for_identity(
        cfg.runtime_sync_url,
        guc_tenant_id=uuid4(),
        guc_user_id=user_primary,
        target_request_id=cache_req_1,
    )
    assert vis_ok == 1
    assert vis_wrong_user == 0
    assert vis_wrong_tenant == 0

    probe = {
        "tenant_id": str(tenant_id),
        "primary_user_id": str(user_primary),
        "breaker_user_id": str(user_breaker),
        "shutoff_user_id": str(user_shutoff),
        "task_rows": {
            key: {
                "endpoint": value["endpoint"],
                "request_id": value["request_id"],
                "status": value["status"],
                "provider": value["provider"],
            }
            for key, value in task_rows.items()
        },
        "cache_request_id": cache_req_2,
        "breaker_blocked_request_id": blocked_req,
        "kill_switch_request_id": kill_req,
        "shutoff_request_id": shutoff_req,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    (cfg.artifact_dir / "runtime_db_probe.json").write_text(json.dumps(probe, indent=2), encoding="utf-8")
