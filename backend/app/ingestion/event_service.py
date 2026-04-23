"""
Event Ingestion Service - B0.4.3 Core Implementation + B0.4.4 DLQ Enhancement

Provides idempotent event ingestion with channel normalization, validation,
and dead-letter queue routing for failed events.

B0.4.4 Enhancement: Integrated DLQHandler with error classification and retry logic.
"""

import logging
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
import time
from typing import Any, Mapping, Optional
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.channel_normalization import normalize_channel
from app.ingestion.dlq_handler import DLQHandler
from app.ingestion.privacy_boundary import enforce_ingress_privacy_boundary
from app.models import AttributionEvent, DeadEvent, RawEventPayload, WebhookIngressIdentity
from app.observability.context import log_context
from app.privacy.authority import minimize_event_payload_for_storage
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
    ) -> IngestionDecision:
        """
        Ingest event with idempotency guarantee and validation.

        Args:
            session: Database session with RLS context set (app.current_tenant_id)
            tenant_id: Tenant UUID for event ownership
            event_data: Event payload targeted for storage assembly.
            idempotency_key: Deduplication key (e.g., external_event_id)
            source: Event source identifier (e.g., 'shopify', 'stripe')

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
        click_resolution_key = _extract_click_resolution_key(
            event_data=ingestion_event_data,
            identity_payload=identity_payload,
        )

        candidate_session_uuid = await resolve_session_candidate_with_ephemeral_substrate(
            session=session,
            tenant_id=tenant_id,
            candidate_session_id=raw_candidate_session_id,
            order_id=order_resolution_key,
            click_id=click_resolution_key,
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
        )
        ingestion_event_data["session_id"] = str(session_resolution.session_id)
        await upsert_ephemeral_resolution_links(
            session=session,
            tenant_id=tenant_id,
            session_id=session_resolution.session_id,
            order_id=order_resolution_key,
            click_id=click_resolution_key,
            source=source,
        )

        start_time = time.perf_counter()
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
            webhook_ingress_identity = None
            webhook_identity_payload = _extract_webhook_ingress_identity(
                source=source,
                event_data=ingestion_event_data,
                tenant_id=tenant_id,
                idempotency_key=idempotency_key,
                event_id=event.id,
                event_timestamp=validated["event_timestamp"],
            )
            if webhook_identity_payload is not None:
                webhook_ingress_identity = WebhookIngressIdentity(
                    **webhook_identity_payload
                )

            # 5. Persist to database
            session.add(event)
            session.add(raw_event_payload)
            if webhook_ingress_identity is not None:
                session.add(webhook_ingress_identity)
            await session.flush()  # Trigger constraint validation before commit

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
            )

        except ValidationError as e:
            # Route validation failures to dead-letter queue
            logger.warning(
                "validation_error_routed_to_dlq",
                extra={
                    "event": "validation_error_routed_to_dlq",
                    "error": str(e),
                    "idempotency_key": idempotency_key,
                    "source": source,
                    "tenant_id": str(tenant_id),
                    "vendor": ingestion_event_data.get("vendor", source),
                    "event_type": ingestion_event_data.get("event_type"),
                    "correlation_id_business": idempotency_key,
                    **log_context(),
                }
            )
            await self._route_to_dlq(
                session=session,
                tenant_id=tenant_id,
                event_data=event_data,
                error_type="validation_error",
                error_message=str(e),
                source=source,
                identity_payload=identity_payload,
                request_headers=request_headers,
            )
            duration = time.perf_counter() - start_time
            # B0.5.6.3: No labels on event metrics (bounded cardinality)
            events_dlq_total.inc()
            ingestion_duration_seconds.observe(duration)
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
        try:
            # Accept datetime object or ISO string
            if isinstance(event_data["event_timestamp"], datetime):
                validated["event_timestamp"] = event_data["event_timestamp"]
            else:
                validated["event_timestamp"] = datetime.fromisoformat(
                    str(event_data["event_timestamp"]).replace("Z", "+00:00")
                )
        except (ValueError, TypeError) as e:
            raise ValidationError(f"Invalid event_timestamp format: {e}")

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


# Transaction Wrapper for External API


async def ingest_with_transaction(
    tenant_id: UUID,
    event_data: dict,
    idempotency_key: str,
    source: str = "webhook",
    identity_payload: Mapping[str, Any] | None = None,
    request_headers: Mapping[str, str] | None = None,
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
            )
            # Commit handled by get_session context manager
            return IngestionTransactionResult(decision=decision)

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
