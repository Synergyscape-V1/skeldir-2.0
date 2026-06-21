from __future__ import annotations

import hashlib
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator
from uuid import UUID, uuid4

import asyncpg
import psycopg2
import pytest
from psycopg2.extensions import connection as PsycopgConnection
from psycopg2.extensions import cursor as PsycopgCursor

from app.core.secrets import get_database_url
from app.db.dsn import to_sync_postgres_dsn


START = datetime(2026, 5, 1, tzinfo=timezone.utc)
END = datetime(2026, 6, 1, tzinfo=timezone.utc)
BAYESIAN_FIT_EXECUTION_TASK = "app.tasks.bayesian.execute_fit_intent"
B24_P6_MODEL_TYPE = "bayesian_attribution_confidence"
B24_P6_MODEL_VERSION = "b24-p6-real-fit-v1"
RAW_DRIVER_PROOF_TOKENS = (
    "DIRECTIVE_XVI_RAW_PSYCOPG_RUNTIME_ROLE_PROOF",
    "DIRECTIVE_XVI_RAW_ASYNCPG_REPRESENTATIVE_PROOF",
    "DIRECTIVE_XVI_SECURITY_DEFINER_DIRECT_ABUSE_PROOF",
)


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
    reason="B2.4-P9 raw PostgreSQL driver proof is opt-in for local runs",
)


def _require_protected_db_mode() -> None:
    if _require_db_proofs():
        return
    if _is_ci():
        pytest.fail("B2.4-P9 raw driver CI requires SKELDIR_B24_P9_REQUIRE_DB_PROOFS=1")
    pytest.skip("B2.4-P9 raw PostgreSQL driver proof is opt-in for local runs")


def _runtime_dsn() -> str:
    return to_sync_postgres_dsn(get_database_url())


def _payload_hash(fit_id: UUID) -> str:
    return hashlib.sha256(
        f"{BAYESIAN_FIT_EXECUTION_TASK}:{fit_id}".encode("utf-8")
    ).hexdigest()


@contextmanager
def _raw_runtime_connection() -> Iterator[PsycopgConnection]:
    _require_protected_db_mode()
    conn = psycopg2.connect(_runtime_dsn())
    try:
        yield conn
    finally:
        conn.close()


def _execute(cur: PsycopgCursor, sql: str, params: tuple[Any, ...] = ()) -> None:
    cur.execute(sql, params)


def _scalar(cur: PsycopgCursor, sql: str, params: tuple[Any, ...] = ()) -> Any:
    cur.execute(sql, params)
    row = cur.fetchone()
    assert row is not None
    return row[0]


def _set_tenant(cur: PsycopgCursor, tenant_id: UUID) -> None:
    _execute(
        cur, "SELECT set_config('app.current_tenant_id', %s, true)", (str(tenant_id),)
    )


def _payload_attempt(fit_id: UUID) -> tuple[UUID, str]:
    return uuid4(), _payload_hash(fit_id)


def _insert_fit_raw(cur: PsycopgCursor, tenant_id: UUID, fit_id: UUID) -> None:
    _set_tenant(cur, tenant_id)
    _execute(
        cur,
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
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'queued', 'eligible', 'complete', false, 60, 160, 1)
        """,
        (
            str(tenant_id),
            str(fit_id),
            B24_P6_MODEL_TYPE,
            B24_P6_MODEL_VERSION,
            START,
            END,
            hashlib.sha256(str(fit_id).encode("utf-8")).hexdigest(),
        ),
    )


def _insert_dispatch_raw(
    cur: PsycopgCursor,
    *,
    tenant_id: UUID,
    fit_id: UUID,
    dispatch_id: UUID,
    attempt_id: UUID,
    payload_hash: str,
    generation_id: str,
    recovery_generation: int = 0,
    assignment_reason: str = "runtime_raw_driver_test",
) -> None:
    _set_tenant(cur, tenant_id)
    _execute(
        cur,
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
            recovery_generation,
            status,
            next_attempt_at,
            next_recovery_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1, now() + interval '10 minutes',
                %s, %s, 'dispatched', now(), now() + interval '10 minutes')
        """,
        (
            str(tenant_id),
            str(dispatch_id),
            str(fit_id),
            f"b24-p9-xvi-raw:{tenant_id}:{fit_id}:{uuid4()}",
            BAYESIAN_FIT_EXECUTION_TASK,
            str(attempt_id),
            payload_hash,
            generation_id,
            assignment_reason,
            recovery_generation,
        ),
    )


