"""
R6 Worker Resource Governance - Context Gathering Harness.

Generates SHA-anchored runtime artifacts and minimal probes for worker
governance controls (timeouts, retries, prefetch).
"""
from __future__ import annotations

import json
import os
import platform
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from fnmatch import fnmatch
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4
from urllib.parse import urlsplit

from celery import __version__ as celery_version
from celery.result import AsyncResult

# PYTHONPATH=backend
from app.celery_app import celery_app  # noqa: E402


WORKER_LOG_ENV = "R6_WORKER_LOG_PATH"


@dataclass(frozen=True)
class R6Context:
    sha: str
    timestamp_utc: str
    run_url: str
    output_dir: Path
    worker_log_path: Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _git_rev_parse_head() -> str:
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.STDOUT)
            .decode("utf-8", errors="replace")
            .strip()
        )
    except Exception:
        return "UNKNOWN"


def _git_status_porcelain() -> str:
    try:
        return (
            subprocess.check_output(["git", "status", "--porcelain"], stderr=subprocess.STDOUT)
            .decode("utf-8", errors="replace")
            .strip()
        )
    except Exception:
        return "UNKNOWN"


def _dsn_scheme_and_hash(dsn: str) -> dict[str, str]:
    if not dsn:
        return {"scheme": "", "sha256": ""}
    parsed = urlsplit(dsn)
    return {"scheme": parsed.scheme, "sha256": sha256(dsn.encode("utf-8")).hexdigest()}


def _write_text(path: Path, content: str, *, sha: str, timestamp: str) -> None:
    header = f"R6_SHA={sha}\nR6_TIMESTAMP_UTC={timestamp}\n"
    path.write_text(header + content, encoding="utf-8")


def _write_json(path: Path, payload: Any, *, sha: str, timestamp: str) -> None:
    if isinstance(payload, dict):
        payload = {"R6_SHA": sha, "R6_TIMESTAMP_UTC": timestamp, **payload}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _run_command(command: list[str]) -> str:
    res = subprocess.run(command, capture_output=True, text=True, check=False)
    return (res.stdout or "") + (res.stderr or "")


def _celery_cli(base_args: list[str]) -> str:
    command = ["celery", "-A", "app.celery_app.celery_app"] + base_args
    return _run_command(command)


def _ensure_output_dir(base_dir: Path, sha: str) -> Path:
    out = base_dir / sha
    out.mkdir(parents=True, exist_ok=True)
    return out


def _parse_active_queues_from_log(log_text: str) -> list[str]:
    queues: set[str] = set()
    for line in log_text.splitlines():
        if "queues:" in line.lower():
            match = re.search(r"queues:\s*(.*)", line, re.IGNORECASE)
            if match:
                tail = match.group(1)
                for token in re.split(r"[,\s]+", tail):
                    token = token.strip("[]")
                    if token:
                        queues.add(token)
    return sorted(queues)


def _resolve_task_route(task_name: str, routes: dict) -> dict[str, str]:
    for pattern, route in routes.items():
        if fnmatch(task_name, pattern):
            if isinstance(route, dict):
                return {
                    "queue": route.get("queue") or "",
                    "routing_key": route.get("routing_key") or "",
                }
            return {"queue": "", "routing_key": ""}
    return {"queue": "", "routing_key": ""}


