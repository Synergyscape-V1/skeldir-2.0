"""Self-falsification of the recovery decision, independent of a live lane."""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import sys
from pathlib import Path

import yaml
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ci"))

from b26_p2_xxv_recovery_probe import (  # noqa: E402
    _OBSERVATION_TIME_PATHS,
    _acceptance,
    _expected_match_entry,
    _expected_provider_entry,
    _expected_webhook_entry,
    _final_causal_progression,
    _global_prefix_digest,
    _is_issuance_audit_entry,
    _key_lifecycle_valid,
    _ledger_entry_hash,
    _negative_decision,
    _offline_verification,
    _restoration_semantic_authority,
    _signed_structure,
    _subject_ref_hash,
    tenant_hash,
)
from app.revenue_verification.source_attestation import (  # noqa: E402
    ATTESTATION_STATEMENT_VERSION,
    canonical_statement_bytes,
)
from app.trust.money_source_adapter import (  # noqa: E402
    resolve_authoritative_money,
)
from app.trust.provenance import (  # noqa: E402
    _internal_decision_entry,
    _registration,
)
from app.trust.source_adapters import (  # noqa: E402
    data_completeness_for_match_status,
    normalize_match_verdict_status,
)
from write_b26_p2_recovery_cell import mode_projection  # noqa: E402


def _baseline() -> dict:
    return {
        "http": 200,
        "verdict_id": "v1",
        "subject": "pi_same",
        "amount_minor": 4321,
        "currency": "USD",
        "reconciliation_status": 200,
        "reconciliation_net_minor": 4321,
        "tenant_id_hash": tenant_hash("tenant"),
    }


def _source_decision_entries(amount: int, observed_at: str) -> list[dict]:
    money = resolve_authoritative_money(
        source_domain="b23_match_verdicts",
        source_field_path="canonical_net_verified_amount_minor",
        raw_value=amount,
        currency="USD",
        intended_trust_field="verified_revenue_minor",
    )
    return [
        _internal_decision_entry(
            _registration("money_authority_source"),
            observed_at=observed_at,
            decision_material=money.external_projection(),
        ),
        _internal_decision_entry(
            _registration("policy_authority_source"),
            observed_at=observed_at,
            decision_material={"policy_state": "read_only"},
        ),
        _internal_decision_entry(
            _registration("reason_code_decision"),
            observed_at=observed_at,
            decision_material={"reason_code": "none"},
        ),
    ]


def _aux_provenance(observed_at: str) -> list[dict]:
    entries = []
    for source_class in (
        "deterministic_attribution_output_refs",
        "b24_source_snapshot_hash",
        "b24_fit_id",
        "b24_diagnostic_fallback_status",
        "b24_artifact_ref_hash",
    ):
        entries.append(
            {
                "authority_table": "trust_provenance_source_registry",
                "provenance_type": "explicit_unavailable",
                "source_ref": f"urn:skeldir:unavailable:{source_class}",
                "source_ref_hash": "sha256:unavailable",
                "source_snapshot_hash": "sha256:unavailable",
                "observed_at": observed_at,
                "display_metadata": {
                    "text_trust_class": "none",
                    "raw_text_sha256": None,
                    "display_transform": "none",
                },
            }
        )
    entries.append(
        {
            "authority_table": "trust_text_disposition",
            "provenance_type": "text_disposition",
            "source_ref": (
                "urn:skeldir:text_disposition_transform_version:6e8f0dae"
                "14e57a0f06f485f0dad4b4807f7175dbe4daa8fedc382c81331aecab"
            ),
            "source_ref_hash": "sha256:text-disposition",
            "source_snapshot_hash": "sha256:text-disposition",
            "observed_at": observed_at,
            "display_metadata": {
                "text_trust_class": "none",
                "raw_text_sha256": None,
                "display_transform": "none",
            },
        }
    )
    return entries


def _artifact(amount: int) -> dict:
    urn = "urn:skeldir:match_verdict:v1"
    digest = _subject_ref_hash(urn)
    return {
        "subject_type": "match_verdict",
        "subject_ref": urn,
        "subject_ref_hash": digest,
        "subject_authority": {
            "subject_type": "match_verdict",
            "subject_ref": urn,
            "subject_ref_hash": digest,
            "source_authority_class": "deterministic_machine_fact",
            "allowed_source_tables": [
                "b23_match_verdicts",
                "b23_revenue_events",
            ],
            "mutable_workflow_subject": False,
        },
        "tenant_id_hash": tenant_hash("tenant"),
        "match_verdict_status": "ambiguous",
        "truth_type": "deterministic_match_verdict",
        "truth_authority": {
            "authority_class": "deterministic_machine_fact",
            "source_system": "skeldir_b23_match_engine",
            "source_snapshot_hash": "sha256:snapshot",
        },
        "verified_revenue_minor": amount,
        "currency": "USD",
        "fallback_applied": False,
        "data_completeness_status": "insufficient_evidence",
        "benchmark_metadata": {
            "benchmark_authority": "explicitly_unavailable",
            "benchmark_hash": None,
            "benchmark_ref": None,
            "benchmark_status": "unavailable",
            "unavailable_reason": "benchmark_source_not_configured",
        },
        "confidence_metadata": {
            "bayesian_model_type": "deterministic_only",
            "bayesian_model_version": None,
            "confidence_authority": "deterministic_only",
            "confidence_score_basis_points": None,
            "confidence_status": "unavailable",
            "diagnostics_status": "not_applicable",
            "inference_provenance": None,
            "unavailable_reason": "not_applicable",
        },
        "policy_action_authority": {
            "allowed_scopes": [
                "trust.envelope.read",
                "trust.envelope.verify",
            ],
            "forbidden_scopes": [
                "trust.action.execute",
                "trust.policy.override",
                "trust.envelope.mutate",
            ],
            "policy_state": "read_only",
            "reason_code": "p1_contract_boundary_only",
        },
        "audience_binding": {
            "audience_mode": "tenant_internal",
            "audience_id_hash": "sha256:audience",
            "audience_scope": [
                "trust.envelope.read",
                "trust.envelope.verify",
            ],
            "presentation_policy": "bearer_not_authority",
            "replay_context_required": True,
        },
        "evidence_temporal_boundary": {
            "staleness_status": "current",
            "snapshot_consistency_status": "consistent",
            "evidence_age_status": "within_supported_horizon",
            "max_source_read_skew_ms": 0,
            "evidence_snapshot_at": "2026-11-03T06:00:00Z",
            "evidence_snapshot_hash": "sha256:snapshot",
            "source_read_started_at": "2026-11-03T06:00:00Z",
            "source_read_completed_at": "2026-11-03T06:00:00Z",
            "data_freshness_seconds": 0,
            "data_freshness_bound": "exact",
        },
        "provenance_chain": [
            {
                "authority_table": "b23_match_verdicts",
                "provenance_type": "match_verdict",
                "source_ref": "urn:skeldir:b23_match_verdicts:v1",
                "source_ref_hash": "sha256:match-ref",
                "source_snapshot_hash": "sha256:snapshot",
                "observed_at": "2026-11-03T06:00:00Z",
                "display_metadata": {
                    "text_trust_class": "none",
                    "raw_text_sha256": None,
                    "display_transform": "none",
                },
            },
            *_source_decision_entries(amount, "2026-11-03T06:00:00Z"),
            *_aux_provenance("2026-11-03T06:00:00Z"),
        ],
        "signing_key_id": "kid",
        "created_at": "2026-11-03T06:00:00Z",
    }


