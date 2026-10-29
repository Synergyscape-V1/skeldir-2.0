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
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

SOURCE_EVIDENCE_VERSION = "b26-p2-source-evidence-v1"


class SourceEvidenceError(RuntimeError):
    """The complete lifecycle manifest cannot be established."""

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


def _statement_matches_source(
    statement: Mapping[str, Any], ingress: Mapping[str, Any]
) -> bool:
    expected = {
        "tenant_id": ingress["tenant_id"],
        "webhook_ingress_identity_id": ingress["id"],
        "provider": ingress["provider"],
        "provider_native_event_reference": ingress[
            "provider_native_event_reference"
        ],
        "provider_native_commerce_reference": ingress[
            "provider_native_commerce_reference"
        ],
        "normalized_commerce_reference_kind": ingress[
            "normalized_commerce_reference_kind"
        ],
        "normalized_commerce_reference_value": ingress[
            "normalized_commerce_reference_value"
        ],
        "verified_amount_minor": ingress["verified_amount_minor"],
        "verified_amount_currency": str(
            ingress["verified_amount_currency"]
        ).upper(),
        "verified_amount_scale": ingress["verified_amount_scale"],
    }
    for key, value in expected.items():
        actual = statement.get(key)
        if key == "verified_amount_currency":
            actual = str(actual or "").upper()
        if str(actual) != str(value):
            return False
    return True


def _statement_matches_adjustment(
    statement: Mapping[str, Any], evidence: Mapping[str, Any]
) -> bool:
    expected = {
        "tenant_id": evidence["tenant_id"],
        "adjustment_evidence_id": evidence["id"],
        "verdict_id": evidence["verdict_id"],
        "provider": evidence["provider"],
        "event_type": evidence["event_type"],
        "provider_native_event_reference": evidence[
            "provider_native_event_reference"
        ],
        "provider_native_commerce_reference": evidence[
            "provider_native_commerce_reference"
        ],
        "verified_amount_minor": evidence["amount_minor"],
        "verified_amount_currency": str(evidence["currency_code"]).upper(),
    }
    for key, value in expected.items():
        actual = statement.get(key)
        if key == "verified_amount_currency":
            actual = str(actual or "").upper()
        if str(actual) != str(value):
            return False
    return True


