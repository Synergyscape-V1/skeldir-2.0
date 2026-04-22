"""B1.4-P4 DB-backed runtime proofs for retention and deterministic deletion semantics."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.api.export import _fetch_reporting_rows
from app.celery_app import celery_app
from app.core.db import engine
from app.db.session import get_session, set_tenant_guc
from app.ingestion.event_service import ingest_with_transaction
from app.main import app
from app.security.auth import AuthContext, get_auth_context
from app.tasks.authority import SystemAuthorityEnvelope
from app.tasks.attribution import recompute_window
from app.tasks.enqueue import enqueue_tenant_task
from app.tasks.maintenance import _delete_expired_raw_event_payload_rows
from app.tasks.privacy import _erase_tenant_privacy_surfaces
from tests.conftest import _insert_tenant


pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


async def _require_b14_p4_schema() -> None:
    async with engine.begin() as conn:
        has_raw_event_payloads = await conn.scalar(
            text("SELECT to_regclass('public.raw_event_payloads')")
        )
        has_session_authority = await conn.scalar(
            text("SELECT to_regclass('public.session_authority')")
        )
        has_compliance_audit_ledger = await conn.scalar(
            text("SELECT to_regclass('public.compliance_audit_ledger')")
        )
    if not has_raw_event_payloads or not has_session_authority or not has_compliance_audit_ledger:
        pytest.skip("B1.4-P4 runtime proofs require alembic head schema with corrected P4 surfaces")


def _auth_context_for_tenant(tenant_id: UUID) -> AuthContext:
    return AuthContext(
        tenant_id=tenant_id,
        user_id=uuid4(),
        jti=uuid4(),
        issued_at_epoch=int(datetime.now(timezone.utc).timestamp()),
        subject="b14-p4-runtime",
        issuer="https://issuer.skeldir.test",
        audience="skeldir-api",
        claims={"scopes": ["viewer"], "tenant_id": str(tenant_id)},
    )


@pytest.mark.asyncio
async def test_b14_p4_runtime_schema_split_writes_raw_payloads_without_mutating_immutable_ledger():
    await _require_b14_p4_schema()
    tenant_id = uuid4()
    now = datetime.now(timezone.utc)
    idempotency_key = f"b14_p4_schema_{uuid4().hex[:10]}"
    session_id = uuid4()

    async with engine.begin() as conn:
        await _insert_tenant(conn, tenant_id, api_key_hash=f"test_hash_{tenant_id}")

    ingest_result = await ingest_with_transaction(
        tenant_id=tenant_id,
        event_data={
            "event_type": "purchase",
            "event_timestamp": _iso(now),
            "revenue_amount": "12.00",
            "currency": "USD",
            "session_id": str(session_id),
            "vendor": "stripe",
            "utm_source": "stripe",
            "utm_medium": "checkout",
            "external_event_id": f"schema-{uuid4().hex[:8]}",
            "campaign_id": "cmp-schema",
            "order_id": f"order-{uuid4().hex[:8]}",
        },
        idempotency_key=idempotency_key,
        source="stripe",
        identity_payload={"session_id": str(session_id)},
        request_headers={"user-agent": "b14-p4-runtime-agent"},
    )
    assert ingest_result.status == "success"

    async with engine.begin() as conn:
        await set_tenant_guc(conn, tenant_id, local=True)
        event_row = (
            await conn.execute(
                text(
                    """
                    SELECT id, raw_payload
                    FROM attribution_events
                    WHERE tenant_id = :tenant_id
                      AND idempotency_key = :idempotency_key
                    """
                ),
                {
                    "tenant_id": str(tenant_id),
                    "idempotency_key": idempotency_key,
                },
            )
        ).mappings().one()
        payload_row = (
            await conn.execute(
                text(
                    """
                    SELECT payload_json, ip_address, user_agent, raw_headers, lookup_hash
                    FROM raw_event_payloads
                    WHERE tenant_id = :tenant_id
                      AND event_id = :event_id
                    """
                ),
                {
                    "tenant_id": str(tenant_id),
                    "event_id": str(event_row["id"]),
                },
            )
        ).mappings().one()

    immutable_payload = event_row["raw_payload"]
    expirable_payload = payload_row["payload_json"]
    assert isinstance(immutable_payload, dict)
    assert isinstance(expirable_payload, dict)
    assert "order_id" not in immutable_payload
    assert expirable_payload.get("order_id") is not None
    assert payload_row["ip_address"] is None
    assert payload_row["user_agent"] is None
    assert payload_row["raw_headers"] is None
    assert payload_row["lookup_hash"] == hashlib.sha256(
        idempotency_key.encode("utf-8")
    ).hexdigest()


@pytest.mark.asyncio
async def test_b14_p4_runtime_90_day_gc_deletes_raw_payloads_without_touching_attribution_events():
    await _require_b14_p4_schema()
    tenant_id = uuid4()
    now = datetime.now(timezone.utc)
    idempotency_key = f"b14_p4_gc_{uuid4().hex[:10]}"
    session_id = uuid4()

    async with engine.begin() as conn:
        await _insert_tenant(conn, tenant_id, api_key_hash=f"test_hash_{tenant_id}")

    ingest_result = await ingest_with_transaction(
        tenant_id=tenant_id,
        event_data={
            "event_type": "purchase",
            "event_timestamp": _iso(now),
            "revenue_amount": "9.00",
            "currency": "USD",
            "session_id": str(session_id),
            "vendor": "shopify",
            "utm_source": "shopify",
            "utm_medium": "paid_social",
            "external_event_id": f"gc-{uuid4().hex[:8]}",
            "campaign_id": "cmp-gc",
        },
        idempotency_key=idempotency_key,
        source="shopify",
        identity_payload={"session_id": str(session_id)},
        request_headers={},
    )
    assert ingest_result.status == "success"

    async with engine.begin() as conn:
        await set_tenant_guc(conn, tenant_id, local=True)
        await conn.execute(
            text(
                """
                UPDATE raw_event_payloads
                SET created_at = :created_at,
                    updated_at = :updated_at
                WHERE tenant_id = :tenant_id
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "created_at": now - timedelta(days=91),
                "updated_at": now - timedelta(days=91),
            },
        )

    gc_result = await _delete_expired_raw_event_payload_rows(
        tenant_id,
        cutoff=datetime.now(timezone.utc) - timedelta(days=90),
        batch_size=100,
    )
    assert gc_result["deleted_rows"] >= 1

    async with engine.begin() as conn:
        await set_tenant_guc(conn, tenant_id, local=True)
        payload_count = await conn.scalar(
            text("SELECT COUNT(*) FROM raw_event_payloads WHERE tenant_id = :tenant_id"),
            {"tenant_id": str(tenant_id)},
        )
        event_count = await conn.scalar(
            text("SELECT COUNT(*) FROM attribution_events WHERE tenant_id = :tenant_id"),
            {"tenant_id": str(tenant_id)},
        )
    assert int(payload_count or 0) == 0
    assert int(event_count or 0) == 1


