"""Structured hash identity for B2.5-P2 TrustEnvelope payloads."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from typing import Any

from app.trust.canonicalization import (
    HASH_ALGORITHM,
    _canonicalize_arrays,
    canonicalize_artifact_payload,
    canonicalize_envelope_payload,
    canonicalize_semantic_truth,
    canonicalize_signature_material,
    validate_envelope_schema,
)
from app.trust.hash_domains import project_domain_payload
from app.trust.schema_versions import validate_schema_canonicalization_compatibility


SEMANTIC_DOMAIN = "semantic_truth_v1"
ARTIFACT_DOMAIN = "artifact_payload_v1"
SIGNATURE_DOMAIN = "signature_material_v1"


class HashIdentityError(ValueError):
    """Raised when hash identity cannot be computed."""


def _tagged_sha256(data: bytes) -> str:
    return f"sha256:{sha256(data).hexdigest()}"


def _versions(payload: dict[str, Any]) -> tuple[str, str]:
    return validate_schema_canonicalization_compatibility(
        payload.get("schema_version"), payload.get("canonicalization_version")
    )


def build_semantic_truth_hash_input(payload: dict[str, Any]) -> dict[str, Any]:
    """Build the structured semantic-truth hash input object."""
    if not isinstance(payload, dict):
        raise HashIdentityError("payload_not_object")
    schema_version, canonicalization_version = _versions(payload)
    validate_envelope_schema(payload)
    prepared = _canonicalize_arrays(payload)
    return {
        "hash_domain": SEMANTIC_DOMAIN,
        "schema_version": schema_version,
        "canonicalization_version": canonicalization_version,
        "hash_algorithm": HASH_ALGORITHM,
        "payload": project_domain_payload(prepared, SEMANTIC_DOMAIN),
    }


def build_artifact_hash_input(payload_or_bytes: dict[str, Any] | bytes) -> dict[str, Any]:
    """Build the structured artifact hash input object."""
    if isinstance(payload_or_bytes, bytes):
        artifact_payload: dict[str, Any] = {
            "artifact_bytes_sha256": _tagged_sha256(payload_or_bytes)
        }
        schema_version = "trust-envelope-schema-v1"
        canonicalization_version = "trust-canonical-json-v1"
    elif isinstance(payload_or_bytes, dict):
        payload = deepcopy(payload_or_bytes)
        schema_version = payload.pop("schema_version", "trust-envelope-schema-v1")
        canonicalization_version = payload.pop(
            "canonicalization_version", "trust-canonical-json-v1"
        )
        if not isinstance(schema_version, str) or not isinstance(
            canonicalization_version, str
        ):
            raise HashIdentityError("artifact_version_not_string")
        artifact_payload = payload
    else:
        raise HashIdentityError("artifact_payload_not_object_or_bytes")
    validate_schema_canonicalization_compatibility(schema_version, canonicalization_version)
    return {
        "hash_domain": ARTIFACT_DOMAIN,
        "schema_version": schema_version,
        "canonicalization_version": canonicalization_version,
        "hash_algorithm": HASH_ALGORITHM,
        "payload": artifact_payload,
    }


def build_signature_hash_input(payload: dict[str, Any]) -> dict[str, Any]:
    """Build the structured signature-domain hash input object."""
    if not isinstance(payload, dict):
        raise HashIdentityError("payload_not_object")
    schema_version, canonicalization_version = _versions(payload)
    validate_envelope_schema(payload)
    prepared = _canonicalize_arrays(payload)
    signature_material = project_domain_payload(prepared, SIGNATURE_DOMAIN)
    signature_material["semantic_truth_hash"] = compute_semantic_truth_hash(payload)
    artifact_hash = payload.get("artifact_hash")
    if artifact_hash is not None:
        signature_material["artifact_hash"] = artifact_hash
    return {
        "hash_domain": SIGNATURE_DOMAIN,
        "schema_version": schema_version,
        "canonicalization_version": canonicalization_version,
        "hash_algorithm": HASH_ALGORITHM,
        "payload": signature_material,
    }


def compute_semantic_truth_hash(payload: dict[str, Any]) -> str:
    """Compute sha256:<hex> over structured canonical semantic-truth bytes."""
    return _tagged_sha256(canonicalize_semantic_truth(payload))


def compute_artifact_hash(payload_or_bytes: dict[str, Any] | bytes) -> str:
    """Compute sha256:<hex> over structured canonical artifact bytes."""
    return _tagged_sha256(canonicalize_artifact_payload(payload_or_bytes))


def compute_signature_hash(payload_or_signature_material: dict[str, Any]) -> str:
    """Compute sha256:<hex> over structured canonical signature-domain bytes."""
    return _tagged_sha256(canonicalize_signature_material(payload_or_signature_material))


def compute_envelope_payload_hash(payload: dict[str, Any]) -> str:
    """Compute a full-envelope canonical payload hash for test/audit tooling."""
    return _tagged_sha256(canonicalize_envelope_payload(payload))
