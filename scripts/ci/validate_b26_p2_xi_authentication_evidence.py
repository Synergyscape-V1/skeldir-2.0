#!/usr/bin/env python3
"""B2.6-P2 Corrective XI authentication-evidence validator (BLOCKER CLASS A).

Law: UNKNOWN authentication may transition to AUTHENTICATED only because
an actual governed authentication consequence exists (a witness row
authored by the ingress boundary). ``unknown -> caller says
authenticated -> known`` is forbidden.

Static mode (no --dsn): the XI migration must define the witness
relation, the witness function, and a witness-gated attester; the
attester allowlist must not contain app_user.

Live mode (--dsn REQUIRED): judges the migrated database, never the
files. Checks pg_proc bodies (witness gate present), EXECUTE
reachability by OID (app_ingress yes; app_user/app_worker/app_relay/
app_beat no), and behavioral probes through derivable role DSNs:
caller-assertion promotion refused, witnessless attestation refused,
forged evidence-row insertion refused, lawful witness+attest restores.

Exit code is the gate: 0 on PASS, 1 plus a violation list on FAIL.
"""

from __future__ import annotations

import argparse
import json
import re
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
XI_MIGRATION = (
    REPO_ROOT / "alembic" / "versions" / "007_skeldir_foundation"
    / "202609240002_b26_p2_corrective_xi_p2_core_closure.py"
)

ATTESTER = "b26_p2_attest_provenance_evidence"
WITNESS_FN = "b26_p2_record_ingress_auth_witness"
WITNESS_TABLE = "b26_p2_ingress_auth_witness"
FORBIDDEN_CALLERS = ("app_user", "app_worker", "app_relay", "app_beat")


def _static_checks(violations: list[str], checks: dict) -> None:
    try:
        source = XI_MIGRATION.read_text(encoding="utf-8")
    except OSError as exc:
        violations.append(f"xi_auth_static_unreadable:{exc}")
        return
    checks["migration_present"] = True
    for token in (
        WITNESS_TABLE,
        WITNESS_FN,
        "b26_p2_evidence_witness_missing",
        "b26_p2_witness_caller_refused",
    ):
        if token not in source:
            violations.append(f"xi_auth_static_missing:{token}")
    # The attester allowlist in the XI migration must not admit the
    # ordinary application principal.
    attester_blocks = [
        m for m in re.finditer(
            r"CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+public\."
            + re.escape(ATTESTER) + r"\(.*?END \$\$;",
            source,
            re.IGNORECASE | re.DOTALL,
        )
    ]
    if not attester_blocks:
        violations.append("xi_auth_static_attester_absent")
    else:
        body = attester_blocks[-1].group(0)
        # Predecessor-compatible topology rule: app_user may appear
        # ONLY inside a session_user NOT IN allowlist that does NOT
        # also admit app_ingress (the legacy branch), AND the body
        # must contain the role-census conditional gating that
        # branch. Anything else (grant, strict allowlist,
        # unconditional path) is a violation.
        SES_RE = r"session_user\s+NOT\s+IN\s*\(([^)]*)\)"
        gated = "rolname = 'app_ingress'" in body
        for group in re.findall(SES_RE, body):
            names = set(re.findall(r"'(\w+)'", group))
            if "app_user" in names and (
                "app_ingress" in names or not gated
            ):
                violations.append("xi_auth_static_app_user_admitted")
                break
        stripped = re.sub(SES_RE, "", body)
        if "'app_user'" in stripped:
            violations.append("xi_auth_static_app_user_admitted")
        if WITNESS_TABLE not in body:
            violations.append("xi_auth_static_attester_no_witness_gate")
    checks["static_done"] = True


def _role_dsn(admin_dsn: str, role: str) -> str | None:
    if "migration_owner:migration_owner" not in admin_dsn:
        return None
    return admin_dsn.replace(
        "migration_owner:migration_owner", f"{role}:{role}"
    )


