"""Celery boot-time topology gate for Bayesian workers."""

from __future__ import annotations

import logging
import os

from celery import signals

from app.bayesian.db_boot_probe import (
    BayesianWorkerBootTopologyProbeError,
    run_bayesian_worker_boot_topology_probe,
)

logger = logging.getLogger(__name__)


class BayesianWorkerBootTopologyProofMissing(RuntimeError):
    """Raised when a Bayesian task starts without process-local topology proof."""


_bayesian_boot_topology_probe_passed = False
_bayesian_boot_topology_probe_pid: int | None = None
_bayesian_boot_topology_probe_signal_registered = False


def bayesian_worker_boot_topology_probe_has_passed() -> bool:
    """Return whether this OS process has completed the boot topology proof."""

    return (
        _bayesian_boot_topology_probe_passed
        and _bayesian_boot_topology_probe_pid == os.getpid()
    )


def assert_bayesian_worker_boot_topology_proven() -> None:
    """Fail closed when a Bayesian task starts without process-local proof."""

    if bayesian_worker_boot_topology_probe_has_passed():
        return
    raise BayesianWorkerBootTopologyProofMissing(
        "bayesian_worker_boot_topology_probe_required"
    )


def _run_bayesian_worker_boot_topology_probe_if_needed() -> None:
    """Fatal pre-consumption gate for processes with Bayesian tasks registered."""

    global _bayesian_boot_topology_probe_passed
    global _bayesian_boot_topology_probe_pid
    if bayesian_worker_boot_topology_probe_has_passed():
        return

    logger.info(
        "bayesian_worker_boot_topology_probe_started",
        extra={
            "event_type": "bayesian.worker_boot_topology_probe",
            "worker_pid": os.getpid(),
        },
    )
    try:
        result = run_bayesian_worker_boot_topology_probe()
    except (BayesianWorkerBootTopologyProbeError, RuntimeError) as exc:
        logger.critical(
            "bayesian_worker_boot_topology_probe_failed",
            extra={
                "event_type": "bayesian.worker_boot_topology_probe",
                "worker_pid": os.getpid(),
                "error": exc.__class__.__name__,
            },
        )
        raise SystemExit("bayesian_worker_boot_topology_probe_failed") from exc

    _bayesian_boot_topology_probe_passed = True
    _bayesian_boot_topology_probe_pid = os.getpid()
    logger.info(
        "bayesian_worker_boot_topology_probe_passed",
        extra={
            "event_type": "bayesian.worker_boot_topology_probe",
            "worker_pid": os.getpid(),
            "old_pid": result.old_pid,
            "new_pid": result.new_pid,
            "elapsed_seconds": result.elapsed_seconds,
        },
    )


def _on_bayesian_worker_init(**kwargs) -> None:
    _run_bayesian_worker_boot_topology_probe_if_needed()


def _on_bayesian_worker_process_init(**kwargs) -> None:
    _run_bayesian_worker_boot_topology_probe_if_needed()


def ensure_bayesian_worker_boot_probe_signal_registered() -> None:
    """Register the Bayesian boot probe on worker parent and child lifecycles."""

    global _bayesian_boot_topology_probe_signal_registered
    if _bayesian_boot_topology_probe_signal_registered:
        return
    signals.worker_init.connect(_on_bayesian_worker_init, weak=False)
    signals.worker_process_init.connect(_on_bayesian_worker_process_init, weak=False)
    _bayesian_boot_topology_probe_signal_registered = True
