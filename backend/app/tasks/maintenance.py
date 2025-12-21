"""
Maintenance Background Tasks

Foundation-level maintenance tasks executed by Celery workers. These tasks are
intentionally minimal but syntactically correct, RLS-aware, and wired to the
shared configuration (Postgres-only broker/backend).
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.compiler import IdentifierPreparer

from app.celery_app import celery_app
from app.core.matview_registry import MATERIALIZED_VIEWS
from app.core.pg_locks import try_acquire_refresh_lock, release_refresh_lock
from app.db.session import engine, set_tenant_guc
from app.observability.context import set_request_correlation_id, set_tenant_id
from app.tasks.context import tenant_task

logger = logging.getLogger(__name__)
_IDENTIFIER_PREPARER = IdentifierPreparer(postgresql.dialect())
_PUBLIC_SCHEMA = _IDENTIFIER_PREPARER.quote_schema("public")


def _validated_matview_identifier(
    view_name: str, task_id: Optional[str] = None, tenant_id: Optional[UUID] = None
) -> str:
    """
    Validate matview name against registry and return a safely quoted identifier.

    Using IdentifierPreparer prevents SQL injection even if a malicious name is passed
    in; validation further constrains the surface to the closed registry set.
    """
    from app.core.matview_registry import validate_matview_name

    if not validate_matview_name(view_name):
        logger.error(
            "matview_refresh_invalid_view_name",
            extra={
                "view_name": view_name,
                "task_id": task_id,
                "tenant_id": str(tenant_id) if tenant_id else None,
            },
        )
        raise ValueError(f"View '{view_name}' not in canonical registry")

    return _IDENTIFIER_PREPARER.quote(view_name)


def _qualified_matview_identifier(
    view_name: str, task_id: Optional[str] = None, tenant_id: Optional[UUID] = None
) -> str:
    """
    Return schema-qualified, safely quoted matview identifier.
    """
    quoted_view = _validated_matview_identifier(view_name, task_id=task_id, tenant_id=tenant_id)
    return f"{_PUBLIC_SCHEMA}.{quoted_view}"


async def _refresh_view(view_name: str, task_id: str, tenant_id: Optional[UUID] = None) -> str:
    """
    Refresh a single materialized view with advisory lock serialization.

    B0.5.4.0: Added pg_advisory_lock to prevent duplicate execution (G12 remediation).

    Args:
        view_name: Name of materialized view to refresh
        task_id: Celery task ID for correlation
        tenant_id: Optional tenant UUID (None for global refresh)

    Returns:
        "success" if refreshed, "skipped_already_running" if lock held
    """
    qualified_view = _qualified_matview_identifier(view_name, task_id=task_id, tenant_id=tenant_id)
    async with engine.begin() as conn:
        # Try to acquire advisory lock
        acquired = await try_acquire_refresh_lock(conn, view_name, tenant_id)
        if not acquired:
            logger.info(
                "matview_refresh_skipped_already_running",
                extra={"view_name": view_name, "task_id": task_id, "reason": "lock_held"}
            )
            return "skipped_already_running"

        try:
            # Refresh the view using a schema-qualified, identifier-quoted name to prevent SQL injection
            await conn.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY " + qualified_view))
            logger.info(
                "matview_refreshed",
                extra={"view_name": view_name, "task_id": task_id},
            )
            return "success"
        finally:
            # Release lock
            await release_refresh_lock(conn, view_name, tenant_id)


@celery_app.task(
    bind=True,
    name="app.tasks.maintenance.refresh_all_matviews_global_legacy",
    routing_key="maintenance.task",
    max_retries=3,
    default_retry_delay=60,
)
def refresh_all_matviews_global_legacy(self) -> Dict[str, str]:
    """
    DEPRECATED: Global refresh (non-tenant-scoped).

    B0.5.4.0: This task violates worker-tenant isolation principles by refreshing
    materialized views without tenant context. Kept for backward compatibility
    during B0.5.4 transition; scheduled for removal in B0.5.5.

    Use `refresh_matview_for_tenant` for new integrations.

    Marked for removal: B0.5.5
    """
    correlation_id = getattr(self.request, "correlation_id", None) or str(uuid4())
    set_request_correlation_id(correlation_id)
    results: Dict[str, str] = {}
    try:
        for view_name in MATERIALIZED_VIEWS:
            results[view_name] = asyncio.run(_refresh_view(view_name, self.request.id))
        return results
    except Exception as exc:
        logger.error(
            "matview_refresh_failed",
            exc_info=exc,
            extra={"task_id": self.request.id, "correlation_id": correlation_id},
        )
        raise self.retry(exc=exc, countdown=60)
    finally:
        set_request_correlation_id(None)


@celery_app.task(
    bind=True,
    name="app.tasks.maintenance.refresh_matview_for_tenant",
    routing_key="maintenance.task",
    max_retries=3,
    default_retry_delay=60,
)
@tenant_task
def refresh_matview_for_tenant(self, tenant_id: UUID, view_name: str, correlation_id: Optional[str] = None) -> Dict[str, str]:
    """
    Refresh a single materialized view for a specific tenant.

    B0.5.4.0: Tenant-aware refresh API surface. This is the preferred interface
    for materialized view refresh operations in the worker-tenant isolation model.

    Args:
        tenant_id: UUID of tenant scope
        view_name: Name of materialized view to refresh (must be in registry)
        correlation_id: Optional correlation ID for tracing

    Returns:
        Dict with status, view_name, tenant_id, and result ("success" or "skipped_already_running")

    Raises:
        ValueError: If view_name not in canonical registry
    """
    from app.core.matview_registry import validate_matview_name

    correlation_id = correlation_id or str(uuid4())
    set_request_correlation_id(correlation_id)
    set_tenant_id(tenant_id)

    try:
        _qualified_matview_identifier(view_name, task_id=self.request.id, tenant_id=tenant_id)
        result = asyncio.run(_refresh_view(view_name, self.request.id, tenant_id))
        logger.info(
            "tenant_matview_refresh_completed",
            extra={
                "view_name": view_name,
                "tenant_id": str(tenant_id),
                "task_id": self.request.id,
                "correlation_id": correlation_id,
                "result": result,
            },
        )
        return {
            "status": "ok",
            "view_name": view_name,
            "tenant_id": str(tenant_id),
            "result": result,
        }
    except Exception as exc:
        logger.error(
            "tenant_matview_refresh_failed",
            exc_info=exc,
            extra={
                "view_name": view_name,
                "tenant_id": str(tenant_id),
                "task_id": self.request.id,
                "correlation_id": correlation_id,
            },
        )
        raise self.retry(exc=exc, countdown=60)


async def _validate_db_connection_for_tenant(tenant_id: UUID) -> str:
    async with engine.begin() as conn:
        await set_tenant_guc(conn, tenant_id, local=False)
        res = await conn.execute(text("SELECT current_setting('app.current_tenant_id')"))
        return res.scalar() or ""


@celery_app.task(
    bind=True,
    name="app.tasks.maintenance.scan_for_pii_contamination",
    max_retries=3,
    default_retry_delay=60,
)
@tenant_task
def scan_for_pii_contamination_task(self, tenant_id: UUID, correlation_id: Optional[str] = None) -> Dict[str, str]:
    """
    Stub PII scan task; validates connectivity and tenant context.
    """
    correlation_id = correlation_id or str(uuid4())
    set_request_correlation_id(correlation_id)
    set_tenant_id(tenant_id)
    try:
        current = asyncio.run(_validate_db_connection_for_tenant(tenant_id))
        logger.info(
            "pii_scan_stub_completed",
            extra={"tenant_id": str(tenant_id), "task_id": self.request.id, "correlation_id": correlation_id},
        )
        return {"status": "ok", "tenant_id": str(tenant_id), "guc": current}
    except Exception as exc:
        logger.error(
            "pii_scan_stub_failed",
            exc_info=exc,
            extra={"tenant_id": str(tenant_id), "task_id": self.request.id, "correlation_id": correlation_id},
        )
        raise self.retry(exc=exc, countdown=60)


async def _enforce_retention(tenant_id: UUID, cutoff_90: datetime, cutoff_30: datetime) -> Dict[str, int]:
    async with engine.begin() as conn:
        await set_tenant_guc(conn, tenant_id, local=False)
        events_deleted = (await conn.execute(text("DELETE FROM attribution_events WHERE event_timestamp < :cutoff"), {"cutoff": cutoff_90})).rowcount or 0
        allocations_deleted = (await conn.execute(text("DELETE FROM attribution_allocations WHERE created_at < :cutoff"), {"cutoff": cutoff_90})).rowcount or 0
        dead_events_deleted = (
            await conn.execute(
                text(
                    """
                    DELETE FROM dead_events
                    WHERE remediation_status IN ('resolved', 'abandoned')
                    AND resolved_at < :cutoff
                    """
                ),
                {"cutoff": cutoff_30},
            )
        ).rowcount or 0
        return {
            "events_deleted": events_deleted,
            "allocations_deleted": allocations_deleted,
            "dead_events_deleted": dead_events_deleted,
        }


@celery_app.task(
    bind=True,
    name="app.tasks.maintenance.enforce_data_retention",
    max_retries=3,
    default_retry_delay=60,
)
@tenant_task
def enforce_data_retention_task(self, tenant_id: UUID, correlation_id: Optional[str] = None) -> Dict[str, int]:
    """
    Tenant-scoped retention enforcement with RLS guardrails.
    """
    correlation_id = correlation_id or str(uuid4())
    set_request_correlation_id(correlation_id)
    set_tenant_id(tenant_id)
    cutoff_90_day = datetime.now(timezone.utc) - timedelta(days=90)
    cutoff_30_day = datetime.now(timezone.utc) - timedelta(days=30)
    try:
        results = asyncio.run(_enforce_retention(tenant_id, cutoff_90_day, cutoff_30_day))
        logger.info(
            "retention_enforced",
            extra={
                "tenant_id": str(tenant_id),
                "task_id": self.request.id,
                "correlation_id": correlation_id,
                **results,
            },
        )
        return results
    except Exception as exc:
        logger.error(
            "retention_enforcement_failed",
            exc_info=exc,
            extra={"tenant_id": str(tenant_id), "task_id": self.request.id, "correlation_id": correlation_id},
        )
        raise self.retry(exc=exc, countdown=60)
