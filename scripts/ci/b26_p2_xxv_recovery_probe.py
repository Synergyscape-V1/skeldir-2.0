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
import hashlib
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
    sql,
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
from app.trust.audit_hash import idempotency_key_hash  # noqa: E402
from app.trust.builder import _subject_ref_hash  # noqa: E402
from app.trust.refusal import tenant_hash  # noqa: E402


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
        "signature_verified": bool(verified),
        "stage": stage,
        "journal_bytes": exported.journal_bytes,
        "records": _records(original_raw, temp),
    }


def _read_trust_attributed(tenant: dict, verdict_id: str) -> dict:
    """Read Trust with an idempotency key we can attribute in the audit log."""
    import uuid  # noqa: PLC0415

    key = f"xxv-recovery-{uuid.uuid4().hex}"
    urn = f"urn:skeldir:match_verdict:{verdict_id}"
    headers = {
        "Authorization": f"Bearer {tenant['machine_token']}",
        "X-Tenant-ID": tenant["tenant_id"],
        "X-Trust-Nonce": f"xxv-{uuid.uuid4().hex}",
        "X-Correlation-ID": str(uuid.uuid4()),
        "X-Idempotency-Key": key,
        "Content-Type": "application/json",
    }
    status, text = http(
        "GET",
        f"http://127.0.0.1:{API_PORT}/api/trust/v1/envelopes/match_verdict/{urn}",
        headers=headers,
    )
    try:
        body = json.loads(text)
    except Exception:  # noqa: BLE001
        body = text
    key_hash = idempotency_key_hash(
        tenant_id_hash=tenant_hash(tenant["tenant_id"]),
        idempotency_key=key,
    )
    rows = sql(
        "SELECT status, reason_code, created_at FROM public.trust_access_log"
        " WHERE tenant_id = %s AND idempotency_key_hash = %s"
        " ORDER BY created_at DESC, id DESC LIMIT 1",
        (tenant["tenant_id"], key_hash),
    )
    refusal = None
    if rows:
        row_status, reason, created_at = rows[0]
        refusal = {
            "status": row_status,
            "reason": reason,
            "created_at": created_at.isoformat()
            if hasattr(created_at, "isoformat")
            else str(created_at),
            "request_idempotency_hash": key_hash,
            "specific": (
                row_status == "refused"
                and isinstance(reason, str)
                and reason
                in {
                    "history_integrity_unverifiable",
                    "history_integrity_source_evidence_unverifiable",
                    "history_integrity_witness_refused",
                }
            ),
        }
    return {
        "http": status,
        "body": body,
        "refusal": refusal,
        "request_idempotency_hash": key_hash,
    }


_JWKS_CACHE: dict[str, object] = {}


def _trust_jwks() -> dict:
    if _JWKS_CACHE:
        return _JWKS_CACHE  # type: ignore[return-value]
    import uuid  # noqa: PLC0415

    status, text = http(
        "GET",
        f"http://127.0.0.1:{API_PORT}/api/trust/v1/keys/jwks",
        headers={"X-Correlation-ID": str(uuid.uuid4())},
    )
    if status != 200:
        raise RuntimeError(f"trust_jwks_unavailable:{status}")
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise RuntimeError("trust_jwks_malformed")
    _JWKS_CACHE.update(payload)
    return payload


def _public_key_basis(artifact: dict) -> dict:
    jwks = _trust_jwks()
    kid = str(artifact.get("signing_key_id") or "")
    keys = jwks.get("keys") if isinstance(jwks, dict) else None
    matching = None
    for key in keys or []:
        if isinstance(key, dict) and str(key.get("kid") or "") == kid:
            matching = key
            break
    if matching is None:
        return {"jwks": jwks, "matching_key": None, "valid": False}
    created = str(artifact.get("created_at") or "")
    valid_from = str(matching.get("skeldir_valid_from") or "")
    valid = bool(
        matching.get("kty") == "OKP"
        and matching.get("crv") == "Ed25519"
        and matching.get("alg") == "EdDSA"
        and matching.get("use") == "sig"
        and matching.get("skeldir_key_state") == "active"
        and matching.get("x")
        and created
        and valid_from
        and created >= valid_from
    )
    return {"jwks": jwks, "matching_key": matching, "valid": valid}


