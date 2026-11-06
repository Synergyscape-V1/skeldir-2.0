"""B2.6-P2 Corrective XXV-2: provider-amendment decision law.

These cells pin the separation between an unauthorised commerce-identity
collision and a legitimate provider amendment, and the correction kernel's
authority to relink a verdict only to a current amending source that satisfies
the provider's own amendment conditions. They are decision-law cells; the
physical journey is the A2/B10 lane falsifier, not this file.

The properties:

* A source demoted by anything other than a provider amendment (revoked or
  lost evidence) is never a lawful relink target.
* The amending source must be current, over the same tenant/provider/commerce
  identity, with the same currency and event family and a non-earlier event
  instant.
* A non-current verdict remains refused unless exactly that lawful amending
  source is supplied.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from app.revenue_verification.match_engine_kernel import (
    _is_lawful_superseding_amendment_source,
    _require_current_verdict_authority,
)

TENANT = UUID("11111111-2222-3333-4444-555555555555")
OLD_INGRESS = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
NEW_INGRESS = UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
VERDICT = UUID("cccccccc-dddd-eeee-ffff-000000000000")
LATER = datetime(2026, 10, 27, 19, 50, tzinfo=timezone.utc)
EARLIER = datetime(2026, 10, 27, 19, 49, tzinfo=timezone.utc)


class _FakeMappings:
    def __init__(self, row: dict[str, object] | None) -> None:
        self._row = row

    def first(self) -> dict[str, object] | None:
        return self._row


class _FakeResult:
    def __init__(self, row: object) -> None:
        self._row = row

    def mappings(self) -> _FakeMappings:
        return _FakeMappings(self._row)  # type: ignore[arg-type]

    def scalar_one_or_none(self) -> object:
        return self._row


class _SequencedSession:
    def __init__(self, *rows: object) -> None:
        self._rows = list(rows)
        self.statements: list[str] = []

    async def execute(self, statement: object, params: dict | None = None) -> _FakeResult:
        self.statements.append(str(statement))
        if not self._rows:
            raise AssertionError("unexpected query")
        return _FakeResult(self._rows.pop(0))


def _old(
    *,
    reason: str = "superseded_by_provider_amendment:evt_B",
    currency: str = "USD",
    event_reference: str = "evt_A",
    ts: datetime = EARLIER,
) -> dict[str, object]:
    return {
        "b26_p2_demotion_reason": reason,
        "provider_native_event_reference": event_reference,
        "verified_amount_currency": currency,
        "event_timestamp": ts,
    }


def _new(
    *,
    current: bool = True,
    provider: str = "stripe",
    commerce: str = "pi_X",
    currency: str = "USD",
    event_reference: str = "evt_B",
    ts: datetime = LATER,
) -> dict[str, object]:
    return {
        "provider": provider,
        "provider_native_event_reference": event_reference,
        "provider_native_commerce_reference": commerce,
        "verified_amount_currency": currency,
        "event_timestamp": ts,
        "is_current": current,
    }


async def _lawful(
    *,
    old: dict[str, object] | None = None,
    new: dict[str, object] | None = None,
) -> bool:
    session = _SequencedSession(
        _old() if old is None else old,
        _new() if new is None else new,
    )
    return await _is_lawful_superseding_amendment_source(
        session,
        tenant_id=TENANT,
        verdict_provider="stripe",
        verdict_native_commerce_reference="pi_X",
        verdict_canonical_commerce_reference="pi_X",
        old_ingress_id=OLD_INGRESS,
        new_ingress_id=NEW_INGRESS,
    )


@pytest.mark.asyncio
async def test_amendment_accepts_later_same_currency_same_family_current_source() -> None:
    assert await _lawful() is True


@pytest.mark.asyncio
async def test_amendment_refuses_revoked_or_lost_evidence_demotion() -> None:
    assert await _lawful(old=_old(reason="xix-evidence-revoked:loss")) is False


@pytest.mark.asyncio
async def test_amendment_refuses_currency_change() -> None:
    assert await _lawful(new=_new(currency="EUR")) is False


@pytest.mark.asyncio
async def test_amendment_refuses_supersession_that_names_a_different_event() -> None:
    # The demotion reason is the admission evidence; it must name exactly the
    # current amending event, so a cross-family or otherwise unrelated later
    # row cannot be substituted for the amendment the old source recorded.
    assert await _lawful(new=_new(event_reference="evt_C")) is False


@pytest.mark.asyncio
async def test_amendment_refuses_earlier_event_instant() -> None:
    assert await _lawful(new=_new(ts=EARLIER - timedelta(seconds=1))) is False


@pytest.mark.asyncio
async def test_amendment_refuses_non_current_source() -> None:
    assert await _lawful(new=_new(current=False)) is False


@pytest.mark.asyncio
async def test_amendment_refuses_different_commerce_identity() -> None:
    assert await _lawful(new=_new(commerce="pi_OTHER")) is False


async def _guard(
    *,
    state: str,
    current_predicate: bool,
    old: dict[str, object] | None = None,
    new: dict[str, object] | None = None,
    superseding: UUID | None = NEW_INGRESS,
) -> None:
    verdict = {
        "provider": "stripe",
        "provider_native_commerce_reference": "pi_X",
        "canonical_commerce_reference": "pi_X",
        "b26_p2_source_authority_state": state,
        "webhook_ingress_identity_id": OLD_INGRESS,
    }
    rows: list[object] = [verdict]
    if state == "current":
        rows.append(current_predicate)
    elif superseding is not None:
        rows.append(_old() if old is None else old)
        rows.append(_new() if new is None else new)
    session = _SequencedSession(*rows)
    await _require_current_verdict_authority(
        session,
        tenant_id=TENANT,
        match_verdict_id=VERDICT,
        superseding_ingress_id=superseding,
    )


@pytest.mark.asyncio
async def test_guard_allows_lawful_provider_amendment_relink() -> None:
    await _guard(state="historically_unverifiable", current_predicate=False)


@pytest.mark.asyncio
async def test_guard_refuses_demoted_verdict_without_superseding_source() -> None:
    with pytest.raises(ValueError, match="b23_match_verdict_authority_not_current"):
        await _guard(
            state="historically_unverifiable",
            current_predicate=False,
            superseding=None,
        )


@pytest.mark.asyncio
async def test_guard_refuses_revoked_source_even_with_an_ingress_id() -> None:
    with pytest.raises(ValueError, match="b23_match_verdict_authority_not_current"):
        await _guard(
            state="historically_unverifiable",
            current_predicate=False,
            old=_old(reason="xix-evidence-revoked:loss"),
        )


@pytest.mark.asyncio
async def test_guard_still_requires_the_predicate_for_a_current_verdict() -> None:
    with pytest.raises(ValueError, match="b23_match_verdict_authority_not_current"):
        await _guard(state="current", current_predicate=False)
