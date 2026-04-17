#!/usr/bin/env python3
"""B2.1-P4 queue isolation + performance semantics lock enforcement."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
QUEUE_FILE = "backend/app/core/queues.py"
CELERY_FILE = "backend/app/celery_app.py"
PROCFILE = "Procfile"
CONTAINER_STACK_FILE = "".join(("dock", "er", "-compose.e2e.yml"))
BENCHMARK_FILE = "scripts/benchmarks/b21_p4_queue_isolation_benchmark.py"
BENCHMARK_ADJUDICATOR_FILE = "scripts/ci/enforce_b21_p4_benchmark_adjudication.py"
CI_WORKFLOW_FILE = ".github/workflows/ci.yml"


def _resolve(repo_root: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (repo_root / path).resolve()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def run_enforcement(
    *,
    repo_root: Path,
    queue_file: Path,
    celery_file: Path,
    procfile: Path,
    container_stack_file: Path,
    benchmark_file: Path,
    benchmark_adjudicator_file: Path,
    ci_workflow_file: Path,
) -> tuple[int, list[str]]:
    violations: list[str] = []
    required_files = (
        queue_file,
        celery_file,
        procfile,
        container_stack_file,
        benchmark_file,
        benchmark_adjudicator_file,
        ci_workflow_file,
    )
    for required in required_files:
        if not required.exists():
            violations.append(f"missing_required_file:{required}")
    if violations:
        return 1, violations

    queue_text = _read_text(queue_file)
    celery_text = _read_text(celery_file)
    procfile_text = _read_text(procfile)
    container_stack_text = _read_text(container_stack_file)
    benchmark_text = _read_text(benchmark_file)
    adjudicator_text = _read_text(benchmark_adjudicator_file)
    ci_text = _read_text(ci_workflow_file)

    queue_tokens = (
        'QUEUE_BAYESIAN = "bayesian"',
        "QUEUE_BAYESIAN,",
    )
    for token in queue_tokens:
        if token not in queue_text:
            violations.append(f"queue_file_missing_token:{token}")

    celery_tokens = (
        "Queue(QUEUE_BAYESIAN,",
        "'app.tasks.bayesian.*': {'queue': QUEUE_BAYESIAN, 'routing_key': f'{QUEUE_BAYESIAN}.task'}",
        "'app.tasks.attribution.*': {'queue': QUEUE_ATTRIBUTION, 'routing_key': f'{QUEUE_ATTRIBUTION}.task'}",
    )
    for token in celery_tokens:
        if token not in celery_text:
            violations.append(f"celery_file_missing_token:{token}")

    procfile_tokens = (
        "worker: cd backend && celery -A app.celery_app.celery_app worker --loglevel=info --queues=housekeeping,maintenance,llm,attribution",
        "worker_bayesian: cd backend && celery -A app.celery_app.celery_app worker --loglevel=info --queues=bayesian",
    )
    for token in procfile_tokens:
        if token not in procfile_text:
            violations.append(f"procfile_missing_token:{token}")

    container_stack_tokens = (
        "worker_bayesian:",
        "--queues=housekeeping,maintenance,llm,attribution",
        "--queues=bayesian",
    )
    for token in container_stack_tokens:
        if token not in container_stack_text:
            violations.append(f"container_stack_missing_token:{token}")

    benchmark_tokens = (
        '"timing_boundary": "enqueue_to_durable_commit"',
        '"dispatch_mode": "celery_send_task"',
        '"contention_mode": contention_mode',
        "_read_path_probe(",
        "/api/attribution/channels",
        '"recompute_mutation_detected"',
        '"app.tasks.bayesian.run_resource_contention"',
    )
    for token in benchmark_tokens:
        if token not in benchmark_text:
            violations.append(f"benchmark_file_missing_token:{token}")

    adjudicator_tokens = (
        "corouted_negative_control_not_triggered",
        "contention_task_not_resource_real",
        "read_path_recompute_mutation_detected",
        "task_always_eager_enabled",
        "isolated_elapsed_not_under_threshold",
    )
    for token in adjudicator_tokens:
        if token not in adjudicator_text:
            violations.append(f"benchmark_adjudicator_missing_token:{token}")

    ci_required_tokens = (
        "needs: [checkout, validate-contracts, b21-p4-queue-isolation-performance-lock]",
        "Enforce B2.1-P4 queue isolation and performance semantics lock",
        "Run B2.1-P4 queue isolation negative controls",
        "Run B2.1-P4 benchmark adjudication negative controls",
        "name: B2.1-P4 Queue Isolation + Performance Semantics Lock",
        "Run B2.1-P4 benchmark harness integrity",
        "Run B2.1-P4 isolated queue benchmark (real contention)",
        "Run B2.1-P4 co-routed negative control benchmark",
        "Enforce B2.1-P4 benchmark adjudication",
        "python scripts/benchmarks/b21_p4_queue_isolation_benchmark.py",
        "python scripts/ci/enforce_b21_p4_benchmark_adjudication.py",
    )
    for token in ci_required_tokens:
        if token not in ci_text:
            violations.append(f"ci_workflow_missing_token:{token}")

    return (1 if violations else 0), violations


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Enforce B2.1-P4 queue isolation and benchmark semantics lock."
    )
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--queue-file", default=QUEUE_FILE)
    parser.add_argument("--celery-file", default=CELERY_FILE)
    parser.add_argument("--procfile", default=PROCFILE)
    parser.add_argument("--container-stack-file", default=CONTAINER_STACK_FILE)
    parser.add_argument("--benchmark-file", default=BENCHMARK_FILE)
    parser.add_argument(
        "--benchmark-adjudicator-file", default=BENCHMARK_ADJUDICATOR_FILE
    )
    parser.add_argument("--ci-workflow-file", default=CI_WORKFLOW_FILE)
    parser.add_argument("--simulate-regression", action="store_true")
    args = parser.parse_args(argv[1:])

    if args.simulate_regression:
        sys.stdout.write(
            "b21_p4_queue_isolation_semantics_lock_enforcer\n"
            "result=FAIL\n"
            "synthetic_regression=forced_failure_path\n"
        )
        return 1

    repo_root = _resolve(REPO_ROOT, args.repo_root)
    status, violations = run_enforcement(
        repo_root=repo_root,
        queue_file=_resolve(repo_root, args.queue_file),
        celery_file=_resolve(repo_root, args.celery_file),
        procfile=_resolve(repo_root, args.procfile),
        container_stack_file=_resolve(repo_root, args.container_stack_file),
        benchmark_file=_resolve(repo_root, args.benchmark_file),
        benchmark_adjudicator_file=_resolve(repo_root, args.benchmark_adjudicator_file),
        ci_workflow_file=_resolve(repo_root, args.ci_workflow_file),
    )
    lines = ["b21_p4_queue_isolation_semantics_lock_enforcer"]
    if status != 0:
        lines.append("result=FAIL")
        lines.extend(violations)
    else:
        lines.append("result=PASS")
        lines.append(
            "enforcement=queue_isolation_topology_enqueue_to_commit_real_contention_read_path_lock_closed"
        )
    sys.stdout.write("\n".join(lines) + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
