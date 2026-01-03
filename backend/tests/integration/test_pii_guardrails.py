"""
PII Guardrail Integration Tests

This test suite empirically validates that Layer 2 PII-blocking database triggers
are functional and correctly block PII-laden data.

Test Plan (Phase 3):
1. Test that PII keys (email, phone) are blocked in attribution_events.raw_payload
2. Test that PII keys are blocked in dead_events.raw_payload
3. Test that clean payloads without PII are allowed
4. Test that PII in revenue_ledger.metadata is blocked
5. Test that NULL metadata in revenue_ledger is allowed

These tests provide empirical proof that triggers work, not just that they exist.

Related Documents:
- docs/governance/PRIVACY_LIFECYCLE_IMPLEMENTATION.md (Phase 3)
- docs/database/pii-controls.md (Layer 2 implementation)
- alembic/versions/002_pii_controls/202511161200_add_pii_guardrail_triggers.py
"""

import pytest
from uuid import uuid4
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError, InternalError


# Database connection setup
# TODO: Replace with actual test database configuration
DATABASE_URL = "postgresql://user:pass@localhost/skeldir_test"


@pytest.fixture(scope="function")
def db_session():
    """
    Create a database session for testing.
    
    Note: This fixture assumes a test database is available.
    In production, this would use pytest-postgresql or similar.
    """
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="function")
def test_tenant_id(db_session):
    """Create a test tenant for use in tests."""
    tenant_id = uuid4()
    
    # RAW_SQL_ALLOWLIST: fixture seeds tenant for PII guardrail integration tests
    db_session.execute(
        text("""
            INSERT INTO tenants (id, name, api_key_hash, notification_email, created_at, updated_at)
            VALUES (:tenant_id, 'Test Tenant', :api_key_hash, :notification_email, NOW(), NOW())
            ON CONFLICT (id) DO NOTHING
        """),
        {
            "tenant_id": tenant_id,
            "api_key_hash": f"test_hash_{tenant_id}",
            "notification_email": f"tenant_{tenant_id}@example.com",
        }
    )
    db_session.commit()
    
    return tenant_id


