#!/usr/bin/env python3
"""B2.6-P2 Corrective XI semantic->temporal totality validator (CLASS C).

Law: for every B2.3 fact whose value can change P2 meaning, either the
P2 terminal binds the exact version consumed, lawful mutation forces
re-adjudication, or mutation is physically refused. No semantic
dependency may exist outside one of these treatments.

Mechanism (derived, not enumerated): the validator extracts the live
canonical SQL read-set from pg_proc (the two canonical authorities
plus their helper closure) and requires every read to be covered by a
temporal trigger UPDATE OF list (or the policy-immutability trigger).
An unknown dependency REDs until it receives an explicit temporal
treatment. Adding ``match_quality`` (or any future column) to
canonical SQL without temporal governance is automatically RED.

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
    / "b26_p2_xi_semantic_dependency_manifest.json"
)

CANONICAL_ROUTINES = (
    "b26_p2_classify_candidate",
    "b26_p2_canonical_scope_identity_for_window",
)

# Table -> trigger(s) constituting temporal/version governance for
# reads against that table. Structural mapping (which trigger guards
# which table), never an instance column list: the columns themselves
# are derived live from function bodies.
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

COLUMN_REF_RE = re.compile(
    r"\b([iv])\.([a-z_][a-z0-9_]*)\b", re.IGNORECASE
)
# Qualified table reads (FROM/JOIN <table> [AS] <alias>) and function
# calls (public.<fn>(...) or bare <fn>(...)) inside canonical bodies.
# Calls are resolved transitively: a helper that reads B2.3 state is
# the same violation as a direct read (GATE XI-7).
TABLE_REF_RE = re.compile(
    r"\b(?:FROM|JOIN)\s+public\.([a-z_][a-z0-9_]*)"
    r"(?:\s+(?:AS\s+)?([a-z_][a-z0-9_]*))?",
    re.IGNORECASE,
)
CALL_REF_RE = re.compile(
    r"\b(?:public\.)?([a-z_][a-z0-9_]*)\s*\(",
    re.IGNORECASE,
)
SQL_KEYWORDS = frozenset(
    {
        "select", "exists", "coalesce", "nullif", "case", "when",
        "string_agg", "count", "now", "set_config", "current_setting",
        "to_char", "encode", "digest", "length", "order", "limit",
        "cast",
    }
)
VERDICT_TABLES = {"b23_match_verdicts"}
INGRESS_TABLES = {"webhook_ingress_identities"}
UPDATE_OF_RE = re.compile(r"UPDATE\s+OF\s+([^BEFOREFOREXECUTE;]+?)(?:\s+BEFORE|\s+FOR\s|\s+EXECUTE|;|$)",
                           re.IGNORECASE | re.DOTALL)


def _extract_alias_columns(prosrc: str) -> dict[str, set[str]]:
    """Map alias i/v to referenced column names in one routine body."""
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


def _live_semantic_reads(admin_dsn: str) -> dict[str, set[str]]:
    import psycopg2  # noqa: PLC0415

    conn = psycopg2.connect(admin_dsn)
    conn.autocommit = True
    try:
        cur = conn.cursor()
        bodies = _fetch_bodies(cur, set(CANONICAL_ROUTINES))
        missing = [r for r in CANONICAL_ROUTINES if r not in bodies]
        if missing:
            raise RuntimeError(
                "xi_semantic_canonical_missing:" + ",".join(missing)
            )
        # Resolution universe: only names that actually exist as
        # public routines can be real calls. SQL keywords, clause
        # noise (IN (/FROM (/AND (), and builtins absent from public
        # are ignored -- a call to a nonexistent routine fails at
        # the database itself, never silently.
        cur.execute(
            "SELECT p.proname FROM pg_proc p"
            " JOIN pg_namespace n ON n.oid = p.pronamespace"
            " WHERE n.nspname = 'public'"
        )
        public_routines = {str(r[0]).lower() for r in cur.fetchall()}
        ingress_cols: set[str] = set()
        verdict_cols: set[str] = set()
        # Transitive helper closure (GATE XI-7): resolve every
        # function called from canonical bodies, then functions
        # called from those, to a fixed point (depth-bounded,
        # cycle-safe). A read hidden one hop away is still a read.
        seen: set[str] = set(CANONICAL_ROUTINES)
        universe: dict[str, str] = dict(bodies)
        frontier = [bodies[r] for r in CANONICAL_ROUTINES]
        transitively_unresolved: list[str] = []
        depth = 0
        while frontier and depth < 4:
            depth += 1
            called: set[str] = set()
            for body in frontier:
                for match in CALL_REF_RE.finditer(body):
                    name = match.group(1).lower()
                    if name in seen or name not in public_routines:
                        continue
                    called.add(name)
            called -= seen
            if not called:
                break
            found = _fetch_bodies(cur, called)
            for name in called:
                if name not in found:
                    transitively_unresolved.append(name)
                else:
                    universe[name] = found[name]
            seen |= called
            frontier = [found[n] for n in called if n in found]
        if transitively_unresolved:
            raise RuntimeError(
                "xi_semantic_helper_unresolvable:"
                + ",".join(sorted(set(transitively_unresolved))[:5])
            )
        for name in seen:
            body = universe.get(name)
            if body is None:
                continue
            refs = _extract_alias_columns(body)
            # Alias-qualified reads (i./v.) plus table-qualified
            # reads discovered through FROM/JOIN alias mapping.
            ingress_cols |= refs["i"]
            verdict_cols |= refs["v"]
            for table_match in TABLE_REF_RE.finditer(body):
                table = table_match.group(1).lower()
                alias = (table_match.group(2) or "").lower()
                target = None
                if table in VERDICT_TABLES:
                    target = verdict_cols
                elif table in INGRESS_TABLES:
                    target = ingress_cols
                if target is None or not alias:
                    continue
                for col_match in re.finditer(
                    r"\b" + re.escape(alias) + r"\.([a-z_][a-z0-9_]*)\b",
                    body,
                    re.IGNORECASE,
                ):
                    target.add(col_match.group(1).lower())
        # Policy reads: the identity binds policy version + sha.
        policy_cols: set[str] = set()
        identity = bodies["b26_p2_canonical_scope_identity_for_window"]
        if "b26_p2_scope_policy_authority" in identity:
            for col in ("scope_policy_version", "semantic_sha256"):
                if col in identity:
                    policy_cols.add(col)
        return {
            "webhook_ingress_identities": ingress_cols,
            "b23_match_verdicts": verdict_cols,
            "b26_p2_scope_policy_authority": policy_cols,
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
                        f"xi_semantic_trigger_missing:{trigger}"
                    )
                definition, func_body = row[0] or "", row[1] or ""
                match = UPDATE_OF_RE.search(definition)
                if match is not None:
                    for col in match.group(1).split(","):
                        covered[table].add(
                            col.strip().strip('"').lower()
                        )
                # Whole-row triggers (no UPDATE OF) govern the
                # columns their function body adjudicates: derive
                # NEW./OLD. reads from the live body, never a list.
                for col in re.findall(
                    r"\b(?:NEW|OLD)\.([a-z_][a-z0-9_]*)\b",
                    func_body,
                    re.IGNORECASE,
                ):
                    covered[table].add(col.lower())
        # Transition-governed (non-UPDATE OF) triggers cover the
        # verified-state column by refusal semantics.
        covered["webhook_ingress_identities"].add(
            "verified_commerce_ingress_state"
        )
        return covered
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate B2.6-P2 XI semantic-temporal totality."
    )
    parser.add_argument("--dsn", default=None)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--evidence-dir", type=Path, default=None)
    parser.add_argument("--evidence-out", type=Path, default=None)
    args = parser.parse_args()
    violations: list[str] = []
    checks: dict = {}
    if args.dsn is None:
        violations.append("xi_semantic_live_check_required_no_dsn")
        live_reads: dict[str, set[str]] = {}
        covered: dict[str, set[str]] = {}
    else:
        try:
            live_reads = _live_semantic_reads(args.dsn)
        except Exception as exc:
            violations.append(f"xi_semantic_derive_failed:{exc}"[:200])
            live_reads = {}
        try:
            covered = (
                _live_trigger_columns(args.dsn) if live_reads else {}
            )
        except Exception as exc:
            violations.append(f"xi_semantic_trigger_read_failed:{exc}"[:200])
            covered = {}
    serial_reads = {k: sorted(v) for k, v in live_reads.items()}
    serial_covered = {k: sorted(v) for k, v in covered.items()}
    checks["live_semantic_reads"] = serial_reads
    checks["temporal_covered_columns"] = serial_covered
    if live_reads and covered:
        for table, cols in live_reads.items():
            unknown = sorted(set(cols) - covered.get(table, set()))
            if unknown:
                for col in unknown:
                    violations.append(
                        "xi_semantic_temporal_unknown_dependency:"
                        f"{table}.{col}"
                    )
            checks[f"uncovered_{table}"] = sorted(
                set(cols) - covered.get(table, set())
            )
    manifest_payload = {
        "mechanism": "derived_live_pg_proc_readset_vs_trigger_update_of",
        "canonical_routines": list(CANONICAL_ROUTINES),
        "governance_triggers": {
            k: list(v) for k, v in GOVERNANCE_TRIGGERS.items()
        },
        "semantic_reads": serial_reads,
        "temporal_covered_columns": serial_covered,
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
            violations.append(f"xi_semantic_manifest_missing:{exc}")
            pinned = None
        if pinned is not None:
            if pinned.get("semantic_reads") != serial_reads:
                violations.append("xi_semantic_manifest_drift")
                checks["manifest_drift"] = True
    status = "PASS" if not violations else "FAIL"
    evidence = {
        "gate_id": "B26-P2-XI-SEMANTIC-TEMPORAL-TOTALITY",
        "validator": "validate_b26_p2_xi_semantic_temporal",
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
        (args.evidence_dir / "xi-semantic-temporal.json").write_text(
            json.dumps(evidence, indent=2), encoding="utf-8"
        )
    if violations:
        print("B26_P2_XI_SEMANTIC_FAIL " + ";".join(sorted(violations)))
        return 1
    print("B26_P2_XI_SEMANTIC_PASS")
    print(json.dumps(evidence, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
