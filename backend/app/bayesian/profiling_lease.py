"""Hash-scoped B2.4-P4 profiling lease before authority/P4 envelope work."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


PROFILING_LEASE_POLICY_VERSION = "b24-p4-profiling-lease-v1"
DEFAULT_PROFILING_LEASE_SECONDS = 300


class ProfilingLeaseStatus(StrEnum):
    PROFILING = "profiling"
    PROFILE_REJECTED = "profile_rejected"
    PROFILE_PASSED = "profile_passed"
    PROFILE_SUPERSEDED = "profile_superseded"
    PROFILE_TIMEOUT = "profile_timeout"
    PROFILE_FAILED = "profile_failed"


@dataclass(frozen=True)
class ProfilingLeaseResult:
    profiling_lease_id: str
    tenant_id: UUID
    model_type: str
    model_version: str
    source_window_start: datetime
    source_window_end: datetime
    source_snapshot_hash: str
    acquired: bool
    status: ProfilingLeaseStatus
    lease_owner: str | None
    leased_until: datetime | None


def profiling_lease_id(
    *,
    tenant_id: UUID,
    model_type: str,
    model_version: str,
    source_window_start: datetime,
    source_window_end: datetime,
    source_snapshot_hash: str,
) -> str:
    """Return the hash-scoped profiling identity used for duplicate P4 suppression."""

    material = (
        f"{tenant_id}|{model_type}|{model_version}|"
        f"{source_window_start.isoformat()}|{source_window_end.isoformat()}|"
        f"{source_snapshot_hash}"
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


async def acquire_profiling_lease(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    model_type: str,
    model_version: str,
    source_window_start: datetime,
    source_window_end: datetime,
    source_snapshot_hash: str,
    lease_owner: str,
    lease_seconds: int = DEFAULT_PROFILING_LEASE_SECONDS,
) -> ProfilingLeaseResult:
    """Acquire one profiler slot for tenant/model/window/source_snapshot_hash."""

    leased_until = datetime.now(timezone.utc) + timedelta(
        seconds=max(1, int(lease_seconds))
    )
    lease_id = profiling_lease_id(
        tenant_id=tenant_id,
        model_type=model_type,
        model_version=model_version,
        source_window_start=source_window_start,
        source_window_end=source_window_end,
        source_snapshot_hash=source_snapshot_hash,
    )
    params = {
        "tenant_id": str(tenant_id),
        "model_type": model_type,
        "model_version": model_version,
        "source_window_start": source_window_start,
        "source_window_end": source_window_end,
        "source_snapshot_hash": source_snapshot_hash,
        "profiling_lease_id": lease_id,
        "lease_owner": lease_owner,
        "leased_until": leased_until,
        "policy_version": PROFILING_LEASE_POLICY_VERSION,
    }
    acquired = (
        (
            await session.execute(
                text(
                    """
                    INSERT INTO public.b24_p4_profiling_leases (
                        tenant_id,
                        model_type,
                        model_version,
                        source_window_start,
                        source_window_end,
                        source_snapshot_hash,
                        profiling_lease_id,
                        status,
                        lease_owner,
                        leased_until,
                        attempt_count,
                        policy_version,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        :tenant_id,
                        :model_type,
                        :model_version,
                        :source_window_start,
                        :source_window_end,
                        :source_snapshot_hash,
                        :profiling_lease_id,
                        'profiling',
                        :lease_owner,
                        :leased_until,
                        1,
                        :policy_version,
                        now(),
                        now()
                    )
                    ON CONFLICT (
                        tenant_id,
                        model_type,
                        model_version,
                        source_window_start,
                        source_window_end,
                        source_snapshot_hash
                    )
                    DO UPDATE SET
                        status = 'profiling',
                        lease_owner = :lease_owner,
                        leased_until = :leased_until,
                        attempt_count = b24_p4_profiling_leases.attempt_count + 1,
                        stale_recovered_at = CASE
                            WHEN b24_p4_profiling_leases.status = 'profiling'
                             AND b24_p4_profiling_leases.leased_until < now()
                                THEN now()
                            ELSE b24_p4_profiling_leases.stale_recovered_at
                        END,
                        terminal_at = NULL,
                        terminal_reason = NULL,
                        updated_at = now()
                    WHERE b24_p4_profiling_leases.status = 'profiling'
                      AND b24_p4_profiling_leases.leased_until < now()
                    RETURNING
                        profiling_lease_id,
                        tenant_id,
                        model_type,
                        model_version,
                        source_window_start,
                        source_window_end,
                        source_snapshot_hash,
                        status,
                        lease_owner,
                        leased_until
                    """
                ),
                params,
            )
        )
        .mappings()
        .one_or_none()
    )
    if acquired is None:
        current = (
            (
                await session.execute(
                    text(
                        """
                        SELECT
                            profiling_lease_id,
                            tenant_id,
                            model_type,
                            model_version,
                            source_window_start,
                            source_window_end,
                            source_snapshot_hash,
                            status,
                            lease_owner,
                            leased_until
                        FROM public.b24_p4_profiling_leases
                        WHERE tenant_id = :tenant_id
                          AND model_type = :model_type
                          AND model_version = :model_version
                          AND source_window_start = :source_window_start
                          AND source_window_end = :source_window_end
                          AND source_snapshot_hash = :source_snapshot_hash
                        """
                    ),
                    params,
                )
            )
            .mappings()
            .one()
        )
        return _lease_result_from_row(dict(current), acquired=False)
    return _lease_result_from_row(dict(acquired), acquired=True)


async def terminalize_profiling_lease(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    model_type: str,
    model_version: str,
    source_window_start: datetime,
    source_window_end: datetime,
    source_snapshot_hash: str,
    lease_owner: str,
    terminal_status: ProfilingLeaseStatus,
    terminal_reason: str | None = None,
) -> None:
    """Release the profiler slot on every terminal P4 path."""

    await session.execute(
        text(
            """
            UPDATE public.b24_p4_profiling_leases
            SET status = :terminal_status,
                leased_until = now(),
                terminal_reason = :terminal_reason,
                terminal_at = now(),
                updated_at = now()
            WHERE tenant_id = :tenant_id
              AND model_type = :model_type
              AND model_version = :model_version
              AND source_window_start = :source_window_start
              AND source_window_end = :source_window_end
              AND source_snapshot_hash = :source_snapshot_hash
              AND lease_owner = :lease_owner
              AND status = 'profiling'
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "model_type": model_type,
            "model_version": model_version,
            "source_window_start": source_window_start,
            "source_window_end": source_window_end,
            "source_snapshot_hash": source_snapshot_hash,
            "lease_owner": lease_owner,
            "terminal_status": terminal_status.value,
            "terminal_reason": terminal_reason,
        },
    )


def _lease_result_from_row(
    row: dict[str, object], *, acquired: bool
) -> ProfilingLeaseResult:
    return ProfilingLeaseResult(
        profiling_lease_id=str(row["profiling_lease_id"]),
        tenant_id=row["tenant_id"],
        model_type=str(row["model_type"]),
        model_version=str(row["model_version"]),
        source_window_start=row["source_window_start"],
        source_window_end=row["source_window_end"],
        source_snapshot_hash=str(row["source_snapshot_hash"]),
        acquired=acquired,
        status=ProfilingLeaseStatus(str(row["status"])),
        lease_owner=str(row["lease_owner"]) if row["lease_owner"] else None,
        leased_until=row["leased_until"],
    )
