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
GATE_SCRIPT = REPO_ROOT / "scripts" / "ci" / "enforce_b13_p9_core_substrate_closure.py"
REQUIRED_CHECKS_CONTRACT = (
    REPO_ROOT / "contracts-internal" / "governance" / "b03_phase2_required_status_checks.main.json"
)


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=REPO_ROOT,
    )


def _artifact_dir() -> Path:
    path = REPO_ROOT / "artifacts" / "b13_p9"
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
    # Run closure-grade runtime proofs against the job-local Postgres database.
    # CI applies migrations ahead of this suite; this fixture only binds URLs.
    # Avoiding per-test CREATE DATABASE removes a skip-prone dependency on admin
    # privileges and makes proof execution deterministic on authoritative runs.
    proof_sync_url = _sync_database_url()
    proof_async_url = _to_async_url(proof_sync_url)
    os.environ["MIGRATION_DATABASE_URL"] = proof_sync_url
    os.environ["DATABASE_URL"] = proof_async_url
    return proof_sync_url, proof_async_url


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
                    pc.lifecycle_status,
                    pc.expires_at,
                    pc.next_refresh_due_at,
                    pc.last_refresh_at,
                    pc.refresh_failure_count,
                    pc.last_failure_class,
                    pc.revoked_at,
                    encode(pc.encrypted_access_token, 'base64') AS encrypted_access_token_b64,
                    COALESCE(encode(pc.encrypted_refresh_token, 'base64'), '') AS encrypted_refresh_token_b64
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


async def _run_scheduled_refresh_for_credential(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    credential_id: UUID,
) -> str:
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
    result = await refresh_credential_once(
        session,
        tenant_id=tenant_id,
        credential_id=credential_id,
        correlation_id=uuid4(),
        force=True,
    )
    return result.status


def test_b13_p9_gate_passes_repo_state() -> None:
    result = _run([sys.executable, str(GATE_SCRIPT)])
    assert result.returncode == 0, result.stdout + "\n" + result.stderr


