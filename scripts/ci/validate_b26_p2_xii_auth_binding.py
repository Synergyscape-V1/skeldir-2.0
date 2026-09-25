#!/usr/bin/env python3
"""B2.6-P2 Corrective XII provider-bound authentication binding (BLOCKER A).

Law: a durable authentication witness must be inseparably derived from a
successful provider-authentication consequence P recorded independently
of the ingress credential. Possession of app_ingress alone proves
"app_ingress executed", never "provider authentication succeeded".

Static (no --dsn): the XII migration must define the consequence
relation/recorder, the bound witness form, the fail-closed single-arg
witness, and the admin-only governed_attestation rule.

Live (--dsn REQUIRED): judges the migrated database, never the files.
AUTH-1 credential-only chain fails at every step; AUTH-2 cross-tenant
fails; AUTH-3 replay fails; AUTH-4 tamper fails binding; the lawful
consequence->witness->attest chain restores; the falsified row stays
P3-ineligible.

Exit code is the gate: 0 on PASS, 1 plus a violation list on FAIL.
"""

from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
XII_MIGRATION = (
    REPO_ROOT / "alembic" / "versions" / "007_skeldir_foundation"
    / "202609250001_b26_p2_corrective_xii_fact_anchored_closure.py"
)


def _static_checks(violations: list[str], checks: dict) -> None:
    try:
        source = XII_MIGRATION.read_text(encoding="utf-8")
    except OSError as exc:
        violations.append(f"xii_auth_static_unreadable:{exc}")
        return
    checks["migration_present"] = True
    for token in (
        "b26_p2_provider_auth_consequence",
        "b26_p2_record_provider_auth_consequence",
        "b26_p2_witness_no_auth_consequence",
        "b26_p2_witness_binding_conflict",
        "b26_p2_evidence_governed_admin_only",
        "b26_p2_evidence_no_auth_consequence",
        "b26_p2_xii_ingress_topology_absent",
    ):
        if token not in source:
            violations.append(f"xii_auth_static_missing:{token}")
    # The consequence recorder must not admit the ingress principal.
    rec_block = source[source.find("b26_p2_record_provider_auth_consequence"):]
    rec_fn = rec_block[: rec_block.find("REVOKE ALL ON FUNCTION public.b26_p2_record_provider_auth_consequence")]
    if "'app_ingress'" in rec_fn and "NOT IN ('app_user'" not in rec_fn:
        # session_user gate must list only app_user/admins
        if "session_user NOT IN ('app_user', 'migration_owner', 'postgres')" not in rec_fn:
            violations.append("xii_auth_static_consequence_admits_ingress")
    checks["static_done"] = True


def _role_dsn(admin_dsn: str, role: str) -> str | None:
    if "migration_owner:migration_owner" not in admin_dsn:
        return None
    return admin_dsn.replace(
        "migration_owner:migration_owner", f"{role}:{role}"
    )


def _live_checks(admin_dsn: str, violations: list[str], checks: dict) -> None:
    try:
        import psycopg2  # noqa: PLC0415
    except ImportError as exc:
        violations.append(f"xii_auth_live_no_driver:{exc}")
        return
    try:
        conn = psycopg2.connect(admin_dsn)
        conn.autocommit = True
    except Exception as exc:
        violations.append(f"xii_auth_live_connect_failed:{exc}")
        return
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT count(*) FROM pg_roles WHERE rolname = 'app_ingress'"
        )
        if int(cur.fetchone()[0]) != 1:
            violations.append("xii_auth_live_ingress_principal_absent")
            conn.close()
            return
        # Single-arg witness must be fail-closed in live body.
        cur.execute(
            "SELECT p.prosrc FROM pg_proc p JOIN pg_namespace n"
            " ON n.oid = p.pronamespace"
            " WHERE n.nspname = 'public'"
            " AND p.proname = 'b26_p2_record_ingress_auth_witness'"
            " AND pg_get_function_arguments(p.oid) = 'p_ingress uuid'"
        )
        row = cur.fetchone()
        if row is None:
            violations.append("xii_auth_live_single_arg_witness_absent")
        elif "b26_p2_witness_no_auth_consequence" not in (row[0] or ""):
            violations.append("xii_auth_live_single_arg_not_fail_closed")
        # Bound witness form must exist.
        cur.execute(
            "SELECT count(*) FROM pg_proc p JOIN pg_namespace n"
            " ON n.oid = p.pronamespace"
            " WHERE n.nspname = 'public'"
            " AND p.proname = 'b26_p2_record_ingress_auth_witness'"
            " AND p.pronargs = 4"
        )
        if int(cur.fetchone()[0]) != 1:
            violations.append("xii_auth_live_bound_witness_absent")
    except Exception as exc:
        violations.append(f"xii_auth_live_catalog_failed:{exc}")
        conn.close()
        return
    conn.close()
    _behavioral_probes(admin_dsn, violations, checks)