def _signed_structure(observation: dict, verdict_id: str, amount: int, currency: str) -> tuple[bool, str]:
    artifact = observation.get("artifact")
    verification = observation.get("verification") or [0, {}]
    if observation.get("status") != 200 or not isinstance(artifact, dict):
        return False, "signed_artifact_unavailable"
    if verification[0] != 200 or not isinstance(verification[1], dict):
        return False, "public_verification_unavailable"
    if verification[1].get("verification_status") != "verified":
        return False, "signature_not_verified"
    if verification[1].get("temporal_scope") != "truth-at-issuance":
        return False, "signed_phase_not_issuance"
    urn = f"urn:skeldir:match_verdict:{verdict_id}"
    if artifact.get("subject_type") != "match_verdict":
        return False, "signed_subject_type_mismatch"
    if artifact.get("subject_ref") != urn:
        return False, "signed_subject_mismatch"
    if artifact.get("subject_ref_hash") != _subject_ref_hash(urn):
        return False, "signed_subject_hash_mismatch"
    if artifact.get("truth_type") != "deterministic_match_verdict":
        return False, "signed_truth_type_mismatch"
    authority = artifact.get("truth_authority") or {}
    if (
        authority.get("authority_class") != "deterministic_machine_fact"
        or authority.get("source_system") != "skeldir_b23_match_engine"
    ):
        return False, "signed_financial_authority_mismatch"
    if artifact.get("verified_revenue_minor") != amount:
        return False, "signed_amount_mismatch"
    if artifact.get("currency") != currency:
        return False, "signed_currency_mismatch"
    if artifact.get("fallback_applied") is not False:
        return False, "signed_fallback_state"
    policy = artifact.get("policy_action_authority") or {}
    if policy.get("policy_state") != "read_only":
        return False, "signed_policy_state"
    boundary = artifact.get("evidence_temporal_boundary") or {}
    if (
        boundary.get("staleness_status") != "current"
        or boundary.get("snapshot_consistency_status") != "consistent"
        or boundary.get("evidence_age_status") != "within_supported_horizon"
    ):
        return False, "signed_history_phase"
    if (
        not authority.get("source_snapshot_hash")
        or authority.get("source_snapshot_hash")
        != boundary.get("evidence_snapshot_hash")
    ):
        return False, "signed_history_binding"
    provenance = artifact.get("provenance_chain") or []
    if not any(
        isinstance(entry, dict)
        and entry.get("authority_table") == "b23_match_verdicts"
        and entry.get("provenance_type") == "match_verdict"
        and entry.get("source_ref")
        == f"urn:skeldir:b23_match_verdicts:{verdict_id}"
        for entry in provenance
    ):
        return False, "signed_financial_history_missing"
    return True, ""


def _signed_observation(observation: dict, verdict_id: str, amount: int, currency: str) -> tuple[bool, str]:
    ok, reason = _signed_structure(observation, verdict_id, amount, currency)
    if not ok:
        return ok, reason
    basis = _public_key_basis(observation.get("artifact") or {})
    observation["public_key_basis"] = basis
    if not basis.get("valid"):
        return False, "signed_public_key_basis_invalid"
    return True, ""


def _wait_signed(
    tenant: dict, verdict_id: str, amount: int, currency: str, *, attempts: int = 60
) -> dict:
    last: dict = {"status": 0, "artifact": None, "verification": None}
    for _ in range(attempts):
        status, body = read_trust(tenant, verdict_id)
        if status == 200 and isinstance(body, dict):
            verification = verify_trust(tenant, body.get("envelope", body))
            last = {
                "status": status,
                "artifact": body,
                "verification": verification,
            }
            observation = {
                "status": status,
                "artifact": body,
                "verification": verification,
            }
            established, reason = _signed_observation(
                observation, verdict_id, amount, currency
            )
            observation["established"] = established
            observation["invalid_reason"] = reason or None
            last = observation
            if established:
                return last
        else:
            last = {"status": status, "artifact": None, "verification": None}
        time.sleep(5)
    return last


def _baseline(state: dict, tenant: dict, amount: int = 4321) -> tuple[dict, dict]:
    intent = f"pi_xxvrec{_uuid_hex()}"
    first_status, _, _ = post_stripe(state, tenant, intent, amount)
    initial = wait_verdict(tenant["tenant_id"], intent, timeout_s=180)
    if initial is None:
        raise RuntimeError("initial_verdict_missing")
    recon_status, recon = read_reconciliation(
        state, tenant, initial["verdict_id"]
    )
    observed_amount = initial.get("canonical_net_verified_amount_minor")
    if not isinstance(observed_amount, int) or observed_amount <= 0:
        raise RuntimeError("initial_amount_unobserved")
    baseline = {
        "http": first_status,
        "verdict_id": initial["verdict_id"],
        "subject": intent,
        "amount_minor": observed_amount,
        "currency": str(initial.get("currency_code") or ""),
        "reconciliation_status": recon_status,
        "reconciliation_net_minor": (
            recon.get("canonical_net_verified_amount_minor")
            if isinstance(recon, dict)
            else None
        ),
    }
    return baseline, initial


