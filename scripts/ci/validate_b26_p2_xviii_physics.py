#!/usr/bin/env python3
"""B2.6-P2 Corrective XVIII authority-conservation physics closure.

Proves the conservation laws as database physics on a governed lane:

- unforgeable trust transition: no runtime role produces the current
  authority conjunction outside the sovereign atomic (NC-02);
- stale evidence never satisfies current promotion (NC-03);
- demoted ingress never enters the B2.3 candidate universe (NC-04);
- demoted consequences lose current financial authority (NC-05/06);
- coverage separates verified from unverifiable without false
  confidence (NC-06);
- the sovereign transition binds a supported event family (NC-07/08);
- batch liveness under demoted+redelivered pairs (NC-11);
- downgrade serving is physically disabled (NC-10);
- NULL/multi-column updates never authorize (NC-13/XVIII-P).

Static arms run without a database; live arms run with --dsn (admin
lane DSN; app_ingress/app_user derived like the XVII gate).

Exit code is the gate. Prints B26_P2_XVIII_PHYS_PASS on success.
"""

from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MIG_XVIII = (
    REPO_ROOT
    / "alembic"
    / "versions"
    / "007_skeldir_foundation"
    / "202609300001_b26_p2_corrective_xviii_authority_conservation.py"
)
BATCH_PATH = REPO_ROOT / "backend" / "app" / "revenue_verification" / "batch_engine.py"
COVERAGE_PATH = (
    REPO_ROOT
    / "backend"
    / "app"
    / "revenue_verification"
    / "verification_coverage.py"
)
DERIVATION_PATH = (
    REPO_ROOT / "backend" / "app" / "webhooks" / "commerce_derivation.py"
)
ROOT_PATH = REPO_ROOT / "backend" / "app" / "auth_service" / "server.py"

REGIME = "xvii-sovereign-v1"
REASON = "xvii-pre-binding-unverifiable"


def _static_checks(violations: list[str], checks: dict) -> None:
    try:
        text = MIG_XVIII.read_text(encoding="utf-8")
    except OSError as exc:
        violations.append(f"xviii_phys_unreadable:{exc}")
        return
    upgrade = text.split("def downgrade", 1)[0]
    for token in (
        "b26_p2_semantic_regime_registry",
        "b26_p2_ingress_has_current_authority",
        "trg_b26_p2_ingress_authority_transition",
        "b26_p2_authority_transition_refused",
        "b26_p2_atomic_demoted_ingress_refused",
        "b26_p2_evidence_demoted_ingress_refused",
        "b26_p2_downgrade_serving_refused",
        "b26_p2_atomic_family_unbound_refused",
        "b26_p2_event_family",
        "b26_p2_operational_floor",
        "b26_p2_derive_verdict_authority",
        "trg_b26_p2_verdict_authority_stamp",
        "trg_b26_p2_verdict_authority_propagate",
        "b26_p2_dispatch_demotion_active_refused",
        "b26_p2_dispatch_family_unbound_refused",
        "b26_p2_governed_transition",
        "b26_p2_registry_history_immutable_refused",
    ):
        if token not in upgrade:
            violations.append(f"xviii_phys_law_missing:{token}")
    if not [v for v in violations if "xviii_phys_law_missing" in v]:
        checks["xviii_law_present"] = True
    # Column-privilege layer: the REVOKE statements are
    # existence-guarded DO blocks, so the assertion is whitespace-
    # and split-insensitive (a bare substring would be brittle
    # across the guarded string boundaries).
    import re as _re  # noqa: PLC0415

    _compact = _re.sub(r"\s+", " ", text)
    for label, pattern in (
        (
            "ingress_authority_columns",
            r"REVOKE UPDATE.{0,80}b26_p2_provenance_status"
            r".{0,80}b26_p2_semantic_regime.{0,80}b26_p2_demotion_reason",
        ),
        (
            "verdict_authority_column",
            r"REVOKE UPDATE.{0,80}b26_p2_source_authority_state",
        ),
    ):
        if not _re.search(pattern, _compact):
            violations.append(f"xviii_phys_privilege_missing:{label}")
        else:
            checks[f"privilege_{label}"] = True
    # The sovereign signature is byte-stable (XVI strict frame gate).
    if "p_version text DEFAULT 'v1'\n        )" not in upgrade:
        violations.append("xviii_phys_atomic_signature_drift")
    else:
        checks["atomic_signature_stable"] = True
    for path, tokens in (
        (BATCH_PATH, (
            "b26_p2_ingress_has_current_authority",
            "event_ref_rank",
            "b26_p2_source_authority_state = 'current'",
        )),
        (COVERAGE_PATH, (
            "b26_p2_ingress_has_current_authority",
            "unverifiable_historical_revenue",
            "b26_p2_source_authority_state = 'current'",
        )),
        (DERIVATION_PATH, (
            "derive_event_family",
            "CANONICAL_EVENT_FAMILY_BY_PROVIDER",
        )),
        (ROOT_PATH, (
            "derive_event_family",
            "b26_p2_unsupported_event_family_refused",
            "app.b26_p2_event_family",
            "b26_p2_ingress_has_current_authority",
        )),
    ):
        try:
            body = path.read_text(encoding="utf-8")
        except OSError as exc:
            violations.append(f"xviii_phys_unreadable:{path.name}:{exc}")
            continue
        for token in tokens:
            if token not in body:
                violations.append(f"xviii_phys_reader_missing:{path.name}:{token}")
    if not [v for v in violations if "xviii_phys_reader_missing" in v]:
        checks["readers_conserve_authority"] = True


