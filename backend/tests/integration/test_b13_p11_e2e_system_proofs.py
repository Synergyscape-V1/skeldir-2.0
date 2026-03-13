from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from starlette.requests import Request

os.environ["TESTING"] = "1"
os.environ.setdefault("PLATFORM_TOKEN_ENCRYPTION_KEY", "test-platform-key")
os.environ.setdefault("PLATFORM_TOKEN_KEY_ID", "test-key")
_BOOTSTRAP_MIGRATION_DATABASE_URL = os.environ.get("MIGRATION_DATABASE_URL")
_BOOTSTRAP_DATABASE_URL = os.environ.get("DATABASE_URL")

from app.api.platform_oauth import (  # noqa: E402
    complete_provider_oauth_callback,
    disconnect_provider_oauth,
    get_provider_oauth_refresh_state,
    get_provider_oauth_status,
    initiate_provider_oauth_authorization,
)
from app.schemas.attribution import (  # noqa: E402
    Platform,
    ProviderOAuthAuthorizeRequest,
    ProviderOAuthDisconnectReason,
    ProviderOAuthDisconnectRequest,
)
from app.security.auth import AuthContext  # noqa: E402
from app.services.platform_credentials import (  # noqa: E402
    PlatformCredentialNotFoundError,
    PlatformCredentialStore,
)
from app.services.provider_oauth_runtime import (  # noqa: E402
    ProviderLifecycleProblem,
    ProviderOAuthLifecycleRuntimeService,
)
from app.services.provider_token_refresh import (  # noqa: E402
    claim_due_credentials_for_tenant,
    refresh_credential_once,
)
from app.services.provider_valid_token_resolution import ProviderValidTokenResolver  # noqa: E402
from app.tasks.authority import AUTHORITY_ENVELOPE_HEADER, SystemAuthorityEnvelope  # noqa: E402
from app.tasks.maintenance import refresh_provider_oauth_credential  # noqa: E402
import app.tasks.maintenance as maintenance_tasks  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parents[3]
GATE_SCRIPT = REPO_ROOT / "scripts" / "ci" / "enforce_b13_p11_e2e_system_proofs.py"
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
    values = tuple(str(item).strip() for item in providers if str(item).strip())
    if len(values) != 6:
        raise AssertionError(f"invalid p10 contract: expected six providers, got {values}")
    return values


