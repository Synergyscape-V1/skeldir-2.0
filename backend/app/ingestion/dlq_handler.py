"""
DLQ (Dead Letter Queue) Handler with Error Classification and Retry Logic

Provides error classification, exponential backoff retry mechanism, and
remediation status state machine for failed event ingestion.

Related: B0.4.4 DLQ Handler Enhancement
"""
import traceback
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError, OperationalError

from app.observability.context import log_context
from app.observability.api_metrics import events_dlq_total
from app.db.session import engine
from sqlalchemy import text

try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class ErrorType(str, Enum):
    """Error type classification for DLQ routing."""
    SCHEMA_VALIDATION = "schema_validation"
    FK_CONSTRAINT = "fk_constraint"
    DUPLICATE_KEY = "duplicate_key"
    DATABASE_TIMEOUT = "database_timeout"
    NETWORK_ERROR = "network_error"
    PII_VIOLATION = "pii_violation"
    UNKNOWN = "unknown"


class ErrorClassification(str, Enum):
    """Error retriability classification."""
    TRANSIENT = "transient"    # Retryable (temporary issue)
    PERMANENT = "permanent"    # Not retryable (data/logic error)
    UNKNOWN = "unknown"        # Default to transient (safe)


class RemediationStatus(str, Enum):
    """
    Remediation status state machine states.

    Note: Maps to database CHECK constraint values:
        - pending → pending
        - in_progress → retrying/manual_review
        - resolved → resolved
        - abandoned → max_retries_exceeded/ignored
    """
    PENDING = "pending"              # Initial state
    RETRYING = "in_progress"         # Retry in progress (maps to 'in_progress')
    RESOLVED = "resolved"            # Successfully reprocessed
    MAX_RETRIES_EXCEEDED = "abandoned"  # Gave up after max attempts (maps to 'abandoned')
    MANUAL_REVIEW = "in_progress"    # Needs human intervention (maps to 'in_progress')
    IGNORED = "abandoned"            # Intentionally skipped (maps to 'abandoned')


# Remediation status state machine transitions
# Note: Since RETRYING=MANUAL_REVIEW='in_progress' and MAX_RETRIES_EXCEEDED=IGNORED='abandoned',
# we define transitions using the enum values (which map to database values)
VALID_TRANSITIONS = {
    "pending": {
        "in_progress",  # RETRYING or MANUAL_REVIEW
        "abandoned",    # MAX_RETRIES_EXCEEDED or IGNORED
    },
    "in_progress": {
        "resolved",     # RESOLVED
        "abandoned",    # MAX_RETRIES_EXCEEDED or IGNORED
        "pending",      # Back to pending if retry fails
    },
    "abandoned": {
        "in_progress",  # Manual retry initiated (MANUAL_REVIEW)
        "resolved",     # Manual retry succeeded
    },
    # Terminal state
    "resolved": set(),
}


def classify_error(error: Exception) -> tuple[ErrorType, ErrorClassification]:
    """
    Classify exception into error type and retriability.

    Args:
        error: Exception raised during event ingestion

    Returns:
        Tuple of (error_type, classification)

    Classification Logic:
        - ValueError/KeyError: Schema validation errors (transient - data may be corrected)
        - IntegrityError (FK): Foreign key violations (permanent - referential integrity)
        - IntegrityError (unique): Duplicate key violations (permanent - idempotency hit)
        - OperationalError (timeout): Database timeouts (transient - retry may succeed)
        - PII detection: PII key found in payload (permanent - security violation)
        - Unknown: Default to transient (safe - allows retry)
    """
    error_msg = str(error).lower()

    # Schema validation errors (missing/invalid fields)
    if isinstance(error, (ValueError, KeyError)):
        return ErrorType.SCHEMA_VALIDATION, ErrorClassification.TRANSIENT

    # Database integrity violations
    if isinstance(error, IntegrityError):
        if 'foreign key' in error_msg or 'fk_' in error_msg:
            return ErrorType.FK_CONSTRAINT, ErrorClassification.PERMANENT
        if 'duplicate' in error_msg or 'unique' in error_msg:
            return ErrorType.DUPLICATE_KEY, ErrorClassification.PERMANENT

    # Database operational errors
    if isinstance(error, OperationalError):
        if 'timeout' in error_msg or 'timed out' in error_msg:
            return ErrorType.DATABASE_TIMEOUT, ErrorClassification.TRANSIENT
        if 'connection' in error_msg or 'network' in error_msg:
            return ErrorType.NETWORK_ERROR, ErrorClassification.TRANSIENT

    # PII violations (from database trigger)
    if 'pii' in error_msg and 'detected' in error_msg:
        return ErrorType.PII_VIOLATION, ErrorClassification.PERMANENT

    # Unknown errors: Default to transient (allows retry, safe fallback)
    return ErrorType.UNKNOWN, ErrorClassification.TRANSIENT


