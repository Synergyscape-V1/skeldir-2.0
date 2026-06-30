"""Typed B2.5-P5 refusal helpers without audit persistence."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from jsonschema import Draft202012Validator

from app.trust.canonicalization import _read_schema
from app.trust.reason_truth_matrix import assert_reason_known


CONTRACT_DIR = Path(__file__).resolve().parents[3] / "contracts/trust-api"
ERROR_SCHEMA_PATH = CONTRACT_DIR / "error-envelope.schema.json"
TRUST_SCHEMA_PATH = CONTRACT_DIR / "trust-envelope.v1.yaml"


class TrustRefusalError(ValueError):
    """Raised when a refusal payload cannot be emitted."""


def tagged_sha256(value: object) -> str:
    """Return a tagged sha256 over stable non-JSON internal bytes."""
    payload = _stable_text(value).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def utc_second(value: datetime | None = None) -> str:
    """Return UTC RFC3339 seconds with Z."""
    instant = value or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    return (
        instant.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def tenant_hash(tenant_id: UUID | str) -> str:
    """Hash raw tenant UUIDs before any external payload projection."""
    return tagged_sha256({"tenant_id": str(tenant_id)})


def _stable_text(value: object) -> str:
    if isinstance(value, dict):
        items = (
            f"{_stable_text(str(key))}:{_stable_text(child)}"
            for key, child in sorted(value.items(), key=lambda item: str(item[0]))
        )
        return "{" + ",".join(items) + "}"
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_stable_text(item) for item in value) + "]"
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def default_audience_binding(
    *, audience_id: str = "b25-p5-internal-builder"
) -> dict[str, object]:
    """Return internal read-only audience binding for unsigned P5 payloads."""
    return {
        "audience_mode": "tenant_internal",
        "audience_id_hash": tagged_sha256({"audience_id": audience_id}),
        "audience_scope": ["trust.envelope.read", "trust.envelope.verify"],
        "presentation_policy": "bearer_not_authority",
        "replay_context_required": True,
    }


def build_error_envelope(
    *,
    tenant_id: UUID | str,
    reason_code: str,
    created_at: datetime | None = None,
    audience_id: str = "b25-p5-internal-builder",
) -> dict[str, object]:
    """Build a schema-valid typed refusal payload without inserting audit rows."""
    reason_code = assert_reason_known(reason_code).value
    payload = {
        "error_envelope_version": "trust-error-envelope-v1",
        "schema_version": "trust-envelope-schema-v1",
        "error_type": reason_code,
        "reason_code": reason_code,
        "tenant_id_hash": tenant_hash(tenant_id),
        "audience_binding": default_audience_binding(audience_id=audience_id),
        "created_at": utc_second(created_at),
        "audit_ref": f"urn:skeldir:audit:p5_refusal_{reason_code}",
        "audit_hash": tagged_sha256(
            {"p5_refusal": reason_code, "tenant": str(tenant_id)}
        ),
    }
    validate_error_envelope(payload)
    return payload


def validate_error_envelope(payload: dict[str, Any]) -> None:
    """Validate a P5 refusal payload against P1 error-envelope authority."""
    schema = _expanded_error_schema()
    errors = sorted(Draft202012Validator(schema).iter_errors(payload), key=str)
    if errors:
        first = errors[0]
        path = ".".join(str(part) for part in first.absolute_path)
        raise TrustRefusalError(
            f"error_envelope_validation_failed:{first.validator}:{path}"
        )


def _expanded_error_schema() -> dict[str, Any]:
    root_schema = _read_schema(ERROR_SCHEMA_PATH)
    trust_schema = _read_schema(TRUST_SCHEMA_PATH)

    def expand(value: Any) -> Any:
        if isinstance(value, dict):
            ref = value.get("$ref")
            if isinstance(ref, str):
                if "trust-envelope.v1.yaml#/$defs/" in ref:
                    return expand(trust_schema["$defs"][ref.rsplit("/", 1)[-1]])
                if ref.startswith("#/$defs/"):
                    return expand(root_schema["$defs"][ref.rsplit("/", 1)[-1]])
                file_ref, _, fragment = ref.partition("#")
                if file_ref:
                    target = _read_schema(CONTRACT_DIR / file_ref.rsplit("/", 1)[-1])
                    if fragment.startswith("/$defs/"):
                        target = target["$defs"][fragment.rsplit("/", 1)[-1]]
                    return expand(target)
            return {key: expand(child) for key, child in value.items()}
        if isinstance(value, list):
            return [expand(child) for child in value]
        return value

    expanded = expand(root_schema)
    if not isinstance(expanded, dict):
        raise TrustRefusalError("expanded_error_schema_not_object")
    return expanded
