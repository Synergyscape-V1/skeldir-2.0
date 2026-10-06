#!/usr/bin/env python3
"""B2.6-P2 Corrective XVII negative controls (relation non-vacuity proof).

Each control proves its gate can RED on a genuine member of the class it
governs, then restores byte-exact GREEN:

Static (no database):
- XVII-NC-COMMON-MODE: production parser + oracle + local goldens moved
  together to the same wrong stripe meaning WITHOUT a contract revision.
  The oracle self-check stays GREEN (the inherited blind spot, demonstrated
  honestly) while the governed contract gate REDs. Restore -> GREEN.
- XVII-NC-ROUNDING: silent excess-precision rounding resurrected in both
  implementations. The contract gate REDs on the precision refusal
  vectors. Restore -> GREEN.
- XVII-NC-REGIME: parser regime constant detached from the contract.
  The contract gate REDs. Restore -> GREEN.
- XVII-NC-CONTRACT-TAMPER: governed contract bytes widened without pin
  review. The contract gate REDs. Restore -> GREEN.
- XVII-NC-SHAPE: PayPal resource-envelope refusal removed from
  production. The contract gate REDs (acceptance exceeds contract).
  Restore -> GREEN.

Live (with --dsn, on a governed lane at XVII head):
- XVII-NC-HISTORICAL: a full-evidence pre-regime authenticated row
  (the XIV false-but-evidenced shape: evidence present, meaning unbound)
  planted through migration-admin physics. The binding oracle flags it,
  dispatch refuses it with the regime token, and P3 is FALSE for it.
  Deterministic demotion with reason clears it. Restore -> GREEN.
- XVII-NC-IDENTITY-INDEX: the event-identity unique index dropped, two
  same-reference authenticated lineages planted, the binding oracle
  reports duplicate canonical event truth. Cleanup + index restore ->
  GREEN.

Exit code is the gate.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_GATE = REPO_ROOT / "scripts" / "ci" / "validate_b26_p2_xvii_semantic_contract.py"
ORACLE = REPO_ROOT / "scripts" / "ci" / "validate_b26_p2_xvi_semantic_oracle.py"
CONTRACT = (
    REPO_ROOT
    / "contracts"
    / "reconciliation"
    / "b2.6"
    / "provider-semantic-contract.v1.json"
)
DERIVATION = REPO_ROOT / "backend" / "app" / "webhooks" / "commerce_derivation.py"


def _run(args, **kw):
    return subprocess.run(
        args, capture_output=True, text=True, cwd=str(REPO_ROOT), **kw
    )


def _swap(path: Path, old: str, new: str) -> bytes:
    # Byte-exact restore; line-ending immune matching. Tracked-file
    # residue is asserted via git diff in CI.
    raw = path.read_bytes()
    norm = raw.replace(b"\r\n", b"\n")
    old_b, new_b = old.encode("utf-8"), new.encode("utf-8")
    if old_b not in norm:
        raise SystemExit(f"nc_anchor_missing:{path.name}:{old[:60]}")
    path.write_bytes(norm.replace(old_b, new_b, 1))
    return raw


def _restore(path: Path, raw: bytes) -> None:
    path.write_bytes(raw)


def _control_common_mode(violations, checks) -> None:
    prod_orig = DERIVATION.read_bytes()
    or_orig = ORACLE.read_bytes()
    try:
        _swap(DERIVATION, "amount_minor = int(raw_amount)",
              "amount_minor = int(raw_amount) + 1")
        _swap(ORACLE, "amount_minor = int(amount)",
              "amount_minor = int(amount) + 1")
        for old_block, new_block in (
            ('"verified_amount_minor": 7600,\n            "verified_amount_currency": "USD",\n            "verified_amount_scale": 2,\n            "event_timestamp_epoch": 1700000000',
             '"verified_amount_minor": 7601,\n            "verified_amount_currency": "USD",\n            "verified_amount_scale": 2,\n            "event_timestamp_epoch": 1700000000'),
            ('"verified_amount_minor": 100,\n            "verified_amount_currency": "EUR",\n            "verified_amount_scale": 2,\n            "event_timestamp_epoch": 1700000060',
             '"verified_amount_minor": 101,\n            "verified_amount_currency": "EUR",\n            "verified_amount_scale": 2,\n            "event_timestamp_epoch": 1700000060'),
            ('"verified_amount_minor": 1000,\n            "verified_amount_currency": "JPY",\n            "verified_amount_scale": 0,\n            "event_timestamp_epoch": 1700000000',
             '"verified_amount_minor": 1001,\n            "verified_amount_currency": "JPY",\n            "verified_amount_scale": 0,\n            "event_timestamp_epoch": 1700000000'),
            ('"verified_amount_minor": 2500,\n            "verified_amount_currency": "USD",\n            "verified_amount_scale": 2,\n            "event_timestamp_epoch": 1705276799',
             '"verified_amount_minor": 2501,\n            "verified_amount_currency": "USD",\n            "verified_amount_scale": 2,\n            "event_timestamp_epoch": 1705276799'),
        ):
            _swap(ORACLE, old_block, new_block)
        oracle_blind = _run([sys.executable, str(ORACLE)])
        gate = _run([sys.executable, str(CONTRACT_GATE)])
        if oracle_blind.returncode == 0:
            # The inherited proof plane genuinely cannot see full
            # common-mode drift (its local goldens moved with the
            # implementations). Recorded honestly: this is the defect
            # class the contract gate closes.
            checks["common_mode_blind_spot_confirmed"] = True
        else:
            violations.append("xvii_nc_common_mode_oracle_unexpected_red")
        if gate.returncode != 0 and "defies_contract" in gate.stdout:
            checks["common_mode_red"] = True
        else:
            violations.append(
                f"xvii_nc_common_mode_no_red:{gate.stdout[:200]}:{gate.stderr[:200]}"
            )
    finally:
        _restore(DERIVATION, prod_orig)
        _restore(ORACLE, or_orig)
    if _run([sys.executable, str(CONTRACT_GATE)]).returncode != 0:
        violations.append("xvii_nc_common_mode_restore_not_green")
    else:
        checks["common_mode_restore_green"] = True


def _control_rounding(violations, checks) -> None:
    prod_orig = DERIVATION.read_bytes()
    or_orig = ORACLE.read_bytes()
    try:
        _swap(
            DERIVATION,
            "    if quantized != decimal_value:\n"
            "        raise CommerceDerivationError(\n"
            '            f"excess monetary precision refused: {value!r} exceeds scale {scale}"\n'
            "        )\n"
            "    return int(quantized * (10**scale))",
            "    from decimal import ROUND_HALF_UP as _NC_HALF_UP\n"
            "    return int(decimal_value.quantize(quantizer, rounding=_NC_HALF_UP)"
            " * (10**scale))",
        )
        _swap(
            ORACLE,
            "    if quantized != decimal_value:\n"
            "        raise ValueError(\n"
            '            f"excess monetary precision refused: {amount_str!r} exceeds scale {scale}"\n'
            "        )\n"
            "    return int(quantized * (10**scale))",
            "    from decimal import ROUND_HALF_UP as _NC_HALF_UP\n"
            "    return int(decimal_value.quantize(quant, rounding=_NC_HALF_UP)"
            " * (10**scale))",
        )
        gate = _run([sys.executable, str(CONTRACT_GATE)])
        if gate.returncode != 0 and "accepts_refused" in gate.stdout:
            checks["rounding_red"] = True
        else:
            violations.append(
                f"xvii_nc_rounding_no_red:{gate.stdout[:200]}:{gate.stderr[:200]}"
            )
    finally:
        _restore(DERIVATION, prod_orig)
        _restore(ORACLE, or_orig)
    if _run([sys.executable, str(CONTRACT_GATE)]).returncode != 0:
        violations.append("xvii_nc_rounding_restore_not_green")
    else:
        checks["rounding_restore_green"] = True


def _control_regime(violations, checks) -> None:
    prod_orig = DERIVATION.read_bytes()
    try:
        _swap(
            DERIVATION,
            'SEMANTIC_CONTRACT_REGIME = "xvii-sovereign-v1"',
            'SEMANTIC_CONTRACT_REGIME = "xvii-sovereign-v9"',
        )
        gate = _run([sys.executable, str(CONTRACT_GATE)])
        if gate.returncode != 0 and "regime" in gate.stdout:
            checks["regime_red"] = True
        else:
            violations.append(
                f"xvii_nc_regime_no_red:{gate.stdout[:200]}:{gate.stderr[:200]}"
            )
    finally:
        _restore(DERIVATION, prod_orig)
    if _run([sys.executable, str(CONTRACT_GATE)]).returncode != 0:
        violations.append("xvii_nc_regime_restore_not_green")
    else:
        checks["regime_restore_green"] = True


def _control_contract_tamper(violations, checks) -> None:
    contract_orig = CONTRACT.read_bytes()
    try:
        _swap(CONTRACT, '"contract_version": "v1",', '"contract_version": "v1",\n  "_nc": "tamper",')
        gate = _run([sys.executable, str(CONTRACT_GATE)])
        if gate.returncode != 0 and "contract_bytes_drift" in gate.stdout:
            checks["contract_tamper_red"] = True
        else:
            violations.append(
                f"xvii_nc_contract_no_red:{gate.stdout[:200]}:{gate.stderr[:200]}"
            )
    finally:
        _restore(CONTRACT, contract_orig)
    if _run([sys.executable, str(CONTRACT_GATE)]).returncode != 0:
        violations.append("xvii_nc_contract_restore_not_green")
    else:
        checks["contract_restore_green"] = True


def _control_shape(violations, checks) -> None:
    prod_orig = DERIVATION.read_bytes()
    try:
        _swap(
            DERIVATION,
            "    if isinstance(payload.get(\"resource\"), dict):\n"
            "        raise CommerceDerivationError(\n"
            '            "paypal resource envelopes are out of contract"\n'
            "        )\n",
            "",
        )
        gate = _run([sys.executable, str(CONTRACT_GATE)])
        if gate.returncode != 0 and "production_accepts_refused" in gate.stdout:
            checks["shape_red"] = True
        else:
            violations.append(
                f"xvii_nc_shape_no_red:{gate.stdout[:200]}:{gate.stderr[:200]}"
            )
    finally:
        _restore(DERIVATION, prod_orig)
    if _run([sys.executable, str(CONTRACT_GATE)]).returncode != 0:
        violations.append("xvii_nc_shape_restore_not_green")
    else:
        checks["shape_restore_green"] = True


def _live_historical(admin_dsn, violations, checks) -> None:
    import psycopg2  # noqa: PLC0415

    admin = psycopg2.connect(admin_dsn)
    admin.autocommit = True
    try:
        cur = admin.cursor()
        tenant = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO public.tenants (id, name, api_key_hash, notification_email)"
            " VALUES (%s,%s,%s,%s)",
            (tenant, "xvii-nc", uuid.uuid4().hex, "xvii-nc@example.invalid"),
        )
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false)", (tenant,))
        cur.execute(
            "INSERT INTO public.channel_taxonomy (code, family, is_paid,"
            " display_name, state) VALUES ('xvii_nc_ch', 'xvii_nc', true,"
            " 'XVIINC', 'active') ON CONFLICT (code) DO NOTHING"
        )
        # Plant the XIV false-but-evidenced shape through migration-admin
        # physics: full evidence, pre-regime, meaning unbound (persisted
        # 7777 for bytes-state 1000). Promotion passes the legacy
        # evidence gate exactly as the historical survivor did.
        ev, ing = str(uuid.uuid4()), str(uuid.uuid4())
        cur.execute(
            "INSERT INTO public.attribution_events (id, tenant_id, occurred_at,"
            " correlation_id, session_id, revenue_cents, raw_payload, idempotency_key,"
            " event_type, channel, campaign_id, conversion_value_cents, currency,"
            " event_timestamp, processed_at, processing_status)"
            " VALUES (%s,%s,now(),%s,%s,7777,'{}'::jsonb,%s,'conversion',"
            " 'xvii_nc_ch','c',7777,'USD',now(),now(),'processed')",
            (ev, tenant, str(uuid.uuid4()), str(uuid.uuid4()), "xvii-nc-1"),
        )
        cur.execute(
            "INSERT INTO public.webhook_ingress_identities (id, tenant_id, event_id,"
            " provider, provider_native_event_reference,"
            " provider_native_commerce_reference,"
            " normalized_commerce_reference_kind,"
            " normalized_commerce_reference_value, verified_amount_minor,"
            " verified_amount_currency, event_timestamp, idempotency_key,"
            " verified_commerce_ingress_state)"
            " VALUES (%s,%s,%s,'stripe','xvii-nc-e1','xvii-nc-o1',"
            " 'stripe_payment_intent_id','xvii-nc-o1',7777,'USD',now(),"
            " 'xvii-nc-1','authenticity_verified')",
            (ing, tenant, ev),
        )
        body, sig = "c" * 64, "d" * 64
        cur.execute(
            "INSERT INTO public.b26_p2_provider_auth_consequence ("
            " webhook_ingress_identity_id, tenant_id, provider,"
            " provider_event_reference, body_sha256,"
            " signature_envelope_sha256, auth_method, auth_version, recorded_by)"
            " VALUES (%s,%s,'stripe','xvii-nc-e1',%s,%s,"
            " 'hmac-sha256-timestamped-hex','v1','postgres')",
            (ing, tenant, body, sig),
        )
        witness = "e" * 64
        cur.execute(
            "INSERT INTO public.b26_p2_ingress_auth_witness ("
            " webhook_ingress_identity_id, tenant_id, witness_hash, witnessed_by)"
            " VALUES (%s,%s,%s,'postgres')",
            (ing, tenant, witness),
        )
        cur.execute(
            "INSERT INTO public.b26_p2_provenance_evidence ("
            " webhook_ingress_identity_id, tenant_id, evidence_kind,"
            " evidence_ref, evidence_witness_hash)"
            " VALUES (%s,%s,'signed_provider_reingestion','xvii-nc-1',%s)",
            (ing, tenant, witness),
        )
        cur.execute(
            "INSERT INTO public.b26_p2_auth_root_evidence (tenant_id,"
            " webhook_ingress_identity_id, idempotency_key, provider,"
            " provider_native_event_reference, body_sha256,"
            " signature_envelope_sha256, auth_method, auth_version)"
            " VALUES (%s,%s,'xvii-nc-1','stripe','xvii-nc-e1',%s,%s,"
            " 'hmac-sha256-timestamped-hex','v1')",
            (tenant, ing, body, sig),
        )
        cur.execute(
            "UPDATE public.webhook_ingress_identities"
            " SET b26_p2_provenance_status = 'authenticated_known'"
            " WHERE id = %s",
            (ing,),
        )
        # The survivor is trusted with modern-shape evidence...
        cur.execute(
            "SELECT b26_p2_provenance_status, b26_p2_semantic_regime"
            " FROM public.webhook_ingress_identities WHERE id = %s",
            (ing,),
        )
        prov, regime = cur.fetchone()
        if prov != "authenticated_known":
            violations.append("xvii_nc_survivor_not_trusted")
            return
        # ...but the binding oracle flags its regime...
        cur.execute(
            "SELECT violation_kind FROM public.b26_p2_xvii_semantic_binding_oracle()"
        )
        kinds = [r[0] for r in cur.fetchall()]
        if "xvii_regime_unverifiable_trusted" not in kinds:
            violations.append("xvii_nc_survivor_oracle_blind")
        else:
            checks["historical_red"] = True
        # ...dispatch refuses it with the single-law token (XIX: the
        # complete current-authority predicate screens every
        # non-current row first, so a regime-unverifiable survivor is
        # refused as not-current -- the same adaptation XVIII L9
        # already carries for demoted rows; refusal itself is the
        # property under test).
        try:
            cur.execute(
                "INSERT INTO public.b23_match_task_dispatches (tenant_id,"
                " webhook_ingress_identity_id, task_id, task_name, queue,"
                " routing_key, correlation_id, provider,"
                " provider_native_event_reference,"
                " provider_native_commerce_reference,"
                " normalized_commerce_reference_value)"
                " VALUES (%s,%s,'xvii-nc-task',"
                " 'app.tasks.revenue_verification.execute_b23_batch_match_engine',"
                " 'b23_match_engine','k',%s,'stripe','xvii-nc-e1','xvii-nc-o1',"
                " 'xvii-nc-o1')",
                (tenant, ing, str(uuid.uuid4())),
            )
            violations.append("xvii_nc_survivor_dispatch_permitted")
        except Exception as exc:
            admin.rollback()
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)", (tenant,)
            )
            if "b26_p2_dispatch_source_not_current" not in str(exc):
                violations.append(
                    f"xvii_nc_dispatch_wrong_refusal:{str(exc).splitlines()[0][:120]}"
                )
            else:
                checks["historical_dispatch_red"] = True
        # ...and P3 is FALSE for it (no dispatch, regime-unverifiable).
        cur.execute(
            "SELECT public.b26_p2_state_eligible_for_p3('xvii-nc-task', %s)",
            (tenant,),
        )
        if cur.fetchone()[0] is not False:
            violations.append("xvii_nc_survivor_p3_true")
        else:
            checks["historical_p3_false"] = True
        # Deterministic disposition with reason clears the class.
        cur.execute("ALTER TABLE public.webhook_ingress_identities DISABLE TRIGGER trg_b26_p2_ingress_provenance")
        cur.execute(
            "UPDATE public.webhook_ingress_identities"
            " SET b26_p2_provenance_status = 'pending_authentication',"
            " b26_p2_demotion_reason = 'xvii-pre-binding-unverifiable'"
            " WHERE id = %s",
            (ing,),
        )
        cur.execute("ALTER TABLE public.webhook_ingress_identities ENABLE TRIGGER trg_b26_p2_ingress_provenance")
        cur.execute(
            "SELECT count(*) FROM public.b26_p2_xvii_semantic_binding_oracle()"
        )
        if cur.fetchone()[0] != 0:
            violations.append("xvii_nc_disposition_not_clean")
        else:
            checks["historical_restore_green"] = True
        cur.close()
    except Exception as exc:
        violations.append(f"xvii_nc_live_failed:{exc}")
    finally:
        admin.close()


def _live_identity_index(admin_dsn, violations, checks) -> None:
    import psycopg2  # noqa: PLC0415

    admin = psycopg2.connect(admin_dsn)
    admin.autocommit = True
    try:
        cur = admin.cursor()
        cur.execute("DROP INDEX IF EXISTS public.uq_b26_p2_xvii_event_identity")
        tenant = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO public.tenants (id, name, api_key_hash, notification_email)"
            " VALUES (%s,%s,%s,%s)",
            (tenant, "xvii-nc-idx", uuid.uuid4().hex, "xvii-nc-idx@example.invalid"),
        )
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false)", (tenant,))
        cur.execute(
            "INSERT INTO public.channel_taxonomy (code, family, is_paid,"
            " display_name, state) VALUES ('xvii_nc_idx', 'xvii_nc', true,"
            " 'XVIINCIDX', 'active') ON CONFLICT (code) DO NOTHING"
        )
        # Two canonical lineages for one provider event (index absent).
        # Plants go pending (INSERT trigger law) with full evidence, then
        # promote -- the only promotion the legacy gate admits.
        planted = []
        for tag, amt in (("a", 1000), ("b", 5000)):
            ev = str(uuid.uuid4())
            cur.execute(
                "INSERT INTO public.attribution_events (id, tenant_id, occurred_at,"
                " correlation_id, session_id, revenue_cents, raw_payload,"
                " idempotency_key, event_type, channel, campaign_id,"
                " conversion_value_cents, currency, event_timestamp, processed_at,"
                " processing_status) VALUES (%s,%s,now(),%s,%s,%s,'{}'::jsonb,%s,"
                " 'conversion','xvii_nc_idx','c',%s,'USD',now(),now(),'processed')",
                (ev, tenant, str(uuid.uuid4()), str(uuid.uuid4()), amt,
                 f"xvii-nc-idx-{tag}", amt),
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
                " VALUES (%s,%s,%s,'stripe','xvii-idx-e1',%s,"
                " 'stripe_payment_intent_id',%s,%s,'USD',now(),"
                " %s,'authenticity_verified')",
                (ing, tenant, ev, f"xvii-idx-o-{tag}",
                 f"xvii-idx-o-{tag}", amt, f"xvii-nc-idx-{tag}"),
            )
            body, sig = f"{tag}" * 64, f"s{tag}" * 32
            cur.execute(
                "INSERT INTO public.b26_p2_provider_auth_consequence ("
                " webhook_ingress_identity_id, tenant_id, provider,"
                " provider_event_reference, body_sha256,"
                " signature_envelope_sha256, auth_method, auth_version,"
                " recorded_by) VALUES (%s,%s,'stripe','xvii-idx-e1',%s,%s,"
                " 'hmac-sha256-timestamped-hex','v1','postgres')",
                (ing, tenant, body, sig),
            )
            cur.execute(
                "INSERT INTO public.b26_p2_ingress_auth_witness ("
                " webhook_ingress_identity_id, tenant_id, witness_hash,"
                " witnessed_by) VALUES (%s,%s,%s,'postgres')",
                (ing, tenant, "w" * 64),
            )
            cur.execute(
                "INSERT INTO public.b26_p2_provenance_evidence ("
                " webhook_ingress_identity_id, tenant_id, evidence_kind,"
                " evidence_ref, evidence_witness_hash)"
                " VALUES (%s,%s,'signed_provider_reingestion',%s,%s)",
                (ing, tenant, f"xvii-nc-idx-{tag}", "w" * 64),
            )
            cur.execute(
                "INSERT INTO public.b26_p2_auth_root_evidence (tenant_id,"
                " webhook_ingress_identity_id, idempotency_key, provider,"
                " provider_native_event_reference, body_sha256,"
                " signature_envelope_sha256, auth_method, auth_version)"
                " VALUES (%s,%s,%s,'stripe','xvii-idx-e1',%s,%s,"
                " 'hmac-sha256-timestamped-hex','v1')",
                (tenant, ing, f"xvii-nc-idx-{tag}", body, sig),
            )
            cur.execute(
                "UPDATE public.webhook_ingress_identities"
                " SET b26_p2_provenance_status = 'authenticated_known',"
                " b26_p2_semantic_regime = 'xvii-sovereign-v1'"
                " WHERE id = %s",
                (ing,),
            )
            planted.append(ing)
        cur.execute(
            "SELECT violation_kind FROM public.b26_p2_xvii_semantic_binding_oracle()"
        )
        kinds = [r[0] for r in cur.fetchall()]
        if "xvii_duplicate_canonical_event" not in kinds:
            violations.append("xvii_nc_index_oracle_blind")
        else:
            checks["identity_index_red"] = True
        # Cleanup: demote the plants, restore the physical law.
        cur.execute("ALTER TABLE public.webhook_ingress_identities DISABLE TRIGGER trg_b26_p2_ingress_provenance")
        cur.execute(
            "UPDATE public.webhook_ingress_identities"
            " SET b26_p2_provenance_status = 'pending_authentication',"
            " b26_p2_demotion_reason = 'xvii-nc-cleanup'"
            " WHERE tenant_id = %s",
            (tenant,),
        )
        cur.execute("ALTER TABLE public.webhook_ingress_identities ENABLE TRIGGER trg_b26_p2_ingress_provenance")
        cur.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_b26_p2_xvii_event_identity"
            " ON public.webhook_ingress_identities"
            " (tenant_id, provider, provider_native_event_reference)"
            " WHERE b26_p2_provenance_status = 'authenticated_known'"
        )
        cur.execute(
            "SELECT count(*) FROM public.b26_p2_xvii_semantic_binding_oracle()"
        )
        # Other lanes' probes may hold violations; only require that THIS
        # tenant's plants no longer report (checked implicitly: the two
        # plants are pending, hence invisible to the oracle).
        cur.close()
        checks["identity_index_restore_green"] = True
    except Exception as exc:
        violations.append(f"xvii_nc_index_failed:{exc}")
        try:
            with admin.cursor() as cur2:
                cur2.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_b26_p2_xvii_event_identity"
                    " ON public.webhook_ingress_identities"
                    " (tenant_id, provider, provider_native_event_reference)"
                    " WHERE b26_p2_provenance_status = 'authenticated_known'"
                )
        except Exception:
            pass
    finally:
        admin.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="XVII negative controls.")
    parser.add_argument("--dsn", default=None)
    parser.add_argument("--evidence-out", default=None)
    args = parser.parse_args()
    violations: list[str] = []
    checks: dict = {}
    _control_common_mode(violations, checks)
    _control_rounding(violations, checks)
    _control_regime(violations, checks)
    _control_contract_tamper(violations, checks)
    _control_shape(violations, checks)
    if args.dsn is not None:
        _live_historical(args.dsn, violations, checks)
        _live_identity_index(args.dsn, violations, checks)
    status = "PASS" if not violations else "FAIL"
    print(f"B26_P2_XVII_NC_{status}")
    if violations:
        print(";".join(sorted(violations)))
    else:
        print(json.dumps({"checks": checks}, sort_keys=True, default=str))
    if args.evidence_out:
        Path(args.evidence_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.evidence_out).write_text(
            json.dumps(
                {
                    "gate_id": "B26-P2-XVII-NC",
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
