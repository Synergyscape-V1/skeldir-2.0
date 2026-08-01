"""Narrow B2.5-P8 public verification key surface."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Header

from app.trust.jwks import default_public_jwks
from app.trust.runtime_keys import (
    RuntimeTrustKeyConfigurationError,
    load_runtime_verification_registry,
)


router = APIRouter()


@router.get("/trust/v1/keys/jwks", openapi_extra={"security": []})
async def get_trust_jwks(
    x_correlation_id: UUID = Header(..., alias="X-Correlation-ID"),
) -> dict[str, object]:
    """Publish public TrustEnvelope verification keys only."""
    _ = x_correlation_id
    try:
        return load_runtime_verification_registry().jwks()
    except RuntimeTrustKeyConfigurationError:
        # Preserve the P8 public-key surface before deployment signing authority
        # is configured; configured deployments additionally publish the active
        # runtime public key through the same public-only representation.
        return default_public_jwks()