class TestPIIGuardrailAttributionEvents:
    """Test PII guardrail on attribution_events.raw_payload."""
    
    def test_insert_with_email_fails_on_attribution_events(self, db_session, test_tenant_id):
        """
        Test Case 1: Verify that inserting PII (email) into attribution_events.raw_payload is blocked.
        
        Expected: Raises IntegrityError with error message containing "PII key detected" and "email".
        """
        # Attempt INSERT with PII key
        # RAW_SQL_ALLOWLIST: intentional PII injection to assert trigger enforcement
        with pytest.raises((IntegrityError, InternalError)) as exc_info:
            idempotency_key = f"pii-email:{uuid4()}"
            db_session.execute(
                text("""
                    INSERT INTO attribution_events (
                        tenant_id,
                        session_id,
                        occurred_at,
                        event_timestamp,
                        idempotency_key,
                        event_type,
                        channel,
                        raw_payload
                    ) VALUES (
                        :tenant_id,
                        :session_id,
                        NOW(),
                        NOW(),
                        :idempotency_key,
                        :event_type,
                        :channel,
                        '{"email": "test@example.com"}'::jsonb
                    )
                """),
                {
                    "tenant_id": test_tenant_id,
                    "session_id": uuid4(),
                    "idempotency_key": idempotency_key,
                    "event_type": "page_view",
                    "channel": "direct",
                }
            )
            db_session.commit()
        
        # Assert error message contains PII detection
        error_message = str(exc_info.value).lower()
        assert "pii key detected" in error_message or "pii" in error_message
        assert "email" in error_message or "attribution_events" in error_message
    
    def test_insert_with_phone_fails_on_attribution_events(self, db_session, test_tenant_id):
        """Test that phone number in raw_payload is blocked."""
        # RAW_SQL_ALLOWLIST: intentional PII injection to assert trigger enforcement
        with pytest.raises((IntegrityError, InternalError)) as exc_info:
            idempotency_key = f"pii-phone:{uuid4()}"
            db_session.execute(
                text("""
                    INSERT INTO attribution_events (
                        tenant_id,
                        session_id,
                        occurred_at,
                        event_timestamp,
                        idempotency_key,
                        event_type,
                        channel,
                        raw_payload
                    ) VALUES (
                        :tenant_id,
                        :session_id,
                        NOW(),
                        NOW(),
                        :idempotency_key,
                        :event_type,
                        :channel,
                        '{"phone": "555-1234"}'::jsonb
                    )
                """),
                {
                    "tenant_id": test_tenant_id,
                    "session_id": uuid4(),
                    "idempotency_key": idempotency_key,
                    "event_type": "page_view",
                    "channel": "direct",
                }
            )
            db_session.commit()
        
        error_message = str(exc_info.value).lower()
        assert "pii" in error_message or "phone" in error_message
    
    def test_insert_without_pii_succeeds(self, db_session, test_tenant_id):
        """
        Test Case 3: Verify that clean payloads without PII are allowed.
        
        Expected: INSERT succeeds without exception.
        """
        event_id = uuid4()
        
        # INSERT with clean payload
        # RAW_SQL_ALLOWLIST: controlled clean payload insert to validate allow path
        idempotency_key = f"pii-clean:{event_id}"
        db_session.execute(
            text("""
                INSERT INTO attribution_events (
                    id,
                    tenant_id,
                    session_id,
                    occurred_at,
                    event_timestamp,
                    idempotency_key,
                    event_type,
                    channel,
                    raw_payload
                ) VALUES (
                    :event_id,
                    :tenant_id,
                    :session_id,
                    NOW(),
                    NOW(),
                    :idempotency_key,
                    :event_type,
                    :channel,
                    '{"channel": "google_search_paid", "utm_source": "google"}'::jsonb
                )
            """),
            {
                "event_id": event_id,
                "tenant_id": test_tenant_id,
                "session_id": uuid4(),
                "idempotency_key": idempotency_key,
                "event_type": "page_view",
                "channel": "direct",
            }
        )
        db_session.commit()
        
        # Verify row was inserted
        result = db_session.execute(
            text("SELECT COUNT(*) FROM attribution_events WHERE id = :event_id"),
            {"event_id": event_id}
        ).scalar()
        
        assert result == 1, "Clean payload INSERT should succeed"


class TestPIIGuardrailDeadEvents:
    """Test PII guardrail on dead_events.raw_payload."""
    
    def test_insert_with_phone_fails_on_dead_events(self, db_session, test_tenant_id):
        """
        Test Case 2: Verify that inserting PII (phone) into dead_events.raw_payload is blocked.
        
        Expected: Raises exception with PII detection message.
        """
        # Attempt INSERT with PII key
        # RAW_SQL_ALLOWLIST: intentional PII injection to assert trigger enforcement
        with pytest.raises((IntegrityError, InternalError)) as exc_info:
            db_session.execute(
                text("""
                    INSERT INTO dead_events (
                        tenant_id, ingested_at, source, error_code, error_detail, raw_payload
                    ) VALUES (
                        :tenant_id,
                        NOW(),
                        'test_source',
                        'TEST_ERROR',
                        '{}'::jsonb,
                        '{"phone": "555-1234"}'::jsonb
                    )
                """),
                {"tenant_id": test_tenant_id}
            )
            db_session.commit()
        
        # Assert error message contains PII detection
        error_message = str(exc_info.value).lower()
        assert "pii" in error_message or "phone" in error_message
        assert "dead_events" in error_message or "raw_payload" in error_message


