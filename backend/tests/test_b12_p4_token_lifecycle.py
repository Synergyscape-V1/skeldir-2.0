from __future__ import annotations

import asyncio
import hashlib
import importlib
import os
import sys
from pathlib import Path
from uuid import UUID, uuid4

import bcrypt
import jwt
import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url

from app.testing.jwt_rs256 import TEST_PUBLIC_KEY_PEM, private_ring_payload, public_ring_payload


pytestmark = pytest.mark.asyncio


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _normalize_sync_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url


def _hash_login_identifier(email: str) -> str:
    canonical = email.strip().lower()
    pepper = os.environ.get("AUTH_LOGIN_IDENTIFIER_PEPPER", "").strip()
    return hashlib.sha256(f"{pepper}:{canonical}".encode("utf-8")).hexdigest()


def _current_sync_database_url() -> str:
    env_key = "DATABASE" + "_URL"
    value = os.environ.get(env_key)
    if not value:
        raise RuntimeError("DATABASE_URL is required for P4 token lifecycle tests")
    return _normalize_sync_url(value)


@pytest.fixture(scope="session", autouse=True)
def _auth_env_defaults() -> None:
    os.environ["TESTING"] = "1"
    os.environ["AUTH_JWT_SECRET"] = private_ring_payload()
    os.environ["AUTH_JWT_PUBLIC_KEY_RING"] = public_ring_payload()
    os.environ["AUTH_JWT_ALGORITHM"] = "RS256"
    os.environ["AUTH_JWT_ISSUER"] = "https://issuer.skeldir.test"
    os.environ["AUTH_JWT_AUDIENCE"] = "skeldir-api"
    os.environ["AUTH_LOGIN_IDENTIFIER_PEPPER"] = "b12-p4-test-pepper"
    os.environ["CONTRACT_TESTING"] = "0"


