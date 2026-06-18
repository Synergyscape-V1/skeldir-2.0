from __future__ import annotations

import os
from datetime import datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.bayesian.dispatch_authority import (
    BAYESIAN_FIT_EXECUTION_TASK,
    dispatch_payload_hash,
)
from app.db.session import engine, get_session


VALID_HASH = "a" * 64
OTHER_HASH = "b" * 64


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _require_db_proofs() -> bool:
    return os.getenv("SKELDIR_B24_P1_REQUIRE_DB_PROOFS", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


async def _assert_table_exists(table_name: str) -> None:
    async with engine.begin() as conn:
        result = await conn.execute(
            text("SELECT to_regclass(:qualified_name)"),
            {"qualified_name": f"public.{table_name}"},
        )
    if result.scalar() is None:
        message = f"B2.4-P1 runtime proof table is missing: {table_name}"
        if _require_db_proofs():
            pytest.fail(message)
        pytest.skip(message)


async def _insert_fit(
    tenant_id: UUID,
    *,
    snapshot_hash: str = VALID_HASH,
    status: str = "pending",
    model_type: str = "mmm",
    model_version: str = "2026.05.p1",
    source_window_start: datetime | None = None,
    source_window_end: datetime | None = None,
) -> UUID:
    fit_id = uuid4()
    window_start = source_window_start or _dt("2026-04-01T00:00:00+00:00")
    window_end = source_window_end or _dt("2026-05-01T00:00:00+00:00")
    async with get_session(tenant_id) as session:
        await session.execute(
            text(
                """
                INSERT INTO bayesian_model_fits (
                    id,
                    tenant_id,
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
                    :id,
                    :tenant_id,
                    :model_type,
                    :model_version,
                    :source_window_start,
                    :source_window_end,
                    :source_snapshot_hash,
                    :status,
                    'eligible',
                    'complete',
                    false,
                    60,
                    1000,
                    2
                )
                """
            ),
            {
                "id": str(fit_id),
                "tenant_id": str(tenant_id),
                "source_snapshot_hash": snapshot_hash,
                "status": status,
                "model_type": model_type,
                "model_version": model_version,
                "source_window_start": window_start,
                "source_window_end": window_end,
            },
        )
    return fit_id


async def _bind_test_dispatch_context(
    session, *, tenant_id: UUID, fit_id: UUID
) -> None:
    dispatch_id = uuid4()
    attempt_id = uuid4()
    payload_hash = dispatch_payload_hash(fit_id=fit_id)
    generation_id = f"p1-artifact-proof-{uuid4().hex[:16]}"
    process_token = f"p1-artifact-token-{uuid4().hex}"
    await session.execute(
        text(
            """
            SELECT public.b24_register_worker_process_authority(
                :generation_id,
                4242,
                1,
                :topology_fingerprint,
                :process_token,
                3600
            )
            """
        ),
        {
            "generation_id": generation_id,
            "topology_fingerprint": VALID_HASH,
            "process_token": process_token,
        },
    )
    await session.execute(
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
                'p1_artifact_constraint_test',
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
            "dispatch_key": f"b24-p1-test:{tenant_id}:{fit_id}:{uuid4()}",
            "task_name": BAYESIAN_FIT_EXECUTION_TASK,
            "attempt_id": str(attempt_id),
            "payload_hash": payload_hash,
            "assigned_worker_generation": generation_id,
        },
    )
    claim_row = (
        (
            await session.execute(
                text(
                    """
                    SELECT *
                    FROM public.b24_claim_fit_dispatch(
                        :dispatch_id,
                        :fit_id,
                        :task_name,
                        :attempt_id,
                        :payload_hash,
                        :worker_generation,
                        4242,
                        :process_token,
                        0,
                        300
                    )
                    """
                ),
                {
                    "dispatch_id": str(dispatch_id),
                    "fit_id": str(fit_id),
                    "task_name": BAYESIAN_FIT_EXECUTION_TASK,
                    "attempt_id": str(attempt_id),
                    "payload_hash": payload_hash,
                    "worker_generation": generation_id,
                    "process_token": process_token,
                },
            )
        )
        .mappings()
        .one()
    )
    assert claim_row["outcome"] == "ACQUIRED"


