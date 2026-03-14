"""Machine-readable privacy authority accessors and helpers."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping
from uuid import UUID, uuid4


_AUTHORITY_PATH = Path(__file__).resolve().parents[3] / "contracts-internal" / "governance" / "b14_p0_privacy_authority.main.json"


def _as_string_set(values: list[Any]) -> set[str]:
    return {str(value).strip().lower() for value in values if str(value).strip()}


@lru_cache(maxsize=1)
def load_privacy_authority() -> dict[str, Any]:
    if not _AUTHORITY_PATH.exists():
        raise FileNotFoundError(f"privacy authority artifact is missing: {_AUTHORITY_PATH}")
    payload = json.loads(_AUTHORITY_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("privacy authority artifact root must be a JSON object")
    return payload


def banned_identifier_key_set() -> set[str]:
    authority = load_privacy_authority()
    direct = authority.get("banned_direct_identifier_keys", [])
    proxy = authority.get("banned_proxy_identifier_keys", [])
    return _as_string_set(list(direct) + list(proxy))


def _payload_allowlist() -> set[str]:
    authority = load_privacy_authority()
    lifecycle = authority.get("event_lifecycle", {})
    durable_store = lifecycle.get("durable_store", {})
    allowlist = durable_store.get("payload_allowlist_keys", [])
    return _as_string_set(list(allowlist))


def _payload_forbidden() -> set[str]:
    authority = load_privacy_authority()
    lifecycle = authority.get("event_lifecycle", {})
    durable_store = lifecycle.get("durable_store", {})
    forbidden = durable_store.get("payload_forbidden_keys", [])
    return _as_string_set(list(forbidden))


def minimize_event_payload_for_storage(event_data: Mapping[str, Any]) -> dict[str, Any]:
    """
    Build a durable, minimized payload for immutable attribution events.

    The durable payload is intentionally constrained so raw provider envelopes and
    identity proxies do not persist on append-only event rows.
    """
    allowlist = _payload_allowlist()
    forbidden = _payload_forbidden() | banned_identifier_key_set()
    minimized: dict[str, Any] = {}
    for key, value in event_data.items():
        normalized = str(key).strip().lower()
        if normalized in forbidden:
            continue
        if normalized in allowlist:
            minimized[normalized] = value
    return minimized


def generate_privacy_session_id() -> UUID:
    """Return a non-deterministic session identifier."""
    return uuid4()

