"""Public-key TrustEnvelope verification for B2.5-P8."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import re
from typing import Any, Literal

from app.trust.canonicalization import (
    canonicalize_envelope_payload,
    canonicalize_signature_material,
)
from app.trust.hash_identity import (
    compute_semantic_truth_hash,
    compute_signature_hash,
)
from app.trust.key_registry import TrustKeyRegistry, TrustKeyRegistryError
from app.trust.schema_verification import (
    SignatureMetadataError,
    validate_signature_metadata,
)
from app.trust.signing import TrustEnvelopeSigningError, verify_ed25519_signature


VerificationStatus = Literal["verified", "rejected"]
_SAFE_REASON_CODE_RE = re.compile(r"^[a-z0-9_.:-]{1,160}$")
_FORBIDDEN_REASON_TOKENS = (
    "database",
    "postgres",
    "sql",
    "guc",
    "tenant_id",
    "traceback",
    "private",
    "secret",
)


@dataclass(frozen=True)
class TrustEnvelopeVerificationResult:
    """Typed verification result with no partial-trust success state."""

    verification_status: VerificationStatus
    reason_code: str | None
    schema_version: str | None
    canonicalization_version: str | None
    signing_key_id: str | None
    signing_algorithm: str | None
    signature_hash: str | None
    semantic_truth_hash: str | None

    def external_projection(self) -> dict[str, object | None]:
        return asdict(self)


def _reject(
    payload: dict[str, Any] | None, reason_code: str
) -> TrustEnvelopeVerificationResult:
    payload = payload or {}
    return TrustEnvelopeVerificationResult(
        verification_status="rejected",
        reason_code=reason_code,
        schema_version=(
            payload.get("schema_version")
            if isinstance(payload.get("schema_version"), str)
            else None
        ),
        canonicalization_version=(
            payload.get("canonicalization_version")
            if isinstance(payload.get("canonicalization_version"), str)
            else None
        ),
        signing_key_id=(
            payload.get("signing_key_id")
            if isinstance(payload.get("signing_key_id"), str)
            else None
        ),
        signing_algorithm=(
            payload.get("signing_algorithm")
            if isinstance(payload.get("signing_algorithm"), str)
            else None
        ),
        signature_hash=(
            payload.get("signature_hash")
            if isinstance(payload.get("signature_hash"), str)
            else None
        ),
        semantic_truth_hash=(
            payload.get("semantic_truth_hash")
            if isinstance(payload.get("semantic_truth_hash"), str)
            else None
        ),
    )


def _safe_reason_code(exc: Exception) -> str:
    candidate = str(exc).strip().lower()
    if not _SAFE_REASON_CODE_RE.fullmatch(candidate):
        return "verification_failed"
    if any(token in candidate for token in _FORBIDDEN_REASON_TOKENS):
        return "verification_failed"
    return candidate


def _utc_parse(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{field}_invalid")
    parsed = datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    return parsed.astimezone(timezone.utc)


def _assert_temporal_validity(
    payload: dict[str, Any],
    *,
    key_valid_from: datetime,
    key_valid_until: datetime | None,
    key_retired_at: datetime | None,
    at_time: datetime,
) -> None:
    created_at = _utc_parse(payload.get("created_at"), "created_at")
    valid_until = _utc_parse(payload.get("valid_until"), "valid_until")
    observed_at = at_time.astimezone(timezone.utc)
    if observed_at > valid_until:
        raise ValueError("envelope_expired")
    if created_at < key_valid_from.astimezone(timezone.utc):
        raise ValueError("key_not_valid_for_envelope_time")
    if key_valid_until is not None and created_at > key_valid_until.astimezone(
        timezone.utc
    ):
        raise ValueError("key_not_valid_for_envelope_time")
    if key_retired_at is not None and created_at > key_retired_at.astimezone(
        timezone.utc
    ):
        raise ValueError("temporal_forgery_rejected:created_after_key_retirement")


def verify_trust_envelope(
    payload: dict[str, Any],
    *,
    key_registry: TrustKeyRegistry,
    at_time: datetime | None = None,
) -> TrustEnvelopeVerificationResult:
    """Verify a signed TrustEnvelope using public key material only."""
    if not isinstance(payload, dict):
        return _reject(None, "payload_not_object")
    candidate = deepcopy(payload)
    try:
        validate_signature_metadata(candidate)
        expected_semantic_hash = compute_semantic_truth_hash(candidate)
        if candidate.get("semantic_truth_hash") != expected_semantic_hash:
            return _reject(candidate, "semantic_truth_hash_mismatch")
        expected_signature_hash = compute_signature_hash(candidate)
        if candidate.get("signature_hash") != expected_signature_hash:
            return _reject(candidate, "signature_hash_mismatch")
        canonicalize_envelope_payload(candidate)
        key = key_registry.verification_key(str(candidate["signing_key_id"]))
        _assert_temporal_validity(
            candidate,
            key_valid_from=key.valid_from,
            key_valid_until=key.valid_until,
            key_retired_at=key.retired_at,
            at_time=at_time or datetime.now(timezone.utc),
        )
        material = canonicalize_signature_material(candidate)
        verify_ed25519_signature(key.public_key, str(candidate["signature"]), material)
    except SignatureMetadataError as exc:
        return _reject(candidate, _safe_reason_code(exc))
    except TrustKeyRegistryError as exc:
        return _reject(candidate, _safe_reason_code(exc))
    except TrustEnvelopeSigningError as exc:
        return _reject(candidate, _safe_reason_code(exc))
    except Exception as exc:
        return _reject(candidate, _safe_reason_code(exc))
    return TrustEnvelopeVerificationResult(
        verification_status="verified",
        reason_code=None,
        schema_version=str(candidate["schema_version"]),
        canonicalization_version=str(candidate["canonicalization_version"]),
        signing_key_id=str(candidate["signing_key_id"]),
        signing_algorithm=str(candidate["signing_algorithm"]),
        signature_hash=str(candidate["signature_hash"]),
        semantic_truth_hash=str(candidate["semantic_truth_hash"]),
    )
