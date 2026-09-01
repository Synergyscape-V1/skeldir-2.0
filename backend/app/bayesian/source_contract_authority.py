"""B2.5-P13 C8 single structured authority for B2.4 source semantics.

Corrective Action VII kept two truths and tried to prove them equal afterwards:
the authoritative source SELECTs in ``source_snapshot._SOURCE_QUERIES``, and a
hand-transcribed membership/projection contract used to render the invalidation
triggers. Independent audit then showed the equivalence check did not actually
compare them -- its projection arm was ``column in str(projection)``, a tautology
over a tuple's own repr, and the membership predicates were never compared to the
source queries at all. Changing source semantics without changing invalidation
semantics left mandatory CI green.

This module removes the second truth rather than checking it harder. One
structured contract per relation is declared here, and both artefacts are
rendered from it:

        SourceRelationContract
                 |
        +--------+--------+
        |                 |
    source SELECT    invalidation DDL

Drift is not detected, it is unrepresentable: there is no second place to drift
from. What remains checkable -- and is checked by the C8 gate -- is that the
shipped SELECT text and the shipped trigger DDL are exactly what this authority
renders.
"""

from __future__ import annotations

import textwrap

from dataclasses import dataclass
from types import MappingProxyType

from app.bayesian.input_contract import LIFECYCLE_INCLUSION_RULES


SOURCE_CONTRACT_AUTHORITY_VERSION = "b25-p13-c8-source-authority-v1"


@dataclass(frozen=True)
class ProjectedColumn:
    """One column the canonical snapshot observes.

    ``expression`` is the SQL the snapshot SELECT emits when the observed value
    is normalized (for example ``upper(currency_code)``). ``column`` is always
    the physical column the invalidation trigger compares, because normalization
    is a pure function of the raw value: comparing raw cannot miss a normalized
    change, it can only over-invalidate, which is efficiency debt rather than a
    correctness defect.
    """

    column: str
    expression: str | None = None
    alias: str | None = None

    def select_fragment(self) -> str:
        if self.expression is None:
            return self.column
        return f"{self.expression} AS {self.alias or self.column}"


@dataclass(frozen=True)
class MembershipFilter:
    """One filter deciding whether a row is in the canonical snapshot.

    ``bind`` selects expanding-parameter rendering for value sets. A filter with
    no bind renders as a literal predicate in both artefacts, which is how a
    boolean column such as ``verified = true`` stays spelled the same way in the
    SELECT and in the trigger instead of being cast through a text set.
    """

    column: str
    values: tuple[str, ...] = ()
    bind: str | None = None
    literal_sql: str | None = None

    def select_fragment(self) -> str:
        if self.literal_sql is not None:
            return self.literal_sql
        return f"{self.column} IN :{self.bind}"

    def trigger_fragment(self, alias: str) -> str:
        if self.literal_sql is not None:
            return f"{alias}.{self.literal_sql}"
        rendered = ", ".join(f"'{value}'" for value in self.values)
        return f"{alias}.{self.column} IN ({rendered})"


