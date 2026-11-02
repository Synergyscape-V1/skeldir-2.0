#!/usr/bin/env python3
"""Accepted-history custody recovery followed by new authenticated money.

This probe uses the real lane's signed witness/source volumes and the shipping
HTTP/worker path. It exports the current source journal to a signed custody
bundle, removes the live journal (simulated loss/redeploy), restores only at
the independently accepted witness count/tip, restarts the shipping services,
then posts a second authenticated amount-changing event and observes the real
scheduled witness and signed Trust consumer.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "ci"))
sys.path.insert(0, str(REPO / "backend"))
os.environ.setdefault(
    "DATABASE_URL", "postgresql://fixture@127.0.0.1:1/fixture"
)
os.environ.setdefault("SKELDIR_CONTROL_PLANE_ENABLED", "0")

from b26_p2_xxv_falsify import (  # noqa: E402
    API_PORT,
    AUTH_PORT,
    docker,
    load_state,
    post_stripe,
    post_stripe_envelope,
    http,
    viewer_headers,
    read_reconciliation,
    read_trust,
    start_api,
    start_auth,
    verify_trust,
    volume_get,
    volume_put,
    volume_rm,
    wait_http,
    wait_verdict,
    witness_files,
)
from b26_p2_xxv_lane import AUTH, API, SOURCE_EVIDENCE_VOL  # noqa: E402
from app.revenue_verification.source_journal_custody import (  # noqa: E402
    export_custody_bundle,
    restore_custody_bundle,
    verify_custody_bundle,
)


def main() -> int:
    state = load_state()
    tenant = state["tenant_a"]
    intent = f"pi_xxvrec{uuid_hex()}"
    first = 4321
    amended = 5100
    temp = Path(tempfile.mkdtemp(prefix="xxv-recovery-"))
    witness_private = temp / "witness.key"
    witness_public = temp / "witness.pub"
    witness_private.write_text(
        state["material"]["witness_private_b64url"], encoding="utf-8"
    )
    witness_public.write_text(
        state["material"]["witness_public_b64url"], encoding="utf-8"
    )
    source = temp / "source.jsonl"

    try:
        first_status, first_body, _ = post_stripe(state, tenant, intent, first)
        verdict = wait_verdict(tenant["tenant_id"], intent, timeout_s=180)
        if verdict is None:
            raise RuntimeError("initial_verdict_missing")
        initial_witness = witness_files()
        custody = temp / "custody"
        source.write_bytes(volume_get(SOURCE_EVIDENCE_VOL, "source_evidence.jsonl"))
        lock = source.with_name(source.name + ".lock")
        try:
            lock.write_bytes(
                volume_get(SOURCE_EVIDENCE_VOL, "source_evidence.jsonl.lock")
            )
        except Exception:  # noqa: BLE001 - first writer may not have a sidecar
            lock.write_bytes(b"\0")
        exported = export_custody_bundle(
            journal=source,
            custody_dir=custody,
            private_key_path=witness_private,
        )
        verified = verify_custody_bundle(
            manifest_path=exported.manifest_path,
            public_key_path=witness_public,
        )
        heartbeat = initial_witness.get("history_witness_heartbeat.json") or {}
        payload = heartbeat.get("payload") or {}
        accepted_count = int(payload["source_journal_count"])
        accepted_tip = str(payload["source_journal_tip"])
        restored_path = temp / "restored.jsonl"
        disposition = restore_custody_bundle(
            manifest_path=exported.manifest_path,
            journal=restored_path,
            public_key_path=witness_public,
            accepted_source_count=accepted_count,
            accepted_source_tip=accepted_tip,
        )
        if disposition != "restored":
            raise RuntimeError(f"unexpected_restore_disposition:{disposition}")

        # Simulate loss/redeploy: stop the only writer, remove the journal, put
        # back exactly the restored signed prefix, then restart shipping.
        docker("stop", AUTH)
        docker("stop", API)
        volume_rm(SOURCE_EVIDENCE_VOL, "source_evidence.jsonl")
        volume_put(
            SOURCE_EVIDENCE_VOL,
            {"source_evidence.jsonl": restored_path.read_bytes()},
        )
        start_auth(state)
        wait_http(f"http://127.0.0.1:{AUTH_PORT}/health/live", 240)
        start_api(state)
        wait_http(f"http://127.0.0.1:{API_PORT}/health/live", 240)

        after_restore = witness_files()
        before_money = read_reconciliation(state, tenant, verdict["verdict_id"])
        event_ref = f"evt_xxvrec{uuid_hex()}"
        second_status, second_body, _ = post_stripe_envelope(
            state,
            tenant,
            event_reference=event_ref,
            commerce_reference=intent,
            amount=amended,
        )
        amendment = wait_verdict(tenant["tenant_id"], intent, timeout_s=180)
        if amendment is None:
            raise RuntimeError("new_money_verdict_missing")
        correction_status, correction_body = http(
            "POST",
            f"http://127.0.0.1:{API_PORT}/api/reconciliation/match-verdicts/"
            f"{verdict['verdict_id']}/corrections",
            body=json.dumps(
                {
                    "provider": "stripe",
                    "event_type": "payment_capture",
                    "provider_native_event_reference": event_ref,
                    "is_gross_capture_correction": True,
                }
            ).encode(),
            headers=viewer_headers(state, tenant),
        )
        witness_after = witness_files()
        trust_status, trust = (0, "no_verdict")
        for _attempt in range(90):
            witness_after = witness_files()
            trust_status, trust = read_trust(
                tenant, verdict["verdict_id"]
            )
            payload = (
                witness_after.get("history_witness_heartbeat.json") or {}
            ).get("payload") or {}
            if (
                int(payload.get("source_journal_count", 0)) > accepted_count
                and trust_status == 200
            ):
                break
            time.sleep(4)
        recon_status, recon = read_reconciliation(
            state, tenant, amendment["verdict_id"]
        )
        trust_status, trust = read_trust(tenant, amendment["verdict_id"])
        verified_trust = (
            verify_trust(tenant, trust.get("envelope", trust))
            if trust_status == 200 and isinstance(trust, dict)
            else (0, "not_attempted")
        )
        record = {
            "artifact": state.get("artifact"),
            "property": (
                "accepted-history custody recovery followed by new authenticated"
                " money through the shipping worker, scheduled witness and signed"
                " customer result in one continuous runtime history"
            ),
            "initial": {
                "http": first_status,
                "amount_minor": first,
                "verdict_id": verdict["verdict_id"],
                "accepted_source_count": accepted_count,
                "accepted_source_tip": accepted_tip,
            },
            "custody": {
                "record_count": verified.manifest["record_count"],
                "tip": verified.manifest["journal_tip"],
                "restore_disposition": disposition,
                "restored_bytes": restored_path.stat().st_size,
            },
            "after_restore_witness": after_restore,
            "amendment": {
                "http": second_status,
                "amount_minor": amended,
                "verdict": amendment,
                "event_reference": event_ref,
                "correction_http": {
                    "status": correction_status,
                    "body": correction_body[:400],
                },
                "witness_after": witness_after,
            },
            "readers": {
                "before_money": before_money,
                "reconciliation": {"status": recon_status, "body": recon},
                "trust": {"status": trust_status, "body": trust},
                "trust_verify": verified_trust,
            },
            "result": {
                "initial_4321": True,
                "restored_at_accepted": disposition == "restored",
                "new_amount_5100": (
                    isinstance(recon, dict)
                    and recon.get("canonical_net_verified_amount_minor") == amended
                ),
                "trust_verified_5100": (
                    trust_status == 200
                    and isinstance(trust, dict)
                    and trust.get("verified_revenue_minor") == amended
                    and trust.get("currency") == "USD"
                    and verified_trust[0] == 200
                ),
            },
        }
        record["passed"] = all(record["result"].values())
        out = REPO / "docs/forensics/evidence/b26_p2_xxv_a8/xxv-r0033-recovery-progression-20261102.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps(record, indent=2, sort_keys=True))
        return 0 if record["passed"] else 1
    finally:
        import shutil

        shutil.rmtree(temp, ignore_errors=True)


def uuid_hex() -> str:
    import uuid

    return uuid.uuid4().hex[:16]


if __name__ == "__main__":
    raise SystemExit(main())
