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
        for operation in ("insert", "update", "delete"):
            names.append(f"b24_invalidate_{relation}_{operation}")
    return tuple(names)


def trigger_names() -> tuple[str, ...]:
    return tuple(f"trg_{name}" for name in function_names())


def render_source_invalidation_ddl() -> str:
    """Render every authority-derived invalidation function and trigger."""

    blocks: list[str] = []
    for relation in governed_relations():
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
        for operation in ("insert", "update", "delete"):
            name = f"b24_invalidate_{relation}_{operation}"
            statements.append(
                f"DROP TRIGGER IF EXISTS trg_{name} ON public.{relation};"
            )
            statements.append(f"DROP FUNCTION IF EXISTS public.{name}();")
    return "\n".join(statements) + "\n"
