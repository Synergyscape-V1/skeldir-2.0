# Data Dictionary

**Generated Date**: 2025-11-13  
**Schema Version**: B0.3 Foundation  
**Migration Baseline**: `202511121302_baseline.py`  
**Latest Migration**: `202511131121_add_grants.py`

## Overview

This data dictionary documents all tables, columns, constraints, indexes, and policies for B0.3 database schema foundation.

## Tables

### tenants

**Purpose**: Store tenant information for multi-tenant isolation  
**Data Class**: Non-PII  
**Ownership**: Backend service  
**RLS**: Enabled (for tenant isolation)

#### Columns

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | NOT NULL | gen_random_uuid() | Primary key UUID. Unique tenant identifier. |
| name | VARCHAR(255) | NOT NULL | - | Tenant name. Human-readable tenant identification. |
| created_at | timestamptz | NOT NULL | now() | Record creation timestamp. Audit trail. |
| updated_at | timestamptz | NOT NULL | now() | Record update timestamp. Audit trail. |

#### Constraints

- **Primary Key**: `id` (uuid)
- **Check Constraint**: `ck_tenants_name_not_empty` - Ensures tenant name is not empty

#### Indexes

- `idx_tenants_name` - Index on tenant name for fast tenant lookup

#### Foreign Keys

None (referenced by all tenant-scoped tables via `tenant_id`)

---

### attribution_events

**Purpose**: Store attribution events for revenue tracking and attribution calculations  
**Data Class**: Non-PII (PII stripped from raw_payload before persistence)  
**Ownership**: Attribution service  
**RLS**: Enabled (for tenant isolation)  
**Contract Mapping**: Supports webhook ingestion endpoints (shopify, stripe, paypal, woocommerce)

#### Columns

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | NOT NULL | gen_random_uuid() | Primary key UUID. Unique event identifier. |
| tenant_id | uuid | NOT NULL | - | Foreign key to tenants table. Tenant isolation. |
| created_at | timestamptz | NOT NULL | now() | Record creation timestamp. Audit trail. |
| updated_at | timestamptz | NOT NULL | now() | Record update timestamp. Audit trail. |
| occurred_at | timestamptz | NOT NULL | - | Domain-specific event timestamp (when event occurred). Business logic timestamping. |
| external_event_id | text | NULL | - | External event ID from source system (e.g., Shopify order ID, PayPal transaction ID). Idempotency key. |
| correlation_id | uuid | NULL | - | Correlation ID from X-Correlation-ID header. Distributed tracing and event stitching across tables. Links attribution_events, dead_events, and future attribution_allocations. |
| session_id | uuid | NULL | - | Session identifier for session-scoped events (30-minute inactivity timeout). Session grouping. |
| revenue_cents | INTEGER | NOT NULL | 0 | Revenue amount in cents (INTEGER). Store revenue for attribution calculations. Contract mapping: total_revenue (number float) → revenue_cents (integer). |
| raw_payload | jsonb | NOT NULL | - | Raw webhook payload (JSONB). Store original event data. PII stripped before persistence per PRIVACY-NOTES.md. |

#### Constraints

- **Primary Key**: `id` (uuid)
- **Foreign Key**: `tenant_id` REFERENCES `tenants(id)` ON DELETE CASCADE
- **Check Constraint**: `ck_attribution_events_revenue_positive` - Ensures revenue_cents >= 0
- **Unique Index**: `idx_attribution_events_tenant_external_event_id` - UNIQUE (tenant_id, external_event_id) WHERE external_event_id IS NOT NULL (idempotency)
- **Unique Index**: `idx_attribution_events_tenant_correlation_id` - UNIQUE (tenant_id, correlation_id) WHERE correlation_id IS NOT NULL AND external_event_id IS NULL (idempotency fallback)

#### Indexes

- `idx_attribution_events_tenant_occurred_at` - Composite index on (tenant_id, occurred_at DESC) for time-series queries
- `idx_attribution_events_session_id` - Index on session_id for session-scoped queries (partial: WHERE session_id IS NOT NULL)

---

### dead_events

