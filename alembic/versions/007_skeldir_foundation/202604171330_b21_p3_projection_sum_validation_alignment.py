"""B2.1-P3 align allocation sum validation with projection identity.

Revision ID: 202604171330
Revises: 202604171200
Create Date: 2026-04-17 13:30:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "202604171330"
down_revision: Union[str, None] = "202604171200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_attribution_allocations_tenant_event_projection
        ON attribution_allocations (tenant_id, event_id, recompute_job_id)
        WHERE recompute_job_id IS NOT NULL
        """
    )
    op.execute(
        """
        COMMENT ON INDEX idx_attribution_allocations_tenant_event_projection IS
        'Projection-scoped sum-validation index for deterministic allocations.'
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION check_allocation_sum_stmt_insert()
        RETURNS TRIGGER AS $$
        DECLARE
            tolerance_cents INTEGER := 1;
            mismatch RECORD;
        BEGIN
            WITH affected AS (
                SELECT DISTINCT tenant_id, event_id, model_version, recompute_job_id
                FROM newrows
                WHERE event_id IS NOT NULL
            )
            SELECT
                a.tenant_id,
                a.event_id,
                a.model_version,
                a.recompute_job_id,
                s.allocated_sum AS allocated_sum,
                e.revenue_cents AS event_revenue_cents,
                ABS(s.allocated_sum - e.revenue_cents) AS drift_cents
            INTO mismatch
            FROM affected a
            JOIN attribution_events e
              ON e.tenant_id = a.tenant_id
             AND e.id = a.event_id
            CROSS JOIN LATERAL (
                SELECT COALESCE(SUM(aa.allocated_revenue_cents), 0) AS allocated_sum
                FROM attribution_allocations aa
                WHERE aa.tenant_id = a.tenant_id
                  AND aa.event_id = a.event_id
                  AND (
                    (a.recompute_job_id IS NOT NULL AND aa.recompute_job_id = a.recompute_job_id)
                    OR (
                        a.recompute_job_id IS NULL
                        AND aa.recompute_job_id IS NULL
                        AND aa.model_version = a.model_version
                    )
                  )
            ) s
            WHERE ABS(s.allocated_sum - e.revenue_cents) > tolerance_cents
            LIMIT 1;

            IF FOUND THEN
                RAISE EXCEPTION
                    'Allocation sum mismatch: tenant_id=% event_id=% model_version=% allocated=% expected=% drift=%',
                    mismatch.tenant_id, mismatch.event_id, mismatch.model_version,
                    mismatch.allocated_sum, mismatch.event_revenue_cents, mismatch.drift_cents;
            END IF;

            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION check_allocation_sum_stmt_update()
        RETURNS TRIGGER AS $$
        DECLARE
            tolerance_cents INTEGER := 1;
            mismatch RECORD;
        BEGIN
            WITH affected AS (
                SELECT DISTINCT tenant_id, event_id, model_version, recompute_job_id
                FROM newrows
                WHERE event_id IS NOT NULL
                UNION
                SELECT DISTINCT tenant_id, event_id, model_version, recompute_job_id
                FROM oldrows
                WHERE event_id IS NOT NULL
            )
            SELECT
                a.tenant_id,
                a.event_id,
                a.model_version,
                a.recompute_job_id,
                s.allocated_sum AS allocated_sum,
                e.revenue_cents AS event_revenue_cents,
                ABS(s.allocated_sum - e.revenue_cents) AS drift_cents
            INTO mismatch
            FROM affected a
            JOIN attribution_events e
              ON e.tenant_id = a.tenant_id
             AND e.id = a.event_id
            CROSS JOIN LATERAL (
                SELECT COALESCE(SUM(aa.allocated_revenue_cents), 0) AS allocated_sum
                FROM attribution_allocations aa
                WHERE aa.tenant_id = a.tenant_id
                  AND aa.event_id = a.event_id
                  AND (
                    (a.recompute_job_id IS NOT NULL AND aa.recompute_job_id = a.recompute_job_id)
                    OR (
                        a.recompute_job_id IS NULL
                        AND aa.recompute_job_id IS NULL
                        AND aa.model_version = a.model_version
                    )
                  )
            ) s
            WHERE ABS(s.allocated_sum - e.revenue_cents) > tolerance_cents
            LIMIT 1;

            IF FOUND THEN
                RAISE EXCEPTION
                    'Allocation sum mismatch: tenant_id=% event_id=% model_version=% allocated=% expected=% drift=%',
                    mismatch.tenant_id, mismatch.event_id, mismatch.model_version,
                    mismatch.allocated_sum, mismatch.event_revenue_cents, mismatch.drift_cents;
            END IF;

            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION check_allocation_sum_stmt_delete()
        RETURNS TRIGGER AS $$
        DECLARE
            tolerance_cents INTEGER := 1;
            mismatch RECORD;
        BEGIN
            WITH affected AS (
                SELECT DISTINCT tenant_id, event_id, model_version, recompute_job_id
                FROM oldrows
                WHERE event_id IS NOT NULL
            )
            SELECT
                a.tenant_id,
                a.event_id,
                a.model_version,
                a.recompute_job_id,
                s.allocated_sum AS allocated_sum,
                e.revenue_cents AS event_revenue_cents,
                ABS(s.allocated_sum - e.revenue_cents) AS drift_cents
            INTO mismatch
            FROM affected a
            JOIN attribution_events e
              ON e.tenant_id = a.tenant_id
             AND e.id = a.event_id
            CROSS JOIN LATERAL (
                SELECT COALESCE(SUM(aa.allocated_revenue_cents), 0) AS allocated_sum
                FROM attribution_allocations aa
                WHERE aa.tenant_id = a.tenant_id
                  AND aa.event_id = a.event_id
                  AND (
                    (a.recompute_job_id IS NOT NULL AND aa.recompute_job_id = a.recompute_job_id)
                    OR (
                        a.recompute_job_id IS NULL
                        AND aa.recompute_job_id IS NULL
                        AND aa.model_version = a.model_version
                    )
                  )
            ) s
            WHERE ABS(s.allocated_sum - e.revenue_cents) > tolerance_cents
            LIMIT 1;

            IF FOUND THEN
                RAISE EXCEPTION
                    'Allocation sum mismatch: tenant_id=% event_id=% model_version=% allocated=% expected=% drift=%',
                    mismatch.tenant_id, mismatch.event_id, mismatch.model_version,
                    mismatch.allocated_sum, mismatch.event_revenue_cents, mismatch.drift_cents;
            END IF;

            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION check_allocation_sum_stmt_insert()
        RETURNS TRIGGER AS $$
        DECLARE
            tolerance_cents INTEGER := 1;
            mismatch RECORD;
        BEGIN
            WITH affected AS (
                SELECT DISTINCT tenant_id, event_id, model_version
                FROM newrows
                WHERE event_id IS NOT NULL
            )
            SELECT
                a.tenant_id,
                a.event_id,
                a.model_version,
                s.allocated_sum AS allocated_sum,
                e.revenue_cents AS event_revenue_cents,
                ABS(s.allocated_sum - e.revenue_cents) AS drift_cents
            INTO mismatch
            FROM affected a
            JOIN attribution_events e
              ON e.tenant_id = a.tenant_id
             AND e.id = a.event_id
            CROSS JOIN LATERAL (
                SELECT COALESCE(SUM(aa.allocated_revenue_cents), 0) AS allocated_sum
                FROM attribution_allocations aa
                WHERE aa.tenant_id = a.tenant_id
                  AND aa.event_id = a.event_id
                  AND aa.model_version = a.model_version
            ) s
            WHERE ABS(s.allocated_sum - e.revenue_cents) > tolerance_cents
            LIMIT 1;

            IF FOUND THEN
                RAISE EXCEPTION
                    'Allocation sum mismatch: tenant_id=% event_id=% model_version=% allocated=% expected=% drift=%',
                    mismatch.tenant_id, mismatch.event_id, mismatch.model_version,
                    mismatch.allocated_sum, mismatch.event_revenue_cents, mismatch.drift_cents;
            END IF;

            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION check_allocation_sum_stmt_update()
        RETURNS TRIGGER AS $$
        DECLARE
            tolerance_cents INTEGER := 1;
            mismatch RECORD;
        BEGIN
            WITH affected AS (
                SELECT DISTINCT tenant_id, event_id, model_version
                FROM newrows
                WHERE event_id IS NOT NULL
                UNION
                SELECT DISTINCT tenant_id, event_id, model_version
                FROM oldrows
                WHERE event_id IS NOT NULL
            )
            SELECT
                a.tenant_id,
                a.event_id,
                a.model_version,
                s.allocated_sum AS allocated_sum,
                e.revenue_cents AS event_revenue_cents,
                ABS(s.allocated_sum - e.revenue_cents) AS drift_cents
            INTO mismatch
            FROM affected a
            JOIN attribution_events e
              ON e.tenant_id = a.tenant_id
             AND e.id = a.event_id
            CROSS JOIN LATERAL (
                SELECT COALESCE(SUM(aa.allocated_revenue_cents), 0) AS allocated_sum
                FROM attribution_allocations aa
                WHERE aa.tenant_id = a.tenant_id
                  AND aa.event_id = a.event_id
                  AND aa.model_version = a.model_version
            ) s
            WHERE ABS(s.allocated_sum - e.revenue_cents) > tolerance_cents
            LIMIT 1;

            IF FOUND THEN
                RAISE EXCEPTION
                    'Allocation sum mismatch: tenant_id=% event_id=% model_version=% allocated=% expected=% drift=%',
                    mismatch.tenant_id, mismatch.event_id, mismatch.model_version,
                    mismatch.allocated_sum, mismatch.event_revenue_cents, mismatch.drift_cents;
            END IF;

            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION check_allocation_sum_stmt_delete()
        RETURNS TRIGGER AS $$
        DECLARE
            tolerance_cents INTEGER := 1;
            mismatch RECORD;
        BEGIN
            WITH affected AS (
                SELECT DISTINCT tenant_id, event_id, model_version
                FROM oldrows
                WHERE event_id IS NOT NULL
            )
            SELECT
                a.tenant_id,
                a.event_id,
                a.model_version,
                s.allocated_sum AS allocated_sum,
                e.revenue_cents AS event_revenue_cents,
                ABS(s.allocated_sum - e.revenue_cents) AS drift_cents
            INTO mismatch
            FROM affected a
            JOIN attribution_events e
              ON e.tenant_id = a.tenant_id
             AND e.id = a.event_id
            CROSS JOIN LATERAL (
                SELECT COALESCE(SUM(aa.allocated_revenue_cents), 0) AS allocated_sum
                FROM attribution_allocations aa
                WHERE aa.tenant_id = a.tenant_id
                  AND aa.event_id = a.event_id
                  AND aa.model_version = a.model_version
            ) s
            WHERE ABS(s.allocated_sum - e.revenue_cents) > tolerance_cents
            LIMIT 1;

            IF FOUND THEN
                RAISE EXCEPTION
                    'Allocation sum mismatch: tenant_id=% event_id=% model_version=% allocated=% expected=% drift=%',
                    mismatch.tenant_id, mismatch.event_id, mismatch.model_version,
                    mismatch.allocated_sum, mismatch.event_revenue_cents, mismatch.drift_cents;
            END IF;

            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        "DROP INDEX IF EXISTS idx_attribution_allocations_tenant_event_projection"
    )  # CI:DESTRUCTIVE_OK - rollback path for projection-aware sum-validation index.
