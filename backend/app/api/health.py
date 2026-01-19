"""
Health check endpoints with explicit semantics (B0.5.6.2).

Three endpoints with rigid, non-overlapping responsibilities:
- /health/live: Pure liveness (process responds, no dependency checks)
- /health/ready: Readiness (DB + RLS + tenant GUC validation)
- /health/worker: Worker capability (data-plane probe via Celery)

Legacy alias:
- /health: Strict liveness only (alias of /health/live)
"""
import logging
import os
import time
import threading
from dataclasses import dataclass
from typing import Optional

from fastapi import APIRouter, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text
from uuid import uuid4

from app.db.session import engine
from app.celery_app import celery_app

router = APIRouter()
logger = logging.getLogger(__name__)

# ============================================================================
# Worker Probe Cache + Single-Flight Lock (EG5 - Probe Safety)
# ============================================================================

# Probe result cache: per-process, TTL-based
def _get_env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except Exception:
        return default


_PROBE_CACHE_TTL_SECONDS = max(0.0, _get_env_float("WORKER_PROBE_CACHE_TTL_SECONDS", 10.0))
_PROBE_TIMEOUT_SECONDS = max(0.1, _get_env_float("WORKER_PROBE_TIMEOUT_SECONDS", 15.0))  # Max time to wait for worker response


@dataclass
class _ProbeResult:
    """Cached worker probe result."""
    timestamp: float
    broker_ok: bool
    database_ok: bool
    worker_ok: bool
    latency_ms: Optional[int]
    error: Optional[str] = None


_probe_cache: Optional[_ProbeResult] = None
_probe_cache_lock = threading.Lock()
_probe_inflight = False
_probe_inflight_lock = threading.Lock()


def _is_cache_valid() -> bool:
    """Check if cached probe result is still valid."""
    global _probe_cache
    if _probe_cache is None:
        return False
    return (time.monotonic() - _probe_cache.timestamp) < _PROBE_CACHE_TTL_SECONDS


def _execute_worker_probe() -> _ProbeResult:
    """
    Execute a data-plane worker capability probe.
    
    Enqueues a health probe task to the housekeeping queue and waits for completion.
    This proves end-to-end: API → broker → worker → result backend → API.
    
    Returns a _ProbeResult with status of each component.
    """
    start = time.monotonic()
    broker_ok = False
    database_ok = False
    worker_ok = False
    latency_ms: Optional[int] = None
    error: Optional[str] = None
    
    try:
        # First, check broker connectivity by sending the task
        # This proves the broker accepts messages
        task_result = celery_app.send_task(
            "app.tasks.health.probe",
            queue="housekeeping",
            kwargs={},
        )
        broker_ok = True
        
        # Wait for worker to complete the task (data-plane proof)
        # The ping task itself validates DB connectivity
        try:
            result = task_result.get(timeout=_PROBE_TIMEOUT_SECONDS)
            elapsed = time.monotonic() - start
            latency_ms = int(elapsed * 1000)
            
            # The health probe task returns {"status": "ok", "db_user": ..., ...} on success
            if isinstance(result, dict) and result.get("status") == "ok":
                worker_ok = True
                # db_user presence proves DB connectivity from worker side
                if result.get("db_user"):
                    database_ok = True
                else:
                    error = "worker_db_user_missing"
            else:
                error = f"unexpected_result: {result}"
        except Exception as exc:
            elapsed = time.monotonic() - start
            latency_ms = int(elapsed * 1000)
            error = f"worker_timeout_or_failure: {type(exc).__name__}: {exc}"
            
    except Exception as exc:
        error = f"broker_send_failed: {type(exc).__name__}: {exc}"
    
    return _ProbeResult(
        timestamp=time.monotonic(),
        broker_ok=broker_ok,
        database_ok=database_ok,
        worker_ok=worker_ok,
        latency_ms=latency_ms,
        error=error,
    )


def _get_or_execute_probe() -> tuple[_ProbeResult, bool]:
    """
    Get cached probe result or execute a new probe (single-flight).
    
    Returns (probe_result, was_cached).
    """
    global _probe_cache, _probe_inflight
    
    # Check cache first (fast path)
    with _probe_cache_lock:
        if _is_cache_valid():
            return _probe_cache, True
    
    # Single-flight: only one probe can be in-flight at a time
    with _probe_inflight_lock:
        if _probe_inflight:
            # Another request is already executing a probe; wait and return cache
            # This is a simplification - in production you'd use a condition variable
            # For now, just return stale cache or error
            with _probe_cache_lock:
                if _probe_cache is not None:
                    return _probe_cache, True
                # No cache available and probe in flight - return error state
                return _ProbeResult(
                    timestamp=time.monotonic(),
                    broker_ok=False,
                    database_ok=False,
                    worker_ok=False,
                    latency_ms=None,
                    error="probe_in_flight_no_cache",
                ), False
        
        # Double-check cache after acquiring inflight lock
        with _probe_cache_lock:
            if _is_cache_valid():
                return _probe_cache, True
        
        # Mark probe as in-flight
        _probe_inflight = True
    
    try:
        # Execute the probe
        result = _execute_worker_probe()
        
        # Update cache
        with _probe_cache_lock:
            _probe_cache = result
        
        return result, False
    finally:
        with _probe_inflight_lock:
            _probe_inflight = False


# ============================================================================
# Health Endpoints
# ============================================================================

