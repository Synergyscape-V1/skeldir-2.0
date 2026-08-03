"""Hash-domain manifest helpers for B2.5-P2 TrustEnvelope identity."""

from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = ROOT / "contracts/trust-api/hash-domain-manifest.v1.yaml"


class HashDomainError(ValueError):
    """Raised when hash-domain classification is missing or invalid."""


@lru_cache(maxsize=1)
def _load_manifest() -> dict[str, Any]:
    """Load the immutable, deploy-time manifest once per worker."""
    with MANIFEST_PATH.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@lru_cache(maxsize=1)
def _field_domains() -> dict[str, str]:
    """Compile the immutable field-domain lookup once per worker."""
    domains: dict[str, str] = {}
    for row in _load_manifest()["field_domains"]:
        path = row["field_path"]
        if path in domains:
            raise HashDomainError(f"hash_domain_duplicate:{path}")
        domains[path] = row["domain"]
    return domains


def classify_hash_domain(field_path: str) -> str:
    """Return the declared hash domain for a TrustEnvelope field path."""
    try:
        return _field_domains()[field_path]
    except KeyError as exc:
        raise HashDomainError(f"hash_domain_unclassified:{field_path}") from exc


def validate_hash_domain_manifest_against_schema(schema_field_paths: set[str]) -> int:
    """Validate exact field-path coverage against schema-discovered fields."""
    domains = _field_domains()
    manifest_paths = set(domains)
    missing = sorted(schema_field_paths - manifest_paths)
    extra = sorted(manifest_paths - schema_field_paths)
    if missing:
        raise HashDomainError(f"hash_manifest_missing_paths:{missing}")
    if extra:
        raise HashDomainError(f"hash_manifest_unknown_paths:{extra}")
    return len(manifest_paths)


def project_domain_payload(payload: dict[str, Any], domain: str) -> dict[str, Any]:
    """Project an envelope payload to fields classified for one hash domain."""
    domains = _field_domains()

    def include(path: str) -> bool:
        return domains.get(path) == domain

    def has_descendant(path: str) -> bool:
        prefix = f"{path}."
        array_prefix = f"{path}[]."
        return any(
            item_domain == domain
            and (
                item_path.startswith(prefix)
                or item_path.startswith(array_prefix)
                or item_path == f"{path}[]"
            )
            for item_path, item_domain in domains.items()
        )

    def project(value: Any, path: str) -> Any:
        if isinstance(value, dict):
            out: dict[str, Any] = {}
            for key, child in value.items():
                child_path = f"{path}.{key}" if path else key
                if include(child_path) or has_descendant(child_path):
                    out[key] = project(child, child_path)
            return out
        if isinstance(value, list):
            child_path = f"{path}[]"
            if include(path) and not has_descendant(child_path):
                return deepcopy(value)
            return [project(item, child_path) for item in value]
        return deepcopy(value)

    projected = project(payload, "")
    if not isinstance(projected, dict):
        raise HashDomainError("hash_domain_projection_not_object")
    return projected
