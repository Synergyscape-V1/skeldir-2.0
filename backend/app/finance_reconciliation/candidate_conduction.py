"""B2.6-P2 Corrective II canonical scope derivation boundary.

Corrective I law (preserved)
----------------------------
Excluded or unresolved evidence never vanishes: the fetch reads ALL
authenticity-verified ingress rows for the verified tenant with no provider,
currency, or window pre-filter, binds each row to its durable match state,
classifies each candidate through the single scope authority, and refuses
fail-closed unless an independent re-read re-derives the same population.

Corrective II law (added)
-------------------------
The live P2 edge existed but lacked authority, identity conservation,
snapshot coherence, and non-vacuous proof. This module now closes that
class:

* One derivation equals one REPEATABLE READ snapshot (H-II-10/H-II-11).
  Population and conservation reads share a single Postgres MVCC snapshot
  acquired before any query. Concurrent commits after the snapshot are
  invisible to both reads by database physics, never by timing luck. The
  derivation refuses unless ``SHOW transaction_isolation`` reports
  ``repeatable read`` -- READ COMMITTED callers cannot obtain scope.
* Exact identity conservation (H-II-05/H-II-06/H-II-20). Conservation
  compares the exact sorted source-identity set (ingress UUIDs), not just
  count+amount arithmetic. The canonical result binds a deterministic
  ``scope_identity`` digest over tenant/window/policy plus the sorted
  identity/disposition/reason/amount material, so equal-value substitution,
  omission, or duplication changes or refuses the identity.
* Common-mode completeness (H-II-07/H-II-08/H-II-09). Both reads traverse
  the same RLS/view/helper root in production, so agreement alone cannot
  prove completeness. Every derivation inspects the physical RLS policy
  definition for the ingress relation and the relation kind, refusing when
  tenant RLS carries unauthorized provider/currency/time/status narrowing
  or when the relation is not an ordinary table. Tenant isolation and
  candidate completeness are separately proven obligations.
* Money sovereignty (H-II-12/H-II-13/H-II-14). Every P2 amount is labeled
  machine-readably as source-verified gross (B2.2 ingress), never canonical
  net (B2.3 verdicts). The scope carries ``money_semantics``,
  ``money_authority``, and ``canonical_net_authority`` on every result and
  summary so no machine caller can confuse P2 gross with B2.3 net.

Sovereign sources composed, never reimplemented
-----------------------------------------------
* Durable ingress rows plus durable match verdicts under the governed
  tenant session (row isolation stays owned by PostgreSQL policy).
* The single scope authority for every disposition decision.
* Transaction-bound tenant authority observed on the live session.
* The persisted commerce clock as the sole event-time authority.
* Postgres MVCC snapshot, pg_policies catalog, and pg_class relation kind
  as the independent completeness/snapshot oracles (observed, not rebuilt).
* Integer minor units observed read-only; this boundary never writes rows,
  never derives coverage ratios, and never touches estimation substrates.

What this module does NOT do
----------------------------
* No durable state: no table, migration, trigger, view, role, grant, or
  policy change. Scope results are immutable in-memory derivations. P4's
  durable reconciliation snapshot is absent by phase law.
* No coverage arithmetic and no match-truth rewrite: verdict rows are read
  to determine reference presence only.
* No per-field transform of money: amounts are carried read-only for
  conservation and cannot alter a disposition.
* No network, estimation, or explanation dependency.
"""

from __future__ import annotations

import hashlib
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


# Machine-readable money semantics (Corrective II, H-II-12/13/14). Every P2
# amount below is source-verified gross from B2.2 ingress, never B2.3
# canonical net. Consumers must read these labels; field names alone are not
# authority.
P2_MONEY_SEMANTICS = "source_verified_gross_not_canonical_net"
P2_MONEY_AUTHORITY = "b2.2_ingress_verified_amount_minor"
P2_CANONICAL_NET_AUTHORITY = (
    "b2.3_match_verdicts.canonical_net_verified_amount_minor_only"
)
P2_SNAPSHOT_ISOLATION_LAW = "repeatable_read_single_snapshot_per_derivation"


