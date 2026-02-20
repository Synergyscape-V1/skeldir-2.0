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

from sqlalchemy.engine.url import make_url

from app.celery_app import celery_app
from app.matviews.executor import RefreshOutcome, RefreshResult, refresh_all_for_tenant, refresh_single
from app.core.secrets import get_database_url
from app.observability import metrics
from app.observability.context import set_request_correlation_id, set_tenant_id
from app.observability.metrics_policy import normalize_view_name

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


def _map_refresh_outcome_to_policy(outcome: RefreshOutcome) -> str:
    """Map RefreshOutcome enum to bounded policy outcome (B0.5.6.3)."""
    mapping = {
        RefreshOutcome.SUCCESS: "success",
        RefreshOutcome.SKIPPED_LOCK_HELD: "skipped",
        RefreshOutcome.FAILED: "failure",
    }
    return mapping.get(outcome, "failure")


def _record_metrics(result: RefreshResult, strategy: TaskOutcomeStrategy) -> None:
    """Record matview refresh metrics with bounded labels (B0.5.6.3)."""
    duration_s = max(result.duration_ms, 0) / 1000.0
    # B0.5.6.3: Normalize labels to bounded sets
    view_name = normalize_view_name(result.view_name)
    outcome = _map_refresh_outcome_to_policy(result.outcome)
    
    metrics.matview_refresh_total.labels(
        view_name=view_name,
        outcome=outcome,
    ).inc()
    metrics.matview_refresh_duration_seconds.labels(
        view_name=view_name,
        outcome=outcome,
    ).observe(duration_s)
    if result.outcome == RefreshOutcome.FAILED:
        metrics.matview_refresh_failures_total.labels(
            view_name=view_name,
            outcome=outcome,
        ).inc()


def _normalize_tenant_id(value: UUID | str) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


def _build_sync_dsn() -> str:
    url = make_url(get_database_url())
    query = dict(url.query)
    query.pop("channel_binding", None)
    url = url.set(query=query)
    if url.drivername.startswith("postgresql+"):
        url = url.set(drivername="postgresql")

    dsn_parts = ["postgresql://"]
    if url.username:
        dsn_parts.append(url.username)
        if url.password:
            dsn_parts.append(":")
            dsn_parts.append(url.password)
        dsn_parts.append("@")
    dsn_parts.append(url.host or "localhost")
    if url.port:
        dsn_parts.append(f":{url.port}")
    if url.database:
        dsn_parts.append(f"/{url.database}")
    return "".join(dsn_parts)


def _fetch_tenant_ids_sync() -> list[UUID]:
    import psycopg2
    dsn = _build_sync_dsn()
    conn = psycopg2.connect(dsn)
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM tenants ORDER BY id")
        rows = cur.fetchall()
        return [UUID(str(row[0])) for row in rows]
    finally:
        conn.close()


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


