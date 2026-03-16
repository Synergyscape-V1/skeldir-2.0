from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import create_async_engine


def _sync_database_url() -> str:
    url = os.environ.get("MIGRATION_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL or MIGRATION_DATABASE_URL is required")
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url


def _to_async_url(sync_url: str) -> str:
    if sync_url.startswith("postgresql+asyncpg://"):
        return sync_url
    return sync_url.replace("postgresql://", "postgresql+asyncpg://", 1)


def _seed_tenant(sync_url: str, tenant_id: UUID) -> None:
    engine = create_engine(sync_url)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO public.tenants (id, name, api_key_hash, notification_email, created_at, updated_at)
                VALUES (:id, :name, :api_key_hash, :notification_email, now(), now())
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {
                "id": str(tenant_id),
                "name": f"b14-tenant-{tenant_id.hex[:8]}",
                "api_key_hash": f"b14-api-key-{tenant_id.hex[:8]}",
                "notification_email": f"tenant-{tenant_id.hex[:8]}@example.test",
            },
        )
    engine.dispose()


@pytest.fixture(scope="session")
def _isolated_database_urls() -> tuple[str, str]:
    cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    base_sync_url = _sync_database_url()
    parsed = make_url(base_sync_url)
    admin_url = str(parsed.set(database="postgres"))
    isolated_db_name = f"skeldir_b14_p0_{uuid4().hex[:12]}"
    isolated_sync_url = str(parsed.set(database=isolated_db_name))
    isolated_async_url = _to_async_url(isolated_sync_url)

    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.begin() as conn:
            conn.execute(text(f'CREATE DATABASE "{isolated_db_name}" OWNER "{parsed.username or "postgres"}"'))
    except Exception as exc:
        pytest.skip(f"unable to create isolated database for B1.4-P0 runtime proofs: {exc}")
    finally:
        admin_engine.dispose()

    os.environ["MIGRATION_DATABASE_URL"] = isolated_sync_url
    os.environ["DATABASE_URL"] = isolated_async_url
    os.environ["TESTING"] = "1"
    cfg.set_main_option("sqlalchemy.url", isolated_sync_url)
    command.upgrade(cfg, "head")

    try:
        yield isolated_sync_url, isolated_async_url
    finally:
        cleanup_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
        try:
            with cleanup_engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        SELECT pg_terminate_backend(pid)
                        FROM pg_stat_activity
                        WHERE datname = :db_name
                          AND pid <> pg_backend_pid()
                        """
                    ),
                    {"db_name": isolated_db_name},
                )
                conn.execute(text(f'DROP DATABASE IF EXISTS "{isolated_db_name}"'))
        finally:
            cleanup_engine.dispose()


def test_b14_p0_runtime_minimizes_immutable_event_payload(
    _isolated_database_urls: tuple[str, str],
) -> None:
    sync_url, _ = _isolated_database_urls
    tenant_id = uuid4()
    _seed_tenant(sync_url, tenant_id)

    from app.privacy.authority import minimize_event_payload_for_storage

    event_data = {
        "event_type": "purchase",
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
        "revenue_amount": "12.34",
        "currency": "USD",
        "session_id": str(uuid4()),
        "vendor": "stripe",
        "utm_source": "stripe",
        "utm_medium": "cpc",
        "external_event_id": "evt_b14_payload_lock",
        "idempotency_key": "evt-b14-payload-lock",
        "vendor_payload": {"customer": {"id": "cus_123"}},
        "raw_body_sha256": "abc123",
    }

    durable_payload = minimize_event_payload_for_storage({**event_data, "channel": "direct"})
    event_id = str(uuid4())

    engine = create_engine(sync_url)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO public.attribution_events (
                    id,
                    tenant_id,
                    session_id,
                    occurred_at,
                    event_timestamp,
                    idempotency_key,
                    event_type,
                    channel,
                    raw_payload
                ) VALUES (
                    :id,
                    :tenant_id,
                    :session_id,
                    now(),
                    now(),
                    :idempotency_key,
                    'purchase',
                    'direct',
                    CAST(:raw_payload AS jsonb)
                )
                """
            ),
            {
                "id": event_id,
                "tenant_id": str(tenant_id),
                "session_id": str(uuid4()),
                "idempotency_key": "evt-b14-payload-lock",
                "raw_payload": json.dumps(durable_payload),
            },
        )
        row = conn.execute(
            text("SELECT raw_payload FROM public.attribution_events WHERE id = :id"),
            {"id": event_id},
        ).scalar_one()
    engine.dispose()

    assert isinstance(row, dict)
    assert "vendor_payload" not in row
    assert "raw_body_sha256" not in row
    assert "session_id" not in row
    assert row.get("event_type") == "purchase"
    assert row.get("vendor") == "stripe"


