from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
import jwt
import pytest
import yaml
from jsonschema import Draft202012Validator, ValidationError
from sqlalchemy import create_engine, text

from app.db.session import engine as async_engine
from app.db.session import set_tenant_guc_async
from app.core.secrets import get_database_url
from app.services.revenue_reconciliation import (
    PlatformClaim,
    RevenueReconciliationService,
    VerifiedRevenue,
)


@dataclass(frozen=True)
class _TenantFixture:
    tenant_id: UUID
    tenant_key: str
    api_key_hash: str
    stripe_secret: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _artifact_dir() -> Path:
    explicit = os.getenv("B07_P8_ARTIFACT_DIR")
    if explicit:
        path = Path(explicit)
    else:
        path = _repo_root() / "artifacts" / "b07-p8"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _runtime_sync_db_url() -> str:
    explicit = os.getenv("B07_P8_RUNTIME_DATABASE_URL")
    if explicit:
        return explicit
    runtime = get_database_url()
    if runtime.startswith("postgresql+asyncpg://"):
        return runtime.replace("postgresql+asyncpg://", "postgresql://", 1)
    return runtime


def _api_base_url() -> str:
    return os.getenv("E2E_API_BASE_URL", "http://127.0.0.1:8000")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_openapi(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Invalid OpenAPI document: {path}")
    return payload


def _resolve_local_refs(value: Any, doc: dict[str, Any]) -> Any:
    if isinstance(value, dict):
        ref = value.get("$ref")
        if isinstance(ref, str):
            if not ref.startswith("#/"):
                raise RuntimeError(f"Only local refs are supported in runtime validator: {ref}")
            target: Any = doc
            for part in ref[2:].split("/"):
                target = target[part]
            merged = dict(target)
            for key, item in value.items():
                if key != "$ref":
                    merged[key] = item
            return _resolve_local_refs(merged, doc)
        return {key: _resolve_local_refs(item, doc) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_local_refs(item, doc) for item in value]
    return value


def _schema_for_response(
    doc: dict[str, Any],
    *,
    path: str,
    method: str,
    status_code: int,
    content_type: str = "application/json",
) -> dict[str, Any]:
    operation = doc["paths"][path][method.lower()]
    responses = operation["responses"]
    response_obj = responses.get(str(status_code))
    if response_obj is None:
        raise RuntimeError(f"Missing response {status_code} for {method.upper()} {path}")
    content = response_obj.get("content") or {}
    if content_type not in content:
        raise RuntimeError(
            f"Missing content type {content_type} for {method.upper()} {path} status {status_code}"
        )
    raw_schema = content[content_type]["schema"]
    resolved = _resolve_local_refs(raw_schema, doc)
    if not isinstance(resolved, dict):
        raise RuntimeError("Resolved schema must be an object")
    return resolved


def _validate_payload(schema: dict[str, Any], payload: Any) -> None:
    Draft202012Validator(schema).validate(payload)


def _seed_tenant(runtime_db_url: str) -> _TenantFixture:
    tenant_id = uuid4()
    tenant_key = f"b07_p8_tenant_key_{tenant_id.hex[:10]}"
    api_key_hash = hashlib.sha256(tenant_key.encode("utf-8")).hexdigest()
    stripe_secret = "whsec_b07_p8_stripe"
    now = datetime.now(timezone.utc)
    engine = create_engine(runtime_db_url)
    with engine.begin() as conn:
        available = set(
            conn.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'tenants'
                    """
                )
            ).scalars()
        )
        required = set(
            conn.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'tenants'
                      AND is_nullable = 'NO'
                      AND column_default IS NULL
                      AND (is_identity IS NULL OR is_identity = 'NO')
                    """
                )
            ).scalars()
        )
    payload = {
        "id": str(tenant_id),
        "name": f"B07 P8 Tenant {tenant_id.hex[:8]}",
        "api_key_hash": api_key_hash,
        "notification_email": f"b07-p8-{tenant_id.hex[:8]}@example.invalid",
        "shopify_webhook_secret": "phase8_shopify_secret",
        "stripe_webhook_secret": stripe_secret,
        "paypal_webhook_secret": "phase8_paypal_secret",
        "woocommerce_webhook_secret": "phase8_woo_secret",
        "created_at": now,
        "updated_at": now,
    }
    insert_cols = [col for col in payload if col in available]
    missing = sorted(col for col in required if col not in payload)
    if missing:
        raise RuntimeError(f"Missing required tenant columns: {', '.join(missing)}")
    if "id" not in insert_cols:
        insert_cols.insert(0, "id")
    if "name" not in insert_cols:
        insert_cols.append("name")
    placeholders = ", ".join(f":{col}" for col in insert_cols)
    # RAW_SQL_ALLOWLIST: phase8 topology probe seeds a tenant fixture directly.
    sql = text(
        f"INSERT INTO tenants ({', '.join(insert_cols)}) VALUES ({placeholders})"
    )
    with engine.begin() as conn:
        conn.execute(sql, payload)
    return _TenantFixture(
        tenant_id=tenant_id,
        tenant_key=tenant_key,
        api_key_hash=api_key_hash,
        stripe_secret=stripe_secret,
    )


