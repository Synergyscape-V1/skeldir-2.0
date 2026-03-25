"""B1.5-P1 lifecycle authority selection, subordination, and destruction plan.

Revision ID: 202603251200
Revises: 202603221130
Create Date: 2026-03-25 12:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "202603251200"
down_revision: Union[str, None] = "202603221130"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _drop_check_constraints(table_name: str) -> None:
    op.execute(
        f"""
        DO $$
        DECLARE
            constraint_row record;
        BEGIN
            FOR constraint_row IN
                SELECT conname
                FROM pg_constraint
                WHERE conrelid = '{table_name}'::regclass
                  AND contype = 'c'
            LOOP
                EXECUTE format('ALTER TABLE {table_name} DROP CONSTRAINT %I', constraint_row.conname);
            END LOOP;
        END
        $$;
        """
    )


def _grant_if_role_exists(role: str, privileges: str, table_name: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                EXECUTE 'GRANT {privileges} ON TABLE {table_name} TO {role}';
            END IF;
        END
        $$;
        """
    )


def _revoke_if_role_exists(role: str, table_name: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                EXECUTE 'REVOKE ALL ON TABLE {table_name} FROM {role}';
            END IF;
        END
        $$;
        """
    )


def upgrade() -> None:
    # Investigation authority table upgrade (public lifecycle owner).
    op.execute("ALTER TABLE investigation_jobs ADD COLUMN IF NOT EXISTS request_id TEXT")
    op.execute("ALTER TABLE investigation_jobs ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now()")
    op.execute("ALTER TABLE investigation_jobs ADD COLUMN IF NOT EXISTS rejected_at TIMESTAMPTZ")
    op.execute("ALTER TABLE investigation_jobs ADD COLUMN IF NOT EXISTS refine_requested_at TIMESTAMPTZ")
    op.execute("ALTER TABLE investigation_jobs ADD COLUMN IF NOT EXISTS rerun_requested_at TIMESTAMPTZ")
    op.execute("ALTER TABLE investigation_jobs ADD COLUMN IF NOT EXISTS failed_at TIMESTAMPTZ")
    op.execute("ALTER TABLE investigation_jobs ADD COLUMN IF NOT EXISTS timeout_at TIMESTAMPTZ")
    op.execute("ALTER TABLE investigation_jobs ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMPTZ")
    op.execute("ALTER TABLE investigation_jobs ADD COLUMN IF NOT EXISTS failure_code TEXT")
    op.execute("ALTER TABLE investigation_jobs ADD COLUMN IF NOT EXISTS failure_reason TEXT")
    _drop_check_constraints("investigation_jobs")

    op.execute(
        """
        UPDATE investigation_jobs
        SET status = CASE status
            WHEN 'PENDING' THEN 'submitted'
            WHEN 'READY_FOR_REVIEW' THEN 'ready_for_review'
            WHEN 'APPROVED' THEN 'approved'
            WHEN 'COMPLETED' THEN 'completed'
            WHEN 'CANCELLED' THEN 'cancelled'
            ELSE status
        END
        """
    )
    op.execute(
        """
        UPDATE investigation_jobs
        SET request_id = COALESCE(request_id, correlation_id, CONCAT('legacy-', id::text))
        WHERE request_id IS NULL
        """
    )
    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                tenant_id,
                request_id,
                ROW_NUMBER() OVER (
                    PARTITION BY tenant_id, request_id
                    ORDER BY created_at, id
                ) AS row_rank
            FROM investigation_jobs
        )
        UPDATE investigation_jobs jobs
        SET request_id = CONCAT(jobs.request_id, ':', jobs.id::text)
        FROM ranked
        WHERE ranked.id = jobs.id
          AND ranked.row_rank > 1
        """
    )
    op.execute("ALTER TABLE investigation_jobs ALTER COLUMN request_id SET NOT NULL")
    op.execute(
        """
        ALTER TABLE investigation_jobs
        ADD CONSTRAINT ck_investigation_jobs_status_valid
        CHECK (
            status IN (
                'submitted',
                'validating',
                'investigating',
                'ready_for_review',
                'approved',
                'rejected',
                'refine_requested',
                'rerun_requested',
                'completed',
                'failed',
                'timeout',
                'cancelled'
            )
        )
        """
    )
    op.execute(
        """
        ALTER TABLE investigation_jobs
        ADD CONSTRAINT ck_investigation_jobs_review_timestamp_integrity
        CHECK (
            status NOT IN ('approved', 'completed')
            OR approved_at IS NOT NULL
        )
        """
    )
    op.execute(
        """
        ALTER TABLE investigation_jobs
        ADD CONSTRAINT ck_investigation_jobs_ready_timestamp_integrity
        CHECK (
            status NOT IN ('ready_for_review', 'approved', 'rejected', 'refine_requested', 'rerun_requested', 'completed')
            OR ready_for_review_at IS NOT NULL
        )
        """
    )
    op.execute(
        """
        ALTER TABLE investigation_jobs
        ADD CONSTRAINT uq_investigation_jobs_tenant_request_id
        UNIQUE (tenant_id, request_id)
        """
    )

    # Budget authority table (public lifecycle owner).
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS budget_jobs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            request_id TEXT NOT NULL,
            correlation_id TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            ready_for_review_at TIMESTAMPTZ,
            approved_at TIMESTAMPTZ,
            rejected_at TIMESTAMPTZ,
            refine_requested_at TIMESTAMPTZ,
            rerun_requested_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            failed_at TIMESTAMPTZ,
            timeout_at TIMESTAMPTZ,
            cancelled_at TIMESTAMPTZ,
            result JSONB,
            failure_code TEXT,
            failure_reason TEXT,
            CONSTRAINT ck_budget_jobs_status_valid CHECK (
                status IN (
                    'submitted',
                    'validating',
                    'investigating',
                    'ready_for_review',
                    'approved',
                    'rejected',
                    'refine_requested',
                    'rerun_requested',
                    'completed',
                    'failed',
                    'timeout',
                    'cancelled'
                )
            ),
            CONSTRAINT uq_budget_jobs_tenant_request_id UNIQUE (tenant_id, request_id)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_budget_jobs_tenant_status
        ON budget_jobs (tenant_id, status, created_at DESC)
        """
    )
    op.execute("ALTER TABLE budget_jobs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE budget_jobs FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON budget_jobs")
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy ON budget_jobs
            USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        """
    )
    _grant_if_role_exists("app_rw", "SELECT, INSERT, UPDATE", "budget_jobs")
    _grant_if_role_exists("app_user", "SELECT, INSERT, UPDATE", "budget_jobs")
    _grant_if_role_exists("app_ro", "SELECT", "budget_jobs")
    op.execute(
        """
        COMMENT ON TABLE budget_jobs IS
            'B1.5 public lifecycle authority for budget recommendation review workflows.'
        """
    )

    # Investigations table demotion to internal compute trace substrate.
    op.execute("ALTER TABLE investigations ADD COLUMN IF NOT EXISTS request_id TEXT")
    op.execute(
        """
        ALTER TABLE investigations
        ADD COLUMN IF NOT EXISTS authority_job_id UUID REFERENCES investigation_jobs(id) ON DELETE SET NULL
        """
    )
    op.execute(
        """
        ALTER TABLE investigations
        ADD COLUMN IF NOT EXISTS lifecycle_role TEXT NOT NULL DEFAULT 'internal_trace'
        """
    )
    op.execute(
        """
        UPDATE investigations
        SET request_id = COALESCE(
            request_id,
            NULLIF(regexp_replace(query, '^provider:', ''), ''),
            CONCAT('legacy-', id::text)
        )
        WHERE request_id IS NULL
        """
    )
    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                tenant_id,
                request_id,
                ROW_NUMBER() OVER (
                    PARTITION BY tenant_id, request_id
                    ORDER BY created_at, id
                ) AS row_rank
            FROM investigations
        )
        UPDATE investigations investigations_table
        SET request_id = CONCAT(investigations_table.request_id, ':', investigations_table.id::text)
        FROM ranked
        WHERE ranked.id = investigations_table.id
          AND ranked.row_rank > 1
        """
    )
    op.execute("ALTER TABLE investigations ALTER COLUMN request_id SET NOT NULL")
    _drop_check_constraints("investigations")
    op.execute(
        """
        UPDATE investigations
        SET status = CASE status
            WHEN 'pending' THEN 'compute_pending'
            WHEN 'running' THEN 'compute_running'
            WHEN 'completed' THEN 'compute_succeeded'
            WHEN 'failed' THEN 'compute_failed'
            ELSE status
        END
        """
    )
    op.execute(
        """
        ALTER TABLE investigations
        ADD CONSTRAINT ck_investigations_status_valid
        CHECK (
            status IN (
                'compute_pending',
                'compute_running',
                'compute_succeeded',
                'compute_failed',
                'compute_timeout',
                'compute_cancelled'
            )
        )
        """
    )
    op.execute(
        """
        ALTER TABLE investigations
        ADD CONSTRAINT ck_investigations_internal_trace_only
        CHECK (lifecycle_role = 'internal_trace')
        """
    )
    op.execute(
        """
        ALTER TABLE investigations
        ADD CONSTRAINT uq_investigations_tenant_request_id
        UNIQUE (tenant_id, request_id)
        """
    )
    op.execute(
        """
        COMMENT ON TABLE investigations IS
            'Internal-only compute trace for investigation workers. Not a public lifecycle authority.'
        """
    )

    # budget_optimization_jobs demotion to internal compute trace substrate.
    op.execute("ALTER TABLE budget_optimization_jobs ADD COLUMN IF NOT EXISTS request_id TEXT")
    op.execute(
        """
        ALTER TABLE budget_optimization_jobs
        ADD COLUMN IF NOT EXISTS authority_job_id UUID REFERENCES budget_jobs(id) ON DELETE SET NULL
        """
    )
    op.execute(
        """
        ALTER TABLE budget_optimization_jobs
        ADD COLUMN IF NOT EXISTS lifecycle_role TEXT NOT NULL DEFAULT 'internal_trace'
        """
    )
    op.execute(
        """
        UPDATE budget_optimization_jobs
        SET request_id = COALESCE(
            request_id,
            recommendations ->> 'request_id',
            CONCAT('legacy-', id::text)
        )
        WHERE request_id IS NULL
        """
    )
    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                tenant_id,
                request_id,
                ROW_NUMBER() OVER (
                    PARTITION BY tenant_id, request_id
                    ORDER BY created_at, id
                ) AS row_rank
            FROM budget_optimization_jobs
        )
        UPDATE budget_optimization_jobs jobs
        SET request_id = CONCAT(jobs.request_id, ':', jobs.id::text)
        FROM ranked
        WHERE ranked.id = jobs.id
          AND ranked.row_rank > 1
        """
    )
    op.execute("ALTER TABLE budget_optimization_jobs ALTER COLUMN request_id SET NOT NULL")
    _drop_check_constraints("budget_optimization_jobs")
    op.execute(
        """
        UPDATE budget_optimization_jobs
        SET status = CASE status
            WHEN 'pending' THEN 'compute_pending'
            WHEN 'running' THEN 'compute_running'
            WHEN 'completed' THEN 'compute_succeeded'
            WHEN 'failed' THEN 'compute_failed'
            ELSE status
        END
        """
    )
    op.execute(
        """
        ALTER TABLE budget_optimization_jobs
        ADD CONSTRAINT ck_budget_optimization_jobs_status_valid
        CHECK (
            status IN (
                'compute_pending',
                'compute_running',
                'compute_succeeded',
                'compute_failed',
                'compute_timeout',
                'compute_cancelled'
            )
        )
        """
    )
    op.execute(
        """
        ALTER TABLE budget_optimization_jobs
        ADD CONSTRAINT ck_budget_optimization_jobs_internal_trace_only
        CHECK (lifecycle_role = 'internal_trace')
        """
    )
    op.execute(
        """
        ALTER TABLE budget_optimization_jobs
        ADD CONSTRAINT uq_budget_optimization_jobs_tenant_request_id
        UNIQUE (tenant_id, request_id)
        """
    )
    op.execute(
        """
        COMMENT ON TABLE budget_optimization_jobs IS
            'Internal-only compute trace for budget workers. Not a public lifecycle authority.'
        """
    )


