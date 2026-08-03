"""Schema and canonicalization-version registry enforcement."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[3]
SCHEMA_REGISTRY_PATH = ROOT / "contracts/trust-api/schema-version-registry.yaml"
CANONICALIZATION_REGISTRY_PATH = (
    ROOT / "contracts/trust-api/canonicalization-version-registry.yaml"
)


class VersionRegistryError(ValueError):
    """Raised when schema/canonicalization versions fail closed."""


@lru_cache(maxsize=2)
def _read_yaml(path: Path) -> dict[str, Any]:
    """Load immutable, deploy-time version registries once per worker."""
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise VersionRegistryError(f"registry_not_object:{path.as_posix()}")
    return data


def get_supported_schema_versions() -> tuple[str, ...]:
    registry = _read_yaml(SCHEMA_REGISTRY_PATH)
    return tuple(
        row["schema_version"]
        for row in registry.get("supported_schema_versions", [])
        if row.get("status") == "supported"
    )


def get_supported_canonicalization_versions() -> tuple[str, ...]:
    registry = _read_yaml(CANONICALIZATION_REGISTRY_PATH)
    return tuple(
        row["canonicalization_version"]
        for row in registry.get("canonicalization_versions", [])
        if row.get("status") == "supported"
    )


def validate_schema_version(schema_version: Any) -> str:
    """Validate schema_version against the fail-closed registry."""
    if not isinstance(schema_version, str) or not schema_version:
        raise VersionRegistryError("schema_version_unsupported:missing")
    if schema_version not in get_supported_schema_versions():
        raise VersionRegistryError(f"schema_version_unsupported:{schema_version}")
    return schema_version


def validate_canonicalization_version(canonicalization_version: Any) -> str:
    """Validate canonicalization_version against the fail-closed registry."""
    if not isinstance(canonicalization_version, str) or not canonicalization_version:
        raise VersionRegistryError("canonicalization_version_unsupported:missing")
    if canonicalization_version not in get_supported_canonicalization_versions():
        raise VersionRegistryError(
            f"canonicalization_version_unsupported:{canonicalization_version}"
        )
    return canonicalization_version


def validate_schema_canonicalization_compatibility(
    schema_version: Any, canonicalization_version: Any
) -> tuple[str, str]:
    """Validate version pair compatibility before canonicalization or hashing."""
    schema = validate_schema_version(schema_version)
    canonical = validate_canonicalization_version(canonicalization_version)
    registry = _read_yaml(CANONICALIZATION_REGISTRY_PATH)
    for row in registry.get("canonicalization_versions", []):
        if row.get("canonicalization_version") == canonical:
            compatible = set(row.get("compatible_schema_versions", []))
            if schema not in compatible:
                raise VersionRegistryError(
                    f"canonicalization_version_incompatible:{schema}:{canonical}"
                )
            return schema, canonical
    raise VersionRegistryError(f"canonicalization_version_unsupported:{canonical}")