@pytest.mark.asyncio
async def test_b24_p1_rls_blocks_cross_tenant_and_missing_context(
    test_tenant_pair,
) -> None:
    await _assert_table_exists("bayesian_model_fits")
    tenant_a, tenant_b = test_tenant_pair
    fit_id = await _insert_fit(tenant_a)

    async with get_session(tenant_b) as session:
        result = await session.execute(
            text("SELECT COUNT(*) FROM bayesian_model_fits WHERE id = :fit_id"),
            {"fit_id": str(fit_id)},
        )
        assert int(result.scalar() or 0) == 0

    async with get_session(tenant_a) as session:
        result = await session.execute(
            text("SELECT COUNT(*) FROM bayesian_model_fits WHERE id = :fit_id"),
            {"fit_id": str(fit_id)},
        )
        assert int(result.scalar() or 0) == 1

    async with engine.begin() as conn:
        result = await conn.execute(
            text("SELECT COUNT(*) FROM bayesian_model_fits WHERE id = :fit_id"),
            {"fit_id": str(fit_id)},
        )
        assert int(result.scalar() or 0) == 0


@pytest.mark.asyncio
async def test_b24_p1_hash_state_and_numeric_constraints_fail(test_tenant_pair) -> None:
    await _assert_table_exists("bayesian_model_fits")
    tenant_a, _ = test_tenant_pair

    bad_payloads = [
        {
            "source_snapshot_hash": "a" * 63,
            "status": "pending",
            "runtime_seconds": None,
        },
        {
            "source_snapshot_hash": "a" * 65,
            "status": "pending",
            "runtime_seconds": None,
        },
        {
            "source_snapshot_hash": ("a" * 63) + "z",
            "status": "pending",
            "runtime_seconds": None,
        },
        {
            "source_snapshot_hash": "G" * 64,
            "status": "pending",
            "runtime_seconds": None,
        },
        {
            "source_snapshot_hash": VALID_HASH,
            "status": "not_a_state",
            "runtime_seconds": None,
        },
        {
            "source_snapshot_hash": VALID_HASH,
            "status": "pending",
            "runtime_seconds": -1,
        },
    ]
    for payload in bad_payloads:
        async with get_session(tenant_a) as session:
            with pytest.raises((IntegrityError, DBAPIError)):
                await session.execute(
                    text(
                        """
                        INSERT INTO bayesian_model_fits (
                            tenant_id,
                            model_type,
                            model_version,
                            source_window_start,
                            source_window_end,
                            source_snapshot_hash,
                            status,
                            eligibility_status,
                            data_completeness_status,
                            fallback_applied,
                            runtime_seconds,
                            max_runtime_seconds,
                            max_samples,
                            max_cores
                        )
                        VALUES (
                            :tenant_id,
                            'mmm',
                            '2026.05.p1',
                            now() - interval '1 day',
                            now(),
                            :source_snapshot_hash,
                            :status,
                            'eligible',
                            'complete',
                            false,
                            :runtime_seconds,
                            60,
                            1000,
                            2
                        )
                        """
                    ),
                    {"tenant_id": str(tenant_a), **payload},
                )

    async with get_session(tenant_a) as session:
        with pytest.raises((IntegrityError, DBAPIError)):
            await session.execute(
                text(
                    """
                    INSERT INTO bayesian_model_fits (
                        tenant_id,
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
                        'mmm',
                        '2026.05.p1',
                        now(),
                        now() - interval '1 day',
                        :source_snapshot_hash,
                        'pending',
                        'eligible',
                        'complete',
                        false,
                        60,
                        1000,
                        2
                    )
                    """
                ),
                {"tenant_id": str(tenant_a), "source_snapshot_hash": VALID_HASH},
            )


