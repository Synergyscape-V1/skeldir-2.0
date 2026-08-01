"""Runtime Ed25519 key authority for the B2.5-P10 Trust API."""

from __future__ import annotations

import base64
import os
from datetime import datetime, timezone

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.trust.jwks import default_public_jwks, registry_from_public_jwks
from app.trust.key_registry import TrustKeyRegistry, TrustSigningKey


class RuntimeTrustKeyConfigurationError(RuntimeError):
    """Raised when runtime signing authority is absent or inconsistent."""


def _decode_seed(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    try:
        seed = base64.urlsafe_b64decode((value + padding).encode("ascii"))
    except Exception as exc:
        raise RuntimeTrustKeyConfigurationError("trust_signing_seed_malformed") from exc
    if len(seed) != 32:
        raise RuntimeTrustKeyConfigurationError("trust_signing_seed_must_be_32_bytes")
    return seed


def _parse_utc(value: str) -> datetime:
    if not value.endswith("Z"):
        raise RuntimeTrustKeyConfigurationError(
            "trust_signing_valid_from_must_be_utc_z"
        )
    try:
        return datetime.fromisoformat(value.removesuffix("Z") + "+00:00").astimezone(
            timezone.utc
        )
    except ValueError as exc:
        raise RuntimeTrustKeyConfigurationError(
            "trust_signing_valid_from_invalid"
        ) from exc


def _active_runtime_key() -> TrustSigningKey:
    seed_value = os.getenv("SKELDIR_TRUST_SIGNING_KEY_SEED_B64URL", "").strip()
    key_id = os.getenv("SKELDIR_TRUST_SIGNING_KEY_ID", "").strip()
    valid_from_value = os.getenv("SKELDIR_TRUST_SIGNING_KEY_VALID_FROM", "").strip()
    if not seed_value or not key_id or not valid_from_value:
        raise RuntimeTrustKeyConfigurationError("trust_signing_authority_unconfigured")
    if not key_id.startswith("kid:") or len(key_id) > 128:
        raise RuntimeTrustKeyConfigurationError("trust_signing_key_id_invalid")
    private_key = Ed25519PrivateKey.from_private_bytes(_decode_seed(seed_value))
    return TrustSigningKey(
        kid=key_id,
        algorithm="ed25519",
        public_key=private_key.public_key(),
        private_key=private_key,
        state="active",
        valid_from=_parse_utc(valid_from_value),
    )


def load_runtime_signing_registry() -> TrustKeyRegistry:
    """Load the one active private signing key from deployment secrets."""
    return TrustKeyRegistry((_active_runtime_key(),))


def load_runtime_verification_registry() -> TrustKeyRegistry:
    """Load active plus public-only historical verification authority."""
    active = _active_runtime_key()
    public_jwks = default_public_jwks()
    historical: tuple[TrustSigningKey, ...] = ()
    if public_jwks.get("keys"):
        public_registry = registry_from_public_jwks(public_jwks)
        historical = tuple(key for key in public_registry.keys if key.kid != active.kid)
    return TrustKeyRegistry((active.public_only(), *historical))
