from __future__ import annotations

from typing import Annotated
from uuid import UUID, uuid4

import pytest
from fastapi import Depends, FastAPI, Security
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import session as db_session
from app.db.deps import get_db_session
from app.security.auth import AuthContext, get_auth_context, mint_internal_jwt
from app.testing.jwt_rs256 import private_ring_payload, public_ring_payload


async def _seed_dead_event(*, tenant_id: UUID, marker: str) -> None:
    async with db_session.get_session(tenant_id=tenant_id, user_id=uuid4()) as session:
        await session.execute(
            text(
                """
                INSERT INTO public.dead_events (
                    id,
                    tenant_id,
                    ingested_at,
                    source,
                    error_code,
                    error_detail,
                    raw_payload,
                    correlation_id,
                    external_event_id,
                    event_type,
                    error_type,
                    error_message,
                    remediation_status
                ) VALUES (
                    :id,
                    :tenant_id,
                    now(),
                    'stripe',
                    'VALIDATION_ERROR',
                    CAST(:error_detail AS jsonb),
                    CAST(:raw_payload AS jsonb),
                    :correlation_id,
                    :external_event_id,
                    'purchase',
                    'validation_error',
                    'seed',
                    'pending'
                )
                """
            ),
            {
                "id": str(uuid4()),
                "tenant_id": str(tenant_id),
                "correlation_id": str(uuid4()),
                "external_event_id": marker,
                "error_detail": '{"detail":"seed"}',
                "raw_payload": '{"seed": true}',
            },
        )


def _build_probe_app() -> FastAPI:
    app = FastAPI()

    @app.get("/probe/tenant-rls", operation_id="probeJwtGucRls")
    async def probe_jwt_guc_rls(
        marker: str,
        other_tenant_id: UUID,
        auth_context: Annotated[AuthContext, Security(get_auth_context, scopes=["viewer"])],
        db: AsyncSession = Depends(get_db_session),
    ) -> dict[str, str | int]:
        tenant_guc = (
            await db.execute(text("SELECT current_setting('app.current_tenant_id', true)"))
        ).scalar_one_or_none()
        user_guc = (
            await db.execute(text("SELECT current_setting('app.current_user_id', true)"))
        ).scalar_one_or_none()
        visible_marker_rows = (
            await db.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.dead_events
                    WHERE external_event_id = :marker
                    """
                ),
                {"marker": marker},
            )
        ).scalar_one()
        visible_other_tenant_rows = (
            await db.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.dead_events
                    WHERE external_event_id = :marker
                      AND tenant_id = :other_tenant_id
                    """
                ),
                {"marker": marker, "other_tenant_id": str(other_tenant_id)},
            )
        ).scalar_one()
        return {
            "tenant_id": str(auth_context.tenant_id),
            "user_id": str(auth_context.user_id),
            "tenant_guc": str(tenant_guc or ""),
            "user_guc": str(user_guc or ""),
            "visible_marker_rows": int(visible_marker_rows),
            "visible_other_tenant_rows": int(visible_other_tenant_rows),
        }

    return app


@pytest.mark.asyncio
async def test_b14_p0_e2e_http_jwt_to_guc_to_rls_chain(
    test_tenant_pair,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTH_JWT_SECRET", private_ring_payload())
    monkeypatch.setenv("AUTH_JWT_PUBLIC_KEY_RING", public_ring_payload())
    monkeypatch.setenv("AUTH_JWT_ALGORITHM", "RS256")
    monkeypatch.setenv("AUTH_JWT_ISSUER", "https://issuer.skeldir.test")
    monkeypatch.setenv("AUTH_JWT_AUDIENCE", "skeldir-api")
    monkeypatch.setenv("SKELDIR_B12_P3_FORCE_PER_REQUEST_VERIFIER_REFRESH", "1")

    tenant_a, tenant_b = test_tenant_pair
    marker = f"b14-rd-b01-1-{uuid4().hex[:12]}"

    await _seed_dead_event(tenant_id=tenant_a, marker=marker)
    await _seed_dead_event(tenant_id=tenant_b, marker=marker)

    user_a = uuid4()
    user_b = uuid4()
    token_a = mint_internal_jwt(
        tenant_id=tenant_a,
        user_id=user_a,
        expires_in_seconds=300,
        additional_claims={"role": "viewer", "roles": ["viewer"], "scopes": ["viewer"]},
    )
    token_b = mint_internal_jwt(
        tenant_id=tenant_b,
        user_id=user_b,
        expires_in_seconds=300,
        additional_claims={"role": "viewer", "roles": ["viewer"], "scopes": ["viewer"]},
    )

    probe_app = _build_probe_app()
    transport = ASGITransport(app=probe_app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response_a = await client.get(
            "/probe/tenant-rls",
            params={"marker": marker, "other_tenant_id": str(tenant_b)},
            headers={
                "X-Correlation-ID": str(uuid4()),
                "Authorization": f"Bearer {token_a}",
            },
        )
        response_b = await client.get(
            "/probe/tenant-rls",
            params={"marker": marker, "other_tenant_id": str(tenant_a)},
            headers={
                "X-Correlation-ID": str(uuid4()),
                "Authorization": f"Bearer {token_b}",
            },
        )

    assert response_a.status_code == 200, response_a.text
    assert response_b.status_code == 200, response_b.text

    payload_a = response_a.json()
    payload_b = response_b.json()

    assert payload_a["tenant_id"] == str(tenant_a)
    assert payload_a["user_id"] == str(user_a)
    assert payload_a["tenant_guc"] == str(tenant_a)
    assert payload_a["user_guc"] == str(user_a)
    assert payload_a["visible_marker_rows"] == 1
    assert payload_a["visible_other_tenant_rows"] == 0

    assert payload_b["tenant_id"] == str(tenant_b)
    assert payload_b["user_id"] == str(user_b)
    assert payload_b["tenant_guc"] == str(tenant_b)
    assert payload_b["user_guc"] == str(user_b)
    assert payload_b["visible_marker_rows"] == 1
    assert payload_b["visible_other_tenant_rows"] == 0
