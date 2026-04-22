#!/usr/bin/env python3
"""B2.2-P5 mounted webhook ingress benchmark harness."""

from __future__ import annotations

import asyncio
import argparse
import base64
import hashlib
import hmac
import json
import math
import os
import sys
import time
import zlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable
from uuid import UUID, uuid4

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import Encoding
from cryptography.x509.oid import NameOID
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, func, select, text

from app.core.secrets import (
    get_database_url,
    get_platform_encryption_material_for_write,
)
from app.db.session import get_session
from app.main import app
from app.models import AttributionEvent, RawEventPayload, WebhookIngressIdentity

BENCHMARK_SCHEMA_VERSION = "b22_p5_webhook_ingress_benchmark.v1"
BENCHMARK_TIMING_BOUNDARY = "mounted_http_request_to_ack_response"
DEFAULT_PAYPAL_TEST_CERT_URL = (
    "https://api-m.paypal.com/v1/notifications/certs/CERT-LOCAL-TEST"
)
MOUNTED_ROUTES = (
    "/api/webhooks/shopify/order_create",
    "/api/webhooks/stripe/payment_intent_succeeded",
    "/api/webhooks/stripe/payment_intent/succeeded",
    "/api/webhooks/paypal/sale_completed",
    "/api/webhooks/woocommerce/order_completed",
)


@dataclass(frozen=True)
class PayPalTestKeyMaterial:
    private_key: rsa.RSAPrivateKey
    certificate_pem: bytes


@dataclass(frozen=True)
class WebhookCase:
    route: str
    body: bytes
    headers: dict[str, str]
    provider: str
    expected_status: str = "success"


@lru_cache(maxsize=1)
def _paypal_test_key_material() -> PayPalTestKeyMaterial:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.now(timezone.utc)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "PayPal Test"),
            x509.NameAttribute(NameOID.COMMON_NAME, "api-m.paypal.com"),
        ]
    )
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=30))
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.DNSName("api-m.paypal.com"),
                    x509.DNSName("api.sandbox.paypal.com"),
                ]
            ),
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )
    return PayPalTestKeyMaterial(
        private_key=private_key,
        certificate_pem=certificate.public_bytes(encoding=Encoding.PEM),
    )


def _configure_paypal_test_certificate_override() -> str:
    key_material = _paypal_test_key_material()
    os.environ["SKELDIR_PAYPAL_TEST_CERT_URL"] = DEFAULT_PAYPAL_TEST_CERT_URL
    os.environ["SKELDIR_PAYPAL_TEST_CERT_PEM"] = key_material.certificate_pem.decode(
        "utf-8"
    )
    return DEFAULT_PAYPAL_TEST_CERT_URL


