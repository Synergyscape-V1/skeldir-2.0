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
import contextlib
import hashlib
import json
import os
import tempfile
import uuid

try:
    import fcntl
except ImportError:  # Windows host tests; the deployed observer is Linux.
    fcntl = None  # type: ignore[assignment]
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

WITNESS_VERSION = 1
HEARTBEAT_VERSION = 1
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


def _heartbeat_hash(payload: Mapping[str, Any]) -> str:
    import hashlib

    material = {key: value for key, value in payload.items() if key != "heartbeat_hash"}
    return hashlib.sha256(_canonical(material)).hexdigest()


def _is_sha256_hex(value: str) -> bool:
    if len(value) != 64:
        return False
    return all(char in "0123456789abcdef" for char in value.lower())


def public_key_fingerprint(public_key: Ed25519PublicKey) -> str:
    """SHA-256 of the raw Ed25519 public key bytes."""
    raw = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return hashlib.sha256(raw).hexdigest()


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
    authority_universe: str | None = None
    source_evidence_digest: str | None = None
    source_evidence_by_tenant: Mapping[str, str] | None = None
    source_evidence_count: int | None = None
    source_evidence_manifest_by_tenant: (
        Mapping[str, Mapping[str, tuple[str, ...]]] | None
    ) = None
    source_evidence_failures_by_tenant: Mapping[str, str] | None = None


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


