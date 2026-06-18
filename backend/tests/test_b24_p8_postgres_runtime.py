from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import bindparam, create_engine, select, text
from sqlalchemy.exc import InvalidRequestError, OperationalError

from app.bayesian.artifact_repository import (
    BayesianArtifactRepository,
    persist_artifact_sync,
    prune_expired_artifacts_sync,
    verify_artifact_bytes_sync,
)
from app.bayesian.dispatch_authority import (
    BAYESIAN_FIT_EXECUTION_TASK,
    BayesianDispatchClaim,
    BayesianDispatchLease,
    BayesianWorkerClaimAuthority,
    claim_fit_dispatch_sync,
    dispatch_payload_hash,
    mark_dispatch_running_sync,
    register_worker_process_authority_sync,
)
from app.bayesian.models import BayesianArtifact
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
                    'queued',
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


def _bind_test_dispatch_context(conn, *, tenant_id: UUID, fit_id: UUID) -> None:
    dispatch_id = uuid4()
    attempt_id = uuid4()
    payload_hash = dispatch_payload_hash(fit_id=fit_id)
    generation_id = f"p8-artifact-proof-{uuid4().hex[:16]}"
    process_token = f"p8-artifact-token-{uuid4().hex}"
    worker_authority = BayesianWorkerClaimAuthority(
        generation_id=generation_id,
        pid=4242,
        process_token=process_token,
    )
    register_worker_process_authority_sync(
        conn,
        generation_id=worker_authority.generation_id,
        pid=worker_authority.pid,
        parent_pid=1,
        topology_fingerprint="8" * 64,
        process_token=worker_authority.process_token,
        ttl_seconds=3600,
    )
    conn.execute(
        text(
            """
            INSERT INTO public.b24_fit_dispatch_outbox (
                tenant_id,
                id,
                fit_id,
                dispatch_key,
                task_name,
                attempt_id,
                payload_hash,
                assigned_worker_generation,
                assignment_generation,
                assignment_expires_at,
                assignment_reason,
                status,
                next_attempt_at,
                next_recovery_at
            )
            VALUES (
                :tenant_id,
                :dispatch_id,
                :fit_id,
                :dispatch_key,
                :task_name,
                :attempt_id,
                :payload_hash,
                :assigned_worker_generation,
                1,
                now() + interval '10 minutes',
                'p8_artifact_lifecycle_test',
                'dispatched',
                now(),
                now() + interval '1 hour'
            )
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "dispatch_id": str(dispatch_id),
            "fit_id": str(fit_id),
            "dispatch_key": f"b24-p8-test:{tenant_id}:{fit_id}",
            "task_name": BAYESIAN_FIT_EXECUTION_TASK,
            "attempt_id": str(attempt_id),
            "payload_hash": payload_hash,
            "assigned_worker_generation": generation_id,
        },
    )
    lease = claim_fit_dispatch_sync(
        conn,
        claim=BayesianDispatchClaim(
            dispatch_id=dispatch_id,
            fit_id=fit_id,
            task_name=BAYESIAN_FIT_EXECUTION_TASK,
            attempt_id=attempt_id,
            payload_hash=payload_hash,
            recovery_generation=0,
        ),
        worker_authority=worker_authority,
        lease_seconds=300,
    )
    assert isinstance(lease, BayesianDispatchLease)
    mark_dispatch_running_sync(conn, lease=lease)
    conn.execute(
        text(
            """
            UPDATE public.bayesian_model_fits
            SET status = 'running',
                updated_at = now()
            WHERE tenant_id = :tenant_id
              AND id = :fit_id
            """
        ),
        {"tenant_id": str(tenant_id), "fit_id": str(fit_id)},
    )


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
            _bind_test_dispatch_context(conn, tenant_id=tenant_id, fit_id=fit_id)
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
            assert replay["rejected"] is False
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
            rejected = persist_artifact_sync(
                conn,
                tenant_id=tenant_id,
                fit_id=fit_id,
                artifact_type="summary",
                payload={"schema_version": "b24-p8-test-v1", "fit_id": str(fit_id)},
                retention_class="standard",
            )
            assert rejected["rejected"] is True
            assert rejected["rejection_reason"] == "tenant_quota_exceeded"
            rejected_row = (
                conn.execute(
                    text(
                        """
                    SELECT lifecycle_status,
                           payload_bytes IS NULL AS no_payload_bytes,
                           payload_byte_count,
                           pruned_metadata->>'rejection_reason' AS rejection_reason
                    FROM public.bayesian_artifacts
                    WHERE tenant_id = :tenant_id
                      AND artifact_ref = :artifact_ref
                    """
                    ),
                    {
                        "tenant_id": str(tenant_id),
                        "artifact_ref": str(rejected["artifact_ref"]),
                    },
                )
                .mappings()
                .one()
            )
            assert rejected_row == {
                "lifecycle_status": "rejected",
                "no_payload_bytes": True,
                "payload_byte_count": 0,
                "rejection_reason": "tenant_quota_exceeded",
            }
            quota_after_rejection = (
                conn.execute(
                    text(
                        """
                    SELECT active_bytes,
                           active_artifact_count,
                           rejected_count,
                           last_rejection_reason
                    FROM public.bayesian_artifact_storage_quotas
                    WHERE tenant_id = :tenant_id
                    """
                    ),
                    {"tenant_id": str(tenant_id)},
                )
                .mappings()
                .one()
            )
            assert quota_after_rejection["active_bytes"] == row["artifact_size_bytes"]
            assert quota_after_rejection["active_artifact_count"] == 1
            assert quota_after_rejection["rejected_count"] == 1
            assert (
                quota_after_rejection["last_rejection_reason"]
                == "tenant_quota_exceeded"
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
        async with get_session(tenant_id) as session:
            repository = BayesianArtifactRepository(session)
            metadata = await repository.get_metadata_by_ref(
                tenant_id=tenant_id,
                artifact_ref=str(artifact["artifact_ref"]),
            )
            assert not hasattr(metadata, "payload_bytes")
            orm_artifact = (
                await session.execute(
                    select(BayesianArtifact).where(
                        BayesianArtifact.tenant_id == tenant_id,
                        BayesianArtifact.artifact_ref == str(artifact["artifact_ref"]),
                    )
                )
            ).scalar_one()
            with pytest.raises(InvalidRequestError):
                _ = orm_artifact.payload_bytes
    finally:
        sync_engine.dispose()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_b24_p8_atomic_quota_allows_exactly_two_concurrent_artifacts(
    test_tenant_pair,
) -> None:
    await _assert_table_exists("bayesian_artifacts")
    await _assert_table_exists("bayesian_artifact_storage_quotas")
    tenant_id, _ = test_tenant_pair
    worker_count = 6
    allowed_count = 2
    fit_ids = [await _insert_test_fit(tenant_id) for _ in range(worker_count)]
    sync_engine = create_engine(
        to_sync_postgres_dsn(get_database_url()),
        pool_pre_ping=True,
        pool_size=worker_count,
        max_overflow=0,
    )
    try:
        with sync_engine.begin() as conn:
            conn.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )
            conn.execute(
                text(
                    """
                    INSERT INTO public.bayesian_artifact_storage_quotas (
                        tenant_id,
                        policy_version,
                        quota_bytes,
                        max_artifact_count,
                        active_bytes,
                        pruned_bytes,
                        active_artifact_count,
                        pruned_artifact_count,
                        rejected_count
                    )
                    VALUES (
                        :tenant_id,
                        'b24-p8-artifact-policy-v1',
                        1048576,
                        :allowed_count,
                        0,
                        0,
                        0,
                        0,
                        0
                    )
                    ON CONFLICT (tenant_id)
                    DO UPDATE SET
                        quota_bytes = EXCLUDED.quota_bytes,
                        max_artifact_count = EXCLUDED.max_artifact_count,
                        active_bytes = 0,
                        pruned_bytes = 0,
                        active_artifact_count = 0,
                        pruned_artifact_count = 0,
                        rejected_count = 0,
                        last_rejection_reason = NULL,
                        updated_at = now()
                    """
                ),
                {"tenant_id": str(tenant_id), "allowed_count": allowed_count},
            )

        barrier = threading.Barrier(worker_count)

        def worker(index: int, fit_id: UUID) -> dict[str, object]:
            with sync_engine.begin() as conn:
                conn.execute(
                    text(
                        "SELECT set_config('app.current_tenant_id', :tenant_id, true)"
                    ),
                    {"tenant_id": str(tenant_id)},
                )
                _bind_test_dispatch_context(conn, tenant_id=tenant_id, fit_id=fit_id)
                conn.execute(text("SET LOCAL lock_timeout = '5s'"))
                conn.execute(text("SET LOCAL statement_timeout = '15s'"))
                backend_pid = int(
                    conn.execute(text("SELECT pg_backend_pid()")).scalar_one()
                )
                barrier.wait(timeout=10)
                artifact = persist_artifact_sync(
                    conn,
                    tenant_id=tenant_id,
                    fit_id=fit_id,
                    artifact_type="diagnostics",
                    payload={
                        "schema_version": "b24-p8-concurrency-v1",
                        "fit_id": str(fit_id),
                        "worker_index": index,
                    },
                    retention_class="standard",
                )
                return {
                    "backend_pid": backend_pid,
                    "rejected": bool(artifact["rejected"]),
                    "artifact_ref": str(artifact["artifact_ref"]),
                }

        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = [
                executor.submit(worker, index, fit_id)
                for index, fit_id in enumerate(fit_ids)
            ]
            results = [future.result(timeout=30) for future in as_completed(futures)]

        assert len({result["backend_pid"] for result in results}) == worker_count
        assert sum(not result["rejected"] for result in results) == allowed_count
        assert sum(result["rejected"] for result in results) == (
            worker_count - allowed_count
        )
        artifact_refs = [str(result["artifact_ref"]) for result in results]

        with sync_engine.begin() as conn:
            conn.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )
            quota = (
                conn.execute(
                    text(
                        """
                    SELECT active_artifact_count,
                           active_bytes,
                           max_artifact_count,
                           rejected_count,
                           last_rejection_reason
                    FROM public.bayesian_artifact_storage_quotas
                    WHERE tenant_id = :tenant_id
                    """
                    ),
                    {"tenant_id": str(tenant_id)},
                )
                .mappings()
                .one()
            )
            artifacts = (
                conn.execute(
                    text(
                        """
                    SELECT lifecycle_status,
                           COUNT(*) AS artifact_count,
                           COUNT(payload_bytes) AS payload_row_count,
                           COALESCE(SUM(payload_byte_count), 0) AS payload_byte_count
                    FROM public.bayesian_artifacts
                    WHERE tenant_id = :tenant_id
                      AND artifact_ref IN :artifact_refs
                    GROUP BY lifecycle_status
                    """
                    ).bindparams(bindparam("artifact_refs", expanding=True)),
                    {
                        "tenant_id": str(tenant_id),
                        "artifact_refs": artifact_refs,
                    },
                )
                .mappings()
                .all()
            )
            by_status = {row["lifecycle_status"]: row for row in artifacts}
            active = by_status["active"]
            rejected = by_status["rejected"]

            assert quota["active_artifact_count"] == allowed_count
            assert quota["active_artifact_count"] <= quota["max_artifact_count"]
            assert quota["active_bytes"] == active["payload_byte_count"]
            assert quota["rejected_count"] == worker_count - allowed_count
            assert quota["last_rejection_reason"] == "tenant_quota_exceeded"
            assert active["artifact_count"] == allowed_count
            assert active["payload_row_count"] == allowed_count
            assert rejected["artifact_count"] == worker_count - allowed_count
            assert rejected["payload_row_count"] == 0
            assert rejected["payload_byte_count"] == 0
    finally:
        sync_engine.dispose()
