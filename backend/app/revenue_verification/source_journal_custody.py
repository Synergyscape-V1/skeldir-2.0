"""Signed custody bundles for the XXV source-evidence journal.

The live journal is writable only by the authentication root. This module
makes an independently signed, immutable snapshot of one coherent committed
prefix available outside that live volume, and restores it without ever
discarding newer committed history. It is deliberately filesystem-agnostic:
the custody directory must be separately administered storage (for example
an S3 Object Lock prefix or an EFS access point) whose write authority is not
the financial database maintenance actor.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from app.revenue_verification.source_evidence_journal import (
    _journal_file_lock,
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


def _records_from_raw(raw: bytes) -> list[dict[str, Any]]:
    """Parse exactly the supplied bytes; never re-read the live journal."""

    if not raw:
        return []
    handle = tempfile.NamedTemporaryFile(
        prefix="b26-custody-parse-", suffix=".jsonl", delete=False
    )
    temporary = Path(handle.name)
    try:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
        handle.close()
        records = load_source_fact_records(temporary)
    finally:
        with contextlib.suppress(OSError):
            handle.close()
        with contextlib.suppress(FileNotFoundError):
            temporary.unlink()
        with contextlib.suppress(FileNotFoundError):
            temporary.with_name(temporary.name + ".lock").unlink()
    if records is None:
        raise SourceJournalCustodyError("custody_bundle_missing")
    return records


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


def _signed_manifest(
    raw: bytes, records: list[dict[str, Any]], private_key_path: Path
) -> dict[str, Any]:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    seed = _decode_ed25519_seed(
        private_key_path.read_text(encoding="utf-8")
    )
    key = Ed25519PrivateKey.from_private_bytes(seed)
    public_raw = key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    tip = journal_record_hash(records[-1]) if records else None
    manifest: dict[str, Any] = {
        "version": CUSTODY_BUNDLE_VERSION,
        "journal_sha256": hashlib.sha256(raw).hexdigest(),
        "journal_size": len(raw),
        "record_count": len(records),
        "journal_tip": tip,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "key_sha256": hashlib.sha256(public_raw).hexdigest(),
    }
    signature = key.sign(_canonical(manifest))
    manifest["signature"] = "ed25519:" + base64.urlsafe_b64encode(
        signature
    ).rstrip(b"=").decode("ascii")
    return manifest


def _bundle_paths(custody_dir: Path, tip: str | None) -> tuple[Path, Path]:
    name = tip or "empty"
    return (
        custody_dir / f"source-evidence-{name}.jsonl",
        custody_dir / f"source-evidence-{name}.manifest.json",
    )


def export_custody_bundle(
    *,
    journal: str | os.PathLike[str],
    custody_dir: str | os.PathLike[str],
    private_key_path: str | os.PathLike[str],
) -> CustodyBundle:
    """Write one coherent committed prefix, completing an interrupted export."""

    journal_path = Path(journal)
    if not journal_path.exists():
        raise SourceJournalCustodyError("custody_journal_missing")

    # One read-only shared lock, one byte read, one parse: the observer never
    # needs write access to the live volume, and a concurrent append cannot
    # split the manifest identity from the bytes it describes.
    with _journal_file_lock(journal_path, read_only=True):
        raw = _committed_journal_bytes(journal_path)
        records = _records_from_raw(raw)
        tip = journal_record_hash(records[-1]) if records else None
        bundle_path, manifest_path = _bundle_paths(Path(custody_dir), tip)

        if manifest_path.exists():
            verified = verify_custody_bundle(
                manifest_path=manifest_path,
                public_key_path=Path(private_key_path),
                public_key_is_private_seed=True,
            )
            return verified

        if bundle_path.exists():
            # A previous process died after publishing bytes but before the
            # manifest. Complete that publication only when the bytes are the
            # exact captured live prefix. An orphan planted or replaced by a
            # store writer without the key must never receive a signature.
            existing_raw = bundle_path.read_bytes()
            if existing_raw != raw:
                raise SourceJournalCustodyError(
                    "custody_bundle_substitution"
                )
            existing_records = _records_from_raw(existing_raw)
            manifest = _signed_manifest(
                existing_raw, existing_records, Path(private_key_path)
            )
            _write_atomic(
                manifest_path,
                json.dumps(manifest, sort_keys=True, indent=2).encode("utf-8"),
                0o444,
            )
            return CustodyBundle(
                manifest=manifest,
                journal_bytes=existing_raw,
                manifest_path=manifest_path,
            )

        manifest = _signed_manifest(raw, records, Path(private_key_path))
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

    records = _records_from_raw(raw)
    if len(records) != int(manifest.get("record_count", -1)):
        raise SourceJournalCustodyError("custody_record_count_mismatch")
    tip = journal_record_hash(records[-1]) if records else None
    if tip != manifest.get("journal_tip"):
        raise SourceJournalCustodyError("custody_journal_tip_mismatch")
    return CustodyBundle(
        manifest=manifest, journal_bytes=raw, manifest_path=manifest_file
    )


def _assert_accepted_prefix(
    records: list[dict[str, Any]],
    *,
    accepted_count: int | None,
    accepted_tip: str | None,
) -> None:
    if accepted_count is None and accepted_tip is None:
        return
    if accepted_count is None:
        raise SourceJournalCustodyError("custody_accepted_count_required")
    if accepted_count < 0:
        raise SourceJournalCustodyError("custody_accepted_count_invalid")
    if len(records) < accepted_count:
        raise SourceJournalCustodyError(
            "custody_restore_below_accepted_commitment"
        )
    if accepted_tip is not None:
        if accepted_count == 0:
            raise SourceJournalCustodyError(
                "custody_restore_below_accepted_commitment"
            )
        if journal_record_hash(records[accepted_count - 1]) != accepted_tip:
            raise SourceJournalCustodyError(
                "custody_restore_below_accepted_commitment"
            )


def restore_custody_bundle(
    *,
    manifest_path: str | os.PathLike[str],
    journal: str | os.PathLike[str],
    public_key_path: str | os.PathLike[str],
    public_key_is_private_seed: bool = False,
    accepted_source_count: int | None = None,
    accepted_source_tip: str | None = None,
) -> str:
    """Restore a bundle without discarding newer committed history.

    A live journal that is an exact prefix of the bundle receives the archived
    newer prefix. A live journal that already contains the bundle is left
    untouched. Anything divergent is refused. When the independently accepted
    witness prefix is supplied, a bundle that does not contain it is refused.
    """

    bundle = verify_custody_bundle(
        manifest_path=manifest_path,
        public_key_path=public_key_path,
        public_key_is_private_seed=public_key_is_private_seed,
    )
    bundle_records = _records_from_raw(bundle.journal_bytes)
    _assert_accepted_prefix(
        bundle_records,
        accepted_count=accepted_source_count,
        accepted_tip=accepted_source_tip,
    )
    journal_path = Path(journal)
    with _journal_file_lock(journal_path):
        live_records = (
            _records_from_raw(_committed_journal_bytes(journal_path))
            if journal_path.exists()
            else []
        )
        if live_records == bundle_records:
            return "already_current"
        if (
            len(live_records) <= len(bundle_records)
            and bundle_records[: len(live_records)] == live_records
        ):
            _write_atomic(journal_path, bundle.journal_bytes, 0o600)
            restored = _records_from_raw(_committed_journal_bytes(journal_path))
            if restored != bundle_records:
                raise SourceJournalCustodyError(
                    "custody_restore_verification_failed"
                )
            return "restored_prefix" if live_records else "restored"
        if (
            len(live_records) > len(bundle_records)
            and live_records[: len(bundle_records)] == bundle_records
        ):
            return "live_is_newer"
        raise SourceJournalCustodyError("custody_restore_diverged")