def _normalize_universe(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        return str(uuid.UUID(str(value)))
    except (TypeError, ValueError) as exc:
        raise HistoryWitnessError("witness_authority_universe_invalid") from exc


def _write_custody(
    custody_path: str | os.PathLike[str] | None,
    *,
    ledger_count: int,
    checkpoint_hash: str,
    authority_universe: str | None,
    source_evidence_digest: str | None = None,
    source_evidence_count: int | None = None,
    source_evidence_failures_by_tenant: Mapping[str, str] | None = None,
) -> None:
    """Persist the latest commitment as a monotonic rollback lower bound.

    The journal itself is append-only by convention; a principal that can
    write the journal can replay an older, still-valid prefix. This custody
    record is written after the journal fsync and never accepts a lower
    count (or a different hash at the same count), so replaying an older
    journal is detected by any verifier that has the custody file.
    """
    if custody_path is None:
        return
    path = Path(custody_path)
    current = load_custody(path)
    if current is not None:
        current_count = int(current.get("ledger_count", -1))
        if ledger_count < current_count:
            raise HistoryWitnessError("witness_custody_rollback")
        if ledger_count == current_count and (
            current.get("checkpoint_hash") != checkpoint_hash
        ):
            current_source_count = current.get("source_evidence_count")
            if current_source_count is None:
                # Bootstrap of the source-completeness manifest after the
                # ledger witness already exists.
                if source_evidence_count is None:
                    raise HistoryWitnessError("witness_custody_fork")
            elif (
                source_evidence_count is None
                or int(source_evidence_count) <= int(current_source_count)
            ) and not source_evidence_failures_by_tenant:
                raise HistoryWitnessError("witness_custody_fork")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ledger_count": int(ledger_count),
        "checkpoint_hash": checkpoint_hash,
        "authority_universe": authority_universe,
        "source_evidence_digest": source_evidence_digest,
        "source_evidence_count": source_evidence_count,
    }
    fd, temporary = tempfile.mkstemp(
        prefix=".history-witness-custody-", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def load_custody(
    custody_path: str | os.PathLike[str] | None,
) -> dict[str, Any] | None:
    if custody_path is None:
        return None
    path = Path(custody_path)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise HistoryWitnessError("witness_custody_unreadable") from exc
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise HistoryWitnessError("witness_custody_malformed") from exc
    if not isinstance(payload, dict):
        raise HistoryWitnessError("witness_custody_malformed")
    count = payload.get("ledger_count")
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise HistoryWitnessError("witness_custody_malformed")
    if not isinstance(payload.get("checkpoint_hash"), str):
        raise HistoryWitnessError("witness_custody_malformed")
    return payload


def _write_heartbeat(
    heartbeat_path: str | os.PathLike[str] | None,
    *,
    private_key: Ed25519PrivateKey,
    observed_at: datetime,
    latest: HistoryCheckpoint,
) -> None:
    """Publish a signed freshness observation without appending history.

    XXIV (A8): an unchanged ledger must be refreshable. A heartbeat
    commits to the exact latest checkpoint and carries a fresh signed
    instant; it is never a new historical checkpoint and never changes
    the journal chain.
    """
    if heartbeat_path is None:
        return
    payload: dict[str, Any] = {
        "version": HEARTBEAT_VERSION,
        "key_id": latest.key_id,
        "observed_at": observed_at.isoformat().replace("+00:00", "Z"),
        "ledger_count": latest.ledger_count,
        "ledger_tip_seq": latest.ledger_tip_seq,
        "ledger_tip_hash": latest.ledger_tip_hash,
        "ledger_prefix_digest": latest.ledger_prefix_digest,
        "checkpoint_hash": latest.checkpoint_hash,
        "source_evidence_digest": latest.source_evidence_digest,
        "source_evidence_by_tenant": latest.source_evidence_by_tenant,
        "source_evidence_count": latest.source_evidence_count,
        "source_evidence_manifest_by_tenant": (
            latest.source_evidence_manifest_by_tenant
        ),
        "source_evidence_failures_by_tenant": (
            latest.source_evidence_failures_by_tenant
        ),
    }
    if latest.authority_universe is not None:
        payload["authority_universe"] = latest.authority_universe
    payload["heartbeat_hash"] = _heartbeat_hash(payload)
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
    path = Path(heartbeat_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(
        prefix=".history-witness-heartbeat-", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(line.encode("utf-8"))
            handle.write(b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _restore_journal(journal: Path, previous_bytes: bytes) -> None:
    if not previous_bytes:
        try:
            journal.unlink()
        except FileNotFoundError:
            pass
        return
    fd, temporary = tempfile.mkstemp(
        prefix=".history-witness-restore-", dir=str(journal.parent)
    )
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(previous_bytes)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, journal)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


@contextlib.contextmanager
def witness_lock(journal_path: str | os.PathLike[str]):
    """Serialize journal readers/writers across observer processes.

    The observer worker and the beat-scheduled task can overlap, and the
    re-drive path can start a second observer process. The journal is a
    single append-only chain; two processes that both read the same prior
    tip and append would fork it. The lock file lives on the same witness
    volume and is held across the read-verify-append sequence. On a Windows
    host (unit tests only) fcntl is unavailable and the lock is a no-op; the
    deployed observer is Linux.
    """
    journal = Path(journal_path)
    lock_path = journal.with_name(journal.name + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "a+", encoding="utf-8") as handle:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def append_checkpoint(
    journal_path: str | os.PathLike[str],
    **kwargs: Any,
) -> HistoryCheckpoint:
    """Publish one observation while holding the cross-process lock."""
    with witness_lock(journal_path):
        return _append_checkpoint_unlocked(journal_path, **kwargs)


def _append_checkpoint_unlocked(
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
    authority_universe: str | None = None,
    prefix_anchor_seq: int | None = None,
    prefix_anchor_hash: str | None = None,
    custody_path: str | os.PathLike[str] | None = None,
    heartbeat_path: str | os.PathLike[str] | None = None,
    source_evidence_digest: str | None = None,
    source_evidence_by_tenant: Mapping[str, str] | None = None,
    source_evidence_count: int | None = None,
    source_evidence_manifest_by_tenant: (
        Mapping[str, Mapping[str, Iterable[str]]] | None
    ) = None,
    source_evidence_failures_by_tenant: Mapping[str, str] | None = None,
) -> HistoryCheckpoint:
    """Verify the existing journal, then atomically publish one observation.

    A lawful ledger grows: the new checkpoint must anchor the exact previous
    tip (prefix_anchor_seq/hash) and strictly advance the tip sequence. The
    checkpoint's live prefix digest must change. Re-observing the same count
    requires byte-identical history and publishes a signed heartbeat instead
    of appending a duplicate checkpoint.

    XXIV (A3/A8): custody is preflighted before any journal byte changes.
    If the custody write fails after a journal append, the prior journal
    bytes are restored, so refusal and durable state cannot diverge.
    """
    journal = Path(journal_path)
    private_key = load_private_key(private_key_path)
    normalized_universe = _normalize_universe(authority_universe)
    if source_evidence_digest is not None and not _is_sha256_hex(
        source_evidence_digest
    ):
        raise HistoryWitnessError("witness_source_evidence_digest_invalid")
    normalized_source_by_tenant: dict[str, str] | None = None
    if source_evidence_by_tenant is not None:
        if not isinstance(source_evidence_by_tenant, Mapping):
            raise HistoryWitnessError("witness_source_evidence_map_invalid")
        normalized_source_by_tenant = {}
        for tenant, digest in source_evidence_by_tenant.items():
            if not isinstance(digest, str) or not _is_sha256_hex(digest):
                raise HistoryWitnessError(
                    "witness_source_evidence_digest_invalid"
                )
            try:
                tenant_key = str(uuid.UUID(str(tenant)))
            except (TypeError, ValueError) as exc:
                raise HistoryWitnessError(
                    "witness_source_evidence_tenant_invalid"
                ) from exc
            normalized_source_by_tenant[tenant_key] = digest.lower()
        material = {
            "version": "b26-p2-source-evidence-v1",
            "tenants": normalized_source_by_tenant,
        }
        computed_global = hashlib.sha256(
            json.dumps(
                material, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()
        if source_evidence_digest is None:
            source_evidence_digest = computed_global
        elif source_evidence_digest != computed_global:
            raise HistoryWitnessError(
                "witness_source_evidence_global_mismatch"
            )
    if source_evidence_count is not None:
        if (
            not isinstance(source_evidence_count, int)
            or isinstance(source_evidence_count, bool)
            or source_evidence_count < 0
        ):
            raise HistoryWitnessError("witness_source_evidence_count_invalid")
    normalized_failures: dict[str, str] | None = None
    if source_evidence_failures_by_tenant is not None:
        if not isinstance(source_evidence_failures_by_tenant, Mapping):
            raise HistoryWitnessError(
                "witness_source_evidence_failures_invalid"
            )
        normalized_failures = {}
        for tenant, reason_digest in source_evidence_failures_by_tenant.items():
            if not isinstance(reason_digest, str) or not _is_sha256_hex(
                reason_digest
            ):
                raise HistoryWitnessError(
                    "witness_source_evidence_failure_digest_invalid"
                )
            try:
                tenant_key = str(uuid.UUID(str(tenant)))
            except (TypeError, ValueError) as exc:
                raise HistoryWitnessError(
                    "witness_source_evidence_tenant_invalid"
                ) from exc
            normalized_failures[tenant_key] = reason_digest.lower()
    normalized_manifest: dict[str, dict[str, tuple[str, ...]]] | None = None
    if source_evidence_manifest_by_tenant is not None:
        if not isinstance(source_evidence_manifest_by_tenant, Mapping):
            raise HistoryWitnessError("witness_source_evidence_manifest_invalid")
        normalized_manifest = {}
        for tenant, manifest in source_evidence_manifest_by_tenant.items():
            if not isinstance(manifest, Mapping):
                raise HistoryWitnessError(
                    "witness_source_evidence_manifest_invalid"
                )
            try:
                tenant_key = str(uuid.UUID(str(tenant)))
            except (TypeError, ValueError) as exc:
                raise HistoryWitnessError(
                    "witness_source_evidence_tenant_invalid"
                ) from exc
            facts = manifest.get("facts")
            states = manifest.get("states")
            if not isinstance(facts, (list, tuple)) or not isinstance(
                states, (list, tuple)
            ):
                raise HistoryWitnessError(
                    "witness_source_evidence_manifest_invalid"
                )
            for value in (*facts, *states):
                if not isinstance(value, str) or not _is_sha256_hex(value):
                    raise HistoryWitnessError(
                        "witness_source_evidence_fact_invalid"
                    )
            normalized_manifest[tenant_key] = {
                "facts": tuple(sorted(str(value) for value in facts)),
                "states": tuple(sorted(str(value) for value in states)),
            }
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
    custody = load_custody(custody_path)
    if previous is not None and custody_path is not None and custody is None:
        raise HistoryWitnessError("witness_custody_missing")
    if custody is not None and previous is not None:
        custody_count = int(custody["ledger_count"])
        if custody_count > previous.ledger_count:
            raise HistoryWitnessError("witness_custody_rollback")
        if (
            custody_count == previous.ledger_count
            and custody.get("checkpoint_hash") != previous.checkpoint_hash
        ):
            raise HistoryWitnessError("witness_custody_fork")
    failure_map_changed = previous is None or normalized_failures != (
        dict(previous.source_evidence_failures_by_tenant)
        if previous.source_evidence_failures_by_tenant is not None
        else None
    )
    if previous is not None:
        if ledger_count < previous.ledger_count:
            raise HistoryWitnessError("witness_history_shrank")
        if previous.authority_universe is not None and (
            normalized_universe != previous.authority_universe
        ):
            raise HistoryWitnessError("witness_authority_universe_changed")
        if ledger_count == previous.ledger_count:
            if (ledger_tip_hash or None) != (previous.ledger_tip_hash or None):
                raise HistoryWitnessError("witness_history_prefix_diverged")
            if (ledger_tip_seq or None) != (previous.ledger_tip_seq or None):
                raise HistoryWitnessError("witness_history_prefix_diverged")
            if (ledger_prefix_digest or None) != (
                previous.ledger_prefix_digest or None
            ):
                raise HistoryWitnessError("witness_history_prefix_diverged")
            if (source_evidence_digest or None) != (
                previous.source_evidence_digest or None
            ):
                # A same-ledger change is a new fact only when the
                # canonical fact count grew. Deletion and rollback shrink
                # or preserve the count and are refused.
                if (
                    previous.source_evidence_count is None
                    or source_evidence_count is None
                    or int(source_evidence_count)
                    <= int(previous.source_evidence_count)
                ) and not failure_map_changed:
                    raise HistoryWitnessError(
                        "witness_source_evidence_diverged_without_ledger"
                    )
            if (
                normalized_source_by_tenant is not None
                and previous.source_evidence_by_tenant is not None
                and normalized_source_by_tenant
                != dict(previous.source_evidence_by_tenant)
                and (source_evidence_digest or None)
                == (previous.source_evidence_digest or None)
            ):
                raise HistoryWitnessError(
                    "witness_source_evidence_map_inconsistent"
                )
        else:
            if (
                previous.source_evidence_count is not None
                and source_evidence_count is not None
                and int(source_evidence_count)
                < int(previous.source_evidence_count)
                and not failure_map_changed
            ):
                raise HistoryWitnessError("witness_source_evidence_shrank")
            if (prefix_anchor_seq or None) != (previous.ledger_tip_seq or None):
                raise HistoryWitnessError("witness_history_prefix_diverged")
            if (prefix_anchor_hash or None) != (previous.ledger_tip_hash or None):
                raise HistoryWitnessError("witness_history_prefix_diverged")
            if (ledger_tip_seq or None) == (previous.ledger_tip_seq or None):
                raise HistoryWitnessError("witness_history_tip_not_advanced")
            if (ledger_prefix_digest or None) == (
                previous.ledger_prefix_digest or None
            ):
                raise HistoryWitnessError("witness_history_prefix_not_advanced")
    if previous is not None and previous.source_evidence_manifest_by_tenant is not None:
        if normalized_manifest is None:
            raise HistoryWitnessError(
                "witness_source_evidence_manifest_missing"
            )
        for tenant, previous_manifest in (
            previous.source_evidence_manifest_by_tenant.items()
        ):
            current_manifest = normalized_manifest.get(str(tenant))
            if current_manifest is None:
                if normalized_failures and str(tenant) in normalized_failures:
                    continue
                raise HistoryWitnessError(
                    "witness_source_evidence_tenant_missing"
                )
            previous_facts = set(previous_manifest.get("facts", ()))
            current_facts = set(current_manifest["facts"])
            if not previous_facts.issubset(current_facts):
                raise HistoryWitnessError(
                    "witness_source_evidence_fact_missing"
                )
            if (
                set(previous_manifest.get("states", ()))
                != set(current_manifest["states"])
                and not (current_facts - previous_facts)
            ):
                raise HistoryWitnessError(
                    "witness_source_evidence_state_changed_without_fact"
                )
    moment = (observed_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    now = datetime.now(timezone.utc)
    if moment > now + timedelta(seconds=FUTURE_TOLERANCE_SECONDS):
        raise HistoryWitnessError("witness_observation_future")
    if previous is not None and moment < previous.observed_at:
        raise HistoryWitnessError("witness_observation_out_of_order")
    source_changed = (
        previous is not None
        and (
            (normalized_source_by_tenant or None)
            != (
                dict(previous.source_evidence_by_tenant)
                if previous.source_evidence_by_tenant is not None
                else None
            )
            or (source_evidence_digest or None)
            != (previous.source_evidence_digest or None)
        )
    )
    if (
        previous is not None
        and ledger_count == previous.ledger_count
        and not source_changed
    ):
        # An unchanged ledger and unchanged source set are a freshness
        # observation, not history.
        if custody is not None and int(custody["ledger_count"]) < ledger_count:
            _write_custody(
                custody_path,
                ledger_count=previous.ledger_count,
                checkpoint_hash=previous.checkpoint_hash,
                authority_universe=previous.authority_universe,
                source_evidence_digest=previous.source_evidence_digest,
                source_evidence_count=previous.source_evidence_count,
            )
        _write_heartbeat(
            heartbeat_path,
            private_key=private_key,
            observed_at=moment,
            latest=previous,
        )
        return HistoryCheckpoint(
            observed_at=moment,
            ledger_count=previous.ledger_count,
            ledger_tip_seq=previous.ledger_tip_seq,
            ledger_tip_hash=previous.ledger_tip_hash,
            ledger_prefix_digest=previous.ledger_prefix_digest,
            previous_checkpoint_hash=previous.previous_checkpoint_hash,
            checkpoint_hash=previous.checkpoint_hash,
            key_id=previous.key_id,
            authority_universe=previous.authority_universe,
            source_evidence_digest=previous.source_evidence_digest,
            source_evidence_by_tenant=previous.source_evidence_by_tenant,
            source_evidence_count=previous.source_evidence_count,
            source_evidence_manifest_by_tenant=(
                previous.source_evidence_manifest_by_tenant
            ),
            source_evidence_failures_by_tenant=(
                previous.source_evidence_failures_by_tenant
            ),
        )
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
    if normalized_universe is not None:
        payload["authority_universe"] = normalized_universe
    if source_evidence_digest is not None:
        payload["source_evidence_digest"] = source_evidence_digest
    if normalized_source_by_tenant is not None:
        payload["source_evidence_by_tenant"] = normalized_source_by_tenant
    if source_evidence_count is not None:
        payload["source_evidence_count"] = source_evidence_count
    if normalized_manifest is not None:
        payload["source_evidence_manifest_by_tenant"] = (
            normalized_manifest
        )
    if normalized_failures is not None:
        payload["source_evidence_failures_by_tenant"] = normalized_failures
    payload["checkpoint_hash"] = _checkpoint_hash(payload)
    if custody is not None and int(custody["ledger_count"]) == int(ledger_count):
        if custody.get("checkpoint_hash") != payload["checkpoint_hash"]:
            current_source_count = custody.get("source_evidence_count")
            if current_source_count is None:
                if source_evidence_count is None:
                    raise HistoryWitnessError("witness_custody_fork")
            elif (
                source_evidence_count is None
                or int(source_evidence_count) <= int(current_source_count)
            ):
                raise HistoryWitnessError("witness_custody_fork")
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
    return_checkpoint = HistoryCheckpoint(
        observed_at=moment,
        ledger_count=int(ledger_count),
        ledger_tip_seq=int(ledger_tip_seq) if ledger_tip_seq is not None else None,
        ledger_tip_hash=ledger_tip_hash,
        ledger_prefix_digest=ledger_prefix_digest,
        previous_checkpoint_hash=payload["previous_checkpoint_hash"],
        checkpoint_hash=payload["checkpoint_hash"],
        key_id=key_id,
        authority_universe=normalized_universe,
        source_evidence_digest=source_evidence_digest,
        source_evidence_by_tenant=normalized_source_by_tenant,
        source_evidence_count=source_evidence_count,
        source_evidence_manifest_by_tenant=normalized_manifest,
        source_evidence_failures_by_tenant=normalized_failures,
    )
    try:
        _write_custody(
            custody_path,
            ledger_count=return_checkpoint.ledger_count,
            checkpoint_hash=return_checkpoint.checkpoint_hash,
            authority_universe=normalized_universe,
            source_evidence_digest=source_evidence_digest,
            source_evidence_count=source_evidence_count,
            source_evidence_failures_by_tenant=normalized_failures,
        )
    except Exception:
        try:
            _restore_journal(journal, existing_bytes)
        except Exception as restore_exc:
            raise HistoryWitnessError(
                "witness_journal_restore_failed"
            ) from restore_exc
        raise
    # XXV (A3/HB-08): publish the freshness observation for a GROWTH append
    # too, not only for an unchanged ledger. Previously the heartbeat was
    # written on the unchanged-ledger path alone, so every lawful history
    # advance left the signed consumer refusing with
    # ``history_integrity_unverifiable`` until the next observer cycle wrote a
    # heartbeat -- an availability hole in the positive obligation, and a
    # window in which a consumer cannot tell a legitimate correction from a
    # broken one. The checkpoint this heartbeat names is the one that was just
    # appended, so it asserts nothing that is not already signed.
    _write_heartbeat(
        heartbeat_path,
        private_key=private_key,
        observed_at=moment,
        latest=return_checkpoint,
    )
    return return_checkpoint


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


def _load_heartbeat(
    heartbeat_path: str | os.PathLike[str] | None,
    key: Ed25519PublicKey,
) -> dict[str, Any] | None:
    if heartbeat_path is None:
        return None
    path = Path(heartbeat_path)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise HistoryWitnessError("witness_heartbeat_unreadable") from exc
    try:
        entry = json.loads(text)
    except json.JSONDecodeError as exc:
        raise HistoryWitnessError("witness_heartbeat_malformed") from exc
    if not isinstance(entry, dict) or not isinstance(entry.get("payload"), dict):
        raise HistoryWitnessError("witness_heartbeat_malformed")
    payload = entry["payload"]
    signature_text = entry.get("signature")
    if not isinstance(signature_text, str) or not signature_text.startswith(
        SIGNATURE_PREFIX
    ):
        raise HistoryWitnessError("witness_heartbeat_signature_missing")
    try:
        signature = _b64url_decode(signature_text.removeprefix(SIGNATURE_PREFIX))
    except Exception as exc:
        raise HistoryWitnessError("witness_heartbeat_signature_malformed") from exc
    try:
        key.verify(signature, _signature_material(payload))
    except InvalidSignature as exc:
        raise HistoryWitnessError("witness_heartbeat_signature_invalid") from exc
    if payload.get("version") != HEARTBEAT_VERSION:
        raise HistoryWitnessError("witness_heartbeat_version_unsupported")
    if payload.get("heartbeat_hash") != _heartbeat_hash(payload):
        raise HistoryWitnessError("witness_heartbeat_hash_invalid")
    if not isinstance(payload.get("checkpoint_hash"), str):
        raise HistoryWitnessError("witness_heartbeat_malformed")
    return payload


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
    expected_universe: str | None = None,
    require_universe: bool = False,
    expected_source_evidence_digest: str | None = None,
    expected_source_evidence_by_tenant: Mapping[str, str] | None = None,
    require_source_evidence: bool = False,
    heartbeat_path: str | os.PathLike[str] | None = None,
    now: datetime | None = None,
) -> VerifiedJournal:
    """Verify the full signed journal, its chain, and optional live state.

    XXIV (A7/A8): a heartbeat may carry freshness for an unchanged ledger,
    but only when it is signed, bound to the exact latest checkpoint, and
    at least as new as that checkpoint. A malformed or diverging heartbeat
    fails closed rather than being ignored.
    """
    path = Path(journal_path)
    key = public_key or (
        load_public_key(public_key_path) if public_key_path is not None else None
    )
    if key is None:
        raise HistoryWitnessError("witness_public_key_required")
    checkpoints: list[HistoryCheckpoint] = []
    previous_hash: str | None = None
    previous_observed: datetime | None = None
    journal_universe: str | None = None
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
        universe = payload.get("authority_universe")
        if universe is not None:
            universe = _normalize_universe(universe)
            if journal_universe is None:
                journal_universe = universe
            elif journal_universe != universe:
                raise HistoryWitnessError("witness_authority_universe_changed")
        source_evidence_digest = payload.get("source_evidence_digest")
        if source_evidence_digest is not None and not _is_sha256_hex(
            source_evidence_digest
        ):
            raise HistoryWitnessError(
                "witness_source_evidence_digest_invalid"
            )
        raw_source_map = payload.get("source_evidence_by_tenant")
        source_evidence_by_tenant: dict[str, str] | None = None
        if raw_source_map is not None:
            if not isinstance(raw_source_map, dict):
                raise HistoryWitnessError(
                    "witness_source_evidence_map_invalid"
                )
            source_evidence_by_tenant = {}
            for tenant, digest in raw_source_map.items():
                if not isinstance(digest, str) or not _is_sha256_hex(digest):
                    raise HistoryWitnessError(
                        "witness_source_evidence_digest_invalid"
                    )
                try:
                    tenant_key = str(uuid.UUID(str(tenant)))
                except (TypeError, ValueError) as exc:
                    raise HistoryWitnessError(
                        "witness_source_evidence_tenant_invalid"
                    ) from exc
                source_evidence_by_tenant[tenant_key] = digest.lower()
            material = {
                "version": "b26-p2-source-evidence-v1",
                "tenants": source_evidence_by_tenant,
            }
            computed_global = hashlib.sha256(
                json.dumps(
                    material, sort_keys=True, separators=(",", ":")
                ).encode("utf-8")
            ).hexdigest()
            if source_evidence_digest is None:
                source_evidence_digest = computed_global
            elif source_evidence_digest != computed_global:
                raise HistoryWitnessError(
                    "witness_source_evidence_global_mismatch"
                )
        source_evidence_count = payload.get("source_evidence_count")
        if source_evidence_count is not None and (
            not isinstance(source_evidence_count, int)
            or isinstance(source_evidence_count, bool)
            or source_evidence_count < 0
        ):
            raise HistoryWitnessError(
                "witness_source_evidence_count_invalid"
            )
        raw_failures = payload.get("source_evidence_failures_by_tenant")
        source_evidence_failures_by_tenant: dict[str, str] | None = None
        if raw_failures is not None:
            if not isinstance(raw_failures, dict):
                raise HistoryWitnessError(
                    "witness_source_evidence_failures_invalid"
                )
            source_evidence_failures_by_tenant = {}
            for tenant, reason_digest in raw_failures.items():
                if not isinstance(reason_digest, str) or not _is_sha256_hex(
                    reason_digest
                ):
                    raise HistoryWitnessError(
                        "witness_source_evidence_failure_digest_invalid"
                    )
                try:
                    tenant_key = str(uuid.UUID(str(tenant)))
                except (TypeError, ValueError) as exc:
                    raise HistoryWitnessError(
                        "witness_source_evidence_tenant_invalid"
                    ) from exc
                source_evidence_failures_by_tenant[tenant_key] = (
                    reason_digest.lower()
                )
        raw_manifest = payload.get("source_evidence_manifest_by_tenant")
        source_evidence_manifest_by_tenant: (
            dict[str, dict[str, tuple[str, ...]]] | None
        ) = None
        if raw_manifest is not None:
            if not isinstance(raw_manifest, dict):
                raise HistoryWitnessError(
                    "witness_source_evidence_manifest_invalid"
                )
            source_evidence_manifest_by_tenant = {}
            for tenant, manifest in raw_manifest.items():
                if not isinstance(manifest, dict):
                    raise HistoryWitnessError(
                        "witness_source_evidence_manifest_invalid"
                    )
                try:
                    tenant_key = str(uuid.UUID(str(tenant)))
                except (TypeError, ValueError) as exc:
                    raise HistoryWitnessError(
                        "witness_source_evidence_tenant_invalid"
                    ) from exc
                facts = manifest.get("facts")
                states = manifest.get("states")
                if not isinstance(facts, list) or not isinstance(states, list):
                    raise HistoryWitnessError(
                        "witness_source_evidence_manifest_invalid"
                    )
                for value in (*facts, *states):
                    if not isinstance(value, str) or not _is_sha256_hex(value):
                        raise HistoryWitnessError(
                            "witness_source_evidence_fact_invalid"
                        )
                source_evidence_manifest_by_tenant[tenant_key] = {
                    "facts": tuple(sorted(facts)),
                    "states": tuple(sorted(states)),
                }
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
            failure_map_changed = (
                source_evidence_failures_by_tenant
                != (
                    dict(last.source_evidence_failures_by_tenant)
                    if last.source_evidence_failures_by_tenant is not None
                    else None
                )
            )
            if count < last.ledger_count:
                raise HistoryWitnessError("witness_history_shrank")
            if count == last.ledger_count and (
                (tip_hash or None) != (last.ledger_tip_hash or None)
                or (tip_seq or None) != (last.ledger_tip_seq or None)
                or (prefix_digest or None)
                != (last.ledger_prefix_digest or None)
            ):
                raise HistoryWitnessError("witness_history_prefix_diverged")
            if count == last.ledger_count and (
                source_evidence_digest or None
            ) != (last.source_evidence_digest or None):
                if (
                    last.source_evidence_count is None
                    or source_evidence_count is None
                    or int(source_evidence_count)
                    <= int(last.source_evidence_count)
                ) and not failure_map_changed:
                    raise HistoryWitnessError(
                        "witness_source_evidence_diverged_without_ledger"
                    )
            if (
                source_evidence_count is not None
                and last.source_evidence_count is not None
                and int(source_evidence_count)
                < int(last.source_evidence_count)
                and not failure_map_changed
            ):
                raise HistoryWitnessError("witness_source_evidence_shrank")
            if (
                last.source_evidence_manifest_by_tenant is not None
            ):
                if source_evidence_manifest_by_tenant is None:
                    raise HistoryWitnessError(
                        "witness_source_evidence_manifest_missing"
                    )
                for tenant, previous_manifest in (
                    last.source_evidence_manifest_by_tenant.items()
                ):
                    current_manifest = (
                        source_evidence_manifest_by_tenant.get(str(tenant))
                    )
                    if current_manifest is None:
                        if (
                            source_evidence_failures_by_tenant
                            and str(tenant)
                            in source_evidence_failures_by_tenant
                        ):
                            continue
                        raise HistoryWitnessError(
                            "witness_source_evidence_tenant_missing"
                        )
                    previous_facts = set(previous_manifest.get("facts", ()))
                    current_facts = set(current_manifest["facts"])
                    if not previous_facts.issubset(current_facts):
                        raise HistoryWitnessError(
                            "witness_source_evidence_fact_missing"
                        )
                    if (
                        set(previous_manifest.get("states", ()))
                        != set(current_manifest["states"])
                        and not (current_facts - previous_facts)
                    ):
                        raise HistoryWitnessError(
                            "witness_source_evidence_state_changed_without_fact"
                        )
            if count > last.ledger_count:
                if (tip_seq or 0) <= (last.ledger_tip_seq or 0):
                    raise HistoryWitnessError("witness_history_tip_not_advanced")
                if (prefix_digest or None) == (last.ledger_prefix_digest or None):
                    raise HistoryWitnessError(
                        "witness_history_prefix_not_advanced"
                    )
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
            authority_universe=universe,
            source_evidence_digest=source_evidence_digest,
            source_evidence_by_tenant=source_evidence_by_tenant,
            source_evidence_count=source_evidence_count,
            source_evidence_manifest_by_tenant=(
                source_evidence_manifest_by_tenant
            ),
            source_evidence_failures_by_tenant=(
                source_evidence_failures_by_tenant
            ),
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
    heartbeat = _load_heartbeat(heartbeat_path, key)
    observed_for_freshness = latest.observed_at
    if heartbeat is not None:
        if heartbeat.get("checkpoint_hash") != latest.checkpoint_hash:
            raise HistoryWitnessError("witness_heartbeat_diverged")
        if (
            heartbeat.get("ledger_count") != latest.ledger_count
            or (heartbeat.get("ledger_tip_seq") or None)
            != (latest.ledger_tip_seq or None)
            or (heartbeat.get("ledger_tip_hash") or None)
            != (latest.ledger_tip_hash or None)
            or (heartbeat.get("ledger_prefix_digest") or None)
            != (latest.ledger_prefix_digest or None)
            or (heartbeat.get("authority_universe") or None)
            != (latest.authority_universe or None)
            or (heartbeat.get("source_evidence_digest") or None)
            != (latest.source_evidence_digest or None)
            or (heartbeat.get("source_evidence_by_tenant") or None)
            != (latest.source_evidence_by_tenant or None)
            or (heartbeat.get("source_evidence_count") or None)
            != (latest.source_evidence_count or None)
            or _canonical(
                heartbeat.get("source_evidence_manifest_by_tenant") or {}
            )
            != _canonical(
                latest.source_evidence_manifest_by_tenant or {}
            )
            or _canonical(
                heartbeat.get("source_evidence_failures_by_tenant") or {}
            )
            != _canonical(
                latest.source_evidence_failures_by_tenant or {}
            )
        ):
            raise HistoryWitnessError("witness_heartbeat_diverged")
        heartbeat_observed = _parse_instant(heartbeat.get("observed_at"))
        if heartbeat_observed < latest.observed_at:
            raise HistoryWitnessError("witness_heartbeat_out_of_order")
        if heartbeat_observed > current + timedelta(
            seconds=FUTURE_TOLERANCE_SECONDS
        ):
            raise HistoryWitnessError("witness_observation_future")
        observed_for_freshness = heartbeat_observed
    if require_freshness and (
        current - observed_for_freshness
    ).total_seconds() > freshness_seconds:
        raise HistoryWitnessError("witness_checkpoint_stale")
    if require_source_evidence and latest.source_evidence_digest is None:
        raise HistoryWitnessError("witness_source_evidence_missing")
    if expected_source_evidence_digest is not None and (
        latest.source_evidence_digest or None
    ) != (expected_source_evidence_digest or None):
        raise HistoryWitnessError("witness_source_evidence_diverged")
    if expected_source_evidence_by_tenant is not None:
        if latest.source_evidence_by_tenant is None:
            raise HistoryWitnessError("witness_source_evidence_missing")
        for tenant, digest in expected_source_evidence_by_tenant.items():
            if (
                latest.source_evidence_by_tenant.get(str(tenant)) or None
            ) != (str(digest) or None):
                raise HistoryWitnessError(
                    "witness_tenant_source_evidence_diverged"
                )
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
    if require_universe and latest.authority_universe is None:
        raise HistoryWitnessError("witness_authority_universe_missing")
    if expected_universe is not None and (
        latest.authority_universe or None
    ) != (_normalize_universe(expected_universe) or None):
        raise HistoryWitnessError("witness_live_universe_diverged")
    return VerifiedJournal(checkpoints=tuple(checkpoints))


__all__ = (
    "DEFAULT_KEY_ID",
    "HistoryCheckpoint",
    "HistoryWitnessError",
    "VerifiedJournal",
    "append_checkpoint",
    "generate_keypair",
    "load_custody",
    "load_private_key",
    "load_public_key",
    "public_key_fingerprint",
    "verify_journal",
)