def _verified(amount: int = 4321) -> dict:
    return {
        "status": 200,
        "artifact": _artifact(amount),
        "verification": [
            200,
            {
                "verification_status": "verified",
                "signature_hash": "sig",
                "signing_key_id": "kid",
                "temporal_scope": "truth-at-issuance",
            },
        ],
        "established": True,
        "offline_verification": {"verification_status": "verified"},
    }


def _signed_witness_commitment(
    global_ledger: list[dict],
    authority_universe: str | None = "universe",
) -> dict:
    private_key = Ed25519PrivateKey.generate()
    public_key = base64.urlsafe_b64encode(
        private_key.public_key().public_bytes_raw()
    ).rstrip(b"=").decode("ascii")
    prefix_digest = _global_prefix_digest(global_ledger)
    payload = {
        "version": 1,
        "key_id": "kid:test-witness",
        "observed_at": "2026-11-03T06:00:06Z",
        "ledger_count": len(global_ledger),
        "ledger_tip_seq": global_ledger[-1]["seq"],
        "ledger_tip_hash": global_ledger[-1]["entry_hash"],
        "ledger_prefix_digest": prefix_digest,
        "previous_checkpoint_hash": None,
        "authority_universe": authority_universe,
    }
    material = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    payload["checkpoint_hash"] = hashlib.sha256(material).hexdigest()
    signed_material = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    signature = private_key.sign(signed_material)
    return {
        "verified": True,
        "reason": None,
        "count": len(global_ledger),
        "tip_seq": global_ledger[-1]["seq"],
        "tip_hash": global_ledger[-1]["entry_hash"],
        "prefix_digest": prefix_digest,
        "public_key": public_key,
        "latest_checkpoint": {
            "payload": payload,
            "signature": "ed25519:"
            + base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii"),
        },
    }


_SOURCE_ATTESTATION_PRIVATE = Ed25519PrivateKey.generate()
_SOURCE_ATTESTATION_PUBLIC = base64.urlsafe_b64encode(
    _SOURCE_ATTESTATION_PRIVATE.public_key().public_bytes_raw()
).rstrip(b"=").decode("ascii")


def _sign_source_statement(statement: dict) -> dict:
    signature = _SOURCE_ATTESTATION_PRIVATE.sign(
        canonical_statement_bytes(statement)
    )
    return {
        "statement": statement,
        "signature": "ed25519:"
        + base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii"),
        "key_sha256": hashlib.sha256(
            _SOURCE_ATTESTATION_PRIVATE.public_key().public_bytes_raw()
        ).hexdigest(),
    }


def _source_attestation(source: dict) -> dict:
    statement = {
        "version": ATTESTATION_STATEMENT_VERSION,
        "tenant_id": source["tenant_id"],
        "webhook_ingress_identity_id": source["id"],
        "provider": source["provider"],
        "provider_native_event_reference": source[
            "provider_native_event_reference"
        ],
        "provider_native_commerce_reference": source[
            "provider_native_commerce_reference"
        ],
        "normalized_commerce_reference_kind": source.get(
            "normalized_commerce_reference_kind"
        ),
        "normalized_commerce_reference_value": source.get(
            "normalized_commerce_reference_value"
        ),
        "verified_amount_minor": source["verified_amount_minor"],
        "verified_amount_currency": source["verified_amount_currency"],
        "verified_amount_scale": source["verified_amount_scale"],
        "event_timestamp": source["event_timestamp"],
        "body_sha256": "0" * 64,
        "authority_universe": "universe",
    }
    return _sign_source_statement(statement)


def _causal_history(status: str = "matched_provisional") -> dict:
    current = {
        "id": "ingress-new",
        "tenant_id": "tenant",
        "provider": "stripe",
        "provider_native_event_reference": "evt_new",
        "provider_native_commerce_reference": "pi_same",
        "normalized_commerce_reference_kind": "commerce_reference",
        "normalized_commerce_reference_value": "pi_same",
        "event_timestamp": "2026-11-03T06:00:04Z",
        "created_at": "2026-11-03T06:00:04Z",
        "verified_amount_minor": 5100,
        "verified_amount_currency": "USD",
        "verified_amount_scale": 2,
        "demotion_reason": None,
    }
    prior = {
        "id": "ingress-old",
        "tenant_id": "tenant",
        "provider": "stripe",
        "provider_native_event_reference": "evt_old",
        "provider_native_commerce_reference": "pi_same",
        "normalized_commerce_reference_kind": "commerce_reference",
        "normalized_commerce_reference_value": "pi_same",
        "event_timestamp": "2026-11-03T05:59:00Z",
        "created_at": "2026-11-03T05:59:00Z",
        "verified_amount_minor": 4321,
        "verified_amount_currency": "USD",
        "verified_amount_scale": 2,
        "demotion_reason": "superseded_by_provider_amendment:evt_new",
    }
    current["source_attestation"] = _source_attestation(current)
    prior["source_attestation"] = _source_attestation(prior)
    ledger_rows = [
        {
            "seq": 9,
            "verdict_id": "v1",
            "tenant_id": "tenant",
            "provider": "stripe",
            "provider_native_event_reference": "evt_old",
            "prior_attributed_amount_minor": 4321,
            "new_attributed_amount_minor": 4321,
            "prior_verified_amount_minor": 4321,
            "new_verified_amount_minor": 4321,
            "prior_authority_state": "current",
            "new_authority_state": "historically_unverifiable",
            "prior_source_ingress": "ingress-old",
            "new_source_ingress": "ingress-old",
            "recorded_at": "2026-11-03T06:00:04Z",
            "prev_entry_hash": None,
            "entry_hash": None,
        },
        {
            "seq": 10,
            "verdict_id": "v1",
            "tenant_id": "tenant",
            "provider": "stripe",
            "provider_native_event_reference": "evt_new",
            "prior_attributed_amount_minor": 4321,
            "new_attributed_amount_minor": 5100,
            "prior_verified_amount_minor": 4321,
            "new_verified_amount_minor": 5100,
            "prior_authority_state": "historically_unverifiable",
            "new_authority_state": "current",
            "prior_source_ingress": "ingress-old",
            "new_source_ingress": "ingress-new",
            "recorded_at": "2026-11-03T06:00:05Z",
            "prev_entry_hash": None,
            "entry_hash": None,
        },
    ]
    global_ledger = []
    previous_hash = None
    for seq in range(1, 9):
        entry_hash = hashlib.sha256(f"filler-{seq}".encode()).hexdigest()
        global_ledger.append(
            {
                "seq": seq,
                "entry_hash": entry_hash,
                "prev_entry_hash": previous_hash,
                "recorded_at": "2026-11-03T06:00:01Z",
            }
        )
        previous_hash = entry_hash
    for ledger_row in ledger_rows:
        ledger_row["prev_entry_hash"] = previous_hash
        ledger_row["entry_hash"] = _ledger_entry_hash(ledger_row)
        global_ledger.append(
            {
                "seq": ledger_row["seq"],
                "entry_hash": ledger_row["entry_hash"],
                "prev_entry_hash": ledger_row["prev_entry_hash"],
                "recorded_at": ledger_row["recorded_at"],
            }
        )
        previous_hash = ledger_row["entry_hash"]
    commitment = _signed_witness_commitment(global_ledger)
    return {
        "complete": True,
        "reason": None,
        "amendment_event_reference": "evt_new",
        "verdict": {
            "id": "v1",
            "tenant_id": "tenant",
            "webhook_ingress_identity_id": "ingress-new",
            "provider": "stripe",
            "provider_native_event_reference": "evt_new",
            "provider_native_commerce_reference": "pi_same",
            "canonical_commerce_reference": "pi_same",
            "status": status,
            "canonical_net_verified_amount_minor": 5100,
            "currency_code": "USD",
            "last_transition_at": "2026-11-03T06:00:05Z",
            "created_at": "2026-11-03T06:00:00Z",
            "updated_at": "2026-11-03T06:00:05Z",
        },
        "current_ingress": current,
        "prior_ingress": prior,
        "source_ingresses": {
            "ingress-new": current,
            "ingress-old": prior,
        },
        "ledger": ledger_rows,
        "global_ledger": global_ledger,
        "witness": {
            "count": commitment["count"],
            "tip_seq": commitment["tip_seq"],
            "tip_hash": commitment["tip_hash"],
        },
        "continuity": {
            "count": commitment["count"],
            "tip_hash": commitment["tip_hash"],
        },
        "prefix_digest": commitment["prefix_digest"],
        "witness_commitment": commitment,
        "source_attestation_public_key": _SOURCE_ATTESTATION_PUBLIC,
        "authority_universe": "universe",
    }


