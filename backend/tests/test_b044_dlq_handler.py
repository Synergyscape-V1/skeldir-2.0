"""
B0.4.4 DLQ Handler Quality Gate Tests

Validates enhanced DLQ routing with error classification, retry logic,
exponential backoff, and RLS tenant isolation.

Quality Gates:
    - QG4.1: Error Classification
    - QG4.2: DLQ Routing Integration
    - QG4.3: Retry Logic with Backoff
    - QG4.4: Max Retries Enforcement
    - QG4.5: RLS Validation Checkpoint (MANDATORY)
"""
import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.ingestion.dlq_handler import (
    DLQHandler,
    ErrorType,
    ErrorClassification,
    RemediationStatus,
    classify_error,
    validate_status_transition,
)
from app.ingestion.event_service import EventIngestionService, ValidationError
from app.models import DeadEvent, AttributionEvent
from app.db.session import get_session


# ==============================================================================
# QG4.1: ERROR CLASSIFICATION
# ==============================================================================


async def test_qg41_error_classification_validation_error():
    """
    QG4.1: Error Classification - ValueError/ValidationError

    Exit Criteria: ValueError classified as schema_validation (transient)
    """
    error = ValueError("Missing required field: revenue_amount")
    error_type, classification = classify_error(error)

    assert error_type == ErrorType.SCHEMA_VALIDATION, \
        f"Expected SCHEMA_VALIDATION, got {error_type}"
    assert classification == ErrorClassification.TRANSIENT, \
        f"Expected TRANSIENT, got {classification}"

    print(f"QG4.1.1 PASS: ValueError -> schema_validation (transient)")


async def test_qg41_error_classification_fk_constraint():
    """
    QG4.1: Error Classification - Foreign Key IntegrityError

    Exit Criteria: FK IntegrityError classified as fk_constraint (permanent)
    """
    fk_error = IntegrityError(
        "violates foreign key constraint fk_attribution_events_channel",
        None,
        None
    )
    error_type, classification = classify_error(fk_error)

    assert error_type == ErrorType.FK_CONSTRAINT, \
        f"Expected FK_CONSTRAINT, got {error_type}"
    assert classification == ErrorClassification.PERMANENT, \
        f"Expected PERMANENT, got {classification}"

    print(f"QG4.1.2 PASS: FK IntegrityError -> fk_constraint (permanent)")


async def test_qg41_error_classification_duplicate_key():
    """
    QG4.1: Error Classification - Duplicate Key IntegrityError

    Exit Criteria: Duplicate IntegrityError classified as duplicate_key (permanent)
    """
    dup_error = IntegrityError(
        "duplicate key value violates unique constraint idx_idempotency_key",
        None,
        None
    )
    error_type, classification = classify_error(dup_error)

    assert error_type == ErrorType.DUPLICATE_KEY, \
        f"Expected DUPLICATE_KEY, got {error_type}"
    assert classification == ErrorClassification.PERMANENT, \
        f"Expected PERMANENT, got {classification}"

    print(f"QG4.1.3 PASS: Duplicate IntegrityError -> duplicate_key (permanent)")


# ==============================================================================
# QG4.2: DLQ ROUTING INTEGRATION
# ==============================================================================


@pytest.mark.asyncio
async def test_qg42_dlq_routing_integration(test_tenant):
    """
    QG4.2: DLQ Routing Integration

    Exit Criteria:
        - Dead event created with correct error_type
        - Retry count initialized to 0
        - Remediation status = 'pending'
        - Error classification captured
    """
    handler = DLQHandler()
    tenant_id = test_tenant

    invalid_payload = {
        "event_type": "purchase",
        # Missing: revenue_amount (required field)
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": str(uuid4()),
    }

    async with get_session(tenant_id=tenant_id) as session:
        dead_event = await handler.route_to_dlq(
            session=session,
            tenant_id=tenant_id,
            original_payload=invalid_payload,
            error=ValueError("Missing required field: revenue_amount"),
            correlation_id=f"qg42_test_{uuid4()}",
            source="test_suite",
        )
        await session.commit()

    # Verify dead event created
    assert dead_event is not None
    assert dead_event.error_type == ErrorType.SCHEMA_VALIDATION.value
    assert dead_event.retry_count == 0
    assert dead_event.remediation_status == RemediationStatus.PENDING.value
    assert dead_event.tenant_id == tenant_id

    # Verify persisted in database
    async with get_session(tenant_id=tenant_id) as session:
        result = await session.execute(
            select(DeadEvent).where(DeadEvent.id == dead_event.id)
        )
        persisted = result.scalar_one_or_none()
        assert persisted is not None
        assert persisted.error_type == ErrorType.SCHEMA_VALIDATION.value

    print(f"QG4.2 PASS: DLQ routing captures error with classification (dead_event_id={dead_event.id})")


