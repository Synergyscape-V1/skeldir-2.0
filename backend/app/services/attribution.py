"""
Scheduling utilities for attribution recompute workflows.

B0.5.3.6 closes the ingestion → scheduling gap by providing a single entry point
for enqueueing recompute_window on the real Celery worker, with deterministic
window validation and correlation propagation.
"""
from datetime import datetime, timezone
from typing import Optional, Union
from uuid import UUID, uuid4

from celery.result import AsyncResult

from app.tasks.attribution import _normalize_timestamp, recompute_window

WindowBoundary = Union[str, datetime]


def _normalize_window_boundary(value: WindowBoundary) -> datetime:
    """
    Normalize window boundaries using the same semantics as the task path.

    Accepts ISO8601 strings or datetime objects and returns a timezone-aware UTC
    datetime suitable for window validation and serialization.
    """
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    return _normalize_timestamp(value)


def _isoformat_utc(dt: datetime) -> str:
    """Serialize a UTC datetime to ISO string with Z suffix for task payloads."""
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def schedule_recompute_window(
    tenant_id: UUID,
    window_start: WindowBoundary,
    window_end: WindowBoundary,
    correlation_id: Optional[str] = None,
    model_version: str = "1.0.0",
    fail: bool = False,
) -> AsyncResult:
    """
    Enqueue the attribution recompute task via the worker subprocess harness.

    Validates window boundaries with task-equivalent normalization, guarantees a
    correlation_id, and propagates that correlation into both task kwargs and
    the Celery message headers to keep DLQ correlation deterministic.
    """
    start_dt = _normalize_window_boundary(window_start)
    end_dt = _normalize_window_boundary(window_end)

    if start_dt >= end_dt:
        raise ValueError(f"window_start ({window_start}) must be < window_end ({window_end})")

    correlation_uuid = UUID(str(correlation_id)) if correlation_id else uuid4()
    start_payload = _isoformat_utc(start_dt)
    end_payload = _isoformat_utc(end_dt)

    return recompute_window.apply_async(
        kwargs={
            "tenant_id": tenant_id,
            "window_start": start_payload,
            "window_end": end_payload,
            "correlation_id": str(correlation_uuid),
            "model_version": model_version,
            "fail": fail,
        },
        correlation_id=str(correlation_uuid),
    )

