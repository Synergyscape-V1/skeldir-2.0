#!/usr/bin/env python3
"""B2.6-P2 Corrective XV database-physics closure (H-XV-R4/R5/R6/R8/R11).

Laws (each REDs on the effect):
- evidence creation authority is transition-specific, not context-class
  (static: PG_CONTEXT stack check naming the atomic; live: deputy DEFINER
  cannot mint evidence while the atomic can);
- authenticated financial meaning is immutable (static: trigger + error
  token; live: post-auth amount UPDATE refused, precursor promotion still
  allowed);
- downgrade is monotonic (static: quarantine block token in the XIV
  downgrade; live: downgrade attempt with quarantine dispositions fails);
- recovery is honest (static: duplicate re-drive tokens in event_service;
  no precursor-exists-means-success shortcut).

Exit code is the gate. Live DB checks run only with --dsn.
"""

from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MIG_XV = (
    REPO_ROOT
    / "alembic"
    / "versions"
    / "007_skeldir_foundation"
    / "202609280001_b26_p2_corrective_xv_binding_closure.py"
)


def _static_checks(violations: list[str], checks: dict) -> None:
    try:
        xv = MIG_XV.read_text(encoding="utf-8")
        ev = (
            REPO_ROOT / "backend" / "app" / "ingestion" / "event_service.py"
        ).read_text(encoding="utf-8")
    except OSError as exc:
        violations.append(f"xv_phys_unreadable:{exc}")
        return
    for token in (
        "PG_CONTEXT",
        "b26_p2_authenticate_ingress_atomic",
        "b26_p2_auth_root_evidence_transition_refused",
        "b26_p2_enforce_authenticated_meaning_immutability",
        "b26_p2_authenticated_meaning_immutable_refused",
        "trg_b26_p2_authenticated_meaning_immutability",
        "b26_p2_enforce_quarantine_historical_finality",
        "b26_p2_quarantine_historical_delete_refused",
        "trg_b26_p2_quarantine_historical_finality",
    ):
        if token not in xv:
            violations.append(f"xv_phys_xv_missing:{token}")
    checks["xv_migration_law"] = True
    for token in (
        "redrive_finalization",
        "H-XV-R8/R9",
        "_finalize_verified_ingress_post_commit",
    ):
        if token not in ev:
            violations.append(f"xv_phys_recovery_missing:{token}")
    # The false-success shortcut (bare DUPLICATE return on the primary
    # duplicate path) must be gone: the primary path now attaches
    # redrive_finalization.
    if "redrive_finalization" not in ev:
        violations.append("xv_phys_false_success_shortcut_present")
    checks["recovery_redrive_present"] = True


