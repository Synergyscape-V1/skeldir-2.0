"""
Event Ingestion Service - B0.4.3 Core Implementation + B0.4.4 DLQ Enhancement

Provides idempotent event ingestion with channel normalization, validation,
and dead-letter queue routing for failed events.

B0.4.4 Enhancement: Integrated DLQHandler with error classification and retry logic.
"""

import logging
import hashlib
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
import time
from typing import Any, Mapping, Optional
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.bayesian.dirty_marker import append_dirty_event
from app.ingestion.channel_normalization import normalize_channel
from app.ingestion.dlq_handler import DLQHandler
from app.ingestion.privacy_boundary import enforce_ingress_privacy_boundary
from app.models import AttributionEvent, DeadEvent, RawEventPayload, WebhookIngressIdentity
from app.observability.context import log_context
from app.privacy.authority import minimize_event_payload_for_storage
from app.privacy.durable_commerce_identity import upsert_durable_commerce_identity_link
from app.privacy.ephemeral_resolution import (
    resolve_session_candidate_with_ephemeral_substrate,
    upsert_ephemeral_resolution_links,
)
from app.privacy.session_authority import resolve_session_authority
from app.revenue_verification.semantic_authority import (
    CanonicalizationStatus,
    canonicalize_attribution_commerce_reference,
    resolve_canonical_match_key,
)
from app.observability.api_metrics import (
    events_dlq_total,
    events_duplicate_total,
    events_ingested_total,
    ingestion_duration_seconds,
)

logger = logging.getLogger(__name__)

_IDEMPOTENCY_UNIQUE_CONSTRAINT = "uq_attribution_events_tenant_idempotency_key"
_SENSITIVE_REQUEST_HEADER_KEYS = frozenset(
    {
        "authorization",
        "cookie",
        "set-cookie",
        "x-skeldir-tenant-key",
        "x-api-key",
        "proxy-authorization",
    }
)
_WEBHOOK_INGRESS_SOURCES = frozenset(
    {
        "shopify",
        "stripe",
        "paypal",
        "woocommerce",
        "webhook",
    }
)
_WEBHOOK_IDENTITY_ENVELOPE_SOURCES = frozenset(
    {
        "shopify",
        "stripe",
        "paypal",
        "woocommerce",
    }
)
_WEBHOOK_INGRESS_IDENTITY_REQUIRED_FIELDS = frozenset(
    {
        "provider",
        "provider_native_event_reference",
        "provider_native_commerce_reference",
        "normalized_commerce_reference_kind",
        "normalized_commerce_reference_value",
        "verified_amount_minor",
        "verified_amount_currency",
        "verified_amount_scale",
        "verified_commerce_ingress_state",
        "verified_at",
    }
)


class ValidationError(Exception):
    """Raised when event data fails validation"""


class AuthoritativeIngressInvariantError(RuntimeError):
    """Raised when authoritative webhook ingress substrate invariants are violated."""


class IngestionResultState(str, Enum):
    """Canonical ingestion outcomes surfaced to orchestration callers."""

    INSERTED = "inserted"
    DUPLICATE = "duplicate"


@dataclass(frozen=True)
class IngestionDecision:
    """Explicit ingestion decision contract for orchestration boundaries."""

    event: AttributionEvent
    state: IngestionResultState
    # B2.6-P2 Corrective XI: verified-ingress finalization deferred
    # past commit. When the caller session cannot author
    # authenticity_verified (ingress isolation), the arrival persists
    # in-transaction as an unverified precursor and this payload
    # completes it post-commit through the dedicated ingress
    # credential (witness + attestation). None when the in-transaction
    # path already established authority (authorized sessions) or no
    # verified ingress was intended.
    ingress_finalization: dict[str, Any] | None = None

    @property
    def is_duplicate(self) -> bool:
        return self.state == IngestionResultState.DUPLICATE


@dataclass(frozen=True)
class IngestionTransactionResult:
    """
    Runtime ingestion boundary contract for webhook orchestration callers.

    Success state is represented by an IngestionDecision instance.
    Error state is represented by explicit error_type/error fields.
    """

    decision: IngestionDecision | None = None
    error_type: str | None = None
    error: str | None = None

    @property
    def status(self) -> str:
        return "success" if self.decision is not None else "error"

    @property
    def event(self) -> AttributionEvent | None:
        if self.decision is None:
            return None
        return self.decision.event

    @property
    def event_id(self) -> str | None:
        event = self.event
        if event is None:
            return None
        return str(event.id)

    @property
    def session_id(self) -> str | None:
        event = self.event
        if event is None:
            return None
        return str(event.session_id)

    @property
    def channel(self) -> str | None:
        event = self.event
        if event is None:
            return None
        return event.channel

    @property
    def idempotency_key(self) -> str | None:
        event = self.event
        if event is None:
            return None
        return event.idempotency_key

    @property
    def is_duplicate(self) -> bool:
        if self.decision is None:
            return False
        return self.decision.is_duplicate

    @property
    def ingestion_state(self) -> str | None:
        if self.decision is None:
            return None
        return self.decision.state.value


def _first_non_empty_resolution_token(*values: Any) -> str | None:
    for value in values:
        if value is None:
            continue
        token = str(value).strip()
        if token:
            return token
    return None


def _lookup_hash_for_selector(value: str) -> str:
    return hashlib.sha256(value.strip().encode("utf-8")).hexdigest()


def _normalized_request_headers(headers: Mapping[str, str] | None) -> dict[str, str]:
    if not headers:
        return {}
    normalized: dict[str, str] = {}
    for key, value in headers.items():
        normalized_key = str(key).strip().lower()
        if not normalized_key or normalized_key in _SENSITIVE_REQUEST_HEADER_KEYS:
            continue
        normalized[normalized_key] = str(value).strip()
    return normalized


def _first_header_value(
    headers: Mapping[str, str],
    keys: tuple[str, ...],
) -> str | None:
    for key in keys:
        value = (headers.get(key) or "").strip()
        if value:
            return value
    return None


def _raw_event_ingress_metadata_for_persistence(
    *,
    source: str,
    normalized_headers: Mapping[str, str],
) -> tuple[str | None, str | None, dict[str, str] | None]:
    """
    Preserve verification substrate in memory only, not in durable webhook storage.
    """
    if source.strip().lower() in _WEBHOOK_INGRESS_SOURCES:
        return None, None, None

    return (
        _first_header_value(normalized_headers, ("x-forwarded-for", "x-real-ip")),
        _first_header_value(normalized_headers, ("user-agent",)),
        dict(normalized_headers) or None,
    )


def _extract_order_resolution_key(
    *,
    event_data: Mapping[str, Any],
    identity_payload: Mapping[str, Any],
) -> str | None:
    raw_order_id = _first_non_empty_resolution_token(
        event_data.get("order_id"),
        identity_payload.get("order_id"),
    )
    if raw_order_id is None:
        return None

    provider_hint = _first_non_empty_resolution_token(
        event_data.get("provider"),
        event_data.get("vendor"),
        identity_payload.get("provider"),
    )
    canonicalized = canonicalize_attribution_commerce_reference(
        provider=provider_hint,
        raw_reference=raw_order_id,
    )
    if canonicalized.status is CanonicalizationStatus.CANONICALIZED:
        return canonicalized.canonical_reference
    return None


def _extract_click_resolution_key(
    *,
    event_data: Mapping[str, Any],
    identity_payload: Mapping[str, Any],
) -> str | None:
    for key in ("click_id", "gclid", "fbclid"):
        resolved = _first_non_empty_resolution_token(
            event_data.get(key),
            identity_payload.get(key),
        )
        if resolved is not None:
            return resolved
    return None


