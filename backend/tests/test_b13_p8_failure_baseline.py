from __future__ import annotations

import json
import os
import subprocess
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.responses import JSONResponse
from starlette.requests import Request
from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.platform_oauth import get_provider_oauth_refresh_state
from app.schemas.attribution import Platform
from app.security.auth import AuthContext
from app.services.oauth_lifecycle_dispatcher import ProviderOAuthLifecycleDispatcher
from app.services.platform_credentials import PlatformCredentialStore
from app.services.provider_oauth_lifecycle import OAuthLifecycleRefreshError, OAuthTokenRefreshRequest
from app.services.provider_token_refresh import claim_due_credentials_for_tenant, refresh_credential_once


REPO_ROOT = Path(__file__).resolve().parents[2]
GATE_SCRIPT = REPO_ROOT / "scripts" / "ci" / "enforce_b13_p8_failure_baseline.py"
REQUIRED_CHECKS_CONTRACT = REPO_ROOT / "contracts-internal/governance/b03_phase2_required_status_checks.main.json"
P0_CAPABILITY_CONTRACT = REPO_ROOT / "contracts-internal/governance/b13_p0_provider_capability_matrix.main.json"

os.environ["TESTING"] = "1"
os.environ.setdefault("PLATFORM_TOKEN_ENCRYPTION_KEY", "test-platform-key")
os.environ.setdefault("PLATFORM_TOKEN_KEY_ID", "test-key")


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=REPO_ROOT,
    )


def _minimal_request(path: str = "/api/attribution/platform-oauth/stripe/refresh-state") -> Request:
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "headers": [],
        "query_string": b"",
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
        "scheme": "http",
    }
    return Request(scope)


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
    try:
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
                    "name": f"p8-tenant-{tenant_id.hex[:8]}",
                    "api_key_hash": f"p8-api-key-{tenant_id.hex[:8]}",
                    "notification_email": f"tenant-{tenant_id.hex[:8]}@example.test",
                },
            )
    finally:
        engine.dispose()


def _seed_user(sync_url: str, user_id: UUID) -> None:
    engine = create_engine(sync_url)
    try:
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
                    "login_hash": f"p8-login-{user_id.hex}",
                    "subject_hash": f"p8-subject-{user_id.hex}",
                },
            )
    finally:
        engine.dispose()


@pytest.fixture(scope="session")
def _isolated_database_urls() -> tuple[str, str]:
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    base_sync_url = _sync_database_url()
    parsed = make_url(base_sync_url)
    admin_url = str(parsed.set(database="postgres"))
    isolated_db_name = f"skeldir_b13_p8_{uuid4().hex[:12]}"
    isolated_sync_url = str(parsed.set(database=isolated_db_name))
    isolated_async_url = _to_async_url(isolated_sync_url)

    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.begin() as conn:
            conn.execute(text(f'CREATE DATABASE "{isolated_db_name}" OWNER "{parsed.username or "postgres"}"'))
    except Exception as exc:
        pytest.skip(f"unable to create isolated database for B1.3-P8 runtime proofs: {exc}")
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


async def _create_connection(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    platform: str,
    account_id: str,
    status: str = "active",
) -> UUID:
    connection_id = uuid4()
    await session.execute(
        text(
            """
            INSERT INTO public.platform_connections (
                id, tenant_id, platform, platform_account_id, status, created_at, updated_at
            ) VALUES (
                :id, :tenant_id, :platform, :platform_account_id, :status, now(), now()
            )
            """
        ),
        {
            "id": str(connection_id),
            "tenant_id": str(tenant_id),
            "platform": platform,
            "platform_account_id": account_id,
            "status": status,
        },
    )
    return connection_id


def _auth_context(tenant_id: UUID, user_id: UUID) -> AuthContext:
    return AuthContext(
        tenant_id=tenant_id,
        user_id=user_id,
        jti=uuid4(),
        issued_at_epoch=int(datetime.now(timezone.utc).timestamp()),
        subject=str(user_id),
        issuer="https://issuer.skeldir.test",
        audience="skeldir-api",
        claims={"scopes": ["manager", "viewer"], "role": "manager"},
    )


def test_b13_p8_gate_passes_repo_state() -> None:
    result = _run([sys.executable, str(GATE_SCRIPT)])
    assert result.returncode == 0, result.stdout + "\n" + result.stderr


