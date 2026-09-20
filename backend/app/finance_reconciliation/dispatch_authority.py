"""B2.6-P2 Corrective II durable dispatch authority boundary.

Class closed here
-----------------
A broker message could supply tenant and/or window values that the worker
promoted into authoritative P2 context without re-binding them to
authenticated durable dispatch provenance (H-II-01/H-II-02). The worker
derived its tenant GUC and its P2 window from raw Celery message arguments
with no binding to the durable dispatch identity, no signature, and no
window law. Any principal holding kombu DML could manufacture authoritative
P2 scope for any tenant over any window.

Closure theorem: the worker derives/verifies tenant, window and required
provenance from lawful durable upstream authority
(``public.b23_match_task_dispatches`` joined to
``public.webhook_ingress_identities``). Broker message contents cannot
independently author financial scope. A task without valid authority fails
closed (exception, task FAILURE, DLQ) before P2 scope is produced -- never
a silent ``p2_scope: null`` success.

Sovereign sources composed, never reimplemented
-----------------------------------------------
* Durable ``b23_match_task_dispatches`` row (task_id PK, tenant FK, ingress
  FK, task_name/queue/status CHECKs) as the dispatch authority.
* Durable ``webhook_ingress_identities.event_timestamp`` as the sole
  window-membership clock (same persisted commerce clock as scope_authority).
* PostgreSQL RLS (FORCE, tenant policy) as the row-visibility owner; this
  module never disables RLS and never uses BYPASSRLS or SECURITY DEFINER.
* Celery ``self.request.id`` (broker-assigned task identity) as the lookup
  key -- never the message tenant/window arguments.

What this module does NOT do
----------------------------
* No durable state: no table, migration, trigger, view, role, grant, or
  policy change. The dispatch table already carries FKs, uniques, CHECKs,
  RLS/FORCE, and worker readability via app_rw inheritance.
* No B2.3 rewrite: verdict truth is never written here.
* No P3/P4/P5: no reason taxonomy, no durable reconciliation snapshot, no
  finance kernel. The returned authority is in-memory only.
* No LLM/B2.4/B2.13: no estimation or explanation dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class DispatchAuthorityError(ValueError):
    """Broker task authority is missing, mismatched, or ungoverned."""


@dataclass(frozen=True)
class DispatchAuthority:
    """Authoritative worker context re-resolved from durable dispatch."""

    tenant_id: UUID
    window_start: datetime
    window_end: datetime
    webhook_ingress_identity_id: UUID
    dispatch_id: UUID
    broker_task_id: str


def derive_reconciliation_window(event_time: datetime) -> tuple[datetime, datetime]:
    """Derive the governed P2 reconciliation window for one ingress instant.

    Single-implementation law (Corrective II, H-II-03): UTC calendar-day
    quantization executed once in ``app.core.day_window``. The
    B2.3 batch match window currently shares this quantization but is a
    distinct authority (batch args); the P2 reconciliation window is always
    derived here from the durable ingress event_timestamp, never from
    broker args. Naive datetimes refuse; timezone-equivalent instants
    quantize identically.
    """
    from app.core.day_window import quantize_utc_day  # noqa: PLC0415

    if not isinstance(event_time, datetime):
        raise DispatchAuthorityError("p2_dispatch_event_time_not_datetime")
    if event_time.tzinfo is None or event_time.tzinfo.utcoffset(event_time) is None:
        raise DispatchAuthorityError("p2_dispatch_event_time_naive_refused")
    try:
        return quantize_utc_day(event_time)
    except ValueError as exc:
        raise DispatchAuthorityError(f"p2_dispatch_event_time_refused:{exc}") from exc


def derive_reconciliation_window_iso(event_timestamp_iso: str) -> tuple[str, str]:
    """ISO-string façade over :func:`derive_reconciliation_window`.

    Delegates to the single core quantization; malformed inputs refuse
    fail-closed.
    """
    from app.core.day_window import quantize_utc_day_iso  # noqa: PLC0415

    try:
        return quantize_utc_day_iso(event_timestamp_iso)
    except ValueError as exc:
        raise DispatchAuthorityError(f"p2_dispatch_event_time_refused:{exc}") from exc


def _coerce_tenant(tenant_id: Any) -> UUID:
    if isinstance(tenant_id, UUID):
        return tenant_id
    token = str(tenant_id or "").strip()
    if not token:
        raise DispatchAuthorityError("p2_dispatch_tenant_missing")
    try:
        return UUID(token)
    except (ValueError, AttributeError) as exc:
        raise DispatchAuthorityError("p2_dispatch_tenant_malformed") from exc


def _normalize_window(value: Any, *, field: str) -> datetime:
    if isinstance(value, str):
        token = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(token)
        except (ValueError, TypeError) as exc:
            raise DispatchAuthorityError(f"{field}:malformed:{exc}") from exc
        value = parsed
    if not isinstance(value, datetime):
        raise DispatchAuthorityError(f"{field}:not_datetime")
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise DispatchAuthorityError(f"{field}:naive_refused")
    return value.astimezone(timezone.utc)


async def resolve_dispatch_authority(
    session: AsyncSession,
    *,
    broker_task_id: str | None,
    message_tenant_id: UUID | str,
    message_window_start: datetime | str,
    message_window_end: datetime | str,
) -> DispatchAuthority:
    """Re-resolve authoritative worker context from durable dispatch.

    Lookup key is the broker-assigned task identity (``self.request.id``),
    never the message tenant/window. The message tenant/window are treated
    as lower-authority claims and compared against the durable authority;
    any absence or mismatch refuses fail-closed (exception). Callers must
    let the exception propagate to task FAILURE/DLQ -- never swallow to
    ``p2_scope: None`` success.

    RLS note: the session carries the message tenant GUC (set by the
    framework before this call). A forged tenant therefore sees no dispatch
    row (RLS hides other tenants) and refuses as missing -- still
    fail-closed and observable. A lawful tenant sees its own dispatch row
    and proceeds to exact tenant/window comparison below.
    """
    task_key = (broker_task_id or "").strip()
    if not task_key:
        raise DispatchAuthorityError("p2_dispatch_authority_missing:no_broker_task_id")
    message_tenant = _coerce_tenant(message_tenant_id)
    try:
        claimed_start = _normalize_window(
            message_window_start, field="p2_dispatch_window_start"
        )
        claimed_end = _normalize_window(
            message_window_end, field="p2_dispatch_window_end"
        )
    except DispatchAuthorityError:
        raise
    if claimed_start >= claimed_end:
        raise DispatchAuthorityError("p2_dispatch_window_not_half_open")

    row = (
        (
            await session.execute(
                text(
                    "SELECT id, tenant_id, webhook_ingress_identity_id,"
                    " task_name, queue, status"
                    " FROM public.b23_match_task_dispatches"
                    " WHERE task_id = :task_id"
                ),
                {"task_id": task_key},
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise DispatchAuthorityError(
            "p2_dispatch_authority_missing:no_lawful_dispatch_for_task"
        )
    dispatch_tenant = UUID(str(row["tenant_id"]))
    if dispatch_tenant != message_tenant:
        raise DispatchAuthorityError(
            "p2_dispatch_tenant_mismatch:"
            f"message={message_tenant}:dispatch={dispatch_tenant}"
        )
    task_name = str(row["task_name"] or "")
    if task_name != "app.tasks.revenue_verification.execute_b23_batch_match_engine":
        raise DispatchAuthorityError(f"p2_dispatch_task_name_mismatch:{task_name}")
    if str(row["queue"] or "") != "b23_match_engine":
        raise DispatchAuthorityError("p2_dispatch_queue_mismatch")
    if str(row["status"] or "") != "dispatched":
        raise DispatchAuthorityError("p2_dispatch_status_not_dispatched")

    ingress_id = UUID(str(row["webhook_ingress_identity_id"]))
    event_row = (
        (
            await session.execute(
                text(
                    "SELECT event_timestamp"
                    " FROM public.webhook_ingress_identities"
                    " WHERE id = :ingress_id"
                    " AND tenant_id = :tenant_id"
                    " AND verified_commerce_ingress_state = 'authenticity_verified'"
                ),
                {"ingress_id": str(ingress_id), "tenant_id": str(dispatch_tenant)},
            )
        )
        .mappings()
        .one_or_none()
    )
    if event_row is None:
        raise DispatchAuthorityError("p2_dispatch_ingress_missing_or_unverified")
    event_time = event_row["event_timestamp"]
    if not isinstance(event_time, datetime):
        raise DispatchAuthorityError("p2_dispatch_event_time_not_datetime")
    authoritative_start, authoritative_end = derive_reconciliation_window(event_time)
    if claimed_start != authoritative_start or claimed_end != authoritative_end:
        raise DispatchAuthorityError(
            "p2_dispatch_window_mismatch:"
            f"message={claimed_start.isoformat()}/{claimed_end.isoformat()}:"
            f"dispatch={authoritative_start.isoformat()}/"
            f"{authoritative_end.isoformat()}"
        )
    return DispatchAuthority(
        tenant_id=dispatch_tenant,
        window_start=authoritative_start,
        window_end=authoritative_end,
        webhook_ingress_identity_id=ingress_id,
        dispatch_id=UUID(str(row["id"])),
        broker_task_id=task_key,
    )


@dataclass(frozen=True)
class AdmittedExecution:
    """Authoritative tenant/window admitted before B2.3 (no GUC trust)."""

    tenant_id: UUID
    window_start: datetime
    window_end: datetime
    webhook_ingress_identity_id: UUID
    broker_task_id: str


async def admit_execution_before_b23(
    session: AsyncSession,
    *,
    broker_task_id: str | None,
    message_tenant_id: UUID | str,
    message_window_start: datetime | str,
    message_window_end: datetime | str,
) -> AdmittedExecution:
    """Admit one worker invocation BEFORE B2.3 execution (Corrective III,
    sovereign root closed in Corrective VI).

    The worker begins from the least forgeable stable handle (broker task
    identity) and resolves the authoritative tenant/window through the
    constrained ``b26_p2_resolve_dispatch_authority`` function. Since
    Corrective VI the resolver is sovereign: it re-establishes D from E
    (dispatch joined to the authenticated ingress under the
    directory-bootstrapped tenant, canonical UTC-day window recomputed in
    SQL from the ingress event clock) and returns the CANONICAL window
    derived from E, never the stored copy. The message tenant/window are
    redundant claims: any absence or mismatch refuses here, before the
    B2.3 engine runs, with zero B2.3 consequence. A forged D or
    projection refuses inside the resolver (B2.3 delta = 0); the P2 tail
    below is redundant defense-in-depth, never the first sovereign
    detector. Callers must invoke this on a bare session (no tenant
    GUC) before opening any governed snapshot or running B2.3. Full
    dispatch-row validation (task_name/queue/status via DB CHECK physics)
    is re-established under the RETURNED tenant in the P2 phase.
    """
    task_key = (broker_task_id or "").strip()
    if not task_key:
        raise DispatchAuthorityError("p2_dispatch_authority_missing:no_broker_task_id")
    message_tenant = _coerce_tenant(message_tenant_id)
    try:
        claimed_start = _normalize_window(
            message_window_start, field="p2_dispatch_window_start"
        )
        claimed_end = _normalize_window(
            message_window_end, field="p2_dispatch_window_end"
        )
    except DispatchAuthorityError:
        raise
    if claimed_start >= claimed_end:
        raise DispatchAuthorityError("p2_dispatch_window_not_half_open")
    try:
        row = (
            (
                await session.execute(
                    text(
                        "SELECT tenant_id, webhook_ingress_identity_id,"
                        " window_start, window_end"
                        " FROM public.b26_p2_resolve_dispatch_authority(:task_id)"
                    ),
                    {"task_id": task_key},
                )
            )
            .mappings()
            .one_or_none()
        )
    except Exception as exc:
        raise DispatchAuthorityError(
            f"p2_dispatch_authority_missing:resolver_unavailable:{exc}"
        ) from exc
    if row is None:
        raise DispatchAuthorityError(
            "p2_dispatch_authority_missing:no_lawful_dispatch_for_task"
        )
    dispatch_tenant = UUID(str(row["tenant_id"]))
    if dispatch_tenant != message_tenant:
        raise DispatchAuthorityError(
            "p2_dispatch_tenant_mismatch:"
            f"message={message_tenant}:dispatch={dispatch_tenant}"
        )
    authoritative_start = row["window_start"]
    authoritative_end = row["window_end"]
    if not isinstance(authoritative_start, datetime) or not isinstance(
        authoritative_end, datetime
    ):
        raise DispatchAuthorityError("p2_dispatch_window_not_datetime")
    if (
        authoritative_start.tzinfo is None
        or authoritative_end.tzinfo is None
        or authoritative_start >= authoritative_end
    ):
        raise DispatchAuthorityError("p2_dispatch_window_not_half_open")
    authoritative_start = authoritative_start.astimezone(timezone.utc)
    authoritative_end = authoritative_end.astimezone(timezone.utc)
    if claimed_start != authoritative_start or claimed_end != authoritative_end:
        raise DispatchAuthorityError(
            "p2_dispatch_window_mismatch:"
            f"message={claimed_start.isoformat()}/{claimed_end.isoformat()}:"
            f"dispatch={authoritative_start.isoformat()}/"
            f"{authoritative_end.isoformat()}"
        )
    return AdmittedExecution(
        tenant_id=dispatch_tenant,
        window_start=authoritative_start,
        window_end=authoritative_end,
        webhook_ingress_identity_id=UUID(str(row["webhook_ingress_identity_id"])),
        broker_task_id=task_key,
    )


__all__ = (
    "AdmittedExecution",
    "DispatchAuthority",
    "DispatchAuthorityError",
    "admit_execution_before_b23",
    "derive_reconciliation_window",
    "derive_reconciliation_window_iso",
    "resolve_dispatch_authority",
)
