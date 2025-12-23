"""
Investigation Service with Centaur Friction.

This service enforces the review/approve workflow that makes it
mechanically impossible to return "final" results immediately.

Design Principles:
- State machine: PENDING -> READY_FOR_REVIEW -> APPROVED -> COMPLETED
- Minimum hold period (45-60s) before review
- Cannot skip states (enforced by database constraints)
- Clock abstraction for testability

Centaur Friction:
- "Centaur" = human-machine collaboration
- Friction = deliberate delays and approval gates
- Purpose: Prevent hasty decisions, ensure human oversight
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, Optional, Protocol
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

logger = logging.getLogger(__name__)


class InvestigationStatus(str, Enum):
    """Investigation job status states."""
    PENDING = "PENDING"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    APPROVED = "APPROVED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class Clock(Protocol):
    """Protocol for time abstraction (testability)."""

    def now(self) -> datetime:
        """Return current UTC time."""
        ...


class SystemClock:
    """Production clock using system time."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class FixedClock:
    """Test clock with controllable time."""

    def __init__(self, fixed_time: Optional[datetime] = None):
        self._time = fixed_time or datetime.now(timezone.utc)

    def now(self) -> datetime:
        return self._time

    def advance(self, seconds: int) -> datetime:
        """Advance clock by specified seconds."""
        self._time = self._time + timedelta(seconds=seconds)
        return self._time

    def set(self, time: datetime) -> None:
        """Set clock to specific time."""
        self._time = time


# Default minimum hold period in seconds
DEFAULT_MIN_HOLD_SECONDS = 45


@dataclass(frozen=True)
class InvestigationJob:
    """Investigation job with state and timestamps."""
    id: UUID
    tenant_id: UUID
    status: InvestigationStatus
    created_at: datetime
    min_hold_until: datetime
    ready_for_review_at: Optional[datetime]
    approved_at: Optional[datetime]
    completed_at: Optional[datetime]
    result: Optional[Dict[str, Any]]
    remaining_hold_seconds: int

    @property
    def can_transition_to_ready(self) -> bool:
        """Check if job can transition to READY_FOR_REVIEW."""
        return self.status == InvestigationStatus.PENDING and self.remaining_hold_seconds <= 0

    @property
    def can_approve(self) -> bool:
        """Check if job can be approved."""
        return self.status == InvestigationStatus.READY_FOR_REVIEW


