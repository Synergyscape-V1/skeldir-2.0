"""XXV coverage must bind the signed source to the selected provider/time/scope."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.core.config import settings
from app.revenue_verification import source_attestation as sa
from app.revenue_verification.verification_coverage import (
    fetch_verification_coverage_aggregate,
)

TENANT = "11111111-2222-3333-4444-555555555555"
INGRESS = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
UNIVERSE = "99999999-8888-7777-6666-555555555555"


class _Rows:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows

    def mappings(self) -> _Rows:
        return self

    def all(self) -> list[dict[str, object]]:
        return self.rows


class _Scalar:
    def __init__(self, value: object) -> None:
        self.value = value

    def scalar_one_or_none(self) -> object:
        return self.value


class _Session:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows

    async def execute(self, statement: object, params: dict | None = None) -> object:
        if "b26_p2_authority_universe" in str(statement):
            return _Scalar(UNIVERSE)
        return _Rows(self.rows)


def _statement(*, provider: str, event_timestamp: str) -> tuple[dict, str]:
    statement = sa.build_statement(
        tenant_id=TENANT,
        webhook_ingress_identity_id=INGRESS,
        provider=provider,
        provider_native_event_reference="pi_1",
        provider_native_commerce_reference="pi_1",
        normalized_commerce_reference_kind="provider_native",
        normalized_commerce_reference_value="pi_1",
        verified_amount_minor=4321,
        verified_amount_currency="USD",
        verified_amount_scale=2,
        event_timestamp=event_timestamp,
        body_sha256="a" * 64,
        authority_universe=UNIVERSE,
    )
    return statement, ""


def _row(statement: dict, signature: str, *, provider: str, occurred: datetime) -> dict:
    return {
        "ingress_id": INGRESS,
        "provider": provider,
        "currency_code": "USD",
        "ingress_amount": 4321,
        "ingress_scale": 2,
        "ingress_event_reference": "pi_1",
        "ingress_commerce_reference": "pi_1",
        "ingress_normalized_kind": "provider_native",
        "ingress_normalized_value": "pi_1",
        "occurred_at": occurred,
        "demotion_reason": None,
        "consequence_body_sha256": "a" * 64,
        "statement": json.dumps(statement),
        "signature": signature,
        "attested_amount": 4321,
        "attested_currency": "USD",
        "root_authenticated": True,
        "verdict_id": None,
        "verdict_status": None,
        "verdict_authority_state": None,
        "verdict_currency": None,
    }


@pytest.mark.asyncio
async def test_coverage_rejects_signed_stripe_evidence_selected_as_paypal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    private_seed, public_b64 = sa.generate_keypair()
    private_path = tmp_path / "attest.key"
    public_path = tmp_path / "attest.pub"
    private_path.write_text(private_seed, encoding="utf-8")
    public_path.write_text(public_b64, encoding="utf-8")
    monkeypatch.setattr(
        settings, "B26_P2_SOURCE_ATTESTATION_REQUIRED", True, raising=False
    )
    monkeypatch.setattr(
        settings, "B26_P2_SOURCE_ATTESTATION_PUBLIC_KEY_PATH", str(public_path)
    )
    statement, _ = _statement(
        provider="stripe", event_timestamp="2026-10-01T16:00:00Z"
    )
    signature, _ = sa.sign_statement(statement, private_key_path=str(private_path))
    row = _row(
        statement,
        signature,
        provider="paypal",
        occurred=datetime(2026, 10, 28, 16, tzinfo=timezone.utc),
    )
    aggregate = await fetch_verification_coverage_aggregate(
        _Session([row]),
        tenant_id=TENANT,
        window_start=datetime(2026, 10, 1, tzinfo=timezone.utc),
        window_end=datetime(2026, 10, 29, tzinfo=timezone.utc),
    )
    assert aggregate.connected_platform_revenue_minor == 0
    assert aggregate.matched_webhook_revenue_minor == 0
    assert aggregate.unverifiable_attestation_revenue_minor == 4321


@pytest.mark.asyncio
async def test_coverage_rejects_signed_october_one_evidence_as_october_28(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    private_seed, public_b64 = sa.generate_keypair()
    private_path = tmp_path / "attest.key"
    public_path = tmp_path / "attest.pub"
    private_path.write_text(private_seed, encoding="utf-8")
    public_path.write_text(public_b64, encoding="utf-8")
    monkeypatch.setattr(
        settings, "B26_P2_SOURCE_ATTESTATION_REQUIRED", True, raising=False
    )
    monkeypatch.setattr(
        settings, "B26_P2_SOURCE_ATTESTATION_PUBLIC_KEY_PATH", str(public_path)
    )
    statement, _ = _statement(
        provider="stripe", event_timestamp="2026-10-01T16:00:00Z"
    )
    signature, _ = sa.sign_statement(statement, private_key_path=str(private_path))
    row = _row(
        statement,
        signature,
        provider="stripe",
        occurred=datetime(2026, 10, 28, 16, tzinfo=timezone.utc),
    )
    aggregate = await fetch_verification_coverage_aggregate(
        _Session([row]),
        tenant_id=TENANT,
        window_start=datetime(2026, 10, 1, tzinfo=timezone.utc),
        window_end=datetime(2026, 10, 29, tzinfo=timezone.utc),
    )
    assert aggregate.connected_platform_revenue_minor == 0
    assert aggregate.matched_webhook_revenue_minor == 0
    assert aggregate.unverifiable_attestation_revenue_minor == 4321
