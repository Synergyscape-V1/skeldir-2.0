import os
import uuid

import pytest
from sqlalchemy import text

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://app_user:app_user@127.0.0.1:5432/skeldir",
)

from app.db.session import engine, set_tenant_guc, set_user_guc  # noqa: E402


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


@pytest.mark.asyncio
async def test_set_user_guc_sets_current_setting():
    user_id = uuid.uuid4()
    async with engine.begin() as conn:
        await set_user_guc(conn, user_id, local=True)
        res = await conn.execute(
            text("SELECT current_setting('app.current_user_id', true)")
        )
        val = res.scalar()
    assert val == str(user_id)
