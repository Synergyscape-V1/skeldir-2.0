from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import text

from app.db.session import engine, get_session
from app.revenue_verification import (
    B23CaptureMatchInput,
    B23PostCaptureInput,
    B23_P3_TRANSITION_SWEEP_CADENCE,
    PROVISIONAL_MATCH_WINDOW,
    WEBHOOK_ARRIVAL_WINDOW,
    process_b23_capture_match,
    register_b23_post_capture_event,
    seed_pending_match_verdict,
)
from app.revenue_verification.extraction_registry import PersistedIngressExtractionInput
from app.revenue_verification.state_transitions import (
    transition_stale_pending_to_unmatched,
    transition_stale_provisional_to_confirmed,
)
from app.schemas.revenue_verification import B23MatchVerdictDetailResponse
from app.tasks.beat_schedule import build_beat_schedule


REQUIRED_B23_P3_TABLES = (
    "b23_match_verdicts",
    "b23_exception_records",
    "b23_revenue_events",
    "b23_webhook_ingestion_logs",
)


def _require_authoritative_db_proofs() -> bool:
    return os.getenv("SKELDIR_B23_P3_REQUIRE_DB_PROOFS", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _db_skip_or_fail(message: str) -> None:
    if _require_authoritative_db_proofs():
        pytest.fail(message)
    pytest.skip(message)


async def _assert_table_exists(table_name: str) -> None:
    try:
        async with engine.connect() as conn:
            regclass = (
                await conn.execute(
                    text("SELECT to_regclass(:qualified_name)"),
                    {"qualified_name": f"public.{table_name}"},
                )
            ).scalar_one_or_none()
    except Exception as exc:  # pragma: no cover
        _db_skip_or_fail(f"B2.3-P3 runtime proof DB is unreachable: {exc}")
    if regclass is None:
        _db_skip_or_fail(f"B2.3-P3 runtime proof table is missing: {table_name}")


async def _assert_required_tables() -> None:
    for table_name in REQUIRED_B23_P3_TABLES:
        await _assert_table_exists(table_name)


async def _create_match(
    *,
    tenant_id: UUID,
    expected_minor: int,
    captured_minor: int,
    occurred_at: datetime | None = None,
):
    now = occurred_at or datetime.now(timezone.utc)
    event_ref = f"evt-{uuid4()}"
    commerce_ref = f"order-{uuid4()}"
    async with get_session(tenant_id) as session:
        outcome = await process_b23_capture_match(
            session,
            B23CaptureMatchInput(
                tenant_id=tenant_id,
                provider="stripe",
                provider_native_event_reference=event_ref,
                provider_native_commerce_reference=commerce_ref,
                normalized_commerce_reference=commerce_ref,
                strict_order_id=commerce_ref,
                attributed_amount_minor=expected_minor,
                attributed_currency_code="USD",
                verified_revenue_input=PersistedIngressExtractionInput(
                    provider="stripe",
                    verified_amount_minor=captured_minor,
                    verified_amount_currency="USD",
                ),
                event_occurred_at=now,
                conversion_occurred_at=now - timedelta(minutes=1),
            ),
        )
    return outcome.match_verdict_id


async def _verdict_row(tenant_id: UUID, verdict_id: UUID):
    async with get_session(tenant_id) as session:
        return (
            await session.execute(
                text(
                    """
                    SELECT *
                    FROM b23_match_verdicts
                    WHERE tenant_id = :tenant_id AND id = :verdict_id
                    """
                ),
                {"tenant_id": str(tenant_id), "verdict_id": str(verdict_id)},
            )
        ).mappings().one()


async def _verdict_row_by_reference(tenant_id: UUID, event_reference: str):
    async with get_session(tenant_id) as session:
        return (
            await session.execute(
                text(
                    """
                    SELECT *
                    FROM b23_match_verdicts
                    WHERE tenant_id = :tenant_id
                      AND provider_native_event_reference = :event_reference
                    """
                ),
                {
                    "tenant_id": str(tenant_id),
                    "event_reference": event_reference,
                },
            )
        ).mappings().one()


async def _open_exception_rows(tenant_id: UUID, verdict_id: UUID):
    async with get_session(tenant_id) as session:
        return (
            await session.execute(
                text(
                    """
                    SELECT *
                    FROM b23_exception_records
                    WHERE tenant_id = :tenant_id
                      AND match_verdict_id = :verdict_id
                      AND status IN ('open', 'acknowledged')
                    ORDER BY raised_at DESC
                    """
                ),
                {"tenant_id": str(tenant_id), "verdict_id": str(verdict_id)},
            )
        ).mappings().all()


def test_b23_p3_transition_jobs_are_registered_in_beat_schedule() -> None:
    schedule = build_beat_schedule()
    assert (
        schedule["b23-p3-pending-to-unmatched-transition"]["task"]
        == "app.tasks.revenue_verification.transition_stale_pending_to_unmatched_all_tenants"
    )
    assert (
        schedule["b23-p3-provisional-to-confirmed-transition"]["task"]
        == "app.tasks.revenue_verification.transition_stale_provisional_to_confirmed_all_tenants"
    )
    assert B23_P3_TRANSITION_SWEEP_CADENCE == timedelta(minutes=5)


def test_b23_p3_strict_response_model_rejects_extra_fields() -> None:
    payload = {
        "id": uuid4(),
        "tenant_id": uuid4(),
        "attribution_event_id": None,
        "webhook_ingress_identity_id": None,
        "provider": "stripe",
        "canonical_commerce_reference": "order-1",
        "provider_native_event_reference": "evt-1",
        "provider_native_commerce_reference": "pi-1",
        "status": "matched_provisional",
        "match_quality": "high",
        "canonical_gross_expected_amount_minor": 1000,
        "canonical_gross_captured_amount_minor": 1000,
        "canonical_net_verified_amount_minor": 1000,
        "discrepancy": {
            "discrepancy_amount_minor": 0,
            "discrepancy_ratio_bps": 0,
            "discrepancy_band": "exact",
            "discrepancy_basis": "gross_expected_vs_gross_captured",
        },
        "adjustments_applied": False,
        "pending_since": datetime.now(timezone.utc),
        "provisional_expires_at": None,
        "confirmed_at": None,
        "adjusted_at": None,
        "unmatched_marked_at": None,
        "last_transition_at": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "extra_field": "forbidden",
    }
    with pytest.raises(ValidationError):
        B23MatchVerdictDetailResponse.model_validate(payload)


@pytest.mark.asyncio
async def test_b23_p3_pending_to_unmatched_transition_uses_arrival_window(
    test_tenant_pair,
) -> None:
    await _assert_table_exists("b23_match_verdicts")
    tenant_a, _ = test_tenant_pair
    now = datetime.now(timezone.utc)
    stale_ref = f"stale-{uuid4()}"
    young_ref = f"young-{uuid4()}"
    async with get_session(tenant_a) as session:
        await seed_pending_match_verdict(
            session,
            tenant_id=tenant_a,
            provider="stripe",
            provider_native_event_reference=stale_ref,
            provider_native_commerce_reference=f"pi-{uuid4()}",
            canonical_commerce_reference=f"pi-{uuid4()}",
            pending_since=now - WEBHOOK_ARRIVAL_WINDOW - timedelta(seconds=1),
        )
        await seed_pending_match_verdict(
            session,
            tenant_id=tenant_a,
            provider="stripe",
            provider_native_event_reference=young_ref,
            provider_native_commerce_reference=f"pi-{uuid4()}",
            canonical_commerce_reference=f"pi-{uuid4()}",
            pending_since=now - timedelta(seconds=60),
        )
        result = await transition_stale_pending_to_unmatched(
            session, tenant_id=tenant_a, now_utc=now
        )
    assert result.transitioned_count >= 1
    async with get_session(tenant_a) as session:
        rows = (
            await session.execute(
                text(
                    """
                    SELECT provider_native_event_reference, status
                    FROM b23_match_verdicts
                    WHERE tenant_id = :tenant_id
                      AND provider_native_event_reference IN (:stale_ref, :young_ref)
                    """
                ),
                {
                    "tenant_id": str(tenant_a),
                    "stale_ref": stale_ref,
                    "young_ref": young_ref,
                },
            )
        ).mappings().all()
    statuses = {row["provider_native_event_reference"]: row["status"] for row in rows}
    assert statuses[stale_ref] == "unmatched"
    assert statuses[young_ref] == "pending"


@pytest.mark.asyncio
async def test_b23_p3_pending_transition_retries_locked_row_on_next_sweep(
    test_tenant_pair,
) -> None:
    await _assert_table_exists("b23_match_verdicts")
    tenant_a, _ = test_tenant_pair
    now = datetime.now(timezone.utc)
    locked_ref = f"locked-{uuid4()}"
    async with get_session(tenant_a) as session:
        await seed_pending_match_verdict(
            session,
            tenant_id=tenant_a,
            provider="stripe",
            provider_native_event_reference=locked_ref,
            provider_native_commerce_reference=f"pi-{uuid4()}",
            canonical_commerce_reference=f"pi-{uuid4()}",
            pending_since=now - WEBHOOK_ARRIVAL_WINDOW - timedelta(days=1),
        )

    async with get_session(tenant_a) as locking_session:
        await locking_session.execute(
            text(
                """
                SELECT id
                FROM b23_match_verdicts
                WHERE tenant_id = :tenant_id
                  AND provider_native_event_reference = :locked_ref
                FOR UPDATE
                """
            ),
            {"tenant_id": str(tenant_a), "locked_ref": locked_ref},
        )
        async with get_session(tenant_a) as sweeping_session:
            skipped = await transition_stale_pending_to_unmatched(
                sweeping_session,
                tenant_id=tenant_a,
                now_utc=now,
                batch_size=1,
            )
        assert skipped.transitioned_count == 0

    async with get_session(tenant_a) as session:
        transitioned = await transition_stale_pending_to_unmatched(
            session,
            tenant_id=tenant_a,
            now_utc=now + B23_P3_TRANSITION_SWEEP_CADENCE,
            batch_size=1,
        )
    assert transitioned.transitioned_count == 1
    assert (await _verdict_row_by_reference(tenant_a, locked_ref))["status"] == "unmatched"


@pytest.mark.asyncio
async def test_b23_p3_transition_jobs_are_tenant_scoped(test_tenant_pair) -> None:
    await _assert_table_exists("b23_match_verdicts")
    tenant_a, tenant_b = test_tenant_pair
    now = datetime.now(timezone.utc)
    tenant_a_ref = f"tenant-a-{uuid4()}"
    tenant_b_ref = f"tenant-b-{uuid4()}"
    async with get_session(tenant_a) as session:
        await seed_pending_match_verdict(
            session,
            tenant_id=tenant_a,
            provider="stripe",
            provider_native_event_reference=tenant_a_ref,
            provider_native_commerce_reference=f"pi-{uuid4()}",
            canonical_commerce_reference=f"pi-{uuid4()}",
            pending_since=now - WEBHOOK_ARRIVAL_WINDOW - timedelta(seconds=1),
        )
    async with get_session(tenant_b) as session:
        await seed_pending_match_verdict(
            session,
            tenant_id=tenant_b,
            provider="stripe",
            provider_native_event_reference=tenant_b_ref,
            provider_native_commerce_reference=f"pi-{uuid4()}",
            canonical_commerce_reference=f"pi-{uuid4()}",
            pending_since=now - WEBHOOK_ARRIVAL_WINDOW - timedelta(seconds=1),
        )

    async with get_session(tenant_a) as session:
        result = await transition_stale_pending_to_unmatched(
            session,
            tenant_id=tenant_a,
            now_utc=now,
        )
    assert result.transitioned_count >= 1
    assert (await _verdict_row_by_reference(tenant_a, tenant_a_ref))["status"] == "unmatched"
    assert (await _verdict_row_by_reference(tenant_b, tenant_b_ref))["status"] == "pending"


@pytest.mark.asyncio
async def test_b23_p3_provisional_to_confirmed_transition_uses_provisional_window(
    test_tenant_pair,
) -> None:
    await _assert_required_tables()
    tenant_a, _ = test_tenant_pair
    now = datetime.now(timezone.utc)
    stale_id = await _create_match(
        tenant_id=tenant_a,
        expected_minor=5000,
        captured_minor=5000,
        occurred_at=now - PROVISIONAL_MATCH_WINDOW - timedelta(minutes=1),
    )
    young_id = await _create_match(
        tenant_id=tenant_a,
        expected_minor=6000,
        captured_minor=6000,
        occurred_at=now,
    )
    async with get_session(tenant_a) as session:
        result = await transition_stale_provisional_to_confirmed(
            session, tenant_id=tenant_a, now_utc=now
        )
    assert result.transitioned_count >= 1
    assert (await _verdict_row(tenant_a, stale_id))["status"] == "matched_confirmed"
    assert (await _verdict_row(tenant_a, young_id))["status"] == "matched_provisional"


@pytest.mark.asyncio
async def test_b23_p3_normal_refunds_update_net_without_exception_lifecycle(
    test_tenant_pair,
) -> None:
    await _assert_required_tables()
    tenant_a, _ = test_tenant_pair
    now = datetime.now(timezone.utc)
    verdict_id = await _create_match(
        tenant_id=tenant_a,
        expected_minor=10000,
        captured_minor=10000,
        occurred_at=now,
    )

    async with get_session(tenant_a) as session:
        await register_b23_post_capture_event(
            session,
            B23PostCaptureInput(
                tenant_id=tenant_a,
                provider="stripe",
                event_type="partial_refund",
                provider_native_event_reference=f"refund-{uuid4()}",
                provider_native_commerce_reference=f"pi-{uuid4()}",
                currency_code="USD",
                amount_minor=2500,
                event_occurred_at=now + timedelta(minutes=1),
                match_verdict_id=verdict_id,
            ),
        )
    partial = await _verdict_row(tenant_a, verdict_id)
    assert partial["status"] == "adjusted"
    assert partial["canonical_net_verified_amount_minor"] == 7500
    assert partial["discrepancy_band"] == "exact"
    assert partial["discrepancy_amount_minor"] == 0
    assert await _open_exception_rows(tenant_a, verdict_id) == []

    async with get_session(tenant_a) as session:
        await register_b23_post_capture_event(
            session,
            B23PostCaptureInput(
                tenant_id=tenant_a,
                provider="stripe",
                event_type="partial_refund",
                provider_native_event_reference=f"refund-{uuid4()}",
                provider_native_commerce_reference=f"pi-{uuid4()}",
                currency_code="USD",
                amount_minor=7500,
                event_occurred_at=now + timedelta(minutes=2),
                match_verdict_id=verdict_id,
            ),
        )
    full = await _verdict_row(tenant_a, verdict_id)
    assert full["canonical_net_verified_amount_minor"] == 0
    assert full["discrepancy_band"] == "exact"
    assert await _open_exception_rows(tenant_a, verdict_id) == []


@pytest.mark.asyncio
async def test_b23_p3_gross_capture_corrections_drive_exception_lifecycle(
    test_tenant_pair,
) -> None:
    await _assert_required_tables()
    tenant_a, _ = test_tenant_pair
    now = datetime.now(timezone.utc)
    verdict_id = await _create_match(
        tenant_id=tenant_a,
        expected_minor=10000,
        captured_minor=10000,
        occurred_at=now,
    )

    async with get_session(tenant_a) as session:
        await register_b23_post_capture_event(
            session,
            B23PostCaptureInput(
                tenant_id=tenant_a,
                provider="stripe",
                event_type="payment_capture",
                provider_native_event_reference=f"gross-flagged-{uuid4()}",
                provider_native_commerce_reference=f"pi-{uuid4()}",
                currency_code="USD",
                amount_minor=9500,
                event_occurred_at=now + timedelta(minutes=1),
                match_verdict_id=verdict_id,
                is_gross_capture_correction=True,
            ),
        )
    flagged = await _open_exception_rows(tenant_a, verdict_id)
    assert len(flagged) == 1
    assert flagged[0]["severity"] == "flagged"

    async with get_session(tenant_a) as session:
        await register_b23_post_capture_event(
            session,
            B23PostCaptureInput(
                tenant_id=tenant_a,
                provider="stripe",
                event_type="payment_capture",
                provider_native_event_reference=f"gross-alert-{uuid4()}",
                provider_native_commerce_reference=f"pi-{uuid4()}",
                currency_code="USD",
                amount_minor=8500,
                event_occurred_at=now + timedelta(minutes=2),
                match_verdict_id=verdict_id,
                is_gross_capture_correction=True,
            ),
        )
    alert = await _open_exception_rows(tenant_a, verdict_id)
    assert len(alert) == 1
    assert alert[0]["severity"] == "alert"

    async with get_session(tenant_a) as session:
        await register_b23_post_capture_event(
            session,
            B23PostCaptureInput(
                tenant_id=tenant_a,
                provider="stripe",
                event_type="payment_capture",
                provider_native_event_reference=f"gross-clean-{uuid4()}",
                provider_native_commerce_reference=f"pi-{uuid4()}",
                currency_code="USD",
                amount_minor=10000,
                event_occurred_at=now + timedelta(minutes=3),
                match_verdict_id=verdict_id,
                is_gross_capture_correction=True,
            ),
        )
    assert await _open_exception_rows(tenant_a, verdict_id) == []
