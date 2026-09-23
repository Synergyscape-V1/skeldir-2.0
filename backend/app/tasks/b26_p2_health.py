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
SCHEDULER_TASK_NAME = "app.tasks.b26_p2_health.tick_b26_p2_scheduler_heartbeat"


async def evaluate_operational_health() -> dict:
    """Evaluate stale/quarantine/disposition counts across tenants.

    Returns counts only (no PII, no financial truth). Emits
    b26_p2_operational_health_evaluated on every tick (liveness: an
    evaluated-ok sweep is distinguishable from a silent evaluator) and
    b26_p2_operational_action_required at WARNING whenever nonzero
    actionable work exists (surfaces in deployed process output).

    Corrective IX separation: this evaluator runs on the relay queue
    under app_relay and ticks ONLY the evaluator heartbeat. It never
    ticks the scheduler heartbeat (public.b26_p2_record_scheduler_heartbeat
    refuses app_relay at the database plane); scheduler liveness is
    ticked separately by tick_scheduler_heartbeat() under the beat
    principal.
    """
    from app.db.session import engine as _engine  # noqa: PLC0415
    from app.db.session import get_session as _tenant_session  # noqa: PLC0415
    from app.finance_reconciliation import conduction_state as _conduction  # noqa: PLC0415

    try:
        threshold = _conduction.staleness_threshold_seconds()
    except ValueError:
        # Corrective VIII threshold reconciliation: the evaluator must not
        # silently continue on a divergent default while the API fails
        # closed (503). Log loudly and write NO heartbeat, so the
        # independent API observer reports evaluator absence instead of
        # consuming a forged-healthy default.
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
    scheduler_plane_absent_total = 0
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
                # Corrective X automatic consumption: the shipped evaluator
                # observes scheduler-plane absence under the same
                # threshold*4 law the API uses, so a silent scheduler
                # plane is operator-visible through this task's WARNING
                # even when nobody polls the endpoint. The relay
                # credential holds SELECT on the scheduler table; only
                # the beat principal can tick it.
                try:
                    sched_row = (
                        (
                            await session.execute(
                                text(
                                    "SELECT EXTRACT(EPOCH FROM (now() - last_tick)) AS age"
                                    " FROM public.b26_p2_scheduler_heartbeat"
                                    " WHERE tenant_id = :tenant"
                                ),
                                {"tenant": str(tenant)},
                            )
                        )
                        .mappings()
                        .one_or_none()
                    )
                    if sched_row is None or sched_row["age"] is None:
                        scheduler_plane_absent_total += 1
                    elif float(sched_row["age"]) > float(int(threshold) * 4):
                        scheduler_plane_absent_total += 1
                except Exception:
                    logger.exception(
                        "b26_p2_scheduler_plane_observation_failed",
                        extra={"tenant_id": str(tenant)},
                    )
                    scheduler_plane_absent_total += 1
                # Heartbeat for monitor-of-monitor (P2-CA7-06, VIII-hardened):
                # the ONLY writer is the SECURITY DEFINER
                # b26_p2_record_evaluator_heartbeat(), which recomputes the
                # operational counts itself. Invoking it IS the governed
                # evaluation: no credential can manufacture healthy evidence
                # without observing (direct heartbeat writes are revoked
                # from the relay credential at the database plane).
                try:
                    await session.execute(
                        text(
                            "SELECT public.b26_p2_record_evaluator_heartbeat"
                            "(:thr) AS outcome"
                        ),
                        {"thr": int(threshold)},
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
        stale_total > 0
        or quarantine_total > 0
        or pending_actionable_total > 0
        or scheduler_plane_absent_total > 0
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
            "scheduler_plane_absent_total": scheduler_plane_absent_total,
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
                "scheduler_plane_absent_total": scheduler_plane_absent_total,
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
        "scheduler_plane_absent_total": scheduler_plane_absent_total,
    }


@celery_app.task(
    bind=True,
    name=EVALUATOR_TASK_NAME,
    routing_key=f"{QUEUE_B26_P2_RELAY}.task",
)
def evaluate_b26_p2_operational_health_task(self) -> dict:
    """Deployed evaluator process: beat-scheduled operational signal."""
    return run_in_worker_loop(evaluate_operational_health())


async def tick_scheduler_heartbeat() -> dict:
    """Tick the scheduler-plane heartbeat across tenants (beat principal only).

    Corrective X execution: the beat scheduler executes this inline on
    its schedule entry (HealingBeatScheduler intercepts the
    ``b26-p2-scheduler-heartbeat`` entry), so the scheduled path has a
    shipped consumer -- the beat process itself, which already holds
    the app_beat credential. No queue consumer is required and none is
    assumed. The Celery task wrapper below remains for manual/compat
    invocation under the beat DSN.

    Corrective X honesty: the ticked rows prove recent authorized
    scheduler-plane activity, never orchestrator-attested process
    liveness. The beating instance identity is recorded for operator
    correlation (see app.beat_instance_id).

    The database function is SECURITY DEFINER and refuses every
    session_user except app_beat/migration_owner/postgres, so invoking
    it here under any other credential (notably app_relay) fails
    closed and is counted as failed, never as healthy evidence.

    Execution requirement: run this under the beat DSN
    (DATABASE_URL=$B26_P2_BEAT_DATABASE_URL, session_user app_beat).

    Returns counts only (no PII, no financial truth).
    """
    from app.db.session import engine as _engine  # noqa: PLC0415
    from app.db.session import get_session as _tenant_session  # noqa: PLC0415

    async with _engine.connect() as conn:
        tenant_rows = (
            (await conn.execute(text("SELECT id FROM public.tenants ORDER BY id")))
            .mappings()
            .all()
        )
    tenants = [str(r["id"]) for r in tenant_rows]
    ticked = 0
    failed = 0
    for tenant in tenants:
        try:
            async with _tenant_session(tenant_id=tenant) as session:
                await session.execute(
                    text(
                        "SELECT public.b26_p2_record_scheduler_heartbeat()"
                        " AS outcome"
                    )
                )
            ticked += 1
        except Exception:
            logger.exception(
                "b26_p2_scheduler_heartbeat_write_failed",
                extra={"tenant_id": str(tenant)},
            )
            failed += 1
    logger.info(
        "b26_p2_scheduler_heartbeat_ticked",
        extra={
            "tenants_scanned": len(tenants),
            "ticked": ticked,
            "failed": failed,
        },
    )
    return {
        "status": "ok" if failed == 0 else "tick_failed",
        "tenants_scanned": len(tenants),
        "ticked": ticked,
        "failed": failed,
    }


@celery_app.task(
    bind=True,
    name=SCHEDULER_TASK_NAME,
)
def tick_b26_p2_scheduler_heartbeat_task(self) -> dict:
    """Deployed scheduler-liveness ticker: beat-scheduled, beat-principal only.

    Beat schedules; an app_beat-principal consumer executes. Must NOT be
    routed to the relay queue (app_relay is refused at the DB plane by
    design, proving evaluator/scheduler separation).
    """
    return run_in_worker_loop(tick_scheduler_heartbeat())


__all__ = (
    "EVALUATOR_TASK_NAME",
    "SCHEDULER_TASK_NAME",
    "evaluate_b26_p2_operational_health_task",
    "evaluate_operational_health",
    "tick_b26_p2_scheduler_heartbeat_task",
    "tick_scheduler_heartbeat",
)