**Purpose**: Dead-letter queue for invalid/unparseable webhook payloads  
**Data Class**: Non-PII (PII stripped from raw_payload before persistence)  
**Ownership**: Ingestion service  
**RLS**: Enabled (for tenant isolation)  
**Contract Mapping**: Supports error handling for webhook ingestion failures

#### Columns

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | NOT NULL | gen_random_uuid() | Primary key UUID. Unique dead event identifier. |
| tenant_id | uuid | NOT NULL | - | Foreign key to tenants table. Tenant isolation. |
| ingested_at | timestamptz | NOT NULL | now() | Timestamp when failure occurred. Failure time tracking. |
| source | text | NOT NULL | - | Source system identifier (e.g., shopify, stripe, paypal, woocommerce). Identify source of failed payload. |
| error_code | text | NOT NULL | - | Error classification code. Categorize failure types. |
| error_detail | jsonb | NOT NULL | - | Structured error information (JSONB). Store detailed error context for debugging. |
| raw_payload | jsonb | NOT NULL | - | Raw webhook payload that failed (JSONB). Store original payload for analysis. PII stripped before persistence per PRIVACY-NOTES.md. |
| correlation_id | uuid | NULL | - | Correlation ID from X-Correlation-ID header. Distributed tracing and event stitching across tables. Links dead_events, attribution_events, and future attribution_allocations. |
| external_event_id | text | NULL | - | External event ID when known (e.g., Shopify order ID). Link to source system event. |

#### Constraints

- **Primary Key**: `id` (uuid)
- **Foreign Key**: `tenant_id` REFERENCES `tenants(id)` ON DELETE CASCADE

#### Indexes

- `idx_dead_events_tenant_ingested_at` - Composite index on (tenant_id, ingested_at DESC) for operator triage queries
- `idx_dead_events_source` - Index on source for filtering by source system
- `idx_dead_events_error_code` - Index on error_code for error analysis queries

---

### attribution_allocations

**Purpose**: Store attribution model allocations (channel credit assignments)  
**Data Class**: Non-PII  
**Ownership**: Attribution service  
**RLS**: Enabled (for tenant isolation)  
**Contract Mapping**: Supports attribution calculations and channel performance queries

#### Columns

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | NOT NULL | gen_random_uuid() | Primary key UUID. Unique allocation identifier. |
| tenant_id | uuid | NOT NULL | - | Foreign key to tenants table. Tenant isolation. |
| event_id | uuid | NOT NULL | - | Foreign key to attribution_events table. Link allocation to source event. |
| created_at | timestamptz | NOT NULL | now() | Record creation timestamp. Audit trail. |
| updated_at | timestamptz | NOT NULL | now() | Record update timestamp. Audit trail. |
| channel | text | NOT NULL | - | Channel identifier (e.g., google_search, facebook_ads). Identify attribution channel. |
| allocated_revenue_cents | INTEGER | NOT NULL | 0 | Allocated revenue amount in cents (INTEGER). Store channel credit amount. |
| model_metadata | jsonb | NULL | - | Attribution model metadata (JSONB). Store model-specific data (e.g., convergence_r_hat, effective_sample_size). |
| correlation_id | uuid | NULL | - | Correlation ID from X-Correlation-ID header. Distributed tracing and event stitching across tables. Links attribution_allocations, attribution_events, and dead_events. |

#### Constraints

- **Primary Key**: `id` (uuid)
- **Foreign Key**: `tenant_id` REFERENCES `tenants(id)` ON DELETE CASCADE
- **Foreign Key**: `event_id` REFERENCES `attribution_events(id)` ON DELETE CASCADE
- **Check Constraint**: `ck_attribution_allocations_revenue_positive` - Ensures allocated_revenue_cents >= 0

#### Indexes

- `idx_attribution_allocations_tenant_created_at` - Composite index on (tenant_id, created_at DESC) for time-series queries
- `idx_attribution_allocations_event_id` - Index on event_id for event-to-allocation joins
- `idx_attribution_allocations_channel` - Index on channel for channel performance queries

---

### revenue_ledger

