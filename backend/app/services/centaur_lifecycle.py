"""Canonical lifecycle grammar for B1.5 centaur authority services."""

from __future__ import annotations

from enum import Enum


class LifecycleStatus(str, Enum):
    """Unified lifecycle vocabulary for investigation and budget authority domains."""

    SUBMITTED = "submitted"
    VALIDATING = "validating"
    INVESTIGATING = "investigating"
    READY_FOR_REVIEW = "ready_for_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    REFINE_REQUESTED = "refine_requested"
    RERUN_REQUESTED = "rerun_requested"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


CANONICAL_LIFECYCLE_STATES: tuple[str, ...] = tuple(status.value for status in LifecycleStatus)

REVIEW_STATES: tuple[LifecycleStatus, ...] = (
    LifecycleStatus.READY_FOR_REVIEW,
    LifecycleStatus.APPROVED,
    LifecycleStatus.REJECTED,
    LifecycleStatus.REFINE_REQUESTED,
    LifecycleStatus.RERUN_REQUESTED,
)

TERMINAL_STATES: tuple[LifecycleStatus, ...] = (
    LifecycleStatus.COMPLETED,
    LifecycleStatus.FAILED,
    LifecycleStatus.TIMEOUT,
    LifecycleStatus.CANCELLED,
)

