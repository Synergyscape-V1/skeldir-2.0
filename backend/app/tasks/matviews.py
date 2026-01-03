"""
Matview task wrapper layer (B0.5.4.3).

Delegates to the matview executor and emits logs/metrics/DLQ-triggering
exceptions without embedding refresh SQL in tasks.
"""
from __future__ import annotations

import logging
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from app.celery_app import celery_app
from app.matviews.executor import RefreshOutcome, RefreshResult, refresh_all_for_tenant, refresh_single
from app.observability import metrics
from app.tasks.context import tenant_task

logger = logging.getLogger(__name__)


class TaskOutcomeStrategy(str, Enum):
    SUCCESS = "SUCCESS"
    SILENT_SKIP = "SILENT_SKIP"
    RETRY = "RETRY"
    DEAD_LETTER = "DEAD_LETTER"


class UnmappedOutcomeError(RuntimeError):
    pass


class MatviewTaskFailure(RuntimeError):
    pass


_OUTCOME_STRATEGY_MAP: dict[RefreshOutcome, TaskOutcomeStrategy] = {
    RefreshOutcome.SUCCESS: TaskOutcomeStrategy.SUCCESS,
    RefreshOutcome.SKIPPED_LOCK_HELD: TaskOutcomeStrategy.SILENT_SKIP,
    RefreshOutcome.FAILED: TaskOutcomeStrategy.DEAD_LETTER,
}


def strategy_for_refresh_result(result: RefreshResult) -> TaskOutcomeStrategy:
    try:
        return _OUTCOME_STRATEGY_MAP[result.outcome]
    except KeyError as exc:
        raise UnmappedOutcomeError(f"Unmapped RefreshOutcome: {result.outcome}") from exc


def _record_metrics(result: RefreshResult, strategy: TaskOutcomeStrategy) -> None:
    duration_s = max(result.duration_ms, 0) / 1000.0
    outcome = result.outcome.value
    metrics.matview_refresh_total.labels(
        view_name=result.view_name,
        outcome=outcome,
        strategy=strategy.value,
    ).inc()
    metrics.matview_refresh_duration_seconds.labels(
        view_name=result.view_name,
        outcome=outcome,
    ).observe(duration_s)
    if result.outcome == RefreshOutcome.FAILED:
        metrics.matview_refresh_failures_total.labels(
            view_name=result.view_name,
            error_type=result.error_type or "unknown",
        ).inc()


def _log_start(
    *,
    task_id: str,
    view_name: str,
    tenant_id: UUID,
    correlation_id: str,
    schedule_class: Optional[str],
    force: bool,
) -> None:
    logger.info(
        "matview_refresh_task_start",
        extra={
            "task_id": task_id,
            "view_name": view_name,
            "tenant_id": str(tenant_id),
            "correlation_id": correlation_id,
            "schedule_class": schedule_class,
            "force": force,
        },
    )


def _log_result(
    *,
    task_id: str,
    result: RefreshResult,
    strategy: TaskOutcomeStrategy,
    schedule_class: Optional[str],
) -> None:
    payload = {
        "task_id": task_id,
        "view_name": result.view_name,
        "tenant_id": str(result.tenant_id) if result.tenant_id else None,
        "correlation_id": result.correlation_id,
        "schedule_class": schedule_class,
        "strategy": strategy.value,
        "result": result.to_log_dict(),
    }
    if result.outcome == RefreshOutcome.FAILED:
        logger.error("matview_refresh_task_failed", extra=payload)
    else:
        logger.info("matview_refresh_task_completed", extra=payload)


def _apply_strategy(
    *,
    task,
    result: RefreshResult,
    strategy: TaskOutcomeStrategy,
    retry_delay_s: int = 60,
) -> dict:
    if strategy == TaskOutcomeStrategy.RETRY:
        raise task.retry(exc=RuntimeError("matview_refresh_retry"), countdown=retry_delay_s)
    if strategy == TaskOutcomeStrategy.DEAD_LETTER:
        raise MatviewTaskFailure(
            f"matview refresh failed: view={result.view_name} outcome={result.outcome.value}"
        )
    return {
        "status": "skipped" if strategy == TaskOutcomeStrategy.SILENT_SKIP else "ok",
        "result": result.to_log_dict(),
        "strategy": strategy.value,
    }


@celery_app.task(
    bind=True,
    name="app.tasks.matviews.refresh_single",
    routing_key="maintenance.task",
    max_retries=3,
    default_retry_delay=60,
)
@tenant_task
def matview_refresh_single(
    self,
    *,
    tenant_id: UUID,
    view_name: str,
    correlation_id: Optional[str] = None,
    schedule_class: Optional[str] = None,
    force: bool = False,
) -> dict:
    correlation_id = correlation_id or str(uuid4())
    _log_start(
        task_id=self.request.id,
        view_name=view_name,
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        schedule_class=schedule_class,
        force=force,
    )
    result = refresh_single(view_name, tenant_id, correlation_id)
    strategy = strategy_for_refresh_result(result)
    _record_metrics(result, strategy)
    _log_result(
        task_id=self.request.id,
        result=result,
        strategy=strategy,
        schedule_class=schedule_class,
    )
    return _apply_strategy(task=self, result=result, strategy=strategy)


@celery_app.task(
    bind=True,
    name="app.tasks.matviews.refresh_all_for_tenant",
    routing_key="maintenance.task",
    max_retries=3,
    default_retry_delay=60,
)
@tenant_task
def matview_refresh_all_for_tenant(
    self,
    *,
    tenant_id: UUID,
    correlation_id: Optional[str] = None,
    schedule_class: Optional[str] = None,
) -> dict:
    correlation_id = correlation_id or str(uuid4())
    logger.info(
        "matview_refresh_all_task_start",
        extra={
            "task_id": self.request.id,
            "tenant_id": str(tenant_id),
            "correlation_id": correlation_id,
            "schedule_class": schedule_class,
        },
    )
    results = refresh_all_for_tenant(tenant_id, correlation_id)
    strategies: list[TaskOutcomeStrategy] = []
    for result in results:
        strategy = strategy_for_refresh_result(result)
        strategies.append(strategy)
        _record_metrics(result, strategy)
        _log_result(
            task_id=self.request.id,
            result=result,
            strategy=strategy,
            schedule_class=schedule_class,
        )

    if TaskOutcomeStrategy.DEAD_LETTER in strategies:
        overall = TaskOutcomeStrategy.DEAD_LETTER
    elif TaskOutcomeStrategy.RETRY in strategies:
        overall = TaskOutcomeStrategy.RETRY
    elif TaskOutcomeStrategy.SILENT_SKIP in strategies:
        overall = TaskOutcomeStrategy.SILENT_SKIP
    else:
        overall = TaskOutcomeStrategy.SUCCESS

    if overall in (TaskOutcomeStrategy.DEAD_LETTER, TaskOutcomeStrategy.RETRY):
        failed = next((r for r in results if r.outcome == RefreshOutcome.FAILED), results[0])
        return _apply_strategy(task=self, result=failed, strategy=overall)

    return {
        "status": "skipped" if overall == TaskOutcomeStrategy.SILENT_SKIP else "ok",
        "results": [r.to_log_dict() for r in results],
        "strategy": overall.value,
    }
