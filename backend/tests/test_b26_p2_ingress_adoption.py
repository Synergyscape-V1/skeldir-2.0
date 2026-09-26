"""B2.6-P2 Corrective VIII authenticated-root adoption unit law.

Pure unit tests (no DB, broker, or network): the sovereign comparison set,
the adoption error classifier, and the promote/adopt/refuse decision table
of the API-path promotion helper (mocked session). Database-plane behavior
(trigger refusal, custody, gate binding) is proven separately by the live
VIII battery against real principals.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.ingestion.event_service import (  # noqa: E402
    ValidationError,
    _adopt_or_promote_ingress,
    _ingress_sovereign_mismatch,
    _is_b26_p2_adoption_error,
    _is_ingress_collision_integrity_error,
)

pytestmark = pytest.mark.unit_pure

DAY_NOON = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)


def _incoming(**overrides):
    base = {
        "tenant_id": "11111111-2222-3333-4444-555555555555",
        "idempotency_key": "viii:unit",
        "provider": "stripe",
        "provider_native_event_reference": "evt",
        "provider_native_commerce_reference": "ord",
        "normalized_commerce_reference_kind": "order_reference",
        "normalized_commerce_reference_value": "ord",
        "verified_amount_minor": 100,
        "verified_amount_currency": "USD",
        "event_timestamp": DAY_NOON,
        "verified_commerce_ingress_state": "authenticity_verified",
        "verified_amount_scale": 2,
        "verified_at": DAY_NOON,
    }
    base.update(overrides)
    return base


def _existing(state="authenticity_verified", **overrides):
    row = SimpleNamespace(
        id=uuid4(),
        tenant_id="11111111-2222-3333-4444-555555555555",
        idempotency_key="viii:unit",
        provider="stripe",
        provider_native_event_reference="evt",
        provider_native_commerce_reference="ord",
        normalized_commerce_reference_kind="order_reference",
        normalized_commerce_reference_value="ord",
        verified_amount_minor=100,
        verified_amount_currency="USD",
        event_timestamp=DAY_NOON,
        verified_commerce_ingress_state=state,
    )
    for key, value in overrides.items():
        setattr(row, key, value)
    return row


def test_sovereign_match_is_not_mismatch():
    assert _ingress_sovereign_mismatch(_existing(), _incoming()) is False


def test_sovereign_mismatch_each_field():
    for field, bad in (
        ("provider", "paypal"),
        ("verified_amount_currency", "EUR"),
        ("verified_amount_minor", 999),
        ("event_timestamp", datetime(2026, 1, 16, 8, tzinfo=timezone.utc)),
        ("provider_native_event_reference", "other"),
        ("provider_native_commerce_reference", "other"),
        ("normalized_commerce_reference_kind", "other"),
        ("normalized_commerce_reference_value", "other"),
    ):
        assert _ingress_sovereign_mismatch(_existing(**{field: bad}), _incoming()) is True


def test_naive_datetime_treated_as_utc():
    row = _existing(event_timestamp=DAY_NOON.replace(tzinfo=None))
    assert _ingress_sovereign_mismatch(row, _incoming()) is False


def test_adoption_error_classifier():
    assert _is_b26_p2_adoption_error(
        Exception("b26_p2_ingress_precursor_present_promote_required")
    ) == "promote_required"
    assert _is_b26_p2_adoption_error(
        Exception("B26_P2_INGRESS_AUTHENTICATED_CONFLICT")
    ) == "authenticated_conflict"
    assert _is_b26_p2_adoption_error(Exception("23505 duplicate")) is None


def test_collision_classifier_constraints():
    from sqlalchemy.exc import IntegrityError

    class _Diag:
        constraint_name = "uq_webhook_ingress_identities_tenant_idempotency"

    class _Orig(Exception):
        pgcode = "23505"
        diag = _Diag()

    err = IntegrityError("stmt", {}, _Orig())
    assert _is_ingress_collision_integrity_error(err) is True

    class _Other(Exception):
        pass

    assert _is_ingress_collision_integrity_error(_Other("nope")) is False


def _session_with(existing):
    session = AsyncMock()
    scalars = SimpleNamespace(one_or_none=lambda: existing)
    result = SimpleNamespace(scalars=lambda: scalars)
    session.execute.return_value = result
    return session


@pytest.mark.asyncio
async def test_promote_pending_precursor_to_authenticated():
    tenant = uuid4()
    precursor = _existing("pending", verified_amount_minor=1)
    session = _session_with(precursor)
    incoming = _incoming()
    incoming["tenant_id"] = str(tenant)
    precursor.tenant_id = str(tenant)
    event_id = uuid4()
    adopted = await _adopt_or_promote_ingress(
        session, tenant_id=tenant, incoming=incoming, event_id=event_id
    )
    assert adopted is precursor
    assert precursor.verified_amount_minor == 100
    assert precursor.verified_commerce_ingress_state == "authenticity_verified"
    assert precursor.event_id == event_id


@pytest.mark.asyncio
async def test_verified_mismatch_raises_dlq():
    tenant = uuid4()
    root = _existing("authenticity_verified", verified_amount_minor=1)
    session = _session_with(root)
    incoming = _incoming()
    incoming["tenant_id"] = str(tenant)
    root.tenant_id = str(tenant)
    with pytest.raises(ValidationError, match="authenticated_conflict"):
        await _adopt_or_promote_ingress(
            session, tenant_id=tenant, incoming=incoming, event_id=uuid4()
        )


@pytest.mark.asyncio
async def test_verified_exact_match_adopts_binding(monkeypatch):
    # Hermetic: no ingress DSN in unit scope, so attestation falls
    # back to the caller session (admins/tests path). Production
    # mounts B26_P2_INGRESS_DATABASE_URL and takes the ingress
    # credential branch instead. Corrective XII: the re-ingestion
    # carries the HMAC-established predecessor consequence, so no
    # consequence lookup query is issued on this path.
    monkeypatch.delenv("B26_P2_INGRESS_DATABASE_URL", raising=False)
    tenant = uuid4()
    root = _existing("authenticity_verified")
    session = _session_with(root)
    incoming = _incoming()
    incoming["tenant_id"] = str(tenant)
    root.tenant_id = str(tenant)
    event_id = uuid4()
    adopted = await _adopt_or_promote_ingress(
        session, tenant_id=tenant, incoming=incoming, event_id=event_id,
        auth_consequence={
            "provider": "stripe",
            "provider_event_reference": "evt",
            "body_sha256": "c" * 64,
        },
    )
    assert adopted is root
    assert root.event_id == event_id
    # Corrective X: a genuine signed duplicate records provenance
    # evidence through the attester (never a bare status write).
    assert session.execute.await_count == 2
    attester_call = session.execute.await_args_list[1]
    assert "b26_p2_attest_provenance_evidence" in str(
        attester_call.args[0]
    )


@pytest.mark.asyncio
async def test_no_collision_returns_none():
    session = _session_with(None)
    adopted = await _adopt_or_promote_ingress(
        session, tenant_id=uuid4(), incoming=_incoming(), event_id=uuid4()
    )
    assert adopted is None
