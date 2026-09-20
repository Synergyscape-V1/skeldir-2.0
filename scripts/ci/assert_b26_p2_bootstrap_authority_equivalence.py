#!/usr/bin/env python3
"""B2.6-P2 Corrective IV bootstrap/migration authority-equivalence proof.

Compares the P2 authority universe of two databases:

  A: empty -> alembic upgrade head (the production construction path)
  B: roles + db/schema/canonical_schema.sql + db/schema/canonical_authority.sql

Object shape can match while authority physics differ (Corrective-III
condition #24 fired exactly this way: zero GRANT/REVOKE in the bootstrap
universe, PUBLIC EXECUTE on the resolver). This proof diffs the authority
physics as catalog facts:

  table grants (role_table_grants) for the P2 tables x runtime roles
  column grants (role_column_grants) for the worker's column-scoped UPDATEs
  routine grants (role_routine_grants) for the admission resolver
  RLS enabled + forced flags
  RLS policies (name + qual + with_check)
  CHECK / FK / UNIQUE definitions on the P2 tables
  triggers on the P2 tables
  function volatility/security/definition for the P2 functions
  default privileges granting to runtime roles

Owner names and database OIDs are excluded (loaders may differ); the
compared facts are the effective authority any runtime principal holds.
Any difference REDs with the exact divergent lines.

Usage:
  python scripts/ci/assert_b26_p2_bootstrap_authority_equivalence.py \
    --migration-built-dsn postgresql://postgres:postgres@127.0.0.1:5432/db_a \
    --bootstrap-dsn postgresql://postgres:postgres@127.0.0.1:5432/db_b \
    [--evidence-out artifacts/b26_p2/topology/bootstrap-equivalence.json]
"""

from __future__ import annotations

import argparse
import itertools
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

P2_TABLES = (
    "b23_match_task_dispatches",
    "b26_p2_execution_outbox",
    "b26_p2_task_authority_directory",
    "b26_p2_conduction_receipts",
    "b26_p2_execution_quarantine",
)

P2_ROUTINES = (
    "b26_p2_resolve_dispatch_authority",
    "b26_p2_enforce_dispatch_immutability",
    "b26_p2_enforce_outbox_transitions",
    "b26_p2_enforce_outbox_issuance",
    "b26_p2_enforce_directory_coherence",
    "b26_p2_enforce_dispatch_sovereign_window",
    "b26_p2_enforce_ingress_sovereign_custody",
    "b26_p2_canonical_day_start",
    "b26_p2_canonical_day_end",
    "b26_p2_record_conduction_receipt",
    "b26_p2_mark_conducted",
    "b26_p2_stale_unconducted",
    "b26_p2_operational_disposition",
)

P2_ROLES = ("app_user", "app_worker", "app_rw", "app_ro", "app_relay", "app_beat", "PUBLIC")

