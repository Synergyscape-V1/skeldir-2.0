import os
import uuid

import pytest
from sqlalchemy import text

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://app_user:Sk3ld1r_App_Pr0d_2025!@ep-lucky-base-aedv3gwo-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require",
)

from app.db.session import engine, set_tenant_guc  # noqa: E402


@pytest.mark.asyncio
async def test_set_tenant_guc_sets_current_setting():
    tenant_id = uuid.uuid4()
    async with engine.begin() as conn:
        await set_tenant_guc(conn, tenant_id, local=True)
        res = await conn.execute(
            text("SELECT current_setting('app.current_tenant_id', true)")
        )
        val = res.scalar()
    assert val == str(tenant_id)
