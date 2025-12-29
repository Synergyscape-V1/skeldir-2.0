"""
R5 performance remediation: make the allocation sum-equality trigger scale ~O(N).

Observed in CI:
- 10k window compute ~25s, 100k ~1600s (quadratic drift).
Root cause hypothesis:
- statement-level trigger function plan falls back to large scans / hash joins as
  attribution_allocations grows.

Fix:
- Replace statement-level trigger functions with a correlated-subquery plan that
  is forced to be key-scoped (tenant_id, event_id, model_version) and therefore
  index-friendly.
- Add a supporting index on (tenant_id, event_id, model_version) to make
  key-scoped SUM lookups cheap and stable.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "202512291600"
down_revision: Union[str, None] = "202512291500"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_attribution_allocations_tenant_event_model
        ON attribution_allocations (tenant_id, event_id, model_version);
        """
    )

    op.execute(
        """
        COMMENT ON INDEX idx_attribution_allocations_tenant_event_model IS
        'R5 performance index for sum-equality enforcement. Supports statement-level trigger lookups by (tenant_id, event_id, model_version).';
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


def downgrade() -> None:
    # Keep the trigger functions as-is; downgrade only removes the index.
    op.execute("DROP INDEX IF EXISTS idx_attribution_allocations_tenant_event_model")  # CI:DESTRUCTIVE_OK
