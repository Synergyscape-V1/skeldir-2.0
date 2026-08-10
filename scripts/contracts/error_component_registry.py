#!/usr/bin/env python3
"""Governed shared error-component registry and provenance fingerprinting.

B2.5-P11 third corrective. The repository-wide error-model gate previously
accepted any 4xx/5xx response that carried
``x-skeldir-shared-error-component: true``. A self-asserted boolean is not
provenance: it let an arbitrary malformed response authorize itself anywhere in
the contract tree.

This module replaces self-attestation with mechanically verified identity:

    declared shared provenance  ->  registered component id
                                ->  exact canonical schema fingerprint
                                ->  mechanically verified shared provenance

Failure modes that must fail closed:

* boolean ``true`` (no identity claimed);
* an unregistered component id;
* a registered id whose response schema does not fingerprint-match;
* a response claiming the identity of a different registered component.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Mapping

import yaml


_REGISTRY_RELATIVE = Path(
    "api-contracts/openapi/v1/_common/error-component-registry.yaml"
)
#: Resolved from this module's location so the gate behaves identically whether
#: it is invoked from the repository root or from any other working directory.
_REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = _REPO_ROOT / _REGISTRY_RELATIVE

PROVENANCE_MARKER = "x-skeldir-shared-error-component"

#: Keys stripped before fingerprinting. These are documentation-only and must
#: not change a component's cryptographic identity.
_NON_SEMANTIC_KEYS = frozenset({"description", "example", "examples", "summary"})

STRUCTURAL_RULE_RFC7807 = "rfc7807"
STRUCTURAL_RULE_EXACT_FINGERPRINT = "exact_fingerprint"

_VALID_STRUCTURAL_RULES = frozenset(
    {STRUCTURAL_RULE_RFC7807, STRUCTURAL_RULE_EXACT_FINGERPRINT}
)


class ErrorComponentRegistryError(ValueError):
    """Raised when the registry itself is malformed."""


def _strip_non_semantic(value: Any) -> Any:
    """Remove documentation-only keys so prose edits cannot change identity."""
    if isinstance(value, dict):
        return {
            key: _strip_non_semantic(child)
            for key, child in value.items()
            if key not in _NON_SEMANTIC_KEYS and not key.startswith("x-")
        }
    if isinstance(value, list):
        return [_strip_non_semantic(child) for child in value]
    return value


def canonical_schema_fingerprint(response: Mapping[str, Any]) -> str:
    """Fingerprint the semantic content of one OpenAPI response object.

    Only ``content`` participates. Descriptions, examples, and ``x-`` extensions
    are excluded so that documentation edits do not require a registry rewrite,
    while any change to media types, schemas, required fields, enums, or
    ``additionalProperties`` produces a different fingerprint.
    """
    content = response.get("content", {})
    normalized = _strip_non_semantic(content)
    serialized = json.dumps(
        normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def load_registry(registry_path: Path | None = None) -> Dict[str, Dict[str, Any]]:
    """Load and structurally validate the governed component registry."""
    path = registry_path or REGISTRY_PATH
    if not path.exists():
        raise ErrorComponentRegistryError(f"registry_missing:{path}")
    with open(path, "r", encoding="utf-8") as fh:
        document = yaml.safe_load(fh)
    if not isinstance(document, dict):
        raise ErrorComponentRegistryError("registry_not_a_mapping")
    components = document.get("components")
    if not isinstance(components, list) or not components:
        raise ErrorComponentRegistryError("registry_components_missing")

    registry: Dict[str, Dict[str, Any]] = {}
    for entry in components:
        if not isinstance(entry, dict):
            raise ErrorComponentRegistryError("registry_entry_not_a_mapping")
        component_id = entry.get("component_id")
        if not isinstance(component_id, str) or not component_id:
            raise ErrorComponentRegistryError("registry_entry_missing_component_id")
        if component_id in registry:
            raise ErrorComponentRegistryError(
                f"registry_duplicate_component_id:{component_id}"
            )
        structural_rule = entry.get("structural_rule")
        if structural_rule not in _VALID_STRUCTURAL_RULES:
            raise ErrorComponentRegistryError(
                f"registry_invalid_structural_rule:{component_id}"
            )
        if not isinstance(entry.get("owning_phase"), str):
            raise ErrorComponentRegistryError(
                f"registry_entry_missing_owning_phase:{component_id}"
            )
        if structural_rule == STRUCTURAL_RULE_EXACT_FINGERPRINT:
            fingerprint = entry.get("schema_fingerprint")
            if not isinstance(fingerprint, str) or not fingerprint.startswith(
                "sha256:"
            ):
                raise ErrorComponentRegistryError(
                    f"registry_entry_missing_fingerprint:{component_id}"
                )
        registry[component_id] = entry
    return registry


def verify_declared_provenance(
    response: Mapping[str, Any],
    registry: Mapping[str, Mapping[str, Any]],
) -> tuple[bool, str]:
    """Mechanically verify a response's declared shared-component provenance.

    Returns ``(is_verified, reason)``. A response that does not declare the
    marker at all returns ``(False, "no_declared_provenance")`` so the caller can
    fall through to the ordinary structural checks.
    """
    if PROVENANCE_MARKER not in response:
        return False, "no_declared_provenance"

    declared = response.get(PROVENANCE_MARKER)

    # A boolean cannot identify a component. This is the exact escape hatch the
    # third corrective closes: self-assertion is not provenance.
    if not isinstance(declared, str) or not declared:
        return False, "provenance_marker_must_name_a_registered_component_id"

    entry = registry.get(declared)
    if entry is None:
        return False, f"provenance_component_id_not_registered:{declared}"

    structural_rule = entry.get("structural_rule")
    if structural_rule == STRUCTURAL_RULE_RFC7807:
        # Registered but governed by the ordinary structural rule; the caller
        # still has to satisfy the RFC 7807 shape check.
        return False, f"provenance_component_requires_structural_check:{declared}"

    expected = entry.get("schema_fingerprint")
    actual = canonical_schema_fingerprint(response)
    if actual != expected:
        return False, (
            f"provenance_schema_fingerprint_mismatch:{declared}:"
            f"expected={expected}:actual={actual}"
        )
    return True, f"provenance_verified:{declared}"


def main() -> int:
    """Recompute fingerprints for every bundled response declaring the marker.

    Operational helper used when a governed component's schema legitimately
    changes. Prints ``component_id  fingerprint`` pairs discovered in the
    bundled contract tree so the registry can be updated deliberately.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Recompute governed error-component fingerprints."
    )
    parser.add_argument("--input-dir", default="api-contracts/dist/openapi/v1")
    args = parser.parse_args()

    seen: Dict[str, str] = {}
    for file_path in sorted(Path(args.input_dir).glob("*.bundled.yaml")):
        with open(file_path, "r", encoding="utf-8") as fh:
            spec = yaml.safe_load(fh)
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
                        seen[declared] = canonical_schema_fingerprint(response)

    for component_id, fingerprint in sorted(seen.items()):
        print(f"{component_id}\t{fingerprint}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
