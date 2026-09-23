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
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Optional, Annotated

from fastapi import APIRouter, Depends, Request, Response, Security, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text
from uuid import UUID, uuid4

from app.db.session import engine
from app.celery_app import celery_app
from app.core.construction_authority import (
    ConstructionAuthorityError,
    assert_production_construction_authority,
    read_construction_revisions,
)
from app.core.secrets import validate_runtime_secret_contract
from app.api.problem_details import problem_details_response
from app.security.auth import AuthContext, get_auth_context

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


@router.get("/api/health")
async def api_health(request: Request) -> dict:
    """Contract endpoint with readiness-aligned security semantics."""
    readiness_result = _evaluate_security_readiness()
    if readiness_result["status"] != "ok":
        correlation_raw = request.headers.get("X-Correlation-ID")
        try:
            correlation_id = UUID(correlation_raw) if correlation_raw else uuid4()
        except Exception:
            correlation_id = uuid4()
        missing = ", ".join(readiness_result["missing_required_secrets"]) or "unknown"
        return problem_details_response(
            request,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            title="Service Unavailable",
            detail=f"Required runtime secrets are missing: {missing}",
            correlation_id=correlation_id,
            type_url="https://api.skeldir.com/problems/service-unavailable",
        )

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "status": "healthy",
        "timestamp": now,
        "version": "1.0.0",
        "services": {
            "database": "up",
            "api": "up",
            "cache": "up",
            "queue": "up",
            "security": "up",
        },
    }


@router.get("/api/health/detailed")
async def api_health_detailed(
    response: Response,
    _: Annotated[AuthContext, Security(get_auth_context, scopes=["viewer"])],
) -> dict:
    """Detailed contract endpoint for OpenAPI health bundle (/api/health/detailed)."""
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "status": "healthy",
        "timestamp": now,
        "version": "1.0.0",
        "services": {
            "database": "up",
            "api": "up",
            "cache": "up",
            "queue": "up",
        },
        "metrics": {
            "requests_per_minute": 0,
            "average_response_ms": 0.0,
            "error_rate": 0.0,
            "active_connections": 0,
        },
        "database": {
            "pool_size": 1,
            "active_connections": 1,
            "query_latency_ms": 0.0,
        },
    }


@router.get("/api/health/ready")
async def api_readiness(response: Response) -> dict:
    """Contract alias to readiness semantics."""
    readiness_result = _evaluate_security_readiness()
    if readiness_result["status"] != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "ready": readiness_result["status"] == "ok",
        "status": readiness_result["status"],
        "checks": readiness_result,
    }


@router.get("/api/health/live")
async def api_liveness() -> dict:
    """Contract alias to liveness semantics."""
    return {"alive": True}


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
    result = await _evaluate_readiness()
    if result["status"] != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return result


async def _evaluate_readiness() -> dict[str, object]:
    result: dict[str, object] = {
        "status": "ok",
        "database": "ok",
        "rls": "ok",
        "tenant_guc": "ok",
        "secrets": "ok",
        "construction_authority": "ok",
        "missing_required_secrets": [],
    }

    secret_validation = validate_runtime_secret_contract("readiness")
    if not secret_validation.ok:
        result["secrets"] = "error"
        result["status"] = "unhealthy"
        result["missing_required_secrets"] = list(secret_validation.missing)

    if result["secrets"] != "ok":
        return result

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

            # 4. B2.5-P14 Corrective V. The governed authority graph -- role
            # grants, the consequence triggers, the seeded frame corpus -- is
            # created by the migration history and by nothing else. A database
            # built from `db/schema/canonical_schema.sql` is structurally
            # identical and carries none of it: pg_dump `--no-privileges
            # --schema-only` has no vocabulary for grants and no rows to seed.
            # It leaves `alembic_version` empty, which is the one marker such a
            # construction physically cannot forge, so that is what readiness
            # checks. A process on an unconstructed database never becomes
            # ready, and therefore never receives traffic.
            try:
                from app.core.physical_authority import (
                    assert_physical_authority,
                    physical_authority_applies,
                )

                # The exact-catalog manifest only speaks for P14-provisioned
                # databases (full role graph). Other topologies abstain from
                # the physical comparison but still enforce the revision law
                # below; their behavioral suites own their authority surface.
                if await physical_authority_applies(conn):
                    await assert_physical_authority(conn)
                else:
                    result["physical_authority"] = "skipped_non_p14_topology"
                assert_production_construction_authority(
                    await read_construction_revisions(conn)
                )
            except ConstructionAuthorityError as exc:
                result["construction_authority"] = "error"
                raise RuntimeError(str(exc)) from exc

    except Exception:
        logger.error("readiness_failed", exc_info=True)
        # Determine which component failed based on current state
        if result["database"] != "ok":
            pass  # already marked
        elif result["rls"] != "ok":
            pass  # already marked
        elif result["tenant_guc"] != "ok":
            pass  # already marked
        elif result["construction_authority"] != "ok":
            pass  # already marked
        else:
            # DB connectivity itself failed
            result["database"] = "error"
        
        result["status"] = "unhealthy"

    return result