@pytest.mark.asyncio
async def test_b24_p1_artifact_constraints_and_fk_are_enforced(
    test_tenant_pair,
) -> None:
    await _assert_table_exists("bayesian_artifacts")
    tenant_a, _ = test_tenant_pair
    fit_id = await _insert_fit(tenant_a, snapshot_hash=OTHER_HASH)
    valid_artifact_ref = (
        f"b24://artifact/{tenant_a}/{fit_id}/diagnostics/{VALID_HASH[:12]}"
    )

    async with get_session(tenant_a) as session:
        await _bind_test_dispatch_context(
            session,
            tenant_id=tenant_a,
            fit_id=fit_id,
        )
        await session.execute(
            text(
                """
                INSERT INTO bayesian_artifacts (
                    tenant_id,
                    fit_id,
                    artifact_ref,
                    artifact_hash,
                    artifact_type,
                    storage_backend,
                    artifact_uri_internal,
                    artifact_size_bytes,
                    payload_bytes,
                    payload_byte_count,
                    compression,
                    retention_class
                )
                VALUES (
                    :tenant_id,
                    :fit_id,
                    :artifact_ref,
                    :artifact_hash,
                    'diagnostics',
                    'postgres',
                    :artifact_ref,
                    0,
                    ''::bytea,
                    0,
                    'none',
                    'standard'
                )
                """
            ),
            {
                "tenant_id": str(tenant_a),
                "fit_id": str(fit_id),
                "artifact_ref": valid_artifact_ref,
                "artifact_hash": VALID_HASH,
            },
        )

    async with get_session(tenant_a) as session:
        with pytest.raises((IntegrityError, DBAPIError)):
            await session.execute(
                text(
                    """
                    INSERT INTO bayesian_artifacts (
                        tenant_id,
                        fit_id,
                        artifact_ref,
                        artifact_hash,
                        artifact_type,
                        storage_backend,
                        artifact_uri_internal,
                        artifact_size_bytes,
                        payload_bytes,
                        payload_byte_count,
                        retention_class
                    )
                VALUES (
                    :tenant_id,
                    :fit_id,
                    :artifact_ref,
                    :artifact_hash,
                    'diagnostics',
                    'postgres',
                        :artifact_ref,
                        -1,
                        ''::bytea,
                        0,
                        'standard'
                    )
                    """
                ),
                {
                    "tenant_id": str(tenant_a),
                    "fit_id": str(fit_id),
                    "artifact_ref": f"b24://artifact/{tenant_a}/{fit_id}/diagnostics/{VALID_HASH[:12]}",
                    "artifact_hash": VALID_HASH,
                },
            )

    bad_artifacts = [
        {
            "artifact_ref": f"b24://artifact/{tenant_a}/{fit_id}/invalid/{VALID_HASH[:12]}",
            "artifact_hash": VALID_HASH,
            "artifact_type": "invalid",
            "storage_backend": "postgres",
            "artifact_size_bytes": 0,
        },
        {
            "artifact_ref": f"b24://artifact/{tenant_a}/{fit_id}/diagnostics/{'a' * 12}",
            "artifact_hash": VALID_HASH,
            "artifact_type": "diagnostics",
            "storage_backend": "s3_public",
            "artifact_size_bytes": 0,
        },
        {
            "artifact_ref": f"b24://artifact/{tenant_a}/{fit_id}/diagnostics/{'b' * 12}",
            "artifact_hash": "c" * 63,
            "artifact_type": "diagnostics",
            "storage_backend": "postgres",
            "artifact_size_bytes": 0,
        },
    ]
    for artifact in bad_artifacts:
        async with get_session(tenant_a) as session:
            with pytest.raises((IntegrityError, DBAPIError)):
                await session.execute(
                    text(
                        """
                        INSERT INTO bayesian_artifacts (
                            tenant_id,
                            fit_id,
                            artifact_ref,
                            artifact_hash,
                            artifact_type,
                            storage_backend,
                            artifact_uri_internal,
                            artifact_size_bytes,
                            payload_bytes,
                            payload_byte_count,
                            retention_class
                        )
                        VALUES (
                            :tenant_id,
                            :fit_id,
                            :artifact_ref,
                            :artifact_hash,
                            :artifact_type,
                            :storage_backend,
                            :artifact_ref,
                            :artifact_size_bytes,
                            ''::bytea,
                            :artifact_size_bytes,
                            'standard'
                        )
                        """
                    ),
                    {"tenant_id": str(tenant_a), "fit_id": str(fit_id), **artifact},
                )


