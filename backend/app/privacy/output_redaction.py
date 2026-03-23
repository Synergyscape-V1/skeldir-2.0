"""Privacy output-surface redaction and leak detection helpers (B1.4-P5)."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.security.secret_boundary import (
    REDACTION_REPLACEMENT,
    normalize_boundary_key,
    redact_text_fragments,
)

_MAX_RECURSION_DEPTH = 10
_AUTHORITY_PATH = (
    Path(__file__).resolve().parents[3]
    / "contracts-internal"
    / "governance"
    / "b14_p0_privacy_authority.main.json"
)

_DEFAULT_PROXY_OUTPUT_KEYS: frozenset[str] = frozenset(
    {
        "session_id",
        "idempotency_key",
        "external_event_id",
        "order_id",
        "click_id",
        "gclid",
        "fbclid",
        "transaction_id",
        "user_agent",
        "raw_headers",
        "raw_payload",
    }
)

_EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}\b")
_IPV4_PATTERN = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"
)
_SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_INLINE_PROXY_VALUE_PATTERN = re.compile(
    r"(?i)\b("
    r"session_id|idempotency_key|external_event_id|order_id|click_id|gclid|fbclid|transaction_id|user_agent|ip_address|ip"
    r")\b"
    r"(\s*[:=]\s*)"
    r"(\"[^\"]*\"|'[^']*'|\S+)"
)


@lru_cache(maxsize=1)
def _load_privacy_authority_payload() -> dict[str, Any]:
    if not _AUTHORITY_PATH.exists():
        return {}
    try:
        payload = json.loads(_AUTHORITY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def _redact_ipv4_match(match: re.Match[str]) -> str:
    value = match.group(0)
    # Preserve loopback/private RFC1918 addresses used in local DSNs and test harnesses.
    if value.startswith("127.") or value.startswith("10.") or value.startswith("192.168."):
        return value
    if value.startswith("172."):
        try:
            second = int(value.split(".", 2)[1])
        except (ValueError, IndexError):
            second = -1
        if 16 <= second <= 31:
            return value
    return REDACTION_REPLACEMENT


def _normalized_key_set(values: Sequence[Any]) -> set[str]:
    return {
        normalize_boundary_key(str(value))
        for value in values
        if str(value).strip()
    }


def output_forbidden_key_set(
    *,
    extra_forbidden: Sequence[str] | None = None,
    exclude: Sequence[str] | None = None,
) -> set[str]:
    """
    Resolve the canonical output-surface forbidden key set for P5.

    This combines P0 authority keys with P5-specific proxy-identifier keys that
    must not appear in export/log/artifact surfaces.
    """
    forbidden: set[str] = set(_DEFAULT_PROXY_OUTPUT_KEYS)
    authority = _load_privacy_authority_payload()

    forbidden.update(_normalized_key_set(authority.get("banned_direct_identifier_keys", [])))
    forbidden.update(_normalized_key_set(authority.get("banned_proxy_identifier_keys", [])))
    log_contract = authority.get("log_artifact_no_leak", {})
    forbidden.update(_normalized_key_set(log_contract.get("forbidden_keys", [])))
    export_contract = authority.get("export_contract", {})
    forbidden.update(_normalized_key_set(export_contract.get("forbidden_fields", [])))

    if extra_forbidden:
        forbidden.update(_normalized_key_set(list(extra_forbidden)))
    if exclude:
        forbidden.difference_update(_normalized_key_set(list(exclude)))
    return forbidden


def redact_output_text(value: str) -> str:
    """Redact direct and proxy identifiers from free-text output."""
    if not value:
        return value
    redacted = redact_text_fragments(value)
    redacted = _EMAIL_PATTERN.sub(REDACTION_REPLACEMENT, redacted)
    redacted = _IPV4_PATTERN.sub(_redact_ipv4_match, redacted)
    redacted = _SSN_PATTERN.sub(REDACTION_REPLACEMENT, redacted)
    redacted = _INLINE_PROXY_VALUE_PATTERN.sub(rf"\1\2{REDACTION_REPLACEMENT}", redacted)
    return redacted


def sanitize_output_payload(
    value: Any,
    *,
    forbidden_keys: set[str] | None = None,
    drop_forbidden_keys: bool = False,
    _depth: int = 0,
) -> Any:
    """Recursively sanitize an output payload for logs/artifacts/exports."""
    if _depth > _MAX_RECURSION_DEPTH:
        return REDACTION_REPLACEMENT

    forbidden = forbidden_keys or output_forbidden_key_set()

    if value is None or isinstance(value, (bool, int, float)):
        return value

    if isinstance(value, bytes):
        return f"[bytes:{len(value)}]"
    if isinstance(value, memoryview):
        return f"[bytes:{len(bytes(value))}]"

    if isinstance(value, str):
        return redact_output_text(value)

    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key)
            if normalize_boundary_key(key) in forbidden:
                if drop_forbidden_keys:
                    continue
                sanitized[key] = REDACTION_REPLACEMENT
                continue
            sanitized[key] = sanitize_output_payload(
                raw_value,
                forbidden_keys=forbidden,
                drop_forbidden_keys=drop_forbidden_keys,
                _depth=_depth + 1,
            )
        return sanitized

    if isinstance(value, tuple):
        return tuple(
            sanitize_output_payload(
                item,
                forbidden_keys=forbidden,
                drop_forbidden_keys=drop_forbidden_keys,
                _depth=_depth + 1,
            )
            for item in value
        )
    if isinstance(value, list):
        return [
            sanitize_output_payload(
                item,
                forbidden_keys=forbidden,
                drop_forbidden_keys=drop_forbidden_keys,
                _depth=_depth + 1,
            )
            for item in value
        ]
    if isinstance(value, set):
        return [
            sanitize_output_payload(
                item,
                forbidden_keys=forbidden,
                drop_forbidden_keys=drop_forbidden_keys,
                _depth=_depth + 1,
            )
            for item in value
        ]
    if isinstance(value, Sequence):
        return [
            sanitize_output_payload(
                item,
                forbidden_keys=forbidden,
                drop_forbidden_keys=drop_forbidden_keys,
                _depth=_depth + 1,
            )
            for item in value
        ]

    return redact_output_text(str(value))


def _contains_forbidden_text(value: str) -> bool:
    return bool(
        _EMAIL_PATTERN.search(value)
        or _IPV4_PATTERN.search(value)
        or _SSN_PATTERN.search(value)
        or _INLINE_PROXY_VALUE_PATTERN.search(value)
    )


def find_output_leaks(
    value: Any,
    *,
    forbidden_keys: set[str] | None = None,
    path: str = "$",
    _depth: int = 0,
) -> list[str]:
    """Find direct/proxy identifier leaks in output payloads."""
    if _depth > _MAX_RECURSION_DEPTH:
        return []
    forbidden = forbidden_keys or output_forbidden_key_set()
    findings: list[str] = []

    if isinstance(value, Mapping):
        for raw_key, raw_value in value.items():
            key = str(raw_key)
            child_path = f"{path}.{key}"
            if normalize_boundary_key(key) in forbidden:
                findings.append(child_path)
            findings.extend(
                find_output_leaks(
                    raw_value,
                    forbidden_keys=forbidden,
                    path=child_path,
                    _depth=_depth + 1,
                )
            )
        return findings

    if isinstance(value, (list, tuple, set)):
        for index, item in enumerate(value):
            findings.extend(
                find_output_leaks(
                    item,
                    forbidden_keys=forbidden,
                    path=f"{path}[{index}]",
                    _depth=_depth + 1,
                )
            )
        return findings

    if isinstance(value, str) and _contains_forbidden_text(value):
        findings.append(path)
        return findings

    if isinstance(value, (bytes, memoryview)):
        findings.append(path)

    return findings
