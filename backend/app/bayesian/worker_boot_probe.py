"""Celery boot-time topology gate for Bayesian workers."""

from __future__ import annotations

import logging
import os
import sys
from typing import Sequence

from celery import signals

from app.bayesian.db_boot_probe import (
    BayesianWorkerBootTopologyProbeError,
    run_bayesian_worker_boot_topology_probe,
)
from app.core.queues import QUEUE_BAYESIAN

logger = logging.getLogger(__name__)

_bayesian_boot_topology_probe_passed = False
_bayesian_boot_topology_probe_signal_registered = False
_BAYESIAN_TOPOLOGY_AUTHORITY_ENV = (
    "SKELDIR_BAYESIAN_DB_TOPOLOGY",
    "SKELDIR_BAYESIAN_DB_TOPOLOGY_ATTESTATION",
    "SKELDIR_BAYESIAN_DB_TOPOLOGY_SOURCE",
)


def _parse_celery_queue_arguments(argv: Sequence[str]) -> set[str] | None:
    """Return explicitly requested Celery queues, or None when all queues apply."""

    queues: set[str] = set()
    index = 0
    while index < len(argv):
        arg = str(argv[index])
        value: str | None = None
        if arg in {"-Q", "--queues"}:
            if index + 1 < len(argv):
                value = str(argv[index + 1])
                index += 1
        elif arg.startswith("--queues="):
            value = arg.split("=", 1)[1]
        elif arg.startswith("-Q") and len(arg) > 2:
            value = arg[2:]

        if value is not None:
            queues.update(item.strip() for item in value.split(",") if item.strip())
        index += 1
    return queues or None


def _worker_may_consume_bayesian_tasks(argv: Sequence[str] | None = None) -> bool:
    """Return whether this worker can consume Bayesian tasks before readiness."""

    if os.getenv("SKELDIR_BAYESIAN_BOOT_PROBE_REQUIRED", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return True
    explicit_queues = _parse_celery_queue_arguments(argv or sys.argv)
    if explicit_queues is None:
        return any(
            os.getenv(name, "").strip() for name in _BAYESIAN_TOPOLOGY_AUTHORITY_ENV
        )
    return QUEUE_BAYESIAN in explicit_queues


def _run_bayesian_worker_boot_topology_probe_if_needed(
    *,
    argv: Sequence[str] | None = None,
) -> None:
    """Fatal pre-consumption gate for workers that can reserve Bayesian work."""

    global _bayesian_boot_topology_probe_passed
    if _bayesian_boot_topology_probe_passed:
        return
    if not _worker_may_consume_bayesian_tasks(argv):
        return

    logger.info(
        "bayesian_worker_boot_topology_probe_started",
        extra={"event_type": "bayesian.worker_boot_topology_probe"},
    )
    try:
        result = run_bayesian_worker_boot_topology_probe()
    except (BayesianWorkerBootTopologyProbeError, RuntimeError) as exc:
        logger.critical(
            "bayesian_worker_boot_topology_probe_failed",
            extra={
                "event_type": "bayesian.worker_boot_topology_probe",
                "error": exc.__class__.__name__,
            },
        )
        raise SystemExit("bayesian_worker_boot_topology_probe_failed") from exc

    _bayesian_boot_topology_probe_passed = True
    logger.info(
        "bayesian_worker_boot_topology_probe_passed",
        extra={
            "event_type": "bayesian.worker_boot_topology_probe",
            "old_pid": result.old_pid,
            "new_pid": result.new_pid,
            "elapsed_seconds": result.elapsed_seconds,
        },
    )


def _on_bayesian_worker_init(**kwargs) -> None:
    _run_bayesian_worker_boot_topology_probe_if_needed()


def ensure_bayesian_worker_boot_probe_signal_registered() -> None:
    """Register the Bayesian boot probe on Celery worker_init exactly once."""

    global _bayesian_boot_topology_probe_signal_registered
    if _bayesian_boot_topology_probe_signal_registered:
        return
    signals.worker_init.connect(_on_bayesian_worker_init, weak=False)
    _bayesian_boot_topology_probe_signal_registered = True