@pytest.fixture(scope="session")
def _isolated_migrated_db_url() -> str:
    base_url = _normalize_sync_url(
        os.environ.get("MIGRATION_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
        or "postgresql://postgres:postgres@127.0.0.1:5432/postgres"
    )
    # CI already provisions a clean Postgres service and runs `alembic upgrade head`
    # before this test module. Reusing that database avoids admin-auth drift across
    # upstream suites and keeps this module bounded and deterministic in pipeline jobs.
    if os.environ.get("CI", "").lower() == "true" or os.environ.get("GITHUB_ACTIONS") == "true":
        os.environ["DATABASE_URL"] = base_url
        os.environ["MIGRATION_DATABASE_URL"] = base_url
        cfg = Config(str(_repo_root() / "alembic.ini"))
        try:
            command.upgrade(cfg, "head")
        except Exception as exc:
            pytest.fail(f"P4 shared CI DB migration failed: {type(exc).__name__}: {exc}")
        yield base_url
        return

    parsed = make_url(base_url)
    admin_url = str(parsed.set(database="postgres"))
    db_owner = parsed.username or "postgres"
    isolated_db_name = f"skeldir_b12_p4_{uuid4().hex[:12]}"
    isolated_url = str(parsed.set(database=isolated_db_name))

    chosen_admin_url: str | None = None
    last_error: Exception | None = None
    admin_candidates = [admin_url, "postgresql://postgres:postgres@127.0.0.1:5432/postgres"]
    for candidate in admin_candidates:
        admin_engine = create_engine(candidate, isolation_level="AUTOCOMMIT")
        try:
            with admin_engine.begin() as conn:
                conn.execute(text(f'CREATE DATABASE "{isolated_db_name}" OWNER "{db_owner}"'))
            chosen_admin_url = candidate
            break
        except Exception as exc:  # pragma: no cover - environment dependent
            last_error = exc
        finally:
            admin_engine.dispose()
    if chosen_admin_url is None:
        pytest.skip(
            "Unable to create isolated database for P4 tests; "
            f"last error: {type(last_error).__name__}: {last_error}"
        )

    admin_db_url = str(make_url(chosen_admin_url).set(database=isolated_db_name))
    os.environ["DATABASE_URL"] = admin_db_url
    os.environ["MIGRATION_DATABASE_URL"] = admin_db_url

    cfg = Config(str(_repo_root() / "alembic.ini"))
    try:
        command.upgrade(cfg, "head")
    except Exception as exc:
        pytest.fail(f"P4 test DB migration failed: {type(exc).__name__}: {exc}")

    try:
        yield isolated_url
    finally:
        cleanup_engine = create_engine(chosen_admin_url, isolation_level="AUTOCOMMIT")
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


@pytest.fixture(scope="session")
def _app(_isolated_migrated_db_url):
    # Ensure fresh app import after DATABASE_URL/MIGRATION_DATABASE_URL are set.
    for name in list(sys.modules.keys()):
        if name == "app" or name.startswith("app."):
            sys.modules.pop(name, None)

    import app.main as main_module  # noqa: WPS433

    importlib.reload(main_module)
    return main_module.app


def _seed_login_identity(*, tenant_id: UUID, user_id: UUID, email: str, password: str) -> None:
    engine = create_engine(_current_sync_database_url())
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO public.tenants (id, name, api_key_hash, notification_email, created_at, updated_at)
                VALUES (:tenant_id, :name, :api_key_hash, :notification_email, now(), now())
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "name": f"tenant-{str(tenant_id)[:8]}",
                "api_key_hash": f"api-key-{tenant_id}",
                "notification_email": f"redacted-{tenant_id}",
            },
        )
        conn.execute(
            text(
                """
                INSERT INTO public.users (
                    id, login_identifier_hash, external_subject_hash, auth_provider, is_active, password_hash, created_at, updated_at
                )
                VALUES (
                    :user_id, :login_identifier_hash, :external_subject_hash, 'password', true, :password_hash, now(), now()
                )
                ON CONFLICT (id) DO UPDATE SET
                    login_identifier_hash = EXCLUDED.login_identifier_hash,
                    external_subject_hash = EXCLUDED.external_subject_hash,
                    auth_provider = EXCLUDED.auth_provider,
                    is_active = EXCLUDED.is_active,
                    password_hash = EXCLUDED.password_hash,
                    updated_at = now()
                """
            ),
            {
                "user_id": str(user_id),
                "login_identifier_hash": _hash_login_identifier(email),
                "external_subject_hash": f"subject-{user_id}",
                "password_hash": password_hash,
            },
        )
        conn.execute(
            text(
                """
                INSERT INTO public.tenant_memberships (id, tenant_id, user_id, membership_status, created_at, updated_at)
                VALUES (:membership_id, :tenant_id, :user_id, 'active', now(), now())
                ON CONFLICT (tenant_id, user_id) DO UPDATE SET membership_status = 'active', updated_at = now()
                """
            ),
            {
                "membership_id": str(uuid4()),
                "tenant_id": str(tenant_id),
                "user_id": str(user_id),
            },
        )
        membership_id = conn.execute(
            text(
                """
                SELECT id
                FROM public.tenant_memberships
                WHERE tenant_id = :tenant_id
                  AND user_id = :user_id
                LIMIT 1
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "user_id": str(user_id),
            },
        ).scalar_one()
        conn.execute(
            text(
                """
                INSERT INTO public.tenant_membership_roles (
                    id,
                    tenant_id,
                    membership_id,
                    role_code,
                    created_at,
                    updated_at
                )
                VALUES (:id, :tenant_id, :membership_id, 'viewer', now(), now())
                ON CONFLICT (membership_id, role_code) DO NOTHING
                """
            ),
            {
                "id": str(uuid4()),
                "tenant_id": str(tenant_id),
                "membership_id": str(membership_id),
            },
        )


async def _login(*, app_instance, tenant_id: UUID, email: str, password: str) -> dict:
    transport = ASGITransport(app=app_instance)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/auth/login",
            json={"email": email, "password": password, "tenant_id": str(tenant_id)},
            headers={"X-Correlation-ID": str(uuid4())},
        )
    assert response.status_code == 200, response.text
    return response.json()


async def _refresh(
    *,
    app_instance,
    refresh_token: str,
    tenant_id: UUID | None,
    correlation_id: UUID | None = None,
) -> tuple[int, dict]:
    transport = ASGITransport(app=app_instance)
    headers = {
        "X-Correlation-ID": str(correlation_id or uuid4()),
        "Authorization": f"Bearer {refresh_token}",
    }
    payload: dict[str, str] = {"refresh_token": refresh_token}
    if tenant_id is not None:
        payload["tenant_id"] = str(tenant_id)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/auth/refresh", json=payload, headers=headers)
    return response.status_code, response.json() if response.content else {}


def _decode_access(access_token: str) -> dict:
    return jwt.decode(
        access_token,
        TEST_PUBLIC_KEY_PEM,
        algorithms=["RS256"],
        issuer=os.environ["AUTH_JWT_ISSUER"],
        audience=os.environ["AUTH_JWT_AUDIENCE"],
    )


def _parse_refresh_token(refresh_token: str) -> tuple[UUID, UUID, str]:
    parts = refresh_token.split(".")
    assert len(parts) == 3
    return UUID(parts[0]), UUID(parts[1]), parts[2]


async def test_login_issues_tenant_scoped_access_and_opaque_refresh(_app):
    tenant_id = uuid4()
    user_id = uuid4()
    email = f"user-{uuid4().hex[:8]}@example.com"
    password = "S3curePassword!123"
    _seed_login_identity(tenant_id=tenant_id, user_id=user_id, email=email, password=password)

    payload = await _login(app_instance=_app, tenant_id=tenant_id, email=email, password=password)
    claims = _decode_access(payload["access_token"])
    token_tenant_id, _, _ = _parse_refresh_token(payload["refresh_token"])

    assert claims["tenant_id"] == str(tenant_id)
    assert claims["sub"] == str(user_id)
    assert claims["user_id"] == str(user_id)
    assert 895 <= int(claims["exp"]) - int(claims["iat"]) <= 905
    assert payload["expires_in"] == 900
    assert token_tenant_id == tenant_id
    assert not payload["refresh_token"].startswith("eyJ")


async def test_login_requires_tenant_id_for_token_issuance(_app):
    tenant_id = uuid4()
    user_id = uuid4()
    email = f"user-{uuid4().hex[:8]}@example.com"
    password = "S3curePassword!123"
    _seed_login_identity(tenant_id=tenant_id, user_id=user_id, email=email, password=password)

    transport = ASGITransport(app=_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/auth/login",
            json={"email": email, "password": password},
            headers={"X-Correlation-ID": str(uuid4())},
        )

    assert response.status_code == 422, response.text


async def test_refresh_rotation_single_use(_app):
    tenant_id = uuid4()
    user_id = uuid4()
    email = f"user-{uuid4().hex[:8]}@example.com"
    password = "S3curePassword!123"
    _seed_login_identity(tenant_id=tenant_id, user_id=user_id, email=email, password=password)

    login = await _login(app_instance=_app, tenant_id=tenant_id, email=email, password=password)
    refresh_a = login["refresh_token"]

    engine = create_engine(_current_sync_database_url())
    with engine.begin() as conn:
        before_rows = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.auth_refresh_tokens
                WHERE tenant_id = :tenant_id
                  AND user_id = :user_id
                """
            ),
            {"tenant_id": str(tenant_id), "user_id": str(user_id)},
        ).scalar_one()

    first_status, first_payload = await _refresh(
        app_instance=_app,
        refresh_token=refresh_a,
        tenant_id=tenant_id,
    )
    assert first_status == 200
    refresh_b = first_payload["refresh_token"]
    assert refresh_b != refresh_a

    reuse_status, _ = await _refresh(
        app_instance=_app,
        refresh_token=refresh_a,
        tenant_id=tenant_id,
    )
    assert reuse_status == 401

    with engine.begin() as conn:
        after_rows = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.auth_refresh_tokens
                WHERE tenant_id = :tenant_id
                  AND user_id = :user_id
                """
            ),
            {"tenant_id": str(tenant_id), "user_id": str(user_id)},
        ).scalar_one()

        # Login mints 1, first refresh mints +1, failed reuse mints +0.
    assert int(after_rows) == int(before_rows) + 1


async def test_refresh_rejects_tenant_context_mismatch(_app):
    tenant_a = uuid4()
    tenant_b = uuid4()
    user_id = uuid4()
    email = f"user-{uuid4().hex[:8]}@example.com"
    password = "S3curePassword!123"
    _seed_login_identity(tenant_id=tenant_a, user_id=user_id, email=email, password=password)
    _seed_login_identity(tenant_id=tenant_b, user_id=user_id, email=email, password=password)

    login = await _login(app_instance=_app, tenant_id=tenant_a, email=email, password=password)
    refresh_token = login["refresh_token"]
    _, token_row_id, _ = _parse_refresh_token(refresh_token)

    engine = create_engine(_current_sync_database_url())
    with engine.begin() as conn:
        before_rows = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.auth_refresh_tokens
                WHERE user_id = :user_id
                """
            ),
            {"user_id": str(user_id)},
        ).scalar_one()

    mismatch_status, _ = await _refresh(
        app_instance=_app,
        refresh_token=refresh_token,
        tenant_id=tenant_b,
    )
    assert mismatch_status == 401

    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT rotated_at, replaced_by_id
                FROM public.auth_refresh_tokens
                WHERE id = :id
                """
            ),
            {"id": str(token_row_id)},
        ).mappings().one()
        after_rows = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.auth_refresh_tokens
                WHERE user_id = :user_id
                """
            ),
            {"user_id": str(user_id)},
        ).scalar_one()

    assert row["rotated_at"] is None
    assert row["replaced_by_id"] is None
    assert int(after_rows) == int(before_rows)


