"""
Tenant Context Propagation Module

This module implements the canonical tenant context derivation and database session wiring
for Phase 2 of the B0.3 Functional Implementation Plan.

Contract: Every tenant-scoped DB interaction MUST carry an unambiguous tenant context
from the edge (auth) down to the DB session, so RLS can actually work.

Related Documents:
- docs/database/Database_Schema_Functional_Implementation_Plan.md (Phase 2)
- db/docs/ROLES_AND_GRANTS.md (Role model)
"""

import logging
import hashlib
import time
from collections import OrderedDict
from threading import Lock
from typing import Optional
from uuid import UUID

from fastapi import Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.db.session import engine
from app.core.config import settings

logger = logging.getLogger(__name__)


class TenantContextError(Exception):
    """Raised when tenant context cannot be derived or is invalid."""
    pass


_TENANT_SECRET_CACHE: OrderedDict[str, tuple[float, dict]] = OrderedDict()
_TENANT_SECRET_CACHE_LOCK = Lock()


def _tenant_secret_cache_get(api_key_hash: str) -> Optional[dict]:
    now = time.monotonic()
    with _TENANT_SECRET_CACHE_LOCK:
        entry = _TENANT_SECRET_CACHE.get(api_key_hash)
        if entry is None:
            return None
        inserted_at, payload = entry
        if (now - inserted_at) > settings.TENANT_SECRETS_CACHE_TTL_SECONDS:
            _TENANT_SECRET_CACHE.pop(api_key_hash, None)
            return None
        _TENANT_SECRET_CACHE.move_to_end(api_key_hash)
        # Return a shallow copy so callers cannot mutate cache state.
        return dict(payload)


def _tenant_secret_cache_put(api_key_hash: str, payload: dict) -> None:
    with _TENANT_SECRET_CACHE_LOCK:
        _TENANT_SECRET_CACHE[api_key_hash] = (time.monotonic(), dict(payload))
        _TENANT_SECRET_CACHE.move_to_end(api_key_hash)
        while len(_TENANT_SECRET_CACHE) > settings.TENANT_SECRETS_CACHE_MAX_ENTRIES:
            _TENANT_SECRET_CACHE.popitem(last=False)


async def get_tenant_with_webhook_secrets(api_key: str) -> dict:
    """
    Resolve tenant identity and webhook secrets by tenant API key.

    Webhook ingress (B0.4) uses a tenant-scoped API key header to select the tenant
    and verify vendor signatures deterministically.

    Returns:
        dict with keys: tenant_id (UUID), shopify_webhook_secret, stripe_webhook_secret,
        paypal_webhook_secret, woocommerce_webhook_secret

    Raises:
        HTTPException(401): if the key is missing/unknown
    """
    if not api_key or not api_key.strip():
        raise HTTPException(status_code=401, detail={"status": "invalid_tenant_key"})

    api_key_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
    cached = _tenant_secret_cache_get(api_key_hash)
    if cached is not None:
        return cached

    async with engine.connect() as conn:
        res = await conn.execute(
            text(
                """
                SELECT
                  tenant_id,
                  shopify_webhook_secret,
                  stripe_webhook_secret,
                  paypal_webhook_secret,
                  woocommerce_webhook_secret
                FROM security.resolve_tenant_webhook_secrets(:api_key_hash)
                """
            ),
            {"api_key_hash": api_key_hash},
        )
        row = res.mappings().first()

    if not row:
        raise HTTPException(status_code=401, detail={"status": "invalid_tenant_key"})

    payload = {
        "tenant_id": UUID(str(row["tenant_id"])),
        "shopify_webhook_secret": row.get("shopify_webhook_secret"),
        "stripe_webhook_secret": row.get("stripe_webhook_secret"),
        "paypal_webhook_secret": row.get("paypal_webhook_secret"),
        "woocommerce_webhook_secret": row.get("woocommerce_webhook_secret"),
    }
    _tenant_secret_cache_put(api_key_hash, payload)
    return payload


