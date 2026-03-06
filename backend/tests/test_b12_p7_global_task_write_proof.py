from __future__ import annotations

import re
from typing import Callable

import pytest
from sqlalchemy import event, text

from app.celery_app import celery_app
from app.db.session import engine
# Force task registration for direct task lookups in this module.
from app.tasks import health as _tasks_health  # noqa: F401
from app.tasks import housekeeping as _tasks_housekeeping  # noqa: F401

_TENANT_DML_PATTERN = re.compile(
    r"\b(insert|update|delete)\b.*\b("
    r"attribution_events|attribution_allocations|worker_side_effects|dead_events|auth_access_token_denylist"
    r")\b",
    re.IGNORECASE | re.DOTALL,
)


def _install_tenant_write_guard() -> tuple[dict[str, int], Callable[[], None]]:
    observed = {"checked": 0}

    def _capture_sql(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        observed["checked"] += 1
        if _TENANT_DML_PATTERN.search(statement or ""):
            raise AssertionError(f"global task write guard blocked SQL: {statement}")

    event.listen(engine.sync_engine, "before_cursor_execute", _capture_sql)

    def _remove() -> None:
        event.remove(engine.sync_engine, "before_cursor_execute", _capture_sql)

    return observed, _remove


def test_global_tasks_do_not_mutate_tenant_tables_under_guard() -> None:
    original_eager = celery_app.conf.task_always_eager
    celery_app.conf.task_always_eager = True
    observed, remove = _install_tenant_write_guard()
    try:
        celery_app.tasks["app.tasks.housekeeping.ping"].delay().get(timeout=30, propagate=True)
        celery_app.tasks["app.tasks.health.probe"].delay().get(timeout=30, propagate=True)
        assert observed["checked"] > 0
    finally:
        remove()
        celery_app.conf.task_always_eager = original_eager


@pytest.mark.asyncio
async def test_global_write_guard_negative_control_fails_on_tenant_dml() -> None:
    observed, remove = _install_tenant_write_guard()
    try:
        with pytest.raises(AssertionError, match="global task write guard"):
            async with engine.begin() as conn:
                await conn.execute(text("DELETE FROM attribution_allocations WHERE 1=0"))
    finally:
        remove()
    assert observed["checked"] > 0
