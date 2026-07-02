"""Fail-closed schema, canonicalization, and signature metadata checks for P8."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml

from app.trust.schema_versions import (
    ROOT,
    VersionRegistryError,
    validate_canonicalization_version,
    validate_schema_version,
)


SIGNATURE_SCHEMA_VERSION = "trust-signature-v1"
SUPPORTED_TRUST_SIGNING_ALGORITHMS: tuple[str, ...] = ("ed25519",)
SignatureAlgorithm = Literal["ed25519"]
SCHEMA_REGISTRY_PATH = Path(ROOT) / "contracts/trust-api/schema-version-registry.yaml"


class SignatureMetadataError(ValueError):
    """Raised when signature metadata is missing, unsupported, or malformed."""


def _read_registry() -> dict[str, Any]:
    with SCHEMA_REGISTRY_PATH.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise SignatureMetadataError("signature_registry_not_object")
    return data


def get_supported_signature_schema_versions() -> tuple[str, ...]:
    """Return supported signature metadata schema versions from contract registry."""
    rows = _read_registry().get("supported_signature_schema_versions", [])
    return tuple(
        row["signature_schema_version"]
        for row in rows
        if row.get("status") == "supported"
    )


def validate_signature_schema_version(signature_schema_version: Any) -> str:
    """Validate signature schema version independently from envelope schema."""
    if not isinstance(signature_schema_version, str) or not signature_schema_version:
        raise SignatureMetadataError("signature_version_rejection:missing")
    if signature_schema_version not in get_supported_signature_schema_versions():
        raise SignatureMetadataError(
            f"signature_version_rejection:{signature_schema_version}"
        )
    return signature_schema_version


def validate_signature_algorithm(signing_algorithm: Any) -> SignatureAlgorithm:
    """P8 runtime signing supports Ed25519 only; HMAC/JWT algorithms fail closed."""
    if not isinstance(signing_algorithm, str) or not signing_algorithm:
        raise SignatureMetadataError("signature_algorithm_unsupported:missing")
    normalized = signing_algorithm.lower()
    if normalized not in SUPPORTED_TRUST_SIGNING_ALGORITHMS:
        raise SignatureMetadataError(f"signature_algorithm_unsupported:{signing_algorithm}")
    return "ed25519"


def validate_signature_metadata_versions(payload: dict[str, Any]) -> None:
    """Reject unsupported versions before any trusted verification result exists."""
    try:
        validate_schema_version(payload.get("schema_version"))
        validate_canonicalization_version(payload.get("canonicalization_version"))
    except VersionRegistryError as exc:
        raise SignatureMetadataError(str(exc)) from exc
    validate_signature_schema_version(SIGNATURE_SCHEMA_VERSION)


def validate_signature_metadata(payload: dict[str, Any]) -> SignatureAlgorithm:
    """Validate required signature metadata fields without accepting JWT/HMAC shapes."""
    validate_signature_metadata_versions(payload)
    signing_key_id = payload.get("signing_key_id")
    signature = payload.get("signature")
    signature_hash = payload.get("signature_hash")
    if not isinstance(signing_key_id, str) or not signing_key_id:
        raise SignatureMetadataError("signing_key_id_missing")
    if not isinstance(signature, str) or not signature:
        raise SignatureMetadataError("signature_missing")
    if not isinstance(signature_hash, str) or not signature_hash:
        raise SignatureMetadataError("signature_hash_missing")
    return validate_signature_algorithm(payload.get("signing_algorithm"))
