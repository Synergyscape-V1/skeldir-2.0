from __future__ import annotations

import hashlib
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Callable, Iterator
from urllib.parse import urlparse
from uuid import UUID, uuid4

import asyncpg
import psycopg2
import pytest
from psycopg2.extensions import connection as PsycopgConnection
from psycopg2.extensions import cursor as PsycopgCursor

from app.core.secrets import get_database_url, get_migration_database_url
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
    "DIRECTIVE_XVIII_CLASSIFIED_RAW_REJECTION_PROOF",
    "DIRECTIVE_XVIII_TARGET_PRESENT_ZERO_ROW_PROOF",
    "DIRECTIVE_XVIII_ASYNCPG_CLASSIFIED_POST_STATE_PROOF",
    "DIRECTIVE_XVIII_SECURITY_DEFINER_SIGNATURE_PROOF",
    "DIRECTIVE_XVIII_EXPLICIT_RUNTIME_ROLE_BINDING_PROOF",
)
POSTGRES_INTEGRITY_SQLSTATES = frozenset({"23503", "23514"})
POSTGRES_PLPGSQL_RAISE_SQLSTATE = "P0001"
POSTGRES_INSUFFICIENT_PRIVILEGE_SQLSTATE = "42501"
FORBIDDEN_MALFORMED_SQLSTATES = frozenset(
    {
        "42601",  # syntax_error
        "42703",  # undefined_column
        "42P01",  # undefined_table
        "42883",  # undefined_function
        "42804",  # datatype_mismatch
        "22P02",  # invalid_text_representation
        "25P02",  # in_failed_sql_transaction
    }
)
SecurityStateReader = Callable[[], tuple[Any, ...]]


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


def _migration_dsn() -> str:
    return to_sync_postgres_dsn(get_migration_database_url())


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


@contextmanager
def _raw_migration_connection() -> Iterator[PsycopgConnection]:
    _require_protected_db_mode()
    conn = psycopg2.connect(_migration_dsn())
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
    tenant_id: UUID | None = None,
    payload_hash: str,
    generation_id: str,
    pid: int,
    process_token: str,
    recovery_generation: int = 0,
) -> dict[str, Any]:
    if tenant_id is not None:
        _set_tenant(cur, tenant_id)
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


def _expected_runtime_db_user() -> str:
    """DIRECTIVE_XVIII_EXPLICIT_RUNTIME_ROLE_BINDING_PROOF."""

    expected = os.getenv("EXPECTED_RUNTIME_DB_USER")
    assert expected, "EXPECTED_RUNTIME_DB_USER must be explicitly bound in P9 CI"
    assert urlparse(_runtime_dsn()).username == expected
    return expected


def _target_present_fit_state(tenant_id: UUID, fit_id: UUID) -> tuple[Any, ...]:
    """DIRECTIVE_XVIII_TARGET_PRESENT_ZERO_ROW_PROOF."""

    with _raw_migration_connection() as verifier:
        with verifier.cursor() as cur:
            _set_tenant(cur, tenant_id)
            _execute(
                cur,
                """
                SELECT tenant_id, id, status, source_snapshot_hash, fallback_applied
                FROM public.bayesian_model_fits
                WHERE tenant_id = %s AND id = %s
                """,
                (str(tenant_id), str(fit_id)),
            )
            row = cur.fetchone()
    assert row is not None, "accepted zero-row hostile proof requires target_present"
    return row


def _dispatch_mutation_state(tenant_id: UUID, dispatch_id: UUID) -> tuple[Any, ...]:
    with _raw_migration_connection() as verifier:
        with verifier.cursor() as cur:
            _set_tenant(cur, tenant_id)
            _execute(
                cur,
                """
                SELECT
                    tenant_id,
                    id,
                    status,
                    claim_epoch,
                    lease_capability_digest,
                    lease_owner,
                    completed_at,
                    terminal_reason,
                    recovery_generation
                FROM public.b24_fit_dispatch_outbox
                WHERE tenant_id = %s AND id = %s
                """,
                (str(tenant_id), str(dispatch_id)),
            )
            row = cur.fetchone()
    assert row is not None, "SECURITY DEFINER abuse proof requires target_present"
    return row


def _assert_post_state_unchanged(
    reader: SecurityStateReader,
    before: tuple[Any, ...],
) -> None:
    assert reader() == before


