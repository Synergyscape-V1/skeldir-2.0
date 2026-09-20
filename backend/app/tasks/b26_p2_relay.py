"""B2.6-P2 Corrective III durable execution-intent relay.

The webhook atomically persists dispatch authority plus an outbox row in
one commit. This relay publishes pending intents to the broker with the
stable logical task identity and marks them published. It is the
recoverable-delivery boundary: broker outage, producer crash, or process
restart cannot permanently strand accepted evidence because pending rows
remain observable and are retried by provider retry, by immediate
re-drive, and by this sweeper.

Duplicate physical delivery is logically idempotent: publication reuses
the stable task_id bound at issuance, B2.3 verdict writes are idempotent
upserts, and P2 derivation recomputes deterministically over the pinned
snapshot.
"""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import text

from app.celery_app import celery_app
from app.core.queues import QUEUE_B23_MATCH_ENGINE
from app.tasks.context import run_in_worker_loop

logger = logging.getLogger(__name__)

RELAY_QUEUE = "b26_p2_relay"
RELAY_TASK_NAME = "app.tasks.b26_p2_relay.relay_b26_p2_pending_dispatches"
MAX_SWEEP_BATCH = 100


async def _publish_one(
    session_factory,
    *,
    tenant_id: str,
    dispatch_task_id: str,
    window_start_iso: str,
    window_end_iso: str,
    correlation_id: str,
) -> bool:
    """Publish one pending intent; return True when broker accepted."""
    from app.tasks.revenue_verification import (  # noqa: PLC0415
        execute_b23_batch_match_engine_task,
    )

    try:
        execute_b23_batch_match_engine_task.apply_async(
            args=[
                str(tenant_id),
                str(window_start_iso),
                str(window_end_iso),
                100,
                str(correlation_id),
            ],
            task_id=str(dispatch_task_id),
            queue=QUEUE_B23_MATCH_ENGINE,
            routing_key=f"{QUEUE_B23_MATCH_ENGINE}.task",
        )
        return True
    except Exception as exc:  # broker unavailable: stay pending, observable
        logger.warning(
            "b26_p2_relay_publish_failed",
            extra={
                "tenant_id": str(tenant_id),
                "task_id": str(dispatch_task_id),
                "error": str(exc)[:500],
            },
        )
        # Corrective IV: drop pooled broker state so the next sweep
        # rebuilds instead of reusing the poisoned producer session.
        from app.celery_app import reset_broker_pools_after_fault  # noqa: PLC0415

        reset_broker_pools_after_fault(reason="relay_publish")
        return False