def _sign_shopify(raw_body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def _sign_woocommerce(raw_body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def _sign_stripe(raw_body: bytes, secret: str) -> str:
    timestamp = int(datetime.now(timezone.utc).timestamp())
    signed_payload = f"{timestamp}.{raw_body.decode('utf-8')}".encode("utf-8")
    signature = hmac.new(
        secret.encode("utf-8"), signed_payload, hashlib.sha256
    ).hexdigest()
    return f"t={timestamp},v1={signature}"


def _build_paypal_auth_headers(
    *,
    raw_body: bytes,
    webhook_id: str,
    cert_url: str,
) -> dict[str, str]:
    transmission_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    transmission_id = f"tr_{uuid4().hex[:16]}"
    crc32_value = zlib.crc32(raw_body) & 0xFFFFFFFF
    message = (
        f"{transmission_id}|{transmission_time}|{webhook_id}|{crc32_value}".encode(
            "utf-8"
        )
    )
    signature = _paypal_test_key_material().private_key.sign(
        message,
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    return {
        "PayPal-Transmission-Id": transmission_id,
        "PayPal-Transmission-Time": transmission_time,
        "PayPal-Transmission-Sig": base64.b64encode(signature).decode("utf-8"),
        "PayPal-Auth-Algo": "SHA256withRSA",
        "PayPal-Cert-Url": cert_url,
        "PayPal-Webhook-Id": webhook_id,
    }


def _normalize_sync_database_url(raw_url: str) -> str:
    if raw_url.startswith("postgresql+asyncpg://"):
        return raw_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return raw_url


def _assert_runtime_tables(sync_database_url: str) -> None:
    engine = create_engine(sync_database_url)
    required_tables = (
        "tenants",
        "attribution_events",
        "raw_event_payloads",
        "webhook_ingress_identities",
    )
    with engine.begin() as conn:
        for table in required_tables:
            table_present = conn.execute(
                text("SELECT to_regclass(:table_name)"),
                {"table_name": f"public.{table}"},
            ).scalar_one()
            if table_present is None:
                raise RuntimeError(f"benchmark requires table public.{table}")
    engine.dispose()


def _insert_tenant_with_webhook_secrets(
    *,
    sync_database_url: str,
    tenant_id: UUID,
    api_key_hash: str,
    secrets: dict[str, str],
) -> None:
    webhook_secret_key_id, webhook_secret_key = (
        get_platform_encryption_material_for_write()
    )
    engine = create_engine(sync_database_url)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO tenants (
                    id,
                    api_key_hash,
                    name,
                    notification_email,
                    shopify_webhook_secret_ciphertext,
                    shopify_webhook_secret_key_id,
                    stripe_webhook_secret_ciphertext,
                    stripe_webhook_secret_key_id,
                    paypal_webhook_secret_ciphertext,
                    paypal_webhook_secret_key_id,
                    woocommerce_webhook_secret_ciphertext,
                    woocommerce_webhook_secret_key_id,
                    created_at,
                    updated_at
                ) VALUES (
                    :tenant_id,
                    :api_key_hash,
                    :tenant_name,
                    :tenant_email,
                    pgp_sym_encrypt(:shopify_secret, :webhook_secret_key),
                    :webhook_secret_key_id,
                    pgp_sym_encrypt(:stripe_secret, :webhook_secret_key),
                    :webhook_secret_key_id,
                    pgp_sym_encrypt(:paypal_secret, :webhook_secret_key),
                    :webhook_secret_key_id,
                    pgp_sym_encrypt(:woocommerce_secret, :webhook_secret_key),
                    :webhook_secret_key_id,
                    NOW(),
                    NOW()
                )
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "api_key_hash": api_key_hash,
                "tenant_name": f"B22 P5 Benchmark {tenant_id.hex[:8]}",
                "tenant_email": f"b22-p5-{tenant_id.hex[:8]}@example.invalid",
                "shopify_secret": secrets["shopify_webhook_secret"],
                "stripe_secret": secrets["stripe_webhook_secret"],
                "paypal_secret": secrets["paypal_webhook_secret"],
                "woocommerce_secret": secrets["woocommerce_webhook_secret"],
                "webhook_secret_key_id": webhook_secret_key_id,
                "webhook_secret_key": webhook_secret_key,
            },
        )
    engine.dispose()


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return float(ordered[index])


def _component_module(value: Any) -> str:
    return str(getattr(value, "__module__", "") or "")


def _component_name(value: Any) -> str:
    return str(
        getattr(value, "__name__", "") or getattr(value, "__qualname__", "") or ""
    )


def _runtime_component_integrity() -> dict[str, Any]:
    from app.api import webhooks as webhooks_api

    expected_modules = {
        "shopify_signature": "app.webhooks.signatures",
        "stripe_signature": "app.webhooks.signatures",
        "paypal_signature": "app.webhooks.signatures",
        "woocommerce_signature": "app.webhooks.signatures",
        "tenant_resolution": "app.core.tenant_context",
        "ingestion_transaction": "app.ingestion.event_service",
    }
    observed = {
        "shopify_signature": _component_module(
            webhooks_api.WEBHOOK_VERIFIERS["shopify"][1]
        ),
        "stripe_signature": _component_module(
            webhooks_api.WEBHOOK_VERIFIERS["stripe"][1]
        ),
        "paypal_signature": _component_module(
            webhooks_api.WEBHOOK_VERIFIERS["paypal"][1]
        ),
        "woocommerce_signature": _component_module(
            webhooks_api.WEBHOOK_VERIFIERS["woocommerce"][1]
        ),
        "tenant_resolution": _component_module(
            webhooks_api.get_tenant_with_webhook_secrets
        ),
        "ingestion_transaction": _component_module(
            webhooks_api.ingest_with_transaction
        ),
    }
    observed_names = {
        "shopify_signature": _component_name(
            webhooks_api.WEBHOOK_VERIFIERS["shopify"][1]
        ),
        "stripe_signature": _component_name(
            webhooks_api.WEBHOOK_VERIFIERS["stripe"][1]
        ),
        "paypal_signature": _component_name(
            webhooks_api.WEBHOOK_VERIFIERS["paypal"][1]
        ),
        "woocommerce_signature": _component_name(
            webhooks_api.WEBHOOK_VERIFIERS["woocommerce"][1]
        ),
        "tenant_resolution": _component_name(
            webhooks_api.get_tenant_with_webhook_secrets
        ),
        "ingestion_transaction": _component_name(webhooks_api.ingest_with_transaction),
    }
    mismatches = [
        f"{component}:{observed_module}!={expected_module}"
        for component, expected_module in expected_modules.items()
        if observed.get(component) != expected_module
    ]
    return {
        "expected_modules": expected_modules,
        "observed_modules": observed,
        "observed_names": observed_names,
        "passes": not mismatches,
        "violations": mismatches,
    }


def _make_shopify_case(
    *, api_key: str, secret: str, event_id: int, topic: str = "orders/create"
) -> WebhookCase:
    body = json.dumps(
        {
            "id": event_id,
            "total_price": "19.95",
            "currency": "USD",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    ).encode("utf-8")
    headers = {
        "X-Shopify-Hmac-Sha256": _sign_shopify(body, secret),
        "X-Shopify-Topic": topic,
        "X-Skeldir-Tenant-Key": api_key,
        "Content-Type": "application/json",
    }
    return WebhookCase(
        route="/api/webhooks/shopify/order_create",
        body=body,
        headers=headers,
        provider="shopify",
    )


def _make_stripe_canonical_case(
    *,
    api_key: str,
    secret: str,
    payment_intent_id: str,
    event_type: str = "payment_intent.succeeded",
) -> WebhookCase:
    body = json.dumps(
        {
            "id": payment_intent_id,
            "amount": 2599,
            "currency": "usd",
            "created": int(datetime.now(timezone.utc).timestamp()),
            "status": "succeeded",
            "type": event_type,
        }
    ).encode("utf-8")
    headers = {
        "Stripe-Signature": _sign_stripe(body, secret),
        "X-Skeldir-Tenant-Key": api_key,
        "Content-Type": "application/json",
    }
    return WebhookCase(
        route="/api/webhooks/stripe/payment_intent_succeeded",
        body=body,
        headers=headers,
        provider="stripe",
    )


def _make_stripe_alias_case(
    *,
    api_key: str,
    secret: str,
    payment_intent_id: str,
    event_type: str = "payment_intent.succeeded",
) -> WebhookCase:
    body = json.dumps(
        {
            "id": f"evt_{uuid4().hex[:16]}",
            "type": event_type,
            "created": int(datetime.now(timezone.utc).timestamp()),
            "data": {
                "object": {
                    "id": payment_intent_id,
                    "amount": 3199,
                    "currency": "usd",
                    "metadata": {"order_id": f"order_{payment_intent_id}"},
                }
            },
        }
    ).encode("utf-8")
    headers = {
        "Stripe-Signature": _sign_stripe(body, secret),
        "X-Skeldir-Tenant-Key": api_key,
        "Content-Type": "application/json",
    }
    return WebhookCase(
        route="/api/webhooks/stripe/payment_intent/succeeded",
        body=body,
        headers=headers,
        provider="stripe",
    )


def _make_paypal_case(
    *,
    api_key: str,
    secret: str,
    cert_url: str,
    transaction_id: str,
    event_type: str = "PAYMENT.SALE.COMPLETED",
) -> WebhookCase:
    body = json.dumps(
        {
            "id": transaction_id,
            "event_type": event_type,
            "amount": {"total": "13.50", "currency": "USD"},
            "create_time": datetime.now(timezone.utc).isoformat(),
        }
    ).encode("utf-8")
    headers = _build_paypal_auth_headers(
        raw_body=body, webhook_id=secret, cert_url=cert_url
    )
    headers["X-Skeldir-Tenant-Key"] = api_key
    headers["Content-Type"] = "application/json"
    return WebhookCase(
        route="/api/webhooks/paypal/sale_completed",
        body=body,
        headers=headers,
        provider="paypal",
    )


def _make_woocommerce_case(
    *,
    api_key: str,
    secret: str,
    order_id: int,
    topic: str = "order.completed",
) -> WebhookCase:
    body = json.dumps(
        {
            "id": order_id,
            "total": "44.10",
            "currency": "USD",
            "status": "completed",
            "date_completed": datetime.now(timezone.utc).isoformat(),
        }
    ).encode("utf-8")
    headers = {
        "X-WC-Webhook-Signature": _sign_woocommerce(body, secret),
        "X-WC-Webhook-Topic": topic,
        "X-Skeldir-Tenant-Key": api_key,
        "Content-Type": "application/json",
    }
    return WebhookCase(
        route="/api/webhooks/woocommerce/order_completed",
        body=body,
        headers=headers,
        provider="woocommerce",
    )


async def _send_case(
    client: AsyncClient, case: WebhookCase
) -> tuple[int, dict[str, Any]]:
    response = await client.post(case.route, content=case.body, headers=case.headers)
    payload: dict[str, Any] = {}
    try:
        parsed = response.json()
        if isinstance(parsed, dict):
            payload = parsed
    except Exception:
        payload = {}
    return response.status_code, payload


async def _run_integrity_probes(
    *,
    client: AsyncClient,
    api_key: str,
    secrets: dict[str, str],
    cert_url: str,
) -> dict[str, Any]:
    component_integrity = _runtime_component_integrity()
    if not component_integrity["passes"]:
        raise RuntimeError(
            "runtime_component_integrity_failed:"
            + "|".join(component_integrity["violations"])
        )

    supported_cases = [
        _make_shopify_case(
            api_key=api_key,
            secret=secrets["shopify_webhook_secret"],
            event_id=int(uuid4().int % 1_000_000),
        ),
        _make_stripe_canonical_case(
            api_key=api_key,
            secret=secrets["stripe_webhook_secret"],
            payment_intent_id=f"pi_{uuid4().hex[:16]}",
        ),
        _make_stripe_alias_case(
            api_key=api_key,
            secret=secrets["stripe_webhook_secret"],
            payment_intent_id=f"pi_{uuid4().hex[:16]}",
        ),
        _make_paypal_case(
            api_key=api_key,
            secret=secrets["paypal_webhook_secret"],
            cert_url=cert_url,
            transaction_id=f"txn_{uuid4().hex[:16]}",
        ),
        _make_woocommerce_case(
            api_key=api_key,
            secret=secrets["woocommerce_webhook_secret"],
            order_id=int(uuid4().int % 1_000_000),
        ),
    ]

    supported_statuses: dict[str, dict[str, Any]] = {}
    for case in supported_cases:
        status_code, payload = await _send_case(client, case)
        if status_code != 200 or str(payload.get("status")) != "success":
            raise RuntimeError(
                f"integrity_supported_case_failed:{case.route}:{status_code}:{payload}"
            )
        supported_statuses[case.route] = {
            "http_status": status_code,
            "status": payload.get("status"),
            "event_id_present": bool(payload.get("event_id")),
        }

    duplicate_probe_case = _make_shopify_case(
        api_key=api_key,
        secret=secrets["shopify_webhook_secret"],
        event_id=int(uuid4().int % 1_000_000),
    )
    first_duplicate_status, first_duplicate_payload = await _send_case(
        client, duplicate_probe_case
    )
    second_duplicate_status, second_duplicate_payload = await _send_case(
        client, duplicate_probe_case
    )
    if first_duplicate_status != 200 or second_duplicate_status != 200:
        raise RuntimeError("integrity_duplicate_probe_http_failed")
    if first_duplicate_payload.get("event_id") != second_duplicate_payload.get(
        "event_id"
    ):
        raise RuntimeError("integrity_duplicate_probe_event_id_mismatch")

    forged_case = _make_shopify_case(
        api_key=api_key,
        secret=secrets["shopify_webhook_secret"],
        event_id=int(uuid4().int % 1_000_000),
    )
    forged_headers = dict(forged_case.headers)
    forged_headers["X-Shopify-Hmac-Sha256"] = "invalid"
    forged_status, _ = await _send_case(
        client,
        WebhookCase(
            route=forged_case.route,
            body=forged_case.body,
            headers=forged_headers,
            provider="shopify",
        ),
    )
    if forged_status != 401:
        raise RuntimeError(f"integrity_forged_signature_not_401:{forged_status}")

    unsupported_cases = [
        _make_shopify_case(
            api_key=api_key,
            secret=secrets["shopify_webhook_secret"],
            event_id=int(uuid4().int % 1_000_000),
            topic="orders/paid",
        ),
        _make_stripe_canonical_case(
            api_key=api_key,
            secret=secrets["stripe_webhook_secret"],
            payment_intent_id=f"pi_{uuid4().hex[:16]}",
            event_type="charge.succeeded",
        ),
        _make_stripe_alias_case(
            api_key=api_key,
            secret=secrets["stripe_webhook_secret"],
            payment_intent_id=f"pi_{uuid4().hex[:16]}",
            event_type="charge.succeeded",
        ),
        _make_paypal_case(
            api_key=api_key,
            secret=secrets["paypal_webhook_secret"],
            cert_url=cert_url,
            transaction_id=f"txn_{uuid4().hex[:16]}",
            event_type="PAYMENT.CAPTURE.COMPLETED",
        ),
        _make_woocommerce_case(
            api_key=api_key,
            secret=secrets["woocommerce_webhook_secret"],
            order_id=int(uuid4().int % 1_000_000),
            topic="order.updated",
        ),
    ]
    unsupported_statuses: dict[str, dict[str, Any]] = {}
    for case in unsupported_cases:
        status_code, payload = await _send_case(client, case)
        if status_code != 200:
            raise RuntimeError(
                f"integrity_unsupported_http_failed:{case.route}:{status_code}"
            )
        if str(payload.get("status")) != "unsupported_event_family_ignored":
            raise RuntimeError(
                f"integrity_unsupported_status_failed:{case.route}:{status_code}:{payload}"
            )
        if str(payload.get("error")) != "unsupported_event_family":
            raise RuntimeError(
                f"integrity_unsupported_error_failed:{case.route}:{status_code}:{payload}"
            )
        unsupported_statuses[case.route] = {
            "http_status": status_code,
            "status": payload.get("status"),
            "error": payload.get("error"),
        }

    return {
        "component_integrity": component_integrity,
        "supported_cases": supported_statuses,
        "forged_signature_http_status": forged_status,
        "duplicate_replay_event_id_stable": True,
        "unsupported_event_family_cases": unsupported_statuses,
    }


def _iter_measurement_cases(
    *,
    api_key: str,
    secrets: dict[str, str],
    cert_url: str,
) -> tuple[Callable[[], WebhookCase], ...]:
    return (
        lambda: _make_shopify_case(
            api_key=api_key,
            secret=secrets["shopify_webhook_secret"],
            event_id=int(uuid4().int % 1_000_000),
        ),
        lambda: _make_stripe_canonical_case(
            api_key=api_key,
            secret=secrets["stripe_webhook_secret"],
            payment_intent_id=f"pi_{uuid4().hex[:16]}",
        ),
        lambda: _make_stripe_alias_case(
            api_key=api_key,
            secret=secrets["stripe_webhook_secret"],
            payment_intent_id=f"pi_{uuid4().hex[:16]}",
        ),
        lambda: _make_paypal_case(
            api_key=api_key,
            secret=secrets["paypal_webhook_secret"],
            cert_url=cert_url,
            transaction_id=f"txn_{uuid4().hex[:16]}",
        ),
        lambda: _make_woocommerce_case(
            api_key=api_key,
            secret=secrets["woocommerce_webhook_secret"],
            order_id=int(uuid4().int % 1_000_000),
        ),
    )


async def _run_measurement(
    *,
    client: AsyncClient,
    api_key: str,
    secrets: dict[str, str],
    cert_url: str,
    warmup_per_route: int,
    iterations_per_route: int,
) -> dict[str, Any]:
    case_builders = _iter_measurement_cases(
        api_key=api_key, secrets=secrets, cert_url=cert_url
    )
    latencies_ms: list[float] = []
    per_route_ms: dict[str, list[float]] = {route: [] for route in MOUNTED_ROUTES}
    success_count = 0

    for _ in range(warmup_per_route):
        for build_case in case_builders:
            case = build_case()
            status_code, payload = await _send_case(client, case)
            if status_code != 200 or str(payload.get("status")) != "success":
                raise RuntimeError(
                    f"warmup_case_failed:{case.route}:{status_code}:{payload}"
                )

    for _ in range(iterations_per_route):
        for build_case in case_builders:
            case = build_case()
            started = time.perf_counter_ns()
            status_code, payload = await _send_case(client, case)
            elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000.0
            if status_code != 200 or str(payload.get("status")) != "success":
                raise RuntimeError(
                    f"measurement_case_failed:{case.route}:{status_code}:{payload}"
                )
            latencies_ms.append(elapsed_ms)
            per_route_ms[case.route].append(elapsed_ms)
            success_count += 1

    per_route_summary = {
        route: {
            "count": len(values),
            "p50_ms": round(_percentile(values, 0.50), 3),
            "p95_ms": round(_percentile(values, 0.95), 3),
            "max_ms": round(max(values) if values else 0.0, 3),
        }
        for route, values in per_route_ms.items()
    }
    return {
        "sample_count": len(latencies_ms),
        "success_count": success_count,
        "p50_ms": round(_percentile(latencies_ms, 0.50), 3),
        "p95_ms": round(_percentile(latencies_ms, 0.95), 3),
        "max_ms": round(max(latencies_ms) if latencies_ms else 0.0, 3),
        "per_route": per_route_summary,
    }


async def _collect_persistence_proof_counts(*, tenant_id: UUID) -> dict[str, int]:
    raw_payload_order_column = (
        getattr(RawEventPayload, "ingested_at", None)
        or getattr(RawEventPayload, "created_at", None)
        or getattr(RawEventPayload, "updated_at", None)
    )
    if raw_payload_order_column is None:
        raise RuntimeError(
            "RawEventPayload model missing timestamp column for benchmark ordering"
        )

    async with get_session(tenant_id=tenant_id) as session:
        attribution_events = await session.scalar(
            select(func.count())
            .select_from(AttributionEvent)
            .where(AttributionEvent.tenant_id == tenant_id)
        )
        webhook_identities = await session.scalar(
            select(func.count())
            .select_from(WebhookIngressIdentity)
            .where(WebhookIngressIdentity.tenant_id == tenant_id)
        )
        raw_payloads = await session.scalar(
            select(func.count())
            .select_from(RawEventPayload)
            .where(RawEventPayload.tenant_id == tenant_id)
        )
        minimized_row = await session.execute(
            select(
                RawEventPayload.ip_address,
                RawEventPayload.user_agent,
                RawEventPayload.raw_headers,
            )
            .where(RawEventPayload.tenant_id == tenant_id)
            .order_by(raw_payload_order_column.desc())
            .limit(1)
        )
        latest = minimized_row.first()
    latest_minimized = {
        "ip_address_is_null": latest is not None and latest[0] is None,
        "user_agent_is_null": latest is not None and latest[1] is None,
        "raw_headers_is_null": latest is not None and latest[2] is None,
    }
    return {
        "attribution_events": int(attribution_events or 0),
        "webhook_ingress_identities": int(webhook_identities or 0),
        "raw_event_payloads": int(raw_payloads or 0),
        "latest_raw_payload_minimized": int(all(latest_minimized.values())),
        "latest_raw_payload_minimization": latest_minimized,
    }


def _build_summary(
    *,
    mode: str,
    threshold_ms: float,
    component_integrity: dict[str, Any],
    integrity_probe: dict[str, Any],
    latency: dict[str, Any] | None,
    persistence_counts: dict[str, Any],
    iterations_per_route: int,
    warmup_per_route: int,
) -> dict[str, Any]:
    from app.celery_app import celery_app

    return {
        "schema_version": BENCHMARK_SCHEMA_VERSION,
        "phase": "B2.2-P5",
        "mode": mode,
        "timing_boundary": BENCHMARK_TIMING_BOUNDARY,
        "mounted_routes": list(MOUNTED_ROUTES),
        "hard_threshold_p95_ms": float(threshold_ms),
        "iterations_per_route": int(iterations_per_route),
        "warmup_per_route": int(warmup_per_route),
        "task_always_eager": bool(getattr(celery_app.conf, "task_always_eager", False)),
        "component_integrity": component_integrity,
        "integrity_probe": integrity_probe,
        "latency": latency,
        "persistence_counts": persistence_counts,
    }


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    os.environ.setdefault("TESTING", "1")
    os.environ.setdefault("CONTRACT_TESTING", "0")

    cert_url = _configure_paypal_test_certificate_override()
    async_database_url = get_database_url()
    sync_database_url = _normalize_sync_database_url(async_database_url)
    _assert_runtime_tables(sync_database_url)

    tenant_id = uuid4()
    api_key = f"b22_p5_api_key_{uuid4()}"
    api_key_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
    secrets = {
        "shopify_webhook_secret": "shopify_secret",
        "stripe_webhook_secret": "stripe_secret",
        "paypal_webhook_secret": "paypal_secret",
        "woocommerce_webhook_secret": "woo_secret",
    }
    _insert_tenant_with_webhook_secrets(
        sync_database_url=sync_database_url,
        tenant_id=tenant_id,
        api_key_hash=api_key_hash,
        secrets=secrets,
    )

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        integrity_probe = await _run_integrity_probes(
            client=client,
            api_key=api_key,
            secrets=secrets,
            cert_url=cert_url,
        )
        latency = None
        if args.mode == "measure":
            latency = await _run_measurement(
                client=client,
                api_key=api_key,
                secrets=secrets,
                cert_url=cert_url,
                warmup_per_route=int(args.warmup_per_route),
                iterations_per_route=int(args.iterations_per_route),
            )

    component_integrity = _runtime_component_integrity()
    persistence_counts = await _collect_persistence_proof_counts(tenant_id=tenant_id)
    return _build_summary(
        mode=args.mode,
        threshold_ms=float(args.threshold_ms),
        component_integrity=component_integrity,
        integrity_probe=integrity_probe,
        latency=latency,
        persistence_counts=persistence_counts,
        iterations_per_route=int(args.iterations_per_route),
        warmup_per_route=int(args.warmup_per_route),
    )


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="B2.2-P5 mounted webhook composed-path benchmark harness."
    )
    parser.add_argument("--mode", choices=("integrity", "measure"), default="measure")
    parser.add_argument("--threshold-ms", type=float, default=500.0)
    parser.add_argument("--iterations-per-route", type=int, default=25)
    parser.add_argument("--warmup-per-route", type=int, default=5)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv[1:])


def main(argv: list[str]) -> int:
    args = _parse_args(argv)
    try:
        summary = asyncio.run(_run(args))
    except Exception as exc:
        payload = {
            "schema_version": BENCHMARK_SCHEMA_VERSION,
            "phase": "B2.2-P5",
            "mode": getattr(args, "mode", "unknown"),
            "result": "FAIL",
            "error": str(exc),
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(json.dumps(payload, indent=2))
        return 1

    summary["result"] = "PASS"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
