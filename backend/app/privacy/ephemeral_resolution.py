"""Ephemeral order/click resolution helpers for session-local ingress binding."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    EphemeralClickResolution,
    EphemeralOrderResolution,
    SessionAuthority,
)
from app.privacy.authority import load_privacy_authority


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _max_resolution_duration() -> timedelta:
    authority = load_privacy_authority()
    duration_minutes = int(
        authority.get("event_lifecycle", {})
        .get("session_boundary", {})
        .get("max_duration_minutes", 1440)
    )
    return timedelta(minutes=duration_minutes)


def _normalize_resolution_key(value: Any) -> str | None:
    if value is None:
        return None
    token = str(value).strip()
    return token if token else None


def _parse_session_uuid(value: str | UUID | None) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    token = str(value).strip()
    if not token:
        return None
    try:
        return UUID(token)
    except ValueError:
        return None


async def _is_active_session_authority(
    *,
    session: AsyncSession,
    tenant_id: UUID,
    session_id: UUID,
    now: datetime,
) -> bool:
    row = await session.scalar(
        select(SessionAuthority.id)
        .where(
            SessionAuthority.tenant_id == tenant_id,
            SessionAuthority.session_id == session_id,
            SessionAuthority.invalidated_at.is_(None),
            SessionAuthority.issued_at <= now,
            SessionAuthority.expires_at > now,
        )
        .limit(1)
    )
    return row is not None


async def _lookup_order_resolution(
    *,
    session: AsyncSession,
    tenant_id: UUID,
    order_id: str,
    now: datetime,
) -> UUID | None:
    return await session.scalar(
        select(EphemeralOrderResolution.session_id)
        .where(
            EphemeralOrderResolution.tenant_id == tenant_id,
            EphemeralOrderResolution.order_id == order_id,
            EphemeralOrderResolution.observed_at <= now,
            EphemeralOrderResolution.expires_at > now,
        )
        .order_by(EphemeralOrderResolution.observed_at.desc())
        .limit(1)
    )


async def _lookup_click_resolution(
    *,
    session: AsyncSession,
    tenant_id: UUID,
    click_id: str,
    now: datetime,
) -> UUID | None:
    return await session.scalar(
        select(EphemeralClickResolution.session_id)
        .where(
            EphemeralClickResolution.tenant_id == tenant_id,
            EphemeralClickResolution.click_id == click_id,
            EphemeralClickResolution.observed_at <= now,
            EphemeralClickResolution.expires_at > now,
        )
        .order_by(EphemeralClickResolution.observed_at.desc())
        .limit(1)
    )


async def resolve_session_candidate_with_ephemeral_substrate(
    *,
    session: AsyncSession,
    tenant_id: UUID,
    candidate_session_id: str | UUID | None,
    order_id: Any = None,
    click_id: Any = None,
    now: datetime | None = None,
) -> UUID | None:
    now_utc = now.astimezone(timezone.utc) if now else _utc_now()

    candidate_uuid = _parse_session_uuid(candidate_session_id)
    if candidate_uuid is not None and await _is_active_session_authority(
        session=session,
        tenant_id=tenant_id,
        session_id=candidate_uuid,
        now=now_utc,
    ):
        return candidate_uuid

    normalized_order_id = _normalize_resolution_key(order_id)
    if normalized_order_id is not None:
        order_session = await _lookup_order_resolution(
            session=session,
            tenant_id=tenant_id,
            order_id=normalized_order_id,
            now=now_utc,
        )
        if order_session is not None and await _is_active_session_authority(
            session=session,
            tenant_id=tenant_id,
            session_id=order_session,
            now=now_utc,
        ):
            return order_session

    normalized_click_id = _normalize_resolution_key(click_id)
    if normalized_click_id is not None:
        click_session = await _lookup_click_resolution(
            session=session,
            tenant_id=tenant_id,
            click_id=normalized_click_id,
            now=now_utc,
        )
        if click_session is not None and await _is_active_session_authority(
            session=session,
            tenant_id=tenant_id,
            session_id=click_session,
            now=now_utc,
        ):
            return click_session

    return candidate_uuid


async def upsert_ephemeral_resolution_links(
    *,
    session: AsyncSession,
    tenant_id: UUID,
    session_id: UUID,
    order_id: Any = None,
    click_id: Any = None,
    source: str = "ingestion_runtime",
    now: datetime | None = None,
) -> None:
    now_utc = now.astimezone(timezone.utc) if now else _utc_now()
    expires_at = now_utc + _max_resolution_duration()

    normalized_order_id = _normalize_resolution_key(order_id)
    if normalized_order_id is not None:
        await session.execute(
            insert(EphemeralOrderResolution)
            .values(
                tenant_id=tenant_id,
                order_id=normalized_order_id,
                session_id=session_id,
                observed_at=now_utc,
                expires_at=expires_at,
                source=source,
                created_at=now_utc,
                updated_at=now_utc,
            )
            .on_conflict_do_update(
                index_elements=["tenant_id", "order_id"],
                set_={
                    "session_id": session_id,
                    "observed_at": now_utc,
                    "expires_at": expires_at,
                    "source": source,
                    "updated_at": now_utc,
                },
                where=EphemeralOrderResolution.observed_at <= now_utc,
            )
        )

    normalized_click_id = _normalize_resolution_key(click_id)
    if normalized_click_id is not None:
        await session.execute(
            insert(EphemeralClickResolution)
            .values(
                tenant_id=tenant_id,
                click_id=normalized_click_id,
                session_id=session_id,
                observed_at=now_utc,
                expires_at=expires_at,
                source=source,
                created_at=now_utc,
                updated_at=now_utc,
            )
            .on_conflict_do_update(
                index_elements=["tenant_id", "click_id"],
                set_={
                    "session_id": session_id,
                    "observed_at": now_utc,
                    "expires_at": expires_at,
                    "source": source,
                    "updated_at": now_utc,
                },
                where=EphemeralClickResolution.observed_at <= now_utc,
            )
        )
