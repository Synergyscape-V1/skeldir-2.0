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

from app.api.platform_oauth import (
    complete_provider_oauth_callback,
    disconnect_provider_oauth,
    get_provider_oauth_status,
    initiate_provider_oauth_authorization,
)
from app.schemas.attribution import (
    Platform,
    ProviderOAuthAuthorizeRequest,
    ProviderOAuthDisconnectReason,
    ProviderOAuthDisconnectRequest,
)
from app.security.auth import AuthContext
from app.services.oauth_lifecycle_dispatcher import ProviderOAuthLifecycleDispatcher
from app.services.provider_oauth_lifecycle import OAuthAuthorizeURLRequest


REPO_ROOT = Path(__file__).resolve().parents[2]
GATE_SCRIPT = REPO_ROOT / "scripts" / "ci" / "enforce_b13_p6_runtime_lifecycle.py"

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


def _minimal_request(path: str = "/api/attribution/platform-oauth/stripe/status") -> Request:
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
                    "name": f"p6-tenant-{tenant_id.hex[:8]}",
                    "api_key_hash": f"p6-api-key-{tenant_id.hex[:8]}",
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
                    "login_hash": f"p6-login-{user_id.hex}",
                    "subject_hash": f"p6-subject-{user_id.hex}",
                },
            )
    finally:
        engine.dispose()


def _credential_count(sync_url: str, tenant_id: UUID) -> int:
    engine = create_engine(sync_url)
    try:
        with engine.begin() as conn:
            return int(
                conn.execute(
                    text("SELECT COUNT(*) FROM public.platform_credentials WHERE tenant_id = :tenant_id"),
                    {"tenant_id": str(tenant_id)},
                ).scalar_one()
            )
    finally:
        engine.dispose()


@pytest.fixture(scope="session")
def _isolated_database_urls() -> tuple[str, str]:
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    base_sync_url = _sync_database_url()
    parsed = make_url(base_sync_url)
    admin_url = str(parsed.set(database="postgres"))
    isolated_db_name = f"skeldir_b13_p6_{uuid4().hex[:12]}"
    isolated_sync_url = str(parsed.set(database=isolated_db_name))
    isolated_async_url = _to_async_url(isolated_sync_url)

    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.begin() as conn:
            conn.execute(text(f'CREATE DATABASE "{isolated_db_name}" OWNER "{parsed.username or "postgres"}"'))
    except Exception as exc:
        pytest.skip(f"unable to create isolated database for B1.3-P6 runtime proofs: {exc}")
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


def test_b13_p6_gate_passes_repo_state() -> None:
    result = _run([sys.executable, str(GATE_SCRIPT)])
    assert result.returncode == 0, result.stdout + "\n" + result.stderr


