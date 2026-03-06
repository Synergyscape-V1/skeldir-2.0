from __future__ import annotations

import time
from typing import Callable
from uuid import uuid4

import pytest
from sqlalchemy import event

from app.db.session import engine
from app.tasks.context import assert_worker_session_claims_active

pytestmark = pytest.mark.asyncio


def _install_revocation_query_counter() -> tuple[dict[str, int], Callable[[], None]]:
    counts = {"revocation": 0}

    def _capture_sql(conn, cursor, statement, parameters, context, executemany):
        lowered = statement.lower()
        if "auth_access_token_denylist" in lowered or "auth_user_token_cutoffs" in lowered:
            counts["revocation"] += 1

    event.listen(engine.sync_engine, "before_cursor_execute", _capture_sql)

    def _remove() -> None:
        event.remove(engine.sync_engine, "before_cursor_execute", _capture_sql)

    return counts, _remove


async def test_worker_session_revocation_hot_path_has_zero_db_lookups_after_warmup(test_tenant):
    user_id = uuid4()
    jti = uuid4()
    iat = int(time.time())

    # Warmup allows bounded cold-start lookup and cache priming.
    assert_worker_session_claims_active(
        tenant_id=test_tenant,
        user_id=user_id,
        jti=jti,
        iat=iat,
    )

    counts, remove = _install_revocation_query_counter()
    try:
        for _ in range(100):
            assert_worker_session_claims_active(
                tenant_id=test_tenant,
                user_id=user_id,
                jti=jti,
                iat=iat,
            )
    finally:
        remove()

    assert counts["revocation"] == 0


async def test_worker_session_revocation_hot_path_forced_db_negative_control(test_tenant, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SKELDIR_B12_P5_FORCE_DB_REVOCATION_HOT_PATH", "1")

    user_id = uuid4()
    jti = uuid4()
    iat = int(time.time())

    counts, remove = _install_revocation_query_counter()
    try:
        for _ in range(25):
            assert_worker_session_claims_active(
                tenant_id=test_tenant,
                user_id=user_id,
                jti=jti,
                iat=iat,
            )
    finally:
        remove()

    assert counts["revocation"] > 0
