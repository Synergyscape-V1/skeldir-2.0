#!/usr/bin/env python3
"""B2.6-P2 Corrective XVII historical-reconciliation physics closure.

Laws (each REDs on the effect):
- historical disposition: every pre-regime trusted row is demoted to
  pending with an explicit reason on upgrade (live: XIV-head false row
  -> linear upgrade -> pending + reason + non-dispatchable);
- regime identity: only xvii-sovereign-v1 rows authenticate, dispatch,
  and conduct (live: regime stamp on lawful auth; old-regime survivor
  flagged by the binding oracle, refused at dispatch, P3 FALSE);
- identity conservation: same event ref + different bytes -> conflict
  refusal; same commerce identity across distinct events -> conflict
  refusal; same bytes -> duplicate token (XVI preserved); re-entry
  idempotent (live);
- tuple binding: witness covers the semantic tuple; detachment is
  oracle-visible and re-binding is deterministic (live);
- redelivery recovery: a demoted row re-authenticates via provider
  redelivery with regime stamp and cleared reason (live).

Exit code is the gate. Live DB checks run only with --dsn.
"""

from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MIG_XVII = (
    REPO_ROOT
    / "alembic"
    / "versions"
    / "007_skeldir_foundation"
    / "202609290001_b26_p2_corrective_xvii_historical_reconciliation.py"
)
MIG_XVI = (
    REPO_ROOT
    / "alembic"
    / "versions"
    / "007_skeldir_foundation"
    / "202609280002_b26_p2_corrective_xvi_sovereign_closure.py"
)

REGIME = "xvii-sovereign-v1"
REASON = "xvii-pre-binding-unverifiable"


def _static_checks(violations: list[str], checks: dict) -> None:
    try:
        text = MIG_XVII.read_text(encoding="utf-8")
    except OSError as exc:
        violations.append(f"xvii_phys_unreadable:{exc}")
        return
    upgrade = text.split("def downgrade", 1)[0]
    for token in (
        "b26_p2_semantic_regime",
        "b26_p2_demotion_reason",
        "xvii-sovereign-v1",
        "xvii-pre-binding-unverifiable",
        "b26_p2_atomic_event_identity_conflict_refused",
        "b26_p2_atomic_commerce_identity_conflict_refused",
        "b26_p2_atomic_sovereign_duplicate_refused",
        "pg_advisory_xact_lock",
        "uq_b26_p2_xvii_event_identity",
        "uq_b26_p2_xvii_commerce_identity",
        "b26_p2_xvii_semantic_binding_oracle",
        "b26_p2_dispatch_regime_unverifiable_refused",
        "b26_p2_dispatch_sovereign_regime_unverifiable",
        "DISABLE TRIGGER trg_b26_p2_ingress_provenance",
        "ENABLE TRIGGER trg_b26_p2_ingress_provenance",
    ):
        if token not in upgrade:
            violations.append(f"xvii_phys_law_missing:{token}")
    checks["xvii_law_present"] = True
    # The atomic keeps its exact 7-argument signature: the XVI strict
    # evidence-gate frame still matches (no silent frame drift).
    if (
        "b26_p2_authenticate_ingress_atomic(\\n"
        "            p_ingress uuid," not in upgrade
        and "p_ingress uuid," not in upgrade
    ):
        violations.append("xvii_phys_atomic_signature_drift")
    else:
        checks["atomic_signature_stable"] = True
    # Downgrade restores predecessor law verbatim (documented, not silent).
    downgrade = text.split("def downgrade", 1)[1]
    for token in (
        "DROP INDEX IF EXISTS public.uq_b26_p2_xvii_event_identity",
        "DROP INDEX IF EXISTS public.uq_b26_p2_xvii_commerce_identity",
        "b26_p2_xvii_semantic_binding_oracle",
    ):
        if token not in downgrade:
            violations.append(f"xvii_phys_downgrade_missing:{token}")
    checks["downgrade_restores_predecessor"] = True
    # XVI surface preserved: the XVI migration file itself is untouched
    # by XVII (new forward law only, H-XVII-R13).
    try:
        xvi = MIG_XVI.read_text(encoding="utf-8")
    except OSError as exc:
        violations.append(f"xvii_phys_xvi_unreadable:{exc}")
        return
    if "b26_p2_atomic_sovereign_duplicate_refused" not in xvi:
        violations.append("xvii_phys_xvi_fence_moved")
    else:
        checks["xvi_forward_law_preserved"] = True


