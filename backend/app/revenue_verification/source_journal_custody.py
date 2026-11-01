"""Signed custody bundles for the XXV source-evidence journal.

The live journal is writable only by the authentication root. This module
makes an independently signed, immutable snapshot of the committed journal
prefix available outside that live volume, and restores it without ever
discarding committed history. It is intentionally filesystem-agnostic: the
custody directory must be a separately administered object/volume (for
example an S3 Object Lock prefix or an EFS access point) whose write
authority is not the financial database maintenance actor.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from app.revenue_verification.source_evidence_journal import (
    journal_record_hash,
    load_source_fact_records,
)

CUSTODY_BUNDLE_VERSION = "b26-p2-source-journal-custody-v1"


class SourceJournalCustodyError(RuntimeError):
    """A bundle, signature or restore transition is not authoritative."""


@dataclass(frozen=True)
class CustodyBundle:
    manifest: Mapping[str, Any]
    journal_bytes: bytes
    manifest_path: Path


def _canonical(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")


def _decode_ed25519_seed(raw_seed: str) -> bytes:
    try:
        seed = base64.urlsafe_b64decode((raw_seed.strip() + "===").encode("ascii"))
    except (ValueError, UnicodeError) as exc:
        raise SourceJournalCustodyError("custody_key_unreadable") from exc
    if len(seed) != 32:
        raise SourceJournalCustodyError("custody_key_wrong_length")
    return seed


def _decode_ed25519_public(raw_public: str) -> bytes:
    try:
        public = base64.urlsafe_b64decode(
            (raw_public.strip() + "===").encode("ascii")
        )
    except (ValueError, UnicodeError) as exc:
        raise SourceJournalCustodyError("custody_public_key_unreadable") from exc
    if len(public) != 32:
        raise SourceJournalCustodyError("custody_public_key_wrong_length")
    return public


def _committed_journal_bytes(journal: Path) -> bytes:
    raw = journal.read_bytes()
    if raw and not raw.endswith(b"\n"):
        index = raw.rfind(b"\n")
        raw = raw[: index + 1] if index >= 0 else b""
    return raw


def _bundle_identity(journal: Path) -> tuple[int, str | None, str]:
    records = load_source_fact_records(journal)
    if records is None:
        raise SourceJournalCustodyError("custody_journal_missing")
    raw = _committed_journal_bytes(journal)
    tip = journal_record_hash(records[-1]) if records else None
    return len(records), tip, hashlib.sha256(raw).hexdigest()


def _manifest_payload(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in manifest.items() if key != "signature"}


def _write_atomic(path: Path, payload: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    with temporary.open("wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(temporary, mode)
    os.replace(temporary, path)


def export_custody_bundle(
    *,
    journal: str | os.PathLike[str],
    custody_dir: str | os.PathLike[str],
    private_key_path: str | os.PathLike[str],
) -> CustodyBundle:
    """Write an immutable signed bundle for the committed journal prefix."""

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    journal_path = Path(journal)
    if not journal_path.exists():
        raise SourceJournalCustodyError("custody_journal_missing")
    records = load_source_fact_records(journal_path)
    if records is None:
        raise SourceJournalCustodyError("custody_journal_missing")
    raw = _committed_journal_bytes(journal_path)
    count = len(records)
    tip = journal_record_hash(records[-1]) if records else None
    digest = hashlib.sha256(raw).hexdigest()

    seed = _decode_ed25519_seed(
        Path(private_key_path).read_text(encoding="utf-8")
    )
    key = Ed25519PrivateKey.from_private_bytes(seed)
    public_raw = key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    manifest: dict[str, Any] = {
        "version": CUSTODY_BUNDLE_VERSION,
        "journal_sha256": digest,
        "journal_size": len(raw),
        "record_count": count,
        "journal_tip": tip,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "key_sha256": hashlib.sha256(public_raw).hexdigest(),
    }
    signature = key.sign(_canonical(manifest))
    manifest["signature"] = "ed25519:" + base64.urlsafe_b64encode(
        signature
    ).rstrip(b"=").decode("ascii")

    custody_root = Path(custody_dir)
    bundle_name = tip or "empty"
    bundle_path = custody_root / f"source-evidence-{bundle_name}.jsonl"
    manifest_path = custody_root / f"source-evidence-{bundle_name}.manifest.json"
    if bundle_path.exists() or manifest_path.exists():
        existing = verify_custody_bundle(
            manifest_path=manifest_path,
            public_key_path=Path(private_key_path),
            public_key_is_private_seed=True,
        )
        if (
            existing.manifest.get("journal_sha256") == digest
            and existing.journal_bytes == raw
        ):
            return existing
        raise SourceJournalCustodyError("custody_bundle_conflict")

    _write_atomic(bundle_path, raw, 0o444)
    _write_atomic(
        manifest_path,
        json.dumps(manifest, sort_keys=True, indent=2).encode("utf-8"),
        0o444,
    )
    return CustodyBundle(
        manifest=manifest, journal_bytes=raw, manifest_path=manifest_path
    )


def verify_custody_bundle(
    *,
    manifest_path: str | os.PathLike[str],
    public_key_path: str | os.PathLike[str],
    public_key_is_private_seed: bool = False,
) -> CustodyBundle:
    """Verify a bundle's signature, bytes, chain, count and tip."""

    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )

    manifest_file = Path(manifest_path)
    try:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SourceJournalCustodyError("custody_manifest_unreadable") from exc
    if manifest.get("version") != CUSTODY_BUNDLE_VERSION:
        raise SourceJournalCustodyError("custody_bundle_version_unsupported")
    signature_text = str(manifest.get("signature") or "")
    if not signature_text.startswith("ed25519:"):
        raise SourceJournalCustodyError("custody_signature_missing")

    key_text = Path(public_key_path).read_text(encoding="utf-8")
    if public_key_is_private_seed:
        key = Ed25519PrivateKey.from_private_bytes(
            _decode_ed25519_seed(key_text)
        )
        public_bytes = key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    else:
        public_bytes = _decode_ed25519_public(key_text)
    if manifest.get("key_sha256") != hashlib.sha256(public_bytes).hexdigest():
        raise SourceJournalCustodyError("custody_key_fingerprint_mismatch")
    try:
        signature = base64.urlsafe_b64decode(
            (signature_text.split(":", 1)[1] + "===").encode("ascii")
        )
        Ed25519PublicKey.from_public_bytes(public_bytes).verify(
            signature, _canonical(_manifest_payload(manifest))
        )
    except (InvalidSignature, ValueError, TypeError) as exc:
        raise SourceJournalCustodyError("custody_signature_invalid") from exc

    bundle_path = manifest_file.with_name(
        manifest_file.name.replace(".manifest.json", ".jsonl")
    )
    try:
        raw = bundle_path.read_bytes()
    except OSError as exc:
        raise SourceJournalCustodyError("custody_bundle_missing") from exc
    if hashlib.sha256(raw).hexdigest() != manifest.get("journal_sha256"):
        raise SourceJournalCustodyError("custody_bundle_digest_mismatch")
    if len(raw) != int(manifest.get("journal_size", -1)):
        raise SourceJournalCustodyError("custody_bundle_size_mismatch")

    import tempfile

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix="b26-custody-verify-", suffix=".jsonl", delete=False
        ) as temporary_handle:
            temporary_path = Path(temporary_handle.name)
            temporary_handle.write(raw)
            temporary_handle.flush()
            os.fsync(temporary_handle.fileno())
        records = load_source_fact_records(temporary_path)
    finally:
        if temporary_path is not None:
            with contextlib.suppress(FileNotFoundError):
                temporary_path.unlink()
    if records is None:
        raise SourceJournalCustodyError("custody_bundle_missing")
    if len(records) != int(manifest.get("record_count", -1)):
        raise SourceJournalCustodyError("custody_record_count_mismatch")
    tip = journal_record_hash(records[-1]) if records else None
    if tip != manifest.get("journal_tip"):
        raise SourceJournalCustodyError("custody_journal_tip_mismatch")
    return CustodyBundle(
        manifest=manifest, journal_bytes=raw, manifest_path=manifest_file
    )