def derive_tenant_id_from_request(request: Request) -> Optional[UUID]:
    """
    Canonical algorithm for deriving tenant_id from API requests.
    
    Derivation order:
    1. JWT claims: `request.state.auth_context.tenant_id` (set by B1.2 Auth middleware)
    2. API Key: Lookup `tenants.api_key_hash` → `tenants.id` (for API key authentication)
    
    Args:
        request: FastAPI request object with auth context
        
    Returns:
        Tenant UUID if successfully derived, None otherwise
        
    Raises:
        TenantContextError: If tenant_id is required but cannot be derived
    """
    # Priority 1: JWT claims (B1.2 Auth middleware sets this)
    if hasattr(request.state, 'auth_context') and hasattr(request.state.auth_context, 'tenant_id'):
        tenant_id = request.state.auth_context.tenant_id
        if tenant_id:
            logger.debug(
                "Tenant ID derived from JWT auth context",
                extra={"tenant_id": str(tenant_id), "source": "jwt"}
            )
            return UUID(str(tenant_id)) if isinstance(tenant_id, str) else tenant_id
    
    # Priority 2: API Key (if API key authentication is used)
    # TODO: Implement API key lookup when B1.2 API key auth is implemented
    # For now, this is a placeholder
    api_key = request.headers.get("X-API-Key")
    if api_key:
        # Future: Lookup tenants.api_key_hash → tenants.id
        logger.warning(
            "API key authentication not yet implemented",
            extra={"api_key_present": True}
        )
    
    return None


async def set_tenant_context_on_session(
    session: AsyncSession,
    tenant_id: UUID,
    local: bool = True
) -> None:
    """
    Set tenant context on database session using PostgreSQL GUC.
    
    This function executes `SET LOCAL app.current_tenant_id = :tenant_id` (or `SET app.current_tenant_id`)
    to enable RLS policy evaluation.
    
    Args:
        session: SQLAlchemy async session
        tenant_id: Tenant UUID to set as context
        local: If True, use `SET LOCAL` (transaction-scoped). If False, use `SET` (session-scoped).
        
    Raises:
        Exception: If SQL execution fails
    """
    command = "SET LOCAL app.current_tenant_id" if local else "SET app.current_tenant_id"
    await session.execute(
        text(f"{command} = :tenant_id"),
        {"tenant_id": str(tenant_id)}
    )
    logger.debug(
        "Tenant context set on database session",
        extra={"tenant_id": str(tenant_id), "scope": "local" if local else "session"}
    )


async def clear_tenant_context_on_session(session: AsyncSession) -> None:
    """
    Clear tenant context by rolling back the transaction (for SET LOCAL) or resetting GUC.
    
    Note: For SET LOCAL, rolling back the transaction automatically clears the variable.
    This function is provided for explicit cleanup if needed.
    
    Args:
        session: SQLAlchemy async session
    """
    # SET LOCAL variables are automatically cleared on transaction end
    # This is a no-op for SET LOCAL, but useful for documentation
    logger.debug("Tenant context will be cleared on transaction end (SET LOCAL)")


async def tenant_context_middleware(request: Request, call_next):
    """
    FastAPI middleware that sets tenant context on database session.
    
    This middleware:
    1. Derives tenant_id from request (JWT or API key)
    2. Sets `app.current_tenant_id` on the database session
    3. Ensures context is cleared on request completion (via transaction rollback)
    
    Usage:
        app.add_middleware(BaseHTTPMiddleware, dispatch=tenant_context_middleware)
    
    Args:
        request: FastAPI request object
        call_next: Next middleware/handler in chain
        
    Returns:
        Response from downstream handler
        
    Raises:
        HTTPException: 500 if tenant context is missing and required
    """
    # Derive tenant_id from request
    tenant_id = derive_tenant_id_from_request(request)
    
    if not tenant_id:
        logger.error(
            "Tenant context missing from request",
            extra={
                "event_type": "rls_violation",
                "endpoint": str(request.url.path),
                "method": request.method,
            }
        )
        raise HTTPException(
            status_code=500,
            detail="Tenant context missing. Authentication required."
        )
    
    # Get database session from request state (set by database dependency)
    if not hasattr(request.state, 'db_session'):
        logger.error(
            "Database session not found in request state",
            extra={"tenant_id": str(tenant_id)}
        )
        raise HTTPException(
            status_code=500,
            detail="Database session not available"
        )
    
    session: AsyncSession = request.state.db_session
    
    # Set tenant context on session (SET LOCAL for transaction scope)
    try:
        await set_tenant_context_on_session(session, tenant_id, local=True)
        
        # Process request
        response = await call_next(request)
        
        return response
        
    except Exception as e:
        logger.error(
            "Error in tenant context middleware",
            extra={"tenant_id": str(tenant_id), "error": str(e)},
            exc_info=True
        )
        # Transaction rollback will clear SET LOCAL automatically
        raise
    finally:
        # SET LOCAL is automatically cleared on transaction end
        # Explicit rollback not needed unless we want to ensure cleanup
        pass

