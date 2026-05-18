"""Seed local-only M4 diagnostic fixtures.

The seeded rows are run-scoped synthetic controls used by the ops runbooks.
They are not production data and are safe to remove with clear_diagnostics.py.
"""

from __future__ import annotations

import hashlib
import os
import secrets
import time
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid4, uuid5

import psycopg2.extras

from common import (
    B23_TASK_ID_PREFIX,
    DLQ_TASK_ID_PREFIX,
    TENANT_NAME_PREFIX,
    WEBHOOK_IDEMPOTENCY_PREFIX,
    connect,
    emit,
    insert_dynamic,
    required_columns,
    set_tenant,
    table_columns,
    write_fixture_state,
)


PROVIDERS = ("shopify", "stripe", "paypal", "woocommerce")


def _tenant_insert(cur, *, tenant_id: str, tenant_name: str, api_key: str, webhook_secret: str) -> None:
    columns = table_columns(cur, "tenants")
    required = required_columns(cur, "tenants")
    encryption_key = os.getenv("PLATFORM_TOKEN_ENCRYPTION_KEY", "").strip()
    encryption_key_id = os.getenv("PLATFORM_TOKEN_KEY_ID", "").strip()
    if not encryption_key or not encryption_key_id:
        raise SystemExit(
            "PLATFORM_TOKEN_ENCRYPTION_KEY and PLATFORM_TOKEN_KEY_ID are required for local webhook fixture seeding"
        )

    payload = {
        "id": tenant_id,
        "name": tenant_name,
        "api_key_hash": hashlib.sha256(api_key.encode("utf-8")).hexdigest(),
        "notification_email": f"m4-{tenant_id[:8]}@test.invalid",
    }
    insert_columns: list[str] = []
    value_sql: list[str] = []
    values: list[object] = []

    for column, value in payload.items():
        if column in columns:
            insert_columns.append(column)
            value_sql.append("%s")
            values.append(value)

    for provider in PROVIDERS:
        plaintext_col = f"{provider}_webhook_secret"
        ciphertext_col = f"{provider}_webhook_secret_ciphertext"
        key_id_col = f"{provider}_webhook_secret_key_id"
        if plaintext_col in columns:
            insert_columns.append(plaintext_col)
            value_sql.append("%s")
            values.append(webhook_secret)
        if ciphertext_col in columns:
            insert_columns.append(ciphertext_col)
            value_sql.append("pgp_sym_encrypt(%s, %s)")
            values.extend([webhook_secret, encryption_key])
        if key_id_col in columns:
            insert_columns.append(key_id_col)
            value_sql.append("%s")
            values.append(encryption_key_id)

    missing = sorted(column for column in required if column not in insert_columns)
    if missing:
        raise SystemExit(f"tenants fixture missing required columns: {missing}")

    cur.execute(
        f"""
        INSERT INTO public.tenants ({", ".join(insert_columns)})
        VALUES ({", ".join(value_sql)})
        ON CONFLICT (id) DO UPDATE SET
          name = EXCLUDED.name,
          updated_at = now()
        """,
        values,
    )


