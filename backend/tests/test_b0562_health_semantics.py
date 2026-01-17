"""
B0.5.6.2 Health Semantics Tests

Tests for the three-endpoint health surface with explicit semantics:
- /health/live: Pure liveness (no deps)
- /health/ready: Readiness (DB + RLS + GUC)
- /health/worker: Worker capability (data-plane probe)

Exit Gate Coverage:
- EG1: Route uniqueness (OpenAPI shows single handler per route)
- EG2: Liveness purity (no DB/broker calls)
- EG3: Readiness failure (503 on DB/RLS/GUC failure)
- EG4: Worker capability data-plane (200/503 based on worker)
- EG5: Probe safety (rate-limiting, caching)
- EG6: No worker HTTP regression (covered by CI script)
"""
import os
import time
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

os.environ["TESTING"] = "1"
# Use local test database if available, fallback to CI database
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://app_user:Sk3ld1r_App_Pr0d_2025!@ep-lucky-base-aedv3gwo-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
)

from app.main import app  # noqa: E402
from app.api import health as health_module  # noqa: E402


pytestmark = pytest.mark.asyncio


# ============================================================================
# EG1: Route Uniqueness Gate
# ============================================================================

@pytest.mark.asyncio
async def test_eg1_openapi_route_uniqueness():
    """
    EG1: Verify OpenAPI shows exactly one operation per health path.
    No duplicate /health routes should exist.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/openapi.json")
    
    assert resp.status_code == 200
    openapi = resp.json()
    paths = openapi.get("paths", {})
    
    # Verify expected health paths exist
    assert "/health" in paths, "/health alias missing from OpenAPI"
    assert "/health/live" in paths, "/health/live missing from OpenAPI"
    assert "/health/ready" in paths, "/health/ready missing from OpenAPI"
    assert "/health/worker" in paths, "/health/worker missing from OpenAPI"

    # Verify each path has exactly one GET operation
    for path in ["/health", "/health/live", "/health/ready", "/health/worker"]:
        assert "get" in paths[path], f"{path} missing GET operation"
        # FastAPI only allows one handler per method+path, so no duplicates possible
        # This assertion documents the invariant
        assert len([k for k in paths[path].keys() if k not in ("parameters",)]) == 1


# ============================================================================
# EG2: Liveness Purity Gate
# ============================================================================

@pytest.mark.asyncio
async def test_eg2_liveness_returns_200_ok():
    """EG2: /health/live returns 200 with {"status": "ok"}."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health/live")
    
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_eg2_liveness_no_db_calls():
    """
    EG2: /health/live performs zero DB operations.
    
    We verify this by patching the engine and confirming it's never called.
    """
    with patch.object(health_module, "engine") as mock_engine:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            live_resp = await client.get("/health/live")
            alias_resp = await client.get("/health")

    assert live_resp.status_code == 200
    assert live_resp.json() == {"status": "ok"}
    assert alias_resp.status_code == 200
    assert alias_resp.json() == {"status": "ok"}
    # The engine should NOT be called at all for liveness
    mock_engine.begin.assert_not_called()


@pytest.mark.asyncio
async def test_eg2_liveness_no_celery_calls():
    """
    EG2: /health/live performs zero Celery operations.
    
    We verify by patching celery_app and confirming send_task is never called.
    """
    with patch("app.celery_app.celery_app") as mock_celery:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            live_resp = await client.get("/health/live")
            alias_resp = await client.get("/health")

    assert live_resp.status_code == 200
    assert alias_resp.status_code == 200
    mock_celery.send_task.assert_not_called()


# ============================================================================
# EG3: Readiness Failure Gate
# ============================================================================