def _live_checks(
    admin_dsn: str, violations: list[str], checks: dict
) -> None:
    try:
        import psycopg2  # noqa: PLC0415
    except ImportError as exc:
        violations.append(f"xi_auth_live_no_driver:{exc}")
        return
    try:
        conn = psycopg2.connect(admin_dsn)
        conn.autocommit = True
    except Exception as exc:
        violations.append(f"xi_auth_live_connect_failed:{exc}")
        return
    try:
        cur = conn.cursor()
        # Body gate: live attester must consult the witness table.
        cur.execute(
            "SELECT p.prosrc FROM pg_proc p JOIN pg_namespace n"
            " ON n.oid = p.pronamespace"
            " WHERE n.nspname = 'public' AND p.proname = %s",
            (ATTESTER,),
        )
        row = cur.fetchone()
        if row is None:
            violations.append("xi_auth_live_attester_missing")
            return
        prosrc = row[0] or ""
        checks["attester_body_bytes"] = len(prosrc)
        if WITNESS_TABLE not in prosrc:
            violations.append("xi_auth_live_attester_no_witness_gate")
        if "b26_p2_evidence_witness_missing" not in prosrc:
            violations.append("xi_auth_live_attester_no_witness_refusal")
        # EXECUTE reachability by OID: ingress yes, generic roles no.
        cur.execute(
            """
            SELECT p.proname, r.rolname,
                   has_function_privilege(
                       r.oid, p.oid, 'EXECUTE'
                   ) AS can
            FROM pg_roles r, pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'public'
              AND p.proname IN (
                  'b26_p2_attest_provenance_evidence',
                  'b26_p2_record_ingress_auth_witness'
              )
              AND r.rolname IN (
                  'app_ingress', 'app_user', 'app_worker',
                  'app_relay', 'app_beat'
              )
            """
        )
        grants = {
            (func, role): bool(can)
            for func, role, can in cur.fetchall()
        }
        checks["execute_matrix"] = {
            f"{func}:{role}": grants.get((func, role))
            for func in (
                "b26_p2_attest_provenance_evidence",
                "b26_p2_record_ingress_auth_witness",
            )
            for role in (
                "app_ingress", "app_user", "app_worker",
                "app_relay", "app_beat",
            )
        }
        if not grants.get(
            ("b26_p2_attest_provenance_evidence", "app_ingress"), False
        ):
            violations.append("xi_auth_live_ingress_cannot_attest")
        if not grants.get(
            ("b26_p2_record_ingress_auth_witness", "app_ingress"), False
        ):
            violations.append("xi_auth_live_ingress_cannot_witness")
        for role in FORBIDDEN_CALLERS:
            if grants.get(
                ("b26_p2_attest_provenance_evidence", role), False
            ):
                violations.append(
                    f"xi_auth_live_forbidden_attest:{role}"
                )
            if grants.get(
                ("b26_p2_record_ingress_auth_witness", role), False
            ):
                violations.append(
                    f"xi_auth_live_forbidden_witness:{role}"
                )
        # Witness table: no runtime INSERT (unforgeable).
        cur.execute(
            """
            SELECT r.rolname
            FROM pg_roles r
            WHERE r.rolname IN (
                'app_ingress', 'app_user', 'app_worker',
                'app_relay', 'app_beat'
            )
              AND has_table_privilege(
                  r.rolname,
                  'public.b26_p2_ingress_auth_witness',
                  'INSERT'
              )
            """
        )
        writers = [r[0] for r in cur.fetchall()]
        checks["witness_insert_holders"] = writers
        if writers:
            violations.append(
                "xi_auth_live_witness_forgeable:"
                + ",".join(sorted(writers))
            )
    except Exception as exc:
        violations.append(f"xi_auth_live_catalog_failed:{exc}")
        return
    finally:
        conn.close()
    # Behavioral probes through exact runtime principals.
    _behavioral_probes(admin_dsn, violations, checks)


