from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import bcrypt
import httpx
import jwt
import pytest
from sqlalchemy import create_engine, text

from app.celery_app import celery_app
from app.core.config import settings
from app.core.secrets import reset_crypto_secret_caches_for_testing
from app.tasks.authority import AUTHORITY_ENVELOPE_HEADER, SessionAuthorityEnvelope
from app.testing.jwt_rs256 import TEST_PUBLIC_KEY_PEM, private_ring_payload, public_ring_payload
from app.webhooks.signatures import verify_stripe_signature
from tests.helpers.webhook_secret_seed import (
    enrich_params_with_webhook_secrets,
    tenant_insert_statement,
)

pytestmark = pytest.mark.asyncio

_FORBIDDEN_ERROR_SUBSTRINGS = (
    "unknown kid",
    "jwks",
    "user not found",
    "signature",
    "shopify",
    "stripe",
    "paypal",
    "woocommerce",
    "invalidtokenerror",
    "pyjwterror",
    "invalid_signature",
    "invalid_tenant_key",
)

_EXPECTED_PROBLEM_KEYS = {
    "type",
    "title",
    "status",
    "detail",
    "instance",
    "correlation_id",
    "timestamp",
    "code",
}


@dataclass(frozen=True)
class _SeededScenario:
    tenant_a: UUID
    tenant_b: UUID
    tenant_a_key: str
    tenant_b_key: str
    tenant_a_stripe_secret: str
    shared_user_id: UUID
    tenant_b_only_user_id: UUID
    email: str
    password: str
    revenue_a_total: float
    revenue_b_total: float


@dataclass
class _SubprocessHandle:
    proc: subprocess.Popen[str]
    log_path: Path
    lines: list[str]
    _thread: threading.Thread
    _stream: Any

    def terminate(self) -> None:
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=20)
        if self._stream is not None:
            try:
                self._stream.close()
            except Exception:
                pass


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _backend_root() -> Path:
    return _repo_root() / "backend"


def _artifacts_dir() -> Path:
    root = _repo_root() / "artifacts" / "b12_p9"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _prepare_prometheus_multiproc_dir() -> Path:
    multiproc_dir = (_artifacts_dir() / "prometheus_multiproc").resolve()
    multiproc_dir.mkdir(parents=True, exist_ok=True)
    for shard in multiproc_dir.glob("*.db"):
        shard.unlink()
    return multiproc_dir


def _normalize_sync_url(value: str) -> str:
    if value.startswith("postgresql+asyncpg://"):
        return value.replace("postgresql+asyncpg://", "postgresql://", 1)
    return value


def _runtime_sync_database_url() -> str:
    value = os.environ.get("DATABASE_URL")
    if not value:
        raise RuntimeError("DATABASE_URL is required for B1.2-P9 system proof test")
    return _normalize_sync_url(value)


def _seed_sync_database_url() -> str:
    migration = os.environ.get("MIGRATION_DATABASE_URL")
    if migration:
        return _normalize_sync_url(migration)
    return _runtime_sync_database_url()


def _with_sql_engine(database_url: str | None = None):
    return create_engine(database_url or _runtime_sync_database_url())


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _stripe_signature(raw_body: bytes, secret: str, *, valid: bool) -> str:
    timestamp = str(int(time.time()))
    signed_payload = f"{timestamp}.{raw_body.decode('utf-8')}".encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    if not valid:
        digest = "0" * len(digest)
    return f"t={timestamp},v1={digest}"


def _decode_access_token(access_token: str) -> dict[str, Any]:
    return jwt.decode(
        access_token,
        TEST_PUBLIC_KEY_PEM,
        algorithms=["RS256"],
        issuer="https://issuer.skeldir.test",
        audience="skeldir-api",
    )


def _parse_refresh_token(token: str) -> tuple[UUID, UUID, str]:
    parts = token.split(".")
    assert len(parts) == 3
    return UUID(parts[0]), UUID(parts[1]), parts[2]


