from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import text

from app.db.session import engine, get_session
from app.revenue_verification.extraction_registry import (
    B23_REVENUE_EXTRACTOR_REGISTRY,
    DecimalMajorRevenueExtractionInput,
    PersistedIngressExtractionInput,
    StripeRevenueExtractionInput,
    SUPPORTED_B23_PROVIDERS,
    extract_revenue_from_typed_input,
)
from app.revenue_verification.match_engine_kernel import (
    B23CaptureMatchInput,
    B23PostCaptureInput,
    B23_POST_CAPTURE_HANDLER_REGISTRY,
    classify_b23_match_quality,
    classify_stale_pending_as_unmatched,
    process_b23_capture_match,
    register_b23_post_capture_event,
    seed_pending_match_verdict,
)
from app.revenue_verification.timing_constants import WEBHOOK_ARRIVAL_WINDOW


def _require_authoritative_db_proofs() -> bool:
    return os.getenv("SKELDIR_B23_P2_REQUIRE_DB_PROOFS", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


async def _assert_table_exists(table_name: str) -> None:
    async with engine.begin() as conn:
        result = await conn.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = :table_name
                )
                """
            ),
            {"table_name": table_name},
        )
    exists = bool(result.scalar())
    if not exists:
        message = f"B2.3-P2 runtime proof table is missing: {table_name}"
        if _require_authoritative_db_proofs():
            pytest.fail(message)
        pytest.skip(message)


def test_b23_p2_registry_extracts_all_platforms_with_typed_inputs() -> None:
    stripe = extract_revenue_from_typed_input(
        StripeRevenueExtractionInput(
            gross_captured_minor=12500,
            net_after_fees_minor=11900,
            currency_code="usd",
        )
    )
    paypal = extract_revenue_from_typed_input(
        DecimalMajorRevenueExtractionInput(
            provider="paypal",
            gross_major="42.15",
            currency_code="USD",
        )
    )
    shopify = extract_revenue_from_typed_input(
        DecimalMajorRevenueExtractionInput(
            provider="shopify",
            gross_major="75.40",
            currency_code="USD",
        )
    )
    woocommerce = extract_revenue_from_typed_input(
        DecimalMajorRevenueExtractionInput(
            provider="woocommerce",
            gross_major="19.99",
            currency_code="USD",
        )
    )
    assert stripe.amount_minor == 12500
    assert stripe.amount_minor != 11900
    assert paypal.amount_minor == 4215
    assert shopify.amount_minor == 7540
    assert woocommerce.amount_minor == 1999


def test_b23_p2_registry_missing_provider_registration_fails() -> None:
    observed = set(B23_REVENUE_EXTRACTOR_REGISTRY.keys())
    assert observed == set(SUPPORTED_B23_PROVIDERS)
    with pytest.raises(KeyError):
        _ = B23_REVENUE_EXTRACTOR_REGISTRY["unsupported"]  # type: ignore[index]


def test_b23_p2_registry_rejects_untyped_and_malformed_inputs() -> None:
    with pytest.raises(Exception):
        extract_revenue_from_typed_input({"provider": "stripe"})  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        extract_revenue_from_typed_input(
            DecimalMajorRevenueExtractionInput(
                provider="paypal",
                gross_major="not-a-number",
                currency_code="USD",
            )
        )


def test_b23_p2_registry_requires_amount_and_currency_fields() -> None:
    with pytest.raises(ValidationError):
        StripeRevenueExtractionInput(gross_captured_minor=None, currency_code="USD")
    with pytest.raises(ValidationError):
        PersistedIngressExtractionInput(
            provider="shopify",
            verified_amount_minor=50,
            verified_amount_currency="",
        )


def test_b23_p2_match_quality_is_deterministic_high_medium_low() -> None:
    high_a = classify_b23_match_quality(
        precedence_source_field="normalized_commerce_reference",
        discrepancy_ratio=Decimal("0.005"),
        conversion_to_event_delta=timedelta(minutes=2),
    )
    high_b = classify_b23_match_quality(
        precedence_source_field="normalized_commerce_reference",
        discrepancy_ratio=Decimal("0.005"),
        conversion_to_event_delta=timedelta(minutes=2),
    )
    medium = classify_b23_match_quality(
        precedence_source_field="provider_native_commerce_reference",
        discrepancy_ratio=Decimal("0.0500"),
        conversion_to_event_delta=timedelta(minutes=20),
    )
    low = classify_b23_match_quality(
        precedence_source_field="strict_order_id",
        discrepancy_ratio=Decimal("0.2500"),
        conversion_to_event_delta=timedelta(hours=2),
    )
    assert high_a == "high"
    assert high_a == high_b
    assert medium == "medium"
    assert low == "low"


def test_b23_p2_cross_platform_unit_mismatch_discrepancy_is_exact() -> None:
    attributed_major = Decimal("123.45")
    provider_minor = 12340
    attributed_minor = int((attributed_major * Decimal("100")).quantize(Decimal("1")))
    discrepancy_minor = abs(provider_minor - attributed_minor)
    discrepancy_ratio = Decimal(discrepancy_minor) / Decimal(
        max(provider_minor, attributed_minor, 1)
    )
    assert attributed_minor == 12345
    assert discrepancy_minor == 5
    assert discrepancy_ratio < Decimal("0.01")


def test_b23_p2_post_capture_handler_coverage_is_complete() -> None:
    expected_events = {
        "partial_refund",
        "full_refund",
        "chargeback_opened",
        "chargeback_won",
        "chargeback_lost",
    }
    for provider in SUPPORTED_B23_PROVIDERS:
        observed = set(B23_POST_CAPTURE_HANDLER_REGISTRY[provider])
        assert observed == expected_events


@pytest.mark.asyncio
async def test_b23_p2_duplicate_same_event_concurrency_writes_one_effect(
    test_tenant_pair,
) -> None:
    await _assert_table_exists("b23_match_verdicts")
    await _assert_table_exists("b23_revenue_events")
    tenant_a, _ = test_tenant_pair
    event_ref = f"evt-{uuid4()}"
    commerce_ref = f"pi-{uuid4()}"
    now = datetime.now(timezone.utc)

    async def _run_once() -> None:
        async with get_session(tenant_a) as session:
            await process_b23_capture_match(
                session,
                B23CaptureMatchInput(
                    tenant_id=tenant_a,
                    provider="stripe",
                    provider_native_event_reference=event_ref,
                    provider_native_commerce_reference=commerce_ref,
                    normalized_commerce_reference=commerce_ref,
                    strict_order_id=commerce_ref,
                    attributed_amount_minor=5000,
                    attributed_currency_code="USD",
                    verified_revenue_input=PersistedIngressExtractionInput(
                        provider="stripe",
                        verified_amount_minor=5000,
                        verified_amount_currency="USD",
                    ),
                    event_occurred_at=now,
                    conversion_occurred_at=now - timedelta(minutes=1),
                ),
            )

    await asyncio.gather(_run_once(), _run_once())

    async with get_session(tenant_a) as session:
        verdict_count = await session.execute(
            text(
                """
                SELECT COUNT(*)
                FROM b23_match_verdicts
                WHERE tenant_id = :tenant_id AND provider_native_event_reference = :event_ref
                """
            ),
            {"tenant_id": str(tenant_a), "event_ref": event_ref},
        )
        revenue_count = await session.execute(
            text(
                """
                SELECT COUNT(*)
                FROM b23_revenue_events
                WHERE tenant_id = :tenant_id AND provider_native_event_reference = :event_ref
                """
            ),
            {"tenant_id": str(tenant_a), "event_ref": event_ref},
        )
    assert int(verdict_count.scalar() or 0) == 1
    assert int(revenue_count.scalar() or 0) == 1


@pytest.mark.asyncio
async def test_b23_p2_distinct_concurrent_events_same_order_persist_once_each(
    test_tenant_pair,
) -> None:
    await _assert_table_exists("b23_match_verdicts")
    await _assert_table_exists("b23_revenue_events")
    tenant_a, _ = test_tenant_pair
    commerce_ref = f"order-{uuid4()}"
    now = datetime.now(timezone.utc)
    event_refs = [f"evt-{uuid4()}", f"evt-{uuid4()}"]

    async def _run_once(event_ref: str) -> None:
        async with get_session(tenant_a) as session:
            await process_b23_capture_match(
                session,
                B23CaptureMatchInput(
                    tenant_id=tenant_a,
                    provider="paypal",
                    provider_native_event_reference=event_ref,
                    provider_native_commerce_reference=commerce_ref,
                    normalized_commerce_reference=commerce_ref,
                    strict_order_id=commerce_ref,
                    attributed_amount_minor=3300,
                    attributed_currency_code="USD",
                    verified_revenue_input=PersistedIngressExtractionInput(
                        provider="paypal",
                        verified_amount_minor=3300,
                        verified_amount_currency="USD",
                    ),
                    event_occurred_at=now,
                    conversion_occurred_at=now - timedelta(minutes=3),
                ),
            )

    await asyncio.gather(_run_once(event_refs[0]), _run_once(event_refs[1]))

    async with get_session(tenant_a) as session:
        verdict_count = await session.execute(
            text(
                """
                SELECT COUNT(*)
                FROM b23_match_verdicts
                WHERE tenant_id = :tenant_id
                  AND provider_native_commerce_reference = :commerce_ref
                  AND (
                      provider_native_event_reference = :ref_a
                      OR provider_native_event_reference = :ref_b
                  )
                """
            ),
            {
                "tenant_id": str(tenant_a),
                "commerce_ref": commerce_ref,
                "ref_a": event_refs[0],
                "ref_b": event_refs[1],
            },
        )
    assert int(verdict_count.scalar() or 0) == 2


@pytest.mark.asyncio
async def test_b23_p2_unmatched_executor_respects_arrival_window(
    test_tenant_pair,
) -> None:
    await _assert_table_exists("b23_match_verdicts")
    tenant_a, _ = test_tenant_pair
    now = datetime.now(timezone.utc)
    young_ref = f"evt-young-{uuid4()}"
    stale_ref = f"evt-stale-{uuid4()}"

    async with get_session(tenant_a) as session:
        await seed_pending_match_verdict(
            session,
            tenant_id=tenant_a,
            provider="shopify",
            provider_native_event_reference=young_ref,
            provider_native_commerce_reference=f"order-{uuid4()}",
            canonical_commerce_reference=f"order-{uuid4()}",
            pending_since=now - timedelta(seconds=60),
        )
        await seed_pending_match_verdict(
            session,
            tenant_id=tenant_a,
            provider="shopify",
            provider_native_event_reference=stale_ref,
            provider_native_commerce_reference=f"order-{uuid4()}",
            canonical_commerce_reference=f"order-{uuid4()}",
            pending_since=now - WEBHOOK_ARRIVAL_WINDOW - timedelta(seconds=1),
        )
        updated = await classify_stale_pending_as_unmatched(
            session,
            tenant_id=tenant_a,
            now_utc=now,
        )
        assert updated >= 1

    async with get_session(tenant_a) as session:
        young_status = await session.execute(
            text(
                """
                SELECT status
                FROM b23_match_verdicts
                WHERE tenant_id = :tenant_id AND provider_native_event_reference = :event_ref
                """
            ),
            {"tenant_id": str(tenant_a), "event_ref": young_ref},
        )
        stale_status = await session.execute(
            text(
                """
                SELECT status
                FROM b23_match_verdicts
                WHERE tenant_id = :tenant_id AND provider_native_event_reference = :event_ref
                """
            ),
            {"tenant_id": str(tenant_a), "event_ref": stale_ref},
        )
    assert str(young_status.scalar_one()) == "pending"
    assert str(stale_status.scalar_one()) == "unmatched"


@pytest.mark.asyncio
async def test_b23_p2_unresolved_post_capture_routes_to_p1_substrates(
    test_tenant_pair,
) -> None:
    await _assert_table_exists("b23_exception_records")
    await _assert_table_exists("b23_webhook_ingestion_logs")
    await _assert_table_exists("b23_revenue_events")
    tenant_a, _ = test_tenant_pair
    event_ref = f"refund-{uuid4()}"
    now = datetime.now(timezone.utc)

    async with get_session(tenant_a) as session:
        inserted = await register_b23_post_capture_event(
            session,
            B23PostCaptureInput(
                tenant_id=tenant_a,
                provider="stripe",
                event_type="partial_refund",
                provider_native_event_reference=event_ref,
                provider_native_commerce_reference=f"pi-{uuid4()}",
                currency_code="USD",
                amount_minor=500,
                event_occurred_at=now,
                failure_reason="missing_resolvable_order_id",
            ),
        )
        assert inserted is False

    async with get_session(tenant_a) as session:
        exception_count = await session.execute(
            text(
                """
                SELECT COUNT(*)
                FROM b23_exception_records
                WHERE tenant_id = :tenant_id
                  AND resolution_notes = 'missing_resolvable_order_id'
                """
            ),
            {"tenant_id": str(tenant_a)},
        )
        log_count = await session.execute(
            text(
                """
                SELECT COUNT(*)
                FROM b23_webhook_ingestion_logs
                WHERE tenant_id = :tenant_id
                  AND provider_native_event_reference = :event_ref
                  AND ingestion_status = 'failed'
                  AND failure_reason = 'missing_resolvable_order_id'
                """
            ),
            {"tenant_id": str(tenant_a), "event_ref": event_ref},
        )
        revenue_count = await session.execute(
            text(
                """
                SELECT COUNT(*)
                FROM b23_revenue_events
                WHERE tenant_id = :tenant_id
                  AND provider_native_event_reference = :event_ref
                """
            ),
            {"tenant_id": str(tenant_a), "event_ref": event_ref},
        )
    assert int(exception_count.scalar() or 0) >= 1
    assert int(log_count.scalar() or 0) == 1
    assert int(revenue_count.scalar() or 0) == 0