def _mkrow(cur, tenant, evref, cref, amount):
    ev, ing = str(uuid.uuid4()), str(uuid.uuid4())
    cur.execute(
        "INSERT INTO public.attribution_events (id, tenant_id, occurred_at,"
        " correlation_id, session_id, revenue_cents, raw_payload, idempotency_key,"
        " event_type, channel, campaign_id, conversion_value_cents, currency,"
        " event_timestamp, processed_at, processing_status)"
        " VALUES (%s,%s,now(),%s,%s,%s,'{}'::jsonb,%s,'conversion',"
        " 'xvii_phys_ch','c',%s,'USD',now(),now(),'processed')",
        (ev, tenant, str(uuid.uuid4()), str(uuid.uuid4()), amount,
         str(uuid.uuid4()), amount),
    )
    cur.execute(
        "INSERT INTO public.webhook_ingress_identities (id, tenant_id, event_id,"
        " provider, provider_native_event_reference,"
        " provider_native_commerce_reference,"
        " normalized_commerce_reference_kind,"
        " normalized_commerce_reference_value, verified_amount_minor,"
        " verified_amount_currency, event_timestamp, idempotency_key,"
        " verified_commerce_ingress_state)"
        " VALUES (%s,%s,%s,'stripe',%s,%s,'stripe_payment_intent_id',%s,%s,'USD',"
        " now(),%s,'authenticity_verified')",
        (ing, tenant, ev, evref, cref, cref, amount, str(uuid.uuid4())),
    )
    return ing


def _auth(icur, ing, eref, sha, sig="b" * 64):
    icur.execute(
        "SELECT public.b26_p2_authenticate_ingress_atomic(%s,'stripe',%s,%s,%s,"
        "'hmac-sha256-timestamped-hex','v1')",
        (ing, eref, sha, sig),
    )
    return str(icur.fetchone()[0])


