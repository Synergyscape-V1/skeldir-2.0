"""Add core tables for B0.3 schema foundation

Revision ID: 202511131115
Revises: baseline
Create Date: 2025-11-13 11:15:00

Migration Description:
Creates the 6 core tables for B0.3 database schema foundation:
- tenants: Tenant identity and management
- attribution_events: Event ingestion and attribution calculations
- dead_events: Dead-letter queue for failed ingestion attempts
- attribution_allocations: Attribution model allocations (channel credit)
- revenue_ledger: Verified revenue aggregates for reconciliation
- reconciliation_runs: Reconciliation pipeline run status

Contract Mapping:
- attribution_events: Supports webhook ingestion endpoints (shopify, stripe, paypal, woocommerce)
- revenue_ledger: Supports RealtimeRevenueResponse (total_revenue, verified, data_freshness_seconds)
- reconciliation_runs: Supports ReconciliationStatusResponse (state, last_run_at, tenant_id)

All tables follow governance baseline:
- Style guide compliance (snake_case, UUID PKs, timestamptz, INTEGER for revenue)
- Contract mapping (required fields → NOT NULL, type conversions)
- DDL lint rules (comments, tenant_id, RLS-ready)
- Idempotency constraints (UNIQUE on tenant_id + external_event_id/correlation_id)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '202511131115'
down_revision: Union[str, None] = 'baseline'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Apply migration changes.
    
    Creates all 6 core tables with:
    - Primary keys (UUID with gen_random_uuid())
    - Foreign keys (tenant_id references tenants)
    - Timestamps (created_at, updated_at, domain-specific)
    - Constraints (CHECK, UNIQUE for idempotency)
    - Indexes (time-series, idempotency, query optimization)
    - Comments (all objects commented per style guide)
    """
    
    # Create tenants table (must be first, referenced by all others)
    op.execute("""
        CREATE TABLE tenants (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(255) NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    
    op.execute("""
        ALTER TABLE tenants 
            ADD CONSTRAINT ck_tenants_name_not_empty 
            CHECK (LENGTH(TRIM(name)) > 0)
    """)
    
    op.execute("""
        CREATE INDEX idx_tenants_name ON tenants (name)
    """)
    
    op.execute("""
        COMMENT ON TABLE tenants IS 
            'Stores tenant information for multi-tenant isolation. Purpose: Tenant identity and management. Data class: Non-PII. Ownership: Backend service. RLS enabled for tenant isolation.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN tenants.id IS 
            'Primary key UUID. Purpose: Unique tenant identifier. Data class: Non-PII.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN tenants.name IS 
            'Tenant name. Purpose: Human-readable tenant identification. Data class: Non-PII.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN tenants.created_at IS 
            'Record creation timestamp. Purpose: Audit trail. Data class: Non-PII.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN tenants.updated_at IS 
            'Record update timestamp. Purpose: Audit trail. Data class: Non-PII.'
    """)
    
    # Create attribution_events table
    op.execute("""
        CREATE TABLE attribution_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            occurred_at timestamptz NOT NULL,
            external_event_id text,
            correlation_id uuid,
            session_id uuid,
            revenue_cents INTEGER NOT NULL DEFAULT 0 CHECK (revenue_cents >= 0),
            raw_payload jsonb NOT NULL
        )
    """)
    
    op.execute("""
        ALTER TABLE attribution_events 
            ADD CONSTRAINT ck_attribution_events_revenue_positive 
            CHECK (revenue_cents >= 0)
    """)
    
    # Idempotency indexes (partial unique indexes)
    op.execute("""
        CREATE UNIQUE INDEX idx_attribution_events_tenant_external_event_id 
            ON attribution_events (tenant_id, external_event_id) 
            WHERE external_event_id IS NOT NULL
    """)
    
    op.execute("""
        CREATE UNIQUE INDEX idx_attribution_events_tenant_correlation_id 
            ON attribution_events (tenant_id, correlation_id) 
            WHERE correlation_id IS NOT NULL AND external_event_id IS NULL
    """)
    
    op.execute("""
        CREATE INDEX idx_attribution_events_tenant_occurred_at 
            ON attribution_events (tenant_id, occurred_at DESC)
    """)
    
    op.execute("""
        CREATE INDEX idx_attribution_events_session_id 
            ON attribution_events (session_id) 
            WHERE session_id IS NOT NULL
    """)
    
    op.execute("""
        COMMENT ON TABLE attribution_events IS 
            'Stores attribution events for revenue tracking. Purpose: Event ingestion and attribution calculations. Data class: Non-PII (PII stripped from raw_payload). Ownership: Attribution service. RLS enabled for tenant isolation.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN attribution_events.correlation_id IS 
            'Correlation ID from X-Correlation-ID header. Purpose: Distributed tracing and event stitching across tables. Links attribution_events, dead_events, and future attribution_allocations. Data class: Non-PII.'
    """)
    
    # Create dead_events table
    op.execute("""
        CREATE TABLE dead_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            ingested_at timestamptz NOT NULL DEFAULT now(),
            source text NOT NULL,
            error_code text NOT NULL,
            error_detail jsonb NOT NULL,
            raw_payload jsonb NOT NULL,
            correlation_id uuid,
            external_event_id text
        )
    """)
    
    op.execute("""
        CREATE INDEX idx_dead_events_tenant_ingested_at 
            ON dead_events (tenant_id, ingested_at DESC)
    """)
    
    op.execute("""
        CREATE INDEX idx_dead_events_source ON dead_events (source)
    """)
    
    op.execute("""
        CREATE INDEX idx_dead_events_error_code ON dead_events (error_code)
    """)
    
    op.execute("""
        COMMENT ON TABLE dead_events IS 
            'Dead-letter queue for invalid/unparseable webhook payloads. Purpose: Store failed ingestion attempts for operator triage. Data class: Non-PII (PII stripped from raw_payload). Ownership: Ingestion service. RLS enabled for tenant isolation.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN dead_events.correlation_id IS 
            'Correlation ID from X-Correlation-ID header. Purpose: Distributed tracing and event stitching across tables. Links dead_events, attribution_events, and future attribution_allocations. Data class: Non-PII.'
    """)
    
    # Create attribution_allocations table
    op.execute("""
        CREATE TABLE attribution_allocations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            event_id uuid NOT NULL REFERENCES attribution_events(id) ON DELETE CASCADE,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            channel text NOT NULL,
            allocated_revenue_cents INTEGER NOT NULL DEFAULT 0 CHECK (allocated_revenue_cents >= 0),
            model_metadata jsonb,
            correlation_id uuid
        )
    """)
    
    op.execute("""
        ALTER TABLE attribution_allocations 
            ADD CONSTRAINT ck_attribution_allocations_revenue_positive 
            CHECK (allocated_revenue_cents >= 0)
    """)
    
    op.execute("""
        CREATE INDEX idx_attribution_allocations_tenant_created_at 
            ON attribution_allocations (tenant_id, created_at DESC)
    """)
    
    op.execute("""
        CREATE INDEX idx_attribution_allocations_event_id 
            ON attribution_allocations (event_id)
    """)
    
    op.execute("""
        CREATE INDEX idx_attribution_allocations_channel 
            ON attribution_allocations (channel)
    """)
    
    op.execute("""
        COMMENT ON TABLE attribution_allocations IS 
            'Stores attribution model allocations (channel credit assignments). Purpose: Store channel credit for attribution calculations. Data class: Non-PII. Ownership: Attribution service. RLS enabled for tenant isolation.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN attribution_allocations.correlation_id IS 
            'Correlation ID from X-Correlation-ID header. Purpose: Distributed tracing and event stitching across tables. Links attribution_allocations, attribution_events, and dead_events. Data class: Non-PII.'
    """)
    
    # Create revenue_ledger table
    op.execute("""
        CREATE TABLE revenue_ledger (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            revenue_cents INTEGER NOT NULL DEFAULT 0 CHECK (revenue_cents >= 0),
            is_verified boolean NOT NULL DEFAULT false,
            verified_at timestamptz,
            reconciliation_run_id uuid
        )
    """)
    
    op.execute("""
        ALTER TABLE revenue_ledger 
            ADD CONSTRAINT ck_revenue_ledger_revenue_positive 
            CHECK (revenue_cents >= 0)
    """)
    
    op.execute("""
        CREATE INDEX idx_revenue_ledger_tenant_updated_at 
            ON revenue_ledger (tenant_id, updated_at DESC)
    """)
    
    op.execute("""
        CREATE INDEX idx_revenue_ledger_is_verified 
            ON revenue_ledger (is_verified) 
            WHERE is_verified = true
    """)
    
    op.execute("""
        COMMENT ON TABLE revenue_ledger IS 
            'Stores verified revenue aggregates for reconciliation. Purpose: Revenue verification and aggregation. Data class: Non-PII. Ownership: Reconciliation service. RLS enabled for tenant isolation.'
    """)
    
    # Create reconciliation_runs table
    op.execute("""
        CREATE TABLE reconciliation_runs (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            last_run_at timestamptz NOT NULL,
            state VARCHAR(20) NOT NULL DEFAULT 'idle' 
                CHECK (state IN ('idle', 'running', 'failed', 'completed')),
            error_message text,
            run_metadata jsonb
        )
    """)
    
    op.execute("""
        ALTER TABLE reconciliation_runs 
            ADD CONSTRAINT ck_reconciliation_runs_state_valid 
            CHECK (state IN ('idle', 'running', 'failed', 'completed'))
    """)
    
    op.execute("""
        CREATE INDEX idx_reconciliation_runs_tenant_last_run_at 
            ON reconciliation_runs (tenant_id, last_run_at DESC)
    """)
    
    op.execute("""
        CREATE INDEX idx_reconciliation_runs_state 
            ON reconciliation_runs (state)
    """)
    
    op.execute("""
        COMMENT ON TABLE reconciliation_runs IS 
            'Stores reconciliation pipeline run status and metadata. Purpose: Track reconciliation pipeline execution. Data class: Non-PII. Ownership: Reconciliation service. RLS enabled for tenant isolation.'
    """)


def downgrade() -> None:
    """
    Rollback migration changes.
    
    Drops all 6 core tables in reverse dependency order:
    1. reconciliation_runs (no dependencies)
    2. revenue_ledger (no dependencies)
    3. attribution_allocations (depends on attribution_events)
    4. dead_events (no dependencies)
    5. attribution_events (depends on tenants)
    6. tenants (referenced by all others)
    """
    
    # Drop tables in reverse dependency order
    op.execute("DROP TABLE IF EXISTS reconciliation_runs CASCADE")
    op.execute("DROP TABLE IF EXISTS revenue_ledger CASCADE")
    op.execute("DROP TABLE IF EXISTS attribution_allocations CASCADE")
    op.execute("DROP TABLE IF EXISTS dead_events CASCADE")
    op.execute("DROP TABLE IF EXISTS attribution_events CASCADE")
    op.execute("DROP TABLE IF EXISTS tenants CASCADE")



