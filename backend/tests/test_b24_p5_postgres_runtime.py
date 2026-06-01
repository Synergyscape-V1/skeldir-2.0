from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.bayesian.compiledir_reaper import create_compiledir_lease
from app.bayesian.sampler_supervisor import (
    build_child_env_for_lease,
    run_supervised_sampler,
    sampler_child_command,
)
from app.core.secrets import get_database_url
from app.db.session import engine, get_session
from app.tasks.bayesian import _emit_fallback_event


START = datetime(2026, 5, 1, tzinfo=timezone.utc)
END = datetime(2026, 6, 1, tzinfo=timezone.utc)


def _require_db_proofs() -> bool:
    return os.getenv("SKELDIR_B24_P5_REQUIRE_DB_PROOFS", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


async def _assert_table_exists(table_name: str) -> None:
    try:
        async with engine.begin() as conn:
            result = await conn.execute(
                text("SELECT to_regclass(:qualified_name)"),
                {"qualified_name": f"public.{table_name}"},
            )
    except OperationalError as exc:
        message = f"B2.4-P5 PostgreSQL runtime proof unavailable: {exc}"
        if _require_db_proofs():
            pytest.fail(message)
        pytest.skip(message)
    if result.scalar() is None:
        message = f"B2.4-P5 PostgreSQL runtime proof table is missing: {table_name}"
        if _require_db_proofs():
            pytest.fail(message)
        pytest.skip(message)


async def _insert_fit(tenant_id: UUID, *, fit_id: UUID, status: str) -> None:
    async with get_session(tenant_id) as session:
        await session.execute(
            text(
                """
                INSERT INTO public.bayesian_model_fits (
                    tenant_id,
                    id,
                    model_type,
                    model_version,
                    source_window_start,
                    source_window_end,
                    source_snapshot_hash,
                    status,
                    eligibility_status,
                    data_completeness_status,
                    fallback_applied,
                    max_runtime_seconds,
                    max_samples,
                    max_cores
                )
                VALUES (
                    :tenant_id,
                    :fit_id,
                    'bayesian_attribution_confidence',
                    :model_version,
                    :source_window_start,
                    :source_window_end,
                    :source_snapshot_hash,
                    :status,
                    'eligible',
                    'complete',
                    false,
                    60,
                    100,
                    1
                )
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "fit_id": str(fit_id),
                "model_version": f"v1-p5-runtime-{str(tenant_id)[:8]}",
                "source_window_start": START,
                "source_window_end": END,
                "source_snapshot_hash": ("5" + str(tenant_id).replace("-", ""))[
                    :64
                ].ljust(64, "5"),
                "status": status,
            },
        )


async def _count_airgap_probe_connections() -> int:
    async with engine.begin() as conn:
        result = await conn.execute(
            text(
                """
                SELECT count(*)
                FROM pg_stat_activity
                WHERE datname = current_database()
                  AND application_name = 'b24_p5_child_airgap'
                """
            )
        )
    return int(result.scalar_one())


@pytest.mark.asyncio
@pytest.mark.integration
async def test_b24_p5_worker_timeout_fallback_persists_tenant_scoped_fit_state(
    test_tenant_pair,
) -> None:
    await _assert_table_exists("bayesian_model_fits")
    tenant_a, tenant_b = test_tenant_pair
    shared_fit_id = uuid4()
    correlation_id = uuid4()

    await _insert_fit(tenant_a, fit_id=shared_fit_id, status="running")
    await _insert_fit(tenant_b, fit_id=shared_fit_id, status="running")

    payload = _emit_fallback_event(
        task_id="p5-durable-timeout-proof",
        tenant_id=tenant_a,
        correlation_id=correlation_id,
        elapsed_ms=7250,
        fit_id=shared_fit_id,
    )

    assert payload["durable_timeout_written"] is True
    assert payload["status"] == "fallback"
    assert payload["fallback_triggered"] is True

    async with get_session(tenant_a) as session:
        tenant_a_row = (
            (
                await session.execute(
                    text(
                        """
                    SELECT status,
                           fallback_applied,
                           fallback_reason,
                           runtime_seconds,
                           completed_at IS NOT NULL AS completed
                    FROM public.bayesian_model_fits
                    WHERE tenant_id = :tenant_id
                      AND id = :fit_id
                    """
                    ),
                    {"tenant_id": str(tenant_a), "fit_id": str(shared_fit_id)},
                )
            )
            .mappings()
            .one()
        )

    assert tenant_a_row == {
        "status": "timeout",
        "fallback_applied": True,
        "fallback_reason": "timeout",
        "runtime_seconds": 7,
        "completed": True,
    }

    async with get_session(tenant_b) as session:
        tenant_b_row = (
            (
                await session.execute(
                    text(
                        """
                    SELECT status,
                           fallback_applied,
                           fallback_reason,
                           runtime_seconds,
                           completed_at IS NOT NULL AS completed
                    FROM public.bayesian_model_fits
                    WHERE tenant_id = :tenant_id
                      AND id = :fit_id
                    """
                    ),
                    {"tenant_id": str(tenant_b), "fit_id": str(shared_fit_id)},
                )
            )
            .mappings()
            .one()
        )

    assert tenant_b_row == {
        "status": "running",
        "fallback_applied": False,
        "fallback_reason": None,
        "runtime_seconds": None,
        "completed": False,
    }


@pytest.mark.asyncio
@pytest.mark.integration
async def test_b24_p5_sampler_child_opens_zero_postgres_connections(
    test_tenant_pair,
    monkeypatch,
) -> None:
    await _assert_table_exists("bayesian_model_fits")
    database_url = get_database_url()
    separator = "&" if "?" in database_url else "?"
    monkeypatch.setenv(
        "DATABASE_URL",
        f"{database_url}{separator}application_name=b24_p5_child_airgap",
    )
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "must-not-cross-child-boundary")

    assert await _count_airgap_probe_connections() == 0

    lease = create_compiledir_lease(execution_id=f"child-db-airgap-{uuid4().hex}")
    result = run_supervised_sampler(
        sampler_child_command(mode="env-report", seconds=1),
        deadline_seconds=5,
        env=build_child_env_for_lease(lease),
        compiledir_lease=lease,
    )

    assert result.status == "completed"
    assert result.returncode == 0
    assert await _count_airgap_probe_connections() == 0
