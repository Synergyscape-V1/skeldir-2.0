"""Self-falsification of the recovery decision, independent of a live lane."""

from __future__ import annotations

import base64
import copy
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ci"))

from b26_p2_xxv_recovery_probe import (  # noqa: E402
    _acceptance,
    _key_lifecycle_valid,
    _negative_decision,
    _offline_verification,
    _signed_structure,
    _subject_ref_hash,
)


def _baseline() -> dict:
    return {
        "http": 200,
        "verdict_id": "v1",
        "subject": "pi_same",
        "amount_minor": 4321,
        "currency": "USD",
        "reconciliation_status": 200,
        "reconciliation_net_minor": 4321,
        "tenant_id_hash": "sha256:tenant",
    }


def _artifact(amount: int) -> dict:
    urn = "urn:skeldir:match_verdict:v1"
    digest = _subject_ref_hash(urn)
    return {
        "subject_type": "match_verdict",
        "subject_ref": urn,
        "subject_ref_hash": digest,
        "tenant_id_hash": "sha256:tenant",
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
        "policy_action_authority": {"policy_state": "read_only"},
        "evidence_temporal_boundary": {
            "staleness_status": "current",
            "snapshot_consistency_status": "consistent",
            "evidence_age_status": "within_supported_horizon",
            "evidence_snapshot_hash": "sha256:snapshot",
        },
        "provenance_chain": [
            {
                "authority_table": "b23_match_verdicts",
                "provenance_type": "match_verdict",
                "source_ref": "urn:skeldir:b23_match_verdicts:v1",
            }
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


def _positive() -> dict:
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
        "final_signed": _verified(5100),
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


def test_contract_confirmed_match_is_consumable() -> None:
    record = _positive()
    record["final_signed"]["artifact"]["match_verdict_status"] = "matched"
    record["final_signed"]["artifact"]["data_completeness_status"] = "complete"
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
