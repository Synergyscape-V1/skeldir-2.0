from __future__ import annotations

from scripts.ci.validate_b25_p2_canonicalization import (
    discover_schema_array_paths,
    discover_schema_field_paths,
)

from app.trust.array_ordering import validate_array_ordering_manifest_against_schema
from app.trust.hash_domains import validate_hash_domain_manifest_against_schema


def test_hash_domain_manifest_covers_every_schema_field_path() -> None:
    assert validate_hash_domain_manifest_against_schema(discover_schema_field_paths()) == 93


def test_array_ordering_manifest_covers_every_schema_array_path() -> None:
    assert validate_array_ordering_manifest_against_schema(discover_schema_array_paths()) == 5

