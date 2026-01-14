from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import text

from app.db.session import engine
from app.tasks import attribution
from app.tasks.maintenance import scan_for_pii_contamination_task
from tests.builders.core_builders import build_tenant




def test_maintenance_task_sets_tenant_guc():
    tenant_id = asyncio.run(build_tenant())["tenant_id"]
    correlation_id = str(uuid4())
    result = scan_for_pii_contamination_task.run(
        tenant_id=tenant_id,
        correlation_id=correlation_id,
    )

    assert result["guc"] == str(tenant_id)


def test_attribution_task_sets_tenant_guc(monkeypatch):
    seen = {}
    real_set = attribution.set_tenant_guc

    async def _spy_set_tenant_guc(conn, tenant_id, local: bool):
        await real_set(conn, tenant_id, local=local)
        res = await conn.execute(text("SELECT current_setting('app.current_tenant_id', true)"))
        seen["value"] = res.scalar()

    monkeypatch.setattr(attribution, "set_tenant_guc", _spy_set_tenant_guc)

    tenant_id = asyncio.run(build_tenant())["tenant_id"]
    correlation_id = str(uuid4())
    now = datetime.now(timezone.utc)
    window_start = (now - timedelta(days=1)).isoformat().replace("+00:00", "Z")
    window_end = now.isoformat().replace("+00:00", "Z")

    result = attribution.recompute_window.run(
        tenant_id=tenant_id,
        window_start=window_start,
        window_end=window_end,
        correlation_id=correlation_id,
        model_version="1.0.0",
    )

    assert seen.get("value") == str(tenant_id)

    async def _cleanup():
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    """
                    DELETE FROM attribution_recompute_jobs
                    WHERE id = :job_id AND tenant_id = :tenant_id
                    """
                ),
                {"job_id": result["job_id"], "tenant_id": tenant_id},
            )

    asyncio.run(_cleanup())
