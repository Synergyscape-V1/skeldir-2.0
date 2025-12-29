"""
R5 remediation requires:
- bulk (set-based) writes to attribution_allocations for 10k/100k feasibility
- deterministic recompute behavior without per-row trigger amplification

This migration converts the allocation sum-equality enforcement trigger from
ROW-level to STATEMENT-level using Postgres transition tables, while preserving
the invariant:
  SUM(allocated_revenue_cents) == attribution_events.revenue_cents
  per (tenant_id, event_id, model_version) within ±1 cent tolerance.

Notes:
- attribution_allocations.event_id is nullable (audit trail) and is set to NULL
  when source events are deleted; sum checks are skipped when event_id is NULL
  or when the corresponding attribution_events row no longer exists.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "202512291500"
down_revision: Union[str, None] = "202512280300"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the existing ROW-level trigger (created by earlier migrations).
    op.execute("DROP TRIGGER IF EXISTS trg_check_allocation_sum ON attribution_allocations;")

    # Replace trigger function with a STATEMENT-level implementation.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION check_allocation_sum()
        RETURNS TRIGGER AS $$
        DECLARE
            tolerance_cents INTEGER := 1; -- ±1 cent rounding tolerance
            mismatch RECORD;
        BEGIN
            /*
             * Use transition tables (newrows/oldrows) to compute the affected
             * (tenant_id, event_id, model_version) keys and validate sums once
             * per statement (not once per row).
             */
            WITH affected AS (
                SELECT DISTINCT tenant_id, event_id, model_version
                FROM newrows
                WHERE event_id IS NOT NULL
                UNION
                SELECT DISTINCT tenant_id, event_id, model_version
                FROM oldrows
                WHERE event_id IS NOT NULL
            ),
            totals AS (
                SELECT
                    a.tenant_id,
                    a.event_id,
                    a.model_version,
                    COALESCE(SUM(aa.allocated_revenue_cents), 0) AS allocated_sum
                FROM affected a
                LEFT JOIN attribution_allocations aa
                  ON aa.tenant_id = a.tenant_id
                 AND aa.event_id = a.event_id
                 AND aa.model_version = a.model_version
                GROUP BY a.tenant_id, a.event_id, a.model_version
            ),
            expected AS (
                SELECT
                    a.tenant_id,
                    a.event_id,
                    a.model_version,
                    e.revenue_cents AS event_revenue_cents
                FROM affected a
                LEFT JOIN attribution_events e
                  ON e.tenant_id = a.tenant_id
                 AND e.id = a.event_id
            )
            SELECT
                t.tenant_id,
                t.event_id,
                t.model_version,
                t.allocated_sum,
                x.event_revenue_cents,
                ABS(t.allocated_sum - x.event_revenue_cents) AS drift_cents
            INTO mismatch
            FROM totals t
            JOIN expected x
              ON x.tenant_id = t.tenant_id
             AND x.event_id = t.event_id
             AND x.model_version = t.model_version
            WHERE x.event_revenue_cents IS NOT NULL
              AND ABS(t.allocated_sum - x.event_revenue_cents) > tolerance_cents
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
        COMMENT ON FUNCTION check_allocation_sum() IS
        'STATEMENT-level validation that allocations sum to event revenue per (tenant_id, event_id, model_version) with ±1 cent tolerance. Uses transition tables to avoid per-row amplification while preserving deterministic revenue accounting correctness.';
        """
    )

    # Recreate trigger as STATEMENT-level with transition tables.
    op.execute(
        """
        CREATE TRIGGER trg_check_allocation_sum
            AFTER INSERT OR UPDATE OR DELETE ON attribution_allocations
            REFERENCING NEW TABLE AS newrows OLD TABLE AS oldrows
            FOR EACH STATEMENT EXECUTE FUNCTION check_allocation_sum();
        """
    )

    op.execute(
        """
        COMMENT ON TRIGGER trg_check_allocation_sum ON attribution_allocations IS
        'Enforces sum-equality invariant at STATEMENT granularity: allocations must sum to event revenue per (tenant_id, event_id, model_version) with ±1 cent tolerance.';
        """
    )


def downgrade() -> None:
    # Revert to ROW-level behavior (pre-R5). This restores the original shape:
    # - trigger fires per row
    # - function uses NEW/OLD row context
    op.execute("DROP TRIGGER IF EXISTS trg_check_allocation_sum ON attribution_allocations;")

    op.execute(
        """
        CREATE OR REPLACE FUNCTION check_allocation_sum()
        RETURNS TRIGGER AS $$
        DECLARE
            event_revenue INTEGER;
            allocated_sum INTEGER;
            tolerance_cents INTEGER := 1; -- ±1 cent rounding tolerance
            target_event_id uuid;
            target_model_version text;
            target_tenant_id uuid;
        BEGIN
            target_event_id := COALESCE(NEW.event_id, OLD.event_id);
            target_model_version := COALESCE(NEW.model_version, OLD.model_version);
            target_tenant_id := COALESCE(NEW.tenant_id, OLD.tenant_id);

            IF target_event_id IS NULL THEN
                RETURN COALESCE(NEW, OLD);
            END IF;

            SELECT revenue_cents INTO event_revenue
            FROM attribution_events
            WHERE id = target_event_id AND tenant_id = target_tenant_id;

            -- Skip check if the source event is missing (audit trail / ON DELETE SET NULL).
            IF event_revenue IS NULL THEN
                RETURN COALESCE(NEW, OLD);
            END IF;

            SELECT COALESCE(SUM(allocated_revenue_cents), 0) INTO allocated_sum
            FROM attribution_allocations
            WHERE tenant_id = target_tenant_id
              AND event_id = target_event_id
              AND model_version = target_model_version;

            IF ABS(allocated_sum - event_revenue) > tolerance_cents THEN
                RAISE EXCEPTION 'Allocation sum mismatch: allocated=% expected=% drift=%',
                    allocated_sum, event_revenue, ABS(allocated_sum - event_revenue);
            END IF;

            RETURN COALESCE(NEW, OLD);
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_check_allocation_sum
            AFTER INSERT OR UPDATE OR DELETE ON attribution_allocations
            FOR EACH ROW EXECUTE FUNCTION check_allocation_sum();
        """
    )
