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
from uuid import uuid4

import pytest

from app.revenue_verification.source_attestation import generate_keypair
from app.revenue_verification.source_evidence_journal import (
    LEGACY_SOURCE_FACT_JOURNAL_VERSION,
    SourceFactJournalError,
    append_source_fact,
    append_source_fact_outcome,
    journal_record_hash,
    load_source_fact_records,
    record_commit_outcome,
    resolve_source_facts,
    source_fact_outcome_transaction,
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


def test_cached_tip_invalidates_on_external_append(tmp_path: Path) -> None:
    journal = tmp_path / "source.jsonl"
    _append(journal, kind="source_money", fact_id="s1", xid="100")
    legacy = {
        "version": LEGACY_SOURCE_FACT_JOURNAL_VERSION,
        "fact_kind": "source_money",
        "fact_id": "s2",
        "tenant_id": "t",
        "verdict_id": "",
        "statement": {"id": "s2"},
        "signature": "sig",
        "key_sha256": "k",
    }
    with journal.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(legacy) + "\n")
        handle.flush()
    _append(journal, kind="source_money", fact_id="s3", xid="300")

    records = load_source_fact_records(journal)
    assert records is not None
    assert records[-1]["previous_record_hash"] == journal_record_hash(legacy)


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


@pytest.mark.asyncio
async def test_signed_unknown_outcome_is_not_an_abort(tmp_path: Path) -> None:
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
        outcome="unknown",
        private_key_path=private_path,
        path=journal,
    )

    resolved = await resolve_source_facts(
        _Session({"100": None}),
        path=journal,
        public_key_path=public_path,
    )

    assert resolved is not None
    assert resolved.unknown == frozenset({("source_money", "s1")})
    assert resolved.aborted == frozenset()


@pytest.mark.asyncio
async def test_exception_without_observed_commit_is_unknown_not_aborted(
    tmp_path: Path,
) -> None:
    private_seed, public_b64 = generate_keypair()
    private_path = tmp_path / "source.key"
    public_path = tmp_path / "source.pub"
    private_path.write_text(private_seed, encoding="utf-8")
    public_path.write_text(public_b64, encoding="utf-8")
    journal = tmp_path / "source.jsonl"

    with pytest.raises(RuntimeError, match="caller failed"):
        async with source_fact_outcome_transaction(str(private_path)):
            _append(
                journal,
                kind="source_money",
                fact_id="s1",
                xid="100",
            )
            raise RuntimeError("caller failed")

    records = load_source_fact_records(journal)
    assert records is not None
    outcomes = [
        record
        for record in records
        if record.get("version") == "b26-p2-source-fact-outcome-v1"
    ]
    assert len(outcomes) == 1
    assert outcomes[0]["outcome"] == "unknown"

    resolved = await resolve_source_facts(
        _Session({"100": None}),
        path=journal,
        public_key_path=public_path,
    )
    assert resolved is not None
    assert resolved.unknown == frozenset({("source_money", "s1")})
    assert resolved.aborted == frozenset()


@pytest.mark.asyncio
async def test_observed_commit_is_signed_committed(tmp_path: Path) -> None:
    private_seed, public_b64 = generate_keypair()
    private_path = tmp_path / "source.key"
    public_path = tmp_path / "source.pub"
    private_path.write_text(private_seed, encoding="utf-8")
    public_path.write_text(public_b64, encoding="utf-8")
    journal = tmp_path / "source.jsonl"

    async with source_fact_outcome_transaction(str(private_path)):
        _append(journal, kind="source_money", fact_id="s1", xid="100")
        record_commit_outcome("committed")

    resolved = await resolve_source_facts(
        _Session({"100": None}),
        path=journal,
        public_key_path=public_path,
    )
    assert resolved is not None
    assert ("source_money", "s1") in resolved.committed
    assert resolved.aborted == frozenset()


class _FakeIngressSession:
    def __init__(self, *, commit_error: Exception | None = None):
        self.info: dict = {}
        self.commit_error = commit_error
        self.rollback_calls = 0

    async def begin(self) -> None:
        return None

    def in_transaction(self) -> bool:
        return True

    async def commit(self) -> None:
        if self.commit_error is not None:
            raise self.commit_error

    async def rollback(self) -> None:
        self.rollback_calls += 1


class _FakeIngressContext:
    def __init__(self, session: _FakeIngressSession):
        self.session = session

    async def __aenter__(self) -> _FakeIngressSession:
        return self.session

    async def __aexit__(self, *_exc) -> bool:
        return False


