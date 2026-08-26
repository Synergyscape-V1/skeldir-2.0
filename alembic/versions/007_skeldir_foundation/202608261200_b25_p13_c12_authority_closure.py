"""B2.5-P13 C12: close self-issued cross-tenant authority surfaces.

Revision ID: 202608261200
Revises: 202608251200
"""

from __future__ import annotations

from alembic import op


revision = "202608261200"
down_revision = "202608251200"
branch_labels = None
depends_on = None


FIT_TABLES = ("bayesian_model_fits",) + tuple(
    f"bayesian_model_fits_p{partition:02d}" for partition in range(16)
)


def _role_exists(role_name: str) -> bool:
    return (
        op.get_bind()
        .exec_driver_sql("SELECT to_regrole(%s)", (role_name,))
        .scalar_one()
        is not None
    )


def _execute_if_role_exists(role_name: str, statement: str) -> None:
    if _role_exists(role_name):
        op.get_bind().exec_driver_sql(statement)


def _replace_fit_policies(*, include_resolution_capability: bool) -> None:
    for table_name in FIT_TABLES:
        policy_name = f"tenant_isolation_policy_{table_name}"
        op.execute(
            f"DROP POLICY IF EXISTS {policy_name} ON public.{table_name}"
        )
        if include_resolution_capability:
            using = """
                tenant_id = NULLIF(
                    current_setting('app.current_tenant_id', true), ''
                )::uuid
                OR id = NULLIF(
                    current_setting('app.b24_fit_resolution_id', true), ''
                )::uuid
            """
        else:
            using = """
                tenant_id = NULLIF(
                    current_setting('app.current_tenant_id', true), ''
                )::uuid
            """
        op.execute(
            f"""
            CREATE POLICY {policy_name}
                ON public.{table_name}
                USING ({using})
                WITH CHECK (
                    tenant_id = NULLIF(
                        current_setting('app.current_tenant_id', true), ''
                    )::uuid
                )
            """
        )