def _final_verified(
    status: str = "matched_provisional", history: dict | None = None
) -> dict:
    history = history or _causal_history(status)
    artifact = _artifact(5100)
    expected_provider = _expected_provider_entry(
        provider=history["current_ingress"]["provider"],
        event_reference=history["current_ingress"][
            "provider_native_event_reference"
        ],
        commerce_reference=history["current_ingress"][
            "provider_native_commerce_reference"
        ],
        observed_at=history["verdict"]["created_at"],
    )
    expected_match = _expected_match_entry(history["verdict"])
    expected_webhook = _expected_webhook_entry(
        history["verdict"], history["current_ingress"]
    )
    artifact["match_verdict_status"] = normalize_match_verdict_status(status)
    artifact["data_completeness_status"] = data_completeness_for_match_status(
        status
    )
    artifact["truth_authority"]["source_snapshot_hash"] = expected_match[
        "source_snapshot_hash"
    ]
    artifact["evidence_temporal_boundary"][
        "evidence_snapshot_hash"
    ] = expected_match["source_snapshot_hash"]
    artifact["evidence_temporal_boundary"][
        "evidence_snapshot_at"
    ] = history["verdict"]["updated_at"]
    artifact["provenance_chain"] = [
        expected_webhook,
        expected_provider,
        expected_match,
        *_source_decision_entries(
            5100, history["verdict"]["updated_at"]
        ),
        *_aux_provenance(history["verdict"]["updated_at"]),
    ]
    artifact["created_at"] = "2026-11-03T06:00:06Z"
    artifact["evidence_temporal_boundary"][
        "source_read_started_at"
    ] = "2026-11-03T06:00:06Z"
    artifact["evidence_temporal_boundary"][
        "source_read_completed_at"
    ] = "2026-11-03T06:00:06Z"
    return {
        "status": 200,
        "artifact": artifact,
        "verification": [
            200,
            {
                "verification_status": "verified",
                "signature_hash": "sig",
                "signing_key_id": "kid",
                "temporal_scope": "truth-at-issuance",
            },
        ],
        "established": True,
        "offline_verification": {"verification_status": "verified"},
    }


def _positive(
    status: str = "matched_provisional", history: dict | None = None
) -> dict:
    history = history or _causal_history(status)
    return {
        "baseline": _baseline(),
        "initial_subject": "pi_same",
        "baseline_signed": _verified(),
        "fault": {
            "specific": True,
            "new_row": True,
            "money_minor": None,
            "status": "refused",
            "reason": "history_integrity_unverifiable",
        },
        "restored_baseline": _verified(),
        "final_signed": _final_verified(status, history),
        "causal_history": history,
        "witness_public_key": history["witness_commitment"]["public_key"],
        "restoration_observation": {
            "started_at": "2026-11-03T06:00:00Z",
            "completed_at": "2026-11-03T06:00:01Z",
        },
        "restoration_observed_at": "2026-11-03T06:00:01Z",
        "amendment_admission_started_at": "2026-11-03T06:00:02Z",
        "amendment_admitted_at": "2026-11-03T06:00:05Z",
        "final_observation": {
            "started_at": "2026-11-03T06:00:05Z",
            "observed_at": "2026-11-03T06:00:07Z",
        },
        "final_observed_at": "2026-11-03T06:00:07Z",
        "custody": {
            "accepted_count": 3,
            "accepted_tip": "tip",
            "restored_count": 3,
            "restored_prefix_tip": "tip",
            "signature_verified": True,
        },
        "amendment": {
            "http": 200,
            "subject": "pi_same",
            "verdict_id": "v1",
            "same_verdict": True,
            "amount_minor": 5100,
            "correction_http": {"status": 200},
            "witness_advanced": True,
        },
        "readers": {
            "reconciliation": {"status": 200, "net_minor": 5100},
            "trust": {
                "status": 200,
                "verified_revenue_minor": 5100,
                "currency": "USD",
            },
            "trust_verify": [
                200,
                {
                    "verification_status": "verified",
                    "signature_hash": "sig",
                    "signing_key_id": "kid",
                },
            ],
        },
    }


def test_valid_recovery_progression_is_accepted() -> None:
    assert _acceptance(_positive()) is True


def test_published_mode_projection_is_replayable() -> None:
    record = _positive()
    record["passed"] = True
    assert _acceptance(mode_projection(record)) is True


def test_retained_exact_head_cell_replays() -> None:
    path = (
        REPO_ROOT
        / "docs"
        / "forensics"
        / "evidence"
        / "b26_p2_xxv_a8"
        / "xxv-r0038-recovery-context-20261104.json"
    )
    document = json.loads(path.read_text(encoding="utf-8"))
    assert _acceptance(document["details"]["modes"]["positive"]) is True


def test_contract_confirmed_match_is_consumable() -> None:
    record = _positive("matched_confirmed")
    assert _acceptance(record) is True


def test_contract_confirmed_baseline_and_restore_are_consumable() -> None:
    record = _positive()
    for observation in (record["baseline_signed"], record["restored_baseline"]):
        observation["artifact"]["match_verdict_status"] = "matched"
        observation["artifact"]["data_completeness_status"] = "complete"
    assert _acceptance(record) is True


def test_internal_lifecycle_spelling_is_not_a_public_qualification() -> None:
    record = _positive()
    record["final_signed"]["artifact"]["match_verdict_status"] = "matched_confirmed"
    assert _acceptance(record) is False


