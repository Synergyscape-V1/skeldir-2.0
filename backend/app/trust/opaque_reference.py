"""Keyed opaque provider-reference pseudonymization for B2.5-P3."""

from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass
from typing import Final


OPAQUE_REFERENCE_HASH_DOMAIN: Final[str] = "opaque_reference_v1"
OPAQUE_REFERENCE_MESSAGE_DOMAIN: Final[str] = "skeldir:b25:p3:opaque_reference:v1"
HMAC_SHA256_RE = re.compile(r"^hmac-sha256:[0-9a-f]{64}$")


class OpaqueReferenceError(ValueError):
    """Raised when an opaque reference cannot be safely emitted."""


@dataclass(frozen=True)
class OpaqueReference:
    opaque_reference_hash: str
    hash_algorithm: str
    hash_domain: str
    key_scope: str
    key_version: str
    provider: str
    source_field_path: str

    def external_metadata(self) -> dict[str, str]:
        """Return non-secret metadata safe for TrustEnvelope projection."""
        return {
            "hash_algorithm": self.hash_algorithm,
            "hash_domain": self.hash_domain,
            "key_scope": self.key_scope,
            "key_version": self.key_version,
            "provider": self.provider,
            "source_field_path": self.source_field_path,
        }


def _require_nonempty(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise OpaqueReferenceError(f"opaque_reference_missing_{field_name}")
    return value


def _reference_bytes(raw_reference: str | bytes) -> bytes:
    if isinstance(raw_reference, bytes):
        return raw_reference
    if isinstance(raw_reference, str):
        return raw_reference.encode("utf-8")
    raise OpaqueReferenceError("opaque_reference_raw_reference_not_text_or_bytes")


def _frame_part(name: str, value: bytes) -> bytes:
    name_bytes = name.encode("ascii")
    return (
        str(len(name_bytes)).encode("ascii")
        + b":"
        + name_bytes
        + b"="
        + str(len(value)).encode("ascii")
        + b":"
        + value
    )


def pseudonymize_provider_reference(
    *,
    raw_reference: str | bytes,
    tenant_scope: str,
    provider: str,
    source_field_path: str,
    key_version: str,
    key_material: bytes,
    hash_domain: str = OPAQUE_REFERENCE_HASH_DOMAIN,
    key_scope: str = "tenant_scoped",
) -> OpaqueReference:
    """Return a tenant/domain/provider/field-separated HMAC reference.

    The raw provider reference is intentionally absent from the returned object.
    """
    tenant_scope = _require_nonempty(tenant_scope, "tenant_scope")
    provider = _require_nonempty(provider, "provider")
    source_field_path = _require_nonempty(source_field_path, "source_field_path")
    key_version = _require_nonempty(key_version, "key_version")
    hash_domain = _require_nonempty(hash_domain, "hash_domain")
    key_scope = _require_nonempty(key_scope, "key_scope")
    if key_scope not in {"tenant_scoped", "trust_scope"}:
        raise OpaqueReferenceError(f"opaque_reference_invalid_key_scope:{key_scope}")
    if not isinstance(key_material, bytes) or not key_material:
        raise OpaqueReferenceError("opaque_reference_missing_key_material")

    message_bytes = b"|".join(
        (
            _frame_part("domain", OPAQUE_REFERENCE_MESSAGE_DOMAIN.encode("ascii")),
            _frame_part("hash_domain", hash_domain.encode("utf-8")),
            _frame_part("key_version", key_version.encode("utf-8")),
            _frame_part("provider", provider.encode("utf-8")),
            _frame_part("raw_reference", _reference_bytes(raw_reference)),
            _frame_part("source_field_path", source_field_path.encode("utf-8")),
            _frame_part("tenant_scope", tenant_scope.encode("utf-8")),
        )
    )
    digest = hmac.new(key_material, message_bytes, hashlib.sha256).hexdigest()
    return OpaqueReference(
        opaque_reference_hash=f"hmac-sha256:{digest}",
        hash_algorithm="hmac-sha256",
        hash_domain=hash_domain,
        key_scope=key_scope,
        key_version=key_version,
        provider=provider,
        source_field_path=source_field_path,
    )


def raw_sha256_provider_reference(raw_reference: str | bytes) -> str:
    """Return the forbidden raw SHA-256 form for negative controls only."""
    return "sha256:" + hashlib.sha256(_reference_bytes(raw_reference)).hexdigest()


def validate_not_raw_sha256_provider_reference(
    *,
    candidate_reference_hash: str,
    raw_reference: str | bytes,
) -> None:
    """Reject enumerable raw SHA-256 provider-reference pseudonyms."""
    if candidate_reference_hash == raw_sha256_provider_reference(raw_reference):
        raise OpaqueReferenceError("opaque_reference_raw_sha256_forbidden")
    if candidate_reference_hash.startswith("sha256:"):
        raise OpaqueReferenceError("opaque_reference_unkeyed_sha256_forbidden")
    if not HMAC_SHA256_RE.match(candidate_reference_hash):
        raise OpaqueReferenceError("opaque_reference_hash_format_invalid")