def _assert_psycopg_security_rejection(
    exc: psycopg2.Error,
    *,
    expected_sqlstates: set[str],
    expected_message_tokens: tuple[str, ...],
) -> None:
    """DIRECTIVE_XVIII_CLASSIFIED_RAW_REJECTION_PROOF."""

    sqlstate = exc.pgcode or getattr(exc.diag, "sqlstate", None)
    message = str(exc)
    assert sqlstate, f"PostgreSQL rejection missing SQLSTATE: {message}"
    assert sqlstate not in FORBIDDEN_MALFORMED_SQLSTATES, message
    assert (
        sqlstate in expected_sqlstates
    ), f"Unexpected PostgreSQL rejection SQLSTATE {sqlstate}: {message}"
    assert any(token in message for token in expected_message_tokens), message


def _assert_asyncpg_security_rejection(
    exc: asyncpg.PostgresError,
    *,
    expected_sqlstates: set[str],
    expected_message_tokens: tuple[str, ...],
) -> None:
    """DIRECTIVE_XVIII_ASYNCPG_CLASSIFIED_POST_STATE_PROOF."""

    sqlstate = exc.sqlstate
    message = str(exc)
    assert sqlstate, f"asyncpg rejection missing SQLSTATE: {message}"
    assert sqlstate not in FORBIDDEN_MALFORMED_SQLSTATES, message
    assert (
        sqlstate in expected_sqlstates
    ), f"Unexpected asyncpg rejection SQLSTATE {sqlstate}: {message}"
    assert any(token in message for token in expected_message_tokens), message


def _assert_raw_rejected(
    conn: PsycopgConnection,
    sql: str,
    params: tuple[Any, ...] = (),
    *,
    expected_sqlstates: set[str],
    expected_message_tokens: tuple[str, ...],
    allowed_zero_rowcount: bool = False,
    target_present_reader: SecurityStateReader | None = None,
    post_state_verifier: Callable[[tuple[Any, ...]], None] | None = None,
) -> None:
    target_present = target_present_reader() if target_present_reader else None
    with conn.cursor() as cur:
        try:
            _execute(cur, sql, params)
        except psycopg2.Error as exc:
            conn.rollback()
            _assert_psycopg_security_rejection(
                exc,
                expected_sqlstates=expected_sqlstates,
                expected_message_tokens=expected_message_tokens,
            )
            if target_present is not None:
                assert post_state_verifier is not None
                post_state_verifier(target_present)
            return
        rowcount = int(cur.rowcount or 0)
        conn.rollback()
    assert allowed_zero_rowcount and rowcount == 0
    assert target_present is not None
    assert post_state_verifier is not None
    post_state_verifier(target_present)


def _assert_security_definer_signatures_present(cur: PsycopgCursor) -> None:
    """DIRECTIVE_XVIII_SECURITY_DEFINER_SIGNATURE_PROOF."""

    for signature in (
        "public.b24_mark_fit_dispatch_running()",
        "public.b24_complete_fit_dispatch()",
        "public.b24_fail_fit_dispatch_terminal(text)",
        "public.b24_fail_fit_dispatch_recoverable(text)",
    ):
        assert _scalar(cur, "SELECT to_regprocedure(%s)", (signature,)) is not None


def _security_definer_direct_abuse_sql(function_expr: str) -> str:
    """Bind valid hostile GUC values before invoking direct abuse probes."""

    return f"""
        WITH dispatch_context AS MATERIALIZED (
            SELECT
                set_config('app.current_tenant_id', %s, true),
                set_config('app.b24_dispatch_id', %s, true),
                set_config('app.b24_attempt_id', %s, true),
                set_config('app.b24_claim_epoch', '0', true),
                set_config('app.b24_lease_capability', 'unauthorized-lease', true)
        )
        SELECT {function_expr}
        FROM dispatch_context
    """


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


