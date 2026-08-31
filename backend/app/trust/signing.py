"""Ed25519 TrustEnvelope signing for B2.5-P8."""

from __future__ import annotations

import base64
from copy import deepcopy
from typing import Any
from uuid import UUID

from cryptography.exceptions import InvalidSignature

from app.inference_policy_registry import (
    PolicyRegistryError,
    validate_envelope_policy_authority,
)
from app.trust.canonicalization import canonicalize_envelope_payload
from app.trust.hash_identity import (
    compute_semantic_truth_hash,
    compute_signature_hash,
)
from app.trust.key_registry import TrustKeyRegistry
from app.trust.schema_verification import (
    SignatureMetadataError,
    validate_signature_algorithm,
    validate_signature_metadata_versions,
)
from app.trust.semantic_authority import (
    AuthorizedTrustEnvelope,
    TrustSemanticAuthorityError,
)
from app.trust.signing_consequence import (
    SignedTrustEnvelopeConsequence,
    SigningConsequenceMaterial,
    mint_signing_consequence,
)
from app.trust.signing_authorization import (
    DurableSigningAuthorization,
    DurableSigningAuthorizationError,
    redeem_durable_signing_authorization,
)


SIGNATURE_PREFIX = "ed25519:"


class TrustEnvelopeSigningError(ValueError):
    """Raised when a TrustEnvelope cannot be signed safely."""


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _decode_b64url(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def encode_ed25519_signature(signature: bytes) -> str:
    """Encode raw Ed25519 signature bytes with an envelope-specific prefix."""
    return f"{SIGNATURE_PREFIX}{_b64url(signature)}"


def decode_ed25519_signature(signature: str) -> bytes:
    """Decode and reject JWT/HMAC-shaped envelope signatures."""
    if not isinstance(signature, str) or not signature.startswith(SIGNATURE_PREFIX):
        raise TrustEnvelopeSigningError("signature_format_unsupported")
    body = signature.removeprefix(SIGNATURE_PREFIX)
    if "." in body or not body:
        raise TrustEnvelopeSigningError("signature_format_unsupported")
    try:
        return _decode_b64url(body)
    except Exception as exc:
        raise TrustEnvelopeSigningError("signature_format_malformed") from exc


def prepare_payload_for_signing(
    payload: dict[str, Any],
    *,
    signing_key_id: str,
    signing_algorithm: str = "ed25519",
) -> dict[str, Any]:
    """Replace unsigned placeholders and compute P8 hash identity before signing."""
    try:
        validate_envelope_policy_authority(payload)
    except PolicyRegistryError as exc:
        raise TrustEnvelopeSigningError(f"policy_authority_refused:{exc}") from exc
    try:
        validate_signature_metadata_versions(payload)
        validate_signature_algorithm(signing_algorithm)
    except SignatureMetadataError as exc:
        raise TrustEnvelopeSigningError(str(exc)) from exc
    prepared = deepcopy(payload)
    prepared["signing_algorithm"] = signing_algorithm
    prepared["signing_key_id"] = signing_key_id
    prepared["signature"] = "ed25519:unsigned-placeholder-for-hash-material"
    prepared["semantic_truth_hash"] = "sha256:" + ("0" * 64)
    prepared["signature_hash"] = "sha256:" + ("0" * 64)
    prepared["semantic_truth_hash"] = compute_semantic_truth_hash(prepared)
    prepared["signature_hash"] = compute_signature_hash(prepared)
    canonicalize_envelope_payload(prepared)
    return prepared


def sign_trust_envelope(
    authorized_envelope: AuthorizedTrustEnvelope,
    *,
    key_registry: TrustKeyRegistry,
) -> dict[str, Any]:
    """Sign only a process-local P5+P7 authority capability."""
    if not isinstance(authorized_envelope, AuthorizedTrustEnvelope):
        raise TrustEnvelopeSigningError("issuance_capability_required")
    try:
        payload = authorized_envelope._validated_payload_copy()
    except TrustSemanticAuthorityError as exc:
        raise TrustEnvelopeSigningError(f"semantic_authority_refused:{exc}") from exc
    return _sign_validated_payload(payload, key_registry=key_registry)


def _sign_validated_payload(
    payload: dict[str, Any], *, key_registry: TrustKeyRegistry
) -> dict[str, Any]:
    """Apply the governed key only after an authority boundary supplied bytes."""
    key = key_registry.active_signing_key()
    prepared = prepare_payload_for_signing(
        payload,
        signing_key_id=key.kid,
        signing_algorithm=key.algorithm,
    )
    from app.trust.canonicalization import canonicalize_signature_material

    material = canonicalize_signature_material(prepared)
    signature = key.private_key.sign(material) if key.private_key else None
    if signature is None:
        raise TrustEnvelopeSigningError("active_signing_key_missing_private_material")
    signed = deepcopy(prepared)
    signed["signature"] = encode_ed25519_signature(signature)
    canonicalize_envelope_payload(signed)
    return signed


def sign_durable_trust_authorization(
    authorization: DurableSigningAuthorization,
    *,
    key_registry: TrustKeyRegistry,
) -> SignedTrustEnvelopeConsequence:
    """Sign authority re-established from PostgreSQL by the signer process."""
    try:
        material = redeem_durable_signing_authorization(authorization)
    except DurableSigningAuthorizationError as exc:
        raise TrustEnvelopeSigningError(str(exc)) from exc
    signed = _sign_validated_payload(
        material.unsigned_envelope,
        key_registry=key_registry,
    )
    return bind_verified_signing_consequence(
        signed,
        key_registry=key_registry,
        tenant_id=material.tenant_id,
        audit_ref=material.audit_ref,
        attempt_id=material.attempt_id,
    )


def sign_trust_envelope_consequence(
    authorized_envelope: AuthorizedTrustEnvelope,
    *,
    key_registry: TrustKeyRegistry,
    tenant_id: UUID,
    audit_ref: str,
    attempt_id: UUID,
) -> SignedTrustEnvelopeConsequence:
    """Sign once and mint an opaque tenant/attempt-bound consequence handle."""
    signed = sign_trust_envelope(authorized_envelope, key_registry=key_registry)
    return bind_verified_signing_consequence(
        signed,
        key_registry=key_registry,
        tenant_id=tenant_id,
        audit_ref=audit_ref,
        attempt_id=attempt_id,
    )


def bind_verified_signing_consequence(
    signed_envelope: dict[str, Any],
    *,
    key_registry: TrustKeyRegistry,
    tenant_id: UUID,
    audit_ref: str,
    attempt_id: UUID,
) -> SignedTrustEnvelopeConsequence:
    """Mint consequence custody only for an independently verified artifact."""
    # Runtime import avoids the signing <-> verification module cycle.
    from app.trust.verification import verify_trust_envelope

    verification = verify_trust_envelope(
        signed_envelope,
        key_registry=key_registry.public_only(),
    )
    if verification.verification_status != "verified":
        raise TrustEnvelopeSigningError(
            f"signing_consequence_verification_refused:{verification.reason_code}"
        )
    return mint_signing_consequence(
        SigningConsequenceMaterial(
            tenant_id=tenant_id,
            audit_ref=audit_ref,
            attempt_id=attempt_id,
            signed_envelope=signed_envelope,
        )
    )


def verify_ed25519_signature(public_key: Any, signature: str, material: bytes) -> None:
    """Verify raw material with public key only."""
    try:
        public_key.verify(decode_ed25519_signature(signature), material)
    except InvalidSignature as exc:
        raise TrustEnvelopeSigningError("signature_invalid") from exc
