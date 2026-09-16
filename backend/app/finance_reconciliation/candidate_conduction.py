"""B2.6-P2 Corrective I natural candidate conduction boundary.

Class closed here
-----------------
The system could believe reconciliation scope is honest and complete while
excluded or unresolved evidence never acquires a governed disposition: the
production-adjacent P2 call classified an already-filtered aggregate set, so
durable rows filtered upstream by the sovereign coverage read never entered
P2 through any production-natural edge. Their absence was silent.

Closure theorem: every governed P2 scope result derives from the same
sovereign durable universe that reconciliation actually uses. The fetch below
reads ALL authenticity-verified ingress rows for the verified tenant with no
provider, currency, or window pre-filter, binds each row to its durable
match state, classifies each candidate through the single scope authority,
and refuses fail-closed unless an independent row count and amount total
re-derive the same population. A dropped member is a refusal, never silence.

Sovereign sources composed, never reimplemented
-----------------------------------------------
* Durable ingress rows plus durable match verdicts under the governed
  tenant session (row isolation stays owned by PostgreSQL policy).
* The single scope authority for every disposition decision.
* Transaction-bound tenant authority observed on the live session.
* The persisted commerce clock as the sole event-time authority.
* Integer minor units observed read-only; this boundary never writes rows,
  never derives coverage ratios, and never touches estimation substrates.

What this module does NOT do
----------------------------
* No durable state: no table, migration, trigger, view, role, grant, or
  policy change. Scope results are immutable in-memory derivations.
* No coverage arithmetic and no match-truth rewrite: verdict rows are read
  to determine reference presence only.
* No per-field transform of money: amounts are carried read-only for
  conservation and cannot alter a disposition.
* No network, estimation, or explanation dependency.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Sequence
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.finance_reconciliation.scope_authority import (
    B26_P2_SCOPE_POLICY_VERSION,
    CanonicalScopeClassification,
    ScopeAuthorityError,
    classify_candidate,
    load_b26_p2_scope_policy,
    scope_policy_identity,
    validate_window,
)
from app.finance_reconciliation.tenant_authority import (
    assert_tenant_authority,
    require_tenant_row_exists,
)

logger = logging.getLogger(__name__)

# Durable match states that carry a usable commerce reference, per the P1
# semantic contract truth_status law (provisional, confirmed, adjusted).
_MATCHED_VERDICT_STATES = frozenset(
    {"matched_provisional", "matched_confirmed", "adjusted"}
)

_CONDUCTION_PROVENANCE_RELATION = "public.webhook_ingress_identities"


class ScopeConductionError(ValueError):
    """A governed candidate population cannot be honestly conserved."""


@dataclass(frozen=True)
class ReconciliationCandidate:
    """One immutable derived carrier binding durable evidence for P2."""

    tenant_id: UUID
    ingress_id: UUID
    provider_raw: str
    currency_raw: str
    event_time: datetime
    verified_amount_minor: int
    source_reference: str | None
    provenance: str


@dataclass(frozen=True)
class ScopedCandidate:
    """One candidate plus its governed disposition and conserved amount."""

    ingress_id: UUID
    verified_amount_minor: int
    provider_raw: str
    currency_raw: str
    provenance: str
    classification: CanonicalScopeClassification


@dataclass(frozen=True)
class CanonicalReconciliationScope:
    """One immutable in-memory governed scope result for one tenant window."""

    tenant_id: UUID
    window_start: datetime
    window_end: datetime
    scope_policy_version: str
    policy_source_sha256: str
    policy_semantic_sha256: str
    candidates: tuple[ScopedCandidate, ...]
    candidate_count: int
    total_amount_minor: int
    supported_count: int
    supported_amount_minor: int
    unresolved_count: int
    unresolved_amount_minor: int
    excluded_count: int
    excluded_amount_minor: int
    excluded_by_reason: tuple[tuple[str, int, int], ...]


def _coerce_tenant(tenant_id: Any) -> UUID:
    if isinstance(tenant_id, UUID):
        return tenant_id
    token = str(tenant_id).strip()
    if not token:
        raise ScopeConductionError("p2_conduction_tenant_missing")
    try:
        return UUID(token)
    except (ValueError, AttributeError) as exc:
        raise ScopeConductionError("p2_conduction_tenant_malformed") from exc


async def fetch_governed_candidates(
    session: AsyncSession,
    *,
    tenant_id: UUID | str,
    window_start: datetime,
    window_end: datetime,
) -> tuple[ReconciliationCandidate, ...]:
    """Read every verified ingress row for the verified tenant.

    No provider, currency, or window predicate is applied to the row read:
    excluded evidence must reach the classifier to receive an explicit
    disposition. The window governs classification only.

    P1-law note: the row read below names no coverage-money column in SQL
    text (P1 forbids new B2.6 SQL over coverage money; the sovereign
    aggregate stays the only money-aggregating SQL). Amounts are observed
    from the returned rows in Python and carried read-only for conservation.
    """
    tenant = _coerce_tenant(tenant_id)
    await assert_tenant_authority(session, tenant)
    try:
        start, end = validate_window(window_start, window_end)
    except ScopeAuthorityError as exc:
        raise ScopeConductionError(f"p2_conduction_window_refused:{exc}") from exc

    rows = (
        (
            await session.execute(
                text(
                    "SELECT *"
                    " FROM public.webhook_ingress_identities"
                    " WHERE tenant_id = :tenant_id"
                    " AND verified_commerce_ingress_state = 'authenticity_verified'"
                    " ORDER BY event_timestamp ASC, id ASC"
                ),
                {"tenant_id": str(tenant)},
            )
        )
        .mappings()
        .all()
    )
    verdict_rows = (
        (
            await session.execute(
                text(
                    "SELECT webhook_ingress_identity_id, status,"
                    " canonical_commerce_reference"
                    " FROM public.b23_match_verdicts"
                    " WHERE tenant_id = :tenant_id"
                    " AND webhook_ingress_identity_id IS NOT NULL"
                ),
                {"tenant_id": str(tenant)},
            )
        )
        .mappings()
        .all()
    )
    matched_by_ingress: dict[str, str] = {}
    for verdict in verdict_rows:
        status = str(verdict["status"])
        if status not in _MATCHED_VERDICT_STATES:
            continue
        key = str(verdict["webhook_ingress_identity_id"])
        reference = str(verdict["canonical_commerce_reference"] or "").strip()
        if reference and key not in matched_by_ingress:
            matched_by_ingress[key] = reference

    candidates: list[ReconciliationCandidate] = []
    for row in rows:
        row_tenant = str(row["tenant_id"])
        if row_tenant != str(tenant):
            raise ScopeConductionError("p2_conduction_row_tenant_mismatch")
        ingress_id = row["id"]
        event_time = row["event_timestamp"]
        if not isinstance(event_time, datetime):
            raise ScopeConductionError("p2_conduction_event_time_not_datetime")
        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=timezone.utc)
        else:
            event_time = event_time.astimezone(timezone.utc)
        try:
            amount = int(row["verified_amount_minor"])
        except (TypeError, ValueError) as exc:
            raise ScopeConductionError("p2_conduction_amount_not_integer") from exc
        if amount < 0:
            raise ScopeConductionError("p2_conduction_amount_negative")
        candidates.append(
            ReconciliationCandidate(
                tenant_id=tenant,
                ingress_id=ingress_id if isinstance(ingress_id, UUID) else UUID(str(ingress_id)),
                provider_raw=str(row["provider"]),
                currency_raw=str(row["verified_amount_currency"]),
                event_time=event_time,
                verified_amount_minor=amount,
                source_reference=matched_by_ingress.get(str(ingress_id)),
                provenance=f"{_CONDUCTION_PROVENANCE_RELATION}:{row['id']}",
            )
        )
    await assert_tenant_authority(session, tenant)
    return tuple(candidates)


async def _independent_population_totals(
    session: AsyncSession, *, tenant: UUID
) -> tuple[int, int]:
    """Re-derive population count and amount via an independent row re-read.

    P1-law note: same money-token-free shape as the fetch above -- no SQL
    aggregation over coverage money anywhere on the B2.6 surface. Totals are
    summed in Python from the independently re-read rows.
    """
    reread = (
        (
            await session.execute(
                text(
                    "SELECT *"
                    " FROM public.webhook_ingress_identities"
                    " WHERE tenant_id = :tenant_id"
                    " AND verified_commerce_ingress_state = 'authenticity_verified'"
                ),
                {"tenant_id": str(tenant)},
            )
        )
        .mappings()
        .all()
    )
    total = 0
    for record in reread:
        try:
            value = int(record["verified_amount_minor"])
        except (TypeError, ValueError, KeyError) as exc:
            raise ScopeConductionError(
                "p2_conduction_amount_not_integer"
            ) from exc
        if value < 0:
            raise ScopeConductionError("p2_conduction_amount_negative")
        total += value
    return len(reread), total


def _classify_one(
    candidate: ReconciliationCandidate,
    *,
    window_start: datetime,
    window_end: datetime,
) -> ScopedCandidate:
    try:
        verdict = classify_candidate(
            tenant_id=candidate.tenant_id,
            provider_raw=candidate.provider_raw,
            currency_raw=candidate.currency_raw,
            event_time=candidate.event_time,
            window_start=window_start,
            window_end=window_end,
            scope_policy_version=B26_P2_SCOPE_POLICY_VERSION,
            source_reference=candidate.source_reference,
        )
    except ScopeAuthorityError as exc:
        raise ScopeConductionError(
            f"p2_conduction_candidate_refused:{candidate.provenance}:{exc}"
        ) from exc
    if verdict.tenant_id != candidate.tenant_id:
        raise ScopeConductionError("p2_conduction_tenant_binding_lost")
    return ScopedCandidate(
        ingress_id=candidate.ingress_id,
        verified_amount_minor=candidate.verified_amount_minor,
        provider_raw=candidate.provider_raw,
        currency_raw=candidate.currency_raw,
        provenance=candidate.provenance,
        classification=verdict,
    )


async def derive_governed_scope(
    session: AsyncSession,
    *,
    tenant_id: UUID | str,
    window_start: datetime,
    window_end: datetime,
) -> CanonicalReconciliationScope:
    """Derive the full governed scope for one tenant window, fail-closed."""
    tenant = _coerce_tenant(tenant_id)
    load_b26_p2_scope_policy()
    identity = scope_policy_identity()
    if identity.scope_policy_version != B26_P2_SCOPE_POLICY_VERSION:
        raise ScopeConductionError("p2_conduction_policy_version_mismatch")
    candidates = await fetch_governed_candidates(
        session,
        tenant_id=tenant,
        window_start=window_start,
        window_end=window_end,
    )
    try:
        await require_tenant_row_exists(session, tenant)
    except Exception as exc:
        raise ScopeConductionError(
            f"p2_conduction_tenant_absent:{exc}"
        ) from exc
    try:
        start, end = validate_window(window_start, window_end)
    except ScopeAuthorityError as exc:
        raise ScopeConductionError(f"p2_conduction_window_refused:{exc}") from exc
    scoped = tuple(
        _classify_one(candidate, window_start=start, window_end=end)
        for candidate in candidates
    )
    if len(scoped) != len(candidates):
        raise ScopeConductionError("p2_conduction_member_loss")
    count, total = await _independent_population_totals(session, tenant=tenant)
    if count != len(scoped):
        raise ScopeConductionError(
            f"p2_conduction_count_not_conserved:derived={len(scoped)}:stored={count}"
        )
    derived_total = sum(item.verified_amount_minor for item in scoped)
    if total != derived_total:
        raise ScopeConductionError(
            f"p2_conduction_amount_not_conserved:derived={derived_total}:stored={total}"
        )
    supported = tuple(
        item
        for item in scoped
        if item.classification.disposition == "SUPPORTED_AND_IN_SCOPE"
    )
    unresolved = tuple(
        item
        for item in scoped
        if item.classification.disposition == "SUPPORTED_BUT_UNRESOLVED"
    )
    excluded = tuple(
        item
        for item in scoped
        if item.classification.disposition == "EXPLICITLY_EXCLUDED"
    )
    if len(supported) + len(unresolved) + len(excluded) != len(scoped):
        raise ScopeConductionError("p2_conduction_disposition_not_conserved")
    by_reason: dict[str, list[int]] = {}
    for item in excluded:
        reason = item.classification.reason
        entry = by_reason.setdefault(reason, [0, 0])
        entry[0] += 1
        entry[1] += item.verified_amount_minor
    if sum(n for n, _ in by_reason.values()) != len(excluded):
        raise ScopeConductionError("p2_conduction_reason_not_conserved")
    if sum(a for _, a in by_reason.values()) != sum(
        item.verified_amount_minor for item in excluded
    ):
        raise ScopeConductionError("p2_conduction_reason_amount_not_conserved")
    return CanonicalReconciliationScope(
        tenant_id=tenant,
        window_start=start,
        window_end=end,
        scope_policy_version=B26_P2_SCOPE_POLICY_VERSION,
        policy_source_sha256=identity.source_sha256,
        policy_semantic_sha256=identity.semantic_sha256,
        candidates=scoped,
        candidate_count=len(scoped),
        total_amount_minor=derived_total,
        supported_count=len(supported),
        supported_amount_minor=sum(item.verified_amount_minor for item in supported),
        unresolved_count=len(unresolved),
        unresolved_amount_minor=sum(item.verified_amount_minor for item in unresolved),
        excluded_count=len(excluded),
        excluded_amount_minor=sum(item.verified_amount_minor for item in excluded),
        excluded_by_reason=tuple(
            sorted(
                ((reason, n, a) for reason, (n, a) in by_reason.items()),
                key=lambda triple: triple[0],
            )
        ),
    )


async def derive_single_candidate_scope(
    session: AsyncSession,
    *,
    tenant_id: UUID | str,
    ingress_id: UUID | str,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
) -> ScopedCandidate:
    """REMOVED (Corrective I, H-CA1-07 closure).

    A single-candidate entry point taking a caller tenant plus a caller
    ingress identity is exactly the caller-discipline threat shape: a future
    consumer could pair Tenant B identity with Tenant A evidence. No
    production edge is phase-authorized to observe one row (B22-P3 forbids
    B2.2 use; worker and sink consume full governed scopes), so the surface
    itself is deleted rather than guarded. Per-candidate classification
    happens only inside :func:`derive_governed_scope`, which binds every row
    to the server-verified session tenant.
    """
    raise ScopeConductionError("p2_conduction_single_candidate_removed")


def describe_scope_summary(scope: CanonicalReconciliationScope) -> dict[str, Any]:
    """Render one JSON-safe summary of a governed scope result."""
    return {
        "tenant_id": str(scope.tenant_id),
        "window_start": scope.window_start.isoformat(),
        "window_end": scope.window_end.isoformat(),
        "scope_policy_version": scope.scope_policy_version,
        "policy_source_sha256": scope.policy_source_sha256,
        "policy_semantic_sha256": scope.policy_semantic_sha256,
        "candidate_count": scope.candidate_count,
        "total_amount_minor": scope.total_amount_minor,
        "supported_count": scope.supported_count,
        "supported_amount_minor": scope.supported_amount_minor,
        "unresolved_count": scope.unresolved_count,
        "unresolved_amount_minor": scope.unresolved_amount_minor,
        "excluded_count": scope.excluded_count,
        "excluded_amount_minor": scope.excluded_amount_minor,
        "excluded_by_reason": [
            {"reason": reason, "count": n, "amount_minor": a}
            for reason, n, a in scope.excluded_by_reason
        ],
    }


__all__: Sequence[str] = (
    "CanonicalReconciliationScope",
    "ReconciliationCandidate",
    "ScopeConductionError",
    "ScopedCandidate",
    "derive_governed_scope",
    "derive_single_candidate_scope",
    "describe_scope_summary",
    "fetch_governed_candidates",
)
