from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.api import webhooks
from app.ingestion.event_service import ValidationError as IngestionValidationError
from app.main import app


@pytest.mark.asyncio
async def test_b26_p2_xxiii_relay_refusal_is_a_governed_outcome(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_ingest(**kwargs):
        raise IngestionValidationError(
            "b26_p2_ingress_relay_refused: status=422"
            " body=b26_p2_lifecycle_not_creation_moment"
        )

    monkeypatch.setattr(webhooks, "ingest_with_transaction", fake_ingest)
    result = await webhooks._handle_ingestion(
        tenant_id=uuid4(),
        event_data={"event_type": "purchase"},
        idempotency_key="xxiii-relay-refusal",
        source="stripe",
        verified_at=datetime.now(timezone.utc),
    )
    assert result["status"] == "authority_refused"
    assert "b26_p2_ingress_relay_refused" in result["error"]


@pytest.mark.asyncio
async def test_b26_p2_xxiii_relay_transport_failure_stays_retryable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_ingest(**kwargs):
        raise IngestionValidationError(
            "b26_p2_ingress_relay_unreachable:ConnectError"
        )

    monkeypatch.setattr(webhooks, "ingest_with_transaction", fake_ingest)
    with pytest.raises(HTTPException) as excinfo:
        await webhooks._handle_ingestion(
            tenant_id=uuid4(),
            event_data={"event_type": "purchase"},
            idempotency_key="xxiii-relay-unreachable",
            source="stripe",
            verified_at=datetime.now(timezone.utc),
        )
    assert excinfo.value.status_code == 503


@pytest.mark.asyncio
async def test_b26_p2_xxiii_relay_refusal_is_http_200_not_500(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = uuid4()

    async def _stripe_auth_override():
        return {
            "tenant_id": tenant_id,
            "verified_at": datetime.now(timezone.utc),
        }

    async def fake_ingest(**kwargs):
        raise IngestionValidationError(
            "b26_p2_ingress_relay_refused: status=422"
            " body=b26_p2_lifecycle_not_creation_moment"
        )

    monkeypatch.setattr(webhooks, "ingest_with_transaction", fake_ingest)
    app.dependency_overrides[webhooks.stripe_webhook_auth] = _stripe_auth_override
    payload = {
        "id": f"evt_{uuid4().hex[:10]}",
        "type": "payment_intent.succeeded",
        "created": int(datetime.now(timezone.utc).timestamp()),
        "data": {
            "object": {
                "id": f"pi_{uuid4().hex[:10]}",
                "amount": 1234,
                "currency": "usd",
            }
        },
    }
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/webhooks/stripe/payment_intent/succeeded",
                headers={
                    "Content-Type": "application/json",
                    "X-Idempotency-Key": f"xxiii-{uuid4().hex}",
                },
                content=json.dumps(payload).encode("utf-8"),
            )
    finally:
        app.dependency_overrides.pop(webhooks.stripe_webhook_auth, None)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "authority_refused"