def _acceptance(record: dict) -> bool:
    baseline = record.get("baseline") or {}
    custody = record.get("custody") or {}
    amendment = record.get("amendment") or {}
    readers = record.get("readers") or {}
    recon = readers.get("reconciliation") or {}
    trust = readers.get("trust") or {}
    verify = readers.get("trust_verify") or [0, ""]
    if not isinstance(verify[1], dict):
        verify = (verify[0], {})
    expected_amount = baseline.get("amount_minor")
    amended_amount = (
        expected_amount + 779 if isinstance(expected_amount, int) else None
    )
    baseline_signed = record.get("baseline_signed") or {}
    baseline_verify = baseline_signed.get("verification") or [0, {}]
    fault = record.get("fault") or {}
    restored_baseline = record.get("restored_baseline") or {}
    restored_verify = restored_baseline.get("verification") or [0, {}]
    final_signed = record.get("final_signed") or {}
    final_verify = final_signed.get("verification") or [0, {}]
    subject = baseline.get("subject")
    verdict_id = baseline.get("verdict_id")
    baseline_structure_ok = False
    restored_structure_ok = False
    final_structure_ok = False
    if isinstance(expected_amount, int) and isinstance(verdict_id, str) and subject:
        currency = str(baseline.get("currency") or "")
        baseline_structure_ok, _ = _signed_structure(
            baseline_signed, verdict_id, expected_amount, currency
        )
        restored_structure_ok, _ = _signed_structure(
            restored_baseline, verdict_id, expected_amount, currency
        )
        final_structure_ok, _ = _signed_structure(
            final_signed, verdict_id, amended_amount, currency
        )
    return all(
        (
            baseline.get("http") == 200,
            isinstance(expected_amount, int) and expected_amount > 0,
            bool(baseline.get("subject")),
            bool(baseline.get("currency")),
            baseline.get("reconciliation_status") == 200,
            baseline.get("reconciliation_net_minor") == expected_amount,
            record.get("initial_subject") == baseline.get("subject"),
            baseline_signed.get("status") == 200,
            baseline_signed.get("established") is True,
            baseline_structure_ok is True,
            baseline_verify[0] == 200,
            isinstance(baseline_verify[1], dict)
            and baseline_verify[1].get("verification_status") == "verified",
            fault.get("specific") is True,
            fault.get("new_row") is True,
            fault.get("money_minor") is None,
            restored_baseline.get("status") == 200,
            restored_baseline.get("established") is True,
            restored_structure_ok is True,
            (restored_baseline.get("artifact") or {}).get(
                "verified_revenue_minor"
            )
            == expected_amount,
            (restored_baseline.get("artifact") or {}).get("currency")
            == baseline.get("currency"),
            restored_verify[0] == 200,
            isinstance(restored_verify[1], dict)
            and restored_verify[1].get("verification_status") == "verified",
            custody.get("accepted_count", -1) >= 0,
            custody.get("restored_count", -1) >= custody.get("accepted_count", 0),
            custody.get("restored_prefix_tip") == custody.get("accepted_tip"),
            custody.get("signature_verified") is True,
            amendment.get("http") == 200,
            amendment.get("subject") == baseline.get("subject"),
            amendment.get("verdict_id") == baseline.get("verdict_id"),
            amendment.get("same_verdict") is True,
            amendment.get("amount_minor") == amended_amount,
            amendment.get("correction_http", {}).get("status") == 200,
            amendment.get("witness_advanced") is True,
            recon.get("status") == 200,
            recon.get("net_minor") == amended_amount,
            trust.get("status") == 200,
            trust.get("verified_revenue_minor") == amended_amount,
            trust.get("currency") == baseline.get("currency"),
            final_signed.get("established") is True,
            final_structure_ok is True,
            final_signed.get("status") == 200,
            (final_signed.get("artifact") or {}).get(
                "verified_revenue_minor"
            )
            == amended_amount,
            (final_signed.get("artifact") or {}).get("currency")
            == baseline.get("currency"),
            final_verify[0] == 200,
            verify[0] == 200,
            verify[1].get("verification_status") == "verified",
            bool(verify[1].get("signature_hash")),
            bool(verify[1].get("signing_key_id")),
        )
    )


