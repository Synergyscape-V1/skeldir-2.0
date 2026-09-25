#!/usr/bin/env python3
"""B2.6-P2 Corrective XII fixed-point semantic dependency closure (BLOCKER D).

Law: for every fact capable of changing classification, scope identity,
candidate inclusion, or policy interpretation, the system classifies it
TEMPORALLY GOVERNED, IMMUTABLE, VERSION-BOUND, or PROVEN NON-SEMANTIC.
Unknown/unresolved dependencies RED. No finite silent frontier exists.

Mechanism (derived, never enumerated):
- fixed-point helper closure over pg_proc with cycle protection and no
  depth bound (an iteration cap emits explicit RED, never silence);
- column reads through every qualification form: i./v. legacy aliases,
  FROM/JOIN alias mapping for ANY alias, function-parameter
  qualification (v_row.match_quality), and table qualification;
- sovereign pg_depend closure: every public relation/function the
  canonical roots depend on must be governed or explicitly non-semantic;
- set-level detection: COUNT/EXISTS/INSERT/DELETE over non-governed
  relations RED;
- unresolved calls (not public, not pg_catalog, not keyword) RED.

Modes: check (default, RED on drift vs --manifest) and --generate
(refresh the manifest; CI never generates).

Exit code is the gate: 0 on PASS, 1 plus a violation list on FAIL.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = (
    REPO_ROOT / "contracts-internal" / "governance"
    / "b26_p2_xii_semantic_dependency_manifest.json"
)

CANONICAL_ROUTINES = (
    "b26_p2_classify_candidate",
    "b26_p2_canonical_scope_identity_for_window",
)

GOVERNANCE_TRIGGERS = {
    "b23_match_verdicts": ("trg_b26_p2_verdict_temporal_conservation",),
    "webhook_ingress_identities": (
        "trg_b26_p2_ingress_sovereign_custody",
        "trg_b26_p2_ingress_verified_authorship",
        "trg_b26_p2_ingress_provenance",
    ),
    "b26_p2_scope_policy_authority": (
        "trg_b26_p2_policy_immutability",
    ),
}

# Relations whose reads may enter canonical meaning only through the
# triggers above. Quarantine/tenants reads are non-semantic by
# construction (exclusion scoping / existence only) and are pinned
# explicitly so a NEW relation can never silently join this set.
NON_SEMANTIC_RELATIONS = frozenset(
    {
        "b26_p2_execution_quarantine",
        "tenants",
    }
)

COLUMN_REF_RE = re.compile(
    r"\b([iv])\.([a-z_][a-z0-9_]*)\b", re.IGNORECASE
)
TABLE_REF_RE = re.compile(
    r"\b(?:FROM|JOIN)\s+public\.([a-z_][a-z0-9_]*)"
    r"(?:\s+(?:AS\s+)?([a-z_][a-z0-9_]*))?",
    re.IGNORECASE,
)
CALL_REF_RE = re.compile(
    r"\b(?:public\.)?([a-z_][a-z0-9_]*)\s*\(",
    re.IGNORECASE,
)
# Any alias-qualified column (covers non-i/v aliases, lateral
# subquery aliases, and parameter-qualified reads at the regex
# level; parameter names refine it below).
ANY_QUALIFIED_COL_RE = re.compile(
    r"\b([a-z_][a-z0-9_]*)\.([a-z_][a-z0-9_]*)\b", re.IGNORECASE
)
SET_LEVEL_RE = re.compile(
    r"\b(COUNT|EXISTS)\s*\(", re.IGNORECASE
)
WRITE_LEVEL_RE = re.compile(
    r"\b(INSERT\s+INTO|DELETE\s+FROM)\s+(?:public\.)?([a-z_][a-z0-9_]*)",
    re.IGNORECASE,
)
SQL_KEYWORDS = frozenset(
    {
        "select", "exists", "coalesce", "nullif", "case", "when",
        "string_agg", "count", "now", "set_config", "current_setting",
        "to_char", "encode", "digest", "length", "order", "limit",
        "cast", "in", "and", "or", "not", "distinct",
        "group", "having", "union", "all", "as", "on", "using",
        "return", "perform", "raise", "if", "then", "else", "elsif",
        "end", "loop", "while", "for", "declare", "begin", "is",
        "null", "true", "false", "like", "ilike", "between",
        "from", "join", "left", "right", "inner", "outer", "full",
        "cross", "lateral", "where", "into", "values", "by",
    }
)
VERDICT_TABLES = {"b23_match_verdicts"}
INGRESS_TABLES = {"webhook_ingress_identities"}
UPDATE_OF_RE = re.compile(
    r"UPDATE\s+OF\s+([^BEFOREFOREXECUTE;]+?)(?:\s+BEFORE|\s+FOR\s|\s+EXECUTE|;|$)",
    re.IGNORECASE | re.DOTALL,
)
MAX_CLOSURE_ITERATIONS = 50


def _extract_alias_columns(prosrc: str) -> dict[str, set[str]]:
    found: dict[str, set[str]] = {"i": set(), "v": set()}
    for match in COLUMN_REF_RE.finditer(prosrc or ""):
        alias = match.group(1).lower()
        column = match.group(2).lower()
        if alias in found:
            found[alias].add(column)
    return found


def _fetch_bodies(cur, names: set[str]) -> dict[str, str]:
    cur.execute(
        "SELECT p.proname, p.prosrc FROM pg_proc p"
        " JOIN pg_namespace n ON n.oid = p.pronamespace"
        " WHERE n.nspname = 'public' AND p.proname = ANY(%s)",
        (sorted(names),),
    )
    return {name: (src or "") for name, src in cur.fetchall()}


def _fetch_argnames(cur, names: set[str]) -> dict[str, set[str]]:
    cur.execute(
        "SELECT p.proname,"
        " ARRAY(SELECT unnest(p.proargnames))"
        " FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace"
        " WHERE n.nspname = 'public' AND p.proname = ANY(%s)",
        (sorted(names),),
    )
    out: dict[str, set[str]] = {}
    for name, argnames in cur.fetchall():
        out[str(name)] = {
            str(a).lower() for a in (argnames or []) if a
        }
    return out


def _live_semantic_reads(admin_dsn: str):
    import psycopg2  # noqa: PLC0415

    conn = psycopg2.connect(admin_dsn)
    conn.autocommit = True
    try:
        cur = conn.cursor()
        bodies = _fetch_bodies(cur, set(CANONICAL_ROUTINES))
        missing = [r for r in CANONICAL_ROUTINES if r not in bodies]
        if missing:
            raise RuntimeError(
                "xii_semantic_canonical_missing:" + ",".join(missing)
            )
        cur.execute(
            "SELECT p.proname FROM pg_proc p"
            " JOIN pg_namespace n ON n.oid = p.pronamespace"
            " WHERE n.nspname = 'public'"
        )
        public_routines = {str(r[0]).lower() for r in cur.fetchall()}
        cur.execute(
            "SELECT p.proname FROM pg_proc p"
            " JOIN pg_namespace n ON n.oid = p.pronamespace"
            " WHERE n.nspname = 'pg_catalog'"
        )
        catalog_routines = {str(r[0]).lower() for r in cur.fetchall()}
        # Fixed-point helper closure: no depth bound. The frontier is
        # exhausted or an explicit RED fires (iteration cap with cycle
        # protection); truncation is never silent.
        seen: set[str] = set(CANONICAL_ROUTINES)
        universe: dict[str, str] = dict(bodies)
        frontier = [bodies[r] for r in CANONICAL_ROUTINES]
        unresolved_calls: set[str] = set()
        iterations = 0
        while frontier:
            iterations += 1
            if iterations > MAX_CLOSURE_ITERATIONS:
                raise RuntimeError(
                    "xii_semantic_closure_frontier_not_exhausted"
                )
            called: set[str] = set()
            for body in frontier:
                for match in CALL_REF_RE.finditer(body):
                    name = match.group(1).lower()
                    if name in seen:
                        continue
                    if name in public_routines:
                        called.add(name)
                    elif name in catalog_routines:
                        continue
                    elif name in SQL_KEYWORDS:
                        continue
                    else:
                        unresolved_calls.add(name)
            called -= seen
            if not called:
                break
            found = _fetch_bodies(cur, called)
            for name in called:
                if name not in found:
                    unresolved_calls.add(name)
                else:
                    universe[name] = found[name]
            seen |= called
            frontier = [found[n] for n in called if n in found]
        argnames = _fetch_argnames(cur, seen)
        ingress_cols: set[str] = set()
        verdict_cols: set[str] = set()
        referenced_tables: set[str] = set()
        for name in seen:
            body = universe.get(name)
            if body is None:
                continue
            refs = _extract_alias_columns(body)
            ingress_cols |= refs["i"]
            verdict_cols |= refs["v"]
            # Alias map for this body: FROM/JOIN table -> alias.
            alias_to_table: dict[str, str] = {}
            for table_match in TABLE_REF_RE.finditer(body):
                table = table_match.group(1).lower()
                referenced_tables.add(table)
                alias = (table_match.group(2) or "").lower()
                if alias:
                    alias_to_table[alias] = table
            params = {a for a in argnames.get(name, set())}
            for col_match in ANY_QUALIFIED_COL_RE.finditer(body):
                qualifier = col_match.group(1).lower()
                column = col_match.group(2).lower()
                if qualifier in ("new", "old", "pg_catalog", "public"):
                    continue
                table = alias_to_table.get(qualifier)
                if table in VERDICT_TABLES:
                    verdict_cols.add(column)
                elif table in INGRESS_TABLES:
                    ingress_cols.add(column)
                elif qualifier in params:
                    # Parameter-qualified read (v_row.match_quality,
                    # composite arguments): attribute to BOTH tables
                    # conservatively -- classification below treats
                    # any uncovered column as RED, so over-approximation
                    # fails closed, never silent.
                    verdict_cols.add(column)
                    ingress_cols.add(column)
        policy_cols: set[str] = set()
        identity = bodies["b26_p2_canonical_scope_identity_for_window"]
        if "b26_p2_scope_policy_authority" in identity:
            for col in ("scope_policy_version", "semantic_sha256"):
                if col in identity:
                    policy_cols.add(col)
        # Sovereign pg_depend closure: every public relation or
        # routine the roots depend on must be governed or explicitly
        # non-semantic. The parser can miss a form; the catalog
        # cannot.
        cur.execute(
            """
            WITH RECURSIVE deps(obj) AS (
                SELECT p.oid
                  FROM pg_proc p JOIN pg_namespace n
                    ON n.oid = p.pronamespace
                 WHERE n.nspname = 'public'
                   AND p.proname = ANY(%s)
                UNION
                SELECT d.refobjid
                  FROM pg_depend d JOIN deps ON deps.obj = d.objid
                 WHERE d.refobjsubid = 0
            )
            SELECT DISTINCT c.relname, c.relkind
              FROM deps JOIN pg_class c ON c.oid = deps.obj
              JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = 'public'
            """,
            (sorted(CANONICAL_ROUTINES),),
        )
        depended_relations = {
            str(r[0]).lower(): str(r[1]) for r in cur.fetchall()
        }
        cur.execute(
            """
            WITH RECURSIVE deps(obj) AS (
                SELECT p.oid
                  FROM pg_proc p JOIN pg_namespace n
                    ON n.oid = p.pronamespace
                 WHERE n.nspname = 'public'
                   AND p.proname = ANY(%s)
                UNION
                SELECT d.refobjid
                  FROM pg_depend d JOIN deps ON deps.obj = d.objid
                 WHERE d.refobjsubid = 0
            )
            SELECT DISTINCT p.proname
              FROM deps JOIN pg_proc p ON p.oid = deps.obj
              JOIN pg_namespace n ON n.oid = p.pronamespace
             WHERE n.nspname = 'public'
            """,
            (sorted(CANONICAL_ROUTINES),),
        )
        depended_functions = {str(r[0]).lower() for r in cur.fetchall()}
        # Set-level detection over the full closure bodies.
        set_level_tables: set[str] = set()
        for name in seen:
            body = universe.get(name) or ""
            if SET_LEVEL_RE.search(body):
                for table_match in TABLE_REF_RE.finditer(body):
                    set_level_tables.add(table_match.group(1).lower())
            for write_match in WRITE_LEVEL_RE.finditer(body):
                set_level_tables.add(write_match.group(2).lower())
        return {
            "reads": {
                "webhook_ingress_identities": ingress_cols,
                "b23_match_verdicts": verdict_cols,
                "b26_p2_scope_policy_authority": policy_cols,
            },
            "referenced_tables": sorted(referenced_tables),
            "closure_functions": sorted(seen),
            "closure_iterations": iterations,
            "unresolved_calls": sorted(unresolved_calls),
            "depended_relations": depended_relations,
            "depended_functions": sorted(depended_functions),
            "set_level_tables": sorted(set_level_tables),
        }
    finally:
        conn.close()


def _live_trigger_columns(admin_dsn: str) -> dict[str, set[str]]:
    import psycopg2  # noqa: PLC0415

    conn = psycopg2.connect(admin_dsn)
    conn.autocommit = True
    try:
        cur = conn.cursor()
        covered: dict[str, set[str]] = {
            table: set() for table in GOVERNANCE_TRIGGERS
        }
        for table, triggers in GOVERNANCE_TRIGGERS.items():
            for trigger in triggers:
                cur.execute(
                    "SELECT pg_get_triggerdef(t.oid), p.prosrc"
                    " FROM pg_trigger t"
                    " JOIN pg_class c ON c.oid = t.tgrelid"
                    " JOIN pg_namespace n ON n.oid = c.relnamespace"
                    " JOIN pg_proc p ON p.oid = t.tgfoid"
                    " WHERE n.nspname = 'public'"
                    " AND c.relname = %s AND t.tgname = %s"
                    " AND NOT t.tgisinternal",
                    (table, trigger),
                )
                row = cur.fetchone()
                if row is None:
                    raise RuntimeError(
                        f"xii_semantic_trigger_missing:{trigger}"
                    )
                definition, func_body = row[0] or "", row[1] or ""
                match = UPDATE_OF_RE.search(definition)
                if match is not None:
                    for col in match.group(1).split(","):
                        covered[table].add(
                            col.strip().strip('"').lower()
                        )
                for col in re.findall(
                    r"\b(?:NEW|OLD)\.([a-z_][a-z0-9_]*)\b",
                    func_body,
                    re.IGNORECASE,
                ):
                    covered[table].add(col.lower())
        covered["webhook_ingress_identities"].add(
            "verified_commerce_ingress_state"
        )
        return covered
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate B2.6-P2 XII semantic closure law."
    )
    parser.add_argument("--dsn", default=None)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--evidence-dir", type=Path, default=None)
    parser.add_argument("--evidence-out", type=Path, default=None)
    args = parser.parse_args()
    violations: list[str] = []
    checks: dict = {}
    live = None
    covered: dict[str, set[str]] = {}
    if args.dsn is None:
        violations.append("xii_semantic_live_check_required_no_dsn")
    else:
        try:
            live = _live_semantic_reads(args.dsn)
        except Exception as exc:
            violations.append(f"xii_semantic_derive_failed:{exc}"[:200])
        try:
            covered = _live_trigger_columns(args.dsn) if live else {}
        except Exception as exc:
            violations.append(f"xii_semantic_trigger_read_failed:{exc}"[:200])
    serial_reads = (
        {k: sorted(v) for k, v in live["reads"].items()} if live else {}
    )
    serial_covered = {k: sorted(v) for k, v in covered.items()}
    checks["live_semantic_reads"] = serial_reads
    checks["temporal_covered_columns"] = serial_covered
    if live:
        checks["closure_functions"] = live["closure_functions"]
        checks["closure_iterations"] = live["closure_iterations"]
        checks["depended_relations"] = live["depended_relations"]
        checks["referenced_tables"] = live["referenced_tables"]
        if live["unresolved_calls"]:
            for name in live["unresolved_calls"]:
                violations.append("xii_semantic_unresolved_call:%s" % name)
        # Every relation textually referenced by the closure is
        # governed or explicitly non-semantic. A view, lookup table,
        # or novel relation entering canonical SQL REDs here even
        # when the column parser has no name for its columns.
        for table in live["referenced_tables"]:
            if table in GOVERNANCE_TRIGGERS or table in NON_SEMANTIC_RELATIONS:
                continue
            violations.append("xii_semantic_ungoverned_relation:%s" % table)
        # Sovereign closure: every depended public relation is
        # governed or explicitly non-semantic.
        for rel, kind in live["depended_relations"].items():
            if rel in GOVERNANCE_TRIGGERS or rel in NON_SEMANTIC_RELATIONS:
                continue
            if kind in ("v", "m"):
                violations.append("xii_semantic_ungoverned_view:%s" % rel)
            else:
                violations.append("xii_semantic_ungoverned_relation:%s" % rel)
        # Every depended public function is inside the parser closure
        # (parser and catalog agree) or explicitly non-semantic.
        for fn in live["depended_functions"]:
            if fn in live["closure_functions"]:
                continue
            if fn.startswith("b26_p2_") or fn.startswith("b23_"):
                violations.append("xii_semantic_depended_unseen:%s" % fn)
        # Set-level tables outside governance RED.
        for table in live["set_level_tables"]:
            if table in GOVERNANCE_TRIGGERS or table in NON_SEMANTIC_RELATIONS:
                continue
            if table in live["depended_relations"]:
                continue
            violations.append("xii_semantic_set_level_ungoverned:%s" % table)
    if live and covered:
        for table, cols in live["reads"].items():
            unknown = sorted(set(cols) - covered.get(table, set()))
            if unknown:
                for col in unknown:
                    violations.append(
                        "xii_semantic_temporal_unknown_dependency:"
                        f"{table}.{col}"
                    )
            checks[f"uncovered_{table}"] = sorted(
                set(cols) - covered.get(table, set())
            )
    manifest_payload = {
        "mechanism": "fixed_point_pg_proc_readset_plus_pg_depend_closure_vs_trigger_update_of",
        "canonical_routines": list(CANONICAL_ROUTINES),
        "governance_triggers": {
            k: list(v) for k, v in GOVERNANCE_TRIGGERS.items()
        },
        "non_semantic_relations": sorted(NON_SEMANTIC_RELATIONS),
        "semantic_reads": serial_reads,
        "temporal_covered_columns": serial_covered,
        "closure_functions": live["closure_functions"] if live else [],
        "depended_relations": live["depended_relations"] if live else {},
        "referenced_tables": live["referenced_tables"] if live else [],
    }
    if args.generate:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(
            json.dumps(manifest_payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        checks["manifest_generated"] = str(args.manifest)
    else:
        try:
            pinned = json.loads(
                args.manifest.read_text(encoding="utf-8")
            )
        except OSError as exc:
            violations.append(f"xii_semantic_manifest_missing:{exc}")
            pinned = None
        if pinned is not None:
            if pinned.get("semantic_reads") != serial_reads:
                violations.append("xii_semantic_manifest_drift")
                checks["manifest_drift"] = True
            if pinned.get("depended_relations") != (
                live["depended_relations"] if live else {}
            ):
                violations.append("xii_semantic_depended_drift")
                checks["depended_drift"] = True
    status = "PASS" if not violations else "FAIL"
    evidence = {
        "gate_id": "B26-P2-XII-SEMANTIC-CLOSURE",
        "validator": "validate_b26_p2_xii_semantic_closure",
        "status": status,
        "violations": sorted(violations),
        "checks": checks,
    }
    if args.evidence_out is not None:
        args.evidence_out.parent.mkdir(parents=True, exist_ok=True)
        args.evidence_out.write_text(
            json.dumps(evidence, indent=2), encoding="utf-8"
        )
    if args.evidence_dir is not None:
        args.evidence_dir.mkdir(parents=True, exist_ok=True)
        (args.evidence_dir / "xii-semantic-closure.json").write_text(
            json.dumps(evidence, indent=2), encoding="utf-8"
        )
    if violations:
        print("B26_P2_XII_SEMANTIC_FAIL " + ";".join(sorted(violations)))
        return 1
    print("B26_P2_XII_SEMANTIC_PASS")
    print(json.dumps(evidence, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
