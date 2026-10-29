#!/usr/bin/env python3
"""R-0021 addendum: presence is not currentness.

Two isolated variants retain every committed source fact. An owner changes only
mutable demotion flags and the verdict link so the superseded 4,321 source is
presented again. The first variant attacks before the amendment has ever been
observed; the second attacks after a signed checkpoint has witnessed it. In
both, an unrelated same-tenant capture is added and a healthy tenant must still
make progress. The current source is derived from the committed signed facts,
not from the mutable flags or link. Exact restoration must make both tenants
and both readers usable again, and the mandatory proof must be RED in between.
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
from b26_p2_xxv_lane import load_state  # noqa: E402

OUT = Path(
    os.environ.get(
        "R21_CURRENT_OUT",
        str(F.LANE_ROOT / "evidence" / "xxv-r21-currentness.json"),
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


def _capture(state, tenant, amount: int, prefix: str) -> tuple[str, str]:
    commerce = f"pi_{prefix}{uuid.uuid4().hex[:12]}"
    status, _body, _raw = F.post_stripe_envelope(
        state,
        tenant,
        event_reference=f"evt_{prefix}{uuid.uuid4().hex[:12]}",
        commerce_reference=commerce,
        amount=amount,
    )
    verdict = F.wait_verdict(tenant["tenant_id"], commerce, timeout_s=180)
    if verdict is None:
        raise RuntimeError(f"verdict_missing:{prefix}:{status}")
    return commerce, verdict["verdict_id"]


def _amend(state, tenant, commerce: str, amount: int) -> tuple[str, str]:
    event = f"evt_am{uuid.uuid4().hex[:12]}"
    status, _body, _raw = F.post_stripe_envelope(
        state,
        tenant,
        event_reference=event,
        commerce_reference=commerce,
        amount=amount,
        created=int(time.time()) + 1,
    )
    verdict = F.wait_verdict(tenant["tenant_id"], commerce, timeout_s=180)
    if verdict is None:
        raise RuntimeError(f"amendment_verdict_missing:{status}")
    correction_status, correction_body = F.http(
        "POST",
        f"http://127.0.0.1:{F.API_PORT}/api/reconciliation/match-verdicts/{verdict['verdict_id']}/corrections",
        body=json.dumps(
            {
                "provider": "stripe",
                "event_type": "payment_capture",
                "provider_native_event_reference": event,
                "is_gross_capture_correction": True,
            }
        ).encode(),
        headers=F.viewer_headers(state, tenant),
    )
    deadline = time.time() + 150
    rows = []
    while time.time() < deadline:
        rows = F.sql(
            "SELECT id::text, provider_native_event_reference,"
            " verified_amount_minor, b26_p2_demotion_reason"
            " FROM public.webhook_ingress_identities"
            " WHERE tenant_id=%s AND provider_native_commerce_reference=%s"
            " ORDER BY created_at",
            (tenant["tenant_id"], commerce),
        )
        verdict_amount = F.sql(
            "SELECT canonical_net_verified_amount_minor FROM public.b23_match_verdicts"
            " WHERE id=%s",
            (verdict["verdict_id"],),
        )[0][0]
        if len(rows) >= 2 and int(rows[-1][2]) == amount and int(verdict_amount) == amount:
            break
        time.sleep(2)
    return event, rows[-1][0]


def _tamper(state, tenant, verdict_id: str, old_ingress: str, new_ingress: str) -> None:
    F.owner_tx(
        [
            ("SELECT set_config('app.current_tenant_id', %s, true)", (tenant["tenant_id"],)),
            ("ALTER TABLE public.webhook_ingress_identities DISABLE TRIGGER USER", ()),
            ("ALTER TABLE public.b23_match_verdicts DISABLE TRIGGER USER", ()),
            ("UPDATE public.webhook_ingress_identities SET b26_p2_demotion_reason=%s WHERE id=%s", ("owner_currentness_tamper", new_ingress)),
            ("UPDATE public.webhook_ingress_identities SET b26_p2_demotion_reason=NULL WHERE id=%s", (old_ingress,)),
            ("UPDATE public.b23_match_verdicts SET webhook_ingress_identity_id=%s, verified_amount_minor=4321,"
             " attributed_amount_minor=4321, canonical_expected_gross_amount_minor=4321,"
             " canonical_captured_gross_amount_minor=4321, canonical_net_verified_amount_minor=4321,"
             " discrepancy_amount_minor=0, discrepancy_ratio_bps=0, discrepancy_band='exact',"
             " b26_p2_source_authority_state='current' WHERE id=%s", (old_ingress, verdict_id)),
            ("ALTER TABLE public.webhook_ingress_identities ENABLE TRIGGER USER", ()),
            ("ALTER TABLE public.b23_match_verdicts ENABLE TRIGGER USER", ()),
        ]
    )


def _restore(state, tenant, verdict_id: str, old_ingress: str, new_ingress: str) -> None:
    F.owner_tx(
        [
            ("SELECT set_config('app.current_tenant_id', %s, true)", (tenant["tenant_id"],)),
            ("ALTER TABLE public.webhook_ingress_identities DISABLE TRIGGER USER", ()),
            ("ALTER TABLE public.b23_match_verdicts DISABLE TRIGGER USER", ()),
            ("UPDATE public.webhook_ingress_identities SET b26_p2_demotion_reason=%s WHERE id=%s", ("superseded_by_provider_amendment", old_ingress)),
            ("UPDATE public.webhook_ingress_identities SET b26_p2_demotion_reason=NULL WHERE id=%s", (new_ingress,)),
            ("UPDATE public.b23_match_verdicts SET webhook_ingress_identity_id=%s, verified_amount_minor=5500,"
             " attributed_amount_minor=4321, canonical_expected_gross_amount_minor=4321,"
             " canonical_captured_gross_amount_minor=5500, canonical_net_verified_amount_minor=5500,"
             " discrepancy_amount_minor=1179, discrepancy_ratio_bps=2728,"
             " discrepancy_band='severe_gap',"
             " b26_p2_source_authority_state='current' WHERE id=%s", (new_ingress, verdict_id)),
            ("ALTER TABLE public.webhook_ingress_identities ENABLE TRIGGER USER", ()),
            ("ALTER TABLE public.b23_match_verdicts ENABLE TRIGGER USER", ()),
        ]
    )


def _variant(state, tenant, label: str, *, witness_amendment: bool) -> dict:
    commerce, verdict_id = _capture(state, tenant, 4321, f"cur{label}")
    F.observe_once(state)
    _event, new_ingress = _amend(state, tenant, commerce, 5500)
    if witness_amendment:
        F.observe_once(state)
    # Same-tenant unrelated growth after the amendment, before the attack.
    _growth_commerce, growth_verdict = _capture(state, tenant, 1234, f"grow{label}")
    rows = F.sql(
        "SELECT id::text, verified_amount_minor, b26_p2_demotion_reason"
        " FROM public.webhook_ingress_identities"
        " WHERE tenant_id=%s AND provider_native_commerce_reference=%s"
        " ORDER BY created_at",
        (tenant["tenant_id"], commerce),
    )
    old_ingress = rows[0][0]
    _tamper(state, tenant, verdict_id, old_ingress, new_ingress)
    observe = [F.observe_once(state) for _ in range(2)]
    challenged = _read(state, tenant, verdict_id, 4321)
    growth = _read(state, tenant, growth_verdict, 1234)
    proof = F.composition_proof_with_source_evidence()
    _restore(state, tenant, verdict_id, old_ingress, new_ingress)
    restored_observe = [F.observe_once(state) for _ in range(2)]
    restored = _read(state, tenant, verdict_id, 5500)
    restored_growth = _read(state, tenant, growth_verdict, 1234)
    restored_proof = F.composition_proof_with_source_evidence()
    return {
        "label": label,
        "witnessed_amendment": witness_amendment,
        "verdict_id": verdict_id,
        "growth_verdict_id": growth_verdict,
        "observe": observe,
        "challenged": challenged,
        "same_tenant_growth": growth,
        "proof": proof,
        "restored_observe": restored_observe,
        "restored": restored,
        "restored_growth": restored_growth,
        "restored_proof": restored_proof,
        "oracle": {
            "challenged_currentness_refused": (
                challenged["history"] == "unverifiable"
                and "verdict_source_not_current" in str(challenged["attestation"])
                and challenged["trust_status"] == 404
            ),
            "same_tenant_growth_refused": (
                growth["history"] == "unverifiable"
                and growth["trust_status"] == 404
            ),
            "proof_red": proof["printed_verdict"] == "FAIL",
            "restored_signed": (
                restored["recon_status"] == 200
                and restored["net"] == 5500
                and restored["trust_status"] == 200
                and restored["signed_minor"] == 5500
                and restored["history"] == "verified"
            ),
            "restored_growth_signed": (
                restored_growth["recon_status"] == 200
                and restored_growth["net"] == 1234
                and restored_growth["trust_status"] == 200
                and restored_growth["signed_minor"] == 1234
            ),
            "proof_green": restored_proof["printed_verdict"] == "PASS",
        },
    }


def main() -> int:
    state = load_state()
    tenant_a = state["tenant_a"]
    tenant_b = state["tenant_b"]
    # A healthy tenant baseline that must remain usable throughout.
    _b_commerce, b_verdict = _capture(state, tenant_b, 2600, "curB")
    F.observe_once(state)
    before_b = _read(state, tenant_b, b_verdict, 2600)

    pre = _variant(state, tenant_a, "pre", witness_amendment=False)
    witnessed = _variant(state, tenant_a, "wit", witness_amendment=True)
    # The mandatory proof's own live checks mutate and restore cells; refresh
    # the observer before judging the healthy tenant's final state.
    F.observe_once(state)
    F.observe_once(state)
    after_b = _read(state, tenant_b, b_verdict, 2600)
    record = {
        "artifact": state["artifact"],
        "healthy_tenant_before": before_b,
        "pre_observation": pre,
        "previously_witnessed": witnessed,
        "healthy_tenant_after": after_b,
        "oracle": {
            "pre": all(pre["oracle"].values()),
            "witnessed": all(witnessed["oracle"].values()),
            "healthy_before": before_b["trust_status"] == 200,
            "healthy_after": after_b["trust_status"] == 200,
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
    print(json.dumps(record["oracle"], indent=2))
    return 0 if all(record["oracle"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