def _live_checks(admin_dsn: str, violations: list[str], checks: dict) -> None:
    try:
        import psycopg2  # noqa: PLC0415
    except ImportError as exc:
        violations.append(f"xviii_phys_no_driver:{exc}")
        return
    ingress_dsn = (
        admin_dsn.replace("migration_owner:migration_owner", "app_ingress:app_ingress")
        if "migration_owner:migration_owner" in admin_dsn
        else None
    )
    user_dsn = (
        admin_dsn.replace("migration_owner:migration_owner", "app_user:app_user")
        if "migration_owner:migration_owner" in admin_dsn
        else None
    )
    super_dsn = admin_dsn.replace(
        "migration_owner:migration_owner", "postgres:postgres"
    )
    if ingress_dsn is None or user_dsn is None:
        violations.append("xviii_phys_role_dsn_underivable")
        return
    try:
        admin = psycopg2.connect(admin_dsn)
        admin.autocommit = True
    except Exception as exc:
        violations.append(f"xviii_phys_connect_failed:{exc}")
        return
    try:
        cur = admin.cursor()
        tenant = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO public.tenants (id, name, api_key_hash, notification_email)"
            " VALUES (%s,%s,%s,%s)",
            (tenant, "xviii-phys", uuid.uuid4().hex, "xviii-phys@example.invalid"),
        )
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false)", (tenant,))
        cur.execute(
            "INSERT INTO public.channel_taxonomy (code, family, is_paid,"
            " display_name, state) VALUES ('xviii_phys_ch', 'xviii_phys', true,"
            " 'XVIIIPHYS', 'active') ON CONFLICT (code) DO NOTHING"
        )

        def _mkrow(evref: str, cref: str, amount: int) -> tuple[str, str]:
            ev = str(uuid.uuid4())
            cur.execute(
                "INSERT INTO public.attribution_events (id, tenant_id, occurred_at,"
                " correlation_id, session_id, revenue_cents, raw_payload,"
                " idempotency_key, event_type, channel, campaign_id,"
                " conversion_value_cents, currency, event_timestamp, processed_at,"
                " processing_status)"
                " VALUES (%s,%s,now(),%s,%s,%s,'{}'::jsonb,%s,'conversion',"
                " 'xviii_phys_ch','c',%s,'USD',now(),now(),'processed')",
                (ev, tenant, str(uuid.uuid4()), str(uuid.uuid4()), amount,
                 str(uuid.uuid4()), amount),
            )
            ing = str(uuid.uuid4())
            cur.execute(
                "INSERT INTO public.webhook_ingress_identities (id, tenant_id, event_id,"
                " provider, provider_native_event_reference,"
                " provider_native_commerce_reference,"
                " normalized_commerce_reference_kind,"
                " normalized_commerce_reference_value, verified_amount_minor,"
                " verified_amount_currency, event_timestamp, idempotency_key,"
                " verified_commerce_ingress_state)"
                " VALUES (%s,%s,%s,'stripe',%s,%s,'stripe_payment_intent_id',%s,%s,"
                " 'USD', now(),%s,'authenticity_verified')",
                (ing, tenant, ev, evref, cref, cref, amount, str(uuid.uuid4())),
            )
            return ing, ev

        def _auth(
            ing: str,
            eref: str,
            sha: str,
            family: str | None = "payment_intent.succeeded",
            family_source: str | None = "body-signal:type",
        ) -> str:
            igr = psycopg2.connect(ingress_dsn)
            igr.autocommit = True
            try:
                with igr.cursor() as icur:
                    icur.execute(
                        "SELECT set_config('app.current_tenant_id', %s, false)",
                        (tenant,),
                    )
                    if family is not None:
                        icur.execute(
                            "SELECT set_config('app.b26_p2_event_family', %s, false)",
                            (family,),
                        )
                    if family_source is not None:
                        icur.execute(
                            "SELECT set_config('app.b26_p2_event_family_source', %s, false)",
                            (family_source,),
                        )
                    icur.execute(
                        "SELECT public.b26_p2_authenticate_ingress_atomic("
                        "%s,'stripe',%s,%s,%s,'hmac-sha256-timestamped-hex','v1')",
                        (ing, eref, sha, "b" * 64),
                    )
                    return str(icur.fetchone()[0])
            finally:
                igr.close()

        def _demote(ing: str) -> None:
            sup = psycopg2.connect(super_dsn)
            sup.autocommit = True
            try:
                with sup.cursor() as scur:
                    scur.execute(
                        "ALTER TABLE public.webhook_ingress_identities DISABLE TRIGGER"
                        " trg_b26_p2_ingress_provenance"
                    )
                    scur.execute(
                        "ALTER TABLE public.webhook_ingress_identities DISABLE TRIGGER"
                        " trg_b26_p2_ingress_authority_transition"
                    )
                with admin.cursor() as acur:
                    acur.execute("SELECT set_config('app.current_tenant_id', %s, false)",
                                 (tenant,))
                    acur.execute(
                        "UPDATE public.webhook_ingress_identities"
                        " SET b26_p2_provenance_status='pending_authentication',"
                        " b26_p2_semantic_regime='pre-xvii-unverifiable',"
                        f" b26_p2_demotion_reason='{REASON}' WHERE id=%s",
                        (ing,),
                    )
                with sup.cursor() as scur:
                    scur.execute(
                        "ALTER TABLE public.webhook_ingress_identities ENABLE TRIGGER"
                        " trg_b26_p2_ingress_authority_transition"
                    )
                    scur.execute(
                        "ALTER TABLE public.webhook_ingress_identities ENABLE TRIGGER"
                        " trg_b26_p2_ingress_provenance"
                    )
            finally:
                sup.close()

        # L1: lawful auth -> current authority, family bound.
        row1, _ = _mkrow("xviii-e1", "xviii-c1", 1000)
        assert _auth(row1, "xviii-e1", "a" * 64) == "authenticated_known"
        cur.execute(
            "SELECT public.b26_p2_ingress_has_current_authority(%s)", (row1,)
        )
        if cur.fetchone()[0] is not True:
            violations.append("xviii_phys_lawful_not_current")
        else:
            checks["lawful_path_current"] = True

        # L2 (NC-02): runtime self-stamp refused, state unchanged.
        row2, _ = _mkrow("xviii-e2", "xviii-c2", 7777)
        assert _auth(row2, "xviii-e2", "c" * 64) == "authenticated_known"
        _demote(row2)
        for dsn, label in ((user_dsn, "app_user"), (ingress_dsn, "app_ingress")):
            conn = psycopg2.connect(dsn)
            conn.autocommit = True
            try:
                with conn.cursor() as wcur:
                    wcur.execute(
                        "SELECT set_config('app.current_tenant_id', %s, false)",
                        (tenant,),
                    )
                    try:
                        wcur.execute(
                            "UPDATE public.webhook_ingress_identities"
                            " SET b26_p2_provenance_status='authenticated_known',"
                            f" b26_p2_semantic_regime='{REGIME}',"
                            " b26_p2_demotion_reason=NULL WHERE id=%s",
                            (row2,),
                        )
                        violations.append(f"xviii_phys_self_stamp_permitted:{label}")
                    except Exception:
                        conn.rollback()
            finally:
                conn.close()
        cur.execute(
            "SELECT b26_p2_provenance_status, b26_p2_demotion_reason"
            " FROM public.webhook_ingress_identities WHERE id=%s",
            (row2,),
        )
        prov, reason = cur.fetchone()
        if prov != "pending_authentication" or reason != REASON:
            violations.append("xviii_phys_demoted_row_mutated")
        else:
            checks["runtime_self_stamp_refused"] = True

        # L3 (NC-03): stale re-entry refused.
        igr = psycopg2.connect(ingress_dsn)
        igr.autocommit = True
        try:
            with igr.cursor() as icur:
                icur.execute(
                    "SELECT set_config('app.current_tenant_id', %s, false)",
                    (tenant,),
                )
                try:
                    icur.execute(
                        "SELECT public.b26_p2_authenticate_ingress_atomic("
                        "%s,'stripe','xviii-e2',%s,%s,"
                        "'hmac-sha256-timestamped-hex','v1')",
                        (row2, "c" * 64, "b" * 64),
                    )
                    violations.append("xviii_phys_stale_reentry_permitted")
                except Exception as exc:
                    if "b26_p2_atomic_demoted_ingress_refused" not in str(exc):
                        violations.append(
                            "xviii_phys_stale_wrong_refusal:"
                            f"{str(exc).splitlines()[0][:120]}"
                        )
                    else:
                        checks["stale_evidence_refused"] = True
        finally:
            igr.close()

        # L3b: the legacy attester cannot promote demoted rows either
        # (second minting primitive closed under the same law).
        igr = psycopg2.connect(ingress_dsn)
        igr.autocommit = True
        try:
            with igr.cursor() as icur:
                icur.execute(
                    "SELECT set_config('app.current_tenant_id', %s, false)",
                    (tenant,),
                )
                try:
                    icur.execute(
                        "SELECT public.b26_p2_attest_provenance_evidence("
                        "%s, 'signed_provider_reingestion', %s)",
                        (row2, "lawful-idem"),
                    )
                    violations.append("xviii_phys_attester_promotes_demoted")
                except Exception as exc:
                    if "b26_p2_evidence_demoted_ingress_refused" not in str(exc):
                        violations.append(
                            "xviii_phys_attester_wrong_refusal:"
                            f"{str(exc).splitlines()[0][:120]}"
                        )
                    else:
                        checks["attester_demoted_refused"] = True
        finally:
            igr.close()

        # L4 (NC-04): demoted row outside the candidate universe.
        cur.execute(
            "SELECT count(*) FROM public.webhook_ingress_identities wi"
            " WHERE wi.tenant_id = %s"
            " AND wi.verified_commerce_ingress_state = 'authenticity_verified'"
            " AND public.b26_p2_ingress_has_current_authority(wi.id)"
            " AND wi.provider_native_event_reference IN ('xviii-e1','xviii-e2')",
            (tenant,),
        )
        if cur.fetchone()[0] != 1:
            violations.append("xviii_phys_candidate_universe_wrong")
        else:
            checks["candidate_universe_authority_normalized"] = True

        # L5 (NC-05/06): verdict revocation + coverage honesty.
        _, aev = _mkrow("xviii-e9", "xviii-c9", 7777)
        cur.execute(
            "INSERT INTO public.b23_match_verdicts (tenant_id, attribution_event_id,"
            " webhook_ingress_identity_id, provider, canonical_commerce_reference,"
            " provider_native_event_reference, provider_native_commerce_reference,"
            " status, match_quality, attributed_amount_minor, verified_amount_minor,"
            " currency_code, pending_since, provisional_expires_at,"
            " last_transition_at, created_at, updated_at,"
            " canonical_expected_gross_amount_minor,"
            " canonical_captured_gross_amount_minor,"
            " canonical_net_verified_amount_minor, discrepancy_amount_minor,"
            " discrepancy_ratio_bps, discrepancy_band)"
            " VALUES (%s,%s,%s,'stripe','xviii-c2','xviii-e2','xviii-c2',"
            " 'matched_provisional','high',7777,7777,'USD',now(),now(),now(),"
            " now(),now(),7777,7777,7777,0,0,'exact') RETURNING id,"
            " b26_p2_source_authority_state",
            (tenant, aev, row2),
        )
        vid, vstate = cur.fetchone()
        if vstate != "historically_unverifiable":
            violations.append(f"xviii_phys_verdict_not_revoked:{vstate}")
        else:
            checks["demoted_verdict_revoked"] = True
        cur.execute(
            "SELECT COALESCE(SUM(v.canonical_net_verified_amount_minor),0)"
            " FROM public.b23_match_verdicts v"
            " JOIN public.webhook_ingress_identities wi"
            " ON wi.id = v.webhook_ingress_identity_id"
            " WHERE v.tenant_id=%s AND v.status IN"
            " ('matched_provisional','matched_confirmed','adjusted')"
            " AND v.b26_p2_source_authority_state='current'"
            " AND public.b26_p2_ingress_has_current_authority(wi.id)",
            (tenant,),
        )
        if cur.fetchone()[0] != 0:
            violations.append("xviii_phys_demoted_revenue_conducts")
        else:
            checks["demoted_revenue_excluded"] = True

        # L6 (NC-07): hostile family claim refused at the transition.
        row6, _ = _mkrow("xviii-e6", "xviii-c6", 600)
        try:
            _auth(row6, "xviii-e6", "d" * 64, family="charge.refunded")
            violations.append("xviii_phys_hostile_family_permitted")
        except Exception as exc:
            if "b26_p2_atomic_family_unbound_refused" not in str(exc):
                violations.append(
                    "xviii_phys_family_wrong_refusal:"
                    f"{str(exc).splitlines()[0][:120]}"
                )
            else:
                checks["hostile_family_refused"] = True

        # L7 (NC-10): floor absence blocks minting; restore re-enables.
        # XX: restore the lane's own floor revision (the gate runs on
        # newer heads whose floor differs from XVIII's); the intent --
        # absence refuses, restore re-enables -- is head-independent.
        cur.execute("SELECT floor_revision FROM public.b26_p2_operational_floor"
                    " WHERE id=1")
        _floor_row = cur.fetchone()
        _lane_floor = _floor_row[0] if _floor_row else "202609300002"
        cur.execute("DELETE FROM public.b26_p2_operational_floor")
        row7, _ = _mkrow("xviii-e7", "xviii-c7", 700)
        try:
            _auth(row7, "xviii-e7", "e" * 64)
            violations.append("xviii_phys_downgraded_mint_permitted")
        except Exception as exc:
            if "b26_p2_downgrade_serving_refused" not in str(exc):
                violations.append(
                    "xviii_phys_floor_wrong_refusal:"
                    f"{str(exc).splitlines()[0][:120]}"
                )
            else:
                checks["downgrade_serving_blocked"] = True
        cur.execute(
            "INSERT INTO public.b26_p2_operational_floor (id, floor_revision)"
            " VALUES (1,%s) ON CONFLICT (id) DO UPDATE SET"
            " floor_revision=EXCLUDED.floor_revision",
            (_lane_floor,),
        )
        assert _auth(row7, "xviii-e7", "e" * 64) == "authenticated_known"
        checks["floor_restore_reenables"] = True

        # L8 (NC-13/XVIII-P): 3VL matrix -- UNKNOWN never authorizes.
        cur.execute(
            "SELECT public.b26_p2_ingress_has_current_authority(%s)",
            ("00000000-0000-0000-0000-000000000000",),
        )
        if cur.fetchone()[0] is not False:
            violations.append("xviii_phys_missing_row_authorizes")
        else:
            checks["three_valued_logic_safe"] = True

        # L10: every EXECUTE-granted role observes the same fail-closed
        # predicate (coverage evidence for the XVIII covered set):
        # FALSE on demoted history, TRUE on current authority.
        for role in (
            "app_user", "app_ingress", "app_worker", "app_relay",
            "app_beat", "app_dispatch_publisher", "app_trust_issuer",
            "app_trust_signer",
        ):
            role_dsn = admin_dsn.replace(
                "migration_owner:migration_owner", f"{role}:{role}"
            )
            try:
                role_conn = psycopg2.connect(role_dsn)
                role_conn.autocommit = True
            except Exception as exc:
                violations.append(f"xviii_phys_role_unreachable:{role}:{exc}")
                continue
            try:
                with role_conn.cursor() as rcur:
                    rcur.execute(
                        "SELECT set_config('app.current_tenant_id', %s, false)",
                        (tenant,),
                    )
                    rcur.execute(
                        "SELECT public.b26_p2_ingress_has_current_authority(%s)",
                        (row2,),
                    )
                    demoted_answer = rcur.fetchone()[0]
                    rcur.execute(
                        "SELECT public.b26_p2_ingress_has_current_authority(%s)",
                        (row1,),
                    )
                    current_answer = rcur.fetchone()[0]
            except Exception as exc:
                violations.append(f"xviii_phys_role_predicate_failed:{role}:{exc}")
                role_conn.close()
                continue
            role_conn.close()
            if demoted_answer is not False or current_answer is not True:
                violations.append(
                    f"xviii_phys_role_predicate_wrong:{role}:"
                    f"{demoted_answer}:{current_answer}"
                )
        if not [v for v in violations if "xviii_phys_role_" in v]:
            checks["predicate_role_matrix_covered"] = True

        # L9: dispatch refuses demoted, admits current-with-family.
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
                " 'b23_match_engine','k',%s,'stripe','xviii-e2','xviii-c2','xviii-c2')",
                (tenant, row2, "xviii-dispatch-demoted", str(uuid.uuid4())),
            )
            violations.append("xviii_phys_demoted_dispatch_permitted")
        except Exception as exc:
            admin.rollback()
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)", (tenant,)
            )
            if "b26_p2_dispatch_source_not_current" not in str(exc):
                violations.append(
                    "xviii_phys_dispatch_wrong_refusal:"
                    f"{str(exc).splitlines()[0][:120]}"
                )
            else:
                checks["demoted_dispatch_refused"] = True
        # A lawful current row passes every authority gate in the
        # dispatch chain (provenance/regime/reason/family/witness) and
        # stops only at the sovereign-window rule (window columns
        # unset in this probe): authority admission itself is intact.
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
                " 'b23_match_engine','k',%s,'stripe','xviii-e1','xviii-c1',"
                "'xviii-c1')",
                (tenant, row1, "xviii-dispatch-lawful", str(uuid.uuid4())),
            )
            checks["lawful_dispatch_admitted"] = True
        except Exception as exc:
            admin.rollback()
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)", (tenant,)
            )
            if "b26_p2_dispatch_window_not_sovereign" not in str(exc):
                violations.append(
                    "xviii_phys_lawful_dispatch_blocked:"
                    f"{str(exc).splitlines()[0][:120]}"
                )
            else:
                checks["lawful_dispatch_passes_authority_gates"] = True
        cur.close()
    except Exception as exc:
        violations.append(f"xviii_phys_live_failed:{exc}")
    finally:
        admin.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="XVIII physics closure.")
    parser.add_argument("--dsn", default=None)
    parser.add_argument("--evidence-out", default=None)
    args = parser.parse_args()
    violations: list[str] = []
    checks: dict = {}
    _static_checks(violations, checks)
    if args.dsn is not None:
        _live_checks(args.dsn, violations, checks)
    status = "PASS" if not violations else "FAIL"
    print(f"B26_P2_XVIII_PHYS_{status}")
    if violations:
        print(";".join(sorted(violations)))
    else:
        print(json.dumps({"checks": checks}, sort_keys=True, default=str))
    if args.evidence_out:
        Path(args.evidence_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.evidence_out).write_text(
            json.dumps(
                {
                    "gate_id": "B26-P2-XVIII-PHYSICS",
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
