from __future__ import annotations

import asyncio
import hashlib
import os
from pathlib import Path
from typing import Callable
from uuid import UUID, uuid4

import bcrypt
import pytest
import yaml
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, text

from app.db.session import AsyncSessionLocal, engine, set_tenant_guc_async
from app.main import app
from app.security.auth import decode_and_verify_jwt


@pytest.fixture(autouse=True)
def _p6_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONTRACT_TESTING", "0")
    monkeypatch.setenv("SKELDIR_B12_P5_ENABLE_REVOCATION_IN_TESTS", "1")


def _login_identifier_hash(email: str) -> str:
    pepper = os.environ.get("AUTH_LOGIN_IDENTIFIER_PEPPER", "").strip()
    canonical = email.strip().lower()
    payload = f"{pepper}:{canonical}" if pepper else canonical
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def _seed_identity_with_role(
    *,
    tenant_id: UUID,
    user_id: UUID,
    email: str,
    password: str,
    role: str,
) -> None:
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    login_hash = _login_identifier_hash(email)
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await session.execute(
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
                    "id": str(user_id),
                    "login_identifier_hash": login_hash,
                    "external_subject_hash": f"subject-{user_id}",
                    "password_hash": password_hash,
                },
            )

            await set_tenant_guc_async(session, tenant_id, local=True)
            membership_row = (
                await session.execute(
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
                        "id": str(uuid4()),
                        "tenant_id": str(tenant_id),
                        "user_id": str(user_id),
                    },
                )
            ).mappings().one()
            membership_id = str(membership_row["id"])
            await session.execute(
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
            await session.execute(
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
    assert response.status_code == 200, response.text
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


def test_eg65_openapi_contract_declares_admin_rbac_endpoints_and_403_schema():
    contract = Path("api-contracts/openapi/v1/auth.yaml")
    doc = yaml.safe_load(contract.read_text(encoding="utf-8"))
    paths = doc["paths"]

    admin_check = paths["/api/auth/admin/rbac-check"]["get"]
    membership_role = paths["/api/auth/admin/membership-role"]["post"]

    assert admin_check["security"] == [{"bearerAuth": []}]
    assert "403" in admin_check["responses"]
    assert membership_role["security"] == [{"bearerAuth": []}]
    assert "403" in membership_role["responses"]


def test_eg66_webhook_contracts_remain_tenant_key_auth_without_bearer_auth():
    webhook_dir = Path("api-contracts/openapi/v1/webhooks")
    for file_name in ("shopify.yaml", "stripe.yaml", "paypal.yaml", "woocommerce.yaml"):
        doc = yaml.safe_load((webhook_dir / file_name).read_text(encoding="utf-8"))
        security = doc.get("security", [])
        assert {"tenantKeyAuth": []} in security
        assert {"bearerAuth": []} not in security
