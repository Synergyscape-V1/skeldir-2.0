from __future__ import annotations

import asyncio
import copy
import importlib
import os
from pathlib import Path
from typing import Annotated, Any, Callable
from uuid import UUID, uuid4

import bcrypt
import pytest
import yaml
from fastapi import FastAPI, Security
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, event, text

from app.db.session import engine
from app.main import app
from app.services.auth_tokens import hash_login_identifier
from app.security.auth import AuthContext, AuthError, decode_and_verify_jwt, get_auth_context


@pytest.fixture(autouse=True)
def _p6_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONTRACT_TESTING", "0")
    monkeypatch.setenv("SKELDIR_B12_P6_ENABLE_NEGATIVE_ADMIN_UNSCOPED_ROUTE", "0")
    monkeypatch.setenv("SKELDIR_B12_P6_NEGATIVE_COPY_ROLE_FORWARD", "0")
    monkeypatch.setenv("SKELDIR_B12_P6_NEGATIVE_MANAGER_SCOPES_THIN", "0")


def _login_identifier_hash(email: str) -> str:
    # Use the same cached pepper source as /api/auth/login to avoid hash drift across test processes.
    from app.api import auth as auth_api

    return hash_login_identifier(email, auth_api._login_identifier_pepper())


async def _seed_identity_with_role(
    *,
    tenant_id: UUID,
    user_id: UUID,
    email: str,
    password: str,
    role: str,
    ensure_user: bool = True,
) -> None:
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    login_hash = _login_identifier_hash(email)
    database_url = os.environ.get("DATABASE_URL", "")
    sync_url = database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    db = create_engine(sync_url)
    with db.begin() as conn:
        current_user = conn.execute(text("SELECT current_user")).scalar_one()
        if str(current_user) not in {"app_user", "postgres"}:
            raise AssertionError(f"seed helper expected app_user/postgres, got {current_user}")
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
        if ensure_user:
            conn.execute(
                text(
                    """
                    INSERT INTO public.users (
                        id,
                        login_identifier_hash,
                        external_subject_hash,
                        auth_provider,
                        is_active,
                        password_hash,
                        created_at,
                        updated_at
                    ) VALUES (
                        :id,
                        :login_identifier_hash,
                        :external_subject_hash,
                        'password',
                        true,
                        :password_hash,
                        now(),
                        now()
                    )
                    """
                ),
                {
                    "id": str(user_id),
                    "login_identifier_hash": login_hash,
                    "external_subject_hash": f"subject-{user_id}",
                    "password_hash": password_hash,
                },
            )

        conn.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
            {"tenant_id": str(tenant_id)},
        )

        membership_id = str(uuid4())
        membership_row = conn.execute(
            text(
                """
                INSERT INTO public.tenant_memberships (id, tenant_id, user_id, membership_status, created_at, updated_at)
                VALUES (:id, :tenant_id, :user_id, 'active', now(), now())
                ON CONFLICT (tenant_id, user_id) DO UPDATE SET
                    membership_status = 'active',
                    updated_at = now()
                RETURNING id
                """
            ),
            {
                "id": membership_id,
                "tenant_id": str(tenant_id),
                "user_id": str(user_id),
            },
        ).mappings().first()
        if membership_row is not None:
            membership_id = str(membership_row["id"])

        conn.execute(
            text(
                """
                DELETE FROM public.tenant_membership_roles
                WHERE tenant_id = :tenant_id
                  AND membership_id = :membership_id
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "membership_id": membership_id,
            },
        )
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
                ) VALUES (
                    gen_random_uuid(),
                    :tenant_id,
                    :membership_id,
                    :role_code,
                    now(),
                    now()
                )
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "membership_id": membership_id,
                "role_code": role,
            },
        )


async def _login(*, tenant_id: UUID, email: str, password: str) -> dict:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/auth/login",
            json={
                "email": email,
                "password": password,
                "tenant_id": str(tenant_id),
            },
            headers={"X-Correlation-ID": str(uuid4())},
        )
    if response.status_code != 200:
        database_url = os.environ.get("DATABASE_URL", "")
        sync_url = database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
        db = create_engine(sync_url)
        login_hash = _login_identifier_hash(email)
        with db.begin() as conn:
            identity = conn.execute(
                text(
                    """
                    SELECT user_id, is_active, auth_provider, password_hash
                    FROM auth.lookup_user_auth_by_login_hash(:login_hash)
                    """
                ),
                {"login_hash": login_hash},
            ).mappings().one_or_none()
            membership = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.tenant_memberships
                    WHERE tenant_id = :tenant_id
                      AND user_id = :user_id
                      AND membership_status = 'active'
                    """
                ),
                {
                    "tenant_id": str(tenant_id),
                    "user_id": str(identity["user_id"]) if identity else None,
                },
            ).scalar_one() if identity else 0
        assert response.status_code == 200, (
            f"{response.text} | login_hash={login_hash} "
            f"| identity_found={identity is not None} "
            f"| identity_auth_provider={identity['auth_provider'] if identity else None} "
            f"| identity_active={identity['is_active'] if identity else None} "
            f"| membership_count={membership}"
        )
    return response.json()


