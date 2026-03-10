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

from app.services.oauth_handshake_state import (
    OAuthHandshakeStateBindingError,
    OAuthHandshakeStateExpiredError,
    OAuthHandshakeStateReplayError,
    OAuthHandshakeStateService,
)


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
                "name": f"p2-tenant-{tenant_id.hex[:8]}",
                "api_key_hash": f"p2-api-key-{tenant_id.hex[:8]}",
                "notification_email": f"tenant-{tenant_id.hex[:8]}@example.test",
            },
        )


def _seed_user(sync_url: str, user_id: UUID) -> None:
    engine = create_engine(sync_url)
    login_hash = f"p2-login-{user_id.hex}"
    subject_hash = f"p2-subject-{user_id.hex}"
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO public.users (
                    id, login_identifier_hash, external_subject_hash, auth_provider, is_active, created_at, updated_at
                )
                VALUES (:id, :login_hash, :subject_hash, 'password', true, now(), now())
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {
                "id": str(user_id),
                "login_hash": login_hash,
                "subject_hash": subject_hash,
            },
        )


def _tenant_count(sync_url: str, table_name: str, tenant_id: UUID) -> int:
    engine = create_engine(sync_url)
    with engine.begin() as conn:
        count = conn.execute(
            text(f"SELECT COUNT(*) FROM public.{table_name} WHERE tenant_id = :tenant_id"),
            {"tenant_id": str(tenant_id)},
        ).scalar_one()
    return int(count)


def _handshake_row(sync_url: str, tenant_id: UUID) -> dict | None:
    engine = create_engine(sync_url)
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT state_nonce_hash, encrypted_pkce_verifier, pkce_key_id, status
                FROM public.oauth_handshake_sessions
                WHERE tenant_id = :tenant_id
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"tenant_id": str(tenant_id)},
        ).mappings().first()
    return dict(row) if row else None


@pytest.fixture(scope="session")
def _isolated_database_urls() -> tuple[str, str]:
    cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    base_sync_url = _sync_database_url()
    parsed = make_url(base_sync_url)
    admin_url = str(parsed.set(database="postgres"))
    isolated_db_name = f"skeldir_b13_p2_{uuid4().hex[:12]}"
    isolated_sync_url = str(parsed.set(database=isolated_db_name))
    isolated_async_url = _to_async_url(isolated_sync_url)

    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.begin() as conn:
            conn.execute(text(f'CREATE DATABASE "{isolated_db_name}" OWNER "{parsed.username or "postgres"}"'))
    except Exception as exc:
        pytest.skip(f"unable to create isolated database for B1.3-P2 runtime proofs: {exc}")
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
    user_id: UUID,
):
    async with session_factory() as session:
        await session.begin()
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
            {"tenant_id": str(tenant_id)},
        )
        await session.execute(
            text("SELECT set_config('app.current_user_id', :user_id, true)"),
            {"user_id": str(user_id)},
        )
        try:
            yield session
            if session.in_transaction():
                await session.commit()
        except Exception:
            if session.in_transaction():
                await session.rollback()
            raise


