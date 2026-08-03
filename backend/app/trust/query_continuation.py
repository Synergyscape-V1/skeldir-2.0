"""Opaque, request-bound continuation authority for B2.5-P10 exact-reference work."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Sequence
from uuid import UUID

from cryptography.exceptions import InvalidSignature

from app.trust.key_registry import TrustKeyRegistry, TrustKeyRegistryError
from app.trust.refusal import tenant_hash


CURSOR_VERSION = 1
CURSOR_PREFIX = "p10c1"
CURSOR_INTEGRITY_DOMAIN = b"skeldir:b25-p10:query-continuation:v1\x00"
CURSOR_TTL = timedelta(minutes=10)
MAX_CURSOR_TOKEN_BYTES = 2048


class TrustQueryContinuationError(ValueError):
    """A cursor is malformed, detached from its request, expired, or invalid."""

    def __init__(self, reason: str = "continuation_invalid") -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class TrustQueryContinuation:
    """Verified next-position state for one immutable accepted-work sequence."""

    next_position: int
    total_accepted: int
    expires_at: datetime


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _decode_b64url(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def _normalized_timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def trust_query_binding_hash(
    *,
    tenant_id: UUID,
    subject_types: Sequence[str],
    subject_refs: Sequence[str],
    updated_at_after: datetime | None,
    updated_at_before: datetime | None,
) -> str:
    """Hash the complete normalized request without exposing tenant or references."""
    material = {
        "authority": "b25-p10-exact-reference-query-v1",
        "tenant_id_hash": tenant_hash(tenant_id),
        "subject_types": list(subject_types),
        "subject_refs": list(subject_refs),
        "updated_at_after": _normalized_timestamp(updated_at_after),
        "updated_at_before": _normalized_timestamp(updated_at_before),
    }
    canonical = json.dumps(
        material,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def continuation_expiry(now: datetime) -> datetime:
    """Return a second-precise root expiry propagated by every later page."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("continuation_clock_timezone_required")
    return now.astimezone(timezone.utc).replace(microsecond=0) + CURSOR_TTL


def issue_trust_query_continuation(
    *,
    key_registry: TrustKeyRegistry,
    binding_hash: str,
    next_position: int,
    total_accepted: int,
    expires_at: datetime,
) -> str:
    """Sign deterministic position state in a cursor-specific Ed25519 domain."""
    if not (0 < next_position < total_accepted <= 50):
        raise ValueError("continuation_position_out_of_bounds")
    if expires_at.tzinfo is None or expires_at.utcoffset() is None:
        raise ValueError("continuation_expiry_timezone_required")
    key = key_registry.active_signing_key()
    if key.private_key is None:
        raise TrustKeyRegistryError("continuation_signing_key_missing_private_material")
    payload = {
        "binding": binding_hash,
        "exp": int(expires_at.astimezone(timezone.utc).timestamp()),
        "kid": key.kid,
        "next": next_position,
        "total": total_accepted,
        "v": CURSOR_VERSION,
    }
    encoded_payload = _b64url(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    )
    signature = key.private_key.sign(
        CURSOR_INTEGRITY_DOMAIN + encoded_payload.encode("ascii")
    )
    token = f"{CURSOR_PREFIX}.{encoded_payload}.{_b64url(signature)}"
    if len(token.encode("ascii")) > MAX_CURSOR_TOKEN_BYTES:
        raise ValueError("continuation_token_budget_exceeded")
    return token


def verify_trust_query_continuation(
    token: str,
    *,
    key_registry: TrustKeyRegistry,
    expected_binding_hash: str,
    expected_total: int,
    now: datetime,
) -> TrustQueryContinuation:
    """Verify cursor integrity, request binding, bounds, version, and expiry."""
    if not isinstance(token, str) or not token:
        raise TrustQueryContinuationError()
    try:
        raw = token.encode("ascii")
    except UnicodeEncodeError as exc:
        raise TrustQueryContinuationError() from exc
    if len(raw) > MAX_CURSOR_TOKEN_BYTES:
        raise TrustQueryContinuationError()
    try:
        prefix, encoded_payload, encoded_signature = token.split(".")
        if prefix != CURSOR_PREFIX:
            raise TrustQueryContinuationError()
        payload_bytes = _decode_b64url(encoded_payload)
        signature = _decode_b64url(encoded_signature)
        if (
            _b64url(payload_bytes) != encoded_payload
            or _b64url(signature) != encoded_signature
        ):
            raise TrustQueryContinuationError()
        decoded = json.loads(payload_bytes)
    except TrustQueryContinuationError:
        raise
    except Exception as exc:
        raise TrustQueryContinuationError() from exc
    if not isinstance(decoded, dict) or set(decoded) != {
        "binding",
        "exp",
        "kid",
        "next",
        "total",
        "v",
    }:
        raise TrustQueryContinuationError()
    try:
        version = decoded["v"]
        kid = decoded["kid"]
        binding_hash = decoded["binding"]
        next_position = decoded["next"]
        total_accepted = decoded["total"]
        expiry_epoch = decoded["exp"]
        if type(version) is not int or version != CURSOR_VERSION:
            raise TrustQueryContinuationError()
        if not isinstance(kid, str) or not isinstance(binding_hash, str):
            raise TrustQueryContinuationError()
        if type(next_position) is not int or type(total_accepted) is not int:
            raise TrustQueryContinuationError()
        if type(expiry_epoch) is not int:
            raise TrustQueryContinuationError()
        verification_key = key_registry.verification_key(kid)
        verification_key.public_key.verify(
            signature,
            CURSOR_INTEGRITY_DOMAIN + encoded_payload.encode("ascii"),
        )
    except TrustQueryContinuationError:
        raise
    except (InvalidSignature, TrustKeyRegistryError, ValueError, TypeError) as exc:
        raise TrustQueryContinuationError() from exc
    if not hmac.compare_digest(binding_hash, expected_binding_hash):
        raise TrustQueryContinuationError()
    if total_accepted != expected_total or not (
        0 < next_position < total_accepted <= 50
    ):
        raise TrustQueryContinuationError()
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("continuation_clock_timezone_required")
    expires_at = datetime.fromtimestamp(expiry_epoch, tz=timezone.utc)
    if now.astimezone(timezone.utc) >= expires_at:
        raise TrustQueryContinuationError("continuation_expired")
    return TrustQueryContinuation(
        next_position=next_position,
        total_accepted=total_accepted,
        expires_at=expires_at,
    )
