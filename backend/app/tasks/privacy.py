"""Privacy lifecycle worker tasks (authority-controlled, non-public API)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
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
        predicates.append("raw_payload->>'idempotency_key' = :idempotency_key")
        params["idempotency_key"] = selector["idempotency_key"]
    if "correlation_id" in selector:
        predicates.append("correlation_id = :correlation_id::uuid")
        params["correlation_id"] = selector["correlation_id"]
    if not predicates:
        raise ValueError("selector_where_clause requires at least one predicate")
    return "(" + " OR ".join(predicates) + ")", params


def _build_privacy_tombstone_payload(
    *,
    idempotency_key: str,
    occurred_at: datetime,
    selector: Dict[str, str],
    effects: Dict[str, int],
) -> dict[str, object]:
    return {
        "event_type": "privacy_tombstone",
        "event_timestamp": occurred_at.isoformat(),
        "vendor": "privacy",
        "utm_source": "privacy",
        "utm_medium": "deletion",
        "external_event_id": f"privacy-tombstone:{idempotency_key}",
        "campaign_id": "privacy_tombstone",
        "idempotency_key": idempotency_key,
        "channel": "direct",
        "selector": selector,
        "effects": effects,
    }


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
    tombstone_idempotency = f"privacy-tombstone-{uuid4()}"
    async with engine.begin() as conn:
        await set_tenant_guc(conn, tenant_id, local=True)
        deleted_raw_event_payloads = (
            await conn.execute(
                text(
                    f"""
                    WITH target_events AS (
                        SELECT id
                        FROM attribution_events
                        WHERE tenant_id = :tenant_id
                          AND {events_where_sql}
                    )
                    DELETE FROM raw_event_payloads rep
                    USING target_events te
                    WHERE rep.tenant_id = :tenant_id
                      AND rep.event_id = te.id
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
        deleted_session_authority = 0
        if target_sessions:
            # This FK is DEFERRABLE INITIALLY DEFERRED in P4 migration.
            await conn.execute(
                text(
                    """
                    SET CONSTRAINTS fk_attribution_events_session_authority DEFERRED
                    """
                )
            )
            deleted_session_authority = (
                await conn.execute(
                    text(
                        """
                        DELETE FROM session_authority
                        WHERE tenant_id = :tenant_id
                          AND session_id = ANY(CAST(:session_ids AS uuid[]))
                        """
                    ),
                    {
                        "tenant_id": str(tenant_id),
                        "session_ids": [str(value) for value in target_sessions],
                    },
                )
            ).rowcount or 0
            # Reinsert invalidated placeholders with identical (tenant_id, session_id)
            # so immutable ledger rows remain referentially valid while live authority
            # capability is erased deterministically.
            await conn.execute(
                text(
                    """
                    INSERT INTO session_authority
                    (
                        tenant_id,
                        session_id,
                        issued_at,
                        expires_at,
                        last_seen_at,
                        invalidated_at,
                        invalidation_reason,
                        issued_by,
                        created_at,
                        updated_at
                    )
                    SELECT
                        :tenant_id,
                        sid,
                        :issued_at,
                        :expires_at,
                        :last_seen_at,
                        :invalidated_at,
                        'privacy_erasure_tombstone',
                        'privacy_erasure_tombstone',
                        :created_at,
                        :updated_at
                    FROM unnest(CAST(:session_ids AS uuid[])) AS sid
                    ON CONFLICT (tenant_id, session_id)
                    DO UPDATE SET
                        invalidated_at = EXCLUDED.invalidated_at,
                        invalidation_reason = EXCLUDED.invalidation_reason,
                        issued_by = EXCLUDED.issued_by,
                        expires_at = EXCLUDED.expires_at,
                        updated_at = EXCLUDED.updated_at
                    """
                ),
                {
                    "tenant_id": str(tenant_id),
                    "session_ids": [str(value) for value in target_sessions],
                    "issued_at": occurred_at - timedelta(minutes=1),
                    "expires_at": occurred_at + timedelta(minutes=1),
                    "last_seen_at": occurred_at - timedelta(minutes=1),
                    "invalidated_at": occurred_at,
                    "created_at": occurred_at,
                    "updated_at": occurred_at,
                },
            )
        dead_events_redacted = (
            await conn.execute(
                text(
                    f"""
                    UPDATE dead_events
                    SET raw_payload = '{{}}'::jsonb,
                        error_detail = '{{}}'::jsonb
                    WHERE {dead_events_where_sql}
                    """
                ),
                dead_events_params,
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
        tombstone_payload = _build_privacy_tombstone_payload(
            idempotency_key=tombstone_idempotency,
            occurred_at=occurred_at,
            selector=selector,
            effects={
                "raw_event_payloads_deleted": int(deleted_raw_event_payloads),
                "session_authority_deleted": int(deleted_session_authority),
                "dead_events_redacted": int(dead_events_redacted),
                "dead_events_quarantine_redacted": int(quarantine_redacted),
            },
        )
        await conn.execute(
            text(
                """
                INSERT INTO attribution_events
                (
                    id,
                    tenant_id,
                    created_at,
                    updated_at,
                    occurred_at,
                    external_event_id,
                    correlation_id,
                    session_id,
                    revenue_cents,
                    raw_payload,
                    idempotency_key,
                    event_type,
                    channel,
                    campaign_id,
                    conversion_value_cents,
                    currency,
                    event_timestamp,
                    processed_at,
                    processing_status,
                    retry_count
                )
                VALUES
                (
                    :id,
                    :tenant_id,
                    :created_at,
                    :updated_at,
                    :occurred_at,
                    :external_event_id,
                    :correlation_id,
                    :session_id,
                    0,
                    CAST(:raw_payload AS jsonb),
                    :idempotency_key,
                    'privacy_tombstone',
                    'direct',
                    'privacy_tombstone',
                    0,
                    'USD',
                    :event_timestamp,
                    :processed_at,
                    'processed',
                    0
                )
                """
            ),
            {
                "id": str(uuid4()),
                "tenant_id": str(tenant_id),
                "created_at": occurred_at,
                "updated_at": occurred_at,
                "occurred_at": occurred_at,
                "external_event_id": f"privacy_tombstone:{uuid4()}",
                "correlation_id": str(correlation_id),
                "session_id": str(uuid4()),
                "raw_payload": json.dumps(tombstone_payload),
                "idempotency_key": tombstone_idempotency,
                "event_timestamp": occurred_at,
                "processed_at": occurred_at,
            },
        )
    return {
        "raw_event_payloads_deleted": deleted_raw_event_payloads,
        "session_authority_deleted": deleted_session_authority,
        "dead_events_redacted": dead_events_redacted,
        "dead_events_quarantine_redacted": quarantine_redacted,
        "privacy_tombstones_inserted": 1,
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
