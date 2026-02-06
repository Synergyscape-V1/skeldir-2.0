"""
Celery worker task lifecycle logging (B0.5.6.6).

Non-negotiable intent:
- Prometheus metrics must remain bounded (no tenant_id labels).
- Tenant traceability must exist for forensics: tenant_id/correlation_id belong in worker logs.

This module emits *canonical* JSON lifecycle records via Celery signals:
status ∈ {"started", "success", "failure"} with a strict allowlist of fields.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from typing import Any, Mapping, Optional, Sequence

from app.observability.context import get_request_correlation_id, get_tenant_id
from app.observability.logging_config import RedactionFilter


LIFECYCLE_LOGGER_NAME = "app.worker.task_lifecycle"
CONTEXT_WARNING_LOGGER_NAME = "app.worker.task_lifecycle_context"

_ALLOWED_LIFECYCLE_KEYS: set[str] = {
    # Required
    "tenant_id",
    "correlation_id",
    "task_name",
    "queue_name",
    "status",
    "error_type",
    # Optional (closed set)
    "task_id",
    "duration_ms",
    "retry",
    "retries",
    "exc_message_trunc",
}

_MAX_EXC_MESSAGE_CHARS = 300


class _RawMessageFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return record.getMessage()


class _StdoutFDHandler(logging.Handler):
    """
    Write log records directly to FD 1 (stdout) to avoid Celery stdout redirection.

    Celery may wrap/redirect `sys.stdout` (e.g., LoggingProxy). Using `os.write(1, ...)`
    preserves a pure JSON line on stdout for forensic parsing.
    """

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            if not msg.endswith("\n"):
                msg += "\n"
            os.write(1, msg.encode("utf-8", errors="replace"))
        except Exception:
            self.handleError(record)


def configure_task_lifecycle_loggers(level: str = "INFO") -> None:
    """
    Configure dedicated raw-JSON loggers for lifecycle events.

    These loggers are isolated from Celery/root hijack and do not rely on
    LogRecord extra propagation (which Celery/formatters may drop).
    """
    _configure_raw_json_logger(LIFECYCLE_LOGGER_NAME, level=level)
    _configure_raw_json_logger(CONTEXT_WARNING_LOGGER_NAME, level=level)


def _configure_raw_json_logger(name: str, *, level: str) -> logging.Logger:
    resolved_level = getattr(logging, str(level).upper(), logging.INFO)
    logger = logging.getLogger(name)
    logger.setLevel(resolved_level)
    logger.propagate = False

    for handler in logger.handlers:
        if getattr(handler, "_skeldir_raw_json_handler", False):
            handler.setLevel(resolved_level)
            return logger

    handler = _StdoutFDHandler()
    handler.setLevel(resolved_level)
    handler.setFormatter(_RawMessageFormatter())
    handler.addFilter(RedactionFilter())
    setattr(handler, "_skeldir_raw_json_handler", True)
    logger.addHandler(handler)
    return logger


def task_lifecycle_started_at(task: Any) -> float:
    """
    Read the task start timestamp stored on the Celery request (if present).

    This is written at task_prerun.
    """
    request = getattr(task, "request", None)
    if request is None:
        return 0.0
    try:
        return float(getattr(request, "_skeldir_lifecycle_started_at", 0.0) or 0.0)
    except Exception:
        return 0.0


def set_task_lifecycle_started_at(task: Any) -> None:
    request = getattr(task, "request", None)
    if request is None:
        return
    try:
        setattr(request, "_skeldir_lifecycle_started_at", time.perf_counter())
    except Exception:
        return


def emit_lifecycle_event(
    *,
    status: str,
    task: Any,
    task_id: Optional[str],
    queue_name: str,
    call_kwargs: Optional[Mapping[str, Any]] = None,
    exception: Optional[BaseException] = None,
    retry: Optional[bool] = None,
    retries: Optional[int] = None,
) -> None:
    """
    Emit a canonical lifecycle JSON record.

    Context acquisition precedence (deterministic, required):
    1) contextvars: app.observability.context (tenant_id, request correlation_id)
    2) task call kwargs by known keys: tenant_id / correlation_id
    3) task.request fields (if present): tenant_id / correlation_id
    4) fallback: "unknown" + emit separate warning JSON record

    Forbidden: raw args/kwargs/payloads/tokens/headers and unbounded stack traces.
    """
    tenant_id, correlation_id, missing_fields = _extract_context(
        task=task, call_kwargs=call_kwargs
    )

    payload: dict[str, Any] = {
        "tenant_id": tenant_id,
        "correlation_id": correlation_id,
        "task_name": str(getattr(task, "name", None) or "unknown"),
        "queue_name": str(queue_name or "unknown"),
        "status": str(status),
        "error_type": None,
    }

    if task_id:
        payload["task_id"] = str(task_id)

    if status in {"success", "failure"}:
        started_at = task_lifecycle_started_at(task)
        if started_at:
            duration_ms = int(max(0.0, (time.perf_counter() - started_at) * 1000.0))
            payload["duration_ms"] = duration_ms

    if status == "failure":
        payload["error_type"] = str(exception.__class__.__name__ if exception else "unknown")
        exc_message = str(exception) if exception else ""
        if exc_message:
            payload["exc_message_trunc"] = exc_message[:_MAX_EXC_MESSAGE_CHARS]
        if retry is not None:
            payload["retry"] = bool(retry)
        if retries is not None:
            payload["retries"] = int(retries)

    _enforce_allowlist(payload)
    logging.getLogger(LIFECYCLE_LOGGER_NAME).info(json.dumps(payload, ensure_ascii=False))

    if missing_fields:
        warning = {
            "event_type": "celery_task_context_missing",
            "task_name": payload["task_name"],
            "task_id": payload.get("task_id"),
            "missing_fields": list(missing_fields),
            "tenant_id": tenant_id,
            "correlation_id": correlation_id,
        }
        logging.getLogger(CONTEXT_WARNING_LOGGER_NAME).warning(json.dumps(warning, ensure_ascii=False))


def _extract_context(*, task: Any, call_kwargs: Optional[Mapping[str, Any]]) -> tuple[str, str, Sequence[str]]:
    missing: list[str] = []

    # (1) Context store
    tenant_id: Optional[str] = get_tenant_id()
    correlation_id: Optional[str] = get_request_correlation_id()

    # (2) kwargs by known key
    if not tenant_id and call_kwargs:
        candidate = call_kwargs.get("tenant_id")
        if candidate:
            tenant_id = str(candidate)
    if not correlation_id and call_kwargs:
        candidate = call_kwargs.get("correlation_id")
        if candidate:
            correlation_id = str(candidate)

    # (3) task.request fields
    request = getattr(task, "request", None)
    if request is not None:
        # Prefer explicit request fields when present (custom request attributes),
        # but also allow extracting known keys from request.kwargs without logging them.
        req_kwargs = getattr(request, "kwargs", None)
        if isinstance(req_kwargs, Mapping):
            if not tenant_id:
                candidate = req_kwargs.get("tenant_id")
                if candidate:
                    tenant_id = str(candidate)
            if not correlation_id:
                candidate = req_kwargs.get("correlation_id")
                if candidate:
                    correlation_id = str(candidate)
        if not tenant_id:
            candidate = getattr(request, "tenant_id", None)
            if candidate:
                tenant_id = str(candidate)
        if not correlation_id:
            candidate = getattr(request, "correlation_id", None)
            if candidate:
                correlation_id = str(candidate)

    # (4) fallback
    if not tenant_id:
        tenant_id = "unknown"
        missing.append("tenant_id")
    if not correlation_id:
        correlation_id = "unknown"
        missing.append("correlation_id")

    return tenant_id, correlation_id, missing


def _enforce_allowlist(payload: Mapping[str, Any]) -> None:
    """
    Enforce strict key allowlist without risking worker/task failure.

    If an unexpected key appears, drop it and emit a separate structured warning.
    """
    unexpected = set(payload.keys()) - _ALLOWED_LIFECYCLE_KEYS
    if not unexpected:
        return

    # Mutate in-place when possible (dict payloads).
    if isinstance(payload, dict):
        for key in unexpected:
            payload.pop(key, None)

    warning = {
        "event_type": "celery_task_lifecycle_schema_violation",
        "unexpected_keys": sorted(unexpected),
    }
    logging.getLogger(CONTEXT_WARNING_LOGGER_NAME).error(json.dumps(warning, ensure_ascii=False))