def validate_status_transition(current: str, new: str) -> bool:
    """
    Validate remediation status state machine transition.

    Args:
        current: Current remediation status (database value)
        new: Proposed new status (database value)

    Returns:
        True if transition is valid, False otherwise
    """
    # Validate using string values (database constraint values)
    if current not in VALID_TRANSITIONS:
        # Terminal state (resolved) - can only stay in same state
        return new == current

    return new in VALID_TRANSITIONS[current]


class DLQHandler:
    """
    Dead Letter Queue handler with retry logic and error classification.

    Provides:
    - Error classification (transient vs. permanent)
    - Exponential backoff retry strategy
    - Remediation status state machine
    - Max retry enforcement
    """

    MAX_RETRIES = 3
    BACKOFF_MULTIPLIER = 2
    INITIAL_DELAY_SECONDS = 60

    async def route_to_dlq(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        original_payload: dict,
        error: Exception,
        correlation_id: str,
        source: str = "ingestion_service"
    ) -> "DeadEvent":
        """
        Route failed event to dead_events table with error classification.

        Args:
            session: Database session (tenant context already set)
            tenant_id: Tenant UUID
            original_payload: Original event data that failed ingestion
            error: Exception that caused failure
            correlation_id: Idempotency key or unique identifier
            source: Source system identifier

        Returns:
            DeadEvent ORM instance

        Side Effects:
            - Inserts row into dead_events table
            - Logs error event
            - Captures full traceback for debugging
        """
        from app.models.dead_event import DeadEvent
        from uuid import uuid4

        error_type, classification = classify_error(error)

        # Convert correlation_id to UUID if it's a string (or None if invalid)
        correlation_uuid = None
        if correlation_id:
            try:
                if isinstance(correlation_id, UUID):
                    correlation_uuid = correlation_id
                else:
                    correlation_uuid = UUID(str(correlation_id))
            except (ValueError, TypeError):
                # Invalid UUID format - leave as None
                correlation_uuid = None

        dead_event = DeadEvent(
            id=uuid4(),
            tenant_id=tenant_id,
            source=source,
            raw_payload=original_payload,
            correlation_id=correlation_uuid,
            error_type=error_type.value,
            error_code=type(error).__name__,
            error_detail={"error": str(error)[:500]},  # JSONB field requires dict
            error_message=str(error)[:500],  # Text field for error message
            error_traceback=traceback.format_exc()[:2000] if traceback.format_exc() != 'NoneType: None\n' else None,
            event_type=original_payload.get("event_type", "unknown"),
            retry_count=0,
            remediation_status=RemediationStatus.PENDING.value,
            ingested_at=datetime.now(timezone.utc),
        )

        session.add(dead_event)
        await session.flush()

        # B0.5.6.3: No labels on event metrics (bounded cardinality)
        events_dlq_total.inc()

        ctx = log_context()
        ctx.update(
            {
                "dead_event_id": str(dead_event.id),
                "tenant_id": str(tenant_id),
                "error_type": error_type.value,
                "error_code": dead_event.error_code,
                "classification": classification.value,
                "correlation_id_business": correlation_id,
                "event": "event_routed_to_dlq",
                "vendor": source or "unknown",
                "event_type": (original_payload or {}).get("event_type", "unknown"),
            }
        )
        # High-volume expected ingress failures (schema/PII) should not emit
        # error-level logs per event; metrics + dead_events rows are the
        # authoritative signal.
        if error_type in {ErrorType.SCHEMA_VALIDATION, ErrorType.PII_VIOLATION}:
            logger.debug("event_routed_to_dlq", extra=ctx)
        elif classification == ErrorClassification.TRANSIENT:
            logger.warning("event_routed_to_dlq", extra=ctx)
        else:
            logger.error("event_routed_to_dlq", extra=ctx)

        return dead_event


    async def retry_dead_event(
        self,
        session: AsyncSession,
        dead_event_id: UUID,
        force_retry: bool = False
    ) -> tuple[bool, str]:
        """
        Retry failed event with exponential backoff strategy.

        Args:
            session: Database session (tenant context already set)
            dead_event_id: UUID of DeadEvent to retry
            force_retry: If True, bypass permanent error check (manual override)

        Returns:
            Tuple of (success: bool, message: str)

        Retry Logic:
            1. Check max retries not exceeded
            2. Check backoff delay elapsed
            3. Attempt re-ingestion via EventIngestionService
            4. On success: Mark resolved
            5. On failure: Increment counter, update last_retry_at

        Exponential Backoff:
            - Retry 1: 60 seconds after initial failure
            - Retry 2: 120 seconds after retry 1
            - Retry 3: 240 seconds after retry 2
        """
        from app.models.dead_event import DeadEvent

        dead_event = await session.get(DeadEvent, dead_event_id)
        if not dead_event:
            return False, "Dead event not found"

        # Check max retries
        if dead_event.retry_count >= self.MAX_RETRIES:
            if dead_event.remediation_status != RemediationStatus.MAX_RETRIES_EXCEEDED.value:
                dead_event.remediation_status = RemediationStatus.MAX_RETRIES_EXCEEDED.value
                await session.flush()

            if not force_retry:
                return False, f"Max retries ({self.MAX_RETRIES}) exceeded. Use force_retry=True to override."

        # Check permanent error classification
        if not force_retry:
            error_msg = dead_event.error_message
            if dead_event.error_code == "IntegrityError":
                error_dummy = IntegrityError(error_msg, None, None)
            else:
                error_dummy = Exception(error_msg)
            _, classification = classify_error(error_dummy)

            if classification == ErrorClassification.PERMANENT:
                msg = f"Permanent error ({dead_event.error_type}). Use force_retry=True to override."
                return False, msg

        # Check backoff delay
        if dead_event.last_retry_at:
            delay = self._calculate_backoff(dead_event.retry_count)
            next_retry = dead_event.last_retry_at + timedelta(seconds=delay)
            if datetime.now(timezone.utc) < next_retry and not force_retry:
                return False, f"Retry scheduled for {next_retry.isoformat()}. {int((next_retry - datetime.now(timezone.utc)).total_seconds())}s remaining."

        # Update status to retrying
        if validate_status_transition(dead_event.remediation_status, RemediationStatus.RETRYING.value):
            dead_event.remediation_status = RemediationStatus.RETRYING.value
            await session.flush()

        # Attempt re-ingestion
        from app.ingestion.event_service import EventIngestionService
        service = EventIngestionService()

        try:
            event = await service.ingest_event(
                session=session,
                tenant_id=dead_event.tenant_id,
                event_data=dead_event.raw_payload,
            )

            # Success - mark resolved
            dead_event.remediation_status = RemediationStatus.RESOLVED.value
            dead_event.resolved_at = datetime.now(timezone.utc)
            dead_event.remediation_notes = f"Retry succeeded: event_id={event.id}"
            await session.flush()

            logger.info(
                "dead_event_retry_success",
                dead_event_id=str(dead_event_id),
                event_id=str(event.id),
                retry_count=dead_event.retry_count,
            )

            return True, f"Resolved: event_id={event.id}"

        except Exception as e:
            # Retry failed - increment counter
            dead_event.retry_count += 1
            dead_event.last_retry_at = datetime.now(timezone.utc)
            dead_event.remediation_status = RemediationStatus.PENDING.value  # Back to pending
            dead_event.remediation_notes = f"Retry {dead_event.retry_count} failed: {str(e)[:200]}"
            await session.flush()

            logger.warning(
                "dead_event_retry_failed",
                dead_event_id=str(dead_event_id),
                retry_count=dead_event.retry_count,
                error=str(e)[:200],
            )

            return False, f"Retry {dead_event.retry_count}/{self.MAX_RETRIES} failed: {str(e)[:100]}"

    def _calculate_backoff(self, retry_count: int) -> int:
        """
        Calculate exponential backoff delay in seconds.

        Args:
            retry_count: Current retry attempt number (0-indexed)

        Returns:
            Delay in seconds before next retry

        Formula:
            delay = INITIAL_DELAY_SECONDS * (BACKOFF_MULTIPLIER ^ retry_count)

        Examples:
            retry_count=0: 60 * (2^0) = 60 seconds
            retry_count=1: 60 * (2^1) = 120 seconds
            retry_count=2: 60 * (2^2) = 240 seconds
        """
        return self.INITIAL_DELAY_SECONDS * (self.BACKOFF_MULTIPLIER ** retry_count)