def _task_governance_matrix() -> list[dict[str, Any]]:
    conf = celery_app.conf
    routes = conf.task_routes or {}
    rows: list[dict[str, Any]] = []
    for task_name, task in celery_app.tasks.items():
        if task_name.startswith("celery.") or task_name.startswith("kombu."):
            task_kind = "system"
        else:
            task_kind = "app"

        options = getattr(task, "options", {}) or {}
        route = _resolve_task_route(task_name, routes)
        queue = options.get("queue") or route["queue"] or conf.task_default_queue
        routing_key = options.get("routing_key") or route["routing_key"] or conf.task_default_routing_key

        max_retries = getattr(task, "max_retries", None)
        retry_backoff = getattr(task, "retry_backoff", None)
        retry_jitter = getattr(task, "retry_jitter", None)
        default_retry_delay = getattr(task, "default_retry_delay", None)
        autoretry_for = getattr(task, "autoretry_for", None)

        time_limit = getattr(task, "time_limit", None) or getattr(conf, "task_time_limit", None)
        soft_time_limit = getattr(task, "soft_time_limit", None) or getattr(
            conf, "task_soft_time_limit", None
        )

        acks_late = getattr(task, "acks_late", None)
        if acks_late is None:
            acks_late = bool(getattr(conf, "task_acks_late", False))
            acks_source = "global"
        else:
            acks_source = "task"

        reject_on_worker_lost = getattr(task, "reject_on_worker_lost", None)
        if reject_on_worker_lost is None:
            reject_on_worker_lost = bool(getattr(conf, "task_reject_on_worker_lost", False))
            reject_source = "global"
        else:
            reject_source = "task"

        retry_source = "missing"
        if max_retries is not None:
            retry_source = "task"
        elif autoretry_for:
            retry_source = "autoretry"

        rows.append(
            {
                "task_name": task_name,
                "task_kind": task_kind,
                "queue": queue,
                "routing_key": routing_key,
                "max_retries": max_retries,
                "retry_backoff": retry_backoff,
                "retry_jitter": retry_jitter,
                "default_retry_delay": default_retry_delay,
                "autoretry_for": [str(x) for x in (autoretry_for or [])],
                "retry_policy_source": retry_source,
                "time_limit": time_limit,
                "soft_time_limit": soft_time_limit,
                "acks_late": acks_late,
                "acks_source": acks_source,
                "reject_on_worker_lost": reject_on_worker_lost,
                "reject_source": reject_source,
                "acks_on_failure_or_timeout": bool(
                    getattr(conf, "task_acks_on_failure_or_timeout", False)
                ),
            }
        )
    return rows


def _render_task_matrix_md(rows: list[dict[str, Any]]) -> str:
    header = [
        "task_name",
        "task_kind",
        "queue",
        "routing_key",
        "max_retries",
        "retry_backoff",
        "retry_jitter",
        "default_retry_delay",
        "autoretry_for",
        "retry_policy_source",
        "time_limit",
        "soft_time_limit",
        "acks_late",
        "acks_source",
        "reject_on_worker_lost",
        "reject_source",
        "acks_on_failure_or_timeout",
    ]
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join(["---"] * len(header)) + " |"]
    for row in rows:
        line = []
        for col in header:
            val = row.get(col, "")
            if val is None:
                val = "MISSING"
            line.append(str(val))
        lines.append("| " + " | ".join(line) + " |")
    return "\n".join(lines)


def _build_gap_report(
    snapshot: dict[str, Any],
    matrix_rows: list[dict[str, Any]],
    active_queues: list[str],
) -> str:
    conf = snapshot.get("conf", {})
    missing_retries = [r["task_name"] for r in matrix_rows if r["max_retries"] is None]
    missing_timeouts = [
        r["task_name"] for r in matrix_rows if r["time_limit"] is None or r["soft_time_limit"] is None
    ]
    lines = [
        "# R6 Governance Gap Report",
        "",
        f"- R6_SHA: {snapshot.get('sha')}",
        f"- R6_TIMESTAMP_UTC: {snapshot.get('timestamp_utc')}",
        "",
        "## Required Control Set",
        "",
        f"- task_time_limit: {conf.get('task_time_limit')} (evidence: R6_CELERY_INSPECT_CONF.json)",
        f"- task_soft_time_limit: {conf.get('task_soft_time_limit')} (evidence: R6_CELERY_INSPECT_CONF.json)",
        f"- task_acks_late: {conf.get('task_acks_late')} (evidence: R6_CELERY_INSPECT_CONF.json)",
        f"- task_reject_on_worker_lost: {conf.get('task_reject_on_worker_lost')} (evidence: R6_CELERY_INSPECT_CONF.json)",
        f"- task_acks_on_failure_or_timeout: {conf.get('task_acks_on_failure_or_timeout')} (evidence: R6_CELERY_INSPECT_CONF.json)",
        f"- worker_prefetch_multiplier: {conf.get('worker_prefetch_multiplier')} (evidence: R6_CELERY_INSPECT_CONF.json)",
        f"- worker_max_tasks_per_child: {conf.get('worker_max_tasks_per_child')} (evidence: R6_CELERY_INSPECT_CONF.json)",
        f"- worker_max_memory_per_child: {conf.get('worker_max_memory_per_child')} (evidence: R6_CELERY_INSPECT_CONF.json)",
        "",
        "## Gaps",
        "",
        f"- tasks_missing_retry_caps: {len(missing_retries)}",
        f"- tasks_missing_timeouts: {len(missing_timeouts)}",
        f"- active_queues_observed: {', '.join(active_queues) if active_queues else 'UNKNOWN'}",
    ]
    if missing_retries:
        lines.append(f"- retry_cap_missing_tasks: {', '.join(missing_retries)}")
    if missing_timeouts:
        lines.append(f"- timeout_missing_tasks: {', '.join(missing_timeouts)}")
    return "\n".join(lines) + "\n"