@pytest.mark.asyncio
async def test_commit_raising_is_unknown_not_aborted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    private_seed, public_b64 = generate_keypair()
    private_path = tmp_path / "source.key"
    public_path = tmp_path / "source.pub"
    private_path.write_text(private_seed, encoding="utf-8")
    public_path.write_text(public_b64, encoding="utf-8")
    journal = tmp_path / "source.jsonl"

    from app.db import session as db_session

    fake = _FakeIngressSession(commit_error=RuntimeError("commit outcome lost"))
    monkeypatch.setenv("SKELDIR_PROCESS_ROLE", "auth_ingress")
    monkeypatch.setattr(
        db_session, "IngressAsyncSessionLocal", lambda: _FakeIngressContext(fake)
    )
    monkeypatch.setattr(db_session, "_require_ingress_auth_boundary", lambda: None)

    with pytest.raises(RuntimeError, match="commit outcome lost"):
        async with source_fact_outcome_transaction(str(private_path)):
            async with db_session.get_ingress_session(uuid4()):
                _append(journal, kind="source_money", fact_id="s1", xid="100")

    outcomes = [
        record
        for record in (load_source_fact_records(journal) or [])
        if record.get("version") == "b26-p2-source-fact-outcome-v1"
    ]
    assert len(outcomes) == 1
    assert outcomes[0]["outcome"] == "unknown"
    assert fake.rollback_calls >= 1

    resolved = await resolve_source_facts(
        _Session({"100": None}),
        path=journal,
        public_key_path=public_path,
    )
    assert resolved is not None
    assert resolved.unknown == frozenset({("source_money", "s1")})
    assert resolved.aborted == frozenset()
    assert resolved.journal_count == 2
    assert resolved.journal_tip


@pytest.mark.asyncio
async def test_journal_chain_detects_record_mutation(tmp_path: Path) -> None:
    journal = tmp_path / "source.jsonl"
    _append(journal, kind="source_money", fact_id="s1", xid="100")
    _append(journal, kind="source_money", fact_id="s2", xid="101")
    records = load_source_fact_records(journal)
    assert records is not None
    assert records[0]["record_hash"]
    records[0]["statement"]["id"] = "tampered"
    journal.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
    with pytest.raises(SourceFactJournalError, match="chain_record_mismatch"):
        load_source_fact_records(journal)


@pytest.mark.asyncio
async def test_journal_chain_detects_record_deletion(tmp_path: Path) -> None:
    journal = tmp_path / "source.jsonl"
    _append(journal, kind="source_money", fact_id="s1", xid="100")
    _append(journal, kind="source_money", fact_id="s2", xid="101")
    lines = journal.read_text(encoding="utf-8").splitlines()
    journal.write_text(lines[1] + "\n", encoding="utf-8")
    with pytest.raises(SourceFactJournalError, match="chain_previous_mismatch"):
        load_source_fact_records(journal)


@pytest.mark.asyncio
async def test_journal_chain_links_a_legacy_prefix(tmp_path: Path) -> None:
    journal = tmp_path / "source.jsonl"
    legacy = {
        "version": LEGACY_SOURCE_FACT_JOURNAL_VERSION,
        "fact_kind": "source_money",
        "fact_id": "s1",
        "tenant_id": "t",
        "verdict_id": "",
        "statement": {"id": "s1"},
        "signature": "sig",
        "key_sha256": "k",
    }
    journal.write_text(json.dumps(legacy, sort_keys=True) + "\n", encoding="utf-8")
    _append(journal, kind="source_money", fact_id="s2", xid="101")
    records = load_source_fact_records(journal)
    assert records is not None
    assert records[1]["previous_record_hash"]
    legacy["statement"]["id"] = "tampered"
    journal.write_text(
        json.dumps(legacy, sort_keys=True) + "\n"
        + "".join(json.dumps(record, sort_keys=True) + "\n" for record in records[1:]),
        encoding="utf-8",
    )
    with pytest.raises(SourceFactJournalError, match="chain_previous_mismatch"):
        load_source_fact_records(journal)


class _NoQuerySession:
    async def execute(self, *_args, **_kwargs):
        raise AssertionError("signed outcome must be resolved before xid lookup")


@pytest.mark.asyncio
async def test_signed_outcome_is_resolved_without_old_xid_lookup(
    tmp_path: Path,
) -> None:
    private_seed, public_b64 = generate_keypair()
    private_path = tmp_path / "source.key"
    public_path = tmp_path / "source.pub"
    private_path.write_text(private_seed, encoding="utf-8")
    public_path.write_text(public_b64, encoding="utf-8")
    journal = tmp_path / "source.jsonl"
    _append(journal, kind="source_money", fact_id="s1", xid="4294967295")
    prepared = load_source_fact_records(journal)
    assert prepared is not None
    append_source_fact_outcome(
        record=prepared[0],
        outcome="committed",
        private_key_path=private_path,
        path=journal,
    )

    resolved = await resolve_source_facts(
        _NoQuerySession(), path=journal, public_key_path=public_path
    )

    assert resolved is not None
    assert ("source_money", "s1") in resolved.committed
    assert resolved.unknown == frozenset()


def _append_many(path: str, count: int, prefix: str) -> None:
    for index in range(count):
        append_source_fact(
            fact_kind="source_money",
            fact_id=f"{prefix}-{index}",
            tenant_id="t",
            verdict_id="v",
            statement={"id": f"{prefix}-{index}"},
            signature="sig",
            key_sha256="k",
            database_transaction_id=f"{prefix}-{index}",
            path=path,
        )


def test_concurrent_writers_preserve_one_chain(tmp_path: Path) -> None:
    import multiprocessing

    journal = tmp_path / "source.jsonl"
    context = multiprocessing.get_context("spawn")
    writers = [
        context.Process(target=_append_many, args=(str(journal), 200, f"w{index}"))
        for index in range(2)
    ]
    for writer in writers:
        writer.start()
    for writer in writers:
        writer.join(timeout=60)
        assert writer.exitcode == 0
    records = load_source_fact_records(journal)
    assert records is not None
    assert len(records) == 400

