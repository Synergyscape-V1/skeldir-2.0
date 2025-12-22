"""Restore canonical matview contract (5 views) and ownership.

Reintroduces mv_realtime_revenue and mv_reconciliation_status to align with
the B0.5.4 contract and sets ownership/grants for all registry matviews so
app_user can refresh CONCURRENTLY.
"""

from alembic import op
from typing import Union

# revision identifiers, used by Alembic.
revision: str = "202512201000"
down_revision: Union[str, None] = "202512191900"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


MATVIEWS = [
    "mv_allocation_summary",
    "mv_channel_performance",
    "mv_daily_revenue_summary",
    "mv_realtime_revenue",
    "mv_reconciliation_status",
]


def _create_mv_realtime_revenue() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_realtime_revenue CASCADE")
    op.execute(
        """
        CREATE MATERIALIZED VIEW mv_realtime_revenue AS
        SELECT 
            rl.tenant_id,
            COALESCE(SUM(COALESCE(rl.amount_cents, rl.revenue_cents)), 0) / 100.0 AS total_revenue,
            BOOL_OR(COALESCE(rl.is_verified, false)) AS verified,
            EXTRACT(EPOCH FROM (now() - MAX(rl.updated_at)))::INTEGER AS data_freshness_seconds
        FROM revenue_ledger rl
        GROUP BY rl.tenant_id;
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX idx_mv_realtime_revenue_tenant_id 
            ON mv_realtime_revenue (tenant_id)
        """
    )


def _create_mv_reconciliation_status() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_reconciliation_status CASCADE")
    op.execute(
        """
        CREATE MATERIALIZED VIEW mv_reconciliation_status AS
        SELECT 
            rr.tenant_id,
            rr.state,
            rr.last_run_at,
            rr.id AS reconciliation_run_id
        FROM reconciliation_runs rr
        INNER JOIN (
            SELECT tenant_id, MAX(last_run_at) AS max_last_run_at
            FROM reconciliation_runs
            GROUP BY tenant_id
        ) latest ON rr.tenant_id = latest.tenant_id 
            AND rr.last_run_at = latest.max_last_run_at;
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX idx_mv_reconciliation_status_tenant_id 
            ON mv_reconciliation_status (tenant_id)
        """
    )


def _grant_and_own() -> None:
    op.execute("GRANT SELECT ON revenue_ledger TO app_user")
    op.execute("GRANT SELECT ON reconciliation_runs TO app_user")
    for view in MATVIEWS:
        op.execute(f"ALTER MATERIALIZED VIEW {view} OWNER TO app_user")


def upgrade() -> None:
    _create_mv_realtime_revenue()
    _create_mv_reconciliation_status()
    _grant_and_own()


def downgrade() -> None:
    # Revert ownership and drop the two reinstated views
    for view in MATVIEWS:
        op.execute(f"ALTER MATERIALIZED VIEW {view} OWNER TO postgres")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_realtime_revenue CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_reconciliation_status CASCADE")
