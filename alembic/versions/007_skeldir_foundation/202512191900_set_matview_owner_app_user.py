"""Set matview ownership to app_user for refresh permissions.

B0.5.4.0 Zero-Drift v3.2: normalize matview ownership so runtime app_user
can refresh all registry materialized views (CONCURRENTLY requires owner).
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "202512191900"
down_revision = "6c5d5f5534ef"
branch_labels = None
depends_on = None


MATVIEWS = [
    "mv_allocation_summary",
    "mv_channel_performance",
    "mv_daily_revenue_summary",
]
SOURCE_TABLES = [
    "attribution_allocations",
    "attribution_events",
    "channel_taxonomy",
    "revenue_ledger",
]


def upgrade() -> None:
    for table in SOURCE_TABLES:
        op.execute(f"GRANT SELECT ON {table} TO app_user")

    for view in MATVIEWS:
        op.execute(f"ALTER MATERIALIZED VIEW {view} OWNER TO app_user")


def downgrade() -> None:
    # Restore ownership to postgres (previous migration role owner)
    for table in SOURCE_TABLES:
        op.execute(f"REVOKE SELECT ON {table} FROM app_user")

    for view in MATVIEWS:
        op.execute(f"ALTER MATERIALIZED VIEW {view} OWNER TO postgres")
