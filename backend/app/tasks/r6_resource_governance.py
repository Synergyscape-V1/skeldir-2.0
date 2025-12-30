"""
R6 worker resource governance probes and runtime diagnostics.

These tasks are instrumentation-only for context gathering.
"""
import json
import logging
import os
import time
from datetime import datetime, timezone
from hashlib import sha256
from urllib.parse import urlsplit

from celery.exceptions import SoftTimeLimitExceeded

from app.celery_app import celery_app

logger = logging.getLogger(__name__)


def _dsn_scheme_and_hash(dsn: str) -> dict[str, str]:
    if not dsn:
        return {"scheme": "", "sha256": ""}
    parsed = urlsplit(dsn)
    return {"scheme": parsed.scheme, "sha256": sha256(dsn.encode("utf-8")).hexdigest()}


def _sanitize_value(value):
    if isinstance(value, dict):
        return {k: _sanitize_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_sanitize_value(v) for v in value]
    return value


def _coerce_json_safe(value):
    try:
        json.dumps(value, allow_nan=False)
        return value
    except Exception:
        return str(value)


def _sanitize_conf(conf) -> dict:
    sanitized: dict = {}
    for key, value in dict(conf).items():
        key_lower = str(key).lower()
        if "password" in key_lower:
            sanitized[key] = "***"
            continue
        if (
            ("url" in key_lower or "broker" in key_lower or "backend" in key_lower)
            and isinstance(value, str)
        ):
            sanitized[key] = _dsn_scheme_and_hash(value)
            continue
        sanitized[key] = _coerce_json_safe(_sanitize_value(value))
    return sanitized


@celery_app.task(
    bind=True,
    name="app.tasks.r6_resource_governance.runtime_snapshot",
    acks_late=False,
    routing_key="housekeeping.task",
)
def runtime_snapshot(self) -> dict:
    """
    Return a sanitized runtime snapshot from inside the worker process.
    """
    conf = self.app.conf
    broker_dsn = str(getattr(conf, "broker_url", "") or "")
    backend_dsn = str(getattr(conf, "result_backend", "") or "")

    snapshot = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "worker_pid": os.getpid(),
        "hostname": getattr(self.request, "hostname", None),
        "conf": {
            "task_time_limit": getattr(conf, "task_time_limit", None),
            "task_soft_time_limit": getattr(conf, "task_soft_time_limit", None),
            "task_acks_late": bool(getattr(conf, "task_acks_late", False)),
            "task_reject_on_worker_lost": bool(getattr(conf, "task_reject_on_worker_lost", False)),
            "task_acks_on_failure_or_timeout": bool(
                getattr(conf, "task_acks_on_failure_or_timeout", False)
            ),
            "worker_prefetch_multiplier": int(
                getattr(conf, "worker_prefetch_multiplier", 0) or 0
            ),
            "worker_max_tasks_per_child": getattr(conf, "worker_max_tasks_per_child", None),
            "worker_max_memory_per_child": getattr(conf, "worker_max_memory_per_child", None),
        },
        "conf_full": _sanitize_conf(conf),
        "broker": _dsn_scheme_and_hash(broker_dsn),
        "backend": _dsn_scheme_and_hash(backend_dsn),
        "task_queues": [q.name for q in (conf.task_queues or [])],
        "task_default_queue": getattr(conf, "task_default_queue", None),
        "task_default_routing_key": getattr(conf, "task_default_routing_key", None),
        "task_default_exchange": getattr(conf, "task_default_exchange", None),
        "env": {
            "CELERYD_CONCURRENCY": os.getenv("CELERYD_CONCURRENCY"),
            "CELERYD_PREFETCH_MULTIPLIER": os.getenv("CELERYD_PREFETCH_MULTIPLIER"),
            "CELERYD_MAX_TASKS_PER_CHILD": os.getenv("CELERYD_MAX_TASKS_PER_CHILD"),
            "CELERYD_MAX_MEMORY_PER_CHILD": os.getenv("CELERYD_MAX_MEMORY_PER_CHILD"),
        },
    }
    logger.info("r6_runtime_snapshot", extra={"snapshot": snapshot})
    return snapshot


