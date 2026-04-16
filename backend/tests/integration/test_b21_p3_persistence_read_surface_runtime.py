"""B2.1-P3 runtime proofs for persisted projection authority read surface."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.db import engine
from app.db.session import set_tenant_guc
from app.main import app
from app.security.auth import AuthContext, get_auth_context
from tests.conftest import _insert_tenant


pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


def _auth_context(*, tenant_id: UUID, user_id: UUID) -> AuthContext:
    now_epoch = int(datetime.now(timezone.utc).timestamp())
    return AuthContext(
        tenant_id=tenant_id,
        user_id=user_id,
        jti=uuid4(),
        issued_at_epoch=now_epoch,
        subject=str(user_id),
        issuer="https://issuer.skeldir.test",
        audience="skeldir-api",
        claims={"role": "viewer", "roles": ["viewer"], "scopes": ["viewer"]},
    )


async def _ensure_runtime_tables() -> None:
    async with engine.begin() as conn:
        required_tables = (
            "attribution_events",
            "attribution_allocations",
            "attribution_recompute_jobs",
            "session_authority",
            "channel_taxonomy",
        )
        for table_name in required_tables:
            present = await conn.scalar(
                text("SELECT to_regclass(:table_name)"),
                {"table_name": f"public.{table_name}"},
            )
            if present is None:
                pytest.skip(f"B2.1-P3 runtime proofs require table: {table_name}")

        projection_column = await conn.scalar(
            text(
                """
                SELECT COUNT(*)
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'attribution_allocations'
                  AND column_name = 'recompute_job_id'
                """
            )
        )
        if int(projection_column or 0) == 0:
            pytest.skip("B2.1-P3 runtime proofs require attribution_allocations.recompute_job_id")


async def _ensure_channel_codes(codes: list[str]) -> None:
    async with engine.begin() as conn:
        for code in codes:
            await conn.execute(
                text(
                    """
                    INSERT INTO channel_taxonomy (code, family, is_paid, display_name, is_active, state)
                    VALUES (:code, 'b21_p3', false, :display_name, true, 'active')
                    ON CONFLICT (code) DO NOTHING
                    """
                ),
                {"code": code, "display_name": code.replace("_", " ").title()},
            )


async def _seed_session_authority(
    *,
    tenant_id: UUID,
    session_id: UUID,
    issued_at: datetime,
    expires_at: datetime,
) -> None:
    async with engine.begin() as conn:
        await set_tenant_guc(conn, tenant_id, local=True)
        await conn.execute(
            text(
                """
                INSERT INTO session_authority (
                    id,
                    tenant_id,
                    session_id,
                    issued_at,
                    expires_at,
                    last_seen_at,
                    invalidated_at,
                    invalidation_reason,
                    issued_by,
                    created_at,
                    updated_at
                ) VALUES (
                    :id,
                    :tenant_id,
                    :session_id,
                    :issued_at,
                    :expires_at,
                    :last_seen_at,
                    NULL,
                    NULL,
                    'b21_p3_runtime',
                    :created_at,
                    :updated_at
                )
                ON CONFLICT (tenant_id, session_id)
                DO UPDATE SET
                    issued_at = EXCLUDED.issued_at,
                    expires_at = EXCLUDED.expires_at,
                    last_seen_at = EXCLUDED.last_seen_at,
                    invalidated_at = NULL,
                    invalidation_reason = NULL,
                    updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "id": str(uuid4()),
                "tenant_id": str(tenant_id),
                "session_id": str(session_id),
                "issued_at": issued_at,
                "expires_at": expires_at,
                "last_seen_at": issued_at + timedelta(minutes=1),
                "created_at": issued_at,
                "updated_at": issued_at,
            },
        )


