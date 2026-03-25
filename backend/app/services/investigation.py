"""Investigation lifecycle authority service for B1.5 centaur control."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional, Protocol
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from app.core import clock as clock_module
from app.services.centaur_lifecycle import LifecycleStatus

logger = logging.getLogger(__name__)


class Clock(Protocol):
    """Protocol for time abstraction (testability)."""

    def now(self) -> datetime:
        """Return current UTC time."""
        ...


class SystemClock:
    """Production clock using system time."""

    def now(self) -> datetime:
        return clock_module.utcnow()


class FixedClock:
    """Test clock with controllable time."""

    def __init__(self, fixed_time: Optional[datetime] = None):
        self._time = fixed_time or clock_module.utcnow()

    def now(self) -> datetime:
        return self._time

    def advance(self, seconds: int) -> datetime:
        self._time = self._time + timedelta(seconds=seconds)
        return self._time

    def set(self, time: datetime) -> None:
        self._time = time


# Backwards-compatible alias used by existing tests.
InvestigationStatus = LifecycleStatus

# Default minimum hold period in seconds.
DEFAULT_MIN_HOLD_SECONDS = 45


@dataclass(frozen=True)
class InvestigationJob:
    """Authoritative investigation lifecycle row."""

    id: UUID
    tenant_id: UUID
    request_id: str
    correlation_id: Optional[str]
    status: LifecycleStatus
    created_at: datetime
    updated_at: datetime
    min_hold_until: datetime
    ready_for_review_at: Optional[datetime]
    approved_at: Optional[datetime]
    rejected_at: Optional[datetime]
    refine_requested_at: Optional[datetime]
    rerun_requested_at: Optional[datetime]
    completed_at: Optional[datetime]
    failed_at: Optional[datetime]
    timeout_at: Optional[datetime]
    cancelled_at: Optional[datetime]
    result: Optional[dict[str, Any]]
    failure_code: Optional[str]
    failure_reason: Optional[str]
    remaining_hold_seconds: int

    @property
    def can_transition_to_ready(self) -> bool:
        return (
            self.status
            in (
                LifecycleStatus.SUBMITTED,
                LifecycleStatus.VALIDATING,
                LifecycleStatus.INVESTIGATING,
                LifecycleStatus.RERUN_REQUESTED,
            )
            and self.remaining_hold_seconds <= 0
        )

    @property
    def can_approve(self) -> bool:
        return self.status == LifecycleStatus.READY_FOR_REVIEW


class InvestigationService:
    """Service-owned investigation lifecycle authority."""

    def __init__(
        self,
        clock: Optional[Clock] = None,
        min_hold_seconds: int = DEFAULT_MIN_HOLD_SECONDS,
    ):
        self.clock = clock or SystemClock()
        self.min_hold_seconds = min_hold_seconds

    async def create_job(
        self,
        conn: AsyncConnection | AsyncSession,
        tenant_id: UUID,
        correlation_id: Optional[str] = None,
        request_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> InvestigationJob:
        now = self.clock.now()
        min_hold_until = now + timedelta(seconds=self.min_hold_seconds)
        resolved_request_id = (
            request_id
            or correlation_id
            or f"investigation-{tenant_id}-{now.isoformat()}"
        )

        insert_result = await conn.execute(
            text(
                """
                INSERT INTO investigation_jobs (
                    tenant_id,
                    request_id,
                    correlation_id,
                    status,
                    created_at,
                    updated_at,
                    min_hold_until,
                    metadata
                ) VALUES (
                    :tenant_id,
                    :request_id,
                    :correlation_id,
                    :status,
                    :created_at,
                    :updated_at,
                    :min_hold_until,
                    CAST(:metadata AS JSONB)
                )
                RETURNING id
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "request_id": resolved_request_id,
                "correlation_id": correlation_id,
                "status": LifecycleStatus.SUBMITTED.value,
                "created_at": now,
                "updated_at": now,
                "min_hold_until": min_hold_until,
                "metadata": json.dumps(metadata or {}),
            },
        )
        job_id = UUID(str(insert_result.scalar_one()))

        logger.info(
            "investigation_job_created",
            extra={
                "job_id": str(job_id),
                "tenant_id": str(tenant_id),
                "request_id": resolved_request_id,
            },
        )

        return InvestigationJob(
            id=job_id,
            tenant_id=tenant_id,
            request_id=resolved_request_id,
            correlation_id=correlation_id,
            status=LifecycleStatus.SUBMITTED,
            created_at=now,
            updated_at=now,
            min_hold_until=min_hold_until,
            ready_for_review_at=None,
            approved_at=None,
            rejected_at=None,
            refine_requested_at=None,
            rerun_requested_at=None,
            completed_at=None,
            failed_at=None,
            timeout_at=None,
            cancelled_at=None,
            result=None,
            failure_code=None,
            failure_reason=None,
            remaining_hold_seconds=self.min_hold_seconds,
        )

    async def get_or_create_job(
        self,
        conn: AsyncConnection | AsyncSession,
        *,
        tenant_id: UUID,
        request_id: str,
        correlation_id: Optional[str] = None,
    ) -> InvestigationJob:
        existing = await self.get_job_by_request_id(
            conn,
            tenant_id=tenant_id,
            request_id=request_id,
        )
        if existing is not None:
            return existing
        return await self.create_job(
            conn,
            tenant_id=tenant_id,
            request_id=request_id,
            correlation_id=correlation_id,
        )

    async def get_job_by_request_id(
        self,
        conn: AsyncConnection | AsyncSession,
        *,
        tenant_id: UUID,
        request_id: str,
    ) -> Optional[InvestigationJob]:
        result = await conn.execute(
            text(
                """
                SELECT
                    id,
                    tenant_id,
                    request_id,
                    correlation_id,
                    status,
                    created_at,
                    updated_at,
                    min_hold_until,
                    ready_for_review_at,
                    approved_at,
                    rejected_at,
                    refine_requested_at,
                    rerun_requested_at,
                    completed_at,
                    failed_at,
                    timeout_at,
                    cancelled_at,
                    result,
                    failure_code,
                    failure_reason
                FROM investigation_jobs
                WHERE tenant_id = :tenant_id
                  AND request_id = :request_id
                """
            ),
            {"tenant_id": str(tenant_id), "request_id": request_id},
        )
        row = result.mappings().first()
        if row is None:
            return None
        return await self._hydrate_with_auto_transition(conn, row)

    async def get_job(
        self,
        conn: AsyncConnection | AsyncSession,
        tenant_id: UUID,
        job_id: UUID,
    ) -> Optional[InvestigationJob]:
        result = await conn.execute(
            text(
                """
                SELECT
                    id,
                    tenant_id,
                    request_id,
                    correlation_id,
                    status,
                    created_at,
                    updated_at,
                    min_hold_until,
                    ready_for_review_at,
                    approved_at,
                    rejected_at,
                    refine_requested_at,
                    rerun_requested_at,
                    completed_at,
                    failed_at,
                    timeout_at,
                    cancelled_at,
                    result,
                    failure_code,
                    failure_reason
                FROM investigation_jobs
                WHERE id = :job_id
                  AND tenant_id = :tenant_id
                """
            ),
            {"job_id": str(job_id), "tenant_id": str(tenant_id)},
        )
        row = result.mappings().first()
        if row is None:
            return None
        return await self._hydrate_with_auto_transition(conn, row)

    async def mark_validating(
        self,
        conn: AsyncConnection | AsyncSession,
        *,
        tenant_id: UUID,
        job_id: UUID,
    ) -> None:
        await self._transition(
            conn,
            tenant_id=tenant_id,
            job_id=job_id,
            next_status=LifecycleStatus.VALIDATING,
            allowed_current=(LifecycleStatus.SUBMITTED, LifecycleStatus.RERUN_REQUESTED),
        )

    async def mark_investigating(
        self,
        conn: AsyncConnection | AsyncSession,
        *,
        tenant_id: UUID,
        job_id: UUID,
    ) -> None:
        await self._transition(
            conn,
            tenant_id=tenant_id,
            job_id=job_id,
            next_status=LifecycleStatus.INVESTIGATING,
            allowed_current=(
                LifecycleStatus.SUBMITTED,
                LifecycleStatus.VALIDATING,
                LifecycleStatus.RERUN_REQUESTED,
            ),
        )

    async def mark_ready_for_review(
        self,
        conn: AsyncConnection | AsyncSession,
        *,
        tenant_id: UUID,
        job_id: UUID,
        result_payload: Optional[dict[str, Any]] = None,
    ) -> None:
        await self._transition(
            conn,
            tenant_id=tenant_id,
            job_id=job_id,
            next_status=LifecycleStatus.READY_FOR_REVIEW,
            allowed_current=(
                LifecycleStatus.SUBMITTED,
                LifecycleStatus.VALIDATING,
                LifecycleStatus.INVESTIGATING,
                LifecycleStatus.RERUN_REQUESTED,
            ),
            ready_for_review=True,
            result_payload=result_payload,
        )

    async def approve_job(
        self,
        conn: AsyncConnection | AsyncSession,
        tenant_id: UUID,
        job_id: UUID,
    ) -> InvestigationJob:
        await self._transition(
            conn,
            tenant_id=tenant_id,
            job_id=job_id,
            next_status=LifecycleStatus.APPROVED,
            allowed_current=(LifecycleStatus.READY_FOR_REVIEW,),
            approved=True,
        )
        job = await self.get_job(conn, tenant_id, job_id)
        if job is None:
            raise ValueError(f"Job {job_id} not found")
        return job

    async def reject_job(
        self,
        conn: AsyncConnection | AsyncSession,
        *,
        tenant_id: UUID,
        job_id: UUID,
        reason: Optional[str] = None,
    ) -> None:
        await self._transition(
            conn,
            tenant_id=tenant_id,
            job_id=job_id,
            next_status=LifecycleStatus.REJECTED,
            allowed_current=(LifecycleStatus.READY_FOR_REVIEW,),
            rejected=True,
            failure_reason=reason,
        )

    async def request_refine(
        self,
        conn: AsyncConnection | AsyncSession,
        *,
        tenant_id: UUID,
        job_id: UUID,
        reason: Optional[str] = None,
    ) -> None:
        await self._transition(
            conn,
            tenant_id=tenant_id,
            job_id=job_id,
            next_status=LifecycleStatus.REFINE_REQUESTED,
            allowed_current=(LifecycleStatus.READY_FOR_REVIEW,),
            refine_requested=True,
            failure_reason=reason,
        )

    async def request_rerun(
        self,
        conn: AsyncConnection | AsyncSession,
        *,
        tenant_id: UUID,
        job_id: UUID,
        reason: Optional[str] = None,
    ) -> None:
        await self._transition(
            conn,
            tenant_id=tenant_id,
            job_id=job_id,
            next_status=LifecycleStatus.RERUN_REQUESTED,
            allowed_current=(
                LifecycleStatus.REJECTED,
                LifecycleStatus.REFINE_REQUESTED,
                LifecycleStatus.FAILED,
                LifecycleStatus.TIMEOUT,
            ),
            rerun_requested=True,
            failure_reason=reason,
        )

    async def complete_job(
        self,
        conn: AsyncConnection | AsyncSession,
        *,
        tenant_id: UUID,
        job_id: UUID,
    ) -> None:
        await self._transition(
            conn,
            tenant_id=tenant_id,
            job_id=job_id,
            next_status=LifecycleStatus.COMPLETED,
            allowed_current=(LifecycleStatus.APPROVED,),
            completed=True,
        )

    async def fail_job(
        self,
        conn: AsyncConnection | AsyncSession,
        *,
        tenant_id: UUID,
        job_id: UUID,
        failure_code: Optional[str] = None,
        failure_reason: Optional[str] = None,
    ) -> None:
        await self._transition(
            conn,
            tenant_id=tenant_id,
            job_id=job_id,
            next_status=LifecycleStatus.FAILED,
            allowed_current=(
                LifecycleStatus.SUBMITTED,
                LifecycleStatus.VALIDATING,
                LifecycleStatus.INVESTIGATING,
                LifecycleStatus.RERUN_REQUESTED,
            ),
            failed=True,
            failure_code=failure_code,
            failure_reason=failure_reason,
        )

    async def timeout_job(
        self,
        conn: AsyncConnection | AsyncSession,
        *,
        tenant_id: UUID,
        job_id: UUID,
        failure_reason: Optional[str] = None,
    ) -> None:
        await self._transition(
            conn,
            tenant_id=tenant_id,
            job_id=job_id,
            next_status=LifecycleStatus.TIMEOUT,
            allowed_current=(
                LifecycleStatus.SUBMITTED,
                LifecycleStatus.VALIDATING,
                LifecycleStatus.INVESTIGATING,
                LifecycleStatus.RERUN_REQUESTED,
            ),
            timeout=True,
            failure_code="timeout",
            failure_reason=failure_reason,
        )

    async def cancel_job(
        self,
        conn: AsyncConnection | AsyncSession,
        *,
        tenant_id: UUID,
        job_id: UUID,
        reason: Optional[str] = None,
    ) -> None:
        await self._transition(
            conn,
            tenant_id=tenant_id,
            job_id=job_id,
            next_status=LifecycleStatus.CANCELLED,
            allowed_current=(
                LifecycleStatus.SUBMITTED,
                LifecycleStatus.VALIDATING,
                LifecycleStatus.INVESTIGATING,
                LifecycleStatus.READY_FOR_REVIEW,
                LifecycleStatus.APPROVED,
                LifecycleStatus.REJECTED,
                LifecycleStatus.REFINE_REQUESTED,
                LifecycleStatus.RERUN_REQUESTED,
            ),
            cancelled=True,
            failure_reason=reason,
        )

    async def _hydrate_with_auto_transition(
        self,
        conn: AsyncConnection | AsyncSession,
        row: Any,
    ) -> InvestigationJob:
        now = self.clock.now()
        status = LifecycleStatus(str(row["status"]))
        min_hold_until = row["min_hold_until"]
        ready_for_review_at = row["ready_for_review_at"]
        if (
            status
            in (
                LifecycleStatus.SUBMITTED,
                LifecycleStatus.VALIDATING,
                LifecycleStatus.INVESTIGATING,
                LifecycleStatus.RERUN_REQUESTED,
            )
            and now >= min_hold_until
            and ready_for_review_at is None
        ):
            await self._transition(
                conn,
                tenant_id=UUID(str(row["tenant_id"])),
                job_id=UUID(str(row["id"])),
                next_status=LifecycleStatus.READY_FOR_REVIEW,
                allowed_current=(
                    LifecycleStatus.SUBMITTED,
                    LifecycleStatus.VALIDATING,
                    LifecycleStatus.INVESTIGATING,
                    LifecycleStatus.RERUN_REQUESTED,
                ),
                ready_for_review=True,
            )
            status = LifecycleStatus.READY_FOR_REVIEW
            ready_for_review_at = now

        if status in (
            LifecycleStatus.SUBMITTED,
            LifecycleStatus.VALIDATING,
            LifecycleStatus.INVESTIGATING,
            LifecycleStatus.RERUN_REQUESTED,
        ):
            remaining_hold_seconds = max(0, int((min_hold_until - now).total_seconds()))
        else:
            remaining_hold_seconds = 0

        return InvestigationJob(
            id=UUID(str(row["id"])),
            tenant_id=UUID(str(row["tenant_id"])),
            request_id=str(row["request_id"]),
            correlation_id=row["correlation_id"],
            status=status,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            min_hold_until=min_hold_until,
            ready_for_review_at=ready_for_review_at,
            approved_at=row["approved_at"],
            rejected_at=row["rejected_at"],
            refine_requested_at=row["refine_requested_at"],
            rerun_requested_at=row["rerun_requested_at"],
            completed_at=row["completed_at"],
            failed_at=row["failed_at"],
            timeout_at=row["timeout_at"],
            cancelled_at=row["cancelled_at"],
            result=row["result"],
            failure_code=row["failure_code"],
            failure_reason=row["failure_reason"],
            remaining_hold_seconds=remaining_hold_seconds,
        )

    async def _transition(
        self,
        conn: AsyncConnection | AsyncSession,
        *,
        tenant_id: UUID,
        job_id: UUID,
        next_status: LifecycleStatus,
        allowed_current: tuple[LifecycleStatus, ...],
        ready_for_review: bool = False,
        approved: bool = False,
        rejected: bool = False,
        refine_requested: bool = False,
        rerun_requested: bool = False,
        completed: bool = False,
        failed: bool = False,
        timeout: bool = False,
        cancelled: bool = False,
        failure_code: Optional[str] = None,
        failure_reason: Optional[str] = None,
        result_payload: Optional[dict[str, Any]] = None,
    ) -> None:
        now = self.clock.now()
        assignments = ["status = :status", "updated_at = :updated_at"]
        params: dict[str, Any] = {
            "status": next_status.value,
            "updated_at": now,
            "job_id": str(job_id),
            "tenant_id": str(tenant_id),
        }

        if ready_for_review:
            assignments.append("ready_for_review_at = :ready_for_review_at")
            params["ready_for_review_at"] = now
        if approved:
            assignments.append("approved_at = :approved_at")
            params["approved_at"] = now
        if rejected:
            assignments.append("rejected_at = :rejected_at")
            params["rejected_at"] = now
        if refine_requested:
            assignments.append("refine_requested_at = :refine_requested_at")
            params["refine_requested_at"] = now
        if rerun_requested:
            assignments.append("rerun_requested_at = :rerun_requested_at")
            params["rerun_requested_at"] = now
        if completed:
            assignments.append("completed_at = :completed_at")
            params["completed_at"] = now
        if failed:
            assignments.append("failed_at = :failed_at")
            params["failed_at"] = now
        if timeout:
            assignments.append("timeout_at = :timeout_at")
            params["timeout_at"] = now
        if cancelled:
            assignments.append("cancelled_at = :cancelled_at")
            params["cancelled_at"] = now
        if failure_code is not None:
            assignments.append("failure_code = :failure_code")
            params["failure_code"] = failure_code
        if failure_reason is not None:
            assignments.append("failure_reason = :failure_reason")
            params["failure_reason"] = failure_reason
        if result_payload is not None:
            assignments.append("result = CAST(:result AS JSONB)")
            params["result"] = json.dumps(result_payload)

        allowed_values = [status.value for status in allowed_current]
        placeholders = ", ".join(f":allowed_{idx}" for idx, _ in enumerate(allowed_values))
        for idx, value in enumerate(allowed_values):
            params[f"allowed_{idx}"] = value

        result = await conn.execute(
            text(
                f"""
                UPDATE investigation_jobs
                SET {", ".join(assignments)}
                WHERE id = :job_id
                  AND tenant_id = :tenant_id
                  AND status IN ({placeholders})
                """
            ),
            params,
        )
        if result.rowcount == 1:
            return

        current = await self.get_job(conn, tenant_id=tenant_id, job_id=job_id)
        if current is not None and current.status == next_status:
            return
        current_status = current.status.value if current is not None else "missing"
        raise ValueError(
            f"Illegal investigation transition {current_status} -> {next_status.value}"
        )
