"""Canonical deterministic attribution semantics for B2.1-P1."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from hashlib import sha256
from typing import Any
from uuid import UUID


ATTRIBUTION_SEMANTICS_VERSION = "b2.1-p1-v1"
DETERMINISTIC_DEFAULT_LOOKBACK_DAYS = 30
_LOOKBACK_MIN_DAYS = 1
_LOOKBACK_MAX_DAYS = 365

TOUCHPOINT_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "ad_click",
        "ad_impression",
        "click",
        "email_click",
        "email_open",
        "landing_page_view",
        "page_view",
        "product_view",
        "session_start",
        "utm_click",
        "view",
    }
)

CONVERSION_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "checkout_completed",
        "conversion",
        "order_completed",
        "payment_intent_succeeded",
        "purchase",
        "sale_completed",
        "subscription_renewed",
    }
)


class AttributionEventKind(str, Enum):
    TOUCHPOINT = "touchpoint"
    CONVERSION = "conversion"
    NON_ATTRIBUTION = "non_attribution"


def _normalize_event_type(value: str) -> str:
    return str(value or "").strip().lower()


def classify_event_type(event_type: str) -> AttributionEventKind:
    normalized = _normalize_event_type(event_type)
    if normalized in TOUCHPOINT_EVENT_TYPES:
        return AttributionEventKind.TOUCHPOINT
    if normalized in CONVERSION_EVENT_TYPES:
        return AttributionEventKind.CONVERSION
    return AttributionEventKind.NON_ATTRIBUTION


def normalize_lookback_days(value: int | None) -> int:
    if value is None:
        return DETERMINISTIC_DEFAULT_LOOKBACK_DAYS
    resolved = int(value)
    if resolved < _LOOKBACK_MIN_DAYS or resolved > _LOOKBACK_MAX_DAYS:
        raise ValueError(
            f"lookback_days must be between {_LOOKBACK_MIN_DAYS} and {_LOOKBACK_MAX_DAYS}"
        )
    return resolved


def session_scope_identity(session_scope: UUID | None) -> str:
    return str(session_scope) if session_scope is not None else "__all__"


def compute_effective_replay_window(
    *,
    window_start: datetime,
    window_end: datetime,
    lookback_days: int,
) -> tuple[datetime, datetime]:
    replay_anchor_at = window_end.astimezone(timezone.utc)
    lookback_floor = replay_anchor_at - timedelta(days=lookback_days)
    effective_start = max(window_start.astimezone(timezone.utc), lookback_floor)
    return effective_start, replay_anchor_at


def digest_canonical_payloads(rows: list[dict[str, Any]]) -> str:
    canonical_json = json.dumps(
        rows,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return sha256(canonical_json.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AttributionInputRow:
    tenant_id: UUID
    event_id: UUID
    idempotency_key: str
    session_id: UUID
    occurred_at: datetime
    event_type: str
    channel_code: str
    revenue_cents: int
    global_idempotency_hash: str | None

    def canonical_identity(self) -> dict[str, Any]:
        return {
            "tenant_id": str(self.tenant_id),
            "event_id": str(self.event_id),
            "idempotency_key": str(self.idempotency_key),
            "session_id": str(self.session_id),
            "occurred_at": self.occurred_at.astimezone(timezone.utc).isoformat(),
            "event_type": _normalize_event_type(self.event_type),
            "channel_code": str(self.channel_code).strip().lower(),
            "revenue_cents": int(self.revenue_cents),
            "global_idempotency_hash": (
                str(self.global_idempotency_hash) if self.global_idempotency_hash else None
            ),
        }


@dataclass(frozen=True)
class AttributionOutputRow:
    allocation_id: UUID
    tenant_id: UUID
    event_id: UUID
    channel_code: str
    allocation_ratio: str
    model_version: str
    model_type: str
    confidence_score: str
    verified: bool
    allocated_revenue_cents: int
    created_at: datetime
    updated_at: datetime

    def canonical_identity(self) -> dict[str, Any]:
        return {
            "allocation_id": str(self.allocation_id),
            "tenant_id": str(self.tenant_id),
            "event_id": str(self.event_id),
            "channel_code": str(self.channel_code).strip().lower(),
            "allocation_ratio": str(self.allocation_ratio),
            "model_version": str(self.model_version),
            "model_type": str(self.model_type),
            "confidence_score": str(self.confidence_score),
            "verified": bool(self.verified),
            "allocated_revenue_cents": int(self.allocated_revenue_cents),
            "created_at": self.created_at.astimezone(timezone.utc).isoformat(),
            "updated_at": self.updated_at.astimezone(timezone.utc).isoformat(),
        }


@dataclass(frozen=True)
class DeterministicReplayIdentity:
    tenant_id: UUID
    model_version: str
    taxonomy_version: str
    lookback_days: int
    window_start: datetime
    window_end: datetime
    replay_window_start: datetime
    replay_window_end: datetime
    replay_anchor_at: datetime
    session_scope_identity: str

    def as_payload(self) -> dict[str, Any]:
        return {
            "tenant_id": str(self.tenant_id),
            "model_version": str(self.model_version),
            "taxonomy_version": str(self.taxonomy_version),
            "lookback_days": int(self.lookback_days),
            "window_start": self.window_start.astimezone(timezone.utc).isoformat(),
            "window_end": self.window_end.astimezone(timezone.utc).isoformat(),
            "replay_window_start": self.replay_window_start.astimezone(timezone.utc).isoformat(),
            "replay_window_end": self.replay_window_end.astimezone(timezone.utc).isoformat(),
            "replay_anchor_at": self.replay_anchor_at.astimezone(timezone.utc).isoformat(),
            "session_scope_identity": str(self.session_scope_identity),
        }

    def digest(self) -> str:
        return digest_canonical_payloads([self.as_payload()])

    def job_model_version(self) -> str:
        replay_suffix = (
            f"taxonomy={self.taxonomy_version};"
            f"lookback_days={self.lookback_days};"
            f"session_scope={self.session_scope_identity};"
            f"replay_anchor_at={self.replay_anchor_at.astimezone(timezone.utc).isoformat()}"
        )
        return f"{self.model_version}::{replay_suffix}"
