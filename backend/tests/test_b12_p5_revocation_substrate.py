from __future__ import annotations

import os
import time
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Callable
from uuid import UUID, uuid4

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy import text

from app.tasks.beat_schedule import build_beat_schedule
from app.db.session import AsyncSessionLocal
from app.db.session import engine
from app.main import app
from app.core.secrets import get_jwt_signing_material
from app.security.revocation_runtime import RevocationRuntimeCache
from app.security.auth import decode_and_verify_jwt, extract_access_token_claims, mint_internal_jwt
from app.services.auth_revocation import denylist_access_token
from app.tasks.maintenance import _delete_expired_denylist_rows
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
    additional_claims: dict[str, object] = {
        "iat": issued_at,
        "exp": exp or (issued_at + 3600),
    }
    if include_jti:
        additional_claims["jti"] = str(jti or uuid4())
    if roles:
        additional_claims["roles"] = roles
    if not include_jti:
        signing = get_jwt_signing_material()
        payload: dict[str, object] = {
            "tenant_id": str(tenant_id),
            "sub": str(user_id),
            "user_id": str(user_id),
            "iat": issued_at,
            "exp": exp or (issued_at + 3600),
        }
        if roles:
            payload["roles"] = roles
        if signing.issuer:
            payload["iss"] = signing.issuer
        if signing.audience:
            payload["aud"] = signing.audience
        return jwt.encode(payload, signing.key, algorithm=signing.algorithm, headers={"kid": signing.kid})
    return mint_internal_jwt(
        tenant_id=tenant_id,
        user_id=user_id,
        expires_in_seconds=max(1, int((exp or (issued_at + 3600)) - issued_at)),
        additional_claims=additional_claims,
    )


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


async def test_kill_switch_negative_control_disabled_revocation_allows_prior_token(test_tenant, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SKELDIR_B12_P5_DISABLE_REVOCATION_CHECKS", "1")

    user_id = uuid4()
    admin_user = uuid4()
    now = int(time.time())

    token_before_cutoff = _build_token(
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

    # Negative control: disabled revocation checks intentionally allow stale token reuse.
    assert await _verify_token(token_before_cutoff) == 200


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


def _install_revocation_query_counter() -> tuple[dict[str, int], Callable[[], None]]:
    counts = {"revocation": 0}

    def _capture_sql(conn, cursor, statement, parameters, context, executemany):
        lowered = statement.lower()
        if "auth_access_token_denylist" in lowered or "auth_user_token_cutoffs" in lowered:
            counts["revocation"] += 1

    event.listen(engine.sync_engine, "before_cursor_execute", _capture_sql)

    def _remove() -> None:
        event.remove(engine.sync_engine, "before_cursor_execute", _capture_sql)

    return counts, _remove


async def test_http_revocation_hot_path_has_zero_db_lookups_after_warmup(test_tenant):
    user_id = uuid4()
    token = _build_token(tenant_id=test_tenant, user_id=user_id)

    # Warmup allows bounded cold-start lookup and cache priming.
    assert await _verify_token(token) == 200

    counts, remove = _install_revocation_query_counter()
    try:
        for _ in range(100):
            assert await _verify_token(token) == 200
    finally:
        remove()

    assert counts["revocation"] == 0


async def test_worker_revocation_hot_path_has_zero_db_lookups_after_warmup(test_tenant):
    user_id = uuid4()
    token = _build_token(tenant_id=test_tenant, user_id=user_id)

    # Warmup allows bounded cold-start lookup and cache priming.
    assert_worker_auth_envelope_active(
        auth_token=token,
        tenant_id=test_tenant,
        user_id=user_id,
    )

    counts, remove = _install_revocation_query_counter()
    try:
        for _ in range(100):
            assert_worker_auth_envelope_active(
                auth_token=token,
                tenant_id=test_tenant,
                user_id=user_id,
            )
    finally:
        remove()

    assert counts["revocation"] == 0


async def test_revocation_events_propagate_across_runtime_caches_within_sla(test_tenant):
    user_id = uuid4()
    token = _build_token(tenant_id=test_tenant, user_id=user_id)
    claims = extract_access_token_claims(decode_and_verify_jwt(token))

    runtime_a = RevocationRuntimeCache(runtime_name="sla-a")
    runtime_b = RevocationRuntimeCache(runtime_name="sla-b")
    runtime_a.ensure_started()
    runtime_b.ensure_started()
    try:
        runtime_b.note_cutoff_absent(tenant_id=claims.tenant_id, user_id=claims.user_id)
        runtime_b.note_clean_token(
            tenant_id=claims.tenant_id,
            user_id=claims.user_id,
            jti=claims.jti,
            expires_at=datetime.fromtimestamp(claims.expires_at_epoch, tz=timezone.utc),
        )

        async with AsyncSessionLocal() as session:
            async with session.begin():
                await denylist_access_token(
                    session,
                    tenant_id=claims.tenant_id,
                    user_id=claims.user_id,
                    jti=claims.jti,
                    expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
                    reason="propagation_sla_test",
                )

        deadline = time.monotonic() + 5.0
        observed = False
        while time.monotonic() < deadline:
            snap = runtime_b.snapshot_for_token(
                tenant_id=claims.tenant_id,
                user_id=claims.user_id,
                jti=claims.jti,
                issued_at_epoch=claims.issued_at_epoch,
            )
            if snap.is_known and snap.is_revoked:
                observed = True
                break
            await asyncio.sleep(0.1)
        assert observed
    finally:
        runtime_a.close()
        runtime_b.close()


async def test_denylist_gc_is_bounded_and_makes_progress(test_tenant):
    user_id = uuid4()
    now = datetime.now(timezone.utc)
    expired_rows = [uuid4() for _ in range(7)]

    async with AsyncSessionLocal() as session:
        async with session.begin():
            await session.execute(
                text(
                    """
                    INSERT INTO public.users (id, login_identifier_hash, auth_provider, is_active)
                    VALUES (:id, :hash, 'password', true)
                    ON CONFLICT (id) DO NOTHING
                    """
                ),
                {"id": str(user_id), "hash": f"gc-test-{user_id}"},
            )
            await session.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(test_tenant)},
            )
            for jti in expired_rows:
                await session.execute(
                    text(
                        """
                        INSERT INTO public.auth_access_token_denylist
                        (tenant_id, user_id, jti, revoked_at, expires_at, reason)
                        VALUES (:tenant_id, :user_id, :jti, :revoked_at, :expires_at, :reason)
                        ON CONFLICT (tenant_id, user_id, jti)
                        DO NOTHING
                        """
                    ),
                    {
                        "tenant_id": str(test_tenant),
                        "user_id": str(user_id),
                        "jti": str(jti),
                        "revoked_at": now - timedelta(minutes=20),
                        "expires_at": now - timedelta(minutes=5),
                        "reason": "gc_test_expired",
                    },
                )

            await session.execute(
                text(
                    """
                    INSERT INTO public.auth_access_token_denylist
                    (tenant_id, user_id, jti, revoked_at, expires_at, reason)
                    VALUES (:tenant_id, :user_id, :jti, :revoked_at, :expires_at, :reason)
                    ON CONFLICT (tenant_id, user_id, jti)
                    DO NOTHING
                    """
                ),
                {
                    "tenant_id": str(test_tenant),
                    "user_id": str(user_id),
                    "jti": str(uuid4()),
                    "revoked_at": now,
                    "expires_at": now + timedelta(minutes=10),
                    "reason": "gc_test_live",
                },
            )

    first_tick = await _delete_expired_denylist_rows(batch_size=3)
    second_tick = await _delete_expired_denylist_rows(batch_size=3)
    third_tick = await _delete_expired_denylist_rows(batch_size=3)

    assert first_tick["deleted_rows"] <= 3
    assert second_tick["deleted_rows"] <= 3
    assert third_tick["deleted_rows"] <= 3
    assert first_tick["deleted_rows"] > 0
    assert first_tick["deleted_rows"] + second_tick["deleted_rows"] + third_tick["deleted_rows"] >= 7


