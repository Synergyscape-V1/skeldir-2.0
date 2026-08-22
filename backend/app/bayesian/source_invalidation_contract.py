"""B2.5-P13 C7 source-change invalidation authority derived from the B2.4 contract.

The canonical P13 question is not "did someone remember to call the dirty
marker" but:

    Would this committed state transition change the bytes produced by the
    authoritative B2.4 source snapshot?

That question is mechanically decidable from the source contract itself.  Each
B2.4 source relation contributes rows to the snapshot only when it satisfies a
membership predicate, and contributes bytes only through a fixed projection.
A committed mutation therefore changes snapshot bytes exactly when it moves a
row into or out of the member set, or changes a projected column of a member
row.

This module renders that decision procedure as PostgreSQL statement-level
triggers.  Invalidation stops being call-site discipline and becomes a physical
property of writing to the relation: a future production writer cannot change
canonical source truth without the invalidation obligation committing in the
same transaction, because there is no code path between the write and the
trigger.

``render_source_invalidation_ddl`` is the single authority.  The C7 migration
embeds its rendered output verbatim and the C7 closure gate re-renders and
diffs, so contract drift cannot land silently.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from app.bayesian.dirty_marker import (
    DEFAULT_BAYESIAN_MODEL_TYPE,
    DEFAULT_BAYESIAN_MODEL_VERSION,
)
from app.bayesian.input_contract import ALLOWED_SOURCE_READ_MODELS


SOURCE_INVALIDATION_CONTRACT_VERSION = "b25-p13-c7-source-invalidation-v1"

# The window key is the column the authoritative B2.4 source query ranges over
# for that relation, and the membership predicate is that query's non-window
# filter.  Both are transcribed from
# ``app.bayesian.source_snapshot._SOURCE_QUERIES`` / ``_QUERY_PARAMS`` and the
# C7 gate asserts they still agree with it.
SOURCE_INVALIDATION_CONTRACT = MappingProxyType(
    {
        "attribution_events": MappingProxyType(
            {
                "window_key": "occurred_at",
                "membership_predicate": (
                    "{alias}.processing_status IN ('processed') "
                    "AND {alias}.event_type IN ('conversion')"
                ),
            }
        ),
        "attribution_allocations": MappingProxyType(
            {
                "window_key": "created_at",
                "membership_predicate": "{alias}.verified = true",
            }
        ),
        "b23_match_verdicts": MappingProxyType(
            {
                "window_key": "last_transition_at",
                "membership_predicate": (
                    "{alias}.status IN ('matched_confirmed', 'adjusted')"
                ),
            }
        ),
        "b23_revenue_events": MappingProxyType(
            {
                "window_key": "event_occurred_at",
                "membership_predicate": (
                    "{alias}.event_type IN ("
                    "'payment_capture', 'partial_refund', 'full_refund', "
                    "'chargeback_lost', 'chargeback_won', 'reversal')"
                ),
            }
        ),
    }
)

# Relations whose contract projection is derived but whose invalidation is
# deliberately not trigger-enforced would live here with a written reason.
# It is empty: every B2.4 source relation is physically covered.
GOVERNED_INVALIDATION_EXCEPTIONS: tuple[str, ...] = ()


@dataclass(frozen=True)
class SourceRelationInvalidation:
    """One relation's decidable snapshot-membership and byte-identity rule."""

    relation: str
    window_key: str
    membership_predicate: str
    projection: tuple[str, ...]

    def member(self, alias: str) -> str:
        """Never-NULL membership test for one row of ``relation``."""

        predicate = self.membership_predicate.format(alias=alias)
        return (
            f"COALESCE({predicate}, false) "
            f"AND {alias}.{self.window_key} IS NOT NULL"
        )

    def projected_row(self, alias: str) -> str:
        """The exact byte-bearing tuple the B2.4 snapshot reads."""

        columns = ", ".join(f"{alias}.{column}" for column in self.projection)
        return f"({columns})"

    def bucket(self, alias: str) -> str:
        return f"date_trunc('day', {alias}.{self.window_key})"


def source_relations() -> tuple[SourceRelationInvalidation, ...]:
    """Derive every governed relation from the B2.4 source contract."""

    relations: list[SourceRelationInvalidation] = []
    for relation in sorted(ALLOWED_SOURCE_READ_MODELS):
        if relation in GOVERNED_INVALIDATION_EXCEPTIONS:
            continue
        rule = SOURCE_INVALIDATION_CONTRACT[relation]
        relations.append(
            SourceRelationInvalidation(
                relation=relation,
                window_key=str(rule["window_key"]),
                membership_predicate=str(rule["membership_predicate"]),
                projection=tuple(ALLOWED_SOURCE_READ_MODELS[relation]),
            )
        )
    return tuple(relations)


_INSERT_HEADER = """\
INSERT INTO public.b24_dirty_events (
    tenant_id, model_type, model_version,
    source_window_start, source_window_end,
    dirty_reason, source_family, event_hash, source_event_id,
    observed_at, status, created_at, updated_at
)
SELECT
    affected.tenant_id,
    '{model_type}',
    '{model_version}',
    affected.window_start,
    affected.window_start + interval '1 day',
    '{relation}_snapshot_changed',
    '{relation}',
    encode(sha256(convert_to(
        '{relation}|' || affected.tenant_id::text || '|'
        || affected.window_start::text, 'UTF8')), 'hex'),
    left('{relation}:' || affected.window_start::text, 128),
    now(),
    'pending',
    now(),
    now()
FROM ("""