async def _admin_rbac_check(token: str) -> int:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/auth/admin/rbac-check",
            headers={
                "X-Correlation-ID": str(uuid4()),
                "Authorization": f"Bearer {token}",
            },
        )
    return response.status_code


async def _refresh(*, refresh_token: str, tenant_id: UUID) -> tuple[int, dict]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token, "tenant_id": str(tenant_id)},
            headers={
                "X-Correlation-ID": str(uuid4()),
                "Authorization": f"Bearer {refresh_token}",
            },
        )
    payload = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
    return response.status_code, payload


def _install_role_query_counter() -> tuple[dict[str, int], Callable[[], None]]:
    counts = {"role_reads": 0}

    def _capture_sql(conn, cursor, statement, parameters, context, executemany):
        lowered = statement.lower()
        if "tenant_membership_roles" in lowered or "tenant_memberships" in lowered:
            counts["role_reads"] += 1

    event.listen(engine.sync_engine, "before_cursor_execute", _capture_sql)

    def _remove() -> None:
        event.remove(engine.sync_engine, "before_cursor_execute", _capture_sql)

    return counts, _remove


OPERATION_METHODS = {"get", "put", "post", "delete", "patch", "options", "head"}
ALLOWED_SCHEMES = {"accessBearerAuth", "refreshBearerAuth", "tenantKeyAuth"}
ALLOWED_ACCESS_SCOPES = {"admin", "manager", "viewer"}
PUBLIC_ALLOWLIST: set[tuple[str, str]] = {
    ("GET", "/"),
    ("GET", "/api/health"),
    ("GET", "/api/health/live"),
    ("GET", "/api/health/ready"),
    ("GET", "/health"),
    ("GET", "/health/live"),
    ("GET", "/health/ready"),
    ("GET", "/health/worker"),
    ("GET", "/metrics"),
    ("POST", "/api/auth/login"),
}


