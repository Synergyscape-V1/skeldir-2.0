"""Standards-bound canonicalization for schema-valid TrustEnvelope payloads."""

from __future__ import annotations

import copy
import json
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from app.trust.array_ordering import canonicalize_array_by_declared_ordering
from app.trust.schema_versions import validate_schema_canonicalization_compatibility


ROOT = Path(__file__).resolve().parents[3]
CONTRACT_DIR = ROOT / "contracts/trust-api"
TRUST_SCHEMA_PATHS = {
    "trust-envelope-schema-v1": CONTRACT_DIR / "trust-envelope.v1.yaml",
    "trust-envelope-schema-v2": CONTRACT_DIR / "trust-envelope.v2.yaml",
}
CANONICALIZATION_PROFILE = "RFC8785-JCS-Skeldir-v1"
HASH_ALGORITHM = "sha-256"
JSON_SAFE_INTEGER_MAX = 9_007_199_254_740_991
JSON_SAFE_INTEGER_MIN = -9_007_199_254_740_991


class CanonicalizationError(ValueError):
    """Raised when canonical TrustEnvelope bytes cannot be emitted."""


def _read_schema(path: Path) -> Any:
    if path.suffix in {".yaml", ".yml"}:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    return json.loads(path.read_text(encoding="utf-8"))


def _expanded_trust_schema(schema_version: str) -> dict[str, Any]:
    try:
        schema_path = TRUST_SCHEMA_PATHS[schema_version]
    except KeyError as exc:
        raise CanonicalizationError(
            f"schema_version_unsupported:{schema_version}"
        ) from exc
    root_schema = _read_schema(schema_path)

    def expand(value: Any) -> Any:
        if isinstance(value, dict):
            ref = value.get("$ref")
            if isinstance(ref, str):
                if ref.startswith("#/$defs/"):
                    return expand(
                        copy.deepcopy(root_schema["$defs"][ref.rsplit("/", 1)[-1]])
                    )
                file_ref, _, fragment = ref.partition("#")
                if file_ref:
                    target = _read_schema(CONTRACT_DIR / file_ref.rsplit("/", 1)[-1])
                    if fragment.startswith("/$defs/"):
                        target = target["$defs"][fragment.rsplit("/", 1)[-1]]
                    return expand(copy.deepcopy(target))
            return {key: expand(child) for key, child in value.items()}
        if isinstance(value, list):
            return [expand(child) for child in value]
        return value

    expanded = expand(root_schema)
    if not isinstance(expanded, dict):
        raise CanonicalizationError("expanded_schema_not_object")
    return expanded


@lru_cache(maxsize=2)
def _schema_validator(schema_version: str) -> Draft202012Validator:
    """Compile immutable contract validation authority once per worker."""
    return Draft202012Validator(_expanded_trust_schema(schema_version))


def validate_envelope_schema(payload: dict[str, Any]) -> None:
    """Validate a TrustEnvelope payload against P1 contract authority."""
    schema_version, _ = validate_schema_canonicalization_compatibility(
        payload.get("schema_version"), payload.get("canonicalization_version")
    )
    errors = sorted(_schema_validator(schema_version).iter_errors(payload), key=str)
    if errors:
        first = errors[0]
        path = ".".join(str(part) for part in first.absolute_path)
        raise CanonicalizationError(
            f"schema_validation_failed:{first.validator}:{path}"
        )


def _assert_safe_value(value: Any, path: str = "$") -> None:
    if isinstance(value, str):
        for char in value:
            codepoint = ord(char)
            if 0xD800 <= codepoint <= 0xDFFF:
                raise CanonicalizationError(f"invalid_unicode_lone_surrogate:{path}")
        return
    if isinstance(value, bool) or value is None:
        return
    if isinstance(value, int):
        if value < JSON_SAFE_INTEGER_MIN or value > JSON_SAFE_INTEGER_MAX:
            raise CanonicalizationError(f"integer_outside_json_safe_range:{path}")
        return
    if isinstance(value, (float, Decimal)):
        raise CanonicalizationError(f"unsupported_numeric_value:{path}")
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                raise CanonicalizationError(f"non_string_object_key:{path}")
            _assert_safe_value(key, f"{path}.{key}<key>")
            _assert_safe_value(child, f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _assert_safe_value(child, f"{path}[{index}]")
        return
    raise CanonicalizationError(f"unsupported_json_type:{path}:{type(value).__name__}")


def _canonicalize_arrays(value: Any, path: str = "") -> Any:
    if isinstance(value, dict):
        return {
            key: _canonicalize_arrays(child, f"{path}.{key}" if path else key)
            for key, child in value.items()
        }
    if isinstance(value, list):
        ordered_children = [_canonicalize_arrays(child, f"{path}[]") for child in value]
        return canonicalize_array_by_declared_ordering(path, ordered_children)
    return copy.deepcopy(value)


def _canonical_bytes(value: Any) -> bytes:
    _assert_safe_value(value)
    text = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return text.encode("utf-8")


def _validate_versions(payload: dict[str, Any]) -> None:
    validate_schema_canonicalization_compatibility(
        payload.get("schema_version"), payload.get("canonicalization_version")
    )


def canonicalize_envelope_payload(payload: dict[str, Any]) -> bytes:
    """Return canonical UTF-8 bytes for a schema-valid TrustEnvelope payload."""
    if not isinstance(payload, dict):
        raise CanonicalizationError("payload_not_object")
    _validate_versions(payload)
    validate_envelope_schema(payload)
    prepared = _canonicalize_arrays(payload)
    return _canonical_bytes(prepared)


def canonicalize_semantic_truth(payload: dict[str, Any]) -> bytes:
    """Return canonical bytes for a structured semantic-truth hash object."""
    from app.trust.hash_identity import build_semantic_truth_hash_input

    return _canonical_bytes(build_semantic_truth_hash_input(payload))


def canonicalize_artifact_payload(payload: dict[str, Any] | bytes) -> bytes:
    """Return canonical bytes for structured artifact hash input material."""
    from app.trust.hash_identity import build_artifact_hash_input

    return _canonical_bytes(build_artifact_hash_input(payload))


def canonicalize_signature_material(payload: dict[str, Any]) -> bytes:
    """Return canonical bytes for structured signature-domain material."""
    from app.trust.hash_identity import build_signature_hash_input

    return _canonical_bytes(build_signature_hash_input(payload))