def test_b24_p9_directive_xviii_rejects_malformed_sqlstate_classifiers() -> None:
    """FORBIDDEN_MALFORMED_SQLSTATES negative classifier control."""

    class _Diag:
        sqlstate = "42601"

    class _MalformedPsycopgError(psycopg2.Error):
        pgcode = "42601"
        diag = _Diag()

        def __str__(self) -> str:
            return "syntax error near hostile proof"

    with pytest.raises(AssertionError):
        _assert_psycopg_security_rejection(
            _MalformedPsycopgError(),
            expected_sqlstates={POSTGRES_INSUFFICIENT_PRIVILEGE_SQLSTATE},
            expected_message_tokens=("permission denied",),
        )


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
    assert row[0] == _expected_runtime_db_user()
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
            _assert_security_definer_signatures_present(cur)
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
            expected_sqlstates={
                POSTGRES_PLPGSQL_RAISE_SQLSTATE,
                POSTGRES_INSUFFICIENT_PRIVILEGE_SQLSTATE,
            },
            expected_message_tokens=(
                "b24_dispatch_fence_rejected",
                "row-level security",
            ),
        )
        _assert_raw_rejected(
            conn,
            "UPDATE public.bayesian_model_fits SET status = 'running' WHERE id = %s",
            (str(fit_id),),
            expected_sqlstates={
                POSTGRES_PLPGSQL_RAISE_SQLSTATE,
                POSTGRES_INSUFFICIENT_PRIVILEGE_SQLSTATE,
            },
            expected_message_tokens=(
                "b24_dispatch_fence_rejected",
                "row-level security",
            ),
            allowed_zero_rowcount=True,
            target_present_reader=lambda: _target_present_fit_state(tenant_a, fit_id),
            post_state_verifier=lambda before: _assert_post_state_unchanged(
                lambda: _target_present_fit_state(tenant_a, fit_id),
                before,
            ),
        )
        _assert_raw_rejected(
            conn,
            """
            WITH tenant_context AS (
                SELECT set_config('app.current_tenant_id', %s, true)
            )
            INSERT INTO public.b24_fit_dispatch_outbox (
                tenant_id, id, fit_id, dispatch_key, task_name, attempt_id,
                payload_hash, assigned_worker_generation, assignment_generation,
                assignment_expires_at, assignment_reason, status, next_attempt_at,
                next_recovery_at
            )
            SELECT %s, %s, %s, %s, %s, %s, %s, %s, 1, now() + interval '10 minutes',
                   'missing_context_raw', 'dispatched', now(), now()
            FROM tenant_context
            """,
            (
                str(tenant_b),
                str(tenant_a),
                str(uuid4()),
                str(fit_id),
                f"b24-p9-xvi-missing:{uuid4()}",
                BAYESIAN_FIT_EXECUTION_TASK,
                str(uuid4()),
                "2" * 64,
                generation_id,
            ),
            expected_sqlstates={
                POSTGRES_INSUFFICIENT_PRIVILEGE_SQLSTATE,
                *POSTGRES_INTEGRITY_SQLSTATES,
            },
            expected_message_tokens=(
                "row-level security",
                "permission denied",
                "violates",
            ),
        )
        _assert_raw_rejected(
            conn,
            """
            WITH tenant_context AS (
                SELECT set_config('app.current_tenant_id', %s, true)
            )
            INSERT INTO public.b24_fit_recovery_outbox (
                tenant_id, dispatch_id, fit_id, attempt_id, task_name,
                payload_hash, recovery_generation
            )
            SELECT %s, %s, %s, %s, %s, %s, 99
            FROM tenant_context
            """,
            (
                str(tenant_b),
                str(tenant_a),
                str(dispatch_id),
                str(fit_id),
                str(uuid4()),
                BAYESIAN_FIT_EXECUTION_TASK,
                payload_hash,
            ),
            expected_sqlstates={
                POSTGRES_INSUFFICIENT_PRIVILEGE_SQLSTATE,
                *POSTGRES_INTEGRITY_SQLSTATES,
            },
            expected_message_tokens=(
                "row-level security",
                "permission denied",
                "violates",
            ),
        )
        _assert_raw_rejected(
            conn,
            """
            WITH dispatch_context AS (
                SELECT
                    set_config('app.current_tenant_id', %s, true),
                    set_config('app.b24_dispatch_id', %s, true),
                    set_config('app.b24_attempt_id', %s, true),
                    set_config('app.b24_claim_epoch', '0', true),
                    set_config('app.b24_lease_capability', 'unauthorized-lease', true)
            )
            INSERT INTO public.bayesian_artifacts (
                tenant_id, fit_id, artifact_ref, artifact_hash, artifact_type,
                storage_backend, artifact_uri_internal, artifact_size_bytes,
                payload_bytes, payload_byte_count, lifecycle_status,
                retention_class, policy_version
            )
            SELECT %s, %s, %s, %s, 'diagnostics', 'postgres', %s, 2, %s, 2,
                   'active', 'audit', 'b24-p9-xvi'
            FROM dispatch_context
            """,
            (
                str(tenant_a),
                str(uuid4()),
                str(uuid4()),
                str(tenant_a),
                str(fit_id),
                f"b24://artifact/{tenant_a}/{fit_id}/diagnostics/abcdef123456",
                "3" * 64,
                f"b24://artifact/{tenant_a}/{fit_id}/diagnostics/abcdef123456",
                psycopg2.Binary(b"{}"),
            ),
            expected_sqlstates={
                POSTGRES_PLPGSQL_RAISE_SQLSTATE,
                POSTGRES_INSUFFICIENT_PRIVILEGE_SQLSTATE,
            },
            expected_message_tokens=(
                "b24_dispatch_fence_rejected",
                "row-level security",
            ),
        )
        _assert_raw_rejected(
            conn,
            "DELETE FROM public.bayesian_model_fits WHERE id = %s",
            (str(fit_id),),
            expected_sqlstates={
                POSTGRES_PLPGSQL_RAISE_SQLSTATE,
                POSTGRES_INSUFFICIENT_PRIVILEGE_SQLSTATE,
            },
            expected_message_tokens=(
                "b24_dispatch_delete_forbidden",
                "row-level security",
                "permission denied",
            ),
            allowed_zero_rowcount=True,
            target_present_reader=lambda: _target_present_fit_state(tenant_a, fit_id),
            post_state_verifier=lambda before: _assert_post_state_unchanged(
                lambda: _target_present_fit_state(tenant_a, fit_id),
                before,
            ),
        )

        with conn.cursor() as cur:
            wrong_tenant_before = _target_present_fit_state(tenant_a, fit_id)
            _set_tenant(cur, tenant_b)
            _execute(
                cur,
                "UPDATE public.bayesian_model_fits SET status = 'failed' WHERE id = %s",
                (str(fit_id),),
            )
            assert int(cur.rowcount or 0) == 0
            _assert_post_state_unchanged(
                lambda: _target_present_fit_state(tenant_a, fit_id),
                wrong_tenant_before,
            )
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
                tenant_id=tenant_a,
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
                tenant_id=tenant_a,
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
                tenant_id=tenant_a,
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
                tenant_id=tenant_a,
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
            "public.b24_mark_fit_dispatch_running()",
            "public.b24_complete_fit_dispatch()",
            "public.b24_fail_fit_dispatch_terminal('xvi_direct_abuse')",
            "public.b24_fail_fit_dispatch_recoverable('xvi_direct_abuse')",
        ):
            _assert_raw_rejected(
                conn,
                _security_definer_direct_abuse_sql(function_sql),
                (str(tenant_a), str(uuid4()), str(uuid4())),
                expected_sqlstates={POSTGRES_PLPGSQL_RAISE_SQLSTATE},
                expected_message_tokens=(
                    "b24_dispatch_running_fence_rejected",
                    "b24_dispatch_complete_fence_rejected",
                    "b24_dispatch_failure_fence_rejected",
                    "b24_dispatch_recoverable_failure_fence_rejected",
                ),
                target_present_reader=lambda: _dispatch_mutation_state(
                    tenant_a, dispatch_id
                ),
                post_state_verifier=lambda before: _assert_post_state_unchanged(
                    lambda: _dispatch_mutation_state(tenant_a, dispatch_id),
                    before,
                ),
            )

        with conn.cursor() as cur:
            stale_recovery_claim = _claim_raw(
                cur,
                dispatch_id=dispatch_id,
                fit_id=fit_id,
                attempt_id=attempt_id,
                tenant_id=tenant_a,
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
        assert current_user == _expected_runtime_db_user()

        with pytest.raises(asyncpg.PostgresError) as rejected_insert:
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
        _assert_asyncpg_security_rejection(
            rejected_insert.value,
            expected_sqlstates={
                POSTGRES_PLPGSQL_RAISE_SQLSTATE,
                POSTGRES_INSUFFICIENT_PRIVILEGE_SQLSTATE,
            },
            expected_message_tokens=(
                "b24_dispatch_fence_rejected",
                "row-level security",
            ),
        )

        before = _target_present_fit_state(tenant_a, fit_id)
        async with conn.transaction():
            await conn.execute(
                "SELECT set_config('app.current_tenant_id', $1, true)", str(tenant_b)
            )
            result = await conn.execute(
                "UPDATE public.bayesian_model_fits SET status = 'failed' WHERE id = $1",
                fit_id,
            )
            assert result == "UPDATE 0"
        _assert_post_state_unchanged(
            lambda: _target_present_fit_state(tenant_a, fit_id),
            before,
        )
    finally:
        await conn.close()