def downgrade() -> None:
    _drop_check_constraints("budget_optimization_jobs")
    op.execute(
        """
        UPDATE budget_optimization_jobs
        SET status = CASE status
            WHEN 'compute_pending' THEN 'pending'
            WHEN 'compute_running' THEN 'running'
            WHEN 'compute_succeeded' THEN 'completed'
            WHEN 'compute_failed' THEN 'failed'
            WHEN 'compute_timeout' THEN 'failed'
            WHEN 'compute_cancelled' THEN 'failed'
            ELSE status
        END
        """
    )
    op.execute(
        """
        ALTER TABLE budget_optimization_jobs
        ADD CONSTRAINT ck_budget_optimization_jobs_status_valid
        CHECK (status IN ('pending', 'running', 'completed', 'failed'))
        """
    )
    op.execute("ALTER TABLE budget_optimization_jobs DROP COLUMN IF EXISTS lifecycle_role")
    op.execute("ALTER TABLE budget_optimization_jobs DROP COLUMN IF EXISTS authority_job_id")
    op.execute("ALTER TABLE budget_optimization_jobs DROP COLUMN IF EXISTS request_id")

    _drop_check_constraints("investigations")
    op.execute(
        """
        UPDATE investigations
        SET status = CASE status
            WHEN 'compute_pending' THEN 'pending'
            WHEN 'compute_running' THEN 'running'
            WHEN 'compute_succeeded' THEN 'completed'
            WHEN 'compute_failed' THEN 'failed'
            WHEN 'compute_timeout' THEN 'failed'
            WHEN 'compute_cancelled' THEN 'failed'
            ELSE status
        END
        """
    )
    op.execute(
        """
        ALTER TABLE investigations
        ADD CONSTRAINT ck_investigations_status_valid
        CHECK (status IN ('pending', 'running', 'completed', 'failed'))
        """
    )
    op.execute("ALTER TABLE investigations DROP COLUMN IF EXISTS lifecycle_role")
    op.execute("ALTER TABLE investigations DROP COLUMN IF EXISTS authority_job_id")
    op.execute("ALTER TABLE investigations DROP COLUMN IF EXISTS request_id")

    _revoke_if_role_exists("app_ro", "budget_jobs")
    _revoke_if_role_exists("app_user", "budget_jobs")
    _revoke_if_role_exists("app_rw", "budget_jobs")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON budget_jobs")
    op.execute("DROP TABLE IF EXISTS budget_jobs")

    _drop_check_constraints("investigation_jobs")
    op.execute(
        """
        UPDATE investigation_jobs
        SET status = CASE status
            WHEN 'submitted' THEN 'PENDING'
            WHEN 'validating' THEN 'PENDING'
            WHEN 'investigating' THEN 'PENDING'
            WHEN 'ready_for_review' THEN 'READY_FOR_REVIEW'
            WHEN 'approved' THEN 'APPROVED'
            WHEN 'rejected' THEN 'CANCELLED'
            WHEN 'refine_requested' THEN 'CANCELLED'
            WHEN 'rerun_requested' THEN 'PENDING'
            WHEN 'completed' THEN 'COMPLETED'
            WHEN 'failed' THEN 'CANCELLED'
            WHEN 'timeout' THEN 'CANCELLED'
            WHEN 'cancelled' THEN 'CANCELLED'
            ELSE status
        END
        """
    )
    op.execute(
        """
        ALTER TABLE investigation_jobs
        ADD CONSTRAINT ck_investigation_jobs_status_valid
        CHECK (status IN ('PENDING', 'READY_FOR_REVIEW', 'APPROVED', 'COMPLETED', 'CANCELLED'))
        """
    )
    op.execute(
        """
        ALTER TABLE investigation_jobs
        ADD CONSTRAINT ck_investigation_jobs_approved_before_completed
        CHECK (status != 'COMPLETED' OR approved_at IS NOT NULL)
        """
    )
    op.execute(
        """
        ALTER TABLE investigation_jobs
        ADD CONSTRAINT ck_investigation_jobs_ready_before_approved
        CHECK (status NOT IN ('APPROVED', 'COMPLETED') OR ready_for_review_at IS NOT NULL)
        """
    )
    op.execute("ALTER TABLE investigation_jobs DROP COLUMN IF EXISTS failure_reason")
    op.execute("ALTER TABLE investigation_jobs DROP COLUMN IF EXISTS failure_code")
    op.execute("ALTER TABLE investigation_jobs DROP COLUMN IF EXISTS cancelled_at")
    op.execute("ALTER TABLE investigation_jobs DROP COLUMN IF EXISTS timeout_at")
    op.execute("ALTER TABLE investigation_jobs DROP COLUMN IF EXISTS failed_at")
    op.execute("ALTER TABLE investigation_jobs DROP COLUMN IF EXISTS rerun_requested_at")
    op.execute("ALTER TABLE investigation_jobs DROP COLUMN IF EXISTS refine_requested_at")
    op.execute("ALTER TABLE investigation_jobs DROP COLUMN IF EXISTS rejected_at")
    op.execute("ALTER TABLE investigation_jobs DROP COLUMN IF EXISTS updated_at")
    op.execute("ALTER TABLE investigation_jobs DROP COLUMN IF EXISTS request_id")
