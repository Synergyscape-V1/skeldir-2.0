from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID

import pytest
from sqlalchemy import text

from app.bayesian import authority_liveness
from app.bayesian.authority_liveness import (
    RECOVERY_ORPHAN_THRESHOLD_MS,
    dispatch_due_feature_authority_builds,
    dispatch_feature_authority_build_by_key,
    request_feature_authority_build,
)
from app.bayesian.enums import FallbackReason
from app.db.session import engine, get_session


START = datetime(2026, 5, 1, tzinfo=timezone.utc)
END = START + timedelta(days=30)


def _require_db_proofs() -> bool:
    return os.getenv("SKELDIR_B24_P4_REQUIRE_DB_PROOFS", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


async def _assert_p4_table_exists(table_name: str) -> None:
    async with engine.begin() as conn:
        result = await conn.execute(
            text("SELECT to_regclass(:qualified_name)"),
            {"qualified_name": f"public.{table_name}"},
        )
    if result.scalar() is None:
        message = f"B2.4-P4 runtime proof table is missing: {table_name}"
        if _require_db_proofs():
            pytest.fail(message)
        pytest.skip(message)


def _snapshot(tenant_id: UUID, *, suffix: str = "a") -> SimpleNamespace:
    return SimpleNamespace(
        tenant_id=tenant_id,
        model_type="bayesian_attribution_confidence",
        model_version=f"v1-runtime-{suffix}",
        source_window_start=START,
        source_window_end=END,
        source_snapshot_hash=(suffix * 64)[:64],
    )


@pytest.mark.asyncio
async def test_b24_p4_runtime_deprecated_profiling_table_absent() -> None:
    async with engine.begin() as conn:
        result = await conn.execute(
            text(
                "SELECT to_regclass('public.b24_p4_profiling_leases') "
                "AS deprecated_p4_profiling_leases"
            )
        )
    assert result.scalar_one() is None


@pytest.mark.asyncio
async def test_b24_p4_runtime_authority_build_request_outbox_and_causal_dispatch(
    test_tenant_pair, monkeypatch
) -> None:
    await _assert_p4_table_exists("b24_feature_authority_build_outbox")
    tenant_id, _ = test_tenant_pair
    snapshot = _snapshot(tenant_id, suffix="c")
    published: list[tuple[str, str]] = []

    def _capture_dispatch(*, tenant_id: UUID, dispatch_key: str) -> str:
        published.append((str(tenant_id), dispatch_key))
        return "captured-dispatch-task"

    monkeypatch.setattr(
        authority_liveness, "publish_feature_authority_dispatch", _capture_dispatch
    )
    async with get_session(tenant_id) as session:
        result = await request_feature_authority_build(
            session,
            snapshot=snapshot,
            reason=FallbackReason.CARDINALITY_AUTHORITY_MISSING,
            detail="runtime missing authority",
        )

    assert published == [(str(tenant_id), result.dispatch_key)]
    dispatched: list[str] = []
    async with get_session(tenant_id) as session:
        row = await dispatch_feature_authority_build_by_key(
            session,
            tenant_id=tenant_id,
            dispatch_key=result.dispatch_key,
            publish=lambda leased: dispatched.append(str(leased.id)) or "build-task",
        )
    assert row is not None
    assert dispatched == [str(row.id)]

    async with get_session(tenant_id) as session:
        status = (
            await session.execute(
                text(
                    """
                    SELECT status
                    FROM public.b24_feature_authority_build_outbox
                    WHERE tenant_id = :tenant_id
                      AND dispatch_key = :dispatch_key
                    """
                ),
                {"tenant_id": str(tenant_id), "dispatch_key": result.dispatch_key},
            )
        ).scalar_one()
    assert status == "dispatched"


@pytest.mark.asyncio
async def test_b24_p4_runtime_sweeper_ignores_fresh_pending_outbox(
    test_tenant_pair, monkeypatch
) -> None:
    await _assert_p4_table_exists("b24_feature_authority_build_outbox")
    tenant_id, _ = test_tenant_pair
    snapshot = _snapshot(tenant_id, suffix="d")
    monkeypatch.setattr(
        authority_liveness,
        "publish_feature_authority_dispatch",
        lambda **_kwargs: "captured-dispatch-task",
    )
    async with get_session(tenant_id) as session:
        await request_feature_authority_build(
            session,
            snapshot=snapshot,
            reason=FallbackReason.CARDINALITY_AUTHORITY_MISSING,
            detail="fresh pending row",
        )
    async with get_session(tenant_id) as session:
        rows = await dispatch_due_feature_authority_builds(
            session,
            publish=lambda _row: "unexpected",
            batch_size=5,
        )
    assert rows == []
    assert RECOVERY_ORPHAN_THRESHOLD_MS > 0


@pytest.mark.asyncio
async def test_b24_p4_runtime_sweeper_claims_retry_due_rows_only(
    test_tenant_pair, monkeypatch
) -> None:
    await _assert_p4_table_exists("b24_feature_authority_build_outbox")
    tenant_id, _ = test_tenant_pair
    snapshot = _snapshot(tenant_id, suffix="e")
    monkeypatch.setattr(
        authority_liveness,
        "publish_feature_authority_dispatch",
        lambda **_kwargs: "captured-dispatch-task",
    )
    async with get_session(tenant_id) as session:
        result = await request_feature_authority_build(
            session,
            snapshot=snapshot,
            reason=FallbackReason.CARDINALITY_AUTHORITY_MISSING,
            detail="retry due row",
        )
        await session.execute(
            text(
                """
                UPDATE public.b24_feature_authority_build_outbox
                SET status = 'failed_retryable',
                    next_attempt_at = now() - interval '1 second',
                    updated_at = now()
                WHERE tenant_id = :tenant_id
                  AND dispatch_key = :dispatch_key
                """
            ),
            {"tenant_id": str(tenant_id), "dispatch_key": result.dispatch_key},
        )
    async with get_session(tenant_id) as session:
        rows = await dispatch_due_feature_authority_builds(
            session,
            publish=lambda _row: "recovered-build-task",
            batch_size=5,
        )
    assert len(rows) == 1
    assert rows[0].source_snapshot_hash == snapshot.source_snapshot_hash


@pytest.mark.asyncio
async def test_b24_p4_runtime_rls_force_enabled_for_p4_tables() -> None:
    async with engine.begin() as conn:
        rows = (
            await conn.execute(
                text(
                    """
                    SELECT relname, relrowsecurity, relforcerowsecurity
                    FROM pg_class
                    WHERE relname IN (
                        'b24_active_execution_leases',
                        'b24_feature_authority_build_requests',
                        'b24_feature_authority_build_outbox',
                        'b24_source_window_feature_authority'
                    )
                    ORDER BY relname
                    """
                )
            )
        ).mappings().all()
    assert {row["relname"] for row in rows} == {
        "b24_active_execution_leases",
        "b24_feature_authority_build_requests",
        "b24_feature_authority_build_outbox",
        "b24_source_window_feature_authority",
    }
    assert all(row["relrowsecurity"] for row in rows)
    assert all(row["relforcerowsecurity"] for row in rows)