def _lint_openapi_default_deny_and_scopes(*, doc: dict[str, Any]) -> None:
    top_security = doc.get("security")
    paths = doc.get("paths", {})
    violations: list[str] = []
    for path, methods in paths.items():
        for method, operation in methods.items():
            if method not in OPERATION_METHODS:
                continue
            method_upper = method.upper()
            route_id = f"{method_upper} {path}"
            effective_security = operation.get("security", top_security)
            if (method_upper, path) not in PUBLIC_ALLOWLIST:
                if effective_security in (None, []):
                    violations.append(f"{route_id}: missing security declaration (default-deny violation)")
                    continue

            if effective_security in (None, []):
                continue

            if not isinstance(effective_security, list):
                violations.append(f"{route_id}: security block must be a list")
                continue

            has_access_bearer = False
            has_admin_scope = False
            for requirement in effective_security:
                if not isinstance(requirement, dict):
                    violations.append(f"{route_id}: security requirement must be an object")
                    continue
                for scheme_name, scopes in requirement.items():
                    if scheme_name not in ALLOWED_SCHEMES:
                        violations.append(f"{route_id}: unknown security scheme '{scheme_name}'")
                        continue
                    if scheme_name == "accessBearerAuth":
                        has_access_bearer = True
                        if not isinstance(scopes, list) or not scopes:
                            violations.append(f"{route_id}: accessBearerAuth requires non-empty scopes")
                            continue
                        normalized_scopes = {str(scope).strip().lower() for scope in scopes if str(scope).strip()}
                        if not normalized_scopes:
                            violations.append(f"{route_id}: accessBearerAuth scopes normalized empty")
                            continue
                        if not normalized_scopes.issubset(ALLOWED_ACCESS_SCOPES):
                            violations.append(f"{route_id}: invalid access scopes {sorted(normalized_scopes)}")
                            continue
                        if normalized_scopes.isdisjoint(ALLOWED_ACCESS_SCOPES):
                            violations.append(f"{route_id}: accessBearerAuth scopes must include viewer/manager/admin")
                        if "admin" in normalized_scopes:
                            has_admin_scope = True
                    elif scheme_name == "refreshBearerAuth":
                        if path != "/api/auth/refresh" or method_upper != "POST":
                            violations.append(f"{route_id}: refreshBearerAuth only allowed on POST /api/auth/refresh")
                        if scopes != []:
                            violations.append(f"{route_id}: refreshBearerAuth scopes must be []")
                    elif scheme_name == "tenantKeyAuth":
                        if not path.startswith("/api/webhooks/"):
                            violations.append(f"{route_id}: tenantKeyAuth only allowed on webhook routes")
                        if scopes != []:
                            violations.append(f"{route_id}: tenantKeyAuth scopes must be []")

            if path == "/api/auth/refresh" and method_upper == "POST":
                if effective_security != [{"refreshBearerAuth": []}]:
                    violations.append(f"{route_id}: refresh endpoint must use refreshBearerAuth only")
            if path.startswith("/api/auth/admin"):
                if not has_access_bearer or not has_admin_scope:
                    violations.append(f"{route_id}: admin route must require accessBearerAuth admin scope")

    assert not violations, "OpenAPI security lint violations:\n" + "\n".join(f"- {v}" for v in violations)


async def _viewer_scope_probe_status(token: str) -> int:
    probe_app = FastAPI()

    @probe_app.exception_handler(AuthError)
    async def _handle_auth_error(_, exc: AuthError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "type": exc.type_url,
                "title": exc.title,
                "detail": exc.detail,
                "status": exc.status_code,
            },
        )

    @probe_app.get("/viewer-probe")
    async def viewer_probe(
        _: Annotated[AuthContext, Security(get_auth_context, scopes=["viewer"])],
    ) -> dict[str, bool]:
        return {"ok": True}

    transport = ASGITransport(app=probe_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/viewer-probe",
            headers={
                "X-Correlation-ID": str(uuid4()),
                "Authorization": f"Bearer {token}",
            },
        )
    return response.status_code


@pytest.mark.asyncio
async def test_eg61_viewer_receives_403_on_admin_only_endpoint(test_tenant):
    tenant_id = test_tenant
    viewer_id = uuid4()
    email = f"viewer-{uuid4().hex[:8]}@example.com"
    password = "ViewerPass!123"
    await _seed_identity_with_role(
        tenant_id=tenant_id,
        user_id=viewer_id,
        email=email,
        password=password,
        role="viewer",
    )
    login = await _login(tenant_id=tenant_id, email=email, password=password)

    status = await _admin_rbac_check(login["access_token"])
    assert status == 403


@pytest.mark.asyncio
async def test_eg62_access_jwt_contains_tenant_user_and_role_claims(test_tenant):
    tenant_id = test_tenant
    user_id = uuid4()
    email = f"manager-{uuid4().hex[:8]}@example.com"
    password = "ManagerPass!123"
    await _seed_identity_with_role(
        tenant_id=tenant_id,
        user_id=user_id,
        email=email,
        password=password,
        role="manager",
    )
    login = await _login(tenant_id=tenant_id, email=email, password=password)

    claims = decode_and_verify_jwt(login["access_token"])
    assert claims["tenant_id"] == str(tenant_id)
    assert claims["user_id"] == str(user_id)
    assert claims["role"] == "manager"
    assert claims["roles"] == ["manager"]
    assert claims["scopes"] == ["manager", "viewer"]


