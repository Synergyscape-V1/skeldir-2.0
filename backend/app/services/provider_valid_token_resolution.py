"""
Canonical valid-token resolution path for provider-facing runtime calls (B1.3-P7).

This path never performs inline refresh calls. It can enqueue bounded worker
refresh when a credential is due while still returning currently valid tokens.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock as clock_module
from app.services.platform_credentials import (
    PlatformCredentialExpiredError,
    PlatformCredentialService,
    PlatformCredentialStore,
    compute_next_refresh_due_at,
)
from app.tasks.enqueue import enqueue_tenant_task_by_name

_REFRESH_TASK_NAME = "app.tasks.maintenance.refresh_provider_oauth_credential"


def _utcnow() -> datetime:
    return clock_module.utcnow()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class ResolvedProviderToken:
    credential_id: UUID
    access_token: str
    refresh_token: str | None
    expires_at: datetime | None
    scope: str | None
    token_type: str | None
    key_id: str
    refresh_enqueued: bool


class ProviderValidTokenResolver:
    def __init__(self, *, enqueue_refresh: bool = True) -> None:
        self._enqueue_refresh = enqueue_refresh

    async def resolve_for_connection(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        connection_id: UUID,
        correlation_id: UUID,
    ) -> ResolvedProviderToken:
        credentials = await PlatformCredentialService.get_credentials(
            session,
            tenant_id=tenant_id,
            connection_id=connection_id,
            allow_expired=True,
        )
        now = _utcnow()
        refresh_due = False
        if credentials.next_refresh_due_at is not None and _as_utc(credentials.next_refresh_due_at) <= now:
            refresh_due = True
        else:
            computed_due = compute_next_refresh_due_at(credentials.expires_at, now=now)
            if computed_due is not None and computed_due <= now:
                refresh_due = True

        refresh_enqueued = False
        if self._enqueue_refresh and refresh_due:
            claimed = await PlatformCredentialStore.claim_refresh_window(
                session,
                tenant_id=tenant_id,
                credential_id=credentials.id,
                as_of=now,
            )
            if claimed:
                try:
                    enqueue_tenant_task_by_name(
                        _REFRESH_TASK_NAME,
                        envelope={
                            "context_type": "system",
                            "tenant_id": str(tenant_id),
                        },
                        kwargs={
                            "credential_id": str(credentials.id),
                            "correlation_id": str(correlation_id),
                            "refresh_claimed": True,
                        },
                        correlation_id=str(correlation_id),
                    )
                    refresh_enqueued = True
                except Exception:
                    refresh_enqueued = False

        if credentials.expires_at is not None and _as_utc(credentials.expires_at) <= now:
            raise PlatformCredentialExpiredError()

        return ResolvedProviderToken(
            credential_id=credentials.id,
            access_token=credentials.access_token,
            refresh_token=credentials.refresh_token,
            expires_at=credentials.expires_at,
            scope=credentials.scope,
            token_type=credentials.token_type,
            key_id=credentials.key_id,
            refresh_enqueued=refresh_enqueued,
        )