def restore_custody_bundle(
    *,
    manifest_path: str | os.PathLike[str],
    journal: str | os.PathLike[str],
    public_key_path: str | os.PathLike[str],
    public_key_is_private_seed: bool = False,
) -> str:
    """Restore only when the live journal is absent or a prefix of the bundle.

    A newer live journal is never overwritten: committed history wins over a
    stale archive. Returns ``restored``, ``already_current`` or
    ``live_is_newer``.
    """

    bundle = verify_custody_bundle(
        manifest_path=manifest_path,
        public_key_path=public_key_path,
        public_key_is_private_seed=public_key_is_private_seed,
    )
    journal_path = Path(journal)
    if journal_path.exists():
        live_records = load_source_fact_records(journal_path) or []
        bundle_records = load_source_fact_records(
            bundle.manifest_path.with_name(
                bundle.manifest_path.name.replace(".manifest.json", ".jsonl")
            )
        ) or []
        if live_records == bundle_records:
            return "already_current"
        if len(live_records) >= len(bundle_records) and live_records[: len(bundle_records)] == bundle_records:
            return "live_is_newer"
        raise SourceJournalCustodyError("custody_restore_diverged")
    _write_atomic(journal_path, bundle.journal_bytes, 0o600)
    restored = load_source_fact_records(journal_path)
    if restored is None or len(restored) != int(
        bundle.manifest.get("record_count", -1)
    ):
        raise SourceJournalCustodyError("custody_restore_verification_failed")
    return "restored"
