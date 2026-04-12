from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from uuid import UUID, uuid4

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError

from app.celery_app import celery_app
from app.main import app
from app.security.auth import AuthContext, get_auth_context
from app.tasks.attribution import recompute_window
from app.tasks.authority import (
    AUTHORITY_ENVELOPE_HEADER,
    SystemAuthorityEnvelope,
    authority_envelope_payload,
)


os.environ.setdefault("TESTING", "1")
os.environ.setdefault("CONTRACT_TESTING", "0")


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required for B2.1-P0 closeout runtime proofs")
    return value


def _runtime_async_url() -> str:
    return _require_env("DATABASE_URL")


def _runtime_sync_url() -> str:
    raw = _runtime_async_url()
    if raw.startswith("postgresql+asyncpg://"):
        return raw.replace("postgresql+asyncpg://", "postgresql://", 1)
    return raw


def _migration_sync_url() -> str:
    raw = _require_env("MIGRATION_DATABASE_URL")
    if raw.startswith("postgresql+asyncpg://"):
        return raw.replace("postgresql+asyncpg://", "postgresql://", 1)
    return raw


def _seed_tenant(conn, tenant_id: UUID, label: str) -> None:
    conn.execute(
        text(
            """
            INSERT INTO public.tenants (
                id, name, api_key_hash, notification_email, created_at, updated_at
            ) VALUES (
                :tenant_id, :name, :api_key_hash, :notification_email, now(), now()
            )
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "name": f"{label}-{tenant_id.hex[:8]}",
            "api_key_hash": f"{label}-key-{tenant_id.hex[:8]}",
            "notification_email": f"{label}-{tenant_id.hex[:8]}@example.test",
        },
    )


def _set_tenant_guc(conn, tenant_id: UUID) -> None:
    conn.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )


def _ensure_channel_taxonomy_code(conn, code: str) -> None:
    conn.execute(
        text(
            """
            INSERT INTO public.channel_taxonomy (code, family, is_paid, display_name, is_active, state)
            VALUES (:code, 'baseline', false, :display_name, true, 'active')
            ON CONFLICT (code) DO NOTHING
            """
        ),
        {"code": code, "display_name": code.replace("_", " ").title()},
    )


def _insert_session_authority(
    conn,
    *,
    tenant_id: UUID,
    session_id: UUID,
    issued_at: datetime,
) -> None:
    _set_tenant_guc(conn, tenant_id)
    conn.execute(
        text(
            """
            INSERT INTO public.session_authority (
                id,
                tenant_id,
                session_id,
                issued_at,
                expires_at,
                last_seen_at,
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
                'b21_p0_runtime_proof',
                now(),
                now()
            )
            ON CONFLICT (tenant_id, session_id) DO UPDATE SET
                issued_at = EXCLUDED.issued_at,
                expires_at = EXCLUDED.expires_at,
                last_seen_at = EXCLUDED.last_seen_at,
                updated_at = now()
            """
        ),
        {
            "id": str(uuid4()),
            "tenant_id": str(tenant_id),
            "session_id": str(session_id),
            "issued_at": issued_at,
            "expires_at": issued_at + timedelta(hours=23),
            "last_seen_at": issued_at + timedelta(minutes=1),
        },
    )


def _insert_event(
    conn,
    *,
    event_id: UUID,
    tenant_id: UUID,
    session_id: UUID,
    occurred_at: datetime,
    idempotency_key: str,
    channel: str,
    revenue_cents: int,
) -> None:
    _set_tenant_guc(conn, tenant_id)
    # RAW_SQL_ALLOWLIST: deterministic tenant-scoped attribution event seed for runtime closeout proofs.
    conn.execute(
        text(
            """
            INSERT INTO public.attribution_events (
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
                '{}'::jsonb,
                :idempotency_key,
                'conversion',
                :channel,
                NULL,
                :revenue_cents,
                'USD',
                :occurred_at,
                now(),
                'processed',
                0,
                now(),
                now()
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
            "revenue_cents": revenue_cents,
            "idempotency_key": idempotency_key,
            "channel": channel,
        },
    )


def _insert_allocation(
    conn,
    *,
    allocation_id: UUID,
    tenant_id: UUID,
    event_id: UUID,
    channel_code: str,
    revenue_cents: int,
) -> None:
    _set_tenant_guc(conn, tenant_id)
    conn.execute(
        text(
            """
            INSERT INTO public.attribution_allocations (
                id,
                tenant_id,
                event_id,
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
                :channel_code,
                :revenue_cents,
                1.0,
                'b21-closeout',
                'deterministic_baseline',
                1.0,
                true,
                now(),
                now()
            )
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {
            "id": str(allocation_id),
            "tenant_id": str(tenant_id),
            "event_id": str(event_id),
            "channel_code": channel_code,
            "revenue_cents": revenue_cents,
        },
    )


def _insert_ephemeral_resolution_rows(conn, *, tenant_id: UUID, session_id: UUID) -> None:
    _set_tenant_guc(conn, tenant_id)
    now_utc = datetime.now(timezone.utc)
    conn.execute(
        text(
            """
            INSERT INTO public.ephemeral_order_resolution (
                id, tenant_id, order_id, session_id, observed_at, expires_at, source, created_at, updated_at
            ) VALUES (
                :id, :tenant_id, :order_id, :session_id, :observed_at, :expires_at, 'b21-closeout', now(), now()
            )
            ON CONFLICT (tenant_id, order_id) DO UPDATE SET
                session_id = EXCLUDED.session_id,
                observed_at = EXCLUDED.observed_at,
                expires_at = EXCLUDED.expires_at,
                updated_at = now()
            """
        ),
        {
            "id": str(uuid4()),
            "tenant_id": str(tenant_id),
            "order_id": f"order-{tenant_id.hex[:8]}",
            "session_id": str(session_id),
            "observed_at": now_utc,
            "expires_at": now_utc + timedelta(hours=1),
        },
    )
    conn.execute(
        text(
            """
            INSERT INTO public.ephemeral_click_resolution (
                id, tenant_id, click_id, session_id, observed_at, expires_at, source, created_at, updated_at
            ) VALUES (
                :id, :tenant_id, :click_id, :session_id, :observed_at, :expires_at, 'b21-closeout', now(), now()
            )
            ON CONFLICT (tenant_id, click_id) DO UPDATE SET
                session_id = EXCLUDED.session_id,
                observed_at = EXCLUDED.observed_at,
                expires_at = EXCLUDED.expires_at,
                updated_at = now()
            """
        ),
        {
            "id": str(uuid4()),
            "tenant_id": str(tenant_id),
            "click_id": f"click-{tenant_id.hex[:8]}",
            "session_id": str(session_id),
            "observed_at": now_utc,
            "expires_at": now_utc + timedelta(hours=1),
        },
    )


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


def test_b21_p0_migration_authority_is_privileged_and_runtime_fails_closed() -> None:
    runtime_async = _runtime_async_url()
    migration_sync = _migration_sync_url()

    assert runtime_async.startswith("postgresql+asyncpg://")
    assert migration_sync.startswith("postgresql://")

    runtime_user = (urlparse(_runtime_sync_url()).username or "").strip()
    migration_user = (urlparse(migration_sync).username or "").strip()
    assert runtime_user == "app_user"
    assert migration_user == "migration_owner"
    assert runtime_user != migration_user

    migration_engine = create_engine(migration_sync)
    runtime_engine = create_engine(_runtime_sync_url())
    try:
        with migration_engine.begin() as migration_conn:
            versions = migration_conn.execute(
                text("SELECT version_num FROM public.alembic_version")
            ).scalars().all()
            assert versions, "migration authority must be able to read alembic_version metadata"

        with runtime_engine.begin() as runtime_conn:
            role_row = runtime_conn.execute(
                text(
                    """
                    SELECT current_user, rolsuper, rolbypassrls
                    FROM pg_roles
                    WHERE rolname = current_user
                    """
                )
            ).mappings().one()
            assert role_row["current_user"] == "app_user"
            assert bool(role_row["rolsuper"]) is False
            assert bool(role_row["rolbypassrls"]) is False

            substrate_tables = runtime_conn.execute(
                text(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name IN (
                        'session_authority',
                        'ephemeral_order_resolution',
                        'ephemeral_click_resolution',
                        'attribution_events',
                        'attribution_allocations'
                      )
                    """
                )
            ).scalars().all()
            assert set(substrate_tables) == {
                "session_authority",
                "ephemeral_order_resolution",
                "ephemeral_click_resolution",
                "attribution_events",
                "attribution_allocations",
            }
    finally:
        migration_engine.dispose()
        runtime_engine.dispose()

    runtime_read_attempt_engine = create_engine(_runtime_sync_url())
    try:
        with pytest.raises(ProgrammingError) as exc_info:
            with runtime_read_attempt_engine.begin() as runtime_conn:
                runtime_conn.execute(text("SELECT version_num FROM public.alembic_version"))
        assert "permission denied for table alembic_version" in str(exc_info.value).lower()
    finally:
        runtime_read_attempt_engine.dispose()


@pytest.mark.asyncio
async def test_b21_p0_channels_route_is_tenant_safe_with_cross_tenant_negative_control() -> None:
    tenant_a = uuid4()
    tenant_b = uuid4()
    user_a = uuid4()
    user_b = uuid4()
    session_a = uuid4()
    session_b = uuid4()
    event_a = uuid4()
    event_b = uuid4()
    allocation_a = uuid4()
    allocation_b = uuid4()
    window_start = datetime.now(timezone.utc) - timedelta(hours=2)
    revenue_a = 12345
    revenue_b = 54321

    migration_engine = create_engine(_migration_sync_url())
    try:
        with migration_engine.begin() as conn:
            _seed_tenant(conn, tenant_a, "b21-channel-a")
            _seed_tenant(conn, tenant_b, "b21-channel-b")
            _ensure_channel_taxonomy_code(conn, "direct")
            _insert_session_authority(
                conn, tenant_id=tenant_a, session_id=session_a, issued_at=window_start
            )
            _insert_session_authority(
                conn, tenant_id=tenant_b, session_id=session_b, issued_at=window_start
            )
            _insert_event(
                conn,
                event_id=event_a,
                tenant_id=tenant_a,
                session_id=session_a,
                occurred_at=window_start,
                idempotency_key=f"b21-ch-a-{event_a.hex[:12]}",
                channel="direct",
                revenue_cents=revenue_a,
            )
            _insert_event(
                conn,
                event_id=event_b,
                tenant_id=tenant_b,
                session_id=session_b,
                occurred_at=window_start,
                idempotency_key=f"b21-ch-b-{event_b.hex[:12]}",
                channel="direct",
                revenue_cents=revenue_b,
            )
            _insert_allocation(
                conn,
                allocation_id=allocation_a,
                tenant_id=tenant_a,
                event_id=event_a,
                channel_code="direct",
                revenue_cents=revenue_a,
            )
            _insert_allocation(
                conn,
                allocation_id=allocation_b,
                tenant_id=tenant_b,
                event_id=event_b,
                channel_code="direct",
                revenue_cents=revenue_b,
            )
            _insert_ephemeral_resolution_rows(conn, tenant_id=tenant_a, session_id=session_a)
            _insert_ephemeral_resolution_rows(conn, tenant_id=tenant_b, session_id=session_b)
    finally:
        migration_engine.dispose()

    active_context = {"value": _auth_context(tenant_id=tenant_a, user_id=user_a)}

    async def _auth_override() -> AuthContext:
        return active_context["value"]

    app.dependency_overrides[get_auth_context] = _auth_override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response_a = await client.get(
                "/api/attribution/channels",
                headers={"X-Correlation-ID": str(uuid4())},
            )
            active_context["value"] = _auth_context(tenant_id=tenant_b, user_id=user_b)
            response_b = await client.get(
                "/api/attribution/channels",
                headers={"X-Correlation-ID": str(uuid4())},
            )

        assert response_a.status_code == status.HTTP_200_OK, response_a.text
        assert response_b.status_code == status.HTTP_200_OK, response_b.text

        payload_a = response_a.json()
        payload_b = response_b.json()
        assert payload_a["tenant_id"] == str(tenant_a)
        assert payload_b["tenant_id"] == str(tenant_b)
        assert payload_a["total_revenue"] == round(revenue_a / 100.0, 2)
        assert payload_b["total_revenue"] == round(revenue_b / 100.0, 2)
        assert payload_a["total_revenue"] != payload_b["total_revenue"]
        assert payload_a["channels"]
        assert payload_b["channels"]
    finally:
        app.dependency_overrides.pop(get_auth_context, None)

    runtime_engine = create_engine(_runtime_sync_url())
    try:
        with runtime_engine.begin() as conn:
            role_row = conn.execute(
                text(
                    """
                    SELECT rolsuper, rolbypassrls
                    FROM pg_roles
                    WHERE rolname = current_user
                    """
                )
            ).mappings().one()
            assert bool(role_row["rolsuper"]) is False
            assert bool(role_row["rolbypassrls"]) is False

            policy_count = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM pg_policies
                    WHERE schemaname = 'public'
                      AND tablename IN ('attribution_events', 'attribution_allocations')
                      AND (
                        qual ILIKE '%current_setting(''app.current_tenant_id''%'
                        OR with_check ILIKE '%current_setting(''app.current_tenant_id''%'
                      )
                    """
                )
            ).scalar_one()
            assert int(policy_count) >= 2

            conn.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_b)},
            )
            tenant_guc = conn.execute(
                text("SELECT current_setting('app.current_tenant_id', true)")
            ).scalar_one_or_none()
            assert tenant_guc == str(tenant_b)

            cross_alloc_count = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.attribution_allocations
                    WHERE tenant_id = :tenant_id
                      AND event_id = :event_id
                    """
                ),
                {"tenant_id": str(tenant_a), "event_id": str(event_a)},
            ).scalar_one()
            cross_event_count = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.attribution_events
                    WHERE tenant_id = :tenant_id
                      AND id = :event_id
                    """
                ),
                {"tenant_id": str(tenant_a), "event_id": str(event_a)},
            ).scalar_one()
            assert int(cross_alloc_count) == 0
            assert int(cross_event_count) == 0
    finally:
        runtime_engine.dispose()


def test_b21_p0_worker_substrate_path_is_tenant_safe_with_cross_tenant_negative_control() -> None:
    tenant_a = uuid4()
    tenant_b = uuid4()
    session_a = uuid4()
    session_b = uuid4()
    event_a = uuid4()
    window_start = datetime.now(timezone.utc) - timedelta(hours=1)
    window_end = datetime.now(timezone.utc) + timedelta(hours=1)
    now_iso_start = window_start.isoformat().replace("+00:00", "Z")
    now_iso_end = window_end.isoformat().replace("+00:00", "Z")

    migration_engine = create_engine(_migration_sync_url())
    try:
        with migration_engine.begin() as conn:
            _seed_tenant(conn, tenant_a, "b21-worker-a")
            _seed_tenant(conn, tenant_b, "b21-worker-b")
            _ensure_channel_taxonomy_code(conn, "direct")
            _insert_session_authority(
                conn, tenant_id=tenant_a, session_id=session_a, issued_at=window_start
            )
            _insert_session_authority(
                conn, tenant_id=tenant_b, session_id=session_b, issued_at=window_start
            )
            _insert_ephemeral_resolution_rows(conn, tenant_id=tenant_a, session_id=session_a)
            _insert_ephemeral_resolution_rows(conn, tenant_id=tenant_b, session_id=session_b)
            _insert_event(
                conn,
                event_id=event_a,
                tenant_id=tenant_a,
                session_id=session_a,
                occurred_at=window_start + timedelta(minutes=1),
                idempotency_key=f"b21-worker-a-{event_a.hex[:12]}",
                channel="direct",
                revenue_cents=30000,
            )
    finally:
        migration_engine.dispose()

    previous_eager = celery_app.conf.task_always_eager
    celery_app.conf.task_always_eager = True
    try:
        positive = recompute_window.apply(
            kwargs={
                "window_start": now_iso_start,
                "window_end": now_iso_end,
                "session_id": str(session_a),
                "correlation_id": str(uuid4()),
            },
            headers={
                AUTHORITY_ENVELOPE_HEADER: authority_envelope_payload(
                    SystemAuthorityEnvelope(tenant_id=tenant_a)
                )
            },
        )
        positive_payload = positive.get(propagate=True)
        assert positive_payload["status"] == "succeeded"
        assert int(positive_payload["event_count"]) >= 1
        assert int(positive_payload["allocation_count"]) >= 3

        cross_tenant_attempt = recompute_window.apply(
            kwargs={
                "window_start": now_iso_start,
                "window_end": now_iso_end,
                "session_id": str(session_a),
                "correlation_id": str(uuid4()),
            },
            headers={
                AUTHORITY_ENVELOPE_HEADER: authority_envelope_payload(
                    SystemAuthorityEnvelope(tenant_id=tenant_b)
                )
            },
        )
        with pytest.raises(ValueError, match="session locality violation"):
            cross_tenant_attempt.get(propagate=True)
    finally:
        celery_app.conf.task_always_eager = previous_eager

    runtime_engine = create_engine(_runtime_sync_url())
    try:
        with runtime_engine.begin() as conn:
            conn.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_b)},
            )
            cross_session_authority = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.session_authority
                    WHERE tenant_id = :tenant_id
                      AND session_id = :session_id
                    """
                ),
                {"tenant_id": str(tenant_a), "session_id": str(session_a)},
            ).scalar_one()
            cross_allocations = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.attribution_allocations
                    WHERE tenant_id = :tenant_id
                      AND event_id = :event_id
                    """
                ),
                {"tenant_id": str(tenant_a), "event_id": str(event_a)},
            ).scalar_one()
            cross_ephemeral_order = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.ephemeral_order_resolution
                    WHERE tenant_id = :tenant_id
                    """
                ),
                {"tenant_id": str(tenant_a)},
            ).scalar_one()
            cross_ephemeral_click = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.ephemeral_click_resolution
                    WHERE tenant_id = :tenant_id
                    """
                ),
                {"tenant_id": str(tenant_a)},
            ).scalar_one()
            assert int(cross_session_authority) == 0
            assert int(cross_allocations) == 0
            assert int(cross_ephemeral_order) == 0
            assert int(cross_ephemeral_click) == 0
    finally:
        runtime_engine.dispose()