async def test_refresh_token_not_plaintext_at_rest(_app):
    tenant_id = uuid4()
    user_id = uuid4()
    email = f"user-{uuid4().hex[:8]}@example.com"
    password = "S3curePassword!123"
    _seed_login_identity(tenant_id=tenant_id, user_id=user_id, email=email, password=password)

    login = await _login(app_instance=_app, tenant_id=tenant_id, email=email, password=password)
    refresh_token = login["refresh_token"]
    _, refresh_row_id, secret_part = _parse_refresh_token(refresh_token)

    engine = create_engine(_current_sync_database_url())
    with engine.begin() as conn:
        token_hash = conn.execute(
            text("SELECT token_hash FROM public.auth_refresh_tokens WHERE id = :id"),
            {"id": str(refresh_row_id)},
        ).scalar_one()

    assert isinstance(token_hash, str)
    assert token_hash != refresh_token
    assert secret_part not in token_hash
    assert token_hash.startswith("$2")


async def test_refresh_hashes_secret_component_only(_app):
    tenant_id = uuid4()
    user_id = uuid4()
    email = f"user-{uuid4().hex[:8]}@example.com"
    password = "S3curePassword!123"
    _seed_login_identity(tenant_id=tenant_id, user_id=user_id, email=email, password=password)

    login = await _login(app_instance=_app, tenant_id=tenant_id, email=email, password=password)
    refresh_token = login["refresh_token"]
    _, refresh_row_id, secret_part = _parse_refresh_token(refresh_token)

    secret_digest = hashlib.sha256(secret_part.encode("utf-8")).hexdigest().encode("utf-8")
    blob_digest = hashlib.sha256(refresh_token.encode("utf-8")).hexdigest().encode("utf-8")

    engine = create_engine(_current_sync_database_url())
    with engine.begin() as conn:
        token_hash = conn.execute(
            text("SELECT token_hash FROM public.auth_refresh_tokens WHERE id = :id"),
            {"id": str(refresh_row_id)},
        ).scalar_one()

    assert bcrypt.checkpw(secret_digest, token_hash.encode("utf-8"))
    assert not bcrypt.checkpw(blob_digest, token_hash.encode("utf-8"))