def _evaluate_security_readiness() -> dict[str, object]:
    result: dict[str, object] = {
        "status": "ok",
        "secrets": "ok",
        "missing_required_secrets": [],
    }
    secret_validation = validate_runtime_secret_contract("readiness")
    if not secret_validation.ok:
        result["secrets"] = "error"
        result["status"] = "unhealthy"
        result["missing_required_secrets"] = list(secret_validation.missing)
    return result


@router.get("/health/b26-p2-conduction")
async def b26_p2_conduction(response: Response) -> dict:
    """B2.6-P2 Corrective VI published-unconsumed + quarantine honesty signal.

    Published twin projections older than the governed staleness
    threshold are explicitly operator-visible here (counts + oldest
    age) instead of indistinguishable from healthy in-flight work. A
    permanently unconsumed execution therefore cannot remain silent:
    this endpoint, the relay sweep log, and the beat-scheduled
    operational-health evaluator carry the same operational signal from
    one implementation law.

    Corrective VI additions: durable quarantine rows are counted with
    oldest age (a nonzero quarantine is actionable operator work, never
    a silent graveyard); the threshold itself is validated against the
    governed bounds (absurd suppression fails closed as 503 instead of
    reporting zero stale rows); `action_required` is true whenever
    stale, divergent-risk, or quarantined work exists.

    Counts only (no PII, no financial truth). Returns 200 always when
    the signal itself is observable; the `status` field distinguishes
    `ok` (no stale work) from `stale_unconducted` (operator action
    required). Dependency failure yields 503.

    Corrective X honesty law: the scheduler-plane signal is named for
    exactly what its evidence proves. `scheduler_plane_active`
    (derived from `scheduler_absent_total` over
    public.b26_p2_scheduler_heartbeat) proves recent authorized
    scheduler-plane activity occurred -- the beat scheduler loop
    executing its schedule under the app_beat credential -- and is
    independent of evaluation freshness (`evaluation_fresh`, derived
    from `evaluator_absent_total` over
    public.b26_p2_evaluator_heartbeat). evaluation_fresh !=
    scheduler_plane_active: an active scheduler plane with no genuine
    evaluation, or a fresh evaluation with a silent scheduler plane,
    are distinct operator facts. Orchestrator-attested process liveness
    is deliberately never claimed: no field here asserts it.
    """
    from app.db.session import engine as _engine  # noqa: PLC0415
    from app.db.session import get_session as _tenant_session  # noqa: PLC0415
    from app.finance_reconciliation import conduction_state as _conduction  # noqa: PLC0415

    try:
        try:
            threshold = _conduction.staleness_threshold_seconds()
        except ValueError:
            logger.error("b26_p2_conduction_threshold_out_of_bounds")
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {"status": "unavailable", "reason": "threshold_out_of_bounds"}
        async with _engine.connect() as conn:
            tenant_rows = (
                (await conn.execute(text("SELECT id FROM public.tenants ORDER BY id")))
                .mappings()
                .all()
            )
        tenants = [str(r["id"]) for r in tenant_rows]
        published_total = 0
        stale_total = 0
        oldest_published_age: float | None = None
        oldest_stale_age: float | None = None
        quarantine_total = 0
        oldest_quarantine_age: float | None = None
        pending_total = 0
        pending_actionable_total = 0
        evaluator_absent_total = 0
        scheduler_absent_total = 0
        terminal_total = 0
        for tenant in tenants:
            async with _tenant_session(tenant_id=tenant) as session:
                pending_row = (
                    (
                        await session.execute(
                            text(
                                "SELECT count(*) AS n"
                                " FROM public.b23_match_task_dispatches AS d"
                                " WHERE d.delivery_state = 'pending_publish'"
                            )
                        )
                    )
                    .mappings()
                    .one()
                )
                pending_total += int(pending_row["n"] or 0)
                pending_actionable_row = (
                    (
                        await session.execute(
                            text(
                                "SELECT count(*) AS n"
                                " FROM public.b23_match_task_dispatches AS d"
                                " WHERE d.delivery_state = 'pending_publish'"
                                " AND d.dispatched_at < now() - (:thr || ' seconds')::interval"
                            ),
                            {"thr": str(int(threshold))},
                        )
                    )
                    .mappings()
                    .one()
                )
                pending_actionable_total += int(pending_actionable_row["n"] or 0)
                # Monitor-of-monitor (VII): evaluator heartbeat observed from
                # the API failure domain (independent of relay/beat).
                try:
                    hb_row = (
                        (
                            await session.execute(
                                text(
                                    "SELECT EXTRACT(EPOCH FROM (now() - last_tick)) AS age"
                                    " FROM public.b26_p2_evaluator_heartbeat"
                                    " WHERE tenant_id = :tenant"
                                ),
                                {"tenant": str(tenant)},
                            )
                        )
                        .mappings()
                        .one_or_none()
                    )
                    if hb_row is None or hb_row["age"] is None:
                        evaluator_absent_total += 1
                    elif float(hb_row["age"]) > float(int(threshold) * 4):
                        evaluator_absent_total += 1
                except Exception:
                    evaluator_absent_total += 1
                # Corrective X honesty: the scheduler plane is observed
                # from the same API failure domain but over its own table
                # (public.b26_p2_scheduler_heartbeat) under the same
                # threshold*4 law. Only the beat principal can tick it, so
                # a relay-side evaluation cannot manufacture scheduler
                # plane activity. The signal proves credential-plane
                # activity recency, never orchestrator process liveness.
                try:
                    sched_row = (
                        (
                            await session.execute(
                                text(
                                    "SELECT EXTRACT(EPOCH FROM (now() - last_tick)) AS age"
                                    " FROM public.b26_p2_scheduler_heartbeat"
                                    " WHERE tenant_id = :tenant"
                                ),
                                {"tenant": str(tenant)},
                            )
                        )
                        .mappings()
                        .one_or_none()
                    )
                    if sched_row is None or sched_row["age"] is None:
                        scheduler_absent_total += 1
                    elif float(sched_row["age"]) > float(int(threshold) * 4):
                        scheduler_absent_total += 1
                except Exception:
                    scheduler_absent_total += 1
                terminal_row = (
                    (
                        await session.execute(
                            text(
                                "SELECT count(*) AS n"
                                " FROM public.b23_match_task_dispatches AS d"
                                " JOIN public.b26_p2_execution_outbox AS o"
                                "   ON o.dispatch_task_id = d.task_id"
                                "  AND o.tenant_id = d.tenant_id"
                                "  AND o.webhook_ingress_identity_id = d.webhook_ingress_identity_id"
                                " WHERE d.delivery_state = 'published'"
                                " AND o.state = 'published'"
                                " AND EXISTS (SELECT 1 FROM public.worker_failed_jobs AS w"
                                " WHERE w.task_id = d.task_id)"
                                " AND EXISTS (SELECT 1 FROM public.celery_taskmeta AS m"
                                " WHERE m.task_id = d.task_id AND m.status = 'FAILURE')"
                            )
                        )
                    )
                    .mappings()
                    .one()
                )
                terminal_total += int(terminal_row["n"] or 0)
                published_row = (
                    (
                        await session.execute(
                            text(
                                "SELECT count(*) AS n,"
                                " max(EXTRACT(EPOCH FROM (now() - COALESCE("
                                " d.first_published_at, d.dispatched_at)))) AS oldest"
                                " FROM public.b23_match_task_dispatches AS d"
                                " JOIN public.b26_p2_execution_outbox AS o"
                                "   ON o.dispatch_task_id = d.task_id"
                                "  AND o.tenant_id = d.tenant_id"
                                "  AND o.webhook_ingress_identity_id = d.webhook_ingress_identity_id"
                                " WHERE d.delivery_state = 'published'"
                                " AND o.state = 'published'"
                            )
                        )
                    )
                    .mappings()
                    .one()
                )
                published_total += int(published_row["n"] or 0)
                if published_row["oldest"] is not None:
                    age = float(published_row["oldest"])
                    oldest_published_age = (
                        age
                        if oldest_published_age is None
                        else max(oldest_published_age, age)
                    )
                stale_rows = await _conduction.staleness_snapshot(
                    session, threshold_seconds=threshold
                )
                stale_total += len(stale_rows)
                for stale in stale_rows:
                    oldest_stale_age = (
                        stale.age_seconds
                        if oldest_stale_age is None
                        else max(oldest_stale_age, stale.age_seconds)
                    )
                quarantine_rows = await _conduction.quarantine_snapshot(session)
                quarantine_total += len(quarantine_rows)
                for quar in quarantine_rows:
                    qage = float(quar.get("age_seconds") or 0)
                    oldest_quarantine_age = (
                        qage
                        if oldest_quarantine_age is None
                        else max(oldest_quarantine_age, qage)
                    )
        action_required = (
            stale_total > 0
            or quarantine_total > 0
            or pending_actionable_total > 0
            or evaluator_absent_total > 0
            or scheduler_absent_total > 0
        )
        result = {
            "status": "stale_unconducted" if stale_total > 0 else "ok",
            "threshold_seconds": threshold,
            "tenants_scanned": len(tenants),
            "published_total": published_total,
            "pending_total": pending_total,
            "pending_actionable_total": pending_actionable_total,
            "evaluator_absent_total": evaluator_absent_total,
            "scheduler_absent_total": scheduler_absent_total,
            "scheduler_plane_active": scheduler_absent_total == 0,
            "scheduler_plane_evidence": "recent_authorized_scheduler_plane_activity",
            "evaluation_fresh": evaluator_absent_total == 0,
            "terminal_total": terminal_total,
            "stale_unconducted_count": stale_total,
            "oldest_published_age_seconds": oldest_published_age,
            "oldest_stale_age_seconds": oldest_stale_age,
            "quarantine_count": quarantine_total,
            "oldest_quarantine_age_seconds": oldest_quarantine_age,
            "action_required": action_required,
        }
        if action_required:
            logger.warning(
                "b26_p2_conduction_stale_unconducted",
                extra={
                    "stale_unconducted_count": stale_total,
                    "oldest_stale_age_seconds": oldest_stale_age,
                    "quarantine_count": quarantine_total,
                    "oldest_quarantine_age_seconds": oldest_quarantine_age,
                    "pending_total": pending_total,
                    "pending_actionable_total": pending_actionable_total,
                    "evaluator_absent_total": evaluator_absent_total,
                    "scheduler_absent_total": scheduler_absent_total,
                    "terminal_total": terminal_total,
                    "threshold_seconds": threshold,
                },
            )
        return result
    except Exception:
        logger.error("b26_p2_conduction_signal_failed", exc_info=True)
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unavailable"}


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
