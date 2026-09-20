"""B2.6-P2 Corrective VI beat-scheduled operational health evaluator.

This is the shipping production consumer of the non-conduction /
quarantine signal (H-VI-D01): a beat-scheduled task that evaluates the
governed disposition law on every tick and emits an explicit operator
fact. It closes the "endpoint exists but nobody consumes it" class:

* the conduction health endpoint answers queries (queryable);
* the relay sweep observes per sweep (transport-coupled);
* THIS evaluator runs on the production beat cadence whether or not any
  operator polls anything (scheduled consumer).

It performs no deterministic financial work, reads no financial truth,
and writes no execution authority: per-tenant SELECTs of operational
counts only. It executes on the relay queue under the relay principal
(beat only schedules; the relay worker consumes), so it needs no new
database authority beyond the relay's governed operational reads.
"""

from __future__ import annotations

import logging

from sqlalchemy import text

from app.celery_app import celery_app
from app.core.queues import QUEUE_B26_P2_RELAY
from app.tasks.context import run_in_worker_loop

logger = logging.getLogger(__name__)

EVALUATOR_TASK_NAME = "app.tasks.b26_p2_health.evaluate_b26_p2_operational_health"


async def evaluate_operational_health() -> dict:
    """Evaluate stale/quarantine/disposition counts across tenants.

    Returns counts only (no PII, no financial truth). Emits
    b26_p2_operational_health_evaluated on every tick (liveness: an
    evaluated-ok sweep is distinguishable from a silent evaluator) and
    b26_p2_operational_action_required at WARNING whenever nonzero
    actionable work exists (surfaces in deployed process output).
    """
    from app.db.session import engine as _engine  # noqa: PLC0415
    from app.db.session import get_session as _tenant_session  # noqa: PLC0415
    from app.finance_reconciliation import conduction_state as _conduction  # noqa: PLC0415

    try:
        threshold = _conduction.staleness_threshold_seconds()
    except ValueError:
        logger.error(
            "b26_p2_operational_health_threshold_invalid",
            extra={"evaluator": EVALUATOR_TASK_NAME},
        )
        return {
            "status": "threshold_invalid",
            "stale_unconducted": 0,
            "quarantine_total": 0,
        }
    async with _engine.connect() as conn:
        tenant_rows = (
            (await conn.execute(text("SELECT id FROM public.tenants ORDER BY id")))
            .mappings()
            .all()
        )
    tenants = [str(r["id"]) for r in tenant_rows]
    stale_total = 0
    oldest_stale_age: float | None = None
    quarantine_total = 0
    oldest_quarantine_age: float | None = None
    pending_total = 0
    pending_actionable_total = 0
    terminal_total = 0
    try:
        for tenant in tenants:
            async with _tenant_session(tenant_id=tenant) as session:
                stale_rows = await _conduction.staleness_snapshot(
                    session, threshold_seconds=threshold
                )
            stale_total += len(stale_rows)
            for stale in stale_rows:
                oldest_stale_age = (
                    stale.age_seconds
                    if oldest_stale_age is None
                    else max(oldest_stale_age, stale.age_seconds)
                )
            async with _tenant_session(tenant_id=tenant) as session:
                quarantine_rows = await _conduction.quarantine_snapshot(session)
            quarantine_total += len(quarantine_rows)
            for row in quarantine_rows:
                age = float(row.get("age_seconds") or 0)
                oldest_quarantine_age = (
                    age
                    if oldest_quarantine_age is None
                    else max(oldest_quarantine_age, age)
                )
            async with _tenant_session(tenant_id=tenant) as session:
                pending_row = (
                    (
                        await session.execute(
                            text(
                                "SELECT count(*) AS n"
                                " FROM public.b23_match_task_dispatches AS d"
                                " WHERE d.delivery_state = 'pending_publish'"
                            )
                        )
                    )
                    .mappings()
                    .one()
                )
                pending_total += int(pending_row["n"] or 0)
                # Corrective VII finiteness (P2-CA7-05): expired pending is
                # actionable operator truth (dispatched_at is immutable, so
                # non-progress metadata cannot extend the horizon).
                pending_actionable_row = (
                    (
                        await session.execute(
                            text(
                                "SELECT count(*) AS n"
                                " FROM public.b23_match_task_dispatches AS d"
                                " WHERE d.delivery_state = 'pending_publish'"
                                " AND d.dispatched_at < now() - (:thr || ' seconds')::interval"
                            ),
                            {"thr": str(int(threshold))},
                        )
                    )
                    .mappings()
                    .one()
                )
                pending_actionable_total += int(pending_actionable_row["n"] or 0)
                # Heartbeat for monitor-of-monitor (P2-CA7-06): the API
                # health endpoint (independent failure domain) observes this
                # tick to detect evaluator absence.
                try:
                    await session.execute(
                        text(
                            "INSERT INTO public.b26_p2_evaluator_heartbeat"
                            " (tenant_id, last_tick, tick_count, updated_at)"
                            " VALUES (:tenant, now(), 1, now())"
                            " ON CONFLICT (tenant_id) DO UPDATE SET"
                            " last_tick = now(),"
                            " tick_count = public.b26_p2_evaluator_heartbeat.tick_count + 1,"
                            " updated_at = now()"
                        ),
                        {"tenant": str(tenant)},
                    )
                except Exception:
                    logger.exception(
                        "b26_p2_evaluator_heartbeat_write_failed",
                        extra={"tenant_id": str(tenant)},
                    )
                terminal_row = (
                    (
                        await session.execute(
                            text(
                                "SELECT count(*) AS n"
                                " FROM public.b23_match_task_dispatches AS d"
                                " JOIN public.b26_p2_execution_outbox AS o"
                                "   ON o.dispatch_task_id = d.task_id"
                                "  AND o.tenant_id = d.tenant_id"
                                "  AND o.webhook_ingress_identity_id = d.webhook_ingress_identity_id"
                                " WHERE d.delivery_state = 'published'"
                                " AND o.state = 'published'"
                                " AND EXISTS (SELECT 1 FROM public.worker_failed_jobs AS w"
                                " WHERE w.task_id = d.task_id)"
                                " AND EXISTS (SELECT 1 FROM public.celery_taskmeta AS m"
                                " WHERE m.task_id = d.task_id AND m.status = 'FAILURE')"
                            )
                        )
                    )
                    .mappings()
                    .one()
                )
                terminal_total += int(terminal_row["n"] or 0)
    except Exception:
        logger.exception(
            "b26_p2_operational_health_evaluation_failed",
            extra={"tenants_scanned": len(tenants)},
        )
        return {
            "status": "evaluation_failed",
            "stale_unconducted": stale_total,
            "quarantine_total": quarantine_total,
        }
    action_required = (
        stale_total > 0 or quarantine_total > 0 or pending_actionable_total > 0
    )
    logger.info(
        "b26_p2_operational_health_evaluated",
        extra={
            "tenants_scanned": len(tenants),
            "threshold_seconds": threshold,
            "stale_unconducted": stale_total,
            "oldest_stale_age_seconds": oldest_stale_age,
            "quarantine_total": quarantine_total,
            "oldest_quarantine_age_seconds": oldest_quarantine_age,
            "pending_total": pending_total,
            "pending_actionable_total": pending_actionable_total,
            "terminal_total": terminal_total,
            "action_required": action_required,
        },
    )
    if action_required:
        logger.warning(
            "b26_p2_operational_action_required",
            extra={
                "tenants_scanned": len(tenants),
                "stale_unconducted": stale_total,
                "oldest_stale_age_seconds": oldest_stale_age,
                "quarantine_total": quarantine_total,
                "oldest_quarantine_age_seconds": oldest_quarantine_age,
                "pending_total": pending_total,
                "pending_actionable_total": pending_actionable_total,
                "terminal_total": terminal_total,
                "evaluator": EVALUATOR_TASK_NAME,
            },
        )
    return {
        "status": "action_required" if action_required else "ok",
        "tenants_scanned": len(tenants),
        "threshold_seconds": threshold,
        "stale_unconducted": stale_total,
        "oldest_stale_age_seconds": oldest_stale_age,
        "quarantine_total": quarantine_total,
        "oldest_quarantine_age_seconds": oldest_quarantine_age,
        "pending_total": pending_total,
        "pending_actionable_total": pending_actionable_total,
        "terminal_total": terminal_total,
    }


@celery_app.task(
    bind=True,
    name=EVALUATOR_TASK_NAME,
    routing_key=f"{QUEUE_B26_P2_RELAY}.task",
)
def evaluate_b26_p2_operational_health_task(self) -> dict:
    """Deployed evaluator process: beat-scheduled operational signal."""
    return run_in_worker_loop(evaluate_operational_health())


__all__ = (
    "EVALUATOR_TASK_NAME",
    "evaluate_b26_p2_operational_health_task",
    "evaluate_operational_health",
)