@celery_app.task(
    bind=True,
    name="app.tasks.r6_resource_governance.timeout_probe",
    soft_time_limit=2,
    time_limit=4,
    routing_key="maintenance.task",
)
def timeout_probe(self, run_id: str) -> None:
    """
    Exceeds soft+hard time limits to prove enforcement.
    """
    logger.info(
        f"r6_timeout_probe_start run_id={run_id} task_id={self.request.id}",
        extra={"run_id": run_id, "task_id": self.request.id},
    )
    try:
        while True:
            time.sleep(0.2)
    except SoftTimeLimitExceeded:
        logger.warning(
            f"r6_timeout_soft_limit_exceeded run_id={run_id} task_id={self.request.id}",
            extra={"run_id": run_id, "task_id": self.request.id},
        )
        while True:
            time.sleep(0.2)


@celery_app.task(
    bind=True,
    name="app.tasks.r6_resource_governance.retry_probe",
    max_retries=2,
    default_retry_delay=1,
    routing_key="housekeeping.task",
)
def retry_probe(self, run_id: str) -> None:
    """
    Always retries until max_retries is exceeded.
    """
    attempt = int(getattr(self.request, "retries", 0) or 0)
    logger.warning(
        f"r6_retry_attempt run_id={run_id} task_id={self.request.id} attempt={attempt}",
        extra={"run_id": run_id, "task_id": self.request.id, "attempt": attempt},
    )
    raise self.retry(exc=RuntimeError("r6 retry probe failure"), countdown=1)


@celery_app.task(
    bind=True,
    name="app.tasks.r6_resource_governance.prefetch_short_task",
    routing_key="housekeeping.task",
)
def prefetch_short_task(self, run_id: str, index: int) -> dict:
    started = datetime.now(timezone.utc).isoformat()
    logger.info(
        f"r6_prefetch_short_start run_id={run_id} task_id={self.request.id} index={index}",
        extra={"run_id": run_id, "task_id": self.request.id, "index": index, "started": started},
    )
    time.sleep(0.2)
    finished = datetime.now(timezone.utc).isoformat()
    logger.info(
        f"r6_prefetch_short_end run_id={run_id} task_id={self.request.id} index={index}",
        extra={"run_id": run_id, "task_id": self.request.id, "index": index, "finished": finished},
    )
    return {"started": started, "finished": finished}


@celery_app.task(
    bind=True,
    name="app.tasks.r6_resource_governance.prefetch_long_task",
    routing_key="maintenance.task",
)
def prefetch_long_task(self, run_id: str, index: int, sleep_s: float = 2.0) -> dict:
    started = datetime.now(timezone.utc).isoformat()
    logger.info(
        f"r6_prefetch_long_start run_id={run_id} task_id={self.request.id} index={index}",
        extra={"run_id": run_id, "task_id": self.request.id, "index": index, "started": started},
    )
    time.sleep(float(sleep_s))
    finished = datetime.now(timezone.utc).isoformat()
    logger.info(
        f"r6_prefetch_long_end run_id={run_id} task_id={self.request.id} index={index}",
        extra={"run_id": run_id, "task_id": self.request.id, "index": index, "finished": finished},
    )
    return {"started": started, "finished": finished}


@celery_app.task(
    bind=True,
    name="app.tasks.r6_resource_governance.pid_probe",
    routing_key="housekeeping.task",
)
def pid_probe(self, run_id: str, index: int) -> dict:
    pid = os.getpid()
    logger.info(
        f"r6_pid_probe run_id={run_id} task_id={self.request.id} index={index} pid={pid}",
        extra={"run_id": run_id, "task_id": self.request.id, "index": index, "pid": pid},
    )
    return {"pid": pid, "index": index}
