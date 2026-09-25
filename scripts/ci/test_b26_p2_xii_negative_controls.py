#!/usr/bin/env python3
"""B2.6-P2 Corrective XII non-vacuous falsification battery (SEM/TEMP).

For each XII mutant class the battery demonstrates:
  pristine lane -> validator GREEN
  plant genuine member of the class (no validator vocabulary tokens) -> RED
  restore exact bytes -> GREEN

Classes: SEM-1 param-qualified helper, SEM-2 depth-6 chain, SEM-3
view/lookup, SEM-4 set-level count, TEMP-1 weakened governed trigger
(behavioral permit while retaining all textual references).

Exit code is the gate: 0 only when every mutant REDs and the lane is
byte-restored GREEN. Any residual mutant fails closed.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SEM_VALIDATOR = [
    sys.executable, "scripts/ci/validate_b26_p2_xii_semantic_closure.py",
    "--manifest", str(
        REPO_ROOT / "contracts-internal" / "governance"
        / "b26_p2_xii_semantic_dependency_manifest.json"
    ),
]
TEMP_VALIDATOR = [
    sys.executable, "scripts/ci/validate_b26_p2_xii_temporal_behavioral.py",
]

IDENTITY_FN = "b26_p2_canonical_scope_identity_for_window"
# Anchor inside the identity body: the verdict-reference lateral. Each
# mutant appends a tautological conjunct here, preserving behavior
# exactly while creating a genuine new semantic dependency.
ANCHOR = "AND public.b26_p2_ascii_strip(COALESCE(v.canonical_commerce_reference,'')) <> ''"


def _run(cmd, dsn):
    proc = subprocess.run(
        cmd + ["--dsn", dsn], capture_output=True, text=True,
        cwd=str(REPO_ROOT),
    )
    first = (proc.stdout.strip().splitlines() or [""])[0]
    return proc.returncode, first


def _backup(cur, fn):
    cur.execute(
        "SELECT p.prosrc FROM pg_proc p JOIN pg_namespace n"
        " ON n.oid=p.pronamespace WHERE n.nspname='public' AND p.proname=%s",
        (fn,),
    )
    return cur.fetchone()[0]


def _restore_fn(cur, fn, prosrc):
    cur.execute(
        "SELECT pg_get_function_identity_arguments(p.oid)"
        " FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace"
        " WHERE n.nspname='public' AND p.proname=%s",
        (fn,),
    )
    row = cur.fetchone()
    args = row[0] if row else ""
    cur.execute(
        "SELECT l.lanname FROM pg_proc p JOIN pg_language l"
        " ON l.oid = p.prolang JOIN pg_namespace n"
        " ON n.oid = p.pronamespace"
        " WHERE n.nspname='public' AND p.proname=%s",
        (fn,),
    )
    lang = cur.fetchone()[0]
    cur.execute(
        "CREATE OR REPLACE FUNCTION public.%s(%s) RETURNS text "
        "LANGUAGE %s SECURITY DEFINER SET search_path TO "
        "'pg_catalog', 'public' AS $XIIRESTORE$%s$XIIRESTORE$;"
        % (fn, args, lang, prosrc)
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run B2.6-P2 XII non-vacuous falsification battery."
    )
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--evidence-out", type=Path, default=None)
    args = parser.parse_args()
    results: dict = {}
    failures: list[str] = []
    try:
        import psycopg2  # noqa: PLC0415
    except ImportError as exc:
        print("B26_P2_XII_NEGATIVE_FAIL no_driver:%s" % exc)
        return 1
    conn = psycopg2.connect(args.dsn)
    conn.autocommit = True
    try:
        cur = conn.cursor()
        identity_src = _backup(cur, IDENTITY_FN)
        if ANCHOR not in identity_src:
            print("B26_P2_XII_NEGATIVE_FAIL anchor_missing")
            return 1

        def plant_identity(extra_sql, tautology):
            if extra_sql:
                cur.execute(extra_sql)
            mutated = identity_src.replace(
                ANCHOR, ANCHOR + " " + tautology, 1
            )
            assert mutated != identity_src
            _restore_fn(cur, IDENTITY_FN, mutated)

        def restore_all(helpers):
            for helper in helpers:
                cur.execute(
                    "DROP FUNCTION IF EXISTS public.%s CASCADE" % helper
                )
            cur.execute("DROP VIEW IF EXISTS public.b26_p2_xii_mut_view")
            cur.execute("DROP TABLE IF EXISTS public.b26_p2_xii_mut_count")
            _restore_fn(cur, IDENTITY_FN, identity_src)
            check = _backup(cur, IDENTITY_FN)
            return check == identity_src

        # Pristine GREEN for both validators.
        rc, first = _run(SEM_VALIDATOR, args.dsn)
        results["pristine_semantic"] = first[:80]
        if rc != 0:
            failures.append("pristine_semantic_not_green:%s" % first[:120])
        rc, first = _run(TEMP_VALIDATOR, args.dsn)
        results["pristine_temporal"] = first[:80]
        if rc != 0:
            failures.append("pristine_temporal_not_green:%s" % first[:120])

        mutants = [
            ("SEM-1 param-alias",
             "CREATE OR REPLACE FUNCTION public.b26_p2_xii_mut_mq("
             "v_row public.b23_match_verdicts) RETURNS text LANGUAGE plpgsql AS "
             "$$ BEGIN RETURN COALESCE(v_row.match_quality, 'x'); END $$;",
             ["b26_p2_xii_mut_mq"],
             "AND public.b26_p2_xii_mut_mq(v) = public.b26_p2_xii_mut_mq(v)"),
            ("SEM-2 depth-6",
             "CREATE OR REPLACE FUNCTION public.b26_p2_xii_d1(v_id uuid) "
             "RETURNS text LANGUAGE sql AS $$ SELECT COALESCE((SELECT v.match_quality "
             "FROM public.b23_match_verdicts AS v WHERE v.id = v_id), 'x') $$; "
             "CREATE OR REPLACE FUNCTION public.b26_p2_xii_d2(v_id uuid) "
             "RETURNS text LANGUAGE sql AS $$ SELECT public.b26_p2_xii_d1(v_id) $$; "
             "CREATE OR REPLACE FUNCTION public.b26_p2_xii_d3(v_id uuid) "
             "RETURNS text LANGUAGE sql AS $$ SELECT public.b26_p2_xii_d2(v_id) $$; "
             "CREATE OR REPLACE FUNCTION public.b26_p2_xii_d4(v_id uuid) "
             "RETURNS text LANGUAGE sql AS $$ SELECT public.b26_p2_xii_d3(v_id) $$; "
             "CREATE OR REPLACE FUNCTION public.b26_p2_xii_d5(v_id uuid) "
             "RETURNS text LANGUAGE sql AS $$ SELECT public.b26_p2_xii_d4(v_id) $$; "
             "CREATE OR REPLACE FUNCTION public.b26_p2_xii_d6(v_id uuid) "
             "RETURNS text LANGUAGE sql AS $$ SELECT public.b26_p2_xii_d5(v_id) $$;",
             ["b26_p2_xii_d1", "b26_p2_xii_d2", "b26_p2_xii_d3",
              "b26_p2_xii_d4", "b26_p2_xii_d5", "b26_p2_xii_d6"],
             "AND public.b26_p2_xii_d6(v.id) = public.b26_p2_xii_d6(v.id)"),
            ("SEM-3 view",
             "CREATE OR REPLACE VIEW public.b26_p2_xii_mut_view AS "
             "SELECT id, match_quality FROM public.b23_match_verdicts;",
             [],
             "AND EXISTS (SELECT 1 FROM public.b26_p2_xii_mut_view AS vv "
             "WHERE vv.id = v.id AND vv.match_quality = vv.match_quality)"),
            ("SEM-4 set-level",
             "CREATE TABLE public.b26_p2_xii_mut_count("
             "tenant_id uuid NOT NULL, n integer NOT NULL DEFAULT 0);",
             [],
             "AND (SELECT COUNT(*) FROM public.b26_p2_xii_mut_count AS xc "
             "WHERE xc.tenant_id = p_tenant) >= 0"),
        ]
        for label, helper_sql, helpers, tautology in mutants:
            plant_identity(helper_sql, tautology)
            rc, first = _run(SEM_VALIDATOR, args.dsn)
            results[label] = first[:160]
            if rc == 0:
                failures.append("%s_not_red" % label)
            if not restore_all(helpers):
                failures.append("%s_restore_not_byte_exact" % label)
                break
            rc, first = _run(SEM_VALIDATOR, args.dsn)
            if rc != 0:
                failures.append("%s_restore_not_green:%s" % (label, first[:120]))

        # TEMP-1: weaken the governed verdict trigger so it retains every
        # textual reference while permitting a conducted-affecting
        # mutation. The behavioral validator must RED; text-only
        # coverage stays GREEN (proving the behavioral delta).
        cur.execute(
            "SELECT p.prosrc FROM pg_proc p JOIN pg_namespace n"
            " ON n.oid=p.pronamespace WHERE n.nspname='public'"
            " AND p.proname='b26_p2_enforce_verdict_temporal_conservation'"
        )
        trigger_src = cur.fetchone()[0]
        weakened = trigger_src.replace(
            "RAISE EXCEPTION 'b26_p2_conducted_verdict_regression_refused'\n"
            "                                USING ERRCODE = '42501';",
            "-- xii-temp-mutant: permit regression\n"
            "                                RAISE NOTICE"
            " 'b26_p2_conducted_verdict_regression_refused';",
            1,
        )
        if weakened == trigger_src:
            failures.append("temp1_anchor_missing")
        else:
            cur.execute(
                "CREATE OR REPLACE FUNCTION public."
                "b26_p2_enforce_verdict_temporal_conservation() "
                "RETURNS trigger LANGUAGE plpgsql "
                "SET search_path TO 'pg_catalog', 'public' "
                "AS $XIITEMP$%s$XIITEMP$;" % weakened
            )
            rc, first = _run(TEMP_VALIDATOR, args.dsn)
            results["TEMP-1 weakened-trigger"] = first[:160]
            if rc == 0:
                failures.append("TEMP-1_not_red")
            cur.execute(
                "CREATE OR REPLACE FUNCTION public."
                "b26_p2_enforce_verdict_temporal_conservation() "
                "RETURNS trigger LANGUAGE plpgsql "
                "SET search_path TO 'pg_catalog', 'public' "
                "AS $XIITEMP$%s$XIITEMP$;" % trigger_src
            )
            check = _backup(
                cur, "b26_p2_enforce_verdict_temporal_conservation"
            )
            if check != trigger_src:
                failures.append("TEMP-1_restore_not_byte_exact")
            rc, first = _run(TEMP_VALIDATOR, args.dsn)
            results["restored_temporal"] = first[:80]
            if rc != 0:
                failures.append("restored_temporal_not_green:%s" % first[:120])
    finally:
        conn.close()
    status = "PASS" if not failures else "FAIL"
    evidence = {
        "gate_id": "B26-P2-XII-NONVACUOUS",
        "status": status,
        "violations": sorted(failures),
        "checks": results,
    }
    if args.evidence_out is not None:
        args.evidence_out.parent.mkdir(parents=True, exist_ok=True)
        args.evidence_out.write_text(
            json.dumps(evidence, indent=2), encoding="utf-8"
        )
    if failures:
        print("B26_P2_XII_NEGATIVE_FAIL " + ";".join(sorted(failures)))
        return 1
    print("B26_P2_XII_NEGATIVE_PASS")
    print(json.dumps(evidence, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
