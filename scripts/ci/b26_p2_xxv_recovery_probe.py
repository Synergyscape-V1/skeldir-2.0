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
import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
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
    await_witness_catchup,
    wait_verdict,
    witness_files,
)
from b26_p2_xxv_lane import (  # noqa: E402
    AUTH,
    API,
    LANE_ROOT,
    SOURCE_EVIDENCE_VOL,
    WITNESS_VOL,
    admin_dsn,
    role_dsn,
)
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
from app.revenue_verification.source_attestation import (  # noqa: E402
    ATTESTATION_STATEMENT_VERSION,
    canonical_statement_bytes,
    verify_signature,
)
from app.trust.audit_hash import idempotency_key_hash  # noqa: E402
from app.trust.builder import _subject_ref_hash  # noqa: E402
from app.trust.canonicalization import (  # noqa: E402
    _canonicalize_arrays,
    canonicalize_json_document,
)
from app.trust.hash_domains import project_domain_payload  # noqa: E402
from app.trust.key_registry import TrustKeyRegistry, TrustSigningKey  # noqa: E402
from app.trust.money_source_adapter import (  # noqa: E402
    AuthoritativeMoneyMinor,
    resolve_authoritative_money,
)
from app.trust.provenance import (  # noqa: E402
    REQUIRED_P7_PROVENANCE_SOURCE_CLASSES,
    _internal_decision_entry,
    _registration,
    _unavailable_entry,
)
from app.trust.refusal import tagged_sha256, tenant_hash, utc_second  # noqa: E402
from app.trust.source_adapters import (  # noqa: E402
    data_completeness_for_match_status,
    normalize_match_verdict_status,
)
from app.trust.subject_authority import subject_authority_definition  # noqa: E402
from app.trust.verification import verify_trust_envelope  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey  # noqa: E402


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
            "financial": (
                row_status == "refused"
                and isinstance(reason, str)
                and bool(reason)
                and (
                    reason in {
                        "money_source_not_authoritative",
                        "source_money_conservation_unverifiable",
                        "source_changed_during_issuance",
                    }
                    or reason.startswith(
                        (
                            "money_",
                            "source_",
                            "attestation_",
                            "history_integrity_",
                        )
                    )
                )
            ),
        }
    return {
        "http": status,
        "body": body,
        "refusal": refusal,
        "request_idempotency_hash": key_hash,
    }


_JWKS_CACHE: dict[str, object] = {}
_CONTRACT_ENUM_CACHE: dict[str, frozenset[str]] = {}
_SEMANTIC_TRUTH_DOMAIN = "semantic_truth_v1"
_OBSERVATION_TIME_PATHS = (
    "evidence_temporal_boundary.source_read_started_at",
    "evidence_temporal_boundary.source_read_completed_at",
    "evidence_temporal_boundary.data_freshness_seconds",
)
_ISSUANCE_PROVENANCE_TYPES = frozenset(
    row.provenance_type
    for row in REQUIRED_P7_PROVENANCE_SOURCE_CLASSES
    if row.availability_when_missing == "deferred"
)


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


def _artifact_trust_jwks(state: dict) -> dict:
    material = state.get("material") or {}
    raw = material.get("trust_jwks_json")
    if isinstance(raw, str) and raw:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    return _trust_jwks()


def _contract_enum(field: str) -> frozenset[str]:
    cached = _CONTRACT_ENUM_CACHE.get(field)
    if cached is not None:
        return cached
    import yaml  # noqa: PLC0415

    schema = yaml.safe_load(
        (REPO / "contracts/trust-api/trust-envelope.v2.yaml").read_text(
            encoding="utf-8"
        )
    )
    values = (schema.get("properties", {}).get(field) or {}).get("enum")
    if not isinstance(values, list) or not values:
        raise RuntimeError(f"trust_contract_enum_missing:{field}")
    enum = frozenset(str(value) for value in values)
    _CONTRACT_ENUM_CACHE[field] = enum
    return enum


def _key_lifecycle_valid(artifact: dict, key: dict) -> bool:
    if (
        key.get("kty") != "OKP"
        or key.get("crv") != "Ed25519"
        or key.get("alg") != "EdDSA"
        or key.get("use") != "sig"
        or key.get("skeldir_key_state") not in {"active", "verification_only"}
        or not key.get("x")
    ):
        return False
    try:
        created_at = datetime.fromisoformat(
            str(artifact.get("created_at") or "").replace("Z", "+00:00")
        )
        valid_from = datetime.fromisoformat(
            str(key["skeldir_valid_from"]).replace("Z", "+00:00")
        )
        valid_until = (
            datetime.fromisoformat(
                str(key["skeldir_valid_until"]).replace("Z", "+00:00")
            )
            if key.get("skeldir_valid_until")
            else None
        )
        retired_at = (
            datetime.fromisoformat(
                str(key["skeldir_retired_at"]).replace("Z", "+00:00")
            )
            if key.get("skeldir_retired_at")
            else None
        )
    except (KeyError, TypeError, ValueError):
        return False
    if created_at < valid_from:
        return False
    if valid_until is not None and created_at > valid_until:
        return False
    if retired_at is not None and created_at > retired_at:
        return False
    return True


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
    valid = bool(matching.get("x") and _key_lifecycle_valid(artifact, matching))
    return {"jwks": jwks, "matching_key": matching, "valid": valid}


def _drop_path(document: dict, path: str) -> None:
    parts = path.split(".")
    cursor = document
    for part in parts[:-1]:
        child = cursor.get(part)
        if not isinstance(child, dict):
            return
        cursor = child
    cursor.pop(parts[-1], None)


def _governed_semantic_meaning(artifact: object) -> dict | None:
    """Project the contract-declared financial meaning, not a local field list."""
    if not isinstance(artifact, dict):
        return None
    try:
        meaning = project_domain_payload(
            _canonicalize_arrays(artifact), _SEMANTIC_TRUTH_DOMAIN
        )
    except Exception:  # noqa: BLE001
        return None
    for path in _OBSERVATION_TIME_PATHS:
        _drop_path(meaning, path)
    meaning["policy_action_authority"] = artifact.get(
        "policy_action_authority"
    )
    meaning["audience_binding"] = artifact.get("audience_binding")
    provenance = meaning.get("provenance_chain")
    if not isinstance(provenance, list):
        return None
    meaning["provenance_chain"] = [
        entry
        for entry in provenance
        if not (
            isinstance(entry, dict) and _is_issuance_audit_entry(entry)
        )
    ]
    return meaning


def _is_issuance_audit_entry(entry: dict) -> bool:
    provenance_type = str(entry.get("provenance_type") or "")
    if provenance_type not in _ISSUANCE_PROVENANCE_TYPES:
        return False
    if entry.get("authority_table") != "trust_access_log":
        return False
    prefix = {
        "audit_access_record": "urn:skeldir:audit:issuance:",
        "audit_hash": "urn:skeldir:audit_hash:",
    }.get(provenance_type)
    return bool(
        prefix
        and str(entry.get("source_ref") or "").startswith(prefix)
    )


