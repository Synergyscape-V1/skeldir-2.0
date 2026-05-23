"""B2.4-P4 cheap preflight lease before P2/P4 work."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


DEFAULT_PREFLIGHT_LEASE_SECONDS = 600
PREFLIGHT_LEASE_POLICY_VERSION = "b24-p4-preflight-lease-v1"


@dataclass(frozen=True)
class PreflightLeaseResult:
    acquired: bool
    tenant_id: UUID
    preflight_lease_id: str
    status: str
    leased_until: datetime | None
    stale_recovered: bool = False


def preflight_lease_id(
    *,
    tenant_id: UUID,
    model_type: str,
    model_version: str,
    source_window_start: datetime,
    source_window_end: datetime,
) -> str:
    """Return the hash-free lease identity used in evidence and profiles."""

    return (
        f"{tenant_id}:{model_type}:{model_version}:"
        f"{source_window_start.isoformat()}:{source_window_end.isoformat()}"
    )


async def acquire_preflight_lease(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    model_type: str,
    model_version: str,
    source_window_start: datetime,
    source_window_end: datetime,
    lease_owner: str,
    lease_seconds: int = DEFAULT_PREFLIGHT_LEASE_SECONDS,
) -> PreflightLeaseResult:
    """Acquire the hash-free P4 lease before source snapshot/profile work."""

    now = datetime.now(timezone.utc)
    leased_until = now + timedelta(seconds=max(1, int(lease_seconds)))
    params = {
        "tenant_id": str(tenant_id),
        "model_type": model_type,
        "model_version": model_version,
        "source_window_start": source_window_start,
        "source_window_end": source_window_end,
        "lease_owner": lease_owner,
        "leased_until": leased_until,
    }
    inserted = (
        (
            await session.execute(
                text(
                    """
                    INSERT INTO public.b24_active_execution_leases (
                        tenant_id,
                        model_type,
                        model_version,
                        source_window_start,
                        source_window_end,
                        status,
                        needs_refit_after_current,
                        lease_owner,
                        leased_until,
                        heartbeat_at,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        :tenant_id,
                        :model_type,
                        :model_version,
                        :source_window_start,
                        :source_window_end,
                        'claiming',
                        false,
                        :lease_owner,
                        :leased_until,
                        now(),
                        now(),
                        now()
                    )
                    ON CONFLICT DO NOTHING
                    RETURNING status, leased_until
                    """
                ),
                params,
            )
        )
        .mappings()
        .one_or_none()
    )
    lease_id = preflight_lease_id(
        tenant_id=tenant_id,
        model_type=model_type,
        model_version=model_version,
        source_window_start=source_window_start,
        source_window_end=source_window_end,
    )
    if inserted is not None:
        return PreflightLeaseResult(True, tenant_id, lease_id, "claiming", leased_until)

    existing = (
        (
            await session.execute(
                text(
                    """
                    SELECT status, fit_id, leased_until
                    FROM public.b24_active_execution_leases
                    WHERE tenant_id = :tenant_id
                      AND model_type = :model_type
                      AND model_version = :model_version
                      AND source_window_start = :source_window_start
                      AND source_window_end = :source_window_end
                    FOR UPDATE
                    """
                ),
                params,
            )
        )
        .mappings()
        .one()
    )
    stale = existing["leased_until"] is not None and existing["leased_until"] < now
    if stale:
        await session.execute(
            text(
                """
                UPDATE public.b24_active_execution_leases
                SET fit_id = NULL,
                    active_source_snapshot_hash = NULL,
                    latest_desired_source_snapshot_hash = NULL,
                    status = 'claiming',
                    needs_refit_after_current = false,
                    lease_owner = :lease_owner,
                    lease_acquired_at = now(),
                    leased_until = :leased_until,
                    heartbeat_at = now(),
                    stale_recovered_at = now(),
                    terminal_at = NULL,
                    updated_at = now()
                WHERE tenant_id = :tenant_id
                  AND model_type = :model_type
                  AND model_version = :model_version
                  AND source_window_start = :source_window_start
                  AND source_window_end = :source_window_end
                """
            ),
            params,
        )
        return PreflightLeaseResult(
            True,
            tenant_id,
            lease_id,
            "claiming",
            leased_until,
            stale_recovered=True,
        )
    return PreflightLeaseResult(
        False,
        tenant_id,
        lease_id,
        str(existing["status"]),
        existing["leased_until"],
    )


async def terminalize_preflight_lease(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    model_type: str,
    model_version: str,
    source_window_start: datetime,
    source_window_end: datetime,
    fit_id: UUID | None,
    terminal_status: str = "fallback_only",
) -> None:
    """Release or terminalize a P4 preflight lease after rejection."""

    if fit_id is None:
        await session.execute(
            text(
                """
                DELETE FROM public.b24_active_execution_leases
                WHERE tenant_id = :tenant_id
                  AND model_type = :model_type
                  AND model_version = :model_version
                  AND source_window_start = :source_window_start
                  AND source_window_end = :source_window_end
                  AND status = 'claiming'
                  AND fit_id IS NULL
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "model_type": model_type,
                "model_version": model_version,
                "source_window_start": source_window_start,
                "source_window_end": source_window_end,
            },
        )
        return
    await session.execute(
        text(
            """
            UPDATE public.b24_active_execution_leases
            SET fit_id = :fit_id,
                status = :terminal_status,
                terminal_at = now(),
                heartbeat_at = now(),
                updated_at = now()
            WHERE tenant_id = :tenant_id
              AND model_type = :model_type
              AND model_version = :model_version
              AND source_window_start = :source_window_start
              AND source_window_end = :source_window_end
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "model_type": model_type,
            "model_version": model_version,
            "source_window_start": source_window_start,
            "source_window_end": source_window_end,
            "fit_id": str(fit_id),
            "terminal_status": terminal_status,
        },
    )