def upgrade() -> None:
    # Tenant context remains application context. A fit identifier is not a
    # capability, so knowledge of a foreign fit ID never widens that context.
    _replace_fit_policies(include_resolution_capability=False)

    # Remove every policy whose extraordinary authority can be minted with a
    # caller-controlled GUC. The old claim-digest policies are also removed:
    # C10 made broker messages secret-free and all live digest columns are null.
    op.execute(
        """
        DROP POLICY IF EXISTS dispatch_capability_claim_select_b24_fit_dispatch_outbox
            ON public.b24_fit_dispatch_outbox;
        DROP POLICY IF EXISTS dispatch_capability_claim_update_b24_fit_dispatch_outbox
            ON public.b24_fit_dispatch_outbox;
        DROP POLICY IF EXISTS dispatch_claim_function_access_b24_fit_dispatch_outbox
            ON public.b24_fit_dispatch_outbox;
        DROP POLICY IF EXISTS dispatch_recovery_reconciler_select_b24_fit_dispatch_outbox
            ON public.b24_fit_dispatch_outbox;
        DROP POLICY IF EXISTS dispatch_recovery_reconciler_update_b24_fit_dispatch_outbox
            ON public.b24_fit_dispatch_outbox;
        DROP POLICY IF EXISTS recovery_reconciler_policy_b24_fit_recovery_outbox
            ON public.b24_fit_recovery_outbox;
        DROP POLICY IF EXISTS function_access_b24_worker_process_authority
            ON public.b24_worker_process_authority;

        CREATE POLICY c12_dispatch_internal_select
            ON public.b24_fit_dispatch_outbox FOR SELECT
            USING (
                current_user = 'migration_owner'
                AND session_user = 'app_worker'
            );
        CREATE POLICY c12_dispatch_internal_update
            ON public.b24_fit_dispatch_outbox FOR UPDATE
            USING (
                current_user = 'migration_owner'
                AND session_user = 'app_worker'
            )
            WITH CHECK (
                current_user = 'migration_owner'
                AND session_user = 'app_worker'
            );

        CREATE POLICY c12_recovery_internal_select
            ON public.b24_fit_recovery_outbox FOR SELECT
            USING (
                current_user = 'migration_owner'
                AND session_user = 'app_worker'
            );
        CREATE POLICY c12_recovery_internal_insert
            ON public.b24_fit_recovery_outbox FOR INSERT
            WITH CHECK (
                current_user = 'migration_owner'
                AND session_user = 'app_worker'
            );
        CREATE POLICY c12_recovery_internal_update
            ON public.b24_fit_recovery_outbox FOR UPDATE
            USING (
                current_user = 'migration_owner'
                AND session_user = 'app_worker'
            )
            WITH CHECK (
                current_user = 'migration_owner'
                AND session_user = 'app_worker'
            );

        CREATE POLICY c12_worker_authority_internal_select
            ON public.b24_worker_process_authority FOR SELECT
            USING (
                current_user = 'migration_owner'
                AND session_user IN ('app_worker', 'app_dispatch_publisher')
            );
        CREATE POLICY c12_worker_authority_internal_insert
            ON public.b24_worker_process_authority FOR INSERT
            WITH CHECK (
                current_user = 'migration_owner'
                AND session_user = 'app_worker'
            );
        CREATE POLICY c12_worker_authority_internal_update
            ON public.b24_worker_process_authority FOR UPDATE
            USING (
                current_user = 'migration_owner'
                AND session_user = 'app_worker'
            )
            WITH CHECK (
                current_user = 'migration_owner'
                AND session_user = 'app_worker'
            );
        """
    )

    # Recovery remains globally functional, but only through a bounded state
    # machine. The caller chooses limits, never a tenant or target row.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b24_lease_fit_recovery_rows(
            p_batch_size integer DEFAULT 25,
            p_stale_publishing_seconds integer DEFAULT 300
        )
        RETURNS TABLE (
            recovery_id uuid,
            tenant_id uuid,
            dispatch_id uuid,
            fit_id uuid,
            task_name text,
            attempt_id uuid,
            payload_hash text,
            recovery_generation integer,
            publish_attempt_count integer
        )
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
        BEGIN
            RETURN QUERY
            WITH due AS (
                SELECT recovery.tenant_id, recovery.id, recovery.dispatch_id
                FROM public.b24_fit_recovery_outbox recovery
                WHERE (
                    recovery.status IN ('pending', 'failed_retryable')
                    OR (
                        recovery.status = 'publishing'
                        AND recovery.updated_at <= now() - (
                            LEAST(
                                GREATEST(
                                    COALESCE(p_stale_publishing_seconds, 300), 1
                                ),
                                86400
                            ) * interval '1 second'
                        )
                    )
                )
                ORDER BY recovery.created_at ASC, recovery.id ASC
                LIMIT LEAST(GREATEST(COALESCE(p_batch_size, 25), 1), 100)
                FOR UPDATE SKIP LOCKED
            ),
            assigned AS (
                UPDATE public.b24_fit_dispatch_outbox dispatch
                SET status = 'dispatching',
                    assigned_worker_generation = NULL,
                    assignment_generation = dispatch.assignment_generation + 1,
                    assignment_expires_at = now() + interval '10 minutes',
                    assignment_reason = 'recovery_shared_eligible',
                    dispatching_started_at = now(),
                    updated_at = now()
                FROM due
                WHERE dispatch.tenant_id = due.tenant_id
                  AND dispatch.id = due.dispatch_id
                RETURNING
                    dispatch.tenant_id,
                    dispatch.id AS dispatch_id,
                    dispatch.fit_id,
                    dispatch.task_name,
                    dispatch.attempt_id,
                    dispatch.payload_hash::text AS payload_hash,
                    dispatch.recovery_generation
            )
            UPDATE public.b24_fit_recovery_outbox recovery
            SET status = 'publishing',
                publish_attempt_count = recovery.publish_attempt_count + 1,
                updated_at = now()
            FROM due
            JOIN assigned
              ON assigned.tenant_id = due.tenant_id
             AND assigned.dispatch_id = due.dispatch_id
            WHERE recovery.tenant_id = due.tenant_id
              AND recovery.id = due.id
            RETURNING
                recovery.id,
                recovery.tenant_id,
                recovery.dispatch_id,
                assigned.fit_id,
                assigned.task_name,
                assigned.attempt_id,
                assigned.payload_hash,
                assigned.recovery_generation,
                recovery.publish_attempt_count;
        END
        $$;

        CREATE OR REPLACE FUNCTION public.b24_mark_fit_recovery_published(
            p_tenant_id uuid,
            p_recovery_id uuid,
            p_dispatch_id uuid
        )
        RETURNS boolean
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
        DECLARE
            v_count integer;
        BEGIN
            UPDATE public.b24_fit_recovery_outbox recovery
            SET status = 'published',
                published_at = now(),
                updated_at = now(),
                last_error = NULL
            WHERE recovery.tenant_id = p_tenant_id
              AND recovery.id = p_recovery_id
              AND recovery.dispatch_id = p_dispatch_id
              AND recovery.status = 'publishing';
            GET DIAGNOSTICS v_count = ROW_COUNT;
            IF v_count <> 1 THEN
                RETURN false;
            END IF;

            UPDATE public.b24_fit_dispatch_outbox dispatch
            SET status = 'dispatched',
                dispatched_at = now(),
                updated_at = now()
            WHERE dispatch.tenant_id = p_tenant_id
              AND dispatch.id = p_dispatch_id
              AND dispatch.status = 'dispatching';
            GET DIAGNOSTICS v_count = ROW_COUNT;
            IF v_count <> 1 THEN
                RAISE EXCEPTION 'b24_recovery_dispatch_transition_missing';
            END IF;
            RETURN true;
        END
        $$;

        CREATE OR REPLACE FUNCTION public.b24_mark_fit_recovery_failed(
            p_tenant_id uuid,
            p_recovery_id uuid,
            p_dispatch_id uuid,
            p_error text,
            p_max_attempts integer DEFAULT 5
        )
        RETURNS boolean
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
        DECLARE
            v_count integer;
        BEGIN
            UPDATE public.b24_fit_recovery_outbox recovery
            SET status = CASE
                    WHEN recovery.publish_attempt_count >= LEAST(
                        GREATEST(COALESCE(p_max_attempts, 5), 1), 100
                    ) THEN 'quarantined'
                    ELSE 'failed_retryable'
                END,
                last_error = left(COALESCE(p_error, ''), 2048),
                updated_at = now()
            WHERE recovery.tenant_id = p_tenant_id
              AND recovery.id = p_recovery_id
              AND recovery.dispatch_id = p_dispatch_id
              AND recovery.status = 'publishing';
            GET DIAGNOSTICS v_count = ROW_COUNT;
            RETURN v_count = 1;
        END
        $$;

        REVOKE ALL ON FUNCTION public.b24_lease_fit_recovery_rows(integer, integer)
            FROM PUBLIC;
        REVOKE ALL ON FUNCTION public.b24_mark_fit_recovery_published(uuid, uuid, uuid)
            FROM PUBLIC;
        REVOKE ALL ON FUNCTION public.b24_mark_fit_recovery_failed(uuid, uuid, uuid, text, integer)
            FROM PUBLIC;
        """
    )

    # No login role receives direct authority over the global worker registry.
    # Worker and publisher code use bounded SECURITY DEFINER functions instead.
    for role_name in (
        "app_user",
        "app_worker",
        "app_dispatch_publisher",
        "app_rw",
        "app_ro",
    ):
        _execute_if_role_exists(
            role_name,
            f"REVOKE ALL ON public.b24_worker_process_authority FROM {role_name}",
        )

    _execute_if_role_exists(
        "app_worker",
        """
        GRANT EXECUTE ON FUNCTION public.b24_lease_fit_recovery_rows(integer, integer)
            TO app_worker;
        GRANT EXECUTE ON FUNCTION public.b24_mark_fit_recovery_published(uuid, uuid, uuid)
            TO app_worker;
        GRANT EXECUTE ON FUNCTION public.b24_mark_fit_recovery_failed(uuid, uuid, uuid, text, integer)
            TO app_worker;
        REVOKE ALL ON FUNCTION public.b24_lease_fit_recovery_rows(integer, integer)
            FROM app_user;
        REVOKE ALL ON FUNCTION public.b24_mark_fit_recovery_published(uuid, uuid, uuid)
            FROM app_user;
        REVOKE ALL ON FUNCTION public.b24_mark_fit_recovery_failed(uuid, uuid, uuid, text, integer)
            FROM app_user;
        """,
    )


def downgrade() -> None:
    op.execute(
        """
        DROP FUNCTION IF EXISTS public.b24_mark_fit_recovery_failed(
            uuid, uuid, uuid, text, integer
        );
        DROP FUNCTION IF EXISTS public.b24_mark_fit_recovery_published(
            uuid, uuid, uuid
        );
        DROP FUNCTION IF EXISTS public.b24_lease_fit_recovery_rows(
            integer, integer
        );

        DROP POLICY IF EXISTS c12_dispatch_internal_select
            ON public.b24_fit_dispatch_outbox;
        DROP POLICY IF EXISTS c12_dispatch_internal_update
            ON public.b24_fit_dispatch_outbox;
        DROP POLICY IF EXISTS c12_recovery_internal_select
            ON public.b24_fit_recovery_outbox;
        DROP POLICY IF EXISTS c12_recovery_internal_insert
            ON public.b24_fit_recovery_outbox;
        DROP POLICY IF EXISTS c12_recovery_internal_update
            ON public.b24_fit_recovery_outbox;
        DROP POLICY IF EXISTS c12_worker_authority_internal_select
            ON public.b24_worker_process_authority;
        DROP POLICY IF EXISTS c12_worker_authority_internal_insert
            ON public.b24_worker_process_authority;
        DROP POLICY IF EXISTS c12_worker_authority_internal_update
            ON public.b24_worker_process_authority;

        CREATE POLICY dispatch_capability_claim_select_b24_fit_dispatch_outbox
            ON public.b24_fit_dispatch_outbox FOR SELECT
            USING (
                claim_capability_digest = NULLIF(
                    current_setting('app.b24_claim_capability_digest', true), ''
                )
                AND claim_capability_expires_at > now()
            );
        CREATE POLICY dispatch_capability_claim_update_b24_fit_dispatch_outbox
            ON public.b24_fit_dispatch_outbox FOR UPDATE
            USING (
                claim_capability_digest = NULLIF(
                    current_setting('app.b24_claim_capability_digest', true), ''
                )
                AND claim_capability_expires_at > now()
            )
            WITH CHECK (
                claim_capability_digest = NULLIF(
                    current_setting('app.b24_claim_capability_digest', true), ''
                )
                AND claim_capability_expires_at > now()
            );
        CREATE POLICY dispatch_claim_function_access_b24_fit_dispatch_outbox
            ON public.b24_fit_dispatch_outbox
            USING (current_setting('app.b24_dispatch_claim_access', true) = 'on')
            WITH CHECK (current_setting('app.b24_dispatch_claim_access', true) = 'on');
        CREATE POLICY dispatch_recovery_reconciler_select_b24_fit_dispatch_outbox
            ON public.b24_fit_dispatch_outbox FOR SELECT
            USING (current_setting('app.b24_recovery_reconciler', true) = 'on');
        CREATE POLICY dispatch_recovery_reconciler_update_b24_fit_dispatch_outbox
            ON public.b24_fit_dispatch_outbox FOR UPDATE
            USING (current_setting('app.b24_recovery_reconciler', true) = 'on')
            WITH CHECK (current_setting('app.b24_recovery_reconciler', true) = 'on');
        CREATE POLICY recovery_reconciler_policy_b24_fit_recovery_outbox
            ON public.b24_fit_recovery_outbox
            USING (current_setting('app.b24_recovery_reconciler', true) = 'on')
            WITH CHECK (current_setting('app.b24_recovery_reconciler', true) = 'on');
        CREATE POLICY function_access_b24_worker_process_authority
            ON public.b24_worker_process_authority
            USING (current_setting('app.b24_worker_authority_access', true) = 'on')
            WITH CHECK (current_setting('app.b24_worker_authority_access', true) = 'on');
        """
    )
    _replace_fit_policies(include_resolution_capability=True)
    _execute_if_role_exists(
        "app_user",
        "GRANT SELECT, INSERT ON public.b24_worker_process_authority TO app_user",
    )