@pytest.mark.asyncio
async def test_b14_p4_runtime_deterministic_delete_wipes_payloads_and_invalidates_session_authority_and_emits_compliance_audit_artifact():
    await _require_b14_p4_schema()
    tenant_id = uuid4()
    now = datetime.now(timezone.utc)
    correlation_id = uuid4()
    idempotency_key = f"b14_p4_delete_{uuid4().hex[:10]}"
    requested_session_id = uuid4()

    async with engine.begin() as conn:
        await _insert_tenant(conn, tenant_id, api_key_hash=f"test_hash_{tenant_id}")

    ingest_result = await ingest_with_transaction(
        tenant_id=tenant_id,
        event_data={
            "event_type": "purchase",
            "event_timestamp": _iso(now),
            "revenue_amount": "14.00",
            "currency": "USD",
            "session_id": str(requested_session_id),
            "vendor": "paypal",
            "utm_source": "paypal",
            "utm_medium": "checkout",
            "external_event_id": f"delete-{uuid4().hex[:8]}",
            "campaign_id": "cmp-delete",
            "correlation_id": str(correlation_id),
        },
        idempotency_key=idempotency_key,
        source="paypal",
        identity_payload={"session_id": str(requested_session_id)},
        request_headers={},
    )
    assert ingest_result.status == "success"
    authoritative_session_id = ingest_result.session_id

    delete_result = await _erase_tenant_privacy_surfaces(
        tenant_id=tenant_id,
        selector={"idempotency_key": idempotency_key},
        correlation_id=correlation_id,
    )
    assert delete_result["raw_event_payloads_deleted"] >= 1
    assert delete_result["session_authority_invalidated"] >= 1
    assert delete_result["privacy_audit_artifacts_inserted"] == 1

    async with engine.begin() as conn:
        await set_tenant_guc(conn, tenant_id, local=True)
        remaining_payloads = await conn.scalar(
            text(
                """
                SELECT COUNT(*)
                FROM raw_event_payloads rep
                JOIN attribution_events e
                  ON e.id = rep.event_id
                WHERE rep.tenant_id = :tenant_id
                  AND e.idempotency_key = :idempotency_key
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "idempotency_key": idempotency_key,
            },
        )
        remaining_active_authority = await conn.scalar(
            text(
                """
                SELECT COUNT(*)
                FROM session_authority
                WHERE tenant_id = :tenant_id
                  AND session_id = :session_id
                  AND invalidated_at IS NULL
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "session_id": authoritative_session_id,
            },
        )
        invalidated_authority = await conn.scalar(
            text(
                """
                SELECT COUNT(*)
                FROM session_authority
                WHERE tenant_id = :tenant_id
                  AND session_id = :session_id
                  AND invalidated_at IS NOT NULL
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "session_id": authoritative_session_id,
            },
        )
        placeholder_rows = await conn.scalar(
            text(
                """
                SELECT COUNT(*)
                FROM session_authority
                WHERE tenant_id = :tenant_id
                  AND issued_by = 'privacy_erasure_tombstone'
                """
            ),
            {
                "tenant_id": str(tenant_id),
            },
        )
        ledger_tombstones = await conn.scalar(
            text(
                """
                SELECT COUNT(*)
                FROM attribution_events
                WHERE tenant_id = :tenant_id
                  AND event_type = 'privacy_tombstone'
                """
            ),
            {"tenant_id": str(tenant_id)},
        )
        audit_rows = await conn.scalar(
            text(
                """
                SELECT COUNT(*)
                FROM compliance_audit_ledger
                WHERE tenant_id = :tenant_id
                  AND audit_event_type = 'privacy_erasure'
                  AND correlation_id = :correlation_id
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "correlation_id": str(correlation_id),
            },
        )
    assert int(remaining_payloads or 0) == 0
    assert int(remaining_active_authority or 0) == 0
    assert int(invalidated_authority or 0) >= 1
    assert int(placeholder_rows or 0) == 0
    assert int(ledger_tombstones or 0) == 0
    assert int(audit_rows or 0) >= 1


