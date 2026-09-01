"""Session authority resolution and 24-hour lifecycle enforcement for B1.4-P2."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SessionAuthority
from app.privacy.authority import load_privacy_authority


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _max_session_duration() -> timedelta:
    authority = load_privacy_authority()
    duration_minutes = int(
        authority.get("event_lifecycle", {})
        .get("session_boundary", {})
        .get("max_duration_minutes", 1440)
    )
    return timedelta(minutes=duration_minutes)


def _parse_session_uuid(value: str | UUID | None) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return UUID(text)
    except ValueError:
        return None


@dataclass(frozen=True)
class SessionAuthorityResolution:
    session_id: UUID
    expires_at: datetime
    reused_existing: bool
    rotated_stale: bool


async def resolve_session_authority(
    *,
    session: AsyncSession,
    tenant_id: UUID,
    candidate_session_id: str | UUID | None,
    source: str = "ingestion_runtime",
    now: datetime | None = None,
) -> SessionAuthorityResolution:
    """Resolve a session through the authority substrate.

    Rules:
    - Active authority rows can be reused.
    - Expired/invalidated authority rows are rotated.
    - Unknown candidate IDs are never adopted; a fresh UUID4 session is issued.
    """
    now_utc = now.astimezone(timezone.utc) if now else _utc_now()
    max_duration = _max_session_duration()
    candidate_uuid = _parse_session_uuid(candidate_session_id)

    if candidate_uuid is not None:
        existing = await session.scalar(
            select(SessionAuthority)
            .where(
                SessionAuthority.tenant_id == tenant_id,
                SessionAuthority.session_id == candidate_uuid,
            )
            .order_by(SessionAuthority.issued_at.desc())
            .limit(1)
        )

        if existing is not None:
            is_active = (
                existing.invalidated_at is None
                and existing.issued_at <= now_utc
                and existing.expires_at > now_utc
            )
            if is_active:
                existing.last_seen_at = now_utc
                existing.updated_at = now_utc
                await session.flush()
                return SessionAuthorityResolution(
                    session_id=existing.session_id,
                    expires_at=existing.expires_at,
                    reused_existing=True,
                    rotated_stale=False,
                )

            if (
                existing.invalidated_at is None
                and existing.issued_at <= now_utc
                and existing.expires_at <= now_utc
            ):
                existing.invalidated_at = now_utc
                existing.invalidation_reason = "expired"
                existing.updated_at = now_utc
                await session.flush()

    new_session_id = uuid4()
    expires_at = now_utc + max_duration
    authority_row = SessionAuthority(
        tenant_id=tenant_id,
        session_id=new_session_id,
        issued_at=now_utc,
        expires_at=expires_at,
        last_seen_at=now_utc,
        invalidated_at=None,
        invalidation_reason=None,
        issued_by=source,
        created_at=now_utc,
        updated_at=now_utc,
    )
    session.add(authority_row)
    await session.flush()
    return SessionAuthorityResolution(
        session_id=new_session_id,
        expires_at=expires_at,
        reused_existing=False,
        rotated_stale=candidate_uuid is not None,
    )
