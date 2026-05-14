"""Inspect canonical queue topology from the source of truth."""

from __future__ import annotations

import ast
from pathlib import Path

from common import emit


ROOT = Path(__file__).resolve().parents[2]
QUEUE_SOURCE = ROOT / "backend/app/core/queues.py"
CELERY_SOURCE = ROOT / "backend/app/celery_app.py"
TASK_SOURCE = ROOT / "backend/app/tasks/revenue_verification.py"


WORKLOADS = {
    "housekeeping": {
        "owner": "health, probes, governance and low-risk background work",
        "producer": "backend/app/celery_app.py task_routes app.tasks.housekeeping.*, app.tasks.health.*",
        "consumer": "worker --queues=housekeeping,...",
    },
    "maintenance": {
        "owner": "materialized views, privacy and maintenance sweeps",
        "producer": "backend/app/tasks/maintenance.py and backend/app/tasks/matviews.py",
        "consumer": "worker --queues=...,maintenance,...",
    },
    "llm": {
        "owner": "bounded explanation and investigation tasks only",
        "producer": "backend/app/tasks/llm.py",
        "consumer": "worker --queues=...,llm,...",
    },
    "attribution": {
        "owner": "deterministic attribution recomputation",
        "producer": "backend/app/tasks/attribution.py",
        "consumer": "worker --queues=...,attribution,...",
    },
    "bayesian": {
        "owner": "B2.4 readiness queue only; no M4 Bayesian feature work",
        "producer": "backend/app/tasks/bayesian.py",
        "consumer": "dedicated/opt-in bayesian worker when enabled",
    },
    "b23_match_engine": {
        "owner": "B2.3 revenue verification and match engine",
        "producer": "backend/app/api/webhooks.py natural dispatch and backend/app/tasks/revenue_verification.py",
        "consumer": "worker --queues=...,b23_match_engine",
    },
}


def _queue_names() -> list[str]:
    module = ast.parse(QUEUE_SOURCE.read_text(encoding="utf-8"))
    names: list[str] = []
    for node in module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id.startswith("QUEUE_")
                    and isinstance(node.value, ast.Constant)
                    and isinstance(node.value.value, str)
                ):
                    names.append(node.value.value)
    return sorted(names)


def main() -> None:
    queues = _queue_names()
    emit(
        {
            "status": "ok",
            "canonical_source": str(QUEUE_SOURCE.relative_to(ROOT)),
            "queues": [
                {
                    "queue": queue,
                    **WORKLOADS.get(queue, {"owner": "undocumented", "producer": "unknown", "consumer": "unknown"}),
                    "health_command": "make ops-worker-inspect",
                }
                for queue in queues
            ],
            "source_files": [
                str(CELERY_SOURCE.relative_to(ROOT)),
                str(TASK_SOURCE.relative_to(ROOT)),
            ],
        }
    )


if __name__ == "__main__":
    main()
