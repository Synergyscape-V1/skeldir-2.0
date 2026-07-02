"""Structured hash identity for B2.5-P2 TrustEnvelope payloads."""

from __future__ import annotations

import re
from copy import deepcopy
from hashlib import sha256
from typing import Any

from jsonschema import Draft202012Validator

from app.trust.canonicalization import (
    HASH_ALGORITHM,
    _canonicalize_arrays,
    canonicalize_artifact_payload,
    canonicalize_envelope_payload,
    canonicalize_semantic_truth,
    canonicalize_signature_material,
    validate_envelope_schema,
)
from app.trust.hash_domains import (
    HashDomainError,
    classify_hash_domain,
    project_domain_payload,
)
from app.trust.schema_versions import validate_schema_canonicalization_compatibility


SEMANTIC_DOMAIN = "semantic_truth_v1"
ARTIFACT_DOMAIN = "artifact_payload_v1"
SIGNATURE_DOMAIN = "signature_material_v1"
HASH_DOMAIN_WRAPPER_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "B2.5-P2 HashDomainWrapper",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "hash_domain",
        "schema_version",
        "canonicalization_version",
        "hash_algorithm",
        "payload",
    ],
    "properties": {
        "hash_domain": {
            "type": "string",
            "enum": [SEMANTIC_DOMAIN, ARTIFACT_DOMAIN, SIGNATURE_DOMAIN],
        },
        "schema_version": {"type": "string"},
        "canonicalization_version": {"type": "string"},
        "hash_algorithm": {"type": "string", "const": HASH_ALGORITHM},
        "payload": {"type": "object"},
    },
}
_HASH_DOMAIN_WRAPPER_VALIDATOR = Draft202012Validator(HASH_DOMAIN_WRAPPER_SCHEMA)
HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_ARTIFACT_BYTES_FIELDS = frozenset({"artifact_bytes_sha256"})
_SIGNATURE_DERIVED_FIELDS = frozenset({"semantic_truth_hash", "artifact_hash"})
_SIGNATURE_BOUND_ARTIFACT_FIELDS = frozenset({"artifact_ref"})


class HashIdentityError(ValueError):
    """Raised when hash identity cannot be computed."""


def _tagged_sha256(data: bytes) -> str:
    return f"sha256:{sha256(data).hexdigest()}"


