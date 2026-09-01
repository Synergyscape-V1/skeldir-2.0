from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import Request, Response
from pydantic import ValidationError

from app.api import attribution as attribution_api
from app.attribution.strategy_kernel import LAST_TOUCH_MODEL
from app.schemas.attribution import TouchpointEventRequest
from app.security.auth import AuthContext


REPO_ROOT = Path(__file__).resolve().parents[2]


def _auth_context(tenant_id):
    return AuthContext(
        tenant_id=tenant_id,
        user_id=uuid4(),
        jti=uuid4(),
        issued_at_epoch=int(datetime.now(timezone.utc).timestamp()),
        subject="c19-manager",
        issuer="skeldir-test",
        audience="skeldir-api",
        claims={"scopes": ["manager", "viewer"]},
    )


@pytest.mark.asyncio
async def test_c19_touchpoint_ingress_is_legitimate_and_schedules_last_touch(
    monkeypatch,
) -> None:
    tenant_id = uuid4()
    event_id = uuid4()
    session_id = uuid4()
    occurred_at = datetime.now(timezone.utc) - timedelta(days=20)
    observed: dict[str, object] = {}

    async def fake_ingest(**kwargs):
        observed["ingest"] = kwargs
        return SimpleNamespace(
            status="success",
            is_duplicate=False,
            session_id=str(session_id),
            event=SimpleNamespace(
                id=event_id,
                session_id=session_id,
                channel="google_search_paid",
                occurred_at=occurred_at,
            ),
        )

    def fake_schedule(**kwargs):
        observed["schedule"] = kwargs
        return SimpleNamespace(id="c19-task")

    monkeypatch.setattr(attribution_api, "ingest_with_transaction", fake_ingest)
    monkeypatch.setattr(attribution_api, "schedule_recompute_window", fake_schedule)

    payload = TouchpointEventRequest(
        event_id="collector-event-001",
        event_type="ad_click",
        event_timestamp=occurred_at,
        vendor="google_ads",
        vendor_channel_indicator="SEARCH",
        campaign_id="campaign-c19",
    )
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/attribution/events",
            "headers": [],
        }
    )
    response = Response()
    result = await attribution_api.ingest_attribution_touchpoint(
        payload=payload,
        request=request,
        response=response,
        x_correlation_id=uuid4(),
        auth_context=_auth_context(tenant_id),
    )

    ingest = observed["ingest"]
    assert ingest["tenant_id"] == tenant_id
    assert ingest["source"] == "first_party_touchpoint"
    assert ingest["event_data"]["revenue_amount"] == "0.00"
    assert ingest["event_data"]["event_type"] == "ad_click"
    assert ingest["idempotency_key"] == f"{tenant_id}:collector-event-001"
    schedule = observed["schedule"]
    assert schedule["model_type"] == LAST_TOUCH_MODEL
    assert schedule["session_id"] == str(session_id)
    assert result.channel_code == "google_search_paid"
    assert result.tenant_id == str(tenant_id)
    assert response.status_code == 201


def test_c19_touchpoint_contract_cannot_claim_conversion_or_revenue_authority() -> None:
    with pytest.raises(ValidationError):
        TouchpointEventRequest(
            event_id="forbidden-conversion",
            event_type="purchase",
            event_timestamp=datetime.now(timezone.utc),
            vendor="google_ads",
            vendor_channel_indicator="SEARCH",
        )

    contract = (
        REPO_ROOT / "api-contracts/openapi/v1/attribution.yaml"
    ).read_text(encoding="utf-8")
    surface = contract.split("/api/attribution/events:", 1)[1].split(
        "/api/attribution/revenue/realtime:", 1
    )[0]
    assert "conversion_authority_forbidden: true" in surface
    assert "revenue_authority_forbidden: true" in surface
    assert "accessBearerAuth: [\"manager\"]" in surface


def test_c19_terminal_preflight_lease_reopens_on_later_dirty_truth() -> None:
    source = (REPO_ROOT / "backend/app/bayesian/preflight_lease.py").read_text(
        encoding="utf-8"
    )
    assert "terminal_reopen" in source
    assert '"fallback_only"' in source
    assert "if stale or terminal_reopen" in source