def _sign_stripe(body: str, secret: str, ts: int) -> str:
    signed_payload = f"{ts}.{body}".encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


def _build_auth_token(tenant_id: UUID, user_id: UUID) -> str:
    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "user_id": str(user_id),
        "tenant_id": str(tenant_id),
        "iss": os.getenv("AUTH_JWT_ISSUER", "https://issuer.skeldir.test"),
        "aud": os.getenv("AUTH_JWT_AUDIENCE", "skeldir-api"),
        "iat": now,
        "exp": now + 3600,
    }
    secret = os.getenv("AUTH_JWT_SECRET", "e2e-secret")
    algorithm = os.getenv("AUTH_JWT_ALGORITHM", "HS256")
    return jwt.encode(payload, secret, algorithm=algorithm)


def _wait_for_count(
    runtime_db_url: str,
    *,
    tenant_id: UUID,
    query: str,
    params: dict[str, Any],
    expected_min: int = 1,
    timeout_s: float = 60.0,
) -> int:
    engine = create_engine(runtime_db_url)
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        with engine.begin() as conn:
            conn.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
                {"tenant_id": str(tenant_id)},
            )
            count = int(conn.execute(text(query), params).scalar_one())
            if count >= expected_min:
                return count
        time.sleep(0.5)
    raise AssertionError(f"Timed out waiting for count >= {expected_min}: {query}")


def _latest_recompute_status(runtime_db_url: str, tenant_id: UUID) -> str | None:
    engine = create_engine(runtime_db_url)
    with engine.begin() as conn:
        conn.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
            {"tenant_id": str(tenant_id)},
        )
        row = conn.execute(
            text(
                """
                SELECT status
                FROM attribution_recompute_jobs
                WHERE tenant_id = :tenant_id
                ORDER BY updated_at DESC
                LIMIT 1
                """
            ),
            {"tenant_id": str(tenant_id)},
        ).first()
        if row is None:
            return None
        return str(row[0])


def _wait_for_recompute_status(
    runtime_db_url: str,
    tenant_id: UUID,
    timeout_s: float = 60.0,
) -> str | None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        status = _latest_recompute_status(runtime_db_url, tenant_id)
        if status is not None:
            return status
        time.sleep(0.5)
    return None


