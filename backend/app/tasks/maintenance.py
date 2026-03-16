"""
Maintenance Background Tasks

Foundation-level maintenance tasks executed by Celery workers. These tasks are
intentionally minimal but syntactically correct, RLS-aware, and wired to the
shared configuration (Postgres-only broker/backend).
"""

import logging
import os
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.compiler import IdentifierPreparer

from app.celery_app import celery_app
from app.matviews.registry import get_entry, list_names
from app.matviews.executor import RefreshOutcome, refresh_single
from app.db.session import AsyncSessionLocal, engine, set_tenant_guc
from app.observability.context import set_request_correlation_id, set_tenant_id
from app.services.provider_token_refresh import (
    claim_due_credentials_for_tenant,
    refresh_credential_once,
)
from app.tasks.authority import SystemAuthorityEnvelope
from app.tasks.context import run_in_worker_loop
from app.tasks.enqueue import enqueue_tenant_task
from app.tasks.tenant_base import TenantTask, task_tenant_id

logger = logging.getLogger(__name__)
_IDENTIFIER_PREPARER = IdentifierPreparer(postgresql.dialect())
_PUBLIC_SCHEMA = _IDENTIFIER_PREPARER.quote_schema("public")
_DEFAULT_DENYLIST_GC_BATCH_SIZE = 1000
_DENYLIST_GC_SINGLEFLIGHT_LOCK_KEY = 1205001
_DEFAULT_PROVIDER_REFRESH_BATCH_SIZE = 100


