"""B2.6-P2 Corrective V conduction-state helpers (single implementation law).

One module owns every read/write of the Corrective-V conduction
surface so the worker, the relay sweeper, the health endpoint, and the
test suite cannot silently diverge:

* :func:`record_conduction_receipt` -- the worker persists
  task-specific operational provenance (B2.3 count + P2 scope
  identity) after B2.3 commit and P2 success, before the gate.
* :func:`mark_conducted_via_gate` -- the worker advances the twin
  projections to conducted through the server-side gate only. Direct
  UPDATEs into conducted refuse at the database plane for every
  runtime principal.
* :func:`staleness_snapshot` -- published-but-unconsumed rows older
  than the governed threshold, per tenant session. Operational
  metadata only; never financial truth.
* :func:`staleness_threshold_seconds` -- the single governed default
  (env-overridable for CI timeboxes, never a user-facing SLA).

Receipts, quarantine rows, staleness output, and `conducted` itself
are operational state. Nothing here is read as reconciliation truth:
the phase-boundary census (no consumer of outbox/directory/receipt
state as financial truth) covers this module too.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def staleness_threshold_seconds() -> int:
    """Governed non-conduction threshold (seconds).

    Distinguishes normal transient flight (relay sweep cadence is 60s
    in production) from non-conduction requiring operator action.

    Corrective VI threshold authority: the production law is 300s. CI
    timeboxes may compress via B26_P2_STALENESS_SECONDS, but absurd
    suppression (>86400s) refuses loudly instead of silently hiding
    stuck work -- the SQL signal function enforces the same bounds, so
    a misconfigured threshold fails closed (503 + RED) rather than
    reporting zero stale rows.
    """
    raw = (os.getenv("B26_P2_STALENESS_SECONDS", "") or "").strip()
    if not raw:
        return 300
    try:
        value = int(raw)
    except ValueError:
        return 300
    if value <= 0:
        return 300
    if value > 86400:
        raise ValueError("b26_p2_staleness_threshold_out_of_bounds")
    return value


#: Production non-conduction threshold law (seconds). Compressed CI
#: timeboxes use the same law with a smaller parameter, never a
#: different law: staleness is always `anchor_age > threshold`.
B26_P2_PRODUCTION_STALENESS_SECONDS = 300

#: Maximum governed threshold (seconds). Anything above refuses at both
#: the Python boundary (here) and the SQL boundary
#: (b26_p2_stale_unconducted / b26_p2_operational_disposition).
B26_P2_MAX_STALENESS_SECONDS = 86400


@dataclass(frozen=True)
class StaleExecution:
    """One published twin projection older than the governed threshold."""

    task_id: str
    tenant_id: UUID
    state: str
    age_seconds: float
    updated_at: datetime | None


async def record_conduction_receipt(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    broker_task_id: str,
    webhook_ingress_identity_id: UUID,
    window_start: datetime,
    window_end: datetime,
    b23_processed_count: int,
    p2_scope_identity: str,
) -> None:
    """Persist the task-specific conduction receipt (worker only).

    Corrective VI non-self-authenticating proof: the worker holds no
    direct INSERT on the receipt table (revoked on every lane). The
    only writer is the SECURITY DEFINER
    ``b26_p2_record_conduction_receipt()`` invoked here, which derives
    tenant/ingress/window server-side from the sovereign execution
    tuple, refuses forged roots before any row exists, and enforces
    64-hex scope shape. The worker supplies only the scope witness
    string and the batch processed count (operational provenance, never
    authority).

    Runs on the worker pool under the ADMITTED tenant. Idempotent on
    task identity: a redelivered worker re-asserts the same receipt
    rather than duplicating it (ON CONFLICT DO NOTHING inside the
    server function keeps receipt authority INSERT-only).
    """
    task_key = (broker_task_id or "").strip()
    if not task_key:
        raise ValueError("b26_p2_receipt_task_missing")
    scope_token = (p2_scope_identity or "").strip()
    if not scope_token:
        raise ValueError("b26_p2_receipt_scope_missing")
    await session.execute(
        text(
            "SELECT public.b26_p2_record_conduction_receipt("
            " :task_id, :scope_identity, :processed_count)"
        ),
        {
            "task_id": task_key,
            "scope_identity": scope_token,
            "processed_count": int(b23_processed_count or 0),
        },
    )


async def mark_conducted_via_gate(
    session: AsyncSession, *, broker_task_id: str
) -> str:
    """Advance one execution to conducted via the server-side gate.

    The gate validates, for exactly this task: twin projections both
    published, conduction receipt present, B2.3 verdict consequence
    present, caller is the worker login. Returns 'conducted' or
    'already_conducted' (crash-boundary idempotence). Any other case
    raises (fail-closed, task FAILURE/DLQ upstream).
    """
    task_key = (broker_task_id or "").strip()
    if not task_key:
        raise ValueError("b26_p2_conducted_task_missing")
    row = (
        (
            await session.execute(
                text("SELECT public.b26_p2_mark_conducted(:task_id) AS outcome"),
                {"task_id": task_key},
            )
        )
        .mappings()
        .one()
    )
    return str(row["outcome"])


async def staleness_snapshot(
    session: AsyncSession, *, threshold_seconds: int | None = None
) -> list[StaleExecution]:
    """Published twin rows older than the threshold (caller tenant GUC).

    The session must carry a tenant GUC (per-tenant loop in health and
    relay); RLS confines each call to its tenant. Pure SELECT.
    """
    threshold = int(threshold_seconds or staleness_threshold_seconds())
    rows = (
        (
            await session.execute(
                text(
                    "SELECT task_id, tenant_id, state, age_seconds, updated_at"
                    " FROM public.b26_p2_stale_unconducted(:threshold)"
                ),
                {"threshold": threshold},
            )
        )
        .mappings()
        .all()
    )
    return [
        StaleExecution(
            task_id=str(r["task_id"]),
            tenant_id=UUID(str(r["tenant_id"])),
            state=str(r["state"]),
            age_seconds=float(r["age_seconds"] or 0),
            updated_at=r["updated_at"],
        )
        for r in rows
    ]


async def operational_disposition(
    session: AsyncSession, *, broker_task_id: str, threshold_seconds: int | None = None
) -> str:
    """Total operational disposition for one execution (caller GUC-free).

    The server function bootstraps tenant visibility from the canonical
    tuple itself, so callers need no tenant GUC. Every accepted D maps
    to one explicit state; unknown tasks return NOT_ACCEPTED (explicit,
    never an empty row set for a known accepted D).
    """
    task_key = (broker_task_id or "").strip()
    if not task_key:
        raise ValueError("b26_p2_disposition_task_missing")
    threshold = int(threshold_seconds or staleness_threshold_seconds())
    row = (
        (
            await session.execute(
                text(
                    "SELECT public.b26_p2_operational_disposition("
                    " :task_id, :threshold) AS disposition"
                ),
                {"task_id": task_key, "threshold": threshold},
            )
        )
        .mappings()
        .one()
    )
    return str(row["disposition"])


async def quarantine_snapshot(session: AsyncSession) -> list[dict[str, Any]]:
    """Operator-visible quarantine rows for the caller tenant (counts only).

    The session must carry a tenant GUC (per-tenant loop in health and
    relay); RLS confines each call to its tenant. Pure SELECT.
    """
    rows = (
        (
            await session.execute(
                text(
                    "SELECT task_id, source_relation, reason,"
                    " EXTRACT(EPOCH FROM (now() - quarantined_at)) AS age_seconds"
                    " FROM public.b26_p2_execution_quarantine"
                    " ORDER BY quarantined_at ASC"
                ),
            )
        )
        .mappings()
        .all()
    )
    return [dict(r) for r in rows]


def describe_staleness(rows: list[StaleExecution]) -> dict[str, Any]:
    """Operator summary over staleness rows (counts only, no PII)."""
    oldest = max((r.age_seconds for r in rows), default=0)
    return {
        "stale_unconducted_count": len(rows),
        "oldest_stale_age_seconds": oldest,
    }


__all__ = (
    "B26_P2_MAX_STALENESS_SECONDS",
    "B26_P2_PRODUCTION_STALENESS_SECONDS",
    "StaleExecution",
    "describe_staleness",
    "mark_conducted_via_gate",
    "operational_disposition",
    "quarantine_snapshot",
    "record_conduction_receipt",
    "staleness_snapshot",
    "staleness_threshold_seconds",
)