_CATALOG_QUERIES: tuple[tuple[str, str], ...] = (
    (
        "table_priv",
        """
        SELECT 'table_priv' AS k, grantee, table_name, privilege_type
        FROM information_schema.role_table_grants
        WHERE table_schema = 'public'
          AND table_name IN ('b23_match_task_dispatches',
                             'b26_p2_execution_outbox',
                             'b26_p2_task_authority_directory',
                             'b26_p2_conduction_receipts',
                             'b26_p2_execution_quarantine')
          AND grantee IN ('app_user', 'app_worker', 'app_rw', 'app_ro', 'app_relay', 'app_beat', 'PUBLIC')
        """,
    ),
    (
        "column_priv",
        """
        SELECT 'column_priv' AS k, grantee, table_name, column_name, privilege_type
        FROM information_schema.role_column_grants
        WHERE table_schema = 'public'
          AND table_name IN ('b23_match_task_dispatches',
                             'b26_p2_execution_outbox',
                             'b26_p2_task_authority_directory',
                             'b26_p2_conduction_receipts',
                             'b26_p2_execution_quarantine')
          AND grantee IN ('app_user', 'app_worker', 'app_rw', 'app_ro', 'app_relay', 'app_beat', 'PUBLIC')
        """,
    ),
    (
        "routine_priv",
        """
        SELECT 'routine_priv' AS k, grantee, routine_name, privilege_type
        FROM information_schema.role_routine_grants
        WHERE routine_schema = 'public'
          AND routine_name IN ('b26_p2_resolve_dispatch_authority',
                               'b26_p2_enforce_dispatch_immutability',
                               'b26_p2_enforce_outbox_transitions',
                               'b26_p2_enforce_outbox_issuance',
                               'b26_p2_enforce_directory_coherence',
                               'b26_p2_enforce_dispatch_sovereign_window',
                               'b26_p2_enforce_ingress_sovereign_custody',
                               'b26_p2_canonical_day_start',
                               'b26_p2_canonical_day_end',
                               'b26_p2_record_conduction_receipt',
                               'b26_p2_mark_conducted',
                               'b26_p2_stale_unconducted',
                               'b26_p2_operational_disposition')
        """,
    ),
    (
        "rls",
        """
        SELECT 'rls' AS k, relname,
               relrowsecurity::text, relforcerowsecurity::text
        FROM pg_class
        WHERE relnamespace = 'public'::regnamespace
          AND relname IN ('b23_match_task_dispatches',
                          'b26_p2_execution_outbox',
                          'b26_p2_task_authority_directory',
                             'b26_p2_conduction_receipts',
                             'b26_p2_execution_quarantine')
        """,
    ),
    (
        "policy",
        """
        SELECT 'policy' AS k, tablename, policyname, roles::text,
               qual, with_check
        FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename IN ('b23_match_task_dispatches',
                            'b26_p2_execution_outbox',
                            'b26_p2_task_authority_directory',
                             'b26_p2_conduction_receipts',
                             'b26_p2_execution_quarantine')
        """,
    ),
    (
        "constraint",
        """
        SELECT 'constraint' AS k, c.conname, contype::text,
               pg_get_constraintdef(c.oid)
        FROM pg_constraint AS c
        JOIN pg_class AS t ON t.oid = c.conrelid
        WHERE t.relnamespace = 'public'::regnamespace
          AND t.relname IN ('b23_match_task_dispatches',
                            'b26_p2_execution_outbox',
                            'b26_p2_task_authority_directory',
                             'b26_p2_conduction_receipts',
                             'b26_p2_execution_quarantine')
          AND c.contype IN ('f', 'u', 'p')
        """,
    ),
    (
        "trigger",
        """
        SELECT 'trigger' AS k, t.tgname,
               p.proname,
               (t.tgenabled <> 'D')::text AS enabled
        FROM pg_trigger AS t
        JOIN pg_class AS c ON c.oid = t.tgrelid
        JOIN pg_proc AS p ON p.oid = t.tgfoid
        WHERE c.relnamespace = 'public'::regnamespace
          AND c.relname IN ('b23_match_task_dispatches',
                            'b26_p2_execution_outbox',
                            'b26_p2_task_authority_directory',
                             'b26_p2_conduction_receipts',
                             'b26_p2_execution_quarantine',
                             'webhook_ingress_identities')
          AND NOT t.tgisinternal
        """,
    ),
    (
        "function",
        """
        SELECT 'function' AS k, p.proname,
               pg_get_function_identity_arguments(p.oid) AS args,
               p.prosecdef::text, p.provolatile,
               p.proconfig::text,
               pg_get_functiondef(p.oid) AS def
        FROM pg_proc AS p
        JOIN pg_namespace AS n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public'
          AND p.proname IN ('b26_p2_resolve_dispatch_authority',
                            'b26_p2_enforce_dispatch_immutability',
                            'b26_p2_enforce_outbox_transitions',
                            'b26_p2_enforce_outbox_issuance',
                               'b26_p2_enforce_directory_coherence',
                               'b26_p2_enforce_dispatch_sovereign_window',
                               'b26_p2_enforce_ingress_sovereign_custody',
                               'b26_p2_canonical_day_start',
                               'b26_p2_canonical_day_end',
                               'b26_p2_record_conduction_receipt',
                               'b26_p2_mark_conducted',
                               'b26_p2_stale_unconducted',
                               'b26_p2_operational_disposition')
        """,
    ),
    (
        "default_acl",
        """
        SELECT 'default_acl' AS k, n.nspname,
               pg_get_userbyid(d.defaclrole) AS owner,
               d.defaclobjtype,
               d.defaclacl::text
        FROM pg_default_acl AS d
        JOIN pg_namespace AS n ON n.oid = d.defaclnamespace
        WHERE n.nspname = 'public'
        """,
    ),
)


def _snapshot(dsn: str) -> list[str]:
    import psycopg2

    lines: list[str] = []
    conn = psycopg2.connect(dsn)
    try:
        cur = conn.cursor()
        for _name, sql in _CATALOG_QUERIES:
            cur.execute(sql)
            for row in cur.fetchall():
                lines.append("|".join("" if v is None else str(v) for v in row))
        lines.extend(_check_behavior_matrix(conn))
    finally:
        conn.close()
    return sorted(lines)