# ==============================================================================
# QG4.3: RETRY LOGIC WITH BACKOFF
# ==============================================================================


@pytest.mark.asyncio
async def test_qg43_retry_increments_counter(test_tenant):
    """
    QG4.3: Retry Logic with Backoff

    Exit Criteria:
        - Retry attempt increments retry_count
        - last_retry_at timestamp updated
        - Backoff delay calculated correctly (60s, 120s, 240s)
    """
    handler = DLQHandler()
    tenant_id = test_tenant

    # Create dead event with malformed data (will fail retry)
    malformed_payload = {
        "event_type": "purchase",
        "event_timestamp": "INVALID_TIMESTAMP",  # Will cause parsing error
        "revenue_amount": 100.00,
        "session_id": str(uuid4()),
    }

    async with get_session(tenant_id=tenant_id) as session:
        dead_event = await handler.route_to_dlq(
            session=session,
            tenant_id=tenant_id,
            original_payload=malformed_payload,
            error=ValueError("Invalid timestamp"),
            correlation_id=f"qg43_test_{uuid4()}",
            source="test_suite",
        )
        await session.commit()
        dead_event_id = dead_event.id

    # Attempt retry (will fail due to malformed timestamp)
    async with get_session(tenant_id=tenant_id) as session:
        success, message = await handler.retry_dead_event(session, dead_event_id)
        await session.commit()

    assert success is False, "Expected retry to fail with malformed data"

    # Verify counter incremented
    async with get_session(tenant_id=tenant_id) as session:
        result = await session.execute(
            select(DeadEvent).where(DeadEvent.id == dead_event_id)
        )
        refreshed = result.scalar_one()

    assert refreshed.retry_count == 1, \
        f"Expected retry_count=1, got {refreshed.retry_count}"
    assert refreshed.last_retry_at is not None, \
        "Expected last_retry_at to be set"

    # Verify backoff calculation
    expected_backoff = handler._calculate_backoff(0)
    assert expected_backoff == 60, \
        f"Expected 60s backoff for retry 0, got {expected_backoff}"

    expected_backoff = handler._calculate_backoff(1)
    assert expected_backoff == 120, \
        f"Expected 120s backoff for retry 1, got {expected_backoff}"

    expected_backoff = handler._calculate_backoff(2)
    assert expected_backoff == 240, \
        f"Expected 240s backoff for retry 2, got {expected_backoff}"

    print(f"QG4.3 PASS: Retry increments counter, backoff calculated correctly (retry_count={refreshed.retry_count})")


# ==============================================================================
# QG4.4: MAX RETRIES ENFORCEMENT
# ==============================================================================


