import hmac
import hashlib
import json
import os
import signal
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import create_engine, text


@dataclass(frozen=True)
class _WebhookFixture:
    tenant_id: UUID
    tenant_key: str
    api_key_hash: str
    stripe_secret: str


def _repo_root() -> Path:
    # backend/tests/integration/... -> backend -> repo root
    return Path(__file__).resolve().parents[3]


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is required for B0.5.7-P3 integration tests")
    return value


def _runtime_sync_db_url() -> str:
    explicit = os.getenv("B057_P3_RUNTIME_DATABASE_URL")
    if explicit:
        return explicit
    runtime_url = _require_env("DATABASE_URL")
    if runtime_url.startswith("postgresql+asyncpg://"):
        return runtime_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return runtime_url


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_ready(base_url: str, timeout_s: float = 30.0) -> None:
    deadline = time.time() + timeout_s
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            res = httpx.get(f"{base_url}/health/ready", timeout=1.0)
            if res.status_code == 200:
                return
        except Exception as exc:  # pragma: no cover - best-effort polling
            last_error = exc
        time.sleep(0.25)
    raise RuntimeError(f"API never became ready; last_error={last_error}")


def _seed_tenant(admin_db_url: str) -> _WebhookFixture:
    tenant_id = uuid4()
    tenant_key = f"b057_p3_test_tenant_key_{tenant_id.hex[:8]}"
    api_key_hash = hashlib.sha256(tenant_key.encode("utf-8")).hexdigest()
    stripe_secret = "whsec_b057_p3_stripe"

    # Keep the value synthetic/non-human to avoid PII in CI artifacts.
    notification_email = f"tenant-{tenant_id.hex[:8]}@example.invalid"

    engine = create_engine(admin_db_url)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO public.tenants (
                  id,
                  name,
                  api_key_hash,
                  notification_email,
                  stripe_webhook_secret
                )
                VALUES (
                  :id,
                  :name,
                  :api_key_hash,
                  :notification_email,
                  :stripe_webhook_secret
                )
                """
            ),
            {
                "id": str(tenant_id),
                "name": "B057 P3 Integration Tenant",
                "api_key_hash": api_key_hash,
                "notification_email": notification_email,
                "stripe_webhook_secret": stripe_secret,
            },
        )

    return _WebhookFixture(
        tenant_id=tenant_id,
        tenant_key=tenant_key,
        api_key_hash=api_key_hash,
        stripe_secret=stripe_secret,
    )


@pytest.fixture(scope="session")
def b057_p3_fixture() -> _WebhookFixture:
    admin_db_url = _require_env("B057_P3_ADMIN_DATABASE_URL")
    return _seed_tenant(admin_db_url)


@pytest.fixture(scope="session")
def api_base_url(b057_p3_fixture: _WebhookFixture) -> str:
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"

    env = os.environ.copy()
    env.setdefault("ENVIRONMENT", "test")

    backend_dir = _repo_root() / "backend"
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "info",
        ],
        cwd=str(backend_dir),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        _wait_ready(base_url)
        yield base_url
    finally:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:  # pragma: no cover
            proc.kill()
            proc.wait(timeout=10)


def test_b057_p3_least_privilege_tenants_denied(b057_p3_fixture: _WebhookFixture):
    engine = create_engine(_runtime_sync_db_url())
    with engine.begin() as conn:
        with pytest.raises(Exception) as excinfo:
            conn.execute(text("SELECT id FROM public.tenants LIMIT 1"))
        assert "permission denied" in str(excinfo.value).lower()


def test_b057_p3_mediated_resolution_callable(b057_p3_fixture: _WebhookFixture):
    engine = create_engine(_runtime_sync_db_url())
    with engine.begin() as conn:
        secret = conn.execute(
            text(
                "SELECT stripe_webhook_secret "
                "FROM security.resolve_tenant_webhook_secrets(:api_key_hash)"
            ),
            {"api_key_hash": b057_p3_fixture.api_key_hash},
        ).scalar_one()
        assert secret == b057_p3_fixture.stripe_secret


def test_b057_p3_webhook_e2e_persists_under_runtime_identity(
    api_base_url: str, b057_p3_fixture: _WebhookFixture
):
    created = int(time.time())
    payload = {
        "id": "evt_b057_p3",
        "created": created,
        "data": {"object": {"id": "pi_b057_p3", "amount": 1234, "currency": "usd"}},
    }
    body = json.dumps(payload, separators=(",", ":"))
    signed_payload = f"{created}.{body}".encode("utf-8")
    sig = hmac.new(
        b057_p3_fixture.stripe_secret.encode("utf-8"),
        signed_payload,
        hashlib.sha256,
    ).hexdigest()
    stripe_header = f"t={created},v1={sig}"

    res = httpx.post(
        f"{api_base_url}/api/webhooks/stripe/payment_intent/succeeded",
        headers={
            "Content-Type": "application/json",
            "X-Skeldir-Tenant-Key": b057_p3_fixture.tenant_key,
            "Stripe-Signature": stripe_header,
        },
        content=body.encode(),
        timeout=10.0,
    )
    assert res.status_code == 200, res.text
    assert res.json().get("status") == "success"

    # Persistence proof: event row exists and is tenant-scoped.
    engine = create_engine(_runtime_sync_db_url())
    with engine.begin() as conn:
        conn.execute(
            text("SELECT set_config('app.current_tenant_id', :tid, false)"),
            {"tid": str(b057_p3_fixture.tenant_id)},
        )
        count = conn.execute(
            text(
                "SELECT COUNT(*) FROM public.attribution_events "
                "WHERE external_event_id = 'pi_b057_p3'"
            )
        ).scalar_one()
        assert int(count) >= 1

    # Invalid signature -> deterministic 401 (never 500)
    res2 = httpx.post(
        f"{api_base_url}/api/webhooks/stripe/payment_intent/succeeded",
        headers={
            "Content-Type": "application/json",
            "X-Skeldir-Tenant-Key": b057_p3_fixture.tenant_key,
            "Stripe-Signature": "t=0,v1=deadbeef",
        },
        content=body.encode(),
        timeout=10.0,
    )
    assert res2.status_code == 401

    # Missing tenant key -> deterministic 401 (never 500)
    res3 = httpx.post(
        f"{api_base_url}/api/webhooks/stripe/payment_intent/succeeded",
        headers={
            "Content-Type": "application/json",
            "Stripe-Signature": "t=0,v1=deadbeef",
        },
        content=body.encode(),
        timeout=10.0,
    )
    assert res3.status_code == 401

    # Unknown tenant key -> deterministic 401 (never 500)
    res4 = httpx.post(
        f"{api_base_url}/api/webhooks/stripe/payment_intent/succeeded",
        headers={
            "Content-Type": "application/json",
            "X-Skeldir-Tenant-Key": "unknown_tenant_key",
            "Stripe-Signature": "t=0,v1=deadbeef",
        },
        content=body.encode(),
        timeout=10.0,
    )
    assert res4.status_code == 401

    # Malformed JSON with valid signature must route to DLQ (never 422 drift).
    bad_key = f"b057_p3_bad_{uuid4().hex[:12]}"
    malformed_body = b'{"id":"evt_bad","created":'
    signed_malformed = f"{created}.{malformed_body.decode('utf-8')}".encode("utf-8")
    malformed_sig = hmac.new(
        b057_p3_fixture.stripe_secret.encode("utf-8"),
        signed_malformed,
        hashlib.sha256,
    ).hexdigest()

    res5 = httpx.post(
        f"{api_base_url}/api/webhooks/stripe/payment_intent/succeeded",
        headers={
            "Content-Type": "application/json",
            "X-Skeldir-Tenant-Key": b057_p3_fixture.tenant_key,
            "Stripe-Signature": f"t={created},v1={malformed_sig}",
            "X-Idempotency-Key": bad_key,
        },
        content=malformed_body,
        timeout=10.0,
    )
    assert res5.status_code == 200, res5.text
    malformed_payload = res5.json()
    assert malformed_payload.get("status") == "dlq_routed"
    assert malformed_payload.get("dead_event_id")

    with engine.begin() as conn:
        conn.execute(
            text("SELECT set_config('app.current_tenant_id', :tid, false)"),
            {"tid": str(b057_p3_fixture.tenant_id)},
        )
        dlq_count = conn.execute(
            text(
                "SELECT COUNT(*) FROM public.dead_events "
                "WHERE raw_payload->>'idempotency_key' = :key"
            ),
            {"key": bad_key},
        ).scalar_one()
        canonical_count = conn.execute(
            text(
                "SELECT COUNT(*) FROM public.attribution_events "
                "WHERE idempotency_key = :key"
            ),
            {"key": bad_key},
        ).scalar_one()

    assert int(dlq_count) >= 1
    assert int(canonical_count) == 0

    # PII payload with valid signature must route to DLQ without 500 and without PII persistence.
    pii_key = f"b057_p3_pii_{uuid4().hex[:12]}"
    pii_payload = {
        "id": "evt_b057_p3_pii",
        "created": created,
        "email": "pii_user@test.invalid",
        "ip_address": "203.0.113.99",
        "data": {
            "object": {
                "id": "pi_b057_p3_pii",
                "amount": 4321,
                "currency": "usd",
                "receipt_email": "receipt@test.invalid",
                "billing_details": {"email": "bill@test.invalid"},
            }
        },
    }
    pii_body = json.dumps(pii_payload, separators=(",", ":")).encode("utf-8")
    pii_signed_payload = f"{created}.{pii_body.decode('utf-8')}".encode("utf-8")
    pii_sig = hmac.new(
        b057_p3_fixture.stripe_secret.encode("utf-8"),
        pii_signed_payload,
        hashlib.sha256,
    ).hexdigest()

    res6 = httpx.post(
        f"{api_base_url}/api/webhooks/stripe/payment_intent/succeeded",
        headers={
            "Content-Type": "application/json",
            "X-Skeldir-Tenant-Key": b057_p3_fixture.tenant_key,
            "Stripe-Signature": f"t={created},v1={pii_sig}",
            "X-Idempotency-Key": pii_key,
        },
        content=pii_body,
        timeout=10.0,
    )
    assert res6.status_code == 200, res6.text
    pii_result = res6.json()
    assert pii_result.get("status") == "dlq_routed"
    assert pii_result.get("dead_event_id")

    with engine.begin() as conn:
        conn.execute(
            text("SELECT set_config('app.current_tenant_id', :tid, false)"),
            {"tid": str(b057_p3_fixture.tenant_id)},
        )
        pii_dlq_count = conn.execute(
            text(
                "SELECT COUNT(*) FROM public.dead_events "
                "WHERE raw_payload->>'idempotency_key' = :key"
            ),
            {"key": pii_key},
        ).scalar_one()
        pii_canonical_count = conn.execute(
            text(
                "SELECT COUNT(*) FROM public.attribution_events "
                "WHERE idempotency_key = :key"
            ),
            {"key": pii_key},
        ).scalar_one()
        pii_key_hits = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.dead_events
                WHERE raw_payload->>'idempotency_key' = :key
                  AND (
                    jsonb_path_exists(raw_payload, '$.**.email')
                    OR jsonb_path_exists(raw_payload, '$.**.receipt_email')
                    OR jsonb_path_exists(raw_payload, '$.**.ip_address')
                  )
                """
            ),
            {"key": pii_key},
        ).scalar_one()

    assert int(pii_dlq_count) >= 1
    assert int(pii_canonical_count) == 0
    assert int(pii_key_hits) == 0
