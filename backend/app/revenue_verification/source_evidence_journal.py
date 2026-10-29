"""Append-only, authentication-root-signed source facts.

The database rows are writable by the maintenance principal.  The
authentication root signs each source or adjustment statement; this journal
records that signed fact at the moment it is produced, outside the database
principal's control.  Readers require a current database fact to have its
signed journal entry, so deleting the database row after authentication is
detectable even before the periodic history observer runs.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

SOURCE_FACT_JOURNAL_VERSION = "b26-p2-source-fact-journal-v1"


def _journal_path(path: str | os.PathLike[str] | None = None) -> Path | None:
    configured = str(path or os.getenv("B26_P2_SOURCE_EVIDENCE_JOURNAL_PATH", "")).strip()
    return Path(configured) if configured else None


def append_source_fact(
    *,
    fact_kind: str,
    fact_id: str,
    tenant_id: str,
    verdict_id: str,
    statement: Mapping[str, Any],
    signature: str,
    key_sha256: str,
    path: str | os.PathLike[str] | None = None,
) -> None:
    """Append one already-signed fact.  The statement signature is the seal."""

    journal = _journal_path(path)
    if journal is None:
        return
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
    }
    line = json.dumps(record, sort_keys=True, separators=(",", ":"), default=str)
    with journal.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def load_source_facts(
    path: str | os.PathLike[str] | None = None,
) -> dict[tuple[str, str], dict[str, Any]] | None:
    """Return signed facts keyed by (kind, id), or None when no journal is configured."""

    journal = _journal_path(path)
    if journal is None:
        return None
    if not journal.exists():
        return {}
    facts: dict[tuple[str, str], dict[str, Any]] = {}
    with journal.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if record.get("version") != SOURCE_FACT_JOURNAL_VERSION:
                raise ValueError("source_fact_journal_version_unsupported")
            facts[(str(record["fact_kind"]), str(record["fact_id"]))] = record
    return facts
