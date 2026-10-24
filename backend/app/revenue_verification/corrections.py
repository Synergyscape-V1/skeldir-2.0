"""Shipping B2.3 post-capture correction conduction.

XXIV (A2/B10): the correction kernel existed but no shipping surface
called it. A correction request names authenticated provider evidence;
the evidence row supplies the amount, currency, commerce reference and
event instant. The API validates the request for a governed response,
then the B2.3 worker re-resolves the same evidence inside its own
transaction before writing, so a caller cannot manufacture money.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .match_engine_kernel import (
    B23PostCaptureInput,
    register_b23_post_capture_event,
)


class CorrectionEvidenceError(ValueError):
    """Governed refusal while resolving correction source authority."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class CorrectionEvidence:
    provider: str
    event_type: str
    provider_native_event_reference: str
    provider_native_commerce_reference: str
    amount_minor: int
    currency_code: str
    event_occurred_at: datetime
    is_gross_capture_correction: bool


async def resolve_correction_evidence(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    verdict_id: UUID,
    provider: str,
    event_type: str,
    provider_native_event_reference: str,
    is_gross_capture_correction: bool,
) -> CorrectionEvidence:
    verdict = (
        await session.execute(
            text(
                """
                SELECT provider, provider_native_commerce_reference,
                       canonical_commerce_reference
                  FROM b23_match_verdicts
                 WHERE tenant_id = :tenant_id AND id = :verdict_id
                """
            ),
            {"tenant_id": str(tenant_id), "verdict_id": str(verdict_id)},
        )
    ).mappings().first()
    if verdict is None:
        raise CorrectionEvidenceError("correction_verdict_missing")
    if str(verdict["provider"]) != provider:
        raise CorrectionEvidenceError("correction_provider_mismatch")
    if event_type == "payment_capture" and not is_gross_capture_correction:
        raise CorrectionEvidenceError("payment_capture_requires_gross_correction")
    if event_type != "payment_capture" and is_gross_capture_correction:
        raise CorrectionEvidenceError("only_payment_capture_may_correct_gross")

    ingress = (
        await session.execute(
            text(
                """
                SELECT provider_native_commerce_reference,
                       verified_amount_minor, verified_amount_currency,
                       event_timestamp
                  FROM webhook_ingress_identities
                 WHERE tenant_id = :tenant_id
                   AND provider = :provider
                   AND provider_native_event_reference = :event_reference
                   AND public.b26_p2_ingress_has_current_authority(id)
                 ORDER BY verified_at DESC NULLS LAST
                 LIMIT 1
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "provider": provider,
                "event_reference": provider_native_event_reference,
            },
        )
    ).mappings().first()
    if ingress is None:
        raise CorrectionEvidenceError("correction_source_authority_unresolved")
    commerce_reference = str(
        ingress["provider_native_commerce_reference"] or ""
    )
    if commerce_reference not in {
        str(verdict["provider_native_commerce_reference"] or ""),
        str(verdict["canonical_commerce_reference"] or ""),
    }:
        raise CorrectionEvidenceError("correction_source_verdict_mismatch")
    return CorrectionEvidence(
        provider=provider,
        event_type=event_type,
        provider_native_event_reference=provider_native_event_reference,
        provider_native_commerce_reference=commerce_reference,
        amount_minor=int(ingress["verified_amount_minor"]),
        currency_code=str(ingress["verified_amount_currency"]),
        event_occurred_at=ingress["event_timestamp"],
        is_gross_capture_correction=is_gross_capture_correction,
    )


async def conduct_correction(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    verdict_id: UUID,
    evidence: CorrectionEvidence,
) -> tuple[bool, int]:
    applied = await register_b23_post_capture_event(
        session,
        B23PostCaptureInput(
            tenant_id=tenant_id,
            provider=evidence.provider,  # type: ignore[arg-type]
            event_type=evidence.event_type,  # type: ignore[arg-type]
            provider_native_event_reference=(
                evidence.provider_native_event_reference
            ),
            provider_native_commerce_reference=(
                evidence.provider_native_commerce_reference
            ),
            currency_code=evidence.currency_code,
            amount_minor=evidence.amount_minor,
            event_occurred_at=evidence.event_occurred_at,
            match_verdict_id=verdict_id,
            is_gross_capture_correction=(
                evidence.is_gross_capture_correction
            ),
        ),
    )
    net_verified_amount = int(
        (
            await session.execute(
                text(
                    """
                    SELECT canonical_net_verified_amount_minor
                      FROM b23_match_verdicts
                     WHERE tenant_id = :tenant_id AND id = :verdict_id
                    """
                ),
                {"tenant_id": str(tenant_id), "verdict_id": str(verdict_id)},
            )
        ).scalar_one()
    )
    return applied, net_verified_amount