@dataclass(frozen=True)
class CanonicalReconciliationScope:
    """One immutable in-memory governed scope result for one tenant window."""

    tenant_id: UUID
    window_start: datetime
    window_end: datetime
    scope_policy_version: str
    policy_source_sha256: str
    policy_semantic_sha256: str
    scope_identity: str
    snapshot_isolation: str
    money_semantics: str
    money_authority: str
    canonical_net_authority: str
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
                ingress_id=(
                    ingress_id
                    if isinstance(ingress_id, UUID)
                    else UUID(str(ingress_id))
                ),
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


async def _require_snapshot_isolation(session: AsyncSession) -> str:
    """Require one REPEATABLE READ snapshot for this derivation.

    The isolation level is database physics observed on the live
    transaction, not a caller string. READ COMMITTED (or any other level)
    refuses with ``p2_snapshot_isolation_not_repeatable_read`` before any
    candidate row is read, so an undefined multi-read snapshot can never
    produce a canonical-looking scope.
    """
    level_row = (
        (await session.execute(text("SHOW transaction_isolation")))
        .mappings()
        .one_or_none()
    )
    level = str(level_row["transaction_isolation"]).strip().lower() if level_row else ""
    if level != "repeatable read":
        raise ScopeConductionError(
            "p2_snapshot_isolation_not_repeatable_read:" f"{level or 'unknown'}"
        )
    return P2_SNAPSHOT_ISOLATION_LAW


async def _inspect_rls_completeness(session: AsyncSession) -> None:
    """Refuse silent candidate-universe narrowing through the visibility root.

    Corrective-III strict law (H-III-D01..D05): candidate completeness is
    proven by effect-closure over the catalog, not by absence of forbidden
    words in tenant-named policy text. Both production reads traverse the
    same RLS/view/helper root, so their agreement cannot prove completeness.
    This oracle observes a different root (catalog + relation flags) and
    requires:

    - exactly one policy on the ingress relation with the governed name;
    - RLS enabled and forced (physical flags, not convention);
    - no RULEs on the relation (alternate narrowing primitive);
    - the single qual/with_check binds tenant authority only and invokes
      no function besides ``current_setting`` (any helper, operator-class,
      or opaque predicate refuses, however named);
    - no provider/currency/time/status/amount token in any predicate.

    A non-table relation refuses with ``p2_source_relation_not_table``.
    A second RESTRICTIVE policy, a neutral helper, or a helper-body drift
    all change the catalog fingerprint and refuse, even when tenant
    isolation still holds.
    """
    import re as _rls_re

    phys_row = (
        (
            await session.execute(
                text(
                    "SELECT c.relkind AS relkind,"
                    " c.relrowsecurity AS rls_enabled,"
                    " c.relforcerowsecurity AS rls_forced"
                    " FROM pg_class c"
                    " JOIN pg_namespace n ON n.oid = c.relnamespace"
                    " WHERE n.nspname = 'public'"
                    " AND c.relname = 'webhook_ingress_identities'"
                )
            )
        )
        .mappings()
        .one_or_none()
    )
    if phys_row is None:
        raise ScopeConductionError("p2_source_relation_not_table:missing")
    raw_kind = phys_row["relkind"]
    if isinstance(raw_kind, (bytes, bytearray)):
        try:
            raw_kind = bytes(raw_kind).decode("utf-8", errors="strict")
        except Exception as exc:
            raise ScopeConductionError(
                f"p2_source_relation_not_table:undecodable:{exc}"
            ) from exc
    if str(raw_kind) != "r":
        raise ScopeConductionError(f"p2_source_relation_not_table:{raw_kind}")
    if not bool(phys_row["rls_enabled"]):
        raise ScopeConductionError("p2_rls_completeness_refused:rls_not_enabled")
    if not bool(phys_row["rls_forced"]):
        raise ScopeConductionError("p2_rls_completeness_refused:rls_not_forced")
    rule_row = (
        (
            await session.execute(
                text(
                    "SELECT count(*) AS rule_count FROM pg_rules"
                    " WHERE schemaname = 'public'"
                    " AND tablename = 'webhook_ingress_identities'"
                )
            )
        )
        .mappings()
        .one_or_none()
    )
    if rule_row is not None and int(rule_row["rule_count"] or 0) != 0:
        raise ScopeConductionError("p2_rls_completeness_refused:relation_rule_present")
    policy_rows = (
        (
            await session.execute(
                text(
                    "SELECT policyname AS policyname,"
                    " permissive AS permissive,"
                    " roles AS roles,"
                    " cmd AS cmd,"
                    " qual AS qual,"
                    " with_check AS with_check"
                    " FROM pg_policies"
                    " WHERE schemaname = 'public'"
                    " AND tablename = 'webhook_ingress_identities'"
                    " ORDER BY policyname"
                )
            )
        )
        .mappings()
        .all()
    )
    if len(policy_rows) != 1:
        raise ScopeConductionError(
            f"p2_rls_completeness_refused:policy_singleton_violated:{len(policy_rows)}"
        )
    policy = policy_rows[0]
    name = str(policy["policyname"] or "")
    if name != "tenant_isolation_policy_webhook_ingress_identities":
        raise ScopeConductionError(
            f"p2_rls_completeness_refused:unexpected_policy:{name}"
        )
    for column in ("qual", "with_check"):
        definition = str(policy[column] or "")
        lowered = definition.lower()
        if not lowered.strip():
            raise ScopeConductionError(
                f"p2_rls_completeness_refused:{name}:{column}:empty_predicate"
            )
        if (
            "current_setting" not in lowered
            or "app.current_tenant_id" not in lowered
        ):
            raise ScopeConductionError(
                f"p2_rls_completeness_refused:{name}:{column}:no_tenant_root"
            )
        # Any function call besides current_setting refuses: strip the one
        # governed call, then any remaining IDENT( pattern is a helper.
        scrubbed = _rls_re.sub(
            r"current_setting\s*\(", "governed_root(", lowered
        )
        scrubbed = scrubbed.replace("governed_root(", "")
        if _rls_re.search(r"[a-z_][a-z0-9_\.]*\s*\(", scrubbed):
            raise ScopeConductionError(
                f"p2_rls_completeness_refused:{name}:{column}:function_call_present"
            )
        for forbidden in (
            "provider",
            "currency",
            "event_timestamp",
            "verified_commerce_ingress_state",
            "verified_amount",
            "status",
            "created_at",
            "updated_at",
        ):
            if forbidden in lowered:
                raise ScopeConductionError(
                    f"p2_rls_completeness_refused:{name}:{column}:{forbidden}"
                )


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
            raise ScopeConductionError("p2_conduction_amount_not_integer") from exc
        if value < 0:
            raise ScopeConductionError("p2_conduction_amount_negative")
        total += value
    return len(reread), total


