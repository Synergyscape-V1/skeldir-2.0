"""Append-only, authentication-root-signed source facts.

The database rows are writable by the maintenance principal.  The
authentication root signs each source or adjustment statement; this journal
records that signed fact at the moment it is produced, outside the database
principal's control.  Readers require a current database fact to have its
signed journal entry, so deleting the database row after authentication is
detectable even before the periodic history observer runs.

Version 2 binds each journal record to the PostgreSQL transaction that produced
it.  The transaction id is assigned before the external fsync and its final
state is read later with ``pg_xact_status``.  This is what distinguishes a
genuine aborted transaction (the journal entry remains, the database row does
not) from owner erasure of a committed fact: an aborted transaction is ignored,
while a committed transaction with a missing row is a completeness failure.
"""

from __future__ import annotations

import base64
import contextlib
import contextvars
import hashlib
import json
import os
import queue
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

SOURCE_FACT_JOURNAL_VERSION = "b26-p2-source-fact-journal-v3"
SOURCE_FACT_JOURNAL_V2 = "b26-p2-source-fact-journal-v2"
LEGACY_SOURCE_FACT_JOURNAL_VERSION = "b26-p2-source-fact-journal-v1"
SOURCE_FACT_OUTCOME_VERSION = "b26-p2-source-fact-outcome-v1"

#: Serialises append + last-hash read within one auth-root process. The
#: production auth root runs one worker; the OS append itself remains
#: durable and fsynced.
_JOURNAL_APPEND_LOCK = threading.Lock()


@contextmanager
def _journal_file_lock(journal: Path):
    """Serialise append/read across processes sharing one journal file.

    The process-local ``threading.Lock`` above is not sufficient for the
    supported two-auth-root topology: two uvicorn processes read the same tip
    and append competing hashes. The OS lock is the cross-process boundary.
    A separate ``.lock`` file keeps the journal itself append-only.
    """
    try:
        import fcntl
    except ImportError:
        fcntl = None
    try:
        import msvcrt
    except ImportError:
        msvcrt = None

    lock_path = journal.with_name(journal.name + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as handle:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        elif msvcrt is not None:
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            while True:
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    time.sleep(0.01)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            elif msvcrt is not None:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


class SourceFactJournalError(RuntimeError):
    """The source-fact journal cannot be read or adjudicated."""


_CURRENT_OUTCOME_CONTEXT: contextvars.ContextVar[
    list[dict[str, Any]] | None
] = contextvars.ContextVar("source_fact_outcome_context", default=None)

#: Commit outcome recorded by the session boundary. ``None`` means the
#: boundary did not observe a definitive commit or rollback; that is an
#: uncertain outcome, never an abort.
_CURRENT_COMMIT_OUTCOME: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "source_fact_commit_outcome", default=None
)


def record_commit_outcome(outcome: str | None) -> None:
    """Record a definitive session outcome for the enclosing fact journal."""

    if outcome not in {None, "committed", "aborted", "unknown"}:
        raise SourceFactJournalError("source_fact_commit_outcome_invalid")
    _CURRENT_COMMIT_OUTCOME.set(outcome)


def current_commit_outcome() -> str | None:
    return _CURRENT_COMMIT_OUTCOME.get()


@dataclass(frozen=True)
class ResolvedSourceFacts:
    """Journal facts after their PostgreSQL transaction outcomes are resolved."""

    committed: Mapping[tuple[str, str], dict[str, Any]]
    legacy: Mapping[tuple[str, str], dict[str, Any]]
    aborted: frozenset[tuple[str, str]]
    in_progress: frozenset[tuple[str, str]]
    unknown: frozenset[tuple[str, str]]
    journal_count: int
    journal_tip: str | None


def _journal_path(path: str | os.PathLike[str] | None = None) -> Path | None:
    configured = str(path or os.getenv("B26_P2_SOURCE_EVIDENCE_JOURNAL_PATH", "")).strip()
    return Path(configured) if configured else None


