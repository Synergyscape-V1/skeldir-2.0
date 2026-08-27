from __future__ import annotations

from scripts.ci.validate_b25_p2_canonicalization import (
    discover_schema_array_paths,
    discover_schema_field_paths,
)

from app.trust.array_ordering import validate_array_ordering_manifest_against_schema
from app.trust.hash_domains import validate_hash_domain_manifest_against_schema


def test_hash_domain_manifest_covers_every_schema_field_path() -> None:
    # 109 before C10, 119 after C10, 121 after C13. The twelve added paths are
    # the inference provenance the signature now commits to: the policy bundle
    # hash, all six policy/semantics versions, and the authorised/observed
    # topology pair. Pinned exactly
    # rather than bounded, so a field entering the schema without a declared
    # hash domain -- signed but unclassified -- turns this red.
    assert (
        validate_hash_domain_manifest_against_schema(discover_schema_field_paths())
        == 121
    )


def test_array_ordering_manifest_covers_every_schema_array_path() -> None:
    assert (
        validate_array_ordering_manifest_against_schema(discover_schema_array_paths())
        == 6
    )