@pytest.mark.asyncio
async def test_eg6s1_negative_control_thin_manager_scopes_break_viewer_scope(monkeypatch: pytest.MonkeyPatch, test_tenant):
    tenant_id = test_tenant
    user_id = uuid4()
    email = f"manager-thin-{uuid4().hex[:8]}@example.com"
    password = "ManagerThinPass!123"

    await _seed_identity_with_role(
        tenant_id=tenant_id,
        user_id=user_id,
        email=email,
        password=password,
        role="manager",
    )

    baseline_login = await _login(tenant_id=tenant_id, email=email, password=password)
    baseline_claims = decode_and_verify_jwt(baseline_login["access_token"])
    assert baseline_claims["scopes"] == ["manager", "viewer"]
    assert await _viewer_scope_probe_status(baseline_login["access_token"]) == 200

    monkeypatch.setenv("SKELDIR_B12_P6_NEGATIVE_MANAGER_SCOPES_THIN", "1")
    thin_login = await _login(tenant_id=tenant_id, email=email, password=password)
    thin_claims = decode_and_verify_jwt(thin_login["access_token"])
    assert thin_claims["scopes"] == ["manager"]
    assert await _viewer_scope_probe_status(thin_login["access_token"]) == 403


@pytest.mark.asyncio
async def test_eg63_role_change_immediately_revokes_prior_privileged_token(test_tenant):
    tenant_id = test_tenant
    admin_actor_id = uuid4()
    target_admin_id = uuid4()
    admin_actor_email = f"admin-actor-{uuid4().hex[:8]}@example.com"
    target_admin_email = f"admin-target-{uuid4().hex[:8]}@example.com"
    password = "AdminPass!123"

    await _seed_identity_with_role(
        tenant_id=tenant_id,
        user_id=admin_actor_id,
        email=admin_actor_email,
        password=password,
        role="admin",
    )
    await _seed_identity_with_role(
        tenant_id=tenant_id,
        user_id=target_admin_id,
        email=target_admin_email,
        password=password,
        role="admin",
    )

    admin_actor_login = await _login(tenant_id=tenant_id, email=admin_actor_email, password=password)
    target_admin_login = await _login(tenant_id=tenant_id, email=target_admin_email, password=password)

    assert await _admin_rbac_check(target_admin_login["access_token"]) == 200

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        downgrade = await client.post(
            "/api/auth/admin/membership-role",
            json={"user_id": str(target_admin_id), "role": "viewer"},
            headers={
                "X-Correlation-ID": str(uuid4()),
                "Authorization": f"Bearer {admin_actor_login['access_token']}",
            },
        )
    assert downgrade.status_code == 200, downgrade.text
    assert downgrade.json()["revoked_existing_tokens"] is True

    assert await _admin_rbac_check(target_admin_login["access_token"]) == 401

    # Revocation cutoff uses sub-second precision while JWT iat is second-granularity.
    # Wait for next second boundary so newly issued downgraded token is not spuriously cut off.
    await asyncio.sleep(1.1)
    target_viewer_login = await _login(tenant_id=tenant_id, email=target_admin_email, password=password)
    claims = decode_and_verify_jwt(target_viewer_login["access_token"])
    assert claims["role"] == "viewer"
    assert claims["roles"] == ["viewer"]
    assert claims["scopes"] == ["viewer"]
    assert await _admin_rbac_check(target_viewer_login["access_token"]) == 403


