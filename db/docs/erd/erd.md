# Entity-Relationship Diagram (ERD)

**Generated Date**: 2025-11-13  
**Schema Version**: B0.3 Foundation

## Entity Relationships

### Core Entities

```
tenants (1)
  │
  ├── attribution_events (1..*)
  │     │
  │     └── attribution_allocations (1..*)
  │
  ├── dead_events (1..*)
  │
  ├── revenue_ledger (1..*)
  │
  └── reconciliation_runs (1..*)
```

### Relationship Details

#### tenants → attribution_events
- **Cardinality**: 1..* (one tenant has many attribution events)
- **Foreign Key**: `attribution_events.tenant_id` REFERENCES `tenants(id)` ON DELETE CASCADE
- **RLS**: Enabled (tenant isolation)

#### tenants → dead_events
- **Cardinality**: 1..* (one tenant has many dead events)
- **Foreign Key**: `dead_events.tenant_id` REFERENCES `tenants(id)` ON DELETE CASCADE
- **RLS**: Enabled (tenant isolation)

#### tenants → attribution_allocations
- **Cardinality**: 1..* (one tenant has many attribution allocations)
- **Foreign Key**: `attribution_allocations.tenant_id` REFERENCES `tenants(id)` ON DELETE CASCADE
- **RLS**: Enabled (tenant isolation)

#### tenants → revenue_ledger
- **Cardinality**: 1..* (one tenant has many revenue ledger entries)
- **Foreign Key**: `revenue_ledger.tenant_id` REFERENCES `tenants(id)` ON DELETE CASCADE
- **RLS**: Enabled (tenant isolation)

#### tenants → reconciliation_runs
- **Cardinality**: 1..* (one tenant has many reconciliation runs)
- **Foreign Key**: `reconciliation_runs.tenant_id` REFERENCES `tenants(id)` ON DELETE CASCADE
- **RLS**: Enabled (tenant isolation)

#### attribution_events → attribution_allocations
- **Cardinality**: 1..* (one event has many allocations)
- **Foreign Key**: `attribution_allocations.event_id` REFERENCES `attribution_events(id)` ON DELETE CASCADE
- **Purpose**: Link allocations to source events

### Correlation ID Stitching

All tables with `correlation_id` can be linked for event stitching:

```
correlation_id (X-Correlation-ID header)
  │
  ├── attribution_events.correlation_id
  ├── dead_events.correlation_id
  └── attribution_allocations.correlation_id
```

**Purpose**: Enable forensic reconstruction of complete event flows

### Materialized Views

#### mv_realtime_revenue
- **Source**: `revenue_ledger`
- **Purpose**: Aggregate revenue data for GET /api/attribution/revenue/realtime
- **Refresh**: CONCURRENTLY with TTL-based refresh (30-60s)

#### mv_reconciliation_status
- **Source**: `reconciliation_runs`
- **Purpose**: Aggregate reconciliation status for GET /api/reconciliation/status
- **Refresh**: CONCURRENTLY with TTL-based refresh (30-60s)

## Entity Attributes Summary

### tenants
- id (PK, uuid)
- name (VARCHAR(255))
- created_at, updated_at (timestamptz)

### attribution_events
- id (PK, uuid)
- tenant_id (FK → tenants)
- occurred_at (timestamptz)
- external_event_id (text, idempotency key)
- correlation_id (uuid, event stitching)
- session_id (uuid)
- revenue_cents (INTEGER)
- raw_payload (jsonb)

### dead_events
- id (PK, uuid)
- tenant_id (FK → tenants)
- ingested_at (timestamptz)
- source (text)
- error_code (text)
- error_detail (jsonb)
- raw_payload (jsonb)
- correlation_id (uuid, event stitching)
- external_event_id (text)

### attribution_allocations
- id (PK, uuid)
- tenant_id (FK → tenants)
- event_id (FK → attribution_events)
- channel (text)
- allocated_revenue_cents (INTEGER)
- model_metadata (jsonb)
- correlation_id (uuid, event stitching)

### revenue_ledger
- id (PK, uuid)
- tenant_id (FK → tenants)
- revenue_cents (INTEGER)
- is_verified (boolean)
- verified_at (timestamptz)
- reconciliation_run_id (uuid, nullable)

### reconciliation_runs
- id (PK, uuid)
- tenant_id (FK → tenants)
- last_run_at (timestamptz)
- state (VARCHAR(20), CHECK: idle|running|failed|completed)
- error_message (text, nullable)
- run_metadata (jsonb, nullable)

## Index Strategy

### Time-Series Indexes
- `attribution_events`: (tenant_id, occurred_at DESC)
- `dead_events`: (tenant_id, ingested_at DESC)
- `attribution_allocations`: (tenant_id, created_at DESC)
- `revenue_ledger`: (tenant_id, updated_at DESC)
- `reconciliation_runs`: (tenant_id, last_run_at DESC)

### Idempotency Indexes
- `attribution_events`: UNIQUE (tenant_id, external_event_id) WHERE external_event_id IS NOT NULL
- `attribution_events`: UNIQUE (tenant_id, correlation_id) WHERE correlation_id IS NOT NULL AND external_event_id IS NULL

### Query Optimization Indexes
- `attribution_events`: session_id (partial)
- `dead_events`: source, error_code
- `attribution_allocations`: event_id, channel
- `revenue_ledger`: is_verified (partial)
- `reconciliation_runs`: state

## Cross-References

- **Data Dictionary**: `db/docs/data_dictionary/data_dictionary.md`
- **Contract Mapping**: `db/docs/contract_schema_mapping.yaml`
- **Migrations**: `alembic/versions/`