def _validated_matview_identifier(
    view_name: str, task_id: Optional[str] = None, tenant_id: Optional[UUID] = None
) -> str:
    """
    Validate matview name against registry and return a safely quoted identifier.

    Using IdentifierPreparer prevents SQL injection even if a malicious name is passed
    in; validation further constrains the surface to the closed registry set.
    """
    try:
        get_entry(view_name)
    except ValueError:
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
        for view_name in list_names():
            result = refresh_single(view_name, None, correlation_id)
            results[view_name] = result.to_log_dict()
            if result.outcome == RefreshOutcome.FAILED:
                raise RuntimeError(f"Matview refresh failed: {view_name}")
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
    base=TenantTask,
    name="app.tasks.maintenance.refresh_matview_for_tenant",
    routing_key="maintenance.task",
    max_retries=3,
    default_retry_delay=60,
)
def refresh_matview_for_tenant(
    self,
    view_name: str,
    correlation_id: Optional[str] = None,
) -> Dict[str, str]:
    """
    Refresh a single materialized view for a specific tenant.

    B0.5.4.0: Tenant-aware refresh API surface. This is the preferred interface
    for materialized view refresh operations in the worker-tenant isolation model.

    Args:
        view_name: Name of materialized view to refresh (must be in registry)
        correlation_id: Optional correlation ID for tracing

    Returns:
        Dict with status, view_name, tenant_id, and result ("success" or "skipped_already_running")

    Raises:
        ValueError: If view_name not in canonical registry
    """
    tenant_id = task_tenant_id(self)
    correlation_id = correlation_id or str(uuid4())
    set_request_correlation_id(correlation_id)
    set_tenant_id(tenant_id)

    try:
        _qualified_matview_identifier(view_name, task_id=self.request.id, tenant_id=tenant_id)
        result = refresh_single(view_name, tenant_id, correlation_id)
        logger.info(
            "tenant_matview_refresh_completed",
            extra={
                "view_name": view_name,
                "tenant_id": str(tenant_id),
                "task_id": self.request.id,
                "correlation_id": correlation_id,
                "result": result.to_log_dict(),
            },
        )
        if result.outcome == RefreshOutcome.FAILED:
            raise RuntimeError("Matview refresh failed")
        return {
            "status": "ok",
            "view_name": view_name,
            "tenant_id": str(tenant_id),
            "result": result.to_log_dict(),
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
        await set_tenant_guc(conn, tenant_id, local=True)
        res = await conn.execute(text("SELECT current_setting('app.current_tenant_id')"))
        return res.scalar() or ""


@celery_app.task(
    bind=True,
    base=TenantTask,
    name="app.tasks.maintenance.scan_for_pii_contamination",
    max_retries=3,
    default_retry_delay=60,
)
def scan_for_pii_contamination_task(
    self,
    correlation_id: Optional[str] = None,
) -> Dict[str, str]:
    """
    Stub PII scan task; validates connectivity and tenant context.
    """
    tenant_id = task_tenant_id(self)
    correlation_id = correlation_id or str(uuid4())
    set_request_correlation_id(correlation_id)
    set_tenant_id(tenant_id)
    try:
        current = run_in_worker_loop(_validate_db_connection_for_tenant(tenant_id))
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
    """
    Enforce data retention policy by purging old data.

    IMPORTANT: Immutable tables (e.g., attribution_events, revenue_ledger) are never
    deleted. Retention enforcement must only operate on mutable tables. For dead-letter
    stores, old payload envelopes are redacted to satisfy raw-event expiry requirements.
    """
    async with engine.begin() as conn:
        await set_tenant_guc(conn, tenant_id, local=True)
        dead_events_payload_redacted = (
            await conn.execute(
                text(
                    """
                    UPDATE dead_events
                    SET raw_payload = '{}'::jsonb,
                        error_detail = '{}'::jsonb
                    WHERE ingested_at < :cutoff
                      AND (
                        raw_payload <> '{}'::jsonb
                        OR error_detail <> '{}'::jsonb
                      )
                    """
                ),
                {"cutoff": cutoff_90},
            )
        ).rowcount or 0
        quarantine_payload_redacted = (
            await conn.execute(
                text(
                    """
                    UPDATE dead_events_quarantine
                    SET raw_payload = '{}'::jsonb,
                        error_detail = '{}'::jsonb
                    WHERE tenant_id = :tenant_id
                      AND ingested_at < :cutoff
                      AND (
                        raw_payload <> '{}'::jsonb
                        OR error_detail <> '{}'::jsonb
                      )
                    """
                ),
                {"tenant_id": tenant_id, "cutoff": cutoff_90},
            )
        ).rowcount or 0
        allocations_deleted = (
            await conn.execute(
                text("DELETE FROM attribution_allocations WHERE created_at < :cutoff"),
                {"cutoff": cutoff_90},
            )
        ).rowcount or 0
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
            "allocations_deleted": allocations_deleted,
            "dead_events_payload_redacted": dead_events_payload_redacted,
            "dead_events_quarantine_payload_redacted": quarantine_payload_redacted,
            "dead_events_deleted": dead_events_deleted,
        }


async def _fetch_all_tenant_ids() -> List[UUID]:
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT id FROM public.tenants ORDER BY id"))
        return [UUID(str(row[0])) for row in result.fetchall()]


@celery_app.task(
    bind=True,
    base=TenantTask,
    name="app.tasks.maintenance.enforce_data_retention",
    max_retries=3,
    default_retry_delay=60,
)
def enforce_data_retention_task(
    self,
    correlation_id: Optional[str] = None,
) -> Dict[str, int]:
    """
    Tenant-scoped retention enforcement with RLS guardrails.
    """
    tenant_id = task_tenant_id(self)
    correlation_id = correlation_id or str(uuid4())
    set_request_correlation_id(correlation_id)
    set_tenant_id(tenant_id)
    cutoff_90_day = datetime.now(timezone.utc) - timedelta(days=90)
    cutoff_30_day = datetime.now(timezone.utc) - timedelta(days=30)
    try:
        results = run_in_worker_loop(_enforce_retention(tenant_id, cutoff_90_day, cutoff_30_day))
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


