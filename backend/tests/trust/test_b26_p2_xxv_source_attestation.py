"""B2.6-P2 Corrective XXV: sovereign source-money attestation — unit cells.

The physical RED for the class these cells govern is falsifier
``xxv-hb03-predecessor-escape`` (executed on the production-equivalent
lane). These cells pin the *decision law* so a later revision cannot
quietly reintroduce an owner-granted exemption, and they are deliberately
written against a fake session: they assert what the reader DECIDES, not
what a particular database happens to contain.

XXV (A6/A10, class closure): the absence of an attestation is never a grant.
A revision of this module granted a "predecessor generation" exemption to a
row with no attestation whose creation time preceded a watermark instant read
from a table the maintenance principal owns. The maintenance principal can
delete the authentication root's attestation row, move that watermark and
rewrite the row's ``created_at``, so the exemption was an owner-controlled
bypass of the only authority the database frame cannot forge. It was
demonstrated physically: the unsigned reader served a coherently forged
amount as ``current`` while the mandatory composition proof printed PASS.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.core.config import settings
from app.revenue_verification import source_attestation as sa


TENANT = "11111111-2222-3333-4444-555555555555"
INGRESS = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


class _FakeMappings:
    def __init__(self, row: dict[str, object] | None) -> None:
        self._row = row

    def one_or_none(self) -> dict[str, object] | None:
        return self._row

    def all(self) -> list[dict[str, object]]:
        return []


class _FakeResult:
    def __init__(self, row: dict[str, object] | None) -> None:
        self._row = row

    def mappings(self) -> _FakeMappings:
        return _FakeMappings(self._row)

    def first(self) -> tuple | None:
        return None if self._row is None else tuple(self._row.values())

    def scalar_one_or_none(self) -> object | None:
        return None if self._row is None else self._row.get("current_universe")


class _FakeSession:
    """Returns one row for the verdict/source query and nothing else."""

    def __init__(self, row: dict[str, object] | None) -> None:
        self.row = row
        self.statements: list[str] = []

    async def execute(self, statement: object, params: dict | None = None) -> _FakeResult:
        self.statements.append(str(statement))
        return _FakeResult(self.row)


def _row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "verdict_net": 4321,
        "verdict_captured": 4321,
        "verdict_verified": 4321,
        "verdict_currency": "USD",
        "verdict_provider": "stripe",
        "verdict_event_reference": "pi_1",
        "verdict_commerce_reference": "pi_1",
        "ingress_id": INGRESS,
        "ingress_amount": 4321,
        "ingress_currency": "USD",
        "ingress_scale": 2,
        "ingress_provider": "stripe",
        "ingress_event_reference": "pi_1",
        "ingress_commerce_reference": "pi_1",
        "ingress_normalized_kind": "provider_native",
        "ingress_normalized_value": "pi_1",
        "ingress_event_timestamp": datetime(2026, 10, 27, 16, tzinfo=timezone.utc),
        "consequence_body_sha256": "a" * 64,
        "current_universe": "99999999-8888-7777-6666-555555555555",
        "ingress_created_at": "2026-10-27T16:00:00Z",
        "statement": None,
        "signature": None,
        "attested_amount": None,
        "attested_currency": None,
        "key_sha256": None,
        "consequence_recorded_by": "app_ingress",
    }
    row.update(overrides)
    return row


@pytest.fixture(autouse=True)
def _attestation_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        settings, "B26_P2_SOURCE_ATTESTATION_REQUIRED", True, raising=False
    )


@pytest.mark.asyncio
async def test_missing_attestation_is_never_a_grant() -> None:
    """The absence of an attestation is `unverifiable`, whatever the age.

    This is the cell that keeps the class closed. A revision that granted a
    predecessor-generation exemption here — for instance by comparing the
    row's creation time with an owner-written watermark — would let the
    maintenance principal convert a deleted attestation into currency.
    """
    session = _FakeSession(_row())
    status = await sa.read_verdict_source_attestation_status(
        session, tenant_id=TENANT, verdict_id="verdict-1"
    )
    assert status.status == "unverifiable:attestation_missing"
    assert status.unverifiable is True
    assert status.attested is False


@pytest.mark.asyncio
async def test_no_reader_query_compares_a_timestamp_with_an_owner_written_instant() -> None:
    """The reader must not consult any instant the maintenance principal owns.

    The reader issues exactly one query, and that query must not read an
    epoch, a watermark or any other row-comparable instant.
    """
    session = _FakeSession(_row())
    await sa.read_verdict_source_attestation_status(
        session, tenant_id=TENANT, verdict_id="verdict-1"
    )
    assert len(session.statements) == 1
    joined = " ".join(session.statements).lower()
    for banned in (
        "attestation_required_from",
        "attestation_watermark",
        "source_attestation_authority",
    ):
        assert banned not in joined


def test_the_reader_module_exposes_no_watermark_reader() -> None:
    """No symbol may re-open the owner-written-instant seam."""
    assert not hasattr(sa, "attestation_watermark")
    source = Path(sa.__file__).read_text(encoding="utf-8")
    assert "attestation_required_from" not in source
    assert "def attestation_watermark" not in source


@pytest.mark.asyncio
async def test_a_valid_signature_over_the_provider_amount_is_attested(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The positive half: a signed statement over the amount is attested."""
    private_seed, public_b64 = sa.generate_keypair()
    private_path = tmp_path / "attest.key"
    public_path = tmp_path / "attest.pub"
    private_path.write_text(private_seed, encoding="utf-8")
    public_path.write_text(public_b64, encoding="utf-8")
    monkeypatch.setattr(
        settings, "B26_P2_SOURCE_ATTESTATION_PUBLIC_KEY_PATH", str(public_path)
    )

    statement = sa.build_statement(
        tenant_id=TENANT,
        webhook_ingress_identity_id=INGRESS,
        provider="stripe",
        provider_native_event_reference="pi_1",
        provider_native_commerce_reference="pi_1",
        normalized_commerce_reference_kind="provider_native",
        normalized_commerce_reference_value="pi_1",
        verified_amount_minor=4321,
        verified_amount_currency="USD",
        verified_amount_scale=2,
        event_timestamp="2026-10-27T16:00:00Z",
        body_sha256="a" * 64,
        authority_universe="99999999-8888-7777-6666-555555555555",
    )
    signature, _fingerprint = sa.sign_statement(
        statement, private_key_path=str(private_path)
    )
    session = _FakeSession(
        _row(
            statement=json.dumps(statement),
            signature=signature,
            attested_amount=4321,
            attested_currency="USD",
        )
    )
    status = await sa.read_verdict_source_attestation_status(
        session, tenant_id=TENANT, verdict_id="verdict-1"
    )
    assert status.status == sa.STATUS_ATTESTED
    assert status.attested is True
    assert status.unverifiable is False
    assert status.attested_amount_minor == 4321
    assert status.attested_currency == "USD"


