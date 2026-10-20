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
    result["witness"] = await _record_signed_checkpoint()
    return result


async def _record_signed_checkpoint() -> Dict[str, Any] | None:
    """Append one Ed25519 checkpoint over the live ledger state.

    The observer reads live state through DEFINER surfaces, verifies the
    prior signed journal prefix, and refuses to sign a shrink or a
    divergent prefix. The journal path and key must be outside the
    database principal's control.
    """
    from sqlalchemy import text  # noqa: PLC0415

    from app.core.config import settings  # noqa: PLC0415
    from app.db.session import engine as _engine  # noqa: PLC0415
    from app.trust.history_witness import (  # noqa: PLC0415
        HistoryWitnessError,
        append_checkpoint,
        load_private_key,
        verify_journal,
    )

    private_key_path = settings.B26_P2_HISTORY_WITNESS_PRIVATE_KEY_PATH
    if not private_key_path:
        return None
    private_key = load_private_key(private_key_path)
    try:
        journal = verify_journal(
            settings.B26_P2_HISTORY_WITNESS_JOURNAL_PATH,
            public_key=private_key.public_key(),
            genesis_hash=settings.B26_P2_HISTORY_WITNESS_GENESIS_HASH,
            require_freshness=False,
        )
    except HistoryWitnessError as exc:
        if str(exc) not in {
            "witness_journal_missing",
            "witness_journal_empty",
        }:
            raise
        if settings.B26_P2_HISTORY_WITNESS_GENESIS_HASH:
            raise HistoryWitnessError("witness_genesis_journal_missing") from exc
        journal = None
    async with _engine.connect() as conn:
        state = (
            (
                await conn.execute(
                    text(
                        "SELECT n, tip_seq, tip_hash FROM"
                        " public.b26_p2_read_history_witness_state()"
                    )
                )
            )
            .mappings()
            .one()
        )
        prefix_digest = await conn.scalar(
            text("SELECT public.b26_p2_read_history_prefix_digest()")
        )
        raw_violations = await conn.scalar(
            text("SELECT public.b26_p2_read_history_violations()")
        )
        previous_tip_hash: str | None = None
        if journal is not None:
            previous = journal.latest
            if previous.ledger_tip_seq is not None:
                previous_tip_hash = await conn.scalar(
                    text(
                        "SELECT public.b26_p2_read_history_entry_hash(:seq)"
                    ),
                    {"seq": int(previous.ledger_tip_seq)},
                )
    violations = str(raw_violations or "").strip()
    if violations:
        raise HistoryWitnessError(
            f"witness_refused_violations:{violations}"
        )
    if journal is not None:
        previous = journal.latest
        if previous.ledger_tip_seq is not None and (
            previous_tip_hash != previous.ledger_tip_hash
        ):
            raise HistoryWitnessError("witness_history_prefix_diverged")
        if (
            int(state["n"] or 0) < previous.ledger_count
            or (
                int(state["n"] or 0) == previous.ledger_count
                and (
                    (state["tip_hash"] or None)
                    != (previous.ledger_tip_hash or None)
                    or (prefix_digest or None)
                    != (previous.ledger_prefix_digest or None)
                )
            )
        ):
            raise HistoryWitnessError("witness_history_prefix_diverged")
    checkpoint = append_checkpoint(
        settings.B26_P2_HISTORY_WITNESS_JOURNAL_PATH,
        private_key_path=private_key_path,
        ledger_count=int(state["n"] or 0),
        ledger_tip_seq=(
            int(state["tip_seq"]) if state["tip_seq"] is not None else None
        ),
        ledger_tip_hash=state["tip_hash"],
        ledger_prefix_digest=prefix_digest,
        genesis_hash=settings.B26_P2_HISTORY_WITNESS_GENESIS_HASH,
    )
    return {
        "ledger_count": checkpoint.ledger_count,
        "ledger_tip_seq": checkpoint.ledger_tip_seq,
        "ledger_tip_hash": checkpoint.ledger_tip_hash,
        "ledger_prefix_digest": checkpoint.ledger_prefix_digest,
        "checkpoint_hash": checkpoint.checkpoint_hash,
        "observed_at": checkpoint.observed_at.isoformat(),
    }


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