@dataclass(frozen=True)
class SourceRelationContract:
    """Everything that decides what this relation contributes to the snapshot."""

    relation: str
    window_key: str
    projection: tuple[ProjectedColumn, ...]
    membership: tuple[MembershipFilter, ...]
    # C19: allocations and verdicts enter the snapshot through the immutable
    # financial event's clock via an aliased join, and events require verified
    # allocation lineage -- a SELECT shape the structural renderer cannot
    # express. The authoritative text is declared here and the C7 gate still
    # compares it byte-level (whitespace-normalised) against what ships.
    select_override: str | None = None
    # C19 moved snapshot membership for this relation onto the immutable
    # financial event's clock while ``window_key`` still names this relation's
    # own transition/write column.  The two must not disagree: a relation may
    # not be inside the snapshot and outside the measurement of that same
    # snapshot.  When set, this predicate is the window bound the bounded-key
    # walk uses, so measurement follows membership.
    walk_window_predicate: str | None = None

    def walk_window_clause(self, alias: str) -> str:
        """The window bound the bounded-key walk applies to one candidate row."""

        if self.walk_window_predicate is not None:
            return self.walk_window_predicate.format(alias=alias)
        return (
            f"{alias}.{self.window_key} >= :window_start"
            + "\n                  AND "
            + f"{alias}.{self.window_key} < :window_end"
        )

    def walk_order_key(self, alias: str) -> str:
        """Deterministic walk tiebreak; the dedup key still leads the ORDER BY."""

        if self.walk_window_predicate is not None:
            return f"{alias}.id"
        return f"{alias}.{self.window_key}, {alias}.id"

    def projected_columns(self) -> tuple[str, ...]:
        return tuple(item.column for item in self.projection)

    def member_predicate(self, alias: str) -> str:
        """Never-NULL membership test for one row of ``relation``."""

        clauses = [item.trigger_fragment(alias) for item in self.membership]
        predicate = " AND ".join(clauses) if clauses else "true"
        return f"COALESCE({predicate}, false) AND {alias}.{self.window_key} IS NOT NULL"

    def projected_row(self, alias: str) -> str:
        columns = ", ".join(f"{alias}.{item.column}" for item in self.projection)
        return f"({columns})"

    def bucket(self, alias: str) -> str:
        return f"date_trunc('day', {alias}.{self.window_key})"

    def render_select(self) -> str:
        """The authoritative canonical snapshot SELECT for this relation."""

        if self.select_override is not None:
            return self.select_override
        columns = ",\n                ".join(
            [f"'{self.relation}' AS source_table_discriminator"]
            + [item.select_fragment() for item in self.projection]
        )
        filters = "".join(
            f"\n              AND {item.select_fragment()}" for item in self.membership
        )
        return (
            "\n            SELECT\n"
            f"                {columns}\n"
            f"            FROM public.{self.relation}\n"
            "            WHERE tenant_id = :tenant_id\n"
            f"              AND {self.window_key} >= :window_start\n"
            f"              AND {self.window_key} < :window_end"
            f"{filters}\n"
            f"            ORDER BY tenant_id ASC, {self.window_key} ASC NULLS LAST,"
            " id ASC\n            "
        )

    def bind_params(self) -> dict[str, tuple[str, ...]]:
        return {
            item.bind: item.values
            for item in self.membership
            if item.bind is not None
        }


def _identity(*columns: str) -> tuple[ProjectedColumn, ...]:
    return tuple(ProjectedColumn(column=column) for column in columns)


def _lifecycle(relation: str, column: str, bind: str) -> "MembershipFilter":
    """One membership filter, read from the lifecycle rules rather than restated.

    B2.4's inclusion rules are the authority on which source rows are members.
    Before this, the same tuples were written out again here, and the two agreed
    only because someone kept them agreeing. That is the shape of defect C8 was
    called to remove from the identity space, and it is the same shape: a value
    that must match another value, with nothing that fails when it stops
    matching. Reading it collapses the pair into one truth, which is what lets
    the cardinality producer derive membership from this contract instead of
    authoring a third copy.
    """

    return MembershipFilter(column, LIFECYCLE_INCLUSION_RULES[f"{relation}.{column}"], bind)


