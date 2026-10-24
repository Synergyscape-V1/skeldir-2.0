"""XXIV (A2/B10): the shipping correction caller is present."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api import reconciliation, revenue_verification
from app.db.deps import get_db_session
from app.main import app
from app.revenue_verification.corrections import (
    CorrectionEvidence,
    CorrectionEvidenceError,
)
from app.security.auth import AuthContext, get_auth_context
from app.tasks import revenue_verification as revenue_tasks


class _ScalarResult:
    def scalar_one(self) -> int:
        return 1000


class _FakeSession:
    async def execute(self, *_args, **_kwargs) -> _ScalarResult:
        return _ScalarResult()


def _auth_context() -> AuthContext:
    return AuthContext(
        tenant_id=UUID("22222222-2222-4222-8222-222222222222"),
        user_id=uuid4(),
        jti=uuid4(),
        issued_at_epoch=0,
        subject=None,
        issuer=None,
        audience=None,
        claims={},
    )


async def _fake_db_session():
    yield _FakeSession()


async def _fake_evidence(*_args, **_kwargs) -> CorrectionEvidence:
    return CorrectionEvidence(
        provider="stripe",
        event_type="payment_capture",
        provider_native_event_reference="evt-corr-1",
        provider_native_commerce_reference="pi_1",
        amount_minor=1200,
        currency_code="USD",
        event_occurred_at=datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc),
        is_gross_capture_correction=True,
    )


def test_reconciliation_reader_uses_sovereign_provider_authority() -> None:
    assert (
        reconciliation._map_source_to_platform_key("woocommerce")
        == "woocommerce"
    )
    assert reconciliation._map_source_to_platform_key("woo") is None
    assert reconciliation._map_source_to_platform_key("woo_commerce") is None


@pytest.mark.asyncio
async def test_candidate_receipt_reaches_all_four_dispositions() -> None:
    now = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)
    app.dependency_overrides[get_auth_context] = _auth_context
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            cases = [
                (
                    {"provider_raw": "stripe", "source_reference": "pi_1"},
                    "SUPPORTED_AND_IN_SCOPE",
                ),
                (
                    {"provider_raw": "stripe", "source_reference": None},
                    "SUPPORTED_BUT_UNRESOLVED",
                ),
                (
                    {"provider_raw": "stripe", "currency_raw": "EUR"},
                    "EXPLICITLY_EXCLUDED",
                ),
                ({"provider_raw": ""}, "INVALID_OR_REFUSED"),
            ]
            observed = []
            for overrides, expected in cases:
                body = {
                    "provider_raw": overrides.get("provider_raw", "stripe"),
                    "currency_raw": overrides.get("currency_raw", "USD"),
                    "event_time": now.isoformat(),
                    "window_start": now.replace(hour=0).isoformat(),
                    "window_end": now.replace(hour=23, minute=59).isoformat(),
                    "scope_policy_version": "b2.6-p2-scope-policy-v2",
                    "source_reference": overrides.get(
                        "source_reference", "pi_1"
                    ),
                    "source_verified_gross_amount_minor": 1000,
                }
                response = await client.post(
                    "/api/reconciliation/candidates/classify",
                    headers={"X-Correlation-ID": str(uuid4())},
                    json=body,
                )
                assert response.status_code == 200, response.text
                observed.append(response.json()["disposition"])
                assert response.json()["disposition"] == expected
            assert observed == [
                "SUPPORTED_AND_IN_SCOPE",
                "SUPPORTED_BUT_UNRESOLVED",
                "EXPLICITLY_EXCLUDED",
                "INVALID_OR_REFUSED",
            ]
    finally:
        app.dependency_overrides.pop(get_auth_context, None)


@pytest.mark.asyncio
async def test_correction_route_enqueues_worker_with_authenticated_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}

    def _capture(**kwargs) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(
        revenue_verification,
        "resolve_correction_evidence",
        _fake_evidence,
    )

    class _FakeSource:
        canonical_net_verified_amount_minor = 1000

    async def _fake_source(*_args, **_kwargs) -> _FakeSource:
        return _FakeSource()

    monkeypatch.setattr(
        revenue_verification,
        "read_match_verdict_source",
        _fake_source,
    )
    monkeypatch.setattr(
        revenue_tasks.register_b23_post_capture_correction_task,
        "apply_async",
        _capture,
    )
    app.dependency_overrides[get_auth_context] = _auth_context
    app.dependency_overrides[get_db_session] = _fake_db_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/reconciliation/match-verdicts/"
                "11111111-1111-4111-8111-111111111111/corrections",
                headers={"X-Correlation-ID": str(uuid4())},
                json={
                    "provider": "stripe",
                    "event_type": "payment_capture",
                    "provider_native_event_reference": "evt-corr-1",
                    "is_gross_capture_correction": True,
                },
            )
    finally:
        app.dependency_overrides.pop(get_auth_context, None)
        app.dependency_overrides.pop(get_db_session, None)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "accepted"
    assert body["match_verdict_id"] == "11111111-1111-4111-8111-111111111111"
    assert captured["queue"] == "b23_match_engine"
    assert captured["args"][:6] == [
        "22222222-2222-4222-8222-222222222222",
        "11111111-1111-4111-8111-111111111111",
        "stripe",
        "payment_capture",
        "evt-corr-1",
        True,
    ]
    assert UUID(captured["args"][6])


@pytest.mark.asyncio
async def test_correction_route_refuses_unresolved_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _unresolved(*_args, **_kwargs):
        raise CorrectionEvidenceError("correction_source_authority_unresolved")

    monkeypatch.setattr(
        revenue_verification,
        "resolve_correction_evidence",
        _unresolved,
    )
    app.dependency_overrides[get_auth_context] = _auth_context
    app.dependency_overrides[get_db_session] = _fake_db_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/reconciliation/match-verdicts/"
                "11111111-1111-4111-8111-111111111111/corrections",
                headers={"X-Correlation-ID": str(uuid4())},
                json={
                    "provider": "stripe",
                    "event_type": "payment_capture",
                    "provider_native_event_reference": "evt-corr-1",
                    "is_gross_capture_correction": True,
                },
            )
    finally:
        app.dependency_overrides.pop(get_auth_context, None)
        app.dependency_overrides.pop(get_db_session, None)
    assert response.status_code == 409
    assert response.json()["detail"] == "correction_source_authority_unresolved"
