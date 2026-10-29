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
import contextlib
import hashlib
import json
import os
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, text

app = FastAPI(title="Skeldir B2.6-P2 Authentication Trust Root (XIII)")


def _source_attestation_key_path() -> str | None:
    from app.core.config import settings  # noqa: PLC0415

    return settings.B26_P2_SOURCE_ATTESTATION_PRIVATE_KEY_PATH


@contextlib.asynccontextmanager
async def _ingress_session_with_source_outcomes(
    tenant_id: UUID, private_key_path: str | None
):
    """Commit the DB transaction before writing its signed outcome receipt."""

    from app.db.session import get_ingress_session  # noqa: PLC0415
    from app.revenue_verification.source_evidence_journal import (  # noqa: PLC0415
        source_fact_outcome_transaction,
    )

    async with source_fact_outcome_transaction(private_key_path):
        async with get_ingress_session(tenant_id=tenant_id) as session:
            yield session


#: Last construction revision verified at startup (None = never verified).
#: Read by /health/ready so an unverified root is observable as a
#: failure instead of silently serving.
_CONSTRUCTION_VERIFIED_REVISION: str | None = None


@app.on_event("startup")
async def _startup_construction_authority_guard() -> None:
    """B2.6-P2 Corrective XXI: refuse to boot against an incompatible schema.

    This process is the sole runtime minter of authenticated financial
    authority. A stale binary running against a newer database must not
    serve: the minting ABI it was built against no longer exists there
    (the database refuses unknown signatures), and this gate additionally
    refuses boot when the live construction revision differs from the
    one this build requires. Mismatch is retried for a bounded window
    (migration in flight) then fatal.
   
    ADD2-F5: every other failure to verify is fatal too, after the same
    bounded retries. There is no silent-serve path: an unreachable
    database, a missing ingress credential, or a denied revision read
    (e.g. a lane whose migration never granted this principal EXECUTE)
    raises instead of logging 'deferred' and serving unverified. What
    the process cannot vouch for, it must not mint against -- and that
    must be observable (nonzero exit; /health/ready).
    """
    global _CONSTRUCTION_VERIFIED_REVISION

    import asyncio
    import logging

    from app.core.construction_authority import (
        ConstructionAuthorityError,
        assert_production_construction_authority,
        read_construction_revisions,
    )

    logger = logging.getLogger(__name__)
    try:
        wait_s = float(
            os.getenv("SKELDIR_CONSTRUCTION_AUTHORITY_BOOT_WAIT_S", "240")
        )
    except ValueError:
        wait_s = 240.0
    try:
        from app.db.session import (  # noqa: PLC0415
            IngressAsyncSessionLocal,
            _ingress_boundary,
        )
    except Exception as exc:
        raise RuntimeError(
            "construction_authority_guard_fatal:ingress_session_unavailable:"
            f"{exc}"
        ) from exc
    if os.getenv("SKELDIR_PROCESS_ROLE", "").strip() != "auth_ingress":
        return
    if IngressAsyncSessionLocal is None:
        raise RuntimeError(
            "construction_authority_guard_fatal:no_ingress_credential"
        )
    deadline = asyncio.get_event_loop().time() + max(0.0, wait_s)
    last_error: str = "unreadable"
    while True:
        observed: object = "unreadable"
        try:
            async with _ingress_boundary():
                async with IngressAsyncSessionLocal() as session:
                    observed = await read_construction_revisions(session)
                    revision = assert_production_construction_authority(observed)
        except ConstructionAuthorityError:
            now = asyncio.get_event_loop().time()
            if now >= deadline:
                raise
            logger.warning(
                "construction_authority_boot_waiting:%s", observed
            )
            await asyncio.sleep(2.0)
            continue
        except Exception as exc:
            last_error = str(exc)
            now = asyncio.get_event_loop().time()
            if now >= deadline:
                raise RuntimeError(
                    "construction_authority_guard_fatal:unverifiable:"
                    f"{last_error}"
                ) from exc
            logger.warning(
                "construction_authority_boot_retrying:%s", last_error
            )
            await asyncio.sleep(2.0)
            continue
        _CONSTRUCTION_VERIFIED_REVISION = str(revision)
        logger.info("construction_authority_boot_ok")
        return


