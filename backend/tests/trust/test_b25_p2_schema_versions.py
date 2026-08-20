from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.trust.canonicalization import canonicalize_envelope_payload
from app.trust.schema_versions import (
    VersionRegistryError,
    get_supported_canonicalization_versions,
    get_supported_schema_versions,
    validate_canonicalization_version,
    validate_schema_version,
)


ROOT = Path(__file__).resolve().parents[3]
EXAMPLES = ROOT / "contracts/trust-api/examples"


def _fixture() -> dict:
    return json.loads(
        (EXAMPLES / "revenue_claim_valid_with_verified_revenue_minor.json").read_text(
            encoding="utf-8"
        )
    )


def test_supported_versions_are_registry_bound() -> None:
    assert get_supported_schema_versions() == (
        "trust-envelope-schema-v1",
        "trust-envelope-schema-v2",
    )
    assert get_supported_canonicalization_versions() == ("trust-canonical-json-v1",)


@pytest.mark.parametrize("value", [None, "", "v0", "trust-envelope-schema-v999"])
def test_schema_version_fails_closed(value) -> None:
    with pytest.raises(VersionRegistryError, match="schema_version_unsupported"):
        validate_schema_version(value)


@pytest.mark.parametrize("value", [None, "", "latest", "RFC8785-JCS-Skeldir-v999"])
def test_canonicalization_version_fails_closed(value) -> None:
    with pytest.raises(
        VersionRegistryError, match="canonicalization_version_unsupported"
    ):
        validate_canonicalization_version(value)


def test_unknown_versions_fail_before_schema_validation_or_hashing() -> None:
    payload = _fixture()
    payload["canonicalization_version"] = "latest"

    with pytest.raises(
        VersionRegistryError, match="canonicalization_version_unsupported"
    ):
        canonicalize_envelope_payload(payload)
