"""B2.6-P2 Corrective IV self-healing Celery beat scheduler.

Class closed here
-----------------
A transient broker fault permanently wedges the scheduler's broker
publisher without killing the process: kombu's SQLAlchemy transport
caches ONE session per channel and rolls back ONLY on OperationalError,
so a permission/connection failure poisons the session and every later
scheduled publish fails with PendingRollbackError on the same poisoned
session. Beat stays alive, the schedule stays intact, supervision sees a
healthy process -- and no scheduled sweep ever publishes again. The P2
recovery motor (the relay sweep) dies from the outage class it repairs,
invisibly.

Closure theorem: when a scheduled apply fails at the broker seam, the
scheduler drops its cached broker state (producer + connection) so the
next tick rebuilds a fresh broker session. A fault that has cleared
heals on the next tick with no human action and no process restart; a
fault that persists keeps failing loudly every tick (no silent
suppression: the original error is still logged by this method).

What this module does NOT do
----------------------------
* No schedule semantics change: entries, intervals, expiry, and heap
  behavior are exactly celery's PersistentScheduler.
* No error suppression: failures are logged with entry identity before
  the broker state is dropped.
* No worker/consumer change: only the beat publisher path is affected.
"""

from __future__ import annotations

import logging
import os
import traceback
import uuid

from celery.beat import PersistentScheduler

logger = logging.getLogger(__name__)

# Corrective X scheduled-execution law: the scheduler-plane heartbeat
# entry is executed inline by the beat scheduler process itself (which
# already holds the app_beat credential), never published to a queue.
# The entry keeps its schedule/cadence/visibility; only the execution
# site changes, from "a queue nobody consumes" to "the process that
# owns the schedule".
B26_P2_SCHEDULER_HEARTBEAT_ENTRY = "b26-p2-scheduler-heartbeat"


def _beat_dsn_for_inline_tick() -> str | None:
    """Return a psycopg2-connectable DSN for the beat credential.

    The beat-specific DSN is read from the environment directly (it is
    a deployment binding, not a classified secret); the shared
    DATABASE_URL fallback goes through the governed secret boundary.
    """
    raw = (os.environ.get("B26_P2_BEAT_DATABASE_URL") or "").strip()
    if not raw:
        try:
            from app.core.secrets import (  # noqa: PLC0415
                get_database_url,
            )

            raw = (get_database_url() or "").strip()
        except Exception:
            return None
    if not raw:
        return None
    # Celery/broker URLs name the async driver (postgresql+asyncpg://);
    # the inline sync tick needs the plain DBAPI scheme.
    for marker in ("postgresql+asyncpg://", "postgres+asyncpg://"):
        if raw.startswith(marker):
            return "postgresql://" + raw[len(marker):]
    for marker in ("postgresql+psycopg2://", "postgres+psycopg2://"):
        if raw.startswith(marker):
            return "postgresql://" + raw[len(marker):]
    return raw


def execute_scheduler_plane_tick_inline(
    *, beat_instance_id: str, dsn: str | None = None
) -> dict:
    """Execute one scheduler-plane tick across tenants, synchronously.

    Lists tenants (app_beat holds column-scoped SELECT(id)) and ticks
    ``public.b26_p2_record_scheduler_heartbeat()`` per tenant with the
    beating instance identity bound via ``app.beat_instance_id``.
    Returns counts only. Raises on total failure so the scheduler can
    log loudly; partial failures are counted, never silent.
    """
    import psycopg2  # noqa: PLC0415  # type: ignore[import-untyped]

    target = dsn or _beat_dsn_for_inline_tick()
    if not target:
        raise RuntimeError("b26_p2_inline_tick_no_beat_dsn")
    tenants: list[str] = []
    ticked = 0
    failed = 0
    conn = psycopg2.connect(target)
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM public.tenants ORDER BY id")
            tenants = [str(row[0]) for row in cur.fetchall()]
        for tenant in tenants:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT set_config('app.current_tenant_id', %s, false)",
                        (tenant,),
                    )
                    cur.execute(
                        "SELECT set_config('app.beat_instance_id', %s, false)",
                        (beat_instance_id,),
                    )
                    cur.execute(
                        "SELECT public.b26_p2_record_scheduler_heartbeat()"
                        " AS outcome"
                    )
                    outcome = cur.fetchone()
                    if outcome is None or str(outcome[0]) != "scheduled":
                        raise RuntimeError(
                            f"b26_p2_inline_tick_unexpected_outcome:{outcome}"
                        )
                ticked += 1
            except Exception:
                logger.exception(
                    "b26_p2_scheduler_plane_inline_tick_failed",
                    extra={
                        "event_type": "celery.beat.tick",
                        "tenant_id": str(tenant),
                    },
                )
                failed += 1
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return {
        "tenants_scanned": len(tenants),
        "ticked": ticked,
        "failed": failed,
    }