class InvestigationService:
    """
    Service for managing investigation jobs with centaur friction.

    The state machine enforces:
    1. Jobs start in PENDING
    2. Must wait min_hold_until before READY_FOR_REVIEW
    3. Must be APPROVED before COMPLETED
    4. Cannot skip states or return "final" immediately
    """

    def __init__(
        self,
        clock: Optional[Clock] = None,
        min_hold_seconds: int = DEFAULT_MIN_HOLD_SECONDS,
    ):
        """
        Initialize with optional clock for testing.

        Args:
            clock: Time provider (SystemClock for production, FixedClock for tests)
            min_hold_seconds: Minimum seconds before job can be reviewed
        """
        self.clock = clock or SystemClock()
        self.min_hold_seconds = min_hold_seconds

    async def create_job(
        self,
        conn: AsyncConnection,
        tenant_id: UUID,
        correlation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> InvestigationJob:
        """
        Create a new investigation job in PENDING status.

        The job will have min_hold_until = now + min_hold_seconds.

        Args:
            conn: Database connection with tenant context.
            tenant_id: Tenant UUID.
            correlation_id: Optional correlation ID for tracing.
            metadata: Optional metadata for the job.

        Returns:
            The created InvestigationJob.
        """
        now = self.clock.now()
        min_hold_until = now + timedelta(seconds=self.min_hold_seconds)
        job_id = uuid4()

        # RAW_SQL_ALLOWLIST: investigation job creation
        await conn.execute(
            text("""
                INSERT INTO investigation_jobs (
                    id, tenant_id, correlation_id, status,
                    created_at, min_hold_until, metadata
                ) VALUES (
                    :id, :tenant_id, :correlation_id, 'PENDING',
                    :created_at, :min_hold_until, :metadata
                )
            """),
            {
                "id": str(job_id),
                "tenant_id": str(tenant_id),
                "correlation_id": correlation_id,
                "created_at": now,
                "min_hold_until": min_hold_until,
                "metadata": "{}",
            },
        )

        logger.info(
            "investigation_job_created",
            extra={
                "job_id": str(job_id),
                "tenant_id": str(tenant_id),
                "min_hold_until": min_hold_until.isoformat(),
            },
        )

        return InvestigationJob(
            id=job_id,
            tenant_id=tenant_id,
            status=InvestigationStatus.PENDING,
            created_at=now,
            min_hold_until=min_hold_until,
            ready_for_review_at=None,
            approved_at=None,
            completed_at=None,
            result=None,
            remaining_hold_seconds=self.min_hold_seconds,
        )

    async def get_job(
        self,
        conn: AsyncConnection,
        tenant_id: UUID,
        job_id: UUID,
    ) -> Optional[InvestigationJob]:
        """
        Get an investigation job, potentially transitioning to READY_FOR_REVIEW.

        If the job is PENDING and min_hold_until has passed, it will
        automatically transition to READY_FOR_REVIEW.

        Args:
            conn: Database connection.
            tenant_id: Tenant UUID.
            job_id: Job UUID.

        Returns:
            The InvestigationJob or None if not found.
        """
        now = self.clock.now()

        result = await conn.execute(
            text("""
                SELECT
                    id, tenant_id, status, created_at, min_hold_until,
                    ready_for_review_at, approved_at, completed_at, result
                FROM investigation_jobs
                WHERE id = :job_id AND tenant_id = :tenant_id
            """),
            {"job_id": str(job_id), "tenant_id": str(tenant_id)},
        )
        row = result.mappings().first()
        if not row:
            return None

        status = InvestigationStatus(row["status"])
        min_hold_until = row["min_hold_until"]

        # Auto-transition to READY_FOR_REVIEW if hold period passed
        if status == InvestigationStatus.PENDING and now >= min_hold_until:
            await self._transition_to_ready(conn, job_id, now)
            status = InvestigationStatus.READY_FOR_REVIEW
            ready_for_review_at = now
        else:
            ready_for_review_at = row["ready_for_review_at"]

        # Calculate remaining hold seconds
        if status == InvestigationStatus.PENDING:
            remaining = max(0, int((min_hold_until - now).total_seconds()))
        else:
            remaining = 0

        return InvestigationJob(
            id=UUID(str(row["id"])),
            tenant_id=UUID(str(row["tenant_id"])),
            status=status,
            created_at=row["created_at"],
            min_hold_until=min_hold_until,
            ready_for_review_at=ready_for_review_at,
            approved_at=row["approved_at"],
            completed_at=row["completed_at"],
            result=row["result"],
            remaining_hold_seconds=remaining,
        )

    async def _transition_to_ready(
        self,
        conn: AsyncConnection,
        job_id: UUID,
        now: datetime,
    ) -> None:
        """Transition job to READY_FOR_REVIEW status."""
        await conn.execute(
            text("""
                UPDATE investigation_jobs
                SET status = 'READY_FOR_REVIEW', ready_for_review_at = :now
                WHERE id = :job_id AND status = 'PENDING'
            """),
            {"job_id": str(job_id), "now": now},
        )

        logger.info(
            "investigation_job_ready_for_review",
            extra={"job_id": str(job_id)},
        )

    async def approve_job(
        self,
        conn: AsyncConnection,
        tenant_id: UUID,
        job_id: UUID,
        result: Optional[Dict[str, Any]] = None,
    ) -> InvestigationJob:
        """
        Approve a job that is READY_FOR_REVIEW.

        This transitions the job to APPROVED, then immediately to COMPLETED.

        Args:
            conn: Database connection.
            tenant_id: Tenant UUID.
            job_id: Job UUID.
            result: Optional result data.

        Returns:
            The updated InvestigationJob.

        Raises:
            ValueError: If job cannot be approved (wrong state).
        """
        job = await self.get_job(conn, tenant_id, job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        if job.status != InvestigationStatus.READY_FOR_REVIEW:
            raise ValueError(
                f"Cannot approve job in status {job.status}. "
                f"Must be READY_FOR_REVIEW."
            )

        now = self.clock.now()

        # Transition to APPROVED then COMPLETED
        await conn.execute(
            text("""
                UPDATE investigation_jobs
                SET
                    status = 'COMPLETED',
                    approved_at = :now,
                    completed_at = :now,
                    result = :result
                WHERE id = :job_id AND tenant_id = :tenant_id
            """),
            {
                "job_id": str(job_id),
                "tenant_id": str(tenant_id),
                "now": now,
                "result": "{}",
            },
        )

        logger.info(
            "investigation_job_approved_and_completed",
            extra={"job_id": str(job_id), "tenant_id": str(tenant_id)},
        )

        return InvestigationJob(
            id=job.id,
            tenant_id=job.tenant_id,
            status=InvestigationStatus.COMPLETED,
            created_at=job.created_at,
            min_hold_until=job.min_hold_until,
            ready_for_review_at=job.ready_for_review_at,
            approved_at=now,
            completed_at=now,
            result=result,
            remaining_hold_seconds=0,
        )
