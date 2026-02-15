from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.problem_details import problem_details_response
from app.db.deps import get_db_session
from app.security.auth import AuthContext, get_auth_context

router = APIRouter()
logger = logging.getLogger(__name__)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


_PLATFORM_NAME_BY_KEY = {
    "meta": "Meta",
    "google": "Google",
    "tiktok": "TikTok",
    "linkedin": "LinkedIn",
    "shopify": "Shopify",
    "woocommerce": "WooCommerce",
    "stripe": "Stripe",
    "paypal": "PayPal",
}

_SOURCE_ALIASES = {
    "meta": {"meta", "facebook"},
    "google": {"google", "google_ads"},
    "tiktok": {"tiktok", "tik_tok"},
    "linkedin": {"linkedin"},
    "shopify": {"shopify"},
    "woocommerce": {"woocommerce", "woo", "woo_commerce"},
    "stripe": {"stripe"},
    "paypal": {"paypal"},
}


class SyncRequest(BaseModel):
    platforms: list[str] = Field(default_factory=list)
    full_sync: bool = False


def _normalize_platform_key(value: str) -> str:
    return value.strip().lower()


def _normalize_source(value: str | None) -> str:
    return (value or "").strip().lower()


def _map_source_to_platform_key(source: str) -> str | None:
    for key, aliases in _SOURCE_ALIASES.items():
        if source in aliases:
            return key
    return None


def _connection_status_for_count(count: int) -> str:
    return "verified" if count > 0 else "pending"


def _db_session_available(db_session: AsyncSession) -> bool:
    return hasattr(db_session, "execute")


async def _latest_reconciliation_run(
    db_session: AsyncSession,
    tenant_id: UUID,
) -> dict[str, Any] | None:
    try:
        row = (
            await db_session.execute(
                text(
                    """
                    SELECT id, state, last_run_at
                    FROM reconciliation_runs
                    WHERE tenant_id = :tenant_id
                    ORDER BY last_run_at DESC
                    LIMIT 1
                    """
                ),
                {"tenant_id": str(tenant_id)},
            )
        ).mappings().first()
        return dict(row) if row else None
    except Exception:
        logger.exception(
            "reconciliation_run_status_unavailable",
            extra={"tenant_id": str(tenant_id)},
        )
        return None


async def _aggregate_revenue_by_source(
    db_session: AsyncSession,
    tenant_id: UUID,
) -> list[dict[str, Any]]:
    rows = (
        await db_session.execute(
            text(
                """
                SELECT
                    lower(COALESCE(verification_source, 'unknown')) AS source,
                    COUNT(*)::INTEGER AS events_processed,
                    COALESCE(
                      SUM(COALESCE(verified_total_cents, amount_cents, revenue_cents)),
                      0
                    )::BIGINT AS verified_total_cents,
                    MAX(COALESCE(verification_timestamp, verified_at, updated_at, created_at)) AS last_sync
                FROM revenue_ledger
                WHERE tenant_id = :tenant_id
                GROUP BY lower(COALESCE(verification_source, 'unknown'))
                """
            ),
            {"tenant_id": str(tenant_id)},
        )
    ).mappings().all()
    return [dict(row) for row in rows]


@router.get("/status", operation_id="getReconciliationStatus")
async def get_reconciliation_status(
    response: Response,
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    auth_context: Annotated[AuthContext, Depends(get_auth_context)],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
):
    response.headers["X-Correlation-ID"] = str(x_correlation_id)
    if not _db_session_available(db_session):
        now = _utcnow_iso()
        return {
            "platforms": [],
            "overall_status": "pending",
            "last_full_sync": now,
        }
    tenant_id = auth_context.tenant_id
    run = await _latest_reconciliation_run(db_session, tenant_id)
    by_source = await _aggregate_revenue_by_source(db_session, tenant_id)

    platform_rows: list[dict[str, Any]] = []
    for source_row in by_source:
        platform_key = _map_source_to_platform_key(_normalize_source(source_row.get("source")))
        if platform_key is None:
            continue
        platform_rows.append(
            {
                "platform_name": _PLATFORM_NAME_BY_KEY[platform_key],
                "connection_status": _connection_status_for_count(int(source_row.get("events_processed", 0))),
                "last_sync": (
                    source_row.get("last_sync") or datetime.now(timezone.utc)
                ).isoformat().replace("+00:00", "Z"),
                "events_processed": int(source_row.get("events_processed", 0)),
                "revenue_verified": round(int(source_row.get("verified_total_cents", 0)) / 100.0, 2),
            }
        )

    state = str((run or {}).get("state") or "idle")
    overall_status = {
        "completed": "verified",
        "running": "pending",
        "failed": "failed",
        "idle": "pending",
    }.get(state, "pending")

    last_full_sync = (
        (run or {}).get("last_run_at") or datetime.now(timezone.utc)
    ).isoformat().replace("+00:00", "Z")
    return {
        "platforms": platform_rows,
        "overall_status": overall_status,
        "last_full_sync": last_full_sync,
    }