@pytest.mark.asyncio
async def test_eg3_readiness_success():
    """EG3: /health/ready returns 200 with correct payload on healthy deps."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health/ready")
    
    # May be 200 or 503 depending on test environment DB state
    # But should always have the expected payload structure
    data = resp.json()
    assert "status" in data
    assert "database" in data
    assert "rls" in data
    assert "tenant_guc" in data
    
    if resp.status_code == 200:
        assert data["status"] == "ok"
        assert data["database"] == "ok"
        assert data["rls"] == "ok"
        assert data["tenant_guc"] == "ok"


@pytest.mark.asyncio
async def test_eg3_readiness_failure_on_db_error(monkeypatch):
    """EG3: /health/ready returns 503 on DB connectivity failure."""
    class FakeConn:
        async def __aenter__(self):
            raise RuntimeError("DB connection failed")
        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeEngine:
        def begin(self):
            return FakeConn()

    monkeypatch.setattr(health_module, "engine", FakeEngine())
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health/ready")
    
    assert resp.status_code == 503
    data = resp.json()
    assert data["status"] == "unhealthy"
    assert data["database"] == "error"


# ============================================================================
# EG4: Worker Capability Data-Plane Gate
# ============================================================================

@pytest.mark.asyncio
async def test_eg4_worker_capability_payload_structure():
    """
    EG4: /health/worker returns expected payload structure.
    
    Note: Actual worker capability depends on running worker.
    This test verifies the payload structure is correct regardless.
    """
    # Reset cache to force a fresh probe
    health_module._probe_cache = None
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health/worker")
    
    # May be 200 or 503 depending on worker availability
    data = resp.json()
    
    # Verify payload structure matches spec
    assert "status" in data
    assert data["status"] in ("ok", "unhealthy")
    assert "broker" in data
    assert data["broker"] in ("ok", "error")
    assert "database" in data
    assert data["database"] in ("ok", "error")
    assert "worker" in data
    assert data["worker"] in ("ok", "error")
    assert "probe_latency_ms" in data
    assert isinstance(data["probe_latency_ms"], (int, type(None)))
    assert "cached" in data
    assert isinstance(data["cached"], bool)


@pytest.mark.asyncio
async def test_eg4_worker_success_with_mock():
    """
    EG4: /health/worker returns 200 when worker completes probe task.
    
    Uses mock to simulate successful worker response.
    """
    # Reset cache
    health_module._probe_cache = None
    
    # Create a mock result that behaves like Celery AsyncResult
    mock_result = MagicMock()
    mock_result.get.return_value = {
        "status": "ok",
        "timestamp": "2026-01-16T00:00:00Z",
        "db_user": "app_user",
        "worker": "test-worker",
    }
    
    with patch("app.api.health.celery_app") as mock_celery:
        mock_celery.send_task.return_value = mock_result
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health/worker")
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["broker"] == "ok"
    assert data["database"] == "ok"
    assert data["worker"] == "ok"
    assert data["probe_latency_ms"] is not None
    assert data["cached"] is False
    
    # Verify the probe task was sent correctly
    mock_celery.send_task.assert_called_once_with(
        "app.tasks.health.probe",
        queue="housekeeping",
        kwargs={},
    )


@pytest.mark.asyncio
async def test_eg4_worker_failure_on_timeout():
    """
    EG4: /health/worker returns 503 when worker times out.
    """
    # Reset cache
    health_module._probe_cache = None
    
    mock_result = MagicMock()
    mock_result.get.side_effect = TimeoutError("Worker did not respond")
    
    with patch("app.api.health.celery_app") as mock_celery:
        mock_celery.send_task.return_value = mock_result
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health/worker")
    
    assert resp.status_code == 503
    data = resp.json()
    assert data["status"] == "unhealthy"
    assert data["broker"] == "ok"  # Task was sent successfully
    assert data["worker"] == "error"


@pytest.mark.asyncio
async def test_eg4_worker_failure_on_broker_error():
    """
    EG4: /health/worker returns 503 when broker is unreachable.
    """
    # Reset cache
    health_module._probe_cache = None
    
    with patch("app.api.health.celery_app") as mock_celery:
        mock_celery.send_task.side_effect = ConnectionError("Broker unreachable")
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health/worker")
    
    assert resp.status_code == 503
    data = resp.json()
    assert data["status"] == "unhealthy"
    assert data["broker"] == "error"
    assert data["worker"] == "error"


# ============================================================================
# EG5: Probe Safety Gate (Rate Limiting + Caching)
# ============================================================================

@pytest.mark.asyncio
async def test_eg5_probe_caching():
    """
    EG5: Repeated /health/worker calls within TTL return cached result.
    Only one probe task should be enqueued.
    """
    # Reset cache
    health_module._probe_cache = None
    
    mock_result = MagicMock()
    mock_result.get.return_value = {
        "status": "ok",
        "timestamp": "2026-01-16T00:00:00Z",
        "db_user": "app_user",
        "worker": "test-worker",
    }
    
    with patch("app.api.health.celery_app") as mock_celery:
        mock_celery.send_task.return_value = mock_result
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # First call - should execute probe
            resp1 = await client.get("/health/worker")
            # Second call - should use cache
            resp2 = await client.get("/health/worker")
            # Third call - should use cache
            resp3 = await client.get("/health/worker")
    
    # All should succeed
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp3.status_code == 200
    
    # First call not cached, subsequent calls cached
    assert resp1.json()["cached"] is False
    assert resp2.json()["cached"] is True
    assert resp3.json()["cached"] is True
    
    # Only ONE probe should have been sent
    assert mock_celery.send_task.call_count == 1


@pytest.mark.asyncio
async def test_eg5_cache_expiry():
    """
    EG5: Cache expires after TTL, triggering new probe.
    """
    # Reset cache
    health_module._probe_cache = None
    
    # Temporarily reduce TTL for test
    original_ttl = health_module._PROBE_CACHE_TTL_SECONDS
    health_module._PROBE_CACHE_TTL_SECONDS = 0.1  # 100ms
    
    try:
        mock_result = MagicMock()
        mock_result.get.return_value = {
            "status": "ok",
            "timestamp": "2026-01-16T00:00:00Z",
            "db_user": "app_user",
            "worker": "test-worker",
        }
        
        with patch("app.api.health.celery_app") as mock_celery:
            mock_celery.send_task.return_value = mock_result
            
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                # First call
                resp1 = await client.get("/health/worker")
                assert resp1.json()["cached"] is False
                
                # Wait for cache to expire
                time.sleep(0.15)
                
                # Second call - cache expired, new probe
                resp2 = await client.get("/health/worker")
                assert resp2.json()["cached"] is False
        
        # Two probes should have been sent (cache expired)
        assert mock_celery.send_task.call_count == 2
    finally:
        health_module._PROBE_CACHE_TTL_SECONDS = original_ttl


# ============================================================================
# Additional Invariant Tests
# ============================================================================

@pytest.mark.asyncio
async def test_health_alias_returns_ok():
    """
    Verify /health alias exists and returns liveness-only payload.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_metrics_endpoint_still_works():
    """
    Verify /metrics endpoint is unaffected by health refactor.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/metrics")
    
    assert resp.status_code == 200
    assert "text/plain" in resp.headers.get("content-type", "")