@celery_app.task(
    bind=True,
    name="app.tasks.maintenance.scan_for_pii_contamination_all_tenants",
    max_retries=3,
    default_retry_delay=60,
)
def scan_for_pii_contamination_all_tenants(self) -> Dict[str, int]:
    correlation_id = getattr(self.request, "correlation_id", None) or str(uuid4())
    set_request_correlation_id(correlation_id)
    tenant_ids = run_in_worker_loop(_fetch_all_tenant_ids())
    dispatched = 0
    for tenant_id in tenant_ids:
        enqueue_tenant_task(
            scan_for_pii_contamination_task,
            envelope=SystemAuthorityEnvelope(tenant_id=tenant_id),
            kwargs={"correlation_id": correlation_id},
        )
        dispatched += 1
    return {"tenant_count": len(tenant_ids), "tasks_dispatched": dispatched}


@celery_app.task(
    bind=True,
    name="app.tasks.maintenance.enforce_data_retention_all_tenants",
    max_retries=3,
    default_retry_delay=60,
)
def enforce_data_retention_all_tenants(self) -> Dict[str, int]:
    correlation_id = getattr(self.request, "correlation_id", None) or str(uuid4())
    set_request_correlation_id(correlation_id)
    tenant_ids = run_in_worker_loop(_fetch_all_tenant_ids())
    dispatched = 0
    for tenant_id in tenant_ids:
        enqueue_tenant_task(
            enforce_data_retention_task,
            envelope=SystemAuthorityEnvelope(tenant_id=tenant_id),
            kwargs={"correlation_id": correlation_id},
        )
        dispatched += 1
    return {"tenant_count": len(tenant_ids), "tasks_dispatched": dispatched}


def _denylist_gc_batch_size() -> int:
    configured = os.getenv("SKELDIR_B12_P5_DENYLIST_GC_BATCH_SIZE")
    if not configured:
        return _DEFAULT_DENYLIST_GC_BATCH_SIZE
    try:
        parsed = int(configured)
    except ValueError:
        return _DEFAULT_DENYLIST_GC_BATCH_SIZE
    return max(1, parsed)


def _provider_refresh_batch_size() -> int:
    configured = os.getenv("SKELDIR_B13_P7_PROVIDER_REFRESH_BATCH_SIZE")
    if not configured:
        return _DEFAULT_PROVIDER_REFRESH_BATCH_SIZE
    try:
        parsed = int(configured)
    except ValueError:
        return _DEFAULT_PROVIDER_REFRESH_BATCH_SIZE
    return max(1, parsed)


def _parse_uuid_or_fallback(value: str | None) -> UUID:
    if value:
        try:
            return UUID(str(value))
        except (ValueError, TypeError):
            pass
    return uuid4()


async def _select_and_enqueue_due_provider_refreshes_for_tenant(
    tenant_id: UUID,
    correlation_id: str,
) -> Dict[str, int]:
    batch_size = _provider_refresh_batch_size()
    async with AsyncSessionLocal() as session:
        await session.begin()
        try:
            await set_tenant_guc(session, tenant_id, local=True)
            selection = await claim_due_credentials_for_tenant(
                session,
                tenant_id=tenant_id,
                as_of=datetime.now(timezone.utc),
                limit=batch_size,
            )
            await session.commit()
        except Exception:
            if session.in_transaction():
                await session.rollback()
            raise

    dispatched = 0
    for credential_id in selection.claimed_credential_ids:
        enqueue_tenant_task(
            refresh_provider_oauth_credential,
            envelope=SystemAuthorityEnvelope(tenant_id=tenant_id),
            kwargs={
                "credential_id": str(credential_id),
                "correlation_id": correlation_id,
                "refresh_claimed": True,
            },
            correlation_id=correlation_id,
        )
        dispatched += 1

    return {
        "due_count": int(selection.due_count),
        "tasks_enqueued": int(dispatched),
        "batch_size": int(batch_size),
    }


async def _refresh_provider_oauth_credential_async(
    *,
    tenant_id: UUID,
    credential_id: UUID,
    correlation_id: UUID,
    force: bool,
) -> dict[str, object]:
    async with AsyncSessionLocal() as session:
        await session.begin()
        try:
            await set_tenant_guc(session, tenant_id, local=True)
            execution = await refresh_credential_once(
                session,
                tenant_id=tenant_id,
                credential_id=credential_id,
                correlation_id=correlation_id,
                force=force,
            )
            await session.commit()
        except Exception:
            if session.in_transaction():
                await session.rollback()
            raise
    return execution.to_public_dict()