def _check_behavior_matrix(conn) -> list[str]:
    """Compare CHECK-constraint BEHAVIOR (not deparse text) across the P2 tables.

    The same predicate written through a migration vs through a pg_dump
    reload deparses to textually different but semantically identical SQL
    (cast-placement wobble). Text comparison would false-positive forever.
    Instead every P2 CHECK is evaluated over a TRUE/FALSE/UNKNOWN probe
    matrix (directive section 8): the two universes are equivalent only
    when every probe yields the same verdict in both.
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT c.conname, t.relname, pg_get_constraintdef(c.oid),
               array_agg(a.attname ORDER BY u.ord) AS cols,
               array_agg(a.atttypid::regtype::text ORDER BY u.ord) AS types
        FROM pg_constraint AS c
        JOIN pg_class AS t ON t.oid = c.conrelid
        JOIN unnest(c.conkey) WITH ORDINALITY AS u(attnum, ord) ON true
        JOIN pg_attribute AS a ON a.attrelid = t.oid AND a.attnum = u.attnum
        WHERE t.relnamespace = 'public'::regnamespace
          AND t.relname IN ('b23_match_task_dispatches',
                            'b26_p2_execution_outbox',
                            'b26_p2_task_authority_directory',
                             'b26_p2_conduction_receipts',
                             'b26_p2_execution_quarantine')
          AND c.contype = 'c'
        GROUP BY c.conname, t.relname, pg_get_constraintdef(c.oid)
        ORDER BY c.conname
        """
    )
    checks = cur.fetchall()
    lines: list[str] = []
    # Corrective VI: quarantine source-relation literals. The generic
    # text probes above cannot distinguish the V 2-value source CHECK
    # from the VI 4-value source CHECK (both FALSE on every generic
    # probe), so source_relation columns additionally probe every
    # governed source value: any lane missing a source law diverges
    # here instead of passing vacuously.
    _QUARANTINE_SOURCES = (
        "'b26_p2_execution_outbox'",
        "'b26_p2_task_authority_directory'",
        "'b23_match_task_dispatches'",
        "'b26_p2_conduction_receipts'",
        "'bogus_source'",
        "NULL",
    )
    for conname, relname, condef, cols, types in checks:
        probes: list[list[str]] = []
        for col, coltype in zip(cols, types):
            if col == "source_relation":
                probes.append(list(_QUARANTINE_SOURCES))
            elif "char" in coltype or "text" in coltype:
                probes.append(
                    ["'pending_publish'", "'published'", "'conducted'",
                     "'bogus'", "NULL", "''"]
                )
            elif "int" in coltype:
                probes.append(["0", "5", "-1", "NULL"])
            elif "timestamp" in coltype:
                probes.append(
                    ["'2026-01-15T00:00:00+00:00'::timestamptz",
                     "'2026-01-16T00:00:00+00:00'::timestamptz", "NULL"]
                )
            else:
                probes.append(["NULL"])
        expr = condef
        if expr.upper().startswith("CHECK"):
            expr = expr[len("CHECK"):].strip()
        for combo in itertools.product(*probes):
            probe_expr = expr
            for col, lit in zip(cols, combo):
                # Word-boundary substitution: 'state' must not rewrite
                # 'delivery_state' (underscore is a word character, so \b
                # already protects it; longest-first is belt and braces).
                probe_expr = re.sub(rf"\b{re.escape(col)}\b", lit, probe_expr)
            try:
                cur.execute(f"SELECT ({probe_expr}) IS TRUE, ({probe_expr}) IS NULL")
                is_true, is_null = cur.fetchone()
                verdict = "TRUE" if is_true else ("UNKNOWN" if is_null else "FALSE")
            except Exception:
                verdict = "ERROR"
            lines.append(
                f"check_behavior|{conname}|{relname}|"
                + "|".join(str(v) for v in combo)
                + f"|{verdict}"
            )
    return lines


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--migration-built-dsn", required=True)
    parser.add_argument("--bootstrap-dsn", required=True)
    parser.add_argument("--evidence-out", type=Path, default=None)
    args = parser.parse_args()

    try:
        built = _snapshot(args.migration_built_dsn)
        boot = _snapshot(args.bootstrap_dsn)
    except Exception as exc:  # noqa: BLE001
        print(f"B26_P2_BOOTSTRAP_EQUIVALENCE_FAIL snapshot_failed:{exc}")
        return 1
    only_built = sorted(set(built) - set(boot))
    only_boot = sorted(set(boot) - set(built))
    details = {
        "compared_lines": len(set(built) | set(boot)),
        "migration_built_lines": len(built),
        "bootstrap_lines": len(boot),
        "only_in_migration_built": only_built[:50],
        "only_in_bootstrap": only_boot[:50],
    }
    if only_built or only_boot:
        print("B26_P2_BOOTSTRAP_EQUIVALENCE_FAIL authority_divergent")
        for line in only_built[:20]:
            print(f"  built-only: {line[:220]}")
        for line in only_boot[:20]:
            print(f"  bootstrap-only: {line[:220]}")
        return 1
    if args.evidence_out is not None:
        from scripts.ci.b26_p2_evidence import write_evidence_cell  # noqa: PLC0415

        write_evidence_cell(
            args.evidence_out,
            gate_id="B26-P2-G8-BOOTSTRAP-EQUIVALENCE",
            producer="b26-p2-production-topology",
            scenario_id="migration-vs-bootstrap-authority",
            falsifier_id="bootstrap-grant-divergence",
            details=details,
        )
    print(f"B26_P2_BOOTSTRAP_EQUIVALENCE_PASS lines={details['compared_lines']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