def test_restored_artifact_with_other_journey_lineage_fails_acceptance() -> None:
    record = _positive()
    record["restored_baseline"]["artifact"]["provenance_chain"].append(
        {
            "authority_table": "b23_match_verdicts",
            "provenance_type": "provider_native_reference",
            "source_ref": "urn:skeldir:provider_native_reference:other",
            "source_ref_hash": "sha256:other",
            "source_snapshot_hash": "sha256:snapshot",
            "observed_at": "2026-11-03T06:00:00Z",
            "display_metadata": {
                "text_trust_class": "none",
                "raw_text_sha256": None,
                "display_transform": "none",
            },
        }
    )
    assert _acceptance(record) is False


def test_restored_post_amendment_lineage_with_baseline_money_fails() -> None:
    record = _positive()
    artifact = record["restored_baseline"]["artifact"]
    artifact["truth_authority"]["source_snapshot_hash"] = "sha256:amended"
    artifact["evidence_temporal_boundary"]["evidence_snapshot_hash"] = "sha256:amended"
    for entry in artifact["provenance_chain"]:
        if entry["provenance_type"] == "match_verdict":
            entry["source_snapshot_hash"] = "sha256:amended"
    assert _acceptance(record) is False


def test_restored_artifact_with_changed_completeness_fails_acceptance() -> None:
    record = _positive()
    record["restored_baseline"]["artifact"]["data_completeness_status"] = "complete"
    assert _acceptance(record) is False


def test_restored_artifact_with_changed_qualification_fails_acceptance() -> None:
    record = _positive()
    record["restored_baseline"]["artifact"]["match_verdict_status"] = "matched"
    assert _acceptance(record) is False


def test_genuine_restoration_may_change_observation_time() -> None:
    record = _positive()
    artifact = record["restored_baseline"]["artifact"]
    artifact["created_at"] = "2026-11-03T06:00:02Z"
    artifact["evidence_temporal_boundary"][
        "source_read_started_at"
    ] = "2026-11-03T06:00:02Z"
    artifact["evidence_temporal_boundary"][
        "source_read_completed_at"
    ] = "2026-11-03T06:00:02Z"
    record["restoration_observation"] = {
        "started_at": "2026-11-03T06:00:01.500Z",
        "completed_at": "2026-11-03T06:00:02.500Z",
    }
    record["restoration_observed_at"] = "2026-11-03T06:00:02Z"
    record["amendment_admission_started_at"] = "2026-11-03T06:00:03Z"
    result = _restoration_semantic_authority(
        record["baseline_signed"],
        record["restored_baseline"],
        restored_observation=record["restoration_observation"],
    )
    assert result["established"] is True
    assert result["observation_time_justified"] is True
    assert result["baseline_meaning_digest"] == result["restored_meaning_digest"]
    assert _acceptance(record) is True


def test_genuine_restoration_may_reissue_audit_provenance() -> None:
    record = _positive()
    record["restored_baseline"]["artifact"]["provenance_chain"].append(
        {
            "authority_table": "trust_access_log",
            "provenance_type": "audit_access_record",
            "source_ref": "urn:skeldir:audit:issuance:reissued",
            "source_ref_hash": "sha256:audit-ref",
            "source_snapshot_hash": "sha256:audit-hash",
            "observed_at": "2026-11-03T06:00:00Z",
            "display_metadata": {
                "text_trust_class": "none",
                "raw_text_sha256": None,
                "display_transform": "none",
            },
        }
    )
    result = _restoration_semantic_authority(
        record["baseline_signed"], record["restored_baseline"]
    )
    assert result["established"] is True
    assert _acceptance(record) is True


def test_restored_semantic_field_outside_old_list_is_refused() -> None:
    record = _positive()
    record["restored_baseline"]["artifact"]["evidence_temporal_boundary"][
        "data_freshness_bound"
    ] = "at_least_ceiling"
    assert _acceptance(record) is False


def test_different_full_semantic_hashes_do_not_refuse_restoration() -> None:
    record = _positive()
    record["baseline_signed"]["artifact"]["semantic_truth_hash"] = (
        "sha256:" + ("a" * 64)
    )
    record["restored_baseline"]["artifact"]["semantic_truth_hash"] = (
        "sha256:" + ("b" * 64)
    )
    result = _restoration_semantic_authority(
        record["baseline_signed"], record["restored_baseline"]
    )
    assert result["established"] is True
    assert _acceptance(record) is True


def test_unsupported_freshness_change_is_refused() -> None:
    record = _positive()
    record["restored_baseline"]["artifact"]["evidence_temporal_boundary"][
        "data_freshness_seconds"
    ] = 1
    result = _restoration_semantic_authority(
        record["baseline_signed"],
        record["restored_baseline"],
        restored_observation=record["restoration_observation"],
    )
    assert result["established"] is False
    assert result["reason"] == "observation_freshness_not_source_exact"
    assert _acceptance(record) is False


def test_policy_authority_change_is_refused() -> None:
    record = _positive()
    record["restored_baseline"]["artifact"]["policy_action_authority"][
        "reason_code"
    ] = "unsupported_policy_change"
    assert _acceptance(record) is False


def _at_path(document: object, path: tuple[object, ...]) -> object:
    cursor = document
    for part in path:
        cursor = cursor[part]
    return cursor


def _mutated(value: object) -> object:
    if isinstance(value, bool):
        return not value
    if isinstance(value, int):
        return value + 1
    if isinstance(value, str):
        return value + "-mutated"
    if isinstance(value, list):
        return [*value, "mutated"]
    if value is None:
        return "mutated"
    raise AssertionError(f"unsupported semantic leaf type: {type(value)!r}")


def _manifest_semantic_leaf_paths() -> list[tuple[object, ...]]:
    manifest = yaml.safe_load(
        (
            REPO_ROOT / "contracts/trust-api/hash-domain-manifest.v1.yaml"
        ).read_text(encoding="utf-8")
    )
    declared = [
        row["field_path"]
        for row in manifest["field_domains"]
        if row["domain"] == "semantic_truth_v1"
    ]
    leaves = [
        path
        for path in declared
        if not any(
            other.startswith(path + ".")
            or other.startswith(path + "[]")
            for other in declared
            if other != path
        )
    ]
    paths = []
    for path in leaves:
        parts: list[object] = []
        for part in path.split("."):
            if part.endswith("[]"):
                parts.extend((part[:-2], 0))
            else:
                parts.append(part)
        paths.append(tuple(parts))
    return paths


def _set_path(document: object, path: tuple[object, ...], value: object) -> None:
    cursor = document
    for index, part in enumerate(path[:-1]):
        if isinstance(part, int):
            while len(cursor) <= part:
                cursor.append({})
            cursor = cursor[part]
            continue
        following = path[index + 1]
        if not isinstance(cursor.get(part), (dict, list)):
            cursor[part] = [] if isinstance(following, int) else {}
        cursor = cursor[part]
    last = path[-1]
    if isinstance(last, int):
        while len(cursor) <= last:
            cursor.append({})
        cursor[last] = value
    else:
        cursor[last] = value