def _assert_non_leaky_problem(response: httpx.Response, *, expected_status: int) -> dict[str, Any]:
    assert response.status_code == expected_status, response.text
    assert response.headers.get("content-type", "").startswith("application/problem+json")
    body = response.json()
    assert set(body.keys()) == _EXPECTED_PROBLEM_KEYS
    assert body["status"] == expected_status
    if expected_status == 401:
        assert body["code"] == "AUTH_UNAUTHORIZED"
    if expected_status == 403:
        assert body["code"] == "AUTH_FORBIDDEN"
    UUID(str(body["correlation_id"]))
    lowered = json.dumps(body, sort_keys=True).lower()
    for forbidden in _FORBIDDEN_ERROR_SUBSTRINGS:
        assert forbidden not in lowered, f"forbidden error substring leaked: {forbidden}"
    return body


def _wait_for_worker_ready(lines: list[str], proc: subprocess.Popen[str], timeout_s: float = 90.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if any("ready." in line for line in lines):
            return
        if proc.poll() is not None:
            raise RuntimeError("Celery worker exited before readiness")
        time.sleep(0.2)
    raise RuntimeError("Timed out waiting for Celery worker readiness")


def _wait_for_api_ready(base_url: str, timeout_s: float = 60.0) -> None:
    deadline = time.time() + timeout_s
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            response = httpx.get(f"{base_url}/health/ready", timeout=1.0)
            if response.status_code == 200:
                return
        except Exception as exc:  # pragma: no cover - readiness polling only
            last_error = exc
        time.sleep(0.2)
    raise RuntimeError(f"API readiness timeout: {last_error}")


def _start_logged_process(cmd: list[str], *, env: dict[str, str], cwd: Path, log_path: Path) -> _SubprocessHandle:
    lines: list[str] = []
    stream = log_path.open("w", encoding="utf-8")
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    def _reader() -> None:
        if proc.stdout is None:
            return
        for raw in proc.stdout:
            line = raw.rstrip("\n")
            lines.append(line)
            stream.write(line + "\n")
            stream.flush()

    thread = threading.Thread(target=_reader, daemon=True)
    thread.start()
    return _SubprocessHandle(
        proc=proc,
        log_path=log_path,
        lines=lines,
        _thread=thread,
        _stream=stream,
    )


def _build_runtime_env() -> dict[str, str]:
    runtime_env = os.environ.copy()
    multiproc_dir = _prepare_prometheus_multiproc_dir()
    runtime_env["TESTING"] = "1"
    runtime_env["CONTRACT_TESTING"] = "0"
    runtime_env["ENVIRONMENT"] = "test"
    runtime_env["AUTH_JWT_SECRET"] = private_ring_payload()
    runtime_env["AUTH_JWT_PUBLIC_KEY_RING"] = public_ring_payload()
    runtime_env["AUTH_JWT_ALGORITHM"] = "RS256"
    runtime_env["AUTH_JWT_ISSUER"] = "https://issuer.skeldir.test"
    runtime_env["AUTH_JWT_AUDIENCE"] = "skeldir-api"
    runtime_env["AUTH_LOGIN_IDENTIFIER_PEPPER"] = "b12-p9-login-pepper"
    runtime_env["PLATFORM_TOKEN_ENCRYPTION_KEY"] = "b12-p9-platform-key"
    runtime_env["PLATFORM_TOKEN_KEY_ID"] = "b12-p9-key-id"
    runtime_env["SKELDIR_TEST_TASKS"] = "1"
    runtime_env["PYTHONPATH"] = str(_repo_root()) + os.pathsep + str(_backend_root())
    runtime_env["PROMETHEUS_MULTIPROC_DIR"] = str(multiproc_dir)
    runtime_env["DATABASE_URL"] = _runtime_sync_database_url()
    runtime_env["MIGRATION_DATABASE_URL"] = _seed_sync_database_url()
    runtime_env["CELERY_BROKER_URL"] = str(celery_app.conf.broker_url)
    runtime_env["CELERY_RESULT_BACKEND"] = str(celery_app.conf.result_backend)
    return runtime_env


def _seed_b12_p9_scenario() -> _SeededScenario:
    tenant_a = uuid4()
    tenant_b = uuid4()
    tenant_a_key = f"b12-p9-tenant-key-a-{tenant_a.hex[:10]}"
    tenant_b_key = f"b12-p9-tenant-key-b-{tenant_b.hex[:10]}"
    tenant_a_api_key_hash = hashlib.sha256(tenant_a_key.encode("utf-8")).hexdigest()
    tenant_b_api_key_hash = hashlib.sha256(tenant_b_key.encode("utf-8")).hexdigest()
    tenant_a_stripe_secret = f"b12-p9-stripe-a-{tenant_a.hex[:8]}"
    tenant_b_stripe_secret = f"b12-p9-stripe-b-{tenant_b.hex[:8]}"
    shared_user_id = uuid4()
    tenant_b_only_user_id = uuid4()
    email = f"b12-p9-shared-{uuid4().hex[:8]}@example.com"
    password = "B12P9-Password!123"
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    pepper = os.environ.get("AUTH_LOGIN_IDENTIFIER_PEPPER", "b12-p9-login-pepper")
    login_identifier_hash = hashlib.sha256(f"{pepper}:{email.strip().lower()}".encode("utf-8")).hexdigest()
    revenue_a_cents = 11100
    revenue_b_cents = 22200
    now = datetime.now(timezone.utc)

    engine = _with_sql_engine(_seed_sync_database_url())
    with engine.begin() as conn:
        tenant_base_columns = "id, name, api_key_hash, notification_email, created_at, updated_at"
        tenant_base_values = ":id, :name, :api_key_hash, :notification_email, now(), now()"
        tenant_stmt = tenant_insert_statement(tenant_base_columns, tenant_base_values)

        tenant_a_params = enrich_params_with_webhook_secrets(
            {
                "id": str(tenant_a),
                "name": f"B12 P9 Tenant A {tenant_a.hex[:8]}",
                "api_key_hash": tenant_a_api_key_hash,
                "notification_email": f"tenant-a-{tenant_a.hex[:8]}@example.invalid",
            },
            shopify_secret=f"shopify-a-{tenant_a.hex[:8]}",
            stripe_secret=tenant_a_stripe_secret,
            paypal_secret=f"paypal-a-{tenant_a.hex[:8]}",
            woocommerce_secret=f"woo-a-{tenant_a.hex[:8]}",
        )
        conn.execute(tenant_stmt, tenant_a_params)

        tenant_b_params = enrich_params_with_webhook_secrets(
            {
                "id": str(tenant_b),
                "name": f"B12 P9 Tenant B {tenant_b.hex[:8]}",
                "api_key_hash": tenant_b_api_key_hash,
                "notification_email": f"tenant-b-{tenant_b.hex[:8]}@example.invalid",
            },
            shopify_secret=f"shopify-b-{tenant_b.hex[:8]}",
            stripe_secret=tenant_b_stripe_secret,
            paypal_secret=f"paypal-b-{tenant_b.hex[:8]}",
            woocommerce_secret=f"woo-b-{tenant_b.hex[:8]}",
        )
        conn.execute(tenant_stmt, tenant_b_params)

        conn.execute(
            text(
                """
                INSERT INTO public.users (
                    id,
                    login_identifier_hash,
                    external_subject_hash,
                    auth_provider,
                    is_active,
                    password_hash,
                    created_at,
                    updated_at
                ) VALUES (
                    :id,
                    :login_identifier_hash,
                    :external_subject_hash,
                    'password',
                    true,
                    :password_hash,
                    now(),
                    now()
                )
                ON CONFLICT (id) DO UPDATE SET
                    login_identifier_hash = EXCLUDED.login_identifier_hash,
                    external_subject_hash = EXCLUDED.external_subject_hash,
                    auth_provider = EXCLUDED.auth_provider,
                    is_active = EXCLUDED.is_active,
                    password_hash = EXCLUDED.password_hash,
                    updated_at = now()
                """
            ),
            {
                "id": str(shared_user_id),
                "login_identifier_hash": login_identifier_hash,
                "external_subject_hash": f"subject-{shared_user_id}",
                "password_hash": password_hash,
            },
        )
        conn.execute(
            text(
                """
                INSERT INTO public.users (
                    id,
                    login_identifier_hash,
                    external_subject_hash,
                    auth_provider,
                    is_active,
                    password_hash,
                    created_at,
                    updated_at
                ) VALUES (
                    :id,
                    :login_identifier_hash,
                    :external_subject_hash,
                    'password',
                    true,
                    :password_hash,
                    now(),
                    now()
                )
                ON CONFLICT (id) DO UPDATE SET
                    login_identifier_hash = EXCLUDED.login_identifier_hash,
                    external_subject_hash = EXCLUDED.external_subject_hash,
                    auth_provider = EXCLUDED.auth_provider,
                    is_active = EXCLUDED.is_active,
                    password_hash = EXCLUDED.password_hash,
                    updated_at = now()
                """
            ),
            {
                "id": str(tenant_b_only_user_id),
                "login_identifier_hash": hashlib.sha256(
                    f"{pepper}:tenant-b-only-{tenant_b_only_user_id}@example.com".encode("utf-8")
                ).hexdigest(),
                "external_subject_hash": f"subject-{tenant_b_only_user_id}",
                "password_hash": password_hash,
            },
        )

        for tenant_id, user_id, role in (
            (tenant_a, shared_user_id, "admin"),
            (tenant_b, shared_user_id, "viewer"),
            (tenant_b, tenant_b_only_user_id, "viewer"),
        ):
            membership_id = uuid4()
            conn.execute(
                text(
                    """
                    INSERT INTO public.tenant_memberships (id, tenant_id, user_id, membership_status, created_at, updated_at)
                    VALUES (:id, :tenant_id, :user_id, 'active', now(), now())
                    ON CONFLICT (tenant_id, user_id) DO UPDATE SET
                        membership_status = 'active',
                        updated_at = now()
                    """
                ),
                {"id": str(membership_id), "tenant_id": str(tenant_id), "user_id": str(user_id)},
            )
            persisted_membership_id = conn.execute(
                text(
                    """
                    SELECT id
                    FROM public.tenant_memberships
                    WHERE tenant_id = :tenant_id
                      AND user_id = :user_id
                    LIMIT 1
                    """
                ),
                {"tenant_id": str(tenant_id), "user_id": str(user_id)},
            ).scalar_one()
            conn.execute(
                text(
                    """
                    DELETE FROM public.tenant_membership_roles
                    WHERE tenant_id = :tenant_id
                      AND membership_id = :membership_id
                    """
                ),
                {"tenant_id": str(tenant_id), "membership_id": str(persisted_membership_id)},
            )
            conn.execute(
                text(
                    """
                    INSERT INTO public.tenant_membership_roles (
                        id,
                        tenant_id,
                        membership_id,
                        role_code,
                        created_at,
                        updated_at
                    ) VALUES (
                        gen_random_uuid(),
                        :tenant_id,
                        :membership_id,
                        :role_code,
                        now(),
                        now()
                    )
                    """
                ),
                {
                    "tenant_id": str(tenant_id),
                    "membership_id": str(persisted_membership_id),
                    "role_code": role,
                },
            )

        for tenant_id, revenue_cents in ((tenant_a, revenue_a_cents), (tenant_b, revenue_b_cents)):
            payload = {
                "tenant_id": str(tenant_id),
                "interval": "minute",
                "currency": "USD",
                "revenue_total_cents": revenue_cents,
                "event_count": 1,
                "verified": False,
                "data_as_of": now.isoformat(),
                "sources": [],
                "confidence_score": 0.0,
                "upgrade_notice": None,
            }
            conn.execute(
                text(
                    """
                    INSERT INTO public.revenue_cache_entries (
                        tenant_id,
                        cache_key,
                        payload,
                        data_as_of,
                        expires_at,
                        error_cooldown_until,
                        last_error_at,
                        last_error_message,
                        etag,
                        created_at,
                        updated_at
                    ) VALUES (
                        :tenant_id,
                        'realtime_revenue:shared:v1',
                        CAST(:payload AS jsonb),
                        :data_as_of,
                        :expires_at,
                        NULL,
                        NULL,
                        NULL,
                        :etag,
                        now(),
                        now()
                    )
                    ON CONFLICT (tenant_id, cache_key) DO UPDATE SET
                        payload = EXCLUDED.payload,
                        data_as_of = EXCLUDED.data_as_of,
                        expires_at = EXCLUDED.expires_at,
                        error_cooldown_until = NULL,
                        last_error_at = NULL,
                        last_error_message = NULL,
                        etag = EXCLUDED.etag,
                        updated_at = now()
                    """
                ),
                {
                    "tenant_id": str(tenant_id),
                    "payload": json.dumps(payload),
                    "data_as_of": now,
                    "expires_at": now + timedelta(hours=1),
                    "etag": f"b12-p9-{tenant_id.hex[:10]}",
                },
            )

    return _SeededScenario(
        tenant_a=tenant_a,
        tenant_b=tenant_b,
        tenant_a_key=tenant_a_key,
        tenant_b_key=tenant_b_key,
        tenant_a_stripe_secret=tenant_a_stripe_secret,
        shared_user_id=shared_user_id,
        tenant_b_only_user_id=tenant_b_only_user_id,
        email=email,
        password=password,
        revenue_a_total=revenue_a_cents / 100.0,
        revenue_b_total=revenue_b_cents / 100.0,
    )


async def _login(client: httpx.AsyncClient, *, tenant_id: UUID, email: str, password: str) -> dict[str, Any]:
    response = await client.post(
        "/api/auth/login",
        json={"email": email, "password": password, "tenant_id": str(tenant_id)},
        headers={"X-Correlation-ID": str(uuid4())},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _read_refresh_row_expiry(refresh_token_row_id: UUID) -> tuple[datetime, datetime]:
    engine = _with_sql_engine(_seed_sync_database_url())
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT created_at, expires_at
                FROM public.auth_refresh_tokens
                WHERE id = :id
                """
            ),
            {"id": str(refresh_token_row_id)},
        ).mappings().one()
    return row["created_at"], row["expires_at"]


def _count_worker_effect_rows(*, tenant_id: UUID, task_id: str) -> int:
    engine = _with_sql_engine(_seed_sync_database_url())
    with engine.begin() as conn:
        count = conn.execute(
            text(
                """
                SELECT COUNT(*)::int
                FROM public.worker_side_effects
                WHERE tenant_id = :tenant_id
                  AND task_id = :task_id
                """
            ),
            {"tenant_id": str(tenant_id), "task_id": str(task_id)},
        ).scalar_one()
    return int(count)


@pytest.fixture(autouse=True)
def _p9_env_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TESTING", "1")
    monkeypatch.setenv("CONTRACT_TESTING", "0")
    monkeypatch.setenv("AUTH_JWT_SECRET", private_ring_payload())
    monkeypatch.setenv("AUTH_JWT_PUBLIC_KEY_RING", public_ring_payload())
    monkeypatch.setenv("AUTH_JWT_ALGORITHM", "RS256")
    monkeypatch.setenv("AUTH_JWT_ISSUER", "https://issuer.skeldir.test")
    monkeypatch.setenv("AUTH_JWT_AUDIENCE", "skeldir-api")
    monkeypatch.setenv("AUTH_LOGIN_IDENTIFIER_PEPPER", "b12-p9-login-pepper")
    monkeypatch.setenv("PLATFORM_TOKEN_ENCRYPTION_KEY", "b12-p9-platform-key")
    monkeypatch.setenv("PLATFORM_TOKEN_KEY_ID", "b12-p9-key-id")
    monkeypatch.setenv("SKELDIR_TEST_TASKS", "1")
    settings.PLATFORM_TOKEN_ENCRYPTION_KEY = "b12-p9-platform-key"
    settings.PLATFORM_TOKEN_KEY_ID = "b12-p9-key-id"
    reset_crypto_secret_caches_for_testing()


async def test_b12_p9_e2e_system_proof() -> None:
    artifacts_dir = _artifacts_dir()
    api_log_path = artifacts_dir / "p9_api.log"
    worker_log_path = artifacts_dir / "p9_worker.log"
    report_path = artifacts_dir / "p9_runtime_report.json"
    runtime_env = _build_runtime_env()
    try:
        seeded = _seed_b12_p9_scenario()
    except Exception as exc:
        lowered = str(exc).lower()
        if "row-level security policy for table \"users\"" in lowered:
            pytest.skip(
                "B1.2-P9 seed requires migration/owner DB privileges in local runs; "
                "CI job runs with postgres service credentials."
            )
        raise

    api_port = _free_port()
    api_base_url = f"http://127.0.0.1:{api_port}"
    api_handle: _SubprocessHandle | None = None
    worker_handle: _SubprocessHandle | None = None

    evidence: dict[str, Any] = {
        "tenant_a": str(seeded.tenant_a),
        "tenant_b": str(seeded.tenant_b),
        "shared_user_id": str(seeded.shared_user_id),
        "tenant_b_only_user_id": str(seeded.tenant_b_only_user_id),
        "api_log": str(api_log_path),
        "worker_log": str(worker_log_path),
    }

    try:
        worker_handle = _start_logged_process(
            [
                sys.executable,
                "-m",
                "celery",
                "-A",
                "app.celery_app.celery_app",
                "worker",
                "-P",
                "solo",
                "-c",
                "1",
                "-Q",
                "housekeeping",
                "--without-gossip",
                "--without-mingle",
                "--without-heartbeat",
                "--loglevel=INFO",
            ],
            env=runtime_env,
            cwd=_backend_root(),
            log_path=worker_log_path,
        )
        _wait_for_worker_ready(worker_handle.lines, worker_handle.proc)

        api_handle = _start_logged_process(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(api_port),
                "--log-level",
                "info",
            ],
            env=runtime_env,
            cwd=_backend_root(),
            log_path=api_log_path,
        )
        _wait_for_api_ready(api_base_url)

        async with httpx.AsyncClient(base_url=api_base_url, timeout=20.0) as client:
            login_a = await _login(
                client,
                tenant_id=seeded.tenant_a,
                email=seeded.email,
                password=seeded.password,
            )
            login_b = await _login(
                client,
                tenant_id=seeded.tenant_b,
                email=seeded.email,
                password=seeded.password,
            )

            access_claims_a = _decode_access_token(login_a["access_token"])
            access_claims_b = _decode_access_token(login_b["access_token"])
            refresh_tenant_id_a, refresh_row_id_a, _ = _parse_refresh_token(login_a["refresh_token"])
            created_at, expires_at = _read_refresh_row_expiry(refresh_row_id_a)
            refresh_ttl_s = int((expires_at - created_at).total_seconds())

            assert 895 <= int(access_claims_a["exp"]) - int(access_claims_a["iat"]) <= 905
            assert refresh_tenant_id_a == seeded.tenant_a
            assert access_claims_a["tenant_id"] == str(seeded.tenant_a)
            assert access_claims_b["tenant_id"] == str(seeded.tenant_b)
            assert 29 * 24 * 3600 <= refresh_ttl_s <= 31 * 24 * 3600

            invalid_jwt_response = await client.get(
                "/api/v1/revenue/realtime",
                headers={
                    "X-Correlation-ID": str(uuid4()),
                    "Authorization": "Bearer not-a-jwt",
                },
            )
            invalid_jwt_problem = _assert_non_leaky_problem(invalid_jwt_response, expected_status=401)

            viewer_admin_response = await client.get(
                "/api/auth/admin/rbac-check",
                headers={
                    "X-Correlation-ID": str(uuid4()),
                    "Authorization": f"Bearer {login_b['access_token']}",
                },
            )
            viewer_admin_problem = _assert_non_leaky_problem(viewer_admin_response, expected_status=403)

            admin_ok_response = await client.get(
                "/api/auth/admin/rbac-check",
                headers={
                    "X-Correlation-ID": str(uuid4()),
                    "Authorization": f"Bearer {login_a['access_token']}",
                },
            )
            assert admin_ok_response.status_code == 200, admin_ok_response.text

            read_a_response = await client.get(
                "/api/attribution/revenue/realtime",
                headers={
                    "X-Correlation-ID": str(uuid4()),
                    "Authorization": f"Bearer {login_a['access_token']}",
                },
            )
            read_b_response = await client.get(
                "/api/attribution/revenue/realtime",
                headers={
                    "X-Correlation-ID": str(uuid4()),
                    "Authorization": f"Bearer {login_b['access_token']}",
                },
            )
            assert read_a_response.status_code == 200, read_a_response.text
            assert read_b_response.status_code == 200, read_b_response.text
            read_a = read_a_response.json()
            read_b = read_b_response.json()
            assert read_a["tenant_id"] == str(seeded.tenant_a)
            assert read_b["tenant_id"] == str(seeded.tenant_b)
            assert float(read_a["total_revenue"]) == pytest.approx(seeded.revenue_a_total)
            assert float(read_b["total_revenue"]) == pytest.approx(seeded.revenue_b_total)
            # Live negative control: wrong-tenant token must not read wrong-tenant seeded row.
            assert float(read_a["total_revenue"]) != pytest.approx(seeded.revenue_b_total)
            assert float(read_b["total_revenue"]) != pytest.approx(seeded.revenue_a_total)

            cross_tenant_write_response = await client.post(
                "/api/auth/admin/membership-role",
                json={"user_id": str(seeded.tenant_b_only_user_id), "role": "admin"},
                headers={
                    "X-Correlation-ID": str(uuid4()),
                    "Authorization": f"Bearer {login_a['access_token']}",
                },
            )
            assert cross_tenant_write_response.status_code == 404, cross_tenant_write_response.text

            session_envelope = SessionAuthorityEnvelope(
                tenant_id=seeded.tenant_a,
                user_id=UUID(str(access_claims_a["user_id"])),
                jti=UUID(str(access_claims_a["jti"])),
                iat=int(access_claims_a["iat"]),
            ).model_dump(mode="json")
            positive_async_result = await asyncio.to_thread(
                celery_app.send_task,
                "app.tasks.observability_test.auth_envelope_probe",
                queue="housekeeping",
                kwargs={"correlation_id": str(uuid4())},
                headers={AUTHORITY_ENVELOPE_HEADER: session_envelope},
            )
            positive_payload = await asyncio.to_thread(
                lambda: positive_async_result.get(timeout=120, propagate=True)
            )
            assert positive_payload["status"] == "ok"
            assert _count_worker_effect_rows(
                tenant_id=seeded.tenant_a,
                task_id=str(positive_async_result.id),
            ) == 1

            missing_envelope_result = await asyncio.to_thread(
                celery_app.send_task,
                "app.tasks.observability_test.auth_envelope_probe",
                queue="housekeeping",
                kwargs={"correlation_id": str(uuid4())},
            )
            with pytest.raises(Exception, match="authority_envelope header is required"):
                await asyncio.to_thread(
                    lambda: missing_envelope_result.get(timeout=120, propagate=True)
                )
            assert _count_worker_effect_rows(
                tenant_id=seeded.tenant_a,
                task_id=str(missing_envelope_result.id),
            ) == 0

            webhook_payload = {
                "id": f"pi_{uuid4().hex[:12]}",
                "amount": 5000,
                "currency": "usd",
                "created": int(time.time()),
                "status": "succeeded",
            }
            webhook_raw = json.dumps(webhook_payload, separators=(",", ":")).encode("utf-8")
            valid_signature = _stripe_signature(
                webhook_raw,
                seeded.tenant_a_stripe_secret,
                valid=True,
            )
            assert verify_stripe_signature(webhook_raw, seeded.tenant_a_stripe_secret, valid_signature)

            webhook_ok_response = await client.post(
                "/api/webhooks/stripe/payment_intent_succeeded",
                content=webhook_raw,
                headers={
                    "content-type": "application/json",
                    "X-Correlation-ID": str(uuid4()),
                    "X-Skeldir-Tenant-Key": seeded.tenant_a_key,
                    "Stripe-Signature": valid_signature,
                },
            )
            assert webhook_ok_response.status_code == 200, webhook_ok_response.text

            invalid_signature = _stripe_signature(
                webhook_raw,
                seeded.tenant_a_stripe_secret,
                valid=False,
            )
            webhook_bad_response = await client.post(
                "/api/webhooks/stripe/payment_intent_succeeded",
                content=webhook_raw,
                headers={
                    "content-type": "application/json",
                    "X-Correlation-ID": str(uuid4()),
                    "X-Skeldir-Tenant-Key": seeded.tenant_a_key,
                    "Stripe-Signature": invalid_signature,
                },
            )
            webhook_problem = _assert_non_leaky_problem(webhook_bad_response, expected_status=401)

            evidence.update(
                {
                    "login_access_ttl_seconds": int(access_claims_a["exp"]) - int(access_claims_a["iat"]),
                    "login_refresh_ttl_seconds": refresh_ttl_s,
                    "tenant_a_read_total_revenue": read_a["total_revenue"],
                    "tenant_b_read_total_revenue": read_b["total_revenue"],
                    "cross_tenant_write_status": cross_tenant_write_response.status_code,
                    "worker_positive_task_id": str(positive_async_result.id),
                    "worker_negative_task_id": str(missing_envelope_result.id),
                    "webhook_signed_status": webhook_ok_response.status_code,
                    "invalid_jwt_problem": invalid_jwt_problem,
                    "rbac_problem": viewer_admin_problem,
                    "webhook_problem": webhook_problem,
                }
            )
    finally:
        if api_handle is not None:
            api_handle.terminate()
        if worker_handle is not None:
            worker_handle.terminate()
        report_path.write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
