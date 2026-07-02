"""TrustEnvelope signing-key registry and public JWKS projection for B2.5-P8."""

from __future__ import annotations

import base64
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Literal

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


TrustKeyState = Literal["active", "verification_only", "revoked", "expired"]


class TrustKeyRegistryError(ValueError):
    """Raised when trust signing-key registry state is invalid."""


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


@dataclass(frozen=True)
class TrustSigningKey:
    """One TrustEnvelope signing key record with explicit verification semantics."""

    kid: str
    algorithm: str
    public_key: Ed25519PublicKey
    private_key: Ed25519PrivateKey | None
    state: TrustKeyState
    valid_from: datetime
    valid_until: datetime | None = None

    def __post_init__(self) -> None:
        if not self.kid.startswith("kid:"):
            raise TrustKeyRegistryError("trust_key_id_must_use_kid_prefix")
        if self.algorithm != "ed25519":
            raise TrustKeyRegistryError(f"unsupported_trust_key_algorithm:{self.algorithm}")
        if self.valid_from.tzinfo is None or self.valid_from.utcoffset() is None:
            raise TrustKeyRegistryError("trust_key_valid_from_timezone_required")
        if self.valid_until is not None and (
            self.valid_until.tzinfo is None or self.valid_until.utcoffset() is None
        ):
            raise TrustKeyRegistryError("trust_key_valid_until_timezone_required")

    def public_only(self) -> "TrustSigningKey":
        """Return a verification-safe record without private signing material."""
        return replace(self, private_key=None)

    def jwk_public(self) -> dict[str, Any]:
        """Return public-only JWK material for verification callers."""
        public_bytes = self.public_key.public_bytes(
            encoding=Encoding.Raw,
            format=PublicFormat.Raw,
        )
        jwk: dict[str, Any] = {
            "kty": "OKP",
            "crv": "Ed25519",
            "kid": self.kid,
            "alg": "EdDSA",
            "use": "sig",
            "key_ops": ["verify"],
            "x": _b64url(public_bytes),
            "skeldir_key_state": self.state,
        }
        if self.valid_until is not None:
            jwk["skeldir_valid_until"] = _utc_second(self.valid_until)
        jwk["skeldir_valid_from"] = _utc_second(self.valid_from)
        return jwk


class TrustKeyRegistry:
    """Small P8 key registry for active signing and historical verification."""

    def __init__(self, keys: tuple[TrustSigningKey, ...]) -> None:
        if not keys:
            raise TrustKeyRegistryError("trust_key_registry_empty")
        seen: set[str] = set()
        for key in keys:
            if key.kid in seen:
                raise TrustKeyRegistryError(f"duplicate_trust_key_id:{key.kid}")
            seen.add(key.kid)
        self._keys = keys

    def active_signing_key(self) -> TrustSigningKey:
        active = [
            key
            for key in self._keys
            if key.state == "active" and key.private_key is not None
        ]
        if len(active) != 1:
            raise TrustKeyRegistryError("exactly_one_active_private_signing_key_required")
        return active[0]

    def verification_key(self, kid: str) -> TrustSigningKey:
        for key in self._keys:
            if key.kid == kid:
                if key.state in {"revoked", "expired"}:
                    raise TrustKeyRegistryError(f"trust_key_not_verification_authorized:{kid}")
                return key.public_only()
        raise TrustKeyRegistryError(f"unknown_trust_signing_key:{kid}")

    def public_only(self) -> "TrustKeyRegistry":
        """Return a registry that cannot sign because private material is absent."""
        return TrustKeyRegistry(tuple(key.public_only() for key in self._keys))

    def jwks(self) -> dict[str, list[dict[str, Any]]]:
        """Return public-only JWKS output. Private material is intentionally absent."""
        return {
            "keys": [
                key.jwk_public()
                for key in self._keys
                if key.state in {"active", "verification_only"}
            ]
        }


def _utc_second(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