@pytest.mark.asyncio
async def test_b24_p1_artifact_fk_is_tenant_bound(test_tenant_pair) -> None:
    await _assert_table_exists("bayesian_artifacts")
    tenant_a, tenant_b = test_tenant_pair
    fit_id = await _insert_fit(
        tenant_a,
        snapshot_hash="c" * 64,
        source_window_start=_dt("2026-02-01T00:00:00+00:00"),
        source_window_end=_dt("2026-03-01T00:00:00+00:00"),
    )
    artifact_ref = f"b24://artifact/{tenant_a}/{fit_id}/diagnostics/{'d' * 12}"

    async with get_session(tenant_b) as session:
        with pytest.raises((IntegrityError, DBAPIError)):
            await session.execute(
                text(
                    """
                    INSERT INTO bayesian_artifacts (
                        tenant_id,
                        fit_id,
                        artifact_ref,
                        artifact_hash,
                        artifact_type,
                        storage_backend,
                        artifact_uri_internal,
                        artifact_size_bytes,
                        payload_bytes,
                        payload_byte_count,
                        retention_class
                    )
                    VALUES (
                        :tenant_id,
                        :fit_id,
                        :artifact_ref,
                        :artifact_hash,
                        'diagnostics',
                        'postgres',
                        :artifact_ref,
                        0,
                        ''::bytea,
                        0,
                        'standard'
                    )
                    """
                ),
                {
                    "tenant_id": str(tenant_b),
                    "fit_id": str(fit_id),
                    "artifact_ref": artifact_ref,
                    "artifact_hash": "d" * 64,
                },
            )

    async with get_session(tenant_b) as session:
        result = await session.execute(
            text(
                """
                SELECT COUNT(*)
                FROM bayesian_artifacts
                WHERE artifact_ref = :artifact_ref
                """
            ),
            {"artifact_ref": artifact_ref},
        )
        assert int(result.scalar() or 0) == 0


@pytest.mark.asyncio
async def test_b24_p1_fit_identity_is_unique_over_window_and_hash(
    test_tenant_pair,
) -> None:
    await _assert_table_exists("bayesian_model_fits")
    tenant_a, _ = test_tenant_pair
    await _insert_fit(
        tenant_a,
        snapshot_hash="e" * 64,
        source_window_start=_dt("2026-01-01T00:00:00+00:00"),
        source_window_end=_dt("2026-02-01T00:00:00+00:00"),
    )

    with pytest.raises((IntegrityError, DBAPIError)):
        await _insert_fit(
            tenant_a,
            snapshot_hash="e" * 64,
            source_window_start=_dt("2026-01-01T00:00:00+00:00"),
            source_window_end=_dt("2026-02-01T00:00:00+00:00"),
        )

    second_fit_id = await _insert_fit(
        tenant_a,
        snapshot_hash="e" * 64,
        source_window_start=_dt("2026-02-01T00:00:00+00:00"),
        source_window_end=_dt("2026-03-01T00:00:00+00:00"),
    )
    async with get_session(tenant_a) as session:
        result = await session.execute(
            text(
                """
                SELECT COUNT(*)
                FROM bayesian_model_fits
                WHERE source_snapshot_hash = :source_snapshot_hash
                  AND model_type = 'mmm'
                  AND model_version = '2026.05.p1'
                """
            ),
            {"source_snapshot_hash": "e" * 64},
        )
        assert int(result.scalar() or 0) == 2
        visible = await session.execute(
            text("SELECT COUNT(*) FROM bayesian_model_fits WHERE id = :fit_id"),
            {"fit_id": str(second_fit_id)},
        )
        assert int(visible.scalar() or 0) == 1

    async with get_session(tenant_a) as session:
        with pytest.raises((IntegrityError, DBAPIError)):
            await session.execute(
                text(
                    """
                    INSERT INTO bayesian_model_fits (
                        tenant_id,
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
                        'mmm',
                        '2026.05.p1',
                        NULL,
                        '2026-04-01T00:00:00+00:00',
                        :source_snapshot_hash,
                        'pending',
                        'eligible',
                        'complete',
                        false,
                        60,
                        1000,
                        2
                    )
                    """
                ),
                {"tenant_id": str(tenant_a), "source_snapshot_hash": "f" * 64},
            )


