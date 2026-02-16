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

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

# Structured logging for API process (JSON with tenant/correlation context).
from app.observability.logging_config import configure_logging
from app.observability.context import get_request_correlation_id

configure_logging(os.getenv("LOG_LEVEL", "INFO"))

# Import routers
from app.api import auth, attribution, export, health, reconciliation, revenue, webhooks, platforms
from app.api.problem_details import problem_details_response
from app.api.webhook_validation import handle_request_validation_error

# Import middleware - Phase G: Active Privacy Defense
from app.middleware import PIIStrippingMiddleware
from app.middleware.observability import ObservabilityMiddleware
from app.security.auth import AuthError

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
app.include_router(revenue.router, prefix="/api/v1", tags=["Revenue"])
app.include_router(reconciliation.router, prefix="/api/reconciliation", tags=["Reconciliation"])
app.include_router(export.router, prefix="/api/export", tags=["Export"])
app.include_router(health.router, tags=["Health"])
app.include_router(webhooks.router, prefix="/api", tags=["Webhooks"])

# Health endpoints are now exclusively in app.api.health with explicit semantics:
# - /health: Legacy alias for liveness only
# - /health/live: Pure liveness (no deps)
# - /health/ready: Readiness (DB + RLS + GUC)
# - /health/worker: Worker capability (data-plane probe)


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
    correlation_value = get_request_correlation_id() or request.headers.get("X-Correlation-ID")
    try:
        correlation_id = UUID(str(correlation_value))
    except (TypeError, ValueError):
        correlation_id = uuid4()
    return problem_details_response(
        request,
        status_code=exc.status_code,
        title=exc.title,
        detail=exc.detail,
        correlation_id=correlation_id,
        type_url=exc.type_url,
    )


@app.exception_handler(RequestValidationError)
async def request_validation_handler(request: Request, exc: RequestValidationError):
    return await handle_request_validation_error(request, exc)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
