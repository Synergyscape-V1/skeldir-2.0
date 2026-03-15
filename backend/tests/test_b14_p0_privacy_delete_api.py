from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.security.auth import mint_internal_jwt


@pytest.mark.asyncio
async def test_b14_p0_privacy_delete_endpoint_accepts_request_in_contract_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CONTRACT_TESTING", "1")

    tenant_id = uuid4()
    user_id = uuid4()
    token = mint_internal_jwt(
        tenant_id=tenant_id,
        user_id=user_id,
        expires_in_seconds=300,
        additional_claims={"role": "viewer", "roles": ["viewer"], "scopes": ["viewer"]},
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/privacy/delete",
            json={"idempotency_key": "evt-b14-delete-accept"},
            headers={
                "X-Correlation-ID": str(uuid4()),
                "Authorization": f"Bearer {token}",
            },
        )

    assert response.status_code == 202, response.text
    payload = response.json()
    assert payload["status"] == "accepted"
    assert payload["tenant_id"] == str(tenant_id)
    assert payload["exposure_model"] == "public_backend_api_worker_orchestrated"
    assert payload["request_id"].startswith("contract-")
    assert payload["selector"]["idempotency_key"] == "evt-b14-delete-accept"


@pytest.mark.asyncio
async def test_b14_p0_privacy_delete_endpoint_rejects_empty_selector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CONTRACT_TESTING", "1")

    token = mint_internal_jwt(
        tenant_id=UUID("00000000-0000-0000-0000-000000000001"),
        user_id=UUID("00000000-0000-0000-0000-000000000002"),
        expires_in_seconds=300,
        additional_claims={"role": "viewer", "roles": ["viewer"], "scopes": ["viewer"]},
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/privacy/delete",
            json={},
            headers={
                "X-Correlation-ID": str(uuid4()),
                "Authorization": f"Bearer {token}",
            },
        )

    assert response.status_code == 422, response.text

