"""Provider routing for the shipping PayPal refund surface."""

from __future__ import annotations

import asyncio
import os

os.environ.setdefault("TESTING", "1")
os.environ.setdefault(
    "DATABASE_URL", "postgresql://fixture@127.0.0.1:1/fixture"
)
os.environ.setdefault("SKELDIR_CONTROL_PLANE_ENABLED", "0")

from app.api import webhooks  # noqa: E402


def test_paypal_refund_route_conducts_paypal_adjustment(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    async def fake_conduct(**kwargs):
        captured.update(kwargs)
        return {"status": "success"}

    monkeypatch.setattr(webhooks, "_conduct_adjustment_events", fake_conduct)
    result = asyncio.run(
        webhooks.paypal_payment_capture_refunded(
            request=None,
            x_idempotency_key="paypal-refund-key",
            tenant_info={"tenant_id": "tenant"},
        )
    )

    assert result == {"status": "success"}
    assert captured["provider"] == "paypal"
    assert captured["x_idempotency_key"] == "paypal-refund-key"
