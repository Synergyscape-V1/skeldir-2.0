from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from app.bayesian.model_spec import B24_P6_MODEL_TYPE, B24_P6_MODEL_VERSION
from app.bayesian.tenant_context import (
    assert_fresh_checkout_is_clean,
    bind_transaction_local_tenant,
    current_tenant_guc,
)
from app.core.secrets import get_database_url
from app.db.dsn import to_sync_postgres_dsn
from app.db.session import engine, get_session


START = datetime(2026, 5, 1, tzinfo=timezone.utc)
END = datetime(2026, 6, 1, tzinfo=timezone.utc)


def _require_db_proofs() -> bool:
    return os.getenv("SKELDIR_B24_P9_REQUIRE_DB_PROOFS", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


pytestmark = pytest.mark.skipif(
    not _require_db_proofs() and os.getenv("CI") != "true",
    reason="B2.4-P9 PostgreSQL proof is opt-in for local runs",
)


async def _assert_table_exists(table_name: str) -> None:
    try:
        async with engine.begin() as conn:
            result = await conn.execute(
                text("SELECT to_regclass(:qualified_name)"),
                {"qualified_name": f"public.{table_name}"},
            )
    except OperationalError as exc:
        message = f"B2.4-P9 PostgreSQL runtime proof unavailable: {exc}"
        if _require_db_proofs():
            pytest.fail(message)
        pytest.skip(message)
    if result.scalar() is None:
        message = f"B2.4-P9 PostgreSQL runtime proof table is missing: {table_name}"
        if _require_db_proofs():
            pytest.fail(message)
        pytest.skip(message)


async def _insert_fit(tenant_id: UUID, *, fit_id: UUID, source_hash: str) -> None:
    async with get_session(tenant_id) as session:
        await session.execute(
            text(
                """
                INSERT INTO public.bayesian_model_fits (
                    tenant_id,
                    id,
                    model_type,
                    model_version,
                    source_window_start,
                    source_window_end,
                    source_snapshot_hash,
                    status,
                    eligibility_status,
                    data_completeness_status,
                    fallback_applied,
                    max_runtime_seconds,
                    max_samples,
                    max_cores
                )
                VALUES (
                    :tenant_id,
                    :fit_id,
                    :model_type,
                    :model_version,
                    :source_window_start,
                    :source_window_end,
                    :source_snapshot_hash,
                    'queued',
                    'eligible',
                    'complete',
                    false,
                    60,
                    160,
                    1
                )
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "fit_id": str(fit_id),
                "model_type": B24_P6_MODEL_TYPE,
                "model_version": B24_P6_MODEL_VERSION,
                "source_window_start": START,
                "source_window_end": END,
                "source_snapshot_hash": source_hash,
            },
        )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_b24_p9_transaction_local_guc_clean_return_and_sequential_isolation(
    test_tenant_pair,
) -> None:
    await _assert_table_exists("bayesian_model_fits")
    tenant_a, tenant_b = test_tenant_pair
    fit_a = uuid4()
    fit_b = uuid4()
    await _insert_fit(tenant_a, fit_id=fit_a, source_hash="a" * 64)
    await _insert_fit(tenant_b, fit_id=fit_b, source_hash="b" * 64)

    sync_engine = create_engine(
        to_sync_postgres_dsn(get_database_url()),
        pool_pre_ping=True,
        pool_size=1,
        max_overflow=0,
    )
    try:
        with pytest.raises(RuntimeError, match="injected_after_set_local"):
            with sync_engine.begin() as conn:
                bind_transaction_local_tenant(conn, tenant_id=tenant_a)
                assert current_tenant_guc(conn) == str(tenant_a)
                raise RuntimeError("injected_after_set_local")

        clean = assert_fresh_checkout_is_clean(sync_engine)
        assert clean.is_clean

        with sync_engine.begin() as conn:
            bind_transaction_local_tenant(conn, tenant_id=tenant_b)
            visible_b = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.bayesian_model_fits
                    WHERE tenant_id = :tenant_id
                      AND id = :fit_id
                    """
                ),
                {"tenant_id": str(tenant_b), "fit_id": str(fit_b)},
            ).scalar_one()
            hidden_a = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.bayesian_model_fits
                    WHERE tenant_id = :tenant_id
                      AND id = :fit_id
                    """
                ),
                {"tenant_id": str(tenant_a), "fit_id": str(fit_a)},
            ).scalar_one()
            assert int(visible_b) == 1
            assert int(hidden_a) == 0
    finally:
        sync_engine.dispose()
