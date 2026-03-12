"""
Provider OAuth token refresh orchestration primitives (B1.3-P7).

This module is intentionally side-effect constrained:
- queryable lifecycle metadata drives selection (no decrypt-all scans)
- adapter dispatch is provider-neutral
- single-flight lock prevents concurrent duplicate refresh per credential
- failure classes map to durable degraded/revoked lifecycle outcomes
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import struct
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock as clock_module
from app.core.secrets import get_platform_encryption_material_for_write
from app.services.oauth_lifecycle_dispatcher import ProviderOAuthLifecycleDispatcher
from app.services.platform_credentials import (
    PlatformCredentialNotFoundError,
    PlatformCredentialService,
    PlatformCredentialStore,
    compute_next_refresh_due_at,
)
from app.services.provider_oauth_lifecycle import (
    OAuthLifecycleAdapterError,
    OAuthLifecycleNotImplementedError,
    OAuthLifecycleRefreshError,
    OAuthTokenRefreshRequest,
)

_REFRESH_LOCK_NAMESPACE = struct.unpack(
    "!i",
    hashlib.sha256(b"provider-token-refresh-lock-namespace").digest()[:4],
)[0]
_TRANSIENT_BACKOFF_BASE = timedelta(minutes=5)
_TRANSIENT_BACKOFF_MAX = timedelta(hours=6)


def _utcnow() -> datetime:
    return clock_module.utcnow()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _int32_from_value(value: str) -> int:
    return struct.unpack("!i", hashlib.sha256(value.encode("utf-8")).digest()[:4])[0]


def _refresh_due_now(
    *,
    next_refresh_due_at: datetime | None,
    expires_at: datetime | None,
    now: datetime,
) -> bool:
    if next_refresh_due_at is not None and _as_utc(next_refresh_due_at) <= now:
        return True
    computed = compute_next_refresh_due_at(expires_at, now=now)
    if computed is not None and computed <= now:
        return True
    return False


def _classify_refresh_error(exc: Exception) -> tuple[str, bool, int | None]:
    if isinstance(exc, OAuthLifecycleRefreshError):
        return exc.failure_class, bool(exc.terminal), exc.retry_after_seconds
    if isinstance(exc, OAuthLifecycleNotImplementedError):
        return "provider_refresh_not_implemented", True, None
    if isinstance(exc, OAuthLifecycleAdapterError):
        return "provider_transport_failure", False, None
    return "provider_transport_failure", False, None


def _next_transient_retry_due_at(
    *,
    now: datetime,
    failure_count: int,
    retry_after_seconds: int | None = None,
) -> datetime:
    if retry_after_seconds is not None and retry_after_seconds > 0:
        return now + timedelta(seconds=retry_after_seconds)
    bounded_count = max(1, min(int(failure_count), 8))
    delay = _TRANSIENT_BACKOFF_BASE * (2 ** (bounded_count - 1))
    if delay > _TRANSIENT_BACKOFF_MAX:
        delay = _TRANSIENT_BACKOFF_MAX
    return now + delay


@dataclass(frozen=True)
class RefreshSelectionResult:
    due_count: int
    claimed_credential_ids: tuple[UUID, ...]


@dataclass(frozen=True)
class RefreshExecutionResult:
    credential_id: UUID
    platform: str | None
    status: str
    failure_class: str | None
    next_refresh_due_at: datetime | None

    def to_public_dict(self) -> dict[str, object]:
        return {
            "credential_id": str(self.credential_id),
            "platform": self.platform,
            "status": self.status,
            "failure_class": self.failure_class,
            "next_refresh_due_at": self.next_refresh_due_at.isoformat() if self.next_refresh_due_at else None,
        }


async def claim_due_credentials_for_tenant(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    as_of: datetime | None = None,
    limit: int = 100,
) -> RefreshSelectionResult:
    now = _as_utc(as_of or _utcnow())
    due_rows = await PlatformCredentialStore.list_refresh_due(
        session,
        tenant_id=tenant_id,
        as_of=now,
        limit=max(1, int(limit)),
    )
    claimed: list[UUID] = []
    for row in due_rows:
        did_claim = await PlatformCredentialStore.claim_refresh_window(
            session,
            tenant_id=tenant_id,
            credential_id=row.id,
            as_of=now,
        )
        if did_claim:
            claimed.append(row.id)

    return RefreshSelectionResult(
        due_count=len(due_rows),
        claimed_credential_ids=tuple(claimed),
    )


async def _try_acquire_refresh_lock(session: AsyncSession, *, credential_id: UUID) -> bool:
    lock_key = _int32_from_value(str(credential_id))
    row = (
        await session.execute(
            text("SELECT pg_try_advisory_xact_lock(:namespace_key, :credential_key) AS acquired"),
            {
                "namespace_key": _REFRESH_LOCK_NAMESPACE,
                "credential_key": lock_key,
            },
        )
    ).mappings().one()
    return bool(row["acquired"])


async def refresh_credential_once(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    credential_id: UUID,
    correlation_id: UUID,
    force: bool = False,
    dispatcher: ProviderOAuthLifecycleDispatcher | None = None,
) -> RefreshExecutionResult:
    now = _as_utc(_utcnow())
    acquired = await _try_acquire_refresh_lock(session, credential_id=credential_id)
    if not acquired:
        return RefreshExecutionResult(
            credential_id=credential_id,
            platform=None,
            status="skipped_locked",
            failure_class=None,
            next_refresh_due_at=None,
        )

    try:
        credentials = await PlatformCredentialService.get_credentials_by_id(
            session,
            tenant_id=tenant_id,
            credential_id=credential_id,
            allow_expired=True,
        )
    except PlatformCredentialNotFoundError:
        return RefreshExecutionResult(
            credential_id=credential_id,
            platform=None,
            status="credential_missing",
            failure_class=None,
            next_refresh_due_at=None,
        )

    if not force and not _refresh_due_now(
        next_refresh_due_at=credentials.next_refresh_due_at,
        expires_at=credentials.expires_at,
        now=now,
    ):
        return RefreshExecutionResult(
            credential_id=credential_id,
            platform=credentials.platform,
            status="skipped_not_due",
            failure_class=None,
            next_refresh_due_at=credentials.next_refresh_due_at,
        )

    if not credentials.refresh_token:
        await PlatformCredentialStore.record_refresh_failure(
            session,
            tenant_id=tenant_id,
            credential_id=credential_id,
            failure_class="provider_refresh_token_missing",
            failure_at=now,
        )
        await PlatformCredentialStore.mark_revoked(
            session,
            tenant_id=tenant_id,
            credential_id=credential_id,
            revoked_at=now,
        )
        return RefreshExecutionResult(
            credential_id=credential_id,
            platform=credentials.platform,
            status="revoked_terminal",
            failure_class="provider_refresh_token_missing",
            next_refresh_due_at=None,
        )

    runtime_dispatcher = dispatcher or ProviderOAuthLifecycleDispatcher()
    try:
        refreshed = await runtime_dispatcher.refresh_token(
            platform=credentials.platform,
            request=OAuthTokenRefreshRequest(
                tenant_id=tenant_id,
                correlation_id=correlation_id,
                refresh_token=credentials.refresh_token,
                scope=credentials.scope,
            ),
        )
        key_id, encryption_key = get_platform_encryption_material_for_write()
        refresh_token_value = refreshed.refresh_token or credentials.refresh_token
        stored = await PlatformCredentialStore.mark_refresh_success(
            session,
            tenant_id=tenant_id,
            credential_id=credential_id,
            access_token=refreshed.access_token,
            refresh_token=refresh_token_value,
            expires_at=refreshed.expires_at,
            scope=refreshed.scope,
            token_type=refreshed.token_type,
            key_id=key_id,
            encryption_key=encryption_key,
            refreshed_at=now,
            next_refresh_due_at=compute_next_refresh_due_at(refreshed.expires_at, now=now),
        )
        return RefreshExecutionResult(
            credential_id=credential_id,
            platform=credentials.platform,
            status="refreshed",
            failure_class=None,
            next_refresh_due_at=stored.get("next_refresh_due_at"),
        )
    except Exception as exc:
        failure_class, is_terminal, retry_after_seconds = _classify_refresh_error(exc)
        if is_terminal:
            await PlatformCredentialStore.record_refresh_failure(
                session,
                tenant_id=tenant_id,
                credential_id=credential_id,
                failure_class=failure_class,
                failure_at=now,
            )
            await PlatformCredentialStore.mark_revoked(
                session,
                tenant_id=tenant_id,
                credential_id=credential_id,
                revoked_at=now,
            )
            return RefreshExecutionResult(
                credential_id=credential_id,
                platform=credentials.platform,
                status="revoked_terminal",
                failure_class=failure_class,
                next_refresh_due_at=None,
            )

        next_due = _next_transient_retry_due_at(
            now=now,
            failure_count=max(1, credentials.refresh_failure_count + 1),
            retry_after_seconds=retry_after_seconds,
        )
        failure_row = await PlatformCredentialStore.record_refresh_failure(
            session,
            tenant_id=tenant_id,
            credential_id=credential_id,
            failure_class=failure_class,
            next_refresh_due_at=next_due,
            failure_at=now,
        )
        return RefreshExecutionResult(
            credential_id=credential_id,
            platform=credentials.platform,
            status="failed_transient",
            failure_class=failure_class,
            next_refresh_due_at=failure_row.get("next_refresh_due_at"),
        )
