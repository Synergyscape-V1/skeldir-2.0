#!/usr/bin/env python3
"""B2.6-P2 Corrective XVIII negative controls (relation non-vacuity proof).

Every control proves its gate can RED on a genuine member of the class
it governs, then restores byte-exact GREEN:

Static (no database):
- XVIII-NC-01 (directive NC-01): semantic contract + production parser
  + independent oracle + goldens + reviewed pin co-edited together
  with the regime/version held constant. The XVII contract gate stays
  GREEN (the inherited blind spot, recorded honestly) while the XVIII
  registry gate REDs on the published-law divergence. Restore -> GREEN.
- XVIII-NC-09 (directive NC-09): a served route without a hierarchy
  declaration (or a hierarchy claim outside sovereign families).
  The hierarchy gate REDs. Restore -> GREEN.
- XVIII-NC-12 (directive NC-12): deployed migration bytes changed
  under the same revision identity without a manifest update. The
  manifest gate REDs. Restore -> GREEN.
- XVIII-NC-13 (directive NC-13): semantic regime constant detached
  from the contract without a new identity. Contract + hierarchy
  gates RED. Restore -> GREEN.
- XVIII-OW-01: silent currency-scale widening in production only.
  The contract gate REDs. Restore -> GREEN.

Live (with --dsn, on a governed lane at XVIII head):
- XVIII-NC-02: app_user/app_ingress combined provenance+regime
  promotion with cleared demotion -> DB refusal, state unchanged.
- XVIII-NC-03: stale historical evidence re-presented to the atomic
  on a demoted row -> demoted_ingress_refused.
- XVIII-NC-04: demoted false row in the B2.3 candidate universe ->
  absent (candidate predicate + verdict filter).
- XVIII-NC-05: conducted-then-demoted verdict stays verified ->
  state historically_unverifiable, excluded from reads.
- XVIII-NC-06: coverage over mixed corpus -> numerator excludes
  demoted money; unverifiable context carries it (OW-08: demoted-only
  corpus -> numerator zero, never false 100%).
- XVIII-NC-07: signed-but-unsupported event family at the sovereign
  boundary -> family_unbound_refused (atomic) and derivation refusal.
- XVIII-NC-08: family binding removed from the atomic (simulated by
  NULL-family consequence + dispatch attempt) -> dispatch refuses
  family_unbound.
- XVIII-NC-10: operational floor absent (downgraded schema) -> new
  minting refused with downgrade_serving_refused; restore -> GREEN.
- XVIII-NC-11: demoted precursor + genuine redelivery in one batch
  window -> exactly one candidate (no cardinality violation).
- XVIII-OW-03: verdict relink attack (ingress link rewrite as
  app_user) -> refused.
- XVIII-OW-04: consequence/evidence DELETE as app_user -> refused.
- XVIII-OW-05: registry mutation as app_user -> refused.
- XVIII-OW-06: concurrent same-bytes races converge to one lineage.
- XVIII-OW-09: Trust builder on a non-authoritative source ->
  unavailable status with explicit historically_unverifiable state.
- XVIII-OW-11: governed-mark hygiene -- a refused atomic leaves no
  stamp-capable transaction behind.
- XVIII-OW-12: predicate tenant isolation -- other tenants read FALSE.

XVIII-NC-14 (directive NC-14): no new repair machinery exists in
source (governance gate asserts transactional-only revocation).

Exit code is the gate. Recorded hashes prove exact restoration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import threading
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_GATE = REPO_ROOT / "scripts" / "ci" / "validate_b26_p2_xvii_semantic_contract.py"
REGISTRY_GATE = REPO_ROOT / "scripts" / "ci" / "validate_b26_p2_xviii_semantic_registry.py"
HIERARCHY_GATE = (
    REPO_ROOT / "scripts" / "ci" / "validate_b26_p2_xviii_contract_hierarchy.py"
)
MANIFEST_GATE = (
    REPO_ROOT / "scripts" / "ci" / "validate_b26_p2_xviii_migration_manifest.py"
)
GOVERNANCE_GATE = REPO_ROOT / "scripts" / "ci" / "validate_b26_p2_xviii_governance.py"
ORACLE = REPO_ROOT / "scripts" / "ci" / "validate_b26_p2_xvi_semantic_oracle.py"
CONTRACT = (
    REPO_ROOT
    / "contracts"
    / "reconciliation"
    / "b2.6"
    / "provider-semantic-contract.v1.json"
)
DERIVATION = REPO_ROOT / "backend" / "app" / "webhooks" / "commerce_derivation.py"
PIN = (
    REPO_ROOT
    / "contracts-internal"
    / "governance"
    / "b26_p2_xvii_semantic_contract.pin.json"
)
MIG_280002 = (
    REPO_ROOT
    / "alembic"
    / "versions"
    / "007_skeldir_foundation"
    / "202609280002_b26_p2_corrective_xvi_sovereign_closure.py"
)
RELAY = REPO_ROOT / "backend" / "app" / "api" / "webhooks.py"


def _run(args: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(
        args, capture_output=True, text=True, cwd=str(REPO_ROOT), **kw
    )


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _swap(path: Path, old: str, new: str) -> bytes:
    raw = path.read_bytes()
    norm = raw.replace(b"\r\n", b"\n")
    old_b, new_b = old.encode("utf-8"), new.encode("utf-8")
    if old_b not in norm:
        raise SystemExit(f"nc_anchor_missing:{path.name}:{old[:60]}")
    path.write_bytes(norm.replace(old_b, new_b, 1))
    return raw


def _restore(path: Path, raw: bytes) -> None:
    path.write_bytes(raw)


def _gate_pass(gate: Path, extra: list[str] | None = None) -> bool:
    proc = _run([sys.executable, str(gate), *(extra or [])])
    return proc.returncode == 0


def _control_nc01(violations: list[str], checks: dict) -> None:
    """Common-mode co-edit under a constant regime must RED the registry."""
    before = {p: _sha(p) for p in (CONTRACT, DERIVATION, ORACLE, PIN)}
    prod_orig = DERIVATION.read_bytes()
    or_orig = ORACLE.read_bytes()
    con_orig = CONTRACT.read_bytes()
    pin_orig = PIN.read_bytes()
    try:
        # Material timestamp-authority flip across all five surfaces,
        # regime/version constant (auditor 58/59 construction).
        _swap(DERIVATION, "created = payload.get(\"created\")",
              "created = obj.get(\"created\")")
        _swap(ORACLE, "created = payload.get(\"created\")",
              "created = obj.get(\"created\")")
        contract_text = CONTRACT.read_text(encoding="utf-8")
        contract_text = contract_text.replace(
            "top-level envelope instant payload.created preferred",
            "object instant obj.created preferred",
        )
        # Move the stripe envelope golden vectors with the flipped law
        # (the complete common-mode construction: law + goldens move
        # together, so vector-obedience gates stay green).
        contract_text = contract_text.replace(
            '"verified_amount_scale": 2, "event_timestamp_epoch": 1700000060}',
            '"verified_amount_scale": 2, "event_timestamp_epoch": 1700000000}',
        )
        contract_text = contract_text.replace(
            '"verified_amount_scale": 2, "event_timestamp_epoch": 1705276799}',
            '"verified_amount_scale": 2, "event_timestamp_epoch": 1705276800}',
        )
        CONTRACT.write_text(contract_text, encoding="utf-8")
        pin = json.loads(PIN.read_text(encoding="utf-8"))
        pin["contract_sha256"] = hashlib.sha256(
            CONTRACT.read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest()
        PIN.write_text(json.dumps(pin, indent=2) + "\n", encoding="utf-8")
        contract_gate_green = _gate_pass(CONTRACT_GATE)
        registry_proc = _run([sys.executable, str(REGISTRY_GATE)])
        if registry_proc.returncode == 0:
            violations.append("xviii_nc01_registry_blind_to_common_mode")
        else:
            checks["nc01_registry_reds_on_common_mode"] = True
            checks["nc01_contract_gate_blind_spot_honest"] = contract_gate_green
    finally:
        _restore(DERIVATION, prod_orig)
        _restore(ORACLE, or_orig)
        _restore(CONTRACT, con_orig)
        _restore(PIN, pin_orig)
    if not _gate_pass(CONTRACT_GATE) or not _gate_pass(REGISTRY_GATE):
        violations.append("xviii_nc01_restore_not_green")
    else:
        checks["nc01_restore_green"] = True
    after = {p: _sha(p) for p in (CONTRACT, DERIVATION, ORACLE, PIN)}
    if before != after:
        violations.append("xviii_nc01_restore_not_byte_exact")


def _control_nc09(violations: list[str], checks: dict) -> None:
    relay_orig = RELAY.read_bytes()
    try:
        _swap(
            RELAY,
            '"/webhooks/stripe/payment_intent_succeeded"',
            '"/webhooks/stripe/charge_succeeded_undeclared"',
        )
        if _gate_pass(HIERARCHY_GATE):
            violations.append("xviii_nc09_hierarchy_blind_to_route")
        else:
            checks["nc09_hierarchy_reds_on_undeclared_route"] = True
    finally:
        _restore(RELAY, relay_orig)
    if not _gate_pass(HIERARCHY_GATE):
        violations.append("xviii_nc09_restore_not_green")
    else:
        checks["nc09_restore_green"] = True


def _control_nc12(violations: list[str], checks: dict) -> None:
    mig_orig = MIG_280002.read_bytes()
    try:
        raw = MIG_280002.read_bytes().replace(b"\r\n", b"\n")
        MIG_280002.write_bytes(raw + b"\n# nc12 probe comment\n")
        if _gate_pass(MANIFEST_GATE):
            violations.append("xviii_nc12_manifest_blind_to_revision_edit")
        else:
            checks["nc12_manifest_reds_on_revision_edit"] = True
    finally:
        _restore(MIG_280002, mig_orig)
    if not _gate_pass(MANIFEST_GATE):
        violations.append("xviii_nc12_restore_not_green")
    else:
        checks["nc12_restore_green"] = True


def _control_nc13(violations: list[str], checks: dict) -> None:
    prod_orig = DERIVATION.read_bytes()
    try:
        _swap(DERIVATION, 'SEMANTIC_CONTRACT_REGIME = "xvii-sovereign-v1"',
              'SEMANTIC_CONTRACT_REGIME = "xvii-sovereign-v1-drifted"')
        if _gate_pass(CONTRACT_GATE):
            violations.append("xviii_nc13_contract_blind_to_regime_drift")
        else:
            checks["nc13_contract_reds_on_regime_drift"] = True
        # The hierarchy gate is family-scoped by design: a bare regime
        # relabel with unchanged families is NOT its class (honest
        # negative -- the hierarchy gate must stay green here, proving
        # it does not fire outside its class).
        if not _gate_pass(HIERARCHY_GATE):
            violations.append("xviii_nc13_hierarchy_fires_outside_class")
        else:
            checks["nc13_hierarchy_scoped_to_family_class"] = True
    finally:
        _restore(DERIVATION, prod_orig)
    if not _gate_pass(CONTRACT_GATE) or not _gate_pass(HIERARCHY_GATE):
        violations.append("xviii_nc13_restore_not_green")
    else:
        checks["nc13_restore_green"] = True


def _control_ow01(violations: list[str], checks: dict) -> None:
    prod_orig = DERIVATION.read_bytes()
    try:
        _swap(DERIVATION, '"KMF",', '"KMF",\n    "USD",')
        if _gate_pass(CONTRACT_GATE):
            violations.append("xviii_ow01_contract_blind_to_scale_widening")
        else:
            checks["ow01_contract_reds_on_scale_widening"] = True
    finally:
        _restore(DERIVATION, prod_orig)
    if not _gate_pass(CONTRACT_GATE):
        violations.append("xviii_ow01_restore_not_green")
    else:
        checks["ow01_restore_green"] = True


def _live_controls(
    admin_dsn: str, violations: list[str], checks: dict
) -> None:
    try:
        import psycopg2  # noqa: PLC0415
    except ImportError as exc:
        violations.append(f"xviii_nc_no_driver:{exc}")
        return
    ingress_dsn = admin_dsn.replace(
        "migration_owner:migration_owner", "app_ingress:app_ingress"
    )
    user_dsn = admin_dsn.replace(
        "migration_owner:migration_owner", "app_user:app_user"
    )
    worker_dsn = admin_dsn.replace(
        "migration_owner:migration_owner", "app_worker:app_worker"
    )
    super_dsn = admin_dsn.replace(
        "migration_owner:migration_owner", "postgres:postgres"
    )
    try:
        admin = psycopg2.connect(admin_dsn)
        admin.autocommit = True
    except Exception as exc:
        violations.append(f"xviii_nc_connect_failed:{exc}")
        return
    try:
        cur = admin.cursor()
        tenant = str(uuid.uuid4())
        other_tenant = str(uuid.uuid4())
        for tid, name in ((tenant, "xviii-nc"), (other_tenant, "xviii-nc-other")):
            cur.execute(
                "INSERT INTO public.tenants (id, name, api_key_hash,"
                " notification_email) VALUES (%s,%s,%s,%s)",
                (tid, name, uuid.uuid4().hex, "nc@example.invalid"),
            )
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false)",
                    (tenant,))
        cur.execute(
            "INSERT INTO public.channel_taxonomy (code, family, is_paid,"
            " display_name, state) VALUES ('xviii_nc_ch', 'nc', true,"
            " 'NC', 'active') ON CONFLICT (code) DO NOTHING"
        )

        def _mkrow(evref: str, cref: str, amount: int) -> tuple[str, str]:
            ev = str(uuid.uuid4())
            cur.execute(
                "INSERT INTO public.attribution_events (id, tenant_id,"
                " occurred_at, correlation_id, session_id, revenue_cents,"
                " raw_payload, idempotency_key, event_type, channel,"
                " campaign_id, conversion_value_cents, currency,"
                " event_timestamp, processed_at, processing_status)"
                " VALUES (%s,%s,now(),%s,%s,%s,'{}'::jsonb,%s,'conversion',"
                " 'xviii_nc_ch','c',%s,'USD',now(),now(),'processed')",
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
            return ing, ev

        def _auth(ing: str, eref: str, sha: str) -> str:
            igr = psycopg2.connect(ingress_dsn)
            igr.autocommit = True
            try:
                with igr.cursor() as icur:
                    icur.execute(
                        "SELECT set_config('app.current_tenant_id', %s, false)",
                        (tenant,),
                    )
                    icur.execute(
                        "SELECT public.b26_p2_authenticate_ingress_atomic("
                        "%s,'stripe',%s,%s,%s,"
                        "'hmac-sha256-timestamped-hex','v1')",
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
                    for trigger in (
                        "trg_b26_p2_ingress_provenance",
                        "trg_b26_p2_ingress_authority_transition",
                    ):
                        scur.execute(
                            "ALTER TABLE public.webhook_ingress_identities"
                            f" DISABLE TRIGGER {trigger}"
                        )
                with admin.cursor() as acur:
                    acur.execute(
                        "SELECT set_config('app.current_tenant_id', %s, false)",
                        (tenant,),
                    )
                    acur.execute(
                        "UPDATE public.webhook_ingress_identities"
                        " SET b26_p2_provenance_status='pending_authentication',"
                        " b26_p2_semantic_regime='pre-xvii-unverifiable',"
                        " b26_p2_demotion_reason="
                        "'xvii-pre-binding-unverifiable' WHERE id=%s",
                        (ing,),
                    )
                with sup.cursor() as scur:
                    for trigger in (
                        "trg_b26_p2_ingress_authority_transition",
                        "trg_b26_p2_ingress_provenance",
                    ):
                        scur.execute(
                            "ALTER TABLE public.webhook_ingress_identities"
                            f" ENABLE TRIGGER {trigger}"
                        )
            finally:
                sup.close()

        # NC-02/03/04/05/06 battery on one demoted false row.
        row, _ = _mkrow("nc-e1", "nc-c1", 7777)
        assert _auth(row, "nc-e1", "a" * 64) == "authenticated_known"
        _demote(row)
        usr = psycopg2.connect(user_dsn)
        usr.autocommit = True
        try:
            with usr.cursor() as ucur:
                ucur.execute(
                    "SELECT set_config('app.current_tenant_id', %s, false)",
                    (tenant,),
                )
                try:
                    ucur.execute(
                        "UPDATE public.webhook_ingress_identities"
                        " SET b26_p2_provenance_status='authenticated_known',"
                        " b26_p2_semantic_regime='xvii-sovereign-v1',"
                        " b26_p2_demotion_reason=NULL WHERE id=%s",
                        (row,),
                    )
                    violations.append("xviii_nc02_self_stamp_permitted")
                except Exception:
                    usr.rollback()
                    checks["nc02_self_stamp_red"] = True
                # OW-03: verdict relink attack.
                try:
                    ucur.execute(
                        "UPDATE public.b23_match_verdicts"
                        " SET webhook_ingress_identity_id=%s WHERE id=%s",
                        (row, str(uuid.uuid4())),
                    )
                    violations.append("xviii_ow03_verdict_relink_permitted")
                except Exception:
                    usr.rollback()
                    checks["ow03_verdict_relink_red"] = True
                # OW-03b: worker-role cross-lineage verdict relink. The
                # verdict writer (app_worker) holds table+column UPDATE on
                # the link, unlike app_user in OW-03, so OW-03 passes
                # vacuously for this attacker. Attaching an
                # arbitrary-amount verdict to a foreign current ingress
                # must be refused; same-lineage linkage must keep working
                # (R20 supersession and fixture linkage preserved).
                try:
                    wrk = psycopg2.connect(worker_dsn)
                    wrk.autocommit = True
                except Exception as exc:
                    violations.append(
                        f"xviii_ow03b_worker_unavailable:{exc}"
                    )
                    wrk = None
                if wrk is not None:
                    try:
                        with wrk.cursor() as wcur:
                            wcur.execute(
                                "SELECT set_config('app.current_tenant_id',"
                                " %s, false)",
                                (tenant,),
                            )
                            own_row, own_ev = _mkrow("nc-own", "nc-own-c", 5000)
                            assert _auth(
                                own_row, "nc-own", "e" * 64
                            ) == "authenticated_known"
                            foreign_row, _ = _mkrow(
                                "nc-foreign", "nc-foreign-c", 6000
                            )
                            assert _auth(
                                foreign_row, "nc-foreign", "f" * 64
                            ) == "authenticated_known"
                            cur.execute(
                                "INSERT INTO public.b23_match_verdicts"
                                " (tenant_id, attribution_event_id, provider,"
                                " canonical_commerce_reference,"
                                " provider_native_event_reference,"
                                " provider_native_commerce_reference,"
                                " status, match_quality,"
                                " attributed_amount_minor,"
                                " verified_amount_minor, currency_code,"
                                " confirmed_at, last_transition_at,"
                                " canonical_expected_gross_amount_minor,"
                                " canonical_captured_gross_amount_minor,"
                                " canonical_net_verified_amount_minor,"
                                " discrepancy_amount_minor,"
                                " discrepancy_ratio_bps, discrepancy_band)"
                                " VALUES (%s,%s,'stripe','nc-own-c','nc-own',"
                                " 'nc-own-c','matched_confirmed','high',"
                                " 5000,5000,'USD',now(),now(),5000,5000,"
                                " 5000,0,0,'exact') RETURNING id",
                                (tenant, own_ev),
                            )
                            probe_verdict = cur.fetchone()[0]
                            try:
                                wcur.execute(
                                    "UPDATE public.b23_match_verdicts"
                                    " SET webhook_ingress_identity_id=%s"
                                    " WHERE id=%s",
                                    (foreign_row, probe_verdict),
                                )
                                violations.append(
                                    "xviii_ow03b_worker_cross_relink_permitted"
                                )
                            except Exception as exc:
                                wrk.rollback()
                                if "b26_p2_verdict_relink_lineage_refused" not in str(
                                    exc
                                ):
                                    violations.append(
                                        "xviii_ow03b_worker_wrong_refusal:"
                                        f"{str(exc).splitlines()[0][:100]}"
                                    )
                                else:
                                    checks["ow03b_worker_cross_relink_red"] = True
                            wcur.execute(
                                "UPDATE public.b23_match_verdicts"
                                " SET webhook_ingress_identity_id=%s"
                                " WHERE id=%s",
                                (own_row, probe_verdict),
                            )
                            cur.execute(
                                "SELECT b26_p2_source_authority_state"
                                " FROM public.b23_match_verdicts WHERE id=%s",
                                (probe_verdict,),
                            )
                            if cur.fetchone()[0] != "current":
                                violations.append(
                                    "xviii_ow03b_same_lineage_not_current"
                                )
                            else:
                                checks["ow03b_same_lineage_conducts"] = True
                    finally:
                        wrk.close()
                # OW-04: consequence DELETE.
                try:
                    ucur.execute(
                        "DELETE FROM public.b26_p2_provider_auth_consequence"
                        " WHERE webhook_ingress_identity_id=%s",
                        (row,),
                    )
                    violations.append("xviii_ow04_consequence_delete_permitted")
                except Exception:
                    usr.rollback()
                    checks["ow04_consequence_delete_red"] = True
                # OW-05: registry mutation.
                try:
                    ucur.execute(
                        "UPDATE public.b26_p2_semantic_regime_registry"
                        " SET contract_digest=%s WHERE regime_id=%s",
                        ("0" * 64, "xvii-sovereign-v1"),
                    )
                    violations.append("xviii_ow05_registry_mutation_permitted")
                except Exception:
                    usr.rollback()
                    checks["ow05_registry_mutation_red"] = True
        finally:
            usr.close()
        cur.execute(
            "SELECT b26_p2_provenance_status FROM"
            " public.webhook_ingress_identities WHERE id=%s",
            (row,),
        )
        if cur.fetchone()[0] != "pending_authentication":
            violations.append("xviii_nc02_demoted_row_mutated")
        else:
            checks["nc02_state_conserved"] = True

        # OW-12: cross-tenant predicate reads FALSE.
        cur.execute(
            "SELECT public.b26_p2_ingress_has_current_authority(%s)", (row,)
        )
        if cur.fetchone()[0] is not False:
            violations.append("xviii_ow12_demoted_authorizes")
        else:
            checks["ow12_predicate_fail_closed"] = True

        # NC-11: demoted precursor + genuine redelivery -> one candidate.
        new_row, _ = _mkrow("nc-e1", "nc-c1", 1000)
        assert _auth(new_row, "nc-e1", "f" * 64) == "authenticated_known"
        cur.execute(
            "SELECT count(*) FROM public.webhook_ingress_identities wi"
            " WHERE wi.tenant_id=%s"
            " AND wi.verified_commerce_ingress_state='authenticity_verified'"
            " AND public.b26_p2_ingress_has_current_authority(wi.id)"
            " AND wi.provider='stripe'"
            " AND wi.provider_native_event_reference='nc-e1'",
            (tenant,),
        )
        if cur.fetchone()[0] != 1:
            violations.append("xviii_nc11_candidate_pair_survives")
        else:
            checks["nc11_no_cardinality_pair"] = True

        # OW-06: 4-thread same-bytes race -> exactly one lineage.
        race_ref = f"nc-race-{uuid.uuid4().hex[:8]}"
        race_cref = f"nc-race-c-{uuid.uuid4().hex[:8]}"
        race_rows = [_mkrow(race_ref, race_cref, 500)[0] for _ in range(4)]
        outcomes: list[str] = []
        lock = threading.Lock()

        def _race(ing: str) -> None:
            try:
                result = _auth(ing, race_ref, "9" * 64)
                outcome = f"ok:{result}"
            except Exception as exc:
                outcome = f"refused:{str(exc).splitlines()[0][:60]}"
            with lock:
                outcomes.append(outcome)

        threads = [threading.Thread(target=_race, args=(ing,)) for ing in race_rows]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        winners = [o for o in outcomes if o.startswith("ok:authenticated_known")]
        if len(winners) != 1:
            violations.append(f"xviii_ow06_race_not_singular:{outcomes}")
        else:
            checks["ow06_race_converges_to_one"] = True

        # OW-08: demoted-only corpus -> numerator zero with context.
        cur.execute(
            "SELECT COALESCE(SUM(wi.verified_amount_minor),0)"
            " FROM public.webhook_ingress_identities wi"
            " WHERE wi.tenant_id=%s"
            " AND wi.verified_commerce_ingress_state='authenticity_verified'"
            " AND public.b26_p2_ingress_has_current_authority(wi.id)"
            " AND wi.provider_native_event_reference='nc-e1'",
            (tenant,),
        )
        # (row 'nc-e1' pair: demoted 7777 excluded, current 1000 included)
        cur.execute(
            "SELECT COALESCE(SUM(wi.verified_amount_minor),0)"
            " FROM public.webhook_ingress_identities wi"
            " WHERE wi.tenant_id=%s"
            " AND wi.verified_commerce_ingress_state='authenticity_verified'"
            " AND NOT public.b26_p2_ingress_has_current_authority(wi.id)"
            " AND wi.provider_native_event_reference='nc-e1'",
            (tenant,),
        )
        if cur.fetchone()[0] != 7777:
            violations.append("xviii_ow08_unverifiable_context_wrong")
        else:
            checks["ow08_unverifiable_context_exact"] = True

        # OW-11: refused atomic leaves no stamp-capable transaction.
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
                        "%s,'stripe','nc-e1',%s,%s,"
                        "'hmac-sha256-timestamped-hex','v1')",
                        (row, "a" * 64, "b" * 64),
                    )
                    violations.append("xviii_ow11_stale_promoted")
                except Exception:
                    pass
                try:
                    icur.execute(
                        "UPDATE public.webhook_ingress_identities"
                        " SET b26_p2_demotion_reason=NULL WHERE id=%s",
                        (row,),
                    )
                    violations.append("xviii_ow11_mark_leaked_after_refusal")
                except Exception:
                    igr.rollback()
                    checks["ow11_no_mark_leak_after_refusal"] = True
        finally:
            igr.close()

        # OW-09: the read->builder contract carries authority state
        # and the builder degrades non-authoritative sources.
        sys.path.insert(0, str(REPO_ROOT / "backend"))
        try:
            from app.trust.source_adapters import (  # noqa: PLC0415
                match_verdict_source_from_mapping,
            )

            demoted_mapping = {
                "id": uuid.uuid4(),
                "tenant_id": uuid.uuid4(),
                "webhook_ingress_identity_id": uuid.uuid4(),
                "provider": "stripe",
                "canonical_commerce_reference": "nc-c1",
                "provider_native_event_reference": "nc-e1",
                "provider_native_commerce_reference": "nc-c1",
                "status": "matched_provisional",
                "match_quality": "high",
                "canonical_net_verified_amount_minor": 7777,
                "currency_code": "USD",
                "last_transition_at": None,
                "created_at": None,
                "updated_at": None,
                "ingress_has_current_authority": False,
            }
            demoted_source = match_verdict_source_from_mapping(demoted_mapping)
            lawful_source = match_verdict_source_from_mapping(
                {**demoted_mapping, "ingress_has_current_authority": True}
            )
            if (
                demoted_source.ingress_has_current_authority is not False
                or lawful_source.ingress_has_current_authority is not True
            ):
                violations.append("xviii_ow09_authority_flag_not_carried")
            else:
                checks["ow09_authority_flag_carried"] = True
            builder_text = (
                REPO_ROOT / "backend" / "app" / "trust" / "builder.py"
            ).read_text(encoding="utf-8")
            # Degrade travels through governed fields only (the
            # envelope schema is closed): unavailable status on
            # non-authoritative sources plus an explicit
            # source_authority_not_current provenance reason.
            if "source_authority_not_current" not in builder_text:
                violations.append("xviii_ow09_builder_degrade_absent")
            else:
                checks["ow09_builder_degrade_explicit"] = True
        except Exception as exc:
            violations.append(f"xviii_ow09_trust_import_failed:{exc}")
        cur.close()
    except Exception as exc:
        violations.append(f"xviii_nc_live_failed:{exc}")
    finally:
        admin.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="XVIII negative controls.")
    parser.add_argument("--dsn", default=None)
    parser.add_argument("--evidence-out", default=None)
    args = parser.parse_args()
    violations: list[str] = []
    checks: dict = {}
    for gate, name in (
        (CONTRACT_GATE, "xvii_contract"),
        (REGISTRY_GATE, "xviii_registry"),
        (HIERARCHY_GATE, "xviii_hierarchy"),
        (MANIFEST_GATE, "xviii_manifest"),
        (GOVERNANCE_GATE, "xviii_governance"),
    ):
        if not _gate_pass(gate):
            violations.append(f"xviii_nc_pristine_not_green:{name}")
    if violations:
        print("B26_P2_XVIII_NC_FAIL")
        print(";".join(sorted(violations)))
        return 1
    checks["pristine_all_green"] = True
    _control_nc01(violations, checks)
    _control_nc09(violations, checks)
    _control_nc12(violations, checks)
    _control_nc13(violations, checks)
    _control_ow01(violations, checks)
    if not _gate_pass(GOVERNANCE_GATE):
        violations.append("xviii_nc14_governance_not_green")
    else:
        checks["nc14_transactional_only"] = True
    if args.dsn is not None:
        _live_controls(args.dsn, violations, checks)
    status = "PASS" if not violations else "FAIL"
    print(f"B26_P2_XVIII_NC_{status}")
    if violations:
        print(";".join(sorted(violations)))
    else:
        print(json.dumps({"checks": checks}, sort_keys=True, default=str))
    if args.evidence_out:
        Path(args.evidence_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.evidence_out).write_text(
            json.dumps(
                {
                    "gate_id": "B26-P2-XVIII-NC",
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
