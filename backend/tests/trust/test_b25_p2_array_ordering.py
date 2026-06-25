from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from app.trust.array_ordering import ArrayOrderingError
from app.trust.hash_identity import compute_semantic_truth_hash


ROOT = Path(__file__).resolve().parents[3]
EXAMPLES = ROOT / "contracts/trust-api/examples"


def _fixture() -> dict:
    return json.loads(
        (EXAMPLES / "revenue_claim_valid_with_verified_revenue_minor.json").read_text(
            encoding="utf-8"
        )
    )


def _second_provenance_entry() -> dict:
    return {
        "provenance_type": "webhook_signature",
        "authority_table": "webhook_ingress_identities",
        "source_ref": "urn:skeldir:webhook_ingress_identities:rc_public",
        "source_ref_hash": "sha256:" + "9" * 64,
        "source_snapshot_hash": "sha256:" + "8" * 64,
        "observed_at": "2026-06-24T09:59:59Z",
        "display_metadata": {
            "text_trust_class": "none",
            "raw_text_sha256": None,
            "display_transform": "none",
        },
    }


def test_provenance_chain_permutations_hash_identically() -> None:
    payload = _fixture()
    payload["provenance_chain"].append(_second_provenance_entry())
    permuted = copy.deepcopy(payload)
    permuted["provenance_chain"] = list(reversed(permuted["provenance_chain"]))

    assert compute_semantic_truth_hash(payload) == compute_semantic_truth_hash(permuted)


def test_duplicate_provenance_sort_key_with_distinct_objects_fails() -> None:
    payload = _fixture()
    duplicate = copy.deepcopy(payload["provenance_chain"][0])
    duplicate["authority_table"] = "webhook_ingress_identities"
    payload["provenance_chain"].append(duplicate)

    with pytest.raises(ArrayOrderingError, match="array_sort_key_ambiguous"):
        compute_semantic_truth_hash(payload)


def test_missing_provenance_sort_key_fails() -> None:
    payload = _fixture()
    del payload["provenance_chain"][0]["source_ref"]

    with pytest.raises(Exception):
        compute_semantic_truth_hash(payload)


def test_scope_array_permutations_hash_identically() -> None:
    payload = _fixture()
    permuted = copy.deepcopy(payload)
    permuted["audience_binding"]["audience_scope"] = list(
        reversed(permuted["audience_binding"]["audience_scope"])
    )
    permuted["policy_action_authority"]["forbidden_scopes"] = list(
        reversed(permuted["policy_action_authority"]["forbidden_scopes"])
    )

    assert compute_semantic_truth_hash(payload) == compute_semantic_truth_hash(permuted)

