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
from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from starlette.requests import Request

os.environ["TESTING"] = "1"
os.environ.setdefault("PLATFORM_TOKEN_ENCRYPTION_KEY", "test-platform-key")
os.environ.setdefault("PLATFORM_TOKEN_KEY_ID", "test-key")

from app.api.platform_oauth import (  # noqa: E402
    complete_provider_oauth_callback,
    disconnect_provider_oauth,
    get_provider_oauth_refresh_state,
    get_provider_oauth_status,
    initiate_provider_oauth_authorization,
)
from app.schemas.attribution import Platform, ProviderOAuthAuthorizeRequest, ProviderOAuthDisconnectReason, ProviderOAuthDisconnectRequest  # noqa: E402
from app.security.auth import AuthContext  # noqa: E402
from app.services.oauth_lifecycle_dispatcher import ProviderOAuthLifecycleDispatcher  # noqa: E402
from app.services.provider_oauth_lifecycle import OAuthCodeExchangeRequest  # noqa: E402
from app.services.provider_token_refresh import refresh_credential_once  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parents[3]
GATE_SCRIPT = REPO_ROOT / "scripts" / "ci" / "enforce_b13_p10_provider_tranche_proofs.py"
P10_CONTRACT = REPO_ROOT / "contracts-internal" / "governance" / "b13_p10_provider_rollout_tranches.main.json"
REQUIRED_CHECKS_CONTRACT = (
    REPO_ROOT / "contracts-internal" / "governance" / "b03_phase2_required_status_checks.main.json"
)
_AUTHORIZE_URL_EXPECTATIONS = {
    "google_ads": "accounts.google.com/o/oauth2/v2/auth",
    "meta_ads": "facebook.com/v19.0/dialog/oauth",
    "paypal": "paypal.com/signin/authorize",
    "shopify": "shopify.com/admin/oauth/authorize",
    "stripe": "connect.stripe.com/oauth/authorize",
    "woocommerce": "woocommerce.com/connect/oauth/authorize",
}


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=REPO_ROOT,
    )


def _load_p10_contract() -> dict[str, object]:
    return json.loads(P10_CONTRACT.read_text(encoding="utf-8"))


def _target_runtime_providers() -> tuple[str, ...]:
    payload = _load_p10_contract()
    providers = payload.get("target_runtime_backed_provider_set")
    if not isinstance(providers, list):
        raise AssertionError("invalid p10 contract: missing target_runtime_backed_provider_set list")
    return tuple(str(item).strip() for item in providers if str(item).strip())


def _active_tranche_providers() -> tuple[str, ...]:
    payload = _load_p10_contract()
    active_tranche_id = str(payload.get("current_active_tranche_id") or "").strip()
    tranches = payload.get("tranches")
    if not active_tranche_id or not isinstance(tranches, list):
        raise AssertionError("invalid p10 contract: missing current_active_tranche_id or tranches")
    for tranche in tranches:
        if not isinstance(tranche, dict):
            continue
        if str(tranche.get("tranche_id") or "").strip() != active_tranche_id:
            continue
        providers = tranche.get("providers")
        if not isinstance(providers, list):
            raise AssertionError("invalid p10 contract: active tranche providers must be list")
        return tuple(str(item).strip() for item in providers if str(item).strip())
    raise AssertionError(f"invalid p10 contract: active tranche not found ({active_tranche_id})")


def _artifact_dir() -> Path:
    path = REPO_ROOT / "artifacts" / "b13_p10"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_artifact(name: str, payload: dict[str, object]) -> None:
    (_artifact_dir() / name).write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _minimal_request(path: str) -> Request:
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


def _seed_tenant(sync_url: str, tenant_id: UUID, label: str) -> None:
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
                    "name": f"{label}-{tenant_id.hex[:8]}",
                    "api_key_hash": f"{label}-api-{tenant_id.hex[:8]}",
                    "notification_email": f"{label}-{tenant_id.hex[:8]}@example.test",
                },
            )
    finally:
        engine.dispose()


def _seed_user(sync_url: str, user_id: UUID, label: str) -> None:
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
                    "login_hash": f"{label}-login-{user_id.hex}",
                    "subject_hash": f"{label}-subject-{user_id.hex}",
                },
            )
    finally:
        engine.dispose()


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


@pytest.fixture(scope="session")
def _isolated_database_urls() -> tuple[str, str]:
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    base_sync_url = _sync_database_url()
    parsed = make_url(base_sync_url)
    admin_url = str(parsed.set(database="postgres"))
    isolated_db_name = f"skeldir_b13_p10_{uuid4().hex[:12]}"
    isolated_sync_url = str(parsed.set(database=isolated_db_name))
    isolated_async_url = _to_async_url(isolated_sync_url)

    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.begin() as conn:
            conn.execute(
                text(
                    f'CREATE DATABASE "{isolated_db_name}" OWNER "{parsed.username or "postgres"}"'
                )
            )
    except Exception as exc:
        pytest.skip(f"unable to create isolated database for B1.3-P10 runtime proofs: {exc}")
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


