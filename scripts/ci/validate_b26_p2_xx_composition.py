#!/usr/bin/env python3
"""B2.6-P2 Corrective XX compositional-closure gate.

H-XX-A..F (Directive XX): XIX closed the named instances; the remaining
class is composition failure -- one subsystem invalidates a source while
another representation stays positive and a consumer produces authority
no longer justified by the source. This gate proves the compositional
closure on a live lane at the XX head:

- XX-C1: single currentness law -- the central predicate, the
  Trust-adapter read, coverage, and verdict propagation agree after a
  lawful registry retirement (GREEN -> retire -> all-FALSE -> restore
  -> all-TRUE), and backfill-tagged history reads non-current;
- XX-C2: event-family authenticity -- cancelled/voided/refunded
  Shopify bodies are refused as orders.create facts even under a
  forged orders/create topic; status-less WooCommerce bodies are
  refused even with a topic; direct persistence of a
  woocommerce-transport family is refused at the seam;
- XX-C3: history protection -- the supersession chain appends and
  verifies; the independent observer reports no violation; disabling
  a protection trigger makes the observer RED (then restored GREEN);
  runtime ledger mutation (UPDATE/DELETE/TRUNCATE) is refused;
- XX-C4: least privilege + downgrade posture -- authority columns
  unreachable, XX downgrade content retains revokes and predicate
  with no GRANT, construction contract equals the migration head.

Prints B26_P2_XX_COMPOSITION_PASS on success.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

MIG_XX = (
    REPO_ROOT
    / "alembic"
    / "versions"
    / "007_skeldir_foundation"
    / "202609300003_b26_p2_corrective_xx_compositional_closure.py"
)
RUNTIME_ROLES = (
    "app_user", "app_ingress", "app_worker", "app_relay", "app_beat",
    "app_dispatch_publisher", "app_trust_issuer", "app_trust_signer",
)


def _static_checks(violations: list[str], checks: dict) -> None:
    try:
        mig = MIG_XX.read_text(encoding="utf-8")
    except OSError as exc:
        violations.append(f"xx_comp_unreadable:{exc}")
        return
    upgrade = mig.split("def downgrade", 1)[0]
    downgrade = mig.split("def downgrade", 1)[1] if "def downgrade" in mig else ""
    # Predicate v2 law present in upgrade.
    for token in (
        "b26_p2_ingress_has_current_authority",
        "b26_p2_family_source IN",
        "body-signal:type",
        "transport-topic:x-shopify-topic",
        "202609300003",
        "b26_p2_state_eligible_for_p3",
        "b26_p2_ingress_has_current_authority(_ingress)",
        "b26_p2_propagate_verdict_authority_on_regime_change",
        "trg_b26_p2_xx_propagate_on_regime_change",
        "b26_p2_chain_verdict_supersession",
        "b26_p2_verify_history_protection",
        "b26_p2_enforce_consequence_family_coherence",
        "b26_p2_woocommerce_transport_family_refused",
        "trg_b26_p2_xx_supersession_chain",
    ):
        if token not in upgrade:
            violations.append(f"xx_comp_law_missing:{token}")
    if not [v for v in violations if "xx_comp_law_missing" in v]:
        checks["xx_law_present"] = True
    # Hygiene law: no floor-change trigger may be CREATED (the floor
    # only changes inside migrations; firing there would poison the
    # cascade with un-restorable session state). Idempotent DROP
    # cleanup of predecessor drafts is allowed. Upgrade re-derivation
    # must be explicit instead.
    if ("CREATE TRIGGER trg_b26_p2_xx_propagate_on_floor_change" in upgrade
            or "CREATE OR REPLACE FUNCTION"
            " public.b26_p2_propagate_verdict_authority_on_floor_change"
            in upgrade):
        violations.append("xx_comp_floor_trigger_present")
    elif "FOR _t IN SELECT t.id FROM public.tenants AS t" not in upgrade:
        violations.append("xx_comp_upgrade_rederivation_missing")
    else:
        checks["cascade_hygiene"] = True
    # Backfill must NOT satisfy the predicate: the allowlisted
    # explicit-source set in the predicate must exclude the backfill tag.
    if "xix-backfill" in upgrade.split(
        "AND c.b26_p2_family_source IN (", 1
    )[-1].split(") THEN", 1)[0]:
        violations.append("xx_comp_backfill_admitted_by_predicate")
    else:
        checks["predicate_excludes_backfill"] = True
    # Downgrade retains safety and grants nothing. The XIX predicate
    # body is restored via the module-level _XX_PREDICATE_XIX_RESTORE
    # constant referenced from downgrade().
    if "GRANT UPDATE" in downgrade or "GRANT SELECT" in downgrade:
        violations.append("xx_comp_downgrade_regrants")
    else:
        checks["downgrade_grants_nothing"] = True
    if "_XX_PREDICATE_XIX_RESTORE" not in downgrade:
        violations.append("xx_comp_downgrade_missing:predicate_restore_ref")
    if "202609300002" not in downgrade:
        violations.append("xx_comp_downgrade_missing:predecessor_floor")
    if "_XX_PREDICATE_XIX_RESTORE = " not in mig:
        violations.append("xx_comp_downgrade_missing:predicate_restore_body")
    if not [v for v in violations if "xx_comp_downgrade_missing" in v]:
        checks["downgrade_restores_xix_law"] = True

    # Single-currentness readers in Python.
    adapters = (REPO_ROOT / "backend" / "app" / "trust" / "source_adapters.py").read_text(
        encoding="utf-8"
    )
    if adapters.count("b26_p2_ingress_has_current_authority(") < 2:
        violations.append("xx_comp_trust_adapter_predicate_missing")
    elif "b26_p2_source_authority_state = 'current'" in adapters and (
        "AS ingress_has_current_authority" in adapters
    ):
        violations.append("xx_comp_trust_adapter_cached_authority")
    else:
        checks["trust_adapter_reads_predicate"] = True
    for rel in (
        "backend/app/bayesian/eligibility.py",
        "backend/app/bayesian/source_snapshot.py",
        "backend/app/bayesian/source_contract_authority.py",
        "backend/app/bayesian/api_projection.py",
        "backend/app/revenue_verification/match_engine_kernel.py",
    ):
        body = (REPO_ROOT / rel).read_text(encoding="utf-8")
        if "b26_p2_ingress_has_current_authority(" not in body:
            violations.append(f"xx_comp_reader_missing_predicate:{rel}")
    if not [v for v in violations if "xx_comp_reader_missing_predicate" in v]:
        checks["bayesian_kernel_read_predicate"] = True

    # Event-family authenticity in Python.
    commerce = (
        REPO_ROOT / "backend" / "app" / "webhooks" / "commerce_derivation.py"
    ).read_text(encoding="utf-8")
    for token in (
        "is not an orders.create fact",
        "terminal financial status",
        "no transported-topic fallback",
    ):
        if token not in commerce:
            violations.append(f"xx_comp_lifecycle_guard_missing:{token}")
    if "transport-topic:x-wc-webhook-topic" in commerce:
        violations.append("xx_comp_woo_transport_fallback_survives")
    if not [v for v in violations if v.startswith("xx_comp_lifecycle") or v.startswith("xx_comp_woo")]:
        checks["family_authenticity_python"] = True
    relay = (REPO_ROOT / "backend" / "app" / "api" / "webhooks.py").read_text(
        encoding="utf-8"
    )
    if "familyless:no-body-status" not in relay:
        violations.append("xx_comp_relay_hint_not_hardened")
    else:
        checks["relay_hint_hardened"] = True

    # Construction contract equals the migration head.
    contract = (
        REPO_ROOT / "backend" / "app" / "core" / "construction_authority.py"
    ).read_text(encoding="utf-8")
    if 'REQUIRED_SCHEMA_REVISION = "202609300003"' not in contract:
        violations.append("xx_comp_construction_contract_not_advanced")
    else:
        checks["construction_contract_at_xx"] = True


def _live_checks(admin_dsn: str, violations: list[str], checks: dict) -> None:
    try:
        import psycopg2  # noqa: PLC0415
    except ImportError as exc:
        violations.append(f"xx_comp_no_driver:{exc}")
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
        violations.append(f"xx_comp_connect_failed:{exc}")
        return
    try:
        cur = admin.cursor()
        tenant = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO public.tenants (id, name, api_key_hash,"
            " notification_email) VALUES (%s,%s,%s,%s)",
            (tenant, "xx-comp", uuid.uuid4().hex, "xx@example.invalid"),
        )
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false)", (tenant,))
        cur.execute(
            "INSERT INTO public.channel_taxonomy (code, family, is_paid,"
            " display_name, state) VALUES ('xx_comp_ch', 'xx', true,"
            " 'XX', 'active') ON CONFLICT (code) DO NOTHING"
        )

        def _mkrow(evref: str, cref: str, amount: int,
                   provider: str = "stripe",
                   kind: str = "stripe_payment_intent_id") -> str:
            ev = str(uuid.uuid4())
            cur.execute(
                "INSERT INTO public.attribution_events (id, tenant_id,"
                " occurred_at, correlation_id, session_id, revenue_cents,"
                " raw_payload, idempotency_key, event_type, channel,"
                " campaign_id, conversion_value_cents, currency,"
                " event_timestamp, processed_at, processing_status)"
                " VALUES (%s,%s,now(),%s,%s,%s,'{}'::jsonb,%s,'conversion',"
                " 'xx_comp_ch','c',%s,'USD',now(),now(),'processed')",
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
                " VALUES (%s,%s,%s,%s,%s,%s,%s,"
                "%s,%s,'USD',now(),%s,'authenticity_verified')",
                (ing, tenant, ev, provider, evref, cref, kind,
                 cref, amount, str(uuid.uuid4())),
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

        def _predicate(ing: str) -> bool | None:
            cur.execute(
                "SELECT public.b26_p2_ingress_has_current_authority(%s)", (ing,)
            )
            return cur.fetchone()[0]

        def _adapter_read(verdict: str) -> tuple[bool | None, str | None]:
            # Exact read-time semantics of the hardened Trust adapter:
            # verdict-local state is display; authority is the canonical
            # predicate over the tenant-coherent backing ingress.
            cur.execute(
                """
                SELECT (
                    i.tenant_id = v.tenant_id
                    AND public.b26_p2_ingress_has_current_authority(
                        v.webhook_ingress_identity_id
                    )
                ) AS auth,
                v.b26_p2_source_authority_state AS state
                FROM public.b23_match_verdicts AS v
                LEFT JOIN public.webhook_ingress_identities AS i
                  ON i.id = v.webhook_ingress_identity_id
                WHERE v.tenant_id = %s AND v.id = %s
                """,
                (tenant, verdict),
            )
            row = cur.fetchone()
            return (row[0], row[1]) if row else (None, None)

        def _mkverdict(ing: str, eref: str, amount: int) -> str:
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
                " SELECT %s, event_id, %s, 'stripe', 'xx-c1',"
                " %s, 'xx-c1', 'matched_provisional', 'high',"
                " %s, %s, 'USD', now(), now(), %s, %s,"
                " %s, 0, 0, 'exact' FROM public.webhook_ingress_identities"
                " WHERE id=%s RETURNING id",
                (tenant, ing, eref, amount, amount, amount, amount, amount, ing),
            )
            return cur.fetchone()[0]

        # C1: lawful mint + reader agreement, then governed retirement.
        row = _mkrow("xx-c1", "xx-cc1", 100000)
        assert _auth(row, "xx-c1", "a" * 64) == "authenticated_known"
        if _predicate(row) is not True:
            violations.append("xx_comp_lawful_mint_not_current")
            return
        verdict = _mkverdict(row, "xx-c1", 100000)
        auth, state = _adapter_read(verdict)
        if auth is not True or state != "current":
            violations.append("xx_comp_adapter_disagrees_at_rest")
        else:
            checks["readers_agree_at_rest"] = True
        cur.execute(
            "UPDATE public.b26_p2_semantic_regime_registry"
            " SET status='retired' WHERE regime_id='xvii-sovereign-v1'"
        )
        if _predicate(row) is not False:
            violations.append("xx_comp_retire_predicate_survives")
        auth, state = _adapter_read(verdict)
        if auth is not False:
            violations.append("xx_comp_retire_adapter_survives")
        cur.execute(
            "SELECT b26_p2_source_authority_state FROM public.b23_match_verdicts"
            " WHERE id=%s",
            (verdict,),
        )
        propagated = cur.fetchone()[0]
        if propagated == "current":
            violations.append("xx_comp_retire_verdict_cache_survives")
        if not [v for v in violations if v.startswith("xx_comp_retire_")]:
            checks["readers_agree_after_retire"] = True
        cur.execute(
            "UPDATE public.b26_p2_semantic_regime_registry"
            " SET status='active' WHERE regime_id='xvii-sovereign-v1'"
        )
        if _predicate(row) is not True:
            violations.append("xx_comp_restore_not_current")
        else:
            checks["readers_agree_after_restore"] = True

        # C1b: backfill-tagged history is preserved but non-current.
        backfill = _mkrow("xx-bf", "xx-cbf", 5000)
        assert _auth(backfill, "xx-bf", "b" * 64) == "authenticated_known"
        if _predicate(backfill) is not True:
            violations.append("xx_comp_backfill_baseline_not_current")
        cur.execute(
            "UPDATE public.b26_p2_provider_auth_consequence"
            " SET b26_p2_family_source='xix-backfill:pre-xix-mint'"
            " WHERE webhook_ingress_identity_id=%s",
            (backfill,),
        )
        if _predicate(backfill) is not False:
            violations.append("xx_comp_backfill_remains_current")
        else:
            checks["backfill_honestly_noncurrent"] = True

        # C2: contradictory body/topic matrix (pure derivation law).
        from app.webhooks.commerce_derivation import (  # noqa: PLC0415
            CommerceDerivationError,
            derive_commerce,
            derive_event_family,
        )

        import json as _json

        def _shopify_body(**overrides: object) -> bytes:
            base: dict[str, object] = {
                "id": 900001,
                "total_price": "10.00",
                "currency": "USD",
                "created_at": "2026-09-01T00:00:00Z",
            }
            base.update(overrides)
            return _json.dumps(base).encode()

        for name, kwargs in (
            ("cancelled", {"cancelled_at": "2026-09-02T00:00:00Z",
                           "cancel_reason": "customer",
                           "financial_status": "voided"}),
            ("voided", {"financial_status": "voided"}),
            ("refunded", {"financial_status": "refunded",
                          "refunds": [{"id": 1}]}),
            ("partially_refunded", {"financial_status": "partially_refunded",
                                    "refunds": [{"id": 2}]}),
        ):
            try:
                derive_commerce("shopify", _shopify_body(**kwargs))
                violations.append(f"xx_comp_terminal_body_conducts:{name}")
            except CommerceDerivationError:
                pass
        # Honest creation still conducts (family + commerce).
        try:
            fam = derive_event_family(
                "shopify", _shopify_body(), topic="orders/create"
            )
            honest = derive_commerce("shopify", _shopify_body())
            if fam != "orders.create" or honest.verified_amount_minor != 1000:
                violations.append("xx_comp_honest_shopify_misderived")
        except CommerceDerivationError as exc:
            violations.append(f"xx_comp_honest_shopify_refused:{exc}")
        # Status-less WooCommerce + topic is familyless.
        try:
            derive_event_family(
                "woocommerce",
                _json.dumps({"id": 7, "currency": "USD",
                             "total": "5.00"}).encode(),
                topic="order.completed",
            )
            violations.append("xx_comp_woo_topic_only_conducts")
        except CommerceDerivationError:
            pass
        if not [v for v in violations if v.startswith("xx_comp_terminal_")
                or v.startswith("xx_comp_honest_")
                or v.startswith("xx_comp_woo_")]:
            checks["contradictory_meaning_refused"] = True

        # C2b: direct persistence of a woocommerce-transport family
        # refused at the seam (H-XX-B). Mint a lawful woocommerce row,
        # then attempt to rewrite its source to the removed fallback.
        woo = _mkrow("xx-woo", "xx-cwoo", 6000,
                     provider="woocommerce",
                     kind="woocommerce_order_id")
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
                    " 'order.completed', true)"
                )
                icur.execute(
                    "SELECT set_config('app.b26_p2_event_family_source',"
                    " 'body-signal:status', true)"
                )
                icur.execute(
                    "SELECT public.b26_p2_authenticate_ingress_atomic("
                    "%s,'woocommerce',%s,%s,%s,"
                    "'hmac-sha256-base64','v1')",
                    (woo, "xx-woo", "f" * 64, "b" * 64),
                )
                igr.commit()
        except Exception as exc:
            igr.rollback()
            violations.append(f"xx_comp_woo_lawful_mint_failed:{str(exc)[:120]}")
        finally:
            igr.close()
        if _predicate(woo) is not True:
            violations.append("xx_comp_woo_lawful_mint_not_current")
        try:
            cur.execute(
                "UPDATE public.b26_p2_provider_auth_consequence"
                " SET b26_p2_family_source="
                "'transport-topic:x-wc-webhook-topic'"
                " WHERE webhook_ingress_identity_id=%s",
                (woo,),
            )
            violations.append("xx_comp_woo_transport_persisted")
        except Exception as exc:
            if "b26_p2_woocommerce_transport_family_refused" not in str(exc):
                violations.append(
                    "xx_comp_woo_transport_wrong_refusal:"
                    f"{str(exc).splitlines()[0][:120]}"
                )
            admin.rollback()
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (tenant,),
            )
            checks["woo_transport_refused_at_seam"] = True
        cur.execute(
            "SELECT tgenabled FROM pg_trigger WHERE tgname ="
            " 'trg_b26_p2_xx_consequence_family_coherence'"
        )
        trow = cur.fetchone()
        if not trow or trow[0] != "O":
            violations.append("xx_comp_coherence_trigger_not_enabled")
        else:
            checks["coherence_trigger_enabled"] = True

        # C3: supersession chain + observer + runtime refusal.
        cur.execute(
            "UPDATE public.b23_match_verdicts"
            " SET attributed_amount_minor=2,"
            " canonical_expected_gross_amount_minor=2,"
            " canonical_captured_gross_amount_minor=2,"
            " verified_amount_minor=2,"
            " canonical_net_verified_amount_minor=2 WHERE id=%s",
            (verdict,),
        )
        cur.execute(
            "SELECT entry_hash, prev_entry_hash FROM"
            " public.b26_p2_verdict_supersession_ledger WHERE verdict_id=%s"
            " ORDER BY recorded_at DESC, id DESC LIMIT 1",
            (verdict,),
        )
        chain = cur.fetchone()
        if not chain or not chain[0]:
            violations.append("xx_comp_chain_not_appended")
        else:
            checks["supersession_chain_appends"] = True
        cur.execute("SELECT violation FROM public.b26_p2_verify_history_protection()")
        observed = [r[0] for r in cur.fetchall()]
        if observed:
            violations.append(f"xx_comp_observer_reports:{'|'.join(observed)[:200]}")
        else:
            checks["history_observer_clean"] = True
        # Observer sensitivity: disabling a protection trigger REDs it.
        cur.execute(
            "ALTER TABLE public.b26_p2_verdict_supersession_ledger"
            " DISABLE TRIGGER trg_b26_p2_xx_supersession_chain"
        )
        cur.execute("SELECT violation FROM public.b26_p2_verify_history_protection()")
        observed = [r[0] for r in cur.fetchall()]
        cur.execute(
            "ALTER TABLE public.b26_p2_verdict_supersession_ledger"
            " ENABLE TRIGGER trg_b26_p2_xx_supersession_chain"
        )
        if not any("trg_b26_p2_xx_supersession_chain" in o for o in observed):
            violations.append("xx_comp_observer_blind_to_disable")
        else:
            checks["observer_detects_disable"] = True
        cur.execute("SELECT violation FROM public.b26_p2_verify_history_protection()")
        if cur.fetchall():
            violations.append("xx_comp_observer_not_restored")
        # Runtime ledger mutation refused (UPDATE/DELETE/TRUNCATE).
        usr = psycopg2.connect(user_dsn)
        usr.autocommit = True
        try:
            with usr.cursor() as ucur:
                for stmt, tag in (
                    ("UPDATE public.b26_p2_verdict_supersession_ledger"
                     " SET new_attributed_amount_minor=9 WHERE verdict_id=%s",
                     "xx_comp_runtime_ledger_update_permitted"),
                    ("DELETE FROM public.b26_p2_verdict_supersession_ledger"
                     " WHERE verdict_id=%s",
                     "xx_comp_runtime_ledger_delete_permitted"),
                    ("TRUNCATE public.b26_p2_verdict_supersession_ledger",
                     "xx_comp_runtime_ledger_truncate_permitted"),
                    ("TRUNCATE public.b26_p2_publication_history",
                     "xx_comp_runtime_history_truncate_permitted"),
                    ("ALTER TABLE public.b26_p2_verdict_supersession_ledger"
                     " DISABLE TRIGGER trg_b26_p2_xx_supersession_chain",
                     "xx_comp_runtime_trigger_disable_permitted"),
                ):
                    try:
                        if "WHERE verdict_id" in stmt:
                            ucur.execute(stmt, (verdict,))
                        else:
                            ucur.execute(stmt)
                        violations.append(tag)
                    except Exception:
                        pass
        finally:
            usr.close()
        if not [v for v in violations if v.startswith("xx_comp_runtime_")]:
            checks["runtime_history_mutation_refused"] = True

        # C4: authority columns unreachable + floor at XX.
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
                        "SELECT has_column_privilege(%s,"
                        " 'webhook_ingress_identities',"
                        " 'b26_p2_provenance_status', 'UPDATE')",
                        (role,),
                    )
                    if rcur.fetchone()[0] is not False:
                        violations.append(
                            f"xx_comp_authority_column_reaches:{role}"
                        )
            finally:
                role_conn.close()
        if not [v for v in violations if "xx_comp_authority_column_reaches" in v]:
            checks["least_privilege_effective"] = True
        cur.execute(
            "SELECT floor_revision FROM public.b26_p2_operational_floor WHERE id=1"
        )
        if cur.fetchone()[0] != "202609300003":
            violations.append("xx_comp_floor_not_advanced")
        else:
            checks["floor_at_xx"] = True
        cur.close()
    except Exception as exc:
        violations.append(f"xx_comp_live_failed:{exc}")
    finally:
        admin.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="XX composition closure.")
    parser.add_argument("--dsn", default=None)
    parser.add_argument("--evidence-out", default=None)
    args = parser.parse_args()
    violations: list[str] = []
    checks: dict = {}
    _static_checks(violations, checks)
    if args.dsn is not None:
        _live_checks(args.dsn, violations, checks)
    status = "PASS" if not violations else "FAIL"
    print(f"B26_P2_XX_COMPOSITION_{status}")
    if violations:
        print(";".join(sorted(violations)))
    else:
        print(json.dumps({"checks": checks}, sort_keys=True, default=str))
    if args.evidence_out:
        Path(args.evidence_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.evidence_out).write_text(
            json.dumps(
                {
                    "gate_id": "B26-P2-XX-COMPOSITION",
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