async def test_p2_transient_substrate_is_distinct_from_durable_provider_tables(
    _isolated_database_urls: tuple[str, str],
    _async_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    sync_url, _ = _isolated_database_urls
    tenant_id = uuid4()
    user_id = uuid4()
    _seed_tenant(sync_url, tenant_id)
    _seed_user(sync_url, user_id)

    before_connections = _tenant_count(sync_url, "platform_connections", tenant_id)
    before_credentials = _tenant_count(sync_url, "platform_credentials", tenant_id)
    before_handshakes = _tenant_count(sync_url, "oauth_handshake_sessions", tenant_id)

    async with _tenant_session(_async_session_factory, tenant_id=tenant_id, user_id=user_id) as session:
        created = await OAuthHandshakeStateService.create_session(
            session,
            tenant_id=tenant_id,
            user_id=user_id,
            platform="stripe",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
            pkce_verifier="pkce-secret-verifier",
            pkce_code_challenge="challenge-abc",
            pkce_code_challenge_method="S256",
            redirect_uri="https://app.example/callback",
            provider_session_metadata={"mode": "test"},
        )

    after_connections = _tenant_count(sync_url, "platform_connections", tenant_id)
    after_credentials = _tenant_count(sync_url, "platform_credentials", tenant_id)
    after_handshakes = _tenant_count(sync_url, "oauth_handshake_sessions", tenant_id)
    row = _handshake_row(sync_url, tenant_id)

    assert after_connections == before_connections
    assert after_credentials == before_credentials
    assert after_handshakes == before_handshakes + 1
    assert row is not None
    assert row["state_nonce_hash"] != created.state_reference
    encrypted = row["encrypted_pkce_verifier"]
    if isinstance(encrypted, memoryview):
        encrypted = bytes(encrypted)
    assert encrypted != b"pkce-secret-verifier"
    assert row["pkce_key_id"] == "test-key"
    assert row["status"] == "pending"


async def test_p2_replay_and_cross_tenant_binding_fail_before_side_effects(
    _isolated_database_urls: tuple[str, str],
    _async_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    sync_url, _ = _isolated_database_urls
    tenant_a = uuid4()
    tenant_b = uuid4()
    user_a = uuid4()
    user_b = uuid4()
    _seed_tenant(sync_url, tenant_a)
    _seed_tenant(sync_url, tenant_b)
    _seed_user(sync_url, user_a)
    _seed_user(sync_url, user_b)

    async with _tenant_session(_async_session_factory, tenant_id=tenant_a, user_id=user_a) as session:
        created = await OAuthHandshakeStateService.create_session(
            session,
            tenant_id=tenant_a,
            user_id=user_a,
            platform="stripe",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
            pkce_verifier="replay-test",
            gc_grace_seconds=0,
        )

    async with _tenant_session(_async_session_factory, tenant_id=tenant_b, user_id=user_b) as wrong_session:
        with pytest.raises(OAuthHandshakeStateBindingError):
            await OAuthHandshakeStateService.consume_session(
                wrong_session,
                tenant_id=tenant_b,
                user_id=user_b,
                platform="stripe",
                state_reference=created.state_reference,
            )

    row_after_wrong = _handshake_row(sync_url, tenant_a)
    assert row_after_wrong is not None
    assert row_after_wrong["status"] == "pending"

    async with _tenant_session(_async_session_factory, tenant_id=tenant_a, user_id=user_a) as session:
        consumed = await OAuthHandshakeStateService.consume_session(
            session,
            tenant_id=tenant_a,
            user_id=user_a,
            platform="stripe",
            state_reference=created.state_reference,
            gc_grace_seconds=0,
        )

    assert consumed.pkce_verifier == "replay-test"

    async with _tenant_session(_async_session_factory, tenant_id=tenant_a, user_id=user_a) as session:
        with pytest.raises(OAuthHandshakeStateReplayError):
            await OAuthHandshakeStateService.consume_session(
                session,
                tenant_id=tenant_a,
                user_id=user_a,
                platform="stripe",
                state_reference=created.state_reference,
            )


async def test_p2_expiry_and_gc_are_bounded(
    _isolated_database_urls: tuple[str, str],
    _async_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    sync_url, _ = _isolated_database_urls
    tenant_id = uuid4()
    user_id = uuid4()
    _seed_tenant(sync_url, tenant_id)
    _seed_user(sync_url, user_id)

    base_now = datetime.now(timezone.utc)
    expires_at = base_now + timedelta(seconds=5)

    async with _tenant_session(_async_session_factory, tenant_id=tenant_id, user_id=user_id) as session:
        created = await OAuthHandshakeStateService.create_session(
            session,
            tenant_id=tenant_id,
            user_id=user_id,
            platform="stripe",
            expires_at=expires_at,
            pkce_verifier="expiry-test",
            gc_grace_seconds=0,
        )

    consume_now = base_now + timedelta(seconds=10)
    async with _tenant_session(_async_session_factory, tenant_id=tenant_id, user_id=user_id) as session:
        with pytest.raises(OAuthHandshakeStateExpiredError):
            await OAuthHandshakeStateService.consume_session(
                session,
                tenant_id=tenant_id,
                user_id=user_id,
                platform="stripe",
                state_reference=created.state_reference,
                now=consume_now,
            )
        expired_rows = await OAuthHandshakeStateService.expire_pending_sessions(
            session,
            now=consume_now,
            batch_size=10,
        )
        deleted_rows = await OAuthHandshakeStateService.gc_eligible_sessions(
            session,
            now=consume_now,
            batch_size=10,
        )

    assert expired_rows == 1
    assert deleted_rows >= 1
    assert _tenant_count(sync_url, "oauth_handshake_sessions", tenant_id) == 0


async def test_p2_consumed_rows_become_gc_eligible(
    _isolated_database_urls: tuple[str, str],
    _async_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    sync_url, _ = _isolated_database_urls
    tenant_id = uuid4()
    user_id = uuid4()
    _seed_tenant(sync_url, tenant_id)
    _seed_user(sync_url, user_id)
    now = datetime.now(timezone.utc)

    async with _tenant_session(_async_session_factory, tenant_id=tenant_id, user_id=user_id) as session:
        created = await OAuthHandshakeStateService.create_session(
            session,
            tenant_id=tenant_id,
            user_id=user_id,
            platform="stripe",
            expires_at=now + timedelta(minutes=5),
            pkce_verifier="gc-consumed",
            gc_grace_seconds=0,
        )
        await OAuthHandshakeStateService.consume_session(
            session,
            tenant_id=tenant_id,
            user_id=user_id,
            platform="stripe",
            state_reference=created.state_reference,
            now=now + timedelta(seconds=1),
            gc_grace_seconds=0,
        )
        deleted_rows = await OAuthHandshakeStateService.gc_eligible_sessions(
            session,
            now=now + timedelta(seconds=1),
            batch_size=10,
        )

    assert deleted_rows == 1
    assert _tenant_count(sync_url, "oauth_handshake_sessions", tenant_id) == 0
