"""XXV source-fact journal transaction-outcome cells.

A journal entry written before database commit is only an intent. The
PostgreSQL transaction id resolves it: committed entries are facts, aborted
entries are not, and an in-progress entry is not yet admitted. These cells pin
that law without a database fixture; the lane falsifier exercises the real
commit/rollback path.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.revenue_verification.source_attestation import generate_keypair
from app.revenue_verification.source_evidence_journal import (
    LEGACY_SOURCE_FACT_JOURNAL_VERSION,
    SourceFactJournalError,
    append_source_fact,
    append_source_fact_outcome,
    load_source_fact_records,
    resolve_source_facts,
)


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _Session:
    def __init__(self, statuses):
        self.statuses = statuses

    async def execute(self, statement, params=None):
        return _Result(
            [
                (xid, self.statuses.get(xid))
                for xid in (params or {}).get("xids", [])
            ]
        )


def _append(path: Path, *, kind: str, fact_id: str, xid: str, tenant: str = "t"):
    append_source_fact(
        fact_kind=kind,
        fact_id=fact_id,
        tenant_id=tenant,
        verdict_id="v",
        statement={"id": fact_id},
        signature="sig",
        key_sha256="k",
        database_transaction_id=xid,
        path=path,
    )


@pytest.mark.asyncio
async def test_committed_aborted_and_in_progress_are_distinct(tmp_path: Path) -> None:
    journal = tmp_path / "source.jsonl"
    _append(journal, kind="source_money", fact_id="s1", xid="100")
    _append(journal, kind="adjustment", fact_id="a1", xid="200")
    _append(journal, kind="adjustment", fact_id="a2", xid="300")

    resolved = await resolve_source_facts(
        _Session({"100": "committed", "200": "aborted", "300": "in progress"}),
        path=journal,
    )

    assert resolved is not None
    assert set(resolved.committed) == {("source_money", "s1")}
    assert resolved.aborted == frozenset({("adjustment", "a1")})
    assert resolved.in_progress == frozenset({("adjustment", "a2")})


@pytest.mark.asyncio
async def test_retry_after_abort_is_committed_by_its_own_transaction(tmp_path: Path) -> None:
    journal = tmp_path / "source.jsonl"
    _append(journal, kind="adjustment", fact_id="a1", xid="200")
    _append(journal, kind="adjustment", fact_id="a1", xid="201")

    resolved = await resolve_source_facts(
        _Session({"200": "aborted", "201": "committed"}), path=journal
    )

    assert resolved is not None
    assert ("adjustment", "a1") in resolved.committed
    assert ("adjustment", "a1") not in resolved.aborted


def test_v2_record_requires_transaction_identity(tmp_path: Path) -> None:
    journal = tmp_path / "source.jsonl"
    with pytest.raises(SourceFactJournalError, match="transaction_identity"):
        append_source_fact(
            fact_kind="source_money",
            fact_id="s1",
            tenant_id="t",
            verdict_id="",
            statement={},
            signature="sig",
            key_sha256="k",
            database_transaction_id="",
            path=journal,
        )


def test_legacy_record_is_preserved(tmp_path: Path) -> None:
    journal = tmp_path / "source.jsonl"
    record = {
        "version": LEGACY_SOURCE_FACT_JOURNAL_VERSION,
        "fact_kind": "source_money",
        "fact_id": "s1",
        "tenant_id": "t",
        "verdict_id": "",
        "statement": {"id": "s1"},
        "signature": "sig",
        "key_sha256": "k",
    }
    journal.write_text(json.dumps(record) + "\n", encoding="utf-8")

    records = load_source_fact_records(journal)
    assert records is not None
    assert records[0]["version"] == LEGACY_SOURCE_FACT_JOURNAL_VERSION


@pytest.mark.asyncio
async def test_signed_outcome_survives_transaction_status_aging(tmp_path: Path) -> None:
    private_seed, public_b64 = generate_keypair()
    private_path = tmp_path / "source.key"
    public_path = tmp_path / "source.pub"
    private_path.write_text(private_seed, encoding="utf-8")
    public_path.write_text(public_b64, encoding="utf-8")
    journal = tmp_path / "source.jsonl"
    _append(journal, kind="source_money", fact_id="s1", xid="100")
    prepared = load_source_fact_records(journal)
    assert prepared is not None
    append_source_fact_outcome(
        record=prepared[0],
        outcome="committed",
        private_key_path=private_path,
        path=journal,
    )

    resolved = await resolve_source_facts(
        _Session({"100": None}),
        path=journal,
        public_key_path=public_path,
    )

    assert resolved is not None
    assert ("source_money", "s1") in resolved.committed
    assert ("source_money", "s1") not in resolved.unknown


@pytest.mark.asyncio
async def test_signed_abort_survives_transaction_status_aging(tmp_path: Path) -> None:
    private_seed, public_b64 = generate_keypair()
    private_path = tmp_path / "source.key"
    public_path = tmp_path / "source.pub"
    private_path.write_text(private_seed, encoding="utf-8")
    public_path.write_text(public_b64, encoding="utf-8")
    journal = tmp_path / "source.jsonl"
    _append(journal, kind="adjustment", fact_id="a1", xid="200")
    prepared = load_source_fact_records(journal)
    assert prepared is not None
    append_source_fact_outcome(
        record=prepared[0],
        outcome="aborted",
        private_key_path=private_path,
        path=journal,
    )

    resolved = await resolve_source_facts(
        _Session({"200": None}),
        path=journal,
        public_key_path=public_path,
    )

    assert resolved is not None
    assert resolved.aborted == frozenset({("adjustment", "a1")})


@pytest.mark.asyncio
async def test_unknown_transaction_without_outcome_is_refused(tmp_path: Path) -> None:
    journal = tmp_path / "source.jsonl"
    _append(journal, kind="source_money", fact_id="s1", xid="300")

    resolved = await resolve_source_facts(
        _Session({"300": None}), path=journal
    )

    assert resolved is not None
    assert resolved.unknown == frozenset({("source_money", "s1")})