async def _seed_projection_fixture(
    *,
    tenant_id: UUID,
    recompute_job_id: UUID,
    model_type: str,
    model_version: str,
    window_start: datetime,
    window_end: datetime,
    session_id: UUID,
    rows: list[tuple[str, int, str, str]],
) -> None:
    async with engine.begin() as conn:
        await set_tenant_guc(conn, tenant_id, local=True)
        await conn.execute(
            text(
                """
                INSERT INTO attribution_recompute_jobs (
                    id,
                    tenant_id,
                    window_start,
                    window_end,
                    model_version,
                    status,
                    run_count,
                    last_correlation_id,
                    replay_event_created_ceiling,
                    created_at,
                    updated_at,
                    started_at,
                    finished_at
                ) VALUES (
                    :id,
                    :tenant_id,
                    :window_start,
                    :window_end,
                    :model_version,
                    'succeeded',
                    1,
                    :last_correlation_id,
                    :replay_event_created_ceiling,
                    now(),
                    now(),
                    :started_at,
                    :finished_at
                )
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {
                "id": str(recompute_job_id),
                "tenant_id": str(tenant_id),
                "window_start": window_start,
                "window_end": window_end,
                "model_version": model_version,
                "last_correlation_id": str(uuid4()),
                "replay_event_created_ceiling": window_end,
                "started_at": window_start,
                "finished_at": window_end,
            },
        )

        occurred_at = window_start + timedelta(minutes=5)
        for index, (channel_code, revenue_cents, allocation_ratio, confidence_score) in enumerate(rows):
            event_id = uuid4()
            idempotency_key = f"b21-p3-{tenant_id.hex[:8]}-{index}-{event_id.hex[:12]}"
            # RAW_SQL_ALLOWLIST: deterministic integration fixture seed for P3 runtime path validation.
            await conn.execute(
                text(
                    """
                    INSERT INTO attribution_events (
                        id,
                        tenant_id,
                        occurred_at,
                        external_event_id,
                        correlation_id,
                        session_id,
                        revenue_cents,
                        raw_payload,
                        idempotency_key,
                        event_type,
                        channel,
                        campaign_id,
                        conversion_value_cents,
                        currency,
                        event_timestamp,
                        processed_at,
                        processing_status,
                        retry_count,
                        created_at,
                        updated_at
                    ) VALUES (
                        :id,
                        :tenant_id,
                        :occurred_at,
                        :external_event_id,
                        :correlation_id,
                        :session_id,
                        :revenue_cents,
                        CAST(:raw_payload AS jsonb),
                        :idempotency_key,
                        'purchase',
                        :channel,
                        'cmp-b21-p3',
                        :conversion_value_cents,
                        'USD',
                        :event_timestamp,
                        :processed_at,
                        'processed',
                        0,
                        :created_at,
                        :updated_at
                    )
                    ON CONFLICT (tenant_id, idempotency_key) DO NOTHING
                    """
                ),
                {
                    "id": str(event_id),
                    "tenant_id": str(tenant_id),
                    "occurred_at": occurred_at,
                    "external_event_id": f"evt-{event_id.hex[:12]}",
                    "correlation_id": str(uuid4()),
                    "session_id": str(session_id),
                    "revenue_cents": int(revenue_cents),
                    "raw_payload": (
                        '{"global_idempotency_hash":"'
                        + f"{event_id.hex:0<64}"[:64]
                        + '"}'
                    ),
                    "idempotency_key": idempotency_key,
                    "channel": channel_code,
                    "conversion_value_cents": int(revenue_cents),
                    "event_timestamp": occurred_at,
                    "processed_at": occurred_at + timedelta(minutes=1),
                    "created_at": occurred_at,
                    "updated_at": occurred_at,
                },
            )
            # RAW_SQL_ALLOWLIST: deterministic integration fixture seed for persisted allocation projection checks.
            await conn.execute(
                text(
                    """
                    INSERT INTO attribution_allocations (
                        id,
                        tenant_id,
                        event_id,
                        recompute_job_id,
                        channel_code,
                        allocated_revenue_cents,
                        allocation_ratio,
                        model_version,
                        model_type,
                        confidence_score,
                        verified,
                        created_at,
                        updated_at
                    ) VALUES (
                        :id,
                        :tenant_id,
                        :event_id,
                        :recompute_job_id,
                        :channel_code,
                        :allocated_revenue_cents,
                        :allocation_ratio,
                        :model_version,
                        :model_type,
                        :confidence_score,
                        false,
                        :created_at,
                        :updated_at
                    )
                    ON CONFLICT (id) DO NOTHING
                    """
                ),
                {
                    "id": str(uuid4()),
                    "tenant_id": str(tenant_id),
                    "event_id": str(event_id),
                    "recompute_job_id": str(recompute_job_id),
                    "channel_code": channel_code,
                    "allocated_revenue_cents": int(revenue_cents),
                    "allocation_ratio": allocation_ratio,
                    "model_version": model_version,
                    "model_type": model_type,
                    "confidence_score": confidence_score,
                    "created_at": occurred_at,
                    "updated_at": occurred_at,
                },
            )


async def _job_run_count(*, tenant_id: UUID, recompute_job_id: UUID) -> int:
    async with engine.begin() as conn:
        await set_tenant_guc(conn, tenant_id, local=True)
        value = await conn.scalar(
            text(
                """
                SELECT run_count
                FROM attribution_recompute_jobs
                WHERE tenant_id = :tenant_id
                  AND id = :recompute_job_id
                """
            ),
            {"tenant_id": str(tenant_id), "recompute_job_id": str(recompute_job_id)},
        )
        return int(value or 0)


@pytest.mark.asyncio
async def test_b21_p3_channels_endpoint_reads_projection_without_recompute_and_preserves_decimal_strings() -> None:
    await _ensure_runtime_tables()
    await _ensure_channel_codes(["direct", "email"])

    tenant_id = uuid4()
    user_id = uuid4()
    session_id = uuid4()
    recompute_job_id = uuid4()
    window_start = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(hours=2)
    window_end = window_start + timedelta(hours=1)
    model_type = "linear"
    model_version = "b21-p3-runtime::model_type=linear"

    async with engine.begin() as conn:
        await _insert_tenant(conn, tenant_id, api_key_hash=f"test_hash_{tenant_id}")
    authority_now = datetime.now(timezone.utc).replace(microsecond=0)
    await _seed_session_authority(
        tenant_id=tenant_id,
        session_id=session_id,
        issued_at=authority_now - timedelta(minutes=5),
        expires_at=authority_now + timedelta(hours=1),
    )
    await _seed_projection_fixture(
        tenant_id=tenant_id,
        recompute_job_id=recompute_job_id,
        model_type=model_type,
        model_version=model_version,
        window_start=window_start,
        window_end=window_end,
        session_id=session_id,
        rows=[
            ("direct", 200, "0.66667", "0.917"),
            ("email", 100, "0.33333", "0.833"),
        ],
    )

    before_run_count = await _job_run_count(
        tenant_id=tenant_id, recompute_job_id=recompute_job_id
    )

    async def _auth_override() -> AuthContext:
        return _auth_context(tenant_id=tenant_id, user_id=user_id)

    app.dependency_overrides[get_auth_context] = _auth_override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            missing_shape = await client.get(
                "/api/attribution/channels",
                headers={"X-Correlation-ID": str(uuid4())},
            )
            assert missing_shape.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

            response = await client.get(
                "/api/attribution/channels",
                params={
                    "model_type": model_type,
                    "recompute_job_id": str(recompute_job_id),
                },
                headers={"X-Correlation-ID": str(uuid4())},
            )
    finally:
        app.dependency_overrides.pop(get_auth_context, None)

    assert response.status_code == status.HTTP_200_OK, response.text
    payload = response.json()
    assert payload["tenant_id"] == str(tenant_id)
    assert payload["projection"]["recompute_job_id"] == str(recompute_job_id)
    assert payload["projection"]["model_type"] == model_type
    assert payload["projection"]["model_version"] == model_version
    assert payload["total_revenue_cents"] == 300
    assert payload["total_revenue"] == 3.0
    assert len(payload["channels"]) == 2

    direct = next(channel for channel in payload["channels"] if channel["channel_code"] == "direct")
    email = next(channel for channel in payload["channels"] if channel["channel_code"] == "email")
    assert direct["allocation_ratio"] == "0.66667"
    assert direct["attribution_weight"] == "0.66667"
    assert isinstance(direct["confidence_score"], str)
    assert email["allocation_ratio"] == "0.33333"
    assert email["attribution_weight"] == "0.33333"
    assert isinstance(email["confidence_score"], str)

    after_run_count = await _job_run_count(
        tenant_id=tenant_id, recompute_job_id=recompute_job_id
    )
    assert after_run_count == before_run_count


@pytest.mark.asyncio
async def test_b21_p3_cross_tenant_projection_identity_is_fail_closed() -> None:
    await _ensure_runtime_tables()
    await _ensure_channel_codes(["direct"])

    tenant_a = uuid4()
    tenant_b = uuid4()
    session_a = uuid4()
    session_b = uuid4()
    window_start = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(hours=2)
    window_end = window_start + timedelta(hours=1)
    job_a = uuid4()
    job_b = uuid4()

    async with engine.begin() as conn:
        await _insert_tenant(conn, tenant_a, api_key_hash=f"test_hash_{tenant_a}")
        await _insert_tenant(conn, tenant_b, api_key_hash=f"test_hash_{tenant_b}")
    authority_now = datetime.now(timezone.utc).replace(microsecond=0)
    await _seed_session_authority(
        tenant_id=tenant_a,
        session_id=session_a,
        issued_at=authority_now - timedelta(minutes=5),
        expires_at=authority_now + timedelta(hours=1),
    )
    await _seed_session_authority(
        tenant_id=tenant_b,
        session_id=session_b,
        issued_at=authority_now - timedelta(minutes=5),
        expires_at=authority_now + timedelta(hours=1),
    )
    await _seed_projection_fixture(
        tenant_id=tenant_a,
        recompute_job_id=job_a,
        model_type="deterministic_baseline",
        model_version="b21-p3-baseline",
        window_start=window_start,
        window_end=window_end,
        session_id=session_a,
        rows=[("direct", 100, "1.00000", "1.000")],
    )
    await _seed_projection_fixture(
        tenant_id=tenant_b,
        recompute_job_id=job_b,
        model_type="deterministic_baseline",
        model_version="b21-p3-baseline",
        window_start=window_start,
        window_end=window_end,
        session_id=session_b,
        rows=[("direct", 200, "1.00000", "1.000")],
    )

    active_context = {"value": _auth_context(tenant_id=tenant_a, user_id=uuid4())}

    async def _auth_override() -> AuthContext:
        return active_context["value"]

    app.dependency_overrides[get_auth_context] = _auth_override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            success = await client.get(
                "/api/attribution/channels",
                params={
                    "model_type": "deterministic_baseline",
                    "recompute_job_id": str(job_a),
                },
                headers={"X-Correlation-ID": str(uuid4())},
            )
            assert success.status_code == status.HTTP_200_OK, success.text

            active_context["value"] = _auth_context(tenant_id=tenant_b, user_id=uuid4())
            cross_tenant = await client.get(
                "/api/attribution/channels",
                params={
                    "model_type": "deterministic_baseline",
                    "recompute_job_id": str(job_a),
                },
                headers={"X-Correlation-ID": str(uuid4())},
            )
    finally:
        app.dependency_overrides.pop(get_auth_context, None)

    assert cross_tenant.status_code == status.HTTP_404_NOT_FOUND
    assert cross_tenant.json()["code"] == "ATTRIBUTION_PROJECTION_NOT_FOUND"


@pytest.mark.asyncio
async def test_b21_p3_projection_window_bound_exceeds_limit_fails_closed() -> None:
    await _ensure_runtime_tables()
    await _ensure_channel_codes(["direct"])

    tenant_id = uuid4()
    user_id = uuid4()
    session_id = uuid4()
    recompute_job_id = uuid4()
    window_start = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(days=45)
    window_end = datetime.now(timezone.utc).replace(microsecond=0)

    async with engine.begin() as conn:
        await _insert_tenant(conn, tenant_id, api_key_hash=f"test_hash_{tenant_id}")
    authority_now = datetime.now(timezone.utc).replace(microsecond=0)
    await _seed_session_authority(
        tenant_id=tenant_id,
        session_id=session_id,
        issued_at=authority_now - timedelta(minutes=5),
        expires_at=authority_now + timedelta(hours=1),
    )
    await _seed_projection_fixture(
        tenant_id=tenant_id,
        recompute_job_id=recompute_job_id,
        model_type="deterministic_baseline",
        model_version="b21-p3-baseline",
        window_start=window_start,
        window_end=window_end,
        session_id=session_id,
        rows=[("direct", 100, "1.00000", "1.000")],
    )

    async def _auth_override() -> AuthContext:
        return _auth_context(tenant_id=tenant_id, user_id=user_id)

    app.dependency_overrides[get_auth_context] = _auth_override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/attribution/channels",
                params={
                    "model_type": "deterministic_baseline",
                    "recompute_job_id": str(recompute_job_id),
                },
                headers={"X-Correlation-ID": str(uuid4())},
            )
    finally:
        app.dependency_overrides.pop(get_auth_context, None)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    body = response.json()
    assert body["code"] == "ATTRIBUTION_WINDOW_OUT_OF_RANGE"