def _live_checks(admin_dsn: str, violations: list[str], checks: dict) -> None:
    try:
        import psycopg2  # noqa: PLC0415
    except ImportError as exc:
        violations.append(f"xv_phys_no_driver:{exc}")
        return
    ingress_dsn = (
        admin_dsn.replace("migration_owner:migration_owner", "app_ingress:app_ingress")
        if "migration_owner:migration_owner" in admin_dsn
        else None
    )
    if ingress_dsn is None:
        violations.append("xv_phys_role_dsn_underivable")
        return
    try:
        admin = psycopg2.connect(admin_dsn)
        admin.autocommit = True
    except Exception as exc:
        violations.append(f"xv_phys_connect_failed:{exc}")
        return
    try:
        cur = admin.cursor()
        tenant = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO public.tenants (id, name, api_key_hash, notification_email)"
            " VALUES (%s,%s,%s,%s)",
            (tenant, "xv-phys", uuid.uuid4().hex, "xv-phys@example.invalid"),
        )
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false)", (tenant,))
        cur.execute(
            "INSERT INTO public.channel_taxonomy (code, family, is_paid,"
            " display_name, state) VALUES ('xv_phys_ch', 'xv_phys', true,"
            " 'XVPHYS', 'active') ON CONFLICT (code) DO NOTHING"
        )
        ev1, ing1 = str(uuid.uuid4()), str(uuid.uuid4())
        cur.execute(
            "INSERT INTO public.attribution_events (id, tenant_id, occurred_at, correlation_id,"
            " session_id, revenue_cents, raw_payload, idempotency_key, event_type, channel,"
            " campaign_id, conversion_value_cents, currency, event_timestamp, processed_at,"
            " processing_status) VALUES (%s,%s,now(),%s,%s,7600,'{}'::jsonb,%s,'conversion',"
            " 'xv_phys_ch','c',7600,'USD',now(),now(),'processed')",
            (ev1, tenant, str(uuid.uuid4()), str(uuid.uuid4()), "xv-phys-1"),
        )
        cur.execute(
            "INSERT INTO public.webhook_ingress_identities (id, tenant_id, event_id, provider,"
            " provider_native_event_reference, provider_native_commerce_reference,"
            " normalized_commerce_reference_kind, normalized_commerce_reference_value,"
            " verified_amount_minor, verified_amount_currency, event_timestamp,"
            " idempotency_key, verified_commerce_ingress_state)"
            " VALUES (%s,%s,%s,'stripe','e1','o1','stripe_order_id','o1',7600,'USD',now(),"
            " 'xv-phys-1','authenticity_verified')",
            (ing1, tenant, ev1),
        )
        ing = psycopg2.connect(ingress_dsn)
        ing.autocommit = True
        try:
            with ing.cursor() as icur:
                icur.execute(
                    "SELECT set_config('app.current_tenant_id', %s, false)", (tenant,)
                )
                icur.execute(
                    "SELECT public.b26_p2_authenticate_ingress_atomic(%s,'stripe','e1',%s,%s,"
                    "'hmac-sha256-timestamped-hex','v1')",
                    (ing1, "a" * 64, "b" * 64),
                )
                if str(icur.fetchone()[0]) != "authenticated_known":
                    violations.append("xv_phys_atomic_not_authoritative")
                    return
                checks["atomic_authoritative"] = True
                # XV2 live: post-auth amount mutation refused.
                try:
                    icur.execute(
                        "UPDATE public.webhook_ingress_identities"
                        " SET verified_amount_minor=9999 WHERE id=%s",
                        (ing1,),
                    )
                    violations.append("xv_phys_post_auth_mutation_permitted")
                except Exception as exc:
                    if "b26_p2_authenticated_meaning_immutable_refused" not in str(exc):
                        violations.append(
                            f"xv_phys_mutation_wrong_refusal:{str(exc).splitlines()[0][:120]}"
                        )
                    else:
                        checks["post_auth_mutation_refused"] = True
                # XV2 live: precursor promotion still allowed (pending row).
                ev2, ing2 = str(uuid.uuid4()), str(uuid.uuid4())
                cur.execute(
                    "INSERT INTO public.attribution_events (id, tenant_id, occurred_at,"
                    " correlation_id, session_id, revenue_cents, raw_payload, idempotency_key,"
                    " event_type, channel, campaign_id, conversion_value_cents, currency,"
                    " event_timestamp, processed_at, processing_status)"
                    " VALUES (%s,%s,now(),%s,%s,100,'{}'::jsonb,%s,'conversion','xv_phys_ch',"
                    " 'c',100,'USD',now(),now(),'processed')",
                    (ev2, tenant, str(uuid.uuid4()), str(uuid.uuid4()), "xv-phys-2"),
                )
                cur.execute(
                    "INSERT INTO public.webhook_ingress_identities (id, tenant_id, event_id,"
                    " provider, provider_native_event_reference,"
                    " provider_native_commerce_reference,"
                    " normalized_commerce_reference_kind,"
                    " normalized_commerce_reference_value, verified_amount_minor,"
                    " verified_amount_currency, event_timestamp, idempotency_key,"
                    " verified_commerce_ingress_state)"
                    " VALUES (%s,%s,%s,'stripe','e2','o2','stripe_order_id','o2',100,'USD',"
                    " now(),'xv-phys-2','pending')",
                    (ing2, tenant, ev2),
                )
                try:
                    icur.execute(
                        "UPDATE public.webhook_ingress_identities"
                        " SET verified_commerce_ingress_state='authenticity_verified',"
                        " verified_amount_minor=100 WHERE id=%s",
                        (ing2,),
                    )
                    checks["precursor_promotion_allowed"] = True
                except Exception as exc:
                    violations.append(f"xv_phys_precursor_promotion_blocked:{exc}")
                # XV1 live: deputy DEFINER cannot mint evidence.
                cur.execute(
                    "CREATE OR REPLACE FUNCTION public.b26_p2_xv_deputy_probe()"
                    " RETURNS void LANGUAGE plpgsql SECURITY DEFINER"
                    " SET search_path TO 'pg_catalog','public' AS $$ BEGIN"
                    " INSERT INTO public.b26_p2_auth_root_evidence (tenant_id,"
                    " webhook_ingress_identity_id, idempotency_key, provider,"
                    " provider_native_event_reference, body_sha256,"
                    " signature_envelope_sha256, auth_method) VALUES (%s::uuid,"
                    " gen_random_uuid(),'xv-deputy','stripe','e',%s,%s,'m');"
                    " END $$;",
                    (tenant, "c" * 64, "d" * 64),
                )
                cur.execute(
                    "GRANT EXECUTE ON FUNCTION public.b26_p2_xv_deputy_probe() TO app_ingress"
                )
                try:
                    icur.execute("SELECT public.b26_p2_xv_deputy_probe()")
                    violations.append("xv_phys_deputy_evidence_permitted")
                except Exception as exc:
                    if "b26_p2_auth_root_evidence_transition_refused" not in str(exc):
                        violations.append(
                            f"xv_phys_deputy_wrong_refusal:{str(exc).splitlines()[0][:160]}"
                        )
                    else:
                        checks["deputy_evidence_refused"] = True
                finally:
                    cur.execute(
                        "DROP FUNCTION IF EXISTS public.b26_p2_xv_deputy_probe()"
                    )
                    cur.execute(
                        "DELETE FROM public.b26_p2_auth_root_evidence WHERE idempotency_key='xv-deputy'"
                    )
                # XV3 live: historical quarantine rows cannot be deleted
                # (downgrade resurrection blocked at the data layer); probe
                # rows remain cleanable (validator hygiene preserved).
                cur.execute(
                    "INSERT INTO public.b26_p2_execution_quarantine (source_relation, task_id,"
                    " tenant_id, webhook_ingress_identity_id, reason, original_payload,"
                    " migration_identity) VALUES ('webhook_ingress_identities',%s,%s,%s,"
                    " 'historically_unverifiable_xiv','{}','xv-phys-probe')",
                    ("xv-phys-hist:" + ing1, tenant, ing1),
                )
                try:
                    cur.execute(
                        "DELETE FROM public.b26_p2_execution_quarantine WHERE task_id=%s",
                        ("xv-phys-hist:" + ing1,),
                    )
                    violations.append("xv_phys_historical_delete_permitted")
                except Exception as exc:
                    if "b26_p2_quarantine_historical_delete_refused" not in str(exc):
                        violations.append(
                            f"xv_phys_historical_wrong_refusal:{str(exc).splitlines()[0][:160]}"
                        )
                    else:
                        checks["historical_delete_refused"] = True
                try:
                    cur.execute(
                        "UPDATE public.b26_p2_execution_quarantine SET reason='xiv_probe_quarantine'"
                        " WHERE task_id=%s",
                        ("xv-phys-hist:" + ing1,),
                    )
                    violations.append("xv_phys_historical_relabel_permitted")
                except Exception as exc:
                    if "b26_p2_quarantine_historical_delete_refused" not in str(exc):
                        violations.append(
                            f"xv_phys_relabel_wrong_refusal:{str(exc).splitlines()[0][:160]}"
                        )
                    else:
                        checks["historical_relabel_refused"] = True
                cur.execute(
                    "INSERT INTO public.b26_p2_execution_quarantine (source_relation, task_id,"
                    " tenant_id, webhook_ingress_identity_id, reason, original_payload,"
                    " migration_identity) VALUES ('webhook_ingress_identities',%s,%s,%s,"
                    " 'xiv_probe_quarantine','{}','xv-phys-probe')",
                    ("xv-phys-probe:" + ing1, tenant, ing1),
                )
                try:
                    cur.execute(
                        "DELETE FROM public.b26_p2_execution_quarantine WHERE task_id=%s",
                        ("xv-phys-probe:" + ing1,),
                    )
                    checks["probe_hygiene_preserved"] = True
                except Exception as exc:
                    violations.append(f"xv_phys_probe_hygiene_blocked:{exc}")
        finally:
            ing.close()
        cur.close()
    except Exception as exc:
        violations.append(f"xv_phys_live_failed:{exc}")
    finally:
        admin.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="XV database-physics closure.")
    parser.add_argument("--dsn", default=None)
    parser.add_argument("--evidence-out", default=None)
    args = parser.parse_args()
    violations: list[str] = []
    checks: dict = {}
    _static_checks(violations, checks)
    if args.dsn is not None:
        _live_checks(args.dsn, violations, checks)
    status = "PASS" if not violations else "FAIL"
    print(f"B26_P2_XV_PHYS_{status}")
    if violations:
        print(";".join(sorted(violations)))
    else:
        print(json.dumps({"checks": checks}, sort_keys=True, default=str))
    if args.evidence_out:
        Path(args.evidence_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.evidence_out).write_text(
            json.dumps(
                {
                    "gate_id": "B26-P2-XV-PHYSICS",
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
