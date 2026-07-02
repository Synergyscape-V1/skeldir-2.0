"""Public TrustEnvelope verification key publication for B2.5-P8."""

from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timezone
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app.trust.key_registry import TrustKeyRegistry, TrustSigningKey


class TrustJWKSError(ValueError):
    """Raised when public trust-key publication material is unsafe."""


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def _parse_utc(value: str) -> datetime:
    if not value.endswith("Z"):
        raise TrustJWKSError("jwks_timestamp_must_be_utc_z")
    return datetime.fromisoformat(value.removesuffix("Z") + "+00:00").astimezone(
        timezone.utc
    )


def _iter_text_values(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, dict):
        texts: list[str] = []
        for key, child in value.items():
            texts.extend(_iter_text_values(key))
            texts.extend(_iter_text_values(child))
        return tuple(texts)
    if isinstance(value, list):
        texts = []
        for child in value:
            texts.extend(_iter_text_values(child))
        return tuple(texts)
    return ()


def assert_jwks_public_only(jwks: dict[str, Any]) -> int:
    """Reject private, secret, seed, scalar, or env-shaped JWK material."""
    keys = jwks.get("keys")
    if not isinstance(keys, list):
        raise TrustJWKSError("jwks_keys_missing")
    forbidden = {
        "d",
        "p",
        "q",
        "dp",
        "dq",
        "qi",
        "k",
        "private_key",
        "privateKey",
        "seed",
        "secret",
        "scalar",
        "env",
        "env_var",
    }
    count = 0
    for key in keys:
        if not isinstance(key, dict):
            raise TrustJWKSError("jwks_key_not_object")
        leaked = sorted(forbidden & set(key))
        if leaked:
            raise TrustJWKSError(f"jwks_private_material_exposed:{leaked}")
        for token in ("BEGIN PRIVATE KEY", "PRIVATE KEY", "SECRET", "SKELDIR_"):
            if any(token in text for text in _iter_text_values(key)):
                raise TrustJWKSError(f"jwks_secret_token_exposed:{token}")
        count += 1
    return count


def build_jwks_response(key_registry: TrustKeyRegistry) -> dict[str, Any]:
    """Build public-only JWKS from the same registry used by verification tests."""
    jwks = key_registry.public_only().jwks()
    assert_jwks_public_only(jwks)
    return jwks


def registry_from_public_jwks(jwks: dict[str, Any]) -> TrustKeyRegistry:
    """Construct a public-only registry from JWKS material."""
    assert_jwks_public_only(jwks)
    records: list[TrustSigningKey] = []
    for key in jwks["keys"]:
        if key.get("kty") != "OKP" or key.get("crv") != "Ed25519":
            raise TrustJWKSError("jwks_key_type_unsupported")
        kid = key.get("kid")
        if not isinstance(kid, str):
            raise TrustJWKSError("jwks_kid_missing")
        public_x = key.get("x")
        if not isinstance(public_x, str):
            raise TrustJWKSError("jwks_public_x_missing")
        state = key.get("skeldir_key_state", "verification_only")
        if state not in {"active", "verification_only", "revoked", "expired"}:
            raise TrustJWKSError(f"jwks_key_state_unsupported:{state}")
        valid_from = key.get("skeldir_valid_from")
        if not isinstance(valid_from, str):
            raise TrustJWKSError("jwks_valid_from_missing")
        valid_until_raw = key.get("skeldir_valid_until")
        records.append(
            TrustSigningKey(
                kid=kid,
                algorithm="ed25519",
                public_key=Ed25519PublicKey.from_public_bytes(_b64url_decode(public_x)),
                private_key=None,
                state=state,
                valid_from=_parse_utc(valid_from),
                valid_until=(
                    _parse_utc(valid_until_raw)
                    if isinstance(valid_until_raw, str)
                    else None
                ),
            )
        )
    return TrustKeyRegistry(tuple(records))


def default_public_jwks() -> dict[str, Any]:
    """Return environment-provided public JWKS, or an empty key set."""
    raw = os.getenv("SKELDIR_TRUST_PUBLIC_JWKS_JSON")
    if not raw:
        return {"keys": []}
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise TrustJWKSError("default_public_jwks_not_object")
    assert_jwks_public_only(data)
    return data
