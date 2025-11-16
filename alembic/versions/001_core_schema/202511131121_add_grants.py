"""Add GRANTs for application roles

Revision ID: 202511131121
Revises: 202511131120
Create Date: 2025-11-13 11:21:00

Migration Description:
Applies GRANTs per ROLES_AND_GRANTS.md matrix for all tenant-scoped tables:
- attribution_events
- dead_events
- attribution_allocations
- revenue_ledger
- reconciliation_runs

Role Permissions:
- app_rw: SELECT, INSERT, UPDATE, DELETE (full CRUD for normal operations)
- app_ro: SELECT (read-only for reporting and analytics)
- PUBLIC: REVOKE ALL (no public access)

Security Model:
- All tenant-scoped tables have RLS enabled (from previous migration)
- GRANTs work in conjunction with RLS policies
- RLS policies enforce tenant isolation (no need for table-level tenant filtering)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '202511131121'
down_revision: Union[str, None] = '202511131120'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Tenant-scoped tables (excluding tenants table itself)
TENANT_SCOPED_TABLES = [
    'attribution_events',
    'dead_events',
    'attribution_allocations',
    'revenue_ledger',
    'reconciliation_runs'
]

# Materialized views
MATERIALIZED_VIEWS = [
    'mv_realtime_revenue',
    'mv_reconciliation_status'
]


def upgrade() -> None:
    """
    Apply GRANTs per ROLES_AND_GRANTS.md matrix.
    
    For each tenant-scoped table:
    1. GRANT SELECT, INSERT, UPDATE, DELETE TO app_rw
    2. GRANT SELECT TO app_ro
    3. REVOKE ALL FROM PUBLIC
    
    For materialized views:
    1. GRANT SELECT TO app_rw
    2. GRANT SELECT TO app_ro
    3. REVOKE ALL FROM PUBLIC
    """
    
    # Grant permissions on tenant-scoped tables
    for table_name in TENANT_SCOPED_TABLES:
        # Grant to app_rw (read-write)
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE {table_name} TO app_rw")
        
        # Grant to app_ro (read-only)
        op.execute(f"GRANT SELECT ON TABLE {table_name} TO app_ro")
        
        # Revoke PUBLIC access
        op.execute(f"REVOKE ALL ON TABLE {table_name} FROM PUBLIC")
    
    # Grant permissions on materialized views
    for view_name in MATERIALIZED_VIEWS:
        # Grant to app_rw (read)
        op.execute(f"GRANT SELECT ON TABLE {view_name} TO app_rw")
        
        # Grant to app_ro (read-only)
        op.execute(f"GRANT SELECT ON TABLE {view_name} TO app_ro")
        
        # Revoke PUBLIC access
        op.execute(f"REVOKE ALL ON TABLE {view_name} FROM PUBLIC")


def downgrade() -> None:
    """
    Revoke GRANTs from application roles.
    
    WARNING: Revoking GRANTs will prevent application access. Only do this if you understand the implications.
    """
    
    # Revoke permissions on tenant-scoped tables
    for table_name in TENANT_SCOPED_TABLES:
        op.execute(f"REVOKE ALL ON TABLE {table_name} FROM app_rw")
        op.execute(f"REVOKE ALL ON TABLE {table_name} FROM app_ro")
    
    # Revoke permissions on materialized views
    for view_name in MATERIALIZED_VIEWS:
        op.execute(f"REVOKE ALL ON TABLE {view_name} FROM app_rw")
        op.execute(f"REVOKE ALL ON TABLE {view_name} FROM app_ro")