async def _fetch_credential_row(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    platform: str,
    platform_account_id: str,
) -> dict[str, object]:
    row = (
        await session.execute(
            text(
                """
                SELECT
                    pc.id,
                    pc.platform_connection_id,
                    pc.expires_at,
                    pc.next_refresh_due_at,
                    encode(pc.encrypted_access_token, 'base64') AS encrypted_access_token_b64,
                    COALESCE(encode(pc.encrypted_refresh_token, 'base64'), '') AS encrypted_refresh_token_b64,
                    conn.metadata AS connection_metadata
                FROM public.platform_credentials pc
                JOIN public.platform_connections conn ON conn.id = pc.platform_connection_id
                WHERE pc.tenant_id = :tenant_id
                  AND pc.platform = :platform
                  AND conn.platform_account_id = :platform_account_id
                ORDER BY pc.updated_at DESC
                LIMIT 1
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "platform": platform,
                "platform_account_id": platform_account_id,
            },
        )
    ).mappings().one()
    return dict(row)


async def _mark_refresh_due_now(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    credential_id: UUID,
) -> None:
    await session.execute(
        text(
            """
            UPDATE public.platform_credentials
            SET next_refresh_due_at = :due_at, updated_at = now()
            WHERE tenant_id = :tenant_id
              AND id = :credential_id
            """
        ),
        {
            "due_at": datetime.now(timezone.utc) - timedelta(minutes=1),
            "tenant_id": str(tenant_id),
            "credential_id": str(credential_id),
        },
    )


def test_b13_p10_gate_passes_repo_state() -> None:
    result = _run([sys.executable, str(GATE_SCRIPT)])
    assert result.returncode == 0, result.stdout + "\n" + result.stderr


def test_b13_p10_negative_control_detects_missing_required_context(tmp_path: Path) -> None:
    payload = json.loads(REQUIRED_CHECKS_CONTRACT.read_text(encoding="utf-8"))
    payload["required_contexts"] = [
        value
        for value in payload.get("required_contexts", [])
        if value != "B1.3 P10 Provider Tranche Proofs"
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
async def test_b13_p10_provider_lifecycle_tranche_proofs_cover_target_six_runtime_backed_providers(
    _isolated_database_urls: tuple[str, str],
    _async_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    sync_url, _ = _isolated_database_urls
    tenant_id = uuid4()
    user_id = uuid4()
    _seed_tenant(sync_url, tenant_id, "p10-breadth")
    _seed_user(sync_url, user_id, "p10-breadth")
    auth_context = _auth_context(tenant_id, user_id)

    providers = _target_runtime_providers()
    active_tranche = set(_active_tranche_providers())
    evidence: dict[str, object] = {
        "tenant_id": str(tenant_id),
        "target_runtime_backed_provider_set": list(providers),
        "active_tranche_providers": sorted(active_tranche),
        "providers": {},
    }

    async with _tenant_session(_async_session_factory, tenant_id=tenant_id, user_id=user_id) as session:
        for provider in providers:
            platform_enum = Platform(provider)
            platform_account_id = f"{provider}-acct-p10"
            authorization_code = f"{provider}-code-{uuid4().hex}"

            authorize = await initiate_provider_oauth_authorization(
                request=_minimal_request(f"/api/attribution/platform-oauth/{provider}/authorize"),
                platform=platform_enum,
                payload=ProviderOAuthAuthorizeRequest(
                    platform_account_id=platform_account_id,
                    redirect_uri="https://app.example/callback",
                    requested_scopes=["read_write"],
                ),
                x_correlation_id=uuid4(),
                db_session=session,
                auth_context=auth_context,
            )
            assert authorize.lifecycle_state.value == "authorization_pending"
            assert _AUTHORIZE_URL_EXPECTATIONS[provider] in authorize.authorization_url

            callback = await complete_provider_oauth_callback(
                request=_minimal_request(f"/api/attribution/platform-oauth/{provider}/callback"),
                platform=platform_enum,
                state=authorize.state_reference,
                x_correlation_id=uuid4(),
                db_session=session,
                auth_context=auth_context,
                code=authorization_code,
                error=None,
                error_description=None,
            )
            assert callback.lifecycle_state.value == "connected"

            credential_row = await _fetch_credential_row(
                session,
                tenant_id=tenant_id,
                platform=provider,
                platform_account_id=platform_account_id,
            )
            assert credential_row["expires_at"] is not None
            assert credential_row["next_refresh_due_at"] is not None
            assert authorization_code not in str(credential_row["encrypted_access_token_b64"])
            assert authorization_code not in str(credential_row["encrypted_refresh_token_b64"])

            metadata = credential_row["connection_metadata"] if isinstance(credential_row["connection_metadata"], dict) else {}
            oauth_metadata = metadata.get("oauth") if isinstance(metadata.get("oauth"), dict) else {}
            provider_account_id = str(oauth_metadata.get("provider_account_id") or "")
            granted_scope = str(oauth_metadata.get("granted_scope") or "")
            assert provider_account_id
            assert granted_scope

            credential_id = UUID(str(credential_row["id"]))
            await _mark_refresh_due_now(
                session,
                tenant_id=tenant_id,
                credential_id=credential_id,
            )
            refreshed = await refresh_credential_once(
                session,
                tenant_id=tenant_id,
                credential_id=credential_id,
                correlation_id=uuid4(),
                force=True,
            )
            assert refreshed.status == "refreshed"

            status_payload = await get_provider_oauth_status(
                request=_minimal_request(f"/api/attribution/platform-oauth/{provider}/status"),
                platform=platform_enum,
                x_correlation_id=uuid4(),
                db_session=session,
                auth_context=auth_context,
                platform_account_id=None,
            )
            assert status_payload.lifecycle_state.value in {"connected", "expired"}

            disconnected = await disconnect_provider_oauth(
                request=_minimal_request(f"/api/attribution/platform-oauth/{provider}/disconnect"),
                platform=platform_enum,
                payload=ProviderOAuthDisconnectRequest(reason=ProviderOAuthDisconnectReason.user_initiated),
                x_correlation_id=uuid4(),
                db_session=session,
                auth_context=auth_context,
            )
            assert disconnected.lifecycle_state.value == "revoked"

            refresh_state = await get_provider_oauth_refresh_state(
                request=_minimal_request(f"/api/attribution/platform-oauth/{provider}/refresh-state"),
                platform=platform_enum,
                x_correlation_id=uuid4(),
                db_session=session,
                auth_context=auth_context,
            )
            assert isinstance(refresh_state, JSONResponse)
            assert refresh_state.status_code == 409
            refresh_payload = json.loads(refresh_state.body.decode("utf-8"))
            assert refresh_payload["code"] == "provider_revoked"

            evidence["providers"][provider] = {
                "authorize_url_fragment": _AUTHORIZE_URL_EXPECTATIONS[provider],
                "connected_state": callback.lifecycle_state.value,
                "refresh_status": refreshed.status,
                "revoked_code": refresh_payload["code"],
                "account_scope_identity_proven": bool(provider_account_id and granted_scope),
                "active_tranche_member": provider in active_tranche,
            }

    _write_artifact("p10_active_tranche_runtime_report.json", evidence)


@pytest.mark.asyncio
async def test_b13_p10_refresh_concurrency_topology_avoids_shared_mutable_seeded_credentials() -> None:
    payload = _load_p10_contract()
    target_providers = _target_runtime_providers()
    topology = payload.get("provider_proof_topology")
    assert isinstance(topology, dict)

    dispatcher = ProviderOAuthLifecycleDispatcher()
    issued_refresh_tokens: list[str] = []
    live_credentials_required_any = False

    for provider in target_providers:
        entry = topology.get(provider)
        assert isinstance(entry, dict)
        assert entry.get("refresh_token_rotation_possible") is True
        assert entry.get("live_credentials_required") is False
        assert entry.get("credential_concurrency_strategy") == "isolated_per_test_database_and_nonshared_tokens"
        live_credentials_required_any = live_credentials_required_any or bool(entry.get("live_credentials_required"))

        exchanged = await dispatcher.exchange_auth_code(
            platform=provider,
            request=OAuthCodeExchangeRequest(
                tenant_id=uuid4(),
                user_id=uuid4(),
                correlation_id=uuid4(),
                authorization_code=f"{provider}-code-{uuid4().hex}",
                redirect_uri="https://app.example/callback",
            ),
        )
        assert exchanged.refresh_token is not None
        issued_refresh_tokens.append(str(exchanged.refresh_token))

    assert live_credentials_required_any is False
    assert len(set(issued_refresh_tokens)) == len(issued_refresh_tokens)
    assert all("seed" not in token.lower() for token in issued_refresh_tokens)

    risky_env_markers = [
        "SHARED_PROVIDER_REFRESH_TOKEN",
        "GLOBAL_PROVIDER_REFRESH_TOKEN",
        "SEEDED_PROVIDER_REFRESH_TOKEN",
    ]
    assert all(os.getenv(marker) in {None, ""} for marker in risky_env_markers)

    topology_report = {
        "target_runtime_backed_provider_set": list(target_providers),
        "live_credentials_required_any": live_credentials_required_any,
        "issued_refresh_token_count": len(issued_refresh_tokens),
        "unique_issued_refresh_token_count": len(set(issued_refresh_tokens)),
        "shared_mutable_refresh_credential_detected": False,
    }
    _write_artifact("p10_proof_topology_report.json", topology_report)
