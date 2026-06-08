from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from app.bayesian.artifact_repository import _artifact_ref
from app.bayesian.cleanup import cleanup_fit_attempt
from app.bayesian.compiledir_reaper import create_compiledir_lease
from app.bayesian.enums import FallbackReason, FitStatus
from app.bayesian.fit_execution import (
    _load_fit_for_execution,
    _mark_fit_failure,
    _persist_result_summary,
    _set_tenant_context,
)
from app.bayesian.model_spec import B24_P6_MODEL_TYPE, B24_P6_MODEL_VERSION
from app.bayesian.temp_workspace import create_workspace_lease
from app.bayesian.tenant_context import (
    assert_bound_tenant,
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


def _is_ci() -> bool:
    return os.getenv("CI", "").strip().lower() == "true"


pytestmark = pytest.mark.skipif(
    not _require_db_proofs() and not _is_ci(),
    reason="B2.4-P9 PostgreSQL proof is opt-in for local runs",
)


def _require_protected_db_mode() -> None:
    if _require_db_proofs():
        return
    if _is_ci():
        pytest.fail("B2.4-P9 protected CI requires SKELDIR_B24_P9_REQUIRE_DB_PROOFS=1")
    pytest.skip("B2.4-P9 PostgreSQL proof is opt-in for local runs")


async def _assert_table_exists(table_name: str) -> None:
    _require_protected_db_mode()
    try:
        async with engine.begin() as conn:
            result = await conn.execute(
                text("SELECT to_regclass(:qualified_name)"),
                {"qualified_name": f"public.{table_name}"},
            )
    except OperationalError as exc:
        message = f"B2.4-P9 PostgreSQL runtime proof unavailable: {exc}"
        if _require_db_proofs() or _is_ci():
            pytest.fail(message)
        pytest.skip(message)
    if result.scalar() is None:
        message = f"B2.4-P9 PostgreSQL runtime proof table is missing: {table_name}"
        if _require_db_proofs() or _is_ci():
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


@pytest.mark.asyncio
@pytest.mark.integration
async def test_b24_p9_db_proof_requires_explicit_flag_in_ci() -> None:
    if _is_ci():
        assert _require_db_proofs()
    else:
        _require_protected_db_mode()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_b24_p9_session_level_guc_poison_is_detected(test_tenant_pair) -> None:
    await _assert_table_exists("bayesian_model_fits")
    tenant_a, _tenant_b = test_tenant_pair
    sync_engine = create_engine(
        to_sync_postgres_dsn(get_database_url()),
        pool_pre_ping=True,
        pool_size=1,
        max_overflow=0,
    )
    try:
        with sync_engine.connect() as conn:
            conn.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
                {"tenant_id": str(tenant_a)},
            )
            assert current_tenant_guc(conn) == str(tenant_a)
            conn.commit()

        with pytest.raises(RuntimeError, match="bayesian_connection_returned_dirty"):
            assert_fresh_checkout_is_clean(sync_engine)

        with sync_engine.connect() as conn:
            conn.execute(text("RESET app.current_tenant_id"))
            conn.commit()
        assert assert_fresh_checkout_is_clean(sync_engine).is_clean
    finally:
        sync_engine.dispose()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_b24_p9_multi_transaction_task_flow_rebinds_each_transaction(
    test_tenant_pair,
) -> None:
    await _assert_table_exists("bayesian_model_fits")
    tenant_a, _tenant_b = test_tenant_pair
    fit_id = uuid4()
    source_hash = "c" * 64
    await _insert_fit(tenant_a, fit_id=fit_id, source_hash=source_hash)

    sync_engine = create_engine(
        to_sync_postgres_dsn(get_database_url()),
        pool_pre_ping=True,
        pool_size=1,
        max_overflow=0,
    )
    result_summary = {
        "diagnostic_status": "passed",
        "credible_interval_status": "available",
        "diagnostic_policy_version": "b24-p7-diagnostic-policy-v1",
        "diagnostic_target_filter_version": "b24-p7-target-filter-v1",
        "interval_policy_version": "b24-p7-interval-policy-v1",
        "n_chains": 1,
        "n_samples_actual": 20,
        "r_hat_max": 1.0,
        "ess_min": 500,
        "divergence_count": 0,
        "hdi_lower": 0.1,
        "hdi_upper": 0.2,
        "interval_shape": [1],
        "interval_element_count": 1,
        "interval_summary_bytes": 32,
    }
    try:
        with sync_engine.begin() as conn:
            row = _load_fit_for_execution(conn, tenant_id=tenant_a, fit_id=fit_id)
            assert row is not None
            assert_bound_tenant(conn, tenant_id=tenant_a)
            conn.execute(
                text(
                    """
                    UPDATE public.bayesian_model_fits
                    SET status = 'running', updated_at = now()
                    WHERE tenant_id = :tenant_id AND id = :fit_id
                    """
                ),
                {"tenant_id": str(tenant_a), "fit_id": str(fit_id)},
            )

        with sync_engine.begin() as conn:
            with pytest.raises(RuntimeError, match="bayesian_tenant_context_not_bound"):
                _persist_result_summary(
                    conn,
                    tenant_id=tenant_a,
                    fit_id=fit_id,
                    source_snapshot_hash=source_hash,
                    runtime_seconds=1,
                    result_summary=result_summary,
                    result_hash="d" * 64,
                )

        with sync_engine.begin() as conn:
            _set_tenant_context(conn, tenant_a)
            _persist_result_summary(
                conn,
                tenant_id=tenant_a,
                fit_id=fit_id,
                source_snapshot_hash=source_hash,
                runtime_seconds=1,
                result_summary=result_summary,
                result_hash="d" * 64,
            )
            assert_bound_tenant(conn, tenant_id=tenant_a)

        with sync_engine.begin() as conn:
            _mark_fit_failure(
                conn,
                tenant_id=tenant_a,
                fit_id=fit_id,
                status=FitStatus.FAILED,
                fallback_reason=FallbackReason.WORKER_FAILURE,
                runtime_seconds=2,
            )
            assert_bound_tenant(conn, tenant_id=tenant_a)
    finally:
        sync_engine.dispose()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_b24_p9_concurrent_tenant_isolation_db_and_runtime_surfaces(
    test_tenant_pair, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    await _assert_table_exists("bayesian_model_fits")
    monkeypatch.setenv("B24_BAYESIAN_WORKSPACE_ROOT", str(tmp_path / "workspaces"))
    monkeypatch.setenv("B24_PYTENSOR_ROOT", str(tmp_path / "compiledirs"))
    tenant_a, tenant_b = test_tenant_pair
    fit_a = uuid4()
    fit_b = uuid4()
    await _insert_fit(tenant_a, fit_id=fit_a, source_hash="a" * 64)
    await _insert_fit(tenant_b, fit_id=fit_b, source_hash="b" * 64)

    sync_engine = create_engine(
        to_sync_postgres_dsn(get_database_url()),
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=0,
    )
    barrier = Barrier(2)

    def lane(
        label: str, tenant_id: UUID, own_fit: UUID, other_fit: UUID
    ) -> dict[str, object]:
        source_hash = ("a" if label == "a" else "b") * 64
        workspace = create_workspace_lease(
            tenant_id=tenant_id,
            fit_id=own_fit,
            source_snapshot_hash=source_hash,
            execution_attempt_id=f"concurrent-{label}",
        )
        compiledir = create_compiledir_lease(
            execution_id=f"concurrent-{label}",
            worker_id="p9-db-concurrent",
            tenant_id=tenant_id,
            fit_id=own_fit,
            source_snapshot_hash=source_hash,
        )
        artifact_ref = _artifact_ref(
            tenant_id=tenant_id,
            fit_id=own_fit,
            artifact_type="diagnostics",
            artifact_hash=source_hash,
        )
        with sync_engine.connect() as conn:
            with conn.begin():
                bind_transaction_local_tenant(conn, tenant_id=tenant_id)
                assert current_tenant_guc(conn) == str(tenant_id)
                barrier.wait(timeout=10)
                own_visible = conn.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM public.bayesian_model_fits
                        WHERE tenant_id = :tenant_id AND id = :fit_id
                        """
                    ),
                    {"tenant_id": str(tenant_id), "fit_id": str(own_fit)},
                ).scalar_one()
                other_visible = conn.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM public.bayesian_model_fits
                        WHERE id = :fit_id
                        """
                    ),
                    {"fit_id": str(other_fit)},
                ).scalar_one()
        workspace_cleanup = cleanup_fit_attempt(workspace=workspace, compiledir=None)
        compiledir_survived = compiledir.path.exists()
        compiledir_cleanup = cleanup_fit_attempt(workspace=None, compiledir=compiledir)
        return {
            "label": label,
            "guc_after_commit_clean": assert_fresh_checkout_is_clean(
                sync_engine
            ).is_clean,
            "own_visible": int(own_visible),
            "other_visible": int(other_visible),
            "workspace": str(workspace.path),
            "compiledir": str(compiledir.path),
            "artifact_ref": artifact_ref,
            "workspace_removed": workspace_cleanup.workspace_removed,
            "compiledir_survived_workspace_cleanup": compiledir_survived,
            "compiledir_removed": compiledir_cleanup.compiledir_removed,
        }

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            result_a = executor.submit(lane, "a", tenant_a, fit_a, fit_b)
            result_b = executor.submit(lane, "b", tenant_b, fit_b, fit_a)
            payload_a = result_a.result(timeout=20)
            payload_b = result_b.result(timeout=20)
        for payload in (payload_a, payload_b):
            assert payload["own_visible"] == 1
            assert payload["other_visible"] == 0
            assert payload["guc_after_commit_clean"] is True
            assert payload["workspace_removed"] is True
            assert payload["compiledir_survived_workspace_cleanup"] is True
            assert payload["compiledir_removed"] is True
        assert payload_a["workspace"] != payload_b["workspace"]
        assert payload_a["compiledir"] != payload_b["compiledir"]
        assert payload_a["artifact_ref"] != payload_b["artifact_ref"]
    finally:
        sync_engine.dispose()
