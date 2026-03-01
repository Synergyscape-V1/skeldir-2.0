"""
B0.6 Phase 2: Platform connection substrate tests.
"""

import os
import sys
import time
from pathlib import Path
from uuid import UUID, uuid4

import jwt
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine, text
from alembic import command
from alembic.config import Config

os.environ["TESTING"] = "1"
os.environ.setdefault("PLATFORM_TOKEN_ENCRYPTION_KEY", "test-platform-key")
os.environ.setdefault("PLATFORM_TOKEN_KEY_ID", "test-key")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/postgres",
)

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))
from app.testing.jwt_rs256 import (  # noqa: E402
    TEST_PRIVATE_KEY_PEM,
    private_ring_payload,
    public_ring_payload,
)

os.environ["AUTH_JWT_SECRET"] = private_ring_payload()
os.environ["AUTH_JWT_PUBLIC_KEY_RING"] = public_ring_payload()
os.environ["AUTH_JWT_ALGORITHM"] = "RS256"
os.environ["AUTH_JWT_ISSUER"] = "https://issuer.skeldir.test"
os.environ["AUTH_JWT_AUDIENCE"] = "skeldir-api"

from app.main import app  # noqa: E402
from tests.builders.core_builders import build_tenant  # noqa: E402

pytestmark = pytest.mark.asyncio


def _sync_database_url() -> str:
    url = os.environ.get("MIGRATION_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is required for Phase 2 tests")
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url


def _build_token(tenant_id: UUID) -> str:
    now = int(time.time())
    payload = {
        "sub": "user-1",
        "iss": os.environ["AUTH_JWT_ISSUER"],
        "aud": os.environ["AUTH_JWT_AUDIENCE"],
        "iat": now,
        "exp": now + 3600,
        "tenant_id": str(tenant_id),
    }
    return jwt.encode(
        payload,
        TEST_PRIVATE_KEY_PEM,
        algorithm=os.environ["AUTH_JWT_ALGORITHM"],
        headers={"kid": "kid-1"},
    )


@pytest.fixture(scope="session", autouse=True)
def _apply_migrations():
    config = Config(str(Path(__file__).parent.parent / "alembic.ini"))
    sync_url = _sync_database_url()
    config.set_main_option("sqlalchemy.url", sync_url)
    os.environ["MIGRATION_DATABASE_URL"] = sync_url
    command.upgrade(config, "head")


@pytest.fixture
async def tenant_ids():
    tenant_a = await build_tenant()
    tenant_b = await build_tenant()
    return tenant_a["tenant_id"], tenant_b["tenant_id"]


async def test_platform_connections_require_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/attribution/platform-connections",
            headers={"X-Correlation-ID": "00000000-0000-0000-0000-000000000000"},
            json={"platform": "google_ads", "platform_account_id": "123"},
        )
    assert resp.status_code == 401


async def test_platform_connection_tenant_isolation_and_secrecy(tenant_ids):
    tenant_a, tenant_b = tenant_ids
    token_a = _build_token(tenant_a)
    token_b = _build_token(tenant_b)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp_a = await client.post(
            "/api/attribution/platform-connections",
            headers={
                "X-Correlation-ID": str(uuid4()),
                "Authorization": f"Bearer {token_a}",
            },
            json={"platform": "meta_ads", "platform_account_id": "act_1", "status": "active"},
        )
        assert resp_a.status_code == 200

        resp_creds = await client.post(
            "/api/attribution/platform-credentials",
            headers={
                "X-Correlation-ID": str(uuid4()),
                "Authorization": f"Bearer {token_a}",
            },
            json={
                "platform": "meta_ads",
                "platform_account_id": "act_1",
                "access_token": "access-token-a",
                "refresh_token": "refresh-token-a",
            },
        )
        assert resp_creds.status_code == 200
        assert "access-token-a" not in resp_creds.text
        assert "refresh-token-a" not in resp_creds.text

        resp_b = await client.get(
            "/api/attribution/platform-connections/meta_ads",
            headers={
                "X-Correlation-ID": str(uuid4()),
                "Authorization": f"Bearer {token_b}",
            },
            params={"platform_account_id": "act_1"},
        )
        assert resp_b.status_code == 404

    sync_engine = create_engine(_sync_database_url())
    with sync_engine.begin() as conn:
        role_exists = conn.execute(
            text("SELECT 1 FROM pg_roles WHERE rolname = 'app_rw'")
        ).scalar_one_or_none()
        if role_exists:
            conn.execute(text("SET ROLE app_rw"))
            conn.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
                {"tenant_id": str(tenant_a)},
            )
            count_a = conn.execute(
                text("SELECT COUNT(*) FROM platform_connections")
            ).scalar_one()
            conn.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
                {"tenant_id": str(tenant_b)},
            )
            count_b = conn.execute(
                text("SELECT COUNT(*) FROM platform_connections")
            ).scalar_one()
            assert count_a == 1
            assert count_b == 0
            conn.execute(text("RESET ROLE"))

        encrypted_token = conn.execute(
            text(
                "SELECT encrypted_access_token FROM platform_credentials "
                "WHERE platform = :platform ORDER BY updated_at DESC LIMIT 1"
            ),
            {"platform": "meta_ads"},
        ).scalar_one()

    assert encrypted_token != b"access-token-a"
