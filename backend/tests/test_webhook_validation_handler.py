from __future__ import annotations

from contextlib import asynccontextmanager
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.exceptions import RequestValidationError
from starlette.requests import Request

from app.api import webhook_validation


def _request(path: str, headers: list[tuple[bytes, bytes]] | None = None) -> Request:
    async def receive():
        return {"type": "http.request", "body": b'{"broken":', "more_body": False}

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": b"",
        "headers": headers or [],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }
    req = Request(scope, receive)
    req.state.original_body = b'{"broken":'
    return req


def _validation_error() -> RequestValidationError:
    return RequestValidationError(
        [
            {
                "type": "json_invalid",
                "loc": ("body", 0),
                "msg": "JSON decode error",
                "input": "{broken",
            }
        ]
    )


@pytest.mark.asyncio
async def test_non_webhook_validation_uses_default_422():
    request = _request("/api/auth/login")
    response = await webhook_validation.handle_request_validation_error(request, _validation_error())
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_webhook_validation_missing_tenant_key_returns_401():
    request = _request("/api/webhooks/stripe/payment_intent/succeeded")
    response = await webhook_validation.handle_request_validation_error(request, _validation_error())
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_webhook_validation_routes_to_dlq(monkeypatch: pytest.MonkeyPatch):
    tenant_id = uuid4()
    dead_event_id = uuid4()

    async def fake_get_tenant(_api_key: str):
        return {"tenant_id": tenant_id}

    @asynccontextmanager
    async def fake_get_session(*, tenant_id):  # noqa: ANN001 - signature parity
        assert tenant_id is not None
        yield object()

    class _FakeDLQ:
        async def route_to_dlq(self, **kwargs):  # noqa: ANN003 - test double
            assert kwargs["tenant_id"] == tenant_id
            assert kwargs["source"] == "stripe"
            return SimpleNamespace(id=dead_event_id)

    monkeypatch.setattr(webhook_validation, "get_tenant_with_webhook_secrets", fake_get_tenant)
    monkeypatch.setattr(webhook_validation, "get_session", fake_get_session)
    monkeypatch.setattr(webhook_validation, "DLQHandler", lambda: _FakeDLQ())

    request = _request(
        "/api/webhooks/stripe/payment_intent/succeeded",
        headers=[(b"x-skeldir-tenant-key", b"tenant-key")],
    )
    response = await webhook_validation.handle_request_validation_error(request, _validation_error())
    assert response.status_code == 200
    payload = json.loads(response.body)
    assert payload["status"] == "dlq_routed"
    assert payload["dead_event_id"] == str(dead_event_id)
