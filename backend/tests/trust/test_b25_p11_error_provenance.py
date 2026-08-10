"""B2.5-P11 third corrective: shared error-model provenance must be verified.

The second corrective cycle made the repository-wide error-model gate accept any
4xx/5xx response carrying ``x-skeldir-shared-error-component: true``. That is
self-attestation, not provenance: an arbitrary malformed response anywhere in the
contract tree could authorize itself.

These are adversarial controls. They prove the checker establishes provenance
mechanically -- registered component identity plus exact canonical schema
fingerprint -- rather than trusting a token's presence.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[3]
CONTRACTS_SCRIPTS = ROOT / "scripts" / "contracts"
BUNDLED_EXPORT = ROOT / "api-contracts/dist/openapi/v1/export.bundled.yaml"

if str(CONTRACTS_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(CONTRACTS_SCRIPTS))

from check_error_model import response_is_valid  # noqa: E402
from error_component_registry import (  # noqa: E402
    PROVENANCE_MARKER,
    canonical_schema_fingerprint,
    load_registry,
)


@pytest.fixture(scope="module")
def registry() -> dict:
    return load_registry()


@pytest.fixture(scope="module")
def governed_response() -> dict:
    """The genuine, post-bundling P11 503 response."""
    if not BUNDLED_EXPORT.exists():
        pytest.skip("bundled export contract not built")
    spec = yaml.safe_load(BUNDLED_EXPORT.read_text(encoding="utf-8"))
    for path_item in (spec.get("paths") or {}).values():
        if not isinstance(path_item, dict):
            continue
        for method_item in path_item.values():
            if not isinstance(method_item, dict):
                continue
            response = (method_item.get("responses") or {}).get("503")
            if isinstance(response, dict):
                return copy.deepcopy(response)
    pytest.fail("no governed 503 response found in bundled export contract")


def _malformed_response() -> dict:
    """A response matching neither RFC 7807 nor any governed component."""
    return {
        "description": "arbitrary non-conforming error",
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {"whatever": {"type": "string"}},
                }
            }
        },
    }


def test_positive_control_legitimate_shared_component_passes(
    governed_response, registry
) -> None:
    valid, reason = response_is_valid(governed_response, registry)
    assert valid is True, reason
    assert reason.startswith("provenance_verified:")


def test_negative_control_a_malformed_without_provenance_fails(registry) -> None:
    valid, reason = response_is_valid(_malformed_response(), registry)
    assert valid is False
    assert reason == "response_does_not_reference_shared_error_component"


def test_negative_control_b_self_asserted_boolean_marker_still_fails(registry) -> None:
    """The exact escape hatch this corrective closes."""
    malformed = _malformed_response()
    malformed[PROVENANCE_MARKER] = True
    valid, reason = response_is_valid(malformed, registry)
    assert valid is False, "a boolean must never authorize an arbitrary error shape"
    assert reason == "provenance_marker_must_name_a_registered_component_id"


def test_negative_control_c_claiming_another_components_identity_fails(
    governed_response, registry
) -> None:
    impostor = copy.deepcopy(governed_response)
    impostor[PROVENANCE_MARKER] = "skeldir.export.ExportLimitExceeded"
    valid, reason = response_is_valid(impostor, registry)
    assert valid is False
    assert reason.startswith("provenance_schema_fingerprint_mismatch:")


def test_negative_control_d_semantically_altered_component_fails(
    governed_response, registry
) -> None:
    """Structurally similar is not good enough; identity must be exact."""
    altered = copy.deepcopy(governed_response)
    schema = altered["content"]["application/json"]["schema"]
    schema["properties"]["detail"]["properties"]["reason_code"]["enum"].append(
        "attacker_injected_reason"
    )
    valid, reason = response_is_valid(altered, registry)
    assert valid is False
    assert reason.startswith("provenance_schema_fingerprint_mismatch:")


def test_negative_control_e_unregistered_component_id_fails(registry) -> None:
    malformed = _malformed_response()
    malformed[PROVENANCE_MARKER] = "skeldir.attacker.Fabricated"
    valid, reason = response_is_valid(malformed, registry)
    assert valid is False
    assert reason.startswith("provenance_component_id_not_registered:")


def test_documentation_edits_do_not_change_component_identity(
    governed_response,
) -> None:
    """Fingerprints must track semantics, not prose."""
    baseline = canonical_schema_fingerprint(governed_response)
    reworded = copy.deepcopy(governed_response)
    reworded["description"] = "completely different wording"
    media = reworded["content"]["application/json"]
    media["examples"] = {"new": {"value": {"detail": {"status": "refused"}}}}
    assert canonical_schema_fingerprint(reworded) == baseline


def test_every_registered_fingerprint_matches_a_real_bundled_response(
    registry,
) -> None:
    """The registry must not drift from the contracts it governs."""
    if not BUNDLED_EXPORT.exists():
        pytest.skip("bundled export contract not built")

    observed: dict[str, set[str]] = {}
    for bundled in sorted(
        (ROOT / "api-contracts/dist/openapi/v1").glob("*.bundled.yaml")
    ):
        spec = yaml.safe_load(bundled.read_text(encoding="utf-8"))
        for path_item in (spec.get("paths") or {}).values():
            if not isinstance(path_item, dict):
                continue
            for method_item in path_item.values():
                if not isinstance(method_item, dict):
                    continue
                for response in (method_item.get("responses") or {}).values():
                    if not isinstance(response, dict):
                        continue
                    declared = response.get(PROVENANCE_MARKER)
                    if isinstance(declared, str) and declared:
                        observed.setdefault(declared, set()).add(
                            canonical_schema_fingerprint(response)
                        )

    for component_id, fingerprints in observed.items():
        entry = registry.get(component_id)
        assert entry is not None, f"{component_id} used but not registered"
        assert len(fingerprints) == 1, (
            f"{component_id} resolves to multiple schemas {fingerprints}; one "
            "component id must denote exactly one schema"
        )
        assert (
            fingerprints.pop() == entry["schema_fingerprint"]
        ), f"{component_id} bundled schema drifted from its registered fingerprint"
