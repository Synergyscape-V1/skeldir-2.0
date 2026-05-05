from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response, Security
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.deps import get_db_session
from app.schemas.revenue_verification import (
    B23DiscrepancyContext,
    B23ExceptionListResponse,
    B23ExceptionRecordResponse,
    B23MatchVerdictDetailResponse,
)
from app.security.auth import AuthContext, get_auth_context


router = APIRouter()


def _match_detail_from_row(row) -> B23MatchVerdictDetailResponse:
    return B23MatchVerdictDetailResponse(
        id=row["id"],
        tenant_id=row["tenant_id"],
        attribution_event_id=row["attribution_event_id"],
        webhook_ingress_identity_id=row["webhook_ingress_identity_id"],
        provider=row["provider"],
        canonical_commerce_reference=row["canonical_commerce_reference"],
        provider_native_event_reference=row["provider_native_event_reference"],
        provider_native_commerce_reference=row["provider_native_commerce_reference"],
        status=row["status"],
        match_quality=row["match_quality"],
        canonical_gross_expected_amount_minor=row[
            "canonical_expected_gross_amount_minor"
        ],
        canonical_gross_captured_amount_minor=row[
            "canonical_captured_gross_amount_minor"
        ],
        canonical_net_verified_amount_minor=row[
            "canonical_net_verified_amount_minor"
        ],
        discrepancy=B23DiscrepancyContext(
            discrepancy_amount_minor=row["discrepancy_amount_minor"],
            discrepancy_ratio_bps=row["discrepancy_ratio_bps"],
            discrepancy_band=row["discrepancy_band"],
            discrepancy_basis="gross_expected_vs_gross_captured",
        ),
        adjustments_applied=bool(row["adjustments_applied"]),
        pending_since=row["pending_since"],
        provisional_expires_at=row["provisional_expires_at"],
        confirmed_at=row["confirmed_at"],
        adjusted_at=row["adjusted_at"],
        unmatched_marked_at=row["unmatched_marked_at"],
        last_transition_at=row["last_transition_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _exception_from_row(row) -> B23ExceptionRecordResponse:
    return B23ExceptionRecordResponse(
        id=row["id"],
        tenant_id=row["tenant_id"],
        match_verdict_id=row["match_verdict_id"],
        provider=row["provider"],
        canonical_commerce_reference=row["canonical_commerce_reference"],
        severity=row["severity"],
        workflow_state=row["status"],
        resolution_code=row["resolution_code"],
        discrepancy_reason=row["resolution_notes"] or row["discrepancy_band"],
        discrepancy_context=B23DiscrepancyContext(
            discrepancy_amount_minor=row["discrepancy_amount_minor"],
            discrepancy_ratio_bps=row["discrepancy_ratio_bps"],
            discrepancy_band=row["discrepancy_band"],
            discrepancy_basis="gross_expected_vs_gross_captured",
        ),
        raised_at=row["raised_at"],
        resolved_at=row["resolved_at"],
        dismissed_at=row["dismissed_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.get(
    "/match-verdicts/{verdict_id}",
    operation_id="getB23MatchVerdict",
    response_model=B23MatchVerdictDetailResponse,
)
async def get_b23_match_verdict(
    verdict_id: UUID,
    response: Response,
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    auth_context: Annotated[AuthContext, Security(get_auth_context, scopes=["viewer"])],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> B23MatchVerdictDetailResponse:
    response.headers["X-Correlation-ID"] = str(x_correlation_id)
    row = (
        await db_session.execute(
            text(
                """
                SELECT
                    v.*,
                    EXISTS (
                        SELECT 1
                        FROM b23_revenue_events e
                        WHERE e.tenant_id = v.tenant_id
                          AND e.match_verdict_id = v.id
                          AND (
                              e.event_type <> 'payment_capture'
                              OR e.is_gross_capture_correction = true
                          )
                    ) AS adjustments_applied
                FROM b23_match_verdicts v
                WHERE v.tenant_id = :tenant_id
                  AND v.id = :verdict_id
                """
            ),
            {
                "tenant_id": str(auth_context.tenant_id),
                "verdict_id": str(verdict_id),
            },
        )
    ).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="B2.3 match verdict not found.")
    return _match_detail_from_row(row)


@router.get(
    "/exceptions",
    operation_id="listB23ExceptionRecords",
    response_model=B23ExceptionListResponse,
)
async def list_b23_exception_records(
    response: Response,
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    auth_context: Annotated[AuthContext, Security(get_auth_context, scopes=["viewer"])],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> B23ExceptionListResponse:
    response.headers["X-Correlation-ID"] = str(x_correlation_id)
    rows = (
        await db_session.execute(
            text(
                """
                SELECT
                    e.id,
                    e.tenant_id,
                    e.match_verdict_id,
                    e.provider,
                    e.canonical_commerce_reference,
                    e.status,
                    e.severity,
                    e.resolution_code,
                    e.resolution_notes,
                    e.raised_at,
                    e.resolved_at,
                    e.dismissed_at,
                    e.created_at,
                    e.updated_at,
                    v.discrepancy_amount_minor,
                    v.discrepancy_ratio_bps,
                    v.discrepancy_band
                FROM b23_exception_records e
                JOIN b23_match_verdicts v
                  ON v.tenant_id = e.tenant_id
                 AND v.id = e.match_verdict_id
                WHERE e.tenant_id = :tenant_id
                ORDER BY e.raised_at DESC, e.id DESC
                LIMIT 100
                """
            ),
            {"tenant_id": str(auth_context.tenant_id)},
        )
    ).mappings().all()
    return B23ExceptionListResponse(
        exceptions=[_exception_from_row(row) for row in rows]
    )


@router.get(
    "/exceptions/{exception_id}",
    operation_id="getB23ExceptionRecord",
    response_model=B23ExceptionRecordResponse,
)
async def get_b23_exception_record(
    exception_id: UUID,
    response: Response,
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    auth_context: Annotated[AuthContext, Security(get_auth_context, scopes=["viewer"])],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> B23ExceptionRecordResponse:
    response.headers["X-Correlation-ID"] = str(x_correlation_id)
    row = (
        await db_session.execute(
            text(
                """
                SELECT
                    e.id,
                    e.tenant_id,
                    e.match_verdict_id,
                    e.provider,
                    e.canonical_commerce_reference,
                    e.status,
                    e.severity,
                    e.resolution_code,
                    e.resolution_notes,
                    e.raised_at,
                    e.resolved_at,
                    e.dismissed_at,
                    e.created_at,
                    e.updated_at,
                    v.discrepancy_amount_minor,
                    v.discrepancy_ratio_bps,
                    v.discrepancy_band
                FROM b23_exception_records e
                JOIN b23_match_verdicts v
                  ON v.tenant_id = e.tenant_id
                 AND v.id = e.match_verdict_id
                WHERE e.tenant_id = :tenant_id
                  AND e.id = :exception_id
                """
            ),
            {
                "tenant_id": str(auth_context.tenant_id),
                "exception_id": str(exception_id),
            },
        )
    ).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="B2.3 exception not found.")
    return _exception_from_row(row)