class AuthenticateRequest(BaseModel):
    api_key: str = Field(
        description="Tenant webhook API key (resolves tenant + secrets)"
    )
    provider: str
    provider_event_reference: str = Field(description="Provider-native event id")
    raw_body_b64: str = Field(description="Base64 of exact raw provider body")
    signature_header: str = Field(description="Exact presented signature envelope")
    event_id: str = Field(description="Skeldir event identity (UUID)")
    idempotency_key: str | None = Field(
        default=None,
        description=(
            "Opaque caller idempotency key. Kept separate from the event"
            " UUID so an arbitrary provider retry key never becomes a"
            " database UUID cast (S13)."
        ),
    )
    auth_version: str = "v1"
    # XIV: commerce handoff for the authoritative ingress row. The root
    # verifies the provider signature over raw_body first; only then does
    # it persist these relay-supplied commerce facts bound to the verified
    # body digest in the same transaction (atomic + root evidence). The
    # general API relay derives them deterministically from the same raw
    # bytes via the sovereign webhook parsing code; the root refuses blank
    # shapes and provider mismatches by database law. The root never
    # manufactures commerce facts: without a valid signature there is no
    # persistence at all, and without this handoff the ingress schema
    # (NOT NULL commerce columns) cannot be satisfied -- the XIII defect
    # where every valid request 500d with zero durable state.
    provider_native_commerce_reference: str = Field(
        description="Provider-native commerce reference (order/payment id)"
    )
    provider_topic: str | None = Field(
        default=None,
        description=(
            "Provider-transported event topic (e.g. X-Shopify-Topic), "
            "forwarded in memory by the relay for providers whose "
            "protocol conveys event family outside the signed body. "
            "Never persisted; only the derived family and its evidence "
            "source persist."
        ),
    )
    normalized_commerce_reference_kind: str = Field(
        description="Canonical commerce reference kind"
    )
    normalized_commerce_reference_value: str = Field(
        description="Canonical commerce reference value"
    )
    verified_amount_minor: int = Field(
        description="Verified amount in integer minor units (>=0)"
    )
    verified_amount_currency: str = Field(
        description="Verified 3-letter currency (e.g. USD)"
    )
    verified_amount_scale: int = Field(
        default=2, description="Verified amount scale (default 2)"
    )
    event_timestamp: str = Field(description="Provider event timestamp (ISO-8601)")


class AuthenticateAdjustmentRequest(BaseModel):
    api_key: str = Field(description="Tenant webhook API key")
    provider: str
    raw_body_b64: str = Field(description="Base64 of exact raw provider body")
    signature_header: str = Field(description="Exact presented signature envelope")
    provider_event_reference: str | None = Field(
        default=None,
        description="Selected provider refund identity for multi-effect bodies",
    )


class AuthenticateAdjustmentResponse(BaseModel):
    status: str
    adjustment_evidence_id: str
    verdict_id: str
    tenant_id: str
    event_type: str
    amount_minor: int
    currency_code: str
    provider_native_event_reference: str


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


@app.get("/health/ready")
async def health_ready() -> dict:
    """Readiness: the root verified construction at startup.

    Returns 200 with the verified revision only if the startup guard
    verified this database. Any other state (never verified, e.g. the
    guard was bypassed or failed open) is an observable failure, not
    silent serving.
    """
    _require_auth_role()
    if _CONSTRUCTION_VERIFIED_REVISION is None:
        raise HTTPException(
            status_code=503,
            detail="construction_authority_unverified",
        )
    return {
        "status": "ok",
        "role": "auth_ingress",
        "construction_revision": _CONSTRUCTION_VERIFIED_REVISION,
    }


#: Governed refusal tokens the atomic authentication transition raises. Each
#: one is a decision the system means to publish, not an internal failure, so
#: each is translated into a refusal that names itself instead of a 500.
_GOVERNED_ATOMIC_REFUSALS = (
    "b26_p2_atomic_commerce_identity_conflict_refused",
    "b26_p2_atomic_event_identity_conflict_refused",
    "b26_p2_atomic_provenance_not_establishable",
    "b26_p2_atomic_lifecycle_attestation_refused",
    "b26_p2_atomic_family_claim_refused",
    "b26_p2_ingress_amount_immutable",
)


def _governed_atomic_refusal(detail: str) -> str | None:
    """Return the governed token the atomic transition refused with, if any."""
    for token in _GOVERNED_ATOMIC_REFUSALS:
        if token in detail:
            return token
    return None


