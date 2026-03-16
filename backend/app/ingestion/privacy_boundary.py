"""
Universal ingress privacy boundary enforcement for B1.4-P1.

This module enforces the write-boundary sequencing:
1) compute idempotency hash on full inbound payload,
2) derive transient pseudonymous session identity,
3) sanitize payload before durable writes.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import NAMESPACE_URL, UUID, uuid5

from app.core.secrets import get_secret

REDACTION_TOKEN = "[REDACTED_B1.4]"

# P0-derived direct identifier taxonomy consumed by P1.
BANNED_DIRECT_PII_KEYS: frozenset[str] = frozenset(
    {
        "address",
        "billing_address",
        "customer_email",
        "customer_phone",
        "email",
        "email_address",
        "first_name",
        "full_name",
        "ip",
        "ip_address",
        "last_name",
        "name",
        "phone",
        "phone_number",
        "receipt_email",
        "shipping_address",
        "social_security_number",
        "ssn",
        "street_address",
        "user_agent",
    }
)

_IDENTIFIER_EMAIL_KEYS: frozenset[str] = frozenset(
    {"email", "email_address", "customer_email", "receipt_email"}
)
_IDENTIFIER_IP_KEYS: frozenset[str] = frozenset({"ip", "ip_address"})
_IDENTIFIER_USER_AGENT_KEYS: frozenset[str] = frozenset({"user_agent"})

_EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}\b")
_IPV4_PATTERN = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"
)
_UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{12}$"
)


@dataclass(frozen=True)
class IngressPrivacyBoundaryResult:
    global_idempotency_hash: str
    session_id: str
    sanitized_payload: dict[str, Any]
    redacted_paths: tuple[str, ...]


def _normalize_key(key: str) -> str:
    return key.strip().lower().replace("-", "_")


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc).isoformat()
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, Mapping):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, set):
        return sorted(_json_safe(v) for v in value)
    return value


def _ensure_payload_dict(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return {}
    normalized = _json_safe(dict(payload))
    if isinstance(normalized, dict):
        return normalized
    return {"payload": normalized}


def compute_global_payload_hash(payload: Mapping[str, Any] | None) -> str:
    normalized = _ensure_payload_dict(payload)
    canonical = json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _daily_pepper(now: datetime | None = None) -> str:
    anchor = now or datetime.now(timezone.utc)
    base_pepper = get_secret("AUTH_LOGIN_IDENTIFIER_PEPPER") or "skeldir-b14-default-pepper"
    return hashlib.sha256(f"{base_pepper}:{anchor.date().isoformat()}".encode("utf-8")).hexdigest()


def _collect_identifier_values(
    payload: Any,
    *,
    request_headers: Mapping[str, str] | None = None,
) -> list[str]:
    values: list[str] = []

    def _walk(node: Any) -> None:
        if isinstance(node, Mapping):
            for raw_key, raw_value in node.items():
                key = _normalize_key(str(raw_key))
                if isinstance(raw_value, str):
                    trimmed = raw_value.strip()
                    if trimmed:
                        if key in _IDENTIFIER_EMAIL_KEYS:
                            values.append(f"email:{trimmed.lower()}")
                        elif key in _IDENTIFIER_IP_KEYS:
                            values.append(f"ip:{trimmed}")
                        elif key in _IDENTIFIER_USER_AGENT_KEYS:
                            values.append(f"ua:{trimmed}")
                _walk(raw_value)
            return
        if isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(payload)

    if request_headers:
        user_agent = (request_headers.get("user-agent") or "").strip()
        if user_agent:
            values.append(f"ua:{user_agent}")

        forwarded_for = (request_headers.get("x-forwarded-for") or "").strip()
        if forwarded_for:
            first_hop = forwarded_for.split(",", 1)[0].strip()
            if first_hop:
                values.append(f"ip:{first_hop}")

        real_ip = (request_headers.get("x-real-ip") or "").strip()
        if real_ip:
            values.append(f"ip:{real_ip}")

    return sorted(set(values))


def derive_transient_session_id(
    *,
    identity_payload: Mapping[str, Any] | None,
    source: str,
    idempotency_key: str,
    global_idempotency_hash: str,
    fallback_session_id: str | None = None,
    request_headers: Mapping[str, str] | None = None,
) -> str:
    identifiers = _collect_identifier_values(
        _ensure_payload_dict(identity_payload), request_headers=request_headers
    )

    if identifiers:
        basis = "|".join(identifiers)
    elif fallback_session_id and _UUID_PATTERN.match(str(fallback_session_id)):
        return str(fallback_session_id)
    else:
        basis = f"fallback:{source}:{idempotency_key}:{global_idempotency_hash[:24]}"

    digest = hashlib.sha256(f"{_daily_pepper()}|{basis}".encode("utf-8")).hexdigest()
    return str(uuid5(NAMESPACE_URL, f"b14-p1-session:{digest}"))


def _contains_direct_pii_value(value: str) -> bool:
    return bool(_EMAIL_PATTERN.search(value) or _IPV4_PATTERN.search(value))


def _sanitize_payload_recursive(
    payload: Any,
    *,
    mode: str,
    path: str,
    redacted_paths: list[str],
) -> Any:
    if isinstance(payload, Mapping):
        sanitized: dict[str, Any] = {}
        for key, value in payload.items():
            normalized_key = _normalize_key(str(key))
            child_path = f"{path}.{key}"

            if normalized_key in BANNED_DIRECT_PII_KEYS:
                redacted_paths.append(child_path)
                if mode == "redact":
                    sanitized[str(key)] = REDACTION_TOKEN
                continue

            sanitized[str(key)] = _sanitize_payload_recursive(
                value,
                mode=mode,
                path=child_path,
                redacted_paths=redacted_paths,
            )
        return sanitized

    if isinstance(payload, list):
        return [
            _sanitize_payload_recursive(
                item,
                mode=mode,
                path=f"{path}[{index}]",
                redacted_paths=redacted_paths,
            )
            for index, item in enumerate(payload)
        ]

    if isinstance(payload, str) and _contains_direct_pii_value(payload):
        redacted_paths.append(path)
        return REDACTION_TOKEN

    return payload


def enforce_ingress_privacy_boundary(
    *,
    storage_payload: Mapping[str, Any] | None,
    identity_payload: Mapping[str, Any] | None,
    source: str,
    idempotency_key: str,
    fallback_session_id: str | None = None,
    request_headers: Mapping[str, str] | None = None,
    mode: str = "strip",
) -> IngressPrivacyBoundaryResult:
    if mode not in {"strip", "redact"}:
        raise ValueError(f"Unsupported privacy boundary mode: {mode}")

    identity_payload_dict = _ensure_payload_dict(identity_payload)
    global_idempotency_hash = compute_global_payload_hash(identity_payload_dict)
    session_id = derive_transient_session_id(
        identity_payload=identity_payload_dict,
        source=source,
        idempotency_key=idempotency_key,
        global_idempotency_hash=global_idempotency_hash,
        fallback_session_id=fallback_session_id,
        request_headers=request_headers,
    )

    storage_payload_dict = _ensure_payload_dict(storage_payload)
    redacted_paths: list[str] = []
    sanitized_payload = _sanitize_payload_recursive(
        storage_payload_dict,
        mode=mode,
        path="root",
        redacted_paths=redacted_paths,
    )
    if not isinstance(sanitized_payload, dict):
        sanitized_payload = {"payload": sanitized_payload}

    sanitized_payload.setdefault("global_idempotency_hash", global_idempotency_hash)
    sanitized_payload.setdefault("session_id", session_id)

    return IngressPrivacyBoundaryResult(
        global_idempotency_hash=global_idempotency_hash,
        session_id=session_id,
        sanitized_payload=sanitized_payload,
        redacted_paths=tuple(sorted(set(redacted_paths))),
    )
