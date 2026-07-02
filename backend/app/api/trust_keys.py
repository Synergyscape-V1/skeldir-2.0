"""Narrow B2.5-P8 public verification key surface."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Header

from app.trust.jwks import default_public_jwks


router = APIRouter()


@router.get("/trust/v1/keys/jwks")
async def get_trust_jwks(
    x_correlation_id: UUID = Header(..., alias="X-Correlation-ID"),
) -> dict[str, object]:
    """Publish public TrustEnvelope verification keys only."""
    _ = x_correlation_id
    return default_public_jwks()
