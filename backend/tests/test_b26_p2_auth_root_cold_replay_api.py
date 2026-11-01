"""Cold concurrent replays through the auth-root ASGI surface do not scan history."""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest

from app.auth_service import server
from app.core.config import settings
from app.revenue_verification.source_evidence_journal import (
    _COMMITTED_FACT_CACHE,
    _COMMITTED_FACT_CACHE_LOCK,
    append_source_fact,
)


class _FakeSession:
    def __init__(self, ingress_id: str) -> None:
        self.ingress_id = ingress_id

    async def execute(self, *_args, **_kwargs):
        class _Mappings:
            def one_or_none(self_inner):
                return {"iid": self.ingress_id}

        class _Result:
            def mappings(self_inner):
                return _Mappings()

            def scalar(self_inner):
                return 1

        return _Result()


@contextlib.asynccontextmanager
async def _fake_session_context(_tenant, _key):
    yield _FakeSession("11111111-2222-3333-4444-555555555555")


@contextlib.asynccontextmanager
async def _fake_boundary():
    yield


@pytest.mark.asyncio
async def test_concurrent_cold_replays_through_auth_root_surface(tmp_path, monkeypatch) -> None:
    journal = tmp_path / "source.jsonl"
    for index in range(500):
        append_source_fact(
            fact_kind="source_money",
            fact_id=f"retained-{index}",
            tenant_id="tenant-retained",
            verdict_id="",
            statement={"id": f"retained-{index}"},
            signature="sig",
            key_sha256="k",
            database_transaction_id=f"retained-{index}",
            path=journal,
        )
    with _COMMITTED_FACT_CACHE_LOCK:
        _COMMITTED_FACT_CACHE.clear()

    tenant_id = uuid4()
    tenant_info = {
        "tenant_id": str(tenant_id),
        "stripe_webhook_secret": "ignored-by-fake-verifier",
    }

    async def _tenant_info(_api_key):
        return tenant_info

    from app.api import webhooks as webhooks_module
    from app.core import tenant_context
    from app.webhooks import commerce_derivation

    monkeypatch.setattr(server, "_require_auth_role", lambda: None)
    monkeypatch.setattr(server, "_ingress_session_with_source_outcomes", _fake_session_context)
    monkeypatch.setattr(server, "_source_money_attestation_exists", AsyncMock(return_value=True))
    monkeypatch.setattr(server, "_write_source_money_attestation", AsyncMock())
    monkeypatch.setattr(webhooks_module, "WEBHOOK_VERIFIERS", {"stripe": ("stripe_webhook_secret", lambda *_a: True)})
    monkeypatch.setattr(tenant_context, "get_tenant_with_webhook_secrets", _tenant_info)
    monkeypatch.setattr(commerce_derivation, "binding_mismatches", lambda **_kwargs: [])
    monkeypatch.setattr(
        commerce_derivation,
        "derive_event_family",
        lambda *_args, **_kwargs: "purchase",
    )
    monkeypatch.setattr(
        commerce_derivation,
        "derive_event_family_source",
        lambda *_args, **_kwargs: "body",
    )
    derived = SimpleNamespace(
        verified_amount_minor=1000,
        verified_amount_currency="USD",
        verified_amount_scale=2,
        provider_native_event_reference="evt_cold",
        provider_native_commerce_reference="pi_cold",
        normalized_commerce_reference_kind="payment_intent_id",
        normalized_commerce_reference_value="pi_cold",
        event_timestamp="2026-01-01T00:00:00Z",
    )
    monkeypatch.setattr(commerce_derivation, "derive_commerce", lambda *_a, **_k: derived)
    monkeypatch.setattr(
        commerce_derivation,
        "derive_shopify_lifecycle",
        lambda *_a, **_k: SimpleNamespace(
            financial_status="paid",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        ),
    )
    from app.db import session as db_session

    monkeypatch.setattr(db_session, "assert_api_ingress_isolation", lambda: None)
    monkeypatch.setattr(db_session, "_ingress_boundary", _fake_boundary)
    from app.core import construction_authority

    monkeypatch.setattr(
        construction_authority,
        "read_construction_revisions",
        AsyncMock(return_value={}),
    )
    monkeypatch.setattr(
        construction_authority,
        "assert_production_construction_authority",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(settings, "B26_P2_SOURCE_EVIDENCE_JOURNAL_PATH", str(journal))
    monkeypatch.setattr(settings, "B26_P2_SOURCE_ATTESTATION_REQUIRED", True)
    monkeypatch.setattr(settings, "B26_P2_SOURCE_ATTESTATION_PRIVATE_KEY_PATH", None)

    from app.revenue_verification import source_evidence_journal as journal_module

    def _must_not_scan(*_args, **_kwargs):
        raise AssertionError("auth-root replay scanned retained journal history")

    monkeypatch.setattr(journal_module, "resolve_source_facts", _must_not_scan)

    raw_body = json.dumps({"id": "evt_cold", "amount": 1000}).encode("utf-8")
    request = {
        "api_key": "cold-replay-key",
        "provider": "stripe",
        "provider_event_reference": "evt_cold",
        "raw_body_b64": base64.b64encode(raw_body).decode("ascii"),
        "signature_header": "t=1,v1=fake",
        "event_id": str(uuid4()),
        "idempotency_key": "cold-replay",
        "provider_native_commerce_reference": "pi_cold",
        "normalized_commerce_reference_kind": "payment_intent_id",
        "normalized_commerce_reference_value": "pi_cold",
        "verified_amount_minor": 1000,
        "verified_amount_currency": "USD",
        "verified_amount_scale": 2,
        "event_timestamp": "2026-01-01T00:00:00Z",
    }

    transport = httpx.ASGITransport(app=server.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://auth") as client:
        responses = await asyncio.gather(
            *[
                client.post("/v1/authenticate-ingress", json=request)
                for _ in range(20)
            ]
        )
    assert [response.status_code for response in responses] == [200] * 20
    assert all(
        response.json()["provenance_status"] == "authenticated_known"
        for response in responses
    )
