"""
Bayesian worker tasks with explicit bounded-compute contracts.

Phase 5 contract:
- Production defaults are explicit: soft=270s, hard=300s.
- Deterministic fallback is emitted on soft timeout before hard kill.
- A health probe task is provided to prove worker liveness after timeout events.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from uuid import UUID

from celery.exceptions import SoftTimeLimitExceeded

from app.celery_app import celery_app
from app.core.config import settings

logger = logging.getLogger(__name__)

# Static production contract. Runtime env may lower limits for non-vacuous CI probes.
PRODUCTION_BAYESIAN_SOFT_TIME_LIMIT_S = 270
PRODUCTION_BAYESIAN_TIME_LIMIT_S = 300

_TASK_SOFT_LIMIT_S = int(settings.BAYESIAN_TASK_SOFT_TIME_LIMIT_S)
_TASK_HARD_LIMIT_S = int(settings.BAYESIAN_TASK_TIME_LIMIT_S)

if _TASK_HARD_LIMIT_S <= _TASK_SOFT_LIMIT_S:
    raise RuntimeError("BAYESIAN_TASK_TIME_LIMIT_S must be greater than BAYESIAN_TASK_SOFT_TIME_LIMIT_S")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_probe_event(event: dict) -> None:
    path = os.getenv("BAYESIAN_PROBE_LOG_PATH")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")
    except Exception:
        logger.warning("bayesian_probe_log_write_failed", extra={"path": path})


def _as_uuid(raw: str | UUID) -> UUID:
    if isinstance(raw, UUID):
        return raw
    return UUID(str(raw))


@celery_app.task(
    bind=True,
    name="app.tasks.bayesian.run_mcmc_inference",
    routing_key="attribution.task",
    soft_time_limit=_TASK_SOFT_LIMIT_S,
    time_limit=_TASK_HARD_LIMIT_S,
    acks_late=True,
    max_retries=0,
)
def run_mcmc_inference(
    self,
    *,
    tenant_id: str,
    correlation_id: str,
    run_seconds: int = 900,
    continue_after_soft_timeout: bool = False,
) -> dict:
    """
    Simulate a long Bayesian/MCMC workload with deterministic timeout fallback behavior.
    """
    tenant = _as_uuid(tenant_id)
    correlation = _as_uuid(correlation_id)
    task_id = str(self.request.id)
    started_at = time.monotonic()

    logger.info(
        "bayesian_run_started",
        extra={
            "event_type": "bayesian.compute",
            "tenant_id": str(tenant),
            "correlation_id": str(correlation),
            "task_id": task_id,
            "run_seconds": int(run_seconds),
            "soft_time_limit_s": _TASK_SOFT_LIMIT_S,
            "time_limit_s": _TASK_HARD_LIMIT_S,
        },
    )
    _append_probe_event(
        {
            "event": "bayesian_run_started",
            "timestamp": _utc_now(),
            "task_id": task_id,
            "tenant_id": str(tenant),
            "correlation_id": str(correlation),
            "soft_time_limit_s": _TASK_SOFT_LIMIT_S,
            "time_limit_s": _TASK_HARD_LIMIT_S,
        }
    )

    try:
        deadline = time.monotonic() + max(1, int(run_seconds))
        while time.monotonic() < deadline:
            time.sleep(0.2)
        elapsed_ms = int((time.monotonic() - started_at) * 1000)
        return {
            "status": "completed",
            "task_id": task_id,
            "tenant_id": str(tenant),
            "correlation_id": str(correlation),
            "elapsed_ms": elapsed_ms,
            "fallback_triggered": False,
        }
    except SoftTimeLimitExceeded:
        elapsed_ms = int((time.monotonic() - started_at) * 1000)
        fallback_payload = {
            "status": "fallback",
            "reason": "bayesian_soft_time_limit_exceeded",
            "task_id": task_id,
            "tenant_id": str(tenant),
            "correlation_id": str(correlation),
            "elapsed_ms": elapsed_ms,
            "fallback_model": "deterministic_last_touch",
            "fallback_lookback_days": 30,
            "fallback_triggered": True,
        }
        logger.warning(
            "bayesian_soft_timeout_fallback",
            extra={
                "event_type": "bayesian.compute",
                "tenant_id": str(tenant),
                "correlation_id": str(correlation),
                "task_id": task_id,
                "fallback_model": "deterministic_last_touch",
            },
        )
        _append_probe_event(
            {
                "event": "bayesian_soft_timeout_fallback",
                "timestamp": _utc_now(),
                **fallback_payload,
            }
        )
        if continue_after_soft_timeout:
            # Keep consuming CPU slot until hard limit kills this worker process.
            while True:
                time.sleep(0.2)
        return fallback_payload


@celery_app.task(
    bind=True,
    name="app.tasks.bayesian.health_probe",
    routing_key="attribution.task",
    soft_time_limit=30,
    time_limit=60,
    acks_late=False,
    max_retries=0,
)
def health_probe(self, *, tenant_id: str, correlation_id: str) -> dict:
    tenant = _as_uuid(tenant_id)
    correlation = _as_uuid(correlation_id)
    payload = {
        "status": "ok",
        "task_id": str(self.request.id),
        "tenant_id": str(tenant),
        "correlation_id": str(correlation),
        "timestamp_utc": _utc_now(),
    }
    _append_probe_event({"event": "bayesian_health_probe_ok", **payload})
    return payload
