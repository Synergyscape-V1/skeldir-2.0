"""
Skeldir Attribution Intelligence - FastAPI Application

This is the main FastAPI application entry point for contract-first enforcement testing.
Routes are organized by domain (auth, attribution, etc.) and must align with OpenAPI contracts.

Contract-First Enforcement:
- All routes under /api/* are governed by contract scope configuration
- Each route must have a corresponding OpenAPI operation
- Static and dynamic conformance checks prevent divergence
"""

import os
from uuid import UUID, uuid4

# B0.5.6.7: No split-brain. PROMETHEUS_MULTIPROC_DIR is reserved for Celery worker
# task metrics shards and must not influence API process metrics.
os.environ.pop("PROMETHEUS_MULTIPROC_DIR", None)

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import (
    http_exception_handler as fastapi_http_exception_handler,
    request_validation_exception_handler as fastapi_request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

# Structured logging for API process (JSON with tenant/correlation context).
from app.observability.logging_config import configure_logging
from app.observability.context import get_request_correlation_id

configure_logging(os.getenv("LOG_LEVEL", "INFO"))

# Import routers
from app.api import (
    auth,
    attribution,
    budget,
    export,
    health,
    investigations,
    privacy,
    platform_oauth,
    platforms,
    reconciliation,
    revenue_verification,
    revenue,
    trust_api,
    trust_export,
    trust_keys,
    webhooks,
)
from app.api.problem_details import problem_details_response

# Import middleware - Phase G: Active Privacy Defense
from app.middleware import PIIStrippingMiddleware
from app.middleware.observability import ObservabilityMiddleware
from app.security.auth import AuthError, forbidden_auth_error, unauthorized_auth_error
from app.core.secrets import assert_runtime_secret_contract
from app.trust.tenant_security import (
    TenantContextMissingException,
    tenant_context_missing_exception_handler,
)

# Initialize FastAPI app
app = FastAPI(
    title="Skeldir Attribution Intelligence API",
    version="1.0.0",
    description="Privacy-first attribution intelligence platform",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# PII Stripping Middleware - Phase G: Defense-in-Depth Layer 1
# Must be added BEFORE other middleware to ensure PII is stripped first
app.add_middleware(PIIStrippingMiddleware)

# Observability middleware: correlation ID context + response header echo
app.add_middleware(ObservabilityMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(attribution.router, prefix="/api/attribution", tags=["Attribution"])
app.include_router(platforms.router, prefix="/api/attribution", tags=["Platform Connections"])
app.include_router(platform_oauth.router, prefix="/api/attribution", tags=["Provider OAuth Lifecycle"])
app.include_router(revenue.router, prefix="/api/v1", tags=["Revenue"])
app.include_router(privacy.router, prefix="/api/v1", tags=["Privacy"])
app.include_router(reconciliation.router, prefix="/api/reconciliation", tags=["Reconciliation"])
app.include_router(
    revenue_verification.router,
    prefix="/api/reconciliation",
    tags=["Revenue Verification"],
)
app.include_router(export.router, prefix="/api/export", tags=["Export"])
from app.api import trust_simulations

app.include_router(trust_simulations.router, prefix="/api", tags=["Trust Simulations"])
app.include_router(trust_api.router, prefix="/api", tags=["Trust API"])
app.include_router(trust_export.router, prefix="/api", tags=["Trust Export"])
app.include_router(trust_keys.router, prefix="/api", tags=["Trust Keys"])
app.include_router(health.router, tags=["Health"])
app.include_router(webhooks.router, prefix="/api", tags=["Webhooks"])
app.include_router(investigations.router, tags=["Investigations"])
app.include_router(budget.router, tags=["Budget"])

# Health endpoints are now exclusively in app.api.health with explicit semantics:
# - /health: Legacy alias for liveness only
# - /health/live: Pure liveness (no deps)
# - /health/ready: Readiness (DB + RLS + GUC)
# - /health/worker: Worker capability (data-plane probe)

@app.on_event("startup")
async def _startup_secret_contract_guard() -> None:
    """Fail closed at boot when required security secrets are unavailable."""
    assert_runtime_secret_contract("api")


@app.on_event("startup")
async def _startup_xii_topology_guard() -> None:
    """B2.6-P2 Corrective XII: refuse to serve when required auth topology absent.

    One XII migration identity represents one authentication law. When the
    database is at/above the XII head but the ingress principal or its
    strict grants are missing, the application is unmistakably
    unavailable instead of silently serving predecessor law.
    """
    import logging

    from sqlalchemy import text

    from app.db.session import engine

    logger = logging.getLogger(__name__)
    try:
        async with engine.begin() as conn:
            head = await conn.execute(text("SELECT version_num FROM alembic_version"))
            heads = [str(r[0]) for r in head.fetchall()]
            if "202609250001" not in heads:
                return
            present = await conn.execute(
                text("SELECT count(*) FROM pg_roles WHERE rolname = 'app_ingress'")
            )
            present_row = present.fetchone()
            if present_row is None or int(present_row[0]) != 1:
                raise RuntimeError(
                    "b26_p2_xii_ingress_topology_absent: XII head requires"
                    " the app_ingress principal"
                )
            topo = await conn.execute(
                text("SELECT public.b26_p2_xii_topology_check()")
            )
            topo.fetchone()
    except RuntimeError:
        raise
    except Exception as exc:
        logger.warning("b26_p2_xii_topology_guard_deferred:%s", exc)


@app.get("/")
async def root():
    """Root endpoint - redirects to documentation."""
    return {
        "message": "Skeldir Attribution Intelligence API",
        "docs": "/docs",
        "openapi": "/openapi.json"
    }


@app.exception_handler(AuthError)
async def auth_error_handler(request: Request, exc: AuthError):
    correlation_id = _resolve_problem_correlation_id(request)
    return problem_details_response(
        request,
        status_code=exc.status_code,
        title=exc.title,
        detail=exc.detail,
        correlation_id=correlation_id,
        type_url=exc.type_url,
        code=exc.code,
    )


app.add_exception_handler(
    TenantContextMissingException,
    tenant_context_missing_exception_handler,
)
app.add_exception_handler(
    trust_api.TrustRequestBoundaryException,
    trust_api.trust_request_boundary_exception_handler,
)
app.add_exception_handler(
    trust_export.TrustExportRequestBoundaryException,
    trust_export.trust_export_request_boundary_exception_handler,
)


@app.exception_handler(HTTPException)
async def normalized_http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code not in (401, 403):
        return await fastapi_http_exception_handler(request, exc)
    normalized = unauthorized_auth_error() if exc.status_code == 401 else forbidden_auth_error()
    correlation_id = _resolve_problem_correlation_id(request)
    return problem_details_response(
        request,
        status_code=normalized.status_code,
        title=normalized.title,
        detail=normalized.detail,
        correlation_id=correlation_id,
        type_url=normalized.type_url,
        code=normalized.code,
    )


@app.exception_handler(RequestValidationError)
async def normalized_request_validation_handler(request: Request, exc: RequestValidationError):
    return await fastapi_request_validation_exception_handler(request, exc)


def _resolve_problem_correlation_id(request: Request) -> UUID:
    correlation_value = get_request_correlation_id() or request.headers.get("X-Correlation-ID")
    try:
        return UUID(str(correlation_value))
    except (TypeError, ValueError):
        return uuid4()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