@pytest.mark.asyncio
async def test_b24_p1_required_indexes_rls_policy_and_corrective_constraints_exist() -> (
    None
):
    await _assert_table_exists("bayesian_model_fits")
    required_indexes = {
        "idx_bayesian_model_fits_tenant_id",
        "idx_bayesian_artifacts_tenant_id",
        "idx_bayesian_model_fits_tenant_model_window",
        "idx_bayesian_model_fits_tenant_source_snapshot_hash",
        "idx_bayesian_model_fits_tenant_status",
        "idx_bayesian_model_fits_tenant_model_eligibility",
        "idx_bayesian_model_fits_tenant_model_fallback",
        "idx_bayesian_artifacts_tenant_fit",
        "idx_bayesian_artifacts_tenant_artifact_ref",
        "idx_bayesian_artifacts_tenant_artifact_hash",
    }
    async with engine.begin() as conn:
        index_result = await conn.execute(
            text(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND tablename IN ('bayesian_model_fits', 'bayesian_artifacts')
                """
            )
        )
        observed = set(index_result.scalars().all())
        assert required_indexes <= observed

        policy_result = await conn.execute(
            text(
                """
                SELECT tablename, policyname, qual, with_check
                FROM pg_policies
                WHERE schemaname = 'public'
                  AND tablename IN ('bayesian_model_fits', 'bayesian_artifacts')
                """
            )
        )
        policies = policy_result.mappings().all()
        assert {row["tablename"] for row in policies} == {
            "bayesian_model_fits",
            "bayesian_artifacts",
        }
        for row in policies:
            assert "app.current_tenant_id" in row["qual"]
            assert "app.current_tenant_id" in row["with_check"]

        constraint_result = await conn.execute(
            text(
                """
                SELECT conname, pg_get_constraintdef(oid) AS definition
                FROM pg_constraint
                WHERE conname IN (
                    'fk_bayesian_artifacts_tenant_fit',
                    'bayesian_model_fits_pkey',
                    'bayesian_artifacts_pkey',
                    'uq_bayesian_model_fits_tenant_model_window_snapshot'
                )
                """
            )
        )
        constraints = {
            row["conname"]: row["definition"] for row in constraint_result.mappings()
        }
        assert (
            "FOREIGN KEY (tenant_id, fit_id)"
            in constraints["fk_bayesian_artifacts_tenant_fit"]
        )
        assert (
            "REFERENCES bayesian_model_fits(tenant_id, id)"
            in constraints["fk_bayesian_artifacts_tenant_fit"]
        )
        assert "PRIMARY KEY (tenant_id, id)" in constraints["bayesian_model_fits_pkey"]
        assert "PRIMARY KEY (tenant_id, id)" in constraints["bayesian_artifacts_pkey"]
        assert (
            "UNIQUE (tenant_id, model_type, model_version, source_window_start, source_window_end, source_snapshot_hash)"
            in constraints["uq_bayesian_model_fits_tenant_model_window_snapshot"]
        )

        partition_result = await conn.execute(
            text(
                """
                SELECT c.relname, c.relkind, pg_get_partkeydef(c.oid) AS partition_key
                FROM pg_class c
                WHERE c.oid IN (
                    'public.bayesian_model_fits'::regclass,
                    'public.bayesian_artifacts'::regclass
                )
                """
            )
        )
        partitions = {row["relname"]: row for row in partition_result.mappings()}
        assert partitions["bayesian_model_fits"]["relkind"] in ("p", b"p")
        assert partitions["bayesian_model_fits"]["partition_key"] == "HASH (tenant_id)"
        assert partitions["bayesian_artifacts"]["relkind"] in ("p", b"p")
        assert partitions["bayesian_artifacts"]["partition_key"] == "HASH (tenant_id)"

        child_result = await conn.execute(
            text(
                """
                SELECT parent.relname AS parent_name, count(*) AS child_count
                FROM pg_inherits
                JOIN pg_class parent ON parent.oid = inhparent
                WHERE parent.relname IN ('bayesian_model_fits', 'bayesian_artifacts')
                GROUP BY parent.relname
                """
            )
        )
        child_counts = {
            row["parent_name"]: int(row["child_count"])
            for row in child_result.mappings()
        }
        assert child_counts["bayesian_model_fits"] == 16
        assert child_counts["bayesian_artifacts"] == 16

        reloptions_result = await conn.execute(
            text(
                """
                SELECT child.reloptions
                FROM pg_inherits
                JOIN pg_class parent ON parent.oid = inhparent
                JOIN pg_class child ON child.oid = inhrelid
                WHERE parent.relname = 'bayesian_model_fits'
                """
            )
        )
        fit_partition_options = [row[0] or [] for row in reloptions_result.all()]
        assert fit_partition_options
        assert all("fillfactor=90" in options for options in fit_partition_options)

        identity_result = await conn.execute(
            text(
                """
                SELECT attname, attnotnull
                FROM pg_attribute
                WHERE attrelid = 'public.bayesian_model_fits'::regclass
                  AND attname IN (
                    'tenant_id',
                    'model_type',
                    'model_version',
                    'source_window_start',
                    'source_window_end',
                    'source_snapshot_hash'
                  )
                """
            )
        )
        identity_columns = {
            row["attname"]: bool(row["attnotnull"])
            for row in identity_result.mappings()
        }
        assert identity_columns == {
            "tenant_id": True,
            "model_type": True,
            "model_version": True,
            "source_window_start": True,
            "source_window_end": True,
            "source_snapshot_hash": True,
        }