@pytest.mark.asyncio
async def test_a_valid_signature_does_not_authorize_a_different_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    private_seed, public_b64 = sa.generate_keypair()
    private_path = tmp_path / "attest.key"
    public_path = tmp_path / "attest.pub"
    private_path.write_text(private_seed, encoding="utf-8")
    public_path.write_text(public_b64, encoding="utf-8")
    monkeypatch.setattr(
        settings, "B26_P2_SOURCE_ATTESTATION_PUBLIC_KEY_PATH", str(public_path)
    )
    statement = sa.build_statement(
        tenant_id=TENANT,
        webhook_ingress_identity_id=INGRESS,
        provider="stripe",
        provider_native_event_reference="pi_1",
        provider_native_commerce_reference="pi_1",
        normalized_commerce_reference_kind="provider_native",
        normalized_commerce_reference_value="pi_1",
        verified_amount_minor=4321,
        verified_amount_currency="USD",
        verified_amount_scale=2,
        event_timestamp="2026-10-01T16:00:00Z",
        body_sha256="a" * 64,
        authority_universe="99999999-8888-7777-6666-555555555555",
    )
    signature, _fingerprint = sa.sign_statement(
        statement, private_key_path=str(private_path)
    )
    session = _FakeSession(
        _row(
            statement=json.dumps(statement),
            signature=signature,
            attested_amount=4321,
            attested_currency="USD",
            ingress_provider="paypal",
        )
    )
    status = await sa.read_verdict_source_attestation_status(
        session, tenant_id=TENANT, verdict_id="verdict-1"
    )
    assert status.unverifiable is True
    assert status.reason == "attestation_provider_mismatch"