async def source_evidence_snapshot(
    session: AsyncSession, *, tenant_id: UUID | str
) -> dict[str, Any]:
    """Return the tenant's root-attested lifecycle manifest.

    Facts are immutable rows (ingress, source attestations, adjustments,
    adjustment attestations and revenue events). The verdict state is a
    separate mutable commitment. The observer requires every previously
    witnessed fact to remain present, and every state change to be
    accompanied by a new fact in the same tenant.
    """

    from app.core.config import settings  # noqa: PLC0415
    from app.revenue_verification.source_attestation import (  # noqa: PLC0415
        SourceAttestationError,
        verify_adjustment_signature,
        verify_signature,
    )

    tenant = str(tenant_id)
    await session.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant, false)"),
        {"tenant": tenant},
    )
    raw: dict[str, list[dict[str, Any]]] = {}
    for label, table, columns in _TABLES:
        raw[label] = await _read_table(session, table, columns, tenant)

    key_path = settings.B26_P2_SOURCE_ATTESTATION_PUBLIC_KEY_PATH
    if not key_path:
        raise SourceEvidenceError("source_evidence_public_key_missing")

    ingress_by_id = {str(row["id"]): row for row in raw["ingress"]}
    valid_sources: dict[str, dict[str, Any]] = {}
    for row in raw["source_attestation"]:
        ingress = ingress_by_id.get(str(row["webhook_ingress_identity_id"]))
        if ingress is None or not _statement_matches_source(
            row["statement"], ingress
        ):
            continue
        try:
            verify_signature(
                row["statement"],
                row["signature"],
                public_key_path=key_path,
            )
        except SourceAttestationError:
            continue
        valid_sources[str(row["webhook_ingress_identity_id"])] = row

    evidence_by_id = {
        str(row["id"]): row for row in raw["adjustment_evidence"]
    }
    valid_adjustments: dict[str, dict[str, Any]] = {}
    for row in raw["adjustment_attestation"]:
        evidence = evidence_by_id.get(str(row["adjustment_evidence_id"]))
        if evidence is None or not _statement_matches_adjustment(
            row["statement"], evidence
        ):
            continue
        try:
            verify_adjustment_signature(
                row["statement"],
                row["signature"],
                public_key_path=key_path,
            )
        except SourceAttestationError:
            continue
        valid_adjustments[str(row["adjustment_evidence_id"])] = row

    attested_ingress = set(valid_sources)
    attested_verdicts: dict[str, dict[str, Any]] = {}
    for row in raw["verdicts"]:
        ingress_id = row.get("webhook_ingress_identity_id")
        if ingress_id is not None and str(ingress_id) in attested_ingress:
            attested_verdicts[str(row["id"])] = row

    adjustments = [
        row
        for row in raw["adjustment_evidence"]
        if str(row["id"]) in valid_adjustments
        and str(row["verdict_id"]) in attested_verdicts
    ]
    adjustment_ids = {str(row["id"]) for row in adjustments}
    facts: dict[str, list[dict[str, Any]]] = {
        "ingress": [
            row for row in raw["ingress"] if str(row["id"]) in attested_ingress
        ],
        "source_attestation": [
            row for row in raw["source_attestation"]
            if str(row["webhook_ingress_identity_id"]) in attested_ingress
        ],
        "adjustment_evidence": adjustments,
        "adjustment_attestation": [
            row for row in raw["adjustment_attestation"]
            if str(row["adjustment_evidence_id"]) in adjustment_ids
        ],
        "revenue_events": [
            row
            for row in raw["revenue_events"]
            if str(row["match_verdict_id"]) in attested_verdicts
        ],
    }
    from app.revenue_verification.source_evidence_journal import (
        SourceFactJournalError,
        resolve_source_facts,
    )

    try:
        journal = await resolve_source_facts(
            session, public_key_path=key_path
        )
    except SourceFactJournalError as exc:
        raise SourceEvidenceError(str(exc)) from exc
    if journal is None:
        if valid_sources or valid_adjustments:
            raise SourceEvidenceError("source_fact_journal_missing")
    else:
        source_attestation_by_id = {
            str(row["webhook_ingress_identity_id"]): row
            for row in raw["source_attestation"]
        }
        adjustment_attestation_by_id = {
            str(row["adjustment_evidence_id"]): row
            for row in raw["adjustment_attestation"]
        }
        for key, record in {
            **journal.committed,
            **journal.legacy,
        }.items():
            kind, fact_id = key
            if str(record.get("tenant_id")) != tenant:
                continue
            if kind == "source_money":
                ingress = ingress_by_id.get(fact_id)
                attestation = source_attestation_by_id.get(fact_id)
                if ingress is None or attestation is None:
                    raise SourceEvidenceError(
                        f"source_fact_journal_source_absent:{fact_id}"
                    )
                if (
                    fact_id not in valid_sources
                    or record.get("statement") != dict(attestation["statement"])
                    or record.get("signature") != attestation["signature"]
                ):
                    raise SourceEvidenceError(
                        f"source_fact_journal_source_unverified:{fact_id}"
                    )
            elif kind == "adjustment":
                evidence = evidence_by_id.get(fact_id)
                attestation = adjustment_attestation_by_id.get(fact_id)
                if evidence is None or attestation is None:
                    raise SourceEvidenceError(
                        f"source_fact_journal_adjustment_absent:{fact_id}"
                    )
                if (
                    fact_id not in valid_adjustments
                    or record.get("statement") != dict(attestation["statement"])
                    or record.get("signature") != attestation["signature"]
                ):
                    raise SourceEvidenceError(
                        f"source_fact_journal_adjustment_unverified:{fact_id}"
                    )
        for ingress_id in valid_sources:
            key = ("source_money", ingress_id)
            if key in journal.committed or key in journal.legacy:
                continue
            if key in journal.aborted:
                raise SourceEvidenceError(
                    f"source_fact_journal_source_not_committed:{ingress_id}"
                )
            if key in journal.in_progress:
                raise SourceEvidenceError(
                    f"source_fact_journal_source_in_progress:{ingress_id}"
                )
            if key in journal.unknown:
                raise SourceEvidenceError(
                    f"source_fact_journal_source_transaction_unknown:{ingress_id}"
                )
            raise SourceEvidenceError(
                f"source_fact_journal_source_missing:{ingress_id}"
            )
        for evidence_id in valid_adjustments:
            key = ("adjustment", evidence_id)
            if key in journal.committed or key in journal.legacy:
                continue
            if key in journal.aborted:
                raise SourceEvidenceError(
                    f"source_fact_journal_adjustment_not_committed:{evidence_id}"
                )
            if key in journal.in_progress:
                raise SourceEvidenceError(
                    f"source_fact_journal_adjustment_in_progress:{evidence_id}"
                )
            if key in journal.unknown:
                raise SourceEvidenceError(
                    "source_fact_journal_adjustment_transaction_unknown:"
                    f"{evidence_id}"
                )
            raise SourceEvidenceError(
                f"source_fact_journal_adjustment_missing:{evidence_id}"
            )

    current_sources: dict[str, dict[str, Any]] = {}
    sources_by_commerce: dict[str, list[dict[str, Any]]] = {}
    for row in valid_sources.values():
        statement = (
            row["statement"]
            if isinstance(row["statement"], dict)
            else json.loads(str(row["statement"]))
        )
        try:
            event_instant = datetime.fromisoformat(
                str(statement["event_timestamp"]).replace("Z", "+00:00")
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise SourceEvidenceError(
                "source_fact_event_timestamp_invalid"
            ) from exc
        if event_instant.tzinfo is None:
            raise SourceEvidenceError("source_fact_event_timestamp_timezone_required")
        key = (
            str(statement.get("provider") or "").lower()
            + "\x1f"
            + str(statement.get("provider_native_commerce_reference") or "")
        )
        sources_by_commerce.setdefault(key, []).append(
            {
                "ingress_id": str(row["webhook_ingress_identity_id"]),
                "amount_minor": int(statement["verified_amount_minor"]),
                "event_timestamp": event_instant.astimezone(timezone.utc),
            }
        )
    for key, candidates in sources_by_commerce.items():
        latest_instant = max(item["event_timestamp"] for item in candidates)
        latest = [
            item for item in candidates if item["event_timestamp"] == latest_instant
        ]
        if len({item["ingress_id"] for item in latest}) != 1:
            current_sources[key] = {
                "status": "ambiguous",
                "event_timestamp": latest_instant.isoformat(),
            }
            continue
        current_sources[key] = {
            "status": "current",
            "ingress_id": latest[0]["ingress_id"],
            "amount_minor": latest[0]["amount_minor"],
            "event_timestamp": latest_instant.isoformat(),
        }

    for verdict in attested_verdicts.values():
        current_key = (
            str(verdict.get("provider") or "").lower()
            + "\x1f"
            + str(verdict.get("provider_native_commerce_reference") or "")
        )
        current_source = current_sources.get(current_key)
        if current_source is None:
            raise SourceEvidenceError(
                f"verdict_source_currentness_unresolved:{verdict['id']}"
            )
        if current_source.get("status") != "current":
            raise SourceEvidenceError(
                f"verdict_source_currentness_ambiguous:{verdict['id']}"
            )
        if str(current_source.get("ingress_id")) != str(
            verdict["webhook_ingress_identity_id"]
        ):
            raise SourceEvidenceError(
                f"verdict_source_not_current:{verdict['id']}"
            )

    fact_hashes = sorted(
        hashlib.sha256(
            _canonical({"kind": kind, "row": row}).encode("utf-8")
        ).hexdigest()
        for kind, rows in facts.items()
        for row in rows
    )
    state_hashes = sorted(
        hashlib.sha256(
            _canonical(
                {
                    "kind": "verdict_state",
                    "row": {
                        "id": row["id"],
                        "webhook_ingress_identity_id": row[
                            "webhook_ingress_identity_id"
                        ],
                        "canonical_net_verified_amount_minor": row[
                            "canonical_net_verified_amount_minor"
                        ],
                        "canonical_captured_gross_amount_minor": row[
                            "canonical_captured_gross_amount_minor"
                        ],
                        "currency_code": row["currency_code"],
                        "b26_p2_source_authority_state": row[
                            "b26_p2_source_authority_state"
                        ],
                    },
                }
            ).encode("utf-8")
        ).hexdigest()
        for row in attested_verdicts.values()
    )
    payload = {
        "version": SOURCE_EVIDENCE_VERSION,
        "tenant_id": tenant,
        "facts": fact_hashes,
        "states": state_hashes,
    }
    digest = hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()
    return {
        "digest": digest,
        "count": len(fact_hashes),
        "facts": fact_hashes,
        "states": state_hashes,
        "current_sources": current_sources,
    }


async def source_evidence_snapshots_with_failures(
    session: AsyncSession,
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    """Return healthy manifests and contain tenant-local completeness failures.

    A committed fact missing in one tenant is a failure of that tenant, not a
    reason to stop witnessing every other tenant. The failure is returned to
    the observer so it is recorded, never silently converted into an empty
    tenant manifest.
    """

    result = await session.execute(text("SELECT id::text FROM public.tenants"))
    tenants = [str(row[0]) for row in result.all()]
    snapshots: dict[str, dict[str, Any]] = {}
    failures: dict[str, str] = {}
    for tenant in sorted(tenants):
        try:
            snapshot = await source_evidence_snapshot(
                session, tenant_id=tenant
            )
        except SourceEvidenceError as exc:
            failures[tenant] = str(exc)
            continue
        if int(snapshot["count"]) > 0:
            snapshots[tenant] = snapshot
    return snapshots, failures


async def source_evidence_snapshots(
    session: AsyncSession,
) -> dict[str, dict[str, Any]]:
    """Return one manifest per tenant, refusing if any tenant is incomplete."""

    snapshots, failures = await source_evidence_snapshots_with_failures(session)
    if failures:
        detail = ",".join(
            f"{tenant}:{reason}" for tenant, reason in sorted(failures.items())
        )
        raise SourceEvidenceError(f"source_evidence_tenant_failures:{detail}")
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


async def source_fact_currentness(
    session: AsyncSession, *, tenant_id: UUID | str
) -> dict[str, Any]:
    """Require the tenant's complete journal fact set to be present now.

    Called by the authoritative readers, not only by the periodic observer.
    A committed source or adjustment fact whose row disappeared is a refusal
    even when every surviving signature is individually valid.
    """

    return await source_evidence_snapshot(session, tenant_id=tenant_id)


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
