"""B2.5-P13 C6 worker authority, planner reachability, and truth closure.

Revision ID: 202608201200
Revises: 202608191200
Create Date: 2026-08-20 12:00:00.000000

The API principal may mark source data dirty and read completed evidence, but it
cannot mint worker generations, claim dispatch leases, or write fit/outbox truth.
Only the separately provisioned ``app_worker`` login owns those capabilities.
The planner tenant selector leases a non-payload wakeup ledger populated in the
same transaction as dirty-event insertion. This avoids bypassing FORCE RLS while
retaining bounded, replayable, revision-aware cross-tenant scheduling.
"""

from __future__ import annotations

from alembic import op


revision = "202608201200"
down_revision = "202608191200"
branch_labels = None
depends_on = None


TERMINAL_FIT_STATUSES = (
    "succeeded",
    "failed",
    "timeout",
    "worker_lost",
    "fallback_only",
    "cancelled",
)

# Machine-related to the Trust read dependencies by
# contracts/trust-api/confidence-projection-dependencies.v1.yaml and the C6 gate.
# Adding a fit column to the signed projection without adding it here is a
# merge-blocking failure.
TRUST_FIT_DEPENDENCY_COLUMNS = (
    "model_type",
    "model_version",
    "source_window_start",
    "source_window_end",
    "source_snapshot_hash",
    "status",
    "data_completeness_status",
    "fallback_applied",
    "fallback_reason",
    "completed_at",
    "updated_at",
    "diagnostic_status",
    "diagnostic_failure_reason",
    "credible_interval_status",
    "confidence_bucket",
    "confidence_bucket_reason",
    "confidence_policy_version",
    "confidence_semantics_version",
    "confidence_deterministic_revenue_minor",
    "confidence_deterministic_row_count",
    "confidence_match_verdict_count",
    "confidence_currency_count",
    "confidence_classified_at",
    "confidence_evidence_snapshot_hash",
    "source_read_started_at",
    "source_read_completed_at",
    "artifact_ref",
    "artifact_hash",
)

WORKER_CONTROL_FUNCTIONS = (
    "public.b24_register_worker_process_authority(text, integer, integer, text, text, integer)",
    "public.b24_next_active_worker_generation()",
    "public.b24_claim_fit_dispatch(uuid, uuid, text, uuid, text, text, integer, text, integer, integer)",
    "public.b24_mark_fit_dispatch_running()",
    "public.b24_complete_fit_dispatch()",
    "public.b24_fail_fit_dispatch_terminal(text)",
    "public.b24_fail_fit_dispatch_recoverable(text)",
    "public.b24_create_fit_recovery_wakeups(integer)",
)


def _changed(columns: tuple[str, ...]) -> str:
    return "\n               OR ".join(
        f"NEW.{column} IS DISTINCT FROM OLD.{column}" for column in columns
    )


def _terminal_status_sql() -> str:
    return ", ".join(f"'{status}'" for status in TERMINAL_FIT_STATUSES)


def _grant_worker(statement: str) -> None:
    """Apply a worker grant only when deployment provisioning created the role."""

    escaped = statement.replace("'", "''")
    op.execute(
        f"""
        DO $$
        BEGIN
            IF to_regrole('app_worker') IS NOT NULL THEN
                EXECUTE '{escaped}';
            END IF;
        END
        $$;
        """
    )


