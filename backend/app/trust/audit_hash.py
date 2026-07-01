"""B2.5-P7 canonical trust audit material and hash identity."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from typing import Any

from app.trust.canonicalization import _assert_safe_value, _canonical_bytes
from app.trust.refusal import tagged_sha256


AUDIT_HASH_DOMAIN = "trust_audit_v1"


class TrustAuditHashError(ValueError):
    """Raised when trust audit material cannot be canonicalized."""


def canonical_audit_material(material: dict[str, Any]) -> dict[str, Any]:
    """Return canonical audit material with a domain wrapper."""
    if not isinstance(material, dict):
        raise TrustAuditHashError("audit_material_not_object")
    wrapped = {
        "audit_hash_domain": AUDIT_HASH_DOMAIN,
        "hash_algorithm": "sha-256",
        "material": deepcopy(material),
    }
    _assert_safe_value(wrapped)
    return wrapped


def canonical_audit_bytes(material: dict[str, Any]) -> bytes:
    """Return deterministic UTF-8 bytes for trust audit hash material."""
    return _canonical_bytes(canonical_audit_material(material))


def compute_audit_hash(material: dict[str, Any]) -> str:
    """Return sha256:<hex> over canonical trust audit material."""
    return "sha256:" + sha256(canonical_audit_bytes(material)).hexdigest()


def audit_ref_from_identity(*, event_type: str, idempotency_key_hash: str) -> str:
    """Return a deterministic opaque audit ref for idempotent reconstruction."""
    digest = tagged_sha256(
        {"event_type": event_type, "idempotency_key_hash": idempotency_key_hash}
    ).split(":", 1)[1]
    return f"urn:skeldir:audit:{event_type}:{digest[:32]}"


def idempotency_key_hash(*, tenant_id_hash: str, idempotency_key: str) -> str:
    """Hash caller-supplied idempotency without exposing the raw key."""
    return tagged_sha256(
        {
            "tenant_id_hash": tenant_id_hash,
            "idempotency_key": str(idempotency_key),
            "purpose": "b25-p7-trust-audit-idempotency",
        }
    )


def request_identity_hash(
    *,
    tenant_id_hash: str,
    subject_type: str,
    subject_ref_hash: str | None,
    audience_id_hash: str | None,
) -> str:
    """Hash stable request identity dimensions for audit lookup."""
    return tagged_sha256(
        {
            "tenant_id_hash": tenant_id_hash,
            "subject_type": subject_type,
            "subject_ref_hash": subject_ref_hash,
            "audience_id_hash": audience_id_hash,
            "purpose": "b25-p7-trust-request-identity",
        }
    )