def test_b13_p6_negative_control_detects_missing_required_context(tmp_path: Path) -> None:
    checks_contract = REPO_ROOT / "contracts-internal/governance/b03_phase2_required_status_checks.main.json"
    payload = json.loads(checks_contract.read_text(encoding="utf-8"))
    payload["required_contexts"] = [
        value
        for value in payload.get("required_contexts", [])
        if value != "B1.3 P6 Runtime Lifecycle Proofs"
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


def test_b13_p6_negative_control_detects_missing_router_registration(tmp_path: Path) -> None:
    main_file = REPO_ROOT / "backend/app/main.py"
    mutated = main_file.read_text(encoding="utf-8").replace(
        "app.include_router(platform_oauth.router, prefix=\"/api/attribution\", tags=[\"Provider OAuth Lifecycle\"])\n",
        "",
        1,
    )
    mutated_path = tmp_path / "main.py"
    mutated_path.write_text(mutated, encoding="utf-8")

    result = _run(
        [
            sys.executable,
            str(GATE_SCRIPT),
            "--main-file",
            str(mutated_path),
        ]
    )
    assert result.returncode != 0
    assert "missing platform_oauth.router registration" in f"{result.stdout}\n{result.stderr}"


@pytest.mark.asyncio
async def test_b13_p6_runtime_authorize_callback_status_disconnect_stripe_path(
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
        authorize = await initiate_provider_oauth_authorization(
            request=_minimal_request("/api/attribution/platform-oauth/stripe/authorize"),
            platform=Platform.stripe,
            payload=ProviderOAuthAuthorizeRequest(
                platform_account_id="acct_runtime_primary",
                redirect_uri="https://app.example/callback",
                requested_scopes=["read_write"],
            ),
            x_correlation_id=uuid4(),
            db_session=session,
            auth_context=auth_context,
        )
        assert authorize.lifecycle_state.value == "authorization_pending"
        assert "connect.stripe.com/oauth/authorize" in authorize.authorization_url

        callback = await complete_provider_oauth_callback(
            request=_minimal_request("/api/attribution/platform-oauth/stripe/callback"),
            platform=Platform.stripe,
            state=authorize.state_reference,
            x_correlation_id=uuid4(),
            db_session=session,
            auth_context=auth_context,
            code="stripe-code-123",
            error=None,
            error_description=None,
        )
        assert callback.lifecycle_state.value == "connected"
        assert callback.refresh_state.value in {"fresh", "due"}

        status_payload = await get_provider_oauth_status(
            request=_minimal_request("/api/attribution/platform-oauth/stripe/status"),
            platform=Platform.stripe,
            x_correlation_id=uuid4(),
            db_session=session,
            auth_context=auth_context,
            platform_account_id=None,
        )
        assert status_payload.lifecycle_state.value in {"connected", "expired"}
        status_json = status_payload.model_dump()
        assert "access_token" not in status_json
        assert "refresh_token" not in status_json

        disconnected = await disconnect_provider_oauth(
            request=_minimal_request("/api/attribution/platform-oauth/stripe/disconnect"),
            platform=Platform.stripe,
            payload=ProviderOAuthDisconnectRequest(
                reason=ProviderOAuthDisconnectReason.user_initiated,
            ),
            x_correlation_id=uuid4(),
            db_session=session,
            auth_context=auth_context,
        )
        assert disconnected.lifecycle_state.value == "revoked"
        disconnect_json = disconnected.model_dump()
        assert "access_token" not in disconnect_json
        assert "refresh_token" not in disconnect_json


@pytest.mark.asyncio
async def test_b13_p6_callback_replay_is_blocked_before_additional_durable_writes(
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
        authorize = await initiate_provider_oauth_authorization(
            request=_minimal_request("/api/attribution/platform-oauth/stripe/authorize"),
            platform=Platform.stripe,
            payload=ProviderOAuthAuthorizeRequest(
                platform_account_id="acct_replay_guard",
                redirect_uri="https://app.example/callback",
                requested_scopes=["read_write"],
            ),
            x_correlation_id=uuid4(),
            db_session=session,
            auth_context=auth_context,
        )

        first_callback = await complete_provider_oauth_callback(
            request=_minimal_request("/api/attribution/platform-oauth/stripe/callback"),
            platform=Platform.stripe,
            state=authorize.state_reference,
            x_correlation_id=uuid4(),
            db_session=session,
            auth_context=auth_context,
            code="stripe-code-replay",
            error=None,
            error_description=None,
        )
        assert first_callback.lifecycle_state.value == "connected"
        before_count = _credential_count(sync_url, tenant_id)
        assert before_count == 1

        replay = await complete_provider_oauth_callback(
            request=_minimal_request("/api/attribution/platform-oauth/stripe/callback"),
            platform=Platform.stripe,
            state=authorize.state_reference,
            x_correlation_id=uuid4(),
            db_session=session,
            auth_context=auth_context,
            code="stripe-code-replay-2",
            error=None,
            error_description=None,
        )
        assert isinstance(replay, JSONResponse)
        assert replay.status_code == 409
        payload = json.loads(replay.body.decode("utf-8"))
        assert payload["code"] == "provider_expired"
        after_count = _credential_count(sync_url, tenant_id)
        assert after_count == before_count


@pytest.mark.asyncio
async def test_b13_p6_callback_binding_mismatch_rejected_without_durable_side_effects(
    _isolated_database_urls: tuple[str, str],
    _async_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    sync_url, _ = _isolated_database_urls
    tenant_id = uuid4()
    user_a = uuid4()
    user_b = uuid4()
    _seed_tenant(sync_url, tenant_id)
    _seed_user(sync_url, user_a)
    _seed_user(sync_url, user_b)
    auth_a = _auth_context(tenant_id, user_a)
    auth_b = _auth_context(tenant_id, user_b)

    async with _tenant_session(_async_session_factory, tenant_id=tenant_id, user_id=user_a) as session_a:
        authorize = await initiate_provider_oauth_authorization(
            request=_minimal_request("/api/attribution/platform-oauth/stripe/authorize"),
            platform=Platform.stripe,
            payload=ProviderOAuthAuthorizeRequest(
                platform_account_id="acct_binding_guard",
                redirect_uri="https://app.example/callback",
                requested_scopes=["read_write"],
            ),
            x_correlation_id=uuid4(),
            db_session=session_a,
            auth_context=auth_a,
        )
        assert authorize.lifecycle_state.value == "authorization_pending"

    async with _tenant_session(_async_session_factory, tenant_id=tenant_id, user_id=user_b) as session_b:
        callback = await complete_provider_oauth_callback(
            request=_minimal_request("/api/attribution/platform-oauth/stripe/callback"),
            platform=Platform.stripe,
            state=authorize.state_reference,
            x_correlation_id=uuid4(),
            db_session=session_b,
            auth_context=auth_b,
            code="stripe-code-binding",
            error=None,
            error_description=None,
        )
        assert isinstance(callback, JSONResponse)
        assert callback.status_code == 404
        payload = json.loads(callback.body.decode("utf-8"))
        assert payload["code"] == "provider_not_connected"

    assert _credential_count(sync_url, tenant_id) == 0


@pytest.mark.asyncio
async def test_b13_p6_proves_deterministic_adapter_and_reference_provider_paths() -> None:
    dispatcher = ProviderOAuthLifecycleDispatcher()
    deterministic = await dispatcher.build_authorize_url(
        platform="dummy",
        request=OAuthAuthorizeURLRequest(
            tenant_id=uuid4(),
            user_id=uuid4(),
            correlation_id=uuid4(),
            redirect_uri="https://app.example/callback",
            state_nonce="state-dummy",
            requested_scopes=("read",),
        ),
    )
    stripe = await dispatcher.build_authorize_url(
        platform="stripe",
        request=OAuthAuthorizeURLRequest(
            tenant_id=uuid4(),
            user_id=uuid4(),
            correlation_id=uuid4(),
            redirect_uri="https://app.example/callback",
            state_nonce="state-stripe",
            requested_scopes=("read_write",),
        ),
    )
    assert deterministic.authorization_url.startswith("https://deterministic.provider.local/oauth/authorize?")
    assert "connect.stripe.com/oauth/authorize" in stripe.authorization_url
