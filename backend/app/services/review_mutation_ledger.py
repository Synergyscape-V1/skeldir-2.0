"""Postgres-native idempotency and audit ledger for B1.5 review mutations."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from app.core import clock as clock_module


class IdempotencyConflictError(ValueError):
    """Raised when an idempotency key is reused with a different payload."""


@dataclass(frozen=True)
class ReviewMutationLedgerResult:
    replayed: bool
    stored_effects: dict[str, Any]


def scoped_review_idempotency_key(
    *,
    domain: str,
    entity_id: UUID,
    action: str,
    idempotency_key: UUID,
) -> str:
    """Derive a deterministic scoped key to avoid cross-action collisions."""
    return f"b15:{domain}:{entity_id}:{action}:{idempotency_key}"


def digest_sha256(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class ReviewMutationLedger:
    """Append-only mutation ledger using compliance_audit_ledger."""

    async def record_or_replay(
        self,
        conn: AsyncConnection | AsyncSession,
        *,
        tenant_id: UUID,
        correlation_id: Optional[UUID],
        actor: UUID,
        scoped_idempotency_key: str,
        selector: dict[str, Any],
        effects: dict[str, Any],
        audit_event_type: str,
    ) -> ReviewMutationLedgerResult:
        selector_hash = digest_sha256(selector)
        effects_hash = digest_sha256(effects)
        occurred_at = clock_module.utcnow()
        inserted = await conn.execute(
            text(
                """
                INSERT INTO compliance_audit_ledger (
                    tenant_id,
                    created_at,
                    updated_at,
                    occurred_at,
                    audit_event_type,
                    correlation_id,
                    idempotency_key,
                    selector,
                    selector_hash,
                    effects,
                    evidence_hash,
                    actor
                ) VALUES (
                    :tenant_id,
                    :created_at,
                    :updated_at,
                    :occurred_at,
                    :audit_event_type,
                    :correlation_id,
                    :idempotency_key,
                    CAST(:selector AS JSONB),
                    :selector_hash,
                    CAST(:effects AS JSONB),
                    :evidence_hash,
                    :actor
                )
                ON CONFLICT ON CONSTRAINT uq_compliance_audit_ledger_tenant_idempotency_key
                DO NOTHING
                RETURNING effects
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "created_at": occurred_at,
                "updated_at": occurred_at,
                "occurred_at": occurred_at,
                "audit_event_type": audit_event_type,
                "correlation_id": str(correlation_id) if correlation_id else None,
                "idempotency_key": scoped_idempotency_key,
                "selector": json.dumps(selector, sort_keys=True, default=str),
                "selector_hash": selector_hash,
                "effects": json.dumps(effects, sort_keys=True, default=str),
                "evidence_hash": effects_hash,
                "actor": str(actor),
            },
        )
        inserted_row = inserted.mappings().first()
        if inserted_row is not None:
            return ReviewMutationLedgerResult(
                replayed=False,
                stored_effects=dict(inserted_row["effects"] or {}),
            )

        existing = await conn.execute(
            text(
                """
                SELECT selector_hash, effects
                FROM compliance_audit_ledger
                WHERE tenant_id = :tenant_id
                  AND idempotency_key = :idempotency_key
                """
            ),
            {"tenant_id": str(tenant_id), "idempotency_key": scoped_idempotency_key},
        )
        existing_row = existing.mappings().first()
        if existing_row is None:
            raise RuntimeError(
                "idempotency ledger conflict without existing row in compliance_audit_ledger"
            )
        if str(existing_row["selector_hash"]) != selector_hash:
            raise IdempotencyConflictError(
                "idempotency key was reused with a different authority-boundary payload"
            )
        return ReviewMutationLedgerResult(
            replayed=True,
            stored_effects=dict(existing_row["effects"] or {}),
        )