def _log_view_result(
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
        logger.error("matview_refresh_view_failed", extra=payload)
    else:
        logger.info("matview_refresh_view_completed", extra=payload)


def _log_task_summary(
    *,
    task_id: str,
    result: RefreshResult,
    strategy: TaskOutcomeStrategy,
    schedule_class: Optional[str],
    view_count: int,
) -> None:
    payload = {
        "task_id": task_id,
        "view_name": result.view_name,
        "tenant_id": str(result.tenant_id) if result.tenant_id else None,
        "correlation_id": result.correlation_id,
        "schedule_class": schedule_class,
        "strategy": strategy.value,
        "view_count": view_count,
        "result": result.to_log_dict(),
    }
    if strategy in (TaskOutcomeStrategy.DEAD_LETTER, TaskOutcomeStrategy.RETRY):
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
def matview_refresh_single(
    self,
    *,
    tenant_id: UUID,
    view_name: str,
    correlation_id: Optional[str] = None,
    schedule_class: Optional[str] = None,
    force: bool = False,
) -> dict:
    tenant_uuid = _normalize_tenant_id(tenant_id)
    correlation_id = correlation_id or str(uuid4())
    set_tenant_id(tenant_uuid)
    set_request_correlation_id(correlation_id)
    _log_start(
        task_id=self.request.id,
        view_name=view_name,
        tenant_id=tenant_uuid,
        correlation_id=correlation_id,
        schedule_class=schedule_class,
        force=force,
    )
    result = refresh_single(view_name, tenant_uuid, correlation_id)
    strategy = strategy_for_refresh_result(result)
    _record_metrics(result, strategy)
    _log_view_result(
        task_id=self.request.id,
        result=result,
        strategy=strategy,
        schedule_class=schedule_class,
    )
    _log_task_summary(
        task_id=self.request.id,
        result=result,
        strategy=strategy,
        schedule_class=schedule_class,
        view_count=1,
    )
    try:
        return _apply_strategy(task=self, result=result, strategy=strategy)
    finally:
        set_tenant_id(None)
        set_request_correlation_id(None)


@celery_app.task(
    bind=True,
    name="app.tasks.matviews.refresh_all_for_tenant",
    routing_key="maintenance.task",
    max_retries=3,
    default_retry_delay=60,
)
def matview_refresh_all_for_tenant(
    self,
    *,
    tenant_id: UUID,
    correlation_id: Optional[str] = None,
    schedule_class: Optional[str] = None,
) -> dict:
    tenant_uuid = _normalize_tenant_id(tenant_id)
    correlation_id = correlation_id or str(uuid4())
    set_tenant_id(tenant_uuid)
    set_request_correlation_id(correlation_id)
    logger.info(
        "matview_refresh_all_task_start",
        extra={
            "task_id": self.request.id,
            "tenant_id": str(tenant_uuid),
            "correlation_id": correlation_id,
            "schedule_class": schedule_class,
        },
    )
    results = refresh_all_for_tenant(tenant_uuid, correlation_id)
    strategies: list[TaskOutcomeStrategy] = []
    for result in results:
        strategy = strategy_for_refresh_result(result)
        strategies.append(strategy)
        _record_metrics(result, strategy)
        _log_view_result(
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

    failed = next((r for r in results if r.outcome == RefreshOutcome.FAILED), results[0])
    _log_task_summary(
        task_id=self.request.id,
        result=failed,
        strategy=overall,
        schedule_class=schedule_class,
        view_count=len(results),
    )
    if overall in (TaskOutcomeStrategy.DEAD_LETTER, TaskOutcomeStrategy.RETRY):
        try:
            return _apply_strategy(task=self, result=failed, strategy=overall)
        finally:
            set_tenant_id(None)
            set_request_correlation_id(None)

    try:
        return {
            "status": "skipped" if overall == TaskOutcomeStrategy.SILENT_SKIP else "ok",
            "results": [r.to_log_dict() for r in results],
            "strategy": overall.value,
        }
    finally:
        set_tenant_id(None)
        set_request_correlation_id(None)


@celery_app.task(
    bind=True,
    name="app.tasks.matviews.pulse_matviews_global",
    routing_key="maintenance.task",
    max_retries=3,
    default_retry_delay=60,
)
def pulse_matviews_global(
    self,
    correlation_id: Optional[str] = None,
    schedule_class: Optional[str] = None,
) -> dict:
    correlation_id = correlation_id or str(uuid4())
    set_request_correlation_id(correlation_id)
    try:
        logger.info(
            "matview_pulse_task_start",
            extra={
                "task_id": self.request.id,
                "correlation_id": correlation_id,
                "schedule_class": schedule_class,
            },
        )
        tenant_ids = _fetch_tenant_ids_sync()
        for tenant_id in tenant_ids:
            matview_refresh_all_for_tenant.delay(
                tenant_id=str(tenant_id),
                correlation_id=correlation_id,
                schedule_class=schedule_class,
            )
        logger.info(
            "matview_pulse_task_dispatched",
            extra={
                "task_id": self.request.id,
                "correlation_id": correlation_id,
                "tenant_count": len(tenant_ids),
                "schedule_class": schedule_class,
            },
        )
        return {"status": "ok", "tenant_count": len(tenant_ids), "correlation_id": correlation_id}
    finally:
        set_request_correlation_id(None)