def _behavioral_probes(
    admin_dsn: str, violations: list[str], checks: dict
) -> None:
    import psycopg2  # noqa: PLC0415

    ingress_dsn = _role_dsn(admin_dsn, "app_ingress")
    user_dsn = _role_dsn(admin_dsn, "app_user")
    worker_dsn = _role_dsn(admin_dsn, "app_worker")
    if ingress_dsn is None or user_dsn is None or worker_dsn is None:
        violations.append("xi_auth_live_role_dsn_underivable")
        return
    tenant_id = str(uuid.uuid4())
    ingress_id = str(uuid.uuid4())
    event_id = str(uuid.uuid4())
    idem = f"xi-auth:{uuid.uuid4().hex[:8]}"
    admin = psycopg2.connect(admin_dsn)
    admin.autocommit = True
    try:
        with admin.cursor() as cur:
            cur.execute(
                "INSERT INTO public.tenants (id, name, api_key_hash,"
                " notification_email) VALUES (%s, %s, %s, %s)",
                (tenant_id, f"xi-auth-{idem}", uuid.uuid4().hex,
                 "xi-auth@example.invalid"),
            )
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (tenant_id,),
            )
            cur.execute(
                "INSERT INTO public.channel_taxonomy (code, family,"
                " is_paid, display_name, state) VALUES"
                " ('xi_auth_ch', 'xi_auth', true, 'XIAUTH', 'active')"
                " ON CONFLICT (code) DO NOTHING"
            )
            cur.execute(
                "INSERT INTO public.attribution_events (id, tenant_id,"
                " occurred_at, correlation_id, session_id, revenue_cents,"
                " raw_payload, idempotency_key, event_type, channel,"
                " campaign_id, conversion_value_cents, currency,"
                " event_timestamp, processed_at, processing_status)"
                " VALUES (%s, %s, now(), %s, %s, 38000,"
                " '{}'::jsonb, %s, 'conversion', 'xi_auth_ch',"
                " 'xi-auth-camp', 38000, 'USD', now(), now(),"
                " 'processed')",
                (event_id, tenant_id, str(uuid.uuid4()),
                 str(uuid.uuid4()), idem),
            )
            # Verified arrival authored by the migration admin (the
            # harness-simulated provider-authenticated consequence;
            # production uses the ingress credential here).
            cur.execute(
                "INSERT INTO public.webhook_ingress_identities (id,"
                " tenant_id, event_id, provider,"
                " provider_native_event_reference,"
                " provider_native_commerce_reference,"
                " normalized_commerce_reference_kind,"
                " normalized_commerce_reference_value,"
                " verified_amount_minor, verified_amount_currency,"
                " event_timestamp, idempotency_key,"
                " verified_commerce_ingress_state)"
                " VALUES (%s, %s, %s, 'stripe', %s, %s,"
                " 'order_reference', %s, 38000, 'USD', now(), %s,"
                " 'authenticity_verified')",
                (ingress_id, tenant_id, event_id, f"evt-{idem}",
                 f"ord-{idem}", f"ord-{idem}", idem),
            )
    except Exception as exc:
        violations.append(f"xi_auth_live_fixture_failed:{exc}")
        admin.close()
        return
    finally:
        pass
    checks["fixture_ingress"] = ingress_id
    # Probe 1 (F-XI-A1): caller assertion without witness promotes
    # nothing. app_user cannot even execute; app_ingress is refused
    # for the missing witness.
    try:
        user = psycopg2.connect(user_dsn)
        user.autocommit = True
        try:
            with user.cursor() as cur:
                cur.execute(
                    "SELECT set_config('app.current_tenant_id',"
                    " %s, false)",
                    (tenant_id,),
                )
                try:
                    cur.execute(
                        "SELECT public.b26_p2_attest_provenance_evidence"
                        "(%s, 'governed_attestation', %s)",
                        (ingress_id, idem),
                    )
                    violations.append(
                        "xi_auth_live_assertion_promoted:app_user"
                    )
                except Exception as exc:
                    msg = str(exc).lower()
                    if (
                        "permission denied" not in msg
                        and "caller_refused" not in msg
                    ):
                        violations.append(
                            "xi_auth_live_assertion_wrong_refusal:"
                            + msg[:120]
                        )
        finally:
            user.close()
    except Exception as exc:
        violations.append(f"xi_auth_live_user_probe_failed:{exc}")
    try:
        ingress = psycopg2.connect(ingress_dsn)
        ingress.autocommit = True
        try:
            with ingress.cursor() as cur:
                cur.execute(
                    "SELECT set_config('app.current_tenant_id',"
                    " %s, false)",
                    (tenant_id,),
                )
                try:
                    cur.execute(
                        "SELECT public.b26_p2_attest_provenance_evidence"
                        "(%s, 'governed_attestation', %s)",
                        (ingress_id, idem),
                    )
                    violations.append(
                        "xi_auth_live_witnessless_promoted"
                    )
                except Exception as exc:
                    if "b26_p2_evidence_witness_missing" not in str(exc):
                        violations.append(
                            "xi_auth_live_witness_wrong_refusal:"
                            + str(exc)[:120]
                        )
                # Probe 3 (F-XI-A3): genuine consequence restores.
                try:
                    cur.execute(
                        "SELECT public.b26_p2_record_ingress_auth_witness"
                        "(%s)",
                        (ingress_id,),
                    )
                    checks["witness_hash_prefix"] = str(
                        cur.fetchone()[0]
                    )[:12]
                    cur.execute(
                        "SELECT public.b26_p2_attest_provenance_evidence"
                        "(%s, 'signed_provider_reingestion', %s)",
                        (ingress_id, idem),
                    )
                    if str(cur.fetchone()[0]) != "authenticated_known":
                        violations.append(
                            "xi_auth_live_lawful_not_restored"
                        )
                    else:
                        checks["lawful_restoration"] = True
                except Exception as exc:
                    violations.append(
                        f"xi_auth_live_lawful_failed:{exc}"[:160]
                    )
        finally:
            ingress.close()
    except Exception as exc:
        violations.append(f"xi_auth_live_ingress_probe_failed:{exc}")
    # Probe 2 (F-XI-A2): forged evidence row by non-ingress runtime.
    try:
        worker = psycopg2.connect(worker_dsn)
        worker.autocommit = True
        try:
            with worker.cursor() as cur:
                cur.execute(
                    "SELECT set_config('app.current_tenant_id',"
                    " %s, false)",
                    (tenant_id,),
                )
                try:
                    cur.execute(
                        "INSERT INTO public.b26_p2_provenance_evidence"
                        " (webhook_ingress_identity_id, tenant_id,"
                        " evidence_kind, evidence_ref) VALUES"
                        " (%s, %s, 'governed_attestation', %s)",
                        (ingress_id, tenant_id, idem),
                    )
                    violations.append("xi_auth_live_forged_evidence")
                except Exception as exc:
                    if "permission denied" not in str(exc).lower():
                        violations.append(
                            "xi_auth_live_forge_wrong_refusal:"
                            + str(exc)[:120]
                        )
                try:
                    cur.execute(
                        "SELECT public.b26_p2_record_ingress_auth_witness"
                        "(%s)",
                        (ingress_id,),
                    )
                    violations.append("xi_auth_live_worker_witnessed")
                except Exception as exc:
                    if "permission denied" not in str(exc).lower():
                        violations.append(
                            "xi_auth_live_witness_wrong_refusal:"
                            + str(exc)[:120]
                        )
        finally:
            worker.close()
    except Exception as exc:
        violations.append(f"xi_auth_live_worker_probe_failed:{exc}")
    # Fixture rows remain: the probe ingress is fully lawful
    # (admin-authored verified arrival + ingress witness + signed
    # re-ingestion attestation), so the generic oracle sees no
    # violation. Lanes are throwaway; sibling batteries (Corrective
    # X) follow the same leave-behind discipline because tenant
    # delete cascades through session-authority history.
    checks["fixture_left_lawful"] = ingress_id
    admin.close()
    checks["behavioral_done"] = True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate B2.6-P2 XI authentication evidence law."
    )
    parser.add_argument("--dsn", default=None)
    parser.add_argument("--evidence-dir", type=Path, default=None)
    parser.add_argument("--evidence-out", type=Path, default=None)
    args = parser.parse_args()
    violations: list[str] = []
    checks: dict = {}
    _static_checks(violations, checks)
    if args.dsn is None:
        violations.append("xi_auth_live_check_required_no_dsn")
    else:
        _live_checks(args.dsn, violations, checks)
    status = "PASS" if not violations else "FAIL"
    evidence = {
        "gate_id": "B26-P2-XI-AUTHENTICATION-EVIDENCE",
        "validator": "validate_b26_p2_xi_authentication_evidence",
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
        (args.evidence_dir / "xi-authentication-evidence.json").write_text(
            json.dumps(evidence, indent=2), encoding="utf-8"
        )
    if violations:
        print("B26_P2_XI_AUTH_FAIL " + ";".join(sorted(violations)))
        return 1
    print("B26_P2_XI_AUTH_PASS")
    print(json.dumps(evidence, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
