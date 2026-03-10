from __future__ import annotations

"""Structural boundary guards for lifecycle-sensitive secret material."""

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

REDACTION_REPLACEMENT = "***"
REDACTED_RAW_PROVIDER_BODY = "[REDACTED_RAW_PROVIDER_BODY]"
SENSITIVE_DETAIL_FALLBACK = "Sensitive details withheld."
MAX_SCAN_FINDINGS = 20
MAX_RECURSION_DEPTH = 10

FORBIDDEN_LIFECYCLE_KEYS: frozenset[str] = frozenset(
    {
        "access_token",
        "refresh_token",
        "authorization_code",
        "code_verifier",
        "client_secret",
    }
)

FORBIDDEN_RAW_PROVIDER_BODY_KEYS: frozenset[str] = frozenset(
    {
        "provider_raw_body",
        "provider_response_body",
        "raw_provider_body",
        "raw_response_body",
        "upstream_raw_body",
        "upstream_response_body",
        "vendor_payload",
        "response_body",
        "raw_body",
    }
)

SENSITIVE_KEY_SUFFIXES: tuple[str, ...] = (
    "_api_key",
    "_secret",
    "_token",
    "_password",
)
_EXPLICIT_SENSITIVE_TEXT_KEYS: tuple[str, ...] = (
    "DATABASE_URL",
    "DATABASE_DSN",
    "CELERY_BROKER_URL",
    "CELERY_RESULT_BACKEND",
    "AUTH_JWT_SECRET",
    "JWT_SECRET",
    "JWT_PRIVATE_KEY",
    "PLATFORM_TOKEN_ENCRYPTION_KEY",
    "LLM_PROVIDER_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "STRIPE_API_KEY",
    "PAYPAL_CLIENT_SECRET",
    "SHOPIFY_WEBHOOK_SECRET",
    "WOOCOMMERCE_WEBHOOK_SECRET",
)

_LIFECYCLE_SECRET_TEXT_PATTERN = re.compile(
    r"(?i)\b(access_token|refresh_token|authorization_code|code_verifier|client_secret)\b"
)
_KEY_VALUE_PATTERN = re.compile(
    r"(?i)\b("
    r"(?:access_token|refresh_token|authorization_code|code_verifier|client_secret)"
    r"|(?:"
    + "|".join(map(re.escape, _EXPLICIT_SENSITIVE_TEXT_KEYS))
    + r")"
    r"|(?:[a-z0-9_.-]+(?:_api_key|_secret|_token|_password))"
    r")\b"
    r"(\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|\S+)"
)
_BEARER_PATTERN = re.compile(r"(?i)\bBearer\s+([A-Za-z0-9\-\._~\+/]+=*)")
_DSN_PASSWORD_PATTERN = re.compile(r"(?i)\b(postgresql(?:\+\w+)?://[^:\s/]+:)([^@\s]+)(@)")


def normalize_boundary_key(key: str) -> str:
    return key.strip().lower().replace("-", "_").replace(" ", "_")


def is_forbidden_boundary_key(key: str) -> bool:
    normalized = normalize_boundary_key(key)
    if normalized in FORBIDDEN_LIFECYCLE_KEYS:
        return True
    if normalized in FORBIDDEN_RAW_PROVIDER_BODY_KEYS:
        return True
    return any(normalized.endswith(suffix) for suffix in SENSITIVE_KEY_SUFFIXES)


def is_raw_provider_body_key(key: str) -> bool:
    normalized = normalize_boundary_key(key)
    return normalized in FORBIDDEN_RAW_PROVIDER_BODY_KEYS


def redact_text_fragments(value: str) -> str:
    if not value:
        return value
    redacted = _KEY_VALUE_PATTERN.sub(rf"\1\2{REDACTION_REPLACEMENT}", value)
    redacted = _BEARER_PATTERN.sub("Bearer ***", redacted)
    redacted = _DSN_PASSWORD_PATTERN.sub(r"\1***\3", redacted)
    return redacted


