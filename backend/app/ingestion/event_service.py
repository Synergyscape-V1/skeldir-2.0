"""
Event Ingestion Service - B0.4.3 Core Implementation + B0.4.4 DLQ Enhancement

Provides idempotent event ingestion with channel normalization, validation,
and dead-letter queue routing for failed events.

B0.4.4 Enhancement: Integrated DLQHandler with error classification and retry logic.
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import time
from typing import Dict, Optional
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.channel_normalization import normalize_channel
from app.ingestion.dlq_handler import DLQHandler
from app.models import AttributionEvent, DeadEvent
from app.observability.context import log_context
from app.observability.metrics import (
    events_dlq_total,
    events_duplicate_total,
    events_ingested_total,
    ingestion_duration_seconds,
)

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when event data fails validation"""
    pass


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

    async def ingest_event(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        event_data: dict,
        idempotency_key: str,
        source: str = "webhook"
    ) -> AttributionEvent:
        """
        Ingest event with idempotency guarantee and validation.

        Args:
            session: Database session with RLS context set (app.current_tenant_id)
            tenant_id: Tenant UUID for event ownership
            event_data: Raw event payload (PII-stripped by middleware)
            idempotency_key: Deduplication key (e.g., external_event_id)
            source: Event source identifier (e.g., 'shopify', 'stripe')

        Returns:
            AttributionEvent instance (new or existing if duplicate)

        Raises:
            ValidationError: Event data fails schema validation (routes to DLQ)
            IntegrityError: Database constraint violation (should not occur with proper validation)

        Idempotency Guarantee:
            Duplicate idempotency_key returns existing event without insert.
            Database UNIQUE constraint enforces deduplication at persistence layer.
        """
        # 1. Idempotency check - return existing event if duplicate
        existing = await self._check_duplicate(session, idempotency_key)
        if existing:
            logger.info(
                "duplicate_event_detected",
                extra={
                    "event": "duplicate_event_detected",
                    "idempotency_key": idempotency_key,
                    "existing_event_id": str(existing.id),
                    "tenant_id": str(tenant_id),
                    "vendor": event_data.get("vendor", source),
                    "event_type": event_data.get("event_type"),
                    **log_context(),
                }
            )
            events_duplicate_total.labels(
                tenant_id=str(tenant_id),
                vendor=event_data.get("vendor", source),
                event_type=event_data.get("event_type", "unknown"),
                error_type="duplicate",
            ).inc()
            return existing

        start_time = time.perf_counter()
        try:
            # 2. Validate event schema
            validated = self._validate_schema(event_data)

            # 3. Normalize channel (vendor indicator → canonical code)
            channel_code = normalize_channel(
                utm_source=event_data.get("utm_source"),
                utm_medium=event_data.get("utm_medium"),
                vendor=event_data.get("vendor", source),
                tenant_id=str(tenant_id)
            )

            # 4. Create event entity
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
                raw_payload=event_data,
                correlation_id=validated.get("correlation_id"),
                external_event_id=event_data.get("external_event_id"),
                campaign_id=event_data.get("campaign_id"),
                conversion_value_cents=event_data.get("conversion_value_cents"),
                processing_status="pending",
                retry_count=0,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )

            # 5. Persist to database
            session.add(event)
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
                    "vendor": event_data.get("vendor", source),
                    "correlation_id_business": idempotency_key,
                    **log_context(),
                }
            )
            duration = time.perf_counter() - start_time
            events_ingested_total.labels(
                tenant_id=str(tenant_id),
                vendor=event_data.get("vendor", source),
                event_type=validated["event_type"],
                error_type="none",
            ).inc()
            ingestion_duration_seconds.labels(
                tenant_id=str(tenant_id),
                vendor=event_data.get("vendor", source),
                event_type=validated["event_type"],
                error_type="none",
            ).observe(duration)

            return event

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
                    "vendor": event_data.get("vendor", source),
                    "event_type": event_data.get("event_type"),
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
            )
            duration = time.perf_counter() - start_time
            events_dlq_total.labels(
                tenant_id=str(tenant_id),
                vendor=event_data.get("vendor", source),
                event_type=event_data.get("event_type", "unknown"),
                error_type="validation_error",
            ).inc()
            ingestion_duration_seconds.labels(
                tenant_id=str(tenant_id),
                vendor=event_data.get("vendor", source),
                event_type=event_data.get("event_type", "unknown"),
                error_type="validation_error",
            ).observe(duration)
            raise  # Re-raise to signal failure to caller

    async def _check_duplicate(
        self, session: AsyncSession, idempotency_key: str
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
                AttributionEvent.idempotency_key == idempotency_key
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
        correlation_id = event_data.get("idempotency_key") or event_data.get("external_event_id") or str(uuid4())

        dead_event = await self.dlq_handler.route_to_dlq(
            session=session,
            tenant_id=tenant_id,
            original_payload=event_data,
            error=error,
            correlation_id=correlation_id,
            source=source,
        )

        return dead_event


# Transaction Wrapper for External API


async def ingest_with_transaction(
    tenant_id: UUID,
    event_data: dict,
    idempotency_key: str,
    source: str = "webhook"
) -> Dict[str, any]:
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
        dict with keys:
            - status: 'success' or 'error'
            - event_id: UUID string (if success)
            - channel: Canonical channel code (if success)
            - error: Error message (if error)
            - dlq_event_id: Dead event UUID (if validation error)

    Raises:
        Exception: Database errors, unexpected failures
    """
    from app.db.session import get_session

    async with get_session(tenant_id=tenant_id) as session:
        try:
            service = EventIngestionService()
            event = await service.ingest_event(
                session=session,
                tenant_id=tenant_id,
                event_data=event_data,
                idempotency_key=idempotency_key,
                source=source,
            )

            # Commit handled by get_session context manager
            return {
                "status": "success",
                "event_id": str(event.id),
                "channel": event.channel,
                "idempotency_key": event.idempotency_key,
            }

        except ValidationError as e:
            # Validation error already routed to DLQ
            # Session commits DLQ entry (handled by context manager)
            logger.info(
                "Ingestion failed - validation error",
                extra={"error": str(e), "tenant_id": str(tenant_id)}
            )
            return {
                "status": "error",
                "error_type": "validation_error",
                "error": str(e),
            }

        except IntegrityError as e:
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
