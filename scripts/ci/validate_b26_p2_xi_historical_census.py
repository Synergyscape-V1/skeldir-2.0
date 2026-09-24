#!/usr/bin/env python3
"""B2.6-P2 Corrective XI historical-invariant + P3-eligibility validator.

Laws:
- D: every truth-capable post-upgrade row satisfies CURRENT XI
  invariants or carries an explicit non-authoritative disposition.
  The proof is POST-MIGRATION: the generic oracle scans final state,
  never the migration's repair branches.
- P3 boundary: only authenticated, current, canonical P2 state is
  visible as eligible for P3 reasoning. P3 consumes the predicate;
  P3 cannot override it.

Live mode (--dsn REQUIRED): oracle empty; P3 predicate present with
sane grants; smoke matrix (unknown task ineligible, receiptless task
ineligible). Full contradiction matrices live in the XI pytest
battery against isolated lanes.

Exit code is the gate: 0 on PASS, 1 plus a violation list on FAIL.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

P3_FUNCTION = "b26_p2_state_eligible_for_p3"
ORACLE_FUNCTION = "b26_p2_xi_invariant_oracle"


def _live_checks(
    admin_dsn: str, violations: list[str], checks: dict
) -> None:
    try:
        import psycopg2  # noqa: PLC0415
    except ImportError as exc:
        violations.append(f"xi_census_live_no_driver:{exc}")
        return
    try:
        conn = psycopg2.connect(admin_dsn)
        conn.autocommit = True
    except Exception as exc:
        violations.append(f"xi_census_live_connect_failed:{exc}")
        return
    try:
        cur = conn.cursor()
        for func in (ORACLE_FUNCTION, P3_FUNCTION):
            cur.execute(
                "SELECT count(*) FROM pg_proc p"
                " JOIN pg_namespace n ON n.oid = p.pronamespace"
                " WHERE n.nspname = 'public' AND p.proname = %s",
                (func,),
            )
            if int(cur.fetchone()[0]) != 1:
                violations.append(f"xi_census_missing_function:{func}")
        # Generic final-state oracle over CURRENT state. RLS is
        # FORCE on P2 tables, so the oracle is evaluated per tenant
        # with that tenant's GUC (the union is the full census; an
        # unset GUC sees nothing by fail-closed policy, never a
        # vacuous global PASS).
        try:
            cur.execute("SELECT id FROM public.tenants")
            tenant_ids = [str(r[0]) for r in cur.fetchall()]
        except Exception as exc:
            violations.append(f"xi_census_tenants_failed:{exc}"[:200])
            tenant_ids = []
        survivors = []
        try:
            for tenant_id in tenant_ids:
                cur.execute(
                    "SELECT set_config('app.current_tenant_id',"
                    " %s, false)",
                    (tenant_id,),
                )
                cur.execute(
                    f"SELECT violation_kind, task_ref"
                    f" FROM public.{ORACLE_FUNCTION}()"
                )
                survivors.extend(cur.fetchall())
        except Exception as exc:
            violations.append(f"xi_census_oracle_failed:{exc}"[:200])
            survivors = [("oracle_error", "?")]
        checks["oracle_survivors"] = [
            f"{k}:{r}" for k, r in survivors
        ]
        if survivors:
            for kind, ref in survivors:
                violations.append(
                    f"xi_census_oracle_survivor:{kind}:{ref}"
                )
        # P3 predicate smoke: unknown task + receiptless states are
        # ineligible; the predicate never returns NULL. The predicate
        # is tenant-bound (FORCE RLS): a spoofed tenant fails closed.
        try:
            cur.execute(
                "SELECT public.b26_p2_state_eligible_for_p3("
                "'no-such-task-00000000000000000000000000000000',"
                " '00000000-0000-0000-0000-000000000000'::uuid)"
            )
            if cur.fetchone()[0] is not False:
                violations.append("xi_p3_unknown_task_eligible")
            cur.execute(
                "SELECT public.b26_p2_state_eligible_for_p3(NULL, NULL)"
            )
            if cur.fetchone()[0] is not False:
                violations.append("xi_p3_null_task_eligible")
            cur.execute(
                "SELECT public.b26_p2_state_eligible_for_p3("
                "'no-such-task-00000000000000000000000000000000', NULL)"
            )
            if cur.fetchone()[0] is not False:
                violations.append("xi_p3_null_tenant_eligible")
            checks["p3_smoke"] = True
        except Exception as exc:
            violations.append(f"xi_p3_smoke_failed:{exc}"[:200])
        # P3 predicate is read-only classification: no grants on
        # underlying truth tables beyond what P2 already issues, and
        # the function itself is EXECUTE-restricted (no PUBLIC).
        cur.execute(
            """
            SELECT grantee FROM information_schema.role_routine_grants
            WHERE routine_schema = 'public'
              AND routine_name = 'b26_p2_state_eligible_for_p3'
            """
        )
        grantees = sorted(r[0] for r in cur.fetchall())
        checks["p3_grantees"] = grantees
        if "PUBLIC" in grantees:
            violations.append("xi_p3_public_execute")
        # Quarantine source law admits ingress-level disposition.
        cur.execute(
            """
            SELECT pg_get_constraintdef(c.oid)
            FROM pg_constraint c JOIN pg_class t ON t.oid = c.conrelid
            WHERE t.relname = 'b26_p2_execution_quarantine'
              AND c.conname = 'ck_b26_p2_quarantine_source'
            """
        )
        row = cur.fetchone()
        if row is None or "webhook_ingress_identities" not in row[0]:
            violations.append("xi_census_quarantine_source_law_stale")
    except Exception as exc:
        violations.append(f"xi_census_live_failed:{exc}"[:200])
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate B2.6-P2 XI historical census + P3 boundary."
    )
    parser.add_argument("--dsn", default=None)
    parser.add_argument("--evidence-dir", type=Path, default=None)
    parser.add_argument("--evidence-out", type=Path, default=None)
    args = parser.parse_args()
    violations: list[str] = []
    checks: dict = {}
    migration = (
        REPO_ROOT / "alembic" / "versions" / "007_skeldir_foundation"
        / "202609240002_b26_p2_corrective_xi_p2_core_closure.py"
    )
    if not migration.is_file():
        violations.append("xi_census_migration_absent")
    if args.dsn is None:
        violations.append("xi_census_live_check_required_no_dsn")
    else:
        _live_checks(args.dsn, violations, checks)
    status = "PASS" if not violations else "FAIL"
    evidence = {
        "gate_id": "B26-P2-XI-HISTORICAL-CENSUS-P3",
        "validator": "validate_b26_p2_xi_historical_census",
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
        (args.evidence_dir / "xi-historical-census.json").write_text(
            json.dumps(evidence, indent=2), encoding="utf-8"
        )
    if violations:
        print("B26_P2_XI_CENSUS_FAIL " + ";".join(sorted(violations)))
        return 1
    print("B26_P2_XI_CENSUS_PASS")
    print(json.dumps(evidence, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