@pytest.mark.asyncio
async def test_b14_p4_runtime_lookup_strategy_is_index_backed():
    await _require_b14_p4_schema()
    async with engine.begin() as conn:
        indexes = (
            await conn.execute(
                text(
                    """
                    SELECT indexname
                    FROM pg_indexes
                    WHERE schemaname = 'public'
                      AND indexname IN (
                        'idx_raw_event_payloads_tenant_lookup_hash',
                        'idx_raw_event_payloads_payload_json_gin',
                        'idx_dead_events_tenant_idempotency_key',
                        'idx_dead_events_quarantine_tenant_idempotency_key'
                      )
                    ORDER BY indexname
                    """
                )
            )
        ).scalars().all()
    assert indexes == [
        "idx_dead_events_quarantine_tenant_idempotency_key",
        "idx_dead_events_tenant_idempotency_key",
        "idx_raw_event_payloads_payload_json_gin",
        "idx_raw_event_payloads_tenant_lookup_hash",
    ]


@pytest.mark.asyncio
async def test_b14_p4_runtime_export_roas_survives_payload_expiry():
    await _require_b14_p4_schema()
    original_eager = celery_app.conf.task_always_eager
    celery_app.conf.task_always_eager = True
    tenant_id = uuid4()
    session_id = uuid4()
    now = datetime.now(timezone.utc)

    async def _auth_override() -> AuthContext:
        return _auth_context_for_tenant(tenant_id)

    app.dependency_overrides[get_auth_context] = _auth_override
    try:
        async with engine.begin() as conn:
            await _insert_tenant(conn, tenant_id, api_key_hash=f"test_hash_{tenant_id}")

        first_key = f"b14_p4_roas_a_{uuid4().hex[:8]}"
        second_key = f"b14_p4_roas_b_{uuid4().hex[:8]}"
        for key, amount in ((first_key, "10.00"), (second_key, "20.00")):
            result = await ingest_with_transaction(
                tenant_id=tenant_id,
                event_data={
                    "event_type": "purchase",
                    "event_timestamp": _iso(now),
                    "revenue_amount": amount,
                    "currency": "USD",
                    "session_id": str(session_id),
                    "vendor": "stripe",
                    "utm_source": "stripe",
                    "utm_medium": "checkout",
                    "external_event_id": f"roas-{uuid4().hex[:8]}",
                    "campaign_id": "cmp-roas",
                },
                idempotency_key=key,
                source="stripe",
                identity_payload={"session_id": str(session_id)},
                request_headers={},
            )
            assert result.status == "success"

        window_start = _iso(now.replace(hour=0, minute=0, second=0, microsecond=0))
        window_end = _iso(now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1))
        recompute_result = enqueue_tenant_task(
            recompute_window,
            envelope=SystemAuthorityEnvelope(tenant_id=tenant_id),
            kwargs={
                "window_start": window_start,
                "window_end": window_end,
                "model_version": "1.0.0",
            },
        ).get()
        assert recompute_result["status"] == "succeeded"

        async with engine.begin() as conn:
            await set_tenant_guc(conn, tenant_id, local=True)
            revenue_before = await conn.scalar(
                text(
                    """
                    SELECT COALESCE(SUM(allocated_revenue_cents), 0)
                    FROM attribution_allocations
                    WHERE tenant_id = :tenant_id
                    """
                ),
                {"tenant_id": str(tenant_id)},
            )
            await conn.execute(
                text(
                    """
                    UPDATE raw_event_payloads
                    SET created_at = :created_at,
                        updated_at = :updated_at
                    WHERE tenant_id = :tenant_id
                    """
                ),
                {
                    "tenant_id": str(tenant_id),
                    "created_at": now - timedelta(days=91),
                    "updated_at": now - timedelta(days=91),
                },
            )

        gc_result = await _delete_expired_raw_event_payload_rows(
            tenant_id,
            cutoff=datetime.now(timezone.utc) - timedelta(days=90),
            batch_size=1000,
        )
        assert gc_result["deleted_rows"] >= 2

        async with engine.begin() as conn:
            await set_tenant_guc(conn, tenant_id, local=True)
            payload_count = await conn.scalar(
                text("SELECT COUNT(*) FROM raw_event_payloads WHERE tenant_id = :tenant_id"),
                {"tenant_id": str(tenant_id)},
            )
            revenue_after = await conn.scalar(
                text(
                    """
                    SELECT COALESCE(SUM(allocated_revenue_cents), 0)
                    FROM attribution_allocations
                    WHERE tenant_id = :tenant_id
                    """
                ),
                {"tenant_id": str(tenant_id)},
            )

        assert int(payload_count or 0) == 0
        assert int(revenue_before or 0) > 0
        assert int(revenue_after or 0) == int(revenue_before or 0)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            export_response = await client.get(
                "/api/export/json",
                headers={"X-Correlation-ID": str(uuid4())},
            )
        assert export_response.status_code == 200, export_response.text
        payload = export_response.json()
        assert payload["data"]

        async with get_session(tenant_id=tenant_id) as db_session:
            rows = await _fetch_reporting_rows(
                db_session=db_session,
                tenant_id=tenant_id,
                session_scope=None,
                start=now.date(),
                end=now.date(),
            )
        assert rows
    finally:
        app.dependency_overrides.pop(get_auth_context, None)
        celery_app.conf.task_always_eager = original_eager