def sanitize_for_transport(value: Any, *, _depth: int = 0) -> Any:
    if _depth > MAX_RECURSION_DEPTH:
        return REDACTION_REPLACEMENT

    if value is None or isinstance(value, (bool, int, float)):
        return value

    if isinstance(value, bytes):
        return f"[bytes:{len(value)}]"
    if isinstance(value, memoryview):
        return f"[bytes:{len(bytes(value))}]"

    if isinstance(value, str):
        return redact_text_fragments(value)

    if isinstance(value, Mapping):
        sanitized: dict[Any, Any] = {}
        for raw_key, raw_val in value.items():
            key = str(raw_key)
            if is_raw_provider_body_key(key):
                sanitized[key] = REDACTED_RAW_PROVIDER_BODY
                continue
            if is_forbidden_boundary_key(key):
                sanitized[key] = REDACTION_REPLACEMENT
                continue
            sanitized[key] = sanitize_for_transport(raw_val, _depth=_depth + 1)
        return sanitized

    if isinstance(value, tuple):
        return tuple(sanitize_for_transport(item, _depth=_depth + 1) for item in value)
    if isinstance(value, list):
        return [sanitize_for_transport(item, _depth=_depth + 1) for item in value]
    if isinstance(value, set):
        return [sanitize_for_transport(item, _depth=_depth + 1) for item in value]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [sanitize_for_transport(item, _depth=_depth + 1) for item in value]

    return redact_text_fragments(str(value))


def _scan_json_encoded_string(value: str, *, path: str, findings: list[str], _depth: int) -> None:
    trimmed = value.strip()
    if len(trimmed) < 2 or trimmed[0] not in "{[":
        return
    if _depth > MAX_RECURSION_DEPTH:
        return
    try:
        decoded = json.loads(trimmed)
    except json.JSONDecodeError:
        return
    for finding in find_forbidden_material(decoded, path=f"{path}.<json>", _depth=_depth + 1):
        if len(findings) >= MAX_SCAN_FINDINGS:
            return
        findings.append(finding)


def find_forbidden_material(value: Any, *, path: str = "$", _depth: int = 0) -> list[str]:
    findings: list[str] = []
    if _depth > MAX_RECURSION_DEPTH:
        return findings

    if isinstance(value, Mapping):
        for raw_key, raw_val in value.items():
            if len(findings) >= MAX_SCAN_FINDINGS:
                break
            key = str(raw_key)
            child_path = f"{path}.{key}"
            if is_forbidden_boundary_key(key):
                findings.append(child_path)
                if len(findings) >= MAX_SCAN_FINDINGS:
                    break
            findings.extend(find_forbidden_material(raw_val, path=child_path, _depth=_depth + 1))
            if len(findings) >= MAX_SCAN_FINDINGS:
                break
        return findings

    if isinstance(value, (list, tuple, set)):
        for idx, item in enumerate(value):
            if len(findings) >= MAX_SCAN_FINDINGS:
                break
            findings.extend(find_forbidden_material(item, path=f"{path}[{idx}]", _depth=_depth + 1))
            if len(findings) >= MAX_SCAN_FINDINGS:
                break
        return findings

    if isinstance(value, str):
        if _LIFECYCLE_SECRET_TEXT_PATTERN.search(value) or _BEARER_PATTERN.search(value):
            findings.append(path)
        _scan_json_encoded_string(value, path=path, findings=findings, _depth=_depth)
        return findings

    if isinstance(value, (bytes, memoryview)):
        findings.append(path)

    return findings


def assert_no_sensitive_material(value: Any, *, boundary_name: str) -> None:
    findings = find_forbidden_material(value)
    if not findings:
        return
    summarized = ", ".join(findings[:5])
    if len(findings) > 5:
        summarized = f"{summarized}, ..."
    raise ValueError(f"sensitive material blocked at {boundary_name}: {summarized}")


def sanitize_problem_detail(detail: str) -> str:
    if not detail:
        return detail
    if find_forbidden_material(detail):
        return SENSITIVE_DETAIL_FALLBACK
    return redact_text_fragments(detail)