def _semantic_digest(meaning: dict | None) -> str | None:
    if meaning is None:
        return None
    try:
        encoded = canonicalize_json_document(meaning)
    except Exception:  # noqa: BLE001
        return None
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _utc_time(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(
            str(value or "").replace("Z", "+00:00")
        )
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _observation_time_facts(artifact: dict) -> dict | None:
    boundary = artifact.get("evidence_temporal_boundary")
    if not isinstance(boundary, dict):
        return None
    facts = {
        "created_at": _utc_time(artifact.get("created_at")),
        "read_started_at": _utc_time(boundary.get("source_read_started_at")),
        "read_completed_at": _utc_time(
            boundary.get("source_read_completed_at")
        ),
        "data_freshness_seconds": boundary.get("data_freshness_seconds"),
    }
    if not all(
        isinstance(facts[key], datetime)
        for key in ("created_at", "read_started_at", "read_completed_at")
    ):
        return None
    freshness = facts["data_freshness_seconds"]
    if freshness is not None and not isinstance(freshness, int):
        return None
    return facts


def _observation_time_justification(
    baseline: dict,
    restored: dict,
    restored_observation: dict | None = None,
) -> tuple[bool, dict, str]:
    baseline_facts = _observation_time_facts(baseline)
    restored_facts = _observation_time_facts(restored)
    if baseline_facts is None or restored_facts is None:
        return False, {}, "observation_time_unavailable"
    for facts in (baseline_facts, restored_facts):
        if (
            facts["read_started_at"] != facts["created_at"]
            or facts["read_completed_at"] != facts["created_at"]
        ):
            return False, {}, "observation_read_not_issuance_time"
        if facts["data_freshness_seconds"] != 0:
            return False, {}, "observation_freshness_not_source_exact"
    if restored_facts["created_at"] < baseline_facts["created_at"]:
        return False, {}, "observation_time_reversed"
    observation_changed = any(
        restored_facts[key] != baseline_facts[key]
        for key in (
            "created_at",
            "read_started_at",
            "read_completed_at",
            "data_freshness_seconds",
        )
    )
    if observation_changed:
        window = restored_observation or {}
        started_at = _utc_time(window.get("started_at"))
        completed_at = _utc_time(
            window.get("completed_at") or window.get("observed_at")
        )
        if started_at is None or completed_at is None:
            return False, {}, "observation_window_missing"
        started_at = started_at.replace(microsecond=0)
        completed_at = completed_at.replace(microsecond=0)
        if not (
            started_at
            <= restored_facts["created_at"]
            <= completed_at
        ):
            return False, {}, "observation_time_not_observed"
    baseline_freshness = baseline_facts["data_freshness_seconds"]
    restored_freshness = restored_facts["data_freshness_seconds"]
    evidence = {
        "baseline": {
            "created_at": baseline_facts["created_at"].isoformat(),
            "source_read_started_at": baseline_facts[
                "read_started_at"
            ].isoformat(),
            "source_read_completed_at": baseline_facts[
                "read_completed_at"
            ].isoformat(),
            "data_freshness_seconds": baseline_freshness,
        },
        "restored": {
            "created_at": restored_facts["created_at"].isoformat(),
            "source_read_started_at": restored_facts[
                "read_started_at"
            ].isoformat(),
            "source_read_completed_at": restored_facts[
                "read_completed_at"
            ].isoformat(),
            "data_freshness_seconds": restored_freshness,
        },
        "restored_observation_window": (
            dict(restored_observation or {})
            if observation_changed
            else None
        ),
    }
    return True, evidence, ""


def _restoration_semantic_authority(
    baseline_signed: dict,
    restored: dict,
    *,
    restored_observation: dict | None = None,
) -> dict:
    baseline = baseline_signed.get("artifact")
    restored_artifact = restored.get("artifact")
    if not isinstance(baseline, dict) or not isinstance(
        restored_artifact, dict
    ):
        return {
            "established": False,
            "reason": "restoration_artifact_unavailable",
        }
    baseline_meaning = _governed_semantic_meaning(baseline)
    restored_meaning = _governed_semantic_meaning(restored_artifact)
    baseline_digest = _semantic_digest(baseline_meaning)
    restored_digest = _semantic_digest(restored_meaning)
    justified, observation, observation_reason = (
        _observation_time_justification(
            baseline, restored_artifact, restored_observation
        )
    )
    established = bool(
        baseline_digest is not None
        and baseline_digest == restored_digest
        and justified
    )
    if baseline_digest is None or restored_digest is None:
        reason = "governed_semantic_meaning_unavailable"
    elif baseline_digest != restored_digest:
        reason = "governed_semantic_meaning_mismatch"
    else:
        reason = observation_reason
    return {
        "established": established,
        "reason": None if established else reason,
        "semantic_domain": _SEMANTIC_TRUTH_DOMAIN,
        "baseline_meaning_digest": baseline_digest,
        "restored_meaning_digest": restored_digest,
        "baseline_signed_semantic_truth_hash": baseline.get(
            "semantic_truth_hash"
        ),
        "restored_signed_semantic_truth_hash": restored_artifact.get(
            "semantic_truth_hash"
        ),
        "observation_time_paths": list(_OBSERVATION_TIME_PATHS),
        "issuance_provenance_types_excluded": sorted(
            _ISSUANCE_PROVENANCE_TYPES
        ),
        "observation_time_justified": justified,
        "observation_time": observation,
        "observation_time_reason": observation_reason or None,
    }


def _issued_observation_justification(
    artifact: dict,
    window: dict | None,
    *,
    require_window: bool,
) -> tuple[bool, dict, str]:
    facts = _observation_time_facts(artifact)
    if facts is None:
        return False, {}, "observation_time_unavailable"
    if (
        facts["read_started_at"] != facts["created_at"]
        or facts["read_completed_at"] != facts["created_at"]
    ):
        return False, {}, "observation_read_not_issuance_time"
    if facts["data_freshness_seconds"] != 0:
        return False, {}, "observation_freshness_not_source_exact"
    boundary = artifact.get("evidence_temporal_boundary") or {}
    if boundary.get("max_source_read_skew_ms") != 0:
        return False, {}, "observation_read_skew_not_exact"
    snapshot_at = _utc_time(boundary.get("evidence_snapshot_at"))
    if snapshot_at is None:
        return False, {}, "observation_snapshot_missing"
    if snapshot_at > facts["created_at"]:
        return False, {}, "observation_snapshot_after_issuance"
    evidence = {
        "created_at": facts["created_at"].isoformat(),
        "source_read_started_at": facts["read_started_at"].isoformat(),
        "source_read_completed_at": facts["read_completed_at"].isoformat(),
        "data_freshness_seconds": facts["data_freshness_seconds"],
    }
    if window is not None:
        started = _utc_time(window.get("started_at"))
        completed = _utc_time(
            window.get("completed_at") or window.get("observed_at")
        )
        if started is None or completed is None:
            return False, evidence, "observation_window_missing"
        started = started.replace(microsecond=0)
        completed = completed.replace(microsecond=0)
        if not (started <= facts["created_at"] <= completed):
            return False, evidence, "observation_time_not_observed"
        evidence["observation_window"] = dict(window)
    elif require_window:
        return False, evidence, "observation_window_missing"
    return True, evidence, ""


def _issued_authority(
    artifact: dict,
    reference_artifact: dict,
    *,
    window: dict | None,
    require_window: bool,
) -> dict:
    justified, observation, reason = _issued_observation_justification(
        artifact, window, require_window=require_window
    )
    if not justified:
        return {
            "established": False,
            "reason": reason,
            "observation": observation,
        }
    reference_policy = reference_artifact.get("policy_action_authority")
    reference_audience = reference_artifact.get("audience_binding")
    if artifact.get("policy_action_authority") != reference_policy:
        return {
            "established": False,
            "reason": "issued_policy_authority_changed",
            "observation": observation,
        }
    if artifact.get("audience_binding") != reference_audience:
        return {
            "established": False,
            "reason": "issued_audience_binding_changed",
            "observation": observation,
        }
    return {
        "established": True,
        "reason": None,
        "observation": observation,
        "policy_action_authority": artifact.get("policy_action_authority"),
        "audience_binding": artifact.get("audience_binding"),
    }


def _result_source_authority(
    artifact: dict,
    *,
    amount: int,
    currency: str,
    observed_at: str | None,
    reason_code: str | None = None,
) -> dict:
    if observed_at is None:
        return {
            "established": False,
            "reason": "result_source_observation_missing",
        }
    subject_type = artifact.get("subject_type")
    try:
        definition = subject_authority_definition(str(subject_type))
    except ValueError:
        return {
            "established": False,
            "reason": "result_subject_authority_unsupported",
        }
    expected_subject = {
        "subject_type": artifact.get("subject_type"),
        "subject_ref": artifact.get("subject_ref"),
        "subject_ref_hash": artifact.get("subject_ref_hash"),
        "source_authority_class": definition.source_authority_class,
        "allowed_source_tables": list(definition.governed_source_tables),
        "mutable_workflow_subject": False,
    }
    if artifact.get("subject_authority") != expected_subject:
        return {
            "established": False,
            "reason": "result_subject_authority_mismatch",
        }
    if subject_type == "match_verdict":
        expected_benchmark = {
            "benchmark_authority": "explicitly_unavailable",
            "benchmark_hash": None,
            "benchmark_ref": None,
            "benchmark_status": "unavailable",
            "unavailable_reason": "benchmark_source_not_configured",
        }
        if artifact.get("benchmark_metadata") != expected_benchmark:
            return {
                "established": False,
                "reason": "result_benchmark_authority_mismatch",
            }
        expected_confidence = {
            "bayesian_model_type": "deterministic_only",
            "bayesian_model_version": None,
            "confidence_authority": "deterministic_only",
            "confidence_score_basis_points": None,
            "confidence_status": "unavailable",
            "diagnostics_status": "not_applicable",
            "inference_provenance": None,
            "unavailable_reason": "not_applicable",
        }
        if artifact.get("confidence_metadata") != expected_confidence:
            return {
                "established": False,
                "reason": "result_confidence_authority_mismatch",
            }
        money = resolve_authoritative_money(
            source_domain="b23_match_verdicts",
            source_field_path="canonical_net_verified_amount_minor",
            raw_value=amount,
            currency=currency,
            intended_trust_field="verified_revenue_minor",
        )
        if not isinstance(money, AuthoritativeMoneyMinor):
            return {
                "established": False,
                "reason": "result_money_source_not_authoritative",
            }
        expected_entries = {
            "money_authority": _internal_decision_entry(
                _registration("money_authority_source"),
                observed_at=observed_at,
                decision_material=money.external_projection(),
            ),
            "policy_decision": _internal_decision_entry(
                _registration("policy_authority_source"),
                observed_at=observed_at,
                decision_material={"policy_state": "read_only"},
            ),
            "reason_code_decision": _internal_decision_entry(
                _registration("reason_code_decision"),
                observed_at=observed_at,
                decision_material={"reason_code": reason_code or "none"},
            ),
        }
        provenance = artifact.get("provenance_chain") or []
        for source_class in (
            "deterministic_attribution_output_refs",
            "b24_source_snapshot_hash",
            "b24_fit_id",
            "b24_diagnostic_fallback_status",
            "b24_artifact_ref_hash",
        ):
            expected_ref = f"urn:skeldir:unavailable:{source_class}"
            actual = next(
                (
                    entry
                    for entry in provenance
                    if isinstance(entry, dict)
                    and entry.get("provenance_type") == "explicit_unavailable"
                    and entry.get("source_ref") == expected_ref
                ),
                None,
            )
            expected = _unavailable_entry(
                _registration(source_class), observed_at=observed_at
            )
            if not _entry_matches(actual, expected):
                return {
                    "established": False,
                    "reason": "result_unavailability_provenance_missing",
                }
        if _one_provenance(artifact, "text_disposition") is None:
            return {
                "established": False,
                "reason": "result_text_disposition_provenance_missing",
            }
        for provenance_type, expected in expected_entries.items():
            actual = _one_provenance(artifact, provenance_type)
            if not _entry_matches(actual, expected):
                return {
                    "established": False,
                    "reason": f"result_{provenance_type}_mismatch",
                }
    return {
        "established": True,
        "reason": None,
        "subject_authority": expected_subject,
        "benchmark_metadata": artifact.get("benchmark_metadata"),
        "confidence_metadata": artifact.get("confidence_metadata"),
        "money_authority": artifact.get("money_authority"),
        "policy_action_authority": artifact.get("policy_action_authority"),
    }


def _result_history_authority(
    artifact: dict, verdict: dict, ingress: dict
) -> dict:
    expected_provider = _expected_provider_entry(
        provider=ingress["provider"],
        event_reference=ingress["provider_native_event_reference"],
        commerce_reference=ingress[
            "provider_native_commerce_reference"
        ],
        observed_at=verdict["created_at"],
    )
    expected_webhook = _expected_webhook_entry(verdict, ingress)
    if not _entry_matches(
        _one_provenance(artifact, "provider_native_reference"),
        expected_provider,
    ):
        return {
            "established": False,
            "reason": "result_provider_history_mismatch",
        }
    if not _entry_matches(
        _one_provenance(artifact, "webhook_signature"),
        expected_webhook,
    ):
        return {
            "established": False,
            "reason": "result_webhook_history_mismatch",
        }
    return {"established": True, "reason": None}


def _utc_second_value(value: object) -> str:
    if isinstance(value, datetime):
        return utc_second(value)
    parsed = _utc_time(value)
    return utc_second(parsed) if parsed is not None else str(value)


def _utc_precise_value(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    parsed = _utc_time(value)
    return parsed.isoformat().replace("+00:00", "Z") if parsed else str(value)


def _one_provenance(artifact: dict, provenance_type: str) -> dict | None:
    entries = [
        entry
        for entry in artifact.get("provenance_chain") or []
        if isinstance(entry, dict)
        and entry.get("provenance_type") == provenance_type
    ]
    return entries[0] if len(entries) == 1 else None


def _expected_provider_entry(
    *, provider: str, event_reference: str, commerce_reference: str,
    observed_at: str
) -> dict:
    reference_hash = tagged_sha256(
        {
            "provider": provider,
            "event_reference": event_reference,
            "commerce_reference": commerce_reference,
        }
    ).split(":", 1)[1]
    source_ref = f"urn:skeldir:provider_native_reference:{reference_hash}"
    return {
        "authority_table": "b23_match_verdicts",
        "provenance_type": "provider_native_reference",
        "source_ref": source_ref,
        "source_ref_hash": tagged_sha256({"source_ref": source_ref}),
        "source_snapshot_hash": tagged_sha256(
            {
                "provider": provider,
                "provider_native_event_reference_hash": tagged_sha256(
                    event_reference
                ),
                "provider_native_commerce_reference_hash": tagged_sha256(
                    commerce_reference
                ),
            }
        ),
        "observed_at": observed_at,
    }


def _expected_match_entry(verdict: dict) -> dict:
    source_ref = f"urn:skeldir:b23_match_verdicts:{verdict['id']}"
    return {
        "authority_table": "b23_match_verdicts",
        "provenance_type": "match_verdict",
        "source_ref": source_ref,
        "source_ref_hash": tagged_sha256({"source_ref": source_ref}),
        "source_snapshot_hash": tagged_sha256(
            {
                "source": "b23_match_verdicts",
                "id": str(verdict["id"]),
                "status": verdict["status"],
                "amount_minor": int(
                    verdict["canonical_net_verified_amount_minor"]
                ),
                "currency": verdict["currency_code"],
                "updated_at": _utc_second_value(verdict["updated_at"]),
            }
        ),
        "observed_at": _utc_second_value(verdict["last_transition_at"]),
    }


def _expected_webhook_entry(verdict: dict, current: dict) -> dict:
    source_ref = (
        "urn:skeldir:webhook_ingress_identity:" f"{current['id']}"
    )
    return {
        "authority_table": "webhook_ingress_identities",
        "provenance_type": "webhook_signature",
        "source_ref": source_ref,
        "source_ref_hash": tagged_sha256({"source_ref": source_ref}),
        "source_snapshot_hash": tagged_sha256(
            {
                "webhook_ingress_identity_id": str(current["id"]),
                "provider": current["provider"],
                "match_verdict_id": str(verdict["id"]),
            }
        ),
        "observed_at": _utc_second_value(verdict["created_at"]),
    }


def _entry_matches(actual: dict | None, expected: dict) -> bool:
    if not isinstance(actual, dict):
        return False
    return all(
        actual.get(key) == expected[key]
        for key in (
            "authority_table",
            "provenance_type",
            "source_ref",
            "source_ref_hash",
            "source_snapshot_hash",
            "observed_at",
        )
    )


def _ledger_nullable(value: object) -> str:
    return "NULL" if value is None else str(value)


def _ledger_entry_hash(row: dict) -> str:
    material = "|".join(
        (
            str(row.get("verdict_id") or ""),
            _ledger_nullable(row.get("prior_attributed_amount_minor")),
            _ledger_nullable(row.get("new_attributed_amount_minor")),
            _ledger_nullable(row.get("prior_verified_amount_minor")),
            _ledger_nullable(row.get("new_verified_amount_minor")),
            str(row.get("prior_authority_state") or "NULL"),
            str(row.get("new_authority_state") or "NULL"),
            str(row.get("prev_entry_hash") or ""),
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _global_prefix_digest(rows: list[dict]) -> str:
    material = "|".join(
        f"{int(row['seq'])}:{row['entry_hash']}" for row in rows
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _verify_signed_latest_checkpoint(
    commitment: dict,
    *,
    global_ledger: list[dict],
    target_ledger: list[dict],
    authority_universe: str | None = None,
) -> tuple[bool, str, dict]:
    public_key = commitment.get("public_key")
    latest = commitment.get("latest_checkpoint")
    if not isinstance(public_key, str) or not isinstance(latest, dict):
        return False, "signed_witness_proof_missing", {}
    payload = latest.get("payload")
    signature = latest.get("signature")
    if not isinstance(payload, dict) or not isinstance(signature, str):
        return False, "signed_witness_proof_malformed", {}
    if not signature.startswith("ed25519:"):
        return False, "signed_witness_signature_algorithm", {}
    if not authority_universe:
        return False, "signed_witness_authority_universe_missing", {}
    if payload.get("authority_universe") != authority_universe:
        return False, "signed_witness_authority_universe_mismatch", {}
    try:
        raw_key = base64.urlsafe_b64decode(
            (public_key + "=" * (-len(public_key) % 4)).encode("ascii")
        )
        signature_text = signature.removeprefix("ed25519:")
        raw_signature = base64.urlsafe_b64decode(
            (signature_text + "=" * (-len(signature_text) % 4)).encode("ascii")
        )
        key = Ed25519PublicKey.from_public_bytes(raw_key)
        material = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        key.verify(raw_signature, material)
    except Exception as exc:  # noqa: BLE001
        return False, f"signed_witness_signature_invalid:{type(exc).__name__}", {}
    without_hash = {
        key: value
        for key, value in payload.items()
        if key != "checkpoint_hash"
    }
    recomputed = hashlib.sha256(
        json.dumps(
            without_hash,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    if payload.get("checkpoint_hash") != recomputed:
        return False, "signed_witness_checkpoint_hash_mismatch", {}
    count = payload.get("ledger_count")
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        return False, "signed_witness_count_invalid", {}
    prefix = global_ledger[:count]
    if len(prefix) != count:
        return False, "signed_witness_covers_absent_ledger", {}
    prefix_digest = _global_prefix_digest(prefix)
    if payload.get("ledger_prefix_digest") != prefix_digest:
        return False, "signed_witness_prefix_mismatch", {}
    if prefix:
        if payload.get("ledger_tip_seq") != prefix[-1]["seq"]:
            return False, "signed_witness_tip_seq_mismatch", {}
        if payload.get("ledger_tip_hash") != prefix[-1]["entry_hash"]:
            return False, "signed_witness_tip_hash_mismatch", {}
    for row in target_ledger:
        if not any(
            candidate["seq"] == row["seq"]
            and candidate["entry_hash"] == row["entry_hash"]
            for candidate in prefix
        ):
            return False, "signed_witness_target_not_member", {}
    evidence = {
        "checkpoint_hash": payload.get("checkpoint_hash"),
        "observed_at": payload.get("observed_at"),
        "ledger_count": count,
        "ledger_tip_seq": payload.get("ledger_tip_seq"),
        "ledger_tip_hash": payload.get("ledger_tip_hash"),
        "ledger_prefix_digest": prefix_digest,
        "target_member_seq": [row["seq"] for row in target_ledger],
    }
    return True, "", evidence


def _read_causal_history(
    tenant_id: str, verdict_id: str, amendment_event_reference: str
) -> dict:
    verdict_rows = sql(
        """
        SELECT v.id::text,
               v.webhook_ingress_identity_id::text,
               v.provider,
               v.provider_native_event_reference,
               v.provider_native_commerce_reference,
               v.canonical_commerce_reference,
               v.status::text,
               v.canonical_net_verified_amount_minor,
               v.currency_code,
               v.last_transition_at,
               v.created_at,
               v.updated_at,
               v.tenant_id::text
          FROM public.b23_match_verdicts AS v
         WHERE v.tenant_id = %s AND v.id = %s
        """,
        (tenant_id, verdict_id),
    )
    if not verdict_rows:
        return {"complete": False, "reason": "verdict_missing"}
    verdict_row = verdict_rows[0]
    current_rows = sql(
        """
        SELECT i.id::text, i.provider,
               i.provider_native_event_reference,
               i.provider_native_commerce_reference,
               i.event_timestamp, i.created_at,
               i.verified_amount_minor, i.verified_amount_currency,
               i.verified_amount_scale,
               i.b26_p2_demotion_reason, i.tenant_id::text
          FROM public.webhook_ingress_identities AS i
         WHERE i.tenant_id = %s AND i.id = %s
        """,
        (tenant_id, str(verdict_row[1])),
    )
    if not current_rows:
        return {"complete": False, "reason": "current_ingress_missing"}
    prior_rows = sql(
        """
        SELECT i.id::text, i.provider,
               i.provider_native_event_reference,
               i.provider_native_commerce_reference,
               i.event_timestamp, i.created_at,
               i.verified_amount_minor, i.verified_amount_currency,
               i.verified_amount_scale,
               i.b26_p2_demotion_reason, i.tenant_id::text
          FROM public.webhook_ingress_identities AS i
         WHERE i.tenant_id = %s AND i.b26_p2_demotion_reason = %s
         ORDER BY i.event_timestamp DESC, i.created_at DESC
         LIMIT 1
        """,
        (
            tenant_id,
            f"superseded_by_provider_amendment:{amendment_event_reference}",
        ),
    )
    if not prior_rows:
        return {"complete": False, "reason": "prior_ingress_missing"}
    ledger_rows = sql(
        """
        SELECT l.seq, l.verdict_id::text, l.tenant_id::text, l.provider,
               l.provider_native_event_reference,
               l.prior_attributed_amount_minor,
               l.new_attributed_amount_minor,
               l.prior_verified_amount_minor, l.new_verified_amount_minor,
               l.prior_authority_state, l.new_authority_state,
               l.prior_source_ingress::text, l.new_source_ingress::text,
               l.recorded_at, l.prev_entry_hash, l.entry_hash
          FROM public.b26_p2_verdict_supersession_ledger AS l
         WHERE l.tenant_id = %s AND l.verdict_id = %s
         ORDER BY l.seq ASC
        """,
        (tenant_id, verdict_id),
    )
    global_ledger_rows = sql(
        """
        SELECT l.seq, l.entry_hash, l.prev_entry_hash, l.recorded_at
          FROM public.b26_p2_verdict_supersession_ledger AS l
         ORDER BY l.seq ASC
        """
    )
    source_rows = sql(
        """
        SELECT i.id::text, i.provider,
               i.provider_native_event_reference,
               i.provider_native_commerce_reference,
               i.event_timestamp, i.created_at,
               i.verified_amount_minor, i.verified_amount_currency,
               i.verified_amount_scale,
               i.b26_p2_demotion_reason, i.tenant_id::text,
               a.statement, a.signature, a.key_sha256,
               i.normalized_commerce_reference_kind,
               i.normalized_commerce_reference_value
          FROM public.webhook_ingress_identities AS i
          LEFT JOIN public.b26_p2_source_money_attestation AS a
                 ON a.webhook_ingress_identity_id = i.id
                AND a.tenant_id = i.tenant_id
         WHERE i.tenant_id = %s
        """,
        (tenant_id,),
    )
    witness_rows = sql(
        "SELECT n, tip_seq, tip_hash"
        " FROM public.b26_p2_read_history_witness_state()"
    )
    continuity_rows = sql(
        "SELECT n, tip"
        " FROM public.b26_p2_read_history_continuity()"
    )
    prefix_rows = sql(
        "SELECT public.b26_p2_read_history_prefix_digest()"
    )
    try:
        source_attestation_public_key = (
            LANE_ROOT / "source_attestation_ed25519.pub"
        ).read_text(encoding="utf-8").strip()
    except OSError:
        source_attestation_public_key = None

    def ingress(row: tuple) -> dict:
        return {
            "id": str(row[0]),
            "provider": str(row[1]),
            "provider_native_event_reference": str(row[2]),
            "provider_native_commerce_reference": str(row[3]),
            "event_timestamp": _utc_second_value(row[4]),
            "created_at": _utc_second_value(row[5]),
            "verified_amount_minor": int(row[6]),
            "verified_amount_currency": str(row[7]).strip().upper(),
            "verified_amount_scale": int(row[8]),
            "demotion_reason": row[9],
            "tenant_id": str(row[10]),
            "source_attestation": (
                {
                    "statement": row[11],
                    "signature": row[12],
                    "key_sha256": row[13],
                }
                if len(row) >= 14 and row[11] is not None
                else None
            ),
            "normalized_commerce_reference_kind": (
                row[14] if len(row) >= 16 else None
            ),
            "normalized_commerce_reference_value": (
                row[15] if len(row) >= 16 else None
            ),
        }

    return {
        "complete": True,
        "reason": None,
        "verdict": {
            "id": str(verdict_row[0]),
            "webhook_ingress_identity_id": str(verdict_row[1]),
            "provider": str(verdict_row[2]),
            "provider_native_event_reference": str(verdict_row[3]),
            "provider_native_commerce_reference": str(verdict_row[4]),
            "canonical_commerce_reference": str(verdict_row[5]),
            "status": str(verdict_row[6]),
            "canonical_net_verified_amount_minor": int(verdict_row[7]),
            "currency_code": str(verdict_row[8]).strip().upper(),
            "last_transition_at": _utc_second_value(verdict_row[9]),
            "created_at": _utc_second_value(verdict_row[10]),
            "updated_at": _utc_second_value(verdict_row[11]),
            "tenant_id": str(verdict_row[12]),
        },
        "current_ingress": ingress(current_rows[0]),
        "prior_ingress": ingress(prior_rows[0]),
        "source_ingresses": {
            str(row[0]): ingress(row) for row in source_rows
        },
        "ledger": [
            {
                "seq": int(row[0]),
                "verdict_id": str(row[1]),
                "tenant_id": str(row[2]),
                "provider": str(row[3]),
                "provider_native_event_reference": str(row[4]),
                "prior_attributed_amount_minor": (
                    int(row[5]) if row[5] is not None else None
                ),
                "new_attributed_amount_minor": (
                    int(row[6]) if row[6] is not None else None
                ),
                "prior_verified_amount_minor": (
                    int(row[7]) if row[7] is not None else None
                ),
                "new_verified_amount_minor": (
                    int(row[8]) if row[8] is not None else None
                ),
                "prior_authority_state": row[9],
                "new_authority_state": row[10],
                "prior_source_ingress": (
                    str(row[11]) if row[11] is not None else None
                ),
                "new_source_ingress": (
                    str(row[12]) if row[12] is not None else None
                ),
                "recorded_at": _utc_precise_value(row[13]),
                "prev_entry_hash": row[14],
                "entry_hash": row[15],
            }
            for row in ledger_rows
        ],
        "global_ledger": [
            {
                "seq": int(row[0]),
                "entry_hash": row[1],
                "prev_entry_hash": row[2],
                "recorded_at": _utc_precise_value(row[3]),
            }
            for row in global_ledger_rows
        ],
        "amendment_event_reference": amendment_event_reference,
        "witness": (
            {
                "count": int(witness_rows[0][0]),
                "tip_seq": (
                    int(witness_rows[0][1])
                    if witness_rows[0][1] is not None
                    else None
                ),
                "tip_hash": witness_rows[0][2],
            }
            if witness_rows
            else None
        ),
        "continuity": (
            {
                "count": int(continuity_rows[0][0]),
                "tip_hash": continuity_rows[0][1],
            }
            if continuity_rows
            else None
        ),
        "prefix_digest": (
            str(prefix_rows[0][0]) if prefix_rows else None
        ),
        "source_attestation_public_key": source_attestation_public_key,
    }


def _verify_witness_commitment(
    *,
    state: dict,
    temp: Path,
    public_key_path: Path,
    history: dict,
) -> dict:
    try:
        from app.trust.history_witness import (  # noqa: PLC0415
            verify_journal,
        )

        journal_path = temp / "history_witness.jsonl"
        heartbeat_path = temp / "history_witness_heartbeat.json"
        journal_path.write_bytes(
            volume_get(WITNESS_VOL, "history_witness.jsonl")
        )
        heartbeat_path.write_bytes(
            volume_get(WITNESS_VOL, "history_witness_heartbeat.json")
        )
        continuity = history.get("continuity") or {}
        witness = history.get("witness") or {}
        journal = verify_journal(
            journal_path,
            public_key_path=public_key_path,
            genesis_hash=state.get("genesis_hash"),
            heartbeat_path=heartbeat_path,
            require_freshness=False,
            expected_count=continuity.get("count"),
            expected_tip_hash=continuity.get("tip_hash"),
            expected_tip_seq=witness.get("tip_seq"),
            expected_prefix_digest=history.get("prefix_digest"),
        )
        latest = journal.latest
        checkpoint_entries = [
            json.loads(line)
            for line in journal_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        latest_entry = next(
            (
                entry
                for entry in reversed(checkpoint_entries)
                if isinstance(entry, dict)
                and isinstance(entry.get("payload"), dict)
                and entry["payload"].get("checkpoint_hash")
                == latest.checkpoint_hash
            ),
            None,
        )
        public_key = public_key_path.read_text(encoding="utf-8").strip()
        return {
            "verified": True,
            "reason": None,
            "count": int(latest.ledger_count),
            "tip_seq": latest.ledger_tip_seq,
            "tip_hash": latest.ledger_tip_hash,
            "prefix_digest": latest.ledger_prefix_digest,
            "public_key": public_key,
            "latest_checkpoint": latest_entry,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "verified": False,
            "reason": f"{type(exc).__name__}:{exc}",
        }


def _verify_source_attestation(
    source: dict,
    public_key: str | None,
    *,
    authority_universe: str | None = None,
    expected_economic_identity: str | None = None,
    expected_key_sha256: str | None = None,
) -> tuple[bool, str]:
    if not isinstance(public_key, str) or not public_key:
        return False, "source_attestation_public_key_missing"
    if not authority_universe:
        return False, "source_attestation_authority_universe_missing"
    attestation = source.get("source_attestation")
    if not isinstance(attestation, dict):
        return False, "source_attestation_missing"
    statement = attestation.get("statement")
    signature = attestation.get("signature")
    if not isinstance(statement, dict) or not isinstance(signature, str):
        return False, "source_attestation_malformed"
    try:
        raw_key = base64.urlsafe_b64decode(
            (public_key + "=" * (-len(public_key) % 4)).encode("ascii")
        )
        fingerprint = hashlib.sha256(raw_key).hexdigest()
        if attestation.get("key_sha256") != fingerprint:
            return False, "source_attestation_key_fingerprint_mismatch"
        if (
            expected_key_sha256 is not None
            and fingerprint != expected_key_sha256
        ):
            return False, "source_attestation_key_not_compiled"
        signature_text = signature.removeprefix("ed25519:")
        if signature_text == signature:
            return False, "source_attestation_signature_algorithm"
        raw_signature = base64.urlsafe_b64decode(
            (signature_text + "=" * (-len(signature_text) % 4)).encode("ascii")
        )
        if int(statement.get("version", 0)) != ATTESTATION_STATEMENT_VERSION:
            return False, "source_attestation_version_unsupported"
        Ed25519PublicKey.from_public_bytes(raw_key).verify(
            raw_signature, canonical_statement_bytes(statement)
        )
    except Exception as exc:  # noqa: BLE001
        return False, f"source_attestation_signature_invalid:{type(exc).__name__}"
    if (
        authority_universe is not None
        and statement.get("authority_universe") != authority_universe
    ):
        return False, "source_attestation_authority_universe_mismatch"
    normalized_value = source.get(
        "normalized_commerce_reference_value"
    ) or source.get("provider_native_commerce_reference")
    if (
        expected_economic_identity is not None
        and normalized_value != expected_economic_identity
    ):
        return False, "source_attestation_economic_identity_mismatch"
    if (
        statement.get("normalized_commerce_reference_kind")
        != source.get("normalized_commerce_reference_kind")
        or statement.get("normalized_commerce_reference_value")
        != source.get("normalized_commerce_reference_value")
    ):
        return False, "source_attestation_economic_identity_mismatch"
    if (
        statement.get("webhook_ingress_identity_id") != source.get("id")
        or statement.get("tenant_id") != source.get("tenant_id")
        or statement.get("provider") != source.get("provider")
        or statement.get("provider_native_event_reference")
        != source.get("provider_native_event_reference")
        or statement.get("provider_native_commerce_reference")
        != source.get("provider_native_commerce_reference")
        or statement.get("verified_amount_minor")
        != source.get("verified_amount_minor")
        or statement.get("verified_amount_currency")
        != source.get("verified_amount_currency")
        or statement.get("verified_amount_scale")
        != source.get("verified_amount_scale")
        or _utc_second_value(statement.get("event_timestamp"))
        != _utc_second_value(source.get("event_timestamp"))
    ):
        return False, "source_attestation_content_mismatch"
    return True, ""


def _final_causal_progression(
    final_signed: dict,
    history: dict,
    *,
    restored_signed: dict,
    restoration_observed_at: str | None,
    amendment_admission_started_at: str | None,
    amendment_admitted_at: str | None,
    final_observed_at: str | None,
    baseline_amount: int,
    amended_amount: int,
    currency: str,
    verdict_id: str,
    trusted_witness_public_key: str | None = None,
    tenant_id_hash: str | None = None,
) -> dict:
    if not history.get("complete"):
        return {
            "established": False,
            "reason": history.get("reason") or "causal_history_unavailable",
        }
    artifact = final_signed.get("artifact")
    if not isinstance(artifact, dict):
        return {"established": False, "reason": "final_artifact_unavailable"}
    verdict = history["verdict"]
    current = history["current_ingress"]
    prior = history["prior_ingress"]
    ledger = history["ledger"]
    reason = ""
    if history.get("amendment_event_reference") != current[
        "provider_native_event_reference"
    ]:
        reason = "amendment_event_reference_mismatch"
    elif verdict["id"] != verdict_id:
        reason = "verdict_identity_mismatch"
    elif tenant_id_hash is not None and (
        not verdict.get("tenant_id")
        or tenant_hash(verdict["tenant_id"]) != tenant_id_hash
    ):
        reason = "verdict_tenant_authority_mismatch"
    elif verdict["webhook_ingress_identity_id"] != current["id"]:
        reason = "current_ingress_link_mismatch"
    elif prior["id"] == current["id"]:
        reason = "prior_ingress_alias"
    elif prior["provider"] != current["provider"]:
        reason = "amendment_provider_mismatch"
    elif (
        prior["provider_native_commerce_reference"]
        != current["provider_native_commerce_reference"]
    ):
        reason = "amendment_commerce_mismatch"
    elif _utc_time(prior["event_timestamp"]) > _utc_time(
        current["event_timestamp"]
    ):
        reason = "amendment_event_order_reversed"
    elif _utc_time(prior["created_at"]) > _utc_time(current["created_at"]):
        reason = "amendment_observation_order_reversed"
    elif _utc_time(verdict["last_transition_at"]) < _utc_time(
        current["event_timestamp"]
    ):
        reason = "verdict_precedes_amendment"
    elif not ledger:
        reason = "supersession_history_missing"
    if reason:
        return {"established": False, "reason": reason}

    first = ledger[0]
    last = ledger[-1]
    if first["prior_source_ingress"] not in (None, prior["id"]):
        reason = "ledger_prior_source_mismatch"
    elif last["new_source_ingress"] != current["id"]:
        reason = "ledger_final_source_mismatch"
    elif last["provider_native_event_reference"] != history[
        "amendment_event_reference"
    ]:
        reason = "ledger_final_event_mismatch"
    elif first["prior_verified_amount_minor"] != baseline_amount:
        reason = "ledger_baseline_amount_mismatch"
    elif last["new_verified_amount_minor"] != amended_amount:
        reason = "ledger_final_amount_mismatch"
    elif first["prior_authority_state"] != "current":
        reason = "ledger_baseline_authority_mismatch"
    elif first["new_authority_state"] != "historically_unverifiable":
        reason = "ledger_fault_authority_mismatch"
    elif last["prior_authority_state"] != "historically_unverifiable":
        reason = "ledger_pre_final_authority_mismatch"
    elif last["new_authority_state"] != "current":
        reason = "ledger_final_authority_mismatch"
    else:
        for previous, row in zip(ledger, ledger[1:]):
            if (
                int(row["seq"]) <= int(previous["seq"])
                or row["prior_verified_amount_minor"]
                != previous["new_verified_amount_minor"]
                or row["prior_source_ingress"]
                != previous["new_source_ingress"]
                or row["prior_authority_state"]
                != previous["new_authority_state"]
            ):
                reason = "ledger_causal_chain_discontinuous"
                break
    if reason:
        return {"established": False, "reason": reason}

    source_ingresses = history.get("source_ingresses") or {}
    global_ledger = history.get("global_ledger") or []
    if not global_ledger:
        reason = "global_history_missing"
    else:
        previous_hash = None
        for row in global_ledger:
            recorded = _utc_time(row.get("recorded_at"))
            if previous_hash is None:
                if row.get("prev_entry_hash") is not None:
                    reason = "global_ledger_origin_mismatch"
                    break
            elif row.get("prev_entry_hash") != previous_hash:
                reason = "global_ledger_chain_discontinuous"
                break
            if recorded is None:
                reason = "global_ledger_time_missing"
                break
            previous_hash = row.get("entry_hash")
    if reason:
        return {"established": False, "reason": reason}
    if _global_prefix_digest(global_ledger) != history.get("prefix_digest"):
        return {"established": False, "reason": "global_prefix_digest_mismatch"}

    global_by_seq = {int(row["seq"]): row for row in global_ledger}
    source_attestation_public_key = history.get(
        "source_attestation_public_key"
    )
    authority_universe = history.get("authority_universe")
    source_attestation_key_sha256 = history.get(
        "source_attestation_public_key_sha256"
    )
    if (
        history.get("require_signature_verification") is True
        and not source_attestation_key_sha256
    ):
        return {
            "established": False,
            "reason": "source_attestation_key_context_missing",
        }
    for row in ledger:
        if row.get("verdict_id") != verdict_id:
            reason = "ledger_verdict_mismatch"
            break
        if row.get("tenant_id") != verdict.get("tenant_id"):
            reason = "ledger_tenant_identity_mismatch"
            break
        if row.get("provider") != current["provider"]:
            reason = "ledger_provider_mismatch"
            break
        global_row = global_by_seq.get(int(row["seq"]))
        if global_row is None:
            reason = "ledger_transition_not_in_global_history"
            break
        if (
            global_row.get("entry_hash") != row.get("entry_hash")
            or global_row.get("prev_entry_hash")
            != row.get("prev_entry_hash")
        ):
            reason = "ledger_transition_membership_mismatch"
            break
        if global_row.get("recorded_at") != row.get("recorded_at"):
            reason = "ledger_transition_time_mismatch"
            break
        if _ledger_entry_hash(row) != row.get("entry_hash"):
            reason = "ledger_transition_content_hash_mismatch"
            break
        new_id = row.get("new_source_ingress")
        new_source = source_ingresses.get(str(new_id)) if new_id else None
        if not isinstance(new_source, dict):
            reason = "ledger_new_source_unexplained"
            break
        if (
            new_source.get("provider") != row.get("provider")
            or new_source.get("tenant_id") != verdict.get("tenant_id")
            or new_source.get("provider_native_event_reference")
            != row.get("provider_native_event_reference")
            or new_source.get("provider_native_commerce_reference")
            != current["provider_native_commerce_reference"]
            or new_source.get("verified_amount_minor")
            != row.get("new_verified_amount_minor")
            or new_source.get("verified_amount_currency") != currency
        ):
            reason = "ledger_new_source_content_mismatch"
            break
        attestation_ok, attestation_reason = _verify_source_attestation(
            new_source,
            source_attestation_public_key,
            authority_universe=authority_universe,
            expected_economic_identity=current[
                "provider_native_commerce_reference"
            ],
            expected_key_sha256=source_attestation_key_sha256,
        )
        if not attestation_ok:
            reason = attestation_reason
            break
        new_created = _utc_time(new_source.get("created_at"))
        new_event = _utc_time(new_source.get("event_timestamp"))
        recorded = _utc_time(row.get("recorded_at"))
        if new_created is None or new_event is None or recorded is None:
            reason = "ledger_source_time_missing"
            break
        prior_id = row.get("prior_source_ingress")
        if prior_id is not None:
            prior_source = source_ingresses.get(str(prior_id))
            if not isinstance(prior_source, dict):
                reason = "ledger_prior_source_unexplained"
                break
            if (
                prior_source.get("provider") != row.get("provider")
                or prior_source.get("tenant_id") != verdict.get("tenant_id")
                or prior_source.get("provider_native_commerce_reference")
                != current["provider_native_commerce_reference"]
                or prior_source.get("verified_amount_minor")
                != row.get("prior_verified_amount_minor")
                or prior_source.get("verified_amount_currency") != currency
            ):
                reason = "ledger_prior_source_content_mismatch"
                break
            attestation_ok, attestation_reason = _verify_source_attestation(
                prior_source,
                source_attestation_public_key,
                authority_universe=authority_universe,
                expected_economic_identity=current[
                    "provider_native_commerce_reference"
                ],
                expected_key_sha256=source_attestation_key_sha256,
            )
            if not attestation_ok:
                reason = attestation_reason
                break
    if reason:
        return {"established": False, "reason": reason}

    restored_artifact = restored_signed.get("artifact")
    restored_created = (
        _utc_time(restored_artifact.get("created_at"))
        if isinstance(restored_artifact, dict)
        else None
    )
    restoration_observed = _utc_time(restoration_observed_at)
    admission_started = _utc_time(amendment_admission_started_at)
    amendment_admitted = _utc_time(amendment_admitted_at)
    final_observed = _utc_time(final_observed_at)
    last_recorded = _utc_time(last["recorded_at"])
    witness = history.get("witness")
    continuity = history.get("continuity")
    commitment = history.get("witness_commitment") or {}
    signed_witness_ok, signed_witness_reason, signed_witness = (
        _verify_signed_latest_checkpoint(
            commitment,
            global_ledger=global_ledger,
            target_ledger=ledger,
            authority_universe=authority_universe,
        )
    )
    compiled_witness_key = history.get("witness_public_key_sha256")
    commitment_key = commitment.get("public_key")
    if (
        history.get("require_signature_verification") is True
        and not compiled_witness_key
    ):
        signed_witness_ok = False
        signed_witness_reason = "signed_witness_key_context_missing"
    elif compiled_witness_key is not None:
        try:
            raw_commitment_key = base64.urlsafe_b64decode(
                (str(commitment_key or "") + "===").encode("ascii")
            )
        except Exception:  # noqa: BLE001
            raw_commitment_key = b""
        if (
            not raw_commitment_key
            or hashlib.sha256(raw_commitment_key).hexdigest()
            != compiled_witness_key
        ):
            signed_witness_ok = False
            signed_witness_reason = "signed_witness_key_not_compiled"
    if (
        trusted_witness_public_key is not None
        and commitment.get("public_key") != trusted_witness_public_key
    ):
        signed_witness_ok = False
        signed_witness_reason = "signed_witness_untrusted_key"
    checkpoint_observed = _utc_time(signed_witness.get("observed_at"))
    if restored_created is None:
        reason = "restored_created_at_invalid"
    elif restoration_observed is None:
        reason = "restoration_observation_missing"
    elif admission_started is None:
        reason = "amendment_admission_start_missing"
    elif amendment_admitted is None:
        reason = "amendment_admission_missing"
    elif final_observed is None:
        reason = "final_observation_missing"
    elif last_recorded is None:
        reason = "accepted_transition_time_missing"
    elif prior["verified_amount_minor"] != baseline_amount:
        reason = "prior_source_money_mismatch"
    elif prior["verified_amount_currency"] != currency:
        reason = "prior_source_currency_mismatch"
    elif current["verified_amount_minor"] != amended_amount:
        reason = "current_source_money_mismatch"
    elif current["verified_amount_currency"] != currency:
        reason = "current_source_currency_mismatch"
    elif verdict["canonical_net_verified_amount_minor"] != amended_amount:
        reason = "verdict_money_mismatch"
    elif verdict["currency_code"] != currency:
        reason = "verdict_currency_mismatch"
    elif restored_created > restoration_observed:
        reason = "restoration_artifact_after_observation"
    elif restoration_observed >= admission_started:
        reason = "restoration_not_before_amendment_admission"
    elif admission_started > amendment_admitted:
        reason = "amendment_admission_time_reversed"
    elif checkpoint_observed is None:
        reason = "signed_witness_observation_missing"
    elif admission_started > checkpoint_observed:
        reason = "amendment_commit_precedes_admission"
    elif restored_created >= checkpoint_observed:
        reason = "restoration_not_before_amendment_commit"
    elif checkpoint_observed > final_observed:
        reason = "final_not_after_amendment_commit"
    elif not witness or not continuity:
        reason = "history_witness_state_missing"
    elif not commitment.get("verified"):
        reason = "history_witness_commitment_unverified"
    elif not signed_witness_ok:
        reason = signed_witness_reason
    elif checkpoint_observed < last_recorded:
        reason = "signed_witness_predates_transition"
    elif int(witness["count"]) != int(continuity["count"]):
        reason = "history_witness_count_diverged"
    elif witness["tip_hash"] != continuity["tip_hash"]:
        reason = "history_witness_tip_diverged"
    elif (
        witness["tip_seq"] is not None
        and int(witness["tip_seq"]) < int(last["seq"])
    ):
        reason = "history_witness_tip_seq_behind_transition"
    elif (
        witness["tip_seq"] is not None
        and int(witness["tip_seq"]) == int(last["seq"])
        and last["entry_hash"] != witness["tip_hash"]
    ):
        reason = "ledger_tip_commitment_mismatch"
    elif int(commitment.get("count", -1)) != int(continuity["count"]):
        reason = "signed_witness_count_mismatch"
    elif commitment.get("tip_hash") != continuity["tip_hash"]:
        reason = "signed_witness_tip_mismatch"
    elif commitment.get("prefix_digest") != history.get("prefix_digest"):
        reason = "signed_witness_prefix_mismatch"
    if reason:
        return {"established": False, "reason": reason}

    for row in ledger:
        recorded = _utc_time(row.get("recorded_at"))
        if recorded is not None and recorded > checkpoint_observed:
            return {
                "established": False,
                "reason": "target_transition_after_witness",
            }
        for source_id in (
            row.get("prior_source_ingress"),
            row.get("new_source_ingress"),
        ):
            if source_id is None:
                continue
            source = source_ingresses.get(str(source_id)) or {}
            created = _utc_time(source.get("created_at"))
            if created is not None and created > checkpoint_observed:
                return {
                    "established": False,
                    "reason": "source_after_witness",
                }
    for row in global_ledger[: int(signed_witness.get("ledger_count", 0))]:
        recorded = _utc_time(row.get("recorded_at"))
        if recorded is not None and recorded > checkpoint_observed:
            return {
                "established": False,
                "reason": "global_transition_after_witness",
            }

    created_at = _utc_time(artifact.get("created_at"))
    if created_at is None:
        reason = "final_created_at_invalid"
    elif (
        last_recorded is not None
        and created_at < last_recorded.replace(microsecond=0)
    ):
        reason = "final_precedes_accepted_transition"
    elif created_at > final_observed:
        reason = "final_created_after_observation"
    elif created_at < _utc_time(verdict["last_transition_at"]):
        reason = "final_precedes_verdict_transition"
    if reason:
        return {"established": False, "reason": reason}

    expected_provider = _expected_provider_entry(
        provider=current["provider"],
        event_reference=current["provider_native_event_reference"],
        commerce_reference=current[
            "provider_native_commerce_reference"
        ],
        observed_at=verdict["created_at"],
    )
    expected_match = _expected_match_entry(verdict)
    expected_webhook = _expected_webhook_entry(verdict, current)
    actual_provider = _one_provenance(artifact, "provider_native_reference")
    actual_match = _one_provenance(artifact, "match_verdict")
    actual_webhook = _one_provenance(artifact, "webhook_signature")
    restored_text = _one_provenance(
        restored_signed.get("artifact") or {}, "text_disposition"
    )
    final_text = _one_provenance(artifact, "text_disposition")
    if not _entry_matches(actual_provider, expected_provider):
        reason = "final_provider_history_mismatch"
    elif not _entry_matches(actual_match, expected_match):
        reason = "final_match_history_mismatch"
    elif not _entry_matches(actual_webhook, expected_webhook):
        reason = "final_ingress_history_mismatch"
    elif (
        not isinstance(final_text, dict)
        or not isinstance(restored_text, dict)
        or any(
            final_text.get(key) != restored_text.get(key)
            for key in (
                "source_ref",
                "source_ref_hash",
                "source_snapshot_hash",
            )
        )
    ):
        reason = "final_text_transform_mismatch"
    elif artifact.get("truth_authority", {}).get(
        "source_snapshot_hash"
    ) != expected_match["source_snapshot_hash"]:
        reason = "final_truth_snapshot_mismatch"
    elif (
        artifact.get("evidence_temporal_boundary") or {}
    ).get("evidence_snapshot_hash") != expected_match[
        "source_snapshot_hash"
    ]:
        reason = "final_evidence_snapshot_mismatch"
    elif _utc_second_value(
        (artifact.get("evidence_temporal_boundary") or {}).get(
            "evidence_snapshot_at"
        )
    ) != _utc_second_value(verdict.get("updated_at")):
        reason = "final_evidence_snapshot_time_mismatch"
    elif artifact.get("match_verdict_status") != (
        normalize_match_verdict_status(verdict["status"])
    ):
        reason = "final_public_qualification_mismatch"
    elif artifact.get("data_completeness_status") != (
        data_completeness_for_match_status(verdict["status"])
    ):
        reason = "final_completeness_mismatch"
    elif artifact.get("verified_revenue_minor") != amended_amount:
        reason = "final_amount_mismatch"
    elif artifact.get("currency") != currency:
        reason = "final_currency_mismatch"
    if reason:
        return {"established": False, "reason": reason}
    return {
        "established": True,
        "reason": None,
        "history_digest": _semantic_digest(history),
        "ledger_sequence": [int(row["seq"]) for row in ledger],
        "prior_ingress": prior["id"],
        "current_ingress": current["id"],
        "accepted_amendment_event": current[
            "provider_native_event_reference"
        ],
        "accepted_transition_at": last["recorded_at"],
        "causal_order": {
            "restoration_observed_at": restoration_observed_at,
            "amendment_admission_started_at": amendment_admission_started_at,
            "amendment_admitted_at": amendment_admitted_at,
            "accepted_transition_at": last["recorded_at"],
            "final_observation_window": history.get("final_observation"),
            "final_observed_at": final_observed_at,
            "final_created_at": artifact.get("created_at"),
            "signed_precision": "second",
            "ledger_precision": "microsecond",
        },
        "signed_witness": signed_witness,
        "expected_provider": expected_provider,
        "expected_match": expected_match,
        "expected_webhook": expected_webhook,
    }


def _signed_structure(
    observation: dict,
    verdict_id: str,
    amount: int,
    currency: str,
    expected_tenant_id_hash: str,
) -> tuple[bool, str]:
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
    if artifact.get("tenant_id_hash") != expected_tenant_id_hash:
        return False, "signed_tenant_mismatch"
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
    if artifact.get("match_verdict_status") not in _contract_enum(
        "match_verdict_status"
    ):
        return False, "signed_financial_qualification"
    if artifact.get("data_completeness_status") not in _contract_enum(
        "data_completeness_status"
    ):
        return False, "signed_data_completeness"
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


def _offline_verification(observation: dict) -> dict:
    artifact = observation.get("artifact")
    basis = observation.get("public_key_basis") or {}
    jwks = basis.get("jwks") or {}
    keys = jwks.get("keys") if isinstance(jwks, dict) else None
    if not isinstance(artifact, dict) or not keys:
        return {"verification_status": "rejected", "reason_code": "jwks_unavailable"}
    parsed = []
    for key in keys:
        if not isinstance(key, dict):
            return {"verification_status": "rejected", "reason_code": "jwks_malformed"}
        try:
            x = str(key.get("x") or "")
            public = Ed25519PublicKey.from_public_bytes(
                base64.urlsafe_b64decode((x + "===").encode("ascii"))
            )
            valid_from = datetime.fromisoformat(
                str(key["skeldir_valid_from"]).replace("Z", "+00:00")
            )
            valid_until = (
                datetime.fromisoformat(
                    str(key["skeldir_valid_until"]).replace("Z", "+00:00")
                )
                if key.get("skeldir_valid_until")
                else None
            )
            retired_at = (
                datetime.fromisoformat(
                    str(key["skeldir_retired_at"]).replace("Z", "+00:00")
                )
                if key.get("skeldir_retired_at")
                else None
            )
            state = str(key.get("skeldir_key_state") or "")
            if key.get("kty") != "OKP" or key.get("crv") != "Ed25519":
                return {"verification_status": "rejected", "reason_code": "jwks_key_type"}
            if state not in {"active", "verification_only", "revoked", "expired"}:
                return {"verification_status": "rejected", "reason_code": "jwks_key_state"}
            parsed.append(
                TrustSigningKey(
                    kid=str(key.get("kid") or ""),
                    algorithm="ed25519",
                    public_key=public,
                    private_key=None,
                    state=state,  # type: ignore[arg-type]
                    valid_from=valid_from,
                    valid_until=valid_until,
                    retired_at=retired_at,
                )
            )
        except Exception as exc:  # noqa: BLE001
            return {
                "verification_status": "rejected",
                "reason_code": f"jwks_key_invalid:{type(exc).__name__}",
            }
    try:
        registry = TrustKeyRegistry(tuple(parsed)).public_only()
        created_at = datetime.fromisoformat(
            str(artifact.get("created_at") or "").replace("Z", "+00:00")
        )
        result = verify_trust_envelope(
            artifact, key_registry=registry, at_time=created_at
        )
        return result.external_projection()
    except Exception as exc:  # noqa: BLE001
        return {
            "verification_status": "rejected",
            "reason_code": f"offline_verification_error:{type(exc).__name__}",
        }


def _trust_registry_digest(jwks: dict) -> str:
    return hashlib.sha256(
        json.dumps(
            jwks,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _verify_observation_with_jwks(
    observation: dict,
    jwks: dict,
    verdict_id: str,
    amount: int,
    currency: str,
    expected_tenant_id_hash: str,
    expected_key_sha256: str | None = None,
) -> dict:
    ok, reason = _signed_structure(
        observation, verdict_id, amount, currency, expected_tenant_id_hash
    )
    if not ok:
        return {"verification_status": "rejected", "reason_code": reason}
    artifact = observation.get("artifact") or {}
    keys = jwks.get("keys") if isinstance(jwks, dict) else None
    matching = None
    for key in keys or []:
        if isinstance(key, dict) and key.get("kid") == artifact.get(
            "signing_key_id"
        ):
            matching = key
            break
    valid = bool(
        isinstance(matching, dict)
        and matching.get("x")
        and _key_lifecycle_valid(artifact, matching)
    )
    if expected_key_sha256 is not None:
        try:
            raw_key = base64.urlsafe_b64decode(
                (str((matching or {}).get("x") or "") + "===").encode(
                    "ascii"
                )
            )
        except Exception:  # noqa: BLE001
            raw_key = b""
        if (
            not raw_key
            or hashlib.sha256(raw_key).hexdigest()
            != expected_key_sha256
        ):
            return {
                "verification_status": "rejected",
                "reason_code": "trust_key_not_compiled",
            }
    trusted = dict(observation)
    trusted["public_key_basis"] = {
        "jwks": jwks,
        "matching_key": matching,
        "valid": valid,
    }
    return _offline_verification(trusted)


def _signed_observation(
    observation: dict,
    verdict_id: str,
    amount: int,
    currency: str,
    expected_tenant_id_hash: str,
) -> tuple[bool, str]:
    ok, reason = _signed_structure(
        observation, verdict_id, amount, currency, expected_tenant_id_hash
    )
    if not ok:
        return ok, reason
    basis = _public_key_basis(observation.get("artifact") or {})
    observation["public_key_basis"] = basis
    if not basis.get("valid"):
        return False, "signed_public_key_basis_invalid"
    offline = _offline_verification(observation)
    observation["offline_verification"] = offline
    if offline.get("verification_status") != "verified":
        return False, "signed_offline_verification_failed"
    return True, ""


def _wait_signed(
    tenant: dict,
    verdict_id: str,
    amount: int,
    currency: str,
    *,
    attempts: int = 60,
    window: dict | None = None,
) -> dict:
    if window is not None:
        window["started_at"] = _now_iso()
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
                "expected_tenant_id_hash": tenant_hash(tenant["tenant_id"]),
            }
            established, reason = _signed_observation(
                observation,
                verdict_id,
                amount,
                currency,
                str(observation.get("expected_tenant_id_hash") or ""),
            )
            observation["established"] = established
            observation["invalid_reason"] = reason or None
            last = observation
            if established:
                if window is not None:
                    window["observed_at"] = _now_iso()
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
        "tenant_id_hash": tenant_hash(tenant["tenant_id"]),
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
    signature_requirement = (
        record.get("require_signature_verification") is True
        or (
            record.get("mode") == "positive"
            and record.get("passed") is True
        )
    )
    baseline_signature_ok = not signature_requirement
    restored_signature_ok = not signature_requirement
    final_signature_ok = not signature_requirement
    restoration_semantic_authority = {
        "established": False,
        "reason": "not_evaluated",
    }
    final_causal_progression = {
        "established": False,
        "reason": "not_evaluated",
    }
    baseline_authority = {"established": False, "reason": "not_evaluated"}
    restored_authority = {"established": False, "reason": "not_evaluated"}
    final_authority = {"established": False, "reason": "not_evaluated"}
    baseline_source_authority = {"established": False, "reason": "not_evaluated"}
    restored_source_authority = {"established": False, "reason": "not_evaluated"}
    final_source_authority = {"established": False, "reason": "not_evaluated"}
    baseline_history_authority = {"established": False, "reason": "not_evaluated"}
    restored_history_authority = {"established": False, "reason": "not_evaluated"}
    if isinstance(expected_amount, int) and isinstance(verdict_id, str) and subject:
        currency = str(baseline.get("currency") or "")
        tenant_id_hash = str(baseline.get("tenant_id_hash") or "")
        baseline_structure_ok, _ = _signed_structure(
            baseline_signed, verdict_id, expected_amount, currency, tenant_id_hash
        )
        restored_structure_ok, _ = _signed_structure(
            restored_baseline, verdict_id, expected_amount, currency, tenant_id_hash
        )
        final_structure_ok, _ = _signed_structure(
            final_signed, verdict_id, amended_amount, currency, tenant_id_hash
        )
        if signature_requirement:
            trust_jwks = record.get("trust_jwks")
            compiled_trust_registry = (record.get("artifact") or {}).get(
                "compiled_trust_registry_sha256"
            )
            if (
                isinstance(trust_jwks, dict)
                and compiled_trust_registry
                and _trust_registry_digest(trust_jwks)
                == compiled_trust_registry
            ):
                baseline_signature_ok = (
                    _verify_observation_with_jwks(
                        baseline_signed,
                        trust_jwks,
                        verdict_id,
                        expected_amount,
                        currency,
                        tenant_id_hash,
                    ).get("verification_status")
                    == "verified"
                )
                restored_signature_ok = (
                    _verify_observation_with_jwks(
                        restored_baseline,
                        trust_jwks,
                        verdict_id,
                        expected_amount,
                        currency,
                        tenant_id_hash,
                    ).get("verification_status")
                    == "verified"
                )
                final_signature_ok = (
                    _verify_observation_with_jwks(
                        final_signed,
                        trust_jwks,
                        verdict_id,
                        amended_amount,
                        currency,
                        tenant_id_hash,
                    ).get("verification_status")
                    == "verified"
                )
        reference_artifact = baseline_signed.get("artifact") or {}
        baseline_authority = _issued_authority(
            baseline_signed.get("artifact") or {},
            reference_artifact,
            window=None,
            require_window=False,
        )
        restored_authority = _issued_authority(
            restored_baseline.get("artifact") or {},
            reference_artifact,
            window=None,
            require_window=False,
        )
        final_authority = _issued_authority(
            final_signed.get("artifact") or {},
            reference_artifact,
            window=record.get("final_observation"),
            require_window=True,
        )
        baseline_boundary = (
            baseline_signed.get("artifact") or {}
        ).get("evidence_temporal_boundary") or {}
        restored_boundary = (
            restored_baseline.get("artifact") or {}
        ).get("evidence_temporal_boundary") or {}
        causal_history = record.get("causal_history") or {}
        final_source_observed = (
            (causal_history.get("verdict") or {}).get("updated_at")
        )
        baseline_source_authority = _result_source_authority(
            baseline_signed.get("artifact") or {},
            amount=expected_amount,
            currency=currency,
            observed_at=baseline_boundary.get("evidence_snapshot_at"),
        )
        restored_source_authority = _result_source_authority(
            restored_baseline.get("artifact") or {},
            amount=expected_amount,
            currency=currency,
            observed_at=restored_boundary.get("evidence_snapshot_at"),
        )
        final_source_authority = _result_source_authority(
            final_signed.get("artifact") or {},
            amount=amended_amount,
            currency=currency,
            observed_at=final_source_observed,
        )
        verdict_record = causal_history.get("verdict") or {}
        prior_record = causal_history.get("prior_ingress") or {}
        if verdict_record and prior_record:
            baseline_history_authority = _result_history_authority(
                baseline_signed.get("artifact") or {},
                verdict_record,
                prior_record,
            )
            restored_history_authority = _result_history_authority(
                restored_baseline.get("artifact") or {},
                verdict_record,
                prior_record,
            )
        restoration_semantic_authority = _restoration_semantic_authority(
            baseline_signed,
            restored_baseline,
            restored_observation=record.get("restoration_observation"),
        )
        final_causal_progression = _final_causal_progression(
            final_signed,
            record.get("causal_history") or {},
            restored_signed=restored_baseline,
            restoration_observed_at=record.get("restoration_observed_at"),
            amendment_admission_started_at=record.get(
                "amendment_admission_started_at"
            ),
            amendment_admitted_at=record.get("amendment_admitted_at"),
            final_observed_at=record.get("final_observed_at"),
            baseline_amount=expected_amount,
            amended_amount=amended_amount,
            currency=currency,
            verdict_id=verdict_id,
            trusted_witness_public_key=record.get(
                "witness_public_key"
            ),
            tenant_id_hash=tenant_id_hash,
        )
        record["baseline_authority"] = baseline_authority
        record["restored_authority"] = restored_authority
        record["final_authority"] = final_authority
        record["baseline_source_authority"] = baseline_source_authority
        record["restored_source_authority"] = restored_source_authority
        record["final_source_authority"] = final_source_authority
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
            baseline_signature_ok is True,
            baseline_authority.get("established") is True,
            baseline_source_authority.get("established") is True,
            baseline_history_authority.get("established") is True,
            (baseline_signed.get("offline_verification") or {}).get(
                "verification_status"
            )
            == "verified",
            baseline_verify[0] == 200,
            isinstance(baseline_verify[1], dict)
            and baseline_verify[1].get("verification_status") == "verified",
            fault.get("http") == 404,
            fault.get("status") == "refused",
            fault.get("reason") == "history_integrity_unverifiable",
            fault.get("specific") is True,
            fault.get("new_row") is True,
            fault.get("money_minor") is None,
            restored_baseline.get("status") == 200,
            restored_baseline.get("established") is True,
            restored_structure_ok is True,
            restored_signature_ok is True,
            restored_authority.get("established") is True,
            restored_source_authority.get("established") is True,
            restored_history_authority.get("established") is True,
            restoration_semantic_authority.get("established") is True,
            (restored_baseline.get("offline_verification") or {}).get(
                "verification_status"
            )
            == "verified",
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
            final_signature_ok is True,
            final_authority.get("established") is True,
            final_source_authority.get("established") is True,
            final_causal_progression.get("established") is True,
            (final_signed.get("offline_verification") or {}).get(
                "verification_status"
            )
            == "verified",
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


def _a12_established(record: dict) -> bool:
    return (record.get("a12_contradictory_state") or {}).get(
        "established"
    ) is True


_A12_RESULT_DIR = REPO / "docs/forensics/evidence/b26_p2_xxv_a8"
_A12_PROOF_SOURCE_PATHS = (
    "scripts/ci/validate_b26_p2_xxii_composition.py",
    "scripts/ci/b26_p2_xxv_attestation_sweep.py",
    "backend/app/revenue_verification/source_attestation.py",
    "backend/app/revenue_verification/source_evidence.py",
    "backend/app/trust/builder.py",
    "backend/app/trust/money_source_adapter.py",
    "backend/app/revenue_verification/corrections.py",
    "backend/app/revenue_verification/batch_engine.py",
    "alembic/versions/007_skeldir_foundation/202610270001_b26_p2_corrective_xxv_source_attestation.py",
    "alembic/versions/007_skeldir_foundation/202610270002_b26_p2_corrective_xxv_provider_amendment.py",
    "alembic/versions/007_skeldir_foundation/202610280001_b26_p2_xxv_post_capture_adjustment.py",
)
_A12_VERDICT_COLUMNS = (
    "id",
    "tenant_id",
    "attribution_event_id",
    "webhook_ingress_identity_id",
    "status",
    "match_quality",
    "verified_amount_minor",
    "attributed_amount_minor",
    "canonical_expected_gross_amount_minor",
    "canonical_captured_gross_amount_minor",
    "canonical_net_verified_amount_minor",
    "discrepancy_amount_minor",
    "discrepancy_ratio_bps",
    "discrepancy_band",
    "b26_p2_source_authority_state",
    "currency_code",
    "updated_at",
    "last_transition_at",
)
_A12_INGRESS_COLUMNS = (
    "id",
    "tenant_id",
    "event_id",
    "verified_amount_minor",
    "verified_amount_currency",
    "verified_amount_scale",
    "updated_at",
    "created_at",
)
_A12_ATTRIBUTION_COLUMNS = (
    "id",
    "tenant_id",
    "revenue_cents",
    "conversion_value_cents",
    "currency",
    "updated_at",
)


def _a12_file_hash(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _a12_proof_source_hashes() -> dict[str, str | None]:
    return {
        relative: _a12_file_hash(REPO / relative)
        for relative in _A12_PROOF_SOURCE_PATHS
    }


def _a12_proof_dsn(tenant_id: str) -> str:
    """The required proof principal, scoped to the subject's RLS cohort.

    The mandatory CI proof runs as ``migration_owner``.  ``public`` financial
    tables are FORCE RLS, so that principal's census is empty unless the
    governing tenant setting is present.  The setting is the real tenant under
    test, not a substitute principal or a different database.
    """
    from urllib.parse import quote  # noqa: PLC0415

    return role_dsn("migration_owner") + "?options=" + quote(
        f"-c app.current_tenant_id={tenant_id}", safe=""
    )


def _a12_role_identity(dsn: str) -> dict:
    import psycopg2  # noqa: PLC0415

    conn = psycopg2.connect(dsn)
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                "SELECT current_user, session_user, r.rolsuper,"
                " r.rolbypassrls, r.rolcreatedb, r.rolcreaterole,"
                " r.rolreplication, r.rolinherit,"
                " current_setting('transaction_isolation')"
                " FROM pg_roles AS r WHERE r.rolname = current_user"
            )
            row = cur.fetchone()
            cur.execute(
                "SELECT has_table_privilege(current_user,"
                " 'public.b23_match_verdicts', 'UPDATE'),"
                " has_table_privilege(current_user,"
                " 'public.webhook_ingress_identities', 'UPDATE'),"
                " has_table_privilege(current_user,"
                " 'public.attribution_events', 'UPDATE')"
            )
            privileges = cur.fetchone()
    finally:
        conn.close()
    return {
        "current_user": row[0],
        "session_user": row[1],
        "rolsuper": bool(row[2]),
        "rolbypassrls": bool(row[3]),
        "rolcreatedb": bool(row[4]),
        "rolcreaterole": bool(row[5]),
        "rolreplication": bool(row[6]),
        "rolinherit": bool(row[7]),
        "transaction_isolation": row[8],
        "update_privileges": {
            "b23_match_verdicts": bool(privileges[0]),
            "webhook_ingress_identities": bool(privileges[1]),
            "attribution_events": bool(privileges[2]),
        },
    }


def _a12_row(cur, table: str, columns: tuple[str, ...], tenant_id: str, row_id):
    from psycopg2 import sql as psql  # noqa: PLC0415

    cur.execute(
        psql.SQL("SELECT {} FROM public.{} WHERE tenant_id = %s AND id = %s").format(
            psql.SQL(", ").join(psql.Identifier(name) for name in columns),
            psql.Identifier(table),
        ),
        (tenant_id, row_id),
    )
    row = cur.fetchone()
    if row is None:
        return None
    return dict(zip(columns, row))


def _a12_table_states(cur) -> dict[str, dict]:
    states: dict[str, dict] = {}
    for table in (
        "b23_match_verdicts",
        "webhook_ingress_identities",
        "attribution_events",
    ):
        cur.execute(
            "SELECT c.relrowsecurity, c.relforcerowsecurity"
            " FROM pg_class AS c JOIN pg_namespace AS n"
            " ON n.oid = c.relnamespace"
            " WHERE n.nspname = 'public' AND c.relname = %s",
            (table,),
        )
        flags = cur.fetchone()
        if flags is None:
            raise RuntimeError(f"a12_table_missing:{table}")
        cur.execute(
            "SELECT t.tgname, t.tgenabled FROM pg_trigger AS t"
            " JOIN pg_class AS c ON c.oid = t.tgrelid"
            " JOIN pg_namespace AS n ON n.oid = c.relnamespace"
            " WHERE n.nspname = 'public' AND c.relname = %s"
            " AND NOT t.tgisinternal ORDER BY t.tgname",
            (table,),
        )
        states[table] = {
            "relrowsecurity": bool(flags[0]),
            "relforcerowsecurity": bool(flags[1]),
            "triggers": [
                {"name": str(name), "tgenabled": str(mode)}
                for name, mode in cur.fetchall()
            ],
        }
    return states


def _a12_assert_governed_states(states: dict[str, dict]) -> str | None:
    for table, state in states.items():
        if not state["relrowsecurity"] or not state["relforcerowsecurity"]:
            return f"a12_rls_not_governed:{table}"
        for trigger in state["triggers"]:
            if trigger["tgenabled"] != "O":
                return (
                    "a12_trigger_not_governed:"
                    f"{table}:{trigger['name']}:{trigger['tgenabled']}"
                )
    return None


def _a12_set_table_state(cur, table: str, state: dict) -> None:
    from psycopg2 import sql as psql  # noqa: PLC0415

    relation = psql.SQL("public.{}").format(psql.Identifier(table))
    cur.execute(
        psql.SQL("ALTER TABLE {} {} ROW LEVEL SECURITY").format(
            relation,
            psql.SQL("ENABLE" if state["relrowsecurity"] else "DISABLE"),
        )
    )
    cur.execute(
        psql.SQL("ALTER TABLE {} {} ROW LEVEL SECURITY").format(
            relation,
            psql.SQL("FORCE" if state["relforcerowsecurity"] else "NO FORCE"),
        )
    )
    for trigger in state["triggers"]:
        action = {
            "O": "ENABLE",
            "D": "DISABLE",
            "A": "ENABLE ALWAYS",
            "R": "ENABLE REPLICA",
        }.get(trigger["tgenabled"])
        if action is None:
            raise RuntimeError(
                f"a12_trigger_mode_unknown:{table}:{trigger['name']}:"
                f"{trigger['tgenabled']}"
            )
        cur.execute(
            psql.SQL("ALTER TABLE {} {} TRIGGER {}").format(
                relation,
                psql.SQL(action),
                psql.Identifier(trigger["name"]),
            )
        )


def _a12_snapshot_rows(cur, tenant_id: str, verdict_id: str) -> dict:
    verdict = _a12_row(
        cur, "b23_match_verdicts", _A12_VERDICT_COLUMNS, tenant_id, verdict_id
    )
    if verdict is None:
        return {"reason": "verdict_missing"}
    ingress_id = verdict["webhook_ingress_identity_id"]
    attribution_id = verdict["attribution_event_id"]
    if ingress_id is None:
        return {"reason": "ingress_link_missing", "verdict": verdict}
    if attribution_id is None:
        return {"reason": "attribution_link_missing", "verdict": verdict}
    ingress = _a12_row(
        cur,
        "webhook_ingress_identities",
        _A12_INGRESS_COLUMNS,
        tenant_id,
        ingress_id,
    )
    if ingress is None:
        return {"reason": "ingress_missing", "verdict": verdict}
    attribution = _a12_row(
        cur,
        "attribution_events",
        _A12_ATTRIBUTION_COLUMNS,
        tenant_id,
        attribution_id,
    )
    if attribution is None:
        return {"reason": "attribution_missing", "verdict": verdict}
    return {
        "verdict": verdict,
        "ingress": ingress,
        "attribution": attribution,
        "attribution_matches_ingress_event": (
            str(ingress["event_id"]) == str(attribution_id)
        ),
    }


def _a12_serialise_row(row: dict | None) -> dict | None:
    if row is None:
        return None
    return {
        key: (
            value.isoformat()
            if hasattr(value, "isoformat")
            else str(value)
            if not isinstance(value, (str, int, float, bool, type(None)))
            else value
        )
        for key, value in row.items()
    }


def _a12_serialise_snapshot(snapshot: dict) -> dict:
    out: dict = {}
    for key, value in snapshot.items():
        if key in {"verdict", "ingress", "attribution"} and isinstance(value, dict):
            out[key] = _a12_serialise_row(value)
        else:
            out[key] = value
    return out


def _a12_rows_json(snapshot: dict) -> str:
    return json.dumps(
        {
            key: _a12_serialise_row(snapshot[key])
            for key in ("verdict", "ingress", "attribution")
            if key in snapshot
        },
        sort_keys=True,
        default=str,
    )


def _a12_attestation_verifies(evidence: dict) -> bool:
    attestation = evidence.get("attestation")
    if not isinstance(attestation, dict):
        return False
    try:
        statement = json.loads(str(attestation["statement"]))
        verify_signature(
            statement,
            str(attestation["signature"] or ""),
            public_key_path=str(LANE_ROOT / "source_attestation_ed25519.pub"),
        )
    except Exception:  # noqa: BLE001
        return False
    return True


def _a12_mutate(
    tenant_id: str,
    verdict_id: str,
    *,
    baseline_amount: int,
    currency: str,
) -> dict:
    import psycopg2  # noqa: PLC0415
    from psycopg2 import sql as psql  # noqa: PLC0415

    contradictory = int(baseline_amount) + 123457
    result: dict = {
        "contradictory_amount_minor": contradictory,
        "currency": currency,
        "committed": False,
    }
    conn = psycopg2.connect(role_dsn("migration_owner"))
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            result["actor"] = _a12_role_identity(role_dsn("migration_owner"))
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, true)",
                (tenant_id,),
            )
            snapshot = _a12_snapshot_rows(cur, tenant_id, verdict_id)
            if snapshot.get("reason"):
                raise RuntimeError(f"a12_snapshot_refused:{snapshot['reason']}")
            states = _a12_table_states(cur)
            snapshot["__guard_states__"] = states
            result["original"] = snapshot
            result["guard_configuration_original"] = states
            governed_reason = _a12_assert_governed_states(states)
            if governed_reason:
                raise RuntimeError(governed_reason)
            verdict = snapshot["verdict"]
            ingress = snapshot["ingress"]
            attribution = snapshot["attribution"]
            if int(verdict["verified_amount_minor"]) != baseline_amount:
                raise RuntimeError("a12_baseline_verdict_verified_mismatch")
            if int(verdict["attributed_amount_minor"]) != baseline_amount:
                raise RuntimeError("a12_baseline_verdict_attributed_mismatch")
            if int(verdict["canonical_captured_gross_amount_minor"]) != baseline_amount:
                raise RuntimeError("a12_baseline_verdict_captured_mismatch")
            if int(verdict["canonical_net_verified_amount_minor"]) != baseline_amount:
                raise RuntimeError("a12_baseline_verdict_net_mismatch")
            if int(verdict["canonical_expected_gross_amount_minor"]) != baseline_amount:
                raise RuntimeError("a12_baseline_verdict_expected_mismatch")
            if str(verdict["currency_code"]).upper() != currency.upper():
                raise RuntimeError("a12_baseline_verdict_currency_mismatch")
            if int(ingress["verified_amount_minor"]) != baseline_amount:
                raise RuntimeError("a12_baseline_ingress_amount_mismatch")
            if str(ingress["verified_amount_currency"]).upper() != currency.upper():
                raise RuntimeError("a12_baseline_ingress_currency_mismatch")
            if int(attribution["revenue_cents"]) != baseline_amount:
                raise RuntimeError("a12_baseline_attribution_amount_mismatch")

            # The actor is the relation owner.  Its write uses the exact
            # trigger modes currently installed; this experiment suppresses
            # those triggers only for the duration of the write and restores
            # each saved mode before commit.  No consumer observes the
            # disabled state.
            for table, state in states.items():
                for trigger in state["triggers"]:
                    cur.execute(
                        psql.SQL("ALTER TABLE public.{} DISABLE TRIGGER {}").format(
                            psql.Identifier(table),
                            psql.Identifier(trigger["name"]),
                        )
                    )
            cur.execute(
                "UPDATE public.b23_match_verdicts"
                " SET verified_amount_minor = %s,"
                " attributed_amount_minor = %s,"
                " canonical_net_verified_amount_minor = %s,"
                " canonical_captured_gross_amount_minor = %s,"
                " canonical_expected_gross_amount_minor = %s,"
                " discrepancy_amount_minor = 0,"
                " discrepancy_ratio_bps = 0,"
                " discrepancy_band = 'exact',"
                " updated_at = now()"
                " WHERE tenant_id = %s AND id = %s",
                (
                    contradictory,
                    contradictory,
                    contradictory,
                    contradictory,
                    contradictory,
                    tenant_id,
                    verdict_id,
                ),
            )
            cur.execute(
                "UPDATE public.webhook_ingress_identities"
                " SET verified_amount_minor = %s, updated_at = now()"
                " WHERE tenant_id = %s AND id = %s",
                (contradictory, tenant_id, ingress["id"]),
            )
            cur.execute(
                "UPDATE public.attribution_events"
                " SET revenue_cents = %s, updated_at = now()"
                " WHERE tenant_id = %s AND id = %s",
                (contradictory, tenant_id, attribution["id"]),
            )
            for table, state in states.items():
                _a12_set_table_state(cur, table, state)
        conn.commit()
        result["mutation_committed"] = True
    except Exception as exc:  # noqa: BLE001 - preserve the first attributable error
        conn.rollback()
        result["mutation_error"] = f"{type(exc).__name__}:{exc}"
        result["mutation_committed"] = False
    finally:
        conn.close()

    if not result.get("mutation_committed"):
        return result

    verify = psycopg2.connect(role_dsn("migration_owner"))
    try:
        verify.autocommit = True
        with verify.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (tenant_id,),
            )
            observed = _a12_snapshot_rows(cur, tenant_id, verdict_id)
            observed_states = _a12_table_states(cur)
        verdict = observed.get("verdict") or {}
        ingress = observed.get("ingress") or {}
        attribution = observed.get("attribution") or {}
        operands = {
            "verdict_verified": int(verdict.get("verified_amount_minor") or -1),
            "verdict_attributed": int(
                verdict.get("attributed_amount_minor") or -1
            ),
            "verdict_net": int(
                verdict.get("canonical_net_verified_amount_minor") or -1
            ),
            "verdict_captured": int(
                verdict.get("canonical_captured_gross_amount_minor") or -1
            ),
            "verdict_expected": int(
                verdict.get("canonical_expected_gross_amount_minor") or -1
            ),
            "verdict_discrepancy_amount": int(
                verdict.get("discrepancy_amount_minor") or -1
            ),
            "verdict_discrepancy_ratio": int(
                verdict.get("discrepancy_ratio_bps") or -1
            ),
            "verdict_band": verdict.get("discrepancy_band"),
            "verdict_authority": verdict.get("b26_p2_source_authority_state"),
            "verdict_currency": verdict.get("currency_code"),
            "ingress_amount": int(ingress.get("verified_amount_minor") or -1),
            "ingress_currency": ingress.get("verified_amount_currency"),
            "attribution_revenue": int(attribution.get("revenue_cents") or -1),
        }
        coherent = (
            operands["verdict_verified"] == contradictory
            and operands["verdict_attributed"] == contradictory
            and operands["verdict_net"] == contradictory
            and operands["verdict_captured"] == contradictory
            and operands["verdict_expected"] == contradictory
            and operands["verdict_discrepancy_amount"] == 0
            and operands["verdict_discrepancy_ratio"] == 0
            and operands["verdict_band"] == "exact"
            and operands["verdict_authority"] == "current"
            and str(operands["verdict_currency"]).upper() == currency.upper()
            and operands["ingress_amount"] == contradictory
            and str(operands["ingress_currency"]).upper() == currency.upper()
            and operands["attribution_revenue"] == contradictory
        )
        result["post_commit_read"] = {
            "rows": _a12_serialise_snapshot(observed),
            "guard_configuration": observed_states,
            "operands": operands,
            "coherent": coherent,
            "guard_configuration_restored": (
                observed_states == result.get("guard_configuration_original")
            ),
        }
        result["committed"] = bool(
            coherent
            and result["post_commit_read"]["guard_configuration_restored"]
        )
        if not result["committed"]:
            result["reason"] = "post_commit_read_failed"
    except Exception as exc:  # noqa: BLE001
        result["post_commit_error"] = f"{type(exc).__name__}:{exc}"
    finally:
        verify.close()
    return result


def _a12_restore(tenant_id: str, verdict_id: str, snapshot: dict) -> dict:
    import psycopg2  # noqa: PLC0415
    from psycopg2 import sql as psql  # noqa: PLC0415

    result: dict = {"restored_exact": False}
    conn = psycopg2.connect(role_dsn("migration_owner"))
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, true)",
                (tenant_id,),
            )
            current = _a12_snapshot_rows(cur, tenant_id, verdict_id)
            if current.get("reason"):
                raise RuntimeError(f"a12_restore_snapshot_refused:{current['reason']}")
            states = _a12_table_states(cur)
            verdict = snapshot["verdict"]
            ingress = snapshot["ingress"]
            attribution = snapshot["attribution"]
            for table, state in states.items():
                for trigger in state["triggers"]:
                    cur.execute(
                        psql.SQL("ALTER TABLE public.{} DISABLE TRIGGER {}").format(
                            psql.Identifier(table),
                            psql.Identifier(trigger["name"]),
                        )
                    )
            cur.execute(
                "UPDATE public.b23_match_verdicts"
                " SET verified_amount_minor = %s,"
                " attributed_amount_minor = %s,"
                " canonical_net_verified_amount_minor = %s,"
                " canonical_captured_gross_amount_minor = %s,"
                " canonical_expected_gross_amount_minor = %s,"
                " discrepancy_amount_minor = %s,"
                " discrepancy_ratio_bps = %s,"
                " discrepancy_band = %s,"
                " updated_at = %s"
                " WHERE tenant_id = %s AND id = %s",
                (
                    verdict["verified_amount_minor"],
                    verdict["attributed_amount_minor"],
                    verdict["canonical_net_verified_amount_minor"],
                    verdict["canonical_captured_gross_amount_minor"],
                    verdict["canonical_expected_gross_amount_minor"],
                    verdict["discrepancy_amount_minor"],
                    verdict["discrepancy_ratio_bps"],
                    verdict["discrepancy_band"],
                    verdict["updated_at"],
                    tenant_id,
                    verdict_id,
                ),
            )
            cur.execute(
                "UPDATE public.webhook_ingress_identities"
                " SET verified_amount_minor = %s, updated_at = %s"
                " WHERE tenant_id = %s AND id = %s",
                (
                    ingress["verified_amount_minor"],
                    ingress["updated_at"],
                    tenant_id,
                    ingress["id"],
                ),
            )
            cur.execute(
                "UPDATE public.attribution_events"
                " SET revenue_cents = %s, updated_at = %s"
                " WHERE tenant_id = %s AND id = %s",
                (
                    attribution["revenue_cents"],
                    attribution["updated_at"],
                    tenant_id,
                    attribution["id"],
                ),
            )
            for table, state in states.items():
                _a12_set_table_state(cur, table, state)
        conn.commit()
    except Exception as exc:  # noqa: BLE001
        conn.rollback()
        result["restore_error"] = f"{type(exc).__name__}:{exc}"
        return result
    finally:
        conn.close()

    verify = psycopg2.connect(role_dsn("migration_owner"))
    try:
        verify.autocommit = True
        with verify.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (tenant_id,),
            )
            restored = _a12_snapshot_rows(cur, tenant_id, verdict_id)
            restored_states = _a12_table_states(cur)
        result["restored"] = _a12_serialise_snapshot(restored)
        result["restored_guard_configuration"] = restored_states
        result["restored_exact"] = bool(
            not restored.get("reason")
            and _a12_rows_json(restored) == _a12_rows_json(snapshot)
            and restored_states == snapshot.get("__guard_states__")
        )
    except Exception as exc:  # noqa: BLE001
        result["restore_verification_error"] = f"{type(exc).__name__}:{exc}"
    finally:
        verify.close()
    return result


def _a12_evidence_snapshot(tenant_id: str, verdict_id: str) -> dict:
    import psycopg2  # noqa: PLC0415

    conn = psycopg2.connect(role_dsn("migration_owner"))
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (tenant_id,),
            )
            cur.execute(
                "SELECT v.webhook_ingress_identity_id::text"
                " FROM public.b23_match_verdicts AS v"
                " WHERE v.tenant_id = %s AND v.id = %s",
                (tenant_id, verdict_id),
            )
            row = cur.fetchone()
            if row is None or row[0] is None:
                return {"reason": "verdict_or_ingress_missing"}
            ingress_id = row[0]
            cur.execute(
                "SELECT a.statement::text, a.signature,"
                " a.attested_amount_minor, a.attested_amount_currency"
                " FROM public.b26_p2_source_money_attestation AS a"
                " WHERE a.tenant_id = %s"
                " AND a.webhook_ingress_identity_id = %s"
                " ORDER BY a.attested_at DESC LIMIT 1",
                (tenant_id, ingress_id),
            )
            attestation = cur.fetchone()
            cur.execute(
                "SELECT COALESCE(jsonb_agg(to_jsonb(x) ORDER BY x.id),"
                " '[]'::jsonb)::text FROM public.b26_p2_auth_root_evidence AS x"
                " WHERE x.tenant_id = %s"
                " AND x.webhook_ingress_identity_id = %s",
                (tenant_id, ingress_id),
            )
            root = cur.fetchone()
    finally:
        conn.close()
    payload = {
        "ingress_id": ingress_id,
        "attestation": (
            {
                "statement": attestation[0],
                "signature": attestation[1],
                "attested_amount_minor": attestation[2],
                "attested_amount_currency": attestation[3],
            }
            if attestation
            else None
        ),
        "auth_root_evidence": root[0] if root else None,
    }
    payload["sha256"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    return payload


def _a12_proof_observation(
    stage: str,
    *,
    tenant: dict,
    verdict_id: str,
    amount_minor: int,
    currency: str,
    temp: Path,
) -> dict:
    """Run the unchanged mandatory proof against this lane and exact subject."""
    from b26_p2_xxv_attestation_sweep import sweep  # noqa: PLC0415

    proof_dir = temp / f"a12-proof-{stage}"
    proof_dir.mkdir(parents=True, exist_ok=True)
    (proof_dir / "history_witness.jsonl").write_bytes(
        volume_get(WITNESS_VOL, "history_witness.jsonl")
    )
    (proof_dir / "history_witness_ed25519.pub").write_bytes(
        volume_get(WITNESS_VOL, "history_witness_ed25519.pub")
    )
    (proof_dir / "source_evidence.jsonl").write_bytes(
        volume_get(SOURCE_EVIDENCE_VOL, "source_evidence.jsonl")
    )
    public_key = str(LANE_ROOT / "source_attestation_ed25519.pub")
    dsn = _a12_proof_dsn(str(tenant["tenant_id"]))
    evidence_out = (
        _A12_RESULT_DIR
        / f"xxv-r0034-a12-required-proof-{stage}-20261102.json"
    )
    env = dict(os.environ)
    env["ENVIRONMENT"] = "ci"
    env["DATABASE_URL"] = role_dsn("app_user").replace(
        "postgresql://", "postgresql+asyncpg://", 1
    )
    env["MIGRATION_DATABASE_URL"] = role_dsn("migration_owner")
    env["B26_P2_HISTORY_WITNESS_JOURNAL_PATH"] = str(
        proof_dir / "history_witness.jsonl"
    )
    env["B26_P2_HISTORY_WITNESS_PUBLIC_KEY_PATH"] = str(
        proof_dir / "history_witness_ed25519.pub"
    )
    env["B26_P2_SOURCE_EVIDENCE_JOURNAL_PATH"] = str(
        proof_dir / "source_evidence.jsonl"
    )
    env["B26_P2_SOURCE_ATTESTATION_PUBLIC_KEY_PATH"] = public_key
    command = [
        sys.executable,
        str(REPO / "scripts/ci/validate_b26_p2_xxii_composition.py"),
        "--dsn",
        dsn,
        "--evidence-out",
        str(evidence_out),
    ]
    proc = subprocess.run(
        command,
        text=True,
        capture_output=True,
        cwd=str(REPO),
        env=env,
    )
    try:
        evidence = json.loads(evidence_out.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        evidence = None
    checks = (evidence or {}).get("checks") or {}
    violations = list((evidence or {}).get("violations") or [])
    support = sweep(dsn, public_key_path=public_key, check_source_evidence=False)
    try:
        import psycopg2  # noqa: PLC0415

        conn = psycopg2.connect(dsn)
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT count(*) FROM public.b23_match_verdicts"
                    " WHERE tenant_id = %s AND id = %s",
                    (str(tenant["tenant_id"]), verdict_id),
                )
                target_rows = int(cur.fetchone()[0] or 0)
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001
        target_rows = f"error:{type(exc).__name__}:{exc}"
    verdicts_examined = checks.get("live_xxv_verdicts_examined")
    target_visible = bool(
        isinstance(verdicts_examined, int)
        and verdicts_examined > 0
        and target_rows == 1
        and support.get("verdicts_examined") == verdicts_examined
    )
    attributable = [
        violation
        for violation in violations
        if verdict_id in violation
        and violation.startswith("xxv_source_money_unattested:")
    ]
    return {
        "stage": stage,
        "command": (
            "scripts/ci/validate_b26_p2_xxii_composition.py --dsn "
            "<migration_owner same lane, tenant RLS scope> --evidence-out "
            f"{evidence_out}"
        ),
        "dsn": dsn,
        "evidence_out": str(evidence_out),
        "returncode": proc.returncode,
        "printed_verdict": (
            "PASS" if "B26_P2_XXII_COMPOSITION_PASS" in proc.stdout else "FAIL"
        ),
        "evidence_status": (evidence or {}).get("status"),
        "violations": violations,
        "attributable_subject_violations": attributable,
        "checks": checks,
        "census": checks.get("live_xxv_attestation_census"),
        "verdicts_examined": verdicts_examined,
        "target_visible": target_visible,
        "target_rows": target_rows,
        "supporting_sweep": {
            "verdicts_examined": support.get("verdicts_examined"),
            "census": support.get("census"),
            "unverifiable_subject": [
                row
                for row in support.get("unverifiable", [])
                if row.get("verdict_id") == verdict_id
            ],
        },
        "source_hashes": _a12_proof_source_hashes(),
        "stdout_tail": proc.stdout[-5000:],
        "stderr_tail": proc.stderr[-2500:],
        "expected_amount_minor": amount_minor,
        "expected_currency": currency,
    }


def _a12_reconciliation_disposition(
    status: int,
    body: object,
    *,
    original_amount: int,
    contradictory_amount: int,
    currency: str,
) -> dict:
    body = body if isinstance(body, dict) else {}
    amount = body.get("canonical_net_verified_amount_minor")
    response_currency = body.get("currency_code")
    authority = body.get("source_authority_state")
    attestation = body.get("source_money_attestation_status")
    attestation_reason = body.get("source_money_attestation_reason")
    history = body.get("history_integrity_status")
    history_reason = body.get("history_integrity_reason")
    original_authoritative = bool(
        status == 200
        and amount == original_amount
        and str(response_currency or "").upper() == currency.upper()
        and authority == "current"
        and isinstance(attestation, str)
        and attestation
        and isinstance(history, str)
        and history == "verified"
    )
    governed_non_authoritative = bool(
        status == 200
        and authority == "source_attestation_unverifiable"
        and isinstance(attestation, str)
        and attestation.startswith("unverifiable:")
        and bool(attestation_reason)
    ) or bool(
        status == 200
        and authority == "historically_unverifiable"
        and history == "unverifiable"
        and bool(history_reason)
    )
    asserts_false_current = bool(status == 200 and amount == contradictory_amount)
    return {
        "status": status,
        "body": body,
        "amount_minor": amount,
        "currency": response_currency,
        "source_authority_state": authority,
        "source_money_attestation_status": attestation,
        "source_money_attestation_reason": attestation_reason,
        "history_integrity_status": history,
        "history_integrity_reason": history_reason,
        "original_authentic_current": original_authoritative,
        "governed_non_authoritative": governed_non_authoritative,
        "asserts_unsupported_amount_as_current": asserts_false_current,
        "definite_disposition": original_authoritative or governed_non_authoritative,
    }


def _a12_trust_disposition(
    observation: dict,
    *,
    tenant: dict,
    original_amount: int,
    contradictory_amount: int,
    currency: str,
) -> dict:
    status = int(observation.get("http") or 0)
    body = observation.get("body")
    body = body if isinstance(body, dict) else {}
    refusal = observation.get("refusal") or {}
    money = body.get("verified_revenue_minor")
    response_currency = body.get("currency")
    verification = [0, {}]
    if status == 200 and isinstance(body, dict):
        verification = verify_trust(tenant, body.get("envelope", body))
    verified = (
        isinstance(verification[1], dict)
        and verification[1].get("verification_status") == "verified"
    )
    financial_refusal = bool(
        400 <= status < 500
        and refusal.get("status") == "refused"
        and isinstance(refusal.get("reason"), str)
        and refusal.get("reason")
        and (
            refusal.get("financial") is True
            or str(refusal.get("reason", "")).startswith(
                ("money_", "source_", "attestation_", "history_integrity_")
            )
        )
    )
    original_authoritative = bool(
        status == 200
        and money == original_amount
        and str(response_currency or "").upper() == currency.upper()
        and verified
    )
    asserts_false_current = bool(
        status == 200 and money == contradictory_amount
    )
    return {
        "status": status,
        "body": body,
        "refusal": refusal,
        "verified_revenue_minor": money,
        "currency": response_currency,
        "verification": verification,
        "original_authentic_current": original_authoritative,
        "financial_refusal": financial_refusal,
        "asserts_unsupported_amount_as_current": asserts_false_current,
        "definite_disposition": original_authoritative or financial_refusal,
    }


def _a12_contradictory_financial_state(
    state: dict,
    tenant: dict,
    verdict_id: str,
    amount_minor: int,
    currency: str,
    temp: Path,
) -> dict:
    """Commit an independent in-scope contradiction, observe authority, restore.

    The contradiction is written directly to the three financial truth rows by
    their owner.  The signed Trust consumer and the reconciliation consumer must
    not serve it as current, and the unchanged mandatory proof must name this
    verdict.  The exact rows and guard modes are then restored, and the same
    consumers plus the unchanged proof must return the lawful baseline.
    """
    result: dict = {
        "original_amount_minor": int(amount_minor),
        "currency": currency,
        "established": False,
    }
    original_evidence = _a12_evidence_snapshot(
        str(tenant["tenant_id"]), verdict_id
    )
    result["original_evidence"] = original_evidence
    result["source_hashes_before"] = _a12_proof_source_hashes()

    baseline_window: dict = {}
    baseline_signed = _wait_signed(
        tenant, verdict_id, amount_minor, currency, window=baseline_window
    )
    baseline_recon_status, baseline_recon = read_reconciliation(
        state, tenant, verdict_id
    )
    result["baseline_signed"] = baseline_signed
    result["baseline_reconciliation"] = _a12_reconciliation_disposition(
        baseline_recon_status,
        baseline_recon,
        original_amount=amount_minor,
        contradictory_amount=amount_minor,
        currency=currency,
    )
    if (
        baseline_signed.get("status") != 200
        or (baseline_signed.get("verification") or [0])[0] != 200
        or not result["baseline_reconciliation"]["original_authentic_current"]
    ):
        result["reason"] = "baseline_not_lawful"
        return result

    baseline_proof = _a12_proof_observation(
        "baseline",
        tenant=tenant,
        verdict_id=verdict_id,
        amount_minor=amount_minor,
        currency=currency,
        temp=temp,
    )
    result["baseline_proof"] = baseline_proof
    if (
        baseline_proof["printed_verdict"] != "PASS"
        or not baseline_proof["target_visible"]
    ):
        result["reason"] = (
            "baseline_proof_not_green"
            if baseline_proof["printed_verdict"] != "PASS"
            else "baseline_proof_census_blind"
        )
        return result

    await_witness_catchup(state)
    mutation = _a12_mutate(
        str(tenant["tenant_id"]),
        verdict_id,
        baseline_amount=int(amount_minor),
        currency=currency,
    )
    result["mutation"] = mutation
    if mutation.get("committed") is not True:
        result["reason"] = mutation.get("mutation_error") or mutation.get(
            "reason", "mutation_not_committed"
        )
        original = mutation.get("original") or {}
        if original.get("verdict"):
            mutation["compensation"] = _a12_restore(
                str(tenant["tenant_id"]), verdict_id, original
            )
        return result

    original = mutation["original"]
    contradictory = int(mutation["contradictory_amount_minor"])
    try:
        false_trust_read = _read_trust_attributed(tenant, verdict_id)
        false_recon_status, false_recon = read_reconciliation(
            state, tenant, verdict_id
        )
        result["contradictory_consumers"] = {
            "trust": _a12_trust_disposition(
                false_trust_read,
                tenant=tenant,
                original_amount=amount_minor,
                contradictory_amount=contradictory,
                currency=currency,
            ),
            "reconciliation": _a12_reconciliation_disposition(
                false_recon_status,
                false_recon,
                original_amount=amount_minor,
                contradictory_amount=contradictory,
                currency=currency,
            ),
        }
        false_proof = _a12_proof_observation(
            "false-world",
            tenant=tenant,
            verdict_id=verdict_id,
            amount_minor=contradictory,
            currency=currency,
            temp=temp,
        )
        result["false_world_proof"] = false_proof
    except Exception as exc:  # noqa: BLE001 - restore before reporting the error
        result["false_world_error"] = f"{type(exc).__name__}:{exc}"
    finally:
        result["restoration"] = _a12_restore(
            str(tenant["tenant_id"]), verdict_id, original
        )

    restoration = result.get("restoration") or {}
    if restoration.get("restored_exact") is not True:
        result["reason"] = (
            restoration.get("restore_error")
            or restoration.get("restore_verification_error")
            or "restoration_not_exact"
        )
        return result

    try:
        await_witness_catchup(state)
    except Exception as exc:  # noqa: BLE001
        result["witness_catchup_error"] = f"{type(exc).__name__}:{exc}"
    restored_window: dict = {}
    restored_signed = _wait_signed(
        tenant, verdict_id, amount_minor, currency, window=restored_window
    )
    restored_recon_status, restored_recon = read_reconciliation(
        state, tenant, verdict_id
    )
    result["restored_reconciliation"] = _a12_reconciliation_disposition(
        restored_recon_status,
        restored_recon,
        original_amount=amount_minor,
        contradictory_amount=contradictory,
        currency=currency,
    )
    result["restored_signed"] = restored_signed
    restored_proof = _a12_proof_observation(
        "restored",
        tenant=tenant,
        verdict_id=verdict_id,
        amount_minor=amount_minor,
        currency=currency,
        temp=temp,
    )
    result["restored_proof"] = restored_proof
    restored_evidence = _a12_evidence_snapshot(
        str(tenant["tenant_id"]), verdict_id
    )
    result["restored_evidence"] = restored_evidence
    result["source_hashes_after"] = _a12_proof_source_hashes()

    trust = (result.get("contradictory_consumers") or {}).get("trust") or {}
    recon = (result.get("contradictory_consumers") or {}).get("reconciliation") or {}
    false_proof = result.get("false_world_proof") or {}
    result["detection"] = {
        "trust_definite_disposition": trust.get("definite_disposition") is True,
        "trust_did_not_assert_false_current": (
            trust.get("asserts_unsupported_amount_as_current") is not True
        ),
        "reconciliation_definite_disposition": (
            recon.get("definite_disposition") is True
        ),
        "reconciliation_did_not_assert_false_current": (
            recon.get("asserts_unsupported_amount_as_current") is not True
        ),
        "proof_red": false_proof.get("printed_verdict") == "FAIL",
        "proof_red_attributable_to_subject": bool(
            false_proof.get("attributable_subject_violations")
        ),
        "proof_census_visible": false_proof.get("target_visible") is True,
    }
    result["established"] = bool(
        mutation.get("committed") is True
        and all(result["detection"].values())
        and restoration.get("restored_exact") is True
        and restored_signed.get("status") == 200
        and (restored_signed.get("verification") or [0])[0] == 200
        and result["restored_reconciliation"]["original_authentic_current"]
        and restored_proof.get("printed_verdict") == "PASS"
        and restored_proof.get("target_visible") is True
        and restored_evidence.get("sha256") == original_evidence.get("sha256")
        and _a12_attestation_verifies(original_evidence)
        and _a12_attestation_verifies(restored_evidence)
        and result["source_hashes_after"] == result["source_hashes_before"]
    )
    if not result["established"]:
        result["reason"] = "a12_required_conditions_not_met"
    return result


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
    a12 = _a12_contradictory_financial_state(
        state,
        tenant,
        initial["verdict_id"],
        baseline["amount_minor"],
        baseline["currency"],
        temp,
    )
    staged = _stage(state, temp)
    kept = False
    mutated = False
    record: dict = {
        "mode": "positive",
        "baseline": baseline,
        "initial_subject": initial.get("commerce_reference"),
        "baseline_signed": baseline_signed,
        "a12_contradictory_state": a12,
        "manual_observer": False,
        "require_signature_verification": True,
        "trust_jwks": _artifact_trust_jwks(state),
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
        restoration_observation: dict = {}
        restored_baseline = _wait_signed(
            tenant,
            initial["verdict_id"],
            baseline["amount_minor"],
            baseline["currency"],
            window=restoration_observation,
        )
        record["restoration_observation"] = restoration_observation
        record["restoration_observed_at"] = restoration_observation.get(
            "observed_at"
        )
        record["restored_baseline"] = restored_baseline
        record["restoration_semantic_authority"] = (
            _restoration_semantic_authority(
                baseline_signed,
                restored_baseline,
                restored_observation=restoration_observation,
            )
        )
        restored_records = _records(restored_path.read_bytes(), temp)
        event_ref = f"evt_xxvrec{_uuid_hex()}"
        record["amendment_admission_started_at"] = _now_iso()
        second_status, _, _ = post_stripe_envelope(
            state,
            tenant,
            event_reference=event_ref,
            commerce_reference=intent,
            amount=amended_amount,
        )
        record["amendment_admitted_at"] = _now_iso()
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
        final_observation_window = {"started_at": _now_iso()}
        trust_status, trust = 404, ""
        for _ in range(60):
            trust_status, trust = read_trust(tenant, initial["verdict_id"])
            if trust_status == 200:
                break
            time.sleep(5)
        final_observation_window["observed_at"] = _now_iso()
        record["final_observation"] = final_observation_window
        record["final_observed_at"] = final_observation_window["observed_at"]
        verified_trust = (
            verify_trust(tenant, trust.get("envelope", trust))
            if trust_status == 200 and isinstance(trust, dict)
            else (0, "not_attempted")
        )
        final_signed_observation = {
            "status": trust_status,
            "artifact": trust if isinstance(trust, dict) else None,
            "verification": verified_trust,
            "expected_tenant_id_hash": baseline["tenant_id_hash"],
        }
        final_established, final_reason = (
            _signed_observation(
                final_signed_observation,
                initial["verdict_id"],
                amended_amount,
                baseline["currency"],
                str(baseline["tenant_id_hash"]),
            )
            if isinstance(trust, dict)
            else (False, "final_signed_artifact_unavailable")
        )
        final_signed_observation["established"] = final_established
        final_signed_observation["invalid_reason"] = final_reason or None
        record["final_signed"] = final_signed_observation
        causal_history = _read_causal_history(
            tenant["tenant_id"], initial["verdict_id"], event_ref
        )
        causal_history["final_observation"] = final_observation_window
        causal_history["authority_universe"] = state.get(
            "authority_universe"
        )
        causal_history["source_attestation_public_key_sha256"] = (
            state.get("artifact") or {}
        ).get("compiled_source_attestation_public_key_sha256")
        causal_history["witness_public_key_sha256"] = (
            state.get("artifact") or {}
        ).get("compiled_public_key_sha256")
        causal_history["require_signature_verification"] = True
        record["artifact"] = state.get("artifact")
        record["witness_public_key"] = staged["public"].read_text(
            encoding="utf-8"
        ).strip()
        causal_history["witness_commitment"] = (
            _verify_witness_commitment(
                state=state,
                temp=temp,
                public_key_path=staged["public"],
                history=causal_history,
            )
        )
        record["causal_history"] = causal_history
        record["causal_progression"] = _final_causal_progression(
            final_signed_observation,
            causal_history,
            restored_signed=restored_baseline,
            restoration_observed_at=record.get("restoration_observed_at"),
            amendment_admission_started_at=record.get(
                "amendment_admission_started_at"
            ),
            amendment_admitted_at=record.get("amendment_admitted_at"),
            final_observed_at=record.get("final_observed_at"),
            baseline_amount=baseline["amount_minor"],
            amended_amount=amended_amount,
            currency=baseline["currency"],
            verdict_id=initial["verdict_id"],
        )
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
    baseline = record.get("baseline") or {}
    if record.get("require_signature_verification") is True:
        trust_jwks = record.get("trust_jwks")
        artifact_identity = record.get("artifact") or {}
        registry_digest = artifact_identity.get(
            "compiled_trust_registry_sha256"
        )
        if (
            not isinstance(trust_jwks, dict)
            or not registry_digest
            or _trust_registry_digest(trust_jwks) != registry_digest
        ):
            return False
        common = (
            str(baseline.get("verdict_id") or ""),
            int(baseline.get("amount_minor") or 0),
            str(baseline.get("currency") or ""),
            str(baseline.get("tenant_id_hash") or ""),
        )
        if (
            _verify_observation_with_jwks(
                record.get("baseline_signed") or {}, trust_jwks, *common
            ).get("verification_status")
            != "verified"
        ):
            return False
        restored = record.get("restored_baseline") or {}
        if restored and (
            _verify_observation_with_jwks(
                restored, trust_jwks, *common
            ).get("verification_status")
            != "verified"
        ):
            return False
    if not (
        (record.get("baseline_signed") or {}).get("established") is True
        and (record.get("baseline_signed") or {})
        .get("offline_verification", {})
        .get("verification_status")
        == "verified"
        and baseline_verify[0] == 200
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
        and restored.get("established") is True
        and _restoration_semantic_authority(
            record.get("baseline_signed") or {},
            restored,
            restored_observation=record.get("restoration_observation"),
        ).get("established")
        is True
        and (restored.get("offline_verification") or {}).get(
            "verification_status"
        )
        == "verified"
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
        "require_signature_verification": True,
        "trust_jwks": _artifact_trust_jwks(state),
        "artifact": state.get("artifact"),
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
        restoration_observation: dict = {}
        record["restored_baseline"] = _wait_signed(
            tenant,
            initial["verdict_id"],
            baseline["amount_minor"],
            baseline["currency"],
            window=restoration_observation,
        )
        record["restoration_observation"] = restoration_observation
        record["restoration_semantic_authority"] = (
            _restoration_semantic_authority(
                baseline_signed,
                record["restored_baseline"],
                restored_observation=restoration_observation,
            )
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
            "recovery acceptance: accepted history restoration bound to the"
            " baseline financial lineage, same-subject progression, natural"
            " witnessing, verified signed money/currency"
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
