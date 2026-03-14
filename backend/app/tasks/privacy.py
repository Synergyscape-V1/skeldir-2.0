"""Privacy lifecycle worker tasks (authority-controlled, non-public API)."""

from __future__ import annotations

import logging
from typing import Dict, Optional
from uuid import UUID, uuid4

from sqlalchemy import text

from app.celery_app import celery_app
from app.db.session import engine, set_tenant_guc
from app.observability.context import set_request_correlation_id, set_tenant_id
from app.tasks.context import run_in_worker_loop
from app.tasks.tenant_base import TenantTask, task_tenant_id

logger = logging.getLogger(__name__)


def _normalize_selector(selector: Dict[str, str]) -> Dict[str, str]:
    idempotency_key = (selector.get("idempotency_key") or "").strip()
    correlation_id = (selector.get("correlation_id") or "").strip()
    if not idempotency_key and not correlation_id:
        raise ValueError("selector must include idempotency_key or correlation_id")
    normalized: Dict[str, str] = {}
    if idempotency_key:
        normalized["idempotency_key"] = idempotency_key
    if correlation_id:
        normalized["correlation_id"] = str(UUID(correlation_id))
    return normalized


def _selector_where_clause(selector: Dict[str, str]) -> tuple[str, Dict[str, str]]:
    predicates: list[str] = []
    params: Dict[str, str] = {}
    if "idempotency_key" in selector:
        predicates.append("raw_payload->>'idempotency_key' = :idempotency_key")
        params["idempotency_key"] = selector["idempotency_key"]
    if "correlation_id" in selector:
        predicates.append("correlation_id = :correlation_id::uuid")
        params["correlation_id"] = selector["correlation_id"]
    if not predicates:
        raise ValueError("selector_where_clause requires at least one predicate")
    return "(" + " OR ".join(predicates) + ")", params


async def _erase_tenant_privacy_surfaces(
    tenant_id: UUID,
    selector: Dict[str, str],
) -> Dict[str, int]:
    where_sql, params = _selector_where_clause(selector)
    async with engine.begin() as conn:
        await set_tenant_guc(conn, tenant_id, local=True)
        dead_events_redacted = (
            await conn.execute(
                text(
                    f"""
                    UPDATE dead_events
                    SET raw_payload = '{{}}'::jsonb,
                        error_detail = '{{}}'::jsonb
                    WHERE {where_sql}
                    """
                ),
                params,
            )
        ).rowcount or 0
        quarantine_redacted = (
            await conn.execute(
                text(
                    f"""
                    UPDATE dead_events_quarantine
                    SET raw_payload = '{{}}'::jsonb,
                        error_detail = '{{}}'::jsonb
                    WHERE tenant_id = :tenant_id
                      AND {where_sql}
                    """
                ),
                {"tenant_id": str(tenant_id), **params},
            )
        ).rowcount or 0
    return {
        "dead_events_redacted": dead_events_redacted,
        "dead_events_quarantine_redacted": quarantine_redacted,
    }


@celery_app.task(
    bind=True,
    base=TenantTask,
    name="app.tasks.privacy.erase_tenant_privacy_surfaces",
    routing_key="maintenance.task",
    max_retries=3,
    default_retry_delay=60,
)
def erase_tenant_privacy_surfaces_task(
    self,
    selector: Dict[str, str],
    correlation_id: Optional[str] = None,
) -> Dict[str, str | int]:
    """Redact mutable privacy-sensitive envelopes for a tenant-scoped selector."""
    tenant_id = task_tenant_id(self)
    correlation_id = correlation_id or str(uuid4())
    set_request_correlation_id(correlation_id)
    set_tenant_id(tenant_id)
    normalized_selector = _normalize_selector(selector)
    try:
        counts = run_in_worker_loop(_erase_tenant_privacy_surfaces(tenant_id, normalized_selector))
        logger.info(
            "privacy_surface_erasure_completed",
            extra={
                "tenant_id": str(tenant_id),
                "task_id": self.request.id,
                "correlation_id": correlation_id,
                "selector": normalized_selector,
                **counts,
            },
        )
        return {
            "status": "ok",
            "tenant_id": str(tenant_id),
            "selector": str(normalized_selector),
            **counts,
        }
    except Exception as exc:
        logger.error(
            "privacy_surface_erasure_failed",
            exc_info=exc,
            extra={
                "tenant_id": str(tenant_id),
                "task_id": self.request.id,
                "correlation_id": correlation_id,
                "selector": normalized_selector,
            },
        )
        raise self.retry(exc=exc, countdown=60)

