from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.core.config import settings
from app.trust.builder import _verify_signed_history_witness
from app.trust.history_witness import append_checkpoint, generate_keypair


def _witness_files(tmp_path: Path) -> tuple[Path, Path]:
    private_seed, public_key = generate_keypair()
    private_path = tmp_path / "witness.ed25519"
    public_path = tmp_path / "witness.ed25519.pub"
    private_path.write_text(private_seed, encoding="utf-8")
    public_path.write_text(public_key, encoding="utf-8")
    return private_path, public_path


def _enable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, **paths: Path) -> Path:
    journal = tmp_path / "journal.jsonl"
    monkeypatch.setattr(settings, "B26_P2_HISTORY_WITNESS_REQUIRED", True)
    monkeypatch.setattr(
        settings, "B26_P2_HISTORY_WITNESS_JOURNAL_PATH", str(journal)
    )
    monkeypatch.setattr(
        settings,
        "B26_P2_HISTORY_WITNESS_PUBLIC_KEY_PATH",
        str(paths["public"]),
    )
    monkeypatch.setattr(settings, "B26_P2_HISTORY_WITNESS_GENESIS_HASH", None)
    return journal


def test_witness_gate_admits_matching_live_state(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    private_path, public_path = _witness_files(tmp_path)
    journal = _enable(monkeypatch, tmp_path, public=public_path)
    digest = "a" * 64
    append_checkpoint(
        journal,
        private_key_path=private_path,
        ledger_count=2,
        ledger_tip_seq=2,
        ledger_tip_hash="b" * 64,
        ledger_prefix_digest=digest,
    )

    assert _verify_signed_history_witness(
        ledger_count=2,
        ledger_tip_hash="b" * 64,
        ledger_prefix_digest=digest,
    ) == (True, "")


def test_witness_gate_refuses_live_tip_divergence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    private_path, public_path = _witness_files(tmp_path)
    journal = _enable(monkeypatch, tmp_path, public=public_path)
    digest = "a" * 64
    append_checkpoint(
        journal,
        private_key_path=private_path,
        ledger_count=2,
        ledger_tip_seq=2,
        ledger_tip_hash="b" * 64,
        ledger_prefix_digest=digest,
    )

    ok, reason = _verify_signed_history_witness(
        ledger_count=2,
        ledger_tip_hash="c" * 64,
        ledger_prefix_digest=digest,
    )
    assert ok is False
    assert reason.endswith("witness_live_tip_diverged")


def test_witness_gate_refuses_prefix_divergence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    private_path, public_path = _witness_files(tmp_path)
    journal = _enable(monkeypatch, tmp_path, public=public_path)
    append_checkpoint(
        journal,
        private_key_path=private_path,
        ledger_count=2,
        ledger_tip_seq=2,
        ledger_tip_hash="b" * 64,
        ledger_prefix_digest="a" * 64,
    )

    ok, reason = _verify_signed_history_witness(
        ledger_count=2,
        ledger_tip_hash="b" * 64,
        ledger_prefix_digest="d" * 64,
    )
    assert ok is False
    assert reason.endswith("witness_live_prefix_diverged")


def test_witness_gate_refuses_stale_checkpoint(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    private_path, public_path = _witness_files(tmp_path)
    journal = _enable(monkeypatch, tmp_path, public=public_path)
    append_checkpoint(
        journal,
        private_key_path=private_path,
        ledger_count=0,
        ledger_tip_seq=None,
        ledger_tip_hash=None,
        ledger_prefix_digest="e" * 64,
        observed_at=datetime.now(timezone.utc) - timedelta(hours=2),
    )

    ok, reason = _verify_signed_history_witness(
        ledger_count=0,
        ledger_tip_hash=None,
        ledger_prefix_digest="e" * 64,
    )
    assert ok is False
    assert reason.endswith("witness_checkpoint_stale")
