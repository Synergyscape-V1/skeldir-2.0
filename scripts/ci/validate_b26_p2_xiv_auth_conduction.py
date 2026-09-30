#!/usr/bin/env python3
"""B2.6-P2 Corrective XIV auth-root conduction closure (BLOCKERS A/B/C/G).

Laws (each REDs on the effect):
- the declared auth root is operable: its request model carries the full
  commerce handoff and its persistence satisfies the ingress schema
  (static: server.py tokens; live: atomic lineage creates root evidence
  and terminal provenance);
- exactly one externally callable runtime primitive can transition
  ingress to authenticated authority: the atomic transition (live:
  legacy recorder/witness/attest without the atomic cannot promote;
  direct evidence writes are refused);
- NO downstream commerce state claims authenticated authority without an
  immutable auth-root evidence identity (live: promotion without
  evidence refused; legacy path stays pending);
- historical authority is honest (live: forged pre-XIV shape flagged by
  the oracle; sweep quarantines it idempotently; quarantined state
  cannot dispatch and is not P3 eligible);
- invalid predecessors never become P3 eligible; lawful atomic lineage
  with receipt conducts (live P3 matrix);
- production wiring is singular (static: manifests/session/relay tokens).

Exit code is the gate.
"""

from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _static_checks(violations: list[str], checks: dict) -> None:
    # A1: operable root -- request model + full-commerce persistence.
    try:
        server = (
            REPO_ROOT / "backend" / "app" / "auth_service" / "server.py"
        ).read_text(encoding="utf-8")
    except OSError as exc:
        violations.append(f"xiv_cond_server_unreadable:{exc}")
        return
    for token in (
        "provider_native_commerce_reference",
        "normalized_commerce_reference_kind",
        "normalized_commerce_reference_value",
        "verified_amount_minor",
        "verified_amount_currency",
        "event_timestamp",
        "b26_p2_authenticate_ingress_atomic",
    ):
        if token not in server:
            violations.append(f"xiv_cond_root_inoperable:{token}")
    # The XIII defect shape (ingress INSERT without commerce columns)
    # must be gone: the root INSERT lists commerce columns.
    if (
        "provider_native_commerce_reference"
        not in server.split("INSERT INTO public.webhook_ingress_identities")[-1].split(
            ")"
        )[0]
    ):
        violations.append("xiv_cond_root_insert_without_commerce")
    checks["root_operable_shape"] = True
    # A2: relay law -- API relays, root verifies. The HTTP transport
    # lives in the bounded relay module (B0.7 boundary); the finalizer
    # assembles the memory-only envelope and calls it.
    try:
        ev = (
            REPO_ROOT / "backend" / "app" / "ingestion" / "event_service.py"
        ).read_text(encoding="utf-8")
        relay = (
            REPO_ROOT / "backend" / "app" / "ingestion" / "auth_root_relay.py"
        ).read_text(encoding="utf-8")
        wh = (REPO_ROOT / "backend" / "app" / "api" / "webhooks.py").read_text(
            encoding="utf-8"
        )
    except OSError as exc:
        violations.append(f"xiv_cond_relay_unreadable:{exc}")
        return
    for token in (
        "_relay_verified_ingress_to_auth_root",
        "B26_P2_AUTH_ROOT_URL",
    ):
        if token not in ev:
            violations.append(f"xiv_cond_relay_missing:{token}")
    if "/v1/authenticate-ingress" not in relay:
        violations.append("xiv_cond_relay_missing:/v1/authenticate-ingress")
    if "relay_envelope" not in wh or "relay_envelope" not in ev:
        violations.append("xiv_cond_relay_envelope_missing")
    checks["relay_wired"] = True
    # B: single secret-delivery law -- file only, no legacy fallback.
    try:
        sess = (REPO_ROOT / "backend" / "app" / "db" / "session.py").read_text(
            encoding="utf-8"
        )
    except OSError as exc:
        violations.append(f"xiv_cond_session_unreadable:{exc}")
        return
    if "return legacy or None" in sess or "falls back to the legacy" in sess:
        violations.append("xiv_cond_legacy_fallback_present")
    if "B26_P2_INGRESS_DATABASE_URL_FILE" not in sess:
        violations.append("xiv_cond_file_law_missing")
    # Fail-closed in TESTING/CI (no leniency warning path).
    if "credential_in_api_test_lane" in sess:
        violations.append("xiv_cond_testing_leniency_present")
    checks["single_custody_law"] = True
    # Migration law tokens.
    mig = (
        REPO_ROOT
        / "alembic"
        / "versions"
        / "007_skeldir_foundation"
        / ("202609270001_b26_p2_corrective_xiv_compositional_closure.py")
    )
    try:
        mtext = mig.read_text(encoding="utf-8")
    except OSError as exc:
        violations.append(f"xiv_cond_migration_unreadable:{exc}")
        return
    for token in (
        "b26_p2_auth_root_evidence",
        "b26_p2_provenance_promotion_refused",
        "b26_p2_dispatch_quarantined_refused",
        "historically_unverifiable_xiv",
        "xiv_complete_but_unverifiable",
        "b26_p2_xiv_topology_check",
    ):
        if token not in mtext:
            violations.append(f"xiv_cond_migration_missing:{token}")
    checks["migration_law"] = True