def _wait_for_worker_snapshot(timeout_s: int = 30) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            result = celery_app.send_task(
                "app.tasks.r6_resource_governance.runtime_snapshot",
                kwargs={},
                queue="housekeeping",
            )
            return result.get(timeout=10)
        except Exception:
            time.sleep(1)
    raise RuntimeError("Worker runtime snapshot did not return within timeout")


def _probe_timeout(ctx: R6Context) -> dict[str, Any]:
    run_id = f"timeout-{uuid4()}"
    result = celery_app.send_task(
        "app.tasks.r6_resource_governance.timeout_probe",
        kwargs={"run_id": run_id},
        queue="maintenance",
    )
    error = None
    try:
        result.get(timeout=15)
    except Exception as exc:  # noqa: BLE001
        error = f"{exc.__class__.__name__}:{exc}"

    log_text = (
        ctx.worker_log_path.read_text(encoding="utf-8", errors="replace")
        if ctx.worker_log_path.exists()
        else ""
    )
    soft_hit = "r6_timeout_soft_limit_exceeded" in log_text
    hard_hit = "Hard time limit" in log_text or "TimeLimitExceeded" in log_text
    payload = {
        "run_id": run_id,
        "soft_limit_observed": soft_hit,
        "hard_limit_observed": hard_hit,
        "result_error": error,
    }
    _write_json(
        ctx.output_dir / "R6_PROBE_TIMEOUT.json",
        payload,
        sha=ctx.sha,
        timestamp=ctx.timestamp_utc,
    )
    return payload


def _probe_retry(ctx: R6Context) -> dict[str, Any]:
    run_id = f"retry-{uuid4()}"
    result = celery_app.send_task(
        "app.tasks.r6_resource_governance.retry_probe",
        kwargs={"run_id": run_id},
        queue="housekeeping",
    )
    error = None
    try:
        result.get(timeout=20)
    except Exception as exc:  # noqa: BLE001
        error = f"{exc.__class__.__name__}:{exc}"

    log_text = (
        ctx.worker_log_path.read_text(encoding="utf-8", errors="replace")
        if ctx.worker_log_path.exists()
        else ""
    )
    attempt_lines = [
        line
        for line in log_text.splitlines()
        if "r6_retry_attempt" in line and run_id in line
    ]
    payload = {
        "run_id": run_id,
        "attempt_lines": attempt_lines,
        "attempt_count": len(attempt_lines),
        "result_error": error,
    }
    _write_json(
        ctx.output_dir / "R6_PROBE_RETRY.json",
        payload,
        sha=ctx.sha,
        timestamp=ctx.timestamp_utc,
    )
    return payload


def _probe_prefetch(ctx: R6Context) -> dict[str, Any]:
    run_id = f"prefetch-{uuid4()}"
    long_ids = [
        celery_app.send_task(
            "app.tasks.r6_resource_governance.prefetch_long_task",
            kwargs={"run_id": run_id, "index": i, "sleep_s": 2.0},
            queue="maintenance",
        ).id
        for i in range(4)
    ]
    short_ids = [
        celery_app.send_task(
            "app.tasks.r6_resource_governance.prefetch_short_task",
            kwargs={"run_id": run_id, "index": i},
            queue="housekeeping",
        ).id
        for i in range(4)
    ]

    for tid in long_ids + short_ids:
        AsyncResult(tid).get(timeout=30)

    log_text = (
        ctx.worker_log_path.read_text(encoding="utf-8", errors="replace")
        if ctx.worker_log_path.exists()
        else ""
    )
    short_starts = [
        line for line in log_text.splitlines() if "r6_prefetch_short_start" in line and run_id in line
    ]
    payload = {
        "run_id": run_id,
        "short_start_log_lines": short_starts,
        "short_start_count": len(short_starts),
        "long_task_count": len(long_ids),
    }
    _write_json(
        ctx.output_dir / "R6_PROBE_PREFETCH.json",
        payload,
        sha=ctx.sha,
        timestamp=ctx.timestamp_utc,
    )
    return payload