async def _delete_expired_denylist_rows(batch_size: int) -> Dict[str, int]:
    deleted = 0
    scanned_tenants = 0
    remaining = max(1, int(batch_size))
    unbounded_delete = os.getenv("SKELDIR_B12_P5_GC_UNBOUNDED_DELETE") == "1"
    disable_singleflight = os.getenv("SKELDIR_B12_P5_DISABLE_GC_SINGLEFLIGHT") == "1"
    hold_seconds_raw = os.getenv("SKELDIR_B12_P5_GC_SINGLEFLIGHT_HOLD_SECONDS", "0")
    try:
        hold_seconds = max(0.0, float(hold_seconds_raw))
    except ValueError:
        hold_seconds = 0.0

    async with engine.begin() as conn:
        lock_acquired = True
        if not disable_singleflight:
            lock_row = (
                await conn.execute(
                    text("SELECT pg_try_advisory_xact_lock(:lock_key) AS acquired"),
                    {"lock_key": _DENYLIST_GC_SINGLEFLIGHT_LOCK_KEY},
                )
            ).mappings().one()
            lock_acquired = bool(lock_row["acquired"])
            if not lock_acquired:
                return {
                    "deleted_rows": 0,
                    "batch_size": int(batch_size),
                    "scanned_tenants": 0,
                    "lock_acquired": 0,
                    "singleflight_disabled": int(disable_singleflight),
                }
        if hold_seconds > 0.0:
            # Test-only hook to force lock overlap during concurrency proofs.
            await asyncio.sleep(hold_seconds)

        tenants_result = await conn.execute(text("SELECT id FROM public.tenants ORDER BY id"))
        tenant_rows = [row[0] for row in tenants_result]

        for tenant_id in tenant_rows:
            if not unbounded_delete and remaining <= 0:
                break
            scanned_tenants += 1
            await set_tenant_guc(conn, tenant_id, local=True)
            if unbounded_delete:
                result = await conn.execute(
                    text(
                        """
                        DELETE FROM public.auth_access_token_denylist
                        WHERE tenant_id = :tenant_id
                          AND expires_at < now()
                        """
                    ),
                    {"tenant_id": str(tenant_id)},
                )
            else:
                result = await conn.execute(
                    text(
                        """
                        WITH doomed AS (
                            SELECT tenant_id, user_id, jti
                            FROM public.auth_access_token_denylist
                            WHERE tenant_id = :tenant_id
                              AND expires_at < now()
                            ORDER BY expires_at
                            LIMIT :batch_size
                        )
                        DELETE FROM public.auth_access_token_denylist d
                        USING doomed
                        WHERE d.tenant_id = doomed.tenant_id
                          AND d.user_id = doomed.user_id
                          AND d.jti = doomed.jti
                        """
                    ),
                    {
                        "tenant_id": str(tenant_id),
                        "batch_size": int(remaining),
                    },
                )
            rowcount = int(result.rowcount or 0)
            deleted += rowcount
            if not unbounded_delete:
                remaining -= rowcount

    return {
        "deleted_rows": deleted,
        "batch_size": int(batch_size),
        "scanned_tenants": scanned_tenants,
        "lock_acquired": int(lock_acquired),
        "singleflight_disabled": int(disable_singleflight),
    }


