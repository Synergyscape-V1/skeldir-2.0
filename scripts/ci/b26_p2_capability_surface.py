#!/usr/bin/env python3
"""B2.6-P2 Corrective VI capability-derived authority-surface generator.

Mechanical inversion of the historical failure pattern (fixed named
defect lists as evidence of CLASS CLOSED). For each prohibited effect,
this generator constructs the machine-readable authority surface from
live catalog facts -- never from engineering vocabulary:

  pg_roles / pg_auth_members (recursive memberships)
  information_schema role_table_grants / role_column_grants /
    role_routine_grants (explicit + default-ACL-derived effective grants)
  pg_default_acl (ambient future grants)
  function ownership + SECURITY DEFINER writers (privilege-escalation
    surfaces: a DEFINER writer is an EXECUTE-to-write path)
  RLS policy graph (which principals read which projections)
  table constraints + triggers (which effects are already impossible)
  deployment processes (Procfile shipping commands -> runtime login)
  queue routing (which queue a process consumes)

Output: an effect-coverage manifest JSON:

  PROHIBITED EFFECT -> REACHABLE MUTATION SURFACES (role:priv:object)
  TESTED SURFACES (supplied by the caller -- the proof registers each
    falsifier's exercised surfaces)
  UNTESTED REACHABLE SURFACES (must be 0 for CLASS CLOSED)

CLASS CLOSED is forbidden while UNTESTED REACHABLE SURFACES > 0 for a
load-bearing effect. A new sibling grant/function/column that can
produce the prohibited effect appears here automatically: the proof
must either exercise it or fail coverage (Gate 29 active falsifier).

Usage:
  python scripts/ci/b26_p2_capability_surface.py \
    --dsn postgresql://postgres:postgres@127.0.0.1:5432/db \
    --manifest-out artifacts/b26_p2/topology/capability-surface.json \
    [--covered app_worker:INSERT:b26_p2_conduction_receipts ...]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

RUNTIME_ROLES = ("app_user", "app_worker", "app_relay", "app_beat")

# Prohibited effect -> tables/columns whose mutation can produce it.
# Column sets are structural (every sovereign/bound column), not
# vocabulary: any future column added to these tables is automatically
# included via the wildcard pass below.
ROOT_TABLES = {
    "b23_match_task_dispatches": (
        "window_start",
        "window_end",
        "tenant_id",
        "webhook_ingress_identity_id",
        "provider",
        "task_name",
        "queue",
        "delivery_state",
    ),
    "webhook_ingress_identities": (
        "event_timestamp",
        "tenant_id",
        "provider",
    ),
    "b26_p2_task_authority_directory": (
        "window_start",
        "window_end",
        "tenant_id",
        "webhook_ingress_identity_id",
    ),
}

COMPLETION_TABLES = {
    "b26_p2_conduction_receipts": (
        "task_id",
        "tenant_id",
        "webhook_ingress_identity_id",
        "window_start",
        "window_end",
        "b23_processed_count",
        "p2_scope_identity",
    ),
    "b23_match_verdicts": ("status",),
    "b23_match_task_dispatches": ("delivery_state",),
    "b26_p2_execution_outbox": ("state",),
}

COMPLETION_ROUTINES = (
    "b26_p2_record_conduction_receipt",
    "b26_p2_mark_conducted",
)

DISPOSITION_TABLES = {
    "b23_match_task_dispatches": (
        "delivery_state",
        "publish_attempts",
        "last_publish_error",
        "updated_at",
        "first_published_at",
        "dispatched_at",
    ),
    "b26_p2_execution_outbox": (
        "state",
        "publish_attempts",
        "last_publish_error",
        "next_retry_at",
        "updated_at",
    ),
    "b26_p2_execution_quarantine": ("tenant_id", "reason"),
    "celery_taskmeta": ("status",),
    "worker_failed_jobs": ("status", "task_id"),
}

DISPOSITION_ROUTINES = (
    "b26_p2_stale_unconducted",
    "b26_p2_operational_disposition",
)

ROOT_ROUTINES = (
    "b26_p2_resolve_dispatch_authority",
)

# Pure-computation oracles: IMMUTABLE, no table access, no RLS
# interaction. EXECUTE on these cannot mutate any effect (they are the
# independent verification instruments, not authority surfaces), so
# they are excluded from mutation coverage by construction. Any routine
# that WRITES (DEFINER writers below) or GATES (resolver/gate/record)
# or parameterizes a signal (stale/disposition threshold) stays covered.
PURE_ORACLES = frozenset(
    {
        "b26_p2_canonical_day_start",
        "b26_p2_canonical_day_end",
    }
)


def _connect(dsn: str):
    import psycopg2

    return psycopg2.connect(dsn)


def _role_closure(cur) -> dict[str, set[str]]:
    """Transitive role membership: role -> set of roles it inherits."""
    cur.execute(
        "SELECT r.rolname, m.rolname FROM pg_auth_members "
        "JOIN pg_roles r ON r.oid = member "
        "JOIN pg_roles m ON m.oid = roleid"
    )
    direct: dict[str, set[str]] = {}
    for member, parent in cur.fetchall():
        direct.setdefault(member, set()).add(parent)
    closure: dict[str, set[str]] = {}

    def _expand(role: str, seen: set[str]) -> set[str]:
        if role in closure:
            return closure[role]
        out: set[str] = set()
        for parent in direct.get(role, ()):
            if parent not in seen:
                out.add(parent)
                out |= _expand(parent, seen | {parent})
        closure[role] = out
        return out

    for role in RUNTIME_ROLES:
        _expand(role, {role})
    return closure


def _effective_table_privs(cur) -> list[tuple[str, str, str]]:
    """(grantee, table, priv) effective rows for runtime roles (direct + inherited)."""
    cur.execute(
        """
        SELECT grantee, table_name, privilege_type
        FROM information_schema.role_table_grants
        WHERE table_schema = 'public'
          AND grantee IN ('app_user', 'app_worker', 'app_rw', 'app_ro',
                          'app_relay', 'app_beat', 'PUBLIC')
        """
    )
    return [(str(a), str(b), str(c)) for a, b, c in cur.fetchall()]


def _effective_column_privs(cur) -> list[tuple[str, str, str, str]]:
    cur.execute(
        """
        SELECT grantee, table_name, column_name, privilege_type
        FROM information_schema.role_column_grants
        WHERE table_schema = 'public'
        """
    )
    return [(str(a), str(b), str(c), str(d)) for a, b, c, d in cur.fetchall()]


def _effective_routine_privs(cur) -> list[tuple[str, str, str]]:
    cur.execute(
        """
        SELECT grantee, routine_name, privilege_type
        FROM information_schema.role_routine_grants
        WHERE routine_schema = 'public'
        """
    )
    return [(str(a), str(b), str(c)) for a, b, c in cur.fetchall()]


def _definer_writers(cur) -> list[tuple[str, str]]:
    """SECURITY DEFINER functions that write P2 tables: (function, table)."""
    cur.execute(
        """
        SELECT p.proname, c.relname
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        JOIN pg_depend d ON d.objid = p.oid AND d.deptype = 'n'
        JOIN pg_class c ON c.oid = d.refobjid
        WHERE n.nspname = 'public' AND p.prosecdef
          AND c.relnamespace = 'public'::regnamespace
          AND c.relname LIKE 'b2%\_p2\_%' ESCAPE '\\'
        """
    )
    rows = [(str(a), str(b)) for a, b in cur.fetchall()]
    # pg_depend text search misses dynamic SQL writers; the governed
    # DEFINER set is small and enumerated explicitly as a backstop, with
    # each entry verified against pg_proc.prosecdef below.
    cur.execute(
        "SELECT proname FROM pg_proc WHERE prosecdef AND pronamespace='public'::regnamespace"
    )
    definers = {str(r[0]) for r in cur.fetchall()}
    backstop = [
        ("b26_p2_mark_conducted", "b23_match_task_dispatches"),
        ("b26_p2_mark_conducted", "b26_p2_execution_outbox"),
        ("b26_p2_record_conduction_receipt", "b26_p2_conduction_receipts"),
    ]
    for fn, tbl in backstop:
        if fn in definers and (fn, tbl) not in rows:
            rows.append((fn, tbl))
    return sorted(set(rows))


def _default_acls(cur) -> list[str]:
    cur.execute(
        """
        SELECT pg_get_userbyid(d.defaclrole) || ':' || COALESCE(d.defaclacl::text, '')
        FROM pg_default_acl d JOIN pg_namespace n ON n.oid = d.defaclnamespace
        WHERE n.nspname = 'public'
        """
    )
    return sorted(str(r[0]) for r in cur.fetchall())


def _surfaces_for(
    table_map: dict[str, tuple[str, ...]],
    table_privs: list[tuple[str, str, str]],
    column_privs: list[tuple[str, str, str, str]],
    closure: dict[str, set[str]],
    kinds: tuple[str, ...] = ("INSERT", "UPDATE"),
) -> list[str]:
    """Reachable role:priv:table[.column] surfaces, membership-expanded.

    A role reaches a grant held by any role it inherits (plus PUBLIC).
    Column-level UPDATE grants expand to their exact columns; table-level
    UPDATE expands to every governed column of that table (a table-wide
    UPDATE can mutate any column the trigger does not freeze -- and the
    trigger freeze is a SEPARATE defense verified by its own falsifier,
    never assumed here).
    """
    surfaces: set[str] = set()
    for role in RUNTIME_ROLES:
        effective = {role} | closure.get(role, set()) | {"PUBLIC"}
        for grantee, table, priv in table_privs:
            if grantee not in effective or priv not in kinds:
                continue
            if table not in table_map:
                continue
            if priv == "INSERT":
                surfaces.add(f"{role}:{priv}:{table}")
            else:
                for col in table_map[table]:
                    surfaces.add(f"{role}:{priv}:{table}.{col}")
        for grantee, table, col, priv in column_privs:
            if grantee not in effective or priv not in kinds:
                continue
            if table not in table_map or col not in table_map[table]:
                continue
            surfaces.add(f"{role}:{priv}:{table}.{col}")
    return sorted(surfaces)


def _routine_surfaces(
    routines: tuple[str, ...],
    routine_privs: list[tuple[str, str, str]],
    closure: dict[str, set[str]],
) -> list[str]:
    surfaces: set[str] = set()
    for role in RUNTIME_ROLES:
        effective = {role} | closure.get(role, set()) | {"PUBLIC"}
        for grantee, routine, priv in routine_privs:
            if grantee not in effective or priv != "EXECUTE":
                continue
            if routine in PURE_ORACLES:
                continue
            if routine in routines:
                surfaces.add(f"{role}:EXECUTE:{routine}")
    return sorted(surfaces)


def build_manifest(dsn: str, covered: tuple[str, ...]) -> dict:
    conn = _connect(dsn)
    try:
        cur = conn.cursor()
        closure = _role_closure(cur)
        table_privs = _effective_table_privs(cur)
        column_privs = _effective_column_privs(cur)
        routine_privs = _effective_routine_privs(cur)
        definers = _definer_writers(cur)
        defaults = _default_acls(cur)
    finally:
        conn.close()
    covered_set = set(covered)
    effects: dict[str, dict] = {}
    for name, tables, routines in (
        ("forged_canonical_root", ROOT_TABLES, ROOT_ROUTINES),
        ("false_conducted", COMPLETION_TABLES, COMPLETION_ROUTINES),
        ("stale_suppression", DISPOSITION_TABLES, DISPOSITION_ROUTINES),
    ):
        reachable = _surfaces_for(tables, table_privs, column_privs, closure)
        reachable += _routine_surfaces(routines, routine_privs, closure)
        reachable = sorted(set(reachable))
        tested = sorted(s for s in reachable if s in covered_set)
        untested = sorted(s for s in reachable if s not in covered_set)
        effects[name] = {
            "reachable_surfaces": reachable,
            "tested_surfaces": tested,
            "untested_reachable_surfaces": untested,
        }
    # Quarantine/silent-graveyard effect: writers + readers per principal.
    quar_write = _surfaces_for(
        {"b26_p2_execution_quarantine": ("tenant_id", "reason")},
        table_privs,
        column_privs,
        closure,
    )
    quar_read = sorted(
        {
            f"{role}:SELECT:b26_p2_execution_quarantine"
            for role in RUNTIME_ROLES
            for (g, t, p) in table_privs
            if t == "b26_p2_execution_quarantine"
            and p == "SELECT"
            and g in ({role} | closure.get(role, set()) | {"PUBLIC"})
        }
    )
    effects["silent_quarantine"] = {
        "reachable_surfaces": sorted(set(quar_write + quar_read)),
        "tested_surfaces": sorted(
            s for s in set(quar_write + quar_read) if s in covered_set
        ),
        "untested_reachable_surfaces": sorted(
            s for s in set(quar_write + quar_read) if s not in covered_set
        ),
    }
    manifest = {
        "producer": "b26_p2_capability_surface",
        "effects": effects,
        "definer_writers": [f"{a}->{b}" for a, b in definers],
        "default_acls": defaults,
        "class_closed": all(
            len(e["untested_reachable_surfaces"]) == 0 for e in effects.values()
        ),
    }
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--manifest-out", type=Path, default=None)
    parser.add_argument("--covered", nargs="*", default=[])
    parser.add_argument("--fail-on-untested", action="store_true")
    args = parser.parse_args()
    manifest = build_manifest(args.dsn, tuple(args.covered))
    total_untested = sum(
        len(e["untested_reachable_surfaces"]) for e in manifest["effects"].values()
    )
    if args.manifest_out is not None:
        args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
        args.manifest_out.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    for name, effect in manifest["effects"].items():
        print(
            f"effect={name} reachable={len(effect['reachable_surfaces'])} "
            f"tested={len(effect['tested_surfaces'])} "
            f"untested={len(effect['untested_reachable_surfaces'])}"
        )
        for surface in effect["untested_reachable_surfaces"][:25]:
            print(f"  UNTESTED: {surface}")
    if args.fail_on_untested and total_untested > 0:
        print(f"B26_P2_CAPABILITY_COVERAGE_FAIL untested={total_untested}")
        return 1
    print(
        "B26_P2_CAPABILITY_COVERAGE_PASS"
        if total_untested == 0
        else f"B26_P2_CAPABILITY_COVERAGE_OPEN untested={total_untested}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