@pytest.mark.asyncio
async def test_a_valid_signature_does_not_authorize_a_different_event_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    private_seed, public_b64 = sa.generate_keypair()
    private_path = tmp_path / "attest.key"
    public_path = tmp_path / "attest.pub"
    private_path.write_text(private_seed, encoding="utf-8")
    public_path.write_text(public_b64, encoding="utf-8")
    monkeypatch.setattr(
        settings, "B26_P2_SOURCE_ATTESTATION_PUBLIC_KEY_PATH", str(public_path)
    )
    statement = sa.build_statement(
        tenant_id=TENANT,
        webhook_ingress_identity_id=INGRESS,
        provider="stripe",
        provider_native_event_reference="pi_1",
        provider_native_commerce_reference="pi_1",
        normalized_commerce_reference_kind="provider_native",
        normalized_commerce_reference_value="pi_1",
        verified_amount_minor=4321,
        verified_amount_currency="USD",
        verified_amount_scale=2,
        event_timestamp="2026-10-01T16:00:00Z",
        body_sha256="a" * 64,
        authority_universe="99999999-8888-7777-6666-555555555555",
    )
    signature, _fingerprint = sa.sign_statement(
        statement, private_key_path=str(private_path)
    )
    session = _FakeSession(
        _row(
            statement=json.dumps(statement),
            signature=signature,
            attested_amount=4321,
            attested_currency="USD",
            ingress_event_timestamp=datetime(2026, 10, 28, 16, tzinfo=timezone.utc),
        )
    )
    status = await sa.read_verdict_source_attestation_status(
        session, tenant_id=TENANT, verdict_id="verdict-1"
    )
    assert status.unverifiable is True
    assert status.reason == "attestation_event_timestamp_mismatch"


@pytest.mark.asyncio
async def test_a_valid_signature_does_not_authorize_a_different_universe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    private_seed, public_b64 = sa.generate_keypair()
    private_path = tmp_path / "attest.key"
    public_path = tmp_path / "attest.pub"
    private_path.write_text(private_seed, encoding="utf-8")
    public_path.write_text(public_b64, encoding="utf-8")
    monkeypatch.setattr(
        settings, "B26_P2_SOURCE_ATTESTATION_PUBLIC_KEY_PATH", str(public_path)
    )
    statement = sa.build_statement(
        tenant_id=TENANT,
        webhook_ingress_identity_id=INGRESS,
        provider="stripe",
        provider_native_event_reference="pi_1",
        provider_native_commerce_reference="pi_1",
        normalized_commerce_reference_kind="provider_native",
        normalized_commerce_reference_value="pi_1",
        verified_amount_minor=4321,
        verified_amount_currency="USD",
        verified_amount_scale=2,
        event_timestamp="2026-10-01T16:00:00Z",
        body_sha256="a" * 64,
        authority_universe="99999999-8888-7777-6666-555555555555",
    )
    signature, _fingerprint = sa.sign_statement(
        statement, private_key_path=str(private_path)
    )
    session = _FakeSession(
        _row(
            statement=json.dumps(statement),
            signature=signature,
            attested_amount=4321,
            attested_currency="USD",
            current_universe="88888888-7777-6666-5555-444444444444",
            ingress_event_timestamp=datetime(
                2026, 10, 1, 16, tzinfo=timezone.utc
            ),
        )
    )
    status = await sa.read_verdict_source_attestation_status(
        session, tenant_id=TENANT, verdict_id="verdict-1"
    )
    assert status.unverifiable is True
    assert status.reason == "attestation_authority_universe_mismatch"


