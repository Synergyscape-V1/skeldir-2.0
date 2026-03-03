from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db.session import AsyncSessionLocal
from app.main import app
from app.security.auth import decode_and_verify_jwt, extract_access_token_claims
from app.services.auth_revocation import denylist_access_token
from app.tasks.context import assert_worker_auth_envelope_active

pytestmark = pytest.mark.asyncio


os.environ.setdefault("AUTH_JWT_SECRET", "test-secret")
os.environ.setdefault("AUTH_JWT_ALGORITHM", "HS256")
os.environ.setdefault("AUTH_JWT_ISSUER", "https://issuer.skeldir.test")
os.environ.setdefault("AUTH_JWT_AUDIENCE", "skeldir-api")


def _build_token(
    *,
    tenant_id: UUID,
    user_id: UUID,
    iat: int | None = None,
    exp: int | None = None,
    jti: UUID | None = None,
    include_jti: bool = True,
    roles: list[str] | None = None,
) -> str:
    now = int(time.time())
    issued_at = iat or now
    payload: dict[str, object] = {
        "sub": str(user_id),
        "user_id": str(user_id),
        "tenant_id": str(tenant_id),
        "iss": os.environ["AUTH_JWT_ISSUER"],
        "aud": os.environ["AUTH_JWT_AUDIENCE"],
        "iat": issued_at,
        "exp": exp or (issued_at + 3600),
    }
    if include_jti:
        payload["jti"] = str(jti or uuid4())
    if roles:
        payload["roles"] = roles
    return jwt.encode(payload, os.environ["AUTH_JWT_SECRET"], algorithm=os.environ["AUTH_JWT_ALGORITHM"])


@pytest.fixture(autouse=True)
def _enable_revocation(monkeypatch: pytest.MonkeyPatch) -> None:
    if "SKELDIR_B12_P5_ENABLE_REVOCATION_IN_TESTS" not in os.environ:
        monkeypatch.setenv("SKELDIR_B12_P5_ENABLE_REVOCATION_IN_TESTS", "1")
    if "CONTRACT_TESTING" not in os.environ:
        monkeypatch.delenv("CONTRACT_TESTING", raising=False)


async def _verify_token(token: str, correlation_id: str | None = None) -> int:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/auth/verify",
            headers={
                "X-Correlation-ID": correlation_id or str(uuid4()),
                "Authorization": f"Bearer {token}",
            },
        )
    return resp.status_code


async def test_missing_jti_claim_returns_401_before_revocation_lookup(test_tenant, monkeypatch: pytest.MonkeyPatch):
    async def _sentinel(*args, **kwargs):
        raise AssertionError("revocation lookup must not run for malformed claim substrate")

    monkeypatch.setattr("app.security.auth.evaluate_access_token_revocation", _sentinel)
    token = _build_token(tenant_id=test_tenant, user_id=uuid4(), include_jti=False)

    status = await _verify_token(token)
    assert status == 401


async def test_logout_denylist_blocks_access_token_reuse_immediately(test_tenant):
    user_id = uuid4()
    token = _build_token(tenant_id=test_tenant, user_id=user_id)

    status_before = await _verify_token(token)
    assert status_before == 200

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        logout_resp = await client.post(
            "/api/auth/logout",
            headers={
                "X-Correlation-ID": str(uuid4()),
                "Authorization": f"Bearer {token}",
            },
        )
    assert logout_resp.status_code == 200

    status_after = await _verify_token(token)
    assert status_after == 401


async def test_logout_denylist_negative_control_disabled_revocation_allows_reuse(test_tenant, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SKELDIR_B12_P5_DISABLE_REVOCATION_CHECKS", "1")

    user_id = uuid4()
    token = _build_token(tenant_id=test_tenant, user_id=user_id)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        logout_resp = await client.post(
            "/api/auth/logout",
            headers={
                "X-Correlation-ID": str(uuid4()),
                "Authorization": f"Bearer {token}",
            },
        )
    assert logout_resp.status_code == 200

    status_after = await _verify_token(token)
    assert status_after == 200


async def test_kill_switch_invalidates_prior_tokens_and_allows_new_tokens(test_tenant):
    user_id = uuid4()
    admin_user = uuid4()
    now = int(time.time())

    token_a = _build_token(
        tenant_id=test_tenant,
        user_id=user_id,
        iat=now - 120,
        exp=now + 3600,
    )
    admin_token = _build_token(
        tenant_id=test_tenant,
        user_id=admin_user,
        iat=now,
        exp=now + 3600,
        roles=["admin"],
    )

    assert await _verify_token(token_a) == 200

    cutoff = datetime.now(timezone.utc) - timedelta(seconds=30)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        cutoff_resp = await client.post(
            "/api/auth/admin/token-cutoff",
            json={
                "user_id": str(user_id),
                "tokens_invalid_before": cutoff.isoformat(),
            },
            headers={
                "X-Correlation-ID": str(uuid4()),
                "Authorization": f"Bearer {admin_token}",
            },
        )
    assert cutoff_resp.status_code == 200

    assert await _verify_token(token_a) == 401

    token_b = _build_token(
        tenant_id=test_tenant,
        user_id=user_id,
        iat=now,
        exp=now + 3600,
    )
    assert await _verify_token(token_b) == 200


async def test_worker_auth_envelope_respects_revocation_before_db_write(test_tenant):
    user_id = uuid4()
    token = _build_token(tenant_id=test_tenant, user_id=user_id)
    claims = decode_and_verify_jwt(token)
    token_claims = extract_access_token_claims(claims)

    async with AsyncSessionLocal() as session:
        async with session.begin():
            await denylist_access_token(
                session,
                tenant_id=test_tenant,
                user_id=user_id,
                jti=token_claims.jti,
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                reason="test_worker_revocation",
            )

    with pytest.raises(ValueError, match="auth envelope revoked"):
        assert_worker_auth_envelope_active(
            auth_token=token,
            tenant_id=test_tenant,
            user_id=user_id,
        )


async def test_revocation_lookups_are_index_backed(test_tenant):
    user_id = uuid4()
    jti = uuid4()

    async with AsyncSessionLocal() as session:
        async with session.begin():
            await session.execute(text("SET LOCAL enable_seqscan = off"))

            denylist_plan_rows = await session.execute(
                text(
                    """
                    EXPLAIN
                    SELECT 1
                    FROM public.auth_access_token_denylist d
                    WHERE d.tenant_id = :tenant_id
                      AND d.user_id = :user_id
                      AND d.jti = :jti
                    """
                ),
                {
                    "tenant_id": str(test_tenant),
                    "user_id": str(user_id),
                    "jti": str(jti),
                },
            )
            denylist_plan = "\n".join(str(row[0]) for row in denylist_plan_rows)

            cutoff_plan_rows = await session.execute(
                text(
                    """
                    EXPLAIN
                    SELECT c.tokens_invalid_before
                    FROM public.auth_user_token_cutoffs c
                    WHERE c.tenant_id = :tenant_id
                      AND c.user_id = :user_id
                    """
                ),
                {
                    "tenant_id": str(test_tenant),
                    "user_id": str(user_id),
                },
            )
            cutoff_plan = "\n".join(str(row[0]) for row in cutoff_plan_rows)

    assert "idx_auth_access_token_denylist" in denylist_plan.lower()
    assert "idx_auth_user_token_cutoffs_tenant_user" in cutoff_plan.lower()