async def _write_verified_revenue(tenant_id: UUID, order_id: str) -> dict[str, Any]:
    svc = RevenueReconciliationService()
    claims = [
        PlatformClaim(source="meta", amount_cents=2500, claim_timestamp=datetime.now(timezone.utc)),
        PlatformClaim(source="google", amount_cents=2500, claim_timestamp=datetime.now(timezone.utc)),
    ]
    verified = VerifiedRevenue(
        source="stripe",
        amount_cents=5000,
        verification_timestamp=datetime.now(timezone.utc),
        transaction_id=f"txn_b07_p8_{uuid4().hex[:10]}",
    )
    async with async_engine.begin() as conn:
        await set_tenant_guc_async(conn, tenant_id, local=True)
        result = await svc.reconcile_order(
            conn=conn,
            tenant_id=tenant_id,
            order_id=order_id,
            platform_claims=claims,
            verified_revenue=verified,
        )
    return {
        "order_id": result.order_id,
        "claimed_total_cents": int(result.claimed_total_cents),
        "verified_total_cents": int(result.verified_total_cents),
        "ghost_revenue_cents": int(result.ghost_revenue_cents),
        "discrepancy_bps": int(result.discrepancy_bps),
        "verification_source": result.verification_source,
        "ledger_id": str(result.ledger_id),
    }