def _artifact_dir() -> Path:
    path = REPO_ROOT / "artifacts" / "b13_p11"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_artifact(name: str, payload: dict[str, object]) -> None:
    (_artifact_dir() / name).write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _write_log_artifact(lines: list[str]) -> None:
    path = _artifact_dir() / "p11_runtime_logs.txt"
    with path.open("a", encoding="utf-8") as handle:
        for line in lines:
            handle.write(line.rstrip("\n"))
            handle.write("\n")


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
    url = (
        _BOOTSTRAP_MIGRATION_DATABASE_URL
        or _BOOTSTRAP_DATABASE_URL
        or os.environ.get("MIGRATION_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
    )
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
        except ProgrammingError as exc:
            # Local least-privilege snapshots can enforce RLS on users. The
            # OAuth integration harness does not require a persisted users row
            # when AuthContext is explicitly injected.
            if "row-level security policy" not in str(exc).lower():
                raise
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
def _runtime_database_urls() -> tuple[str, str]:
    sync_url = _sync_database_url()
    async_url = _to_async_url(sync_url)
    os.environ["MIGRATION_DATABASE_URL"] = sync_url
    os.environ["DATABASE_URL"] = async_url
    return sync_url, async_url


@pytest.fixture
async def _async_session_factory(
    _runtime_database_urls: tuple[str, str],
) -> async_sessionmaker[AsyncSession]:
    _, async_url = _runtime_database_urls
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
                    pc.lifecycle_status,
                    pc.expires_at,
                    pc.next_refresh_due_at,
                    pc.last_refresh_at,
                    pc.refresh_failure_count,
                    pc.last_failure_class,
                    pc.revoked_at,
                    encode(pc.encrypted_access_token, 'base64') AS encrypted_access_token_b64,
                    COALESCE(encode(pc.encrypted_refresh_token, 'base64'), '') AS encrypted_refresh_token_b64,
                    conn.connection_metadata AS connection_metadata
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


async def _provider_row_count(session: AsyncSession, *, tenant_id: UUID) -> int:
    row = (
        await session.execute(
            text(
                """
                SELECT COUNT(*) AS credential_count
                FROM public.platform_credentials
                WHERE tenant_id = :tenant_id
                """
            ),
            {"tenant_id": str(tenant_id)},
        )
    ).mappings().one()
    return int(row["credential_count"])


def _assert_not_leaked(text_value: str, sensitive_values: tuple[str, ...]) -> None:
    for sensitive in sensitive_values:
        assert sensitive not in text_value


def test_b13_p11_gate_passes_repo_state() -> None:
    result = _run([sys.executable, str(GATE_SCRIPT)])
    assert result.returncode == 0, result.stdout + "\n" + result.stderr


def test_b13_p11_negative_control_detects_missing_required_context(tmp_path: Path) -> None:
    payload = json.loads(REQUIRED_CHECKS_CONTRACT.read_text(encoding="utf-8"))
    payload["required_contexts"] = [
        value
        for value in payload.get("required_contexts", [])
        if value != "B1.3 P11 E2E System Proofs"
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


def test_b13_p11_negative_control_detects_artifact_integrity_gaps(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    junit_xml = artifacts_dir / "junit.xml"
    junit_xml.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<testsuite tests="2" skipped="0" failures="0" errors="0">
  <testcase classname="p11" name="test_b13_p11_composed_lifecycle_lock_with_six_provider_topology"></testcase>
  <testcase classname="p11" name="test_b13_p11_multi_tenant_safety_lock_and_tenantless_worker_fail_closed"></testcase>
</testsuite>
""",
        encoding="utf-8",
    )
    (artifacts_dir / "p11_composed_runtime_report.json").write_text(
        json.dumps(
            {
                "target_runtime_backed_provider_set": list(_target_runtime_providers()),
                "providers": {
                    provider: {
                        "authorize_state": "authorization_pending",
                        "callback_state": "connected",
                        "refresh_status": "refreshed",
                        "downstream_use_after_refresh": True,
                        "revoked_state": "revoked",
                        "graceful_degraded_code": "provider_revoked",
                        "encrypted_store_verified": True,
                        "expiry_tracked": True,
                    }
                    for provider in _target_runtime_providers()
                },
                "invalid_credential_path": {
                    "terminal_status": "revoked_terminal",
                    "terminal_failure_class": "provider_invalid_client",
                    "graceful_degraded_code": "provider_revoked",
                    "non_leaky": True,
                },
            }
        ),
        encoding="utf-8",
    )
    (artifacts_dir / "p11_negative_controls_report.json").write_text(
        json.dumps(
            {
                "cross_tenant_status_code": 404,
                "cross_tenant_disconnect_code": 404,
                "tenantless_worker_error": "authority_envelope header is required",
                "tenantless_side_effects_blocked": True,
                "worker_positive_status": "refreshed",
            }
        ),
        encoding="utf-8",
    )
    (artifacts_dir / "p11_db_runtime_evidence.json").write_text(
        json.dumps(
            {
                "provider_row_count": 6,
                "encrypted_credentials_verified": True,
                "plaintext_leak_detected": False,
            }
        ),
        encoding="utf-8",
    )
    result = _run(
        [
            sys.executable,
            str(GATE_SCRIPT),
            "--require-runtime-execution",
            "--junit-xml",
            str(junit_xml),
            "--artifacts-dir",
            str(artifacts_dir),
        ]
    )
    assert result.returncode != 0
    assert "missing runtime proof artifact" in f"{result.stdout}\n{result.stderr}"


def test_b13_p11_runtime_execution_gate_passes_with_real_artifact_shape(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    junit_xml = artifacts_dir / "junit.xml"
    junit_xml.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<testsuite tests="2" skipped="0" failures="0" errors="0">
  <testcase classname="p11" name="test_b13_p11_composed_lifecycle_lock_with_six_provider_topology"></testcase>
  <testcase classname="p11" name="test_b13_p11_multi_tenant_safety_lock_and_tenantless_worker_fail_closed"></testcase>
</testsuite>
""",
        encoding="utf-8",
    )
    providers = list(_target_runtime_providers())
    (artifacts_dir / "p11_composed_runtime_report.json").write_text(
        json.dumps(
            {
                "target_runtime_backed_provider_set": providers,
                "providers": {
                    provider: {
                        "authorize_state": "authorization_pending",
                        "callback_state": "connected",
                        "refresh_status": "refreshed",
                        "downstream_use_after_refresh": True,
                        "revoked_state": "revoked",
                        "graceful_degraded_code": "provider_revoked",
                        "encrypted_store_verified": True,
                        "expiry_tracked": True,
                    }
                    for provider in providers
                },
                "invalid_credential_path": {
                    "terminal_status": "revoked_terminal",
                    "terminal_failure_class": "provider_invalid_client",
                    "graceful_degraded_code": "provider_revoked",
                    "non_leaky": True,
                },
            }
        ),
        encoding="utf-8",
    )
    (artifacts_dir / "p11_negative_controls_report.json").write_text(
        json.dumps(
            {
                "cross_tenant_status_code": 404,
                "cross_tenant_disconnect_code": 404,
                "tenantless_worker_error": "authority_envelope header is required",
                "tenantless_side_effects_blocked": True,
                "worker_positive_status": "refreshed",
            }
        ),
        encoding="utf-8",
    )
    (artifacts_dir / "p11_db_runtime_evidence.json").write_text(
        json.dumps(
            {
                "provider_row_count": 6,
                "encrypted_credentials_verified": True,
                "plaintext_leak_detected": False,
            }
        ),
        encoding="utf-8",
    )
    (artifacts_dir / "p11_runtime_logs.txt").write_text(
        "p11 runtime log capture\n",
        encoding="utf-8",
    )
    (artifacts_dir / "p11_branch_protection_evidence.json").write_text(
        json.dumps(
            {
                "authority_mode": "fallback_workflow_contract_only",
                "required_context_present_in_contract": True,
                "required_context_present_in_workflow": True,
            }
        ),
        encoding="utf-8",
    )
    result = _run(
        [
            sys.executable,
            str(GATE_SCRIPT),
            "--require-runtime-execution",
            "--junit-xml",
            str(junit_xml),
            "--artifacts-dir",
            str(artifacts_dir),
        ]
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr

@pytest.mark.asyncio
async def test_b13_p11_composed_lifecycle_lock_with_six_provider_topology(
    _runtime_database_urls: tuple[str, str],
    _async_session_factory: async_sessionmaker[AsyncSession],
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    providers = _target_runtime_providers()
    sync_url, _ = _runtime_database_urls
    tenant_id = uuid4()
    user_id = uuid4()
    _seed_tenant(sync_url, tenant_id, "p11-composed")
    _seed_user(sync_url, user_id, "p11-composed")
    auth_context = _auth_context(tenant_id, user_id)
    runtime_service = ProviderOAuthLifecycleRuntimeService()
    resolver = ProviderValidTokenResolver(enqueue_refresh=False)

    composed_evidence: dict[str, object] = {
        "tenant_id": str(tenant_id),
        "target_runtime_backed_provider_set": list(providers),
        "providers": {},
        "invalid_credential_path": {},
    }
    db_evidence: dict[str, object] = {
        "tenant_id": str(tenant_id),
        "provider_rows": {},
        "provider_row_count": 0,
        "encrypted_credentials_verified": True,
        "plaintext_leak_detected": False,
    }
    sensitive_values: list[str] = []

    async with _tenant_session(_async_session_factory, tenant_id=tenant_id, user_id=user_id) as session:
        for provider in providers:
            platform_enum = Platform(provider)
            platform_account_id = f"{provider}-acct-p11"
            authorization_code = f"{provider}-code-{uuid4().hex}"
            sensitive_values.append(authorization_code)

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

            status_payload = await get_provider_oauth_status(
                request=_minimal_request(f"/api/attribution/platform-oauth/{provider}/status"),
                platform=platform_enum,
                x_correlation_id=uuid4(),
                db_session=session,
                auth_context=auth_context,
                platform_account_id=None,
            )
            assert status_payload.lifecycle_state.value in {"connected", "expired"}

            credential_row = await _fetch_credential_row(
                session,
                tenant_id=tenant_id,
                platform=provider,
                platform_account_id=platform_account_id,
            )
            assert credential_row["expires_at"] is not None
            assert credential_row["next_refresh_due_at"] is not None
            encrypted_access = str(credential_row["encrypted_access_token_b64"])
            encrypted_refresh = str(credential_row["encrypted_refresh_token_b64"])
            assert encrypted_access
            assert encrypted_refresh
            assert authorization_code not in encrypted_access
            assert authorization_code not in encrypted_refresh

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
            due = await claim_due_credentials_for_tenant(
                session,
                tenant_id=tenant_id,
                as_of=datetime.now(timezone.utc),
                limit=100,
            )
            assert credential_id in due.claimed_credential_ids
            refreshed = await refresh_credential_once(
                session,
                tenant_id=tenant_id,
                credential_id=credential_id,
                correlation_id=uuid4(),
                force=True,
            )
            assert refreshed.status == "refreshed"

            resolved = await resolver.resolve_for_connection(
                session,
                tenant_id=tenant_id,
                connection_id=UUID(str(credential_row["platform_connection_id"])),
                correlation_id=uuid4(),
            )
            expected_prefix = f"{provider}-refresh-access-"
            assert resolved.access_token.startswith(expected_prefix)
            sensitive_values.append(resolved.access_token)

            disconnected = await disconnect_provider_oauth(
                request=_minimal_request(f"/api/attribution/platform-oauth/{provider}/disconnect"),
                platform=platform_enum,
                payload=ProviderOAuthDisconnectRequest(
                    reason=ProviderOAuthDisconnectReason.user_initiated,
                ),
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
            assert "access_token" not in refresh_state.body.decode("utf-8")
            assert "refresh_token" not in refresh_state.body.decode("utf-8")

            with pytest.raises(PlatformCredentialNotFoundError):
                await resolver.resolve_for_connection(
                    session,
                    tenant_id=tenant_id,
                    connection_id=UUID(str(credential_row["platform_connection_id"])),
                    correlation_id=uuid4(),
                )

            composed_evidence["providers"][provider] = {
                "authorize_state": authorize.lifecycle_state.value,
                "callback_state": callback.lifecycle_state.value,
                "status_state": status_payload.lifecycle_state.value,
                "refresh_status": refreshed.status,
                "downstream_use_after_refresh": resolved.access_token.startswith(expected_prefix),
                "revoked_state": disconnected.lifecycle_state.value,
                "graceful_degraded_code": refresh_payload["code"],
                "encrypted_store_verified": True,
                "expiry_tracked": True,
                "account_scope_identity_proven": bool(provider_account_id and granted_scope),
            }
            db_evidence["provider_rows"][provider] = {
                "platform_account_id": platform_account_id,
                "credential_id": str(credential_row["id"]),
                "encrypted_access_token_len": len(encrypted_access),
                "encrypted_refresh_token_len": len(encrypted_refresh),
            }

        invalid_provider = "stripe"
        invalid_account_id = "stripe-acct-p11-invalid"
        invalid_code = f"stripe-code-{uuid4().hex}"
        invalid_refresh_value = "stripe-invalid_client-terminal"
        sensitive_values.extend([invalid_code, invalid_refresh_value])

        invalid_authorize = await initiate_provider_oauth_authorization(
            request=_minimal_request("/api/attribution/platform-oauth/stripe/authorize"),
            platform=Platform.stripe,
            payload=ProviderOAuthAuthorizeRequest(
                platform_account_id=invalid_account_id,
                redirect_uri="https://app.example/callback",
                requested_scopes=["read_write"],
            ),
            x_correlation_id=uuid4(),
            db_session=session,
            auth_context=auth_context,
        )
        assert invalid_authorize.lifecycle_state.value == "authorization_pending"

        invalid_callback = await complete_provider_oauth_callback(
            request=_minimal_request("/api/attribution/platform-oauth/stripe/callback"),
            platform=Platform.stripe,
            state=invalid_authorize.state_reference,
            x_correlation_id=uuid4(),
            db_session=session,
            auth_context=auth_context,
            code=invalid_code,
            error=None,
            error_description=None,
        )
        assert invalid_callback.lifecycle_state.value == "connected"

        invalid_row = await _fetch_credential_row(
            session,
            tenant_id=tenant_id,
            platform="stripe",
            platform_account_id=invalid_account_id,
        )
        invalid_credential_id = UUID(str(invalid_row["id"]))
        await PlatformCredentialStore.mark_refresh_success(
            session,
            tenant_id=tenant_id,
            credential_id=invalid_credential_id,
            access_token="stripe-terminal-prep-access",
            refresh_token=invalid_refresh_value,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=4),
            scope="read_write",
            token_type="Bearer",
            key_id="test-key",
            encryption_key="test-platform-key",
        )
        await _mark_refresh_due_now(
            session,
            tenant_id=tenant_id,
            credential_id=invalid_credential_id,
        )
        terminal_result = await refresh_credential_once(
            session,
            tenant_id=tenant_id,
            credential_id=invalid_credential_id,
            correlation_id=uuid4(),
            force=True,
        )
        assert terminal_result.status == "revoked_terminal"
        assert terminal_result.failure_class == "provider_invalid_client"
        _assert_not_leaked(
            json.dumps(terminal_result.to_public_dict(), sort_keys=True),
            (invalid_refresh_value,),
        )

        with pytest.raises(ProviderLifecycleProblem) as terminal_refresh_state:
            await runtime_service.get_refresh_state(
                session,
                tenant_id=tenant_id,
                user_id=user_id,
                platform="stripe",
            )
        assert terminal_refresh_state.value.code == "provider_revoked"
        assert invalid_refresh_value not in terminal_refresh_state.value.detail

        composed_evidence["invalid_credential_path"] = {
            "provider": invalid_provider,
            "terminal_status": terminal_result.status,
            "terminal_failure_class": terminal_result.failure_class,
            "graceful_degraded_code": terminal_refresh_state.value.code,
            "non_leaky": invalid_refresh_value not in terminal_refresh_state.value.detail,
        }

        db_evidence["provider_row_count"] = await _provider_row_count(session, tenant_id=tenant_id)
        db_evidence["encrypted_credentials_verified"] = True
        db_evidence["plaintext_leak_detected"] = False

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    _assert_not_leaked(log_text, tuple(sensitive_values))
    _assert_not_leaked(json.dumps(composed_evidence, sort_keys=True), tuple(sensitive_values))
    _assert_not_leaked(json.dumps(db_evidence, sort_keys=True), tuple(sensitive_values))

    _write_artifact("p11_composed_runtime_report.json", composed_evidence)
    _write_artifact("p11_db_runtime_evidence.json", db_evidence)
    _write_log_artifact(
        [
            f"captured_log_records={len(caplog.records)}",
            f"tenant_id={tenant_id}",
            "composed_lifecycle_lock=passed",
            "six_provider_topology=passed",
            "invalid_credential_degrade_non_leaky=passed",
        ]
    )


@pytest.mark.asyncio
async def test_b13_p11_multi_tenant_safety_lock_and_tenantless_worker_fail_closed(
    _runtime_database_urls: tuple[str, str],
    _async_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sync_url, _ = _runtime_database_urls
    tenant_a = uuid4()
    tenant_b = uuid4()
    user_a = uuid4()
    user_b = uuid4()
    _seed_tenant(sync_url, tenant_a, "p11-tenant-a")
    _seed_tenant(sync_url, tenant_b, "p11-tenant-b")
    _seed_user(sync_url, user_a, "p11-user-a")
    _seed_user(sync_url, user_b, "p11-user-b")
    auth_a = _auth_context(tenant_a, user_a)
    auth_b = _auth_context(tenant_b, user_b)

    evidence: dict[str, object] = {
        "tenant_a": str(tenant_a),
        "tenant_b": str(tenant_b),
    }

    async with _tenant_session(_async_session_factory, tenant_id=tenant_a, user_id=user_a) as session_a:
        authorize = await initiate_provider_oauth_authorization(
            request=_minimal_request("/api/attribution/platform-oauth/stripe/authorize"),
            platform=Platform.stripe,
            payload=ProviderOAuthAuthorizeRequest(
                platform_account_id="acct-p11-isolation",
                redirect_uri="https://app.example/callback",
                requested_scopes=["read_write"],
            ),
            x_correlation_id=uuid4(),
            db_session=session_a,
            auth_context=auth_a,
        )
        callback = await complete_provider_oauth_callback(
            request=_minimal_request("/api/attribution/platform-oauth/stripe/callback"),
            platform=Platform.stripe,
            state=authorize.state_reference,
            x_correlation_id=uuid4(),
            db_session=session_a,
            auth_context=auth_a,
            code=f"stripe-code-{uuid4().hex}",
            error=None,
            error_description=None,
        )
        assert callback.lifecycle_state.value == "connected"
        row_before = await _fetch_credential_row(
            session_a,
            tenant_id=tenant_a,
            platform="stripe",
            platform_account_id="acct-p11-isolation",
        )
        credential_id = UUID(str(row_before["id"]))

    async with _tenant_session(_async_session_factory, tenant_id=tenant_b, user_id=user_b) as session_b:
        cross_status = await get_provider_oauth_status(
            request=_minimal_request("/api/attribution/platform-oauth/stripe/status"),
            platform=Platform.stripe,
            x_correlation_id=uuid4(),
            db_session=session_b,
            auth_context=auth_b,
            platform_account_id=None,
        )
        assert isinstance(cross_status, JSONResponse)
        assert cross_status.status_code == 404
        cross_status_payload = json.loads(cross_status.body.decode("utf-8"))
        assert cross_status_payload["code"] == "provider_not_connected"

        cross_disconnect = await disconnect_provider_oauth(
            request=_minimal_request("/api/attribution/platform-oauth/stripe/disconnect"),
            platform=Platform.stripe,
            payload=ProviderOAuthDisconnectRequest(
                reason=ProviderOAuthDisconnectReason.user_initiated,
            ),
            x_correlation_id=uuid4(),
            db_session=session_b,
            auth_context=auth_b,
        )
        assert isinstance(cross_disconnect, JSONResponse)
        assert cross_disconnect.status_code == 404
        cross_disconnect_payload = json.loads(cross_disconnect.body.decode("utf-8"))
        assert cross_disconnect_payload["code"] == "provider_not_connected"

    async with _tenant_session(_async_session_factory, tenant_id=tenant_a, user_id=user_a) as session_a_check:
        row_after_cross_tenant = await _fetch_credential_row(
            session_a_check,
            tenant_id=tenant_a,
            platform="stripe",
            platform_account_id="acct-p11-isolation",
        )
        assert row_after_cross_tenant["last_refresh_at"] is None
        assert int(row_after_cross_tenant["refresh_failure_count"]) == 0
        await _mark_refresh_due_now(
            session_a_check,
            tenant_id=tenant_a,
            credential_id=credential_id,
        )

    tenantless_result = refresh_provider_oauth_credential.apply(
        kwargs={
            "credential_id": str(credential_id),
            "correlation_id": str(uuid4()),
            "refresh_claimed": True,
        }
    )
    with pytest.raises(ValueError, match="authority_envelope header is required"):
        tenantless_result.get(propagate=True)

    async with _tenant_session(_async_session_factory, tenant_id=tenant_a, user_id=user_a) as session_a_check:
        row_after_tenantless = await _fetch_credential_row(
            session_a_check,
            tenant_id=tenant_a,
            platform="stripe",
            platform_account_id="acct-p11-isolation",
        )
        assert row_after_tenantless["last_refresh_at"] is None
        assert int(row_after_tenantless["refresh_failure_count"]) == 0

    monkeypatch.setattr(maintenance_tasks, "AsyncSessionLocal", _async_session_factory)
    positive_result = refresh_provider_oauth_credential.apply(
        kwargs={
            "credential_id": str(credential_id),
            "correlation_id": str(uuid4()),
            "refresh_claimed": True,
        },
        headers={
            AUTHORITY_ENVELOPE_HEADER: SystemAuthorityEnvelope(tenant_id=tenant_a).model_dump(mode="json"),
        },
    )
    positive_payload = positive_result.get(propagate=True)
    assert positive_payload["status"] == "refreshed"

    async with _tenant_session(_async_session_factory, tenant_id=tenant_a, user_id=user_a) as session_a_check:
        row_after_worker_positive = await _fetch_credential_row(
            session_a_check,
            tenant_id=tenant_a,
            platform="stripe",
            platform_account_id="acct-p11-isolation",
        )
        assert row_after_worker_positive["last_refresh_at"] is not None

    evidence.update(
        {
            "cross_tenant_status_code": cross_status_payload["status"],
            "cross_tenant_disconnect_code": cross_disconnect_payload["status"],
            "tenantless_worker_error": "authority_envelope header is required",
            "tenantless_side_effects_blocked": True,
            "worker_positive_status": positive_payload["status"],
            "worker_positive_failure_class": positive_payload.get("failure_class"),
        }
    )
    _write_artifact("p11_negative_controls_report.json", evidence)
    _write_log_artifact(
        [
            "multi_tenant_safety_lock=passed",
            "tenantless_worker_fail_closed=passed",
        ]
    )