**Purpose**: Store verified revenue aggregates for reconciliation  
**Data Class**: Non-PII  
**Ownership**: Reconciliation service  
**RLS**: Enabled (for tenant isolation)  
**Contract Mapping**: Supports RealtimeRevenueResponse (total_revenue, verified, data_freshness_seconds)

#### Columns

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | NOT NULL | gen_random_uuid() | Primary key UUID. Unique ledger entry identifier. |
| tenant_id | uuid | NOT NULL | - | Foreign key to tenants table. Tenant isolation. |
| created_at | timestamptz | NOT NULL | now() | Record creation timestamp. Audit trail. |
| updated_at | timestamptz | NOT NULL | now() | Record update timestamp. Audit trail. |
| revenue_cents | INTEGER | NOT NULL | 0 | Revenue amount in cents (INTEGER). Store verified revenue aggregate. Contract mapping: total_revenue (number float) → revenue_cents (integer). |
| is_verified | boolean | NOT NULL | false | Whether revenue has been verified through reconciliation pipeline. Reconciliation status. Contract mapping: verified (boolean) → is_verified (boolean). |
| verified_at | timestamptz | NULL | - | Timestamp when revenue was verified. Verification time tracking. |
| reconciliation_run_id | uuid | NULL | - | Reference to reconciliation run that verified this revenue. Link to reconciliation_runs table. |

#### Constraints

- **Primary Key**: `id` (uuid)
- **Foreign Key**: `tenant_id` REFERENCES `tenants(id)` ON DELETE CASCADE
- **Check Constraint**: `ck_revenue_ledger_revenue_positive` - Ensures revenue_cents >= 0

#### Indexes

- `idx_revenue_ledger_tenant_updated_at` - Composite index on (tenant_id, updated_at DESC) for time-series queries
- `idx_revenue_ledger_is_verified` - Partial index on is_verified WHERE is_verified = true for verified revenue queries

---

### reconciliation_runs

**Purpose**: Store reconciliation pipeline run status and metadata  
**Data Class**: Non-PII  
**Ownership**: Reconciliation service  
**RLS**: Enabled (for tenant isolation)  
**Contract Mapping**: Supports ReconciliationStatusResponse (state, last_run_at, tenant_id)

#### Columns

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | NOT NULL | gen_random_uuid() | Primary key UUID. Unique reconciliation run identifier. |
| tenant_id | uuid | NOT NULL | - | Foreign key to tenants table. Tenant isolation. |
| created_at | timestamptz | NOT NULL | now() | Record creation timestamp. Audit trail. |
| updated_at | timestamptz | NOT NULL | now() | Record update timestamp. Audit trail. |
| last_run_at | timestamptz | NOT NULL | - | Timestamp of the last reconciliation run. Track last execution time. Contract mapping: last_run_at (string date-time) → last_run_at (timestamptz). |
| state | VARCHAR(20) | NOT NULL | 'idle' | Current state of the reconciliation pipeline. Track pipeline status. Contract mapping: state enum (idle\|running\|failed\|completed) → state VARCHAR(20) CHECK. |
| error_message | text | NULL | - | Error message if state is failed. Store failure details. |
| run_metadata | jsonb | NULL | - | Structured run information (JSONB). Store run-specific metadata. |

#### Constraints

- **Primary Key**: `id` (uuid)
- **Foreign Key**: `tenant_id` REFERENCES `tenants(id)` ON DELETE CASCADE
- **Check Constraint**: `ck_reconciliation_runs_state_valid` - Ensures state is one of: idle, running, failed, completed

#### Indexes

- `idx_reconciliation_runs_tenant_last_run_at` - Composite index on (tenant_id, last_run_at DESC) for status queries
- `idx_reconciliation_runs_state` - Index on state for filtering by pipeline state

---

## Materialized Views

### mv_realtime_revenue

**Purpose**: Aggregate realtime revenue data for GET /api/attribution/revenue/realtime endpoint  
**Data Class**: Non-PII  
**Ownership**: Attribution service  
**Contract Mapping**: api-contracts/openapi/v1/attribution.yaml:39-64 (RealtimeRevenueResponse)  
**Refresh Policy**: CONCURRENTLY with TTL-based refresh (30-60s)