def test_every_contract_semantic_leaf_changes_authority() -> None:
    baseline = _real_baseline()
    paths = _manifest_semantic_leaf_paths()
    assert paths
    for path in paths:
        field = ".".join(str(part) for part in path)
        if field in _OBSERVATION_TIME_PATHS:
            continue
        restored = {"artifact": copy.deepcopy(baseline["artifact"])}
        artifact = restored["artifact"]
        if path[0] == "provenance_chain":
            index = next(
                index
                for index, entry in enumerate(artifact["provenance_chain"])
                if not _is_issuance_audit_entry(entry)
            )
            path = ("provenance_chain", index) + path[2:]
        try:
            current = _at_path(artifact, path)
        except (KeyError, IndexError, TypeError):
            current = None
        _set_path(
            artifact,
            path,
            "contract-leaf" if current is None else _mutated(current),
        )
        result = _restoration_semantic_authority(baseline, restored)
        assert result["established"] is False, field


def test_audit_label_cannot_hide_unsupported_provenance() -> None:
    record = _positive()
    record["restored_baseline"]["artifact"]["provenance_chain"].append(
        {
            "authority_table": "b23_match_verdicts",
            "provenance_type": "audit_hash",
            "source_ref": "urn:skeldir:b23_match_verdicts:unsupported",
            "source_ref_hash": "sha256:unsupported",
            "source_snapshot_hash": "sha256:unsupported",
            "observed_at": "2026-11-03T06:00:00Z",
            "display_metadata": {
                "text_trust_class": "none",
                "raw_text_sha256": None,
                "display_transform": "none",
            },
        }
    )
    assert _acceptance(record) is False


def test_contradictory_source_money_is_refused() -> None:
    record = _positive()
    record["causal_history"]["prior_ingress"][
        "verified_amount_minor"
    ] = 9999
    assert _acceptance(record) is False


def test_signed_witness_commitment_mismatch_is_refused() -> None:
    record = _positive()
    record["causal_history"]["witness_commitment"]["tip_hash"] = "c"
    result = _final_causal_progression(
        record["final_signed"],
        record["causal_history"],
        restored_signed=record["restored_baseline"],
        restoration_observed_at=record["restoration_observed_at"],
        amendment_admission_started_at=record[
            "amendment_admission_started_at"
        ],
        amendment_admitted_at=record["amendment_admitted_at"],
        final_observed_at=record["final_observed_at"],
        baseline_amount=4321,
        amended_amount=5100,
        currency="USD",
        verdict_id="v1",
    )
    assert result["established"] is False
    assert result["reason"] == "signed_witness_tip_mismatch"


def test_restoration_observed_after_amendment_is_refused() -> None:
    record = _positive()
    record["restoration_observed_at"] = "2026-11-03T06:00:06Z"
    record["restoration_observation"] = {
        "started_at": "2026-11-03T06:00:06Z",
        "completed_at": "2026-11-03T06:00:06Z",
    }
    result = _final_causal_progression(
        record["final_signed"],
        record["causal_history"],
        restored_signed=record["restored_baseline"],
        restoration_observed_at=record["restoration_observed_at"],
        amendment_admission_started_at=record[
            "amendment_admission_started_at"
        ],
        amendment_admitted_at=record["amendment_admitted_at"],
        final_observed_at=record["final_observed_at"],
        baseline_amount=4321,
        amended_amount=5100,
        currency="USD",
        verdict_id="v1",
    )
    assert result["established"] is False
    assert result["reason"] == "restoration_not_before_amendment_admission"


def test_final_provider_history_fabrication_is_refused() -> None:
    record = _positive()
    final = record["final_signed"]["artifact"]
    provider = next(
        entry
        for entry in final["provenance_chain"]
        if entry["provenance_type"] == "provider_native_reference"
    )
    provider["source_ref"] = (
        "urn:skeldir:provider_native_reference:fabricated"
    )
    assert _acceptance(record) is False


def test_final_ingress_history_fabrication_is_refused() -> None:
    record = _positive()
    final = record["final_signed"]["artifact"]
    webhook = next(
        entry
        for entry in final["provenance_chain"]
        if entry["provenance_type"] == "webhook_signature"
    )
    webhook["source_ref"] = (
        "urn:skeldir:webhook_ingress_identity:ingress-old"
    )
    assert _acceptance(record) is False


def test_final_causal_order_fabrication_is_refused() -> None:
    record = _positive()
    record["final_signed"]["artifact"]["created_at"] = (
        "2026-11-03T06:00:04Z"
    )
    result = _final_causal_progression(
        record["final_signed"],
        record["causal_history"],
        restored_signed=record["restored_baseline"],
        restoration_observed_at=record["restoration_observed_at"],
        amendment_admission_started_at=record[
            "amendment_admission_started_at"
        ],
        amendment_admitted_at=record["amendment_admitted_at"],
        final_observed_at=record["final_observed_at"],
        baseline_amount=4321,
        amended_amount=5100,
        currency="USD",
        verdict_id="v1",
    )
    assert result["established"] is False
    assert result["reason"] == "final_precedes_accepted_transition"


def test_all_results_bind_policy_audience_and_observation() -> None:
    for name in ("baseline_signed", "restored_baseline", "final_signed"):
        mutations = (
            lambda artifact: artifact["policy_action_authority"][
                "allowed_scopes"
            ].append("trust.action.execute"),
            lambda artifact: artifact["policy_action_authority"][
                "forbidden_scopes"
            ].remove("trust.action.execute"),
            lambda artifact: artifact["audience_binding"].__setitem__(
                "audience_id_hash", "sha256:other-audience"
            ),
            lambda artifact: artifact["evidence_temporal_boundary"].__setitem__(
                "data_freshness_seconds", 1
            ),
            lambda artifact: artifact["evidence_temporal_boundary"].__setitem__(
                "source_read_started_at",
                "2026-11-03T06:00:01Z",
            ),
        )
        for mutate in mutations:
            record = _positive()
            mutate(record[name]["artifact"])
            assert _acceptance(record) is False, name


def test_all_results_bind_source_authority() -> None:
    for name in ("baseline_signed", "restored_baseline", "final_signed"):
        for provenance_type in (
            "money_authority",
            "policy_decision",
            "reason_code_decision",
        ):
            record = _positive()
            entry = next(
                entry
                for entry in record[name]["artifact"]["provenance_chain"]
                if entry["provenance_type"] == provenance_type
            )
            entry["source_ref"] = "urn:skeldir:unrelated-source"
            assert _acceptance(record) is False, (name, provenance_type)
        record = _positive()
        record[name]["artifact"]["subject_authority"][
            "allowed_source_tables"
        ].append("unrelated_source_table")
        assert _acceptance(record) is False, name
        record = _positive()
        record[name]["artifact"]["benchmark_metadata"][
            "benchmark_status"
        ] = "available"
        record[name]["artifact"]["benchmark_metadata"][
            "benchmark_hash"
        ] = "sha256:invented"
        assert _acceptance(record) is False, name
        record = _positive()
        record[name]["artifact"]["confidence_metadata"][
            "confidence_status"
        ] = "available"
        assert _acceptance(record) is False, name


def test_final_changed_freshness_without_new_read_is_refused() -> None:
    record = _positive()
    final = record["final_signed"]["artifact"]
    final["evidence_temporal_boundary"]["data_freshness_seconds"] = 1
    assert _acceptance(record) is False