def upgrade() -> None:
    # The deployment provisioner creates the LOGIN worker before migration.
    # Legacy migration-only jobs intentionally have no CREATEROLE capability;
    # when no worker exists, grants remain absent rather than falling back to an
    # application identity. Reverse inheritance is rejected whenever the
    # provisioned role is present.
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regrole('app_worker') IS NOT NULL THEN
                IF pg_has_role('app_user', 'app_worker', 'MEMBER') THEN
                    RAISE EXCEPTION 'b25_p13_c6_app_user_must_not_inherit_worker';
                END IF;
                IF pg_has_role('app_ro', 'app_worker', 'MEMBER')
                   OR pg_has_role('app_rw', 'app_worker', 'MEMBER') THEN
                    RAISE EXCEPTION 'b25_p13_c6_shared_role_must_not_inherit_worker';
                END IF;
            END IF;
        END
        $$;
        """
    )

    for function_signature in WORKER_CONTROL_FUNCTIONS:
        op.execute(
            f"REVOKE ALL ON FUNCTION {function_signature} "
            "FROM PUBLIC, app_user, app_rw, app_ro"
        )
        _grant_worker(f"GRANT EXECUTE ON FUNCTION {function_signature} TO app_worker")

    # Web/read identities retain SELECT and dirty-event INSERT authority only.
    # The planner and compute worker use the dedicated login.
    op.execute(
        """
        REVOKE INSERT, UPDATE, DELETE ON public.bayesian_model_fits
            FROM app_user, app_rw, app_ro;
        REVOKE INSERT, UPDATE, DELETE ON public.bayesian_artifacts
            FROM app_user, app_rw, app_ro;
        REVOKE INSERT, UPDATE, DELETE ON public.b24_fit_dispatch_outbox
            FROM app_user, app_rw, app_ro;
        REVOKE INSERT, UPDATE, DELETE ON public.b24_active_execution_leases
            FROM app_user, app_rw, app_ro;

        """
    )
    for worker_grant in (
        "GRANT SELECT, INSERT, UPDATE ON public.bayesian_model_fits TO app_worker",
        "GRANT SELECT, INSERT, UPDATE ON public.bayesian_artifacts TO app_worker",
        "GRANT SELECT, INSERT, UPDATE ON public.b24_fit_dispatch_outbox TO app_worker",
        "GRANT SELECT, INSERT, UPDATE ON public.b24_fit_recovery_outbox TO app_worker",
        "GRANT SELECT, INSERT, UPDATE, DELETE ON public.b24_active_execution_leases TO app_worker",
        "GRANT SELECT, INSERT, UPDATE ON public.b24_dirty_events TO app_worker",
        "GRANT SELECT, INSERT, UPDATE ON public.b24_feature_authority_build_requests TO app_worker",
        "GRANT SELECT, INSERT, UPDATE ON public.b24_feature_authority_build_outbox TO app_worker",
        # The worker owns its Postgres-backed Celery transport and result path;
        # these relations are queue mechanics, never tenant truth.
        "GRANT SELECT, INSERT, UPDATE, DELETE ON public.kombu_queue TO app_worker",
        "GRANT SELECT, INSERT, UPDATE, DELETE ON public.kombu_message TO app_worker",
        "GRANT SELECT, INSERT, UPDATE, DELETE ON public.celery_taskmeta TO app_worker",
        "GRANT SELECT, INSERT, UPDATE, DELETE ON public.celery_tasksetmeta TO app_worker",
        "GRANT SELECT, INSERT, UPDATE ON public.worker_failed_jobs TO app_worker",
        "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_worker",
    ):
        _grant_worker(worker_grant)

    # Successor-safe terminal truth: all fields on which the Trust confidence
    # projection depends are frozen, including identity and source window.
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION public.b24_fit_status_is_terminal(p_status text)
        RETURNS boolean
        LANGUAGE sql
        IMMUTABLE
        AS $$ SELECT p_status IN ({_terminal_status_sql()}) $$;

        CREATE OR REPLACE FUNCTION public.b24_enforce_terminal_fit_truth()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF public.b24_fit_status_is_terminal(OLD.status)
               AND ({_changed(TRUST_FIT_DEPENDENCY_COLUMNS)}) THEN
                RAISE EXCEPTION 'b24_terminal_fit_truth_immutable';
            END IF;
            RETURN NEW;
        END
        $$;
        """
    )

    # A global wakeup ledger is deliberately not tenant-queryable. It contains
    # no financial/source payload, is writable only through a dirty-event
    # trigger, and is callable only through the two worker functions below.
    # The revision prevents a completion acknowledgement from deleting a new
    # wakeup that arrived while the prior revision was being processed.
    op.execute(
        """
        CREATE TABLE public.b24_fit_planner_wakeups (
            tenant_id uuid PRIMARY KEY
                REFERENCES public.tenants(id) ON DELETE CASCADE,
            wakeup_revision bigint NOT NULL DEFAULT 1
                CHECK (wakeup_revision > 0),
            status text NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'leased')),
            lease_owner text,
            lease_expires_at timestamptz,
            observed_at timestamptz NOT NULL DEFAULT now(),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CHECK (
                (status = 'pending' AND lease_owner IS NULL
                    AND lease_expires_at IS NULL)
                OR
                (status = 'leased' AND lease_owner IS NOT NULL
                    AND lease_expires_at IS NOT NULL)
            )
        );
        ALTER TABLE public.b24_fit_planner_wakeups ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.b24_fit_planner_wakeups FORCE ROW LEVEL SECURITY;
        CREATE POLICY b24_fit_planner_wakeups_worker_only
            ON public.b24_fit_planner_wakeups
            FOR ALL TO PUBLIC
            USING (current_user = 'app_worker')
            WITH CHECK (current_user = 'app_worker');

        CREATE OR REPLACE FUNCTION public.b24_signal_fit_planner_wakeup()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public, pg_temp
        AS $$
        BEGIN
            IF NEW.status IN ('pending', 'authority_retry_ready')
               AND (
                    TG_OP = 'INSERT'
                    OR OLD.status IS DISTINCT FROM NEW.status
               ) THEN
                INSERT INTO public.b24_fit_planner_wakeups (
                    tenant_id, observed_at
                ) VALUES (NEW.tenant_id, NEW.observed_at)
                ON CONFLICT (tenant_id) DO UPDATE
                SET wakeup_revision =
                        b24_fit_planner_wakeups.wakeup_revision + 1,
                    observed_at = LEAST(
                        b24_fit_planner_wakeups.observed_at,
                        EXCLUDED.observed_at
                    ),
                    updated_at = now();
            END IF;
            RETURN NEW;
        END
        $$;

        DO $$
        BEGIN
            IF to_regrole('app_worker') IS NOT NULL THEN
                EXECUTE 'GRANT CREATE ON SCHEMA public TO app_worker';
                EXECUTE 'ALTER FUNCTION public.b24_signal_fit_planner_wakeup() '
                        'OWNER TO app_worker';
                EXECUTE 'REVOKE CREATE ON SCHEMA public FROM app_worker';
            END IF;
        END
        $$;

        CREATE TRIGGER trg_b24_signal_fit_planner_wakeup
        AFTER INSERT OR UPDATE OF status ON public.b24_dirty_events
        FOR EACH ROW EXECUTE FUNCTION public.b24_signal_fit_planner_wakeup();
        REVOKE ALL ON FUNCTION public.b24_signal_fit_planner_wakeup()
            FROM PUBLIC, app_user, app_rw, app_ro;

        INSERT INTO public.b24_fit_planner_wakeups (tenant_id, observed_at)
        SELECT tenant_id, min(observed_at)
        FROM public.b24_dirty_events
        WHERE status IN ('pending', 'authority_retry_ready')
           OR (
                status = 'leased'
                AND lease_expires_at IS NOT NULL
                AND lease_expires_at <= now()
           )
        GROUP BY tenant_id
        ON CONFLICT (tenant_id) DO NOTHING;
        REVOKE ALL ON public.b24_fit_planner_wakeups
            FROM PUBLIC, app_user, app_rw, app_ro;

        CREATE OR REPLACE FUNCTION public.b24_due_fit_planner_tenants(
            p_lease_owner text,
            p_limit integer DEFAULT 25
        )
        RETURNS TABLE(tenant_id uuid, wakeup_revision bigint)
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public, pg_temp
        AS $$
        BEGIN
            IF session_user <> 'app_worker' THEN
                RAISE EXCEPTION 'b24_worker_database_identity_required';
            END IF;
            IF p_lease_owner IS NULL OR btrim(p_lease_owner) = '' THEN
                RAISE EXCEPTION 'b24_fit_planner_lease_owner_required';
            END IF;
            RETURN QUERY
            WITH due AS (
                SELECT wakeup.tenant_id
                FROM public.b24_fit_planner_wakeups wakeup
                WHERE wakeup.status = 'pending'
                   OR (
                        wakeup.status = 'leased'
                        AND wakeup.lease_expires_at <= now()
                   )
                ORDER BY wakeup.observed_at, wakeup.tenant_id
                LIMIT LEAST(GREATEST(p_limit, 1), 100)
                FOR UPDATE SKIP LOCKED
            )
            UPDATE public.b24_fit_planner_wakeups wakeup
            SET status = 'leased',
                lease_owner = p_lease_owner,
                lease_expires_at = now() + interval '5 minutes',
                updated_at = now()
            FROM due
            WHERE wakeup.tenant_id = due.tenant_id
            RETURNING wakeup.tenant_id, wakeup.wakeup_revision;
        END
        $$;
        REVOKE ALL ON FUNCTION public.b24_due_fit_planner_tenants(text, integer)
            FROM PUBLIC, app_user, app_rw, app_ro;

        CREATE OR REPLACE FUNCTION public.b24_complete_fit_planner_wakeup(
            p_tenant_id uuid,
            p_lease_owner text,
            p_wakeup_revision bigint,
            p_succeeded boolean
        )
        RETURNS boolean
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public, pg_temp
        AS $$
        DECLARE
            affected integer;
        BEGIN
            IF session_user <> 'app_worker' THEN
                RAISE EXCEPTION 'b24_worker_database_identity_required';
            END IF;
            IF p_succeeded THEN
                DELETE FROM public.b24_fit_planner_wakeups
                WHERE tenant_id = p_tenant_id
                  AND status = 'leased'
                  AND lease_owner = p_lease_owner
                  AND wakeup_revision = p_wakeup_revision;
            ELSE
                UPDATE public.b24_fit_planner_wakeups
                SET status = 'pending', lease_owner = NULL,
                    lease_expires_at = NULL, updated_at = now()
                WHERE tenant_id = p_tenant_id
                  AND status = 'leased'
                  AND lease_owner = p_lease_owner;
            END IF;
            GET DIAGNOSTICS affected = ROW_COUNT;
            IF p_succeeded AND affected = 0 THEN
                UPDATE public.b24_fit_planner_wakeups
                SET status = 'pending', lease_owner = NULL,
                    lease_expires_at = NULL, updated_at = now()
                WHERE tenant_id = p_tenant_id
                  AND status = 'leased'
                  AND lease_owner = p_lease_owner;
            END IF;
            RETURN affected = 1;
        END
        $$;
        REVOKE ALL ON FUNCTION public.b24_complete_fit_planner_wakeup(
            uuid, text, bigint, boolean
        ) FROM PUBLIC, app_user, app_rw, app_ro;

        DO $$
        BEGIN
            IF to_regrole('app_worker') IS NOT NULL THEN
                EXECUTE 'GRANT CREATE ON SCHEMA public TO app_worker';
                EXECUTE 'ALTER FUNCTION '
                        'public.b24_due_fit_planner_tenants(text, integer) '
                        'OWNER TO app_worker';
                EXECUTE 'ALTER FUNCTION '
                        'public.b24_complete_fit_planner_wakeup('
                        'uuid, text, bigint, boolean) OWNER TO app_worker';
                EXECUTE 'REVOKE CREATE ON SCHEMA public FROM app_worker';
            END IF;
        END
        $$;
        """
    )
    _grant_worker(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON "
        "public.b24_fit_planner_wakeups TO app_worker"
    )
    _grant_worker(
        "GRANT EXECUTE ON FUNCTION "
        "public.b24_due_fit_planner_tenants(text, integer) TO app_worker"
    )
    _grant_worker(
        "GRANT EXECUTE ON FUNCTION "
        "public.b24_complete_fit_planner_wakeup(uuid, text, bigint, boolean) "
        "TO app_worker"
    )