def main() -> None:
    run_id = secrets.token_hex(6)
    now = datetime.now(timezone.utc)
    tenant_id = str(uuid4())
    rls_peer_tenant_id = str(uuid4())
    tenant_name = f"{TENANT_NAME_PREFIX} {run_id}"
    rls_peer_tenant_name = f"{TENANT_NAME_PREFIX} RLS Peer {run_id}"
    api_key = f"m4-local-api-key-{secrets.token_urlsafe(18)}"
    webhook_secret = secrets.token_urlsafe(32)
    correlation_id = str(uuid5(NAMESPACE_URL, f"m4-ops-correlation-{run_id}"))
    attribution_event_id = str(uuid4())
    webhook_ingress_identity_id = str(uuid4())
    verdict_id = str(uuid4())
    b23_revenue_event_id = str(uuid4())
    dlq_task_id = f"{DLQ_TASK_ID_PREFIX}-{run_id}"
    rls_peer_dlq_task_id = f"{DLQ_TASK_ID_PREFIX}-rls-peer-{run_id}"
    b23_task_id = f"{B23_TASK_ID_PREFIX}-{run_id}"
    webhook_idempotency_key = f"{WEBHOOK_IDEMPOTENCY_PREFIX}-{run_id}"
    commerce_ref = f"pi_m4diag{run_id}"
    provider_event_ref = f"evt_m4diag{run_id}"

    with connect() as conn:
        with conn.cursor() as cur:
            _tenant_insert(
                cur,
                tenant_id=tenant_id,
                tenant_name=tenant_name,
                api_key=api_key,
                webhook_secret=webhook_secret,
            )
            _tenant_insert(
                cur,
                tenant_id=rls_peer_tenant_id,
                tenant_name=rls_peer_tenant_name,
                api_key=f"m4-local-peer-api-key-{secrets.token_urlsafe(18)}",
                webhook_secret=secrets.token_urlsafe(32),
            )
            set_tenant(cur, tenant_id)

            insert_dynamic(
                cur,
                "attribution_events",
                {
                    "id": attribution_event_id,
                    "tenant_id": tenant_id,
                    "occurred_at": now,
                    "event_timestamp": now,
                    "created_at": now,
                    "updated_at": now,
                    "external_event_id": f"m4-attribution-{run_id}",
                    "correlation_id": correlation_id,
                    "session_id": str(uuid4()),
                    "revenue_cents": 12500,
                    "conversion_value_cents": 12500,
                    "raw_payload": psycopg2.extras.Json({"fixture": "m4_b23_trace", "run_id": run_id}),
                    "idempotency_key": f"m4-attribution-{run_id}",
                    "event_type": "purchase",
                    "channel": "direct",
                    "channel_code": "direct",
                    "utm_source": "direct",
                    "currency": "USD",
                },
                conflict="ON CONFLICT DO NOTHING",
            )

            insert_dynamic(
                cur,
                "worker_failed_jobs",
                {
                    "id": str(uuid4()),
                    "task_id": dlq_task_id,
                    "task_name": "app.tasks.revenue_verification.execute_b23_batch_match_engine",
                    "queue": "b23_match_engine",
                    "worker": "m4-local-fixture",
                    "task_args": psycopg2.extras.Json([tenant_id]),
                    "task_kwargs": psycopg2.extras.Json(
                        {
                            "tenant_id": tenant_id,
                            "correlation_id": correlation_id,
                            "fixture": "m4_dlq_positive",
                        }
                    ),
                    "tenant_id": tenant_id,
                    "error_type": "validation_error",
                    "exception_class": "M4SyntheticDiagnosticError",
                    "error_message": "m4 synthetic failed task fixture",
                    "traceback": "synthetic traceback for local diagnostic fixture only",
                    "retry_count": 2,
                    "status": "pending",
                    "correlation_id": correlation_id,
                    "failed_at": now,
                },
                conflict="ON CONFLICT DO NOTHING",
            )

            set_tenant(cur, rls_peer_tenant_id)
            insert_dynamic(
                cur,
                "worker_failed_jobs",
                {
                    "id": str(uuid4()),
                    "task_id": rls_peer_dlq_task_id,
                    "task_name": "app.tasks.revenue_verification.execute_b23_batch_match_engine",
                    "queue": "b23_match_engine",
                    "worker": "m4-local-fixture",
                    "task_args": psycopg2.extras.Json([rls_peer_tenant_id]),
                    "task_kwargs": psycopg2.extras.Json(
                        {
                            "tenant_id": rls_peer_tenant_id,
                            "correlation_id": correlation_id,
                            "fixture": "m4_rls_peer_positive",
                        }
                    ),
                    "tenant_id": rls_peer_tenant_id,
                    "error_type": "validation_error",
                    "exception_class": "M4SyntheticDiagnosticError",
                    "error_message": "m4 synthetic peer failed task fixture",
                    "traceback": "synthetic traceback for local RLS diagnostic fixture only",
                    "retry_count": 1,
                    "status": "pending",
                    "correlation_id": correlation_id,
                    "failed_at": now,
                },
                conflict="ON CONFLICT DO NOTHING",
            )
            set_tenant(cur, tenant_id)

            insert_dynamic(
                cur,
                "webhook_ingress_identities",
                {
                    "id": webhook_ingress_identity_id,
                    "tenant_id": tenant_id,
                    "event_id": attribution_event_id,
                    "provider": "stripe",
                    "provider_native_event_reference": provider_event_ref,
                    "provider_native_commerce_reference": commerce_ref,
                    "normalized_commerce_reference_kind": "stripe_payment_intent_id",
                    "normalized_commerce_reference_value": commerce_ref,
                    "verified_amount_minor": 12500,
                    "verified_amount_currency": "USD",
                    "verified_amount_scale": 2,
                    "event_timestamp": now,
                    "idempotency_key": f"m4-b23-ingress-{run_id}",
                    "verified_commerce_ingress_state": "authenticity_verified",
                    "verified_at": now,
                    "created_at": now,
                    "updated_at": now,
                },
                conflict="ON CONFLICT DO NOTHING",
            )

            insert_dynamic(
                cur,
                "b23_match_task_dispatches",
                {
                    "id": str(uuid4()),
                    "tenant_id": tenant_id,
                    "webhook_ingress_identity_id": webhook_ingress_identity_id,
                    "task_id": b23_task_id,
                    "task_name": "app.tasks.revenue_verification.execute_b23_batch_match_engine",
                    "queue": "b23_match_engine",
                    "routing_key": "b23_match_engine.task",
                    "correlation_id": correlation_id,
                    "provider": "stripe",
                    "provider_native_event_reference": provider_event_ref,
                    "provider_native_commerce_reference": commerce_ref,
                    "normalized_commerce_reference_value": commerce_ref,
                    "status": "dispatched",
                    "dispatched_at": now,
                    "created_at": now,
                    "updated_at": now,
                },
                conflict="ON CONFLICT DO NOTHING",
            )

            insert_dynamic(
                cur,
                "b23_match_verdicts",
                {
                    "id": verdict_id,
                    "tenant_id": tenant_id,
                    "attribution_event_id": attribution_event_id,
                    "webhook_ingress_identity_id": webhook_ingress_identity_id,
                    "provider": "stripe",
                    "canonical_commerce_reference": commerce_ref,
                    "provider_native_event_reference": provider_event_ref,
                    "provider_native_commerce_reference": commerce_ref,
                    "status": "matched_confirmed",
                    "match_quality": "high",
                    "attributed_amount_minor": 12500,
                    "verified_amount_minor": 12500,
                    "expected_amount_minor": 12500,
                    "captured_amount_minor": 12500,
                    "canonical_expected_gross_amount_minor": 12500,
                    "canonical_captured_gross_amount_minor": 12500,
                    "canonical_net_verified_amount_minor": 12500,
                    "discrepancy_amount_minor": 0,
                    "discrepancy_ratio_bps": 0,
                    "discrepancy_band": "exact",
                    "currency_code": "USD",
                    "confirmed_at": now,
                    "pending_since": now,
                    "last_transition_at": now,
                    "created_at": now,
                    "updated_at": now,
                },
                conflict="ON CONFLICT DO NOTHING",
            )

            insert_dynamic(
                cur,
                "b23_revenue_events",
                {
                    "id": b23_revenue_event_id,
                    "tenant_id": tenant_id,
                    "match_verdict_id": verdict_id,
                    "webhook_ingress_identity_id": webhook_ingress_identity_id,
                    "provider": "stripe",
                    "provider_native_event_reference": provider_event_ref,
                    "provider_native_commerce_reference": commerce_ref,
                    "canonical_commerce_reference": commerce_ref,
                    "event_type": "payment_capture",
                    "amount_minor": 12500,
                    "captured_amount_minor": 12500,
                    "currency_code": "USD",
                    "event_occurred_at": now,
                    "recorded_at": now,
                    "created_at": now,
                    "updated_at": now,
                },
                conflict="ON CONFLICT DO NOTHING",
            )

    state = {
        "run_id": run_id,
        "created_epoch": int(time.time()),
        "tenant_id": tenant_id,
        "rls_peer_tenant_id": rls_peer_tenant_id,
        "tenant_name": tenant_name,
        "rls_peer_tenant_name": rls_peer_tenant_name,
        "api_key": api_key,
        "stripe_webhook_secret": webhook_secret,
        "correlation_id": correlation_id,
        "dlq_task_id": dlq_task_id,
        "rls_peer_dlq_task_id": rls_peer_dlq_task_id,
        "b23_task_id": b23_task_id,
        "attribution_event_id": attribution_event_id,
        "webhook_ingress_identity_id": webhook_ingress_identity_id,
        "b23_match_verdict_id": verdict_id,
        "webhook_idempotency_key": webhook_idempotency_key,
        "stripe_payment_intent_id": f"pi_m4replay{run_id}",
        "stripe_event_id": f"evt_m4replay{run_id}",
    }
    write_fixture_state(state)
    emit(
        {
            "status": "seeded",
            "fixture_class": "local_only_run_scoped",
            "tenant_id": tenant_id,
            "dlq_task_id": dlq_task_id,
            "b23_task_id": b23_task_id,
            "webhook_fixture": "m4-webhook-valid/tampered/duplicate",
        }
    )


if __name__ == "__main__":
    main()
