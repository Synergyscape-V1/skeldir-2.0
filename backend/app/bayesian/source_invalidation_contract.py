"""B2.5-P13 source-change invalidation DDL, rendered from the source authority.

C7 introduced these triggers and proved they fire atomically. C8 corrects what
they emit. Two defects made the mechanism epistemically disconnected from the
truth it was supposed to protect:

* the model identity was inherited from ``dirty_marker``'s B2.4-P3 defaults
  (``mmm``), an identity the Trust confidence read model refuses, so no
  obligation this mechanism created could ever reach a projectable fit; and
* the membership and projection rules were transcribed by hand beside the
  authoritative source queries rather than derived from them.

Both are now structural. The rendering inputs come from
``source_contract_authority`` -- the same object that renders the canonical
snapshot SELECT -- and the emitted identity comes from ``model_identity``, which
declares exactly one identity production may emit.

A dirty event records the SCOPE of a source change: tenant, model family, and
the day interval the change landed in. It deliberately does not attempt to name
the fit windows it affects, because a writer cannot know them and fanning out
across a historical fit universe at write time is unbounded. The affected-fit
relation is instead evaluated at read time by bounded window overlap; see
``b24_dirty_event_stales_fit``.
"""

from __future__ import annotations

from typing import cast

from app.bayesian.input_contract import LIFECYCLE_INCLUSION_RULES
from app.bayesian.model_identity import active_identity
from app.bayesian.source_contract_authority import (
    SOURCE_CONTRACT_AUTHORITY,
    source_contracts,
)


SOURCE_INVALIDATION_CONTRACT_VERSION = "b25-p13-c8-source-invalidation-v2"

# Relations whose invalidation is deliberately not trigger-enforced would live
# here with a written reason. It is empty: every B2.4 source relation is
# physically covered.
GOVERNED_INVALIDATION_EXCEPTIONS: tuple[str, ...] = ()


def governed_relations() -> tuple[str, ...]:
    return tuple(
        contract.relation
        for contract in source_contracts()
        if contract.relation not in GOVERNED_INVALIDATION_EXCEPTIONS
    )


# C19: allocation and verdict changes invalidate the governed daily window of
# the underlying immutable financial event, not the database write/transition
# clock. These two relations carry the financial-window surface; every other
# governed relation keeps the write-clock statement-level surface.
FINANCIAL_WINDOW_RELATIONS: frozenset[str] = frozenset(
    {"attribution_allocations", "b23_match_verdicts"}
)


def financial_window_relations() -> tuple[str, ...]:
    return tuple(
        relation
        for relation in governed_relations()
        if relation in FINANCIAL_WINDOW_RELATIONS
    )


def write_clock_relations() -> tuple[str, ...]:
    return tuple(
        relation
        for relation in governed_relations()
        if relation not in FINANCIAL_WINDOW_RELATIONS
    )


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


def _emit(contract, body: str) -> str:
    identity = active_identity()
    header = _INSERT_HEADER.format(
        model_type=identity.model_type,
        model_version=identity.model_version,
        relation=contract.relation,
    )
    indented = "\n".join(
        f"    {line}" if line else "" for line in body.strip("\n").split("\n")
    )
    return f"{header}\n{indented}\n) affected;"


def _single_table_body(contract, table: str) -> str:
    alias = "row_set"
    return (
        "SELECT DISTINCT\n"
        f"    {alias}.tenant_id AS tenant_id,\n"
        f"    {contract.bucket(alias)} AS window_start\n"
        f"FROM {table} {alias}\n"
        f"WHERE {contract.member_predicate(alias)}"
    )