def _emit(rule: SourceRelationInvalidation, body: str) -> str:
    header = _INSERT_HEADER.format(
        model_type=DEFAULT_BAYESIAN_MODEL_TYPE,
        model_version=DEFAULT_BAYESIAN_MODEL_VERSION,
        relation=rule.relation,
    )
    indented = "\n".join(
        f"    {line}" if line else "" for line in body.strip("\n").split("\n")
    )
    return f"{header}\n{indented}\n) affected;"


def _single_table_body(rule: SourceRelationInvalidation, table: str) -> str:
    alias = "row_set"
    return (
        "SELECT DISTINCT\n"
        f"    {alias}.tenant_id AS tenant_id,\n"
        f"    {rule.bucket(alias)} AS window_start\n"
        f"FROM {table} {alias}\n"
        f"WHERE {rule.member(alias)}"
    )


def _update_body(rule: SourceRelationInvalidation) -> str:
    changed = (
        f"({rule.member('new_row')}) IS DISTINCT FROM ({rule.member('old_row')})\n"
        f"    OR {rule.projected_row('new_row')}\n"
        f"       IS DISTINCT FROM {rule.projected_row('old_row')}"
    )
    guard = (
        f"WHERE (({rule.member('new_row')}) OR ({rule.member('old_row')}))\n"
        f"  AND (\n"
        f"    {changed}\n"
        f"  )"
    )
    join = (
        "FROM new_rows new_row\n"
        "JOIN old_rows old_row ON old_row.id = new_row.id\n"
    )
    return (
        "SELECT DISTINCT tenant_id, window_start FROM (\n"
        "    SELECT new_row.tenant_id AS tenant_id,\n"
        f"           {rule.bucket('new_row')} AS window_start\n"
        f"    {join.replace(chr(10), chr(10) + '    ').rstrip()}\n"
        f"    {guard.replace(chr(10), chr(10) + '    ')}\n"
        "    UNION\n"
        "    SELECT old_row.tenant_id AS tenant_id,\n"
        f"           {rule.bucket('old_row')} AS window_start\n"
        f"    {join.replace(chr(10), chr(10) + '    ').rstrip()}\n"
        f"    {guard.replace(chr(10), chr(10) + '    ')}\n"
        ") both_buckets\n"
        "WHERE window_start IS NOT NULL"
    )


def _function(name: str, body: str) -> str:
    return (
        f"CREATE OR REPLACE FUNCTION public.{name}()\n"
        "RETURNS trigger\n"
        "LANGUAGE plpgsql\n"
        "SECURITY DEFINER\n"
        "SET search_path = public, pg_temp\n"
        "AS $b24_invalidation$\n"
        "BEGIN\n"
        + "\n".join(f"    {line}" if line else "" for line in body.split("\n"))
        + "\n    RETURN NULL;\n"
        "END\n"
        "$b24_invalidation$;"
    )


def function_names() -> tuple[str, ...]:
    names: list[str] = []
    for rule in source_relations():
        for operation in ("insert", "update", "delete"):
            names.append(f"b24_invalidate_{rule.relation}_{operation}")
    return tuple(names)


def trigger_names() -> tuple[str, ...]:
    names: list[str] = []
    for rule in source_relations():
        for operation in ("insert", "update", "delete"):
            names.append(f"trg_b24_invalidate_{rule.relation}_{operation}")
    return tuple(names)


def render_source_invalidation_ddl() -> str:
    """Render every contract-derived invalidation function and trigger."""

    blocks: list[str] = []
    for rule in source_relations():
        insert_fn = f"b24_invalidate_{rule.relation}_insert"
        update_fn = f"b24_invalidate_{rule.relation}_update"
        delete_fn = f"b24_invalidate_{rule.relation}_delete"
        blocks.append(
            _function(insert_fn, _emit(rule, _single_table_body(rule, "new_rows")))
        )
        blocks.append(_function(update_fn, _emit(rule, _update_body(rule))))
        blocks.append(
            _function(delete_fn, _emit(rule, _single_table_body(rule, "old_rows")))
        )
        blocks.append(
            f"DROP TRIGGER IF EXISTS trg_{insert_fn} ON public.{rule.relation};\n"
            f"CREATE TRIGGER trg_{insert_fn}\n"
            f"AFTER INSERT ON public.{rule.relation}\n"
            "REFERENCING NEW TABLE AS new_rows\n"
            f"FOR EACH STATEMENT EXECUTE FUNCTION public.{insert_fn}();"
        )
        blocks.append(
            f"DROP TRIGGER IF EXISTS trg_{update_fn} ON public.{rule.relation};\n"
            f"CREATE TRIGGER trg_{update_fn}\n"
            f"AFTER UPDATE ON public.{rule.relation}\n"
            "REFERENCING OLD TABLE AS old_rows NEW TABLE AS new_rows\n"
            f"FOR EACH STATEMENT EXECUTE FUNCTION public.{update_fn}();"
        )
        blocks.append(
            f"DROP TRIGGER IF EXISTS trg_{delete_fn} ON public.{rule.relation};\n"
            f"CREATE TRIGGER trg_{delete_fn}\n"
            f"AFTER DELETE ON public.{rule.relation}\n"
            "REFERENCING OLD TABLE AS old_rows\n"
            f"FOR EACH STATEMENT EXECUTE FUNCTION public.{delete_fn}();"
        )
    return "\n\n".join(blocks) + "\n"


def render_drop_ddl() -> str:
    """Reverse the invalidation surface for a clean C7 downgrade."""

    statements: list[str] = []
    for rule in source_relations():
        for operation in ("insert", "update", "delete"):
            name = f"b24_invalidate_{rule.relation}_{operation}"
            statements.append(
                f"DROP TRIGGER IF EXISTS trg_{name} ON public.{rule.relation};"
            )
            statements.append(f"DROP FUNCTION IF EXISTS public.{name}();")
    return "\n".join(statements) + "\n"
