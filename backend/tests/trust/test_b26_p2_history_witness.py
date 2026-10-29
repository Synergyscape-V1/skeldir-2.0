from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.core.config import settings
from app.trust import history_witness, witness_anchor
from app.trust.builder import _verify_signed_history_witness
from app.trust.history_witness import (
    HistoryWitnessError,
    append_checkpoint,
    generate_keypair,
    load_custody,
    load_public_key,
    public_key_fingerprint,
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
    monkeypatch.setattr(
        settings,
        "B26_P2_HISTORY_WITNESS_HEARTBEAT_PATH",
        str(tmp_path / "heartbeat.json"),
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
        custody_path=settings.B26_P2_HISTORY_WITNESS_CUSTODY_PATH,
        heartbeat_path=settings.B26_P2_HISTORY_WITNESS_HEARTBEAT_PATH,
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

def test_unchanged_count_publishes_heartbeat_without_appending(
    tmp_path: Path,
) -> None:
    private_path, public_path = _witness_files(tmp_path)
    journal = tmp_path / "journal.jsonl"
    custody = tmp_path / "custody.json"
    heartbeat = tmp_path / "heartbeat.json"
    first = append_checkpoint(
        journal,
        private_key_path=private_path,
        ledger_count=1,
        ledger_tip_seq=1,
        ledger_tip_hash="1" * 64,
        ledger_prefix_digest="a" * 64,
        authority_universe=UNIVERSE,
        custody_path=custody,
        heartbeat_path=heartbeat,
    )
    journal_bytes = journal.read_bytes()
    refreshed = append_checkpoint(
        journal,
        private_key_path=private_path,
        ledger_count=1,
        ledger_tip_seq=1,
        ledger_tip_hash="1" * 64,
        ledger_prefix_digest="a" * 64,
        authority_universe=UNIVERSE,
        custody_path=custody,
        heartbeat_path=heartbeat,
        observed_at=first.observed_at + timedelta(seconds=30),
    )
    assert journal.read_bytes() == journal_bytes
    assert refreshed.checkpoint_hash == first.checkpoint_hash
    assert heartbeat.exists()
    verified = verify_journal(
        journal,
        public_key_path=public_path,
        expected_count=1,
        expected_tip_hash="1" * 64,
        expected_universe=UNIVERSE,
        require_universe=True,
        require_freshness=True,
        freshness_seconds=1200,
        heartbeat_path=heartbeat,
    )
    assert verified.latest.checkpoint_hash == first.checkpoint_hash
    assert load_custody(custody)["ledger_count"] == 1


def test_same_count_retry_does_not_fork_custody(tmp_path: Path) -> None:
    private_path, public_path = _witness_files(tmp_path)
    journal = tmp_path / "journal.jsonl"
    custody = tmp_path / "custody.json"
    heartbeat = tmp_path / "heartbeat.json"
    first = append_checkpoint(
        journal,
        private_key_path=private_path,
        ledger_count=2,
        ledger_tip_seq=2,
        ledger_tip_hash="2" * 64,
        ledger_prefix_digest="b" * 64,
        authority_universe=UNIVERSE,
        custody_path=custody,
        heartbeat_path=heartbeat,
    )
    for offset in (1, 2, 3):
        append_checkpoint(
            journal,
            private_key_path=private_path,
            ledger_count=2,
            ledger_tip_seq=2,
            ledger_tip_hash="2" * 64,
            ledger_prefix_digest="b" * 64,
            authority_universe=UNIVERSE,
            custody_path=custody,
            heartbeat_path=heartbeat,
            observed_at=first.observed_at + timedelta(seconds=offset),
        )
    assert len(journal.read_text(encoding="utf-8").splitlines()) == 1
    assert load_custody(custody)["ledger_count"] == 2
    verify_journal(
        journal,
        public_key_path=public_path,
        expected_count=2,
        heartbeat_path=heartbeat,
        require_freshness=False,
    )


def test_missing_custody_after_journal_is_refused(tmp_path: Path) -> None:
    private_path, _public_path = _witness_files(tmp_path)
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
    custody.unlink()
    with pytest.raises(HistoryWitnessError, match="witness_custody_missing"):
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


def test_custody_write_failure_restores_journal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    private_path, _public_path = _witness_files(tmp_path)
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
    journal_bytes = journal.read_bytes()
    custody_bytes = custody.read_bytes()

    def _fail_custody(*_args: object, **_kwargs: object) -> None:
        raise OSError("simulated custody outage")

    monkeypatch.setattr(history_witness, "_write_custody", _fail_custody)
    with pytest.raises(OSError, match="simulated custody outage"):
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
    assert journal.read_bytes() == journal_bytes
    assert custody.read_bytes() == custody_bytes


def test_custody_ahead_of_journal_is_refused(tmp_path: Path) -> None:
    private_path, _public_path = _witness_files(tmp_path)
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
    with pytest.raises(HistoryWitnessError, match="witness_custody_rollback"):
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


def test_source_evidence_divergence_without_ledger_is_refused(
    tmp_path: Path,
) -> None:
    private_path, _public_path = _witness_files(tmp_path)
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
        source_evidence_digest="c" * 64,
    )
    with pytest.raises(
        HistoryWitnessError,
        match="witness_source_evidence_diverged_without_ledger",
    ):
        append_checkpoint(
            journal,
            private_key_path=private_path,
            ledger_count=1,
            ledger_tip_seq=1,
            ledger_tip_hash="1" * 64,
            ledger_prefix_digest="a" * 64,
            authority_universe=UNIVERSE,
            custody_path=custody,
            source_evidence_digest="d" * 64,
        )


def test_tampered_heartbeat_is_refused(tmp_path: Path) -> None:
    private_path, public_path = _witness_files(tmp_path)
    journal = tmp_path / "journal.jsonl"
    custody = tmp_path / "custody.json"
    heartbeat = tmp_path / "heartbeat.json"
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
    append_checkpoint(
        journal,
        private_key_path=private_path,
        ledger_count=1,
        ledger_tip_seq=1,
        ledger_tip_hash="1" * 64,
        ledger_prefix_digest="a" * 64,
        authority_universe=UNIVERSE,
        custody_path=custody,
        heartbeat_path=heartbeat,
        observed_at=first.observed_at + timedelta(seconds=5),
    )
    payload = json.loads(heartbeat.read_text(encoding="utf-8"))
    payload["payload"]["ledger_count"] = 2
    heartbeat.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(HistoryWitnessError, match="witness_heartbeat"):
        verify_journal(
            journal,
            public_key_path=public_path,
            require_freshness=False,
            heartbeat_path=heartbeat,
        )


def test_public_key_fingerprint_is_stable(tmp_path: Path) -> None:
    _private_path, public_path = _witness_files(tmp_path)
    from app.trust.history_witness import load_public_key

    key = load_public_key(public_path)
    assert public_key_fingerprint(key) == public_key_fingerprint(key)
    assert len(public_key_fingerprint(key)) == 64


def _production_anchor_fixture(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> tuple[Path, Path, object, str]:
    private_path, public_path = _witness_files(tmp_path)
    journal = _enable(monkeypatch, tmp_path, public=public_path)
    digest = hashlib.sha256(b"").hexdigest()
    checkpoint = append_checkpoint(
        journal,
        private_key_path=private_path,
        ledger_count=0,
        ledger_tip_seq=None,
        ledger_tip_hash=None,
        ledger_prefix_digest=digest,
        authority_universe=UNIVERSE,
        custody_path=settings.B26_P2_HISTORY_WITNESS_CUSTODY_PATH,
        heartbeat_path=settings.B26_P2_HISTORY_WITNESS_HEARTBEAT_PATH,
    )
    fingerprint = public_key_fingerprint(load_public_key(public_path))
    # XXV (HB-01): the fixture used to set ENVIRONMENT="production" -- a value
    # resolve_control_plane_env never produces, because it canonicalises that
    # alias to "prod" before Settings stores it. So these cells proved the
    # anchor guard worked only in a state no deployment can be in, while the
    # guard was unreachable in every real process. The fixture now uses the
    # canonical value, and the guard itself no longer depends on it.
    monkeypatch.setattr(settings, "ENVIRONMENT", "prod")
    return journal, public_path, checkpoint, fingerprint


def test_production_compiled_anchor_missing_refuses(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _journal, _public, _checkpoint, _fingerprint = _production_anchor_fixture(
        monkeypatch, tmp_path
    )
    monkeypatch.setattr(witness_anchor, "COMPILED_PUBLIC_KEY_SHA256", None)
    monkeypatch.setattr(witness_anchor, "COMPILED_GENESIS_HASH", None)
    accepted, reason = _verify_signed_history_witness(
        ledger_count=0,
        ledger_tip_hash=None,
        ledger_prefix_digest=hashlib.sha256(b"").hexdigest(),
        authority_universe=UNIVERSE,
    )
    assert accepted is False
    assert reason.endswith("witness_compiled_anchor_missing")


def test_production_compiled_genesis_mismatch_refuses(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _journal, _public, _checkpoint, fingerprint = _production_anchor_fixture(
        monkeypatch, tmp_path
    )
    monkeypatch.setattr(
        witness_anchor, "COMPILED_PUBLIC_KEY_SHA256", fingerprint
    )
    monkeypatch.setattr(
        witness_anchor, "COMPILED_GENESIS_HASH", "0" * 64
    )
    monkeypatch.setattr(
        settings, "B26_P2_HISTORY_WITNESS_GENESIS_HASH", "1" * 64
    )
    accepted, reason = _verify_signed_history_witness(
        ledger_count=0,
        ledger_tip_hash=None,
        ledger_prefix_digest=hashlib.sha256(b"").hexdigest(),
        authority_universe=UNIVERSE,
    )
    assert accepted is False
    assert reason.endswith("witness_compiled_genesis_mismatch")


def test_production_compiled_public_key_mismatch_refuses(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _journal, _public, checkpoint, _fingerprint = _production_anchor_fixture(
        monkeypatch, tmp_path
    )
    monkeypatch.setattr(
        witness_anchor, "COMPILED_PUBLIC_KEY_SHA256", "0" * 64
    )
    monkeypatch.setattr(
        witness_anchor, "COMPILED_GENESIS_HASH", checkpoint.checkpoint_hash
    )
    monkeypatch.setattr(
        settings,
        "B26_P2_HISTORY_WITNESS_GENESIS_HASH",
        checkpoint.checkpoint_hash,
    )
    accepted, reason = _verify_signed_history_witness(
        ledger_count=0,
        ledger_tip_hash=None,
        ledger_prefix_digest=hashlib.sha256(b"").hexdigest(),
        authority_universe=UNIVERSE,
    )
    assert accepted is False
    assert reason.endswith("witness_compiled_public_key_mismatch")


def test_production_missing_custody_refuses(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _journal, _public, checkpoint, fingerprint = _production_anchor_fixture(
        monkeypatch, tmp_path
    )
    monkeypatch.setattr(
        witness_anchor, "COMPILED_PUBLIC_KEY_SHA256", fingerprint
    )
    monkeypatch.setattr(
        witness_anchor, "COMPILED_GENESIS_HASH", checkpoint.checkpoint_hash
    )
    monkeypatch.setattr(
        settings,
        "B26_P2_HISTORY_WITNESS_GENESIS_HASH",
        checkpoint.checkpoint_hash,
    )
    # XXV: the fixture now publishes custody with the checkpoint (a lawful
    # observer always does), so the custody record has to be REMOVED to
    # exercise the loss this cell governs -- which is exactly the capability
    # both independent audits used.
    Path(settings.B26_P2_HISTORY_WITNESS_CUSTODY_PATH).unlink()
    accepted, reason = _verify_signed_history_witness(
        ledger_count=0,
        ledger_tip_hash=None,
        ledger_prefix_digest=hashlib.sha256(b"").hexdigest(),
        authority_universe=UNIVERSE,
    )
    assert accepted is False
    assert reason.endswith("witness_custody_missing")


def test_xxv_compiled_anchor_mismatch_refuses_outside_production(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """XXV (HB-01/A1): the anchor comparison is not behind an environment.

    Both XXIV audits replaced the entire witness verification root and kept
    receiving signed envelopes, because the comparison sat behind
    ``settings.ENVIRONMENT == "production"`` -- unreachable after
    canonicalisation. The comparison now fires wherever the image carries an
    anchor, which this cell asserts in a NON-production environment: if the
    guard were still environment-gated, the mismatch below would be ignored.
    """
    private_path, public_path = _witness_files(tmp_path)
    journal = _enable(monkeypatch, tmp_path, public=public_path)
    digest = hashlib.sha256(b"").hexdigest()
    append_checkpoint(
        journal,
        private_key_path=private_path,
        ledger_count=0,
        ledger_tip_seq=None,
        ledger_tip_hash=None,
        ledger_prefix_digest=digest,
        authority_universe=UNIVERSE,
        custody_path=settings.B26_P2_HISTORY_WITNESS_CUSTODY_PATH,
        heartbeat_path=settings.B26_P2_HISTORY_WITNESS_HEARTBEAT_PATH,
    )
    monkeypatch.setattr(settings, "ENVIRONMENT", "ci")
    monkeypatch.setattr(witness_anchor, "COMPILED_PUBLIC_KEY_SHA256", "f" * 64)
    monkeypatch.setattr(
        witness_anchor,
        "COMPILED_GENESIS_HASH",
        settings.B26_P2_HISTORY_WITNESS_GENESIS_HASH or "e" * 64,
    )
    accepted, reason = _verify_signed_history_witness(
        ledger_count=0,
        ledger_tip_hash=None,
        ledger_prefix_digest=digest,
        authority_universe=UNIVERSE,
    )
    assert accepted is False
    assert "witness_compiled_" in reason


def test_xxv_missing_custody_refuses_outside_production(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """XXV (HB-02/A5): custody loss refuses everywhere, not only in "production".

    Nicholas deleted the custody record on a production-configured deployment
    and received HTTP 200 with a signed envelope for a subject that had never
    been issued; Trey reproduced it. The refusal was written, but behind the
    same unreachable environment literal.
    """
    private_path, public_path = _witness_files(tmp_path)
    journal = _enable(monkeypatch, tmp_path, public=public_path)
    digest = hashlib.sha256(b"").hexdigest()
    append_checkpoint(
        journal,
        private_key_path=private_path,
        ledger_count=0,
        ledger_tip_seq=None,
        ledger_tip_hash=None,
        ledger_prefix_digest=digest,
        authority_universe=UNIVERSE,
        custody_path=settings.B26_P2_HISTORY_WITNESS_CUSTODY_PATH,
        heartbeat_path=settings.B26_P2_HISTORY_WITNESS_HEARTBEAT_PATH,
    )
    monkeypatch.setattr(settings, "ENVIRONMENT", "ci")
    assert _verify_signed_history_witness(
        ledger_count=0,
        ledger_tip_hash=None,
        ledger_prefix_digest=digest,
        authority_universe=UNIVERSE,
    ) == (True, "")

    Path(settings.B26_P2_HISTORY_WITNESS_CUSTODY_PATH).unlink()
    accepted, reason = _verify_signed_history_witness(
        ledger_count=0,
        ledger_tip_hash=None,
        ledger_prefix_digest=digest,
        authority_universe=UNIVERSE,
    )
    assert accepted is False
    assert reason.endswith("witness_custody_missing")