class HealingBeatScheduler(PersistentScheduler):
    """PersistentScheduler that drops poisoned broker state on apply failure.

    Observability is byte-identical to celery's scheduler (same
    'Scheduler: Sending due task' info line and sent-debug lines), so log
    consumers and live-beat proofs observe no difference; the only delta
    is the broker-state drop plus the heal log on failure.

    Corrective X: the scheduler-plane heartbeat entry is executed inline
    (see module docstring law above). Every other entry publishes
    exactly as before.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # Per-boot scheduler-plane identity, recorded on every inline
        # tick for operator correlation (never a process proof).
        self._b26_p2_beat_instance_id = str(uuid.uuid4())

    def apply_entry(self, entry, producer=None) -> None:
        # Corrective X inline execution: the scheduler-plane heartbeat
        # entry executes in this process (which holds the app_beat
        # credential) instead of publishing to a queue nobody consumes.
        if entry.name == B26_P2_SCHEDULER_HEARTBEAT_ENTRY:
            self._apply_scheduler_plane_tick_inline(entry)
            return
        # Message text is identical to celery's scheduler (log consumers
        # grep "Scheduler: Sending due task <entry>").
        logger.info("Scheduler: Sending due task %s (%s)", entry.name, entry.task)
        try:
            result = self.apply_async(entry, producer=producer, advance=False)
        except Exception as exc:
            logger.error(
                "Message Error: %s\n%s",
                exc,
                traceback.format_stack(),
                exc_info=True,
            )
            logger.error(
                "beat_scheduled_apply_failed_dropping_broker_state",
                extra={
                    "event_type": "celery.beat.heal",
                    "schedule_entry": entry.name,
                    "task": entry.task,
                    "error": str(exc)[:500],
                    "error_class": type(exc).__name__,
                },
            )
            self._drop_broker_state()
        else:
            if result and hasattr(result, "id"):
                logger.debug("%s sent. id->%s", entry.task, result.id)
            else:
                logger.debug("%s sent.", entry.task)

    def _apply_scheduler_plane_tick_inline(self, entry) -> None:
        """Execute the scheduler-plane tick in-process, fail-loudly.

        Never raises: a tick failure is logged with entry identity (the
        absence law surfaces it as scheduler_plane_absent_total), and
        the scheduler loop continues. A missing beat DSN is a
        deployment misconfiguration: loud every tick, never silent.
        """
        logger.info(
            "Scheduler: Sending due task %s (%s)", entry.name, entry.task
        )
        try:
            result = execute_scheduler_plane_tick_inline(
                beat_instance_id=self._b26_p2_beat_instance_id
            )
        except Exception as exc:
            logger.error(
                "b26_p2_scheduler_plane_inline_tick_error",
                extra={
                    "event_type": "celery.beat.tick",
                    "schedule_entry": entry.name,
                    "error": str(exc)[:500],
                    "error_class": type(exc).__name__,
                },
                exc_info=True,
            )
            return
        logger.info(
            "b26_p2_scheduler_plane_ticked_inline",
            extra={
                "event_type": "celery.beat.tick",
                "schedule_entry": entry.name,
                "beat_instance_id": self._b26_p2_beat_instance_id,
                "tenants_scanned": result["tenants_scanned"],
                "ticked": result["ticked"],
                "failed": result["failed"],
            },
        )

    def _drop_broker_state(self) -> None:
        """Forget the cached producer and close its connection.

        The scheduler's ``producer`` is a cached_property bound to one
        kombu connection/channel/session. Forgetting the cache forces
        re-creation on the next tick (fresh broker session); closing the
        connection releases the poisoned channel/session promptly instead
        of waiting for garbage collection. Failures here must never raise:
        the worst case is one more failed tick, never a dead scheduler.
        """
        try:
            producer = self.__dict__.pop("producer", None)
            if producer is None:
                return
            connection = getattr(producer, "__connection__", None)
            if connection is None:
                connection = getattr(producer, "connection", None)
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    logger.warning(
                        "beat_broker_connection_close_failed",
                        extra={"event_type": "celery.beat.heal"},
                        exc_info=True,
                    )
        except Exception:
            logger.warning(
                "beat_broker_state_drop_failed",
                extra={"event_type": "celery.beat.heal"},
                exc_info=True,
            )


__all__ = [
    "B26_P2_SCHEDULER_HEARTBEAT_ENTRY",
    "HealingBeatScheduler",
    "execute_scheduler_plane_tick_inline",
]
