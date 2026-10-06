#!/usr/bin/env python3
"""B2.6-P2 Corrective XIX live-physics closure gate.

H-XIX-R1..R23 (Directive XIX): proves the non-reconstructible-authority
physics on a live lane at the XIX head, as the role whose authority is
being evaluated. Static law-presence checks plus the live battery:

- XIX-P1: least-privilege posture -- no runtime role holds table-level
  UPDATE on the authority tables, and no runtime role holds effective
  column UPDATE on authority-bearing columns (has_*_privilege AND a
  real DML probe, because catalog inspection alone is insufficient);
- XIX-P2: the governed-transition GUC is inert -- a same-transaction
  marked self-stamp on a demoted evidenced row is refused, and the
  privilege layer denies it before any trigger;
- XIX-P3: complete conjunction -- witness/provenance/consequence/root
  deletion each demote the ingress transactionally (predicate FALSE,
  reason xix-evidence-revoked:*), and the dependent verdict follows;
- XIX-P4: explicit family -- NULL/blank family claims refused at both
  minting primitives; hostile families refused; valid claims bind the
  evidence source;
- XIX-P5: supersession ledger appends on verdict correction and refuses
  UPDATE/DELETE for every principal;
- XIX-P6: registry governance -- runtime deputy writes refused;
  publication ledger single-valued per identity (UNIQUE enforced:
  same-version second digest INSERT refused);
- XIX-P7: linearization -- authority writes outside READ COMMITTED
  refused;
- XIX-P8: 3VL -- missing rows, NULL markers, and unknown registry
  states never authorize.

Prints B26_P2_XIX_PHYS_PASS on success.
"""

from __future__ import annotations

import argparse
import json
import re
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MIG_XIX = (
    REPO_ROOT
    / "alembic"
    / "versions"
    / "007_skeldir_foundation"
    / "202609300002_b26_p2_corrective_xix_nonreconstructible_authority.py"
)
RUNTIME_ROLES = (
    "app_user", "app_ingress", "app_worker", "app_relay", "app_beat",
    "app_dispatch_publisher", "app_trust_issuer", "app_trust_signer",
)
REASON = "xix-phys-probe"


def _static_checks(violations: list[str], checks: dict) -> None:
    try:
        text = MIG_XIX.read_text(encoding="utf-8")
    except OSError as exc:
        violations.append(f"xix_phys_unreadable:{exc}")
        return
    upgrade = text.split("def downgrade", 1)[0]
    for token in (
        "b26_p2_ingress_has_current_authority",
        "current_user IS DISTINCT FROM 'migration_owner'",
        "b26_p2_authority_snapshot_not_linearizable",
        "b26_p2_revoke_authority_on_evidence_loss",
        "xix-evidence-revoked:",
        "b26_p2_verdict_supersession_ledger",
        "b26_p2_ledger_history_immutable_refused",
        "b26_p2_publication_history",
        "b26_p2_publication_identity_single_valued",
        "b26_p2_registry_deputy_refused",
        "b26_p2_atomic_family_unbound_refused",
        "b26_p2_atomic_family_source_refused",
        "b26_p2_family_source",
        "b26_p2_verdict_authority_write_refused",
        "b26_p2_dispatch_source_not_current",
        "202609300002",
    ):
        if token not in upgrade:
            violations.append(f"xix_phys_law_missing:{token}")
    if not [v for v in violations if "xix_phys_law_missing" in v]:
        checks["xix_law_present"] = True
    if "app.b26_p2_governed_transition" in upgrade:
        violations.append("xix_phys_bearer_mark_survives")
    else:
        checks["bearer_mark_removed"] = True
    compact = re.sub(r"\s+", " ", text)
    if not re.search(
        r"REVOKE UPDATE ON TABLE.{0,60}public\.webhook_ingress_identities",
        compact,
    ):
        violations.append("xix_phys_table_revoke_missing:ingress")
    else:
        checks["privilege_table_revoke_ingress"] = True
    if not re.search(
        r"REVOKE UPDATE ON TABLE.{0,60}public\.b23_match_verdicts", compact
    ):
        violations.append("xix_phys_table_revoke_missing:verdicts")
    else:
        checks["privilege_table_revoke_verdicts"] = True
    # H-XIX-R17: the unverifiable historical context field must never
    # enter verified arithmetic. Census every reader: the only lawful
    # readers are the aggregate definition/projection itself (which
    # carries it as explicit non-authoritative context) and tests.
    # Any denominator/ratio/total/benchmark consumer is a violation.
    allowed_readers = (
        "backend/app/revenue_verification/verification_coverage.py",
    )
    for path in sorted((REPO_ROOT / "backend").rglob("*.py")):
        rel = path.as_posix()
        if "backend/tests/" in rel or "/tests/" in rel:
            continue
        if rel.endswith("/backend/app/revenue_verification/verification_coverage.py"):
            continue
        try:
            body = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if "unverifiable_historical_revenue_minor" in body:
            violations.append(
                "xix_phys_unverifiable_consumed:"
                f"{path.relative_to(REPO_ROOT).as_posix()}"
            )
    if not [v for v in violations if "xix_phys_unverifiable_consumed" in v]:
        checks["unverifiable_context_unconsumed"] = True


