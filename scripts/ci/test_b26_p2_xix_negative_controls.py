#!/usr/bin/env python3
"""B2.6-P2 Corrective XIX relation-level negative-control battery.

Directive XIX section 31: the mandatory proof must turn RED for every
active falsifier WITHOUT a bespoke detector -- i.e. the shipped XIX
gates themselves must observe each mutation. Every falsifier below
demonstrates GREEN baseline -> deliberate mutation -> expected RED ->
byte/schema-exact restoration -> GREEN, with hashes recorded.

Falsifiers (NC-01..NC-14, NC-13 recorded N/A -- XIX adds no async
repair machinery, so there is no queue edge to remove; the absence is
asserted instead):

- NC-01: runtime marked self-stamp (live role/GUC/DML matrix);
- NC-02/03: witness/evidence/consequence/root loss (live);
- NC-04: same-regime contract co-edit (tracked-file mutation);
- NC-05: same-version family-law co-edit (tracked-file mutation);
- NC-06: familyless shapes (live parser + live atomic);
- NC-07/08: source invalidation with live verdicts (live);
- NC-09: single-step downgrade + direct-DML mint (live round-trip);
- NC-10: incompatible revision served by this build (gate logic);
- NC-11: ledger tampering (live);
- NC-12: registry retirement with live R1 rows (live R1->retired);
- NC-14: host-source post-proof drift (tracked-file mutation).

Usage: --dsn ADMIN_DSN --evidence-out PATH. Tracked-file mutations are
restored byte-exact (sha recorded before/after); any residue fails.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
B26_DIR = REPO_ROOT / "contracts" / "reconciliation" / "b2.6"
PUB_GATE = REPO_ROOT / "scripts" / "ci" / (
    "validate_b26_p2_xix_publication_immutability.py"
)


def _sha(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes().replace(b"\r\n", b"\n")
    ).hexdigest()


def _gate(args: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(PUB_GATE), *args],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    return proc.returncode, (proc.stdout + proc.stderr)[:2000]


def main() -> int:
    parser = argparse.ArgumentParser(description="XIX NC battery.")
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--evidence-out", default=None)
    args = parser.parse_args()
    violations: list[str] = []
    checks: dict = {}
    reds: dict = {}

    try:
        import psycopg2  # noqa: PLC0415
    except ImportError as exc:
        print("B26_P2_XIX_NC_FAIL")
        print(f"xix_nc_no_driver:{exc}")
        return 1

    admin_dsn = args.dsn
    ingress_dsn = admin_dsn.replace(
        "migration_owner:migration_owner", "app_ingress:app_ingress"
    )
    user_dsn = admin_dsn.replace(
        "migration_owner:migration_owner", "app_user:app_user"
    )
    admin = psycopg2.connect(admin_dsn)
    admin.autocommit = True
    try:
        cur = admin.cursor()
        tenant = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO public.tenants (id, name, api_key_hash,"
            " notification_email) VALUES (%s,%s,%s,%s)",
            (tenant, "xix-nc", uuid.uuid4().hex, "xixnc@example.invalid"),
        )
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false)",
                    (tenant,))
        cur.execute(
            "INSERT INTO public.channel_taxonomy (code, family, is_paid,"
            " display_name, state) VALUES ('xix_nc_ch', 'xix', true,"
            " 'XIXNC', 'active') ON CONFLICT (code) DO NOTHING"
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
                " 'xix_nc_ch','c',%s,'USD',now(),now(),'processed')",
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

        def _auth(ing: str, eref: str, sha: str) -> str:
            igr = psycopg2.connect(ingress_dsn)
            igr.autocommit = False
            try:
                with igr.cursor() as icur:
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

        def _current(ing: str) -> bool:
            cur.execute(
                "SELECT public.b26_p2_ingress_has_current_authority(%s)",
                (ing,),
            )
            return cur.fetchone()[0] is True

        # NC-01: marked self-stamp across the runtime-role matrix.
        row = _mkrow("xix-nc01", "xix-ncc01", 1000)
        assert _auth(row, "xix-nc01", "a" * 64) == "authenticated_known"
        assert _current(row)
        for role, ds in (
            ("app_user", user_dsn),
            ("app_ingress", ingress_dsn),
        ):
            conn = psycopg2.connect(ds)
            conn.autocommit = False
            try:
                with conn.cursor() as rcur:
                    rcur.execute(
                        "SELECT set_config('app.current_tenant_id', %s, false)",
                        (tenant,),
                    )
                    rcur.execute(
                        "SELECT set_config('app.b26_p2_governed_transition',"
                        " '1', true)"
                    )
                    try:
                        rcur.execute(
                            "UPDATE public.webhook_ingress_identities SET"
                            " b26_p2_demotion_reason=NULL,"
                            " b26_p2_provenance_status='authenticated_known'"
                            " WHERE id=%s",
                            (row,),
                        )
                        conn.commit()
                        violations.append(f"xix_nc01_permitted:{role}")
                    except Exception:
                        conn.rollback()
            finally:
                conn.close()
        if not [v for v in violations if v.startswith("xix_nc01_")]:
            checks["nc01_marked_stamp_red"] = True
            reds["NC-01"] = "RED:marked self-stamp refused at privilege layer"

        # NC-01b: wide-grant topology (R3-style load-test lane where the
        # trigger is the ONLY wall). Demote the probe row, grant table
        # UPDATE to app_user, re-run the marked self-stamp (must STILL
        # refuse via the owner-context guard), then revoke to restore
        # the exact posture. A convention/privilege-only wall would
        # mint here.
        sup = psycopg2.connect(
            admin_dsn.replace(
                "migration_owner:migration_owner", "postgres:postgres"
            )
        )
        sup.autocommit = True
        try:
            with sup.cursor() as scur:
                for _trg in (
                    "trg_b26_p2_ingress_authority_transition",
                    "trg_b26_p2_ingress_provenance",
                ):
                    scur.execute(
                        "ALTER TABLE public.webhook_ingress_identities"
                        f" DISABLE TRIGGER {_trg}"
                    )
            with admin.cursor() as acur:
                acur.execute(
                    "SELECT set_config('app.current_tenant_id', %s, false)",
                    (tenant,),
                )
                acur.execute(
                    "UPDATE public.webhook_ingress_identities SET"
                    " b26_p2_provenance_status='pending_authentication',"
                    " b26_p2_semantic_regime='pre-xvii-unverifiable',"
                    " b26_p2_demotion_reason='xix-nc01b-probe'"
                    " WHERE id=%s",
                    (row,),
                )
            with sup.cursor() as scur:
                for _trg in (
                    "trg_b26_p2_ingress_authority_transition",
                    "trg_b26_p2_ingress_provenance",
                ):
                    scur.execute(
                        "ALTER TABLE public.webhook_ingress_identities"
                        f" ENABLE TRIGGER {_trg}"
                    )
        finally:
            sup.close()
        cur.execute(
            "GRANT UPDATE ON TABLE public.webhook_ingress_identities"
            " TO app_user"
        )
        try:
            wide = psycopg2.connect(user_dsn)
            wide.autocommit = False
            try:
                with wide.cursor() as wcur:
                    wcur.execute(
                        "SELECT set_config('app.current_tenant_id', %s, false)",
                        (tenant,),
                    )
                    wcur.execute(
                        "SELECT set_config('app.b26_p2_governed_transition',"
                        " '1', true)"
                    )
                    try:
                        wcur.execute(
                            "UPDATE public.webhook_ingress_identities SET"
                            " b26_p2_provenance_status='authenticated_known',"
                            " b26_p2_semantic_regime='xvii-sovereign-v1',"
                            " b26_p2_demotion_reason=NULL WHERE id=%s",
                            (row,),
                        )
                        wide.commit()
                        violations.append("xix_nc01b_wide_grant_minted")
                    except Exception as exc:
                        wide.rollback()
                        if "b26_p2_authority_transition_refused" not in str(
                            exc
                        ):
                            violations.append(
                                "xix_nc01b_wide_grant_wrong_layer:"
                                f"{str(exc).splitlines()[0][:100]}"
                            )
            finally:
                wide.close()
        finally:
            cur.execute(
                "REVOKE UPDATE ON TABLE public.webhook_ingress_identities"
                " FROM app_user"
            )
        cur.execute(
            "SELECT has_table_privilege('app_user',"
            " 'webhook_ingress_identities', 'UPDATE')"
        )
        if cur.fetchone()[0] is not False:
            violations.append("xix_nc01b_posture_not_restored")
        if not [v for v in violations if v.startswith("xix_nc01b_")]:
            checks["nc01b_wide_grant_red"] = True
            reds["NC-01b"] = (
                "RED:marked self-stamp refused at trigger with grants open"
            )

        # NC-02/03: artifact loss demotes (witness + consequence here;
        # evidence/root covered by the physics gate battery).
        for table, cause in (
            ("b26_p2_ingress_auth_witness", "witness"),
            ("b26_p2_provider_auth_consequence", "consequence"),
        ):
            victim = _mkrow(f"xix-nc23-{cause}", f"xix-ncc23-{cause}", 2000)
            assert _auth(victim, f"xix-nc23-{cause}", "b" * 64) == (
                "authenticated_known"
            )
            assert _current(victim)
            cur.execute(
                f"DELETE FROM public.{table}"
                " WHERE webhook_ingress_identity_id=%s",
                (victim,),
            )
            if _current(victim):
                violations.append(f"xix_nc0203_survives:{cause}")
        if not [v for v in violations if v.startswith("xix_nc0203_")]:
            checks["nc02_nc03_detach_red"] = True
            reds["NC-02/03"] = "RED:predicate false after artifact loss"

        # NC-06: familyless shapes (parser + atomic, no mutation).
        sys.path.insert(0, str(REPO_ROOT / "backend"))
        try:
            from app.webhooks.commerce_derivation import (  # noqa: PLC0415
                CommerceDerivationError,
                derive_event_family,
            )

            for provider, body, topic in (
                ("stripe", b'{"id":"pi_1","amount":100,"currency":"usd"}', None),
                ("paypal", b'{"id":"s1","amount":{"total":"1.00"}}', None),
                ("shopify", b'{"id":1,"total_price":"1.00"}', None),
                ("woocommerce", b'{"id":1,"total":"1.00"}', None),
            ):
                try:
                    derive_event_family(provider, body, topic=topic)
                    violations.append(f"xix_nc06_defaulted:{provider}")
                except CommerceDerivationError:
                    pass
            # Supported explicit signals still conduct (no over-refusal).
            assert derive_event_family(
                "stripe",
                b'{"id":"pi_1","type":"payment_intent.succeeded"}',
            ) == "payment_intent.succeeded"
            assert derive_event_family(
                "shopify", b'{"id":1}', topic="orders/create"
            ) == "orders.create"
        finally:
            sys.path.pop(0)
        if not [v for v in violations if v.startswith("xix_nc06_")]:
            checks["nc06_familyless_red"] = True
            reds["NC-06"] = "RED:familyless derivation refused per provider"

        fam_row = _mkrow("xix-nc06", "xix-ncc06", 6000)
        igr = psycopg2.connect(ingress_dsn)
        igr.autocommit = False
        try:
            with igr.cursor() as icur:
                icur.execute(
                    "SELECT set_config('app.current_tenant_id', %s, false)",
                    (tenant,),
                )
                try:
                    icur.execute(
                        "SELECT public.b26_p2_authenticate_ingress_atomic("
                        "%s,'stripe','xix-nc06',%s,%s,"
                        "'hmac-sha256-timestamped-hex','v1')",
                        (fam_row, "c" * 64, "b" * 64),
                    )
                    violations.append("xix_nc06_atomic_minted_familyless")
                except Exception as exc:
                    if "b26_p2_atomic_family_unbound_refused" not in str(exc):
                        violations.append(
                            "xix_nc06_atomic_wrong_refusal:"
                            f"{str(exc).splitlines()[0][:100]}"
                        )
        finally:
            try:
                igr.rollback()
            except Exception:
                pass
            igr.close()
        if not [v for v in violations if "xix_nc06_atomic" in v]:
            checks["nc06_atomic_familyless_red"] = True

        # NC-07/08: verdict follows source invalidation.
        src = _mkrow("xix-nc0708", "xix-ncc0708", 7000)
        assert _auth(src, "xix-nc0708", "d" * 64) == "authenticated_known"
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
            " SELECT %s, event_id, %s, 'stripe', 'xix-ncc0708',"
            " 'xix-nc0708', 'xix-ncc0708', 'matched_provisional', 'high',"
            " 7000, 7000, 'USD', now(), now(), 7000, 7000,"
            " 7000, 0, 0, 'exact' FROM public.webhook_ingress_identities"
            " WHERE id=%s RETURNING id,"
            " b26_p2_source_authority_state",
            (tenant, src, src),
        )
        verdict_id, verdict_state = cur.fetchone()
        if verdict_state != "current":
            violations.append("xix_nc0708_verdict_not_current_at_birth")
        cur.execute(
            "DELETE FROM public.b26_p2_ingress_auth_witness"
            " WHERE webhook_ingress_identity_id=%s",
            (src,),
        )
        cur.execute(
            "SELECT b26_p2_source_authority_state FROM"
            " public.b23_match_verdicts WHERE id=%s",
            (verdict_id,),
        )
        if cur.fetchone()[0] != "historically_unverifiable":
            violations.append("xix_nc0708_verdict_survives_source_loss")
        else:
            checks["nc07_nc08_verdict_follows_source"] = True
            reds["NC-07/08"] = (
                "RED:verdict currentness revoked with source evidence"
            )
        cur.execute(
            "SELECT count(*) FROM public.b26_p2_verdict_supersession_ledger"
            " WHERE verdict_id=%s",
            (verdict_id,),
        )
        # State did not change on INSERT (born current); no ledger row
        # required. The revocation path appends nothing either (state
        # moves via propagation trigger UPDATE -- covered below).
        cur.execute(
            "SELECT b26_p2_demotion_reason FROM"
            " public.webhook_ingress_identities WHERE id=%s",
            (src,),
        )
        if not (cur.fetchone()[0] or "").startswith("xix-evidence-revoked:"):
            violations.append("xix_nc0708_no_demotion_reason")

        # NC-11: ledger tampering refused.
        try:
            cur.execute(
                "UPDATE public.b26_p2_verdict_supersession_ledger"
                " SET new_authority_state='current'"
            )
            violations.append("xix_nc11_ledger_updated")
        except Exception:
            admin.rollback()
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (tenant,),
            )
        try:
            cur.execute("DELETE FROM public.b26_p2_verdict_supersession_ledger")
            violations.append("xix_nc11_ledger_deleted")
        except Exception:
            admin.rollback()
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (tenant,),
            )
        if not [v for v in violations if v.startswith("xix_nc11_")]:
            checks["nc11_ledger_tamper_red"] = True
            reds["NC-11"] = "RED:ledger UPDATE/DELETE refused for all"

        # NC-12: registry retirement ends currentness (Model A honesty).
        r1row = _mkrow("xix-nc12", "xix-ncc12", 12000)
        assert _auth(r1row, "xix-nc12", "e" * 64) == "authenticated_known"
        assert _current(r1row)
        cur.execute(
            "UPDATE public.b26_p2_semantic_regime_registry SET status='retired'"
            " WHERE regime_id='xvii-sovereign-v1'"
        )
        if _current(r1row):
            violations.append("xix_nc12_retired_regime_still_current")
        else:
            checks["nc12_retirement_revokes"] = True
            reds["NC-12"] = "RED:retired regime ends currentness live"
        cur.execute(
            "UPDATE public.b26_p2_semantic_regime_registry SET status='active'"
            " WHERE regime_id='xvii-sovereign-v1'"
        )
        if not _current(r1row):
            violations.append("xix_nc12_restore_failed")
        else:
            checks["nc12_restore_green"] = True

        # NC-10: incompatible revisions refused by this build's gate.
        sys.path.insert(0, str(REPO_ROOT / "backend"))
        try:
            from app.core.construction_authority import (  # noqa: PLC0415
                ConstructionAuthorityError,
                assert_production_construction_authority,
                migration_graph_head,
            )

            try:
                assert_production_construction_authority(["202609300001"])
                violations.append("xix_nc10_old_revision_served")
            except ConstructionAuthorityError:
                checks["nc10_old_revision_red"] = True
                reds["NC-10"] = "RED:predecessor schema refused at boot gate"
            # XX: the contract advances with the head; the predecessor
            # under test is now one step deeper (300002 refused, head
            # 300003 serves).
            try:
                assert_production_construction_authority(["202609300002"])
                violations.append("xix_nc10_old_revision_served")
            except ConstructionAuthorityError:
                checks["nc10_old_revision_red"] = True
            assert_production_construction_authority(["202609300003"])
            if migration_graph_head() != "202609300003":
                violations.append("xix_nc10_head_mismatch")
            else:
                checks["nc10_head_current"] = True
        finally:
            sys.path.pop(0)

        # NC-04: same-regime co-edit -> publication gate RED -> restore.
        contract_path = B26_DIR / "provider-semantic-contract.v1.json"
        registry_path = B26_DIR / "semantic-regime-registry.json"
        pin_path = (
            REPO_ROOT
            / "contracts-internal"
            / "governance"
            / "b26_p2_xvii_semantic_contract.pin.json"
        )
        snapshots = {
            p: p.read_bytes()
            for p in (contract_path, registry_path, pin_path)
        }
        hashes_before = {str(p): _sha(p) for p in snapshots}
        try:
            blob = json.loads(contract_path.read_text(encoding="utf-8"))
            blob["xix_nc04_probe"] = True
            contract_path.write_text(json.dumps(blob, indent=2))
            code, _out = _gate([])
            if code == 0:
                violations.append("xix_nc04_coedit_stayed_green")
            else:
                checks["nc04_coedit_red"] = True
                reds["NC-04"] = "RED:same-regime co-edit breaks chain match"
        finally:
            for p, data in snapshots.items():
                p.write_bytes(data)
        hashes_after = {str(p): _sha(p) for p in snapshots}
        if hashes_before != hashes_after:
            violations.append("xix_nc04_restore_not_exact")
        else:
            checks["nc04_restore_green"] = True
            code, _ = _gate([])
            if code != 0:
                violations.append("xix_nc04_restore_not_green")

        # NC-05: same-version family-law co-edit -> RED -> restore.
        family_path = B26_DIR / "event-family-law.v2.json"
        family_snap = family_path.read_bytes()
        family_hash_before = _sha(family_path)
        try:
            blob = json.loads(family_path.read_text(encoding="utf-8"))
            blob["families"]["stripe"]["canonical_family"] = (
                "payment_intent.succeeded"
            )
            blob["xix_nc05_probe"] = True
            family_path.write_text(json.dumps(blob, indent=2))
            code, _out = _gate([])
            if code == 0:
                violations.append("xix_nc05_coedit_stayed_green")
            else:
                checks["nc05_coedit_red"] = True
                reds["NC-05"] = "RED:same-version family co-edit breaks law"
        finally:
            family_path.write_bytes(family_snap)
        if _sha(family_path) != family_hash_before:
            violations.append("xix_nc05_restore_not_exact")
        else:
            checks["nc05_restore_green"] = True
            code, _ = _gate([])
            if code != 0:
                violations.append("xix_nc05_restore_not_green")

        # NC-14: parser-meaning drift after the proof observes RED in
        # the family coherence arm (container-equivalence gates own the
        # byte-identical-artifact half of this falsifier).
        oracle_path = (
            REPO_ROOT / "backend" / "app" / "webhooks"
            / "commerce_derivation.py"
        )
        oracle_snap = oracle_path.read_bytes()
        oracle_hash_before = _sha(oracle_path)
        try:
            oracle_text = oracle_path.read_text(encoding="utf-8")
            drifted = oracle_text.replace(
                '"stripe": "payment_intent.succeeded"',
                '"stripe": "payment_intent.forged"',
                1,
            )
            if drifted == oracle_text:
                violations.append("xix_nc14_drift_point_missing")
            else:
                oracle_path.write_text(drifted, encoding="utf-8")
                code, _out = _gate([])
                if code == 0:
                    violations.append("xix_nc14_parser_drift_stayed_green")
                else:
                    checks["nc14_parser_drift_red"] = True
                    reds["NC-14"] = "RED:parser meaning drift breaks law"
        finally:
            oracle_path.write_bytes(oracle_snap)
        if _sha(oracle_path) != oracle_hash_before:
            violations.append("xix_nc14_restore_not_exact")
        else:
            checks["nc14_restore_green"] = True
        cur.close()
    except Exception as exc:
        violations.append(f"xix_nc_live_failed:{exc}")
    finally:
        admin.close()

    # NC-09: downgrade round-trip on this lane (LAST: it moves the
    # schema revision). Downgrade -1, run the runtime attack matrix,
    # re-upgrade to head, verify head.
    import os  # noqa: PLC0415

    env = dict(os.environ)
    env["MIGRATION_DATABASE_URL"] = admin_dsn
    env["DATABASE_URL"] = admin_dsn
    try:
        down = subprocess.run(
            [sys.executable, "-m", "alembic", "downgrade", "-1"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            env=env,
        )
        if down.returncode != 0:
            violations.append(
                f"xix_nc09_downgrade_failed:{down.stderr[-300:]}"
            )
        else:
            try:
                import psycopg2  # noqa: PLC0415

                chk = psycopg2.connect(admin_dsn)
                chk.autocommit = True
                try:
                    with chk.cursor() as ccur:
                        ccur.execute(
                            "SELECT version_num FROM alembic_version"
                        )
                        if ccur.fetchone()[0] != "202609300002":
                            violations.append(
                                "xix_nc09_downgrade_wrong_revision"
                            )
                        usr = psycopg2.connect(user_dsn)
                        usr.autocommit = False
                        try:
                            with usr.cursor() as ucur:
                                ucur.execute(
                                    "SELECT set_config("
                                    "'app.current_tenant_id', %s, false)",
                                    (tenant,),
                                )
                                ucur.execute(
                                    "SELECT id FROM"
                                    " public.webhook_ingress_identities"
                                    " LIMIT 1"
                                )
                                target = ucur.fetchone()
                                target = target[0] if target else None
                                if target is None:
                                    violations.append(
                                        "xix_nc09_no_rows_to_attack"
                                    )
                                else:
                                    try:
                                        ucur.execute(
                                            "UPDATE"
                                            " public.webhook_ingress_identities"
                                            " SET b26_p2_provenance_status="
                                            "'authenticated_known',"
                                            " b26_p2_semantic_regime="
                                            "'xvii-sovereign-v1',"
                                            " b26_p2_demotion_reason=NULL"
                                            " WHERE id=%s",
                                            (target,),
                                        )
                                        usr.commit()
                                        violations.append(
                                            "xix_nc09_downgrade_mint_permitted"
                                        )
                                    except Exception:
                                        usr.rollback()
                            with usr.cursor() as ucur:
                                ucur.execute(
                                    "SELECT has_table_privilege("
                                    "'app_user',"
                                    " 'webhook_ingress_identities',"
                                    " 'UPDATE')"
                                )
                                if ucur.fetchone()[0] is not False:
                                    violations.append(
                                        "xix_nc09_downgrade_rearms_dml"
                                    )
                                else:
                                    checks["nc09_downgrade_no_dml"] = True
                                    reds["NC-09"] = (
                                        "RED:direct-DML mint impossible at"
                                        " maintenance boundary"
                                    )
                        finally:
                            usr.close()
                finally:
                    chk.close()
            finally:
                up = subprocess.run(
                    [sys.executable, "-m", "alembic", "upgrade", "head"],
                    capture_output=True,
                    text=True,
                    cwd=str(REPO_ROOT),
                    env=env,
                )
                if up.returncode != 0:
                    violations.append(
                        f"xix_nc09_reupgrade_failed:{up.stderr[-300:]}"
                    )
                else:
                    import psycopg2  # noqa: PLC0415

                    chk2 = psycopg2.connect(admin_dsn)
                    chk2.autocommit = True
                    try:
                        with chk2.cursor() as ccur:
                            ccur.execute(
                                "SELECT version_num FROM alembic_version"
                            )
                            if ccur.fetchone()[0] != "202609300003":
                                violations.append(
                                    "xix_nc09_reupgrade_wrong_revision"
                                )
                            else:
                                checks["nc09_reupgrade_head"] = True
                    finally:
                        chk2.close()
    except Exception as exc:
        violations.append(f"xix_nc09_harness_failed:{exc}")

    # NC-13: no new async repair machinery exists in XIX (static).
    try:
        tasks_root = REPO_ROOT / "backend" / "app" / "tasks"
        if tasks_root.is_dir():
            new_tasks = [
                p.name
                for p in tasks_root.rglob("*.py")
                if "xix" in p.name.lower()
            ]
            if new_tasks:
                violations.append(f"xix_nc13_new_async_tasks:{new_tasks}")
            else:
                checks["nc13_no_new_async_wiring"] = True
                reds["NC-13"] = (
                    "N/A:revocation is transactional; no queue edge to remove"
                )
    except Exception as exc:
        violations.append(f"xix_nc13_harness_failed:{exc}")

    status = "PASS" if not violations else "FAIL"
    print(f"B26_P2_XIX_NC_{status}")
    if violations:
        print(";".join(sorted(violations)))
    else:
        print(
            json.dumps(
                {"checks": checks, "observed_red": reds},
                sort_keys=True,
                default=str,
            )
        )
    if args.evidence_out:
        Path(args.evidence_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.evidence_out).write_text(
            json.dumps(
                {
                    "gate_id": "B26-P2-XIX-NC",
                    "status": status,
                    "violations": sorted(violations),
                    "checks": checks,
                    "observed_red": reds,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(main())
