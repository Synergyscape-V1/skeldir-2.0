"""Privacy lifecycle worker tasks (authority-controlled, non-public API)."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
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


def _selector_where_clause_for_events(selector: Dict[str, str]) -> tuple[str, Dict[str, str]]:
    predicates: list[str] = []
    params: Dict[str, str] = {}
    if "idempotency_key" in selector:
        predicates.append("idempotency_key = :idempotency_key")
        params["idempotency_key"] = selector["idempotency_key"]
    if "correlation_id" in selector:
        predicates.append("correlation_id = :correlation_id::uuid")
        params["correlation_id"] = selector["correlation_id"]
    if not predicates:
        raise ValueError("selector_where_clause requires at least one predicate")
    return "(" + " OR ".join(predicates) + ")", params


def _selector_where_clause_for_dead_events(selector: Dict[str, str]) -> tuple[str, Dict[str, str]]:
    predicates: list[str] = []
    params: Dict[str, str] = {}
    if "idempotency_key" in selector:
        predicates.append("idempotency_key = :idempotency_key")
        params["idempotency_key"] = selector["idempotency_key"]
    if "correlation_id" in selector:
        predicates.append("correlation_id = :correlation_id::uuid")
        params["correlation_id"] = selector["correlation_id"]
    if not predicates:
        raise ValueError("selector_where_clause requires at least one predicate")
    return "(" + " OR ".join(predicates) + ")", params


def _stable_hash(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def _erase_tenant_privacy_surfaces(
    tenant_id: UUID,
    selector: Dict[str, str],
    *,
    correlation_id: UUID,
) -> Dict[str, int]:
    events_where_sql, events_params = _selector_where_clause_for_events(selector)
    dead_events_where_sql, dead_events_params = _selector_where_clause_for_dead_events(selector)
    selector_with_tenant = {"tenant_id": str(tenant_id), **events_params}
    occurred_at = datetime.now(timezone.utc)
    audit_idempotency = f"privacy-erasure-{uuid4()}"
    async with engine.begin() as conn:
        await set_tenant_guc(conn, tenant_id, local=True)

        deleted_raw_event_payloads = (
            await conn.execute(
                text(
                    f"""
                    DELETE FROM raw_event_payloads rep
                    USING attribution_events e
                    WHERE rep.tenant_id = :tenant_id
                      AND rep.event_id = e.id
                      AND e.tenant_id = :tenant_id
                      AND {events_where_sql}
                    """
                ),
                selector_with_tenant,
            )
        ).rowcount or 0

        target_sessions = (
            await conn.execute(
                text(
                    f"""
                    SELECT DISTINCT session_id
                    FROM attribution_events
                    WHERE tenant_id = :tenant_id
                      AND {events_where_sql}
                    """
                ),
                selector_with_tenant,
            )
        ).scalars().all()

        invalidated_session_authority = 0
        if target_sessions:
            invalidated_session_authority = (
                await conn.execute(
                    text(
                        """
                        UPDATE session_authority
                        SET
                            invalidated_at = GREATEST(
                                COALESCE(invalidated_at, :occurred_at),
                                issued_at
                            ),
                            invalidation_reason = 'privacy_erasure',
                            issued_by = 'privacy_erasure',
                            expires_at = GREATEST(
                                issued_at + interval '1 second',
                                LEAST(expires_at, :occurred_at)
                            ),
                            updated_at = :occurred_at
                        WHERE tenant_id = :tenant_id
                          AND session_id = ANY(CAST(:session_ids AS uuid[]))
                        """
                    ),
                    {
                        "tenant_id": str(tenant_id),
                        "session_ids": [str(value) for value in target_sessions],
                        "occurred_at": occurred_at,
                    },
                )
            ).rowcount or 0

        dead_events_redacted = (
            await conn.execute(
                text(
                    f"""
                    UPDATE dead_events
                    SET raw_payload = '{{}}'::jsonb,
                        error_detail = '{{}}'::jsonb
                    WHERE tenant_id = :tenant_id
                      AND {dead_events_where_sql}
                    """
                ),
                {"tenant_id": str(tenant_id), **dead_events_params},
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
                      AND {dead_events_where_sql}
                    """
                ),
                {"tenant_id": str(tenant_id), **dead_events_params},
            )
        ).rowcount or 0

        audit_selector_hash = _stable_hash({"selector": selector})
        effects = {
            "raw_event_payloads_deleted": int(deleted_raw_event_payloads),
            "session_authority_invalidated": int(invalidated_session_authority),
            "dead_events_redacted": int(dead_events_redacted),
            "dead_events_quarantine_redacted": int(quarantine_redacted),
        }
        evidence_hash = _stable_hash(
            {
                "tenant_id": str(tenant_id),
                "correlation_id": str(correlation_id),
                "selector_hash": audit_selector_hash,
                "effects": effects,
                "occurred_at": occurred_at.isoformat(),
            }
        )
        await conn.execute(
            text(
                """
                INSERT INTO compliance_audit_ledger
                (
                    id,
                    tenant_id,
                    created_at,
                    updated_at,
                    occurred_at,
                    audit_event_type,
                    correlation_id,
                    idempotency_key,
                    selector,
                    selector_hash,
                    effects,
                    evidence_hash,
                    actor
                )
                VALUES
                (
                    :id,
                    :tenant_id,
                    :created_at,
                    :updated_at,
                    :occurred_at,
                    'privacy_erasure',
                    :correlation_id,
                    :idempotency_key,
                    CAST(:selector AS jsonb),
                    :selector_hash,
                    CAST(:effects AS jsonb),
                    :evidence_hash,
                    'privacy_worker'
                )
                """
            ),
            {
                "id": str(uuid4()),
                "tenant_id": str(tenant_id),
                "created_at": occurred_at,
                "updated_at": occurred_at,
                "occurred_at": occurred_at,
                "correlation_id": str(correlation_id),
                "idempotency_key": audit_idempotency,
                "selector": json.dumps(selector),
                "selector_hash": audit_selector_hash,
                "effects": json.dumps(effects),
                "evidence_hash": evidence_hash,
            },
        )

    return {
        "raw_event_payloads_deleted": deleted_raw_event_payloads,
        "session_authority_invalidated": invalidated_session_authority,
        "dead_events_redacted": dead_events_redacted,
        "dead_events_quarantine_redacted": quarantine_redacted,
        "privacy_audit_artifacts_inserted": 1,
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
        counts = run_in_worker_loop(
            _erase_tenant_privacy_surfaces(
                tenant_id,
                normalized_selector,
                correlation_id=UUID(correlation_id),
            )
        )
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
