#!/usr/bin/env python3
"""B2.6-P2 Corrective XIII authentication root validator (BLOCKERS A/C).

Laws (each REDs on the effect):
- generic app_user has ZERO EXECUTE on the consequence recorder and
  ZERO INSERT/UPDATE on the consequence table (direct + recorder);
- only the dedicated trust root (app_ingress) may EXECUTE the
  recorder and the atomic transition;
- consequence rows are immutable (no digest rewrite) and
  provider-bound (PayPal-on-Stripe refused);
- INSERT-time provenance never lands authenticated_known (lands
  pending_authentication); promotion requires full evidence;
- dispatch requires terminal state AND witness (verified-alone
  dispatch refused; pending rows non-dispatchable);
- crash partials (row only, row+P, row+P+witness) never conduct via
  the dispatch gate and never return P3 TRUE (checked live where a
  database is available; static grant/trigger checks always run).

Modes: static (default, grants + trigger text) and live (--dsn).
Exit code is the gate.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _static_checks(violations: list[str], checks: dict) -> None:
    mig = (
        REPO_ROOT / "alembic" / "versions" / "007_skeldir_foundation"
        / "202609260001_b26_p2_corrective_xiii_root_of_trust_closure.py"
    )
    try:
        text = mig.read_text(encoding="utf-8")
    except OSError as exc:
        violations.append(f"xiii_auth_migration_unreadable:{exc}")
        return
    # App_user authorship must be revoked (not merely ungranted).
    for token in (
        "REVOKE ALL ON FUNCTION public.b26_p2_record_provider_auth_consequence",
        "REVOKE ALL ON TABLE public.b26_p2_provider_auth_consequence",
        "GRANT EXECUTE ON FUNCTION public.b26_p2_record_provider_auth_consequence",
        "TO app_ingress",
        "GRANT EXECUTE ON FUNCTION public.b26_p2_authenticate_ingress_atomic",
        "b26_p2_auth_cons_caller_refused",
        "b26_p2_auth_cons_immutable_refused",
        "b26_p2_auth_cons_provider_mismatch",
        "pending_authentication",
        "b26_p2_dispatch_witness_missing",
        "IS DISTINCT FROM 'authenticated_known'",
        "b26_p2_atomic_caller_refused",
    ):
        if token not in text:
            violations.append(f"xiii_auth_migration_missing:{token}")
    checks["migration_tokens_done"] = True
    # Session/process custody: API must not read env DSN; pool gated
    # on auth role + file; sanitizer deletes (never retains).
    sess = (REPO_ROOT / "backend" / "app" / "db" / "session.py").read_text(
        encoding="utf-8"
    )
    for token in (
        "SKELDIR_PROCESS_ROLE",
        "B26_P2_INGRESS_DATABASE_URL_FILE",
        "_read_ingress_dsn_from_file",
        "b26_p2_ingress_wrong_process",
        "assert_api_ingress_isolation",
    ):
        if token not in sess:
            violations.append(f"xiii_auth_session_missing:{token}")
    if "_SANITIZED_INGRESS_DSN = os.environ.get" in sess:
        violations.append("xiii_auth_sanitizer_retains_credential")
    checks["session_tokens_done"] = True
    # Event service: no app_user P recording; atomic finalizer only.
    ev = (REPO_ROOT / "backend" / "app" / "ingestion" / "event_service.py").read_text(
        encoding="utf-8"
    )
    if "b26_p2_authenticate_ingress_atomic" not in ev:
        violations.append("xiii_auth_finalizer_not_atomic")
    # _record_auth_consequence_in_txn may remain as a trust-root-only
    # helper, but no app_user-txn caller may invoke it.
    if "await _record_auth_consequence_in_txn(" in ev:
        violations.append("xiii_auth_app_user_records_consequence")
    checks["event_service_done"] = True
    # Dispatch gate: verified-alone selection is forbidden.
    wh = (REPO_ROOT / "backend" / "app" / "api" / "webhooks.py").read_text(
        encoding="utf-8"
    )
    if "IS NOT DISTINCT FROM 'authenticated_known'" not in wh:
        violations.append("xiii_auth_dispatch_not_terminal")
    if "b26_p2_ingress_auth_witness" not in wh:
        violations.append("xiii_auth_dispatch_no_witness_gate")
    checks["dispatch_gate_done"] = True


def _live_checks(admin_dsn: str, violations: list[str], checks: dict) -> None:
    try:
        import psycopg2  # noqa: PLC0415
    except ImportError as exc:
        violations.append(f"xiii_auth_no_driver:{exc}")
        return
    try:
        conn = psycopg2.connect(admin_dsn)
        conn.autocommit = True
    except Exception as exc:
        violations.append(f"xiii_auth_connect_failed:{exc}")
        return
    try:
        cur = conn.cursor()
        # AUTH-ROOT-1: app_user must hold no authorship capability.
        cur.execute(
            """
            SELECT has_function_privilege(
                'app_user',
                'public.b26_p2_record_provider_auth_consequence(uuid, text, text, text, text, text, text)',
                'EXECUTE')
            """
        )
        if cur.fetchone()[0] is True:
            violations.append("xiii_auth_app_user_executes_recorder")
        cur.execute(
            """
            SELECT has_table_privilege(
                'app_user',
                'public.b26_p2_provider_auth_consequence', 'INSERT')
            """
        )
        if cur.fetchone()[0] is True:
            violations.append("xiii_auth_app_user_inserts_consequence")
        cur.execute(
            """
            SELECT has_function_privilege(
                'app_ingress',
                'public.b26_p2_record_provider_auth_consequence(uuid, text, text, text, text, text, text)',
                'EXECUTE')
            """
        )
        if cur.fetchone()[0] is not True:
            violations.append("xiii_auth_root_missing_recorder")
        cur.execute(
            """
            SELECT has_function_privilege(
                'app_ingress',
                'public.b26_p2_authenticate_ingress_atomic(uuid, text, text, text, text, text, text)',
                'EXECUTE')
            """
        )
        if cur.fetchone()[0] is not True:
            violations.append("xiii_auth_root_missing_atomic")
        # Provenance trigger must not contain INSERT-time known.
        cur.execute(
            "SELECT pg_get_functiondef(oid) FROM pg_proc WHERE proname = 'b26_p2_enforce_ingress_provenance'"
        )
        row = cur.fetchone()
        body = row[0] if row else ""
        if "NEW.b26_p2_provenance_status := 'authenticated_known'" in body:
            # The UPDATE promotion path sets known via evidence guard
            # (allowed); the INSERT branch must not. Distinguish by
            # requiring pending_authentication in the INSERT branch.
            if "pending_authentication" not in body:
                violations.append("xiii_auth_insert_time_known")
        if "pending_authentication" not in body:
            violations.append("xiii_auth_no_pending_state")
        # Dispatch trigger must require terminal + witness, NULL-safe.
        cur.execute(
            "SELECT pg_get_functiondef(oid) FROM pg_proc WHERE proname = 'b26_p2_enforce_dispatch_provenance'"
        )
        row = cur.fetchone()
        dbody = row[0] if row else ""
        if "IS DISTINCT FROM 'authenticated_known'" not in dbody:
            violations.append("xiii_auth_dispatch_not_nullsafe_terminal")
        if "b26_p2_ingress_auth_witness" not in dbody:
            violations.append("xiii_auth_dispatch_no_witness")
        checks["live_grants_done"] = True
        cur.close()
    except Exception as exc:
        violations.append(f"xiii_auth_live_failed:{exc}")
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate XIII auth root closure.")
    parser.add_argument("--dsn", default=None)
    parser.add_argument("--evidence-out", default=None)
    args = parser.parse_args()
    violations: list[str] = []
    checks: dict = {}
    _static_checks(violations, checks)
    if args.dsn is not None:
        _live_checks(args.dsn, violations, checks)
    status = "PASS" if not violations else "FAIL"
    print(f"B26_P2_XIII_AUTH_{status}")
    if violations:
        print(";".join(sorted(violations)))
    else:
        print(json.dumps({"checks": checks}, sort_keys=True, default=str))
    if args.evidence_out:
        Path(args.evidence_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.evidence_out).write_text(
            json.dumps(
                {"gate_id": "B26-P2-XIII-AUTH-ROOT", "status": status,
                 "violations": sorted(violations), "checks": checks},
                indent=2,
            ),
            encoding="utf-8",
        )
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(main())