@router.get("/health/live")
async def liveness(response: Response) -> dict:
    """
    Liveness probe: process-only, no dependency checks.
    
    Returns 200 if the API process can respond.
    Performs zero DB, broker, or Celery operations.
    Constant-time response.
    
    Use for: Kubernetes liveness probe, load balancer health.
    """
    response.headers["X-Health-Status"] = "healthy"
    return {"status": "ok"}


@router.get("/health")
async def health_alias(response: Response) -> dict:
    """
    Legacy health alias: strict liveness only (no dependency checks).
    """
    response.headers["X-Health-Status"] = "healthy"
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness(response: Response) -> dict:
    """
    Readiness probe: API safe to receive traffic.
    
    Returns 200 only if:
    - DB connectivity check passes
    - RLS enforcement checks pass  
    - Tenant context GUC validation passes
    
    Returns 503 on any failure.
    
    Use for: Kubernetes readiness probe, traffic routing decisions.
    """
    result = {
        "status": "ok",
        "database": "ok",
        "rls": "ok",
        "tenant_guc": "ok",
    }
    
    try:
        async with engine.begin() as conn:
            # 1. Basic DB connectivity
            await conn.execute(text("SELECT 1"))
            
            # 2. RLS enforcement on core table
            rls_check = await conn.execute(
                text(
                    "SELECT relrowsecurity, relforcerowsecurity "
                    "FROM pg_class WHERE relname = 'attribution_events'"
                )
            )
            rls_row = rls_check.first()
            if not rls_row or not (rls_row[0] and rls_row[1]):
                result["rls"] = "error"
                raise RuntimeError("RLS not enforced on attribution_events")
            
            # 3. Tenant context GUC validation
            tenant_probe = str(uuid4())
            await conn.execute(
                text("SELECT set_config('app.current_tenant_id', :tid, false)"),
                {"tid": tenant_probe},
            )
            cur = await conn.execute(
                text("SELECT current_setting('app.current_tenant_id', true)")
            )
            current_tid = cur.scalar_one_or_none()
            if current_tid != tenant_probe:
                result["tenant_guc"] = "error"
                raise RuntimeError("Tenant context GUC not set correctly")
                
    except Exception as exc:
        logger.error("readiness_failed", exc_info=True)
        # Determine which component failed based on current state
        if result["database"] != "ok":
            pass  # already marked
        elif result["rls"] != "ok":
            pass  # already marked
        elif result["tenant_guc"] != "ok":
            pass  # already marked
        else:
            # DB connectivity itself failed
            result["database"] = "error"
        
        result["status"] = "unhealthy"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    
    return result


@router.get("/health/worker")
async def worker_capability(response: Response) -> dict:
    """
    Worker capability probe: data-plane round-trip validation.
    
    Proves end-to-end async capability by:
    1. Enqueuing a probe task to the Celery broker
    2. Waiting for a real worker to pick it up and complete
    3. Validating the result within a bounded timeout
    
    Rate-limited and cached (TTL) to prevent probe-induced DoS.
    Single-flight lock prevents concurrent probe storms.
    
    Returns 200 when capability is proven within threshold.
    Returns 503 when capability cannot be proven.
    
    Use for: Deep health checks, worker fleet validation (NOT for liveness).
    
    WARNING: Do not wire as Kubernetes liveness probe - this endpoint
    can legitimately fail during queue backlog/worker scaling, which
    should not trigger pod restarts.
    """
    probe, was_cached = _get_or_execute_probe()
    
    result = {
        "status": "ok" if probe.worker_ok else "unhealthy",
        "broker": "ok" if probe.broker_ok else "error",
        "database": "ok" if probe.database_ok else "error",
        "worker": "ok" if probe.worker_ok else "error",
        "probe_latency_ms": probe.latency_ms,
        "cached": was_cached,
        "cache_scope": "process",
    }
    
    if not probe.worker_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        if probe.error:
            logger.warning(
                "worker_capability_probe_failed",
                extra={"error": probe.error, "cached": was_cached},
            )
    
    return result


# ============================================================================
# Metrics Endpoint (B0.5.6.7: No split-brain)
# ============================================================================

def _get_metrics_data() -> bytes:
    """
    Generate Prometheus metrics for the API process.

    B0.5.6.7: No split-brain. API `/metrics` must not aggregate from
    `PROMETHEUS_MULTIPROC_DIR` because that directory belongs to Celery worker
    task metrics and is exposed via the dedicated exporter.
    """
    from app.observability import broker_queue_stats

    broker_queue_stats.ensure_default_registry_registered()

    # B0.5.6.7: Even if worker modules are imported in-process (e.g., test suite
    # configuring Celery), API `/metrics` must not expose worker task metrics.
    from prometheus_client import CollectorRegistry, REGISTRY

    excluded_prefixes = (
        "celery_task_",
        "matview_refresh_",
        "multiproc_",
    )

    class _FilteredDefaultRegistryCollector:
        def collect(self):
            for metric in REGISTRY.collect():
                if metric.name.startswith(excluded_prefixes):
                    continue
                yield metric

    registry = CollectorRegistry(auto_describe=True)
    registry.register(_FilteredDefaultRegistryCollector())
    return generate_latest(registry)


@router.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint.

    B0.5.6.7: API `/metrics` exposes API metrics + broker-truth queue gauges only.
    Worker task metrics are exposed via `app.observability.worker_metrics_exporter`.
    """
    from app.observability import broker_queue_stats
    broker_queue_stats.ensure_default_registry_registered()
    await broker_queue_stats.maybe_refresh_broker_queue_stats()
    data = _get_metrics_data()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)