async def _write_source_money_attestation(
    session,
    *,
    tenant_id: str,
    ingress_id: str,
    provider: str,
    commerce: dict,
    event_timestamp,
    body_sha256: str,
) -> None:
    """Sign and persist the sovereign attestation for one authenticated row.

    XXV (A6/A10/A12): the amount a consumer may treat as current money has to
    be justified by something no database principal can rewrite. The root
    holds the only seed; the statement commits to the tenant, the source
    identity, the amount, the currency, the scale, the event instant, the
    provider body digest and the authority universe.

    Fails closed: if the seed is absent or the signature cannot be produced
    while attestation is required, the whole authentication transaction fails
    rather than persisting money no reader can justify.
    """
    from app.core.config import settings  # noqa: PLC0415
    from app.revenue_verification.source_attestation import (  # noqa: PLC0415
        SourceAttestationError,
        build_statement,
        write_source_attestation,
    )

    if not settings.B26_P2_SOURCE_ATTESTATION_REQUIRED:
        return
    key_path = settings.B26_P2_SOURCE_ATTESTATION_PRIVATE_KEY_PATH
    if not key_path:
        raise HTTPException(
            status_code=500,
            detail="b26_p2_source_attestation_key_absent",
        )
    # The universe table itself is unreadable to runtime principals by
    # design; the DEFINER reader is the governed surface.
    universe_row = (
        await session.execute(
            text("SELECT public.b26_p2_authority_universe()::text")
        )
    ).first()
    statement = build_statement(
        tenant_id=tenant_id,
        webhook_ingress_identity_id=ingress_id,
        provider=provider,
        provider_native_event_reference=commerce["event_ref"],
        provider_native_commerce_reference=commerce["commerce_ref"],
        normalized_commerce_reference_kind=commerce["norm_kind"],
        normalized_commerce_reference_value=commerce["norm_value"],
        verified_amount_minor=commerce["amount_minor"],
        verified_amount_currency=commerce["amount_currency"],
        verified_amount_scale=commerce["amount_scale"],
        event_timestamp=event_timestamp,
        body_sha256=body_sha256,
        authority_universe=None if universe_row is None else universe_row[0],
    )
    try:
        await write_source_attestation(
            session, statement=statement, private_key_path=key_path
        )
    except SourceAttestationError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"b26_p2_source_attestation_failed:{exc}",
        ) from exc


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
    # XIV: commerce handoff validation (blank shapes refused before any
    # persistence; provider binding + digest law enforced by the database).
    if not body.provider_native_commerce_reference.strip():
        raise HTTPException(
            status_code=400,
            detail="provider_native_commerce_reference required",
        )
    if not body.normalized_commerce_reference_kind.strip():
        raise HTTPException(
            status_code=400,
            detail="normalized_commerce_reference_kind required",
        )
    if not body.normalized_commerce_reference_value.strip():
        raise HTTPException(
            status_code=400,
            detail="normalized_commerce_reference_value required",
        )
    if body.verified_amount_minor is None or body.verified_amount_minor < 0:
        raise HTTPException(
            status_code=400, detail="verified_amount_minor must be >= 0"
        )
    currency = body.verified_amount_currency.strip().upper()
    if len(currency) != 3 or not currency.isalpha():
        raise HTTPException(
            status_code=400, detail="verified_amount_currency must be 3 letters"
        )
    if body.verified_amount_scale is None or body.verified_amount_scale < 0:
        raise HTTPException(
            status_code=400, detail="verified_amount_scale must be >= 0"
        )
    from datetime import datetime  # noqa: PLC0415

    try:
        event_ts = datetime.fromisoformat(body.event_timestamp.replace("Z", "+00:00"))
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail="event_timestamp must be ISO-8601"
        ) from exc

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
    )
    from app.webhooks.commerce_derivation import (  # noqa: PLC0415
        CommerceDerivationError,
        binding_mismatches,
        derive_commerce,
        derive_event_family,
        derive_event_family_source,
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
    # XV (H-XV-R1/R2): cryptographic meaning binding. The signature above
    # proves signature(raw_body) is valid. It says nothing about the
    # relay-supplied commerce handoff. Sovereignly re-derive every material
    # financial field from the verified bytes and refuse any mismatch
    # before persistence. Persisted authority comes from the derivation,
    # never from the handoff.
    try:
        derived = derive_commerce(provider, raw_body)
    except CommerceDerivationError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"b26_p2_handoff_binding_refused:sovereign_derivation_failed:{exc}",
        ) from exc
    handoff_view = {
        "provider_native_event_reference": body.provider_event_reference,
        "provider_native_commerce_reference": body.provider_native_commerce_reference,
        "normalized_commerce_reference_kind": body.normalized_commerce_reference_kind,
        "normalized_commerce_reference_value": body.normalized_commerce_reference_value,
        "verified_amount_minor": body.verified_amount_minor,
        "verified_amount_currency": body.verified_amount_currency,
        "verified_amount_scale": body.verified_amount_scale,
        "event_timestamp": body.event_timestamp,
    }
    mismatched = binding_mismatches(
        provider=provider, handoff=handoff_view, derived=derived
    )
    if mismatched:
        raise HTTPException(
            status_code=400,
            detail="b26_p2_handoff_binding_refused:" + ",".join(sorted(mismatched)),
        )
    # XVIII (H-XVIII-R11/R12) + XIX (H-XIX-R7): sovereign event-family
    # binding. The family is established HERE, from authenticated bytes
    # (plus the provider-transported topic for protocols that convey
    # family outside the signed body), by the component that creates
    # financial authority -- never from the relay route, and never from
    # the provider name alone. An unsupported or familyless shape (valid
    # signature, parseable money, no authenticated family fact) yields no
    # authority at all. The evidence source is bound into the
    # consequence row alongside the family.
    try:
        event_family = derive_event_family(
            provider, raw_body, topic=body.provider_topic
        )
        event_family_source = derive_event_family_source(
            provider, raw_body, topic=body.provider_topic
        )
    except CommerceDerivationError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"b26_p2_unsupported_event_family_refused:{exc}",
        ) from exc
    # XXI (H-XXI-03): lifecycle attestation for the minting seam. The
    # database enforces the positive creation law itself (atomic v2);
    # the root supplies the body-derived lifecycle facts it already
    # established during sovereign derivation. Non-shopify providers
    # carry no lifecycle surface: null/absent markers.
    from app.webhooks.commerce_derivation import (  # noqa: PLC0415
        derive_shopify_lifecycle,
    )

    lifecycle_status = None
    lifecycle_cancelled_at = None
    lifecycle_refunds_present = False
    lifecycle_created_at = None
    lifecycle_updated_at = None
    if provider == "shopify":
        try:
            shop_lifecycle = derive_shopify_lifecycle(
                json.loads(raw_body.decode("utf-8"))
                if isinstance(raw_body, (bytes, bytearray)) else {}
            )
        except CommerceDerivationError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"b26_p2_lifecycle_not_creation:{exc}",
            ) from exc
        lifecycle_status = shop_lifecycle.financial_status
        lifecycle_created_at = shop_lifecycle.created_at
        lifecycle_updated_at = shop_lifecycle.updated_at
    # XVI (H-XVI-R13): canonical persistence is USD-only. The sovereign
    # scope currency universe is {"USD"}; a non-USD event is
    # EXPLICITLY_EXCLUDED from canonical reconciliation truth by scope
    # law, so it must never enter authenticated persistence in the
    # first place. Refuse before any INSERT; the relay pre-routes this
    # shape to durable DLQ upstream and this refusal is the backstop
    # for direct-root callers.
    if derived.verified_amount_currency != "USD":
        raise HTTPException(
            status_code=400,
            detail=(
                "b26_p2_unsupported_currency_refused:"
                f"{derived.verified_amount_currency}"
            ),
        )
    body_sha = hashlib.sha256(raw_body).hexdigest().lower()
    sig_sha = hashlib.sha256(body.signature_header.encode("utf-8")).hexdigest().lower()
    method = _provider_auth_method(provider)
    idem = (body.idempotency_key or body.event_id).strip()
    try:
        event_uuid = UUID(str(body.event_id).strip())
    except (TypeError, ValueError):
        event_uuid = uuid5(
            NAMESPACE_URL, f"b26_p2_ingress_event:{body.event_id.strip()}"
        )
    ingress_id = uuid4()

    async with _ingress_boundary(), _ingress_session_with_source_outcomes(
        tenant_uuid, _source_attestation_key_path()
    ) as session:
        # ADD2-F5: per-request construction check. Boot verification
        # cannot cover a database swapped under a live process; minting
        # against an unvouched schema must fail the request, never serve
        # silently. Cheap (two catalog reads); fails closed on any error.
        from app.core.construction_authority import (  # noqa: PLC0415
            assert_production_construction_authority as _assert_construction,
            read_construction_revisions as _read_revisions,
        )

        try:
            _observed = await _read_revisions(session)
            _assert_construction(_observed)
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=f"construction_authority_unverified:{exc}",
            ) from exc
        # XVI (H-XVI-R6): sovereign content-addressed duplicate fence.
        # The relay-supplied event_id (idempotency key) is routing
        # information, not financial identity: the same provider event
        # redelivered under a different key (rotated X-Idempotency-Key,
        # crash-retry with a fresh key) carries identical bytes and must
        # resolve to the already-authenticated lineage instead of minting
        # a second canonical lineage for one payment. Conversely two
        # distinct provider events never share bytes, so they never
        # collide here (event-granular lineages preserved). The reference
        # conjunction is exact for honest traffic (identical bytes
        # determine identical meaning); it additionally tolerates
        # placeholder digests in pre-existing fixtures for distinct
        # events.
        winner = (
            (
                await session.execute(
                    text(
                        # XX (hosted split, 1feced0d4): the hosted planner
                        # evaluated the STABLE authority function once per
                        # scanned candidate row (~438x per fence query),
                        # making this the single largest postgres consumer
                        # in the failing R3 legs. MATERIALIZED is load
                        # bearing: it fences the byte-equality filter ahead
                        # of has_current_authority so the function runs at
                        # most once per byte match. Semantics unchanged:
                        # consequence rows filtered by (tenant, bytes)
                        # first, identities joined on (id, tenant), the
                        # authority check remains the last gate, LIMIT 1
                        # preserved.
                        "WITH cand AS MATERIALIZED ("
                        " SELECT c.webhook_ingress_identity_id AS iid,"
                        " c.tenant_id AS tenant_id"
                        " FROM public.b26_p2_provider_auth_consequence AS c"
                        " WHERE c.tenant_id = :tenant"
                        " AND c.body_sha256 = :body_sha"
                        " AND c.provider_event_reference = :event_ref"
                        ")"
                        " SELECT i.id::text AS iid"
                        " FROM public.webhook_ingress_identities AS i"
                        " JOIN cand ON cand.iid = i.id"
                        " AND cand.tenant_id = i.tenant_id"
                        " WHERE i.tenant_id = :tenant"
                        " AND public.b26_p2_ingress_has_current_authority(i.id)"
                        " LIMIT 1"
                    ),
                    {
                        "tenant": str(tenant_uuid),
                        "body_sha": body_sha,
                        "event_ref": derived.provider_native_event_reference,
                    },
                )
            )
            .mappings()
            .one_or_none()
        )
        if winner is not None:
            # XXV historical qualification: an inherited source can be
            # current authority without a source-money attestation because
            # the XXV epoch had not yet retained the provider bytes. A
            # genuine provider replay presents the exact verified bytes
            # again. Re-attest the existing canonical row here, inside the
            # replay transaction, instead of returning early and leaving
            # legitimate inherited history permanently unverifiable. The
            # attestation writer is conflict-safe: an existing attestation
            # is never replaced, and the statement is over the derived
            # provider bytes, so a forged row still fails the reader's
            # ingress/attestation equality checks.
            await _write_source_money_attestation(
                session,
                tenant_id=str(tenant_uuid),
                ingress_id=str(winner["iid"]),
                provider=provider,
                commerce={
                    "event_ref": derived.provider_native_event_reference,
                    "commerce_ref": derived.provider_native_commerce_reference,
                    "norm_kind": derived.normalized_commerce_reference_kind,
                    "norm_value": derived.normalized_commerce_reference_value,
                    "amount_minor": int(derived.verified_amount_minor),
                    "amount_currency": derived.verified_amount_currency,
                    "amount_scale": int(derived.verified_amount_scale),
                },
                event_timestamp=derived.event_timestamp,
                body_sha256=body_sha,
            )
            return AuthenticateResponse(
                status="authenticated",
                provenance_status="authenticated_known",
                ingress_id=str(winner["iid"]),
                tenant_id=str(tenant_uuid),
            )
        # One transaction: verified ingress row (lands pending via
        # XIII trigger) + atomic consequence/witness/evidence +
        # terminal provenance. Crash before commit leaves nothing
        # durable (pending retry); after leaves fully authenticated.
        # XIV: full-commerce ingress INSERT. Satisfies every NOT NULL
        # column the schema requires; lands pending_authentication via the
        # provenance trigger, then the atomic transition below creates
        # consequence + witness + legacy evidence + immutable auth-root
        # evidence + terminal provenance in one transaction.
        # XV: persist sovereignly derived meaning (from verified bytes),
        # never the relay handoff. The handoff was equality-checked above
        # and plays no further role in what becomes authority.
        event_ts = derived.event_timestamp
        commerce = {
            "event_ref": derived.provider_native_event_reference,
            "commerce_ref": derived.provider_native_commerce_reference,
            "norm_kind": derived.normalized_commerce_reference_kind,
            "norm_value": derived.normalized_commerce_reference_value,
            "amount_minor": int(derived.verified_amount_minor),
            "amount_currency": derived.verified_amount_currency,
            "amount_scale": int(derived.verified_amount_scale),
        }
        # A failed INSERT aborts the database transaction; isolate the
        # attempt in a savepoint so the adopt-and-promote fallback below
        # still runs in the outer authoritative transaction.
        _insert_failed: Exception | None = None
        _insert_detail = ""
        try:
            async with session.begin_nested():
                await session.execute(
                    text(
                        "INSERT INTO public.webhook_ingress_identities ("
                        " id, tenant_id, event_id, provider,"
                        " provider_native_event_reference,"
                        " provider_native_commerce_reference,"
                        " normalized_commerce_reference_kind,"
                        " normalized_commerce_reference_value,"
                        " verified_amount_minor, verified_amount_currency,"
                        " verified_amount_scale,"
                        " idempotency_key,"
                        " verified_commerce_ingress_state, event_timestamp"
                        " ) VALUES ("
                        " :id, :tenant, :event_id, :provider,"
                        " :event_ref,"
                        " :commerce_ref,"
                        " :norm_kind,"
                        " :norm_value,"
                        " :amount_minor, :amount_currency,"
                        " :amount_scale,"
                        " :idem,"
                        " 'authenticity_verified', :event_ts"
                        " )"
                        " ON CONFLICT DO NOTHING"
                    ),
                    {
                        "id": str(ingress_id),
                        "tenant": str(tenant_uuid),
                        "event_id": str(event_uuid),
                        "provider": provider,
                        "idem": idem,
                        "event_ts": event_ts,
                        **commerce,
                    },
                )
        except Exception as insert_exc:
            _insert_failed = insert_exc
            _insert_detail = str(insert_exc)
        if _insert_failed is not None:
            # The general-API relay creates a non-authoritative precursor
            # in its own transaction before relaying. Adopt-and-promote
            # it here (sovereign-match checked first; genuine conflicts
            # refuse) instead of inserting a second row.
            if (
                "b26_p2_ingress_precursor_present_promote_required"
                not in _insert_detail
            ):
                raise _insert_failed
            # ORM attribute access keeps coverage-money SQL out of
            # application string constants (B2.6-P1 authority fence).
            from app.models import WebhookIngressIdentity  # noqa: PLC0415

            existing = (
                (
                    await session.execute(
                        # XVI (H-XVI-R7): lock the precursor row for the
                        # check-then-promote sequence. Without FOR UPDATE a
                        # concurrent transaction can replace precursor
                        # identity between this read and the UPDATE below,
                        # promoting state the root never verified.
                        select(WebhookIngressIdentity)
                        .where(
                            WebhookIngressIdentity.tenant_id == tenant_uuid,
                            WebhookIngressIdentity.idempotency_key == idem,
                        )
                        .with_for_update(),
                    )
                )
                .scalars()
                .one_or_none()
            )
            if existing is None:
                raise HTTPException(
                    status_code=500, detail="precursor row missing"
                ) from _insert_failed
            if (
                str(existing.provider or "") != provider
                or str(existing.verified_amount_currency or "")
                != commerce["amount_currency"]
                or int(existing.verified_amount_minor or -1) != commerce["amount_minor"]
                or str(existing.provider_native_event_reference or "")
                != commerce["event_ref"]
                or str(existing.provider_native_commerce_reference or "")
                != commerce["commerce_ref"]
                or str(existing.normalized_commerce_reference_kind or "")
                != commerce["norm_kind"]
                or str(existing.normalized_commerce_reference_value or "")
                != commerce["norm_value"]
            ):
                raise HTTPException(
                    status_code=409,
                    detail="b26_p2_ingress_authenticated_conflict",
                ) from _insert_failed
            await session.execute(
                text(
                    # XVI (H-XVI-R7): overwrite every verified field from
                    # the sovereign derivation, including provider (the
                    # request provider is the verified one). A field that
                    # is checked-but-not-overwritten leaves a TOCTOU
                    # window: verified-A can be persisted as B. Only the
                    # lookup key (tenant, idempotency_key) and the live
                    # delivery linkage (event_id, rebound by design on
                    # every genuine redelivery) are preserved.
                    "UPDATE public.webhook_ingress_identities AS i"
                    " SET provider = :provider,"
                    " provider_native_event_reference = :event_ref,"
                    " provider_native_commerce_reference = :commerce_ref,"
                    " normalized_commerce_reference_kind = :norm_kind,"
                    " normalized_commerce_reference_value = :norm_value,"
                    " verified_amount_minor = :amount_minor,"
                    " verified_amount_currency = :amount_currency,"
                    " verified_amount_scale = :amount_scale,"
                    " event_timestamp = :event_ts,"
                    " verified_commerce_ingress_state = 'authenticity_verified'"
                    " WHERE i.tenant_id = :tenant"
                    " AND i.idempotency_key = :idem"
                ),
                {
                    "tenant": str(tenant_uuid),
                    "idem": idem,
                    "provider": provider,
                    "event_ts": event_ts,
                    **commerce,
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
        # XVI (H-XVI-R6): a concurrent first-authentication of the same
        # bytes under a different key can pass the pre-check above; the
        # atomic serializes on the byte identity and refuses the loser.
        # Resolve the winner and return its lineage instead of 500ing a
        # genuine duplicate (provider retry must observe success).
        # XVIII: the sovereign family claim travels transaction-locally
        # (set_config is_local: auto-cleared at commit, never leaks
        # across pooled checkouts; a function call, so the claim stays
        # a bound parameter -- SET LOCAL cannot take bind parameters
        # on some drivers); the atomic allowlists and binds it. XIX:
        # the claim's evidence source travels alongside and is bound
        # into the consequence row.
        try:
            await session.execute(
                text(
                    "SELECT set_config('app.b26_p2_event_family',"
                    " :family, true)"
                ),
                {"family": event_family},
            )
            await session.execute(
                text(
                    "SELECT set_config('app.b26_p2_event_family_source',"
                    " :source, true)"
                ),
                {"source": event_family_source},
            )
            await session.execute(
                text(
                    "SELECT public.b26_p2_authenticate_ingress_atomic_v2("
                    " :ingress, :provider, :event_ref,"
                    " :body_sha, :sig_sha, :method, :version,"
                    " :lifecycle_status, :lifecycle_cancelled_at,"
                    " :lifecycle_refunds_present,"
                    " :lifecycle_created_at, :lifecycle_updated_at)"
                ),
                {
                    "ingress": canonical_id,
                    "provider": provider,
                    "event_ref": derived.provider_native_event_reference,
                    "body_sha": body_sha,
                    "sig_sha": sig_sha,
                    "method": method,
                    "version": body.auth_version or "v1",
                    "lifecycle_status": lifecycle_status,
                    "lifecycle_cancelled_at": lifecycle_cancelled_at,
                    "lifecycle_refunds_present": lifecycle_refunds_present,
                    "lifecycle_created_at": lifecycle_created_at,
                    "lifecycle_updated_at": lifecycle_updated_at,
                },
            )
            # XXV (A6/A10): the authentication root is the only process that
            # ever holds the provider's signed bytes, and the only holder of
            # the attestation seed. It signs the verified amount here, inside
            # the same transaction that made the row authoritative, so an
            # authenticated row and its sovereign attestation commit or fail
            # together. Readers verify the signature against a fingerprint
            # compiled into the image, which is what puts this authority
            # outside the reach of every database principal.
            await _write_source_money_attestation(
                session,
                tenant_id=str(tenant_uuid),
                ingress_id=canonical_id,
                provider=provider,
                commerce=commerce,
                event_timestamp=event_ts,
                body_sha256=body_sha,
            )
        except Exception as atomic_exc:
            detail = str(atomic_exc)
            if "b26_p2_atomic_sovereign_duplicate_refused" not in detail:
                # XXV (A9/B7): the atomic transition raises its governed
                # refusal tokens as ERRCODE 42501. Letting them propagate
                # turned a governed refusal into an HTTP 500 whose internal
                # text the relay then handed to the provider inside a
                # 200 body -- observed as
                # `authority_refused ... status=500 body=Internal Server
                # Error` for a second provider event over the same commerce
                # identity. A refusal the system intends must leave as a
                # refusal that names itself.
                governed = _governed_atomic_refusal(detail)
                if governed is not None:
                    await session.rollback()
                    raise HTTPException(status_code=409, detail=governed)
                raise
            await session.rollback()
            resolved = (
                (
                    await session.execute(
                        text(
                            # Same MATERIALIZED fence as the pre-check
                            # above: byte filter before any authority
                            # evaluation (rare path, same shape).
                            "WITH cand AS MATERIALIZED ("
                            " SELECT c.webhook_ingress_identity_id AS iid,"
                            " c.tenant_id AS tenant_id"
                            " FROM public.b26_p2_provider_auth_consequence AS c"
                            " WHERE c.tenant_id = :tenant"
                            " AND c.body_sha256 = :body_sha"
                            " AND c.provider_event_reference = :event_ref"
                            ")"
                            " SELECT i.id::text AS iid"
                            " FROM public.webhook_ingress_identities AS i"
                            " JOIN cand ON cand.iid = i.id"
                            " AND cand.tenant_id = i.tenant_id"
                            " WHERE i.tenant_id = :tenant"
                            " AND public.b26_p2_ingress_has_current_authority(i.id)"
                            " LIMIT 1"
                        ),
                        {
                            "tenant": str(tenant_uuid),
                            "body_sha": body_sha,
                            "event_ref": derived.provider_native_event_reference,
                        },
                    )
                )
                .mappings()
                .one_or_none()
            )
            if resolved is None:
                raise HTTPException(
                    status_code=500,
                    detail="b26_p2_sovereign_duplicate_unresolved",
                ) from atomic_exc
            return AuthenticateResponse(
                status="authenticated",
                provenance_status="authenticated_known",
                ingress_id=str(resolved["iid"]),
                tenant_id=str(tenant_uuid),
            )
    return AuthenticateResponse(
        status="authenticated",
        provenance_status="authenticated_known",
        ingress_id=canonical_id,
        tenant_id=str(tenant_uuid),
    )


@app.post(
    "/v1/authenticate-adjustment",
    response_model=AuthenticateAdjustmentResponse,
)
async def authenticate_adjustment(
    body: AuthenticateAdjustmentRequest,
) -> AuthenticateAdjustmentResponse:
    """Authenticate a post-capture provider adjustment and sign its evidence.

    Creation-family law is untouched. The root verifies the provider's
    refund/chargeback bytes, resolves the currently authoritative parent
    verdict, persists a separate adjustment-evidence row, and signs the
    adjustment identity, direction, amount and verdict link. The evidence is
    not a webhook ingress and never competes with the capture source.
    """
    _require_auth_role()
    provider = body.provider.strip().lower()
    if provider not in ("stripe", "shopify", "woocommerce", "paypal"):
        raise HTTPException(status_code=400, detail="unsupported adjustment provider")
    try:
        raw_body = base64.b64decode(body.raw_body_b64, validate=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="raw_body_b64 invalid") from exc
    from app.api.webhooks import WEBHOOK_VERIFIERS  # noqa: PLC0415
    from app.core.tenant_context import (  # noqa: PLC0415
        get_tenant_with_webhook_secrets,
    )
    from app.db.session import (  # noqa: PLC0415
        _ingress_boundary,
        assert_api_ingress_isolation,
    )
    from app.webhooks.commerce_derivation import (  # noqa: PLC0415
        CommerceDerivationError,
        derive_adjustment,
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
    try:
        adjusted = derive_adjustment(
            provider,
            raw_body,
            provider_event_reference=body.provider_event_reference,
        )
    except CommerceDerivationError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"adjustment_derivation_refused:{exc}",
        ) from exc
    if adjusted.verified_amount_currency.upper() != "USD":
        raise HTTPException(
            status_code=400,
            detail="adjustment_unsupported_currency:"
            + adjusted.verified_amount_currency,
        )
    body_sha = hashlib.sha256(raw_body).hexdigest().lower()
    sig_sha = hashlib.sha256(
        body.signature_header.encode("utf-8")
    ).hexdigest().lower()
    async with _ingress_boundary(), _ingress_session_with_source_outcomes(
        tenant_uuid, _source_attestation_key_path()
    ) as session:
        from app.core.construction_authority import (  # noqa: PLC0415
            assert_production_construction_authority as _assert_construction,
            read_construction_revisions as _read_revisions,
        )

        try:
            _assert_construction(await _read_revisions(session))
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=f"construction_authority_unverified:{exc}",
            ) from exc
        current = (
            (
                await session.execute(
                    text(
                        "SELECT verdict_id, captured_amount_minor,"
                        " currency_code FROM"
                        " public.b26_p2_current_verdict_for_adjustment"
                        " (:tenant, :provider, :parent)"
                    ),
                    {
                        "tenant": str(tenant_uuid),
                        "provider": provider,
                        "parent": adjusted.provider_native_commerce_reference,
                    },
                )
            )
            .mappings()
            .first()
        )
        if current is None:
            raise HTTPException(
                status_code=409,
                detail="adjustment_parent_verdict_unresolved",
            )
        captured = int(current["captured_amount_minor"] or 0)
        await session.execute(
            text(
                "SELECT pg_advisory_xact_lock("
                "hashtextextended(CAST(:verdict AS text), 0))"
            ),
            {"verdict": str(current["verdict_id"])},
        )
        prior = (
            (
                await session.execute(
                    text(
                        "SELECT id::text, verdict_id::text, event_type,"
                        " amount_minor, currency_code"
                        " FROM public.b26_p2_adjustment_evidence"
                        " WHERE tenant_id = :tenant AND provider = :provider"
                        " AND provider_native_event_reference = :event_ref"
                    ),
                    {
                        "tenant": str(tenant_uuid),
                        "provider": provider,
                        "event_ref": adjusted.provider_native_event_reference,
                    },
                )
            )
            .mappings()
            .one_or_none()
        )
        if prior is not None:
            return AuthenticateAdjustmentResponse(
                status="authenticated",
                adjustment_evidence_id=prior["id"],
                verdict_id=prior["verdict_id"],
                tenant_id=str(tenant_uuid),
                event_type=prior["event_type"],
                amount_minor=int(prior["amount_minor"]),
                currency_code=str(prior["currency_code"]),
                provider_native_event_reference=(
                    adjusted.provider_native_event_reference
                ),
            )
        prior_refunded = int(
            (
                await session.execute(
                    text(
                        "SELECT COALESCE(SUM(amount_minor), 0)"
                        " FROM public.b26_p2_adjustment_evidence"
                        " WHERE tenant_id = :tenant AND verdict_id = :verdict"
                        " AND event_type IN ('partial_refund', 'full_refund')"
                    ),
                    {
                        "tenant": str(tenant_uuid),
                        "verdict": str(current["verdict_id"]),
                    },
                )
            ).scalar_one()
            or 0
        )
        if (
            int(adjusted.verified_amount_minor) > captured
            or prior_refunded + int(adjusted.verified_amount_minor) > captured
        ):
            raise HTTPException(
                status_code=400,
                detail="adjustment_exceeds_remaining_captured_amount",
            )
        if str(current["currency_code"] or "").upper() != (
            adjusted.verified_amount_currency.upper()
        ):
            raise HTTPException(
                status_code=400,
                detail="adjustment_currency_mismatch",
            )
        event_type = (
            "full_refund"
            if int(adjusted.verified_amount_minor) == captured
            else "partial_refund"
        )
        evidence_id = uuid4()
        inserted = (
            (
                await session.execute(
                    text(
                        "INSERT INTO public.b26_p2_adjustment_evidence ("
                        " id, tenant_id, verdict_id, provider, event_type,"
                        " provider_native_event_reference,"
                        " provider_native_commerce_reference, currency_code,"
                        " amount_minor, event_timestamp, body_sha256,"
                        " signature_header_sha256, recorded_by"
                        ") VALUES (:id, :tenant, :verdict, :provider, :event_type,"
                        " :event_ref, :parent, :currency, :amount, :event_ts,"
                        " :body_sha, :sig_sha, 'app_ingress')"
                        " ON CONFLICT (tenant_id, provider,"
                        " provider_native_event_reference) DO NOTHING"
                        " RETURNING id::text"
                    ),
                    {
                        "id": str(evidence_id),
                        "tenant": str(tenant_uuid),
                        "verdict": str(current["verdict_id"]),
                        "provider": provider,
                        "event_type": event_type,
                        "event_ref": adjusted.provider_native_event_reference,
                        "parent": adjusted.provider_native_commerce_reference,
                        "currency": adjusted.verified_amount_currency.upper(),
                        "amount": int(adjusted.verified_amount_minor),
                        "event_ts": adjusted.event_timestamp,
                        "body_sha": body_sha,
                        "sig_sha": sig_sha,
                    },
                )
            )
            .scalar_one_or_none()
        )
        if inserted is None:
            existing = (
                (
                    await session.execute(
                        text(
                            "SELECT id::text, verdict_id::text, event_type,"
                            " amount_minor, currency_code"
                            " FROM public.b26_p2_adjustment_evidence"
                            " WHERE tenant_id = :tenant AND provider = :provider"
                            " AND provider_native_event_reference = :event_ref"
                        ),
                        {
                            "tenant": str(tenant_uuid),
                            "provider": provider,
                            "event_ref": adjusted.provider_native_event_reference,
                        },
                    )
                )
                .mappings()
                .one()
            )
            return AuthenticateAdjustmentResponse(
                status="authenticated",
                adjustment_evidence_id=existing["id"],
                verdict_id=existing["verdict_id"],
                tenant_id=str(tenant_uuid),
                event_type=existing["event_type"],
                amount_minor=int(existing["amount_minor"]),
                currency_code=str(existing["currency_code"]),
                provider_native_event_reference=(
                    adjusted.provider_native_event_reference
                ),
            )
        universe_row = (
            await session.execute(
                text("SELECT public.b26_p2_authority_universe()::text")
            )
        ).first()
        from app.revenue_verification.source_attestation import (  # noqa: PLC0415
            build_adjustment_statement,
            write_adjustment_attestation,
        )

        statement = build_adjustment_statement(
            tenant_id=str(tenant_uuid),
            adjustment_evidence_id=inserted,
            verdict_id=str(current["verdict_id"]),
            provider=provider,
            event_type=event_type,
            provider_native_event_reference=(
                adjusted.provider_native_event_reference
            ),
            provider_native_commerce_reference=(
                adjusted.provider_native_commerce_reference
            ),
            verified_amount_minor=int(adjusted.verified_amount_minor),
            verified_amount_currency=adjusted.verified_amount_currency.upper(),
            verified_amount_scale=int(adjusted.verified_amount_scale),
            event_timestamp=adjusted.event_timestamp,
            body_sha256=body_sha,
            authority_universe=(
                None if universe_row is None else universe_row[0]
            ),
        )
        key_path = os.getenv("B26_P2_SOURCE_ATTESTATION_PRIVATE_KEY_PATH", "").strip()
        if not key_path:
            from app.core.config import settings  # noqa: PLC0415

            key_path = settings.B26_P2_SOURCE_ATTESTATION_PRIVATE_KEY_PATH
        if not key_path:
            raise HTTPException(
                status_code=500,
                detail="adjustment_attestation_key_absent",
            )
        await write_adjustment_attestation(
            session, statement=statement, private_key_path=key_path
        )
    return AuthenticateAdjustmentResponse(
        status="authenticated",
        adjustment_evidence_id=inserted,
        verdict_id=str(current["verdict_id"]),
        tenant_id=str(tenant_uuid),
        event_type=event_type,
        amount_minor=int(adjusted.verified_amount_minor),
        currency_code=adjusted.verified_amount_currency.upper(),
        provider_native_event_reference=adjusted.provider_native_event_reference,
    )
