from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.db.session import engine, get_session


def _require_authoritative_db_proofs() -> bool:
    return os.getenv("SKELDIR_B23_P1_REQUIRE_DB_PROOFS", "0").strip().lower() in {
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
        message = f"B2.3-P1 runtime proof table is missing: {table_name}"
        if _require_authoritative_db_proofs():
            pytest.fail(message)
        pytest.skip(message)


@pytest.mark.asyncio
async def test_b23_p1_exception_resolved_requires_resolution_code_db_constraint(test_tenant_pair) -> None:
    await _assert_table_exists("b23_exception_records")
    tenant_a, _ = test_tenant_pair
    match_id = uuid4()

    async with get_session(tenant_a) as session:
        await session.execute(
            text(
                """
                INSERT INTO b23_match_verdicts (
                    id,
                    tenant_id,
                    provider,
                    canonical_commerce_reference,
                    provider_native_event_reference,
                    provider_native_commerce_reference,
                    status,
                    match_quality,
                    attributed_amount_minor,
                    verified_amount_minor,
                    currency_code
                )
                VALUES (
                    :id,
                    :tenant_id,
                    :provider,
                    :canonical_commerce_reference,
                    :provider_native_event_reference,
                    :provider_native_commerce_reference,
                    :status,
                    :match_quality,
                    :attributed_amount_minor,
                    :verified_amount_minor,
                    :currency_code
                )
                """
            ),
            {
                "id": str(match_id),
                "tenant_id": str(tenant_a),
                "provider": "stripe",
                "canonical_commerce_reference": f"order-{uuid4()}",
                "provider_native_event_reference": f"evt-{uuid4()}",
                "provider_native_commerce_reference": f"pi-{uuid4()}",
                "status": "pending",
                "match_quality": "high",
                "attributed_amount_minor": 1200,
                "verified_amount_minor": 1200,
                "currency_code": "USD",
            },
        )
        with pytest.raises(IntegrityError):
            await session.execute(
                text(
                    """
                    INSERT INTO b23_exception_records (
                        tenant_id,
                        match_verdict_id,
                        provider,
                        canonical_commerce_reference,
                        status,
                        severity,
                        resolution_code
                    )
                    VALUES (
                        :tenant_id,
                        :match_verdict_id,
                        :provider,
                        :canonical_commerce_reference,
                        :status,
                        :severity,
                        :resolution_code
                    )
                    """
                ),
                {
                    "tenant_id": str(tenant_a),
                    "match_verdict_id": str(match_id),
                    "provider": "stripe",
                    "canonical_commerce_reference": "order-missing-resolution",
                    "status": "resolved",
                    "severity": "flagged",
                    "resolution_code": None,
                },
            )


@pytest.mark.asyncio
async def test_b23_p1_revenue_event_idempotency_is_db_enforced(test_tenant_pair) -> None:
    await _assert_table_exists("b23_revenue_events")
    tenant_a, _ = test_tenant_pair
    provider_event_reference = f"evt-{uuid4()}"

    async with get_session(tenant_a) as session:
        payload = {
            "tenant_id": str(tenant_a),
            "provider": "paypal",
            "provider_native_event_reference": provider_event_reference,
            "provider_native_commerce_reference": f"txn-{uuid4()}",
            "canonical_commerce_reference": f"order-{uuid4()}",
            "event_type": "payment_capture",
            "amount_minor": 1550,
            "currency_code": "USD",
        }
        await session.execute(
            text(
                """
                INSERT INTO b23_revenue_events (
                    tenant_id,
                    provider,
                    provider_native_event_reference,
                    provider_native_commerce_reference,
                    canonical_commerce_reference,
                    event_type,
                    amount_minor,
                    currency_code,
                    event_occurred_at
                )
                VALUES (
                    :tenant_id,
                    :provider,
                    :provider_native_event_reference,
                    :provider_native_commerce_reference,
                    :canonical_commerce_reference,
                    :event_type,
                    :amount_minor,
                    :currency_code,
                    now()
                )
                """
            ),
            payload,
        )
        with pytest.raises(IntegrityError):
            await session.execute(
                text(
                    """
                    INSERT INTO b23_revenue_events (
                        tenant_id,
                        provider,
                        provider_native_event_reference,
                        provider_native_commerce_reference,
                        canonical_commerce_reference,
                        event_type,
                        amount_minor,
                        currency_code,
                        event_occurred_at
                    )
                    VALUES (
                        :tenant_id,
                        :provider,
                        :provider_native_event_reference,
                        :provider_native_commerce_reference,
                        :canonical_commerce_reference,
                        :event_type,
                        :amount_minor,
                        :currency_code,
                        now()
                    )
                    """
                ),
                payload,
            )


@pytest.mark.asyncio
async def test_b23_p1_tenant_rls_blocks_cross_tenant_visibility_and_missing_context(test_tenant_pair) -> None:
    await _assert_table_exists("b23_webhook_ingestion_logs")
    tenant_a, tenant_b = test_tenant_pair
    event_reference = f"evt-{uuid4()}"

    async with get_session(tenant_a) as session:
        await session.execute(
            text(
                """
                INSERT INTO b23_webhook_ingestion_logs (
                    tenant_id,
                    provider,
                    provider_native_event_reference,
                    ingestion_status,
                    failure_reason
                )
                VALUES (
                    :tenant_id,
                    :provider,
                    :provider_native_event_reference,
                    :ingestion_status,
                    :failure_reason
                )
                """
            ),
            {
                "tenant_id": str(tenant_a),
                "provider": "shopify",
                "provider_native_event_reference": event_reference,
                "ingestion_status": "success",
                "failure_reason": None,
            },
        )

    async with get_session(tenant_b) as session:
        result = await session.execute(
            text(
                """
                SELECT COUNT(*)
                FROM b23_webhook_ingestion_logs
                WHERE provider_native_event_reference = :event_reference
                """
            ),
            {"event_reference": event_reference},
        )
        assert int(result.scalar() or 0) == 0

    async with get_session(tenant_a) as session:
        result = await session.execute(
            text(
                """
                SELECT COUNT(*)
                FROM b23_webhook_ingestion_logs
                WHERE provider_native_event_reference = :event_reference
                """
            ),
            {"event_reference": event_reference},
        )
        assert int(result.scalar() or 0) == 1

    async with engine.begin() as conn:
        result = await conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM b23_webhook_ingestion_logs
                WHERE provider_native_event_reference = :event_reference
                """
            ),
            {"event_reference": event_reference},
        )
        assert int(result.scalar() or 0) == 0

    async with engine.begin() as conn:
        with pytest.raises(DBAPIError):
            # RAW_SQL_ALLOWLIST: explicit missing-GUC write failure proof for B2.3-P1 RLS fail-closed behavior.
            await conn.execute(
                text(
                    """
                    INSERT INTO b23_webhook_ingestion_logs (
                        tenant_id,
                        provider,
                        provider_native_event_reference,
                        ingestion_status
                    )
                    VALUES (:tenant_id, :provider, :provider_native_event_reference, :ingestion_status)
                    """
                ),
                {
                    "tenant_id": str(tenant_b),
                    "provider": "woocommerce",
                    "provider_native_event_reference": f"evt-{uuid4()}",
                    "ingestion_status": "success",
                },
            )