def test_final_observation_without_window_is_refused() -> None:
    record = _positive()
    record.pop("final_observation")
    assert _acceptance(record) is False


def test_final_gained_scope_is_refused() -> None:
    record = _positive()
    record["final_signed"]["artifact"]["policy_action_authority"][
        "allowed_scopes"
    ].append("trust.action.execute")
    assert _acceptance(record) is False


def test_final_dropped_forbidden_scope_is_refused() -> None:
    record = _positive()
    record["final_signed"]["artifact"]["policy_action_authority"][
        "forbidden_scopes"
    ].remove("trust.action.execute")
    assert _acceptance(record) is False


def test_final_other_audience_is_refused() -> None:
    record = _positive()
    record["final_signed"]["artifact"]["audience_binding"][
        "audience_id_hash"
    ] = "sha256:other-audience"
    assert _acceptance(record) is False


def test_invented_transition_content_under_unchanged_hash_is_refused() -> None:
    record = _positive()
    record["causal_history"]["ledger"][0][
        "prior_attributed_amount_minor"
    ] = 9999
    result = _final_causal_progression(
        record["final_signed"],
        record["causal_history"],
        restored_signed=record["restored_baseline"],
        restoration_observed_at=record["restoration_observed_at"],
        amendment_admission_started_at=record[
            "amendment_admission_started_at"
        ],
        amendment_admitted_at=record["amendment_admitted_at"],
        final_observed_at=record["final_observed_at"],
        baseline_amount=4321,
        amended_amount=5100,
        currency="USD",
        verdict_id="v1",
    )
    assert result["established"] is False
    assert result["reason"] == "ledger_transition_content_hash_mismatch"


def test_unexplained_origin_source_is_refused() -> None:
    record = _positive()
    record["causal_history"]["source_ingresses"].pop("ingress-old")
    result = _final_causal_progression(
        record["final_signed"],
        record["causal_history"],
        restored_signed=record["restored_baseline"],
        restoration_observed_at=record["restoration_observed_at"],
        amendment_admission_started_at=record[
            "amendment_admission_started_at"
        ],
        amendment_admitted_at=record["amendment_admitted_at"],
        final_observed_at=record["final_observed_at"],
        baseline_amount=4321,
        amended_amount=5100,
        currency="USD",
        verdict_id="v1",
    )
    assert result["established"] is False
    assert result["reason"] == "ledger_new_source_unexplained"


def test_foreign_modelled_later_witness_is_refused() -> None:
    record = _positive()
    history = record["causal_history"]
    row = history["ledger"][-1]
    row["new_attributed_amount_minor"] = 5200
    row["entry_hash"] = _ledger_entry_hash(row)
    history["global_ledger"][-1]["entry_hash"] = row["entry_hash"]
    replacement = _signed_witness_commitment(
        history["global_ledger"], history["authority_universe"]
    )
    history["witness_commitment"] = replacement
    history["prefix_digest"] = replacement["prefix_digest"]
    history["witness"] = {
        "count": replacement["count"],
        "tip_seq": replacement["tip_seq"],
        "tip_hash": replacement["tip_hash"],
    }
    history["continuity"] = {
        "count": replacement["count"],
        "tip_hash": replacement["tip_hash"],
    }
    result = _final_causal_progression(
        record["final_signed"],
        history,
        restored_signed=record["restored_baseline"],
        restoration_observed_at=record["restoration_observed_at"],
        amendment_admission_started_at=record[
            "amendment_admission_started_at"
        ],
        amendment_admitted_at=record["amendment_admitted_at"],
        final_observed_at=record["final_observed_at"],
        baseline_amount=4321,
        amended_amount=5100,
        currency="USD",
        verdict_id="v1",
        trusted_witness_public_key=record["witness_public_key"],
    )
    assert result["established"] is False
    assert result["reason"] == "signed_witness_untrusted_key"


def test_resigned_history_without_authority_restoration_is_refused() -> None:
    record = _positive()
    history = record["causal_history"]
    row = history["ledger"][-1]
    row["new_authority_state"] = "historically_unverifiable"
    row["entry_hash"] = _ledger_entry_hash(row)
    history["global_ledger"][-1]["entry_hash"] = row["entry_hash"]
    replacement = _signed_witness_commitment(
        history["global_ledger"], history["authority_universe"]
    )
    history["witness_commitment"] = replacement
    history["prefix_digest"] = replacement["prefix_digest"]
    history["witness"] = {
        "count": replacement["count"],
        "tip_seq": replacement["tip_seq"],
        "tip_hash": replacement["tip_hash"],
    }
    history["continuity"] = {
        "count": replacement["count"],
        "tip_hash": replacement["tip_hash"],
    }
    result = _final_causal_progression(
        record["final_signed"],
        history,
        restored_signed=record["restored_baseline"],
        restoration_observed_at=record["restoration_observed_at"],
        amendment_admission_started_at=record[
            "amendment_admission_started_at"
        ],
        amendment_admitted_at=record["amendment_admitted_at"],
        final_observed_at=record["final_observed_at"],
        baseline_amount=4321,
        amended_amount=5100,
        currency="USD",
        verdict_id="v1",
        tenant_id_hash=tenant_hash("tenant"),
    )
    assert result["established"] is False
    assert result["reason"] == "ledger_final_authority_mismatch"


def test_changed_tenant_identity_is_refused() -> None:
    record = _positive()
    record["causal_history"]["ledger"][0]["tenant_id"] = "other-tenant"
    result = _final_causal_progression(
        record["final_signed"],
        record["causal_history"],
        restored_signed=record["restored_baseline"],
        restoration_observed_at=record["restoration_observed_at"],
        amendment_admission_started_at=record[
            "amendment_admission_started_at"
        ],
        amendment_admitted_at=record["amendment_admitted_at"],
        final_observed_at=record["final_observed_at"],
        baseline_amount=4321,
        amended_amount=5100,
        currency="USD",
        verdict_id="v1",
        tenant_id_hash=tenant_hash("tenant"),
    )
    assert result["established"] is False
    assert result["reason"] == "ledger_tenant_identity_mismatch"


def test_tampered_source_attestation_is_refused() -> None:
    record = _positive()
    source = record["causal_history"]["source_ingresses"]["ingress-new"]
    source["source_attestation"]["statement"][
        "verified_amount_minor"
    ] = 9999
    result = _final_causal_progression(
        record["final_signed"],
        record["causal_history"],
        restored_signed=record["restored_baseline"],
        restoration_observed_at=record["restoration_observed_at"],
        amendment_admission_started_at=record[
            "amendment_admission_started_at"
        ],
        amendment_admitted_at=record["amendment_admitted_at"],
        final_observed_at=record["final_observed_at"],
        baseline_amount=4321,
        amended_amount=5100,
        currency="USD",
        verdict_id="v1",
    )
    assert result["established"] is False
    assert result["reason"].startswith("source_attestation_")


