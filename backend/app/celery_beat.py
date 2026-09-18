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

from celery.beat import PersistentScheduler

logger = logging.getLogger(__name__)


class HealingBeatScheduler(PersistentScheduler):
    """PersistentScheduler that drops poisoned broker state on apply failure."""

    def apply_entry(self, entry, producer=None) -> None:
        try:
            result = self.apply_async(entry, producer=producer, advance=False)
        except Exception as exc:
            logger.error(
                "beat_scheduled_apply_failed_dropping_broker_state",
                extra={
                    "event_type": "celery.beat.heal",
                    "schedule_entry": entry.name,
                    "task": entry.task,
                    "error": str(exc)[:500],
                    "error_class": type(exc).__name__,
                },
                exc_info=True,
            )
            self._drop_broker_state()
        else:
            if result is not None and hasattr(result, "id"):
                logger.debug("beat_scheduled_apply_ok:entry=%s", entry.name)

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


__all__ = ["HealingBeatScheduler"]