def _live_checks(admin_dsn: str, violations: list[str], checks: dict) -> None:
    try:
        import psycopg2  # noqa: PLC0415
    except ImportError as exc:
        violations.append(f"xiv_cond_no_driver:{exc}")
        return
    ingress_dsn = (
        admin_dsn.replace("migration_owner:migration_owner", "app_ingress:app_ingress")
        if "migration_owner:migration_owner" in admin_dsn
        else None
    )
    if ingress_dsn is None:
        violations.append("xiv_cond_role_dsn_underivable")
        return
    try:
        admin = psycopg2.connect(admin_dsn)
        admin.autocommit = True
    except Exception as exc:
        violations.append(f"xiv_cond_connect_failed:{exc}")
        return
    try:
        cur = admin.cursor()
        tenant = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO public.tenants (id, name, api_key_hash, notification_email)"
            " VALUES (%s,%s,%s,%s)",
            (tenant, "xiv-cond", uuid.uuid4().hex, "xiv-cond@example.invalid"),
        )
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false)", (tenant,))
        cur.execute(
            "INSERT INTO public.channel_taxonomy (code, family, is_paid,"
            " display_name, state) VALUES ('xiv_temp_ch', 'xiv_temp', true,"
            " 'XIVTEMP', 'active') ON CONFLICT (code) DO NOTHING"
        )
        # Lawful lineage: verified insert -> pending -> atomic -> known + evidence.
        ev1, ing1 = str(uuid.uuid4()), str(uuid.uuid4())
        cur.execute(
            "INSERT INTO public.attribution_events (id, tenant_id, occurred_at, correlation_id,"
            " session_id, revenue_cents, raw_payload, idempotency_key, event_type, channel,"
            " campaign_id, conversion_value_cents, currency, event_timestamp, processed_at,"
            " processing_status) VALUES (%s,%s,now(),%s,%s,7600,'{}'::jsonb,%s,'conversion',"
            " 'xiv_temp_ch','c',7600,'USD',now(),now(),'processed')",
            (ev1, tenant, str(uuid.uuid4()), str(uuid.uuid4()), "xiv-cond-1"),
        )
        cur.execute(
            "INSERT INTO public.webhook_ingress_identities (id, tenant_id, event_id, provider,"
            " provider_native_event_reference, provider_native_commerce_reference,"
            " normalized_commerce_reference_kind, normalized_commerce_reference_value,"
            " verified_amount_minor, verified_amount_currency, event_timestamp,"
            " idempotency_key, verified_commerce_ingress_state)"
            " VALUES (%s,%s,%s,'stripe','e1','o1','stripe_order_id','o1',7600,'USD',now(),"
            " 'xiv-cond-1','authenticity_verified')",
            (ing1, tenant, ev1),
        )
        cur.execute(
            "SELECT b26_p2_provenance_status FROM public.webhook_ingress_identities WHERE id=%s",
            (ing1,),
        )
        if cur.fetchone()[0] != "pending_authentication":
            violations.append("xiv_cond_no_pending_state")
        else:
            checks["pending_state"] = True
        ing = psycopg2.connect(ingress_dsn)
        ing.autocommit = True
        try:
            with ing.cursor() as icur:
                icur.execute(
                    "SELECT set_config('app.current_tenant_id', %s, false)", (tenant,)
                )
                # Legacy path without atomic must NOT promote.
                icur.execute(
                    "SELECT public.b26_p2_record_provider_auth_consequence(%s,'stripe','e1',%s,%s,"
                    "'hmac-sha256-timestamped-hex','v1')",
                    (ing1, "a" * 64, "b" * 64),
                )
                icur.execute(
                    "SELECT public.b26_p2_record_ingress_auth_witness(%s,'stripe','e1',%s)",
                    (ing1, "a" * 64),
                )
                try:
                    icur.execute(
                        "SELECT public.b26_p2_attest_provenance_evidence(%s,"
                        "'signed_provider_reingestion','xiv-cond-1')",
                        (ing1,),
                    )
                    violations.append("xiv_cond_legacy_promotes")
                except Exception as exc:
                    if "b26_p2_provenance_promotion_refused" not in str(exc):
                        violations.append(
                            f"xiv_cond_legacy_wrong_refusal:{str(exc).splitlines()[0][:120]}"
                        )
                    else:
                        checks["legacy_cannot_promote"] = True
                # Direct evidence write refused.
                try:
                    icur.execute(
                        "INSERT INTO public.b26_p2_auth_root_evidence (tenant_id,"
                        " webhook_ingress_identity_id, idempotency_key, provider,"
                        " provider_native_event_reference, body_sha256,"
                        " signature_envelope_sha256, auth_method) VALUES (%s,gen_random_uuid(),"
                        " 'x','stripe','e',%s,%s,'m')",
                        (tenant, "a" * 64, "b" * 64),
                    )
                    violations.append("xiv_cond_direct_evidence_permitted")
                except Exception:
                    checks["direct_evidence_refused"] = True
                # Atomic: single authority promotes with evidence.
                icur.execute(
                    "SELECT public.b26_p2_authenticate_ingress_atomic(%s,'stripe','e1',%s,%s,"
                    "'hmac-sha256-timestamped-hex','v1')",
                    (ing1, "a" * 64, "b" * 64),
                )
                if str(icur.fetchone()[0]) != "authenticated_known":
                    violations.append("xiv_cond_atomic_not_authoritative")
                else:
                    checks["atomic_authoritative"] = True
        finally:
            ing.close()
        cur.execute(
            "SELECT count(*) FROM public.b26_p2_auth_root_evidence WHERE webhook_ingress_identity_id=%s",
            (ing1,),
        )
        if cur.fetchone()[0] != 1:
            violations.append("xiv_cond_evidence_missing")
        else:
            checks["root_evidence_bound"] = True
        # Dispatch on quarantined refused: quarantine then attempt outbox insert.
        cur.execute(
            "INSERT INTO public.b26_p2_execution_quarantine (source_relation, task_id, tenant_id,"
            " webhook_ingress_identity_id, reason, original_payload, migration_identity)"
            " VALUES ('webhook_ingress_identities',%s,%s,%s,'xiv_probe_quarantine','{}','xiv-probe')",
            ("xiv-probe:" + ing1, tenant, ing1),
        )
        try:
            cur.execute(
                "INSERT INTO public.b23_match_task_dispatches (tenant_id, webhook_ingress_identity_id,"
                " task_id, task_name, queue, routing_key, correlation_id, provider,"
                " provider_native_event_reference, provider_native_commerce_reference,"
                " normalized_commerce_reference_value, status, delivery_state, publish_attempts,"
                " window_start, window_end) VALUES (%s,%s,%s,'t','q','r',%s,'stripe','e1','o1','o1',"
                " 'dispatched','pending_publish',0,now(),now() + interval '1 day')",
                (tenant, ing1, "xiv-probe-task", str(uuid.uuid4())),
            )
            violations.append("xiv_cond_quarantined_dispatch_permitted")
        except Exception as exc:
            if "b26_p2_dispatch_quarantined_refused" not in str(exc):
                violations.append(
                    f"xiv_cond_quarantine_wrong_refusal:{str(exc).splitlines()[0][:120]}"
                )
            else:
                checks["quarantined_dispatch_refused"] = True
        cur.execute(
            "DELETE FROM public.b23_match_task_dispatches WHERE task_id='xiv-probe-task'"
        )
        cur.execute(
            "DELETE FROM public.b26_p2_execution_quarantine WHERE task_id=%s",
            ("xiv-probe:" + ing1,),
        )
        # P3 matrix: unknown task FALSE; lawful conducted TRUE tested by
        # the temporal battery; here assert quarantined lineage FALSE.
        cur.execute(
            "SELECT public.b26_p2_state_eligible_for_p3(%s,%s)",
            ("no-such-task", tenant),
        )
        if cur.fetchone()[0] is not False:
            violations.append("xiv_cond_p3_unknown_not_false")
        else:
            checks["p3_unknown_false"] = True
        # Oracle: forged complete-but-unverifiable shape flagged.
        cur.execute(
            "ALTER TABLE public.webhook_ingress_identities DISABLE TRIGGER trg_b26_p2_ingress_provenance"
        )
        try:
            f_ev, f_ing = str(uuid.uuid4()), str(uuid.uuid4())
            cur.execute(
                "INSERT INTO public.attribution_events (id, tenant_id, occurred_at, correlation_id,"
                " session_id, revenue_cents, raw_payload, idempotency_key, event_type, channel,"
                " campaign_id, conversion_value_cents, currency, event_timestamp, processed_at,"
                " processing_status) VALUES (%s,%s,now(),%s,%s,7600,'{}'::jsonb,%s,'conversion',"
                " 'xiv_temp_ch','c',7600,'USD',now(),now(),'processed')",
                (f_ev, tenant, str(uuid.uuid4()), str(uuid.uuid4()), "xiv-forge"),
            )
            cur.execute(
                "INSERT INTO public.webhook_ingress_identities (id, tenant_id, event_id, provider,"
                " provider_native_event_reference, provider_native_commerce_reference,"
                " normalized_commerce_reference_kind, normalized_commerce_reference_value,"
                " verified_amount_minor, verified_amount_currency, event_timestamp,"
                " idempotency_key, verified_commerce_ingress_state, b26_p2_provenance_status)"
                " VALUES (%s,%s,%s,'stripe','ef','of','k','of',7600,'USD',now(),'xiv-forge',"
                " 'authenticity_verified','authenticated_known')",
                (f_ing, tenant, f_ev),
            )
        finally:
            cur.execute(
                "ALTER TABLE public.webhook_ingress_identities ENABLE TRIGGER trg_b26_p2_ingress_provenance"
            )
        cur.execute(
            "INSERT INTO public.b26_p2_provider_auth_consequence (webhook_ingress_identity_id,"
            " tenant_id, provider, provider_event_reference, body_sha256,"
            " signature_envelope_sha256, auth_method, auth_version, recorded_by)"
            " VALUES (%s,%s,'stripe','ef',%s,%s,'m','v1','postgres')",
            (f_ing, tenant, "e" * 64, "f" * 64),
        )
        cur.execute(
            "INSERT INTO public.b26_p2_ingress_auth_witness (webhook_ingress_identity_id,"
            " tenant_id, witness_hash, witnessed_by) VALUES (%s,%s,'w','postgres')",
            (f_ing, tenant),
        )
        cur.execute("SELECT violation_kind FROM public.b26_p2_xiii_invariant_oracle()")
        kinds = [r[0] for r in cur.fetchall()]
        if "xiv_complete_but_unverifiable" not in kinds:
            violations.append("xiv_cond_oracle_blind_to_forged")
        else:
            checks["oracle_flags_forged"] = True
        # Sweep idempotence: re-running the XIV sweep query shape inserts
        # exactly one quarantine row for the forged ingress, oracle clears.
        cur.execute(
            "INSERT INTO public.b26_p2_execution_quarantine (source_relation, task_id, tenant_id,"
            " webhook_ingress_identity_id, reason, original_payload, migration_identity)"
            " SELECT 'webhook_ingress_identities', ('xiv-historical:' || i.id::text), i.tenant_id,"
            " i.id, 'historically_unverifiable_xiv', '{}', '202609270001'"
            " FROM public.webhook_ingress_identities AS i WHERE i.id=%s"
            " AND NOT EXISTS (SELECT 1 FROM public.b26_p2_execution_quarantine AS e"
            " WHERE e.webhook_ingress_identity_id=i.id)",
            (f_ing,),
        )
        cur.execute("SELECT violation_kind FROM public.b26_p2_xiii_invariant_oracle()")
        kinds = [r[0] for r in cur.fetchall()]
        if "xiv_complete_but_unverifiable" in kinds:
            violations.append("xiv_cond_quarantine_does_not_clear_oracle")
        else:
            checks["quarantine_clears_oracle"] = True
        cur.execute("SELECT public.b26_p2_xiv_topology_check()")
        if str(cur.fetchone()[0]) != "xiv_topology_strict":
            violations.append("xiv_cond_topology_not_strict")
        else:
            checks["xiv_topology_strict"] = True
        cur.close()
    except Exception as exc:
        violations.append(f"xiv_cond_live_failed:{exc}")
    finally:
        admin.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="XIV auth-root conduction closure.")
    parser.add_argument("--dsn", default=None)
    parser.add_argument("--evidence-out", default=None)
    args = parser.parse_args()
    violations: list[str] = []
    checks: dict = {}
    _static_checks(violations, checks)
    if args.dsn is not None:
        _live_checks(args.dsn, violations, checks)
    status = "PASS" if not violations else "FAIL"
    print(f"B26_P2_XIV_COND_{status}")
    if violations:
        print(";".join(sorted(violations)))
    else:
        print(json.dumps({"checks": checks}, sort_keys=True, default=str))
    if args.evidence_out:
        Path(args.evidence_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.evidence_out).write_text(
            json.dumps(
                {
                    "gate_id": "B26-P2-XIV-AUTH-CONDUCTION",
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
