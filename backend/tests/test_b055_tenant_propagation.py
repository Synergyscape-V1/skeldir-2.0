from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import text

from app.celery_app import celery_app
from app.db.session import engine
from app.tasks.authority import SystemAuthorityEnvelope
from app.tasks.enqueue import enqueue_tenant_task
from app.tasks import attribution
from app.tasks.maintenance import scan_for_pii_contamination_task
from tests.builders.core_builders import build_tenant


def test_maintenance_task_sets_tenant_guc():
    tenant_id = asyncio.run(build_tenant())["tenant_id"]
    correlation_id = str(uuid4())
    original_eager = celery_app.conf.task_always_eager
    celery_app.conf.task_always_eager = True
    try:
        result = enqueue_tenant_task(
            scan_for_pii_contamination_task,
            envelope=SystemAuthorityEnvelope(tenant_id=tenant_id),
            kwargs={"correlation_id": correlation_id},
        ).get()
        assert result["guc"] == str(tenant_id)
    finally:
        celery_app.conf.task_always_eager = original_eager


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

    original_eager = celery_app.conf.task_always_eager
    celery_app.conf.task_always_eager = True
    try:
        enqueue_tenant_task(
            attribution.recompute_window,
            envelope=SystemAuthorityEnvelope(tenant_id=tenant_id),
            kwargs={
                "window_start": window_start,
                "window_end": window_end,
                "correlation_id": correlation_id,
                "model_version": "1.0.0",
            },
        ).get()
        assert seen.get("value") == str(tenant_id)
    finally:
        celery_app.conf.task_always_eager = original_eager