def test_b07_p8_three_topologies_contract_fidelity_and_non_vacuous_controls() -> None:
    runtime_db = _runtime_sync_db_url()
    api_base_url = _api_base_url()
    artifact_dir = _artifact_dir()

    reconciliation_spec_path = (
        _repo_root() / "api-contracts" / "dist" / "openapi" / "v1" / "reconciliation.bundled.yaml"
    )
    attribution_spec_path = (
        _repo_root() / "api-contracts" / "dist" / "openapi" / "v1" / "attribution.bundled.yaml"
    )
    reconciliation_doc = _load_openapi(reconciliation_spec_path)
    attribution_doc = _load_openapi(attribution_spec_path)

    tenant = _seed_tenant(runtime_db)
    user_id = uuid4()
    token = _build_auth_token(tenant.tenant_id, user_id)

    created = int(time.time())
    order_external_id = f"pi_b07_p8_{uuid4().hex[:10]}"
    webhook_payload = {
        "id": f"evt_b07_p8_{uuid4().hex[:8]}",
        "created": created,
        "data": {
            "object": {
                "id": order_external_id,
                "amount": 5000,
                "currency": "usd",
                "metadata": {"order_id": f"order_b07_p8_{uuid4().hex[:10]}"},
            }
        },
    }
    webhook_body = json.dumps(webhook_payload, separators=(",", ":"))
    stripe_signature = _sign_stripe(webhook_body, tenant.stripe_secret, created)

    webhook_response = httpx.post(
        f"{api_base_url}/api/webhooks/stripe/payment_intent/succeeded",
        headers={
            "Content-Type": "application/json",
            "X-Skeldir-Tenant-Key": tenant.tenant_key,
            "Stripe-Signature": stripe_signature,
        },
        content=webhook_body.encode("utf-8"),
        timeout=20.0,
    )
    assert webhook_response.status_code == 200, webhook_response.text
    webhook_data = webhook_response.json()
    assert webhook_data.get("status") == "success"

    event_count = _wait_for_count(
        runtime_db,
        tenant_id=tenant.tenant_id,
        query=(
            "SELECT COUNT(*) FROM attribution_events "
            "WHERE tenant_id = :tenant_id AND external_event_id = :external_event_id"
        ),
        params={"tenant_id": str(tenant.tenant_id), "external_event_id": order_external_id},
    )
    recompute_status = _wait_for_recompute_status(runtime_db, tenant.tenant_id)
    if recompute_status is not None:
        assert recompute_status in {"running", "succeeded", "failed"}
        assert recompute_status != "failed"

    order_id = f"order_b07_p8_{uuid4().hex[:10]}"
    reconciliation_result = asyncio.run(_write_verified_revenue(tenant.tenant_id, order_id))

    headers = {
        "Authorization": f"Bearer {token}",
        "X-Correlation-ID": str(uuid4()),
    }
    sync_response = httpx.post(
        f"{api_base_url}/api/reconciliation/sync",
        headers=headers,
        json={"platforms": ["stripe"], "full_sync": False},
        timeout=20.0,
    )
    assert sync_response.status_code == 202, sync_response.text
    sync_payload = sync_response.json()
    sync_schema = _schema_for_response(
        reconciliation_doc,
        path="/api/reconciliation/sync",
        method="post",
        status_code=202,
    )
    _validate_payload(sync_schema, sync_payload)

    status_response = httpx.get(
        f"{api_base_url}/api/reconciliation/status",
        headers={"Authorization": f"Bearer {token}", "X-Correlation-ID": str(uuid4())},
        timeout=20.0,
    )
    assert status_response.status_code == 200, status_response.text
    status_payload = status_response.json()
    status_schema = _schema_for_response(
        reconciliation_doc,
        path="/api/reconciliation/status",
        method="get",
        status_code=200,
    )
    _validate_payload(status_schema, status_payload)

    platform_response = httpx.get(
        f"{api_base_url}/api/reconciliation/platform/stripe",
        headers={"Authorization": f"Bearer {token}", "X-Correlation-ID": str(uuid4())},
        timeout=20.0,
    )
    assert platform_response.status_code == 200, platform_response.text
    platform_payload = platform_response.json()
    platform_schema = _schema_for_response(
        reconciliation_doc,
        path="/api/reconciliation/platform/{platform_id}",
        method="get",
        status_code=200,
    )
    _validate_payload(platform_schema, platform_payload)
    assert platform_payload["platform_name"] == "Stripe"
    assert float(platform_payload["revenue_verified"]) >= 50.0

    realtime_response = httpx.get(
        f"{api_base_url}/api/attribution/revenue/realtime",
        headers={"Authorization": f"Bearer {token}", "X-Correlation-ID": str(uuid4())},
        timeout=20.0,
    )
    assert realtime_response.status_code in {200, 503}, realtime_response.text
    if realtime_response.status_code == 200:
        realtime_schema = _schema_for_response(
            attribution_doc,
            path="/api/attribution/revenue/realtime",
            method="get",
            status_code=200,
        )
        _validate_payload(realtime_schema, realtime_response.json())

    # Non-vacuous negative controls for contract validator: missing required
    # field and wrong type must fail.
    missing_required = dict(status_payload)
    missing_required.pop("overall_status", None)
    with pytest.raises(ValidationError):
        _validate_payload(status_schema, missing_required)

    wrong_type = dict(status_payload)
    wrong_type["platforms"] = "invalid"
    with pytest.raises(ValidationError):
        _validate_payload(status_schema, wrong_type)

    engine = create_engine(runtime_db)
    with engine.begin() as conn:
        conn.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
            {"tenant_id": str(tenant.tenant_id)},
        )
        same_tenant_count = int(
            conn.execute(
                text(
                    "SELECT COUNT(*) FROM attribution_events WHERE external_event_id = :external_event_id"
                ),
                {"external_event_id": order_external_id},
            ).scalar_one()
        )
        conn.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
            {"tenant_id": str(uuid4())},
        )
        cross_tenant_count = int(
            conn.execute(
                text(
                    "SELECT COUNT(*) FROM attribution_events WHERE external_event_id = :external_event_id"
                ),
                {"external_event_id": order_external_id},
            ).scalar_one()
        )
    assert same_tenant_count >= 1
    assert cross_tenant_count == 0

    probe = {
        "tenant_id": str(tenant.tenant_id),
        "user_id": str(user_id),
        "openapi_spec_sha256": {
            "reconciliation": _sha256_file(reconciliation_spec_path),
            "attribution": _sha256_file(attribution_spec_path),
        },
        "negative_controls": {
            "missing_required_field_rejected": True,
            "wrong_type_rejected": True,
        },
        "webhook_response": webhook_data,
        "event_count": event_count,
        "recompute_status": recompute_status,
        "reconciliation_result": reconciliation_result,
        "sync_response": sync_payload,
        "status_response": status_payload,
        "platform_response": platform_payload,
        "attribution_realtime_status_code": realtime_response.status_code,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    (artifact_dir / "p8_topology_probe.json").write_text(
        json.dumps(probe, indent=2, sort_keys=True),
        encoding="utf-8",
    )