def _causal(record: dict, history: dict | None = None) -> dict:
    return _final_causal_progression(
        record["final_signed"],
        history or record["causal_history"],
        restored_signed=record["restored_baseline"],
        restoration_observed_at=record["restoration_observed_at"],
        amendment_admission_started_at=record[
            "amendment_admission_started_at"
        ],
        amendment_admitted_at=record["amendment_admitted_at"],
        final_observed_at=record["final_observed_at"],
        baseline_amount=4321,
        amended_amount=5100,
        currency="USD",
        verdict_id="v1",
        tenant_id_hash=tenant_hash("tenant"),
    )


def test_foreign_authority_universe_is_refused() -> None:
    record = _positive()
    source = record["causal_history"]["source_ingresses"]["ingress-new"]
    statement = dict(source["source_attestation"]["statement"])
    statement["authority_universe"] = "other-universe"
    source["source_attestation"] = _sign_source_statement(statement)
    result = _causal(record)
    assert result["established"] is False
    assert result["reason"] == "source_attestation_authority_universe_mismatch"


def test_foreign_economic_identity_is_refused() -> None:
    record = _positive()
    source = record["causal_history"]["source_ingresses"]["ingress-new"]
    statement = dict(source["source_attestation"]["statement"])
    statement["normalized_commerce_reference_value"] = "pi_other"
    source["source_attestation"] = _sign_source_statement(statement)
    result = _causal(record)
    assert result["established"] is False
    assert result["reason"] == "source_attestation_economic_identity_mismatch"


def test_future_final_evidence_snapshot_is_refused() -> None:
    record = _positive()
    record["final_signed"]["artifact"]["evidence_temporal_boundary"][
        "evidence_snapshot_at"
    ] = "2026-11-03T06:00:07Z"
    assert _acceptance(record) is False


def test_valid_concurrent_reversed_timestamps_are_accepted() -> None:
    record = _positive()
    history = record["causal_history"]
    history["ledger"][0]["recorded_at"] = "2026-11-03T06:00:05Z"
    history["ledger"][1]["recorded_at"] = "2026-11-03T06:00:04Z"
    history["global_ledger"][-2]["recorded_at"] = "2026-11-03T06:00:05Z"
    history["global_ledger"][-1]["recorded_at"] = "2026-11-03T06:00:04Z"
    assert _acceptance(record) is True


def test_inconsistent_target_and_global_time_is_refused() -> None:
    record = _positive()
    record["causal_history"]["ledger"][-1][
        "recorded_at"
    ] = "2026-11-03T06:00:04Z"
    result = _causal(record)
    assert result["established"] is False
    assert result["reason"] == "ledger_transition_time_mismatch"


def test_source_created_after_witness_is_refused() -> None:
    record = _positive()
    record["causal_history"]["source_ingresses"]["ingress-new"][
        "created_at"
    ] = "2026-11-03T06:00:07Z"
    result = _causal(record)
    assert result["established"] is False
    assert result["reason"] == "source_after_witness"


def test_removed_unavailability_provenance_is_refused() -> None:
    record = _positive()
    artifact = record["final_signed"]["artifact"]
    artifact["provenance_chain"] = [
        entry
        for entry in artifact["provenance_chain"]
        if not (
            entry.get("provenance_type") == "explicit_unavailable"
            and entry.get("source_ref")
            == "urn:skeldir:unavailable:b24_fit_id"
        )
    ]
    assert _acceptance(record) is False


def test_changed_text_transform_evidence_is_refused() -> None:
    record = _positive()
    entry = next(
        entry
        for entry in record["final_signed"]["artifact"]["provenance_chain"]
        if entry["provenance_type"] == "text_disposition"
    )
    entry["source_ref"] = "urn:skeldir:unrelated-text-transform"
    assert _acceptance(record) is False


def test_altered_read_skew_is_refused() -> None:
    record = _positive()
    record["final_signed"]["artifact"]["evidence_temporal_boundary"][
        "max_source_read_skew_ms"
    ] = 1
    assert _acceptance(record) is False


def test_missing_authority_universe_is_refused() -> None:
    record = _positive()
    record["causal_history"].pop("authority_universe")
    assert _acceptance(record) is False


def test_rollback_sequence_labels_are_accepted() -> None:
    record = _positive()
    history = record["causal_history"]
    first, second = history["ledger"]
    first["seq"] = 1
    first["prev_entry_hash"] = None
    first["entry_hash"] = _ledger_entry_hash(first)
    second["seq"] = 3
    second["prev_entry_hash"] = first["entry_hash"]
    second["entry_hash"] = _ledger_entry_hash(second)
    history["global_ledger"] = [
        {
            "seq": 1,
            "entry_hash": first["entry_hash"],
            "prev_entry_hash": None,
            "recorded_at": first["recorded_at"],
        },
        {
            "seq": 3,
            "entry_hash": second["entry_hash"],
            "prev_entry_hash": first["entry_hash"],
            "recorded_at": second["recorded_at"],
        },
    ]
    replacement = _signed_witness_commitment(
        history["global_ledger"], history["authority_universe"]
    )
    history["witness_commitment"] = replacement
    history["prefix_digest"] = replacement["prefix_digest"]
    history["witness"] = {
        "count": replacement["count"],
        "tip_seq": replacement["tip_seq"],
        "tip_hash": replacement["tip_hash"],
    }
    history["continuity"] = {
        "count": replacement["count"],
        "tip_hash": replacement["tip_hash"],
    }
    record["witness_public_key"] = replacement["public_key"]
    assert _acceptance(record) is True


def test_shared_ledger_activity_is_preserved() -> None:
    record = _positive()
    history = record["causal_history"]
    assert len(history["global_ledger"]) > len(history["ledger"])
    assert _acceptance(record) is True


def test_final_issued_in_same_second_as_commit_is_accepted() -> None:
    record = _positive()
    final = record["final_signed"]["artifact"]
    final["created_at"] = "2026-11-03T06:00:05Z"
    final["evidence_temporal_boundary"][
        "source_read_started_at"
    ] = "2026-11-03T06:00:05Z"
    final["evidence_temporal_boundary"][
        "source_read_completed_at"
    ] = "2026-11-03T06:00:05Z"
    assert _acceptance(record) is True


def test_ledger_chain_fabrication_is_refused() -> None:
    record = _positive()
    record["causal_history"]["ledger"][0][
        "prior_source_ingress"
    ] = "ingress-fabricated"
    result = _final_causal_progression(
        record["final_signed"],
        record["causal_history"],
        restored_signed=record["restored_baseline"],
        restoration_observed_at=record["restoration_observed_at"],
        amendment_admission_started_at=record[
            "amendment_admission_started_at"
        ],
        amendment_admitted_at=record["amendment_admitted_at"],
        final_observed_at=record["final_observed_at"],
        baseline_amount=4321,
        amended_amount=5100,
        currency="USD",
        verdict_id="v1",
    )
    assert result["established"] is False
    assert result["reason"] == "ledger_prior_source_mismatch"


def test_wrong_subject_fails_acceptance() -> None:
    record = _positive()
    record["amendment"]["subject"] = "pi_other"
    assert _acceptance(record) is False


def test_wrong_amount_fails_acceptance() -> None:
    record = _positive()
    record["amendment"]["amount_minor"] = 5000
    assert _acceptance(record) is False


def test_wrong_currency_fails_acceptance() -> None:
    record = _positive()
    record["readers"]["trust"]["currency"] = "EUR"
    assert _acceptance(record) is False


