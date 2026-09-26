"""B2.6-P2 Corrective XIII dedicated provider-authentication trust root.

This process is the SOLE runtime authority capable of creating
authenticated-ingress truth:

- possesses the provider verification material (tenant webhook
  secrets via the application credential for resolution, plus the
  ingress credential for persistence; no raw provider secret is
  ever persisted);
- receives the raw provider request (body + signature envelope +
  tenant API key);
- performs HMAC/signature verification (sovereign signatures lib);
- possesses the sole runtime capability to persist authenticated
  ingress (SKELDIR_PROCESS_ROLE=auth_ingress + file-mounted
  B26_P2_INGRESS_DATABASE_URL_FILE + app_ingress DB grants);
- writes authenticated evidence/state only after successful
  verification, atomically (ingress row + consequence + witness +
  evidence + terminal provenance in one transaction).

No other shipping principal can create its durable output (DB grants
deny app_user; process manifests deny every non-auth process the
credential). Crash before commit leaves fully pending state (lawful
retry completes); crash after commit leaves fully authenticated
state. Intermediate states are never dispatchable (dispatch requires
provenance=authenticated_known AND witness) and never P3-eligible.
"""

from __future__ import annotations

import base64
import hashlib
import os
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

app = FastAPI(title="Skeldir B2.6-P2 Authentication Trust Root (XIII)")


class AuthenticateRequest(BaseModel):
    api_key: str = Field(description="Tenant webhook API key (resolves tenant + secrets)")
    provider: str
    provider_event_reference: str = Field(description="Provider-native event id")
    raw_body_b64: str = Field(description="Base64 of exact raw provider body")
    signature_header: str = Field(description="Exact presented signature envelope")
    event_id: str = Field(description="Skeldir event identity for idempotency")
    auth_version: str = "v1"


class AuthenticateResponse(BaseModel):
    status: str
    provenance_status: str
    ingress_id: str
    tenant_id: str


def _require_auth_role() -> None:
    if os.getenv("SKELDIR_PROCESS_ROLE", "").strip() != "auth_ingress":
        raise HTTPException(
            status_code=500,
            detail=(
                "b26_p2_ingress_wrong_process: authentication trust root"
                " requires SKELDIR_PROCESS_ROLE=auth_ingress"
            ),
        )


@app.get("/health/live")
async def health_live() -> dict:
    _require_auth_role()
    return {"status": "ok", "role": "auth_ingress"}


@app.post("/v1/authenticate-ingress", response_model=AuthenticateResponse)
async def authenticate_ingress(body: AuthenticateRequest) -> AuthenticateResponse:
    """Verify provider signature, then atomically persist auth truth."""
    _require_auth_role()
    provider = body.provider.strip().lower()
    if provider not in ("stripe", "shopify", "woocommerce", "paypal"):
        raise HTTPException(status_code=400, detail="unsupported provider")
    try:
        raw_body = base64.b64decode(body.raw_body_b64, validate=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="raw_body_b64 invalid") from exc
    if not body.api_key.strip():
        raise HTTPException(status_code=401, detail="missing api key")
    if not body.provider_event_reference.strip():
        raise HTTPException(status_code=400, detail="provider_event_reference required")

    from app.api.webhooks import (  # noqa: PLC0415
        WEBHOOK_VERIFIERS,
        _provider_auth_method,
    )
    from app.core.tenant_context import (  # noqa: PLC0415
        get_tenant_with_webhook_secrets,
    )
    from app.db.session import (  # noqa: PLC0415
        _ingress_boundary,
        assert_api_ingress_isolation,
        get_ingress_session,
    )

    try:
        assert_api_ingress_isolation()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    entry = WEBHOOK_VERIFIERS.get(provider)
    if entry is None:
        raise HTTPException(status_code=400, detail="unsupported provider")
    secret_field, verifier = entry
    try:
        tenant_info = await get_tenant_with_webhook_secrets(body.api_key)
    except Exception:
        raise HTTPException(status_code=401, detail="unknown tenant key")
    material = tenant_info.get(secret_field)
    if not material:
        raise HTTPException(status_code=401, detail="missing verification material")
    try:
        valid = verifier(raw_body, str(material), body.signature_header)
    except Exception:
        valid = False
    if not valid:
        raise HTTPException(status_code=401, detail="invalid provider signature")

    tenant_uuid = tenant_info["tenant_id"]
    if isinstance(tenant_uuid, str):
        tenant_uuid = UUID(tenant_uuid)
    body_sha = hashlib.sha256(raw_body).hexdigest().lower()
    sig_sha = hashlib.sha256(
        body.signature_header.encode("utf-8")
    ).hexdigest().lower()
    method = _provider_auth_method(provider)
    idem = body.event_id.strip()
    ingress_id = uuid4()

    async with _ingress_boundary(), get_ingress_session(
        tenant_id=tenant_uuid
    ) as session:
        # One transaction: verified ingress row (lands pending via
        # XIII trigger) + atomic consequence/witness/evidence +
        # terminal provenance. Crash before commit leaves nothing
        # durable (pending retry); after leaves fully authenticated.
        await session.execute(
            text(
                "INSERT INTO public.webhook_ingress_identities ("
                " id, tenant_id, event_id, provider,"
                " provider_native_event_reference, idempotency_key,"
                " verified_commerce_ingress_state, event_timestamp"
                " ) VALUES ("
                " :id, :tenant, :event_id, :provider,"
                " :event_ref, :idem,"
                " 'authenticity_verified', now()"
                " )"
                " ON CONFLICT DO NOTHING"
            ),
            {
                "id": str(ingress_id),
                "tenant": str(tenant_uuid),
                "event_id": idem,
                "provider": provider,
                "event_ref": body.provider_event_reference.strip(),
                "idem": idem,
            },
        )
        # Resolve the canonical row (idempotent on retry).
        row = (
            (
                await session.execute(
                    text(
                        "SELECT i.id::text AS iid"
                        " FROM public.webhook_ingress_identities AS i"
                        " WHERE i.tenant_id = :tenant"
                        " AND i.idempotency_key = :idem"
                    ),
                    {"tenant": str(tenant_uuid), "idem": idem},
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise HTTPException(status_code=500, detail="ingress row missing")
        canonical_id = str(row["iid"])
        await session.execute(
            text(
                "SELECT public.b26_p2_authenticate_ingress_atomic("
                " :ingress, :provider, :event_ref,"
                " :body_sha, :sig_sha, :method, :version)"
            ),
            {
                "ingress": canonical_id,
                "provider": provider,
                "event_ref": body.provider_event_reference.strip(),
                "body_sha": body_sha,
                "sig_sha": sig_sha,
                "method": method,
                "version": body.auth_version or "v1",
            },
        )
    return AuthenticateResponse(
        status="authenticated",
        provenance_status="authenticated_known",
        ingress_id=canonical_id,
        tenant_id=str(tenant_uuid),
    )