def _extract_webhook_ingress_identity(
    *,
    source: str,
    event_data: Mapping[str, Any],
    tenant_id: UUID,
    idempotency_key: str,
    event_id: UUID,
    event_timestamp: datetime,
) -> dict[str, Any] | None:
    normalized_source = source.strip().lower()
    provider_hint = str(event_data.get("provider", "")).strip().lower()
    if (
        normalized_source not in _WEBHOOK_IDENTITY_ENVELOPE_SOURCES
        and provider_hint not in _WEBHOOK_IDENTITY_ENVELOPE_SOURCES
    ):
        return None

    populated_fields = {
        key
        for key in _WEBHOOK_INGRESS_IDENTITY_REQUIRED_FIELDS
        if event_data.get(key) not in (None, "")
    }
    authoritative_ingress_state_present = (
        event_data.get("verified_commerce_ingress_state") not in (None, "")
    )
    if not populated_fields:
        if authoritative_ingress_state_present:
            raise AuthoritativeIngressInvariantError(
                "Authoritative webhook ingress cannot bypass canonical identity envelope persistence."
            )
        return None

    missing_fields = [
        key
        for key in sorted(_WEBHOOK_INGRESS_IDENTITY_REQUIRED_FIELDS)
        if key not in populated_fields
    ]
    if missing_fields:
        raise ValidationError(
            "Missing required webhook identity envelope fields: "
            + ", ".join(missing_fields)
        )

    amount_minor = event_data.get("verified_amount_minor")
    amount_scale = event_data.get("verified_amount_scale")
    try:
        amount_minor_int = int(amount_minor)
        amount_scale_int = int(amount_scale)
    except (TypeError, ValueError) as exc:
        raise ValidationError(
            "Webhook identity envelope monetary fields must be integers"
        ) from exc
    if amount_minor_int < 0:
        raise ValidationError("verified_amount_minor must be non-negative")
    if amount_scale_int < 0:
        raise ValidationError("verified_amount_scale must be non-negative")

    amount_currency = str(event_data["verified_amount_currency"]).strip().upper()
    if len(amount_currency) != 3:
        raise ValidationError("verified_amount_currency must be a 3-letter ISO code")
    verified_at_value = event_data.get("verified_at")
    if isinstance(verified_at_value, datetime):
        verified_at = (
            verified_at_value.astimezone(timezone.utc)
            if verified_at_value.tzinfo is not None
            else verified_at_value.replace(tzinfo=timezone.utc)
        )
    else:
        raise ValidationError(
            "verified_at must be captured at verification time and provided as a datetime"
        )

    precedence_resolution = resolve_canonical_match_key(
        provider=provider_hint or normalized_source,
        normalized_commerce_reference=str(
            event_data["normalized_commerce_reference_value"]
        ).strip(),
        provider_native_commerce_reference=str(
            event_data["provider_native_commerce_reference"]
        ).strip(),
        strict_order_id=_first_non_empty_resolution_token(event_data.get("order_id")),
    )
    if precedence_resolution.status is CanonicalizationStatus.CANONICALIZATION_FAILED:
        raise ValidationError(
            "Webhook identity canonicalization failed under B2.3-P0 authority policy."
        )

    return {
        "id": uuid4(),
        "tenant_id": tenant_id,
        "event_id": event_id,
        "provider": provider_hint or normalized_source,
        "provider_native_event_reference": str(
            event_data["provider_native_event_reference"]
        ).strip(),
        "provider_native_commerce_reference": str(
            event_data["provider_native_commerce_reference"]
        ).strip(),
        "normalized_commerce_reference_kind": str(
            event_data["normalized_commerce_reference_kind"]
        ).strip(),
        "normalized_commerce_reference_value": str(
            event_data["normalized_commerce_reference_value"]
        ).strip(),
        "verified_amount_minor": amount_minor_int,
        "verified_amount_currency": amount_currency,
        "verified_amount_scale": amount_scale_int,
        "event_timestamp": event_timestamp,
        "idempotency_key": idempotency_key,
        "verified_commerce_ingress_state": str(
            event_data["verified_commerce_ingress_state"]
        ).strip(),
        "verified_at": verified_at,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }


# B2.6-P2 Corrective VIII authenticated-root adoption law (H-VIII-A02/A03).
# Sovereign comparison set for duplicate adoption: every commerce-meaning
# column plus tenant/state. Row-identity columns (id, event_id,
# verified_at) are adoption bindings, compared never: a legitimate arrival
# adopts the canonical row and binds its own event. Mirrors
# b26_p2_enforce_ingress_duplicate_adoption(); divergence between the two
# is itself a defect (the trigger is the unavoidable backstop for
# direct-SQL paths, this helper is the availability-preserving promotion
# for the API path).
_B26_P2_INGRESS_SOVEREIGN_FIELDS = (
    "provider",
    "provider_native_event_reference",
    "provider_native_commerce_reference",
    "normalized_commerce_reference_kind",
    "normalized_commerce_reference_value",
    "verified_amount_minor",
    "verified_amount_currency",
    "event_timestamp",
)

_B26_P2_AUTHENTICATED_STATE = "authenticity_verified"


def _ingress_sovereign_mismatch(existing: Any, incoming: Mapping[str, Any]) -> bool:
    for field in _B26_P2_INGRESS_SOVEREIGN_FIELDS:
        old = getattr(existing, field, None)
        new = incoming.get(field)
        if isinstance(old, datetime) and isinstance(new, datetime):
            old_utc = (
                old.astimezone(timezone.utc)
                if old.tzinfo is not None
                else old.replace(tzinfo=timezone.utc)
            )
            new_utc = (
                new.astimezone(timezone.utc)
                if new.tzinfo is not None
                else new.replace(tzinfo=timezone.utc)
            )
            if old_utc != new_utc:
                return True
            continue
        if str(old) != str(new):
            return True
    if str(getattr(existing, "tenant_id", "")) != str(incoming.get("tenant_id", "")):
        return True
    return False


