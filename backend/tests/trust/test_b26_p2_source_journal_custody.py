"""Signed custody export/restore for the XXV source-evidence journal."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app.revenue_verification.source_attestation import generate_keypair
from app.revenue_verification.source_evidence_journal import (
    append_source_fact,
    journal_record_hash,
    load_source_fact_records,
)
from app.revenue_verification.source_journal_custody import (
    SourceJournalCustodyError,
    export_custody_bundle,
    restore_custody_bundle,
    verify_custody_bundle,
)


def _append(journal: Path, fact_id: str, xid: str) -> None:
    append_source_fact(
        fact_kind="source_money",
        fact_id=fact_id,
        tenant_id="custody-tenant",
        verdict_id="custody-verdict",
        statement={"id": fact_id},
        signature="sig",
        key_sha256="k",
        database_transaction_id=xid,
        path=journal,
    )


def _keys(tmp_path: Path) -> tuple[Path, Path]:
    private_seed, public_b64 = generate_keypair()
    private_path = tmp_path / "custody.key"
    public_path = tmp_path / "custody.pub"
    private_path.write_text(private_seed, encoding="utf-8")
    public_path.write_text(public_b64, encoding="utf-8")
    return private_path, public_path


def _manifest(bundle_dir: Path) -> Path:
    manifests = sorted(bundle_dir.glob("*.manifest.json"))
    assert len(manifests) == 1
    return manifests[0]


def test_export_verify_and_restore_preserve_committed_records(tmp_path: Path) -> None:
    private_path, public_path = _keys(tmp_path)
    journal = tmp_path / "live.jsonl"
    _append(journal, "s1", "100")
    _append(journal, "s2", "200")
    custody = tmp_path / "custody"

    exported = export_custody_bundle(
        journal=journal,
        custody_dir=custody,
        private_key_path=private_path,
    )
    verified = verify_custody_bundle(
        manifest_path=exported.manifest_path,
        public_key_path=public_path,
    )
    assert verified.manifest["record_count"] == 2

    restored = tmp_path / "restored.jsonl"
    disposition = restore_custody_bundle(
        manifest_path=exported.manifest_path,
        journal=restored,
        public_key_path=public_path,
    )
    assert disposition == "restored"
    assert load_source_fact_records(restored) == load_source_fact_records(journal)


def test_restore_never_overwrites_newer_committed_history(tmp_path: Path) -> None:
    private_path, public_path = _keys(tmp_path)
    journal = tmp_path / "live.jsonl"
    _append(journal, "s1", "100")
    custody = tmp_path / "custody"
    exported = export_custody_bundle(
        journal=journal,
        custody_dir=custody,
        private_key_path=private_path,
    )
    _append(journal, "s2", "200")
    before = load_source_fact_records(journal)

    disposition = restore_custody_bundle(
        manifest_path=exported.manifest_path,
        journal=journal,
        public_key_path=public_path,
    )
    assert disposition == "live_is_newer"
    assert load_source_fact_records(journal) == before


def test_divergent_live_journal_is_refused(tmp_path: Path) -> None:
    private_path, public_path = _keys(tmp_path)
    journal = tmp_path / "live.jsonl"
    _append(journal, "s1", "100")
    custody = tmp_path / "custody"
    exported = export_custody_bundle(
        journal=journal,
        custody_dir=custody,
        private_key_path=private_path,
    )
    divergent = tmp_path / "other.jsonl"
    _append(divergent, "other", "999")

    with pytest.raises(SourceJournalCustodyError, match="restore_diverged"):
        restore_custody_bundle(
            manifest_path=exported.manifest_path,
            journal=divergent,
            public_key_path=public_path,
        )


def test_bundle_tamper_and_signature_tamper_are_refused(tmp_path: Path) -> None:
    private_path, public_path = _keys(tmp_path)
    journal = tmp_path / "live.jsonl"
    _append(journal, "s1", "100")
    custody = tmp_path / "custody"
    exported = export_custody_bundle(
        journal=journal,
        custody_dir=custody,
        private_key_path=private_path,
    )
    bundle_path = exported.manifest_path.with_name(
        exported.manifest_path.name.replace(".manifest.json", ".jsonl")
    )
    raw = bundle_path.read_bytes()
    os.chmod(bundle_path, 0o644)
    bundle_path.write_bytes(raw.replace(b"s1", b"s9", 1))
    with pytest.raises(SourceJournalCustodyError, match="digest_mismatch"):
        verify_custody_bundle(
            manifest_path=exported.manifest_path,
            public_key_path=public_path,
        )

    bundle_path.write_bytes(raw)
    os.chmod(exported.manifest_path, 0o644)
    manifest = json.loads(exported.manifest_path.read_text(encoding="utf-8"))
    manifest["record_count"] = 99
    exported.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(SourceJournalCustodyError, match="signature_invalid"):
        verify_custody_bundle(
            manifest_path=exported.manifest_path,
            public_key_path=public_path,
        )



def test_valid_live_prefix_is_extended_to_archived_commitment(tmp_path: Path) -> None:
    private_path, public_path = _keys(tmp_path)
    journal = tmp_path / "live.jsonl"
    _append(journal, "s1", "100")
    _append(journal, "s2", "200")
    _append(journal, "s3", "300")
    custody = tmp_path / "custody"
    exported = export_custody_bundle(
        journal=journal,
        custody_dir=custody,
        private_key_path=private_path,
    )
    lines = journal.read_bytes().splitlines(keepends=True)
    journal.write_bytes(b"".join(lines[:2]))

    disposition = restore_custody_bundle(
        manifest_path=exported.manifest_path,
        journal=journal,
        public_key_path=public_path,
    )
    assert disposition == "restored_prefix"
    restored = load_source_fact_records(journal)
    assert restored is not None
    assert [record["fact_id"] for record in restored] == ["s1", "s2", "s3"]


def test_retry_completes_interrupted_publication(tmp_path: Path) -> None:
    private_path, public_path = _keys(tmp_path)
    journal = tmp_path / "live.jsonl"
    _append(journal, "s1", "100")
    custody = tmp_path / "custody"
    exported = export_custody_bundle(
        journal=journal,
        custody_dir=custody,
        private_key_path=private_path,
    )
    os.chmod(exported.manifest_path, 0o644)
    exported.manifest_path.unlink()
    assert not exported.manifest_path.exists()

    completed = export_custody_bundle(
        journal=journal,
        custody_dir=custody,
        private_key_path=private_path,
    )
    assert completed.manifest_path.exists()
    assert verify_custody_bundle(
        manifest_path=completed.manifest_path,
        public_key_path=public_path,
    ).manifest["record_count"] == 1



def test_restore_at_or_above_accepted_witness_prefix_is_allowed(tmp_path: Path) -> None:
    private_path, public_path = _keys(tmp_path)
    journal = tmp_path / "live.jsonl"
    _append(journal, "s1", "100")
    _append(journal, "s2", "200")
    _append(journal, "s3", "300")
    records = load_source_fact_records(journal)
    assert records is not None
    custody = tmp_path / "custody"
    exported = export_custody_bundle(
        journal=journal,
        custody_dir=custody,
        private_key_path=private_path,
    )
    restored = tmp_path / "restored.jsonl"
    disposition = restore_custody_bundle(
        manifest_path=exported.manifest_path,
        journal=restored,
        public_key_path=public_path,
        accepted_source_count=2,
        accepted_source_tip=journal_record_hash(records[1]),
    )
    assert disposition == "restored"
    assert len(load_source_fact_records(restored) or []) == 3
def test_restore_below_accepted_witness_prefix_is_refused(tmp_path: Path) -> None:
    private_path, public_path = _keys(tmp_path)
    journal = tmp_path / "live.jsonl"
    _append(journal, "s1", "100")
    _append(journal, "s2", "200")
    custody = tmp_path / "custody"
    exported = export_custody_bundle(
        journal=journal,
        custody_dir=custody,
        private_key_path=private_path,
    )
    with pytest.raises(
        SourceJournalCustodyError,
        match="restore_below_accepted_commitment",
    ):
        restore_custody_bundle(
            manifest_path=exported.manifest_path,
            journal=tmp_path / "empty.jsonl",
            public_key_path=public_path,
            accepted_source_count=3,
            accepted_source_tip="f" * 64,
        )
def test_empty_committed_journal_round_trips(tmp_path: Path) -> None:
    private_path, public_path = _keys(tmp_path)
    journal = tmp_path / "empty.jsonl"
    journal.write_bytes(b"")
    custody = tmp_path / "custody"
    exported = export_custody_bundle(
        journal=journal,
        custody_dir=custody,
        private_key_path=private_path,
    )
    assert exported.manifest["record_count"] == 0
    restored = tmp_path / "restored.jsonl"
    assert (
        restore_custody_bundle(
            manifest_path=exported.manifest_path,
            journal=restored,
            public_key_path=public_path,
        )
        == "already_current"
    )
    assert load_source_fact_records(restored) == []