def downgrade() -> None:
    op.execute(
        """
        DROP FUNCTION IF EXISTS public.b24_complete_fit_planner_wakeup(
            uuid, text, bigint, boolean
        );
        DROP FUNCTION IF EXISTS public.b24_due_fit_planner_tenants(text, integer);
        DROP TRIGGER IF EXISTS trg_b24_signal_fit_planner_wakeup
            ON public.b24_dirty_events;
        DROP FUNCTION IF EXISTS public.b24_signal_fit_planner_wakeup();
        DROP TABLE IF EXISTS public.b24_fit_planner_wakeups;  -- # CI:DESTRUCTIVE_OK - ADR-016 reversible C6 rollback.
        """
    )  # CI:DESTRUCTIVE_OK - reversible C6 planner selector rollback.
    for function_signature in WORKER_CONTROL_FUNCTIONS:
        op.execute(f"GRANT EXECUTE ON FUNCTION {function_signature} TO app_user")
    op.execute(
        """
        GRANT INSERT, UPDATE ON public.bayesian_model_fits TO app_user, app_rw;
        GRANT INSERT, UPDATE ON public.bayesian_artifacts TO app_user, app_rw;
        GRANT INSERT, UPDATE ON public.b24_fit_dispatch_outbox TO app_user;
        GRANT INSERT, UPDATE ON public.b24_active_execution_leases TO app_user;
        """
    )