def test_b14_p0_runtime_negative_control_rejects_forbidden_payload_key(
    _isolated_database_urls: tuple[str, str],
) -> None:
    sync_url, _ = _isolated_database_urls
    tenant_id = uuid4()
    _seed_tenant(sync_url, tenant_id)

    engine = create_engine(sync_url)
    with engine.begin() as conn:
        with pytest.raises(Exception) as exc_info:
            conn.execute(
                text(
                    """
                    INSERT INTO public.attribution_events (
                        id,
                        tenant_id,
                        session_id,
                        occurred_at,
                        event_timestamp,
                        idempotency_key,
                        event_type,
                        channel,
                        raw_payload
                    ) VALUES (
                        :id,
                        :tenant_id,
                        :session_id,
                        now(),
                        now(),
                        :idempotency_key,
                        'purchase',
                        'direct',
                        '{"vendor_payload": {"raw": true}}'::jsonb
                    )
                    """
                ),
                {
                    "id": str(uuid4()),
                    "tenant_id": str(tenant_id),
                    "session_id": str(uuid4()),
                    "idempotency_key": f"b14-forbidden-{uuid4()}",
                },
            )
    engine.dispose()

    assert "privacy authority violation" in str(exc_info.value).lower()


def test_b14_p0_runtime_retention_redacts_old_dead_event_payloads(
    _isolated_database_urls: tuple[str, str],
) -> None:
    sync_url, async_url = _isolated_database_urls
    tenant_id = uuid4()
    _seed_tenant(sync_url, tenant_id)

    old_ingested_at = datetime.now(timezone.utc) - timedelta(days=95)
    correlation_id = uuid4()

    engine = create_engine(sync_url)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO public.dead_events (
                    id,
                    tenant_id,
                    ingested_at,
                    source,
                    error_code,
                    error_detail,
                    raw_payload,
                    correlation_id,
                    event_type,
                    error_type,
                    error_message,
                    remediation_status
                ) VALUES (
                    :id,
                    :tenant_id,
                    :ingested_at,
                    'stripe',
                    'VALIDATION_ERROR',
                    '{"detail": "bad shape"}'::jsonb,
                    CAST(:raw_payload AS jsonb),
                    :correlation_id,
                    'purchase',
                    'validation_error',
                    'bad shape',
                    'pending'
                )
                """
            ),
            {
                "id": str(uuid4()),
                "tenant_id": str(tenant_id),
                "ingested_at": old_ingested_at,
                "correlation_id": str(correlation_id),
                "raw_payload": json.dumps(
                    {"idempotency_key": "b14-retention", "vendor_payload": {"a": 1}}
                ),
            },
        )
        conn.execute(
            text(
                """
                INSERT INTO public.dead_events_quarantine (
                    id,
                    tenant_id,
                    source,
                    raw_payload,
                    error_type,
                    error_message,
                    error_detail,
                    correlation_id,
                    ingested_at
                ) VALUES (
                    :id,
                    :tenant_id,
                    'stripe',
                    CAST(:raw_payload AS jsonb),
                    'validation_error',
                    'bad shape',
                    '{"detail":"x"}'::jsonb,
                    :correlation_id,
                    :ingested_at
                )
                """
            ),
            {
                "id": str(uuid4()),
                "tenant_id": str(tenant_id),
                "correlation_id": str(correlation_id),
                "ingested_at": old_ingested_at,
                "raw_payload": json.dumps({"idempotency_key": "b14-retention", "raw": "value"}),
            },
        )
    engine.dispose()

    import app.tasks.maintenance as maintenance_module

    async_engine = create_async_engine(async_url, pool_pre_ping=True)
    original_engine = maintenance_module.engine
    maintenance_module.engine = async_engine
    try:
        results = asyncio.run(
            maintenance_module._enforce_retention(
                tenant_id=tenant_id,
                cutoff_90=datetime.now(timezone.utc) - timedelta(days=90),
                cutoff_30=datetime.now(timezone.utc) - timedelta(days=30),
            )
        )
    finally:
        maintenance_module.engine = original_engine
        asyncio.run(async_engine.dispose())

    assert int(results.get("dead_events_payload_redacted", 0)) >= 1
    assert int(results.get("dead_events_quarantine_payload_redacted", 0)) >= 1

    engine = create_engine(sync_url)
    with engine.begin() as conn:
        dead_payload = conn.execute(
            text(
                "SELECT raw_payload, error_detail FROM public.dead_events "
                "WHERE tenant_id = :tenant_id AND correlation_id = :correlation_id"
            ),
            {"tenant_id": str(tenant_id), "correlation_id": str(correlation_id)},
        ).mappings().one()
        quarantine_payload = conn.execute(
            text(
                "SELECT raw_payload, error_detail FROM public.dead_events_quarantine "
                "WHERE tenant_id = :tenant_id AND correlation_id = :correlation_id"
            ),
            {"tenant_id": str(tenant_id), "correlation_id": str(correlation_id)},
        ).mappings().one()
    engine.dispose()

    assert dead_payload["raw_payload"] == {}
    assert dead_payload["error_detail"] == {}
    assert quarantine_payload["raw_payload"] == {}
    assert quarantine_payload["error_detail"] == {}


def test_b14_p0_runtime_internal_erasure_surface_is_worker_authoritative(
    _isolated_database_urls: tuple[str, str],
) -> None:
    sync_url, async_url = _isolated_database_urls
    tenant_id = uuid4()
    _seed_tenant(sync_url, tenant_id)

    correlation_id = uuid4()
    idempotency_key = f"b14-erase-{uuid4().hex[:8]}"

    engine = create_engine(sync_url)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO public.dead_events (
                    id,
                    tenant_id,
                    ingested_at,
                    source,
                    error_code,
                    error_detail,
                    raw_payload,
                    correlation_id,
                    event_type,
                    error_type,
                    error_message,
                    remediation_status
                ) VALUES (
                    :id,
                    :tenant_id,
                    now(),
                    'stripe',
                    'VALIDATION_ERROR',
                    '{"detail":"x"}'::jsonb,
                    CAST(:raw_payload AS jsonb),
                    :correlation_id,
                    'purchase',
                    'validation_error',
                    'bad shape',
                    'pending'
                )
                """
            ),
            {
                "id": str(uuid4()),
                "tenant_id": str(tenant_id),
                "correlation_id": str(correlation_id),
                "raw_payload": json.dumps({"idempotency_key": idempotency_key, "opaque": "data"}),
            },
        )
        conn.execute(
            text(
                """
                INSERT INTO public.dead_events_quarantine (
                    id,
                    tenant_id,
                    source,
                    raw_payload,
                    error_type,
                    error_message,
                    error_detail,
                    correlation_id,
                    ingested_at
                ) VALUES (
                    :id,
                    :tenant_id,
                    'stripe',
                    CAST(:raw_payload AS jsonb),
                    'validation_error',
                    'bad shape',
                    '{"detail":"x"}'::jsonb,
                    :correlation_id,
                    now()
                )
                """
            ),
            {
                "id": str(uuid4()),
                "tenant_id": str(tenant_id),
                "correlation_id": str(correlation_id),
                "raw_payload": json.dumps({"idempotency_key": idempotency_key, "opaque": "data"}),
            },
        )
    engine.dispose()

    import app.tasks.privacy as privacy_module

    async_engine = create_async_engine(async_url, pool_pre_ping=True)
    original_engine = privacy_module.engine
    privacy_module.engine = async_engine
    try:
        results = asyncio.run(
            privacy_module._erase_tenant_privacy_surfaces(
                tenant_id=tenant_id,
                selector={"idempotency_key": idempotency_key},
            )
        )
    finally:
        privacy_module.engine = original_engine
        asyncio.run(async_engine.dispose())
    assert int(results.get("dead_events_redacted", 0)) >= 1
    assert int(results.get("dead_events_quarantine_redacted", 0)) >= 1

    engine = create_engine(sync_url)
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT
                  de.raw_payload AS dead_payload,
                  dq.raw_payload AS quarantine_payload
                FROM public.dead_events de
                JOIN public.dead_events_quarantine dq
                  ON dq.tenant_id = de.tenant_id
                 AND dq.correlation_id = de.correlation_id
                WHERE de.tenant_id = :tenant_id
                  AND de.correlation_id = :correlation_id
                """
            ),
            {"tenant_id": str(tenant_id), "correlation_id": str(correlation_id)},
        ).mappings().one()
    engine.dispose()

    assert row["dead_payload"] == {}
    assert row["quarantine_payload"] == {}
