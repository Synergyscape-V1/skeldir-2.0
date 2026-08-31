"""Public-API client for the separately credentialed Trust signer process."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

import httpx

from app.trust.key_registry import TrustKeyRegistry
from app.trust.signer_service import (
    SignContinuationRequest,
    SignEnvelopeRequest,
    SignExportArtifactRequest,
    execute_continuation_signing,
    execute_envelope_signing,
    execute_export_artifact_signing,
)


class TrustSignerGatewayError(RuntimeError):
    """Raised when the isolated signer cannot establish a consequence."""


def _in_process_test_mode() -> bool:
    return (
        os.getenv("TESTING") == "1"
        and os.getenv("SKELDIR_TRUST_SIGNER_FORCE_REMOTE_TEST") != "1"
    )


def assert_public_api_signer_isolation() -> None:
    """Ensure production API custody excludes signer credentials and keys."""
    if _in_process_test_mode():
        return
    for forbidden in (
        "TRUST_SIGNER_DATABASE_URL",
        "SKELDIR_TRUST_SIGNING_KEY_SEED_B64URL",
    ):
        if os.getenv(forbidden, "").strip():
            raise TrustSignerGatewayError(
                f"public_api_forbidden_signer_authority:{forbidden}"
            )


def _signer_url() -> str:
    raw = os.getenv("TRUST_SIGNER_URL", "").strip().rstrip("/")
    parsed = urlparse(raw)
    if not raw or parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise TrustSignerGatewayError("trust_signer_url_required")
    if parsed.scheme != "https" and parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise TrustSignerGatewayError("trust_signer_transport_tls_required")
    return raw


def _signer_secret() -> str:
    secret = os.getenv("TRUST_SIGNER_SHARED_SECRET", "")
    if len(secret.encode("utf-8")) < 32:
        raise TrustSignerGatewayError("trust_signer_shared_secret_too_short")
    return secret


async def _post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    assert_public_api_signer_isolation()
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                _signer_url() + path,
                json=payload,
                headers={"Authorization": f"Bearer {_signer_secret()}"},
            )
        response.raise_for_status()
        decoded = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise TrustSignerGatewayError("trust_signer_request_failed") from exc
    if not isinstance(decoded, dict):
        raise TrustSignerGatewayError("trust_signer_response_invalid")
    return decoded


async def request_trust_envelope_signature(
    *,
    tenant_id: UUID,
    audit_ref: str,
    attempt_id: UUID,
    unsigned_envelope: dict[str, Any],
    test_signing_registry: TrustKeyRegistry | None = None,
) -> dict[str, Any]:
    request = SignEnvelopeRequest(
        tenant_id=tenant_id,
        audit_ref=audit_ref,
        attempt_id=attempt_id,
        unsigned_envelope=unsigned_envelope,
    )
    if _in_process_test_mode():
        return await execute_envelope_signing(
            request,
            signing_registry=test_signing_registry,
        )
    return await _post(
        "/internal/trust/v1/sign-envelope",
        request.model_dump(mode="json"),
    )


async def request_trust_export_artifact_signature(
    *,
    tenant_id: UUID,
    attempt_id: UUID,
    unsigned_artifact: dict[str, Any],
    test_signing_registry: TrustKeyRegistry | None = None,
) -> dict[str, Any]:
    request = SignExportArtifactRequest(
        tenant_id=tenant_id,
        attempt_id=attempt_id,
        unsigned_artifact=unsigned_artifact,
    )
    if _in_process_test_mode():
        return await execute_export_artifact_signing(
            request,
            signing_registry=test_signing_registry,
        )
    return await _post(
        "/internal/trust/v1/sign-export-artifact",
        request.model_dump(mode="json"),
    )


async def request_trust_continuation_signature(
    *,
    binding_hash: str,
    next_position: int,
    total_accepted: int,
    expires_at: datetime,
    test_signing_registry: TrustKeyRegistry | None = None,
) -> str:
    request = SignContinuationRequest(
        binding_hash=binding_hash,
        next_position=next_position,
        total_accepted=total_accepted,
        expires_at=expires_at,
    )
    if _in_process_test_mode():
        return await execute_continuation_signing(
            request,
            signing_registry=test_signing_registry,
        )
    decoded = await _post(
        "/internal/trust/v1/sign-continuation",
        request.model_dump(mode="json"),
    )
    token = decoded.get("continuation_token")
    if not isinstance(token, str):
        raise TrustSignerGatewayError("trust_signer_continuation_response_invalid")
    return token
