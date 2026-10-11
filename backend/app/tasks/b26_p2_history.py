"""B2.6-P2 history-integrity beat observation (XXI, H-XXI-07/Gate N).

Scheduled task recording ledger count/tip plus observer violations with
unforgeable authorship. Trust issuance degrades unless a fresh
beat-authored clean observation agrees with live state; CI gates
deployment-time continuity against the committed anchor file.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from app.celery_app import celery_app
from app.core.queues import QUEUE_B23_MATCH_ENGINE

logger = logging.getLogger(__name__)

HISTORY_TASK_NAME = "app.tasks.b26_p2_history.observe_history_integrity"


async def observe_history_integrity() -> Dict[str, Any]:
    """Record one history-integrity observation row. Returns the observation.

    Executes the owner-context observation function (which reads the
    ledgers the caller cannot) and returns the recorded outcome. The
    beat row's author is the caller's session_user, stamped by the
    database and unforgeable in-session.
    """
    from sqlalchemy import text  # noqa: PLC0415

    from app.db.session import engine as _engine  # noqa: PLC0415

    async with _engine.connect() as conn:
        row = (
            (
                await conn.execute(
                    text(
                        "SELECT * FROM"
                        " public.b26_p2_observe_history_integrity()"
                    )
                )
            )
            .mappings()
            .one()
        )
        await conn.commit()
    violations = [
        v for v in str(row["violations"] or "").split(";") if v.strip()
    ]
    result = {
        "observation_id": str(row["observation_id"]),
        "observed_at": row["observed_at"].isoformat(),
        "ledger_count": int(row["ledger_count"]),
        "ledger_tip": row["ledger_tip"],
        "violations": violations,
    }
    if violations:
        logger.warning(
            "b26_p2_history_integrity_violations",
            extra={"violations": violations[:10]},
        )
    return result


@celery_app.task(
    bind=True,
    name=HISTORY_TASK_NAME,
    routing_key=f"{QUEUE_B23_MATCH_ENGINE}.task",
    max_retries=3,
    default_retry_delay=60,
)
def observe_history_integrity_task(self) -> Dict[str, Any]:
    """Deployed history observation: ledger continuity to durable rows."""
    from app.tasks.context import run_in_worker_loop  # noqa: PLC0415

    return run_in_worker_loop(observe_history_integrity())


__all__ = (
    "HISTORY_TASK_NAME",
    "observe_history_integrity",
    "observe_history_integrity_task",
)
