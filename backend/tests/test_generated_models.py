import pytest
from backend.app.schemas.attribution import RealtimeRevenueResponse
from backend.app.schemas.auth import LoginRequest, LoginResponse, RefreshRequest, RefreshResponse
from backend.app.schemas.reconciliation import ReconciliationStatusResponse
from backend.app.schemas.export import ExportRevenueResponse


def test_realtime_revenue_response_instantiation():
    """Test that RealtimeRevenueResponse can be instantiated with valid data."""
    data = {
        "total_revenue": 125000.50,
        "verified": True,
        "data_freshness_seconds": 45,
        "tenant_id": "550e8400-e29b-41d4-a716-446655440000"
    }
    model = RealtimeRevenueResponse(**data)
    assert model.total_revenue == 125000.50
    assert model.verified is True
    assert model.data_freshness_seconds == 45


def test_realtime_revenue_response_validation_failure():
    """Test that RealtimeRevenueResponse raises validation error on missing required field."""
    data = {
        "total_revenue": 125000.50,
        "verified": True,
        # Missing data_freshness_seconds (required field)
        "tenant_id": "550e8400-e29b-41d4-a716-446655440000"
    }
    with pytest.raises(Exception):  # Pydantic ValidationError
        RealtimeRevenueResponse(**data)


def test_login_request_instantiation():
    """Test that LoginRequest can be instantiated."""
    data = {"email": "test@example.com", "password": "secure123"}
    model = LoginRequest(**data)
    assert model.email == "test@example.com"
    assert model.password.get_secret_value() == "secure123"


def test_login_response_instantiation():
    """Test that LoginResponse can be instantiated."""
    data = {
        "access_token": "eyJhbGc...",
        "refresh_token": "eyJhbGc...",
        "expires_in": 3600,
        "token_type": "Bearer"
    }
    model = LoginResponse(**data)
    assert model.expires_in == 3600
    assert model.token_type == "Bearer"


def test_refresh_request_instantiation():
    """Test that RefreshRequest can be instantiated."""
    data = {"refresh_token": "eyJhbGc..."}
    model = RefreshRequest(**data)
    assert model.refresh_token == "eyJhbGc..."


def test_refresh_response_instantiation():
    """Test that RefreshResponse can be instantiated."""
    data = {
        "access_token": "eyJhbGc...",
        "refresh_token": "eyJhbGc...",
        "expires_in": 3600,
        "token_type": "Bearer"
    }
    model = RefreshResponse(**data)
    assert model.expires_in == 3600


def test_reconciliation_status_response_instantiation():
    """Test that ReconciliationStatusResponse can be instantiated."""
    data = {
        "state": "completed",
        "last_run_at": "2025-11-10T14:30:00Z",
        "tenant_id": "550e8400-e29b-41d4-a716-446655440000"
    }
    model = ReconciliationStatusResponse(**data)
    assert model.state.value == "completed"


def test_export_revenue_response_instantiation():
    """Test that ExportRevenueResponse can be instantiated."""
    data = {
        "file_url": "https://api.skeldir.com/exports/revenue_20251110.json",
        "tenant_id": "550e8400-e29b-41d4-a716-446655440000"
    }
    model = ExportRevenueResponse(**data)
    assert "revenue_20251110.json" in str(model.file_url)