@pytest.mark.asyncio
async def test_qg44_max_retries_enforcement(test_tenant):
    """
    QG4.4: Max Retries Enforcement

    Exit Criteria:
        - Retry attempt with retry_count >= MAX_RETRIES fails
        - Remediation status updated to 'max_retries_exceeded'
        - Error message indicates max retries reached
    """
    handler = DLQHandler()
    tenant_id = test_tenant

    malformed_payload = {
        "event_type": "purchase",
        "event_timestamp": "INVALID",
        "revenue_amount": 100.00,
        "session_id": str(uuid4()),
    }

    # Create dead event already at max retries
    async with get_session(tenant_id=tenant_id) as session:
        dead_event = DeadEvent(
            id=uuid4(),
            tenant_id=tenant_id,
            source="test_suite",
            raw_payload=malformed_payload,
            correlation_id=uuid4(),  # Valid UUID
            error_type=ErrorType.SCHEMA_VALIDATION.value,
            error_code="ValueError",
            error_detail={"error": "Invalid timestamp"},  # JSONB field
            error_message="Invalid timestamp",  # Text field
            event_type="purchase",
            retry_count=handler.MAX_RETRIES,  # Already at max
            remediation_status=RemediationStatus.PENDING.value,
            ingested_at=datetime.now(timezone.utc),
        )
        session.add(dead_event)
        await session.commit()
        dead_event_id = dead_event.id

    # Attempt retry (should fail due to max retries)
    async with get_session(tenant_id=tenant_id) as session:
        success, message = await handler.retry_dead_event(session, dead_event_id)
        await session.commit()

    assert success is False, "Expected retry to fail at max retries"
    assert "Max retries" in message, f"Expected 'Max retries' in message, got: {message}"

    # Verify status updated to max_retries_exceeded
    async with get_session(tenant_id=tenant_id) as session:
        result = await session.execute(
            select(DeadEvent).where(DeadEvent.id == dead_event_id)
        )
        refreshed = result.scalar_one()

    assert refreshed.remediation_status == RemediationStatus.MAX_RETRIES_EXCEEDED.value, \
        f"Expected max_retries_exceeded, got {refreshed.remediation_status}"

    print(f"QG4.4 PASS: Max retries enforced (retry_count={refreshed.retry_count}, status={refreshed.remediation_status})")


# ==============================================================================
# QG4.5: RLS VALIDATION CHECKPOINT (MANDATORY)
# ==============================================================================


@pytest.mark.asyncio
async def test_qg45_rls_validation_checkpoint(test_tenant_pair):
    """
    QG4.5: RLS Validation Checkpoint (MANDATORY)

    Exit Criteria:
        - Dead event ingested for tenant_a
        - Query from tenant_b returns None (cross-tenant access blocked)
        - Query from tenant_a succeeds (same-tenant access allowed)

    RLS Policy:
        dead_events.tenant_id = current_setting('app.current_tenant_id')::uuid

    Critical: This validates tenant isolation at database layer for DLQ.
    """
    tenant_a, tenant_b = test_tenant_pair
    handler = DLQHandler()

    # Create dead event for tenant A
    test_payload = {
        "event_type": "purchase",
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
        "revenue_amount": 100.00,
        "session_id": str(uuid4()),
    }

    async with get_session(tenant_id=tenant_a) as session:
        dead_event = await handler.route_to_dlq(
            session=session,
            tenant_id=tenant_a,
            original_payload=test_payload,
            error=ValueError("Test RLS isolation"),
            correlation_id=f"qg45_test_{uuid4()}",
            source="test_suite",
        )
        await session.commit()
        dead_event_id = dead_event.id

    # Query from tenant B - should return None (RLS blocks)
    async with get_session(tenant_id=tenant_b) as session:
        # Verify session context
        result = await session.execute(text("SELECT current_setting('app.current_tenant_id', true)"))
        context = result.scalar()
        assert str(context) == str(tenant_b), \
            f"Session context mismatch: expected {tenant_b}, got {context}"

        # Query dead event
        result = await session.execute(
            select(DeadEvent).where(DeadEvent.id == dead_event_id)
        )
        cross_tenant_access = result.scalar_one_or_none()

        if cross_tenant_access is not None:
            pytest.fail(
                f"RLS VIOLATION: Tenant B can see Tenant A dead event\n"
                f"  Dead Event ID: {dead_event_id}\n"
                f"  Dead Event tenant_id: {cross_tenant_access.tenant_id}\n"
                f"  Query tenant context: {tenant_b}\n"
                f"  RLS policy FAILED to block cross-tenant access"
            )

    # Query from tenant A - should succeed (same tenant)
    async with get_session(tenant_id=tenant_a) as session:
        result = await session.execute(
            select(DeadEvent).where(DeadEvent.id == dead_event_id)
        )
        same_tenant_access = result.scalar_one_or_none()

        assert same_tenant_access is not None, \
            "RLS FAILED: Tenant A cannot access own dead event"
        assert same_tenant_access.tenant_id == tenant_a, \
            f"Tenant mismatch: expected {tenant_a}, got {same_tenant_access.tenant_id}"

    print(f"QG4.5 PASS (MANDATORY): RLS enforced on dead_events (tenant_a={tenant_a}, tenant_b={tenant_b})")