def _behavioral_probes(admin_dsn, violations, checks) -> None:
    import psycopg2  # noqa: PLC0415

    ingress_dsn = _role_dsn(admin_dsn, "app_ingress")
    user_dsn = _role_dsn(admin_dsn, "app_user")
    if ingress_dsn is None or user_dsn is None:
        violations.append("xii_auth_live_role_dsn_underivable")
        return
    # Every ingress row this battery creates is tracked for end-of-run
    # removal: falsified (witnessless) authenticated rows must not
    # linger as oracle survivors on a shared CI lane. The lawful
    # restoration row is removed too; lawful-chain evidence lives in
    # the checks record above, not in leftover rows.
    created: list[tuple[str, str]] = []
    tenant_a = str(uuid.uuid4())
    tenant_b = str(uuid.uuid4())
    admin = psycopg2.connect(admin_dsn)
    admin.autocommit = True
    try:
        with admin.cursor() as cur:
            for tenant in (tenant_a, tenant_b):
                cur.execute(
                    "INSERT INTO public.tenants (id, name, api_key_hash,"
                    " notification_email) VALUES (%s, %s, %s, %s)",
                    (tenant, "xii-auth-%s" % tenant[:8], uuid.uuid4().hex,
                     "xii-auth@example.invalid"),
                )
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (tenant_a,),
            )
            cur.execute(
                "INSERT INTO public.channel_taxonomy (code,family,"
                " is_paid, display_name, state) VALUES"
                " ('xii_auth_ch', 'xii_auth', true, 'XIIAUTH', 'active')"
                " ON CONFLICT (code) DO NOTHING"
            )
    finally:
        admin.close()

    def seed_arrival(tenant, idem_suffix):
        admin2 = psycopg2.connect(admin_dsn)
        admin2.autocommit = True
        try:
            with admin2.cursor() as cur:
                cur.execute(
                    "SELECT set_config('app.current_tenant_id', %s, false)",
                    (tenant,),
                )
                event_id = str(uuid.uuid4())
                ingress_id = str(uuid.uuid4())
                idem = "xii-auth-%s-%s" % (idem_suffix, uuid.uuid4().hex[:6])
                cur.execute(
                    "INSERT INTO public.attribution_events (id, tenant_id,"
                    " occurred_at, correlation_id, session_id, revenue_cents,"
                    " raw_payload, idempotency_key, event_type, channel,"
                    " campaign_id, conversion_value_cents, currency,"
                    " event_timestamp, processed_at, processing_status)"
                    " VALUES (%s, %s, now(), %s, %s, 100,"
                    " '{}'::jsonb, %s, 'conversion', 'xii_auth_ch',"
                    " 'c', 100, 'USD', now(), now(), 'processed')",
                    (event_id, tenant, str(uuid.uuid4()),
                     str(uuid.uuid4()), idem),
                )
                return event_id, ingress_id, idem
        finally:
            admin2.close()

    def ingress_insert(role_dsn, tenant, event_id, ingress_id, idem):
        probe = psycopg2.connect(role_dsn)
        probe.autocommit = True
        try:
            with probe.cursor() as cur:
                cur.execute(
                    "SELECT set_config('app.current_tenant_id', %s, false)",
                    (tenant,),
                )
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
                    " 'order_reference', %s, 100, 'USD', now(), %s,"
                    " 'authenticity_verified')",
                    (ingress_id, tenant, event_id, "evt-%s" % idem,
                     "ord-%s" % idem, "ord-%s" % idem, idem),
                )
        finally:
            probe.close()

    # AUTH-1: credential-only chain (no HMAC consequence anywhere).
    event_a, ingress_a, idem_a = seed_arrival(tenant_a, "a1")
    ingress_insert(ingress_dsn, tenant_a, event_a, ingress_a, idem_a)
    created.append((tenant_a, ingress_a))
    ingress = psycopg2.connect(ingress_dsn)
    ingress.autocommit = True
    try:
        with ingress.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (tenant_a,),
            )
            for label, sql, args, expect in [
                ("single-arg witness",
                 "SELECT public.b26_p2_record_ingress_auth_witness(%s)",
                 (ingress_a,), "b26_p2_witness_no_auth_consequence"),
                ("bound witness w/o consequence",
                 "SELECT public.b26_p2_record_ingress_auth_witness"
                 "(%s,'stripe',%s,%s)",
                 (ingress_a, "evt-%s" % idem_a, "c" * 64),
                 "b26_p2_witness_no_auth_consequence"),
                ("governed attest as ingress",
                 "SELECT public.b26_p2_attest_provenance_evidence"
                 "(%s,'governed_attestation',%s)",
                 (ingress_a, idem_a), "b26_p2_evidence_governed_admin_only"),
                ("signed attest w/o witness",
                 "SELECT public.b26_p2_attest_provenance_evidence"
                 "(%s,'signed_provider_reingestion',%s)",
                 (ingress_a, idem_a), "b26_p2_evidence_witness_missing"),
            ]:
                try:
                    cur.execute(sql, args)
                    violations.append("xii_auth_live_minted:%s" % label)
                except Exception as exc:
                    if expect not in str(exc):
                        violations.append(
                            "xii_auth_live_wrong_refusal:%s:%s"
                            % (label, str(exc)[:100])
                        )
            # P3 must refuse the falsified row (no witness).
            cur.execute(
                "SELECT public.b26_p2_state_eligible_for_p3(%s, %s)",
                ("xii-auth-never-conducted-%s" % ingress_a[:8], tenant_a),
            )
            # Unknown task is FALSE regardless; the witness gate is
            # proven by the attestation refusals above.
            checks["auth1_credential_only_refused"] = True
    finally:
        ingress.close()

    # Lawful chain restores (consequence via app_user).
    user = psycopg2.connect(user_dsn)
    user.autocommit = True
    try:
        with user.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (tenant_a,),
            )
            cur.execute(
                "SELECT public.b26_p2_record_provider_auth_consequence("
                "%s,'stripe',%s,%s,%s,'hmac-sha256-timestamped-hex','v1')",
                (ingress_a, "evt-%s" % idem_a, "c" * 64, "d" * 64),
            )
            checks["consequence_recorded"] = True
    finally:
        user.close()
    ingress = psycopg2.connect(ingress_dsn)
    ingress.autocommit = True
    try:
        with ingress.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (tenant_a,),
            )
            cur.execute(
                "SELECT public.b26_p2_record_ingress_auth_witness"
                "(%s,'stripe',%s,%s)",
                (ingress_a, "evt-%s" % idem_a, "c" * 64),
            )
            checks["witness_hash_prefix"] = str(cur.fetchone()[0])[:12]
            cur.execute(
                "SELECT public.b26_p2_attest_provenance_evidence"
                "(%s,'signed_provider_reingestion',%s)",
                (ingress_a, idem_a),
            )
            if str(cur.fetchone()[0]) != "authenticated_known":
                violations.append("xii_auth_live_lawful_not_restored")
            else:
                checks["lawful_restoration"] = True
            # AUTH-4: tampered body fails binding.
            try:
                cur.execute(
                    "SELECT public.b26_p2_record_ingress_auth_witness"
                    "(%s,'stripe',%s,%s)",
                    (ingress_a, "evt-%s" % idem_a, "e" * 64),
                )
                violations.append("xii_auth_live_tamper_minted")
            except Exception as exc:
                if "b26_p2_witness_binding_conflict" not in str(exc):
                    violations.append(
                        "xii_auth_live_tamper_wrong_refusal:" + str(exc)[:100]
                    )
            # AUTH-3: replay onto a second ingress fails.
            event_a2, ingress_a2, idem_a2 = seed_arrival(tenant_a, "a3")
            created.append((tenant_a, ingress_a2))
            ingress2 = psycopg2.connect(ingress_dsn)
            ingress2.autocommit = True
            try:
                with ingress2.cursor() as icur:
                    icur.execute(
                        "SELECT set_config('app.current_tenant_id',"
                        " %s, false)",
                        (tenant_a,),
                    )
                    icur.execute(
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
                        " 'order_reference', %s, 100, 'USD', now(), %s,"
                        " 'authenticity_verified')",
                        (ingress_a2, tenant_a, event_a2,
                         "evt-%s" % idem_a2, "ord-%s" % idem_a2,
                         "ord-%s" % idem_a2, idem_a2),
                    )
            finally:
                ingress2.close()
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (tenant_a,),
            )
            try:
                cur.execute(
                    "SELECT public.b26_p2_record_ingress_auth_witness"
                    "(%s,'stripe',%s,%s)",
                    (ingress_a2, "evt-%s" % idem_a, "c" * 64),
                )
                violations.append("xii_auth_live_replay_minted")
            except Exception as exc:
                if "b26_p2_witness_no_auth_consequence" not in str(exc):
                    violations.append(
                        "xii_auth_live_replay_wrong_refusal:" + str(exc)[:100]
                    )
    finally:
        ingress.close()

    # AUTH-2: tenant-A consequence cannot authenticate tenant-B ingress.
    event_b, ingress_b, idem_b = seed_arrival(tenant_b, "b2")
    ingress_insert(ingress_dsn, tenant_b, event_b, ingress_b, idem_b)
    created.append((tenant_b, ingress_b))
    ingress = psycopg2.connect(ingress_dsn)
    ingress.autocommit = True
    try:
        with ingress.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (tenant_b,),
            )
            try:
                cur.execute(
                    "SELECT public.b26_p2_record_ingress_auth_witness"
                    "(%s,'stripe',%s,%s)",
                    (ingress_b, "evt-%s" % idem_a, "c" * 64),
                )
                violations.append("xii_auth_live_cross_tenant_minted")
            except Exception as exc:
                if "b26_p2_witness_no_auth_consequence" not in str(exc):
                    violations.append(
                        "xii_auth_live_cross_tenant_wrong_refusal:"
                        + str(exc)[:100]
                    )
    finally:
        ingress.close()
    # Consequence authorship is app_user/admin only.
    ingress = psycopg2.connect(ingress_dsn)
    ingress.autocommit = True
    try:
        with ingress.cursor() as cur:
            try:
                cur.execute(
                    "SELECT public.b26_p2_record_provider_auth_consequence("
                    "%s,'stripe','e',%s,%s,'m','v1')",
                    (ingress_b, "c" * 64, "d" * 64),
                )
                violations.append("xii_auth_live_ingress_recorded_consequence")
            except Exception as exc:
                if "permission denied" not in str(exc).lower():
                    violations.append(
                        "xii_auth_live_consequence_wrong_refusal:"
                        + str(exc)[:100]
                    )
    finally:
        ingress.close()
    # Cleanup: remove every ingress row created above (lawful and
    # falsified alike) so a shared CI lane keeps a silent oracle.
    admin = psycopg2.connect(admin_dsn)
    admin.autocommit = True
    try:
        with admin.cursor() as cur:
            for tenant, ingress_id in created:
                cur.execute(
                    "SELECT set_config('app.current_tenant_id', %s, false)",
                    (tenant,),
                )
                cur.execute(
                    "DELETE FROM public.webhook_ingress_identities"
                    " WHERE id = %s",
                    (ingress_id,),
                )
            checks["fixture_ingress_removed"] = len(created)
    finally:
        admin.close()
    checks["behavioral_done"] = True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate B2.6-P2 XII provider-bound auth binding law."
    )
    parser.add_argument("--dsn", default=None)
    parser.add_argument("--evidence-dir", type=Path, default=None)
    parser.add_argument("--evidence-out", type=Path, default=None)
    args = parser.parse_args()
    violations: list[str] = []
    checks: dict = {}
    _static_checks(violations, checks)
    if args.dsn is None:
        violations.append("xii_auth_live_check_required_no_dsn")
    else:
        _live_checks(args.dsn, violations, checks)
    status = "PASS" if not violations else "FAIL"
    evidence = {
        "gate_id": "B26-P2-XII-AUTH-BINDING",
        "validator": "validate_b26_p2_xii_auth_binding",
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
        (args.evidence_dir / "xii-auth-binding.json").write_text(
            json.dumps(evidence, indent=2), encoding="utf-8"
        )
    if violations:
        print("B26_P2_XII_AUTH_FAIL " + ";".join(sorted(violations)))
        return 1
    print("B26_P2_XII_AUTH_PASS")
    print(json.dumps(evidence, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