def _iter_payload_paths(value: Any, path: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else key
            paths.append(child_path)
            paths.extend(_iter_payload_paths(child, child_path))
    elif isinstance(value, list):
        child_path = f"{path}[]"
        for child in value:
            paths.extend(_iter_payload_paths(child, child_path))
    return paths


def _get_path_value(payload: dict[str, Any], path: str) -> Any:
    value: Any = payload
    for part in path.split("."):
        if part.endswith("[]"):
            return None
        value = value[part]
    return value


def _validate_payload_path(domain: str, path: str, value: Any) -> None:
    if domain == ARTIFACT_DOMAIN and path in _ARTIFACT_BYTES_FIELDS:
        if not isinstance(value, str) or not HASH_RE.match(value):
            raise HashDomainError(f"hash_wrapper_invalid_artifact_bytes_hash:{path}")
        return
    if domain == SIGNATURE_DOMAIN and path in _SIGNATURE_DERIVED_FIELDS:
        if not isinstance(value, str) or not HASH_RE.match(value):
            raise HashDomainError(f"hash_wrapper_invalid_derived_hash:{path}")
        return
    if domain == SIGNATURE_DOMAIN and path in _SIGNATURE_BOUND_ARTIFACT_FIELDS:
        if value is not None and not isinstance(value, str):
            raise HashDomainError(f"hash_wrapper_invalid_artifact_ref:{path}")
        return

    declared_domain = classify_hash_domain(path)
    if declared_domain != domain:
        raise HashDomainError(
            f"hash_wrapper_payload_domain_mismatch:{domain}:{path}:{declared_domain}"
        )


def _validate_hash_domain_wrapper_schema(wrapper: Any) -> dict[str, Any]:
    """Apply the declarative wrapper closure contract before domain checks."""
    errors = sorted(
        _HASH_DOMAIN_WRAPPER_VALIDATOR.iter_errors(wrapper),
        key=lambda error: (list(error.path), list(error.schema_path)),
    )
    if errors:
        first = errors[0]
        path = ".".join(str(part) for part in first.absolute_path) or "$"
        raise HashDomainError(
            f"hash_wrapper_schema_validation_failed:{first.validator}:{path}"
        )
    if not isinstance(wrapper, dict):
        raise HashDomainError("hash_wrapper_schema_validation_failed:type:$")
    return wrapper


def validate_hash_domain_wrapper(wrapper: Any) -> dict[str, Any]:
    """Validate closed hash-domain wrapper shape before canonical byte encoding."""
    validated = _validate_hash_domain_wrapper_schema(wrapper)
    wrapper_copy = deepcopy(validated)

    validate_schema_canonicalization_compatibility(
        wrapper_copy["schema_version"], wrapper_copy["canonicalization_version"]
    )

    domain = wrapper_copy["hash_domain"]
    payload = wrapper_copy["payload"]
    for path in _iter_payload_paths(payload):
        _validate_payload_path(domain, path, _get_path_value(payload, path))
    return wrapper_copy


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
    return validate_hash_domain_wrapper(
        {
            "hash_domain": SEMANTIC_DOMAIN,
            "schema_version": schema_version,
            "canonicalization_version": canonicalization_version,
            "hash_algorithm": HASH_ALGORITHM,
            "payload": project_domain_payload(prepared, SEMANTIC_DOMAIN),
        }
    )


def build_artifact_hash_input(
    payload_or_bytes: dict[str, Any] | bytes,
) -> dict[str, Any]:
    """Build the structured artifact hash input object."""
    if isinstance(payload_or_bytes, bytes):
        artifact_payload: dict[str, Any] = {
            "artifact_bytes_sha256": _tagged_sha256(payload_or_bytes)
        }
        schema_version = "trust-envelope-schema-v1"
        canonicalization_version = "trust-canonical-json-v1"
    elif isinstance(payload_or_bytes, dict):
        payload = deepcopy(payload_or_bytes)
        schema_version = payload.get("schema_version", "trust-envelope-schema-v1")
        canonicalization_version = payload.get(
            "canonicalization_version", "trust-canonical-json-v1"
        )
        if not isinstance(schema_version, str) or not isinstance(
            canonicalization_version, str
        ):
            raise HashIdentityError("artifact_version_not_string")
        if "envelope_version" in payload:
            validate_envelope_schema(payload)
            artifact_payload = project_domain_payload(
                _canonicalize_arrays(payload), ARTIFACT_DOMAIN
            )
        else:
            payload.pop("schema_version", None)
            payload.pop("canonicalization_version", None)
            artifact_payload = payload
    else:
        raise HashIdentityError("artifact_payload_not_object_or_bytes")
    validate_schema_canonicalization_compatibility(
        schema_version, canonicalization_version
    )
    return validate_hash_domain_wrapper(
        {
            "hash_domain": ARTIFACT_DOMAIN,
            "schema_version": schema_version,
            "canonicalization_version": canonicalization_version,
            "hash_algorithm": HASH_ALGORITHM,
            "payload": artifact_payload,
        }
    )


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
    artifact_ref = payload.get("artifact_ref")
    if artifact_ref is not None:
        signature_material["artifact_ref"] = artifact_ref
    return validate_hash_domain_wrapper(
        {
            "hash_domain": SIGNATURE_DOMAIN,
            "schema_version": schema_version,
            "canonicalization_version": canonicalization_version,
            "hash_algorithm": HASH_ALGORITHM,
            "payload": signature_material,
        }
    )


def compute_semantic_truth_hash(payload: dict[str, Any]) -> str:
    """Compute sha256:<hex> over structured canonical semantic-truth bytes."""
    return _tagged_sha256(canonicalize_semantic_truth(payload))


def compute_artifact_hash(payload_or_bytes: dict[str, Any] | bytes) -> str:
    """Compute sha256:<hex> over structured canonical artifact bytes."""
    return _tagged_sha256(canonicalize_artifact_payload(payload_or_bytes))


def compute_signature_hash(payload_or_signature_material: dict[str, Any]) -> str:
    """Compute sha256:<hex> over structured canonical signature-domain bytes."""
    return _tagged_sha256(
        canonicalize_signature_material(payload_or_signature_material)
    )


def compute_envelope_payload_hash(payload: dict[str, Any]) -> str:
    """Compute a full-envelope canonical payload hash for test/audit tooling."""
    return _tagged_sha256(canonicalize_envelope_payload(payload))
