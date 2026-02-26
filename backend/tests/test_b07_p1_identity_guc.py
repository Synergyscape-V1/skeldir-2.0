from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text
from starlette.requests import Request

from app.celery_app import celery_app
from app.db.deps import get_db_session
from app.db.session import get_session
from app.security.auth import AuthContext
from app.tasks.context import tenant_task


@celery_app.task(bind=True, name="test.b07.identity_guc.tenant_task_probe")
@tenant_task
def _tenant_task_probe(self, tenant_id, marker: str, user_id=None, correlation_id=None):
    return {"tenant_id": str(tenant_id), "marker": marker}


@pytest.mark.asyncio
async def test_api_db_session_sets_user_and_tenant_guc():
    tenant_id = uuid4()
    user_id = uuid4()
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": []})
    auth_context = AuthContext(
        tenant_id=tenant_id,
        user_id=user_id,
        subject=None,
        issuer=None,
        audience=None,
        claims={},
    )

    async for session in get_db_session(request, auth_context):
        tenant = await session.execute(
            text("SELECT current_setting('app.current_tenant_id', true)")
        )
        user = await session.execute(
            text("SELECT current_setting('app.current_user_id', true)")
        )
        assert tenant.scalar() == str(tenant_id)
        assert user.scalar() == str(user_id)


@pytest.mark.asyncio
async def test_worker_session_sets_user_and_tenant_guc():
    tenant_id = uuid4()
    user_id = uuid4()
    async with get_session(tenant_id=tenant_id, user_id=user_id) as session:
        tenant = await session.execute(
            text("SELECT current_setting('app.current_tenant_id', true)")
        )
        user = await session.execute(
            text("SELECT current_setting('app.current_user_id', true)")
        )
        assert tenant.scalar() == str(tenant_id)
        assert user.scalar() == str(user_id)


def test_worker_tenant_task_rejects_missing_tenant_envelope():
    original_eager = celery_app.conf.task_always_eager
    original_propagates = celery_app.conf.task_eager_propagates
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    try:
        with pytest.raises(ValueError, match="tenant_id is required"):
            _tenant_task_probe.apply(kwargs={"marker": "missing-tenant"}).get(propagate=True)
    finally:
        celery_app.conf.task_always_eager = original_eager
        celery_app.conf.task_eager_propagates = original_propagates


def test_worker_tenant_task_attempts_guc_binding_before_task_sql(monkeypatch):
    original_eager = celery_app.conf.task_always_eager
    original_propagates = celery_app.conf.task_eager_propagates
    celery_app.conf.task_always_eager = False
    celery_app.conf.task_eager_propagates = True
    guc_call_count = {"count": 0}

    def _fake_run_in_worker_loop(coro):
        guc_call_count["count"] += 1
        coro.close()
        return None

    monkeypatch.setattr("app.tasks.context.run_in_worker_loop", _fake_run_in_worker_loop)
    try:
        tenant_id = uuid4()
        result = _tenant_task_probe.apply(
            kwargs={"tenant_id": str(tenant_id), "marker": "guc-before-task"}
        ).get(propagate=True)
        assert result["tenant_id"] == str(tenant_id)
        assert result["marker"] == "guc-before-task"
        assert guc_call_count["count"] == 1
    finally:
        celery_app.conf.task_always_eager = original_eager
        celery_app.conf.task_eager_propagates = original_propagates
