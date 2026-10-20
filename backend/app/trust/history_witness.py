"""B2.6-P2 Corrective XXII independent history witness.

The supersession ledger lives inside PostgreSQL. Any principal that can act
as the table owner can rewrite it and recompute its internal hash chain, so
ledger-only continuity is not independent evidence. This module keeps a
signed checkpoint journal *outside* the database. The observer process holds
the Ed25519 private key; the builder holds only the public key and refuses to
issue unless the freshest signed checkpoint exactly matches the live ledger
count and tip.

The journal is append-only by convention and each checkpoint commits to the
previous checkpoint hash, so deleting or rearranging entries is detectable.
The private key path and journal path must be writable only by the witness
identity, never by the database principal.
"""

from __future__ import annotations

import base64
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

WITNESS_VERSION = 1
SIGNATURE_PREFIX = "ed25519:"
DEFAULT_KEY_ID = "kid:b26-p2-history-witness-v1"
FUTURE_TOLERANCE_SECONDS = 120


class HistoryWitnessError(ValueError):
    """The independent witness is missing, malformed, stale, or divergent."""


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def _canonical(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def _checkpoint_hash(payload: Mapping[str, Any]) -> str:
    import hashlib

    material = {key: value for key, value in payload.items() if key != "checkpoint_hash"}
    return hashlib.sha256(_canonical(material)).hexdigest()


def _is_sha256_hex(value: str) -> bool:
    if len(value) != 64:
        return False
    return all(char in "0123456789abcdef" for char in value.lower())


def _parse_instant(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise HistoryWitnessError("witness_observed_at_missing")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (ValueError, TypeError) as exc:
        raise HistoryWitnessError("witness_observed_at_malformed") from exc
    if parsed.tzinfo is None:
        raise HistoryWitnessError("witness_observed_at_timezone_required")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class HistoryCheckpoint:
    observed_at: datetime
    ledger_count: int
    ledger_tip_seq: int | None
    ledger_tip_hash: str | None
    ledger_prefix_digest: str | None
    previous_checkpoint_hash: str | None
    checkpoint_hash: str
    key_id: str


@dataclass(frozen=True)
class VerifiedJournal:
    checkpoints: tuple[HistoryCheckpoint, ...]

    @property
    def latest(self) -> HistoryCheckpoint:
        if not self.checkpoints:
            raise HistoryWitnessError("witness_journal_empty")
        return self.checkpoints[-1]

    @property
    def genesis_hash(self) -> str:
        return self.checkpoints[0].checkpoint_hash


def load_private_key(path: str | os.PathLike[str]) -> Ed25519PrivateKey:
    """Load a raw 32-byte Ed25519 seed stored as base64url text."""
    try:
        raw = _b64url_decode(Path(path).read_text(encoding="utf-8").strip())
    except (OSError, ValueError) as exc:
        raise HistoryWitnessError("witness_private_key_unreadable") from exc
    if len(raw) != 32:
        raise HistoryWitnessError("witness_private_key_wrong_length")
    return Ed25519PrivateKey.from_private_bytes(raw)


def load_public_key(path: str | os.PathLike[str]) -> Ed25519PublicKey:
    """Load a raw 32-byte Ed25519 public key stored as base64url text."""
    try:
        raw = _b64url_decode(Path(path).read_text(encoding="utf-8").strip())
    except (OSError, ValueError) as exc:
        raise HistoryWitnessError("witness_public_key_unreadable") from exc
    if len(raw) != 32:
        raise HistoryWitnessError("witness_public_key_wrong_length")
    return Ed25519PublicKey.from_public_bytes(raw)


def generate_keypair() -> tuple[str, str]:
    """Create a new keypair as (private_seed_b64url, public_key_b64url)."""
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        NoEncryption,
        PrivateFormat,
        PublicFormat,
    )

    private_key = Ed25519PrivateKey.generate()
    private_raw = private_key.private_bytes(
        encoding=Encoding.Raw,
        format=PrivateFormat.Raw,
        encryption_algorithm=NoEncryption(),
    )
    public_raw = private_key.public_key().public_bytes(
        encoding=Encoding.Raw,
        format=PublicFormat.Raw,
    )
    return _b64url_encode(private_raw), _b64url_encode(public_raw)


def _signature_material(payload: Mapping[str, Any]) -> bytes:
    return _canonical(payload)


def append_checkpoint(
    journal_path: str | os.PathLike[str],
    *,
    private_key_path: str | os.PathLike[str],
    ledger_count: int,
    ledger_tip_seq: int | None,
    ledger_tip_hash: str | None,
    ledger_prefix_digest: str | None = None,
    key_id: str = DEFAULT_KEY_ID,
    observed_at: datetime | None = None,
    genesis_hash: str | None = None,
) -> HistoryCheckpoint:
    """Verify the existing journal, then atomically append one checkpoint."""
    journal = Path(journal_path)
    private_key = load_private_key(private_key_path)
    try:
        existing = verify_journal(
            journal,
            public_key_path=None,
            public_key=private_key.public_key(),
            genesis_hash=genesis_hash,
            require_freshness=False,
        )
        previous = existing.latest
    except HistoryWitnessError as exc:
        if str(exc) not in {"witness_journal_missing", "witness_journal_empty"}:
            raise
        previous = None
    if previous is not None:
        if ledger_count < previous.ledger_count:
            raise HistoryWitnessError("witness_history_shrank")
        if ledger_count == previous.ledger_count:
            if (ledger_tip_hash or None) != (previous.ledger_tip_hash or None):
                raise HistoryWitnessError("witness_history_prefix_diverged")
        if (ledger_tip_seq or None) != (previous.ledger_tip_seq or None):
            raise HistoryWitnessError("witness_history_prefix_diverged")
        if (ledger_prefix_digest or None) != (
            previous.ledger_prefix_digest or None
        ):
            raise HistoryWitnessError("witness_history_prefix_diverged")
    moment = (observed_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    now = datetime.now(timezone.utc)
    if moment > now + timedelta(seconds=FUTURE_TOLERANCE_SECONDS):
        raise HistoryWitnessError("witness_observation_future")
    if previous is not None and moment < previous.observed_at:
        raise HistoryWitnessError("witness_observation_out_of_order")
    payload: dict[str, Any] = {
        "version": WITNESS_VERSION,
        "key_id": key_id,
        "observed_at": moment.isoformat().replace("+00:00", "Z"),
        "ledger_count": int(ledger_count),
        "ledger_tip_seq": int(ledger_tip_seq) if ledger_tip_seq is not None else None,
        "ledger_tip_hash": ledger_tip_hash,
        "ledger_prefix_digest": ledger_prefix_digest,
        "previous_checkpoint_hash": (
            previous.checkpoint_hash if previous is not None else None
        ),
    }
    payload["checkpoint_hash"] = _checkpoint_hash(payload)
    signature = private_key.sign(_signature_material(payload))
    line = json.dumps(
        {
            "payload": payload,
            "signature": f"{SIGNATURE_PREFIX}{_b64url_encode(signature)}",
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    journal.parent.mkdir(parents=True, exist_ok=True)
    existing_bytes = journal.read_bytes() if journal.exists() else b""
    prefix = b"" if not existing_bytes or existing_bytes.endswith(b"\n") else b"\n"
    fd, temporary = tempfile.mkstemp(
        prefix=".history-witness-", dir=str(journal.parent)
    )
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(existing_bytes)
            handle.write(prefix)
            handle.write(line.encode("utf-8"))
            handle.write(b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, journal)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
    return HistoryCheckpoint(
        observed_at=moment,
        ledger_count=int(ledger_count),
        ledger_tip_seq=int(ledger_tip_seq) if ledger_tip_seq is not None else None,
        ledger_tip_hash=ledger_tip_hash,
        ledger_prefix_digest=ledger_prefix_digest,
        previous_checkpoint_hash=payload["previous_checkpoint_hash"],
        checkpoint_hash=payload["checkpoint_hash"],
        key_id=key_id,
    )


def _iter_entries(journal_path: Path) -> Iterable[dict[str, Any]]:
    try:
        text = journal_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise HistoryWitnessError("witness_journal_missing") from exc
    except OSError as exc:
        raise HistoryWitnessError("witness_journal_unreadable") from exc
    for line_number, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            entry = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise HistoryWitnessError(
                f"witness_journal_malformed:{line_number}"
            ) from exc
        if not isinstance(entry, dict) or not isinstance(entry.get("payload"), dict):
            raise HistoryWitnessError(f"witness_journal_shape:{line_number}")
        yield entry


def verify_journal(
    journal_path: str | os.PathLike[str],
    *,
    public_key_path: str | os.PathLike[str] | None = None,
    public_key: Ed25519PublicKey | None = None,
    genesis_hash: str | None = None,
    require_freshness: bool = False,
    freshness_seconds: int = 1200,
    expected_count: int | None = None,
    expected_tip_hash: str | None = None,
    expected_tip_seq: int | None = None,
    expected_prefix_digest: str | None = None,
    now: datetime | None = None,
) -> VerifiedJournal:
    """Verify the full signed journal, its chain, and optional live state."""
    path = Path(journal_path)
    key = public_key or (
        load_public_key(public_key_path) if public_key_path is not None else None
    )
    if key is None:
        raise HistoryWitnessError("witness_public_key_required")
    checkpoints: list[HistoryCheckpoint] = []
    previous_hash: str | None = None
    previous_observed: datetime | None = None
    for entry in _iter_entries(path):
        payload = entry["payload"]
        signature_text = entry.get("signature")
        if not isinstance(signature_text, str) or not signature_text.startswith(
            SIGNATURE_PREFIX
        ):
            raise HistoryWitnessError("witness_signature_missing")
        try:
            signature = _b64url_decode(signature_text.removeprefix(SIGNATURE_PREFIX))
        except Exception as exc:
            raise HistoryWitnessError("witness_signature_malformed") from exc
        try:
            key.verify(signature, _signature_material(payload))
        except InvalidSignature as exc:
            raise HistoryWitnessError("witness_signature_invalid") from exc
        if payload.get("version") != WITNESS_VERSION:
            raise HistoryWitnessError("witness_version_unsupported")
        observed_at = _parse_instant(payload.get("observed_at"))
        if previous_observed is not None and observed_at < previous_observed:
            raise HistoryWitnessError("witness_observation_out_of_order")
        previous_observed = observed_at
        count = payload.get("ledger_count")
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise HistoryWitnessError("witness_ledger_count_invalid")
        tip_seq = payload.get("ledger_tip_seq")
        if tip_seq is not None and (
            not isinstance(tip_seq, int) or isinstance(tip_seq, bool)
        ):
            raise HistoryWitnessError("witness_ledger_tip_seq_invalid")
        tip_hash = payload.get("ledger_tip_hash")
        if tip_hash is not None and not isinstance(tip_hash, str):
            raise HistoryWitnessError("witness_ledger_tip_hash_invalid")
        prefix_digest = payload.get("ledger_prefix_digest")
        if prefix_digest is not None and (
            not isinstance(prefix_digest, str)
            or not _is_sha256_hex(prefix_digest)
        ):
            raise HistoryWitnessError("witness_ledger_prefix_digest_invalid")
        if count == 0 and (tip_seq is not None or tip_hash is not None):
            raise HistoryWitnessError("witness_empty_ledger_with_tip")
        if count > 0 and (tip_seq is None or not tip_hash):
            raise HistoryWitnessError("witness_nonempty_ledger_without_tip")
        computed_hash = _checkpoint_hash(payload)
        if payload.get("checkpoint_hash") != computed_hash:
            raise HistoryWitnessError("witness_checkpoint_hash_invalid")
        if payload.get("previous_checkpoint_hash") != previous_hash:
            raise HistoryWitnessError("witness_chain_broken")
        if checkpoints:
            last = checkpoints[-1]
            if count < last.ledger_count:
                raise HistoryWitnessError("witness_history_shrank")
            if count == last.ledger_count and (
                (tip_hash or None) != (last.ledger_tip_hash or None)
                or (tip_seq or None) != (last.ledger_tip_seq or None)
                or (prefix_digest or None)
                != (last.ledger_prefix_digest or None)
            ):
                raise HistoryWitnessError("witness_history_prefix_diverged")
        key_id_value = payload.get("key_id") or ""
        checkpoint = HistoryCheckpoint(
            observed_at=observed_at,
            ledger_count=count,
            ledger_tip_seq=tip_seq,
            ledger_tip_hash=tip_hash,
            ledger_prefix_digest=prefix_digest,
            previous_checkpoint_hash=payload.get("previous_checkpoint_hash"),
            checkpoint_hash=computed_hash,
            key_id=key_id_value,
        )
        checkpoints.append(checkpoint)
        previous_hash = computed_hash
    if not checkpoints:
        raise HistoryWitnessError("witness_journal_empty")
    if genesis_hash is not None and checkpoints[0].checkpoint_hash != genesis_hash:
        raise HistoryWitnessError("witness_genesis_mismatch")
    latest = checkpoints[-1]
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if latest.observed_at > current + timedelta(seconds=FUTURE_TOLERANCE_SECONDS):
        raise HistoryWitnessError("witness_observation_future")
    if require_freshness and (
        current - latest.observed_at
    ).total_seconds() > freshness_seconds:
        raise HistoryWitnessError("witness_checkpoint_stale")
    if expected_count is not None and latest.ledger_count != int(expected_count):
        raise HistoryWitnessError("witness_live_count_diverged")
    if expected_tip_hash is not None and (latest.ledger_tip_hash or None) != (
        expected_tip_hash or None
    ):
        raise HistoryWitnessError("witness_live_tip_diverged")
    if expected_tip_seq is not None and (latest.ledger_tip_seq or None) != (
        expected_tip_seq or None
    ):
        raise HistoryWitnessError("witness_live_tip_seq_diverged")
    if expected_prefix_digest is not None and (
        latest.ledger_prefix_digest or None
    ) != (expected_prefix_digest or None):
        raise HistoryWitnessError("witness_live_prefix_diverged")
    return VerifiedJournal(checkpoints=tuple(checkpoints))


__all__ = (
    "DEFAULT_KEY_ID",
    "HistoryCheckpoint",
    "HistoryWitnessError",
    "VerifiedJournal",
    "append_checkpoint",
    "generate_keypair",
    "load_private_key",
    "load_public_key",
    "verify_journal",
)
