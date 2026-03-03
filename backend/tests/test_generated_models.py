#!/usr/bin/env python3
"""
Unit tests for generated Pydantic models.
Validates model structure and basic functionality.
"""

import pytest
from pydantic import ValidationError


def test_realtime_revenue_response_import():
    """Test that RealtimeRevenueResponse can be imported."""
    from app.schemas.attribution import RealtimeRevenueResponse
    assert RealtimeRevenueResponse is not None


def test_login_request_validation():
    """Test LoginRequest validates correctly."""
    from app.schemas.auth import LoginRequest

    # Valid request
    valid_data = {
        "email": "test@example.com",
        "password": "securepass123",
        "tenant_id": "00000000-0000-0000-0000-000000000000",
    }
    request = LoginRequest(**valid_data)
    assert request.email == "test@example.com"


def test_model_inheritance():
    """Test that RealtimeRevenueResponse inherits from RealtimeRevenueCounter."""
    from app.schemas.attribution import (
        RealtimeRevenueResponse,
        RealtimeRevenueCounter,
    )

    assert issubclass(RealtimeRevenueResponse, RealtimeRevenueCounter)


def test_webhook_acknowledgement():
    """Test webhook acknowledgement model."""
    from app.schemas.webhooks_shopify import WebhookAcknowledgement

    ack = WebhookAcknowledgement(acknowledged=True, event_id="evt_550e8400e29b41d4a716446655440000")
    assert ack.acknowledged == True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