async def _adopt_or_promote_ingress(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    incoming: dict[str, Any],
    event_id: UUID,
    auth_consequence: Mapping[str, Any] | None = None,
) -> Any | None:
    """Govern duplicate ingress adoption for one authenticated arrival.

    Returns None when no row collides (caller INSERTs normally), otherwise
    returns the adopted/promoted ORM row (caller must NOT insert a new
    row). Raises ValidationError (routed to DLQ, never silent success)
    when an authenticated root already carries different sovereign values
    or when two lower-authority precursors collide.
    """
    existing = (
        (
            await session.execute(
                select(WebhookIngressIdentity).where(
                    WebhookIngressIdentity.tenant_id == tenant_id,
                    WebhookIngressIdentity.idempotency_key
                    == incoming["idempotency_key"],
                )
            )
        )
        .scalars()
        .one_or_none()
    )
    if existing is None:
        return None
    mismatch = _ingress_sovereign_mismatch(existing, incoming)
    existing_verified = (
        str(existing.verified_commerce_ingress_state) == _B26_P2_AUTHENTICATED_STATE
    )
    incoming_verified = (
        str(incoming.get("verified_commerce_ingress_state"))
        == _B26_P2_AUTHENTICATED_STATE
    )
    if existing_verified:
        if mismatch or not incoming_verified:
            raise ValidationError(
                "b26_p2_ingress_authenticated_conflict: a canonical"
                " authenticated root already carries different sovereign"
                " values for this identity"
            )
        existing.event_id = event_id
        existing.updated_at = datetime.now(timezone.utc)
        # Corrective X re-ingestion restoration: a genuine signed
        # duplicate re-establishes provenance through recorded evidence,
        # never a bare status write. Corrective XI: the witness and the
        # attestation execute with ingress authority (dedicated
        # credential when mounted, else the caller session for
        # admins/tests). The attester binds the row's own provider
        # idempotency key as the evidence reference and promotes
        # unknown_legacy roots; already-known roots simply refresh
        # their evidence trail.
        await _attest_reingestion_as_ingress(
            session,
            ingress_id=str(existing.id),
            evidence_ref=str(existing.idempotency_key),
            auth_consequence=auth_consequence,
        )
        return existing
    if incoming_verified:
        for field in (
            *_B26_P2_INGRESS_SOVEREIGN_FIELDS,
            "verified_amount_scale",
            "verified_commerce_ingress_state",
            "verified_at",
        ):
            setattr(existing, field, incoming[field])
        existing.event_id = event_id
        existing.updated_at = datetime.now(timezone.utc)
        logger.warning(
            "b26_p2_ingress_precursor_promoted",
            extra={
                "tenant_id": str(tenant_id),
                "idempotency_key": str(incoming.get("idempotency_key")),
                "ingress_id": str(getattr(existing, "id", "")),
            },
        )
        return existing
    raise ValidationError(
        "b26_p2_ingress_precursor_collision: lower-authority precursor"
        " already occupies this identity"
    )


def _is_b26_p2_adoption_error(error: Exception) -> str | None:
    lowered = str(error).lower()
    if "b26_p2_ingress_precursor_present_promote_required" in lowered:
        return "promote_required"
    if "b26_p2_ingress_authenticated_conflict" in lowered:
        return "authenticated_conflict"
    return None


def _is_verified_intended(ingress_payload: Mapping[str, Any] | None) -> bool:
    """True when the arrival intends authenticity_verified ingress."""
    return (
        ingress_payload is not None
        and str(ingress_payload.get("verified_commerce_ingress_state"))
        == _B26_P2_AUTHENTICATED_STATE
    )


def _is_b26_p2_verified_authorship_error(error: Exception) -> bool:
    """True when a flush failed on XI ingress-authorship isolation.

    B2.6-P2 Corrective XI: only the dedicated ingress principal
    (app_ingress) may author authenticity_verified. The API session
    (ordinary application authority) hitting this refusal must persist
    the HMAC-verified arrival through the ingress credential instead of
    failing the webhook. The refusal is fail-closed routing, not data.
    """
    return "b26_p2_verified_authorship_refused" in str(error).lower()


def _b26_p2_ingress_dsn() -> str | None:
    """Dedicated authenticated-ingress DSN, mounted only into the API."""
    dsn = os.environ.get("B26_P2_INGRESS_DATABASE_URL", "").strip()
    return dsn or None


_B26_P2_PRECURSOR_STATE = "pending"


