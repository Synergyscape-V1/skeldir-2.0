#!/usr/bin/env python3
"""B2.5-P13 C21 / Exit Gate XXI-F: one authority physics from every build path.

Corrective XXI adds a migration *after* the head Corrective XX proved, so XX's
migration-equivalence evidence does not carry: an incremental cluster that
already sat at ``202609021200`` and a cluster built from empty must arrive at
the same authority graph, and the checked-in canonical bootstrap must carry the
same authority objects.

The comparison is catalogue-level and exhaustive over the dimensions that decide
who may assert what: owners, RLS enable/force, policies, triggers, constraints,
function ownership and security flags, table and column grants, function EXECUTE
and role memberships. It then repeats the C21 forbidden/lawful capability
questions directly in each universe, because a catalogue can agree while the
capability it encodes does not.

The canonical bootstrap is dumped ``--no-owner --no-privileges``, so privilege
and ownership dimensions are not expressible in that file at all. Universes
declared ``--structural-only`` are therefore compared on structure, and their
authority objects are asserted to be present, rather than being asked a question
the artefact cannot answer.

Constraint definitions in the canonical universe carry a known, pre-existing
pg_dump text round-trip artefact: ``ANY (ARRAY['x'::varchar, ...]::text[])``
re-renders as ``ANY (ARRAY[('x'::varchar)::text, ...])``. The two are the same
predicate; the difference is how PostgreSQL prints a cast it re-parsed. That
rewriting is recognised and reported, never silently accepted as equality.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

import psycopg2


DIMENSIONS: dict[str, str] = {
    "table_owners": """
        SELECT c.relname, o.rolname
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_roles o ON o.oid = c.relowner
        WHERE n.nspname = 'public' AND c.relkind IN ('r','p','m','v')
        ORDER BY 1, 2
    """,
    "rls_flags": """
        SELECT c.relname, c.relrowsecurity::text, c.relforcerowsecurity::text
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind = 'r'
        ORDER BY 1
    """,
    "policies": """
        SELECT tablename, policyname, permissive, cmd,
               COALESCE((
                   SELECT string_agg(role_name, ',' ORDER BY role_name)
                   FROM unnest(roles) AS role_name
               ), ''),
               COALESCE(qual, ''), COALESCE(with_check, '')
        FROM pg_policies
        WHERE schemaname = 'public'
        ORDER BY 1, 2
    """,
    "triggers": """
        SELECT c.relname, t.tgname, pg_get_triggerdef(t.oid)
        FROM pg_trigger t
        JOIN pg_class c ON c.oid = t.tgrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND NOT t.tgisinternal
        ORDER BY 1, 2
    """,
    "constraints": """
        SELECT c.relname, con.conname, pg_get_constraintdef(con.oid)
        FROM pg_constraint con
        JOIN pg_class c ON c.oid = con.conrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
        ORDER BY 1, 2
    """,
    "functions": """
        SELECT p.proname, pg_get_function_identity_arguments(p.oid), o.rolname,
               p.prosecdef::text, COALESCE(array_to_string(p.proconfig, ','), '')
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        JOIN pg_roles o ON o.oid = p.proowner
        WHERE n.nspname = 'public'
        ORDER BY 1, 2
    """,
    "table_grants": """
        SELECT grantee, table_name,
               string_agg(privilege_type, ',' ORDER BY privilege_type)
        FROM information_schema.role_table_grants
        WHERE table_schema = 'public' AND grantee LIKE 'app%'
        GROUP BY 1, 2 ORDER BY 1, 2
    """,
    "column_grants": """
        SELECT grantee, table_name, column_name,
               string_agg(privilege_type, ',' ORDER BY privilege_type)
        FROM information_schema.column_privileges
        WHERE table_schema = 'public' AND grantee LIKE 'app%'
        GROUP BY 1, 2, 3 ORDER BY 1, 2, 3
    """,
    "function_execute": """
        SELECT r.rolname, p.proname, pg_get_function_identity_arguments(p.oid)
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        CROSS JOIN pg_roles r
        WHERE n.nspname = 'public' AND r.rolname LIKE 'app%'
          AND has_function_privilege(r.rolname, p.oid, 'EXECUTE')
        ORDER BY 1, 2, 3
    """,
    "role_memberships": """
        SELECT m.rolname, r.rolname
        FROM pg_auth_members am
        JOIN pg_roles m ON m.oid = am.member
        JOIN pg_roles r ON r.oid = am.roleid
        WHERE m.rolname LIKE 'app%' OR m.rolname = 'migration_owner'
        ORDER BY 1, 2
    """,
}

STRUCTURAL_DIMENSIONS = ("rls_flags", "policies", "triggers", "constraints")

# The C21 authority objects. Every construction path must carry both.
REQUIRED_TRIGGERS = (
    "trg_b24_dirty_event_authority",
    "trg_trust_issuance_history_immutable",
)

# (role, relation, operation, expected). The two C21 surfaces, asked directly.
CAPABILITY_MATRIX = (
    ("app_user", "b24_dirty_events", "SELECT", True),
    ("app_user", "b24_dirty_events", "INSERT", True),
    ("app_user", "b24_dirty_events", "UPDATE", False),
    ("app_user", "b24_dirty_events", "DELETE", False),
    ("app_worker", "b24_dirty_events", "SELECT", True),
    ("app_worker", "b24_dirty_events", "INSERT", True),
    ("app_worker", "b24_dirty_events", "UPDATE", True),
    ("app_rw", "b24_dirty_events", "UPDATE", False),
    ("app_user", "trust_envelope_issuance_log", "SELECT", True),
    ("app_user", "trust_envelope_issuance_log", "INSERT", True),
    ("app_user", "trust_envelope_issuance_log", "UPDATE", False),
    ("app_user", "trust_envelope_issuance_log", "DELETE", False),
    ("app_rw", "trust_envelope_issuance_log", "UPDATE", False),
    ("app_user", "trust_replay_events", "UPDATE", False),
    ("app_user", "trust_scope_denial_events", "UPDATE", False),
    ("app_user", "trust_access_log", "UPDATE", True),
    ("app_rw", "trust_access_log", "UPDATE", False),
)

# The migration path renders ``ANY ((ARRAY['x'::character varying, ...])::text[])``.
# After a pg_dump round-trip PostgreSQL re-parses the same predicate and prints
# ``ANY (ARRAY[('x'::character varying)::text, ...])`` -- the cast distributes
# over the elements instead of applying to the array. Same predicate, different
# printing; both forms are folded onto one so a real divergence still shows.
_ELEMENT_CAST = re.compile(r"\('(?P<literal>[^']*)'::charactervarying\)::text")
_ARRAY_CAST = re.compile(r"\(ARRAY\[(?P<items>.*?)\]\)::text\[\]")


def _canonicalise_constraint(definition: str) -> str:
    """Erase the pg_dump cast round-trip so real divergence stands out."""

    collapsed = definition.replace(" ", "")
    collapsed = _ELEMENT_CAST.sub(
        lambda match: f"'{match.group('literal')}'::charactervarying", collapsed
    )
    return _ARRAY_CAST.sub(lambda match: f"ARRAY[{match.group('items')}]", collapsed)


def _connect(admin_dsn: str, database: str):
    parts = urlsplit(admin_dsn.replace("postgresql+psycopg2://", "postgresql://"))
    return psycopg2.connect(
        dbname=database,
        host=parts.hostname,
        port=parts.port or 5432,
        user=parts.username,
        password=parts.password,
    )


def _snapshot(admin_dsn: str, database: str) -> dict[str, list[tuple[str, ...]]]:
    conn = _connect(admin_dsn, database)
    try:
        result: dict[str, list[tuple[str, ...]]] = {}
        with conn.cursor() as cursor:
            for name, query in DIMENSIONS.items():
                cursor.execute(query)
                result[name] = [
                    tuple("" if value is None else str(value) for value in row)
                    for row in cursor.fetchall()
                ]
        return result
    finally:
        conn.close()


def _capabilities(admin_dsn: str, database: str) -> dict[str, object]:
    conn = _connect(admin_dsn, database)
    observed: dict[str, object] = {}
    try:
        with conn.cursor() as cursor:
            for role, relation, operation, expected in CAPABILITY_MATRIX:
                cursor.execute(
                    "SELECT has_table_privilege(%s, %s, %s)",
                    (role, f"public.{relation}", operation),
                )
                held = bool(cursor.fetchone()[0])
                observed[f"{role}:{relation}:{operation}"] = {
                    "held": held,
                    "expected": expected,
                    "agrees": held == expected,
                }
            cursor.execute(
                "SELECT tgname FROM pg_trigger WHERE tgname = ANY(%s) ORDER BY 1",
                (list(REQUIRED_TRIGGERS),),
            )
            observed["authority_triggers"] = [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()
    return observed


def _compare(
    baseline: dict[str, list[tuple[str, ...]]],
    other: dict[str, list[tuple[str, ...]]],
    dimensions: tuple[str, ...],
) -> dict[str, object]:
    report: dict[str, object] = {}
    for dimension in dimensions:
        left, right = baseline[dimension], other[dimension]
        identical = left == right
        entry: dict[str, object] = {
            "identical": identical,
            "baseline_rows": len(left),
            "candidate_rows": len(right),
        }
        if not identical and dimension == "constraints":
            left_c = {(a, b, _canonicalise_constraint(c)) for a, b, c in left}
            right_c = {(a, b, _canonicalise_constraint(c)) for a, b, c in right}
            entry["identical_after_cast_normalisation"] = left_c == right_c
            entry["cast_rewrites"] = sum(
                1
                for _, _, definition in right
                if _ELEMENT_CAST.search(definition.replace(" ", ""))
            )
            if left_c != right_c:
                entry["only_in_baseline"] = sorted(left_c - right_c)[:8]
                entry["only_in_candidate"] = sorted(right_c - left_c)[:8]
        elif not identical:
            left_set, right_set = set(left), set(right)
            entry["only_in_baseline"] = sorted(left_set - right_set)[:8]
            entry["only_in_candidate"] = sorted(right_set - left_set)[:8]
        report[dimension] = entry
    return report


def _dimension_ok(entry: dict[str, object]) -> bool:
    if entry.get("identical"):
        return True
    return bool(entry.get("identical_after_cast_normalisation"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--admin-dsn", required=True)
    parser.add_argument(
        "--universe",
        action="append",
        required=True,
        metavar="NAME=DATABASE",
        help="First --universe is the baseline; every later one is compared to it.",
    )
    parser.add_argument(
        "--structural-only",
        action="append",
        default=[],
        help="Universe names built from an artefact that carries no privileges.",
    )
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    universes: list[tuple[str, str]] = []
    for raw in args.universe:
        name, _, database = raw.partition("=")
        if not name or not database:
            print(f"[c21-universes] bad --universe value: {raw!r}")
            return 2
        universes.append((name, database))
    if len(universes) < 2:
        print("[c21-universes] need a baseline and at least one candidate")
        return 2

    structural_only = set(args.structural_only)
    baseline_name, baseline_db = universes[0]
    snapshots = {name: _snapshot(args.admin_dsn, db) for name, db in universes}

    report: dict[str, object] = {"baseline": baseline_name}
    failed = False

    for name, database in universes[1:]:
        dimensions = (
            STRUCTURAL_DIMENSIONS
            if name in structural_only
            else tuple(DIMENSIONS)
        )
        comparison = _compare(snapshots[baseline_name], snapshots[name], dimensions)
        report[f"{baseline_name}_vs_{name}"] = comparison
        for dimension, entry in comparison.items():
            if not _dimension_ok(entry):
                failed = True
                print(f"[c21-universes] DIVERGENCE {name}.{dimension}")
                print(json.dumps(entry, indent=2, default=str))

    capabilities: dict[str, object] = {}
    for name, database in universes:
        observed = _capabilities(args.admin_dsn, database)
        capabilities[name] = observed
        present = observed["authority_triggers"]
        if list(present) != sorted(REQUIRED_TRIGGERS):
            failed = True
            print(f"[c21-universes] {name} is missing C21 authority triggers: {present}")
        if name in structural_only:
            # A --no-privileges artefact cannot express grants; the structural
            # authority objects above are what it is asked for.
            continue
        for key, value in observed.items():
            if key == "authority_triggers":
                continue
            if not value["agrees"]:
                failed = True
                print(f"[c21-universes] {name} capability mismatch {key}: {value}")
    report["capabilities"] = capabilities
    report["verdict"] = "DIVERGENT" if failed else "EQUIVALENT"

    if args.out:
        path = Path(args.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8"
        )
        print(f"[c21-universes] wrote {path}")

    for name, _ in universes[1:]:
        summary = report[f"{baseline_name}_vs_{name}"]
        agreed = sum(1 for entry in summary.values() if _dimension_ok(entry))
        print(
            f"[c21-universes] {baseline_name} vs {name}:"
            f" {agreed}/{len(summary)} dimensions equivalent"
        )
    print(f"[c21-universes] verdict={report['verdict']}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