@celery_app.task(
    bind=True,
    name="app.tasks.maintenance.gc_expired_access_token_denylist",
    max_retries=3,
    default_retry_delay=60,
)
def gc_expired_access_token_denylist(self) -> Dict[str, int]:
    correlation_id = getattr(self.request, "correlation_id", None) or str(uuid4())
    set_request_correlation_id(correlation_id)
    batch_size = _denylist_gc_batch_size()
    try:
        result = run_in_worker_loop(_delete_expired_denylist_rows(batch_size))
        logger.info(
            "denylist_gc_completed",
            extra={
                "task_id": self.request.id,
                "correlation_id": correlation_id,
                **result,
            },
        )
        return result
    except Exception as exc:
        logger.error(
            "denylist_gc_failed",
            exc_info=exc,
            extra={
                "task_id": self.request.id,
                "correlation_id": correlation_id,
                "batch_size": batch_size,
            },
        )
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(
    bind=True,
    name="app.tasks.maintenance.schedule_provider_oauth_refresh_all_tenants",
    routing_key="maintenance.task",
    max_retries=3,
    default_retry_delay=60,
    ignore_result=True,
)
def schedule_provider_oauth_refresh_all_tenants(self) -> Dict[str, int]:
    correlation_id = getattr(self.request, "correlation_id", None) or str(uuid4())
    set_request_correlation_id(correlation_id)
    tenant_ids = run_in_worker_loop(_fetch_all_tenant_ids())
    dispatched = 0
    for tenant_id in tenant_ids:
        enqueue_tenant_task(
            schedule_provider_oauth_refresh_for_tenant,
            envelope=SystemAuthorityEnvelope(tenant_id=tenant_id),
            kwargs={"correlation_id": correlation_id},
            correlation_id=correlation_id,
        )
        dispatched += 1
    return {"tenant_count": len(tenant_ids), "tasks_dispatched": dispatched}


@celery_app.task(
    bind=True,
    base=TenantTask,
    name="app.tasks.maintenance.schedule_provider_oauth_refresh_for_tenant",
    routing_key="maintenance.task",
    max_retries=3,
    default_retry_delay=60,
    ignore_result=True,
)
def schedule_provider_oauth_refresh_for_tenant(
    self,
    correlation_id: Optional[str] = None,
) -> Dict[str, int]:
    tenant_id = task_tenant_id(self)
    correlation_id = correlation_id or str(uuid4())
    set_request_correlation_id(correlation_id)
    set_tenant_id(tenant_id)
    try:
        result = run_in_worker_loop(
            _select_and_enqueue_due_provider_refreshes_for_tenant(tenant_id, correlation_id)
        )
        logger.info(
            "provider_oauth_refresh_scheduled_for_tenant",
            extra={
                "tenant_id": str(tenant_id),
                "task_id": self.request.id,
                "correlation_id": correlation_id,
                **result,
            },
        )
        return result
    except Exception as exc:
        logger.error(
            "provider_oauth_refresh_schedule_failed_for_tenant",
            exc_info=exc,
            extra={
                "tenant_id": str(tenant_id),
                "task_id": self.request.id,
                "correlation_id": correlation_id,
            },
        )
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(
    bind=True,
    base=TenantTask,
    name="app.tasks.maintenance.refresh_provider_oauth_credential",
    routing_key="maintenance.task",
    max_retries=0,
    ignore_result=True,
)
def refresh_provider_oauth_credential(
    self,
    credential_id: str,
    correlation_id: Optional[str] = None,
    refresh_claimed: bool = False,
) -> dict[str, object]:
    tenant_id = task_tenant_id(self)
    correlation_id = correlation_id or str(uuid4())
    correlation_uuid = _parse_uuid_or_fallback(correlation_id)
    credential_uuid = UUID(str(credential_id))
    set_request_correlation_id(correlation_id)
    set_tenant_id(tenant_id)

    result = run_in_worker_loop(
        _refresh_provider_oauth_credential_async(
            tenant_id=tenant_id,
            credential_id=credential_uuid,
            correlation_id=correlation_uuid,
            force=bool(refresh_claimed),
        )
    )
    logger.info(
        "provider_oauth_credential_refresh_completed",
        extra={
            "tenant_id": str(tenant_id),
            "credential_id": str(credential_uuid),
            "task_id": self.request.id,
            "correlation_id": correlation_id,
            "refresh_status": result.get("status"),
            "failure_class": result.get("failure_class"),
        },
    )
    return result