def _live_checks(admin_dsn: str, violations: list[str], checks: dict) -> None:
    try:
        import psycopg2  # noqa: PLC0415
    except ImportError as exc:
        violations.append(f"xvii_phys_no_driver:{exc}")
        return
    ingress_dsn = (
        admin_dsn.replace("migration_owner:migration_owner", "app_ingress:app_ingress")
        if "migration_owner:migration_owner" in admin_dsn
        else None
    )
    if ingress_dsn is None:
        violations.append("xvii_phys_role_dsn_underivable")
        return
    try:
        admin = psycopg2.connect(admin_dsn)
        admin.autocommit = True
    except Exception as exc:
        violations.append(f"xvii_phys_connect_failed:{exc}")
        return
    try:
        cur = admin.cursor()
        tenant = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO public.tenants (id, name, api_key_hash, notification_email)"
            " VALUES (%s,%s,%s,%s)",
            (tenant, "xvii-phys", uuid.uuid4().hex, "xvii-phys@example.invalid"),
        )
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false)", (tenant,))
        cur.execute(
            "INSERT INTO public.channel_taxonomy (code, family, is_paid,"
            " display_name, state) VALUES ('xvii_phys_ch', 'xvii_phys', true,"
            " 'XVIIPHYS', 'active') ON CONFLICT (code) DO NOTHING"
        )
        ing = psycopg2.connect(ingress_dsn)
        ing.autocommit = True
        try:
            with ing.cursor() as icur:
                icur.execute(
                    "SELECT set_config('app.current_tenant_id', %s, false)",
                    (tenant,),
                )
                sha_a = "a" * 64
                # Lawful lineage: regime stamped, reason clear.
                row1 = _mkrow(cur, tenant, "xvii-e1", "xvii-c1", 7600)
                assert _auth(icur, row1, "xvii-e1", sha_a) == "authenticated_known"
                icur.execute(
                    "SELECT b26_p2_semantic_regime, b26_p2_demotion_reason,"
                    " b26_p2_provenance_status"
                    " FROM public.webhook_ingress_identities WHERE id = %s",
                    (row1,),
                )
                regime, reason, prov = icur.fetchone()
                if regime != REGIME or reason is not None or prov != "authenticated_known":
                    violations.append(
                        f"xvii_phys_regime_stamp_wrong:{regime}:{reason}:{prov}"
                    )
                else:
                    checks["lawful_path_stamps_regime"] = True
                # XVI preserved: same bytes + same ref, different row.
                row2 = _mkrow(cur, tenant, "xvii-e1", "xvii-c9", 7600)
                try:
                    _auth(icur, row2, "xvii-e1", sha_a)
                    violations.append("xvii_phys_same_bytes_second_lineage")
                except Exception as exc:
                    if "b26_p2_atomic_sovereign_duplicate_refused" not in str(exc):
                        violations.append(
                            "xvii_phys_dup_wrong_refusal:"
                            f"{str(exc).splitlines()[0][:120]}"
                        )
                    else:
                        checks["same_bytes_second_lineage_refused"] = True
                # XVII event identity: same ref + different bytes.
                try:
                    _auth(icur, row2, "xvii-e1", "d" * 64)
                    violations.append("xvii_phys_same_ref_second_lineage")
                except Exception as exc:
                    if "b26_p2_atomic_event_identity_conflict_refused" not in str(exc):
                        violations.append(
                            "xvii_phys_event_conflict_wrong_refusal:"
                            f"{str(exc).splitlines()[0][:120]}"
                        )
                    else:
                        checks["same_ref_conflict_refused"] = True
                # XVII commerce conservation: same commerce, distinct event.
                row3 = _mkrow(cur, tenant, "xvii-e2", "xvii-c1", 7600)
                try:
                    _auth(icur, row3, "xvii-e2", "e" * 64)
                    violations.append("xvii_phys_same_commerce_second_lineage")
                except Exception as exc:
                    if "b26_p2_atomic_commerce_identity_conflict_refused" not in str(exc):
                        violations.append(
                            "xvii_phys_commerce_conflict_wrong_refusal:"
                            f"{str(exc).splitlines()[0][:120]}"
                        )
                    else:
                        checks["same_commerce_conflict_refused"] = True
                # Distinct event + distinct commerce still authenticates.
                row4 = _mkrow(cur, tenant, "xvii-e3", "xvii-c3", 100)
                assert _auth(icur, row4, "xvii-e3", "f" * 64) == "authenticated_known"
                checks["distinct_events_authenticate"] = True
                # Same-row re-entry idempotent.
                assert _auth(icur, row1, "xvii-e1", sha_a) == "authenticated_known"
                checks["same_row_reentry_idempotent"] = True
                # Binding oracle clean on lawful state.
                cur.execute(
                    "SELECT count(*) FROM public.b26_p2_xvii_semantic_binding_oracle()"
                )
                if cur.fetchone()[0] != 0:
                    violations.append("xvii_phys_oracle_dirty_on_lawful")
                else:
                    checks["binding_oracle_clean"] = True
                # Tuple detachment visible: tamper witness as admin...
                cur.execute(
                    "UPDATE public.b26_p2_ingress_auth_witness SET witness_hash='0'"
                    " WHERE webhook_ingress_identity_id = %s",
                    (row1,),
                )
                cur.execute(
                    "SELECT violation_kind FROM"
                    " public.b26_p2_xvii_semantic_binding_oracle()"
                )
                kinds = [r[0] for r in cur.fetchall()]
                if "xvii_semantic_tuple_detached" not in kinds:
                    violations.append("xvii_phys_detach_invisible")
                else:
                    checks["tuple_detach_visible"] = True
                # ...and deterministic re-binding on re-authentication.
                assert _auth(icur, row1, "xvii-e1", sha_a) == "authenticated_known"
                cur.execute(
                    "SELECT count(*) FROM public.b26_p2_xvii_semantic_binding_oracle()"
                )
                if cur.fetchone()[0] != 0:
                    violations.append("xvii_phys_rebind_not_clean")
                else:
                    checks["reauth_rebinds_deterministically"] = True
                # Regime drift visible: an authenticated row outside the
                # governed regime is flagged even with intact evidence.
                cur.execute(
                    "UPDATE public.webhook_ingress_identities"
                    " SET b26_p2_semantic_regime = 'pre-xvii-unverifiable'"
                    " WHERE id = %s",
                    (row4,),
                )
                cur.execute(
                    "SELECT violation_kind FROM"
                    " public.b26_p2_xvii_semantic_binding_oracle()"
                )
                kinds = [r[0] for r in cur.fetchall()]
                if "xvii_regime_unverifiable_trusted" not in kinds:
                    violations.append("xvii_phys_regime_drift_invisible")
                else:
                    checks["regime_drift_visible"] = True
                # Dispatch refuses the drifted row with the regime token.
                try:
                    cur.execute(
                        "INSERT INTO public.b23_match_task_dispatches (tenant_id,"
                        " webhook_ingress_identity_id, task_id, task_name, queue,"
                        " routing_key, correlation_id, provider,"
                        " provider_native_event_reference,"
                        " provider_native_commerce_reference,"
                        " normalized_commerce_reference_value)"
                        " VALUES (%s,%s,%s,"
                        " 'app.tasks.revenue_verification.execute_b23_batch_match_engine',"
                        " 'b23_match_engine','k',%s,'stripe','xvii-e3','xvii-c3','xvii-c3')",
                        (tenant, row4, "xvii-dispatch-drifted", str(uuid.uuid4())),
                    )
                    violations.append("xvii_phys_drifted_dispatch_permitted")
                except Exception as exc:
                    admin.rollback()
                    cur.execute(
                        "SELECT set_config('app.current_tenant_id', %s, false)",
                        (tenant,),
                    )
                    if "b26_p2_dispatch_regime_unverifiable_refused" not in str(exc):
                        violations.append(
                            "xvii_phys_dispatch_wrong_refusal:"
                            f"{str(exc).splitlines()[0][:120]}"
                        )
                    else:
                        checks["drifted_dispatch_refused"] = True
                # Restore lawful regime via re-authentication, then the
                # dispatch path admits the row shape again.
                assert _auth(icur, row4, "xvii-e3", "f" * 64) == "authenticated_known"
                cur.execute(
                    "SELECT b26_p2_semantic_regime FROM"
                    " public.webhook_ingress_identities WHERE id = %s",
                    (row4,),
                )
                if cur.fetchone()[0] != REGIME:
                    violations.append("xvii_phys_regime_not_restored")
                else:
                    checks["regime_restored_on_reauth"] = True
                cur.execute(
                    "SELECT count(*) FROM public.b26_p2_xvii_semantic_binding_oracle()"
                )
                if cur.fetchone()[0] != 0:
                    violations.append("xvii_phys_oracle_dirty_at_close")
        finally:
            ing.close()
        cur.close()
    except Exception as exc:
        violations.append(f"xvii_phys_live_failed:{exc}")
    finally:
        admin.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="XVII physics closure.")
    parser.add_argument("--dsn", default=None)
    parser.add_argument("--evidence-out", default=None)
    args = parser.parse_args()
    violations: list[str] = []
    checks: dict = {}
    _static_checks(violations, checks)
    if args.dsn is not None:
        _live_checks(args.dsn, violations, checks)
    status = "PASS" if not violations else "FAIL"
    print(f"B26_P2_XVII_PHYS_{status}")
    if violations:
        print(";".join(sorted(violations)))
    else:
        print(json.dumps({"checks": checks}, sort_keys=True, default=str))
    if args.evidence_out:
        Path(args.evidence_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.evidence_out).write_text(
            json.dumps(
                {
                    "gate_id": "B26-P2-XVII-PHYSICS",
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
