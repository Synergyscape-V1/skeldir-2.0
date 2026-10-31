"""XXV replay must resolve a committed-but-unacknowledged source."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.auth_service import server
from app.core.config import settings
from app.revenue_verification.source_attestation import generate_keypair
from app.revenue_verification.source_evidence_journal import (
    append_source_fact,
    append_source_fact_outcome,
    load_source_fact_records,
)


class _NoQuerySession:
    async def execute(self, *_args, **_kwargs):
        raise AssertionError("signed outcomes must resolve without xid lookup")


def _prepare(tmp_path: Path, outcome: str) -> tuple[Path, Path]:
    private_seed, public_b64 = generate_keypair()
    private_path = tmp_path / "source.key"
    public_path = tmp_path / "source.pub"
    private_path.write_text(private_seed, encoding="utf-8")
    public_path.write_text(public_b64, encoding="utf-8")
    journal = tmp_path / "source.jsonl"
    append_source_fact(
        fact_kind="source_money",
        fact_id="ingress-1",
        tenant_id="tenant-1",
        verdict_id="",
        statement={"id": "ingress-1"},
        signature="sig",
        key_sha256="k",
        database_transaction_id="100",
        path=journal,
    )
    prepared = load_source_fact_records(journal)
    assert prepared is not None
    append_source_fact_outcome(
        record=prepared[0],
        outcome=outcome,
        private_key_path=private_path,
        path=journal,
    )
    return private_path, public_path


@pytest.mark.asyncio
async def test_unknown_replay_requires_writer(tmp_path, monkeypatch) -> None:
    _, public_path = _prepare(tmp_path, "unknown")
    monkeypatch.setattr(server, "_source_money_attestation_exists", AsyncMock(return_value=True))
    monkeypatch.setattr(settings, "B26_P2_SOURCE_EVIDENCE_JOURNAL_PATH", str(tmp_path / "source.jsonl"))
    monkeypatch.setattr(settings, "B26_P2_SOURCE_ATTESTATION_PUBLIC_KEY_PATH", str(public_path))
    assert await server._source_money_attestation_replay_required(
        _NoQuerySession(), "ingress-1"
    ) is True


@pytest.mark.asyncio
async def test_committed_replay_keeps_fast_path(tmp_path, monkeypatch) -> None:
    _, public_path = _prepare(tmp_path, "committed")
    monkeypatch.setattr(server, "_source_money_attestation_exists", AsyncMock(return_value=True))
    monkeypatch.setattr(settings, "B26_P2_SOURCE_EVIDENCE_JOURNAL_PATH", str(tmp_path / "source.jsonl"))
    monkeypatch.setattr(settings, "B26_P2_SOURCE_ATTESTATION_PUBLIC_KEY_PATH", str(public_path))
    assert await server._source_money_attestation_replay_required(
        _NoQuerySession(), "ingress-1"
    ) is False


@pytest.mark.asyncio
async def test_missing_attestation_requires_writer(monkeypatch) -> None:
    monkeypatch.setattr(server, "_source_money_attestation_exists", AsyncMock(return_value=False))
    assert await server._source_money_attestation_replay_required(
        _NoQuerySession(), "ingress-1"
    ) is True


@pytest.mark.asyncio
async def test_no_journal_keeps_legacy_fast_path(monkeypatch) -> None:
    monkeypatch.setattr(server, "_source_money_attestation_exists", AsyncMock(return_value=True))
    monkeypatch.setattr(settings, "B26_P2_SOURCE_EVIDENCE_JOURNAL_PATH", None)
    monkeypatch.delenv("B26_P2_SOURCE_EVIDENCE_JOURNAL_PATH", raising=False)
    assert await server._source_money_attestation_replay_required(
        _NoQuerySession(), "ingress-1"
    ) is False
