from __future__ import annotations

import base64
from contextlib import contextmanager
import hashlib
import hmac
import asyncio
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from celery.contrib.testing.worker import start_worker
from celery.exceptions import TimeoutError as CeleryTimeoutError
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

os.environ.setdefault("SKELDIR_CELERY_INCLUDE_BAYESIAN_TASKS", "0")

from app.celery_app import celery_app
from app.core.queues import QUEUE_B23_MATCH_ENGINE
from app.db.session import b23_engine, engine, get_b23_session, get_session
from app.main import app
from app.revenue_verification import (
    PROVISIONAL_MATCH_WINDOW,
    VERIFICATION_COVERAGE,
    VerificationCoverageAggregate,
    compute_verification_coverage,
    fetch_verification_coverage_aggregate,
)
from app.revenue_verification.state_transitions import (
    transition_stale_provisional_to_confirmed,
)
from app.security.auth import AuthContext, get_auth_context
from app.tasks.context import run_in_worker_loop
from tests.helpers.webhook_secret_seed import (
    webhook_secret_insert_columns,
    webhook_secret_insert_params,
)


def _require_authoritative_db_proofs() -> bool:
    return os.getenv("SKELDIR_B23_P6_REQUIRE_DB_PROOFS", "0").strip().lower() in {
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
        _db_skip_or_fail(f"B2.3-P6 runtime proof DB is unreachable: {exc}")
    if regclass is None:
        _db_skip_or_fail(f"B2.3-P6 runtime proof table is missing: {table_name}")


async def _create_tenant_with_webhook_secrets() -> tuple[UUID, str, dict[str, str]]:
    tenant_id = uuid4()
    api_key = f"b23_p6_api_key_{uuid4()}"
    api_key_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
    secrets = {
        "shopify_webhook_secret": "b23_p6_shopify_secret",
        "stripe_webhook_secret": "b23_p6_stripe_secret",
        "paypal_webhook_secret": "b23_p6_paypal_secret",
        "woocommerce_webhook_secret": "b23_p6_woocommerce_secret",
    }
    secret_insert = webhook_secret_insert_params(
        shopify_secret=secrets["shopify_webhook_secret"],
        stripe_secret=secrets["stripe_webhook_secret"],
        paypal_secret=secrets["paypal_webhook_secret"],
        woocommerce_secret=secrets["woocommerce_webhook_secret"],
    )
    async with engine.begin() as conn:
        await conn.execute(
            text(
                f"""
                INSERT INTO public.tenants (
                    id,
                    api_key_hash,
                    name,
                    notification_email,
                    {webhook_secret_insert_columns()},
                    created_at,
                    updated_at
                )
                VALUES (
                    :tenant_id,
                    :api_key_hash,
                    :name,
                    :notification_email,
                    pgp_sym_encrypt(:shopify_webhook_secret, :webhook_secret_key),
                    :webhook_secret_key_id,
                    pgp_sym_encrypt(:stripe_webhook_secret, :webhook_secret_key),
                    :webhook_secret_key_id,
                    pgp_sym_encrypt(:paypal_webhook_secret, :webhook_secret_key),
                    :webhook_secret_key_id,
                    pgp_sym_encrypt(:woocommerce_webhook_secret, :webhook_secret_key),
                    :webhook_secret_key_id,
                    now(),
                    now()
                )
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "api_key_hash": api_key_hash,
                "name": f"B23P6 Tenant {str(tenant_id)[:8]}",
                "notification_email": f"b23p6_{str(tenant_id)[:8]}@test.local",
                **secrets,
                **secret_insert,
            },
        )
    return tenant_id, api_key, secrets


def _sign_shopify(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def _shopify_order_body(
    *, order_id: str, amount_minor: int, occurred_at: datetime
) -> bytes:
    return json.dumps(
        {
            "id": int(order_id),
            "total_price": f"{Decimal(amount_minor) / Decimal(100):.2f}",
            "currency": "USD",
            "created_at": occurred_at.isoformat(),
        },
        separators=(",", ":"),
    ).encode("utf-8")


async def _post_shopify_webhook(
    *,
    api_key: str,
    body: bytes,
    signature: str | None,
) -> tuple[int, dict[str, object]]:
    headers = {
        "Content-Type": "application/json",
        "X-Skeldir-Tenant-Key": api_key,
    }
    if signature is not None:
        headers["X-Shopify-Hmac-Sha256"] = signature
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/webhooks/shopify/order_create",
            content=body,
            headers=headers,
        )
    return response.status_code, response.json()


async def _clear_b23_match_engine_queue() -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                DELETE FROM public.kombu_message
                WHERE queue_id = (
                    SELECT id
                    FROM public.kombu_queue
                    WHERE name = :queue_name
                )
                """
            ),
            {"queue_name": QUEUE_B23_MATCH_ENGINE},
        )


@contextmanager
def _start_b23_match_worker():
    previous_prometheus_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    os.environ["PROMETHEUS_MULTIPROC_DIR"] = (
        previous_prometheus_dir or tempfile.mkdtemp(prefix="b23_p6_prom_")
    )
    try:
        with start_worker(
            celery_app,
            queues=[QUEUE_B23_MATCH_ENGINE],
            perform_ping_check=False,
            pool="solo",
            concurrency=1,
            loglevel="INFO",
        ):
            yield
    finally:
        if previous_prometheus_dir is None:
            os.environ.pop("PROMETHEUS_MULTIPROC_DIR", None)


def _auth_context(tenant_id: UUID) -> AuthContext:
    return AuthContext(
        tenant_id=tenant_id,
        user_id=uuid4(),
        jti=uuid4(),
        issued_at_epoch=int(datetime.now(timezone.utc).timestamp()),
        subject="b23-p6-runtime-proof",
        issuer="pytest",
        audience="skeldir-api",
        claims={"scopes": ["viewer"]},
    )


async def _seed_attribution_side_event(
    *,
    tenant_id: UUID,
    order_id: str,
    amount_minor: int,
    occurred_at: datetime,
) -> UUID:
    async with engine.begin() as conn:
        await conn.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
            {"tenant_id": str(tenant_id)},
        )
        await conn.execute(
            text(
                """
                INSERT INTO public.channel_taxonomy (
                    code,
                    family,
                    is_paid,
                    display_name,
                    is_active,
                    state
                )
                VALUES ('paid_search', 'paid', true, 'Paid Search', true, 'active')
                ON CONFLICT (code) DO NOTHING
                """
            )
        )
        attribution_id = (
            await conn.execute(
                text(
                    """
                    INSERT INTO public.attribution_events (
                        tenant_id,
                        occurred_at,
                        session_id,
                        revenue_cents,
                        raw_payload,
                        idempotency_key,
                        event_type,
                        channel,
                        conversion_value_cents,
                        currency,
                        event_timestamp,
                        processing_status
                    )
                    VALUES (
                        :tenant_id,
                        :occurred_at,
                        gen_random_uuid(),
                        :amount_minor,
                        jsonb_build_object('order_id', CAST(:order_id AS text)),
                        :idempotency_key,
                        'conversion',
                        'paid_search',
                        :amount_minor,
                        'USD',
                        :occurred_at,
                        'processed'
                    )
                    RETURNING id
                    """
                ),
                {
                    "tenant_id": str(tenant_id),
                    "occurred_at": occurred_at,
                    "amount_minor": amount_minor,
                    "order_id": order_id,
                    "idempotency_key": f"b23-p6-attribution-{tenant_id}-{order_id}",
                },
            )
        ).scalar_one()
        await conn.execute(
            text(
                """
                INSERT INTO public.attribution_commerce_identities (
                    tenant_id,
                    attribution_event_id,
                    provider,
                    canonical_commerce_reference,
                    source,
                    first_observed_at,
                    last_observed_at
                )
                VALUES (
                    :tenant_id,
                    :attribution_event_id,
                    'shopify',
                    :order_id,
                    'b23_p6_e2e_fixture',
                    :occurred_at,
                    :occurred_at
                )
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "attribution_event_id": str(attribution_id),
                "order_id": order_id,
                "occurred_at": occurred_at,
            },
        )
    return UUID(str(attribution_id))


async def _send_signed_shopify_webhook(
    *,
    api_key: str,
    secret: str,
    order_id: str,
    amount_minor: int,
    occurred_at: datetime,
) -> tuple[int, dict[str, object]]:
    body = _shopify_order_body(
        order_id=order_id, amount_minor=amount_minor, occurred_at=occurred_at
    )
    return await _post_shopify_webhook(
        api_key=api_key,
        body=body,
        signature=_sign_shopify(body, secret),
    )


async def _fetch_natural_dispatch_trace(
    *, tenant_id: UUID, order_id: str
) -> dict[str, object] | None:
    async with get_session(tenant_id) as session:
        row = (
            (
                await session.execute(
                    text(
                        """
                        SELECT
                            d.task_id,
                            d.task_name,
                            d.queue,
                            d.routing_key,
                            d.correlation_id,
                            d.provider,
                            d.provider_native_event_reference,
                            d.provider_native_commerce_reference,
                            d.normalized_commerce_reference_value,
                            d.webhook_ingress_identity_id,
                            wi.event_id AS webhook_event_id,
                            wi.idempotency_key,
                            wi.event_timestamp
                        FROM public.b23_match_task_dispatches d
                        JOIN public.webhook_ingress_identities wi
                          ON wi.tenant_id = d.tenant_id
                         AND wi.id = d.webhook_ingress_identity_id
                        WHERE d.tenant_id = :tenant_id
                          AND d.provider = 'shopify'
                          AND d.provider_native_event_reference = :order_id
                          AND d.normalized_commerce_reference_value = :order_id
                        """
                    ),
                    {"tenant_id": str(tenant_id), "order_id": order_id},
                )
            )
            .mappings()
            .one_or_none()
        )
    return dict(row) if row is not None else None


async def _wait_for_natural_dispatch_trace(
    *, tenant_id: UUID, order_id: str, timeout_seconds: float = 30.0
) -> dict[str, object]:
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    while asyncio.get_running_loop().time() < deadline:
        row = await _fetch_natural_dispatch_trace(tenant_id=tenant_id, order_id=order_id)
        if row is not None:
            return row
        await asyncio.sleep(0.25)
    raise AssertionError("B2.3 natural dispatch trace did not appear before deadline")


async def _wait_for_b23_task_result(task_id: str) -> dict[str, object]:
    async_result = celery_app.AsyncResult(task_id)
    try:
        payload = await asyncio.to_thread(
            async_result.get, timeout=90, propagate=True
        )
    except CeleryTimeoutError as exc:
        raise AssertionError(
            "B2.3 naturally emitted match task timed out without bounded completion"
        ) from exc
    assert async_result.state == "SUCCESS"
    assert isinstance(payload, dict)
    return payload


async def _fetch_verdict_by_reference(
    *, tenant_id: UUID, order_id: str
) -> dict[str, object] | None:
    async with get_b23_session(tenant_id) as session:
        row = (
            (
                await session.execute(
                    text(
                        """
                        SELECT
                            id,
                            attribution_event_id,
                            webhook_ingress_identity_id,
                            provider_native_event_reference,
                            canonical_commerce_reference
                        FROM public.b23_match_verdicts
                        WHERE tenant_id = :tenant_id
                          AND provider = 'shopify'
                          AND provider_native_event_reference = :order_id
                        """
                    ),
                    {"tenant_id": str(tenant_id), "order_id": order_id},
                )
            )
            .mappings()
            .one_or_none()
        )
    return dict(row) if row is not None else None


async def _wait_for_verdict_by_reference(
    *, tenant_id: UUID, order_id: str, timeout_seconds: float = 30.0
) -> dict[str, object]:
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    while asyncio.get_running_loop().time() < deadline:
        row = await _fetch_verdict_by_reference(tenant_id=tenant_id, order_id=order_id)
        if row is not None:
            return row
        await asyncio.sleep(0.25)
    raise AssertionError("B2.3 verdict did not appear before deadline")


async def _assert_no_verdict_before_deadline(
    *, tenant_id: UUID, order_id: str, timeout_seconds: float = 2.0
) -> None:
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    while asyncio.get_running_loop().time() < deadline:
        row = await _fetch_verdict_by_reference(tenant_id=tenant_id, order_id=order_id)
        assert row is None
        await asyncio.sleep(0.25)


async def _create_verdict_from_signed_webhook(
    *,
    tenant_id: UUID,
    api_key: str,
    secret: str,
    order_id: str,
    amount_minor: int,
    occurred_at: datetime,
) -> tuple[UUID, UUID]:
    attribution_event_id = await _seed_attribution_side_event(
        tenant_id=tenant_id,
        order_id=order_id,
        amount_minor=amount_minor,
        occurred_at=occurred_at - timedelta(seconds=30),
    )
    previous_eager = celery_app.conf.task_always_eager
    celery_app.conf.task_always_eager = False
    assert celery_app.conf.task_always_eager is False
    await _clear_b23_match_engine_queue()
    await b23_engine.dispose()
    await engine.dispose()
    try:
        with _start_b23_match_worker():
            status_code, payload = await _send_signed_shopify_webhook(
                api_key=api_key,
                secret=secret,
                order_id=order_id,
                amount_minor=amount_minor,
                occurred_at=occurred_at,
            )
            assert status_code == 200, payload
            assert payload["status"] == "success"
            leaked_fields = {
                "task_id",
                "queue",
                "routing_key",
                "outbox_id",
                "dispatch_trace_id",
                "worker",
                "worker_name",
                "b23_match_task_id",
            }
            assert leaked_fields.isdisjoint(payload.keys())
            trace = await _wait_for_natural_dispatch_trace(
                tenant_id=tenant_id, order_id=order_id
            )
            assert trace["task_id"]
            assert trace["task_name"] == (
                "app.tasks.revenue_verification.execute_b23_batch_match_engine"
            )
            assert trace["queue"] == QUEUE_B23_MATCH_ENGINE
            assert trace["routing_key"] == f"{QUEUE_B23_MATCH_ENGINE}.task"
            assert trace["provider"] == "shopify"
            assert trace["provider_native_event_reference"] == order_id
            assert trace["provider_native_commerce_reference"] == order_id
            assert trace["normalized_commerce_reference_value"] == order_id
            task_payload = await _wait_for_b23_task_result(str(trace["task_id"]))
            run_in_worker_loop(b23_engine.dispose())
            run_in_worker_loop(engine.dispose())
    finally:
        celery_app.conf.task_always_eager = previous_eager
    assert task_payload["task_name"] == (
        "app.tasks.revenue_verification.execute_b23_batch_match_engine"
    )
    assert task_payload["queue"] == QUEUE_B23_MATCH_ENGINE
    assert task_payload["db_session_pool"] == "b23"
    assert task_payload["processed_count"] == 1

    row = await _wait_for_verdict_by_reference(tenant_id=tenant_id, order_id=order_id)
    assert str(row["webhook_ingress_identity_id"]) == str(
        trace["webhook_ingress_identity_id"]
    )
    assert UUID(str(row["attribution_event_id"])) == attribution_event_id
    return UUID(str(row["id"])), attribution_event_id


async def _read_verdict_api(
    verdict_id: UUID, tenant_id: UUID
) -> tuple[int, dict[str, object]]:
    async def _auth_override():
        return _auth_context(tenant_id)

    app.dependency_overrides[get_auth_context] = _auth_override
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                f"/api/reconciliation/match-verdicts/{verdict_id}",
                headers={"X-Correlation-ID": str(uuid4())},
            )
        return response.status_code, response.json()
    finally:
        app.dependency_overrides.pop(get_auth_context, None)


@pytest.mark.asyncio(loop_scope="module")
async def test_b23_p6_natural_dispatch_requires_worker_for_verdict_creation() -> None:
    await _assert_table_exists("b23_match_task_dispatches")
    tenant_id, api_key, secrets = await _create_tenant_with_webhook_secrets()
    now = datetime.now(timezone.utc).replace(microsecond=0)
    order_id = str(uuid4().int % 1_000_000_000)
    await _seed_attribution_side_event(
        tenant_id=tenant_id,
        order_id=order_id,
        amount_minor=76000,
        occurred_at=now - timedelta(seconds=30),
    )
    previous_eager = celery_app.conf.task_always_eager
    celery_app.conf.task_always_eager = False
    try:
        await _clear_b23_match_engine_queue()
        status_code, payload = await _send_signed_shopify_webhook(
            api_key=api_key,
            secret=secrets["shopify_webhook_secret"],
            order_id=order_id,
            amount_minor=76000,
            occurred_at=now,
        )
        assert status_code == 200, payload
        trace = await _wait_for_natural_dispatch_trace(
            tenant_id=tenant_id, order_id=order_id
        )
        assert trace["queue"] == QUEUE_B23_MATCH_ENGINE
        await _assert_no_verdict_before_deadline(
            tenant_id=tenant_id, order_id=order_id
        )
    finally:
        await _clear_b23_match_engine_queue()
        celery_app.conf.task_always_eager = previous_eager


@pytest.mark.asyncio(loop_scope="module")
async def test_b23_p6_disabling_production_enqueue_prevents_verdict_creation() -> None:
    await _assert_table_exists("b23_match_task_dispatches")
    tenant_id, api_key, secrets = await _create_tenant_with_webhook_secrets()
    now = datetime.now(timezone.utc).replace(microsecond=0)
    order_id = str(uuid4().int % 1_000_000_000)
    await _seed_attribution_side_event(
        tenant_id=tenant_id,
        order_id=order_id,
        amount_minor=76000,
        occurred_at=now - timedelta(seconds=30),
    )
    previous_disable = os.environ.get("SKELDIR_B23_P6_DISABLE_NATURAL_DISPATCH")
    os.environ["SKELDIR_B23_P6_DISABLE_NATURAL_DISPATCH"] = "1"
    try:
        status_code, payload = await _send_signed_shopify_webhook(
            api_key=api_key,
            secret=secrets["shopify_webhook_secret"],
            order_id=order_id,
            amount_minor=76000,
            occurred_at=now,
        )
        assert status_code == 200, payload
        await _assert_no_verdict_before_deadline(
            tenant_id=tenant_id, order_id=order_id
        )
        assert (
            await _fetch_natural_dispatch_trace(tenant_id=tenant_id, order_id=order_id)
        ) is None
    finally:
        if previous_disable is None:
            os.environ.pop("SKELDIR_B23_P6_DISABLE_NATURAL_DISPATCH", None)
        else:
            os.environ["SKELDIR_B23_P6_DISABLE_NATURAL_DISPATCH"] = previous_disable


@pytest.mark.asyncio(loop_scope="module")
async def test_b23_p6_signed_webhook_to_confirmed_api_downstream_closure() -> None:
    for table_name in (
        "webhook_ingress_identities",
        "attribution_events",
        "attribution_commerce_identities",
        "b23_match_verdicts",
        "b23_match_task_dispatches",
        "b23_exception_records",
    ):
        await _assert_table_exists(table_name)

    tenant_a, api_key, secrets = await _create_tenant_with_webhook_secrets()
    tenant_b, _, _ = await _create_tenant_with_webhook_secrets()
    now = datetime.now(timezone.utc).replace(microsecond=0)
    order_id = str(uuid4().int % 1_000_000_000)

    verdict_id, attribution_event_id = await _create_verdict_from_signed_webhook(
        tenant_id=tenant_a,
        api_key=api_key,
        secret=secrets["shopify_webhook_secret"],
        order_id=order_id,
        amount_minor=76000,
        occurred_at=now,
    )

    body = _shopify_order_body(order_id=order_id, amount_minor=76000, occurred_at=now)
    mutated_body = _shopify_order_body(
        order_id=order_id, amount_minor=76001, occurred_at=now
    )
    invalid_status, _ = await _post_shopify_webhook(
        api_key=api_key,
        body=body,
        signature="invalid",
    )
    mutated_status, _ = await _post_shopify_webhook(
        api_key=api_key,
        body=mutated_body,
        signature=_sign_shopify(body, secrets["shopify_webhook_secret"]),
    )
    wrong_secret_status, _ = await _post_shopify_webhook(
        api_key=api_key,
        body=body,
        signature=_sign_shopify(body, "b23_p6_wrong_secret"),
    )
    missing_hmac_status, _ = await _post_shopify_webhook(
        api_key=api_key,
        body=body,
        signature=None,
    )
    duplicate_status, _ = await _post_shopify_webhook(
        api_key=api_key,
        body=body,
        signature=_sign_shopify(body, secrets["shopify_webhook_secret"]),
    )
    assert invalid_status == 401
    assert mutated_status == 401
    assert wrong_secret_status == 401
    assert missing_hmac_status == 401
    assert duplicate_status == 200

    async with get_session(tenant_a) as session:
        identity_count = (
            await session.execute(
                text(
                    """
                    SELECT count(*)
                    FROM public.webhook_ingress_identities
                    WHERE tenant_id = :tenant_id
                      AND provider = 'shopify'
                      AND provider_native_event_reference = :order_id
                    """
                ),
                {"tenant_id": str(tenant_a), "order_id": order_id},
            )
        ).scalar_one()
    assert int(identity_count) == 1
    assert await _fetch_natural_dispatch_trace(tenant_id=tenant_b, order_id=order_id) is None
    assert (
        await _fetch_natural_dispatch_trace(
            tenant_id=tenant_a, order_id=f"mismatched-{order_id}"
        )
        is None
    )

    status_code, provisional_payload = await _read_verdict_api(verdict_id, tenant_a)
    assert status_code == 200
    assert provisional_payload["status"] == "matched_provisional"
    assert provisional_payload["tenant_id"] == str(tenant_a)
    assert provisional_payload["attribution_event_id"] == str(attribution_event_id)
    assert provisional_payload["match_quality"] == "high"
    assert provisional_payload["canonical_net_verified_amount_minor"] == 76000
    assert provisional_payload["canonical_gross_expected_amount_minor"] == 76000
    assert provisional_payload["canonical_gross_captured_amount_minor"] == 76000
    assert provisional_payload["discrepancy"]["discrepancy_band"] == "exact"
    assert provisional_payload["adjustments_applied"] is False

    wrong_status_code, _ = await _read_verdict_api(verdict_id, tenant_b)
    assert wrong_status_code == 404

    young_order_id = str(uuid4().int % 1_000_000_000)
    young_verdict_id, _ = await _create_verdict_from_signed_webhook(
        tenant_id=tenant_a,
        api_key=api_key,
        secret=secrets["shopify_webhook_secret"],
        order_id=young_order_id,
        amount_minor=80000,
        occurred_at=now + timedelta(minutes=1),
    )

    async with get_b23_session(tenant_a) as session:
        unchanged = await transition_stale_provisional_to_confirmed(
            session,
            tenant_id=tenant_a,
            now_utc=now,
        )
    assert unchanged.transitioned_count == 0

    async with get_b23_session(tenant_a) as session:
        await session.execute(
            text(
                """
                UPDATE public.b23_match_verdicts
                SET
                    provisional_expires_at = :expired_at,
                    last_transition_at = :expired_at,
                    updated_at = :expired_at
                WHERE tenant_id = :tenant_id
                  AND id = :verdict_id
                """
            ),
            {
                "tenant_id": str(tenant_a),
                "verdict_id": str(verdict_id),
                "expired_at": now - PROVISIONAL_MATCH_WINDOW - timedelta(seconds=1),
            },
        )
        transitioned = await transition_stale_provisional_to_confirmed(
            session,
            tenant_id=tenant_a,
            now_utc=now,
        )
    assert transitioned.transitioned_count == 1

    async with get_b23_session(tenant_a) as session:
        rows = (
            (
                await session.execute(
                    text(
                        """
                    SELECT id, status, attribution_event_id
                    FROM public.b23_match_verdicts
                    WHERE tenant_id = :tenant_id
                      AND id IN (:stale_id, :young_id)
                    """
                    ),
                    {
                        "tenant_id": str(tenant_a),
                        "stale_id": str(verdict_id),
                        "young_id": str(young_verdict_id),
                    },
                )
            )
            .mappings()
            .all()
        )
        joined = (
            (
                await session.execute(
                    text(
                        """
                    SELECT
                        v.tenant_id,
                        v.provider,
                        v.canonical_commerce_reference,
                        v.canonical_net_verified_amount_minor,
                        ae.id AS attribution_event_id,
                        ae.raw_payload ->> 'order_id' AS attribution_order_id,
                        ae.conversion_value_cents
                    FROM public.b23_match_verdicts v
                    JOIN public.attribution_events ae
                      ON ae.tenant_id = v.tenant_id
                     AND ae.id = v.attribution_event_id
                    WHERE v.tenant_id = :tenant_id
                      AND v.id = :verdict_id
                    """
                    ),
                    {"tenant_id": str(tenant_a), "verdict_id": str(verdict_id)},
                )
            )
            .mappings()
            .one()
        )
        cross_tenant_count = (
            await session.execute(
                text(
                    """
                    SELECT count(*)
                    FROM public.b23_match_verdicts v
                    JOIN public.attribution_events ae
                      ON ae.tenant_id = :wrong_tenant
                     AND ae.id = v.attribution_event_id
                    WHERE v.tenant_id = :tenant_id
                      AND v.id = :verdict_id
                    """
                ),
                {
                    "tenant_id": str(tenant_a),
                    "wrong_tenant": str(tenant_b),
                    "verdict_id": str(verdict_id),
                },
            )
        ).scalar_one()

    statuses = {UUID(str(row["id"])): row["status"] for row in rows}
    assert statuses[verdict_id] == "matched_confirmed"
    assert statuses[young_verdict_id] == "matched_provisional"
    assert joined["provider"] == "shopify"
    assert joined["canonical_commerce_reference"] == order_id
    assert joined["attribution_order_id"] == order_id
    assert joined["canonical_net_verified_amount_minor"] == 76000
    assert joined["conversion_value_cents"] == 76000
    assert int(cross_tenant_count) == 0

    status_code, confirmed_payload = await _read_verdict_api(verdict_id, tenant_a)
    assert status_code == 200
    assert confirmed_payload["status"] == "matched_confirmed"
    assert confirmed_payload["attribution_event_id"] == str(attribution_event_id)


@pytest.mark.asyncio(loop_scope="module")
async def test_b23_p6_matched_states_require_attribution_fk_at_db_layer(
    test_tenant_pair,
) -> None:
    await _assert_table_exists("b23_match_verdicts")
    tenant_a, _ = test_tenant_pair
    now = datetime.now(timezone.utc)

    async with get_b23_session(tenant_a) as session:
        for status_value in ("pending", "unmatched"):
            await session.execute(
                text(
                    """
                    INSERT INTO public.b23_match_verdicts (
                        tenant_id,
                        provider,
                        canonical_commerce_reference,
                        provider_native_event_reference,
                        provider_native_commerce_reference,
                        status,
                        match_quality,
                        attributed_amount_minor,
                        verified_amount_minor,
                        currency_code,
                        pending_since,
                        last_transition_at,
                        created_at,
                        updated_at,
                        canonical_expected_gross_amount_minor,
                        canonical_captured_gross_amount_minor,
                        canonical_net_verified_amount_minor,
                        discrepancy_amount_minor,
                        discrepancy_ratio_bps,
                        discrepancy_band
                    )
                    VALUES (
                        :tenant_id,
                        'shopify',
                        :reference,
                        :event_reference,
                        :reference,
                        :status_value,
                        'low',
                        0,
                        0,
                        'USD',
                        :now_utc,
                        :now_utc,
                        :now_utc,
                        :now_utc,
                        0,
                        0,
                        0,
                        0,
                        0,
                        'exact'
                    )
                    """
                ),
                {
                    "tenant_id": str(tenant_a),
                    "reference": f"b23-p6-null-ok-{status_value}-{uuid4()}",
                    "event_reference": f"b23-p6-event-{status_value}-{uuid4()}",
                    "status_value": status_value,
                    "now_utc": now,
                },
            )

    for status_value in ("matched_provisional", "matched_confirmed", "adjusted"):
        with pytest.raises(IntegrityError):
            async with get_b23_session(tenant_a) as session:
                await session.execute(
                    text(
                        """
                        INSERT INTO public.b23_match_verdicts (
                            tenant_id,
                            provider,
                            canonical_commerce_reference,
                            provider_native_event_reference,
                            provider_native_commerce_reference,
                            status,
                            match_quality,
                            attributed_amount_minor,
                            verified_amount_minor,
                            currency_code,
                            pending_since,
                            last_transition_at,
                            created_at,
                            updated_at,
                            canonical_expected_gross_amount_minor,
                            canonical_captured_gross_amount_minor,
                            canonical_net_verified_amount_minor,
                            discrepancy_amount_minor,
                            discrepancy_ratio_bps,
                            discrepancy_band
                        )
                        VALUES (
                            :tenant_id,
                            'shopify',
                            :reference,
                            :event_reference,
                            :reference,
                            :status_value,
                            'high',
                            100,
                            100,
                            'USD',
                            :now_utc,
                            :now_utc,
                            :now_utc,
                            :now_utc,
                            100,
                            100,
                            100,
                            0,
                            0,
                            'exact'
                        )
                        """
                    ),
                    {
                        "tenant_id": str(tenant_a),
                        "reference": f"b23-p6-null-fail-{status_value}-{uuid4()}",
                        "event_reference": f"b23-p6-event-fail-{status_value}-{uuid4()}",
                        "status_value": status_value,
                        "now_utc": now,
                    },
                )


@pytest.mark.asyncio(loop_scope="module")
async def test_b23_p6_exception_records_remain_base_table() -> None:
    await _assert_table_exists("b23_exception_records")
    async with engine.connect() as conn:
        table_type = (
            await conn.execute(
                text(
                    """
                    SELECT table_type
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name = 'b23_exception_records'
                    """
                )
            )
        ).scalar_one()
    assert table_type == "BASE TABLE"


@pytest.mark.asyncio(loop_scope="module")
async def test_b23_p6_verification_coverage_callable_is_deterministic_and_bounded() -> (
    None
):
    tenant_a, _, _ = await _create_tenant_with_webhook_secrets()
    tenant_b, _, _ = await _create_tenant_with_webhook_secrets()
    now = datetime.now(timezone.utc).replace(microsecond=0)
    window_start = now - timedelta(hours=1)
    window_end = now + timedelta(hours=1)

    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO public.channel_taxonomy (
                    code,
                    family,
                    is_paid,
                    display_name,
                    is_active,
                    state
                )
                VALUES ('paid_search', 'paid', true, 'Paid Search', true, 'active')
                ON CONFLICT (code) DO NOTHING
                """
            )
        )

        async def insert_verified_webhook(
            *,
            tenant_id: UUID,
            provider: str,
            reference: str,
            amount_minor: int,
            currency: str,
            occurred_at: datetime,
        ) -> tuple[UUID, UUID]:
            await conn.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )
            attribution_event_id = UUID(
                str(
                    (
                        await conn.execute(
                            text(
                                """
                                INSERT INTO public.attribution_events (
                                    tenant_id,
                                    occurred_at,
                                    session_id,
                                    revenue_cents,
                                    raw_payload,
                                    idempotency_key,
                                    event_type,
                                    channel,
                                    conversion_value_cents,
                                    currency,
                                    event_timestamp,
                                    processing_status
                                )
                                VALUES (
                                    :tenant_id,
                                    :occurred_at,
                                    gen_random_uuid(),
                                    :amount_minor,
                                    jsonb_build_object('order_id', CAST(:reference AS text)),
                                    :idempotency_key,
                                    'conversion',
                                    'paid_search',
                                    :amount_minor,
                                    :currency,
                                    :occurred_at,
                                    'processed'
                                )
                                RETURNING id
                                """
                            ),
                            {
                                "tenant_id": str(tenant_id),
                                "occurred_at": occurred_at,
                                "amount_minor": amount_minor,
                                "reference": reference,
                                "currency": currency,
                                "idempotency_key": (
                                    f"b23-p6-coverage-attribution-{tenant_id}-{reference}"
                                ),
                            },
                        )
                    ).scalar_one()
                )
            )
            webhook_id = UUID(
                str(
                    (
                        await conn.execute(
                            text(
                                """
                                INSERT INTO public.webhook_ingress_identities (
                                    tenant_id,
                                    event_id,
                                    provider,
                                    provider_native_event_reference,
                                    provider_native_commerce_reference,
                                    normalized_commerce_reference_kind,
                                    normalized_commerce_reference_value,
                                    verified_amount_minor,
                                    verified_amount_currency,
                                    verified_amount_scale,
                                    event_timestamp,
                                    idempotency_key,
                                    verified_commerce_ingress_state,
                                    verified_at
                                )
                                VALUES (
                                    :tenant_id,
                                    :event_id,
                                    :provider,
                                    :event_reference,
                                    :commerce_reference,
                                    'order_id',
                                    :commerce_reference,
                                    :amount_minor,
                                    :currency,
                                    2,
                                    :occurred_at,
                                    :idempotency_key,
                                    'authenticity_verified',
                                    :occurred_at
                                )
                                RETURNING id
                                """
                            ),
                            {
                                "tenant_id": str(tenant_id),
                                "event_id": str(attribution_event_id),
                                "provider": provider,
                                "event_reference": f"coverage-event-{reference}",
                                "commerce_reference": reference,
                                "amount_minor": amount_minor,
                                "currency": currency,
                                "occurred_at": occurred_at,
                                "idempotency_key": (
                                    f"b23-p6-coverage-{tenant_id}-{reference}"
                                ),
                            },
                        )
                    ).scalar_one()
                )
            )
            return webhook_id, attribution_event_id

        matched_webhook_id, matched_attribution_id = await insert_verified_webhook(
            tenant_id=tenant_a,
            provider="stripe",
            reference=f"coverage-a-matched-{uuid4().hex[:8]}",
            amount_minor=76000,
            currency="USD",
            occurred_at=now,
        )
        await insert_verified_webhook(
            tenant_id=tenant_a,
            provider="stripe",
            reference=f"coverage-a-unmatched-{uuid4().hex[:8]}",
            amount_minor=4000,
            currency="USD",
            occurred_at=now,
        )
        await insert_verified_webhook(
            tenant_id=tenant_a,
            provider="bank_wire",
            reference=f"coverage-a-unsupported-{uuid4().hex[:8]}",
            amount_minor=20000,
            currency="USD",
            occurred_at=now,
        )
        await insert_verified_webhook(
            tenant_id=tenant_a,
            provider="stripe",
            reference=f"coverage-a-window-{uuid4().hex[:8]}",
            amount_minor=50000,
            currency="USD",
            occurred_at=window_end + timedelta(seconds=1),
        )
        await insert_verified_webhook(
            tenant_id=tenant_a,
            provider="stripe",
            reference=f"coverage-a-eur-{uuid4().hex[:8]}",
            amount_minor=60000,
            currency="EUR",
            occurred_at=now,
        )
        (
            tenant_b_matched_webhook_id,
            tenant_b_attribution_id,
        ) = await insert_verified_webhook(
            tenant_id=tenant_b,
            provider="stripe",
            reference=f"coverage-b-matched-{uuid4().hex[:8]}",
            amount_minor=900000,
            currency="USD",
            occurred_at=now,
        )
        await insert_verified_webhook(
            tenant_id=tenant_b,
            provider="stripe",
            reference=f"coverage-b-unmatched-{uuid4().hex[:8]}",
            amount_minor=100000,
            currency="USD",
            occurred_at=now,
        )

        async def insert_matched_verdict(
            *,
            tenant_id: UUID,
            attribution_event_id: UUID,
            webhook_ingress_identity_id: UUID,
            reference: str,
            amount_minor: int,
        ) -> None:
            await conn.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )
            await conn.execute(
                text(
                    """
                    INSERT INTO public.b23_match_verdicts (
                        tenant_id,
                        attribution_event_id,
                        webhook_ingress_identity_id,
                        provider,
                        canonical_commerce_reference,
                        provider_native_event_reference,
                        provider_native_commerce_reference,
                        status,
                        match_quality,
                        attributed_amount_minor,
                        verified_amount_minor,
                        currency_code,
                        pending_since,
                        provisional_expires_at,
                        last_transition_at,
                        created_at,
                        updated_at,
                        canonical_expected_gross_amount_minor,
                        canonical_captured_gross_amount_minor,
                        canonical_net_verified_amount_minor,
                        discrepancy_amount_minor,
                        discrepancy_ratio_bps,
                        discrepancy_band
                    )
                    VALUES (
                        :tenant_id,
                        :attribution_event_id,
                        :webhook_ingress_identity_id,
                        'stripe',
                        :reference,
                        :event_reference,
                        :reference,
                        'matched_confirmed',
                        'high',
                        :amount_minor,
                        :amount_minor,
                        'USD',
                        :now_utc,
                        :now_utc,
                        :now_utc,
                        :now_utc,
                        :now_utc,
                        :amount_minor,
                        :amount_minor,
                        :amount_minor,
                        0,
                        0,
                        'exact'
                    )
                    """
                ),
                {
                    "tenant_id": str(tenant_id),
                    "attribution_event_id": str(attribution_event_id),
                    "webhook_ingress_identity_id": str(webhook_ingress_identity_id),
                    "reference": reference,
                    "event_reference": f"{reference}-event",
                    "amount_minor": amount_minor,
                    "now_utc": now,
                },
            )

        await insert_matched_verdict(
            tenant_id=tenant_a,
            attribution_event_id=matched_attribution_id,
            webhook_ingress_identity_id=matched_webhook_id,
            reference="coverage-a-matched",
            amount_minor=76000,
        )
        await insert_matched_verdict(
            tenant_id=tenant_b,
            attribution_event_id=tenant_b_attribution_id,
            webhook_ingress_identity_id=tenant_b_matched_webhook_id,
            reference="coverage-b-matched",
            amount_minor=900000,
        )

    async with get_b23_session(tenant_a) as session:
        aggregate = await fetch_verification_coverage_aggregate(
            session,
            tenant_id=tenant_a,
            window_start=window_start,
            window_end=window_end,
            supported_platforms=("stripe",),
            currency_code="USD",
        )

    assert aggregate.matched_webhook_revenue_minor == 76000
    assert aggregate.connected_platform_revenue_minor == 80000
    result = compute_verification_coverage(aggregate)
    assert result.coverage_percent == Decimal("95.00")
    assert result.numerator_matched_webhook_revenue_minor == 76000
    assert result.denominator_connected_platform_revenue_minor == 80000
    assert result.zero_denominator is False

    assert VERIFICATION_COVERAGE.compute(aggregate).coverage_percent == Decimal("95.00")

    zero = compute_verification_coverage(
        VerificationCoverageAggregate(
            tenant_id=tenant_a,
            currency_code="USD",
            window_start=window_start,
            window_end=window_end,
            matched_webhook_revenue_minor=0,
            connected_platform_revenue_minor=0,
        )
    )
    assert zero.coverage_percent == Decimal("0.00")
    assert zero.zero_denominator is True

    tenant_b_result = compute_verification_coverage(
        VerificationCoverageAggregate(
            tenant_id=tenant_b,
            currency_code="USD",
            window_start=window_start,
            window_end=window_end,
            matched_webhook_revenue_minor=900000,
            connected_platform_revenue_minor=1000000,
        )
    )
    assert tenant_b_result.coverage_percent == Decimal("90.00")

    async with get_b23_session(tenant_a) as session:
        empty_aggregate = await fetch_verification_coverage_aggregate(
            session,
            tenant_id=tenant_a,
            window_start=window_end + timedelta(days=1),
            window_end=window_end + timedelta(days=2),
            supported_platforms=("stripe",),
            currency_code="USD",
        )
    assert empty_aggregate.connected_platform_revenue_minor == 0
