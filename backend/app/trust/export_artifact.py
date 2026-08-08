"""Bounded, domain-separated signed export artifacts for B2.5-P11."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Literal

from app.trust.canonicalization import canonicalize_envelope_payload
from app.trust.hash_identity import compute_artifact_hash
from app.trust.key_registry import TrustKeyRegistry
from app.trust.signing import (
    TrustEnvelopeSigningError,
    encode_ed25519_signature,
    verify_ed25519_signature,
)
from app.trust.verification import verify_trust_envelope


EXPORT_ARTIFACT_SCHEMA_VERSION = "b25-p11-export-artifact-v1"
EXPORT_ARTIFACT_CANONICALIZATION_VERSION = "b25-p11-artifact-framing-v1"
EXPORT_ARTIFACT_SIGNING_DOMAIN = b"skeldir:b25-p11:export-artifact:v1\x00"
EXPORT_ARTIFACT_SIGNING_DOMAIN_LABEL = "skeldir:b25-p11:export-artifact:v1\\0"
MAX_EXPORT_ARTIFACT_ENVELOPES = 2

_BASE_FIELDS = frozenset(
    {
        "artifact_schema_version",
        "canonicalization_version",
        "artifact_signing_domain",
        "envelopes",
        "generated_at",
        "tenant_id_hash",
    }
)
_SIGNED_FIELDS = _BASE_FIELDS | frozenset(
    {"artifact_hash", "signature", "signing_key_id", "signing_algorithm"}
)


class ExportArtifactError(ValueError):
    """Raised when an export artifact violates identity or signing physics."""


@dataclass(frozen=True)
class ExportArtifactVerificationResult:
    verification_status: Literal["verified", "rejected"]
    reason_code: str | None
    artifact_hash: str | None
    signing_key_id: str | None

    def external_projection(self) -> dict[str, object | None]:
        return asdict(self)


def _utc_second(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ExportArtifactError("artifact_generated_at_timezone_required")
    return (
        value.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _frame(label: str, payload: bytes) -> bytes:
    label_bytes = label.encode("utf-8")
    return (
        len(label_bytes).to_bytes(2, "big")
        + label_bytes
        + len(payload).to_bytes(8, "big")
        + payload
    )


def _require_text(value: Any, field_path: str) -> str:
    if not isinstance(value, str):
        raise ExportArtifactError(f"artifact_text_field_invalid:{field_path}")
    return value


def _ordered_envelopes(envelopes: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    copied = [deepcopy(value) for value in envelopes]
    return sorted(
        copied,
        key=lambda value: (
            _require_text(value.get("subject_ref"), "envelopes[].subject_ref"),
            _require_text(
                value.get("semantic_truth_hash"),
                "envelopes[].semantic_truth_hash",
            ),
            _require_text(value.get("envelope_id"), "envelopes[].envelope_id"),
        ),
    )


def _assert_no_raw_tenant_or_float(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        if "tenant_id" in value:
            raise ExportArtifactError(f"raw_tenant_id_forbidden:{path}")
        for key, child in value.items():
            _assert_no_raw_tenant_or_float(child, f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_raw_tenant_or_float(child, f"{path}[{index}]")
        return
    if isinstance(value, float):
        raise ExportArtifactError(f"artifact_float_forbidden:{path}")


def _validate_envelopes(
    envelopes: list[dict[str, Any]],
    *,
    tenant_id_hash: str,
    key_registry: TrustKeyRegistry | None = None,
) -> None:
    if not 1 <= len(envelopes) <= MAX_EXPORT_ARTIFACT_ENVELOPES:
        raise ExportArtifactError("artifact_envelope_count_out_of_bounds")
    for envelope in envelopes:
        canonicalize_envelope_payload(envelope)
        if envelope.get("subject_type") != "match_verdict":
            raise ExportArtifactError("unsupported_export_subject_type")
        if envelope.get("tenant_id_hash") != tenant_id_hash:
            raise ExportArtifactError("artifact_envelope_tenant_mismatch")
        if key_registry is not None:
            result = verify_trust_envelope(
                envelope,
                key_registry=key_registry.public_only(),
            )
            if result.verification_status != "verified":
                raise ExportArtifactError(
                    f"embedded_envelope_verification_failed:{result.reason_code}"
                )


def build_export_artifact(
    *,
    envelopes: Iterable[dict[str, Any]],
    tenant_id_hash: str,
    generated_at: datetime,
) -> dict[str, Any]:
    """Build deterministic unsigned artifact content from complete envelopes."""
    ordered = _ordered_envelopes(envelopes)
    _validate_envelopes(ordered, tenant_id_hash=tenant_id_hash)
    artifact = {
        "artifact_schema_version": EXPORT_ARTIFACT_SCHEMA_VERSION,
        "canonicalization_version": EXPORT_ARTIFACT_CANONICALIZATION_VERSION,
        "artifact_signing_domain": EXPORT_ARTIFACT_SIGNING_DOMAIN_LABEL,
        "envelopes": ordered,
        "generated_at": _utc_second(generated_at),
        "tenant_id_hash": tenant_id_hash,
    }
    _assert_no_raw_tenant_or_float(artifact)
    return artifact


def _artifact_identity_bytes(payload: dict[str, Any]) -> bytes:
    if not _BASE_FIELDS.issubset(payload):
        raise ExportArtifactError("artifact_identity_fields_missing")
    envelopes = _ordered_envelopes(payload["envelopes"])
    pieces = [
        _frame(
            "artifact_schema_version",
            _require_text(
                payload["artifact_schema_version"], "artifact_schema_version"
            ).encode("utf-8"),
        ),
        _frame(
            "canonicalization_version",
            _require_text(
                payload["canonicalization_version"], "canonicalization_version"
            ).encode("utf-8"),
        ),
        _frame(
            "artifact_signing_domain",
            _require_text(
                payload["artifact_signing_domain"], "artifact_signing_domain"
            ).encode("utf-8"),
        ),
        _frame(
            "generated_at",
            _require_text(payload["generated_at"], "generated_at").encode("utf-8"),
        ),
        _frame(
            "tenant_id_hash",
            _require_text(payload["tenant_id_hash"], "tenant_id_hash").encode("utf-8"),
        ),
        _frame(
            "signing_key_id",
            _require_text(payload["signing_key_id"], "signing_key_id").encode("utf-8"),
        ),
        _frame(
            "signing_algorithm",
            _require_text(payload["signing_algorithm"], "signing_algorithm").encode(
                "utf-8"
            ),
        ),
        _frame("envelope_count", str(len(envelopes)).encode("ascii")),
    ]
    pieces.extend(
        _frame(f"envelopes[{index}]", canonicalize_envelope_payload(envelope))
        for index, envelope in enumerate(envelopes)
    )
    return b"".join(pieces)


def export_artifact_signature_material(artifact_hash: str) -> bytes:
    """Return the domain-separated bytes covered by the export signature."""
    return EXPORT_ARTIFACT_SIGNING_DOMAIN + artifact_hash.encode("ascii")


def sign_export_artifact(
    payload: dict[str, Any],
    *,
    key_registry: TrustKeyRegistry,
) -> dict[str, Any]:
    """Hash and sign an export with the P8 active key only."""
    if set(payload) != _BASE_FIELDS:
        raise ExportArtifactError("unsigned_artifact_shape_invalid")
    key = key_registry.active_signing_key()
    if key.private_key is None:
        raise ExportArtifactError("active_signing_key_missing_private_material")
    signed = deepcopy(payload)
    signed["signing_key_id"] = key.kid
    signed["signing_algorithm"] = key.algorithm
    _validate_envelopes(
        signed["envelopes"],
        tenant_id_hash=_require_text(signed["tenant_id_hash"], "tenant_id_hash"),
        key_registry=key_registry,
    )
    signed["artifact_hash"] = compute_artifact_hash(_artifact_identity_bytes(signed))
    signed["signature"] = encode_ed25519_signature(
        key.private_key.sign(
            export_artifact_signature_material(
                _require_text(signed["artifact_hash"], "artifact_hash")
            )
        )
    )
    _assert_no_raw_tenant_or_float(signed)
    return signed


def verify_export_artifact(
    payload: dict[str, Any],
    *,
    key_registry: TrustKeyRegistry,
) -> ExportArtifactVerificationResult:
    """Verify artifact shape, embedded envelopes, hash, domain, and signature."""
    candidate = deepcopy(payload) if isinstance(payload, dict) else {}
    try:
        if set(candidate) != _SIGNED_FIELDS:
            raise ExportArtifactError("artifact_shape_invalid")
        if candidate["artifact_schema_version"] != EXPORT_ARTIFACT_SCHEMA_VERSION:
            raise ExportArtifactError("artifact_schema_version_unsupported")
        if (
            candidate["canonicalization_version"]
            != EXPORT_ARTIFACT_CANONICALIZATION_VERSION
        ):
            raise ExportArtifactError("artifact_canonicalization_version_unsupported")
        if candidate["artifact_signing_domain"] != EXPORT_ARTIFACT_SIGNING_DOMAIN_LABEL:
            raise ExportArtifactError("artifact_signing_domain_mismatch")
        if candidate["signing_algorithm"] != "ed25519":
            raise ExportArtifactError("artifact_signing_algorithm_unsupported")
        _assert_no_raw_tenant_or_float(candidate)
        _validate_envelopes(
            candidate["envelopes"],
            tenant_id_hash=_require_text(candidate["tenant_id_hash"], "tenant_id_hash"),
            key_registry=key_registry,
        )
        expected_hash = compute_artifact_hash(_artifact_identity_bytes(candidate))
        if candidate["artifact_hash"] != expected_hash:
            raise ExportArtifactError("artifact_hash_mismatch")
        key = key_registry.verification_key(
            _require_text(candidate["signing_key_id"], "signing_key_id")
        )
        verify_ed25519_signature(
            key.public_key,
            _require_text(candidate["signature"], "signature"),
            export_artifact_signature_material(expected_hash),
        )
    except (
        ExportArtifactError,
        TrustEnvelopeSigningError,
        ValueError,
        TypeError,
    ) as exc:
        reason = str(exc)
        if not reason or len(reason) > 180:
            reason = "artifact_verification_failed"
        rejected_hash = candidate.get("artifact_hash")
        rejected_key_id = candidate.get("signing_key_id")
        return ExportArtifactVerificationResult(
            verification_status="rejected",
            reason_code=reason,
            artifact_hash=rejected_hash if isinstance(rejected_hash, str) else None,
            signing_key_id=(
                rejected_key_id if isinstance(rejected_key_id, str) else None
            ),
        )
    return ExportArtifactVerificationResult(
        verification_status="verified",
        reason_code=None,
        artifact_hash=_require_text(candidate["artifact_hash"], "artifact_hash"),
        signing_key_id=_require_text(candidate["signing_key_id"], "signing_key_id"),
    )