async def publish_pending_outbox(*, limit: int = MAX_SWEEP_BATCH) -> dict:
    """Sweep pending outbox rows and publish them with stable identity.

    Runs under the producer principal (app_user). Each row is published
    with its issuance task_id; success marks both outbox and dispatch
    published atomically. Failure increments attempts and backs off.
    """
    from app.db.session import get_session  # noqa: PLC0415

    published = 0
    failed = 0
    # Sweep without tenant scoping first (server-owned relay): read pending
    # rows via a privileged session? The relay runs as app_user with no
    # single tenant GUC, so it iterates tenants present in the outbox.
    # To avoid GUC/RLS circularity, the sweep reads task identities via the
    # server-owned resolver path per row (no tenant trust).
    import uuid as _uuid

    _sweep_tenant = _uuid.uuid4()  # placeholder; per-row sessions below
    del _sweep_tenant
    # Implementation: per-tenant sweep using explicit GUC per row tenant.
    # First collect distinct tenants with pending rows using migration_owner?
    # The relay principal (app_user) cannot see all tenants without GUC, so
    # it enumerates tenants from the public.tenants table (no RLS) and then
    # sweeps each tenant scope.
    from app.db.session import engine as _engine  # noqa: PLC0415

    async with _engine.connect() as conn:
        tenant_rows = (
            (await conn.execute(text("SELECT id FROM public.tenants ORDER BY id")))
            .mappings()
            .all()
        )
    tenants = [str(r["id"]) for r in tenant_rows]
    divergent_total = 0
    stale_total = 0
    oldest_stale_age = 0
    quarantine_total = 0
    oldest_quarantine_age = 0
    pending_total = 0
    for tenant in tenants:
        async with get_session(tenant_id=tenant) as session:
            # Corrective V: the sweep joins on the full execution tuple
            # (task + tenant + ingress), not on task identity alone. The
            # database tuple FKs make a forked child unencodable; the
            # tuple join keeps the relay's own reads on the same single
            # execution authority even before the database refuses.
            # Corrective IV: the sweep claims rows with FOR UPDATE SKIP
            # LOCKED so two relay processes (or beat redelivery overlapping
            # a slow sweep) never publish the same intent twice. Both the
            # outbox AND the dispatch must be pending_publish: a divergence
            # between the two is fail-closed observable (counted, never
            # swept, never silently dropped) because the FK coherence law
            # says they must agree -- disagreement means a writer bypassed
            # the governed path and an operator must look.
            rows = (
                (
                    await session.execute(
                        text(
                            "SELECT o.dispatch_task_id AS task_id,"
                            " o.webhook_ingress_identity_id AS ingress_id,"
                            " o.publish_attempts AS attempts,"
                            " d.window_start AS window_start,"
                            " d.window_end AS window_end,"
                            " d.correlation_id AS correlation_id,"
                            " d.delivery_state AS dispatch_state"
                            " FROM public.b26_p2_execution_outbox AS o"
                            " JOIN public.b23_match_task_dispatches AS d"
                            "   ON d.task_id = o.dispatch_task_id"
                            "  AND d.tenant_id = o.tenant_id"
                            "  AND d.webhook_ingress_identity_id = o.webhook_ingress_identity_id"
                            " WHERE o.tenant_id = :tenant"
                            " AND o.state = 'pending_publish'"
                            " AND o.next_retry_at <= now()"
                            " ORDER BY o.created_at ASC"
                            " LIMIT :limit"
                            " FOR UPDATE OF o SKIP LOCKED"
                        ),
                        {"tenant": str(tenant), "limit": int(limit)},
                    )
                )
                .mappings()
                .all()
            )
            divergent = [r for r in rows if str(r["dispatch_state"]) != "pending_publish"]
            if divergent:
                divergent_total += len(divergent)
                logger.warning(
                    "b26_p2_relay_outbox_dispatch_divergent",
                    extra={
                        "tenant_id": str(tenant),
                        "divergent_task_ids": [str(r["task_id"]) for r in divergent][:10],
                        "divergent_count": len(divergent),
                    },
                )
            rows = [r for r in rows if str(r["dispatch_state"]) == "pending_publish"]
            for row in rows:
                task_id = str(row["task_id"])
                ws = row["window_start"]
                we = row["window_end"]
                # Legacy rows without persisted window: derive from ingress.
                if ws is None or we is None:
                    ev = (
                        (
                            await session.execute(
                                text(
                                    "SELECT event_timestamp FROM"
                                    " public.webhook_ingress_identities"
                                    " WHERE id = :ingress AND tenant_id = :tenant"
                                ),
                                {
                                    "ingress": str(row["ingress_id"]),
                                    "tenant": str(tenant),
                                },
                            )
                        )
                        .mappings()
                        .one_or_none()
                    )
                    if ev is None:
                        failed += 1
                        continue
                    from app.finance_reconciliation.dispatch_authority import (  # noqa: PLC0415
                        derive_reconciliation_window,
                    )

                    ws, we = derive_reconciliation_window(ev["event_timestamp"])
                ok = await _publish_one(
                    None,
                    tenant_id=str(tenant),
                    dispatch_task_id=task_id,
                    window_start_iso=ws.isoformat()
                    if isinstance(ws, datetime)
                    else str(ws),
                    window_end_iso=we.isoformat()
                    if isinstance(we, datetime)
                    else str(we),
                    correlation_id=str(row["correlation_id"] or task_id),
                )
                if ok:
                    await session.execute(
                        text(
                            "UPDATE public.b26_p2_execution_outbox"
                            " SET state = 'published', updated_at = now()"
                            " WHERE dispatch_task_id = :task_id"
                        ),
                        {"task_id": task_id},
                    )
                    await session.execute(
                        text(
                            "UPDATE public.b23_match_task_dispatches"
                            " SET delivery_state = 'published',"
                            " publish_attempts = publish_attempts + 1,"
                            " updated_at = now()"
                            " WHERE task_id = :task_id"
                        ),
                        {"task_id": task_id},
                    )
                    published += 1
                else:
                    backoff = min(300, 15 * (int(row["attempts"] or 0) + 1))
                    await session.execute(
                        text(
                            "UPDATE public.b26_p2_execution_outbox"
                            " SET publish_attempts = publish_attempts + 1,"
                            " last_publish_error = 'broker_unavailable',"
                            " next_retry_at = now() + (:backoff || ' seconds')::interval,"
                            " updated_at = now()"
                            " WHERE dispatch_task_id = :task_id"
                        ),
                        {"task_id": task_id, "backoff": str(backoff)},
                    )
                    await session.execute(
                        text(
                            "UPDATE public.b23_match_task_dispatches"
                            " SET publish_attempts = publish_attempts + 1,"
                            " last_publish_error = 'broker_unavailable',"
                            " updated_at = now()"
                            " WHERE task_id = :task_id"
                        ),
                        {"task_id": task_id},
                    )
                    failed += 1
    # In-process principal evidence: the deployed proof captures which
    # database login actually performed the sweep (must be the relay
    # principal -- only the producer may issue delivery state, and the
    # relay may only recover/publish existing execution authority, never
    # mint it).
    try:
        async with _engine.connect() as _principal_conn:
            relay_principal = str(
                (await _principal_conn.execute(text("SELECT current_user"))).scalar_one()
            )
    except Exception:
        relay_principal = "unknown"
    # Published-unconsumed honesty (Corrective V): every sweep observes
    # the governed staleness signal per tenant. A permanently
    # unconsumed published execution therefore becomes an explicit
    # operator fact (counts + oldest age in the sweep log) instead of
    # silently healthy in-flight work. Staleness is operational
    # metadata only; it never alters deterministic numbers.
    try:
        from app.finance_reconciliation import conduction_state as _conduction  # noqa: PLC0415

        from app.db.session import get_session as _tenant_session  # noqa: PLC0415

        for tenant in tenants:
            async with _tenant_session(tenant_id=tenant) as _stale_session:
                _stale_rows = await _conduction.staleness_snapshot(_stale_session)
            if _stale_rows:
                stale_total += len(_stale_rows)
                oldest_stale_age = max(
                    oldest_stale_age,
                    max(r.age_seconds for r in _stale_rows),
                )
            async with _tenant_session(tenant_id=tenant) as _quar_session:
                _quar_rows = await _conduction.quarantine_snapshot(_quar_session)
            if _quar_rows:
                quarantine_total += len(_quar_rows)
                oldest_quarantine_age = max(
                    oldest_quarantine_age,
                    max(float(r.get("age_seconds") or 0) for r in _quar_rows),
                )
            async with _tenant_session(tenant_id=tenant) as _pend_session:
                _pend = await _pend_session.execute(
                    text(
                        "SELECT count(*) AS n"
                        " FROM public.b23_match_task_dispatches AS d"
                        " WHERE d.delivery_state = 'pending_publish'"
                    )
                )
                pending_total += int(_pend.mappings().one()["n"] or 0)
    except Exception:
        logger.exception(
            "b26_p2_relay_staleness_observation_failed",
            extra={"tenants_scanned": len(tenants)},
        )
    # Recovery-liveness observability (H-IV-B05): every sweep emits its
    # counts. A silent relay (no log lines) vs an empty sweep
    # (published=0) vs a failing sweep (failed>0) are three different
    # operator facts; conflating them hid the unscheduled-relay class.
    # Corrective VI actionability: nonzero stale/divergent/quarantine is
    # ALSO emitted at WARNING (b26_p2_operational_action_required) so the
    # deployed relay process output itself carries the actionable signal
    # -- a shipping consumer, not a callable-only endpoint. WARNING (not
    # INFO) because INFO sweep lines are filtered from the deployed
    # relay output while warnings surface.
    logger.info(
        "b26_p2_relay_sweep_completed",
        extra={
            "tenants_scanned": len(tenants),
            "published": published,
            "failed": failed,
            "divergent": divergent_total,
            "stale_unconducted": stale_total,
            "oldest_stale_age_seconds": oldest_stale_age,
            "quarantine_total": quarantine_total,
            "oldest_quarantine_age_seconds": oldest_quarantine_age,
            "pending_total": pending_total,
            "database_user": relay_principal,
        },
    )
    if stale_total > 0 or divergent_total > 0 or quarantine_total > 0:
        logger.warning(
            "b26_p2_operational_action_required",
            extra={
                "tenants_scanned": len(tenants),
                "stale_unconducted": stale_total,
                "oldest_stale_age_seconds": oldest_stale_age,
                "divergent": divergent_total,
                "quarantine_total": quarantine_total,
                "oldest_quarantine_age_seconds": oldest_quarantine_age,
                "pending_total": pending_total,
                "database_user": relay_principal,
            },
        )
    return {
        "published": published,
        "failed": failed,
        "divergent": divergent_total,
        "stale_unconducted": stale_total,
        "oldest_stale_age_seconds": oldest_stale_age,
        "quarantine_total": quarantine_total,
        "oldest_quarantine_age_seconds": oldest_quarantine_age,
        "pending_total": pending_total,
        "database_user": relay_principal,
    }


@celery_app.task(
    bind=True,
    name=RELAY_TASK_NAME,
    routing_key=f"{RELAY_QUEUE}.task",
    max_retries=3,
    default_retry_delay=30,
)
def relay_b26_p2_pending_dispatches_task(self, limit: int = MAX_SWEEP_BATCH) -> dict:
    """Deployed recovery process: sweep pending intents to the broker."""
    return run_in_worker_loop(publish_pending_outbox(limit=int(limit or MAX_SWEEP_BATCH)))


__all__ = (
    "RELAY_QUEUE",
    "RELAY_TASK_NAME",
    "publish_pending_outbox",
    "relay_b26_p2_pending_dispatches_task",
)