def _register_worker_raw(
    cur: PsycopgCursor,
    *,
    generation_id: str,
    pid: int,
    process_token: str,
) -> None:
    _execute(
        cur,
        """
        SELECT public.b24_register_worker_process_authority(%s, %s, %s, %s, %s, %s)
        """,
        (generation_id, pid, 1, "c" * 64, process_token, 3600),
    )


def _claim_raw(
    cur: PsycopgCursor,
    *,
    dispatch_id: UUID,
    fit_id: UUID,
    attempt_id: UUID,
    payload_hash: str,
    generation_id: str,
    pid: int,
    process_token: str,
    recovery_generation: int = 0,
) -> dict[str, Any]:
    _execute(
        cur,
        """
        SELECT outcome, tenant_id, fit_id, dispatch_id, attempt_id, claim_epoch,
               lease_capability, lease_expires_at
        FROM public.b24_claim_fit_dispatch(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            str(dispatch_id),
            str(fit_id),
            BAYESIAN_FIT_EXECUTION_TASK,
            str(attempt_id),
            payload_hash,
            generation_id,
            pid,
            process_token,
            recovery_generation,
            120,
        ),
    )
    row = cur.fetchone()
    assert row is not None
    keys = (
        "outcome",
        "tenant_id",
        "fit_id",
        "dispatch_id",
        "attempt_id",
        "claim_epoch",
        "lease_capability",
        "lease_expires_at",
    )
    return dict(zip(keys, row, strict=True))


def _bind_raw_lease(cur: PsycopgCursor, lease: dict[str, Any]) -> None:
    _execute(
        cur,
        """
        SELECT
            set_config('app.current_tenant_id', %s, true),
            set_config('app.b24_dispatch_id', %s, true),
            set_config('app.b24_attempt_id', %s, true),
            set_config('app.b24_claim_epoch', %s, true),
            set_config('app.b24_lease_capability', %s, true)
        """,
        (
            str(lease["tenant_id"]),
            str(lease["dispatch_id"]),
            str(lease["attempt_id"]),
            str(lease["claim_epoch"]),
            str(lease["lease_capability"]),
        ),
    )


def _assert_raw_rejected(
    conn: PsycopgConnection,
    sql: str,
    params: tuple[Any, ...] = (),
    *,
    allowed_zero_rowcount: bool = False,
) -> None:
    with conn.cursor() as cur:
        try:
            _execute(cur, sql, params)
        except psycopg2.Error:
            conn.rollback()
            return
        rowcount = int(cur.rowcount or 0)
        conn.rollback()
    assert allowed_zero_rowcount and rowcount == 0


def _assert_no_authority_mutation(
    cur: PsycopgCursor,
    *,
    tenant_id: UUID,
    dispatch_id: UUID,
) -> None:
    _set_tenant(cur, tenant_id)
    _execute(
        cur,
        """
        SELECT status, claim_epoch, lease_capability_digest, completed_at
        FROM public.b24_fit_dispatch_outbox
        WHERE tenant_id = %s AND id = %s
        """,
        (str(tenant_id), str(dispatch_id)),
    )
    row = cur.fetchone()
    assert row is not None
    assert row[0] in {"dispatched", "failed_retryable", "stale_recovered"}
    assert row[2] is None or row[0] == "dispatched"
    assert row[3] is None


def _assert_runtime_role_hygiene(cur: PsycopgCursor) -> None:
    """DIRECTIVE_XVI_RAW_PSYCOPG_RUNTIME_ROLE_PROOF."""

    _execute(
        cur,
        """
        SELECT
            current_user,
            rol.rolsuper,
            rol.rolbypassrls,
            pg_has_role(current_user, 'migration_owner', 'member') AS is_migration_member,
            EXISTS (
                SELECT 1
                FROM pg_class cls
                JOIN pg_namespace ns ON ns.oid = cls.relnamespace
                WHERE ns.nspname = 'public'
                  AND cls.relname IN (
                    'bayesian_model_fits',
                    'bayesian_artifacts',
                    'b24_fit_dispatch_outbox',
                    'b24_fit_recovery_outbox',
                    'b24_worker_process_authority'
                  )
                  AND pg_get_userbyid(cls.relowner) = current_user
            ) AS owns_protected_tables,
            EXISTS (
                SELECT 1
                FROM pg_auth_members member
                JOIN pg_roles role_ref ON role_ref.oid = member.roleid
                JOIN pg_roles member_ref ON member_ref.oid = member.member
                WHERE member_ref.rolname = current_user
                  AND role_ref.rolbypassrls
            ) AS inherits_bypassrls
        FROM pg_roles rol
        WHERE rol.rolname = current_user
        """,
    )
    row = cur.fetchone()
    assert row is not None
    assert row[0] == (os.getenv("EXPECTED_RUNTIME_DB_USER") or "app_user")
    assert row[1] is False
    assert row[2] is False
    assert row[3] is False
    assert row[4] is False
    assert row[5] is False


@pytest.mark.asyncio
@pytest.mark.integration
async def test_b24_p9_directive_xvi_raw_psycopg_runtime_role_rejects_hostile_sql(
    test_tenant_pair,
) -> None:
    tenant_a, tenant_b = test_tenant_pair
    fit_id = uuid4()
    dispatch_id = uuid4()
    attempt_id, payload_hash = _payload_attempt(fit_id)
    generation_id = f"xvi-raw-generation-{uuid4().hex[:16]}"
    process_token = f"xvi-raw-token-{uuid4().hex}"
    pid = 4701

    with _raw_runtime_connection() as conn:
        with conn.cursor() as cur:
            _assert_runtime_role_hygiene(cur)
            _insert_fit_raw(cur, tenant_a, fit_id)
            _insert_dispatch_raw(
                cur,
                tenant_id=tenant_a,
                fit_id=fit_id,
                dispatch_id=dispatch_id,
                attempt_id=attempt_id,
                payload_hash=payload_hash,
                generation_id=generation_id,
            )
            _register_worker_raw(
                cur,
                generation_id=generation_id,
                pid=pid,
                process_token=process_token,
            )
        conn.commit()

        _assert_raw_rejected(
            conn,
            """
            INSERT INTO public.bayesian_model_fits (
                tenant_id, id, model_type, model_version, source_window_start,
                source_window_end, source_snapshot_hash, status, eligibility_status,
                data_completeness_status, fallback_applied, max_runtime_seconds,
                max_samples, max_cores
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'queued', 'eligible', 'complete',
                    false, 60, 160, 1)
            """,
            (
                str(tenant_a),
                str(uuid4()),
                B24_P6_MODEL_TYPE,
                B24_P6_MODEL_VERSION,
                START,
                END,
                "1" * 64,
            ),
        )
        _assert_raw_rejected(
            conn,
            "UPDATE public.bayesian_model_fits SET status = 'running' WHERE id = %s",
            (str(fit_id),),
            allowed_zero_rowcount=True,
        )
        _assert_raw_rejected(
            conn,
            """
            INSERT INTO public.b24_fit_dispatch_outbox (
                tenant_id, id, fit_id, dispatch_key, task_name, attempt_id,
                payload_hash, assigned_worker_generation, assignment_generation,
                assignment_expires_at, assignment_reason, status, next_attempt_at,
                next_recovery_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1, now() + interval '10 minutes',
                    'missing_context_raw', 'dispatched', now(), now())
            """,
            (
                str(tenant_a),
                str(uuid4()),
                str(fit_id),
                f"b24-p9-xvi-missing:{uuid4()}",
                BAYESIAN_FIT_EXECUTION_TASK,
                str(uuid4()),
                "2" * 64,
                generation_id,
            ),
        )
        _assert_raw_rejected(
            conn,
            """
            INSERT INTO public.b24_fit_recovery_outbox (
                tenant_id, dispatch_id, fit_id, attempt_id, task_name,
                payload_hash, recovery_generation
            )
            VALUES (%s, %s, %s, %s, %s, %s, 99)
            """,
            (
                str(tenant_a),
                str(dispatch_id),
                str(fit_id),
                str(uuid4()),
                BAYESIAN_FIT_EXECUTION_TASK,
                payload_hash,
            ),
        )
        _assert_raw_rejected(
            conn,
            """
            INSERT INTO public.bayesian_artifacts (
                tenant_id, fit_id, artifact_ref, artifact_hash, artifact_type,
                storage_backend, artifact_uri_internal, artifact_size_bytes,
                payload_bytes, payload_byte_count, lifecycle_status,
                retention_class, policy_version
            )
            VALUES (%s, %s, %s, %s, 'diagnostics', 'postgres', %s, 2, %s, 2,
                    'active', 'audit', 'b24-p9-xvi')
            """,
            (
                str(tenant_a),
                str(fit_id),
                f"b24://artifact/{tenant_a}/{fit_id}/diagnostics/abcdef123456",
                "3" * 64,
                f"b24://artifact/{tenant_a}/{fit_id}/diagnostics/abcdef123456",
                psycopg2.Binary(b"{}"),
            ),
        )
        _assert_raw_rejected(
            conn,
            "DELETE FROM public.bayesian_model_fits WHERE id = %s",
            (str(fit_id),),
            allowed_zero_rowcount=True,
        )

        with conn.cursor() as cur:
            _set_tenant(cur, tenant_b)
            _execute(
                cur,
                "UPDATE public.bayesian_model_fits SET status = 'failed' WHERE id = %s",
                (str(fit_id),),
            )
            assert int(cur.rowcount or 0) == 0
            _execute(
                cur,
                """
                INSERT INTO public.bayesian_model_fits (
                    tenant_id, id, model_type, model_version, source_window_start,
                    source_window_end, source_snapshot_hash, status,
                    eligibility_status, data_completeness_status, fallback_applied,
                    max_runtime_seconds, max_samples, max_cores
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'queued', 'eligible',
                        'complete', false, 60, 160, 1)
                """,
                (
                    str(tenant_b),
                    str(uuid4()),
                    B24_P6_MODEL_TYPE,
                    B24_P6_MODEL_VERSION,
                    START,
                    END,
                    "4" * 64,
                ),
            )
        conn.commit()

        with conn.cursor() as cur:
            forged_claim = _claim_raw(
                cur,
                dispatch_id=dispatch_id,
                fit_id=fit_id,
                attempt_id=attempt_id,
                payload_hash=payload_hash,
                generation_id=generation_id,
                pid=pid,
                process_token="forged-process-token",
            )
            wrong_pid_claim = _claim_raw(
                cur,
                dispatch_id=dispatch_id,
                fit_id=fit_id,
                attempt_id=attempt_id,
                payload_hash=payload_hash,
                generation_id=generation_id,
                pid=pid + 1,
                process_token=process_token,
            )
            wrong_task_claim = _claim_raw(
                cur,
                dispatch_id=dispatch_id,
                fit_id=fit_id,
                attempt_id=attempt_id,
                payload_hash="5" * 64,
                generation_id=generation_id,
                pid=pid,
                process_token=process_token,
            )
            lease = _claim_raw(
                cur,
                dispatch_id=dispatch_id,
                fit_id=fit_id,
                attempt_id=attempt_id,
                payload_hash=payload_hash,
                generation_id=generation_id,
                pid=pid,
                process_token=process_token,
            )
            assert forged_claim["outcome"] == "UNAUTHORIZED"
            assert wrong_pid_claim["outcome"] == "UNAUTHORIZED"
            assert wrong_task_claim["outcome"] == "UNAUTHORIZED"
            assert lease["outcome"] == "ACQUIRED"
            _bind_raw_lease(cur, lease)
            _execute(cur, "SELECT public.b24_mark_fit_dispatch_running()")
            _execute(
                cur,
                "UPDATE public.bayesian_model_fits SET status = 'running' WHERE id = %s",
                (str(fit_id),),
            )
            _execute(
                cur,
                "SELECT public.b24_fail_fit_dispatch_recoverable(%s)",
                ("directive_xvi_raw_recoverable_ack",),
            )
        conn.commit()

        with conn.cursor() as cur:
            _bind_raw_lease(cur, lease)
            with pytest.raises(psycopg2.Error, match="b24_dispatch_fence_rejected"):
                _execute(
                    cur,
                    "UPDATE public.bayesian_model_fits SET updated_at = now() WHERE id = %s",
                    (str(fit_id),),
                )
        conn.rollback()

        for function_sql in (
            "SELECT public.b24_mark_fit_dispatch_running()",
            "SELECT public.b24_complete_fit_dispatch()",
            "SELECT public.b24_fail_fit_dispatch_terminal('xvi_direct_abuse')",
            "SELECT public.b24_fail_fit_dispatch_recoverable('xvi_direct_abuse')",
        ):
            _assert_raw_rejected(conn, function_sql)

        with conn.cursor() as cur:
            stale_recovery_claim = _claim_raw(
                cur,
                dispatch_id=dispatch_id,
                fit_id=fit_id,
                attempt_id=attempt_id,
                payload_hash=payload_hash,
                generation_id=generation_id,
                pid=pid,
                process_token=process_token,
                recovery_generation=0,
            )
            assert stale_recovery_claim["outcome"] == "UNAUTHORIZED"
            _assert_no_authority_mutation(
                cur,
                tenant_id=tenant_a,
                dispatch_id=dispatch_id,
            )
        conn.commit()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_b24_p9_directive_xvi_raw_asyncpg_representative_hostile_writes(
    test_tenant_pair,
) -> None:
    """DIRECTIVE_XVI_RAW_ASYNCPG_REPRESENTATIVE_PROOF."""

    tenant_a, tenant_b = test_tenant_pair
    fit_id = uuid4()

    with _raw_runtime_connection() as conn:
        with conn.cursor() as cur:
            _assert_runtime_role_hygiene(cur)
            _insert_fit_raw(cur, tenant_a, fit_id)
        conn.commit()

    async_dsn = _runtime_dsn()
    conn = await asyncpg.connect(async_dsn)
    try:
        current_user = await conn.fetchval("SELECT current_user")
        assert current_user == (os.getenv("EXPECTED_RUNTIME_DB_USER") or "app_user")

        with pytest.raises(Exception):
            async with conn.transaction():
                await conn.execute(
                    """
                    INSERT INTO public.bayesian_model_fits (
                        tenant_id, id, model_type, model_version,
                        source_window_start, source_window_end, source_snapshot_hash,
                        status, eligibility_status, data_completeness_status,
                        fallback_applied, max_runtime_seconds, max_samples, max_cores
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, 'queued', 'eligible',
                            'complete', false, 60, 160, 1)
                    """,
                    tenant_a,
                    uuid4(),
                    B24_P6_MODEL_TYPE,
                    B24_P6_MODEL_VERSION,
                    START,
                    END,
                    "6" * 64,
                )

        async with conn.transaction():
            await conn.execute(
                "SELECT set_config('app.current_tenant_id', $1, true)", str(tenant_b)
            )
            result = await conn.execute(
                "UPDATE public.bayesian_model_fits SET status = 'failed' WHERE id = $1",
                fit_id,
            )
            assert result == "UPDATE 0"
    finally:
        await conn.close()