@router.get("/platform/{platform_id}", operation_id="getPlatformReconciliationStatus")
async def get_platform_reconciliation_status(
    platform_id: str,
    request: Request,
    response: Response,
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    auth_context: Annotated[AuthContext, Depends(get_auth_context)],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
):
    key = _normalize_platform_key(platform_id)
    if key not in _PLATFORM_NAME_BY_KEY:
        return problem_details_response(
            request,
            status_code=status.HTTP_404_NOT_FOUND,
            title="Platform Not Found",
            detail=f"Unknown platform_id: {platform_id}",
            correlation_id=x_correlation_id,
            type_url="https://api.skeldir.com/problems/platform-not-found",
        )

    if not _db_session_available(db_session):
        now = _utcnow_iso()
        response.headers["X-Correlation-ID"] = str(x_correlation_id)
        return {
            "platform_name": _PLATFORM_NAME_BY_KEY[key],
            "connection_status": "pending",
            "last_sync": now,
            "events_processed": 0,
            "revenue_verified": 0.0,
        }

    tenant_id = auth_context.tenant_id
    aliases = _SOURCE_ALIASES.get(key, {key})
    rows = await _aggregate_revenue_by_source(db_session, tenant_id)
    events_processed = 0
    verified_total_cents = 0
    last_sync_value: datetime | None = None
    for item in rows:
        source = _normalize_source(item.get("source"))
        if source not in aliases:
            continue
        events_processed += int(item.get("events_processed", 0) or 0)
        verified_total_cents += int(item.get("verified_total_cents", 0) or 0)
        item_last_sync = item.get("last_sync")
        if item_last_sync and (last_sync_value is None or item_last_sync > last_sync_value):
            last_sync_value = item_last_sync

    response.headers["X-Correlation-ID"] = str(x_correlation_id)
    if last_sync_value is None:
        last_sync_value = datetime.now(timezone.utc)
    return {
        "platform_name": _PLATFORM_NAME_BY_KEY[key],
        "connection_status": _connection_status_for_count(events_processed),
        "last_sync": last_sync_value.isoformat().replace("+00:00", "Z"),
        "events_processed": events_processed,
        "revenue_verified": round(verified_total_cents / 100.0, 2),
    }


@router.post("/sync", status_code=202, operation_id="triggerSync")
async def trigger_sync(
    payload: SyncRequest,
    response: Response,
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    auth_context: Annotated[AuthContext, Depends(get_auth_context)],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
):
    now = datetime.now(timezone.utc)
    sync_id = uuid4()
    if _db_session_available(db_session):
        try:
            await db_session.execute(
                text(
                    """
                    INSERT INTO reconciliation_runs (
                        id, tenant_id, created_at, updated_at, last_run_at, state, run_metadata
                    )
                    VALUES (
                        :id, :tenant_id, now(), now(), :last_run_at, 'running', :run_metadata::jsonb
                    )
                    """
                ),
                {
                    "id": str(sync_id),
                    "tenant_id": str(auth_context.tenant_id),
                    "last_run_at": now,
                    "run_metadata": json.dumps(
                        {
                            "requested_platforms": [_normalize_platform_key(v) for v in payload.platforms],
                            "full_sync": bool(payload.full_sync),
                        }
                    ),
                },
            )
        except Exception:
            logger.exception(
                "reconciliation_sync_enqueue_failed",
                extra={"tenant_id": str(auth_context.tenant_id), "sync_id": str(sync_id)},
            )

    response.headers["X-Correlation-ID"] = str(x_correlation_id)
    eta = (now + timedelta(minutes=2)).isoformat().replace("+00:00", "Z")
    return {
        "sync_id": str(sync_id),
        "status": "queued",
        "estimated_completion": eta,
    }
