"""Canonical completeness manifest for one tenant's financial lifecycle.

The per-fact attestations in :mod:`source_attestation` prove that a fact which
is present was signed by the authentication root.  They do not prove that the
set of facts is complete.  This module hashes the complete set of money-bearing
rows for a tenant so the independent history witness can commit to that set.
A deletion, rollback or relink changes the digest even when every remaining row
still has a valid signature.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

SOURCE_EVIDENCE_VERSION = "b26-p2-source-evidence-v1"

_TABLES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "verdicts",
        "public.b23_match_verdicts",
        (
            "id",
            "tenant_id",
            "webhook_ingress_identity_id",
            "provider",
            "canonical_commerce_reference",
            "provider_native_event_reference",
            "provider_native_commerce_reference",
            "attributed_amount_minor",
            "verified_amount_minor",
            "currency_code",
            "canonical_expected_gross_amount_minor",
            "canonical_captured_gross_amount_minor",
            "canonical_net_verified_amount_minor",
            "discrepancy_amount_minor",
            "discrepancy_ratio_bps",
            "discrepancy_band",
            "b26_p2_source_authority_state",
        ),
    ),
    (
        "ingress",
        "public.webhook_ingress_identities",
        (
            "id",
            "tenant_id",
            "provider",
            "provider_native_event_reference",
            "provider_native_commerce_reference",
            "normalized_commerce_reference_kind",
            "normalized_commerce_reference_value",
            "verified_amount_minor",
            "verified_amount_currency",
            "verified_amount_scale",
            "event_timestamp",
            "verified_commerce_ingress_state",
            "b26_p2_provenance_status",
            "b26_p2_semantic_regime",
            "b26_p2_demotion_reason",
        ),
    ),
    (
        "source_attestation",
        "public.b26_p2_source_money_attestation",
        (
            "webhook_ingress_identity_id",
            "tenant_id",
            "statement_version",
            "attested_amount_minor",
            "attested_amount_currency",
            "attested_amount_scale",
            "statement",
            "signature",
            "key_id",
            "key_sha256",
        ),
    ),
    (
        "adjustment_evidence",
        "public.b26_p2_adjustment_evidence",
        (
            "id",
            "tenant_id",
            "verdict_id",
            "provider",
            "provider_native_event_reference",
            "provider_native_commerce_reference",
            "event_type",
            "amount_minor",
            "currency_code",
            "event_timestamp",
            "body_sha256",
        ),
    ),
    (
        "adjustment_attestation",
        "public.b26_p2_adjustment_attestation",
        (
            "adjustment_evidence_id",
            "tenant_id",
            "statement_version",
            "attested_amount_minor",
            "attested_amount_currency",
            "attested_amount_scale",
            "statement",
            "signature",
            "key_id",
            "key_sha256",
        ),
    ),
    (
        "revenue_events",
        "public.b23_revenue_events",
        (
            "id",
            "tenant_id",
            "match_verdict_id",
            "provider",
            "provider_native_event_reference",
            "provider_native_commerce_reference",
            "canonical_commerce_reference",
            "event_type",
            "currency_code",
            "event_occurred_at",
            "captured_amount_minor",
            "refund_amount_minor",
            "chargeback_amount_minor",
            "reversal_amount_minor",
            "net_effect_sign",
            "is_gross_capture_correction",
        ),
    ),
)


def _normal(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _normal(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normal(item) for item in value]
    return value


def _canonical(rows: Mapping[str, Any]) -> str:
    return json.dumps(
        _normal(rows),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


async def _read_table(
    session: AsyncSession, table: str, columns: tuple[str, ...], tenant: str
) -> list[dict[str, Any]]:
    result = await session.execute(
        text(
            "SELECT "
            + ", ".join(columns)
            + f" FROM {table} WHERE tenant_id = :tenant ORDER BY "
            + columns[0]
        ),
        {"tenant": tenant},
    )
    return [dict(row) for row in result.mappings().all()]


async def source_evidence_snapshot(
    session: AsyncSession, *, tenant_id: UUID | str
) -> dict[str, Any]:
    """Return the tenant's root-attested financial manifest and row count.

    Unattested historical/current fixtures are outside the authority this
    manifest governs; readers already refuse them. Facts inside the manifest
    must have a valid authentication-root signature on the capture and on
    every adjustment. A deletion or rollback therefore changes the selected
    set even when the remaining rows are individually valid.
    """

    from app.revenue_verification.source_attestation import (
        read_verdict_source_attestation_status,
    )

    tenant = str(tenant_id)
    await session.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant, false)"),
        {"tenant": tenant},
    )
    raw: dict[str, list[dict[str, Any]]] = {}
    for label, table, columns in _TABLES:
        raw[label] = await _read_table(session, table, columns, tenant)

    attested_verdicts: set[str] = set()
    for row in raw["verdicts"]:
        if str(row.get("b26_p2_source_authority_state") or "") != "current":
            continue
        status = await read_verdict_source_attestation_status(
            session, tenant_id=tenant, verdict_id=row["id"]
        )
        if status.status == "xxv_attested":
            attested_verdicts.add(str(row["id"]))

    verdicts = [
        row for row in raw["verdicts"] if str(row["id"]) in attested_verdicts
    ]
    ingress_ids = {
        str(row["webhook_ingress_identity_id"])
        for row in verdicts
        if row["webhook_ingress_identity_id"] is not None
    }
    adjustments = [
        row
        for row in raw["adjustment_evidence"]
        if str(row["verdict_id"]) in attested_verdicts
    ]
    adjustment_ids = {str(row["id"]) for row in adjustments}
    facts = {
        "verdicts": verdicts,
        "ingress": [
            row for row in raw["ingress"] if str(row["id"]) in ingress_ids
        ],
        "source_attestation": [
            row
            for row in raw["source_attestation"]
            if str(row["webhook_ingress_identity_id"]) in ingress_ids
        ],
        "adjustment_evidence": adjustments,
        "adjustment_attestation": [
            row
            for row in raw["adjustment_attestation"]
            if str(row["adjustment_evidence_id"]) in adjustment_ids
        ],
        "revenue_events": [
            row
            for row in raw["revenue_events"]
            if str(row["match_verdict_id"]) in attested_verdicts
        ],
    }
    count = sum(len(rows) for rows in facts.values())
    payload = {
        "version": SOURCE_EVIDENCE_VERSION,
        "tenant_id": tenant,
        "facts": facts,
    }
    digest = hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()
    return {"digest": digest, "count": count}


async def source_evidence_snapshots(
    session: AsyncSession,
) -> dict[str, dict[str, Any]]:
    """Return one manifest per tenant, for the independent observer."""

    result = await session.execute(text("SELECT id::text FROM public.tenants"))
    tenants = [str(row[0]) for row in result.all()]
    snapshots: dict[str, dict[str, Any]] = {}
    for tenant in sorted(tenants):
        snapshots[tenant] = await source_evidence_snapshot(
            session, tenant_id=tenant
        )
    return snapshots


def global_source_evidence_digest(
    snapshots: Mapping[str, Mapping[str, Any]],
) -> str:
    """Hash the per-tenant map so one checkpoint commits to all of them."""

    material = {
        "version": SOURCE_EVIDENCE_VERSION,
        "tenants": {
            str(tenant): str(snapshot["digest"])
            for tenant, snapshot in sorted(snapshots.items())
        },
    }
    return hashlib.sha256(_canonical(material).encode("utf-8")).hexdigest()


async def source_evidence_is_attested(
    session: AsyncSession, *, tenant_id: UUID | str
) -> tuple[bool, str]:
    """Require valid capture/adjustment signatures on every current verdict."""

    from app.revenue_verification.source_attestation import (
        read_verdict_source_attestation_status,
    )

    tenant = str(tenant_id)
    await session.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant, false)"),
        {"tenant": tenant},
    )
    rows = (
        await session.execute(
            text(
                "SELECT id::text FROM public.b23_match_verdicts"
                " WHERE tenant_id = :tenant"
                "   AND b26_p2_source_authority_state = 'current'"
            ),
            {"tenant": tenant},
        )
    ).all()
    for (verdict_id,) in rows:
        status = await read_verdict_source_attestation_status(
            session, tenant_id=tenant, verdict_id=verdict_id
        )
        if status.status != "xxv_attested":
            return False, f"{verdict_id}:{status.status}"
    return True, ""