def test_b13_p8_negative_control_detects_missing_required_context(tmp_path: Path) -> None:
    payload = json.loads(REQUIRED_CHECKS_CONTRACT.read_text(encoding="utf-8"))
    payload["required_contexts"] = [
        value
        for value in payload.get("required_contexts", [])
        if value != "B1.3 P8 Failure & Baseline Proofs"
    ]
    mutated = tmp_path / "required_checks.json"
    mutated.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    result = _run(
        [
            sys.executable,
            str(GATE_SCRIPT),
            "--required-checks-contract",
            str(mutated),
        ]
    )
    assert result.returncode != 0
    assert "missing context" in f"{result.stdout}\n{result.stderr}"


@pytest.mark.asyncio
async def test_b13_p8_failure_taxonomy_is_explicit_on_refresh_state_surface(
    _isolated_database_urls: tuple[str, str],
    _async_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    sync_url, _ = _isolated_database_urls
    tenant_id = uuid4()
    user_id = uuid4()
    _seed_tenant(sync_url, tenant_id)
    _seed_user(sync_url, user_id)
    auth_context = _auth_context(tenant_id, user_id)

    async with _tenant_session(_async_session_factory, tenant_id=tenant_id, user_id=user_id) as session:
        await _create_connection(
            session,
            tenant_id=tenant_id,
            platform="stripe",
            account_id="acct_p8_taxonomy",
        )
        created = await PlatformCredentialStore.upsert_tokens(
            session,
            tenant_id=tenant_id,
            platform="stripe",
            platform_account_id="acct_p8_taxonomy",
            access_token="taxonomy-access",
            refresh_token="taxonomy-refresh",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
            scope="read_write",
            token_type="Bearer",
            key_id="test-key",
            encryption_key="test-platform-key",
        )
        credential_id = created["id"]

        failure_expectations = (
            ("provider_rate_limited", 429, "provider_rate_limited"),
            ("provider_transport_failure", 503, "provider_transport_failure"),
            ("provider_scope_insufficient", 403, "provider_scope_insufficient"),
        )
        for failure_class, expected_status, expected_code in failure_expectations:
            await PlatformCredentialStore.record_refresh_failure(
                session,
                tenant_id=tenant_id,
                credential_id=credential_id,
                failure_class=failure_class,
                next_refresh_due_at=datetime.now(timezone.utc) + timedelta(minutes=10),
                failure_at=datetime.now(timezone.utc),
            )
            response = await get_provider_oauth_refresh_state(
                request=_minimal_request(),
                platform=Platform.stripe,
                x_correlation_id=uuid4(),
                db_session=session,
                auth_context=auth_context,
            )
            assert isinstance(response, JSONResponse)
            assert response.status_code == expected_status
            payload = json.loads(response.body.decode("utf-8"))
            assert payload["code"] == expected_code
            assert "taxonomy-access" not in response.body.decode("utf-8")
            assert "taxonomy-refresh" not in response.body.decode("utf-8")

        await PlatformCredentialStore.record_refresh_failure(
            session,
            tenant_id=tenant_id,
            credential_id=credential_id,
            failure_class="provider_invalid_client",
            failure_at=datetime.now(timezone.utc),
        )
        await PlatformCredentialStore.mark_revoked(
            session,
            tenant_id=tenant_id,
            credential_id=credential_id,
            revoked_at=datetime.now(timezone.utc),
        )
        revoked_response = await get_provider_oauth_refresh_state(
            request=_minimal_request(),
            platform=Platform.stripe,
            x_correlation_id=uuid4(),
            db_session=session,
            auth_context=auth_context,
        )
        assert isinstance(revoked_response, JSONResponse)
        assert revoked_response.status_code == 409
        revoked_payload = json.loads(revoked_response.body.decode("utf-8"))
        assert revoked_payload["code"] == "provider_revoked"


@pytest.mark.asyncio
async def test_b13_p8_terminal_invalid_client_suppresses_refresh_churn(
    _isolated_database_urls: tuple[str, str],
    _async_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    sync_url, _ = _isolated_database_urls
    tenant_id = uuid4()
    user_id = uuid4()
    _seed_tenant(sync_url, tenant_id)
    _seed_user(sync_url, user_id)

    async with _tenant_session(_async_session_factory, tenant_id=tenant_id, user_id=user_id) as session:
        await _create_connection(
            session,
            tenant_id=tenant_id,
            platform="stripe",
            account_id="acct_p8_terminal",
        )
        created = await PlatformCredentialStore.upsert_tokens(
            session,
            tenant_id=tenant_id,
            platform="stripe",
            platform_account_id="acct_p8_terminal",
            access_token="terminal-access",
            refresh_token="stripe-invalid_client-terminal",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
            scope="read_write",
            token_type="Bearer",
            key_id="test-key",
            encryption_key="test-platform-key",
        )
        credential_id = created["id"]

        result = await refresh_credential_once(
            session,
            tenant_id=tenant_id,
            credential_id=credential_id,
            correlation_id=uuid4(),
        )
        assert result.status == "revoked_terminal"
        assert result.failure_class == "provider_invalid_client"

        due = await claim_due_credentials_for_tenant(
            session,
            tenant_id=tenant_id,
            as_of=datetime.now(timezone.utc) + timedelta(days=3),
            limit=100,
        )
        assert due.due_count == 0
        assert due.claimed_credential_ids == ()


@pytest.mark.asyncio
async def test_b13_p8_reconnectable_degradation_is_explicit_when_connection_has_no_credentials(
    _isolated_database_urls: tuple[str, str],
    _async_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    sync_url, _ = _isolated_database_urls
    tenant_id = uuid4()
    user_id = uuid4()
    _seed_tenant(sync_url, tenant_id)
    _seed_user(sync_url, user_id)
    auth_context = _auth_context(tenant_id, user_id)

    async with _tenant_session(_async_session_factory, tenant_id=tenant_id, user_id=user_id) as session:
        await _create_connection(
            session,
            tenant_id=tenant_id,
            platform="stripe",
            account_id="acct_p8_reconnect",
        )
        result = await get_provider_oauth_refresh_state(
            request=_minimal_request(),
            platform=Platform.stripe,
            x_correlation_id=uuid4(),
            db_session=session,
            auth_context=auth_context,
        )
        assert result.lifecycle_state.value == "reconnect_required"
        assert result.refresh_state.value == "not_attempted"
        assert result.last_error_code is None


@pytest.mark.asyncio
async def test_b13_p8_supported_provider_tranche_baseline_is_explicit_and_callable() -> None:
    capability_contract = json.loads(P0_CAPABILITY_CONTRACT.read_text(encoding="utf-8"))
    runtime_backed = capability_contract.get("runtime_backed_providers")
    internal_only = capability_contract.get("runtime_internal_only_providers")
    assert runtime_backed == [
        "google_ads",
        "meta_ads",
        "paypal",
        "shopify",
        "stripe",
        "woocommerce",
    ]
    assert internal_only == ["dummy"]

    dispatcher = ProviderOAuthLifecycleDispatcher()

    with pytest.raises(OAuthLifecycleRefreshError) as stripe_rate_limit:
        await dispatcher.refresh_token(
            platform="stripe",
            request=OAuthTokenRefreshRequest(
                tenant_id=uuid4(),
                correlation_id=uuid4(),
                refresh_token="stripe-rate_limit-baseline",
                scope="read_write",
            ),
        )
    assert stripe_rate_limit.value.failure_class == "provider_rate_limited"
    assert stripe_rate_limit.value.terminal is False

    with pytest.raises(OAuthLifecycleRefreshError) as paypal_invalid_grant:
        await dispatcher.refresh_token(
            platform="paypal",
            request=OAuthTokenRefreshRequest(
                tenant_id=uuid4(),
                correlation_id=uuid4(),
                refresh_token="paypal-invalid_grant-baseline",
                scope="payments_read",
            ),
        )
    assert paypal_invalid_grant.value.failure_class == "provider_invalid_grant"
    assert paypal_invalid_grant.value.terminal is True

    with pytest.raises(OAuthLifecycleRefreshError) as dummy_invalid_client:
        await dispatcher.refresh_token(
            platform="dummy",
            request=OAuthTokenRefreshRequest(
                tenant_id=uuid4(),
                correlation_id=uuid4(),
                refresh_token="dummy-invalid_client-baseline",
                scope="read_revenue",
            ),
        )
    assert dummy_invalid_client.value.failure_class == "provider_invalid_client"
    assert dummy_invalid_client.value.terminal is True