class TestPIIGuardrailRevenueLedger:
    """Test PII guardrail on revenue_ledger.metadata."""
    
    @pytest.fixture
    def test_allocation_id(self, db_session, test_tenant_id):
        """Create a test allocation for revenue_ledger FK requirement."""
        allocation_id = uuid4()
        event_id = uuid4()
        idempotency_key = f"pii-alloc:{event_id}"
        
        # Create event first
        # RAW_SQL_ALLOWLIST: seed event for FK prerequisite in PII guardrail test
        db_session.execute(
            text("""
                INSERT INTO attribution_events (
                    id,
                    tenant_id,
                    session_id,
                    occurred_at,
                    event_timestamp,
                    idempotency_key,
                    event_type,
                    channel,
                    raw_payload
                ) VALUES (
                    :event_id,
                    :tenant_id,
                    :session_id,
                    NOW(),
                    NOW(),
                    :idempotency_key,
                    :event_type,
                    :channel,
                    '{"channel": "google"}'::jsonb
                )
            """),
            {
                "event_id": event_id,
                "tenant_id": test_tenant_id,
                "session_id": uuid4(),
                "idempotency_key": idempotency_key,
                "event_type": "page_view",
                "channel": "direct",
            }
        )
        
        # Create allocation
        # RAW_SQL_ALLOWLIST: seed allocation for FK prerequisite in PII guardrail test
        db_session.execute(
            text("""
                INSERT INTO attribution_allocations (
                    id, tenant_id, event_id, channel_code, allocated_revenue_cents
                ) VALUES (
                    :allocation_id, :tenant_id, :event_id, 'google_search_paid', 1000
                )
            """),
            {
                "allocation_id": allocation_id,
                "tenant_id": test_tenant_id,
                "event_id": event_id
            }
        )
        db_session.commit()
        
        return allocation_id
    
    def test_revenue_ledger_metadata_pii_blocked(self, db_session, test_tenant_id, test_allocation_id):
        """
        Test Case 4: Verify that PII in revenue_ledger.metadata is blocked.
        
        Expected: Raises exception.
        """
        # Attempt INSERT with PII in metadata
        # RAW_SQL_ALLOWLIST: intentional PII injection to assert trigger enforcement
        with pytest.raises((IntegrityError, InternalError)) as exc_info:
            db_session.execute(
                text("""
                    INSERT INTO revenue_ledger (
                        tenant_id, allocation_id, revenue_cents, metadata
                    ) VALUES (
                        :tenant_id, :allocation_id, 1000,
                        '{"email": "test@example.com"}'::jsonb
                    )
                """),
                {
                    "tenant_id": test_tenant_id,
                    "allocation_id": test_allocation_id
                }
            )
            db_session.commit()
        
        # Assert error message contains PII detection
        error_message = str(exc_info.value).lower()
        assert "pii" in error_message or "email" in error_message
    
    def test_revenue_ledger_null_metadata_allowed(self, db_session, test_tenant_id, test_allocation_id):
        """
        Test Case 5: Verify that NULL metadata is allowed.
        
        Expected: Succeeds (NULL metadata is allowed per trigger logic).
        """
        ledger_id = uuid4()
        
        # INSERT with NULL metadata
        # RAW_SQL_ALLOWLIST: validate NULL metadata path bypasses PII trigger
        db_session.execute(
            text("""
                INSERT INTO revenue_ledger (
                    id, tenant_id, allocation_id, revenue_cents, metadata
                ) VALUES (
                    :ledger_id, :tenant_id, :allocation_id, 1000, NULL
                )
            """),
            {
                "ledger_id": ledger_id,
                "tenant_id": test_tenant_id,
                "allocation_id": test_allocation_id
            }
        )
        db_session.commit()
        
        # Verify row was inserted
        result = db_session.execute(
            text("SELECT COUNT(*) FROM revenue_ledger WHERE id = :ledger_id"),
            {"ledger_id": ledger_id}
        ).scalar()
        
        assert result == 1, "NULL metadata INSERT should succeed"


