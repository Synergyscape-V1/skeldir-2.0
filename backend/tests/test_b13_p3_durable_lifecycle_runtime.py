from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.services.platform_credentials import PlatformCredentialStore


pytestmark = pytest.mark.asyncio

os.environ["TESTING"] = "1"
os.environ.setdefault("PLATFORM_TOKEN_ENCRYPTION_KEY", "test-platform-key")
os.environ.setdefault("PLATFORM_TOKEN_KEY_ID", "test-key")


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
                "name": f"p3-tenant-{tenant_id.hex[:8]}",
                "api_key_hash": f"p3-api-key-{tenant_id.hex[:8]}",
                "notification_email": f"tenant-{tenant_id.hex[:8]}@example.test",
            },
        )


@pytest.fixture(scope="session")
def _isolated_database_urls() -> tuple[str, str]:
    cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    base_sync_url = _sync_database_url()
    parsed = make_url(base_sync_url)
    admin_url = str(parsed.set(database="postgres"))
    isolated_db_name = f"skeldir_b13_p3_{uuid4().hex[:12]}"
    isolated_sync_url = str(parsed.set(database=isolated_db_name))
    isolated_async_url = _to_async_url(isolated_sync_url)

    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.begin() as conn:
            conn.execute(text(f'CREATE DATABASE "{isolated_db_name}" OWNER "{parsed.username or "postgres"}"'))
    except Exception as exc:
        pytest.skip(f"unable to create isolated database for B1.3-P3 runtime proofs: {exc}")
    finally:
        admin_engine.dispose()

    os.environ["MIGRATION_DATABASE_URL"] = isolated_sync_url
    os.environ["DATABASE_URL"] = isolated_async_url
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


@pytest.fixture
async def _async_session_factory(
    _isolated_database_urls: tuple[str, str],
) -> async_sessionmaker[AsyncSession]:
    _, async_url = _isolated_database_urls
    engine = create_async_engine(
        async_url,
        pool_pre_ping=True,
        echo=False,
        poolclass=NullPool,
    )
    try:
        yield async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    finally:
        await engine.dispose()


@asynccontextmanager
async def _tenant_session(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    tenant_id: UUID,
):
    async with session_factory() as session:
        await session.begin()
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
            {"tenant_id": str(tenant_id)},
        )
        try:
            yield session
            if session.in_transaction():
                await session.commit()
        except Exception:
            if session.in_transaction():
                await session.rollback()
            raise


async def _create_connection(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    platform: str,
    account_suffix: str,
) -> str:
    connection_id = str(uuid4())
    await session.execute(
        text(
            """
            INSERT INTO public.platform_connections (
                id, tenant_id, platform, platform_account_id, status, created_at, updated_at
            ) VALUES (
                :id, :tenant_id, :platform, :platform_account_id, 'active', now(), now()
            )
            """
        ),
        {
            "id": connection_id,
            "tenant_id": str(tenant_id),
            "platform": platform,
            "platform_account_id": f"acct_{account_suffix}",
        },
    )
    return connection_id


