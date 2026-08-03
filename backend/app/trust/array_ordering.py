"""Manifest-driven array ordering for TrustEnvelope canonicalization."""

from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = ROOT / "contracts/trust-api/array-ordering-manifest.v1.yaml"


class ArrayOrderingError(ValueError):
    """Raised when an array field cannot be canonically ordered."""


@lru_cache(maxsize=1)
def _load_manifest() -> dict[str, Any]:
    """Load the immutable, deploy-time manifest once per worker."""
    with MANIFEST_PATH.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@lru_cache(maxsize=1)
def _array_rules() -> dict[str, dict[str, Any]]:
    """Compile the immutable array-ordering lookup once per worker."""
    return {row["field_path"]: row for row in _load_manifest()["array_fields"]}


def classify_array_ordering(field_path: str) -> str:
    """Return the declared ordering class for a TrustEnvelope array path."""
    try:
        return str(_array_rules()[field_path]["ordering"])
    except KeyError as exc:
        raise ArrayOrderingError(f"array_ordering_unclassified:{field_path}") from exc


def _canonical_element_bytes(value: Any) -> bytes:
    text = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return text.encode("utf-8")


def _canonical_element_hash(value: Any) -> str:
    return sha256(_canonical_element_bytes(value)).hexdigest()


def _sort_by_declared_key_tuple(
    field_path: str, array_value: list[Any], sort_key: list[str]
) -> list[Any]:
    seen: dict[tuple[Any, ...], Any] = {}
    keyed: list[tuple[tuple[Any, ...], Any]] = []
    for item in array_value:
        if not isinstance(item, dict):
            raise ArrayOrderingError(f"array_item_not_object:{field_path}")
        missing = [key for key in sort_key if key not in item]
        if missing:
            raise ArrayOrderingError(f"array_sort_key_missing:{field_path}:{missing[0]}")
        key = tuple(item[key] for key in sort_key)
        if key in seen and seen[key] != item:
            raise ArrayOrderingError(f"array_sort_key_ambiguous:{field_path}:{key!r}")
        seen[key] = item
        keyed.append((key, item))
    return [deepcopy(item) for _, item in sorted(keyed, key=lambda pair: pair[0])]


def _sort_by_canonical_element_hash(field_path: str, array_value: list[Any]) -> list[Any]:
    seen: dict[str, Any] = {}
    keyed: list[tuple[str, Any]] = []
    for item in array_value:
        digest = _canonical_element_hash(item)
        if digest in seen and seen[digest] != item:
            raise ArrayOrderingError(f"array_element_hash_collision:{field_path}:{digest}")
        seen[digest] = item
        keyed.append((digest, item))
    return [deepcopy(item) for _, item in sorted(keyed, key=lambda pair: pair[0])]


def canonicalize_array_by_declared_ordering(
    field_path: str, array_value: list[Any]
) -> list[Any]:
    """Return an array ordered according to the array-ordering manifest."""
    rule = _array_rules().get(field_path)
    if rule is None:
        raise ArrayOrderingError(f"array_ordering_unclassified:{field_path}")
    ordering = rule["ordering"]
    if ordering == "ordered_sequence_preserve_order":
        return deepcopy(array_value)
    if ordering == "unordered_set_sort_by_declared_key_tuple":
        return _sort_by_declared_key_tuple(field_path, array_value, rule["sort_key"])
    if ordering == "unordered_set_sort_by_canonical_element_hash":
        return _sort_by_canonical_element_hash(field_path, array_value)
    if ordering == "single_item_or_empty_constrained_array":
        if len(array_value) > 1:
            raise ArrayOrderingError(f"array_too_many_items:{field_path}")
        return deepcopy(array_value)
    raise ArrayOrderingError(f"array_ordering_reserved_or_unknown:{field_path}:{ordering}")


def validate_array_ordering_manifest_against_schema(
    schema_array_paths: set[str],
) -> int:
    """Validate manifest coverage against schema-discovered array paths."""
    rules = _array_rules()
    manifest_paths = set(rules)
    missing = sorted(schema_array_paths - manifest_paths)
    extra = sorted(manifest_paths - schema_array_paths)
    if missing:
        raise ArrayOrderingError(f"array_manifest_missing_paths:{missing}")
    if extra:
        raise ArrayOrderingError(f"array_manifest_unknown_paths:{extra}")
    return len(manifest_paths)