#### Columns

| Column | Type | Description |
|--------|------|-------------|
| tenant_id | uuid | Tenant identifier. Tenant isolation. |
| total_revenue | numeric | Total revenue in dollars (float). Aggregate revenue sum. Contract mapping: total_revenue (number float). |
| verified | boolean | Whether revenue has been verified. Reconciliation status. Contract mapping: verified (boolean). |
| data_freshness_seconds | integer | Seconds since data was last updated. Data freshness tracking. Contract mapping: data_freshness_seconds (integer). |

#### Indexes

- `idx_mv_realtime_revenue_tenant_id` - Unique index on tenant_id for fast tenant-scoped queries (p95 < 50ms target)

---

### mv_reconciliation_status

**Purpose**: Aggregate reconciliation pipeline status for GET /api/reconciliation/status endpoint  
**Data Class**: Non-PII  
**Ownership**: Reconciliation service  
**Contract Mapping**: api-contracts/openapi/v1/reconciliation.yaml:39-64 (ReconciliationStatusResponse)  
**Refresh Policy**: CONCURRENTLY with TTL-based refresh (30-60s)

#### Columns

| Column | Type | Description |
|--------|------|-------------|
| tenant_id | uuid | Tenant identifier. Tenant isolation. |
| state | VARCHAR(20) | Current state of the reconciliation pipeline. Track pipeline status. Contract mapping: state enum (idle\|running\|failed\|completed). |
| last_run_at | timestamptz | Timestamp of the last reconciliation run. Track last execution time. Contract mapping: last_run_at (string date-time). |
| reconciliation_run_id | uuid | Reference to reconciliation_runs.id (internal use). |

#### Indexes

- `idx_mv_reconciliation_status_tenant_id` - Unique index on tenant_id for fast tenant-scoped queries (p95 < 50ms target)

---

## Row-Level Security (RLS) Policies

All tenant-scoped tables have RLS enabled and forced:

- `attribution_events`: `tenant_isolation_policy` using `current_setting('app.current_tenant_id')::uuid`
- `dead_events`: `tenant_isolation_policy` using `current_setting('app.current_tenant_id')::uuid`
- `attribution_allocations`: `tenant_isolation_policy` using `current_setting('app.current_tenant_id')::uuid`
- `revenue_ledger`: `tenant_isolation_policy` using `current_setting('app.current_tenant_id')::uuid`
- `reconciliation_runs`: `tenant_isolation_policy` using `current_setting('app.current_tenant_id')::uuid`

**Policy Pattern**:
```sql
CREATE POLICY tenant_isolation_policy ON {table_name}
    USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid)
```

---

## Roles and GRANTs

### app_rw (Read-Write Application Role)

**Grants on Tables**:
- `attribution_events`: SELECT, INSERT, UPDATE, DELETE
- `dead_events`: SELECT, INSERT, UPDATE, DELETE
- `attribution_allocations`: SELECT, INSERT, UPDATE, DELETE
- `revenue_ledger`: SELECT, INSERT, UPDATE, DELETE
- `reconciliation_runs`: SELECT, INSERT, UPDATE, DELETE

**Grants on Views**:
- `mv_realtime_revenue`: SELECT
- `mv_reconciliation_status`: SELECT

### app_ro (Read-Only Application Role)

**Grants on Tables**:
- `attribution_events`: SELECT
- `dead_events`: SELECT
- `attribution_allocations`: SELECT
- `revenue_ledger`: SELECT
- `reconciliation_runs`: SELECT

**Grants on Views**:
- `mv_realtime_revenue`: SELECT
- `mv_reconciliation_status`: SELECT

### PUBLIC

**Revoked**: All permissions revoked on all tables and views (no public access)

---

## Cross-References

- **Contract Mapping**: `db/docs/contract_schema_mapping.yaml`
- **Style Guide**: `db/docs/SCHEMA_STYLE_GUIDE.md`
- **RLS Policies**: `alembic/versions/202511131120_add_rls_policies.py`
- **GRANTs**: `alembic/versions/202511131121_add_grants.py`
- **Migrations**: `alembic/versions/`