@pytest.mark.asyncio
async def test_a_forged_amount_is_refused_even_when_the_signature_verifies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A valid signature does not carry a different amount than it signed."""
    private_seed, public_b64 = sa.generate_keypair()
    private_path = tmp_path / "attest.key"
    public_path = tmp_path / "attest.pub"
    private_path.write_text(private_seed, encoding="utf-8")
    public_path.write_text(public_b64, encoding="utf-8")
    monkeypatch.setattr(
        settings, "B26_P2_SOURCE_ATTESTATION_PUBLIC_KEY_PATH", str(public_path)
    )

    statement = sa.build_statement(
        tenant_id=TENANT,
        webhook_ingress_identity_id=INGRESS,
        provider="stripe",
        provider_native_event_reference="pi_1",
        provider_native_commerce_reference="pi_1",
        normalized_commerce_reference_kind="provider_native",
        normalized_commerce_reference_value="pi_1",
        verified_amount_minor=4321,
        verified_amount_currency="USD",
        verified_amount_scale=2,
        event_timestamp="2026-10-27T16:00:00Z",
        body_sha256="a" * 64,
        authority_universe="99999999-8888-7777-6666-555555555555",
    )
    signature, _fingerprint = sa.sign_statement(
        statement, private_key_path=str(private_path)
    )
    # The owner rewrote the money but kept the root's row.
    session = _FakeSession(
        _row(
            statement=json.dumps(statement),
            signature=signature,
            attested_amount=4321,
            attested_currency="USD",
            ingress_amount=77777,
            verdict_net=77777,
            verdict_captured=77777,
            verdict_verified=77777,
        )
    )
    status = await sa.read_verdict_source_attestation_status(
        session, tenant_id=TENANT, verdict_id="verdict-1"
    )
    assert status.unverifiable is True
    assert status.status == "unverifiable:ingress_amount_diverged_from_attestation"


@pytest.mark.asyncio
async def test_a_valid_signature_does_not_authorize_a_relinked_verdict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    private_seed, public_b64 = sa.generate_keypair()
    private_path = tmp_path / "attest.key"
    public_path = tmp_path / "attest.pub"
    private_path.write_text(private_seed, encoding="utf-8")
    public_path.write_text(public_b64, encoding="utf-8")
    monkeypatch.setattr(
        settings, "B26_P2_SOURCE_ATTESTATION_PUBLIC_KEY_PATH", str(public_path)
    )
    statement = sa.build_statement(
        tenant_id=TENANT,
        webhook_ingress_identity_id=INGRESS,
        provider="stripe",
        provider_native_event_reference="pi_1",
        provider_native_commerce_reference="pi_1",
        normalized_commerce_reference_kind="provider_native",
        normalized_commerce_reference_value="pi_1",
        verified_amount_minor=4321,
        verified_amount_currency="USD",
        verified_amount_scale=2,
        event_timestamp="2026-10-27T16:00:00Z",
        body_sha256="a" * 64,
        authority_universe="99999999-8888-7777-6666-555555555555",
    )
    signature, _fingerprint = sa.sign_statement(
        statement, private_key_path=str(private_path)
    )
    session = _FakeSession(
        _row(
            statement=json.dumps(statement),
            signature=signature,
            attested_amount=4321,
            attested_currency="USD",
            verdict_commerce_reference="pi_other",
        )
    )
    status = await sa.read_verdict_source_attestation_status(
        session, tenant_id=TENANT, verdict_id="verdict-1"
    )
    assert status.unverifiable is True
    assert status.reason == "verdict_commerce_reference_mismatch"

def test_private_key_cache_rotates_with_the_mounted_file(tmp_path) -> None:
    import os

    from app.revenue_verification.source_attestation import (
        generate_keypair,
        load_private_key,
        sign_statement,
        verify_signature,
    )

    path = tmp_path / "source.key"
    seed_one, _ = generate_keypair()
    path.write_text(seed_one, encoding="utf-8")
    first = load_private_key(path)

    seed_two, public_two = generate_keypair()
    path.write_text(seed_two, encoding="utf-8")
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
    second = load_private_key(path)
    assert second is not first

    statement = {
        "version": 1,
        "tenant_id": "t",
        "webhook_ingress_identity_id": "i",
        "provider": "stripe",
        "provider_native_event_reference": "e",
        "provider_native_commerce_reference": "c",
        "normalized_commerce_reference_kind": "order_reference",
        "normalized_commerce_reference_value": "c",
        "verified_amount_minor": 1,
        "verified_amount_currency": "USD",
        "verified_amount_scale": 2,
        "event_timestamp": "2026-01-01T00:00:00Z",
        "body_sha256": "a" * 64,
        "authority_universe": None,
    }
    signature, fingerprint = sign_statement(statement, private_key_path=path)
    public_path = tmp_path / "source.pub"
    public_path.write_text(public_two, encoding="utf-8")
    assert verify_signature(statement, signature, public_key_path=public_path) == fingerprint