SOURCE_CONTRACT_AUTHORITY: MappingProxyType = MappingProxyType(
    {
        "attribution_events": SourceRelationContract(
            # C19 authoritative SELECT (see select_override).
            select_override=textwrap.dedent(
                """\n            SELECT
                'attribution_events' AS source_table_discriminator,
                id::text AS id,
                tenant_id::text AS tenant_id,
                occurred_at,
                event_timestamp,
                event_type,
                channel,
                campaign_id,
                revenue_cents,
                conversion_value_cents,
                upper(coalesce(currency, 'USD')) AS currency,
                processing_status
            FROM public.attribution_events AS e
            WHERE e.tenant_id = :tenant_id
              AND e.occurred_at >= :window_start
              AND e.occurred_at < :window_end
              AND e.processing_status IN :processed_statuses
              AND e.event_type IN :conversion_event_types
              AND EXISTS (
                    SELECT 1
                    FROM public.attribution_allocations AS authority
                    WHERE authority.tenant_id = e.tenant_id
                      AND authority.event_id = e.id
                      AND authority.verified = true
              )
            ORDER BY e.tenant_id ASC, e.occurred_at ASC NULLS LAST, e.id ASC
            
                """
            ).strip(),
            relation="attribution_events",
            window_key="occurred_at",
            projection=(
                ProjectedColumn("id", "id::text", "id"),
                ProjectedColumn("tenant_id", "tenant_id::text", "tenant_id"),
                *_identity(
                    "occurred_at",
                    "event_timestamp",
                    "event_type",
                    "channel",
                    "campaign_id",
                    "revenue_cents",
                    "conversion_value_cents",
                ),
                ProjectedColumn(
                    "currency", "upper(coalesce(currency, 'USD'))", "currency"
                ),
                ProjectedColumn("processing_status"),
            ),
            membership=(
                _lifecycle(
                    "attribution_events", "processing_status", "processed_statuses"
                ),
                _lifecycle(
                    "attribution_events", "event_type", "conversion_event_types"
                ),
            ),
        ),
        "attribution_allocations": SourceRelationContract(
            # C19 authoritative SELECT (see select_override).
            select_override=textwrap.dedent(
                """\n        SELECT
            'attribution_allocations' AS source_table_discriminator,
            a.id::text AS id,
            a.tenant_id::text AS tenant_id,
            a.event_id::text AS event_id,
            a.created_at,
            a.channel_code,
            a.allocated_revenue_cents,
            a.allocation_ratio,
            a.model_type,
            a.model_version,
            a.verified,
            a.verification_source,
            a.verification_timestamp
        FROM public.attribution_allocations AS a
        JOIN public.attribution_events AS e
          ON e.tenant_id = a.tenant_id
         AND e.id = a.event_id
        WHERE a.tenant_id = :tenant_id
          AND e.occurred_at >= :window_start
          AND e.occurred_at < :window_end
          AND e.processing_status IN :processed_statuses
          AND e.event_type IN :conversion_event_types
          AND a.verified = true
        ORDER BY a.tenant_id ASC, e.occurred_at ASC NULLS LAST, a.id ASC
            
                """
            ).strip(),
            relation="attribution_allocations",
            window_key="created_at",
            projection=(
                ProjectedColumn("id", "id::text", "id"),
                ProjectedColumn("tenant_id", "tenant_id::text", "tenant_id"),
                ProjectedColumn("event_id", "event_id::text", "event_id"),
                *_identity(
                    "created_at",
                    "channel_code",
                    "allocated_revenue_cents",
                    "allocation_ratio",
                    "model_type",
                    "model_version",
                    "verified",
                    "verification_source",
                    "verification_timestamp",
                ),
            ),
            membership=(
                MembershipFilter("verified", literal_sql="verified = true"),
            ),
        ),
        "b23_match_verdicts": SourceRelationContract(
            # C19 authoritative SELECT (see select_override).
            select_override=textwrap.dedent(
                """\n            SELECT
                'b23_match_verdicts' AS source_table_discriminator,
                v.id::text AS id,
                v.tenant_id::text AS tenant_id,
                v.attribution_event_id::text AS attribution_event_id,
                v.provider,
                v.canonical_commerce_reference,
                v.status,
                v.match_quality,
                v.attributed_amount_minor,
                v.verified_amount_minor,
                upper(v.currency_code) AS currency_code,
                v.confirmed_at,
                v.adjusted_at,
                v.last_transition_at,
                v.canonical_expected_gross_amount_minor,
                v.canonical_captured_gross_amount_minor,
                v.canonical_net_verified_amount_minor,
                v.discrepancy_amount_minor,
                v.discrepancy_ratio_bps,
                v.discrepancy_band
            FROM public.b23_match_verdicts AS v
            JOIN public.attribution_events AS e
              ON e.tenant_id = v.tenant_id
             AND e.id = v.attribution_event_id
            WHERE v.tenant_id = :tenant_id
              AND e.occurred_at >= :window_start
              AND e.occurred_at < :window_end
              AND e.processing_status IN :processed_statuses
              AND e.event_type IN :conversion_event_types
              AND v.status IN :match_verdict_statuses
            ORDER BY v.tenant_id ASC, e.occurred_at ASC NULLS LAST, v.id ASC
            
                """
            ).strip(),
            relation="b23_match_verdicts",
            window_key="last_transition_at",
            # A verdict enters the snapshot through its financial event, so its
            # width must be measured the same way.  Bounding the walk by
            # last_transition_at instead lost every provider whose verdict was
            # reconciled after the window closed -- the ordinary case for late
            # settlement -- while those verdicts stayed in the snapshot.
            walk_window_predicate=(
                "EXISTS (SELECT 1 FROM public.attribution_events AS window_event"
                " WHERE window_event.tenant_id = {alias}.tenant_id"
                " AND window_event.id = {alias}.attribution_event_id"
                " AND window_event.occurred_at >= :window_start"
                " AND window_event.occurred_at < :window_end)"
            ),
            projection=(
                ProjectedColumn("id", "id::text", "id"),
                ProjectedColumn("tenant_id", "tenant_id::text", "tenant_id"),
                ProjectedColumn(
                    "attribution_event_id",
                    "attribution_event_id::text",
                    "attribution_event_id",
                ),
                *_identity(
                    "provider",
                    "canonical_commerce_reference",
                    "status",
                    "match_quality",
                    "attributed_amount_minor",
                    "verified_amount_minor",
                ),
                ProjectedColumn(
                    "currency_code", "upper(currency_code)", "currency_code"
                ),
                *_identity(
                    "confirmed_at",
                    "adjusted_at",
                    "last_transition_at",
                    "canonical_expected_gross_amount_minor",
                    "canonical_captured_gross_amount_minor",
                    "canonical_net_verified_amount_minor",
                    "discrepancy_amount_minor",
                    "discrepancy_ratio_bps",
                    "discrepancy_band",
                ),
            ),
            membership=(
                _lifecycle(
                    "b23_match_verdicts", "status", "match_verdict_statuses"
                ),
            ),
        ),
        "b23_revenue_events": SourceRelationContract(
            relation="b23_revenue_events",
            window_key="event_occurred_at",
            projection=(
                ProjectedColumn("id", "id::text", "id"),
                ProjectedColumn("tenant_id", "tenant_id::text", "tenant_id"),
                ProjectedColumn(
                    "match_verdict_id", "match_verdict_id::text", "match_verdict_id"
                ),
                *_identity(
                    "provider",
                    "canonical_commerce_reference",
                    "event_type",
                ),
                ProjectedColumn(
                    "currency_code", "upper(currency_code)", "currency_code"
                ),
                *_identity(
                    "event_occurred_at",
                    "captured_amount_minor",
                    "refund_amount_minor",
                    "chargeback_amount_minor",
                    "reversal_amount_minor",
                    "net_effect_sign",
                    "is_gross_capture_correction",
                ),
            ),
            membership=(
                _lifecycle(
                    "b23_revenue_events", "event_type", "revenue_event_types"
                ),
            ),
        ),
    }
)


def source_contracts() -> tuple[SourceRelationContract, ...]:
    return tuple(SOURCE_CONTRACT_AUTHORITY[name] for name in sorted(SOURCE_CONTRACT_AUTHORITY))


def allowed_source_read_models() -> MappingProxyType:
    """The projected column inventory, derived rather than separately declared."""

    return MappingProxyType(
        {
            name: contract.projected_columns()
            for name, contract in SOURCE_CONTRACT_AUTHORITY.items()
        }
    )


def query_params() -> dict[str, tuple[str, ...]]:
    """Expanding bind values for every membership filter across all relations."""

    params: dict[str, tuple[str, ...]] = {}
    for contract in SOURCE_CONTRACT_AUTHORITY.values():
        params.update(contract.bind_params())
    return params

# ``attribution_allocations.verified`` is a boolean predicate rather than an
# IN-list, so it cannot be rendered from the rule the way the others are. It is
# bound by assertion instead, which fails at import if the rule ever stops
# meaning "verified is true" -- the one thing the literal SQL above assumes.
assert LIFECYCLE_INCLUSION_RULES["attribution_allocations.verified"] == (True,), (
    "attribution_allocations membership no longer means verified = true"
)
