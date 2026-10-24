from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response, Security
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.queues import QUEUE_B23_MATCH_ENGINE
from app.db.deps import get_db_session
from app.finance_reconciliation.scope_authority import (
    DISPOSITION_INVALID_OR_REFUSED,
    ScopeAuthorityError,
    classify_candidate,
)
from app.revenue_verification.corrections import (
    CorrectionEvidenceError,
    resolve_correction_evidence,
)
from app.schemas.revenue_verification import (
    B23DiscrepancyContext,
    B23ExceptionListResponse,
    B23ExceptionRecordResponse,
    B23MatchVerdictDetailResponse,
    B23P2CandidateClassificationRequest,
    B23P2CandidateClassificationResponse,
    B23PostCaptureCorrectionRequest,
    B23PostCaptureCorrectionResponse,
)
from app.security.auth import AuthContext, get_auth_context
from app.trust.source_adapters import resolve_event_family_law_cohort


router = APIRouter()


def _match_detail_from_row(
    row,
    *,
    event_family_law_version: str | None,
    event_family_law_current: bool | None,
) -> B23MatchVerdictDetailResponse:
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
        source_authority_state=str(
            row["b26_p2_source_authority_state"]
            if "b26_p2_source_authority_state" in row.keys()
            else "unknown"
        ),
        pending_since=row["pending_since"],
        provisional_expires_at=row["provisional_expires_at"],
        confirmed_at=row["confirmed_at"],
        adjusted_at=row["adjusted_at"],
        unmatched_marked_at=row["unmatched_marked_at"],
        last_transition_at=row["last_transition_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        event_family_law_version=event_family_law_version,
        event_family_law_current=event_family_law_current,
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
                    i.verified_at AS ingress_verified_at,
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
                LEFT JOIN webhook_ingress_identities i
                  ON i.tenant_id = v.tenant_id
                 AND i.id = v.webhook_ingress_identity_id
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
    # XXI P1: consumer-visible event-family-law qualification. The law
    # cohort resolves through the trust surface's governed resolver
    # (single source of truth) against the tenant-coherent backing
    # ingress mint; only Shopify rows are governed by the
    # creation-window law. A missing mint fails closed (unknown, not
    # current).
    law_version: str | None = None
    law_current: bool | None = None
    if row["provider"] == "shopify":
        resolved_version, law_current = await resolve_event_family_law_cohort(
            db_session, mint_moment=row["ingress_verified_at"]
        )
        law_version = resolved_version or "unknown"
    return _match_detail_from_row(
        row,
        event_family_law_version=law_version,
        event_family_law_current=law_current,
    )


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


@router.post(
    "/candidates/classify",
    operation_id="classifyB23P2Candidate",
    response_model=B23P2CandidateClassificationResponse,
)
async def classify_b23_p2_candidate(
    payload: B23P2CandidateClassificationRequest,
    response: Response,
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    auth_context: Annotated[AuthContext, Security(get_auth_context, scopes=["viewer"])],
) -> B23P2CandidateClassificationResponse:
    """Machine receipt for every canonical P2 disposition.

    XXIV (B3): the fourth canonical class is reachable without inserting
    invalid input into authenticated finance. A malformed candidate is
    returned as a governed ``INVALID_OR_REFUSED`` receipt with its
    refusal reason; valid candidates are classified by the sovereign
    P2 authority.
    """
    response.headers["X-Correlation-ID"] = str(x_correlation_id)
    provider_token = (payload.provider_raw or "").strip().lower()
    currency_token = (payload.currency_raw or "").strip().upper()
    try:
        classification = classify_candidate(
            tenant_id=auth_context.tenant_id,
            provider_raw=payload.provider_raw,
            currency_raw=payload.currency_raw,
            event_time=payload.event_time,
            window_start=payload.window_start,
            window_end=payload.window_end,
            scope_policy_version=payload.scope_policy_version,
            source_reference=payload.source_reference,
        )
    except ScopeAuthorityError as exc:
        return B23P2CandidateClassificationResponse(
            disposition=DISPOSITION_INVALID_OR_REFUSED,
            reason=str(exc),
            provider=provider_token,
            rail=provider_token,
            currency_code=currency_token,
            window_start=payload.window_start,
            window_end=payload.window_end,
            scope_policy_version=payload.scope_policy_version,
            source_verified_gross_amount_minor=(
                payload.source_verified_gross_amount_minor
            ),
        )
    return B23P2CandidateClassificationResponse(
        disposition=classification.disposition,
        reason=classification.reason,
        provider=classification.provider,
        rail=classification.rail,
        currency_code=classification.currency_code,
        window_start=classification.window_start,
        window_end=classification.window_end,
        scope_policy_version=classification.scope_policy_version,
        source_verified_gross_amount_minor=(
            payload.source_verified_gross_amount_minor
        ),
    )


@router.post(
    "/match-verdicts/{verdict_id}/corrections",
    operation_id="createB23PostCaptureCorrection",
    response_model=B23PostCaptureCorrectionResponse,
)
async def create_b23_post_capture_correction(
    verdict_id: UUID,
    payload: B23PostCaptureCorrectionRequest,
    response: Response,
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    auth_context: Annotated[AuthContext, Security(get_auth_context, scopes=["manager"])],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> B23PostCaptureCorrectionResponse:
    """Conduct a provider-authenticated correction through shipping B2.3.

    XXIV (A2/B10): the caller names authenticated provider evidence; the
    amount, currency, commerce reference and event instant are read from
    that ingress row, never from the request. This is the natural
    shipping surface that was missing while only the probe script called
    ``register_b23_post_capture_event``.
    """
    response.headers["X-Correlation-ID"] = str(x_correlation_id)
    try:
        evidence = await resolve_correction_evidence(
            db_session,
            tenant_id=auth_context.tenant_id,
            verdict_id=verdict_id,
            provider=payload.provider,
            event_type=payload.event_type,
            provider_native_event_reference=(
                payload.provider_native_event_reference
            ),
            is_gross_capture_correction=(
                payload.is_gross_capture_correction
            ),
        )
    except CorrectionEvidenceError as exc:
        status_code = (
            404 if exc.reason == "correction_verdict_missing" else 409
        )
        if exc.reason in {
            "correction_provider_mismatch",
            "payment_capture_requires_gross_correction",
            "only_payment_capture_may_correct_gross",
        }:
            status_code = 422
        raise HTTPException(status_code=status_code, detail=exc.reason) from exc
    net_verified_amount = int(
        (
            await db_session.execute(
                text(
                    """
                    SELECT canonical_net_verified_amount_minor
                      FROM b23_match_verdicts
                     WHERE tenant_id = :tenant_id AND id = :verdict_id
                    """
                ),
                {
                    "tenant_id": str(auth_context.tenant_id),
                    "verdict_id": str(verdict_id),
                },
            )
        ).scalar_one()
    )
    from app.tasks.revenue_verification import (  # noqa: PLC0415
        register_b23_post_capture_correction_task,
    )

    try:
        register_b23_post_capture_correction_task.apply_async(
            args=[
                str(auth_context.tenant_id),
                str(verdict_id),
                evidence.provider,
                evidence.event_type,
                evidence.provider_native_event_reference,
                evidence.is_gross_capture_correction,
                str(x_correlation_id),
            ],
            queue=QUEUE_B23_MATCH_ENGINE,
            routing_key=f"{QUEUE_B23_MATCH_ENGINE}.task",
        )
    except Exception as exc:  # broker unavailable: do not claim conduction
        raise HTTPException(
            status_code=503,
            detail="Correction queue is unavailable.",
        ) from exc
    return B23PostCaptureCorrectionResponse(
        status="accepted",
        match_verdict_id=verdict_id,
        revenue_event_written=False,
        net_verified_amount_minor=net_verified_amount,
    )