def main() -> int:
    run_url = os.getenv("R6_RUN_URL", "UNKNOWN")
    sha = os.getenv("R6_SHA", _git_rev_parse_head())
    timestamp = _utc_now()
    output_root = Path("docs/validation/runtime/R6_context_gathering")
    output_dir = _ensure_output_dir(output_root, sha)

    worker_log_path = Path(os.getenv(WORKER_LOG_ENV, "r6_worker.log"))
    ctx = R6Context(
        sha=sha,
        timestamp_utc=timestamp,
        run_url=run_url,
        output_dir=output_dir,
        worker_log_path=worker_log_path,
    )

    env_snapshot = {
        "R6_SHA": sha,
        "R6_TIMESTAMP_UTC": timestamp,
        "git_status_porcelain": _git_status_porcelain(),
        "run_url": run_url,
        "os": {"platform": platform.platform(), "machine": platform.machine()},
        "python": {"version": sys.version.split()[0], "full": sys.version},
        "celery": {"version": celery_version},
        "docker_version": _run_command(["docker", "--version"]).strip(),
        "postgres_image": os.getenv("R6_POSTGRES_IMAGE", "unknown"),
    }
    _write_json(output_dir / "R6_ENV_SNAPSHOT.json", env_snapshot, sha=sha, timestamp=timestamp)

    _write_text(
        output_dir / "R6_CELERY_REPORT.log",
        _celery_cli(["report"]),
        sha=sha,
        timestamp=timestamp,
    )
    _write_text(
        output_dir / "R6_CELERY_INSPECT_CONF.log",
        _celery_cli(["inspect", "conf"]),
        sha=sha,
        timestamp=timestamp,
    )
    _write_text(
        output_dir / "R6_CELERY_INSPECT_STATS.log",
        _celery_cli(["inspect", "stats"]),
        sha=sha,
        timestamp=timestamp,
    )
    _write_text(
        output_dir / "R6_ACTIVE_QUEUES.log",
        _celery_cli(["inspect", "active_queues"]),
        sha=sha,
        timestamp=timestamp,
    )
    _write_text(
        output_dir / "R6_TASK_REGISTRY.log",
        _celery_cli(["inspect", "registered"]),
        sha=sha,
        timestamp=timestamp,
    )

    snapshot = _wait_for_worker_snapshot()
    snapshot["sha"] = sha
    snapshot["timestamp_utc"] = timestamp
    snapshot["run_url"] = run_url
    _write_json(output_dir / "R6_CELERY_INSPECT_CONF.json", snapshot, sha=sha, timestamp=timestamp)

    inspector = celery_app.control.inspect(timeout=5)
    stats = inspector.stats() or {}
    active = inspector.active_queues() or {}
    registered = inspector.registered() or {}

    _write_json(output_dir / "R6_CELERY_INSPECT_STATS.json", stats, sha=sha, timestamp=timestamp)
    _write_json(output_dir / "R6_ACTIVE_QUEUES.json", active, sha=sha, timestamp=timestamp)
    registry_payload = registered
    if not registry_payload:
        registry_payload = {
            "source": "app_registry_fallback",
            "tasks": sorted(celery_app.tasks.keys()),
        }
    _write_json(output_dir / "R6_TASK_REGISTRY.json", registry_payload, sha=sha, timestamp=timestamp)

    matrix_rows = _task_governance_matrix()
    _write_text(
        output_dir / "R6_TASK_GOVERNANCE_MATRIX.md",
        _render_task_matrix_md(matrix_rows),
        sha=sha,
        timestamp=timestamp,
    )

    worker_stats = {}
    if stats:
        _, worker_stats = next(iter(stats.items()))
    concurrency_snapshot = {
        "worker_stats": worker_stats,
        "runtime_snapshot": snapshot,
        "active_queues": active,
    }
    _write_json(
        output_dir / "R6_CONCURRENCY_SNAPSHOT.json",
        concurrency_snapshot,
        sha=sha,
        timestamp=timestamp,
    )

    conf = celery_app.conf
    topology = {
        "task_queues": [q.name for q in (conf.task_queues or [])],
        "task_routes": conf.task_routes or {},
        "task_default_queue": conf.task_default_queue,
        "task_default_exchange": conf.task_default_exchange,
        "task_default_routing_key": conf.task_default_routing_key,
        "active_queues": active,
    }
    _write_json(output_dir / "R6_QUEUE_TOPOLOGY.json", topology, sha=sha, timestamp=timestamp)

    active_from_logs = _parse_active_queues_from_log(
        ctx.worker_log_path.read_text(encoding="utf-8", errors="replace")
        if ctx.worker_log_path.exists()
        else ""
    )
    gap_report = _build_gap_report(snapshot, matrix_rows, active_from_logs)
    _write_text(output_dir / "R6_GAP_REPORT.md", gap_report, sha=sha, timestamp=timestamp)

    _probe_timeout(ctx)
    _probe_retry(ctx)
    _probe_prefetch(ctx)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
