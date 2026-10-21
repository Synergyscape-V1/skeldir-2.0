from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.core.config import settings
from app.trust.builder import _verify_signed_history_witness
from app.trust.history_witness import (
    HistoryWitnessError,
    append_checkpoint,
    generate_keypair,
    load_custody,
    verify_journal,
)

UNIVERSE = "11111111-1111-1111-1111-111111111111"
OTHER_UNIVERSE = "22222222-2222-2222-2222-222222222222"


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
    monkeypatch.setattr(
        settings,
        "B26_P2_HISTORY_WITNESS_CUSTODY_PATH",
        str(tmp_path / "custody.json"),
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
        authority_universe=UNIVERSE,
    )

    assert _verify_signed_history_witness(
        ledger_count=2,
        ledger_tip_hash="b" * 64,
        ledger_prefix_digest=digest,
        authority_universe=UNIVERSE,
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
        authority_universe=UNIVERSE,
    )

    ok, reason = _verify_signed_history_witness(
        ledger_count=2,
        ledger_tip_hash="c" * 64,
        ledger_prefix_digest=digest,
        authority_universe=UNIVERSE,
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
        authority_universe=UNIVERSE,
    )

    ok, reason = _verify_signed_history_witness(
        ledger_count=2,
        ledger_tip_hash="b" * 64,
        ledger_prefix_digest="d" * 64,
        authority_universe=UNIVERSE,
    )
    assert ok is False
    assert reason.endswith("witness_live_prefix_diverged")


def test_witness_gate_refuses_foreign_universe(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    private_path, public_path = _witness_files(tmp_path)
    journal = _enable(monkeypatch, tmp_path, public=public_path)
    append_checkpoint(
        journal,
        private_key_path=private_path,
        ledger_count=1,
        ledger_tip_seq=1,
        ledger_tip_hash="b" * 64,
        ledger_prefix_digest="a" * 64,
        authority_universe=UNIVERSE,
    )

    ok, reason = _verify_signed_history_witness(
        ledger_count=1,
        ledger_tip_hash="b" * 64,
        ledger_prefix_digest="a" * 64,
        authority_universe=OTHER_UNIVERSE,
    )
    assert ok is False
    assert reason.endswith("witness_live_universe_diverged")


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
        authority_universe=UNIVERSE,
    )

    ok, reason = _verify_signed_history_witness(
        ledger_count=0,
        ledger_tip_hash=None,
        ledger_prefix_digest="e" * 64,
        authority_universe=UNIVERSE,
    )
    assert ok is False
    assert reason.endswith("witness_checkpoint_stale")


def test_lawful_growth_appends_and_advances(tmp_path: Path) -> None:
    private_path, public_path = _witness_files(tmp_path)
    journal = tmp_path / "journal.jsonl"
    custody = tmp_path / "custody.json"
    first = append_checkpoint(
        journal,
        private_key_path=private_path,
        ledger_count=1,
        ledger_tip_seq=1,
        ledger_tip_hash="1" * 64,
        ledger_prefix_digest="a" * 64,
        authority_universe=UNIVERSE,
        custody_path=custody,
    )
    second = append_checkpoint(
        journal,
        private_key_path=private_path,
        ledger_count=2,
        ledger_tip_seq=2,
        ledger_tip_hash="2" * 64,
        ledger_prefix_digest="b" * 64,
        authority_universe=UNIVERSE,
        prefix_anchor_seq=first.ledger_tip_seq,
        prefix_anchor_hash=first.ledger_tip_hash,
        custody_path=custody,
    )
    verified = verify_journal(
        journal,
        public_key_path=public_path,
        expected_count=2,
        expected_tip_hash="2" * 64,
        expected_universe=UNIVERSE,
        require_universe=True,
        require_freshness=False,
    )
    assert verified.latest.checkpoint_hash == second.checkpoint_hash
    assert load_custody(custody)["ledger_count"] == 2


def test_growth_without_previous_tip_anchor_is_refused(tmp_path: Path) -> None:
    private_path, _public_path = _witness_files(tmp_path)
    journal = tmp_path / "journal.jsonl"
    append_checkpoint(
        journal,
        private_key_path=private_path,
        ledger_count=1,
        ledger_tip_seq=1,
        ledger_tip_hash="1" * 64,
        ledger_prefix_digest="a" * 64,
        authority_universe=UNIVERSE,
    )
    with pytest.raises(HistoryWitnessError) as excinfo:
        append_checkpoint(
            journal,
            private_key_path=private_path,
            ledger_count=2,
            ledger_tip_seq=2,
            ledger_tip_hash="2" * 64,
            ledger_prefix_digest="b" * 64,
            authority_universe=UNIVERSE,
            prefix_anchor_seq=None,
            prefix_anchor_hash=None,
        )
    assert "witness_history_prefix_diverged" in str(excinfo.value)


def test_custody_refuses_replayed_journal_prefix(tmp_path: Path) -> None:
    private_path, public_path = _witness_files(tmp_path)
    journal = tmp_path / "journal.jsonl"
    custody = tmp_path / "custody.json"
    append_checkpoint(
        journal,
        private_key_path=private_path,
        ledger_count=1,
        ledger_tip_seq=1,
        ledger_tip_hash="1" * 64,
        ledger_prefix_digest="a" * 64,
        authority_universe=UNIVERSE,
        custody_path=custody,
    )
    saved_prefix = journal.read_bytes()
    append_checkpoint(
        journal,
        private_key_path=private_path,
        ledger_count=2,
        ledger_tip_seq=2,
        ledger_tip_hash="2" * 64,
        ledger_prefix_digest="b" * 64,
        authority_universe=UNIVERSE,
        prefix_anchor_seq=1,
        prefix_anchor_hash="1" * 64,
        custody_path=custody,
    )
    journal.write_bytes(saved_prefix)
    replayed = verify_journal(
        journal,
        public_key_path=public_path,
        require_freshness=False,
    )
    recorded = load_custody(custody)
    assert recorded is not None
    assert replayed.latest.ledger_count < int(recorded["ledger_count"])
