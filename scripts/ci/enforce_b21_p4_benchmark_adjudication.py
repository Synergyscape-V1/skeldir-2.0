#!/usr/bin/env python3
"""B2.1-P4 benchmark adjudication enforcer."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON payload must be an object: {path}")
    return payload


def _require(condition: bool, failures: list[str], message: str) -> None:
    if not condition:
        failures.append(message)


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _adjudicate_single(
    *,
    label: str,
    summary: dict[str, Any],
    expected_topology_mode: str,
    required_event_count: int,
    min_contention_db_queries: int,
    min_contention_iterations: int,
    threshold_seconds: float,
) -> tuple[list[str], float | None]:
    failures: list[str] = []

    _require(
        summary.get("schema_version") == "b21_p4_queue_isolation_benchmark.v1",
        failures,
        f"{label}_schema_version_mismatch",
    )
    _require(summary.get("mode") == "measure", failures, f"{label}_mode_not_measure")
    _require(
        summary.get("topology_mode") == expected_topology_mode,
        failures,
        f"{label}_topology_mode_mismatch",
    )
    authority_negative = summary.get("authority_negative_control")
    if label == "corouted" and isinstance(authority_negative, dict):
        _require(
            summary.get("contention_mode") == "real",
            failures,
            "corouted_contention_mode_not_real",
        )
        _require(
            _int(summary.get("event_count")) == required_event_count,
            failures,
            "corouted_event_count_mismatch",
        )
        _require(
            authority_negative.get("rejected") is True,
            failures,
            "corouted_shared_worker_not_rejected",
        )
        _require(
            authority_negative.get("reason")
            == "bayesian_worker_boot_topology_probe_failed",
            failures,
            "corouted_rejection_not_c6_authority_guard",
        )
        _require(
            authority_negative.get("worker_database_identity") == "app_user",
            failures,
            "corouted_rejection_identity_not_app_user",
        )
        return failures, None
    _require(
        summary.get("timing_boundary") == "enqueue_to_durable_commit",
        failures,
        f"{label}_timing_boundary_invalid",
    )
    _require(
        summary.get("dispatch_mode") == "celery_send_task",
        failures,
        f"{label}_dispatch_mode_not_celery_send_task",
    )
    _require(
        summary.get("task_always_eager") is False,
        failures,
        f"{label}_task_always_eager_enabled",
    )

    broker_url = str(summary.get("broker_url", ""))
    result_backend = str(summary.get("result_backend", ""))
    _require(
        broker_url.startswith("sqla+postgresql"),
        failures,
        f"{label}_broker_not_sqlalchemy_postgres",
    )
    _require(
        result_backend.startswith("db+postgresql"),
        failures,
        f"{label}_result_backend_not_db_postgres",
    )

    event_count = _int(summary.get("event_count"))
    _require(event_count is not None, failures, f"{label}_event_count_missing")
    if event_count is not None:
        _require(
            event_count == required_event_count,
            failures,
            f"{label}_event_count_mismatch:{event_count}!={required_event_count}",
        )

    deterministic = summary.get("deterministic", {})
    if not isinstance(deterministic, dict):
        failures.append(f"{label}_deterministic_payload_invalid")
        deterministic = {}

    elapsed = _float(deterministic.get("elapsed_seconds"))
    _require(elapsed is not None, failures, f"{label}_elapsed_seconds_missing")

    _require(
        deterministic.get("task_name") == "app.tasks.attribution.recompute_window",
        failures,
        f"{label}_deterministic_task_name_invalid",
    )
    _require(
        str(deterministic.get("job_status", "")).strip().lower() == "succeeded",
        failures,
        f"{label}_deterministic_job_status_not_succeeded",
    )
    allocation_count = _int(deterministic.get("allocation_count"))
    _require(
        allocation_count is not None, failures, f"{label}_allocation_count_missing"
    )
    if allocation_count is not None:
        _require(
            allocation_count > 0, failures, f"{label}_allocation_count_not_positive"
        )

    contention = summary.get("contention", {})
    if not isinstance(contention, dict):
        failures.append(f"{label}_contention_payload_invalid")
        contention = {}
    _require(
        summary.get("contention_mode") == "real",
        failures,
        f"{label}_contention_mode_not_real",
    )
    _require(
        contention.get("task_name") == "app.tasks.bayesian.run_resource_contention",
        failures,
        f"{label}_contention_task_not_resource_real",
    )
    _require(
        str(contention.get("error", "")).strip() == "",
        failures,
        f"{label}_contention_task_error_present",
    )
    contention_result = contention.get("result", {})
    if not isinstance(contention_result, dict):
        failures.append(f"{label}_contention_result_invalid")
        contention_result = {}
    _require(
        str(contention_result.get("status", "")).strip().lower() == "completed",
        failures,
        f"{label}_contention_status_not_completed",
    )
    db_queries = _int(contention_result.get("db_queries"))
    iterations = _int(contention_result.get("iterations"))
    _require(db_queries is not None, failures, f"{label}_contention_db_queries_missing")
    _require(iterations is not None, failures, f"{label}_contention_iterations_missing")
    if db_queries is not None:
        _require(
            db_queries >= min_contention_db_queries,
            failures,
            f"{label}_contention_db_queries_below_min:{db_queries}<{min_contention_db_queries}",
        )
    if iterations is not None:
        _require(
            iterations >= min_contention_iterations,
            failures,
            f"{label}_contention_iterations_below_min:{iterations}<{min_contention_iterations}",
        )

    read_path = summary.get("read_path", {})
    if not isinstance(read_path, dict):
        failures.append(f"{label}_read_path_payload_invalid")
        read_path = {}
    _require(
        _int(read_path.get("status_code")) == 200,
        failures,
        f"{label}_read_path_status_not_200",
    )
    _require(
        read_path.get("recompute_mutation_detected") is False,
        failures,
        f"{label}_read_path_recompute_mutation_detected",
    )
    _require(
        str(read_path.get("projection_recompute_job_id", ""))
        == str(deterministic.get("job_id", "")),
        failures,
        f"{label}_read_path_projection_job_mismatch",
    )

    if label == "isolated":
        if elapsed is not None:
            _require(
                elapsed < threshold_seconds,
                failures,
                f"isolated_elapsed_not_under_threshold:{elapsed:.4f}>={threshold_seconds:.4f}",
            )
    elif label == "corouted":
        if elapsed is not None:
            _require(
                elapsed >= threshold_seconds,
                failures,
                f"corouted_negative_control_not_triggered:{elapsed:.4f}<{threshold_seconds:.4f}",
            )

    return failures, elapsed


def _adjudicate(
    *,
    isolated_summary: dict[str, Any],
    corouted_summary: dict[str, Any],
    required_event_count: int,
    min_contention_db_queries: int,
    min_contention_iterations: int,
    threshold_seconds: float,
) -> tuple[int, list[str]]:
    failures: list[str] = []

    isolated_failures, isolated_elapsed = _adjudicate_single(
        label="isolated",
        summary=isolated_summary,
        expected_topology_mode="isolated",
        required_event_count=required_event_count,
        min_contention_db_queries=min_contention_db_queries,
        min_contention_iterations=min_contention_iterations,
        threshold_seconds=threshold_seconds,
    )
    failures.extend(isolated_failures)

    corouted_failures, corouted_elapsed = _adjudicate_single(
        label="corouted",
        summary=corouted_summary,
        expected_topology_mode="corouted_shared_worker",
        required_event_count=required_event_count,
        min_contention_db_queries=min_contention_db_queries,
        min_contention_iterations=min_contention_iterations,
        threshold_seconds=threshold_seconds,
    )
    failures.extend(corouted_failures)

    if isolated_elapsed is not None and corouted_elapsed is not None:
        _require(
            isolated_elapsed < corouted_elapsed,
            failures,
            f"isolation_advantage_absent:{isolated_elapsed:.4f}>={corouted_elapsed:.4f}",
        )

    return (1 if failures else 0), failures


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="B2.1-P4 queue isolation benchmark adjudication"
    )
    parser.add_argument("--isolated-file", required=True)
    parser.add_argument("--corouted-file", required=True)
    parser.add_argument("--required-event-count", type=int, default=10000)
    parser.add_argument("--min-contention-db-queries", type=int, default=20)
    parser.add_argument("--min-contention-iterations", type=int, default=2)
    parser.add_argument("--threshold-seconds", type=float, default=5.0)
    args = parser.parse_args(argv[1:])

    isolated_path = Path(args.isolated_file).resolve()
    corouted_path = Path(args.corouted_file).resolve()
    for required in (isolated_path, corouted_path):
        if not required.exists():
            sys.stdout.write(
                "b21_p4_benchmark_adjudication\n"
                "result=FAIL\n"
                f"missing_file:{required}\n"
            )
            return 1

    isolated_summary = _load_json(isolated_path)
    corouted_summary = _load_json(corouted_path)
    status, failures = _adjudicate(
        isolated_summary=isolated_summary,
        corouted_summary=corouted_summary,
        required_event_count=int(args.required_event_count),
        min_contention_db_queries=int(args.min_contention_db_queries),
        min_contention_iterations=int(args.min_contention_iterations),
        threshold_seconds=float(args.threshold_seconds),
    )
    lines = ["b21_p4_benchmark_adjudication"]
    if status != 0:
        lines.append("result=FAIL")
        lines.extend(failures)
    else:
        lines.append("result=PASS")
        lines.append(
            "adjudication=queue_isolation_real_contention_enqueue_to_commit_read_path_lock_closed"
        )
    sys.stdout.write("\n".join(lines) + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
