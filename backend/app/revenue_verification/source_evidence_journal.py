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
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

SOURCE_FACT_JOURNAL_VERSION = "b26-p2-source-fact-journal-v2"
LEGACY_SOURCE_FACT_JOURNAL_VERSION = "b26-p2-source-fact-journal-v1"
SOURCE_FACT_OUTCOME_VERSION = "b26-p2-source-fact-outcome-v1"


class SourceFactJournalError(RuntimeError):
    """The source-fact journal cannot be read or adjudicated."""


_CURRENT_OUTCOME_CONTEXT: contextvars.ContextVar[
    list[dict[str, Any]] | None
] = contextvars.ContextVar("source_fact_outcome_context", default=None)


@dataclass(frozen=True)
class ResolvedSourceFacts:
    """Journal facts after their PostgreSQL transaction outcomes are resolved."""

    committed: Mapping[tuple[str, str], dict[str, Any]]
    legacy: Mapping[tuple[str, str], dict[str, Any]]
    aborted: frozenset[tuple[str, str]]
    in_progress: frozenset[tuple[str, str]]
    unknown: frozenset[tuple[str, str]]


def _journal_path(path: str | os.PathLike[str] | None = None) -> Path | None:
    configured = str(path or os.getenv("B26_P2_SOURCE_EVIDENCE_JOURNAL_PATH", "")).strip()
    return Path(configured) if configured else None


def _canonical_outcome(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")


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

    if outcome not in {"committed", "aborted"}:
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
    line = json.dumps(
        {
            **payload,
            "signature": "ed25519:"
            + base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii"),
            "key_sha256": __import__("hashlib").sha256(public_raw).hexdigest(),
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    journal.parent.mkdir(parents=True, exist_ok=True)
    with journal.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
        handle.flush()
        os.fsync(handle.fileno())


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
    try:
        yield
    except Exception:
        for fact in facts:
            try:
                append_source_fact_outcome(
                    record=fact,
                    outcome="aborted",
                    private_key_path=private_key_path,
                    path=fact.get("path"),
                )
            except Exception:  # noqa: BLE001 - preserve the original failure
                pass
        raise
    else:
        for fact in facts:
            append_source_fact_outcome(
                record=fact,
                outcome="committed",
                private_key_path=private_key_path,
                path=fact.get("path"),
            )
    finally:
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
    line = json.dumps(record, sort_keys=True, separators=(",", ":"), default=str)
    with journal.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
        handle.flush()
        os.fsync(handle.fileno())
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
    with journal.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            version = record.get("version")
            if version not in {
                SOURCE_FACT_JOURNAL_VERSION,
                LEGACY_SOURCE_FACT_JOURNAL_VERSION,
                SOURCE_FACT_OUTCOME_VERSION,
            }:
                raise SourceFactJournalError(
                    "source_fact_journal_version_unsupported"
                )
            if version == SOURCE_FACT_JOURNAL_VERSION and not str(
                record.get("database_transaction_id") or ""
            ).strip():
                raise SourceFactJournalError(
                    "source_fact_journal_transaction_identity_missing"
                )
            records.append(record)
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
                "SELECT xid::text, pg_xact_status(xid::xid8)::text"
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
    transaction_ids = {
        str(record["database_transaction_id"])
        for record in records
        if record.get("version") == SOURCE_FACT_JOURNAL_VERSION
    }
    statuses = await _transaction_statuses(session, transaction_ids)

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for record in records:
        grouped.setdefault(
            (str(record["fact_kind"]), str(record["fact_id"])), []
        ).append(record)

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

    return ResolvedSourceFacts(
        committed=committed,
        legacy=legacy,
        aborted=frozenset(aborted),
        in_progress=frozenset(in_progress),
        unknown=frozenset(unknown),
    )
