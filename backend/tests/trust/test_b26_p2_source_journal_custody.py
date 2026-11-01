"""Signed custody export/restore for the XXV source-evidence journal."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app.revenue_verification.source_attestation import generate_keypair
from app.revenue_verification.source_evidence_journal import (
    append_source_fact,
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
        == "restored"
    )
    assert load_source_fact_records(restored) == []