def test_b13_p9_negative_control_detects_missing_required_context(tmp_path: Path) -> None:
    payload = json.loads(REQUIRED_CHECKS_CONTRACT.read_text(encoding="utf-8"))
    payload["required_contexts"] = [
        value
        for value in payload.get("required_contexts", [])
        if value != "B1.3 P9 Core Substrate Closure Proofs"
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


def test_b13_p9_negative_control_detects_skipped_runtime_execution(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    junit_xml = artifacts_dir / "junit.xml"
    junit_xml.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<testsuite tests="2" skipped="1" failures="0" errors="0">
  <testcase classname="p9" name="test_b13_p9_composed_lifecycle_closure_with_deterministic_and_stripe_paths"><skipped message="fixture unavailable">skip</skipped></testcase>
  <testcase classname="p9" name="test_b13_p9_cross_tenant_and_tenantless_worker_fail_before_side_effects"></testcase>
</testsuite>
""",
        encoding="utf-8",
    )
    (artifacts_dir / "p9_composed_runtime_report.json").write_text(
        json.dumps({"stripe_path": {"refresh_status": "refreshed"}, "dummy_path": {"terminal_status": "revoked_terminal", "graceful_degraded_code": "provider_revoked"}}),
        encoding="utf-8",
    )
    (artifacts_dir / "p9_negative_controls_report.json").write_text(
        json.dumps(
            {
                "cross_tenant_status_code": 404,
                "cross_tenant_disconnect_code": 404,
                "tenantless_worker_error": "authority_envelope header is required",
                "worker_positive_status": "refreshed",
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
    assert "did not pass (outcome=skipped)" in f"{result.stdout}\n{result.stderr}"


def test_b13_p9_runtime_execution_gate_passes_with_real_artifact_shape(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    junit_xml = artifacts_dir / "junit.xml"
    junit_xml.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<testsuite tests="2" skipped="0" failures="0" errors="0">
  <testcase classname="p9" name="test_b13_p9_composed_lifecycle_closure_with_deterministic_and_stripe_paths"></testcase>
  <testcase classname="p9" name="test_b13_p9_cross_tenant_and_tenantless_worker_fail_before_side_effects"></testcase>
</testsuite>
""",
        encoding="utf-8",
    )
    (artifacts_dir / "p9_composed_runtime_report.json").write_text(
        json.dumps(
            {
                "stripe_path": {"refresh_status": "refreshed"},
                "dummy_path": {
                    "terminal_status": "revoked_terminal",
                    "graceful_degraded_code": "provider_revoked",
                },
            }
        ),
        encoding="utf-8",
    )
    (artifacts_dir / "p9_negative_controls_report.json").write_text(
        json.dumps(
            {
                "cross_tenant_status_code": 404,
                "cross_tenant_disconnect_code": 404,
                "tenantless_worker_error": "authority_envelope header is required",
                "worker_positive_status": "refreshed",
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
async def test_b13_p9_composed_lifecycle_closure_with_deterministic_and_stripe_paths(
    _isolated_database_urls: tuple[str, str],
    _async_session_factory: async_sessionmaker[AsyncSession],
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    sync_url, _ = _isolated_database_urls
    tenant_id = uuid4()
    user_id = uuid4()
    _seed_tenant(sync_url, tenant_id, "p9-substrate")
    _seed_user(sync_url, user_id, "p9-substrate")
    auth_context = _auth_context(tenant_id, user_id)
    runtime_service = ProviderOAuthLifecycleRuntimeService()
    resolver = ProviderValidTokenResolver(enqueue_refresh=False)

    evidence: dict[str, object] = {
        "tenant_id": str(tenant_id),
        "user_id": str(user_id),
        "stripe_path": {},
        "dummy_path": {},
    }

    async with _tenant_session(_async_session_factory, tenant_id=tenant_id, user_id=user_id) as session:
        stripe_authorize = await initiate_provider_oauth_authorization(
            request=_minimal_request("/api/attribution/platform-oauth/stripe/authorize"),
            platform=Platform.stripe,
            payload=ProviderOAuthAuthorizeRequest(
                platform_account_id="acct_p9_core",
                redirect_uri="https://app.example/callback",
                requested_scopes=["read_write"],
            ),
            x_correlation_id=uuid4(),
            db_session=session,
            auth_context=auth_context,
        )
        assert stripe_authorize.lifecycle_state.value == "authorization_pending"

        stripe_callback = await complete_provider_oauth_callback(
            request=_minimal_request("/api/attribution/platform-oauth/stripe/callback"),
            platform=Platform.stripe,
            state=stripe_authorize.state_reference,
            x_correlation_id=uuid4(),
            db_session=session,
            auth_context=auth_context,
            code="stripe-code-p9-core",
            error=None,
            error_description=None,
        )
        assert stripe_callback.lifecycle_state.value == "connected"

        stripe_status = await get_provider_oauth_status(
            request=_minimal_request("/api/attribution/platform-oauth/stripe/status"),
            platform=Platform.stripe,
            x_correlation_id=uuid4(),
            db_session=session,
            auth_context=auth_context,
            platform_account_id=None,
        )
        assert stripe_status.lifecycle_state.value in {"connected", "expired"}
        status_dump = stripe_status.model_dump()
        assert "access_token" not in status_dump
        assert "refresh_token" not in status_dump

        stripe_row = await _fetch_credential_row(
            session,
            tenant_id=tenant_id,
            platform="stripe",
            platform_account_id="acct_p9_core",
        )
        assert stripe_row["expires_at"] is not None
        assert stripe_row["next_refresh_due_at"] is not None
        assert "stripe-code-p9-core" not in str(stripe_row["encrypted_access_token_b64"])
        assert "stripe-code-p9-core" not in str(stripe_row["encrypted_refresh_token_b64"])

        stripe_refresh_status = await _run_scheduled_refresh_for_credential(
            session,
            tenant_id=tenant_id,
            credential_id=UUID(str(stripe_row["id"])),
        )
        assert stripe_refresh_status == "refreshed"

        resolved_stripe = await resolver.resolve_for_connection(
            session,
            tenant_id=tenant_id,
            connection_id=UUID(str(stripe_row["platform_connection_id"])),
            correlation_id=uuid4(),
        )
        assert resolved_stripe.access_token.startswith("stripe-refresh-access-")

        stripe_disconnect = await disconnect_provider_oauth(
            request=_minimal_request("/api/attribution/platform-oauth/stripe/disconnect"),
            platform=Platform.stripe,
            payload=ProviderOAuthDisconnectRequest(
                reason=ProviderOAuthDisconnectReason.user_initiated,
            ),
            x_correlation_id=uuid4(),
            db_session=session,
            auth_context=auth_context,
        )
        assert stripe_disconnect.lifecycle_state.value == "revoked"
        disconnect_dump = stripe_disconnect.model_dump()
        assert "access_token" not in disconnect_dump
        assert "refresh_token" not in disconnect_dump

        stripe_refresh_state = await get_provider_oauth_refresh_state(
            request=_minimal_request("/api/attribution/platform-oauth/stripe/refresh-state"),
            platform=Platform.stripe,
            x_correlation_id=uuid4(),
            db_session=session,
            auth_context=auth_context,
        )
        assert isinstance(stripe_refresh_state, JSONResponse)
        assert stripe_refresh_state.status_code == 409
        stripe_refresh_payload = json.loads(stripe_refresh_state.body.decode("utf-8"))
        assert stripe_refresh_payload["code"] == "provider_revoked"
        assert "access_token" not in stripe_refresh_state.body.decode("utf-8")
        assert "refresh_token" not in stripe_refresh_state.body.decode("utf-8")

        with pytest.raises(PlatformCredentialNotFoundError):
            await resolver.resolve_for_connection(
                session,
                tenant_id=tenant_id,
                connection_id=UUID(str(stripe_row["platform_connection_id"])),
                correlation_id=uuid4(),
            )

        evidence["stripe_path"] = {
            "authorize_state": stripe_authorize.lifecycle_state.value,
            "callback_state": stripe_callback.lifecycle_state.value,
            "status_state": stripe_status.lifecycle_state.value,
            "refresh_status": stripe_refresh_status,
            "disconnect_state": stripe_disconnect.lifecycle_state.value,
            "refresh_state_error_code": stripe_refresh_payload["code"],
        }

        dummy_authorize = await runtime_service.initiate_authorization(
            session,
            tenant_id=tenant_id,
            user_id=user_id,
            platform="dummy",
            correlation_id=uuid4(),
            platform_account_id="det_acct_p9_core",
            redirect_uri="https://app.example/callback",
            requested_scopes=("read_revenue",),
        )
        assert dummy_authorize.lifecycle_state == "authorization_pending"

        dummy_callback = await runtime_service.complete_callback(
            session,
            tenant_id=tenant_id,
            user_id=user_id,
            platform="dummy",
            correlation_id=uuid4(),
            state_reference=dummy_authorize.state_reference,
            authorization_code="dummy-code-p9-core",
            provider_error_code=None,
        )
        assert dummy_callback.lifecycle_state == "connected"

        dummy_status = await runtime_service.get_status(
            session,
            tenant_id=tenant_id,
            user_id=user_id,
            platform="dummy",
            platform_account_id=None,
        )
        assert dummy_status.lifecycle_state in {"connected", "expired"}

        dummy_row = await _fetch_credential_row(
            session,
            tenant_id=tenant_id,
            platform="dummy",
            platform_account_id="det_acct_p9_core",
        )
        assert dummy_row["expires_at"] is not None
        assert dummy_row["next_refresh_due_at"] is not None
        assert "dummy-code-p9-core" not in str(dummy_row["encrypted_access_token_b64"])
        assert "dummy-code-p9-core" not in str(dummy_row["encrypted_refresh_token_b64"])

        dummy_refresh_status = await _run_scheduled_refresh_for_credential(
            session,
            tenant_id=tenant_id,
            credential_id=UUID(str(dummy_row["id"])),
        )
        assert dummy_refresh_status == "refreshed"

        resolved_dummy = await resolver.resolve_for_connection(
            session,
            tenant_id=tenant_id,
            connection_id=UUID(str(dummy_row["platform_connection_id"])),
            correlation_id=uuid4(),
        )
        assert resolved_dummy.access_token.startswith("det-refresh-access-")

        await PlatformCredentialStore.mark_refresh_success(
            session,
            tenant_id=tenant_id,
            credential_id=UUID(str(dummy_row["id"])),
            access_token="dummy-terminal-prep-access",
            refresh_token="dummy-invalid_client-terminal",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=4),
            scope="read_revenue",
            token_type="Bearer",
            key_id="test-key",
            encryption_key="test-platform-key",
        )
        await _mark_refresh_due_now(
            session,
            tenant_id=tenant_id,
            credential_id=UUID(str(dummy_row["id"])),
        )
        terminal_result = await refresh_credential_once(
            session,
            tenant_id=tenant_id,
            credential_id=UUID(str(dummy_row["id"])),
            correlation_id=uuid4(),
            force=True,
        )
        assert terminal_result.status == "revoked_terminal"
        assert terminal_result.failure_class == "provider_invalid_client"
        assert "access_token" not in terminal_result.to_public_dict()
        assert "refresh_token" not in terminal_result.to_public_dict()

        with pytest.raises(ProviderLifecycleProblem) as dummy_revoked:
            await runtime_service.get_refresh_state(
                session,
                tenant_id=tenant_id,
                user_id=user_id,
                platform="dummy",
            )
        assert dummy_revoked.value.code == "provider_revoked"
        assert "dummy-invalid_client-terminal" not in dummy_revoked.value.detail

        evidence["dummy_path"] = {
            "authorize_state": dummy_authorize.lifecycle_state,
            "callback_state": dummy_callback.lifecycle_state,
            "status_state": dummy_status.lifecycle_state,
            "refresh_status": dummy_refresh_status,
            "terminal_failure_class": terminal_result.failure_class,
            "terminal_status": terminal_result.status,
            "graceful_degraded_code": dummy_revoked.value.code,
        }

    logged_text = "\n".join(record.getMessage() for record in caplog.records)
    assert "stripe-code-p9-core" not in logged_text
    assert "dummy-invalid_client-terminal" not in logged_text
    assert "det-refresh-access" not in logged_text

    _write_artifact("p9_composed_runtime_report.json", evidence)


@pytest.mark.asyncio
async def test_b13_p9_cross_tenant_and_tenantless_worker_fail_before_side_effects(
    _isolated_database_urls: tuple[str, str],
    _async_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sync_url, _ = _isolated_database_urls
    tenant_a = uuid4()
    tenant_b = uuid4()
    user_a = uuid4()
    user_b = uuid4()
    _seed_tenant(sync_url, tenant_a, "p9-tenant-a")
    _seed_tenant(sync_url, tenant_b, "p9-tenant-b")
    _seed_user(sync_url, user_a, "p9-user-a")
    _seed_user(sync_url, user_b, "p9-user-b")
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
                platform_account_id="acct_p9_isolation",
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
            code="stripe-code-p9-isolation",
            error=None,
            error_description=None,
        )
        assert callback.lifecycle_state.value == "connected"
        row_before = await _fetch_credential_row(
            session_a,
            tenant_id=tenant_a,
            platform="stripe",
            platform_account_id="acct_p9_isolation",
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
            platform_account_id="acct_p9_isolation",
        )
        assert row_after_cross_tenant["lifecycle_status"] == "active"
        assert row_after_cross_tenant["last_refresh_at"] is None
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
            platform_account_id="acct_p9_isolation",
        )
        assert row_after_tenantless["last_refresh_at"] is None
        assert int(row_after_tenantless["refresh_failure_count"]) == 0

    # Bind worker refresh session factory to the isolated proof database.
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
    assert positive_payload["failure_class"] is None

    async with _tenant_session(_async_session_factory, tenant_id=tenant_a, user_id=user_a) as session_a_check:
        row_after_worker_positive = await _fetch_credential_row(
            session_a_check,
            tenant_id=tenant_a,
            platform="stripe",
            platform_account_id="acct_p9_isolation",
        )
        assert row_after_worker_positive["last_refresh_at"] is not None
        assert row_after_worker_positive["lifecycle_status"] == "active"

    evidence.update(
        {
            "cross_tenant_status_code": cross_status_payload["status"],
            "cross_tenant_disconnect_code": cross_disconnect_payload["status"],
            "tenantless_worker_error": "authority_envelope header is required",
            "worker_positive_status": positive_payload["status"],
            "worker_positive_failure_class": positive_payload["failure_class"],
        }
    )
    _write_artifact("p9_negative_controls_report.json", evidence)
