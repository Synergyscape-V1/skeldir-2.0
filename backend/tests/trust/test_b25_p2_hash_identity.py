from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest

from app.trust.hash_identity import (
    HASH_DOMAIN_WRAPPER_SCHEMA,
    build_semantic_truth_hash_input,
    compute_artifact_hash,
    compute_semantic_truth_hash,
    compute_signature_hash,
    validate_hash_domain_wrapper,
)
from app.trust.hash_domains import HashDomainError


ROOT = Path(__file__).resolve().parents[3]
EXAMPLES = ROOT / "contracts/trust-api/examples"
HASH_RE = re.compile(r"^sha256:[a-f0-9]{64}$")


def _fixture() -> dict:
    return json.loads(
        (EXAMPLES / "revenue_claim_valid_with_verified_revenue_minor.json").read_text(
            encoding="utf-8"
        )
    )


def test_hash_outputs_use_fixed_prefixed_lowercase_hex() -> None:
    payload = _fixture()

    assert HASH_RE.match(compute_semantic_truth_hash(payload))
    assert HASH_RE.match(compute_artifact_hash(b"artifact-bytes"))
    assert HASH_RE.match(compute_signature_hash(payload))


def test_signature_metadata_does_not_change_semantic_truth_hash() -> None:
    payload = _fixture()
    changed = copy.deepcopy(payload)
    changed["signing_key_id"] = "kid:b25-p2-other-key"
    changed["signature"] = "different-placeholder-signature"

    assert compute_semantic_truth_hash(payload) == compute_semantic_truth_hash(changed)
    assert compute_signature_hash(payload) != compute_signature_hash(changed)


def test_display_only_text_does_not_contaminate_semantic_truth_hash() -> None:
    payload = _fixture()
    changed = copy.deepcopy(payload)
    changed["untrusted_display_data"]["display_text"] = "provider label changed"

    assert compute_semantic_truth_hash(payload) == compute_semantic_truth_hash(changed)


def test_semantic_unicode_probe_participates_in_semantic_truth_hash() -> None:
    payload = json.loads(
        (
            EXAMPLES / "canonicalization/revenue_claim_semantic_unicode_valid.json"
        ).read_text(encoding="utf-8")
    )
    changed = copy.deepcopy(payload)
    del changed["semantic_unicode_probe"]

    assert (
        build_semantic_truth_hash_input(payload)["payload"]["semantic_unicode_probe"]
        == payload["semantic_unicode_probe"]
    )
    assert compute_semantic_truth_hash(payload) != compute_semantic_truth_hash(changed)


def test_semantic_mutation_changes_only_semantic_identity() -> None:
    payload = _fixture()
    changed = copy.deepcopy(payload)
    changed["verified_revenue_minor"] = payload["verified_revenue_minor"] + 1

    assert compute_semantic_truth_hash(payload) != compute_semantic_truth_hash(changed)


def test_artifact_payload_hash_is_domain_separated_from_semantic_truth() -> None:
    payload = _fixture()

    assert compute_semantic_truth_hash(payload) != compute_artifact_hash(b"same bytes")
    assert compute_artifact_hash(b"artifact-v1") != compute_artifact_hash(
        b"artifact-v2"
    )


def test_structured_hash_input_prevents_concatenation_ambiguity() -> None:
    base = _fixture()
    case_1 = copy.deepcopy(base)
    case_2 = copy.deepcopy(base)
    case_1["subject_ref"] = "urn:skeldir:revenue_claim:a"
    case_1["subject_authority"]["subject_ref"] = case_1["subject_ref"]
    case_1["currency"] = "USD"
    case_2["subject_ref"] = "urn:skeldir:revenue_claim:ab"
    case_2["subject_authority"]["subject_ref"] = case_2["subject_ref"]
    case_2["currency"] = "USC"

    input_1 = build_semantic_truth_hash_input(case_1)
    input_2 = build_semantic_truth_hash_input(case_2)
    assert input_1["payload"]["subject_ref"] != input_2["payload"]["subject_ref"]
    assert compute_semantic_truth_hash(case_1) != compute_semantic_truth_hash(case_2)


def test_hash_domain_wrapper_rejects_extra_or_wrong_domain_payload_fields() -> None:
    valid = build_semantic_truth_hash_input(_fixture())
    extra_key = copy.deepcopy(valid)
    extra_key["malicious_policy_override"] = True
    wrong_payload = copy.deepcopy(valid)
    wrong_payload["payload"]["signing_key_id"] = "kid:bad"

    with pytest.raises(
        HashDomainError,
        match="hash_wrapper_schema_validation_failed:additionalProperties",
    ):
        validate_hash_domain_wrapper(extra_key)
    with pytest.raises(HashDomainError, match="hash_wrapper_payload_domain_mismatch"):
        validate_hash_domain_wrapper(wrong_payload)


def test_hash_domain_wrapper_schema_is_declaratively_closed() -> None:
    assert HASH_DOMAIN_WRAPPER_SCHEMA["additionalProperties"] is False
    assert set(HASH_DOMAIN_WRAPPER_SCHEMA["required"]) == {
        "hash_domain",
        "schema_version",
        "canonicalization_version",
        "hash_algorithm",
        "payload",
    }
    assert HASH_DOMAIN_WRAPPER_SCHEMA["properties"]["hash_algorithm"]["const"] == (
        "sha-256"
    )