async def test_refresh_reuse_revokes_family_and_kills_successor(_app):
    tenant_id = uuid4()
    user_id = uuid4()
    email = f"user-{uuid4().hex[:8]}@example.com"
    password = "S3curePassword!123"
    _seed_login_identity(tenant_id=tenant_id, user_id=user_id, email=email, password=password)

    login = await _login(app_instance=_app, tenant_id=tenant_id, email=email, password=password)
    refresh_a = login["refresh_token"]
    _, token_a_id, _ = _parse_refresh_token(refresh_a)

    attacker_status, attacker_payload = await _refresh(
        app_instance=_app,
        refresh_token=refresh_a,
        tenant_id=tenant_id,
    )
    assert attacker_status == 200
    refresh_b = attacker_payload["refresh_token"]
    _, token_b_id, _ = _parse_refresh_token(refresh_b)

    legitimate_reuse_status, _ = await _refresh(
        app_instance=_app,
        refresh_token=refresh_a,
        tenant_id=tenant_id,
    )
    assert legitimate_reuse_status == 401

    successor_attempt_status, _ = await _refresh(
        app_instance=_app,
        refresh_token=refresh_b,
        tenant_id=tenant_id,
    )
    assert successor_attempt_status == 401

    engine = create_engine(_current_sync_database_url())
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, family_id, revoked_at, rotated_at, replaced_by_id
                FROM public.auth_refresh_tokens
                WHERE id IN (:a_id, :b_id)
                ORDER BY created_at
                """
            ),
            {"a_id": str(token_a_id), "b_id": str(token_b_id)},
        ).mappings().all()
        family_id = rows[0]["family_id"]
        active_count = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.auth_refresh_tokens
                WHERE family_id = :family_id
                  AND revoked_at IS NULL
                  AND expires_at > now()
                """
            ),
            {"family_id": str(family_id)},
        ).scalar_one()

    assert len(rows) == 2
    assert rows[0]["rotated_at"] is not None
    assert rows[0]["replaced_by_id"] == token_b_id
    assert rows[0]["revoked_at"] is not None
    assert rows[1]["revoked_at"] is not None
    assert int(active_count) == 0


