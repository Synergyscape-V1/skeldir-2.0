"""
Postgres-backed realtime revenue cache with stampede prevention.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import struct
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import set_tenant_guc_async

DEFAULT_CACHE_KEY = "realtime_revenue:shared:v1"


@dataclass(frozen=True)
class RealtimeRevenueSnapshot:
    tenant_id: UUID
    interval: str
    currency: str
    revenue_total_cents: int
    event_count: int
    verified: bool
    data_as_of: datetime
    sources: list[str]
    confidence_score: float | None = None
    upgrade_notice: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "tenant_id": str(self.tenant_id),
            "interval": self.interval,
            "currency": self.currency,
            "revenue_total_cents": self.revenue_total_cents,
            "event_count": self.event_count,
            "verified": self.verified,
            "data_as_of": self.data_as_of.isoformat(),
            "sources": list(self.sources),
            "confidence_score": self.confidence_score,
            "upgrade_notice": self.upgrade_notice,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "RealtimeRevenueSnapshot":
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:
                payload = {}
        data_as_of_raw = payload.get("data_as_of")
        data_as_of = _parse_datetime(data_as_of_raw) if data_as_of_raw else _utcnow()
        return cls(
            tenant_id=UUID(str(payload["tenant_id"])),
            interval=str(payload.get("interval", "minute")),
            currency=str(payload.get("currency", "USD")),
            revenue_total_cents=int(payload.get("revenue_total_cents", 0)),
            event_count=int(payload.get("event_count", 0)),
            verified=bool(payload.get("verified", False)),
            data_as_of=data_as_of,
            sources=list(payload.get("sources") or []),
            confidence_score=payload.get("confidence_score"),
            upgrade_notice=payload.get("upgrade_notice"),
        )


class RealtimeRevenueUnavailable(Exception):
    def __init__(self, retry_after_seconds: int, reason: str) -> None:
        super().__init__(reason)
        self.retry_after_seconds = max(1, int(retry_after_seconds))
        self.reason = reason


FetchSnapshotFn = Callable[[UUID], Awaitable[RealtimeRevenueSnapshot]]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return _utcnow()


def _get_int_env(name: str, default: int, minimum: int = 0) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except Exception:
        return default
    return max(minimum, value)


def _cache_ttl_seconds() -> int:
    return _get_int_env("REALTIME_REVENUE_CACHE_TTL_SECONDS", 30, minimum=0)


def _error_cooldown_seconds() -> int:
    return _get_int_env("REALTIME_REVENUE_ERROR_COOLDOWN_SECONDS", 10, minimum=1)


def _follower_wait_timeout_seconds() -> int:
    return _get_int_env("REALTIME_REVENUE_SINGLEFLIGHT_WAIT_SECONDS", 5, minimum=1)


def _follower_poll_interval_seconds() -> float:
    raw = os.environ.get("REALTIME_REVENUE_SINGLEFLIGHT_POLL_SECONDS")
    if not raw:
        return 0.1
    try:
        return max(0.05, float(raw))
    except Exception:
        return 0.1


def _lock_key(tenant_id: UUID, cache_key: str) -> int:
    seed = f"{tenant_id}:{cache_key}".encode("utf-8")
    digest = hashlib.sha256(seed).digest()
    return struct.unpack("!q", digest[:8])[0]


async def _try_advisory_lock(session: AsyncSession, key: int) -> bool:
    result = await session.execute(
        text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": key}
    )
    return bool(result.scalar())


def _compute_etag(payload: dict[str, Any]) -> str:
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            payload = {}
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return f"\"{digest}\""


async def _fetch_cache_row(
    session: AsyncSession, tenant_id: UUID, cache_key: str
) -> dict[str, Any] | None:
    result = await session.execute(
        text(
            """
            SELECT tenant_id, cache_key, payload, data_as_of, expires_at,
                   error_cooldown_until, last_error_at, last_error_message, etag
            FROM revenue_cache_entries
            WHERE tenant_id = :tenant_id AND cache_key = :cache_key
            """
        ),
        {"tenant_id": str(tenant_id), "cache_key": cache_key},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def _upsert_cache_row(
    session: AsyncSession,
    tenant_id: UUID,
    cache_key: str,
    payload: dict[str, Any],
    data_as_of: datetime,
    expires_at: datetime,
    *,
    etag: str | None,
    error_cooldown_until: datetime | None,
    last_error_at: datetime | None,
    last_error_message: str | None,
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO revenue_cache_entries (
                tenant_id, cache_key, payload, data_as_of, expires_at,
                error_cooldown_until, last_error_at, last_error_message, etag,
                created_at, updated_at
            ) VALUES (
                :tenant_id, :cache_key, CAST(:payload AS jsonb), :data_as_of, :expires_at,
                :error_cooldown_until, :last_error_at, :last_error_message, :etag,
                now(), now()
            )
            ON CONFLICT (tenant_id, cache_key) DO UPDATE SET
                payload = EXCLUDED.payload,
                data_as_of = EXCLUDED.data_as_of,
                expires_at = EXCLUDED.expires_at,
                error_cooldown_until = EXCLUDED.error_cooldown_until,
                last_error_at = EXCLUDED.last_error_at,
                last_error_message = EXCLUDED.last_error_message,
                etag = EXCLUDED.etag,
                updated_at = now()
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "cache_key": cache_key,
            "payload": json.dumps(payload),
            "data_as_of": data_as_of,
            "expires_at": expires_at,
            "error_cooldown_until": error_cooldown_until,
            "last_error_at": last_error_at,
            "last_error_message": last_error_message,
            "etag": etag,
        },
    )


async def _refresh_snapshot(
    session: AsyncSession,
    tenant_id: UUID,
    cache_key: str,
    fetcher: FetchSnapshotFn,
) -> tuple[RealtimeRevenueSnapshot, str]:
    snapshot = await fetcher(tenant_id)
    payload = snapshot.to_payload()
    etag = _compute_etag(payload)
    now = _utcnow()
    ttl_seconds = _cache_ttl_seconds()
    expires_at = now + timedelta(seconds=ttl_seconds)
    await _upsert_cache_row(
        session,
        tenant_id,
        cache_key,
        payload,
        snapshot.data_as_of,
        expires_at,
        etag=etag,
        error_cooldown_until=None,
        last_error_at=None,
        last_error_message=None,
    )
    await session.commit()
    return snapshot, etag


async def _record_failure(
    session: AsyncSession,
    tenant_id: UUID,
    cache_key: str,
    *,
    existing_payload: dict[str, Any] | None,
    existing_data_as_of: datetime | None,
    error_message: str,
) -> None:
    now = _utcnow()
    await set_tenant_guc_async(session, tenant_id, local=False)
    cooldown = now + timedelta(seconds=_error_cooldown_seconds())
    payload = existing_payload or {
        "tenant_id": str(tenant_id),
        "interval": "minute",
        "currency": "USD",
        "revenue_total_cents": 0,
        "event_count": 0,
        "verified": False,
        "data_as_of": now.isoformat(),
        "sources": [],
        "confidence_score": None,
        "upgrade_notice": None,
    }
    data_as_of = existing_data_as_of or now
    await _upsert_cache_row(
        session,
        tenant_id,
        cache_key,
        payload,
        data_as_of,
        now,
        etag=None,
        error_cooldown_until=cooldown,
        last_error_at=now,
        last_error_message=error_message,
    )
    await session.commit()


async def get_realtime_revenue_snapshot(
    session: AsyncSession | object,
    tenant_id: UUID,
    *,
    cache_key: str = DEFAULT_CACHE_KEY,
    fetcher: FetchSnapshotFn | None = None,
) -> tuple[RealtimeRevenueSnapshot, str, bool]:
    """
    Return realtime revenue snapshot using Postgres cache + advisory lock singleflight.

    Returns (snapshot, etag, was_cached).
    Raises RealtimeRevenueUnavailable on cooldown/timeout/failure.
    """
    if not hasattr(session, "execute"):
        snapshot = await _default_fetcher(tenant_id)
        payload = snapshot.to_payload()
        return snapshot, _compute_etag(payload), False

    fetcher = fetcher or _default_fetcher
    now = _utcnow()

    row = await _fetch_cache_row(session, tenant_id, cache_key)
    if row:
        cooldown_until = row.get("error_cooldown_until")
        if cooldown_until and cooldown_until > now:
            retry_after = int((cooldown_until - now).total_seconds())
            raise RealtimeRevenueUnavailable(retry_after, "error_cooldown_active")
        expires_at = row.get("expires_at")
        payload = row.get("payload") or {}
        if expires_at and expires_at > now and payload:
            snapshot = RealtimeRevenueSnapshot.from_payload(payload)
            etag = row.get("etag") or _compute_etag(payload)
            return snapshot, etag, True

    lock_key = _lock_key(tenant_id, cache_key)
    acquired = await _try_advisory_lock(session, lock_key)
    if acquired:
        row = await _fetch_cache_row(session, tenant_id, cache_key)
        if row:
            cooldown_until = row.get("error_cooldown_until")
            if cooldown_until and cooldown_until > now:
                retry_after = int((cooldown_until - now).total_seconds())
                raise RealtimeRevenueUnavailable(retry_after, "error_cooldown_active")
            expires_at = row.get("expires_at")
            payload = row.get("payload") or {}
            if expires_at and expires_at > now and payload:
                snapshot = RealtimeRevenueSnapshot.from_payload(payload)
                etag = row.get("etag") or _compute_etag(payload)
                return snapshot, etag, True
        try:
            snapshot, etag = await _refresh_snapshot(
                session, tenant_id, cache_key, fetcher
            )
            return snapshot, etag, False
        except Exception as exc:
            await session.rollback()
            payload = row.get("payload") if row else None
            data_as_of = row.get("data_as_of") if row else None
            try:
                await _record_failure(
                    session,
                    tenant_id,
                    cache_key,
                    existing_payload=payload,
                    existing_data_as_of=data_as_of,
                    error_message=str(exc),
                )
            except Exception:
                await session.rollback()
            raise RealtimeRevenueUnavailable(
                _error_cooldown_seconds(), "upstream_fetch_failed"
            ) from exc

    timeout = _follower_wait_timeout_seconds()
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    poll_interval = _follower_poll_interval_seconds()
    while loop.time() < deadline:
        await asyncio.sleep(poll_interval)
        row = await _fetch_cache_row(session, tenant_id, cache_key)
        if row:
            cooldown_until = row.get("error_cooldown_until")
            now = _utcnow()
            if cooldown_until and cooldown_until > now:
                retry_after = int((cooldown_until - now).total_seconds())
                raise RealtimeRevenueUnavailable(retry_after, "error_cooldown_active")
            expires_at = row.get("expires_at")
            payload = row.get("payload") or {}
            if expires_at and expires_at > now and payload:
                snapshot = RealtimeRevenueSnapshot.from_payload(payload)
                etag = row.get("etag") or _compute_etag(payload)
                return snapshot, etag, True

    raise RealtimeRevenueUnavailable(1, "refresh_timeout")


async def _default_fetcher(tenant_id: UUID) -> RealtimeRevenueSnapshot:
    now = _utcnow()
    return RealtimeRevenueSnapshot(
        tenant_id=tenant_id,
        interval="minute",
        currency="USD",
        revenue_total_cents=12_500_050,
        event_count=0,
        verified=False,
        data_as_of=now,
        sources=[],
        confidence_score=None,
        upgrade_notice="Revenue data pending reconciliation. Full statistical verification available in Phase B2.6.",
    )