def test_rejected_signature_fails_acceptance() -> None:
    record = _positive()
    record["readers"]["trust_verify"][1]["verification_status"] = "rejected"
    assert _acceptance(record) is False


def test_unrestored_prefix_fails_acceptance() -> None:
    record = _positive()
    record["custody"]["restored_prefix_tip"] = "other"
    assert _acceptance(record) is False


def test_money_after_history_loss_fails_omitted_control() -> None:
    record = {
        "mode": "omit-restore",
        "baseline_signed": _verified(),
        "observed": {
            "http": 200,
            "money_minor": 5100,
            "specific": False,
            "new_row": True,
        },
        "compensation": {"restored_original": True},
        "original_unchanged": True,
        "restored_baseline": _verified(),
    }
    assert _negative_decision(record) is False


def test_transport_unavailability_fails_omitted_control() -> None:
    record = {
        "mode": "omit-restore",
        "baseline_signed": _verified(),
        "observed": {"http": 0, "specific": False, "new_row": False},
        "compensation": {"restored_original": True},
        "original_unchanged": True,
        "restored_baseline": _verified(),
    }
    assert _negative_decision(record) is False


def test_failed_restoration_fails_omitted_control() -> None:
    record = {
        "mode": "omit-restore",
        "baseline_signed": _verified(),
        "observed": {"http": 404, "specific": True, "new_row": True},
        "compensation": {"restored_original": False},
        "original_unchanged": False,
        "restored_baseline": _verified(),
    }
    assert _negative_decision(record) is False


def test_tamper_that_verifies_fails_control() -> None:
    record = {
        "mode": "tamper-signature",
        "baseline_signed": _verified(),
        "observed": {"signature_refused": False},
        "original_unchanged": True,
    }
    assert _negative_decision(record) is False


def test_successful_restore_fails_restore_failure_control() -> None:
    record = {
        "mode": "restore-failure",
        "baseline_signed": _verified(),
        "observed": {"restoration_refused": False},
        "original_unchanged": True,
    }
    assert _negative_decision(record) is False


def test_subject_refusal_cannot_be_borrowed() -> None:
    record = {
        "mode": "omit-restore",
        "baseline_signed": _verified(),
        "observed": {
            "http": 404,
            "money_minor": None,
            "specific": False,
            "new_row": False,
            "reason": "history_integrity_unverifiable",
        },
        "compensation": {"restored_original": True},
        "original_unchanged": True,
        "restored_baseline": _verified(),
    }
    assert _negative_decision(record) is False


def test_restored_other_journey_history_fails_omitted_control() -> None:
    restored = _verified()
    restored["artifact"]["provenance_chain"][0][
        "source_ref"
    ] = "urn:skeldir:b23_match_verdicts:other"
    record = {
        "mode": "omit-restore",
        "baseline_signed": _verified(),
        "observed": {
            "http": 404,
            "money_minor": None,
            "specific": True,
            "new_row": True,
            "reason": "history_integrity_unverifiable",
        },
        "compensation": {"restored_original": True},
        "original_unchanged": True,
        "restored_baseline": restored,
    }
    assert _negative_decision(record) is False


def test_signed_5100_cannot_satisfy_4321_baseline() -> None:
    record = _positive()
    record["baseline_signed"] = _verified(5100)
    assert _acceptance(record) is False


def test_signed_4321_for_another_subject_cannot_satisfy_baseline() -> None:
    record = _positive()
    artifact = _artifact(4321)
    artifact["subject_ref"] = "urn:skeldir:match_verdict:other"
    record["baseline_signed"]["artifact"] = artifact
    assert _acceptance(record) is False


def test_final_4321_cannot_satisfy_5100_progression() -> None:
    record = _positive()
    record["final_signed"] = _verified(4321)
    assert _acceptance(record) is False


def _real_baseline() -> dict:
    path = (
        REPO_ROOT
        / "docs"
        / "forensics"
        / "evidence"
        / "b26_p2_xxv_a8"
        / "xxv-r0034-recovery-positive-20261102.json"
    )
    document = json.loads(path.read_text(encoding="utf-8"))
    return copy.deepcopy(document["baseline_signed"])


def test_incompatible_public_key_cannot_verify_retained_artifact() -> None:
    observation = _real_baseline()
    keys = observation["public_key_basis"]["jwks"]["keys"]
    keys[0]["x"] = base64.urlsafe_b64encode(b"\x01" * 32).rstrip(b"=").decode("ascii")
    result = _offline_verification(observation)
    assert result["verification_status"] == "rejected"


def _matching_public_key(observation: dict) -> dict:
    kid = observation["artifact"]["signing_key_id"]
    return next(
        key
        for key in observation["public_key_basis"]["jwks"]["keys"]
        if key["kid"] == kid
    )


def test_verification_only_key_verifies_historical_signature() -> None:
    observation = _real_baseline()
    key = _matching_public_key(observation)
    key["skeldir_key_state"] = "verification_only"
    key["skeldir_retired_at"] = "2099-01-01T00:00:00Z"
    assert _key_lifecycle_valid(observation["artifact"], key) is True
    result = _offline_verification(observation)
    assert result["verification_status"] == "verified"


def test_retired_key_cannot_authenticate_a_new_result() -> None:
    observation = _real_baseline()
    key = _matching_public_key(observation)
    key["skeldir_key_state"] = "verification_only"
    key["skeldir_retired_at"] = "2026-11-03T00:00:00Z"
    assert _key_lifecycle_valid(observation["artifact"], key) is False
    result = _offline_verification(observation)
    assert result["verification_status"] == "rejected"


def test_revoked_or_expired_key_is_not_a_verification_basis() -> None:
    observation = _real_baseline()
    key = _matching_public_key(observation)
    for state in ("revoked", "expired"):
        key["skeldir_key_state"] = state
        assert _key_lifecycle_valid(observation["artifact"], key) is False


def test_key_cannot_verify_result_created_before_its_validity() -> None:
    observation = _real_baseline()
    key = _matching_public_key(observation)
    key["skeldir_valid_from"] = "2099-01-01T00:00:00Z"
    assert _key_lifecycle_valid(observation["artifact"], key) is False


def test_changed_tenant_cannot_satisfy_signed_structure() -> None:
    observation = _real_baseline()
    artifact = observation["artifact"]
    verdict_id = artifact["subject_ref"].rsplit(":", 1)[-1]
    ok, reason = _signed_structure(
        observation,
        verdict_id,
        artifact["verified_revenue_minor"],
        artifact["currency"],
        "sha256:another-tenant",
    )
    assert ok is False
    assert reason == "signed_tenant_mismatch"


def test_unsupported_financial_qualification_is_refused() -> None:
    observation = _real_baseline()
    artifact = observation["artifact"]
    verdict_id = artifact["subject_ref"].rsplit(":", 1)[-1]
    artifact["match_verdict_status"] = "signed_but_not_a_contract_state"
    ok, reason = _signed_structure(
        observation,
        verdict_id,
        artifact["verified_revenue_minor"],
        artifact["currency"],
        artifact["tenant_id_hash"],
    )
    assert ok is False
    assert reason == "signed_financial_qualification"