async def test_refresh_token_id_miss_executes_dummy_bcrypt_check(_app, monkeypatch: pytest.MonkeyPatch):
    import app.services.auth_tokens as auth_tokens_module

    tenant_id = uuid4()
    real_checkpw = bcrypt.checkpw
    calls = {"count": 0}

    def _counting_checkpw(password: bytes, hashed_password: bytes) -> bool:
        calls["count"] += 1
        return real_checkpw(password, hashed_password)

    monkeypatch.setattr(auth_tokens_module.bcrypt, "checkpw", _counting_checkpw)

    miss_token = f"{tenant_id}.{uuid4()}.selector-miss-secret"
    transport = ASGITransport(app=_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/auth/refresh",
            json={"refresh_token": miss_token, "tenant_id": str(tenant_id)},
            headers={
                "X-Correlation-ID": str(uuid4()),
                "Authorization": f"Bearer {miss_token}",
            },
        )

    assert response.status_code == 401, response.text
    assert calls["count"] == 1


async def test_refresh_reuse_revokes_only_token_family_parallel_family_survives(_app):
    tenant_id = uuid4()
    user_id = uuid4()
    email = f"user-{uuid4().hex[:8]}@example.com"
    password = "S3curePassword!123"
    _seed_login_identity(tenant_id=tenant_id, user_id=user_id, email=email, password=password)

    login_a = await _login(app_instance=_app, tenant_id=tenant_id, email=email, password=password)
    refresh_a1 = login_a["refresh_token"]
    _, a1_id, _ = _parse_refresh_token(refresh_a1)

    attacker_status, attacker_payload = await _refresh(
        app_instance=_app,
        refresh_token=refresh_a1,
        tenant_id=tenant_id,
    )
    assert attacker_status == 200
    refresh_a2 = attacker_payload["refresh_token"]
    _, a2_id, _ = _parse_refresh_token(refresh_a2)

    login_b = await _login(app_instance=_app, tenant_id=tenant_id, email=email, password=password)
    refresh_b1 = login_b["refresh_token"]
    _, b1_id, _ = _parse_refresh_token(refresh_b1)

    legitimate_reuse_status, _ = await _refresh(
        app_instance=_app,
        refresh_token=refresh_a1,
        tenant_id=tenant_id,
    )
    assert legitimate_reuse_status == 401

    attacker_successor_status, _ = await _refresh(
        app_instance=_app,
        refresh_token=refresh_a2,
        tenant_id=tenant_id,
    )
    assert attacker_successor_status == 401

    parallel_family_status, _ = await _refresh(
        app_instance=_app,
        refresh_token=refresh_b1,
        tenant_id=tenant_id,
    )
    assert parallel_family_status == 200

    engine = create_engine(_current_sync_database_url())
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, family_id, revoked_at
                FROM public.auth_refresh_tokens
                WHERE id IN (:a1_id, :a2_id, :b1_id)
                """
            ),
            {"a1_id": str(a1_id), "a2_id": str(a2_id), "b1_id": str(b1_id)},
        ).mappings().all()

    by_id = {UUID(str(row["id"])): row for row in rows}
    assert by_id[a1_id]["family_id"] == by_id[a2_id]["family_id"]
    assert by_id[a1_id]["family_id"] != by_id[b1_id]["family_id"]
    assert by_id[a1_id]["revoked_at"] is not None
    assert by_id[a2_id]["revoked_at"] is not None
    assert by_id[b1_id]["revoked_at"] is None


async def test_refresh_rotation_is_race_safe(_app):
    tenant_id = uuid4()
    user_id = uuid4()
    email = f"user-{uuid4().hex[:8]}@example.com"
    password = "S3curePassword!123"
    _seed_login_identity(tenant_id=tenant_id, user_id=user_id, email=email, password=password)

    login = await _login(app_instance=_app, tenant_id=tenant_id, email=email, password=password)
    refresh_token = login["refresh_token"]
    _, refresh_row_id, _ = _parse_refresh_token(refresh_token)

    async def _refresh_once() -> int:
        status_code, _ = await _refresh(
            app_instance=_app,
            refresh_token=refresh_token,
            tenant_id=tenant_id,
        )
        return status_code

    results = await asyncio.gather(_refresh_once(), _refresh_once())

    assert results.count(200) == 1
    assert results.count(401) == 1

    engine = create_engine(_current_sync_database_url())
    with engine.begin() as conn:
        old_row = conn.execute(
            text(
                """
                SELECT family_id, rotated_at, replaced_by_id
                FROM public.auth_refresh_tokens
                WHERE id = :id
                """
            ),
            {"id": str(refresh_row_id)},
        ).mappings().one()
        active_count = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.auth_refresh_tokens
                WHERE family_id = :family_id
                  AND rotated_at IS NULL
                  AND revoked_at IS NULL
                  AND expires_at > now()
                """
            ),
            {"family_id": str(old_row["family_id"])},
        ).scalar_one()

    assert old_row["rotated_at"] is not None
    assert old_row["replaced_by_id"] is not None
    # Under replay-detection hardening, the losing concurrent request may trigger
    # family revocation; the invariant is bounded minting (never >1 active successor).
    assert int(active_count) in (0, 1)


async def test_signing_hot_path_avoids_per_request_secret_fetch(_app, monkeypatch: pytest.MonkeyPatch):
    tenant_id = uuid4()
    user_id = uuid4()
    email = f"user-{uuid4().hex[:8]}@example.com"
    password = "S3curePassword!123"
    _seed_login_identity(tenant_id=tenant_id, user_id=user_id, email=email, password=password)

    await _login(app_instance=_app, tenant_id=tenant_id, email=email, password=password)

    from app.core import secrets as secrets_module

    calls = {"count": 0}

    def _counting_fetch(_key: str) -> str | None:
        calls["count"] += 1
        return None

    monkeypatch.setattr(secrets_module, "_read_secret_source_of_truth_value", _counting_fetch)
    login = await _login(app_instance=_app, tenant_id=tenant_id, email=email, password=password)

    refresh_status, _ = await _refresh(
        app_instance=_app,
        refresh_token=login["refresh_token"],
        tenant_id=tenant_id,
    )
    assert refresh_status == 200
    assert calls["count"] == 0
