"""Credential-isolated Trust signer service.

This process is the only production runtime that receives both the Ed25519
private key and ``app_trust_signer`` DSN.  It never receives the issuer or
migration DSNs.  The public API can request a real consequence over an already
durable, tenant-bound attempt; it cannot directly author signer evidence.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import hmac
import os
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.trust.audit import (
    assert_durable_export_signing_request,
    authorize_durable_trust_signing_request,
    record_trust_export_artifact_issued,
    record_trust_signature_consequence,
)
from app.trust.export_artifact import sign_export_artifact
from app.trust.key_registry import TrustKeyRegistry
from app.trust.query_continuation import issue_trust_query_continuation
from app.trust.runtime_keys import load_runtime_signing_registry
from app.trust.signer_session import trust_signer_database_url
from app.trust.signing import sign_durable_trust_authorization


class SignEnvelopeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: UUID
    audit_ref: str = Field(min_length=1, max_length=512)
    attempt_id: UUID
    unsigned_envelope: dict[str, Any]


class SignExportArtifactRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: UUID
    attempt_id: UUID
    unsigned_artifact: dict[str, Any]


class SignContinuationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    binding_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    next_position: int
    total_accepted: int
    expires_at: datetime


def assert_signer_process_custody() -> None:
    """Fail startup if issuer/migration authority leaked into this process."""
    trust_signer_database_url()
    if not os.getenv("SKELDIR_TRUST_SIGNING_KEY_SEED_B64URL", "").strip():
        raise RuntimeError("trust_signer_private_key_required")
    if os.getenv("TESTING") == "1":
        return
    for forbidden in ("TRUST_ISSUANCE_DATABASE_URL", "MIGRATION_DATABASE_URL"):
        if os.getenv(forbidden, "").strip():
            raise RuntimeError(f"trust_signer_forbidden_authority:{forbidden}")
    secret = os.getenv("TRUST_SIGNER_SHARED_SECRET", "")
    if len(secret.encode("utf-8")) < 32:
        raise RuntimeError("trust_signer_shared_secret_too_short")


def _expected_shared_secret() -> str:
    secret = os.getenv("TRUST_SIGNER_SHARED_SECRET", "")
    if len(secret.encode("utf-8")) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Signer authentication unavailable.",
        )
    return secret


async def require_signer_client(
    authorization: str | None = Header(default=None),
) -> None:
    expected = _expected_shared_secret()
    supplied = ""
    if authorization and authorization.startswith("Bearer "):
        supplied = authorization.removeprefix("Bearer ")
    if not hmac.compare_digest(supplied, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Signer client authentication failed.",
        )


async def execute_envelope_signing(
    request: SignEnvelopeRequest,
    *,
    signing_registry: TrustKeyRegistry | None = None,
) -> dict[str, Any]:
    """Validate durable authority, sign once, and persist before returning."""
    authorization = await authorize_durable_trust_signing_request(
        tenant_id=request.tenant_id,
        audit_ref=request.audit_ref,
        attempt_id=request.attempt_id,
        unsigned_envelope=request.unsigned_envelope,
    )
    registry = signing_registry or load_runtime_signing_registry()
    consequence = await asyncio.to_thread(
        sign_durable_trust_authorization,
        authorization,
        key_registry=registry,
    )
    return await record_trust_signature_consequence(consequence)


async def execute_export_artifact_signing(
    request: SignExportArtifactRequest,
    *,
    signing_registry: TrustKeyRegistry | None = None,
) -> dict[str, Any]:
    """Sign and retain the outer wrapper inside signer custody."""
    await assert_durable_export_signing_request(
        tenant_id=request.tenant_id,
        attempt_id=request.attempt_id,
        unsigned_artifact=request.unsigned_artifact,
    )
    registry = signing_registry or load_runtime_signing_registry()
    artifact = await asyncio.to_thread(
        sign_export_artifact,
        request.unsigned_artifact,
        key_registry=registry,
    )
    await record_trust_export_artifact_issued(
        tenant_id=request.tenant_id,
        attempt_id=request.attempt_id,
        artifact=artifact,
        key_registry=registry,
    )
    return artifact


async def execute_continuation_signing(
    request: SignContinuationRequest,
    *,
    signing_registry: TrustKeyRegistry | None = None,
) -> str:
    """Keep the Trust private key out of the public API for cursor signing."""
    registry = signing_registry or load_runtime_signing_registry()
    return await asyncio.to_thread(
        issue_trust_query_continuation,
        key_registry=registry,
        binding_hash=request.binding_hash,
        next_position=request.next_position,
        total_accepted=request.total_accepted,
        expires_at=request.expires_at,
    )


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    assert_signer_process_custody()
    yield


app = FastAPI(
    title="Skeldir Trust Signer",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=_lifespan,
)


@app.get("/health/live", include_in_schema=False)
async def health_live() -> dict[str, str]:
    return {"status": "alive"}


@app.post(
    "/internal/trust/v1/sign-envelope", dependencies=[Depends(require_signer_client)]
)
async def sign_envelope(request: SignEnvelopeRequest) -> dict[str, Any]:
    return await execute_envelope_signing(request)


@app.post(
    "/internal/trust/v1/sign-export-artifact",
    dependencies=[Depends(require_signer_client)],
)
async def sign_export(request: SignExportArtifactRequest) -> dict[str, Any]:
    return await execute_export_artifact_signing(request)


@app.post(
    "/internal/trust/v1/sign-continuation",
    dependencies=[Depends(require_signer_client)],
)
async def sign_continuation(request: SignContinuationRequest) -> dict[str, str]:
    return {"continuation_token": await execute_continuation_signing(request)}