def _precursor_payload(
    ingress_payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Downgrade a verified-intended arrival to an in-txn precursor.

    B2.6-P2 Corrective XI: sessions without ingress authority cannot
    author authenticity_verified, but they must not fail (or silently
    drop) an HMAC-verified arrival either. The precursor persists
    atomically with the event; the dedicated ingress credential
    promotes it post-commit (see finalize function below), when the
    committed event row is visible and the FK holds. No certainty is
    manufactured in-transaction: provenance stays non-authenticated
    until the witness consequence runs.
    """
    precursor = dict(ingress_payload)
    precursor["verified_commerce_ingress_state"] = _B26_P2_PRECURSOR_STATE
    return precursor


def _finalization_payload(
    ingress_payload: Mapping[str, Any],
    auth_consequence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Snapshot a verified arrival for post-commit finalization."""
    snapshot = {
        key: ingress_payload.get(key)
        for key in (
            "id", "tenant_id", "event_id", "provider",
            "provider_native_event_reference",
            "provider_native_commerce_reference",
            "normalized_commerce_reference_kind",
            "normalized_commerce_reference_value",
            "verified_amount_minor", "verified_amount_currency",
            "verified_amount_scale", "event_timestamp",
            "idempotency_key", "verified_at",
        )
    }
    # B2.6-P2 Corrective XII: the predecessor event P (successful
    # provider-signature verification) travels with the finalization so
    # the post-commit witness is bound to it. None means no P was
    # established in the HMAC-verified path; finalization then fails
    # closed instead of self-certifying.
    snapshot["auth_consequence"] = (
        dict(auth_consequence) if auth_consequence is not None else None
    )
    return snapshot


async def _record_auth_consequence_as_app_user(
    *,
    tenant_uuid: UUID,
    ingress_id: str,
    consequence: Mapping[str, Any],
) -> None:
    """Record predecessor event P with the API application principal.

    B2.6-P2 Corrective XII: P is authored by app_user in the
    HMAC-verified path and consumed by the ingress boundary. The
    ingress principal cannot author P (grants deny), so possession of
    the ingress credential alone cannot manufacture the prerequisite.
    """
    from app.db.session import get_session  # noqa: PLC0415

    async with get_session(tenant_id=tenant_uuid) as session:
        await session.execute(
            text(
                "SELECT public.b26_p2_record_provider_auth_consequence("
                " :ingress_id, :provider, :event_ref,"
                " :body_sha256, :sig_sha256, :method, :version)"
            ),
            {
                "ingress_id": str(ingress_id),
                "provider": str(consequence.get("provider")),
                "event_ref": str(consequence.get("provider_event_reference")),
                "body_sha256": str(consequence.get("body_sha256")).lower(),
                "sig_sha256": str(
                    consequence.get("signature_envelope_sha256")
                ).lower(),
                "method": str(consequence.get("auth_method")),
                "version": str(consequence.get("auth_version") or "v1"),
            },
        )


async def _finalize_verified_ingress_post_commit(
    finalization: Mapping[str, Any],
) -> None:
    """Complete a verified arrival through the ingress credential (XII).

    Runs AFTER the caller transaction commits, in an ORM session bound
    to the dedicated ingress pool: the committed event row is visible,
    so the ingress FK holds. Idempotent by (tenant_id,
    idempotency_key): inserts the verified row when absent, promotes a
    pending precursor (refusing genuine sovereign conflicts via the
    shared sovereign comparator), records the predecessor consequence
    P with the application principal, derives the bound witness, and
    attests provenance -- one governed authentication consequence.
    Requires the HMAC-established consequence snapshot; without P the
    finalizer fails closed (no self-certification). Raises when no
    ingress DSN is mounted (fail-closed: the lane must provision the
    ingress principal; never silently leave the arrival unverified).
    ORM attribute access keeps coverage-money SQL out of application
    string constants (B2.6-P1 coverage fence).
    """
    from app.db.session import _ingress_boundary, get_ingress_session  # noqa: PLC0415

    tenant_id = finalization.get("tenant_id")
    idem = str(finalization.get("idempotency_key"))
    consequence = finalization.get("auth_consequence")
    if not isinstance(consequence, dict) or not consequence.get("body_sha256"):
        raise ValidationError(
            "b26_p2_ingress_finalization_no_auth_consequence: verified"
            " arrival requires the HMAC-established predecessor event"
        )
    try:
        tenant_uuid = UUID(str(tenant_id))
    except (TypeError, ValueError) as exc:
        raise ValidationError(
            "b26_p2_ingress_finalization_tenant_invalid"
        ) from exc
    consequence_summary = {
        "provider": str(finalization.get("provider")),
        "provider_event_reference": str(
            finalization.get("provider_native_event_reference")
        ),
        "body_sha256": str(consequence.get("body_sha256")).lower(),
        "signature_envelope_sha256": str(
            consequence.get("signature_envelope_sha256")
        ).lower(),
        "auth_method": str(consequence.get("auth_method")),
        "auth_version": str(consequence.get("auth_version") or "v1"),
    }
    async with _ingress_boundary(), get_ingress_session(
        tenant_id=tenant_uuid
    ) as session:
        existing = (
            (
                await session.execute(
                    select(WebhookIngressIdentity).where(
                        WebhookIngressIdentity.tenant_id == tenant_uuid,
                        WebhookIngressIdentity.idempotency_key == idem,
                    )
                )
            )
            .scalars()
            .one_or_none()
        )
        if existing is None:
            session.add(
                WebhookIngressIdentity(
                    id=finalization.get("id") or uuid4(),
                    tenant_id=tenant_uuid,
                    event_id=finalization.get("event_id"),
                    provider=finalization.get("provider"),
                    provider_native_event_reference=finalization.get(
                        "provider_native_event_reference"
                    ),
                    provider_native_commerce_reference=finalization.get(
                        "provider_native_commerce_reference"
                    ),
                    normalized_commerce_reference_kind=finalization.get(
                        "normalized_commerce_reference_kind"
                    ),
                    normalized_commerce_reference_value=finalization.get(
                        "normalized_commerce_reference_value"
                    ),
                    verified_amount_minor=finalization.get(
                        "verified_amount_minor"
                    ),
                    verified_amount_currency=finalization.get(
                        "verified_amount_currency"
                    ),
                    verified_amount_scale=finalization.get(
                        "verified_amount_scale"
                    ),
                    event_timestamp=finalization.get("event_timestamp"),
                    idempotency_key=idem,
                    verified_commerce_ingress_state=(
                        _B26_P2_AUTHENTICATED_STATE
                    ),
                    verified_at=finalization.get("verified_at"),
                )
            )
            await session.flush()
            existing = (
                (
                    await session.execute(
                        select(WebhookIngressIdentity).where(
                            WebhookIngressIdentity.tenant_id == tenant_uuid,
                            WebhookIngressIdentity.idempotency_key == idem,
                        )
                    )
                )
                .scalars()
                .one()
            )
        elif (
            str(existing.verified_commerce_ingress_state)
            != _B26_P2_AUTHENTICATED_STATE
        ):
            if _ingress_sovereign_mismatch(existing, finalization):
                raise ValidationError(
                    "b26_p2_ingress_authenticated_conflict: a canonical"
                    " authenticated root already carries different"
                    " sovereign values for this identity"
                )
            for field in (
                *_B26_P2_INGRESS_SOVEREIGN_FIELDS,
                "verified_amount_scale",
                "verified_commerce_ingress_state",
                "verified_at",
            ):
                if field == "verified_commerce_ingress_state":
                    setattr(
                        existing, field, _B26_P2_AUTHENTICATED_STATE
                    )
                elif field in finalization:
                    setattr(existing, field, finalization[field])
            await session.flush()
        ingress_uuid = str(existing.id)
    # First transaction committed on context exit: the ingress row is
    # now visible to the application pool. XII: record P with the
    # application principal (independently of the ingress credential),
    # then derive the bound witness and attest with ingress authority.
    # Either step failing closed leaves no self-certified token.
    from app.db.session import _ingress_boundary as _xii_boundary2  # noqa: PLC0415
    from app.db.session import get_ingress_session as _xii_ingress2  # noqa: PLC0415

    await _record_auth_consequence_as_app_user(
        tenant_uuid=tenant_uuid,
        ingress_id=ingress_uuid,
        consequence=consequence_summary,
    )
    async with _xii_boundary2(), _xii_ingress2(
        tenant_id=tenant_uuid
    ) as witness_session:
        await witness_session.execute(
            text(
                "SELECT public.b26_p2_record_ingress_auth_witness("
                " :ingress_id, :provider, :event_ref, :body_sha256)"
            ),
            {
                "ingress_id": ingress_uuid,
                "provider": consequence_summary["provider"],
                "event_ref": consequence_summary[
                    "provider_event_reference"
                ],
                "body_sha256": consequence_summary["body_sha256"],
            },
        )
        await witness_session.execute(
            text(
                "SELECT public.b26_p2_attest_provenance_evidence("
                " :ingress_id, 'signed_provider_reingestion',"
                " :evidence_ref)"
            ),
            {
                "ingress_id": ingress_uuid,
                "evidence_ref": idem,
            },
        )


async def _attest_reingestion_as_ingress(
    session: AsyncSession,
    *,
    ingress_id: str,
    evidence_ref: str,
    auth_consequence: Mapping[str, Any] | None = None,
) -> None:
    """Attest a genuine signed re-ingestion with ingress authority (XII).

    Prefers the dedicated ingress credential when mounted (the API
    production path); falls back to the caller session so migration
    admins and test harnesses keep a working path. A bare app_user
    session is refused by the database either way. The bound witness
    form is always used: re-ingestion refreshes evidence for an
    ingress whose predecessor consequence already exists; without P
    the call fails closed.
    """
    if auth_consequence is not None:
        provider = str(auth_consequence.get("provider"))
        event_ref = str(auth_consequence.get("provider_event_reference"))
        body_sha256 = str(auth_consequence.get("body_sha256")).lower()
    else:
        existing_cons = (
            (
                await session.execute(
                    text(
                        "SELECT c.provider, c.provider_event_reference,"
                        " c.body_sha256"
                        " FROM public.b26_p2_provider_auth_consequence AS c"
                        " WHERE c.webhook_ingress_identity_id = :ingress_id"
                    ),
                    {"ingress_id": ingress_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        if existing_cons is None:
            raise ValidationError(
                "b26_p2_reingestion_no_auth_consequence: genuine signed"
                " re-ingestion requires the recorded predecessor event"
            )
        provider = str(existing_cons["provider"])
        event_ref = str(existing_cons["provider_event_reference"])
        body_sha256 = str(existing_cons["body_sha256"]).lower()
    if _b26_p2_ingress_dsn() is not None:
        try:
            import asyncpg  # noqa: PLC0415
        except ImportError as exc:
            raise ValidationError(
                "b26_p2_ingress_credential_unavailable"
            ) from exc
        dsn = _b26_p2_ingress_dsn()
        assert dsn is not None
        if dsn.startswith("postgresql+asyncpg://"):
            dsn = "postgresql://" + dsn[len("postgresql+asyncpg://"):]
        conn = await asyncpg.connect(dsn)
        try:
            await conn.execute(
                "SELECT public.b26_p2_record_ingress_auth_witness("
                "$1::uuid, $2, $3, $4)",
                ingress_id, provider, event_ref, body_sha256,
            )
            await conn.execute(
                "SELECT public.b26_p2_attest_provenance_evidence("
                "$1::uuid, 'signed_provider_reingestion', $2)",
                ingress_id, evidence_ref,
            )
            return
        finally:
            await conn.close()
    await session.execute(
        text(
            "SELECT public.b26_p2_attest_provenance_evidence("
            " :ingress_id, 'signed_provider_reingestion',"
            " :evidence_ref)"
        ),
        {
            "ingress_id": ingress_id,
            "evidence_ref": evidence_ref,
        },
    )


_INGRESS_COLLISION_CONSTRAINTS = frozenset(
    {
        "uq_webhook_ingress_identities_tenant_idempotency",
        "uq_webhook_ingress_identities_tenant_event",
        "uq_webhook_ingress_identities_event_id",
    }
)


def _is_ingress_collision_integrity_error(error: Exception) -> bool:
    """True when a flush failed on a webhook-ingress identity unique."""
    constraint = _integrity_error_constraint_name(error) if isinstance(
        error, IntegrityError
    ) else None
    if constraint and constraint in _INGRESS_COLLISION_CONSTRAINTS:
        return True
    if isinstance(error, IntegrityError):
        sqlstate = _integrity_error_sqlstate(error)
        msg = str(error).lower()
        if sqlstate == "23505" and "webhook_ingress_identities" in msg:
            return True
    return False


def _integrity_error_sqlstate(error: IntegrityError) -> str | None:
    orig = getattr(error, "orig", None)
    if orig is None:
        return None
    for attr in ("pgcode", "sqlstate"):
        value = getattr(orig, attr, None)
        if value:
            return str(value)
    return None


def _integrity_error_constraint_name(error: IntegrityError) -> str | None:
    orig = getattr(error, "orig", None)
    if orig is None:
        return None

    diag = getattr(orig, "diag", None)
    if diag is not None:
        name = getattr(diag, "constraint_name", None)
        if name:
            return str(name)

    name = getattr(orig, "constraint_name", None)
    if name:
        return str(name)

    return None


def _is_idempotency_duplicate_integrity_error(error: IntegrityError) -> bool:
    """
    Detect tenant-scoped idempotency races deterministically.

    We prefer SQLSTATE/constraint-name detection over fragile string matching.
    Fallback to message matching covers older driver variants.
    """
    constraint = _integrity_error_constraint_name(error)
    if constraint and _IDEMPOTENCY_UNIQUE_CONSTRAINT in constraint:
        return True

    sqlstate = _integrity_error_sqlstate(error)
    if sqlstate == "23505" and constraint and "idempotency" in constraint:
        return True

    msg = str(error).lower()
    return (
        "duplicate key value violates unique constraint" in msg
        and ("idempotency" in msg or _IDEMPOTENCY_UNIQUE_CONSTRAINT in msg)
    )


async def _fetch_existing_event_for_key(
    session: AsyncSession, *, tenant_id: UUID, idempotency_key: str
) -> Optional[AttributionEvent]:
    res = await session.execute(
        select(AttributionEvent).where(
            AttributionEvent.tenant_id == tenant_id,
            AttributionEvent.idempotency_key == idempotency_key,
        )
    )
    return res.scalar_one_or_none()


def _programming_error_sqlstate(error: ProgrammingError) -> str | None:
    orig = getattr(error, "orig", None)
    if orig is None:
        return None
    for attr in ("pgcode", "sqlstate"):
        value = getattr(orig, attr, None)
        if value:
            return str(value)
    return None


def _is_missing_webhook_identity_relation_error(error: ProgrammingError) -> bool:
    sqlstate = _programming_error_sqlstate(error)
    lowered = str(error).lower()
    if sqlstate == "42P01":
        return "webhook_ingress_identities" in lowered
    return (
        "relation" in lowered
        and "does not exist" in lowered
        and "webhook_ingress_identities" in lowered
    )


def _is_missing_attribution_commerce_identity_relation_error(error: ProgrammingError) -> bool:
    sqlstate = _programming_error_sqlstate(error)
    lowered = str(error).lower()
    if sqlstate == "42P01":
        return "attribution_commerce_identities" in lowered
    return (
        "relation" in lowered
        and "does not exist" in lowered
        and "attribution_commerce_identities" in lowered
    )


class EventIngestionService:
    """
    Core service for idempotent webhook event ingestion.

    Responsibilities:
        - Idempotency enforcement via database UNIQUE constraint
        - Schema validation (required fields, type checking)
        - Channel normalization (vendor indicators → canonical codes)
        - Dead-letter queue routing on validation failures
        - Atomic transaction management (commit success, rollback on error)

    Integration Points:
        - channel_normalization.normalize_channel(): Vendor → canonical mapping
        - AttributionEvent ORM: Database insert with RLS enforcement
        - DeadEvent ORM: DLQ capture for failed validations
        - DLQHandler: Enhanced error classification and retry logic (B0.4.4)
    """

    def __init__(self):
        """Initialize service with DLQ handler."""
        self.dlq_handler = DLQHandler()

    async def ingest_event_with_decision(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        event_data: dict,
        idempotency_key: str,
        source: str = "webhook",
        identity_payload: Mapping[str, Any] | None = None,
        request_headers: Mapping[str, str] | None = None,
        auth_consequence: Mapping[str, Any] | None = None,
    ) -> IngestionDecision:
        """
        Ingest event with idempotency guarantee and validation.

        Args:
            session: Database session with RLS context set (app.current_tenant_id)
            tenant_id: Tenant UUID for event ownership
            event_data: Event payload targeted for storage assembly.
            idempotency_key: Deduplication key (e.g., external_event_id)
            source: Event source identifier (e.g., 'shopify', 'stripe')
            auth_consequence: B2.6-P2 Corrective XII predecessor event P
                established by successful provider-signature verification
                (provider/event/body/signature/method). Required for a
                verified arrival to finalize; None fails that path
                closed while leaving unverified ingestion unaffected.

        Returns:
            IngestionDecision with event + explicit duplicate/inserted state.

        Raises:
            ValidationError: Event data fails schema validation (routes to DLQ)
            IntegrityError: Database constraint violation (should not occur with proper validation)

        Idempotency Guarantee:
            Duplicate idempotency_key returns existing event without insert.
            Database UNIQUE constraint enforces deduplication at persistence layer.
        """
        identity_payload = dict(identity_payload or event_data)
        boundary = enforce_ingress_privacy_boundary(
            storage_payload=event_data,
            identity_payload=identity_payload,
            source=source,
            idempotency_key=idempotency_key,
            fallback_session_id=str(event_data.get("session_id", "")) or None,
            request_headers=request_headers,
            mode="strip",
        )
        raw_candidate_session_id = str(event_data.get("session_id", "")).strip() or None
        ingestion_event_data = dict(event_data)
        ingestion_event_data["global_idempotency_hash"] = boundary.global_idempotency_hash
        ingestion_event_data["pii_redacted_paths"] = list(boundary.redacted_paths)
        order_resolution_key = _extract_order_resolution_key(
            event_data=ingestion_event_data,
            identity_payload=identity_payload,
        )
        commerce_identity_provider = _first_non_empty_resolution_token(
            ingestion_event_data.get("provider"),
            ingestion_event_data.get("vendor"),
            identity_payload.get("provider"),
            source,
        ) or "unknown"
        click_resolution_key = _extract_click_resolution_key(
            event_data=ingestion_event_data,
            identity_payload=identity_payload,
        )
        start_time = time.perf_counter()
        try:
            event_authority_time = self._coerce_event_timestamp(
                ingestion_event_data.get("event_timestamp")
            )
        except ValidationError as exc:
            await self._route_validation_error_to_dlq(
                session=session,
                tenant_id=tenant_id,
                event_data=event_data,
                ingestion_event_data=ingestion_event_data,
                identity_payload=identity_payload,
                request_headers=request_headers,
                idempotency_key=idempotency_key,
                source=source,
                error=exc,
                start_time=start_time,
            )
            raise

        candidate_session_uuid = await resolve_session_candidate_with_ephemeral_substrate(
            session=session,
            tenant_id=tenant_id,
            candidate_session_id=raw_candidate_session_id,
            order_id=order_resolution_key,
            click_id=click_resolution_key,
            now=event_authority_time,
        )
        candidate_session_id = str(candidate_session_uuid) if candidate_session_uuid is not None else None

        # 1. Idempotency check - return existing event if duplicate
        existing = await self._check_duplicate(session, tenant_id, idempotency_key)
        if existing:
            await upsert_ephemeral_resolution_links(
                session=session,
                tenant_id=tenant_id,
                session_id=existing.session_id,
                order_id=order_resolution_key,
                click_id=click_resolution_key,
                source=source,
                now=existing.occurred_at,
            )
            logger.info(
                "duplicate_event_detected",
                extra={
                    "event": "duplicate_event_detected",
                    "idempotency_key": idempotency_key,
                    "existing_event_id": str(existing.id),
                    "tenant_id": str(tenant_id),
                    "vendor": ingestion_event_data.get("vendor", source),
                    "event_type": ingestion_event_data.get("event_type"),
                    **log_context(),
                }
            )
            # B0.5.6.3: No labels on event metrics (bounded cardinality)
            events_duplicate_total.inc()
            return IngestionDecision(
                event=existing,
                state=IngestionResultState.DUPLICATE,
            )

        session_resolution = await resolve_session_authority(
            session=session,
            tenant_id=tenant_id,
            candidate_session_id=candidate_session_id,
            source=source,
            now=event_authority_time,
        )
        ingestion_event_data["session_id"] = str(session_resolution.session_id)
        await upsert_ephemeral_resolution_links(
            session=session,
            tenant_id=tenant_id,
            session_id=session_resolution.session_id,
            order_id=order_resolution_key,
            click_id=click_resolution_key,
            source=source,
            now=event_authority_time,
        )

        try:
            # 2. Validate event schema
            validated = self._validate_schema(ingestion_event_data)

            # 3. Normalize channel (vendor indicator → canonical code)
            channel_code = normalize_channel(
                utm_source=ingestion_event_data.get("utm_source"),
                utm_medium=ingestion_event_data.get("utm_medium"),
                vendor=ingestion_event_data.get("vendor", source),
                tenant_id=str(tenant_id)
            )

            # 4. Create event entity
            durable_payload = minimize_event_payload_for_storage(
                {**boundary.sanitized_payload, "channel": channel_code}
            )
            event = AttributionEvent(
                id=uuid4(),
                tenant_id=tenant_id,
                idempotency_key=idempotency_key,
                channel=channel_code,
                event_type=validated["event_type"],
                event_timestamp=validated["event_timestamp"],
                occurred_at=validated["event_timestamp"],
                session_id=validated["session_id"],
                revenue_cents=validated["revenue_cents"],
                currency=validated.get("currency", "USD"),
                raw_payload=durable_payload,
                correlation_id=validated.get("correlation_id"),
                external_event_id=ingestion_event_data.get("external_event_id"),
                campaign_id=ingestion_event_data.get("campaign_id"),
                conversion_value_cents=ingestion_event_data.get("conversion_value_cents"),
                processing_status="pending",
                retry_count=0,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            normalized_headers = _normalized_request_headers(request_headers)
            persisted_ip_address, persisted_user_agent, persisted_raw_headers = (
                _raw_event_ingress_metadata_for_persistence(
                    source=source,
                    normalized_headers=normalized_headers,
                )
            )
            raw_event_payload = RawEventPayload(
                id=uuid4(),
                tenant_id=tenant_id,
                event_id=event.id,
                payload_json=boundary.sanitized_payload,
                lookup_hash=_lookup_hash_for_selector(idempotency_key),
                ip_address=persisted_ip_address,
                user_agent=persisted_user_agent,
                raw_headers=persisted_raw_headers,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            webhook_identity_payload = _extract_webhook_ingress_identity(
                source=source,
                event_data=ingestion_event_data,
                tenant_id=tenant_id,
                idempotency_key=idempotency_key,
                event_id=event.id,
                event_timestamp=validated["event_timestamp"],
            )

            # 5. Persist to database. Fast path: a single flush with no
            # extra reads on the hot path. Authenticated-root adoption
            # (Corrective VIII) is adjudicated ONLY on collision: a
            # colliding precursor is promoted to the authenticated values
            # (or the conflict is disposed explicitly); the authenticated
            # payload's sovereign values always win and a verified-vs-
            # verified mismatch never succeeds silently.
            #
            # B2.6-P2 Corrective XI: sessions without ingress authority
            # cannot author authenticity_verified. Such a verified
            # arrival (already HMAC-verified by this process) persists
            # in-transaction as an unverified precursor and finalizes
            # post-commit through the dedicated ingress credential
            # (witness + attestation), when the committed event row is
            # visible and the ingress FK holds. A separate connection
            # can never see the uncommitted event, so pre-commit
            # ingress writes are structurally impossible here.
            pending_finalization: dict[str, Any] | None = None
            session.add(event)
            session.add(raw_event_payload)
            if webhook_identity_payload is not None:
                session.add(
                    WebhookIngressIdentity(**webhook_identity_payload)
                )
            try:
                await session.flush()  # Trigger constraint validation before commit
            except Exception as flush_error:
                if webhook_identity_payload is None:
                    raise
                if _is_b26_p2_verified_authorship_error(flush_error):
                    await session.rollback()
                    session.add(event)
                    session.add(raw_event_payload)
                    session.add(
                        WebhookIngressIdentity(
                            **_precursor_payload(webhook_identity_payload)
                        )
                    )
                    await session.flush()
                    pending_finalization = _finalization_payload(
                        webhook_identity_payload,
                        auth_consequence,
                    )
                else:
                    adoption = _is_b26_p2_adoption_error(flush_error)
                    if adoption is None and not _is_ingress_collision_integrity_error(
                        flush_error
                    ):
                        raise
                    await session.rollback()
                    # Re-attach the pending entities after the rollback.
                    session.add(event)
                    session.add(raw_event_payload)
                    if adoption == "authenticated_conflict":
                        raise ValidationError(
                            "b26_p2_ingress_authenticated_conflict: a canonical"
                            " authenticated root already carries different"
                            " sovereign values for this identity"
                        ) from flush_error
                    adopted = await _adopt_or_promote_ingress(
                        session,
                        tenant_id=tenant_id,
                        incoming=webhook_identity_payload,
                        event_id=event.id,
                        auth_consequence=auth_consequence,
                    )
                    if adopted is None:
                        # Genuine concurrent-issue race with no precursor:
                        # if the winner already completed ingestion, this
                        # arrival is its duplicate (stable redrive path
                        # downstream). The winner's finalizer owns
                        # authority; this decision still carries a
                        # finalization so a crashed winner cannot strand
                        # the arrival (idempotent post-commit).
                        existing_event = await _fetch_existing_event_for_key(
                            session, tenant_id=tenant_id,
                            idempotency_key=idempotency_key,
                        )
                        if existing_event is not None:
                            events_duplicate_total.inc()
                            return IngestionDecision(
                                event=existing_event,
                                state=IngestionResultState.DUPLICATE,
                                ingress_finalization=(
                                    _finalization_payload(
                                        webhook_identity_payload,
                                        auth_consequence,
                                    )
                                    if _is_verified_intended(
                                        webhook_identity_payload
                                    )
                                    else None
                                ),
                            )
                        session.add(
                            WebhookIngressIdentity(**webhook_identity_payload)
                        )
                    try:
                        await session.flush()
                    except Exception as flush_tail_error:
                        if not (
                            _is_verified_intended(webhook_identity_payload)
                            and _is_b26_p2_verified_authorship_error(
                                flush_tail_error
                            )
                        ):
                            raise
                        # The adoption updated a precursor toward
                        # verified through a session that cannot author
                        # it (or a re-added verified payload collided
                        # with the authorship gate). Roll back to the
                        # committed precursor (or nothing) and let the
                        # idempotent post-commit finalizer converge it:
                        # it inserts when absent and promotes when
                        # pending, refusing genuine conflicts.
                        await session.rollback()
                        session.add(event)
                        session.add(raw_event_payload)
                        await session.flush()
                        pending_finalization = _finalization_payload(
                            webhook_identity_payload,
                            auth_consequence,
                        )
            if order_resolution_key is not None:
                await upsert_durable_commerce_identity_link(
                    session=session,
                    tenant_id=tenant_id,
                    attribution_event_id=event.id,
                    provider=commerce_identity_provider,
                    canonical_commerce_reference=order_resolution_key,
                    source=source,
                    observed_at=validated["event_timestamp"],
                )
            dirty_window_start = validated["event_timestamp"].replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
            await append_dirty_event(
                session,
                tenant_id=tenant_id,
                source_window_start=dirty_window_start,
                source_window_end=dirty_window_start + timedelta(days=1),
                dirty_reason="attribution_event_ingested",
                source_family="attribution_events",
                source_event_id=event.id,
                observed_at=validated["event_timestamp"],
            )

            logger.info(
                "event_ingested",
                extra={
                    "event": "event_ingested",
                    "event_id": str(event.id),
                    "idempotency_key": idempotency_key,
                    "channel": channel_code,
                    "event_type": event.event_type,
                    "revenue_cents": event.revenue_cents,
                    "tenant_id": str(tenant_id),
                    "vendor": ingestion_event_data.get("vendor", source),
                    "correlation_id_business": idempotency_key,
                    **log_context(),
                }
            )
            duration = time.perf_counter() - start_time
            # B0.5.6.3: No labels on event metrics (bounded cardinality)
            events_ingested_total.inc()
            ingestion_duration_seconds.observe(duration)
            return IngestionDecision(
                event=event,
                state=IngestionResultState.INSERTED,
                ingress_finalization=pending_finalization,
            )

        except ValidationError as e:
            await self._route_validation_error_to_dlq(
                session=session,
                tenant_id=tenant_id,
                event_data=event_data,
                ingestion_event_data=ingestion_event_data,
                identity_payload=identity_payload,
                request_headers=request_headers,
                idempotency_key=idempotency_key,
                source=source,
                error=e,
                start_time=start_time,
            )
            raise  # Re-raise to signal failure to caller

        except IntegrityError as e:
            # Idempotency races: concurrent inserts may bypass the pre-check.
            if not _is_idempotency_duplicate_integrity_error(e):
                raise

            await session.rollback()
            existing_after_race = await _fetch_existing_event_for_key(
                session, tenant_id=tenant_id, idempotency_key=idempotency_key
            )
            if existing_after_race:
                logger.info(
                    "duplicate_event_detected_race",
                    extra={
                        "event": "duplicate_event_detected_race",
                        "idempotency_key": idempotency_key,
                        "existing_event_id": str(existing_after_race.id),
                        "tenant_id": str(tenant_id),
                        "vendor": ingestion_event_data.get("vendor", source),
                        "event_type": ingestion_event_data.get("event_type"),
                        **log_context(),
                    },
                )
                # B0.5.6.3: No labels on event metrics (bounded cardinality)
                events_duplicate_total.inc()
                return IngestionDecision(
                    event=existing_after_race,
                    state=IngestionResultState.DUPLICATE,
                )

            raise
        except ProgrammingError as e:
            if _is_missing_webhook_identity_relation_error(e):
                raise AuthoritativeIngressInvariantError(
                    "Canonical webhook identity substrate is unavailable for authoritative ingress "
                    f"(source={source}, tenant_id={tenant_id}, idempotency_key={idempotency_key})."
                ) from e
            if _is_missing_attribution_commerce_identity_relation_error(e):
                raise AuthoritativeIngressInvariantError(
                    "B2.3-P0 delayed-arrival commerce identity substrate is unavailable for "
                    f"authoritative ingestion (source={source}, tenant_id={tenant_id}, "
                    f"idempotency_key={idempotency_key})."
                ) from e
            raise

    async def ingest_event(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        event_data: dict,
        idempotency_key: str,
        source: str = "webhook",
        identity_payload: Mapping[str, Any] | None = None,
        request_headers: Mapping[str, str] | None = None,
    ) -> AttributionEvent:
        """
        Backward-compatible API returning only the ingestion event.
        """
        decision = await self.ingest_event_with_decision(
            session=session,
            tenant_id=tenant_id,
            event_data=event_data,
            idempotency_key=idempotency_key,
            source=source,
            identity_payload=identity_payload,
            request_headers=request_headers,
        )
        return decision.event

    async def _check_duplicate(
        self, session: AsyncSession, tenant_id: UUID, idempotency_key: str
    ) -> Optional[AttributionEvent]:
        """
        Check if event with given idempotency key already exists.

        Uses database query (no cache) for authoritative deduplication.
        RLS ensures tenant isolation (only returns events for current tenant).

        Args:
            session: Database session with RLS context
            idempotency_key: Deduplication key to check

        Returns:
            Existing AttributionEvent or None if not found
        """
        result = await session.execute(
            select(AttributionEvent).where(
                AttributionEvent.tenant_id == tenant_id,
                AttributionEvent.idempotency_key == idempotency_key,
            )
        )
        return result.scalar_one_or_none()

    def _validate_schema(self, event_data: dict) -> dict:
        """
        Validate event data against required schema.

        Required Fields:
            - event_type: Event classification (conversion, click, etc.)
            - event_timestamp: ISO 8601 timestamp
            - revenue_amount: Decimal revenue value
            - session_id: UUID session identifier

        Args:
            event_data: Raw event payload

        Returns:
            Validated and normalized event data

        Raises:
            ValidationError: Missing required field or invalid type
        """
        validated = {}

        # Required: event_type
        if "event_type" not in event_data or not event_data["event_type"]:
            raise ValidationError("Missing required field: event_type")
        validated["event_type"] = str(event_data["event_type"])

        # Required: event_timestamp
        if "event_timestamp" not in event_data:
            raise ValidationError("Missing required field: event_timestamp")
        validated["event_timestamp"] = self._coerce_event_timestamp(
            event_data["event_timestamp"]
        )

        # Required: revenue_amount (convert to cents)
        if "revenue_amount" not in event_data:
            raise ValidationError("Missing required field: revenue_amount")
        try:
            revenue_decimal = Decimal(str(event_data["revenue_amount"]))
            validated["revenue_cents"] = int(revenue_decimal * 100)
        except (InvalidOperation, ValueError, TypeError) as e:
            raise ValidationError(f"Invalid revenue_amount: {e}")

        # Required: session_id
        if "session_id" not in event_data:
            raise ValidationError("Missing required field: session_id")
        try:
            # Accept UUID object or string
            if isinstance(event_data["session_id"], UUID):
                validated["session_id"] = event_data["session_id"]
            else:
                validated["session_id"] = UUID(str(event_data["session_id"]))
        except (ValueError, TypeError) as e:
            raise ValidationError(f"Invalid session_id format: {e}")

        # Optional: currency (default USD)
        validated["currency"] = event_data.get("currency", "USD")

        # Optional: correlation_id
        if "correlation_id" in event_data and event_data["correlation_id"]:
            try:
                if isinstance(event_data["correlation_id"], UUID):
                    validated["correlation_id"] = event_data["correlation_id"]
                else:
                    validated["correlation_id"] = UUID(str(event_data["correlation_id"]))
            except (ValueError, TypeError):
                # Ignore invalid correlation_id (optional field)
                validated["correlation_id"] = None
        else:
            validated["correlation_id"] = None

        return validated

    @staticmethod
    def _coerce_event_timestamp(value: object) -> datetime:
        """Return an authenticated event time as a timezone-aware UTC value."""

        try:
            parsed = (
                value
                if isinstance(value, datetime)
                else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            )
        except (ValueError, TypeError) as exc:
            raise ValidationError(f"Invalid event_timestamp format: {exc}") from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    async def _route_to_dlq(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        event_data: dict,
        error_type: str,
        error_message: str,
        source: str,
        error_traceback: Optional[str] = None,
        identity_payload: Mapping[str, Any] | None = None,
        request_headers: Mapping[str, str] | None = None,
    ) -> DeadEvent:
        """
        Route failed event to dead-letter queue with enhanced error classification.

        B0.4.4 Enhancement: Uses DLQHandler for error classification and retry support.
        Backward compatible with B0.4.3 call sites.

        Args:
            session: Database session with RLS context
            tenant_id: Tenant UUID
            event_data: Raw event payload (failed validation)
            error_type: Error classification (e.g., 'validation_error')
            error_message: Human-readable error description
            source: Event source identifier
            error_traceback: Optional stack trace
            identity_payload: Full inbound payload used for hash + pseudonymization.
            request_headers: Request headers used for pseudonymization entropy.

        Returns:
            DeadEvent instance with error classification and retry metadata
        """
        # Create exception object from error message for classification
        # This allows DLQHandler to classify errors properly
        if "ValidationError" in error_message or error_type == "validation_error":
            error = ValidationError(error_message)
        elif "IntegrityError" in error_message or "foreign key" in error_message.lower():
            error = IntegrityError(error_message, None, None)
        else:
            error = Exception(error_message)

        # Use enhanced DLQHandler for routing with classification
        correlation_id = (
            event_data.get("correlation_id")
            or event_data.get("idempotency_key")
            or event_data.get("external_event_id")
            or str(uuid4())
        )

        dead_event = await self.dlq_handler.route_to_dlq(
            session=session,
            tenant_id=tenant_id,
            original_payload=event_data,
            error=error,
            correlation_id=correlation_id,
            source=source,
            identity_payload=identity_payload,
            request_headers=request_headers,
        )

        return dead_event

    async def _route_validation_error_to_dlq(
        self,
        *,
        session: AsyncSession,
        tenant_id: UUID,
        event_data: dict,
        ingestion_event_data: Mapping[str, Any],
        identity_payload: Mapping[str, Any],
        request_headers: Mapping[str, str] | None,
        idempotency_key: str,
        source: str,
        error: ValidationError,
        start_time: float,
    ) -> None:
        """Persist a validation failure before returning it to the caller."""

        logger.warning(
            "validation_error_routed_to_dlq",
            extra={
                "event": "validation_error_routed_to_dlq",
                "error": str(error),
                "idempotency_key": idempotency_key,
                "source": source,
                "tenant_id": str(tenant_id),
                "vendor": ingestion_event_data.get("vendor", source),
                "event_type": ingestion_event_data.get("event_type"),
                "correlation_id_business": idempotency_key,
                **log_context(),
            },
        )
        await self._route_to_dlq(
            session=session,
            tenant_id=tenant_id,
            event_data=event_data,
            error_type="validation_error",
            error_message=str(error),
            source=source,
            identity_payload=identity_payload,
            request_headers=request_headers,
        )
        events_dlq_total.inc()
        ingestion_duration_seconds.observe(time.perf_counter() - start_time)


# Transaction Wrapper for External API


async def ingest_with_transaction(
    tenant_id: UUID,
    event_data: dict,
    idempotency_key: str,
    source: str = "webhook",
    identity_payload: Mapping[str, Any] | None = None,
    request_headers: Mapping[str, str] | None = None,
    auth_consequence: Mapping[str, Any] | None = None,
) -> IngestionTransactionResult:
    """
    Transactional wrapper for event ingestion.

    Manages session lifecycle: RLS context, commit on success, rollback on error.
    Recommended entry point for API routes and webhook handlers.

    Args:
        tenant_id: Tenant UUID (from auth context or API key)
        event_data: Raw event payload (PII-stripped)
        idempotency_key: Deduplication key
        source: Event source identifier
        auth_consequence: B2.6-P2 Corrective XII predecessor event P from
            successful provider-signature verification. Webhook handlers
            pass it; other callers leave None (verified finalization then
            fails closed while unverified ingestion is unaffected).

    Returns:
        IngestionTransactionResult runtime boundary object.

    Raises:
        Exception: Database errors, unexpected failures
    """
    from app.db.session import get_session

    async with get_session(tenant_id=tenant_id) as session:
        try:
            service = EventIngestionService()
            decision = await service.ingest_event_with_decision(
                session=session,
                tenant_id=tenant_id,
                event_data=event_data,
                idempotency_key=idempotency_key,
                source=source,
                identity_payload=identity_payload,
                request_headers=request_headers,
                auth_consequence=auth_consequence,
            )
            # Commit handled by get_session context manager.
            # B2.6-P2 Corrective XI: verified-ingress finalization
            # runs AFTER commit (see IngestionDecision): the
            # ingress-credential connection can only observe
            # committed rows, and only then does the ingress FK hold.
            # A finalizer failure propagates like any post-commit
            # error (provider retry replays into the idempotent
            # finalizer through the duplicate path).
            pending = decision.ingress_finalization
        except ValidationError as e:
            # Validation error already routed to DLQ
            # Session commits DLQ entry (handled by context manager)
            logger.info(
                "Ingestion failed - validation error",
                extra={"error": str(e), "tenant_id": str(tenant_id)}
            )
            return IngestionTransactionResult(
                error_type="validation_error",
                error=str(e),
            )

        except IntegrityError as e:
            # Idempotency races can surface here if callers bypass service-level handling.
            if _is_idempotency_duplicate_integrity_error(e):
                await session.rollback()
                existing = await _fetch_existing_event_for_key(
                    session, tenant_id=tenant_id, idempotency_key=idempotency_key
                )
                if existing:
                    return IngestionTransactionResult(
                        decision=IngestionDecision(
                            event=existing,
                            state=IngestionResultState.DUPLICATE,
                        )
                    )

            # Database constraint violation (should be rare with validation)
            await session.rollback()
            logger.error(
                "Ingestion failed - integrity error",
                extra={"error": str(e), "tenant_id": str(tenant_id)},
                exc_info=True,
            )
            raise

        except Exception as e:
            # Unexpected error - rollback and propagate
            await session.rollback()
            logger.error(
                "Ingestion failed - unexpected error",
                extra={"error": str(e), "tenant_id": str(tenant_id)},
                exc_info=True,
            )
            raise

    # The session committed on context exit. Complete deferred
    # verified-ingress authority, if any, through the dedicated
    # ingress credential (committed visibility for the FK).
    if pending:
        await _finalize_verified_ingress_post_commit(pending)
    return IngestionTransactionResult(decision=decision)
