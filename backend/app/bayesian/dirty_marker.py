"""B2.4-P3 append-only dirty event capture.

Hot deterministic paths call only this module. It deliberately performs one
tenant-scoped INSERT and does not compute source snapshots, claim fits, or
publish queue messages.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession


DEFAULT_BAYESIAN_MODEL_TYPE = "mmm"
DEFAULT_BAYESIAN_MODEL_VERSION = "b24-p3-orchestration-v1"
DIRTY_EVENT_LOW_CONTENTION_POLICY = "append_only_single_insert_v1"


@dataclass(frozen=True)
class DirtyEventRef:
    id: UUID
    tenant_id: UUID
    model_type: str
    model_version: str
    source_window_start: datetime
    source_window_end: datetime
    dirty_reason: str
    source_family: str
    event_hash: str | None


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def dirty_event_hash(
    *,
    tenant_id: UUID,
    source_family: str,
    source_event_id: str | UUID | None,
    observed_at: datetime,
    dirty_reason: str,
) -> str:
    """Hash non-PII event identity for observability without dedup compaction."""

    payload = {
        "tenant_id": str(tenant_id),
        "source_family": source_family,
        "source_event_id": str(source_event_id or ""),
        "observed_at": _utc(observed_at).isoformat(timespec="microseconds"),
        "dirty_reason": dirty_reason,
    }
    material = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


async def append_dirty_event(
    session: AsyncSession | AsyncConnection,
    *,
    tenant_id: UUID,
    source_window_start: datetime,
    source_window_end: datetime,
    dirty_reason: str,
    source_family: str,
    source_event_id: str | UUID | None = None,
    model_type: str = DEFAULT_BAYESIAN_MODEL_TYPE,
    model_version: str = DEFAULT_BAYESIAN_MODEL_VERSION,
    observed_at: datetime | None = None,
) -> DirtyEventRef:
    """Append one low-contention dirty event inside the caller's transaction."""

    observed = _utc(observed_at or datetime.now(timezone.utc))
    event_hash = dirty_event_hash(
        tenant_id=tenant_id,
        source_family=source_family,
        source_event_id=source_event_id,
        observed_at=observed,
        dirty_reason=dirty_reason,
    )
    result = await session.execute(
        text(
            """
            INSERT INTO public.b24_dirty_events (
                tenant_id,
                model_type,
                model_version,
                source_window_start,
                source_window_end,
                dirty_reason,
                source_family,
                event_hash,
                source_event_id,
                observed_at,
                status,
                created_at,
                updated_at
            )
            VALUES (
                :tenant_id,
                :model_type,
                :model_version,
                :source_window_start,
                :source_window_end,
                :dirty_reason,
                :source_family,
                :event_hash,
                :source_event_id,
                :observed_at,
                'pending',
                now(),
                now()
            )
            RETURNING id
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "model_type": model_type,
            "model_version": model_version,
            "source_window_start": _utc(source_window_start),
            "source_window_end": _utc(source_window_end),
            "dirty_reason": dirty_reason,
            "source_family": source_family,
            "event_hash": event_hash,
            "source_event_id": str(source_event_id) if source_event_id is not None else None,
            "observed_at": observed,
        },
    )
    return DirtyEventRef(
        id=result.scalar_one(),
        tenant_id=tenant_id,
        model_type=model_type,
        model_version=model_version,
        source_window_start=_utc(source_window_start),
        source_window_end=_utc(source_window_end),
        dirty_reason=dirty_reason,
        source_family=source_family,
        event_hash=event_hash,
    )
