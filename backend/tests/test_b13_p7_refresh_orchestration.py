from __future__ import annotations

import asyncio
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
from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.services.platform_credentials import PlatformCredentialStore
from app.services.provider_oauth_lifecycle import OAuthTokenSet
from app.services.provider_token_refresh import refresh_credential_once
from app.services.provider_valid_token_resolution import ProviderValidTokenResolver


REPO_ROOT = Path(__file__).resolve().parents[2]
GATE_SCRIPT = REPO_ROOT / "scripts" / "ci" / "enforce_b13_p7_refresh_orchestration.py"

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
                    "name": f"p7-tenant-{tenant_id.hex[:8]}",
                    "api_key_hash": f"p7-api-key-{tenant_id.hex[:8]}",
                    "notification_email": f"tenant-{tenant_id.hex[:8]}@example.test",
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
    isolated_db_name = f"skeldir_b13_p7_{uuid4().hex[:12]}"
    isolated_sync_url = str(parsed.set(database=isolated_db_name))
    isolated_async_url = _to_async_url(isolated_sync_url)

    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.begin() as conn:
            conn.execute(text(f'CREATE DATABASE "{isolated_db_name}" OWNER "{parsed.username or "postgres"}"'))
    except Exception as exc:
        pytest.skip(f"unable to create isolated database for B1.3-P7 runtime proofs: {exc}")
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
    account_id: str,
) -> UUID:
    connection_id = uuid4()
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
            "id": str(connection_id),
            "tenant_id": str(tenant_id),
            "platform": platform,
            "platform_account_id": account_id,
        },
    )
    return connection_id


def test_b13_p7_gate_passes_repo_state() -> None:
    result = _run([sys.executable, str(GATE_SCRIPT)])
    assert result.returncode == 0, result.stdout + "\n" + result.stderr


