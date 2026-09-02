"""B2.4-P4 source-window cardinality producer.

The B2.5-P13 C8-N contiguous journey established that
``b24_source_window_feature_authority`` had no production writer. The planner
requested an authority, ``build_feature_authority`` read the table, found
nothing, and parked the request for another sixty seconds -- forever. Every
proof that had ever shown a fit supplied that row itself, which is why nothing
in the repository could see it.

This module is the missing writer. What it is *not* is equally important.

Feature authority does not decide whether a dataset is trustworthy. That
question already belongs to ``b24-eligibility-v1``, which owns every minimum:
events, distinct events, conversions, confirmed verdicts, distinct channels,
per-currency observations and window density. Nor does it decide whether a
dataset is affordable -- that belongs to the B2.4 resource policy and its caps.
Feature authority answers only the middle question, *how wide is this snapshot*,
so those two policies can do their jobs:

    minimum sufficiency  (P2 eligibility)
            |
            v
    source shape         (this module)
            |
            v
    maximum complexity   (P4 resource policy)

So this module introduces no thresholds. It computes cardinality, not
confidence, and every rule it applies is read from an authority that already
exists:

* membership comes from ``SOURCE_CONTRACT_AUTHORITY``, which renders the same
  predicate into the canonical snapshot SELECT and into the invalidation trigger
  DDL, and which now reads its values from ``LIFECYCLE_INCLUSION_RULES``;
* the caps come from ``B24_RESOURCE_POLICY``;
* the counting discipline is the already-adjudicated
  ``true_next_key_early_stop_cap_plus_one_v1``;
* channel and currency cardinality are taken from the P2 preflight that already
  computes them, rather than recomputed here under a second definition.

Only ``provider`` and ``campaign_or_feature`` needed new derivations, because
P2 selects those columns but never aggregates them.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.bayesian.eligibility import EligibilityPreflightResult
from app.bayesian.resource_bounds import (
    B24_DISTINCT_CARDINALITY_POLICY,
    B24_RESOURCE_POLICY,
)
from app.bayesian.source_contract_authority import (
    SOURCE_CONTRACT_AUTHORITY,
    SourceRelationContract,
)


BOUNDED_CARDINALITY_POLICY = B24_DISTINCT_CARDINALITY_POLICY

#: Which resource cap bounds each dimension. The producer never states a number;
#: it states which governed cap applies and reads the value from the policy.
DIMENSION_CAPS = {
    "channel": B24_RESOURCE_POLICY.max_channels,
    "currency": B24_RESOURCE_POLICY.max_currencies,
    "provider": B24_RESOURCE_POLICY.max_providers,
    "campaign_or_feature": B24_RESOURCE_POLICY.max_campaigns_or_feature_keys,
}

#: Where each derived dimension's keys live. Channel and currency are absent
#: because P2 already computes them; adding them here would be the second
#: definition this module exists to avoid.
DERIVED_DIMENSION_SOURCES: dict[str, tuple[tuple[str, str], ...]] = {
    "provider": (
        ("b23_match_verdicts", "provider"),
        ("b23_revenue_events", "provider"),
    ),
    "campaign_or_feature": (("attribution_events", "campaign_id"),),
}


@dataclass(frozen=True)
class BoundedCardinality:
    """One dimension's width, and whether that width is exact.

    ``overflowed`` is the honest part. Once a dimension is known to exceed its
    cap, the exact count carries no further decision information -- the resource
    policy has already refused it -- so the walk stops and the value reported is
    ``cap + 1``. Recording that the value is a floor rather than a count keeps a
    later reader from mistaking one for the other.
    """

    dimension: str
    value: int
    cap: int
    overflowed: bool

    @property
    def is_exact(self) -> bool:
        return not self.overflowed


@dataclass(frozen=True)
class SourceWindowCardinality:
    """The four widths the feature authority stores, plus their provenance."""

    channel: BoundedCardinality
    currency: BoundedCardinality
    provider: BoundedCardinality
    campaign_or_feature: BoundedCardinality
    cardinality_policy: str
    source_snapshot_hash: str

    def counts(self) -> dict[str, int]:
        return {
            "channel_count": self.channel.value,
            "currency_count": self.currency.value,
            "provider_count": self.provider.value,
            "campaign_or_feature_count": self.campaign_or_feature.value,
        }

    def any_overflowed(self) -> bool:
        return any(
            item.overflowed
            for item in (
                self.channel,
                self.currency,
                self.provider,
                self.campaign_or_feature,
            )
        )


def _bounded(dimension: str, raw: int, *, proven_overflow: bool = False) -> BoundedCardinality:
    """Apply the cap-plus-one reporting rule to one measured width."""

    cap = DIMENSION_CAPS[dimension]
    overflowed = proven_overflow or raw > cap
    return BoundedCardinality(
        dimension=dimension,
        value=cap + 1 if overflowed else raw,
        cap=cap,
        overflowed=overflowed,
    )


def render_bounded_key_walk(contract: SourceRelationContract, *, key: str) -> str:
    """A loose index scan that visits each distinct key once and then stops.

    This is the shape B2.4 already adopted for channel cardinality, generalised
    to any relation and key in the source contract. It matters that it is a walk
    rather than a ``COUNT(DISTINCT ...)``: the walk touches one row per distinct
    key and stops at the cap, so a tenant with two hundred thousand campaign
    identifiers costs the same as one with two thousand and one. A COUNT DISTINCT
    over the same window would read all of them to produce a number the resource
    policy would discard anyway.

    Membership and window key are rendered from the source contract -- the same
    method that renders the invalidation trigger's predicate -- so a relation
    cannot mean one thing when it is snapshotted, another when it is
    invalidated, and a third when it is measured.
    """

    relation = contract.relation
    window_clause = contract.walk_window_clause("candidate")
    order_key = contract.walk_order_key("candidate")
    member = contract.member_predicate("candidate")
    key_expr = f"nullif(candidate.{key}, '')"
    return f"""
        WITH RECURSIVE walked(source_key, ordinal) AS (
            (
                SELECT {key_expr} AS source_key, 1 AS ordinal
                FROM public.{relation} AS candidate
                WHERE candidate.tenant_id = :tenant_id
                  AND {window_clause}
                  AND {member}
                  AND {key_expr} IS NOT NULL
                ORDER BY {key_expr}, {order_key}
                LIMIT 1
            )
            UNION ALL
            SELECT next_key.source_key, walked.ordinal + 1
            FROM walked
            CROSS JOIN LATERAL (
                SELECT {key_expr} AS source_key
                FROM public.{relation} AS candidate
                WHERE candidate.tenant_id = :tenant_id
                  AND {window_clause}
                  AND {member}
                  AND {key_expr} IS NOT NULL
                  AND {key_expr} > walked.source_key
                ORDER BY {key_expr}, {order_key}
                LIMIT 1
            ) AS next_key
            WHERE walked.ordinal < :cap_plus_one
        )
        SELECT source_key FROM walked
    """


async def _walk_keys(
    session: AsyncSession,
    *,
    relation: str,
    key: str,
    tenant_id: UUID,
    source_window_start: datetime,
    source_window_end: datetime,
    cap: int,
) -> tuple[set[str], bool]:
    """Distinct keys for one relation, bounded at ``cap + 1``."""

    contract = SOURCE_CONTRACT_AUTHORITY[relation]
    rows = await session.execute(
        text(render_bounded_key_walk(contract, key=key)),
        {
            "tenant_id": str(tenant_id),
            "window_start": source_window_start,
            "window_end": source_window_end,
            "cap_plus_one": cap + 1,
        },
    )
    keys = {str(row[0]) for row in rows if row[0] is not None}
    return keys, len(keys) > cap


async def _derive_dimension(
    session: AsyncSession,
    *,
    dimension: str,
    tenant_id: UUID,
    source_window_start: datetime,
    source_window_end: datetime,
) -> BoundedCardinality:
    """One dimension's width across every relation that contributes to it.

    A dimension spanning two relations is walked once per relation and unioned.
    That stays bounded -- at most ``2 * (cap + 1)`` keys are ever held -- and
    stays correct: if either walk overflowed then the union overflows too, since
    the union contains each part; and if neither overflowed then both key sets
    are complete, so their union is exact.
    """

    cap = DIMENSION_CAPS[dimension]
    union: set[str] = set()
    overflowed = False
    for relation, key in DERIVED_DIMENSION_SOURCES[dimension]:
        keys, part_overflowed = await _walk_keys(
            session,
            relation=relation,
            key=key,
            tenant_id=tenant_id,
            source_window_start=source_window_start,
            source_window_end=source_window_end,
            cap=cap,
        )
        union |= keys
        overflowed = overflowed or part_overflowed
    return _bounded(dimension, len(union), proven_overflow=overflowed)


async def measure_walked_dimensions(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    source_window_start: datetime,
    source_window_end: datetime,
) -> dict[str, BoundedCardinality]:
    """The two dimensions P2 does not aggregate, measured on the given session.

    Which session is given is the entire safety property. These walks must run
    inside the transaction that produced the hash the resulting authority will
    be stamped with, or they describe a different state of the database than the
    hash does.
    """

    return {
        dimension: await _derive_dimension(
            session,
            dimension=dimension,
            tenant_id=tenant_id,
            source_window_start=source_window_start,
            source_window_end=source_window_end,
        )
        for dimension in DERIVED_DIMENSION_SOURCES
    }


def assemble_source_window_cardinality(
    *,
    preflight: EligibilityPreflightResult,
    walked: dict[str, BoundedCardinality],
    source_snapshot_hash: str,
) -> SourceWindowCardinality:
    """Combine the two P2-measured widths with the two walked ones.

    Both halves must have come from the same transaction. This function cannot
    check that -- nothing in the values themselves records which snapshot they
    were read from -- which is exactly why the only production caller obtains
    both inside one, and why the safety lives there rather than here.
    """

    return SourceWindowCardinality(
        channel=_bounded("channel", int(preflight.eligible_channel_count)),
        currency=_bounded("currency", len(preflight.currency_groups)),
        provider=walked["provider"],
        campaign_or_feature=walked["campaign_or_feature"],
        cardinality_policy=BOUNDED_CARDINALITY_POLICY,
        source_snapshot_hash=source_snapshot_hash,
    )


async def measure_source_window_within_one_snapshot(
    *,
    tenant_id: UUID,
    model_type: str,
    model_version: str,
    source_window_start: datetime,
    source_window_end: datetime,
    barrier: Callable[[], Awaitable[None]] | None = None,
) -> tuple[Any, SourceWindowCardinality]:
    """Hash and all four widths, read from one MVCC snapshot.

    This is the function the exact-snapshot invariant lives in. The hash, the P2
    preflight that supplies channel and currency width, and the walks that
    supply provider and campaign width are all reads inside a single
    ``REPEATABLE READ READ ONLY`` transaction, so they describe one state of the
    database because they *are* one read of it.

    ``barrier`` is awaited inside that transaction, after the hash and preflight
    and before the walks -- the precise window in which the earlier
    two-transaction implementation could be made to lie. A proof passes a
    callback that commits a real mutation there. It can change when the walks
    run; it cannot change what they see.
    """

    from app.bayesian.source_snapshot import compute_source_snapshot_hash
    from app.db.session import AsyncSessionLocal

    async def _within(session: AsyncSession) -> dict[str, BoundedCardinality]:
        if barrier is not None:
            await barrier()
        return await measure_walked_dimensions(
            session,
            tenant_id=tenant_id,
            source_window_start=source_window_start,
            source_window_end=source_window_end,
        )

    # No tenant GUC is bound here on purpose. compute_source_snapshot_hash opens
    # its own transaction and sets the GUC inside it, and touching the session
    # first starts an implicit transaction that its begin() then refuses.
    async with AsyncSessionLocal() as snapshot_session:
        snapshot = await compute_source_snapshot_hash(
            snapshot_session,
            tenant_id=tenant_id,
            model_type=model_type,
            model_version=model_version,
            source_window_start=source_window_start,
            source_window_end=source_window_end,
            within_snapshot=_within,
        )

    walked = snapshot.within_snapshot_result
    if not isinstance(walked, dict):
        raise RuntimeError(
            "feature cardinality was not measured inside the snapshot transaction"
        )
    return snapshot, assemble_source_window_cardinality(
        preflight=snapshot.preflight,
        walked=walked,
        source_snapshot_hash=snapshot.source_snapshot_hash,
    )


async def produce_source_window_feature_authority(
    *,
    tenant_id: UUID,
    model_type: str,
    model_version: str,
    source_window_start: datetime,
    source_window_end: datetime,
    expected_source_snapshot_hash: str,
    barrier: Callable[[], Awaitable[None]] | None = None,
) -> "SourceWindowFeatureAuthority | None":
    """Materialize the feature authority for one exact source snapshot.

    Every dimension is measured inside the same repeatable-read transaction that
    produces the hash the row is stamped with. That is the whole design, and the
    first version of this function did not have it.

    It hashed the source and ran the P2 preflight in one transaction, let that
    transaction close, then walked provider and campaign width in a second,
    later one. Both halves were individually correct. Together they were a lie
    waiting for a coincidence: a mutation committed in the gap changed provider
    and campaign width without changing the hash, and the row was written
    ``fresh`` describing a snapshot that had never existed -- channel and
    currency from S0, provider and campaign from S1, keyed by hash(S0). No test
    could catch it, because the only guard compared the caller's expectation
    against the hash the *first* transaction had already returned, and that
    comparison is blind to anything happening after it.

    Measuring inside one snapshot removes the coincidence rather than detecting
    it. Under ``REPEATABLE READ`` a mutation committed after the transaction
    begins is invisible to every read within it, so the five measurements agree
    because they are one observation, not because nothing happened to disturb
    them.

    Freshness is therefore snapshot identity. The row is written only when the
    snapshot it describes is the snapshot the request named; if the source moved
    before the request arrived, nothing is written and the caller parks it.

    ``barrier`` exists so this can be disproved -- see
    ``measure_source_window_within_one_snapshot``. Production passes nothing.

    Eligibility is deliberately not consulted. Whether a snapshot has *enough*
    data is the eligibility policy's decision; this function reports how wide it
    is and lets that decision be made from the measurement.
    """

    from app.bayesian.feature_authority import (
        B24_FEATURE_AUTHORITY_POLICY_VERSION,
        FeatureAuthorityStatus,
        SourceWindowFeatureAuthority,
        upsert_source_window_feature_authority,
    )
    from app.db.session import get_session

    snapshot, cardinality = await measure_source_window_within_one_snapshot(
        tenant_id=tenant_id,
        model_type=model_type,
        model_version=model_version,
        source_window_start=source_window_start,
        source_window_end=source_window_end,
        barrier=barrier,
    )

    if snapshot.source_snapshot_hash != expected_source_snapshot_hash:
        return None

    counts = cardinality.counts()
    async with get_session(tenant_id) as session:
        authority = SourceWindowFeatureAuthority(
            tenant_id=tenant_id,
            model_type=model_type,
            model_version=model_version,
            source_window_start=source_window_start,
            source_window_end=source_window_end,
            source_snapshot_hash=snapshot.source_snapshot_hash,
            channel_count=counts["channel_count"],
            currency_count=counts["currency_count"],
            provider_count=counts["provider_count"],
            campaign_or_feature_count=counts["campaign_or_feature_count"],
            freshness_status=FeatureAuthorityStatus.FRESH,
            policy_version=B24_FEATURE_AUTHORITY_POLICY_VERSION,
            computed_at=datetime.now(timezone.utc),
        )
        await upsert_source_window_feature_authority(session, authority=authority)
    return authority