# ==============================================================================
# SUPPLEMENTARY TESTS - State Machine
# ==============================================================================


async def test_status_transition_validation():
    """
    Supplementary: Remediation Status State Machine

    Validates state machine transitions are correctly enforced.
    """
    # Valid transitions
    assert validate_status_transition(
        RemediationStatus.PENDING.value,
        RemediationStatus.RETRYING.value
    ) is True

    assert validate_status_transition(
        RemediationStatus.RETRYING.value,
        RemediationStatus.RESOLVED.value
    ) is True

    # Invalid transitions
    assert validate_status_transition(
        RemediationStatus.RESOLVED.value,
        RemediationStatus.PENDING.value
    ) is False

    assert validate_status_transition(
        RemediationStatus.IGNORED.value,
        RemediationStatus.RETRYING.value
    ) is False

    print("State machine transitions validated correctly")


# ==============================================================================
# INTEGRATION TEST - End-to-End Retry Success
# ==============================================================================


@pytest.mark.asyncio
async def test_integration_retry_success_after_fix(test_tenant):
    """
    Integration: Successful retry after data correction

    Scenario:
        1. Event fails validation (missing revenue_amount)
        2. Routed to DLQ
        3. Payload corrected (revenue_amount added)
        4. Retry succeeds
        5. Remediation status = 'resolved'
    """
    handler = DLQHandler()
    service = EventIngestionService()
    tenant_id = test_tenant

    # Step 1: Create dead event with fixable payload
    correlation_id = f"integration_test_{uuid4()}"
    incomplete_payload = {
        "idempotency_key": correlation_id,
        "event_type": "purchase",
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
        # Missing: revenue_amount (will be added later)
        "session_id": str(uuid4()),
        "source": "test",
    }

    async with get_session(tenant_id=tenant_id) as session:
        dead_event = await handler.route_to_dlq(
            session=session,
            tenant_id=tenant_id,
            original_payload=incomplete_payload,
            error=ValidationError("Missing revenue_amount"),
            correlation_id=correlation_id,
            source="test_suite",
        )
        await session.commit()
        dead_event_id = dead_event.id

    # Step 2: Fix payload (add revenue_amount)
    async with get_session(tenant_id=tenant_id) as session:
        result = await session.execute(
            select(DeadEvent).where(DeadEvent.id == dead_event_id)
        )
        dead_event = result.scalar_one()

        # Simulate operator fixing payload
        dead_event.raw_payload["revenue_amount"] = 100.00
        await session.commit()

    # Step 3: Retry with fixed payload
    async with get_session(tenant_id=tenant_id) as session:
        success, message = await handler.retry_dead_event(session, dead_event_id)
        await session.commit()

    # Verify retry succeeded
    assert success is True, f"Expected retry to succeed, got: {message}"
    assert "event_id=" in message, f"Expected event_id in message, got: {message}"

    # Verify remediation status updated
    async with get_session(tenant_id=tenant_id) as session:
        result = await session.execute(
            select(DeadEvent).where(DeadEvent.id == dead_event_id)
        )
        resolved_event = result.scalar_one()

    assert resolved_event.remediation_status == RemediationStatus.RESOLVED.value, \
        f"Expected resolved, got {resolved_event.remediation_status}"
    assert resolved_event.resolved_at is not None, \
        "Expected resolved_at timestamp"

    print(f"INTEGRATION PASS: Retry succeeded after payload fix (dead_event_id={dead_event_id})")