@pytest.mark.asyncio
async def test_eg64_rbac_enforcement_hot_path_has_zero_role_table_reads_after_warmup(test_tenant):
    tenant_id = test_tenant
    admin_id = uuid4()
    email = f"rbac-admin-{uuid4().hex[:8]}@example.com"
    password = "AdminPass!123"
    await _seed_identity_with_role(
        tenant_id=tenant_id,
        user_id=admin_id,
        email=email,
        password=password,
        role="admin",
    )
    admin_login = await _login(tenant_id=tenant_id, email=email, password=password)
    token = admin_login["access_token"]

    assert await _admin_rbac_check(token) == 200

    counts, remove = _install_role_query_counter()
    try:
        for _ in range(100):
            assert await _admin_rbac_check(token) == 200
    finally:
        remove()

    assert counts["role_reads"] == 0


def test_eg6deny_openapi_default_deny_and_scope_coverage():
    _lint_openapi_default_deny_and_scopes(doc=app.openapi())


def test_eg6admin_negative_control_unscoped_admin_route_fails_lint(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SKELDIR_B12_P6_ENABLE_NEGATIVE_ADMIN_UNSCOPED_ROUTE", "1")
    import app.api.auth as auth_module

    reloaded = importlib.reload(auth_module)
    candidate = FastAPI()
    candidate.include_router(reloaded.router, prefix="/api/auth")
    with pytest.raises(AssertionError):
        _lint_openapi_default_deny_and_scopes(doc=candidate.openapi())

    monkeypatch.setenv("SKELDIR_B12_P6_ENABLE_NEGATIVE_ADMIN_UNSCOPED_ROUTE", "0")
    importlib.reload(auth_module)


def test_eg6deny_negative_control_missing_security_route_fails_lint():
    candidate = FastAPI()

    @candidate.get("/api/private/no-security")
    async def private_unsecured() -> dict[str, bool]:
        return {"ok": True}

    with pytest.raises(AssertionError):
        _lint_openapi_default_deny_and_scopes(doc=candidate.openapi())


def test_eg6view_negative_control_access_scheme_empty_scopes_fails_lint():
    doc = copy.deepcopy(app.openapi())
    doc["paths"]["/api/negative/access-empty"] = {
        "get": {
            "operationId": "negativeAccessEmptyScopes",
            "responses": {"200": {"description": "ok"}},
            "security": [{"accessBearerAuth": []}],
        }
    }
    with pytest.raises(AssertionError):
        _lint_openapi_default_deny_and_scopes(doc=doc)


def test_eg6scheme_negative_control_refresh_route_misdeclared_as_access_fails_lint():
    doc = copy.deepcopy(app.openapi())
    doc["paths"]["/api/auth/refresh"]["post"]["security"] = [{"accessBearerAuth": ["viewer"]}]
    with pytest.raises(AssertionError):
        _lint_openapi_default_deny_and_scopes(doc=doc)


@pytest.mark.asyncio
async def test_eg6t1_tenant_divergence_same_user_roles_diverge(test_tenant):
    tenant_a = test_tenant
    tenant_b = uuid4()
    user_id = uuid4()
    email = f"divergence-{uuid4().hex[:8]}@example.com"
    password = "DivergencePass!123"
    tenant_b_only_user = uuid4()
    tenant_b_only_email = f"tenant-b-only-{uuid4().hex[:8]}@example.com"

    await _seed_identity_with_role(
        tenant_id=tenant_a,
        user_id=user_id,
        email=email,
        password=password,
        role="admin",
    )
    await _seed_identity_with_role(
        tenant_id=tenant_b,
        user_id=user_id,
        email=email,
        password=password,
        role="viewer",
        ensure_user=False,
    )
    await _seed_identity_with_role(
        tenant_id=tenant_b,
        user_id=tenant_b_only_user,
        email=tenant_b_only_email,
        password=password,
        role="viewer",
    )

    login_a = await _login(tenant_id=tenant_a, email=email, password=password)
    login_b = await _login(tenant_id=tenant_b, email=email, password=password)
    claims_a = decode_and_verify_jwt(login_a["access_token"])
    claims_b = decode_and_verify_jwt(login_b["access_token"])

    assert claims_a["tenant_id"] == str(tenant_a)
    assert claims_a["role"] == "admin"
    assert claims_a["scopes"] == ["admin", "manager", "viewer"]
    assert claims_b["tenant_id"] == str(tenant_b)
    assert claims_b["role"] == "viewer"
    assert claims_b["scopes"] == ["viewer"]

    assert await _admin_rbac_check(login_a["access_token"]) == 200
    assert await _admin_rbac_check(login_b["access_token"]) == 403

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        cross_tenant_mutation = await client.post(
            "/api/auth/admin/membership-role",
            json={"user_id": str(tenant_b_only_user), "role": "admin"},
            headers={
                "X-Correlation-ID": str(uuid4()),
                "Authorization": f"Bearer {login_a['access_token']}",
            },
        )
    assert cross_tenant_mutation.status_code == 404


@pytest.mark.asyncio
async def test_eg6r1_refresh_after_downgrade_db_authoritative(test_tenant):
    tenant_id = test_tenant
    admin_actor_id = uuid4()
    target_admin_id = uuid4()
    admin_actor_email = f"refresh-admin-actor-{uuid4().hex[:8]}@example.com"
    target_admin_email = f"refresh-admin-target-{uuid4().hex[:8]}@example.com"
    password = "RefreshAdminPass!123"

    await _seed_identity_with_role(
        tenant_id=tenant_id,
        user_id=admin_actor_id,
        email=admin_actor_email,
        password=password,
        role="admin",
    )
    await _seed_identity_with_role(
        tenant_id=tenant_id,
        user_id=target_admin_id,
        email=target_admin_email,
        password=password,
        role="admin",
    )

    admin_actor_login = await _login(tenant_id=tenant_id, email=admin_actor_email, password=password)
    target_login = await _login(tenant_id=tenant_id, email=target_admin_email, password=password)
    old_refresh = target_login["refresh_token"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        downgrade = await client.post(
            "/api/auth/admin/membership-role",
            json={"user_id": str(target_admin_id), "role": "viewer"},
            headers={
                "X-Correlation-ID": str(uuid4()),
                "Authorization": f"Bearer {admin_actor_login['access_token']}",
            },
        )
    assert downgrade.status_code == 200, downgrade.text

    assert await _admin_rbac_check(target_login["access_token"]) == 401
    await asyncio.sleep(1.1)
    refresh_status, refresh_payload = await _refresh(refresh_token=old_refresh, tenant_id=tenant_id)
    assert refresh_status == 200, refresh_payload
    refreshed_claims = decode_and_verify_jwt(refresh_payload["access_token"])
    assert refreshed_claims["role"] == "viewer"
    assert refreshed_claims["roles"] == ["viewer"]
    assert refreshed_claims["scopes"] == ["viewer"]
    assert await _admin_rbac_check(refresh_payload["access_token"]) == 403


@pytest.mark.asyncio
async def test_eg6rdel_membership_deletion_blocks_refresh_remint(test_tenant):
    tenant_id = test_tenant
    target_user_id = uuid4()
    target_email = f"refresh-delete-{uuid4().hex[:8]}@example.com"
    password = "RefreshDeletePass!123"

    await _seed_identity_with_role(
        tenant_id=tenant_id,
        user_id=target_user_id,
        email=target_email,
        password=password,
        role="admin",
    )
    target_login = await _login(tenant_id=tenant_id, email=target_email, password=password)
    old_refresh = target_login["refresh_token"]

    database_url = os.environ.get("MIGRATION_DATABASE_URL") or os.environ.get("DATABASE_URL", "")
    sync_url = database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    db = create_engine(sync_url)
    with db.begin() as conn:
        deleted_roles = conn.execute(
            text(
                """
                DELETE FROM public.tenant_membership_roles
                WHERE tenant_id = :tenant_id
                  AND membership_id IN (
                    SELECT id
                    FROM public.tenant_memberships
                    WHERE tenant_id = :tenant_id
                      AND user_id = :user_id
                  )
                """
            ),
            {"tenant_id": str(tenant_id), "user_id": str(target_user_id)},
        )
        deleted_memberships = conn.execute(
            text(
                """
                DELETE FROM public.tenant_memberships
                WHERE tenant_id = :tenant_id
                  AND user_id = :user_id
                """
            ),
            {"tenant_id": str(tenant_id), "user_id": str(target_user_id)},
        )
    assert (deleted_roles.rowcount or 0) >= 1
    assert (deleted_memberships.rowcount or 0) >= 1

    refresh_status, _refresh_payload = await _refresh(refresh_token=old_refresh, tenant_id=tenant_id)
    assert refresh_status in {401, 403}


@pytest.mark.asyncio
async def test_eg6r1_negative_control_copy_forward_role_toggle_demonstrates_violation(
    test_tenant,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("SKELDIR_B12_P6_NEGATIVE_COPY_ROLE_FORWARD", "1")
    tenant_id = test_tenant
    admin_actor_id = uuid4()
    target_admin_id = uuid4()
    admin_actor_email = f"neg-refresh-admin-actor-{uuid4().hex[:8]}@example.com"
    target_admin_email = f"neg-refresh-admin-target-{uuid4().hex[:8]}@example.com"
    password = "RefreshNegativePass!123"

    await _seed_identity_with_role(
        tenant_id=tenant_id,
        user_id=admin_actor_id,
        email=admin_actor_email,
        password=password,
        role="admin",
    )
    await _seed_identity_with_role(
        tenant_id=tenant_id,
        user_id=target_admin_id,
        email=target_admin_email,
        password=password,
        role="admin",
    )

    admin_actor_login = await _login(tenant_id=tenant_id, email=admin_actor_email, password=password)
    target_login = await _login(tenant_id=tenant_id, email=target_admin_email, password=password)
    old_refresh = target_login["refresh_token"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        downgrade = await client.post(
            "/api/auth/admin/membership-role",
            json={"user_id": str(target_admin_id), "role": "viewer"},
            headers={
                "X-Correlation-ID": str(uuid4()),
                "Authorization": f"Bearer {admin_actor_login['access_token']}",
            },
        )
    assert downgrade.status_code == 200, downgrade.text

    await asyncio.sleep(1.1)
    refresh_status, refresh_payload = await _refresh(refresh_token=old_refresh, tenant_id=tenant_id)
    assert refresh_status == 200
    refreshed_claims = decode_and_verify_jwt(refresh_payload["access_token"])
    assert refreshed_claims["role"] == "admin"
    assert refreshed_claims["scopes"] == ["admin", "manager", "viewer"]
    assert await _admin_rbac_check(refresh_payload["access_token"]) == 200


def test_eg65_openapi_contract_declares_admin_rbac_endpoints_and_403_schema():
    contract = Path("api-contracts/openapi/v1/auth.yaml")
    doc = yaml.safe_load(contract.read_text(encoding="utf-8"))
    paths = doc["paths"]

    token_cutoff = paths["/api/auth/admin/token-cutoff"]["post"]
    admin_check = paths["/api/auth/admin/rbac-check"]["get"]
    membership_role = paths["/api/auth/admin/membership-role"]["post"]
    refresh = paths["/api/auth/refresh"]["post"]
    logout = paths["/api/auth/logout"]["post"]
    verify = paths["/api/auth/verify"]["get"]

    assert token_cutoff["security"] == [{"accessBearerAuth": ["admin"]}]
    assert admin_check["security"] == [{"accessBearerAuth": ["admin"]}]
    assert "403" in admin_check["responses"]
    assert membership_role["security"] == [{"accessBearerAuth": ["admin"]}]
    assert "403" in membership_role["responses"]
    assert refresh["security"] == [{"refreshBearerAuth": []}]
    assert logout["security"] == [{"accessBearerAuth": ["viewer"]}]
    assert verify["security"] == [{"accessBearerAuth": ["viewer"]}]


def test_eg66_webhook_contracts_remain_tenant_key_auth_without_bearer_auth():
    webhook_dir = Path("api-contracts/openapi/v1/webhooks")
    for file_name in ("shopify.yaml", "stripe.yaml", "paypal.yaml", "woocommerce.yaml"):
        doc = yaml.safe_load((webhook_dir / file_name).read_text(encoding="utf-8"))
        security = doc.get("security", [])
        assert {"tenantKeyAuth": []} in security
        assert {"accessBearerAuth": ["viewer"]} not in security