async def test_p3_lifecycle_transitions_are_persisted_durably(
    _isolated_database_urls: tuple[str, str],
    _async_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    sync_url, _ = _isolated_database_urls
    tenant_id = uuid4()
    _seed_tenant(sync_url, tenant_id)
    now = datetime.now(timezone.utc)

    async with _tenant_session(_async_session_factory, tenant_id=tenant_id) as session:
        await _create_connection(session, tenant_id=tenant_id, platform="stripe", account_suffix="primary")
        created = await PlatformCredentialStore.upsert_tokens(
            session,
            tenant_id=tenant_id,
            platform="stripe",
            platform_account_id="acct_primary",
            access_token="access-token-v1",
            refresh_token="refresh-token-v1",
            expires_at=now + timedelta(hours=1),
            scope="read write",
            token_type="Bearer",
            key_id="test-key",
            encryption_key="test-platform-key",
        )

        credential_id = created["id"]
        failure = await PlatformCredentialStore.record_refresh_failure(
            session,
            tenant_id=tenant_id,
            credential_id=credential_id,
            failure_class="provider_rate_limited",
            next_refresh_due_at=now + timedelta(minutes=5),
            failure_at=now,
        )
        assert failure["lifecycle_status"] == "degraded"
        assert int(failure["refresh_failure_count"]) == 1

        success = await PlatformCredentialStore.mark_refresh_success(
            session,
            tenant_id=tenant_id,
            credential_id=credential_id,
            access_token="access-token-v2",
            refresh_token="refresh-token-v2",
            expires_at=now + timedelta(hours=2),
            scope="read write",
            token_type="Bearer",
            key_id="test-key",
            encryption_key="test-platform-key",
            refreshed_at=now + timedelta(minutes=10),
        )
        assert success["lifecycle_status"] == "active"
        assert int(success["refresh_failure_count"]) == 0
        assert success["last_refresh_at"] is not None

        revoked = await PlatformCredentialStore.mark_revoked(
            session,
            tenant_id=tenant_id,
            credential_id=credential_id,
            revoked_at=now + timedelta(minutes=15),
        )
        assert revoked["lifecycle_status"] == "revoked"
        assert revoked["next_refresh_due_at"] is None

        row = (
            await session.execute(
                text(
                    """
                    SELECT encrypted_access_token, lifecycle_status, refresh_failure_count,
                           pg_typeof(encrypted_access_token)::text AS encrypted_type,
                           pg_typeof(next_refresh_due_at)::text AS due_type
                    FROM public.platform_credentials
                    WHERE tenant_id = :tenant_id AND id = :id
                    """
                ),
                {"tenant_id": str(tenant_id), "id": str(credential_id)},
            )
        ).mappings().one()

        encrypted_access = row["encrypted_access_token"]
        if isinstance(encrypted_access, memoryview):
            encrypted_access = bytes(encrypted_access)
        assert encrypted_access != b"access-token-v2"
        assert row["lifecycle_status"] == "revoked"
        assert int(row["refresh_failure_count"]) == 0
        assert row["encrypted_type"] == "bytea"
        assert row["due_type"] == "timestamp with time zone"

        due_rows = await PlatformCredentialStore.list_refresh_due(
            session,
            tenant_id=tenant_id,
            as_of=now + timedelta(hours=3),
            limit=10,
        )
        assert due_rows == []


async def test_p3_due_selection_query_plan_is_indexed_without_decrypt(
    _isolated_database_urls: tuple[str, str],
    _async_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    sync_url, _ = _isolated_database_urls
    tenant_id = uuid4()
    _seed_tenant(sync_url, tenant_id)
    as_of = datetime.now(timezone.utc)

    async with _tenant_session(_async_session_factory, tenant_id=tenant_id) as session:
        due_ids: list[UUID] = []
        for idx in range(12):
            await _create_connection(
                session,
                tenant_id=tenant_id,
                platform="stripe",
                account_suffix=f"due_{idx}",
            )
            inserted = await PlatformCredentialStore.upsert_tokens(
                session,
                tenant_id=tenant_id,
                platform="stripe",
                platform_account_id=f"acct_due_{idx}",
                access_token=f"access-{idx}",
                refresh_token=f"refresh-{idx}",
                expires_at=as_of + timedelta(hours=4),
                scope="read",
                token_type="Bearer",
                key_id="test-key",
                encryption_key="test-platform-key",
            )
            due_ids.append(inserted["id"])

        for idx, credential_id in enumerate(due_ids):
            due_at = as_of - timedelta(minutes=idx + 1)
            if idx % 2 == 0:
                await PlatformCredentialStore.record_refresh_failure(
                    session,
                    tenant_id=tenant_id,
                    credential_id=credential_id,
                    failure_class="provider_transport_failure",
                    next_refresh_due_at=due_at,
                    failure_at=as_of - timedelta(minutes=idx + 1),
                )
            else:
                await session.execute(
                    text(
                        """
                        UPDATE public.platform_credentials
                        SET next_refresh_due_at = :due_at,
                            lifecycle_status = 'active',
                            updated_at = now()
                        WHERE tenant_id = :tenant_id
                          AND id = :credential_id
                        """
                    ),
                    {
                        "due_at": due_at,
                        "tenant_id": str(tenant_id),
                        "credential_id": str(credential_id),
                    },
                )

        await session.execute(text("SET LOCAL enable_seqscan = off"))
        plan_rows = (
            await session.execute(
                text(
                    """
                    EXPLAIN (FORMAT TEXT)
                    SELECT id
                    FROM public.platform_credentials
                    WHERE tenant_id = :tenant_id
                      AND lifecycle_status IN ('active', 'degraded')
                      AND next_refresh_due_at IS NOT NULL
                      AND next_refresh_due_at <= :as_of
                    ORDER BY next_refresh_due_at ASC
                    LIMIT 25
                    """
                ),
                {"tenant_id": str(tenant_id), "as_of": as_of},
            )
        ).scalars().all()
        plan_text = "\n".join(plan_rows)
        lowered = plan_text.lower()

        assert "idx_platform_credentials_refresh_due" in lowered
        assert "pgp_sym_decrypt" not in lowered

        due_rows = await PlatformCredentialStore.list_refresh_due(
            session,
            tenant_id=tenant_id,
            as_of=as_of,
            limit=25,
        )
        assert len(due_rows) == len(due_ids)
        assert all(row.next_refresh_due_at <= as_of for row in due_rows)


async def test_p3_rls_continuity_on_durable_provider_tables(
    _isolated_database_urls: tuple[str, str],
) -> None:
    sync_url, _ = _isolated_database_urls
    engine = create_engine(sync_url)
    with engine.begin() as conn:
        rls_rows = conn.execute(
            text(
                """
                SELECT relname, relrowsecurity, relforcerowsecurity
                FROM pg_class
                WHERE relname IN ('platform_connections', 'platform_credentials')
                ORDER BY relname
                """
            )
        ).mappings().all()
        policies = conn.execute(
            text(
                """
                SELECT tablename, policyname
                FROM pg_policies
                WHERE schemaname = 'public'
                  AND tablename IN ('platform_connections', 'platform_credentials')
                  AND policyname = 'tenant_isolation_policy'
                ORDER BY tablename
                """
            )
        ).mappings().all()

    engine.dispose()

    assert len(rls_rows) == 2
    assert all(bool(row["relrowsecurity"]) for row in rls_rows)
    assert all(bool(row["relforcerowsecurity"]) for row in rls_rows)

    policy_tables = {row["tablename"] for row in policies}
    assert policy_tables == {"platform_connections", "platform_credentials"}