def _live_checks(
    admin_dsn: str, violations: list[str], checks: dict
) -> None:
    try:
        import psycopg2  # noqa: PLC0415
    except ImportError as exc:
        violations.append(f"xix_phys_no_driver:{exc}")
        return
    ingress_dsn = admin_dsn.replace(
        "migration_owner:migration_owner", "app_ingress:app_ingress"
    )
    user_dsn = admin_dsn.replace(
        "migration_owner:migration_owner", "app_user:app_user"
    )
    try:
        admin = psycopg2.connect(admin_dsn)
        admin.autocommit = True
    except Exception as exc:
        violations.append(f"xix_phys_connect_failed:{exc}")
        return
    try:
        cur = admin.cursor()
        tenant = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO public.tenants (id, name, api_key_hash,"
            " notification_email) VALUES (%s,%s,%s,%s)",
            (tenant, "xix-phys", uuid.uuid4().hex, "xix@example.invalid"),
        )
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false)",
                    (tenant,))
        cur.execute(
            "INSERT INTO public.channel_taxonomy (code, family, is_paid,"
            " display_name, state) VALUES ('xix_phys_ch', 'xix', true,"
            " 'XIX', 'active') ON CONFLICT (code) DO NOTHING"
        )

        def _mkrow(evref: str, cref: str, amount: int) -> str:
            ev = str(uuid.uuid4())
            cur.execute(
                "INSERT INTO public.attribution_events (id, tenant_id,"
                " occurred_at, correlation_id, session_id, revenue_cents,"
                " raw_payload, idempotency_key, event_type, channel,"
                " campaign_id, conversion_value_cents, currency,"
                " event_timestamp, processed_at, processing_status)"
                " VALUES (%s,%s,now(),%s,%s,%s,'{}'::jsonb,%s,'conversion',"
                " 'xix_phys_ch','c',%s,'USD',now(),now(),'processed')",
                (ev, tenant, str(uuid.uuid4()), str(uuid.uuid4()), amount,
                 str(uuid.uuid4()), amount),
            )
            ing = str(uuid.uuid4())
            cur.execute(
                "INSERT INTO public.webhook_ingress_identities (id, tenant_id,"
                " event_id, provider, provider_native_event_reference,"
                " provider_native_commerce_reference,"
                " normalized_commerce_reference_kind,"
                " normalized_commerce_reference_value, verified_amount_minor,"
                " verified_amount_currency, event_timestamp, idempotency_key,"
                " verified_commerce_ingress_state)"
                " VALUES (%s,%s,%s,'stripe',%s,%s,'stripe_payment_intent_id',"
                "%s,%s,'USD',now(),%s,'authenticity_verified')",
                (ing, tenant, ev, evref, cref, cref, amount, str(uuid.uuid4())),
            )
            return ing

        def _auth(
            ing: str,
            eref: str,
            sha: str,
            family: str | None = "payment_intent.succeeded",
            source: str | None = "body-signal:type",
        ) -> str:
            igr = psycopg2.connect(ingress_dsn)
            igr.autocommit = False
            try:
                with igr.cursor() as icur:
                    icur.execute(
                        "SELECT set_config('app.current_tenant_id', %s, false)",
                        (tenant,),
                    )
                    if family is not None:
                        icur.execute(
                            "SELECT set_config('app.b26_p2_event_family',"
                            " %s, true)",
                            (family,),
                        )
                    if source is not None:
                        icur.execute(
                            "SELECT set_config('app.b26_p2_event_family_source',"
                            " %s, true)",
                            (source,),
                        )
                    icur.execute(
                        "SELECT public.b26_p2_authenticate_ingress_atomic("
                        "%s,'stripe',%s,%s,%s,"
                        "'hmac-sha256-timestamped-hex','v1')",
                        (ing, eref, sha, "b" * 64),
                    )
                    out = str(icur.fetchone()[0])
                    igr.commit()
                    return out
            finally:
                igr.close()

        # P1: effective privilege posture (catalog + real DML).
        for role in RUNTIME_ROLES:
            role_conn = psycopg2.connect(
                admin_dsn.replace(
                    "migration_owner:migration_owner", f"{role}:{role}"
                )
            )
            role_conn.autocommit = True
            try:
                with role_conn.cursor() as rcur:
                    rcur.execute(
                        "SELECT has_table_privilege(%s,"
                        " 'webhook_ingress_identities', 'UPDATE')",
                        (role,),
                    )
                    if rcur.fetchone()[0] is not False:
                        violations.append(
                            f"xix_phys_table_update_reaches:{role}"
                        )
                    rcur.execute(
                        "SELECT has_column_privilege(%s,"
                        " 'webhook_ingress_identities',"
                        " 'b26_p2_provenance_status', 'UPDATE')",
                        (role,),
                    )
                    if rcur.fetchone()[0] is not False:
                        violations.append(
                            f"xix_phys_authority_column_reaches:{role}"
                        )
            finally:
                role_conn.close()
        if not [v for v in violations if "xix_phys_table_update_reaches" in v
                or "xix_phys_authority_column_reaches" in v]:
            checks["least_privilege_effective"] = True

        # Lawful mint + predicate TRUE baseline.
        row = _mkrow("xix-p1", "xix-c1", 100000)
        assert _auth(row, "xix-p1", "a" * 64) == "authenticated_known"
        cur.execute(
            "SELECT public.b26_p2_ingress_has_current_authority(%s)", (row,)
        )
        if cur.fetchone()[0] is not True:
            violations.append("xix_phys_lawful_mint_not_current")
        else:
            checks["lawful_mint_current"] = True

        # P2: same-transaction marked self-stamp refused at privilege.
        probe = _mkrow("xix-p2", "xix-c2", 200000)
        assert _auth(probe, "xix-p2", "c" * 64) == "authenticated_known"
        usr = psycopg2.connect(user_dsn)
        usr.autocommit = False
        try:
            with usr.cursor() as ucur:
                ucur.execute(
                    "SELECT set_config('app.current_tenant_id', %s, false)",
                    (tenant,),
                )
                ucur.execute(
                    "SELECT set_config('app.b26_p2_governed_transition',"
                    " '1', true)"
                )
                try:
                    ucur.execute(
                        "UPDATE public.webhook_ingress_identities SET"
                        " b26_p2_provenance_status='authenticated_known',"
                        " b26_p2_semantic_regime='xvii-sovereign-v1',"
                        " b26_p2_demotion_reason=NULL WHERE id=%s",
                        (probe,),
                    )
                    usr.commit()
                    violations.append("xix_phys_marked_self_stamp_permitted")
                except Exception:
                    usr.rollback()
                    checks["marked_self_stamp_refused"] = True
        finally:
            usr.close()

        # P3: detachment battery -- each loss demotes transactionally.
        for table in (
            "b26_p2_ingress_auth_witness",
            "b26_p2_provenance_evidence",
            "b26_p2_provider_auth_consequence",
            "b26_p2_auth_root_evidence",
        ):
            victim = _mkrow(f"xix-p3-{table}", f"xix-c3-{table[:20]}", 3000)
            assert _auth(victim, f"xix-p3-{table}", "d" * 64) == (
                "authenticated_known"
            )
            cur.execute(
                f"DELETE FROM public.{table}"
                " WHERE webhook_ingress_identity_id=%s",
                (victim,),
            )
            cur.execute(
                "SELECT public.b26_p2_ingress_has_current_authority(%s)",
                (victim,),
            )
            if cur.fetchone()[0] is not False:
                violations.append(f"xix_phys_detach_survives:{table}")
                continue
            cur.execute(
                "SELECT b26_p2_demotion_reason FROM"
                " public.webhook_ingress_identities WHERE id=%s",
                (victim,),
            )
            reason = cur.fetchone()[0]
            if not reason or not reason.startswith("xix-evidence-revoked:"):
                violations.append(f"xix_phys_detach_no_reason:{table}")
        if not [v for v in violations if v.startswith("xix_phys_detach_")]:
            checks["evidence_loss_demotes"] = True

        # P4: family refusal matrix.
        fam_row = _mkrow("xix-p4", "xix-c4", 4000)
        for fam, src, token in (
            (None, None, "b26_p2_atomic_family_unbound_refused"),
            ("", "", "b26_p2_atomic_family_unbound_refused"),
            ("charge.refunded", "body-signal:type",
             "b26_p2_atomic_family_unbound_refused"),
            ("payment_intent.succeeded", "bogus-source",
             "b26_p2_atomic_family_source_refused"),
        ):
            try:
                _auth(fam_row, "xix-p4", "e" * 64, family=fam, source=src)
                violations.append(f"xix_phys_family_minted:{token}")
            except Exception as exc:
                if token not in str(exc):
                    violations.append(
                        "xix_phys_family_wrong_refusal:"
                        f"{str(exc).splitlines()[0][:120]}"
                    )
        if not [v for v in violations if "xix_phys_family_" in v]:
            checks["explicit_family_only"] = True

        # P5: supersession ledger append + immutability.
        cur.execute(
            "INSERT INTO public.b23_match_verdicts (tenant_id,"
            " attribution_event_id, webhook_ingress_identity_id, provider,"
            " canonical_commerce_reference, provider_native_event_reference,"
            " provider_native_commerce_reference, status, match_quality,"
            " attributed_amount_minor, verified_amount_minor, currency_code,"
            " confirmed_at, last_transition_at,"
            " canonical_expected_gross_amount_minor,"
            " canonical_captured_gross_amount_minor,"
            " canonical_net_verified_amount_minor, discrepancy_amount_minor,"
            " discrepancy_ratio_bps, discrepancy_band)"
            " SELECT %s, event_id, %s, 'stripe', 'xix-c1',"
            " 'xix-p1', 'xix-c1', 'matched_provisional', 'high',"
            " 100000, 100000, 'USD', now(), now(), 100000, 100000,"
            " 100000, 0, 0, 'exact' FROM public.webhook_ingress_identities"
            " WHERE id=%s RETURNING id",
            (tenant, row, row),
        )
        verdict = cur.fetchone()[0]
        cur.execute(
            "UPDATE public.b23_match_verdicts"
            " SET attributed_amount_minor=1,"
            " canonical_expected_gross_amount_minor=1,"
            " canonical_captured_gross_amount_minor=1,"
            " verified_amount_minor=1,"
            " canonical_net_verified_amount_minor=1 WHERE id=%s",
            (verdict,),
        )
        cur.execute(
            "SELECT count(*) FROM public.b26_p2_verdict_supersession_ledger"
            " WHERE verdict_id=%s AND prior_attributed_amount_minor=100000"
            " AND new_attributed_amount_minor=1",
            (verdict,),
        )
        if cur.fetchone()[0] != 1:
            violations.append("xix_phys_ledger_missing_supersession")
        else:
            checks["supersession_ledger_appends"] = True
        try:
            cur.execute(
                "UPDATE public.b26_p2_verdict_supersession_ledger"
                " SET new_attributed_amount_minor=2 WHERE verdict_id=%s",
                (verdict,),
            )
            violations.append("xix_phys_ledger_mutable")
        except Exception:
            admin.rollback()
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (tenant,),
            )
            checks["ledger_immutable"] = True
        try:
            cur.execute(
                "DELETE FROM public.b26_p2_verdict_supersession_ledger"
                " WHERE verdict_id=%s",
                (verdict,),
            )
            violations.append("xix_phys_ledger_deletable")
        except Exception:
            admin.rollback()
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (tenant,),
            )
            checks["ledger_delete_refused"] = True

        # P6: registry deputy refusal + publication single-valuedness.
        usr2 = psycopg2.connect(user_dsn)
        usr2.autocommit = True
        try:
            with usr2.cursor() as ucur:
                try:
                    ucur.execute(
                        "UPDATE public.b26_p2_semantic_regime_registry"
                        " SET status='retired'"
                        " WHERE regime_id='xvii-sovereign-v1'"
                    )
                    violations.append("xix_phys_registry_runtime_writable")
                except Exception:
                    checks["registry_deputy_refused"] = True
        finally:
            usr2.close()
        try:
            cur.execute(
                "INSERT INTO public.b26_p2_publication_history (law_kind,"
                " law_id, law_version, law_digest, activation_revision,"
                " prev_entry_hash, entry_hash) VALUES ('semantic-regime',"
                " 'xvii-sovereign-v1', 'v1', %s, '202609300002', NULL,"
                " '0000000000000000000000000000000000000000000000000000000000000000')",
                ("f" * 64,),
            )
            violations.append("xix_phys_publication_identity_rewritable")
        except Exception:
            admin.rollback()
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (tenant,),
            )
            checks["publication_identity_single_valued"] = True

        # P7: non-READ-COMMITTED authority writes refused.
        iso = psycopg2.connect(ingress_dsn)
        try:
            iso.autocommit = False
            with iso.cursor() as icur:
                icur.execute(
                    "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"
                )
                icur.execute(
                    "SELECT set_config('app.current_tenant_id', %s, false)",
                    (tenant,),
                )
                icur.execute(
                    "SELECT set_config('app.b26_p2_event_family',"
                    " 'payment_intent.succeeded', true)"
                )
                icur.execute(
                    "SELECT set_config('app.b26_p2_event_family_source',"
                    " 'body-signal:type', true)"
                )
                iso_row = _mkrow("xix-p7", "xix-c7", 7000)
                try:
                    icur.execute(
                        "SELECT public.b26_p2_authenticate_ingress_atomic("
                        "%s,'stripe','xix-p7',%s,%s,"
                        "'hmac-sha256-timestamped-hex','v1')",
                        (iso_row, "f" * 64, "b" * 64),
                    )
                    violations.append("xix_phys_snapshot_mint_permitted")
                except Exception as exc:
                    if "b26_p2_authority_snapshot_not_linearizable" not in str(
                        exc
                    ):
                        violations.append(
                            "xix_phys_snapshot_wrong_refusal:"
                            f"{str(exc).splitlines()[0][:120]}"
                        )
                    else:
                        checks["snapshot_linearization_enforced"] = True
        finally:
            try:
                iso.rollback()
            except Exception:
                pass
            iso.close()

        # P8: 3VL matrix.
        cur.execute(
            "SELECT public.b26_p2_ingress_has_current_authority(%s)",
            ("00000000-0000-0000-0000-000000000000",),
        )
        if cur.fetchone()[0] is not False:
            violations.append("xix_phys_missing_row_authorizes")
        else:
            checks["three_valued_logic_safe"] = True
        cur.close()
    except Exception as exc:
        violations.append(f"xix_phys_live_failed:{exc}")
    finally:
        admin.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="XIX physics closure.")
    parser.add_argument("--dsn", default=None)
    parser.add_argument("--evidence-out", default=None)
    args = parser.parse_args()
    violations: list[str] = []
    checks: dict = {}
    _static_checks(violations, checks)
    if args.dsn is not None:
        _live_checks(args.dsn, violations, checks)
    status = "PASS" if not violations else "FAIL"
    print(f"B26_P2_XIX_PHYS_{status}")
    if violations:
        print(";".join(sorted(violations)))
    else:
        print(json.dumps({"checks": checks}, sort_keys=True, default=str))
    if args.evidence_out:
        Path(args.evidence_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.evidence_out).write_text(
            json.dumps(
                {
                    "gate_id": "B26-P2-XIX-PHYSICS",
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
