"""Budget lifecycle authority service for B1.5 centaur review control."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock as clock_module
from app.services.centaur_lifecycle import LifecycleStatus

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BudgetJobRecord:
    """Authoritative budget lifecycle row."""

    id: UUID
    tenant_id: UUID
    request_id: str
    correlation_id: str
    status: LifecycleStatus
    created_at: datetime
    updated_at: datetime
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


class BudgetJobService:
    """Service-owned budget lifecycle authority."""

    async def get_or_create_job(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        request_id: str,
        correlation_id: str,
    ) -> BudgetJobRecord:
        existing = await self.get_by_request_id(
            session,
            tenant_id=tenant_id,
            request_id=request_id,
        )
        if existing is not None:
            return existing

        now = clock_module.utcnow()
        insert_result = await session.execute(
            text(
                """
                INSERT INTO budget_jobs (
                    tenant_id,
                    request_id,
                    correlation_id,
                    status,
                    created_at,
                    updated_at
                ) VALUES (
                    :tenant_id,
                    :request_id,
                    :correlation_id,
                    :status,
                    :created_at,
                    :updated_at
                )
                RETURNING id
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "request_id": request_id,
                "correlation_id": correlation_id,
                "status": LifecycleStatus.SUBMITTED.value,
                "created_at": now,
                "updated_at": now,
            },
        )
        job_id = UUID(str(insert_result.scalar_one()))
        logger.info(
            "budget_job_created",
            extra={
                "tenant_id": str(tenant_id),
                "request_id": request_id,
                "job_id": str(job_id),
            },
        )
        return await self.get_by_id(session, tenant_id=tenant_id, job_id=job_id)

    async def get_by_request_id(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        request_id: str,
    ) -> Optional[BudgetJobRecord]:
        result = await session.execute(
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
                FROM budget_jobs
                WHERE tenant_id = :tenant_id
                  AND request_id = :request_id
                """
            ),
            {"tenant_id": str(tenant_id), "request_id": request_id},
        )
        row = result.mappings().first()
        if row is None:
            return None
        return self._to_record(row)

    async def get_by_id(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        job_id: UUID,
    ) -> BudgetJobRecord:
        result = await session.execute(
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
                FROM budget_jobs
                WHERE tenant_id = :tenant_id
                  AND id = :job_id
                """
            ),
            {"tenant_id": str(tenant_id), "job_id": str(job_id)},
        )
        row = result.mappings().first()
        if row is None:
            raise ValueError(f"Budget job {job_id} not found")
        return self._to_record(row)

    async def mark_validating(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        job_id: UUID,
    ) -> None:
        await self._transition(
            session,
            tenant_id=tenant_id,
            job_id=job_id,
            next_status=LifecycleStatus.VALIDATING,
            allowed_current=(LifecycleStatus.SUBMITTED, LifecycleStatus.RERUN_REQUESTED),
        )

    async def mark_investigating(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        job_id: UUID,
    ) -> None:
        await self._transition(
            session,
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
        session: AsyncSession,
        *,
        tenant_id: UUID,
        job_id: UUID,
        result_payload: Optional[dict[str, Any]] = None,
    ) -> None:
        await self._transition(
            session,
            tenant_id=tenant_id,
            job_id=job_id,
            next_status=LifecycleStatus.READY_FOR_REVIEW,
            allowed_current=(
                LifecycleStatus.SUBMITTED,
                LifecycleStatus.VALIDATING,
                LifecycleStatus.INVESTIGATING,
                LifecycleStatus.RERUN_REQUESTED,
            ),
            result_payload=result_payload,
            ready_for_review=True,
        )

    async def approve_job(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        job_id: UUID,
    ) -> None:
        await self._transition(
            session,
            tenant_id=tenant_id,
            job_id=job_id,
            next_status=LifecycleStatus.APPROVED,
            allowed_current=(LifecycleStatus.READY_FOR_REVIEW,),
            approved=True,
        )

    async def reject_job(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        job_id: UUID,
        reason: Optional[str] = None,
    ) -> None:
        await self._transition(
            session,
            tenant_id=tenant_id,
            job_id=job_id,
            next_status=LifecycleStatus.REJECTED,
            allowed_current=(LifecycleStatus.READY_FOR_REVIEW,),
            rejected=True,
            failure_reason=reason,
        )

    async def request_refine(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        job_id: UUID,
        reason: Optional[str] = None,
    ) -> None:
        await self._transition(
            session,
            tenant_id=tenant_id,
            job_id=job_id,
            next_status=LifecycleStatus.REFINE_REQUESTED,
            allowed_current=(LifecycleStatus.READY_FOR_REVIEW,),
            refine_requested=True,
            failure_reason=reason,
        )

    async def request_rerun(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        job_id: UUID,
        reason: Optional[str] = None,
    ) -> None:
        await self._transition(
            session,
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

    async def request_retry(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        job_id: UUID,
        reason: Optional[str] = None,
    ) -> None:
        await self._transition(
            session,
            tenant_id=tenant_id,
            job_id=job_id,
            next_status=LifecycleStatus.RERUN_REQUESTED,
            allowed_current=(
                LifecycleStatus.FAILED,
                LifecycleStatus.TIMEOUT,
                LifecycleStatus.CANCELLED,
            ),
            rerun_requested=True,
            failure_reason=reason,
        )

    async def complete_job(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        job_id: UUID,
    ) -> None:
        await self._transition(
            session,
            tenant_id=tenant_id,
            job_id=job_id,
            next_status=LifecycleStatus.COMPLETED,
            allowed_current=(LifecycleStatus.APPROVED,),
            completed=True,
        )

    async def fail_job(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        job_id: UUID,
        failure_code: Optional[str] = None,
        failure_reason: Optional[str] = None,
    ) -> None:
        await self._transition(
            session,
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
        session: AsyncSession,
        *,
        tenant_id: UUID,
        job_id: UUID,
        failure_reason: Optional[str] = None,
    ) -> None:
        await self._transition(
            session,
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
        session: AsyncSession,
        *,
        tenant_id: UUID,
        job_id: UUID,
        reason: Optional[str] = None,
    ) -> None:
        await self._transition(
            session,
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

    async def get_status_projection(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        job_id: UUID,
    ) -> Optional[BudgetJobRecord]:
        """Read status-only projection without hydrating full recommendation payload."""
        result = await session.execute(
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
                    ready_for_review_at,
                    approved_at,
                    rejected_at,
                    refine_requested_at,
                    rerun_requested_at,
                    completed_at,
                    failed_at,
                    timeout_at,
                    cancelled_at,
                    failure_code,
                    failure_reason
                FROM budget_jobs
                WHERE tenant_id = :tenant_id
                  AND id = :job_id
                """
            ),
            {"tenant_id": str(tenant_id), "job_id": str(job_id)},
        )
        row = result.mappings().first()
        if row is None:
            return None
        return BudgetJobRecord(
            id=UUID(str(row["id"])),
            tenant_id=UUID(str(row["tenant_id"])),
            request_id=str(row["request_id"]),
            correlation_id=str(row["correlation_id"]),
            status=LifecycleStatus(str(row["status"])),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            ready_for_review_at=row["ready_for_review_at"],
            approved_at=row["approved_at"],
            rejected_at=row["rejected_at"],
            refine_requested_at=row["refine_requested_at"],
            rerun_requested_at=row["rerun_requested_at"],
            completed_at=row["completed_at"],
            failed_at=row["failed_at"],
            timeout_at=row["timeout_at"],
            cancelled_at=row["cancelled_at"],
            result=None,
            failure_code=row["failure_code"],
            failure_reason=row["failure_reason"],
        )

    async def _transition(
        self,
        session: AsyncSession,
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
        now = clock_module.utcnow()
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

        result = await session.execute(
            text(
                f"""
                UPDATE budget_jobs
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

        current = await self.get_by_id(session, tenant_id=tenant_id, job_id=job_id)
        if current.status == next_status:
            return
        raise ValueError(
            f"Illegal budget job transition {current.status.value} -> {next_status.value}"
        )

    @staticmethod
    def _to_record(row: Any) -> BudgetJobRecord:
        return BudgetJobRecord(
            id=UUID(str(row["id"])),
            tenant_id=UUID(str(row["tenant_id"])),
            request_id=str(row["request_id"]),
            correlation_id=str(row["correlation_id"]),
            status=LifecycleStatus(str(row["status"])),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            ready_for_review_at=row["ready_for_review_at"],
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
        )