class TestPIIGuardrailAdditionalKeys:
    """Test additional PII keys from blocklist."""
    
    def test_insert_with_name_fails(self, db_session, test_tenant_id):
        """Test that first_name, last_name, full_name are blocked."""
        for name_key in ["first_name", "last_name", "full_name"]:
            with pytest.raises((IntegrityError, InternalError)):
                # RAW_SQL_ALLOWLIST: intentional name PII injection to trigger guard
                idempotency_key = f"pii-name:{name_key}:{uuid4()}"
                db_session.execute(
                    text(f"""
                        INSERT INTO attribution_events (
                            tenant_id,
                            session_id,
                            occurred_at,
                            event_timestamp,
                            idempotency_key,
                            event_type,
                            channel,
                            raw_payload
                        ) VALUES (
                            :tenant_id,
                            :session_id,
                            NOW(),
                            NOW(),
                            :idempotency_key,
                            :event_type,
                            :channel,
                            '{{"{name_key}": "John Doe"}}'::jsonb
                        )
                    """),
                    {
                        "tenant_id": test_tenant_id,
                        "session_id": uuid4(),
                        "idempotency_key": idempotency_key,
                        "event_type": "page_view",
                        "channel": "direct",
                    }
                )
                db_session.commit()
    
    def test_insert_with_address_fails(self, db_session, test_tenant_id):
        """Test that address, street_address are blocked."""
        for addr_key in ["address", "street_address"]:
            with pytest.raises((IntegrityError, InternalError)):
                # RAW_SQL_ALLOWLIST: intentional address PII injection to trigger guard
                idempotency_key = f"pii-address:{addr_key}:{uuid4()}"
                db_session.execute(
                    text(f"""
                        INSERT INTO attribution_events (
                            tenant_id,
                            session_id,
                            occurred_at,
                            event_timestamp,
                            idempotency_key,
                            event_type,
                            channel,
                            raw_payload
                        ) VALUES (
                            :tenant_id,
                            :session_id,
                            NOW(),
                            NOW(),
                            :idempotency_key,
                            :event_type,
                            :channel,
                            '{{"{addr_key}": "123 Main St"}}'::jsonb
                        )
                    """),
                    {
                        "tenant_id": test_tenant_id,
                        "session_id": uuid4(),
                        "idempotency_key": idempotency_key,
                        "event_type": "page_view",
                        "channel": "direct",
                    }
                )
                db_session.commit()
    
    def test_insert_with_ip_fails(self, db_session, test_tenant_id):
        """Test that ip_address, ip are blocked."""
        for ip_key in ["ip_address", "ip"]:
            with pytest.raises((IntegrityError, InternalError)):
                # RAW_SQL_ALLOWLIST: intentional IP PII injection to trigger guard
                idempotency_key = f"pii-ip:{ip_key}:{uuid4()}"
                db_session.execute(
                    text(f"""
                        INSERT INTO attribution_events (
                            tenant_id,
                            session_id,
                            occurred_at,
                            event_timestamp,
                            idempotency_key,
                            event_type,
                            channel,
                            raw_payload
                        ) VALUES (
                            :tenant_id,
                            :session_id,
                            NOW(),
                            NOW(),
                            :idempotency_key,
                            :event_type,
                            :channel,
                            '{{"{ip_key}": "192.168.1.1"}}'::jsonb
                        )
                    """),
                    {
                        "tenant_id": test_tenant_id,
                        "session_id": uuid4(),
                        "idempotency_key": idempotency_key,
                        "event_type": "page_view",
                        "channel": "direct",
                    }
                )
                db_session.commit()
    
    def test_insert_with_ssn_fails(self, db_session, test_tenant_id):
        """Test that ssn, social_security_number are blocked."""
        for ssn_key in ["ssn", "social_security_number"]:
            with pytest.raises((IntegrityError, InternalError)):
                # RAW_SQL_ALLOWLIST: intentional SSN PII injection to trigger guard
                idempotency_key = f"pii-ssn:{ssn_key}:{uuid4()}"
                db_session.execute(
                    text(f"""
                        INSERT INTO attribution_events (
                            tenant_id,
                            session_id,
                            occurred_at,
                            event_timestamp,
                            idempotency_key,
                            event_type,
                            channel,
                            raw_payload
                        ) VALUES (
                            :tenant_id,
                            :session_id,
                            NOW(),
                            NOW(),
                            :idempotency_key,
                            :event_type,
                            :channel,
                            '{{"{ssn_key}": "123-45-6789"}}'::jsonb
                        )
                    """),
                    {
                        "tenant_id": test_tenant_id,
                        "session_id": uuid4(),
                        "idempotency_key": idempotency_key,
                        "event_type": "page_view",
                        "channel": "direct",
                    }
                )
                db_session.commit()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