def _update_body(contract) -> str:
    changed = (
        f"({contract.member_predicate('new_row')}) "
        f"IS DISTINCT FROM ({contract.member_predicate('old_row')})\n"
        f"    OR {contract.projected_row('new_row')}\n"
        f"       IS DISTINCT FROM {contract.projected_row('old_row')}"
    )
    guard = (
        f"WHERE (({contract.member_predicate('new_row')})"
        f" OR ({contract.member_predicate('old_row')}))\n"
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
        f"           {contract.bucket('new_row')} AS window_start\n"
        f"    {join.replace(chr(10), chr(10) + '    ').rstrip()}\n"
        f"    {guard.replace(chr(10), chr(10) + '    ')}\n"
        "    UNION\n"
        "    SELECT old_row.tenant_id AS tenant_id,\n"
        f"           {contract.bucket('old_row')} AS window_start\n"
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
    for relation in governed_relations():
        if relation in FINANCIAL_WINDOW_RELATIONS:
            prefix = str(_FINANCIAL_WINDOW_SPECS[relation]["surface_prefix"])
            names.append(f"b24_mark_{prefix}_financial_window_dirty")
            continue
        for operation in ("insert", "update", "delete"):
            names.append(f"b24_invalidate_{relation}_{operation}")
    return tuple(names)


def trigger_names() -> tuple[str, ...]:
    return tuple(f"trg_{name}" for name in function_names())


_FINANCIAL_WINDOW_SPECS: dict[str, dict[str, object]] = {
    "attribution_allocations": {
        "surface_prefix": "allocation",
        "changed_columns": (
            "event_id",
            "tenant_id",
            "channel_code",
            "allocated_revenue_cents",
            "allocation_ratio",
            "model_type",
            "model_version",
            "verified",
            "verification_source",
            "verification_timestamp",
        ),
        "event_link_column": "event_id",
        "authority_gate": "verified_column",
    },
    "b23_match_verdicts": {
        "surface_prefix": "verdict",
        "changed_columns": (
            "attribution_event_id",
            "tenant_id",
            "status",
            "canonical_net_verified_amount_minor",
            "currency_code",
            "last_transition_at",
        ),
        "event_link_column": "attribution_event_id",
        "authority_gate": "status_membership",
    },
}


def _sql_in_list(values: tuple[str, ...] | list[str]) -> str:
    rendered = ", ".join(f"'{value}'" for value in values)
    return f"({rendered})"


def _financial_window_function(relation: str) -> str:
    spec = _FINANCIAL_WINDOW_SPECS[relation]
    columns = cast(tuple[str, ...], spec["changed_columns"])
    link = str(spec["event_link_column"])
    identity = active_identity()
    new_tuple = ",\n       ".join(f"NEW.{column}" for column in columns)
    old_tuple = ",\n       ".join(f"OLD.{column}" for column in columns)
    if spec["authority_gate"] == "verified_column":
        authority_gate = """IF NOT COALESCE(
            CASE WHEN TG_OP = 'DELETE' THEN OLD.verified
                 WHEN TG_OP = 'INSERT' THEN NEW.verified
                 ELSE OLD.verified OR NEW.verified END,
            false
        ) THEN
            RETURN NULL;
        END IF;"""
    else:
        statuses = _sql_in_list(
            list(LIFECYCLE_INCLUSION_RULES["b23_match_verdicts.status"])
        )
        authority_gate = f"""IF NOT (
            (TG_OP <> 'INSERT' AND OLD.status IN {statuses})
            OR
            (TG_OP <> 'DELETE' AND NEW.status IN {statuses})
        ) THEN
            RETURN NULL;
        END IF;"""
    processed = _sql_in_list(
        list(LIFECYCLE_INCLUSION_RULES["attribution_events.processing_status"])
    )
    event_types = _sql_in_list(
        list(LIFECYCLE_INCLUSION_RULES["attribution_events.event_type"])
    )
    prefix = str(spec["surface_prefix"])
    return (
        "CREATE OR REPLACE FUNCTION public."
        f"b24_mark_{prefix}_financial_window_dirty()\n"
        "RETURNS trigger\n"
        "LANGUAGE plpgsql\n"
        "SECURITY DEFINER\n"
        "SET search_path = pg_catalog, public\n"
        "AS $BODY$\n"
        "DECLARE\n"
        f"    source_row public.{relation}%ROWTYPE;\n"
        "    financial_window_start timestamptz;\n"
        "BEGIN\n"
        "    source_row := CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;\n"
        "    IF TG_OP = 'UPDATE' AND\n"
        f"       ({new_tuple})\n"
        "       IS NOT DISTINCT FROM\n"
        f"       ({old_tuple}) THEN\n"
        "        RETURN NULL;\n"
        "    END IF;\n"
        f"    {authority_gate}\n"
        "\n"
        "    SELECT date_trunc('day', event.occurred_at)\n"
        "      INTO financial_window_start\n"
        "      FROM public.attribution_events AS event\n"
        "     WHERE event.tenant_id = source_row.tenant_id\n"
        f"       AND event.id = source_row.{link}\n"
        f"       AND event.processing_status IN {processed}\n"
        f"       AND event.event_type IN {event_types};\n"
        "    IF financial_window_start IS NULL THEN\n"
        "        RETURN NULL;\n"
        "    END IF;\n"
        "\n"
        "    INSERT INTO public.b24_dirty_events (\n"
        "        tenant_id, model_type, model_version,\n"
        "        source_window_start, source_window_end,\n"
        "        dirty_reason, source_family, event_hash, source_event_id,\n"
        "        observed_at, status, created_at, updated_at\n"
        "    ) VALUES (\n"
        "        source_row.tenant_id,\n"
        f"        '{identity.model_type}', '{identity.model_version}',\n"
        "        financial_window_start, financial_window_start + interval '1 day',\n"
        f"        '{relation}_financial_event_changed',\n"
        f"        '{relation}',\n"
        "        encode(sha256(convert_to(\n"
        f"            'c19|{relation}|' || source_row.tenant_id::text || '|'\n"
        "            || source_row.id::text || '|' || TG_OP || '|'\n"
        "            || transaction_timestamp()::text || '|' || txid_current()::text,\n"
        "            'UTF8')), 'hex'),\n"
        f"        left('{relation}:' || source_row.id::text, 128),\n"
        "        transaction_timestamp(), 'pending',\n"
        "        transaction_timestamp(), transaction_timestamp()\n"
        "    );\n"
        "    RETURN NULL;\n"
        "END;\n"
        "$BODY$;"
    )


def _financial_window_trigger(relation: str) -> str:
    prefix = str(_FINANCIAL_WINDOW_SPECS[relation]["surface_prefix"])
    name = f"b24_mark_{prefix}_financial_window_dirty"
    return (
        f"DROP TRIGGER IF EXISTS trg_{name} ON public.{relation};\n"
        f"CREATE TRIGGER trg_{name}\n"
        f"AFTER INSERT OR UPDATE OR DELETE ON public.{relation}\n"
        "FOR EACH ROW\n"
        f"EXECUTE FUNCTION public.{name}();"
    )


def render_source_invalidation_ddl(
    relations: tuple[str, ...] | None = None,
) -> str:
    """Render every authority-derived invalidation function and trigger.

    ``relations`` selects a carrier subset: the write-clock statement-level
    surface, the C19 financial-window surface, or (default) both.
    """

    selected = governed_relations() if relations is None else relations
    blocks: list[str] = []
    for relation in selected:
        if relation in FINANCIAL_WINDOW_RELATIONS:
            blocks.append(_financial_window_function(relation))
            blocks.append(_financial_window_trigger(relation))
            continue
        contract = SOURCE_CONTRACT_AUTHORITY[relation]
        insert_fn = f"b24_invalidate_{relation}_insert"
        update_fn = f"b24_invalidate_{relation}_update"
        delete_fn = f"b24_invalidate_{relation}_delete"
        blocks.append(
            _function(insert_fn, _emit(contract, _single_table_body(contract, "new_rows")))
        )
        blocks.append(_function(update_fn, _emit(contract, _update_body(contract))))
        blocks.append(
            _function(delete_fn, _emit(contract, _single_table_body(contract, "old_rows")))
        )
        blocks.append(
            f"DROP TRIGGER IF EXISTS trg_{insert_fn} ON public.{relation};\n"
            f"CREATE TRIGGER trg_{insert_fn}\n"
            f"AFTER INSERT ON public.{relation}\n"
            "REFERENCING NEW TABLE AS new_rows\n"
            f"FOR EACH STATEMENT EXECUTE FUNCTION public.{insert_fn}();"
        )
        blocks.append(
            f"DROP TRIGGER IF EXISTS trg_{update_fn} ON public.{relation};\n"
            f"CREATE TRIGGER trg_{update_fn}\n"
            f"AFTER UPDATE ON public.{relation}\n"
            "REFERENCING OLD TABLE AS old_rows NEW TABLE AS new_rows\n"
            f"FOR EACH STATEMENT EXECUTE FUNCTION public.{update_fn}();"
        )
        blocks.append(
            f"DROP TRIGGER IF EXISTS trg_{delete_fn} ON public.{relation};\n"
            f"CREATE TRIGGER trg_{delete_fn}\n"
            f"AFTER DELETE ON public.{relation}\n"
            "REFERENCING OLD TABLE AS old_rows\n"
            f"FOR EACH STATEMENT EXECUTE FUNCTION public.{delete_fn}();"
        )
    return "\n\n".join(blocks) + "\n"


def render_drop_ddl() -> str:
    """Reverse the invalidation surface for a clean downgrade."""

    statements: list[str] = []
    for relation in governed_relations():
        if relation in FINANCIAL_WINDOW_RELATIONS:
            prefix = str(_FINANCIAL_WINDOW_SPECS[relation]["surface_prefix"])
            name = f"b24_mark_{prefix}_financial_window_dirty"
            statements.append(
                f"DROP TRIGGER IF EXISTS trg_{name} ON public.{relation};"
            )
            statements.append(f"DROP FUNCTION IF EXISTS public.{name}();")
            continue
        for operation in ("insert", "update", "delete"):
            name = f"b24_invalidate_{relation}_{operation}"
            statements.append(
                f"DROP TRIGGER IF EXISTS trg_{name} ON public.{relation};"
            )
            statements.append(f"DROP FUNCTION IF EXISTS public.{name}();")
    return "\n".join(statements) + "\n"