def _canonical_outcome(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")


def _record_hash(record: Mapping[str, Any]) -> str:
    """Hash one journal record, excluding its own chain hash."""

    material = {
        key: value
        for key, value in record.items()
        if key != "record_hash"
    }
    return hashlib.sha256(_canonical_outcome(material)).hexdigest()


def journal_record_hash(record: Mapping[str, Any]) -> str:
    """Public hash identity of one journal record."""

    return str(record.get("record_hash") or "") or _record_hash(record)


#: Last (size, mtime_ns, hash) observed for each journal path. Reading the
#: whole journal on every append is quadratic in the number of authenticated
#: facts: at R3's 46 rps profile that read dominated the leg and pushed p95
#: past its ceiling. The file is written only by this auth-root process, and
#: the stat identity makes an external append/truncate invalidate the cache.
_LAST_RECORD_HASH_CACHE: dict[str, tuple[int, int, str | None]] = {}


def _last_record_hash_unlocked(journal: Path) -> str | None:
    try:
        stat = journal.stat()
    except FileNotFoundError:
        _LAST_RECORD_HASH_CACHE.pop(str(journal), None)
        return None
    cached = _LAST_RECORD_HASH_CACHE.get(str(journal))
    if cached is not None and cached[0] == stat.st_size and cached[1] == stat.st_mtime_ns:
        return cached[2]
    last: str | None = None
    with journal.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                last = line.strip()
    if last is None:
        result = None
    else:
        record = json.loads(last)
        if record.get("version") == SOURCE_FACT_JOURNAL_VERSION:
            result = str(record.get("record_hash") or "") or None
        else:
            result = _record_hash(record)
    _LAST_RECORD_HASH_CACHE[str(journal)] = (stat.st_size, stat.st_mtime_ns, result)
    return result


@dataclass
class _JournalAppendRequest:
    record: dict[str, Any]
    event: threading.Event
    error: BaseException | None = None


class _JournalWriter:
    """Group-commit writer for one journal path.

    Each caller waits for the fsync of the batch containing its record, so the
    durability contract is unchanged. Batching amortises the fsync and the
    cross-process lock across concurrent authenticated arrivals.
    """

    def __init__(self, journal: Path) -> None:
        self.journal = journal
        self.queue: queue.Queue[_JournalAppendRequest] = queue.Queue()
        self.thread = threading.Thread(
            target=self._run,
            name=f"b26-p2-journal-writer:{journal.name}",
            daemon=True,
        )
        self.thread.start()

    def append(self, record: dict[str, Any]) -> None:
        request = _JournalAppendRequest(record=record, event=threading.Event())
        self.queue.put(request)
        if not request.event.wait(timeout=30.0):
            raise SourceFactJournalError("source_fact_journal_append_timeout")
        if request.error is not None:
            raise request.error

    def _run(self) -> None:
        while True:
            first = self.queue.get()
            batch = [first]
            deadline = time.monotonic() + 0.002
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                try:
                    batch.append(self.queue.get(timeout=remaining))
                except queue.Empty:
                    break
            try:
                self._append_batch(batch)
            except BaseException as exc:  # noqa: BLE001 - delivered to callers
                for request in batch:
                    request.error = exc
            finally:
                for request in batch:
                    request.event.set()

    def _append_batch(self, batch: list[_JournalAppendRequest]) -> None:
        with _JOURNAL_APPEND_LOCK:
            with _journal_file_lock(self.journal):
                previous = _last_record_hash_unlocked(self.journal)
                lines: list[str] = []
                for request in batch:
                    record = request.record
                    record["previous_record_hash"] = previous
                    record["record_hash"] = _record_hash(record)
                    lines.append(
                        json.dumps(
                            record,
                            sort_keys=True,
                            separators=(",", ":"),
                            default=str,
                        )
                    )
                    previous = str(record["record_hash"])
                self.journal.parent.mkdir(parents=True, exist_ok=True)
                with self.journal.open("a", encoding="utf-8") as handle:
                    handle.write("\n".join(lines) + "\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                stat = self.journal.stat()
                _LAST_RECORD_HASH_CACHE[str(self.journal)] = (
                    stat.st_size,
                    stat.st_mtime_ns,
                    previous,
                )


_JOURNAL_WRITERS: dict[str, _JournalWriter] = {}
_JOURNAL_WRITERS_LOCK = threading.Lock()


def _writer_for(journal: Path) -> _JournalWriter:
    key = str(journal.resolve())
    with _JOURNAL_WRITERS_LOCK:
        writer = _JOURNAL_WRITERS.get(key)
        if writer is None:
            writer = _JournalWriter(journal)
            _JOURNAL_WRITERS[key] = writer
        return writer


def _append_chained_record(journal: Path, record: dict[str, Any]) -> None:
    """Append one v3 record with a durable previous/record hash chain."""

    _writer_for(journal).append(record)


def _verify_outcome(
    record: Mapping[str, Any], public_key_path: str | os.PathLike[str]
) -> None:
    from cryptography.exceptions import InvalidSignature  # noqa: PLC0415
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (  # noqa: PLC0415
        Ed25519PublicKey,
    )

    from app.revenue_verification.source_attestation import (  # noqa: PLC0415
        compiled_attestation_anchor,
        load_public_key_raw,
        public_key_fingerprint_from_raw,
    )

    raw_public = load_public_key_raw(public_key_path)
    fingerprint = public_key_fingerprint_from_raw(raw_public)
    anchor = compiled_attestation_anchor()
    if anchor and fingerprint != anchor:
        raise SourceFactJournalError("source_fact_outcome_key_not_anchored")
    signature_text = str(record.get("signature") or "")
    if not signature_text.startswith("ed25519:"):
        raise SourceFactJournalError("source_fact_outcome_signature_missing")
    try:
        signature = base64.urlsafe_b64decode(
            (signature_text.split(":", 1)[1] + "===").encode("ascii")
        )
        payload = _outcome_payload(
            record, str(record.get("outcome") or "")
        )
        Ed25519PublicKey.from_public_bytes(raw_public).verify(
            signature, _canonical_outcome(payload)
        )
    except (InvalidSignature, ValueError, TypeError) as exc:
        raise SourceFactJournalError(
            "source_fact_outcome_signature_invalid"
        ) from exc


def _outcome_payload(record: Mapping[str, Any], outcome: str) -> dict[str, Any]:
    return {
        "version": SOURCE_FACT_OUTCOME_VERSION,
        "record_type": "outcome",
        "fact_kind": str(record["fact_kind"]),
        "fact_id": str(record["fact_id"]),
        "tenant_id": str(record["tenant_id"]),
        "database_transaction_id": str(
            record["database_transaction_id"]
        ),
        "outcome": outcome,
        "statement_signature": str(
            record.get("statement_signature", record["signature"])
        ),
    }


def append_source_fact_outcome(
    *,
    record: Mapping[str, Any],
    outcome: str,
    private_key_path: str | os.PathLike[str],
    path: str | os.PathLike[str] | None = None,
) -> None:
    """Append an auth-root-signed post-commit outcome for one prepared fact."""

    if outcome not in {"committed", "aborted", "unknown"}:
        raise SourceFactJournalError("source_fact_outcome_invalid")
    journal = _journal_path(path or record.get("path"))
    if journal is None:
        raise SourceFactJournalError("source_fact_journal_missing")
    from cryptography.hazmat.primitives import serialization  # noqa: PLC0415
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (  # noqa: PLC0415
        Ed25519PrivateKey,
    )

    try:
        raw = base64.urlsafe_b64decode(
            (Path(private_key_path).read_text(encoding="utf-8").strip() + "===")
            .encode("ascii")
        )
    except (OSError, ValueError) as exc:
        raise SourceFactJournalError(
            "source_fact_outcome_key_unreadable"
        ) from exc
    if len(raw) != 32:
        raise SourceFactJournalError("source_fact_outcome_key_wrong_length")
    key = Ed25519PrivateKey.from_private_bytes(raw)
    payload = _outcome_payload(record, outcome)
    signature = key.sign(_canonical_outcome(payload))
    public_raw = key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    record_payload = {
        **payload,
        "signature": "ed25519:"
        + base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii"),
        "key_sha256": hashlib.sha256(public_raw).hexdigest(),
    }
    _append_chained_record(journal, record_payload)


@contextlib.asynccontextmanager
async def source_fact_outcome_transaction(
    private_key_path: str | os.PathLike[str] | None,
):
    """Record the outcome after the database transaction has resolved.

    The context wraps the database session from the outside: the session
    commits or rolls back before this context exits. A commit receipt makes a
    committed fact adjudicable after PostgreSQL has forgotten the transaction
    id; an abort receipt keeps an abandoned attempt from blocking later work.
    """

    if private_key_path is None:
        yield
        return
    facts: list[dict[str, Any]] = []
    token = _CURRENT_OUTCOME_CONTEXT.set(facts)
    commit_token = _CURRENT_COMMIT_OUTCOME.set(None)
    try:
        yield
    except Exception:
        # A raised call is not proof of rollback. The session boundary
        # records ``committed``/``aborted`` only when it observed that
        # outcome; a failed commit leaves ``unknown``. Never manufacture an
        # ``aborted`` receipt from an exception alone.
        outcome = current_commit_outcome() or "unknown"
        if outcome not in {"committed", "aborted"}:
            outcome = "unknown"
        for fact in facts:
            try:
                append_source_fact_outcome(
                    record=fact,
                    outcome=outcome,
                    private_key_path=private_key_path,
                    path=fact.get("path"),
                )
            except Exception:  # noqa: BLE001 - preserve the original failure
                pass
        raise
    else:
        # Normal return without an observed database outcome is not proof
        # of commit. Only the session boundary may record ``committed``;
        # otherwise the fact remains unknown.
        outcome = current_commit_outcome() or "unknown"
        if outcome not in {"committed", "aborted", "unknown"}:
            outcome = "unknown"
        for fact in facts:
            append_source_fact_outcome(
                record=fact,
                outcome=outcome,
                private_key_path=private_key_path,
                path=fact.get("path"),
            )
    finally:
        _CURRENT_COMMIT_OUTCOME.reset(commit_token)
        _CURRENT_OUTCOME_CONTEXT.reset(token)


def append_source_fact(
    *,
    fact_kind: str,
    fact_id: str,
    tenant_id: str,
    verdict_id: str,
    statement: Mapping[str, Any],
    signature: str,
    key_sha256: str,
    database_transaction_id: str,
    path: str | os.PathLike[str] | None = None,
) -> None:
    """Append one already-signed fact with its producing transaction id."""

    journal = _journal_path(path)
    if journal is None:
        return
    transaction_id = str(database_transaction_id or "").strip()
    if not transaction_id:
        raise SourceFactJournalError("source_fact_journal_transaction_identity_missing")
    journal.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "version": SOURCE_FACT_JOURNAL_VERSION,
        "fact_kind": fact_kind,
        "fact_id": str(fact_id),
        "tenant_id": str(tenant_id),
        "verdict_id": str(verdict_id),
        "statement": dict(statement),
        "signature": signature,
        "key_sha256": key_sha256,
        "database_transaction_id": transaction_id,
    }
    _append_chained_record(journal, record)
    context = _CURRENT_OUTCOME_CONTEXT.get()
    if context is not None:
        context.append({**record, "path": str(journal)})


def load_source_fact_records(
    path: str | os.PathLike[str] | None = None,
) -> list[dict[str, Any]] | None:
    """Return every journal record, including retries of the same fact."""

    journal = _journal_path(path)
    if journal is None:
        return None
    if not journal.exists():
        return []
    records: list[dict[str, Any]] = []
    with _journal_file_lock(journal):
        with journal.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                version = record.get("version")
                if version not in {
                    SOURCE_FACT_JOURNAL_VERSION,
                    SOURCE_FACT_JOURNAL_V2,
                    LEGACY_SOURCE_FACT_JOURNAL_VERSION,
                    SOURCE_FACT_OUTCOME_VERSION,
                }:
                    raise SourceFactJournalError(
                        "source_fact_journal_version_unsupported"
                    )
                if version in {
                    SOURCE_FACT_JOURNAL_VERSION,
                    SOURCE_FACT_JOURNAL_V2,
                } and not str(record.get("database_transaction_id") or "").strip():
                    raise SourceFactJournalError(
                        "source_fact_journal_transaction_identity_missing"
                    )
                records.append(record)
    # v3 records carry an explicit previous/record hash chain. v2/v1 records
    # are still accepted as legacy prefixes; their computed hash is the link
    # the first v3 record must cite, so modifying or deleting a legacy record
    # breaks the chain at the first v3 record.
    previous: str | None = None
    for record in records:
        if record.get("version") == SOURCE_FACT_JOURNAL_VERSION:
            if str(record.get("previous_record_hash") or "") != str(
                previous or ""
            ):
                raise SourceFactJournalError(
                    "source_fact_journal_chain_previous_mismatch"
                )
            computed = _record_hash(record)
            if str(record.get("record_hash") or "") != computed:
                raise SourceFactJournalError(
                    "source_fact_journal_chain_record_mismatch"
                )
            previous = computed
        else:
            previous = _record_hash(record)
    return records


def load_source_facts(
    path: str | os.PathLike[str] | None = None,
) -> dict[tuple[str, str], dict[str, Any]] | None:
    """Return the last record per fact key (compatibility view)."""

    records = load_source_fact_records(path)
    if records is None:
        return None
    facts: dict[tuple[str, str], dict[str, Any]] = {}
    for record in records:
        facts[(str(record["fact_kind"]), str(record["fact_id"]))] = record
    return facts


async def _transaction_statuses(
    session: Any, transaction_ids: set[str]
) -> dict[str, str | None]:
    if not transaction_ids:
        return {}
    from sqlalchemy import text  # noqa: PLC0415

    rows = (
        await session.execute(
            text(
                "SELECT xid::text,"
                " CASE WHEN xid::xid8 >= pg_current_xact_id() THEN NULL"
                " ELSE pg_xact_status(xid::xid8)::text END"
                " FROM unnest(CAST(:xids AS text[])) AS xid"
            ),
            {"xids": sorted(transaction_ids)},
        )
    ).all()
    return {str(xid): (None if status is None else str(status)) for xid, status in rows}


async def resolve_source_facts(
    session: Any,
    *,
    path: str | os.PathLike[str] | None = None,
    public_key_path: str | os.PathLike[str] | None = None,
) -> ResolvedSourceFacts | None:
    """Resolve journal facts against the transaction that produced each one.

    A committed transaction whose row is gone is an omission, not an aborted
    attempt.  An aborted transaction is not a fact.  A transaction still in
    progress is not yet a fact and must not be mistaken for one.
    """

    records = load_source_fact_records(path)
    if records is None:
        return None

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for record in records:
        grouped.setdefault(
            (str(record["fact_kind"]), str(record["fact_id"])), []
        ).append(record)
    # A signed outcome is authoritative and survives cluster migration. Do
    # not ask a new cluster about an old transaction id (it can be in that
    # cluster's future) before consulting the signed outcome.
    transaction_ids = {
        str(record["database_transaction_id"])
        for entries in grouped.values()
        if not any(
            record.get("version") == SOURCE_FACT_OUTCOME_VERSION
            for record in entries
        )
        for record in entries
        if record.get("version")
        in {SOURCE_FACT_JOURNAL_VERSION, SOURCE_FACT_JOURNAL_V2}
    }
    statuses = await _transaction_statuses(session, transaction_ids)

    committed: dict[tuple[str, str], dict[str, Any]] = {}
    legacy: dict[tuple[str, str], dict[str, Any]] = {}
    aborted: set[tuple[str, str]] = set()
    in_progress: set[tuple[str, str]] = set()
    unknown: set[tuple[str, str]] = set()
    for key, entries in grouped.items():
        prepared = [
            record
            for record in entries
            if record.get("version")
            in {
                SOURCE_FACT_JOURNAL_VERSION,
                SOURCE_FACT_JOURNAL_V2,
                LEGACY_SOURCE_FACT_JOURNAL_VERSION,
            }
        ]
        outcomes = [
            record
            for record in entries
            if record.get("version") == SOURCE_FACT_OUTCOME_VERSION
        ]
        if outcomes:
            if public_key_path is None:
                raise SourceFactJournalError(
                    "source_fact_outcome_public_key_missing"
                )
            for outcome_record in outcomes:
                _verify_outcome(outcome_record, public_key_path)
                if str(outcome_record.get("outcome")) not in {
                    "committed",
                    "aborted",
                    "unknown",
                }:
                    raise SourceFactJournalError(
                        "source_fact_outcome_value_unsupported"
                    )
            committed_outcomes = [
                record
                for record in outcomes
                if str(record.get("outcome")) == "committed"
            ]
            if committed_outcomes:
                signatures = {
                    str(record.get("statement_signature"))
                    for record in committed_outcomes
                }
                chosen = next(
                    (
                        record
                        for record in prepared
                        if str(record.get("signature")) in signatures
                    ),
                    None,
                )
                if chosen is None:
                    raise SourceFactJournalError(
                        "source_fact_outcome_prepared_fact_missing"
                    )
                committed[key] = chosen
                continue
            if any(
                str(record.get("outcome")) == "unknown"
                for record in outcomes
            ):
                unknown.add(key)
                continue
            aborted.add(key)
            continue
        states: list[tuple[str, dict[str, Any]]] = []
        for record in prepared:
            if record.get("version") == LEGACY_SOURCE_FACT_JOURNAL_VERSION:
                states.append(("legacy", record))
                continue
            status = statuses.get(str(record["database_transaction_id"]))
            normalized = (status or "").strip().lower().replace(" ", "_")
            if normalized == "committed":
                states.append(("committed", record))
            elif normalized == "aborted":
                states.append(("aborted", record))
            elif normalized == "in_progress":
                states.append(("in_progress", record))
            else:
                states.append(("unknown", record))
        if any(state == "committed" for state, _ in states):
            committed[key] = next(record for state, record in states if state == "committed")
        elif any(state == "legacy" for state, _ in states):
            legacy[key] = next(record for state, record in states if state == "legacy")
        elif any(state == "in_progress" for state, _ in states):
            in_progress.add(key)
        elif any(state == "unknown" for state, _ in states):
            unknown.add(key)
        else:
            aborted.add(key)

    journal_tip = None
    if records:
        last = records[-1]
        journal_tip = (
            str(last.get("record_hash") or "") or _record_hash(last)
        )
    return ResolvedSourceFacts(
        committed=committed,
        legacy=legacy,
        aborted=frozenset(aborted),
        in_progress=frozenset(in_progress),
        unknown=frozenset(unknown),
        journal_count=len(records),
        journal_tip=journal_tip,
    )