def _positive(state: dict, tenant: dict, temp: Path) -> dict:
    baseline, initial = _baseline(state, tenant, 4321)
    amended_amount = baseline["amount_minor"] + 779
    intent = baseline["subject"]
    baseline_signed = _wait_signed(
        tenant,
        initial["verdict_id"],
        baseline["amount_minor"],
        baseline["currency"],
    )
    if (
        baseline_signed.get("status") != 200
        or (baseline_signed.get("verification") or [0])[0] != 200
    ):
        raise RuntimeError("baseline_signed_result_unavailable")
    staged = _stage(state, temp)
    kept = False
    mutated = False
    record: dict = {
        "mode": "positive",
        "baseline": baseline,
        "initial_subject": initial.get("commerce_reference"),
        "baseline_signed": baseline_signed,
        "manual_observer": False,
    }
    try:
        docker("stop", AUTH)
        docker("stop", API)
        volume_rm(SOURCE_EVIDENCE_VOL, "source_evidence.jsonl")
        mutated = True
        _start_services(state)
        observed_refusal = _read_trust_attributed(
            tenant, initial["verdict_id"]
        )
        trust_body = observed_refusal["body"]
        money = (
            trust_body.get("verified_revenue_minor")
            if isinstance(trust_body, dict)
            else None
        )
        refusal = observed_refusal.get("refusal") or {}
        record["fault"] = {
            **refusal,
            "http": observed_refusal["http"],
            "money_minor": money,
            "new_row": bool(refusal),
            "specific": (
                refusal.get("specific") is True
                and observed_refusal["http"] == 404
                and money is None
            ),
        }
        restored_path = temp / "restored.jsonl"
        disposition = restore_custody_bundle(
            manifest_path=staged["manifest_path"],
            journal=restored_path,
            public_key_path=staged["public"],
            accepted_source_count=staged["accepted_count"],
            accepted_source_tip=staged["accepted_tip"],
        )
        volume_put(
            SOURCE_EVIDENCE_VOL,
            {"source_evidence.jsonl": restored_path.read_bytes()},
        )
        _start_services(state)
        restored_baseline = _wait_signed(
            tenant,
            initial["verdict_id"],
            baseline["amount_minor"],
            baseline["currency"],
        )
        record["restored_baseline"] = restored_baseline
        restored_records = _records(restored_path.read_bytes(), temp)
        event_ref = f"evt_xxvrec{_uuid_hex()}"
        second_status, _, _ = post_stripe_envelope(
            state,
            tenant,
            event_reference=event_ref,
            commerce_reference=intent,
            amount=amended_amount,
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
        final_observation = {
            "status": trust_status,
            "artifact": trust if isinstance(trust, dict) else None,
            "verification": verified_trust,
        }
        final_established, final_reason = (
            _signed_observation(
                final_observation,
                initial["verdict_id"],
                amended_amount,
                baseline["currency"],
            )
            if isinstance(trust, dict)
            else (False, "final_signed_artifact_unavailable")
        )
        final_observation["established"] = final_established
        final_observation["invalid_reason"] = final_reason or None
        record["final_signed"] = final_observation
        prefix_records = restored_records[: staged["accepted_count"]]
        record.update(
            {
                "custody": {
                    "accepted_count": staged["accepted_count"],
                    "accepted_tip": staged["accepted_tip"],
                    "restored_count": len(restored_records),
                    "restored_prefix_tip": journal_record_hash(prefix_records[-1])
                    if prefix_records
                    else None,
                    "signature_verified": staged.get("signature_verified"),
                    "disposition": disposition,
                    "stage": str(staged["stage"]),
                },
                "amendment": {
                    "http": second_status,
                    "amount_minor": amended_amount,
                    "subject": amended.get("commerce_reference") if amended else None,
                    "verdict_id": amended.get("verdict_id") if amended else None,
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
                        "artifact": trust if isinstance(trust, dict) else None,
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


def _negative_decision(record: dict) -> bool:
    mode = record.get("mode")
    observed = record.get("observed") or {}
    baseline_verify = (record.get("baseline_signed") or {}).get(
        "verification"
    ) or [0, {}]
    if not (
        baseline_verify[0] == 200
        and isinstance(baseline_verify[1], dict)
        and baseline_verify[1].get("verification_status") == "verified"
    ):
        return False
    if mode == "tamper-signature":
        return (
            observed.get("signature_refused") is True
            and record.get("original_unchanged") is True
        )
    if mode == "restore-failure":
        return (
            observed.get("restoration_refused") is True
            and record.get("original_unchanged") is True
        )
    restored = record.get("restored_baseline") or {}
    restored_verify = restored.get("verification") or [0, {}]
    return (
        observed.get("specific") is True
        and observed.get("new_row") is True
        and record.get("compensation", {}).get("restored_original") is True
        and record.get("original_unchanged") is True
        and restored.get("status") == 200
        and (restored.get("artifact") or {}).get("verified_revenue_minor")
        == (record.get("baseline") or {}).get("amount_minor")
        and (restored.get("artifact") or {}).get("currency")
        == (record.get("baseline") or {}).get("currency")
        and restored_verify[0] == 200
        and isinstance(restored_verify[1], dict)
        and restored_verify[1].get("verification_status") == "verified"
    )


def _negative(state: dict, tenant: dict, temp: Path, mode: str) -> dict:
    baseline, initial = _baseline(state, tenant, 4321)
    baseline_signed = _wait_signed(
        tenant,
        initial["verdict_id"],
        baseline["amount_minor"],
        baseline["currency"],
    )
    if (
        baseline_signed.get("status") != 200
        or (baseline_signed.get("verification") or [0])[0] != 200
    ):
        raise RuntimeError("baseline_signed_result_unavailable")
    staged = _stage(state, temp)
    original_raw = staged["original_raw"]
    original_sha = hashlib.sha256(original_raw).hexdigest()
    record: dict = {
        "mode": mode,
        "baseline": baseline,
        "baseline_signed": baseline_signed,
        "initial_subject": initial.get("commerce_reference"),
        "original_sha256": original_sha,
        "manual_observer": False,
    }
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
            refusal = "NONE"
            try:
                verify_custody_bundle(
                    manifest_path=staged["manifest_path"],
                    public_key_path=staged["public"],
                )
            except SourceJournalCustodyError as exc:
                refusal = f"{type(exc).__name__}:{exc}"
            except Exception as exc:  # noqa: BLE001
                refusal = f"unrelated:{type(exc).__name__}:{exc}"
            record["observed"] = {
                "signature_refusal": refusal,
                "signature_refused": refusal == "SourceJournalCustodyError:custody_signature_invalid",
            }
        elif mode == "restore-failure":
            refusal = "NONE"
            try:
                restore_custody_bundle(
                    manifest_path=staged["manifest_path"],
                    journal=temp / "must-not-restore.jsonl",
                    public_key_path=staged["public"],
                    accepted_source_count=staged["accepted_count"] + 1,
                    accepted_source_tip=staged["accepted_tip"],
                )
            except SourceJournalCustodyError as exc:
                refusal = f"{type(exc).__name__}:{exc}"
            except Exception as exc:  # noqa: BLE001
                refusal = f"unrelated:{type(exc).__name__}:{exc}"
            record["observed"] = {
                "restoration_refusal": refusal,
                "restoration_refused": "custody_restore_below_accepted_commitment"
                in refusal,
            }
        else:
            docker("stop", AUTH)
            docker("stop", API)
            volume_rm(SOURCE_EVIDENCE_VOL, "source_evidence.jsonl")
            mutated = True
            try:
                _start_services(state)
                record["start_error"] = None
            except Exception as exc:  # noqa: BLE001
                record["start_error"] = f"{type(exc).__name__}:{exc}"
            observed_refusal = _read_trust_attributed(
                tenant, initial["verdict_id"]
            )
            trust_body = observed_refusal["body"]
            refusal = observed_refusal.get("refusal") or {}
            money = (
                trust_body.get("verified_revenue_minor")
                if isinstance(trust_body, dict)
                else None
            )
            record["observed"] = {
                **refusal,
                "http": observed_refusal["http"],
                "money_minor": money,
                "new_row": bool(refusal),
                "specific": (
                    refusal.get("specific") is True
                    and observed_refusal["http"] == 404
                    and money is None
                ),
            }
    finally:
        if mutated:
            record["compensation"] = _restore_original(state, original_raw)
            record["original_unchanged"] = (
                hashlib.sha256(
                    volume_get(SOURCE_EVIDENCE_VOL, "source_evidence.jsonl")
                ).hexdigest()
                == original_sha
            )
        else:
            record["original_unchanged"] = (
                hashlib.sha256(
                    volume_get(SOURCE_EVIDENCE_VOL, "source_evidence.jsonl")
                ).hexdigest()
                == original_sha
            )
    if mode == "omit-restore" and record.get("compensation", {}).get(
        "restored_original"
    ):
        record["restored_baseline"] = _wait_signed(
            tenant,
            initial["verdict_id"],
            baseline["amount_minor"],
            baseline["currency"],
        )
    record["passed"] = _negative_decision(record)
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=("positive", "omit-restore", "tamper-signature", "restore-failure"),
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