async def test_denylist_gc_singleflight_allows_only_one_active_deleter(test_tenant, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SKELDIR_B12_P5_GC_SINGLEFLIGHT_HOLD_SECONDS", "0.35")

    user_id = uuid4()
    now = datetime.now(timezone.utc)
    expired_rows = [uuid4() for _ in range(24)]

    async with AsyncSessionLocal() as session:
        async with session.begin():
            await session.execute(
                text(
                    """
                    INSERT INTO public.users (id, login_identifier_hash, auth_provider, is_active)
                    VALUES (:id, :hash, 'password', true)
                    ON CONFLICT (id) DO NOTHING
                    """
                ),
                {"id": str(user_id), "hash": f"gc-singleflight-{user_id}"},
            )
            await session.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(test_tenant)},
            )
            for jti in expired_rows:
                await session.execute(
                    text(
                        """
                        INSERT INTO public.auth_access_token_denylist
                        (tenant_id, user_id, jti, revoked_at, expires_at, reason)
                        VALUES (:tenant_id, :user_id, :jti, :revoked_at, :expires_at, :reason)
                        ON CONFLICT (tenant_id, user_id, jti)
                        DO NOTHING
                        """
                    ),
                    {
                        "tenant_id": str(test_tenant),
                        "user_id": str(user_id),
                        "jti": str(jti),
                        "revoked_at": now - timedelta(minutes=20),
                        "expires_at": now - timedelta(minutes=5),
                        "reason": "gc_singleflight_concurrency",
                    },
                )

    first, second = await asyncio.gather(
        _delete_expired_denylist_rows(batch_size=12),
        _delete_expired_denylist_rows(batch_size=12),
    )
    results = [first, second]

    assert sorted(result["lock_acquired"] for result in results) == [0, 1]
    assert sum(result["deleted_rows"] for result in results) > 0
    assert any(result["lock_acquired"] == 0 and result["deleted_rows"] == 0 for result in results)
    assert any(result["lock_acquired"] == 1 and result["deleted_rows"] > 0 for result in results)


async def test_denylist_gc_job_is_registered_in_beat_schedule():
    schedule = build_beat_schedule()
    assert "auth-denylist-gc" in schedule
