#!/usr/bin/env python3
"""R-0021 equivalent-effect proof: omission, containment, restoration.

A genuine signed amendment is committed through the shipping correction path
while the observer is starved by an owner grant change. The owner then removes
the amendment's signed source attestation and revenue effect and relinks the
verdict to the superseded 4,321 source. A second tenant commits an unrelated
2,600 capture. The repaired system must:

* refuse the challenged tenant's current money through every reader;
* still serve the healthy tenant a signed, current result;
* make the mandatory proof RED on that same financial universe; and
* after exact restoration of the deleted rows and verdict state, resume both
tenants and make the proof PASS again.

This is an independently chosen sibling of R-0021 G1, not a replay of the
original fixture.
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import b26_p2_xxv_falsify as F  # noqa: E402
from b26_p2_xxv_lane import load_state, sql  # noqa: E402

OUT = Path(
    os.environ.get(
        "R21_EQUIV_OUT",
        str(F.LANE_ROOT / "evidence" / "xxv-r21-equivalent-effects.json"),
    )
)


def _read(state, tenant, verdict_id, expected):
    recon_status, recon = F.read_reconciliation(state, tenant, verdict_id)
    signed = F.signed_financial_result(
        tenant, verdict_id, expected_minor=expected, expected_currency="USD"
    )
    recon = recon if isinstance(recon, dict) else {"raw": str(recon)[:300]}
    return {
        "recon_status": recon_status,
        "net": recon.get("canonical_net_verified_amount_minor"),
        "authority": recon.get("source_authority_state"),
        "attestation": recon.get("source_money_attestation_status"),
        "history": recon.get("history_integrity_status"),
        "history_reason": str(recon.get("history_integrity_reason") or "")[:300],
        "trust_status": signed.get("trust_status"),
        "signed_minor": signed.get("verified_revenue_minor"),
        "verify": signed.get("verification_status"),
        "refusal": signed.get("durable_refusal_reason"),
    }


def main() -> int:
    state = load_state()
    tenant_a = state["tenant_a"]
    tenant_b = state["tenant_b"]
    commerce = f"pi_r21eq{uuid.uuid4().hex[:12]}"
    event_a = f"evt_r21eqA{uuid.uuid4().hex[:12]}"
    event_b = f"evt_r21eqB{uuid.uuid4().hex[:12]}"
    record: dict[str, object] = {
        "artifact": state["artifact"],
        "commerce": commerce,
    }

    status, _body, _raw = F.post_stripe_envelope(
        state,
        tenant_a,
        event_reference=event_a,
        commerce_reference=commerce,
        amount=4321,
    )
    verdict_a = F.wait_verdict(tenant_a["tenant_id"], commerce, timeout_s=180)
    if verdict_a is None:
        record["error"] = "capture_verdict_missing"
        OUT.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
        return 1
    verdict_id = verdict_a["verdict_id"]
    record["capture_http"] = status
    record["verdict_id"] = verdict_id
    record["capture_observe"] = [F.observe_once(state) for _ in range(2)]
    record["capture_read"] = _read(state, tenant_a, verdict_id, 4321)

    owner_tx = [
        ("REVOKE SELECT ON public.b26_p2_adjustment_attestation FROM app_worker, app_ro", ()),
    ]
    record["observer_starve"] = F.owner_tx(owner_tx)
    status, _body, _raw = F.post_stripe_envelope(
        state,
        tenant_a,
        event_reference=event_b,
        commerce_reference=commerce,
        amount=5500,
        created=int(time.time()) + 1,
    )
    correction_status, correction_body = F.http(
        "POST",
        f"http://127.0.0.1:{F.API_PORT}/api/reconciliation/match-verdicts/{verdict_id}/corrections",
        body=json.dumps(
            {
                "provider": "stripe",
                "event_type": "payment_capture",
                "provider_native_event_reference": event_b,
                "is_gross_capture_correction": True,
            }
        ).encode(),
        headers=F.viewer_headers(state, tenant_a),
    )
    deadline = time.time() + 150
    while time.time() < deadline:
        amount = sql(
            "SELECT verified_amount_minor FROM public.b23_match_verdicts WHERE id=%s",
            (verdict_id,),
        )[0][0]
        if int(amount) == 5500:
            break
        time.sleep(2)
    rows = sql(
        "SELECT id::text, provider_native_event_reference, verified_amount_minor,"
        " b26_p2_demotion_reason FROM public.webhook_ingress_identities"
        " WHERE tenant_id=%s AND provider_native_commerce_reference=%s"
        " ORDER BY created_at",
        (tenant_a["tenant_id"], commerce),
    )
    record["amendment"] = {
        "http": status,
        "correction_http": correction_status,
        "correction_body": correction_body[:300],
        "ingress": rows,
        "verdict": sql(
            "SELECT webhook_ingress_identity_id::text, verified_amount_minor,"
            " canonical_net_verified_amount_minor FROM public.b23_match_verdicts WHERE id=%s",
            (verdict_id,),
        ),
    }
    record["observer_starved"] = [F.observe_once(state)]

    # Healthy tenant B progresses while tenant A's history is about to fail.
    commerce_b = f"pi_r21eqB{uuid.uuid4().hex[:12]}"
    status_b, _body_b, _raw_b = F.post_stripe_envelope(
        state,
        tenant_b,
        event_reference=f"evt_r21eqB{uuid.uuid4().hex[:12]}",
        commerce_reference=commerce_b,
        amount=2600,
    )
    verdict_b = F.wait_verdict(
        tenant_b["tenant_id"],
        commerce_b,
        timeout_s=180,
    )
    if verdict_b is None:
        record["error"] = "healthy_verdict_missing"
        OUT.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
        return 1
    verdict_b_id = verdict_b["verdict_id"]
    record["healthy_capture_http"] = status_b
    record["healthy_verdict_id"] = verdict_b_id

    a_id, b_id = rows[0][0], rows[1][0]
    F.owner_tx(
        [
            ("DROP TABLE IF EXISTS public.r21eq_att_backup", ()),
            ("DROP TABLE IF EXISTS public.r21eq_rev_backup", ()),
        ]
    )
    F.owner_tx(
        [
            ("SELECT set_config('app.current_tenant_id', %s, true)", (tenant_a["tenant_id"],)),
            ("CREATE TABLE public.r21eq_att_backup AS SELECT * FROM public.b26_p2_source_money_attestation WHERE webhook_ingress_identity_id=%s", (b_id,)),
            ("CREATE TABLE public.r21eq_rev_backup AS SELECT * FROM public.b23_revenue_events WHERE match_verdict_id=%s AND is_gross_capture_correction", (verdict_id,)),
            ("ALTER TABLE public.webhook_ingress_identities DISABLE TRIGGER USER", ()),
            ("ALTER TABLE public.b23_match_verdicts DISABLE TRIGGER USER", ()),
            ("ALTER TABLE public.b23_revenue_events DISABLE TRIGGER USER", ()),
            ("DELETE FROM public.b26_p2_source_money_attestation WHERE webhook_ingress_identity_id=%s", (b_id,)),
            ("DELETE FROM public.b23_revenue_events WHERE match_verdict_id=%s AND is_gross_capture_correction", (verdict_id,)),
            ("UPDATE public.webhook_ingress_identities SET b26_p2_demotion_reason=%s WHERE id=%s", (f"superseded_by_provider_amendment:{event_a}", b_id)),
            ("UPDATE public.webhook_ingress_identities SET b26_p2_demotion_reason=NULL WHERE id=%s", (a_id,)),
            ("UPDATE public.b23_match_verdicts SET webhook_ingress_identity_id=%s, verified_amount_minor=4321,"
             " canonical_captured_gross_amount_minor=4321, canonical_net_verified_amount_minor=4321,"
             " discrepancy_amount_minor=0, discrepancy_ratio_bps=0, discrepancy_band='exact',"
             " b26_p2_source_authority_state='current' WHERE id=%s", (a_id, verdict_id)),
            ("ALTER TABLE public.webhook_ingress_identities ENABLE TRIGGER USER", ()),
            ("ALTER TABLE public.b23_match_verdicts ENABLE TRIGGER USER", ()),
            ("ALTER TABLE public.b23_revenue_events ENABLE TRIGGER USER", ()),
            ("GRANT SELECT ON public.b26_p2_adjustment_attestation TO app_worker, app_ro", ()),
        ]
    )
    record["tamper_observe"] = [F.observe_once(state) for _ in range(2)]
    record["challenged_read"] = _read(state, tenant_a, verdict_id, 4321)
    record["healthy_read"] = _read(state, tenant_b, verdict_b_id, 2600)
    record["proof_before_restore"] = F.composition_proof_with_source_evidence()

    F.owner_tx(
        [
            ("SELECT set_config('app.current_tenant_id', %s, true)", (tenant_a["tenant_id"],)),
            ("ALTER TABLE public.webhook_ingress_identities DISABLE TRIGGER USER", ()),
            ("ALTER TABLE public.b23_match_verdicts DISABLE TRIGGER USER", ()),
            ("ALTER TABLE public.b23_revenue_events DISABLE TRIGGER USER", ()),
            ("INSERT INTO public.b26_p2_source_money_attestation SELECT * FROM public.r21eq_att_backup", ()),
            ("INSERT INTO public.b23_revenue_events SELECT * FROM public.r21eq_rev_backup", ()),
            ("UPDATE public.webhook_ingress_identities SET b26_p2_demotion_reason=%s WHERE id=%s", (f"superseded_by_provider_amendment:{event_b}", a_id)),
            ("UPDATE public.webhook_ingress_identities SET b26_p2_demotion_reason=NULL WHERE id=%s", (b_id,)),
            ("UPDATE public.b23_match_verdicts SET webhook_ingress_identity_id=%s, verified_amount_minor=5500,"
             " attributed_amount_minor=4321, canonical_expected_gross_amount_minor=4321,"
             " canonical_captured_gross_amount_minor=5500, canonical_net_verified_amount_minor=5500,"
             " discrepancy_amount_minor=1179, discrepancy_ratio_bps=2728,"
             " discrepancy_band='severe_gap',"
             " b26_p2_source_authority_state='current' WHERE id=%s", (b_id, verdict_id)),
            ("ALTER TABLE public.webhook_ingress_identities ENABLE TRIGGER USER", ()),
            ("ALTER TABLE public.b23_match_verdicts ENABLE TRIGGER USER", ()),
            ("ALTER TABLE public.b23_revenue_events ENABLE TRIGGER USER", ()),
            ("DROP TABLE public.r21eq_att_backup", ()),
            ("DROP TABLE public.r21eq_rev_backup", ()),
        ]
    )
    record["restored_observe"] = [F.observe_once(state) for _ in range(2)]
    record["restored_challenged_read"] = _read(state, tenant_a, verdict_id, 5500)
    record["restored_healthy_read"] = _read(state, tenant_b, verdict_b_id, 2600)
    record["proof_after_restore"] = F.composition_proof_with_source_evidence()

    challenged = record["challenged_read"]
    healthy = record["healthy_read"]
    restored = record["restored_challenged_read"]
    record["oracle"] = {
        "challenged_refused": (
            challenged["history"] == "unverifiable"
            and challenged["trust_status"] == 404
            and challenged["net"] == 4321
        ),
        "healthy_signed": (
            healthy["recon_status"] == 200
            and healthy["net"] == 2600
            and healthy["trust_status"] == 200
            and healthy["signed_minor"] == 2600
            and healthy["history"] == "verified"
        ),
        "proof_red": record["proof_before_restore"]["printed_verdict"] == "FAIL",
        "restored_signed": (
            restored["recon_status"] == 200
            and restored["net"] == 5500
            and restored["trust_status"] == 200
            and restored["signed_minor"] == 5500
            and restored["history"] == "verified"
        ),
        "proof_green_after_restore": (
            record["proof_after_restore"]["printed_verdict"] == "PASS"
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
    print(json.dumps(record["oracle"], indent=2))
    return 0 if all(record["oracle"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
