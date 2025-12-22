"""Add RLS policies to LLM subsystem tables

Revision ID: 202512081510
Revises: 202512081500
Create Date: 2025-12-08 15:10:00

Migration Description:
Enables Row-Level Security (RLS) and creates tenant isolation policies for all 7 LLM subsystem tables:
- llm_api_calls
- llm_monthly_costs
- investigations
- investigation_tool_calls
- explanation_cache
- budget_optimization_jobs
- llm_validation_failures

Security Model:
- RLS is ENABLED and FORCED on all LLM tables
- Policies use current_setting('app.current_tenant_id')::uuid for tenant context
- Default-deny: No access without tenant context set
- All operations (SELECT, INSERT, UPDATE, DELETE) are filtered by tenant_id

GUC Contract:
- Application must set tenant context via: set_config('app.current_tenant_id', tenant_id::text, false)
- Policy predicate uses current_setting to get tenant context
- Tenant context is session-scoped (SET LOCAL) or transaction-scoped
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '202512081510'
down_revision: Union[str, None] = '202512081500'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# LLM subsystem tenant-scoped tables
LLM_TABLES = [
    'llm_api_calls',
    'llm_monthly_costs',
    'investigations',
    'investigation_tool_calls',
    'explanation_cache',
    'budget_optimization_jobs',
    'llm_validation_failures'
]


def upgrade() -> None:
    """
    Enable RLS and create tenant isolation policies for all LLM subsystem tables.

    For each table:
    1. Enable ROW LEVEL SECURITY
    2. Force ROW LEVEL SECURITY (prevents bypass)
    3. Create tenant_isolation_policy using current_setting('app.current_tenant_id')::uuid
    4. Add policy comment
    """

    for table_name in LLM_TABLES:
        # Enable RLS
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")

        # Force RLS (prevents bypass even for table owners)
        op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")

        # Create tenant isolation policy
        op.execute(f"""
            CREATE POLICY tenant_isolation_policy ON {table_name}
                USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
                WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        """)

        # Add policy comment
        op.execute(f"""
            COMMENT ON POLICY tenant_isolation_policy ON {table_name} IS
                'RLS policy enforcing tenant isolation. Purpose: Prevent cross-tenant data access. Requires app.current_tenant_id to be set via set_config().'
        """)


def downgrade() -> None:
    """
    Remove RLS policies and disable RLS for all LLM subsystem tables.

    WARNING: Disabling RLS removes tenant isolation. Only do this if you understand the security implications.
    """

    for table_name in LLM_TABLES:
        # Drop policy
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {table_name}")

        # Disable RLS
        op.execute(f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY")