def test_b13_p7_negative_control_detects_missing_required_context(tmp_path: Path) -> None:
    checks_contract = REPO_ROOT / "contracts-internal/governance/b03_phase2_required_status_checks.main.json"
    payload = json.loads(checks_contract.read_text(encoding="utf-8"))
    payload["required_contexts"] = [
        value
        for value in payload.get("required_contexts", [])
        if value != "B1.3 P7 Refresh Orchestration Proofs"
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


def test_b13_p7_negative_control_detects_missing_single_flight_lock(tmp_path: Path) -> None:
    refresh_service = REPO_ROOT / "backend/app/services/provider_token_refresh.py"
    mutated = refresh_service.read_text(encoding="utf-8").replace(
        "pg_try_advisory_xact_lock",
        "pg_advisory_lock",
        1,
    )
    mutated_path = tmp_path / "provider_token_refresh.py"
    mutated_path.write_text(mutated, encoding="utf-8")

    result = _run(
        [
            sys.executable,
            str(GATE_SCRIPT),
            "--refresh-service-file",
            str(mutated_path),
        ]
    )
    assert result.returncode != 0
    assert "pg_try_advisory_xact_lock" in f"{result.stdout}\n{result.stderr}"


@pytest.mark.asyncio
async def test_b13_p7_valid_token_resolver_enqueues_due_refresh_without_leaking_payload(
    _isolated_database_urls: tuple[str, str],
    _async_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sync_url, _ = _isolated_database_urls
    tenant_id = uuid4()
    _seed_tenant(sync_url, tenant_id)

    captured: dict[str, object] = {}

    def _capture_enqueue(task_name: str, *, envelope, kwargs=None, queue=None, correlation_id=None):  # noqa: ANN001
        captured["task_name"] = task_name
        captured["kwargs"] = dict(kwargs or {})
        captured["correlation_id"] = correlation_id
        captured["envelope"] = envelope.model_dump(mode="json")
        captured["queue"] = queue
        return {"queued": True}

    monkeypatch.setattr(
        "app.services.provider_valid_token_resolution.enqueue_tenant_task_by_name",
        _capture_enqueue,
    )

    async with _tenant_session(_async_session_factory, tenant_id=tenant_id) as session:
        connection_id = await _create_connection(
            session,
            tenant_id=tenant_id,
            platform="stripe",
            account_id="acct_p7_resolver",
        )
        stored = await PlatformCredentialStore.upsert_tokens(
            session,
            tenant_id=tenant_id,
            platform="stripe",
            platform_account_id="acct_p7_resolver",
            access_token="resolver-access-token",
            refresh_token="resolver-refresh-token",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
            scope="read_write",
            token_type="Bearer",
            key_id="test-key",
            encryption_key="test-platform-key",
        )
        resolver = ProviderValidTokenResolver()
        resolved = await resolver.resolve_for_connection(
            session,
            tenant_id=tenant_id,
            connection_id=connection_id,
            correlation_id=uuid4(),
        )

    assert resolved.access_token == "resolver-access-token"
    assert resolved.refresh_enqueued is True
    assert captured["task_name"] == "app.tasks.maintenance.refresh_provider_oauth_credential"
    assert set(captured["kwargs"].keys()) == {"credential_id", "correlation_id", "refresh_claimed"}
    assert str(stored["id"]) == captured["kwargs"]["credential_id"]
    assert captured["kwargs"]["refresh_claimed"] is True
    assert "access_token" not in captured["kwargs"]
    assert "refresh_token" not in captured["kwargs"]


@pytest.mark.asyncio
async def test_b13_p7_refresh_success_updates_canonical_lifecycle_state(
    _isolated_database_urls: tuple[str, str],
    _async_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    sync_url, _ = _isolated_database_urls
    tenant_id = uuid4()
    _seed_tenant(sync_url, tenant_id)
    now = datetime.now(timezone.utc)

    async with _tenant_session(_async_session_factory, tenant_id=tenant_id) as session:
        await _create_connection(
            session,
            tenant_id=tenant_id,
            platform="stripe",
            account_id="acct_p7_success",
        )
        created = await PlatformCredentialStore.upsert_tokens(
            session,
            tenant_id=tenant_id,
            platform="stripe",
            platform_account_id="acct_p7_success",
            access_token="seed-access",
            refresh_token="stripe-refresh-success",
            expires_at=now + timedelta(hours=24),
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
        assert result.status == "refreshed"
        assert result.failure_class is None
        public_payload = result.to_public_dict()
        assert "access_token" not in public_payload
        assert "refresh_token" not in public_payload

        row = (
            await session.execute(
                text(
                    """
                    SELECT lifecycle_status, refresh_failure_count, last_failure_class,
                           last_refresh_at, next_refresh_due_at
                    FROM public.platform_credentials
                    WHERE tenant_id = :tenant_id
                      AND id = :credential_id
                    """
                ),
                {"tenant_id": str(tenant_id), "credential_id": str(credential_id)},
            )
        ).mappings().one()

    assert row["lifecycle_status"] == "active"
    assert int(row["refresh_failure_count"]) == 0
    assert row["last_failure_class"] is None
    assert row["last_refresh_at"] is not None
    assert row["next_refresh_due_at"] is not None
    assert row["next_refresh_due_at"] > now + timedelta(hours=12)


@pytest.mark.asyncio
async def test_b13_p7_terminal_invalid_grant_revokes_credential(
    _isolated_database_urls: tuple[str, str],
    _async_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    sync_url, _ = _isolated_database_urls
    tenant_id = uuid4()
    _seed_tenant(sync_url, tenant_id)

    async with _tenant_session(_async_session_factory, tenant_id=tenant_id) as session:
        await _create_connection(
            session,
            tenant_id=tenant_id,
            platform="stripe",
            account_id="acct_p7_terminal",
        )
        created = await PlatformCredentialStore.upsert_tokens(
            session,
            tenant_id=tenant_id,
            platform="stripe",
            platform_account_id="acct_p7_terminal",
            access_token="seed-access",
            refresh_token="stripe-invalid_grant-terminal",
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
        assert result.failure_class == "provider_invalid_grant"

        row = (
            await session.execute(
                text(
                    """
                    SELECT lifecycle_status, next_refresh_due_at, revoked_at, last_failure_class
                    FROM public.platform_credentials
                    WHERE tenant_id = :tenant_id
                      AND id = :credential_id
                    """
                ),
                {"tenant_id": str(tenant_id), "credential_id": str(credential_id)},
            )
        ).mappings().one()

    assert row["lifecycle_status"] == "revoked"
    assert row["next_refresh_due_at"] is None
    assert row["revoked_at"] is not None
    assert row["last_failure_class"] == "provider_invalid_grant"


@pytest.mark.asyncio
async def test_b13_p7_single_flight_refresh_allows_one_provider_call(
    _isolated_database_urls: tuple[str, str],
    _async_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    sync_url, _ = _isolated_database_urls
    tenant_id = uuid4()
    _seed_tenant(sync_url, tenant_id)
    refresh_counter = {"count": 0}

    class _SlowDispatcher:
        async def refresh_token(self, *, platform: str, request):  # noqa: ANN001
            _ = platform
            _ = request
            refresh_counter["count"] += 1
            await asyncio.sleep(0.25)
            return OAuthTokenSet(
                access_token="single-flight-access",
                refresh_token="single-flight-refresh",
                expires_at=datetime.now(timezone.utc) + timedelta(days=3),
                scope="read_write",
                token_type="Bearer",
                provider_account_id="acct_single_flight",
            )

    async with _tenant_session(_async_session_factory, tenant_id=tenant_id) as session:
        await _create_connection(
            session,
            tenant_id=tenant_id,
            platform="stripe",
            account_id="acct_single_flight",
        )
        created = await PlatformCredentialStore.upsert_tokens(
            session,
            tenant_id=tenant_id,
            platform="stripe",
            platform_account_id="acct_single_flight",
            access_token="seed-access",
            refresh_token="stripe-refresh-single-flight",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
            scope="read_write",
            token_type="Bearer",
            key_id="test-key",
            encryption_key="test-platform-key",
        )
        credential_id = created["id"]

    async def _run_once() -> str:
        async with _tenant_session(_async_session_factory, tenant_id=tenant_id) as session:
            outcome = await refresh_credential_once(
                session,
                tenant_id=tenant_id,
                credential_id=credential_id,
                correlation_id=uuid4(),
                dispatcher=_SlowDispatcher(),
            )
            return outcome.status

    statuses = await asyncio.gather(_run_once(), _run_once())
    assert refresh_counter["count"] == 1
    assert "refreshed" in statuses
    assert any(status in {"skipped_locked", "skipped_not_due"} for status in statuses)