async def route_unresolved_tenant_to_quarantine(
    *,
    source: str,
    payload: dict,
    error_message: str,
    error_type: str = "unresolved_tenant",
    correlation_id: str | None = None,
) -> None:
    """
    Write unresolved-tenant events into the quarantine DLQ lane.

    This path intentionally does not require tenant context and is restricted by
    RLS policies to write-only for app runtime roles and read-only for ops role.
    """
    correlation_uuid = None
    if correlation_id:
        try:
            correlation_uuid = UUID(str(correlation_id))
        except (TypeError, ValueError):
            correlation_uuid = None

    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO dead_events_quarantine
                (
                    tenant_id,
                    source,
                    raw_payload,
                    error_type,
                    error_code,
                    error_message,
                    error_detail,
                    correlation_id
                )
                VALUES
                (
                    NULL,
                    :source,
                    :raw_payload::jsonb,
                    :error_type,
                    :error_code,
                    :error_message,
                    '{}'::jsonb,
                    :correlation_id
                )
                """
            ),
            {
                "source": source,
                "raw_payload": payload or {},
                "error_type": error_type,
                "error_code": "UNRESOLVED_TENANT",
                "error_message": str(error_message)[:500],
                "correlation_id": str(correlation_uuid) if correlation_uuid else None,
            },
        )
