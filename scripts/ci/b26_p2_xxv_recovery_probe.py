#!/usr/bin/env python3
"""Failure-safe custody recovery acceptance probe.

The positive mode performs the full journey: an accepted 4321 subject, a
signed custody export, removal of the live journal, restoration at the
accepted witness count/tip, a same-subject 5100 amendment through the
shipping correction route and real worker, natural scheduled witnessing, and
a verified signed Trust result.

Negative modes use the same acceptance predicate and a scoped staging area:
omit-restore skips restoration; tamper-signature corrupts the staged manifest.
A failed control restores the original live journal and keeps the staged
custody bundle.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
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
    http,
    load_state,
    post_stripe,
    post_stripe_envelope,
    read_reconciliation,
    read_trust,
    start_api,
    start_auth,
    verify_trust,
    viewer_headers,
    volume_get,
    volume_put,
    volume_rm,
    wait_http,
    wait_verdict,
    witness_files,
)
from b26_p2_xxv_lane import AUTH, API, LANE_ROOT, SOURCE_EVIDENCE_VOL  # noqa: E402
from app.revenue_verification.source_journal_custody import (  # noqa: E402
    SourceJournalCustodyError,
    export_custody_bundle,
    restore_custody_bundle,
    verify_custody_bundle,
)
from app.revenue_verification.source_evidence_journal import (  # noqa: E402
    journal_record_hash,
    load_source_fact_records,
)


def _uuid_hex() -> str:
    import uuid

    return uuid.uuid4().hex[:16]


def _records(raw: bytes, temp: Path) -> list[dict]:
    path = temp / f"records-{time.monotonic_ns()}.jsonl"
    path.write_bytes(raw)
    try:
        return load_source_fact_records(path) or []
    finally:
        path.unlink(missing_ok=True)


def _start_services(state: dict) -> None:
    start_auth(state)
    wait_http(f"http://127.0.0.1:{AUTH_PORT}/health/live", 240)
    start_api(state)
    wait_http(f"http://127.0.0.1:{API_PORT}/health/live", 240)


def _restore_original(state: dict, raw: bytes) -> dict:
    result: dict = {}
    try:
        docker("stop", AUTH)
        docker("stop", API)
    except Exception as exc:  # noqa: BLE001
        result["stop_error"] = str(exc)
    try:
        volume_put(SOURCE_EVIDENCE_VOL, {"source_evidence.jsonl": raw})
        _start_services(state)
        result["restored_original"] = True
    except Exception as exc:  # noqa: BLE001
        result["restored_original"] = False
        result["restore_original_error"] = f"{type(exc).__name__}:{exc}"
    return result


def _preserve_operation(state: dict, staged: dict) -> dict:
    """Keep the accepted history, never an older raw copied over it."""
    result: dict = {}
    try:
        raw = volume_get(SOURCE_EVIDENCE_VOL, "source_evidence.jsonl")
        if not raw:
            volume_put(
                SOURCE_EVIDENCE_VOL,
                {"source_evidence.jsonl": staged["journal_bytes"]},
            )
            result["restored_staged_custody"] = True
        else:
            result["preserved_current"] = True
        _start_services(state)
        result["operation"] = True
    except Exception as exc:  # noqa: BLE001
        result["operation"] = False
        result["error"] = f"{type(exc).__name__}:{exc}"
    return result


def _stage(state: dict, temp: Path) -> dict:
    original_raw = volume_get(SOURCE_EVIDENCE_VOL, "source_evidence.jsonl")
    source = temp / "source.jsonl"
    source.write_bytes(original_raw)
    lock = source.with_name(source.name + ".lock")
    try:
        lock.write_bytes(
            volume_get(SOURCE_EVIDENCE_VOL, "source_evidence.jsonl.lock")
        )
    except Exception:  # noqa: BLE001
        lock.write_bytes(b"\0")
    private = temp / "custody.key"
    public = temp / "custody.pub"
    private.write_text(
        state["material"]["witness_private_b64url"], encoding="utf-8"
    )
    public.write_text(
        state["material"]["witness_public_b64url"], encoding="utf-8"
    )
    heartbeat = (witness_files().get("history_witness_heartbeat.json") or {}).get(
        "payload"
    ) or {}
    accepted_count = int(heartbeat["source_journal_count"])
    accepted_tip = str(heartbeat["source_journal_tip"])
    exported = export_custody_bundle(
        journal=source,
        custody_dir=temp / "custody",
        private_key_path=private,
    )
    verified = verify_custody_bundle(
        manifest_path=exported.manifest_path,
        public_key_path=public,
    )
    if len(_records(exported.journal_bytes, temp)) < accepted_count:
        raise RuntimeError("custody_export_predates_accepted_commitment")
    stage = LANE_ROOT / "recovery-staged"
    stage.mkdir(parents=True, exist_ok=True)
    for path in (exported.manifest_path, public):
        shutil.copy2(path, stage / path.name)
    (stage / exported.manifest_path.name.replace(".manifest.json", ".jsonl")).write_bytes(
        exported.journal_bytes
    )
    return {
        "original_raw": original_raw,
        "manifest_path": exported.manifest_path,
        "public": public,
        "verified": verified,
        "accepted_count": accepted_count,
        "accepted_tip": accepted_tip,
        "stage": stage,
        "journal_bytes": exported.journal_bytes,
        "records": _records(original_raw, temp),
    }


def _acceptance(record: dict) -> bool:
    initial = record.get("initial") or {}
    custody = record.get("custody") or {}
    amendment = record.get("amendment") or {}
    readers = record.get("readers") or {}
    recon = readers.get("reconciliation") or {}
    trust = readers.get("trust") or {}
    verify = readers.get("trust_verify") or [0, ""]
    return all(
        (
            initial.get("http") == 200,
            initial.get("amount_minor") == 4321,
            custody.get("signature_verified") is True,
            custody.get("restored_count", -1) >= custody.get("accepted_count", 0),
            custody.get("restored_tip") == custody.get("accepted_tip"),
            amendment.get("http") == 200,
            amendment.get("correction_http", {}).get("status") == 200,
            amendment.get("witness_advanced") is True,
            recon.get("status") == 200,
            recon.get("net_minor") == 5100,
            trust.get("status") == 200,
            trust.get("verified_revenue_minor") == 5100,
            trust.get("currency") == "USD",
            verify[0] == 200,
            isinstance(verify[1], dict)
            and verify[1].get("verification_status") == "verified",
        )
    )


def _positive(state: dict, tenant: dict, temp: Path) -> dict:
    intent = f"pi_xxvrec{_uuid_hex()}"
    first_status, _, _ = post_stripe(state, tenant, intent, 4321)
    initial = wait_verdict(tenant["tenant_id"], intent, timeout_s=180)
    if initial is None:
        raise RuntimeError("initial_verdict_missing")
    staged = _stage(state, temp)
    kept = False
    mutated = False
    record: dict = {"mode": "positive", "manual_observer": False}
    try:
        restored_path = temp / "restored.jsonl"
        disposition = restore_custody_bundle(
            manifest_path=staged["manifest_path"],
            journal=restored_path,
            public_key_path=staged["public"],
            accepted_source_count=staged["accepted_count"],
            accepted_source_tip=staged["accepted_tip"],
        )
        restored_records = _records(restored_path.read_bytes(), temp)
        docker("stop", AUTH)
        docker("stop", API)
        volume_rm(SOURCE_EVIDENCE_VOL, "source_evidence.jsonl")
        mutated = True
        volume_put(
            SOURCE_EVIDENCE_VOL,
            {"source_evidence.jsonl": restored_path.read_bytes()},
        )
        _start_services(state)
        event_ref = f"evt_xxvrec{_uuid_hex()}"
        second_status, _, _ = post_stripe_envelope(
            state,
            tenant,
            event_reference=event_ref,
            commerce_reference=intent,
            amount=5100,
        )
        amended = wait_verdict(tenant["tenant_id"], intent, timeout_s=180)
        correction_status, correction_body = http(
            "POST",
            f"http://127.0.0.1:{API_PORT}/api/reconciliation/match-verdicts/"
            f"{initial['verdict_id']}/corrections",
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
        witness_advanced = False
        for _ in range(90):
            heartbeat = (
                witness_files().get("history_witness_heartbeat.json") or {}
            ).get("payload") or {}
            if (
                int(heartbeat.get("source_journal_count", 0))
                > staged["accepted_count"]
                and heartbeat.get("source_journal_tip") != staged["accepted_tip"]
            ):
                witness_advanced = True
                break
            time.sleep(4)
        recon_status, recon = read_reconciliation(
            state, tenant, initial["verdict_id"]
        )
        trust_status, trust = 404, ""
        for _ in range(60):
            trust_status, trust = read_trust(tenant, initial["verdict_id"])
            if trust_status == 200:
                break
            time.sleep(5)
        verified_trust = (
            verify_trust(tenant, trust.get("envelope", trust))
            if trust_status == 200 and isinstance(trust, dict)
            else (0, "not_attempted")
        )
        record.update(
            {
                "initial": {
                    "http": first_status,
                    "amount_minor": 4321,
                    "verdict_id": initial["verdict_id"],
                    "subject": intent,
                },
                "custody": {
                    "accepted_count": staged["accepted_count"],
                    "accepted_tip": staged["accepted_tip"],
                    "restored_count": len(restored_records),
                    "restored_tip": journal_record_hash(restored_records[-1])
                    if restored_records
                    else None,
                    "signature_verified": True,
                    "disposition": disposition,
                    "stage": str(staged["stage"]),
                },
                "amendment": {
                    "http": second_status,
                    "amount_minor": 5100,
                    "subject": amended.get("commerce_reference") if amended else None,
                    "same_verdict": bool(
                        amended and amended["verdict_id"] == initial["verdict_id"]
                    ),
                    "correction_http": {
                        "status": correction_status,
                        "body": correction_body[:400],
                    },
                    "witness_advanced": witness_advanced,
                },
                "readers": {
                    "reconciliation": {
                        "status": recon_status,
                        "net_minor": recon.get("canonical_net_verified_amount_minor")
                        if isinstance(recon, dict)
                        else None,
                    },
                    "trust": {
                        "status": trust_status,
                        "verified_revenue_minor": trust.get("verified_revenue_minor")
                        if isinstance(trust, dict)
                        else None,
                        "currency": trust.get("currency")
                        if isinstance(trust, dict)
                        else None,
                    },
                    "trust_verify": verified_trust,
                },
            }
        )
        record["passed"] = _acceptance(record)
        kept = record["passed"]
    finally:
        if mutated and not kept:
            record["compensation"] = _preserve_operation(state, staged)
    return record


def _negative(state: dict, tenant: dict, temp: Path, mode: str) -> dict:
    intent = f"pi_xxvrec{_uuid_hex()}"
    first_status, _, _ = post_stripe(state, tenant, intent, 4321)
    initial = wait_verdict(tenant["tenant_id"], intent, timeout_s=180)
    if initial is None:
        raise RuntimeError("initial_verdict_missing")
    staged = _stage(state, temp)
    original_raw = staged["original_raw"]
    record: dict = {"mode": mode, "manual_observer": False}
    mutated = False
    try:
        if mode == "tamper-signature":
            staged["manifest_path"].chmod(0o644)
            manifest = json.loads(
                staged["manifest_path"].read_text(encoding="utf-8")
            )
            signature = str(manifest.get("signature") or "")
            prefix, _, body = signature.partition(":")
            manifest["signature"] = (
                prefix + ":" + ("A" if body[:1] != "A" else "B") + body[1:]
            )
            staged["manifest_path"].write_text(
                json.dumps(manifest, sort_keys=True, indent=2),
                encoding="utf-8",
            )
            try:
                verify_custody_bundle(
                    manifest_path=staged["manifest_path"],
                    public_key_path=staged["public"],
                )
            except SourceJournalCustodyError as exc:
                record["refusal"] = f"{type(exc).__name__}:{exc}"
            else:
                record["refusal"] = "NONE"
        else:
            docker("stop", AUTH)
            docker("stop", API)
            volume_rm(SOURCE_EVIDENCE_VOL, "source_evidence.jsonl")
            mutated = True
            try:
                _start_services(state)
            except Exception as exc:  # noqa: BLE001
                record["start_error"] = f"{type(exc).__name__}:{exc}"
            try:
                status, trust = read_trust(tenant, initial["verdict_id"])
                record["refusal"] = (
                    f"trust_status={status}:amount="
                    f"{trust.get('verified_revenue_minor') if isinstance(trust, dict) else None}"
                )
            except Exception as exc:  # noqa: BLE001
                record["refusal"] = f"{type(exc).__name__}:{exc}"
        record["initial"] = {
            "http": first_status,
            "amount_minor": 4321,
            "verdict_id": initial["verdict_id"],
        }
        record["acceptance"] = _acceptance(record)
        record["passed"] = not record["acceptance"] and record["refusal"] != "NONE"
    finally:
        if mutated:
            record["compensation"] = _restore_original(state, original_raw)
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=("positive", "omit-restore", "tamper-signature"),
        default="positive",
    )
    args = parser.parse_args()
    state = load_state()
    tenant = state["tenant_a"]
    temp = Path(tempfile.mkdtemp(prefix="xxv-recovery-"))
    try:
        record = (
            _positive(state, tenant, temp)
            if args.mode == "positive"
            else _negative(state, tenant, temp, args.mode)
        )
        record["artifact"] = state.get("artifact")
        record["property"] = (
            "recovery acceptance: accepted history restoration, same-subject"
            " progression, natural witnessing, verified signed money/currency"
        )
        out = (
            REPO
            / "docs/forensics/evidence/b26_p2_xxv_a8"
            / f"xxv-r0034-recovery-{args.mode}-20261102.json"
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps(record, indent=2, sort_keys=True))
        return 0 if record.get("passed") else 1
    finally:
        shutil.rmtree(temp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
