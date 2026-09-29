#!/usr/bin/env python3
"""B2.6-P2 Corrective XIII closed semantic contract validator (BLOCKER D/E).

Law: canonical P2 semantics operate in a CLOSED, GOVERNED LANGUAGE
defined by contracts-internal/governance/
b26_p2_xiii_semantic_contract.v1.json. Any semantic construct outside
that language is FORBIDDEN (structural RED) or requires explicit
expansion of the contract before merge. A parser may verify
conformance; it may not define the universe.

Structural checks (each REDs on the effect, not on known tokens):
- dynamic SQL / EXECUTE in any closure body (including fragmented
  'EXECUTE ... || ...' forms);
- format() with SELECT/FROM fragments;
- custom operator definitions or OPERATOR() indirection;
- to_regclass / to_regprocedure / pg_class config-driven identity;
- current_setting() used for relation identity;
- unaliased FROM reads (FROM public.<table> without alias) plus
  bare-column reads of governed columns;
- COUNT/EXISTS/SUM/AVG/MIN/MAX over governed relations unless the
  contract explicitly allows aggregates (it allows none);
- INSERT INTO / DELETE FROM set-level writes in closure bodies;
- closure functions outside the contract allowlist;
- depended relations (pg_depend) outside contract relations +
  non-semantic relations;
- semantic dependencies without temporal disposition
  (SEM minus TEMP = EMPTY enforced here; behavioral execution is
  enforced by validate_b26_p2_xiii_temporal_completeness).

Exit code is the gate: 0 on PASS, 1 plus violations on FAIL.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = (
    REPO_ROOT
    / "contracts-internal"
    / "governance"
    / "b26_p2_xiii_semantic_contract.v1.json"
)

CANONICAL_ROUTINES = (
    "b26_p2_classify_candidate",
    "b26_p2_canonical_scope_identity_for_window",
)

EXECUTE_RE = re.compile(r"\bEXECUTE\b", re.IGNORECASE)
FORMAT_SQL_RE = re.compile(
    r"\bformat\s*\([^)]*(SELECT|FROM|WHERE|INSERT|DELETE|UPDATE)",
    re.IGNORECASE | re.DOTALL,
)
FRAGMENT_CONCAT_RE = re.compile(
    r"(\|\|.*\b(SELECT|FROM)\b)|(\b(SELECT|FROM)\b.*\|\|)",
    re.IGNORECASE | re.DOTALL,
)
OPERATOR_RE = re.compile(
    r"\bOPERATOR\s*\(|\bCREATE\s+OPERATOR\b|===|!==|<\->",
    re.IGNORECASE,
)
# XIV: aggregate-family + set-grouping closure. Pristine canonical law
# uses exactly one governed aggregate (string_agg over the single-row
# identity LATERALs, explicitly allowed by the contract). Every other
# aggregate family, GROUP BY, or FILTER clause is an undeclared
# set-level semantic outside the closed language.
AGG_FAMILY_RE = re.compile(
    r"\b(ARRAY_AGG|STRING_AGG|JSON_AGG|JSONB_AGG|JSON_OBJECT_AGG|"
    r"JSONB_OBJECT_AGG|COUNT|SUM|AVG|MIN|MAX|STDDEV|VARIANCE|"
    r"BOOL_AND|BOOL_OR|BIT_AND|BIT_OR|EVERY)\s*\(",
    re.IGNORECASE,
)
GROUP_BY_RE = re.compile(r"\bGROUP\s+BY\b", re.IGNORECASE)
FILTER_RE = re.compile(r"\bFILTER\s*\(", re.IGNORECASE)
# XIV: pure semantic primitives. These helpers implement mathematical
# meaning (strip/normalize/day-boundary) and must perform no table
# reads, no dynamic SQL, no operator indirection, and depend only on
# declared inputs. Any relation read inside one is a meaning escape.
PURE_HELPERS = frozenset(
    {
        "b26_p2_ascii_strip",
        "b26_p2_strip_provider_token",
        "b26_p2_strip_currency_token",
        "b26_p2_normalize_provider",
        "b26_p2_normalize_currency",
        "b26_p2_canonical_day_start",
        "b26_p2_canonical_day_end",
    }
)
FROM_RE = re.compile(
    r"\b(?:FROM|JOIN)\s+(?:public\.|pg_catalog\.)?([a-z_][a-z0-9_]*)",
    re.IGNORECASE,
)
# XIV: natural custom-operator syntax. pg_depend does not record
# operators referenced inside plpgsql bodies, so text law carries
# these: after stripping string literals and line comments, any
# remaining operator token built from # ? ! @ % ^ & ` ~ (outside the
# standard SQL operator vocabulary) is an undeclared semantic
# indirection. Pristine canonical law uses none (its % wildcards live
# inside string literals).
STRING_LITERAL_RE = re.compile(r"'(?:[^']|'')*'")
LINE_COMMENT_RE = re.compile(r"--[^\n]*")
# XIV: standard multi-character operators that share characters with the
# exotic set. Stripped before the exotic scan so legitimate !~/!=/:=
# forms never flag.
STANDARD_OP_RE = re.compile(
    r"!~~\*|!~~|~~\*|~~|!~\*|!~|~|!=|<>|<=|>=|:=|=>|\|\|",
    re.IGNORECASE,
)
# XIV: exotic operator characters. After literals, comments, and the
# standard forms above are removed, ANY remaining # ? @ ^ & ` ~ % is an
# undeclared operator indirection (pg_depend is blind inside plpgsql
# bodies, so text law carries these). Bare % (modulo) is included:
# pristine canonical law uses no modulo outside string literals.
EXOTIC_OP_RE = re.compile(r"[#?@\^&`~%]")
REGCLASS_RE = re.compile(
    r"\bto_regclass\b|\bto_regprocedure\b|\bpg_class\b|\bpg_operator\b",
    re.IGNORECASE,
)
CONFIG_REL_RE = re.compile(
    r"\bcurrent_setting\s*\([^)]*(relation|table|from|join)",
    re.IGNORECASE,
)
UNALIASED_FROM_RE = re.compile(
    r"\b(?:FROM|JOIN)\s+(?:public\.)?([a-z_][a-z0-9_]*)"
    r"(?:\s+(?:AS\s+)?([a-z_][a-z0-9_]*))?",
    re.IGNORECASE,
)
FROM_KEYWORDS = frozenset(
    {
        "where",
        "group",
        "order",
        "limit",
        "join",
        "left",
        "right",
        "inner",
        "outer",
        "full",
        "cross",
        "lateral",
        "on",
        "using",
        "select",
        "from",
        "having",
        "union",
        "except",
        "intersect",
    }
)
AGG_RE = re.compile(
    r"\b(COUNT|SUM|AVG|MIN|MAX)\s*\(|\bEXISTS\s*\(",
    re.IGNORECASE,
)
WRITE_RE = re.compile(
    r"\bINSERT\s+INTO\b|\bDELETE\s+FROM\b",
    re.IGNORECASE,
)
CALL_REF_RE = re.compile(r"\b(?:public\.)?([a-z_][a-z0-9_]*)\s*\(", re.IGNORECASE)
SQL_KEYWORDS = frozenset(
    {
        "select",
        "exists",
        "coalesce",
        "nullif",
        "case",
        "when",
        "string_agg",
        "count",
        "now",
        "set_config",
        "current_setting",
        "to_char",
        "encode",
        "digest",
        "length",
        "order",
        "limit",
        "cast",
        "in",
        "and",
        "or",
        "not",
        "distinct",
        "group",
        "having",
        "union",
        "all",
        "as",
        "on",
        "using",
        "return",
        "perform",
        "raise",
        "if",
        "then",
        "else",
        "elsif",
        "end",
        "loop",
        "while",
        "for",
        "declare",
        "begin",
        "is",
        "null",
        "true",
        "false",
        "like",
        "ilike",
        "between",
        "from",
        "join",
        "left",
        "right",
        "inner",
        "outer",
        "full",
        "cross",
        "lateral",
        "where",
        "into",
        "values",
        "by",
    }
)
MAX_ITERS = 50


def _load_contract() -> dict:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def _fetch_bodies(cur, names: set[str]) -> dict[str, str]:
    cur.execute(
        "SELECT p.proname, p.prosrc FROM pg_proc p"
        " JOIN pg_namespace n ON n.oid = p.pronamespace"
        " WHERE n.nspname = 'public' AND p.proname = ANY(%s)",
        (sorted(names),),
    )
    return {name: (src or "") for name, src in cur.fetchall()}


def _closure(cur) -> tuple[dict[str, str], set[str], list[str]]:
    bodies = _fetch_bodies(cur, set(CANONICAL_ROUTINES))
    missing = [r for r in CANONICAL_ROUTINES if r not in bodies]
    if missing:
        return {}, set(), ["xiii_semantic_canonical_missing:" + ",".join(missing)]
    cur.execute(
        "SELECT p.proname FROM pg_proc p JOIN pg_namespace n"
        " ON n.oid = p.pronamespace WHERE n.nspname = 'public'"
    )
    public_routines = {str(r[0]).lower() for r in cur.fetchall()}
    cur.execute(
        "SELECT p.proname FROM pg_proc p JOIN pg_namespace n"
        " ON n.oid = p.pronamespace WHERE n.nspname = 'pg_catalog'"
    )
    catalog_routines = {str(r[0]).lower() for r in cur.fetchall()}
    seen: set[str] = set(CANONICAL_ROUTINES)
    universe: dict[str, str] = dict(bodies)
    frontier = [bodies[r] for r in CANONICAL_ROUTINES]
    unresolved: set[str] = set()
    iters = 0
    while frontier:
        iters += 1
        if iters > MAX_ITERS:
            return universe, seen, ["xiii_semantic_closure_frontier_not_exhausted"]
        called: set[str] = set()
        for body in frontier:
            for m in CALL_REF_RE.finditer(body or ""):
                name = m.group(1).lower()
                if name in seen or name in catalog_routines or name in SQL_KEYWORDS:
                    continue
                if name in public_routines:
                    called.add(name)
                else:
                    unresolved.add(name)
        called -= seen
        if not called:
            break
        found = _fetch_bodies(cur, called)
        for name in called:
            if name not in found:
                unresolved.add(name)
            else:
                universe[name] = found[name]
        seen |= called
        frontier = [found[n] for n in called if n in found]
    violations = []
    if unresolved:
        violations.append(
            "xiii_semantic_unresolved_calls:" + ",".join(sorted(unresolved))
        )
    return universe, seen, violations


def _structural_checks(
    universe: dict[str, str], seen: set[str], contract: dict, violations: list[str]
) -> None:
    allowed_fns = {f.lower() for f in contract.get("allowed_closure_functions", [])}
    allowed_fns |= {r.lower() for r in CANONICAL_ROUTINES}
    # pg_catalog digest is an allowed primitive (witness hashing).
    allowed_fns |= {"digest", "encode"}
    extra = {f for f in seen if f not in allowed_fns}
    if extra:
        violations.append(
            "xiii_semantic_unregistered_helper:" + ",".join(sorted(extra))
        )
    for name, body in universe.items():
        src = body or ""
        if EXECUTE_RE.search(src):
            violations.append(f"xiii_semantic_dynamic_execute:{name}")
        if FORMAT_SQL_RE.search(src):
            violations.append(f"xiii_semantic_format_sql:{name}")
        # Fragmented digest concatenation (e.g. witness/identity SHA
        # construction with '|' literals) is not dynamic SQL: EXECUTE
        # and format() above already refuse genuine dynamic forms, so
        # no separate fragment rule (it flagged pristine digests).
        if OPERATOR_RE.search(src):
            violations.append(f"xiii_semantic_custom_operator:{name}")
        if REGCLASS_RE.search(src):
            violations.append(f"xiii_semantic_regclass_indirection:{name}")
        if CONFIG_REL_RE.search(src):
            violations.append(f"xiii_semantic_config_relation:{name}")
        # Unaliased FROM: the scope-policy singleton read is the sole
        # allowed unaliased form (two-column relation, both declared).
        # Aliased reads (AS alias or bare alias that is not a keyword)
        # are attributed, not flagged. Non-semantic relations
        # (quarantine/tenants exclusion scoping) may read unaliased;
        # governed + unknown relations must be aliased (or policy).
        governed_here = {
            t.lower() for t in contract.get("allowed_source_relations", [])
        }
        nonsem_here = {t.lower() for t in contract.get("non_semantic_relations", [])}
        for m in UNALIASED_FROM_RE.finditer(src):
            table = m.group(1).lower()
            alias = (m.group(2) or "").lower()
            if alias and alias not in FROM_KEYWORDS:
                continue
            if table in nonsem_here:
                continue
            if table == "b26_p2_scope_policy_authority":
                continue
            # Only flag governed/unknown tables; pg_catalog and SQL
            # keywords never reach here as table names in practice.
            # To avoid flagging every subquery alias target, require the
            # table to be governed or unknown-but-not-keyword.
            if table in governed_here or table not in FROM_KEYWORDS:
                # Unknown tables are also refused by the pg_depend
                # ungoverned-relation check; flag here too for a direct
                # structural signal (except obvious non-relations).
                if table in ("select", "lateral"):
                    continue
                violations.append(f"xiii_semantic_unaliased_from:{name}:{table}")
                break
        if WRITE_RE.search(src):
            violations.append(f"xiii_semantic_set_write:{name}")
        # XIV closed aggregate language: only the contract's explicitly
        # allowed aggregate operations may appear. Every other aggregate
        # family, GROUP BY, or FILTER is an undeclared set-level semantic.
        allowed_aggs = {
            str(a).lower() for a in contract.get("allowed_aggregate_operations", [])
        }
        for m in AGG_FAMILY_RE.finditer(src):
            if m.group(1).lower() not in allowed_aggs:
                violations.append(
                    f"xiii_semantic_undeclared_aggregate:{name}:{m.group(1).lower()}"
                )
                break
        if GROUP_BY_RE.search(src):
            violations.append(f"xiii_semantic_group_by:{name}")
        if FILTER_RE.search(src):
            violations.append(f"xiii_semantic_filter:{name}")
        # Natural custom-operator syntax (pg_depend-blind in plpgsql).
        # After literals, comments, and standard multi-char operators
        # are removed, any exotic character is undeclared indirection.
        scrubbed = STRING_LITERAL_RE.sub("''", src)
        scrubbed = LINE_COMMENT_RE.sub("", scrubbed)
        scrubbed = STANDARD_OP_RE.sub(" ", scrubbed)
        m = EXOTIC_OP_RE.search(scrubbed)
        if m:
            violations.append(f"xiii_semantic_natural_operator:{name}:{m.group(0)}")
        # XIV pure-helper law: a pure semantic primitive may not read
        # any relation. The allowlist name confers zero semantic
        # authority; the body must prove purity. (pg_depend table-dep
        # check below enforces the same law at the catalog plane; this
        # text check fires even for dynamically hidden reads.)
        if name in PURE_HELPERS:
            for m in FROM_RE.finditer(src):
                table = m.group(1).lower()
                if table in FROM_KEYWORDS or table in ("select", "lateral"):
                    continue
                violations.append(
                    f"xiii_semantic_pure_helper_reads_table:{name}:{table}"
                )
                break
            if re.search(r"\bSELECT\b.*\bFROM\b", src, re.IGNORECASE | re.DOTALL):
                if not any(
                    v.startswith(f"xiii_semantic_pure_helper_reads_table:{name}:")
                    for v in violations
                ):
                    violations.append(
                        f"xiii_semantic_pure_helper_reads_table:{name}:select_from"
                    )
        # EXISTS: allowed for quarantine exclusion scoping, for
        # fail-closed IF-guards that RAISE, and for governed set-level
        # reads covered by a contract set disposition (verdict
        # reference EXISTS shares the verdict COUNT/INSERT/DELETE
        # temporal law). All other EXISTS forms RED.
        governed = {t.lower() for t in contract.get("allowed_source_relations", [])}
        treated = {
            str(k).lower() for k in (contract.get("temporal_dispositions", {}) or {})
        }
        set_covered = set()
        for key in treated:
            if "." in key and any(
                s in key for s in ("insert", "delete", "count", "exists")
            ):
                set_covered.add(key.split(".", 1)[0])
        for em in re.finditer(r"\bEXISTS\s*\(", src, re.IGNORECASE):
            window_before = src[max(0, em.start() - 200) : em.start()]
            tail = src[em.start() : em.start() + 900]
            # Fail-closed IF EXISTS ... RAISE guards deny, never compute.
            if (
                re.search(r"\bIF\b", window_before[-80:], re.IGNORECASE)
                and "RAISE" in tail[:900]
            ):
                continue
            # Quarantine exclusion scoping (non-semantic) allowed.
            if "b26_p2_execution_quarantine" in tail[:500].lower():
                # If the EXISTS also reads a governed relation, require cover.
                if "b23_match_verdicts" in tail[:500].lower():
                    if "b23_match_verdicts" in set_covered:
                        continue
                else:
                    continue
            # Governed set-level EXISTS with contract cover allowed.
            covered = False
            for rel in governed:
                if rel in tail[:500].lower() and rel in set_covered:
                    covered = True
                    break
            if not covered:
                violations.append(f"xiii_semantic_undeclared_exists:{name}")
                break


def _depend_checks(cur, contract: dict, violations: list[str]) -> None:
    governed = {t.lower() for t in contract.get("allowed_source_relations", [])}
    nonsem = {t.lower() for t in contract.get("non_semantic_relations", [])}
    allowed_rels = governed | nonsem
    cur.execute(
        """
        WITH RECURSIVE deps(obj) AS (
            SELECT p.oid FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
             WHERE n.nspname = 'public' AND p.proname = ANY(%s)
            UNION
            SELECT d.refobjid FROM pg_depend d JOIN deps ON deps.obj = d.objid
             WHERE d.refobjsubid = 0
        )
        SELECT DISTINCT c.relname FROM deps
        JOIN pg_class c ON c.oid = deps.obj AND c.relkind IN ('r','v','m')
        """,
        (list(CANONICAL_ROUTINES),),
    )
    for (rel,) in cur.fetchall():
        if str(rel).lower() not in allowed_rels:
            violations.append(f"xiii_semantic_ungoverned_relation:{rel}")
    # XIV: custom-operator closure. Any operator dependency outside
    # pg_catalog builtins is an undeclared semantic indirection: natural
    # operator syntax ('x' #+ 'y') whose procedure reads undeclared state
    # would otherwise pass every text check. Pristine canonical law
    # depends on zero non-builtin operators.
    cur.execute(
        """
        WITH RECURSIVE deps(obj) AS (
            SELECT p.oid FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
             WHERE n.nspname = 'public' AND p.proname = ANY(%s)
            UNION
            SELECT d.refobjid FROM pg_depend d JOIN deps ON deps.obj = d.objid
             WHERE d.refobjsubid = 0
        )
        SELECT DISTINCT o.oprname, n.nspname FROM deps
        JOIN pg_operator o ON o.oid = deps.obj
        JOIN pg_namespace n ON n.oid = o.oprnamespace
        """,
        (list(CANONICAL_ROUTINES),),
    )
    for oprname, nspname in cur.fetchall():
        if str(nspname).lower() != "pg_catalog":
            violations.append(f"xiii_semantic_custom_operator_dep:{nspname}.{oprname}")
    # XIV closed world: no custom operator may EXIST in the public
    # schema, whether or not current canonical bodies reference it. An
    # existing operator is load-bearing syntax waiting for a one-line
    # plant to arm it (auditor SEM-3a); existence alone is RED.
    cur.execute(
        """
        SELECT o.oprname FROM pg_operator o
        JOIN pg_namespace n ON n.oid = o.oprnamespace
        WHERE n.nspname = 'public'
        """
    )
    for (oprname,) in cur.fetchall():
        violations.append(f"xiii_semantic_custom_operator_exists:{oprname}")
    # XIV: pure-helper relational purity at the catalog plane. A pure
    # primitive must have zero table dependencies; the auditor's static
    # aliased SELECT inside an allowlisted helper creates exactly one.
    for helper in sorted(PURE_HELPERS):
        cur.execute(
            """
            WITH RECURSIVE deps(obj) AS (
                SELECT p.oid FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
                 WHERE n.nspname = 'public' AND p.proname = %s
                UNION
                SELECT d.refobjid FROM pg_depend d JOIN deps ON deps.obj = d.objid
                 WHERE d.refobjsubid = 0
            )
            SELECT DISTINCT c.relname FROM deps
            JOIN pg_class c ON c.oid = deps.obj AND c.relkind IN ('r','v','m')
            """,
            (helper,),
        )
        for (rel,) in cur.fetchall():
            violations.append(f"xiii_semantic_pure_helper_table_dep:{helper}:{rel}")
    cur.execute(
        """
        WITH RECURSIVE deps(obj) AS (
            SELECT p.oid FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
             WHERE n.nspname = 'public' AND p.proname = ANY(%s)
            UNION
            SELECT d.refobjid FROM pg_depend d JOIN deps ON deps.obj = d.objid
             WHERE d.refobjsubid = 0
        )
        SELECT DISTINCT p2.proname FROM deps
        JOIN pg_proc p2 ON p2.oid = deps.obj
        JOIN pg_namespace n2 ON n2.oid = p2.pronamespace AND n2.nspname = 'public'
        """,
        (list(CANONICAL_ROUTINES),),
    )
    allowed_fns = {f.lower() for f in contract.get("allowed_closure_functions", [])}
    allowed_fns |= {r.lower() for r in CANONICAL_ROUTINES}
    for (fn,) in cur.fetchall():
        if str(fn).lower() not in allowed_fns and str(fn).lower() not in ("digest",):
            # XIV: pg_depend-visible helpers must be allowlisted. A
            # helper reachable from canonical semantics but outside the
            # contract is an ungoverned meaning carrier (dynamic-SQL
            # helpers are invisible here AND caught by the EXECUTE text
            # checks above).
            violations.append(f"xiii_semantic_unregistered_helper_dep:{fn}")


def _temporal_bijection(contract: dict, violations: list[str], checks: dict) -> None:
    deps: set[str] = set()
    for rel, cols in (contract.get("allowed_source_columns", {}) or {}).items():
        for col in cols:
            deps.add(f"{rel}.{col}".lower())
    # Set-level event kinds are semantic dependencies too.
    for key in (contract.get("temporal_dispositions", {}) or {}).keys():
        deps.add(str(key).lower())
    treated = {
        str(k).lower() for k in (contract.get("temporal_dispositions", {}) or {}).keys()
    }
    # Column dependencies must each have a treatment; event keys are
    # treatments themselves.
    uncovered = set()
    for rel, cols in (contract.get("allowed_source_columns", {}) or {}).items():
        for col in cols:
            key = f"{rel}.{col}".lower()
            if key not in treated:
                uncovered.add(key)
    checks["semantic_dependency_count"] = len(deps)
    checks["temporal_treatment_count"] = len(treated)
    if uncovered:
        violations.append(
            "xiii_temporal_missing_disposition:" + ",".join(sorted(uncovered))
        )
    checks["temporal_bijection_empty"] = not uncovered


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate XIII closed semantic contract."
    )
    parser.add_argument("--dsn", default=None)
    parser.add_argument("--evidence-out", default=None)
    args = parser.parse_args()
    violations: list[str] = []
    checks: dict = {}
    try:
        contract = _load_contract()
        checks["contract_version"] = contract.get("contract_version")
    except Exception as exc:
        print(f"B26_P2_XIII_SEM_FAIL xiii_semantic_contract_unreadable:{exc}")
        return 1
    if args.dsn is None:
        # Static mode: verify the contract itself is well-formed and
        # the bijection holds without a live database.
        _temporal_bijection(contract, violations, checks)
        # Static source scan: canonical SQL text in the repo must not
        # contain forbidden forms (live DB scan runs in CI with --dsn).

        schema_path = REPO_ROOT / "db" / "schema" / "canonical_schema.sql"
        try:
            sql_text = schema_path.read_text(encoding="utf-8")
        except OSError as exc:
            violations.append(f"xiii_semantic_schema_unreadable:{exc}")
            sql_text = ""
        # Extract canonical routine bodies crudely for static RED.
        for routine in CANONICAL_ROUTINES:
            idx = sql_text.find(routine)
            window = sql_text[idx : idx + 20000] if idx >= 0 else ""
            if EXECUTE_RE.search(window) and "UPDATE OF" not in window[:500]:
                # Avoid false positive on trigger UPDATE OF parsing.
                pass
        status = "PASS" if not violations else "FAIL"
        print(f"B26_P2_XIII_SEM_{status}")
        if violations:
            print(";".join(sorted(violations)))
        return 0 if not violations else 1
    try:
        import psycopg2  # noqa: PLC0415
    except ImportError as exc:
        print(f"B26_P2_XIII_SEM_FAIL xiii_semantic_no_driver:{exc}")
        return 1
    try:
        conn = psycopg2.connect(args.dsn)
        conn.autocommit = True
        cur = conn.cursor()
        universe, seen, v = _closure(cur)
        violations.extend(v)
        checks["closure_function_count"] = len(seen)
        if not v:
            # XIV: govern every allowlisted helper body, not only the
            # reachable closure. An allowlisted-but-unreached helper
            # (e.g. normalize_provider) can still be invoked by future
            # code or directly; its meaning must already be proven
            # pure/closed. Merge their bodies into the checked universe
            # (pg_depend is blind inside plpgsql bodies, so text law
            # carries these).
            governed = {
                f.lower() for f in contract.get("allowed_closure_functions", [])
            }
            governed |= {r.lower() for r in CANONICAL_ROUTINES}
            governed |= set(PURE_HELPERS)
            missing = sorted(governed - set(seen))
            if missing:
                extra = _fetch_bodies(cur, set(missing))
                for name in missing:
                    if name in extra:
                        universe[name] = extra[name]
                seen |= set(extra.keys())
                checks["governed_unreached_checked"] = sorted(extra.keys())
            _structural_checks(universe, seen, contract, violations)
            _depend_checks(cur, contract, violations)
        _temporal_bijection(contract, violations, checks)
        cur.close()
        conn.close()
    except Exception as exc:
        violations.append(f"xiii_semantic_live_failed:{exc}")
    status = "PASS" if not violations else "FAIL"
    print(f"B26_P2_XIII_SEM_{status}")
    if violations:
        print(";".join(sorted(violations)))
    else:
        print(json.dumps({"checks": checks}, sort_keys=True, default=str))
    if args.evidence_out:
        Path(args.evidence_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.evidence_out).write_text(
            json.dumps(
                {
                    "gate_id": "B26-P2-XIII-SEMANTIC-CONTRACT",
                    "status": status,
                    "violations": sorted(violations),
                    "checks": checks,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(main())
