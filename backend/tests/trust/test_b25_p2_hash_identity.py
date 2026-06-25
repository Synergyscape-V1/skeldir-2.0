from __future__ import annotations

import copy
import json
import re
from pathlib import Path

from app.trust.hash_identity import (
    build_semantic_truth_hash_input,
    compute_artifact_hash,
    compute_semantic_truth_hash,
    compute_signature_hash,
)


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


def test_semantic_mutation_changes_only_semantic_identity() -> None:
    payload = _fixture()
    changed = copy.deepcopy(payload)
    changed["verified_revenue_minor"] = payload["verified_revenue_minor"] + 1

    assert compute_semantic_truth_hash(payload) != compute_semantic_truth_hash(changed)


def test_artifact_payload_hash_is_domain_separated_from_semantic_truth() -> None:
    payload = _fixture()

    assert compute_semantic_truth_hash(payload) != compute_artifact_hash(b"same bytes")
    assert compute_artifact_hash(b"artifact-v1") != compute_artifact_hash(b"artifact-v2")


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

