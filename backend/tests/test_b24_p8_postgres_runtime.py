from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from app.bayesian.artifact_repository import (
    persist_artifact_sync,
    prune_expired_artifacts_sync,
    verify_artifact_bytes_sync,
)
from app.bayesian.exceptions import BayesianArtifactQuotaExceededError
from app.core.secrets import get_database_url
from app.db.dsn import to_sync_postgres_dsn
from app.db.session import engine, get_session


START = datetime(2026, 5, 1, tzinfo=timezone.utc)
END = datetime(2026, 6, 1, tzinfo=timezone.utc)
VALID_HASH = "8" * 64


def _require_db_proofs() -> bool:
    return os.getenv("SKELDIR_B24_P8_REQUIRE_DB_PROOFS", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


pytestmark = pytest.mark.skipif(
    not _require_db_proofs() and os.getenv("CI") != "true",
    reason="B2.4-P8 PostgreSQL proof is opt-in for local runs",
)


async def _assert_table_exists(table_name: str) -> None:
    try:
        async with engine.begin() as conn:
            result = await conn.execute(
                text("SELECT to_regclass(:qualified_name)"),
                {"qualified_name": f"public.{table_name}"},
            )
    except OperationalError as exc:
        message = f"B2.4-P8 PostgreSQL runtime proof unavailable: {exc}"
        if _require_db_proofs():
            pytest.fail(message)
        pytest.skip(message)
    if result.scalar() is None:
        message = f"B2.4-P8 PostgreSQL runtime proof table is missing: {table_name}"
        if _require_db_proofs():
            pytest.fail(message)
        pytest.skip(message)


async def _insert_test_fit(tenant_id: UUID, *, fit_id: UUID | None = None) -> UUID:
    resolved_fit_id = fit_id or uuid4()
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
                    fallback_reason,
                    max_runtime_seconds,
                    max_samples,
                    max_cores
                )
                VALUES (
                    :tenant_id,
                    :fit_id,
                    'bayesian_attribution_confidence',
                    :model_version,
                    :source_window_start,
                    :source_window_end,
                    :source_snapshot_hash,
                    'running',
                    'eligible',
                    'complete',
                    false,
                    NULL,
                    60,
                    1000,
                    2
                )
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "fit_id": str(resolved_fit_id),
                "model_version": f"b24-p8-db-{uuid4().hex[:12]}",
                "source_window_start": START,
                "source_window_end": END,
                "source_snapshot_hash": VALID_HASH,
            },
        )
    return resolved_fit_id


@pytest.mark.asyncio
@pytest.mark.integration
async def test_b24_p8_repository_persists_verifies_quota_and_prunes(
    test_tenant_pair,
) -> None:
    await _assert_table_exists("bayesian_artifacts")
    await _assert_table_exists("bayesian_artifact_storage_quotas")
    tenant_id, _ = test_tenant_pair
    fit_id = await _insert_test_fit(tenant_id)
    sync_engine = create_engine(
        to_sync_postgres_dsn(get_database_url()),
        pool_pre_ping=True,
        pool_size=1,
        max_overflow=0,
    )
    try:
        with sync_engine.begin() as conn:
            conn.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )
            artifact = persist_artifact_sync(
                conn,
                tenant_id=tenant_id,
                fit_id=fit_id,
                artifact_type="diagnostics",
                payload={
                    "schema_version": "b24-p8-test-v1",
                    "fit_id": str(fit_id),
                    "r_hat_max": 1.0,
                    "ess_min": 500.0,
                    "divergence_count": 0,
                },
                retention_class="ephemeral",
            )
            replay = persist_artifact_sync(
                conn,
                tenant_id=tenant_id,
                fit_id=fit_id,
                artifact_type="diagnostics",
                payload={
                    "schema_version": "b24-p8-test-v1",
                    "fit_id": str(fit_id),
                    "r_hat_max": 1.0,
                    "ess_min": 500.0,
                    "divergence_count": 0,
                },
                retention_class="ephemeral",
            )
            assert replay["idempotent_replay"] is True
            assert verify_artifact_bytes_sync(
                conn,
                tenant_id=tenant_id,
                artifact_ref=str(artifact["artifact_ref"]),
            )
            row = (
                conn.execute(
                    text(
                        """
                    SELECT artifact_hash,
                           artifact_uri_internal,
                           artifact_size_bytes,
                           payload_byte_count,
                           lifecycle_status,
                           storage_backend
                    FROM public.bayesian_artifacts
                    WHERE tenant_id = :tenant_id
                      AND artifact_ref = :artifact_ref
                    """
                    ),
                    {
                        "tenant_id": str(tenant_id),
                        "artifact_ref": str(artifact["artifact_ref"]),
                    },
                )
                .mappings()
                .one()
            )
            assert row["artifact_hash"] == artifact["artifact_hash"]
            assert row["artifact_uri_internal"] == artifact["artifact_ref"]
            assert row["artifact_size_bytes"] == row["payload_byte_count"]
            assert row["lifecycle_status"] == "active"
            assert row["storage_backend"] == "postgres"

            conn.execute(
                text(
                    """
                    UPDATE public.bayesian_artifact_storage_quotas
                    SET quota_bytes = active_bytes
                    WHERE tenant_id = :tenant_id
                    """
                ),
                {"tenant_id": str(tenant_id)},
            )
            with pytest.raises(BayesianArtifactQuotaExceededError):
                persist_artifact_sync(
                    conn,
                    tenant_id=tenant_id,
                    fit_id=fit_id,
                    artifact_type="summary",
                    payload={"schema_version": "b24-p8-test-v1", "fit_id": str(fit_id)},
                    retention_class="standard",
                )

            conn.execute(
                text(
                    """
                    UPDATE public.bayesian_artifacts
                    SET expires_at = now() - interval '1 second'
                    WHERE tenant_id = :tenant_id
                      AND artifact_ref = :artifact_ref
                    """
                ),
                {
                    "tenant_id": str(tenant_id),
                    "artifact_ref": str(artifact["artifact_ref"]),
                },
            )
            pruned = prune_expired_artifacts_sync(
                conn, tenant_id=tenant_id, batch_limit=10
            )
            assert pruned["pruned_count"] == 1
            assert pruned["pruned_bytes"] == artifact["artifact_size_bytes"]
            tombstone = (
                conn.execute(
                    text(
                        """
                    SELECT lifecycle_status,
                           payload_bytes IS NULL AS payload_removed,
                           payload_byte_count,
                           pruned_metadata->>'artifact_hash' AS pruned_hash
                    FROM public.bayesian_artifacts
                    WHERE tenant_id = :tenant_id
                      AND artifact_ref = :artifact_ref
                    """
                    ),
                    {
                        "tenant_id": str(tenant_id),
                        "artifact_ref": str(artifact["artifact_ref"]),
                    },
                )
                .mappings()
                .one()
            )
            assert tombstone == {
                "lifecycle_status": "pruned",
                "payload_removed": True,
                "payload_byte_count": 0,
                "pruned_hash": artifact["artifact_hash"],
            }
    finally:
        sync_engine.dispose()