async def _independent_population_identities(
    session: AsyncSession, *, tenant: UUID
) -> tuple[str, ...]:
    """Re-read the exact sorted source-identity set for conservation.

    Identity conservation is separate from amount conservation (H-II-20):
    hashing the set returned by a narrowed visibility domain only creates a
    stable digest of the wrong universe. This re-read returns sorted ingress
    UUID strings observed in the same REPEATABLE READ snapshot; the caller
    compares the set to the derived population and refuses on any
    substitution, omission, or duplication even when count+amount agree.
    """
    reread = (
        (
            await session.execute(
                text(
                    "SELECT id"
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
    return tuple(sorted(str(record["id"]) for record in reread))


SCOPE_IDENTITY_VERSION = "b2.6-p2-scope-identity-v3"

# Default-include law (Corrective III, H-III-F01..F07): any field capable of
# changing canonical P2 meaning is identity-bearing unless the contract
# explicitly declares and proves it non-identity metadata. Within-window
# event instants are the sole declared non-identity field: the governed
# window is day-granular, so two instants in the same UTC day carry the
# same scope meaning (proven by the window oracle half-open law). Every
# other semantic field below is identity-bearing.


def _compute_scope_identity(
    *,
    tenant: UUID,
    window_start: datetime,
    window_end: datetime,
    scope_policy_version: str,
    scoped: tuple[ScopedCandidate, ...],
    policy_semantic_sha256: str = "",
    money_semantics: str = "",
    money_authority: str = "",
    canonical_net_authority: str = "",
) -> str:
    """Bind the complete canonical P2 semantic record to one digest.

    Material per candidate is
    ``ingress_id:provider:rail:currency:disposition:reason:amount`` using
    canonical normalized provider/rail/currency (representational variants
    such as case/whitespace normalize identically and preserve identity,
    while a supported provider A -> supported provider B, a rail change, or
    a currency semantic change changes the digest even when disposition,
    reason, amount, and source UUID are unchanged). The top-level material
    binds the governing SEMANTIC policy identity (semantic SHA, not the
    human version string alone and never the policy file's raw source
    bytes) and the money-semantic labels, so a policy semantic change or
    a money-label change changes the identity even when every numeric
    aggregate is unchanged, while a comment/whitespace-only policy edit
    preserves it (Corrective IV semantic-vs-provenance law). The source
    SHA remains emitted on every scope result as audit provenance; it is
    deliberately not identity-bearing. The multiset is sorted so replay is
    stable and ordering-only changes preserve identity.
    """
    lines = sorted(
        f"{item.ingress_id}:{item.classification.provider}:"
        f"{item.classification.rail}:{item.classification.currency_code}:"
        f"{item.classification.disposition}:"
        f"{item.classification.reason}:{int(item.verified_amount_minor)}"
        for item in scoped
    )
    payload = "|".join(
        [
            SCOPE_IDENTITY_VERSION,
            str(tenant),
            window_start.isoformat(),
            window_end.isoformat(),
            str(scope_policy_version),
            str(policy_semantic_sha256 or ""),
            str(money_semantics or P2_MONEY_SEMANTICS),
            str(money_authority or P2_MONEY_AUTHORITY),
            str(canonical_net_authority or P2_CANONICAL_NET_AUTHORITY),
            *lines,
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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
    snapshot_law = await _require_snapshot_isolation(session)
    await _inspect_rls_completeness(session)
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
        raise ScopeConductionError(f"p2_conduction_tenant_absent:{exc}") from exc
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
    derived_identity_set = tuple(sorted(str(item.ingress_id) for item in scoped))
    reread_identity_set = await _independent_population_identities(
        session, tenant=tenant
    )
    if derived_identity_set != reread_identity_set:
        raise ScopeConductionError(
            "p2_conduction_identity_not_conserved:"
            f"derived={len(derived_identity_set)}:stored={len(reread_identity_set)}"
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
    scope_identity = _compute_scope_identity(
        tenant=tenant,
        window_start=start,
        window_end=end,
        scope_policy_version=B26_P2_SCOPE_POLICY_VERSION,
        scoped=scoped,
        # Corrective IV: the source SHA is provenance (still stored on the
        # result below), never identity material. Only the semantic SHA
        # binds the digest, so nonsemantic policy bytes cannot drift scope.
        policy_semantic_sha256=identity.semantic_sha256,
        money_semantics=P2_MONEY_SEMANTICS,
        money_authority=P2_MONEY_AUTHORITY,
        canonical_net_authority=P2_CANONICAL_NET_AUTHORITY,
    )
    if len(scope_identity) != 64:
        raise ScopeConductionError("p2_scope_identity_malformed")
    return CanonicalReconciliationScope(
        tenant_id=tenant,
        window_start=start,
        window_end=end,
        scope_policy_version=B26_P2_SCOPE_POLICY_VERSION,
        policy_source_sha256=identity.source_sha256,
        policy_semantic_sha256=identity.semantic_sha256,
        scope_identity=scope_identity,
        snapshot_isolation=snapshot_law,
        money_semantics=P2_MONEY_SEMANTICS,
        money_authority=P2_MONEY_AUTHORITY,
        canonical_net_authority=P2_CANONICAL_NET_AUTHORITY,
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
        "scope_identity": scope.scope_identity,
        "snapshot_isolation": scope.snapshot_isolation,
        "money_semantics": scope.money_semantics,
        "money_authority": scope.money_authority,
        "canonical_net_authority": scope.canonical_net_authority,
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
    "P2_CANONICAL_NET_AUTHORITY",
    "P2_MONEY_AUTHORITY",
    "P2_MONEY_SEMANTICS",
    "P2_SNAPSHOT_ISOLATION_LAW",
    "CanonicalReconciliationScope",
    "ReconciliationCandidate",
    "ScopeConductionError",
    "ScopedCandidate",
    "derive_governed_scope",
    "derive_single_candidate_scope",
    "describe_scope_summary",
    "fetch_governed_candidates",
)
