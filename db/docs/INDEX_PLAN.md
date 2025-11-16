# Index Plan

This document defines all indexes for B0.3 core tables, with justification linked to concrete contract query paths.

## Index Justification Methodology

Each index must be justified by:
1. **Contract Query Path**: Specific OpenAPI endpoint that requires this index
2. **Access Pattern**: Query pattern (e.g., filter by tenant_id + time range)
3. **Performance Target**: p95 < 50ms (per architectural guidance)

## Core Tables Indexes

### tenants

#### idx_tenants_name

**Table**: `tenants`  
**Columns**: `name`  
**Type**: BTREE  
**Query Path**: Tenant lookup by name (administrative queries)  
**Justification**: Enables fast tenant lookup for administrative operations  
**Performance Target**: p95 < 10ms (simple lookup)

---

### attribution_events

#### idx_attribution_events_tenant_occurred_at

**Table**: `attribution_events`  
**Columns**: `(tenant_id, occurred_at DESC)`  
**Type**: BTREE  
**Query Path**: `GET /api/attribution/revenue/realtime?tenant_id=X`  
**Justification**: 
- Contract: `api-contracts/openapi/v1/attribution.yaml:12-29`
- Query pattern: Filter by `tenant_id`, order by `occurred_at DESC` (most recent events first)
- Supports time-series queries for revenue aggregation
- Composite index optimizes tenant-scoped time-range queries

**Performance Target**: p95 < 50ms

#### idx_attribution_events_tenant_external_event_id

**Table**: `attribution_events`  
**Columns**: `(tenant_id, external_event_id)`  
**Type**: UNIQUE BTREE (partial: `WHERE external_event_id IS NOT NULL`)  
**Query Path**: Webhook ingestion idempotency (Shopify, PayPal, WooCommerce)  
**Justification**: 
- Enforces idempotency for sources with `external_event_id`
- Prevents duplicate ingestion
- Partial index only indexes non-null values (efficient)

**Performance Target**: p95 < 10ms (insertion check)

#### idx_attribution_events_tenant_correlation_id

**Table**: `attribution_events`  
**Columns**: `(tenant_id, correlation_id)`  
**Type**: UNIQUE BTREE (partial: `WHERE correlation_id IS NOT NULL AND external_event_id IS NULL`)  
**Query Path**: Webhook ingestion idempotency (Stripe)  
**Justification**: 
- Enforces idempotency for sources without `external_event_id` (Stripe)
- Fallback idempotency mechanism
- Partial index only indexes relevant rows

**Performance Target**: p95 < 10ms (insertion check)

#### idx_attribution_events_session_id

**Table**: `attribution_events`  
**Columns**: `session_id`  
**Type**: BTREE (partial: `WHERE session_id IS NOT NULL`)  
**Query Path**: Session-scoped event queries (future feature)  
**Justification**: 
- Supports session grouping queries
- Partial index only indexes non-null values
- Future-proofing for session-based attribution

**Performance Target**: p95 < 50ms

---

### dead_events

#### idx_dead_events_tenant_ingested_at

**Table**: `dead_events`  
**Columns**: `(tenant_id, ingested_at DESC)`  
**Type**: BTREE  
**Query Path**: Operator triage queries (administrative)  
**Justification**: 
- Supports operator queries: "Show me recent failures for tenant X"
- Composite index optimizes tenant-scoped time-range queries
- Enables efficient pagination of dead events

**Performance Target**: p95 < 50ms

#### idx_dead_events_source

**Table**: `dead_events`  
**Columns**: `source`  
**Type**: BTREE  
**Query Path**: Operator triage queries (filter by source)  
**Justification**: 
- Supports operator queries: "Show me failures from Shopify"
- Enables source-specific error analysis

**Performance Target**: p95 < 50ms

#### idx_dead_events_error_code

**Table**: `dead_events`  
**Columns**: `error_code`  
**Type**: BTREE  
**Query Path**: Operator triage queries (filter by error type)  
**Justification**: 
- Supports operator queries: "Show me validation errors"
- Enables error categorization and analysis

**Performance Target**: p95 < 50ms

---

### attribution_allocations

#### idx_attribution_allocations_tenant_created_at

**Table**: `attribution_allocations`  
**Columns**: `(tenant_id, created_at DESC)`  
**Type**: BTREE  
**Query Path**: Channel performance queries (future feature)  
**Justification**: 
- Supports time-series queries for attribution allocations
- Composite index optimizes tenant-scoped time-range queries
- Future-proofing for channel performance dashboards

**Performance Target**: p95 < 50ms

#### idx_attribution_allocations_event_id

**Table**: `attribution_allocations`  
**Columns**: `event_id`  
**Type**: BTREE  
**Query Path**: Event-to-allocation joins  
**Justification**: 
- Supports joins: `attribution_events` → `attribution_allocations`
- Enables efficient queries: "Show me all allocations for event X"
- Foreign key index for referential integrity

**Performance Target**: p95 < 50ms

#### idx_attribution_allocations_channel

**Table**: `attribution_allocations`  
**Columns**: `channel`  
**Type**: BTREE  
**Query Path**: Channel performance queries (future feature)  
**Justification**: 
- Supports channel-specific queries: "Show me all Google Search allocations"
- Enables channel performance aggregation
- Future-proofing for channel dashboards

**Performance Target**: p95 < 50ms

#### idx_attribution_allocations_tenant_event_model_channel

**Table**: `attribution_allocations`  
**Columns**: `(tenant_id, event_id, model_version, channel)`  
**Type**: UNIQUE BTREE (partial: `WHERE model_version IS NOT NULL`)  
**Query Path**: Idempotency enforcement (Phase 4A requirement)  
**Justification**: 
- Enforces idempotency per (tenant_id, event_id, model_version, channel)
- Prevents duplicate allocations for the same event/model/channel combination
- Supports sum-equality validation
- Partial index only indexes rows with model_version

**Performance Target**: p95 < 10ms (insertion check)

#### idx_attribution_allocations_tenant_model_version

**Table**: `attribution_allocations`  
**Columns**: `(tenant_id, model_version)`  
**Type**: BTREE  
**Query Path**: Model rollups and sum-equality validation (Phase 4A requirement)  
**Justification**: 
- Supports queries: "Show me all allocations for model version 1.0.0"
- Enables fast model rollups per tenant
- Supports sum-equality validation queries per model version
- Required for deterministic revenue accounting

**Performance Target**: p95 < 50ms

---

### revenue_ledger

#### idx_revenue_ledger_tenant_updated_at

**Table**: `revenue_ledger`  
**Columns**: `(tenant_id, updated_at DESC)`  
**Type**: BTREE  
**Query Path**: `GET /api/attribution/revenue/realtime?tenant_id=X`  
**Justification**: 
- Contract: `api-contracts/openapi/v1/attribution.yaml:12-29`
- Query pattern: Filter by `tenant_id`, order by `updated_at DESC` (most recent revenue first)
- Supports realtime revenue queries
- Composite index optimizes tenant-scoped time-range queries

**Performance Target**: p95 < 50ms

#### idx_revenue_ledger_is_verified

**Table**: `revenue_ledger`  
**Columns**: `is_verified`  
**Type**: BTREE (partial: `WHERE is_verified = true`)  
**Query Path**: Verified revenue queries  
**Justification**: 
- Supports queries: "Show me only verified revenue"
- Partial index only indexes verified rows (efficient)
- Enables fast filtering for verified revenue aggregation

**Performance Target**: p95 < 50ms

#### idx_revenue_ledger_tenant_allocation_id

**Table**: `revenue_ledger`  
**Columns**: `(tenant_id, allocation_id)`  
**Type**: UNIQUE BTREE (partial: `WHERE allocation_id IS NOT NULL`)  
**Query Path**: Idempotency enforcement for allocation-based posting (Phase 4C requirement)  
**Justification**: 
- Enforces idempotency per (tenant_id, allocation_id) for allocation-based posting
- Prevents duplicate ledger entries for the same allocation
- Supports idempotent allocation-to-ledger posting
- Partial index only indexes rows with allocation_id

**Performance Target**: p95 < 10ms (insertion check)

---

### reconciliation_runs

#### idx_reconciliation_runs_tenant_last_run_at

**Table**: `reconciliation_runs`  
**Columns**: `(tenant_id, last_run_at DESC)`  
**Type**: BTREE  
**Query Path**: `GET /api/reconciliation/status?tenant_id=X`  
**Justification**: 
- Contract: `api-contracts/openapi/v1/reconciliation.yaml:12-29`
- Query pattern: Filter by `tenant_id`, order by `last_run_at DESC` (most recent run first)
- Supports reconciliation status queries
- Composite index optimizes tenant-scoped status queries

**Performance Target**: p95 < 50ms

#### idx_reconciliation_runs_state

**Table**: `reconciliation_runs`  
**Columns**: `state`  
**Type**: BTREE  
**Query Path**: Reconciliation status queries (filter by state)  
**Justification**: 
- Supports queries: "Show me all running reconciliations"
- Enables state-based filtering for monitoring

**Performance Target**: p95 < 50ms

---

## Deferred Indexes

### JSONB GIN Indexes

**Status**: **DEFERRED** (not created in initial migration)

**Rationale**: 
- GIN indexes on JSONB columns (`raw_payload`, `error_detail`, `model_metadata`, `run_metadata`) are expensive to maintain
- No current query paths require JSONB queries
- Add only if concrete query paths require JSONB filtering/searching

**Future Consideration**: 
- If query paths require JSONB queries (e.g., "find events where raw_payload->>'source' = 'shopify'"), add GIN indexes at that time
- Avoid speculative indexing (per Jamie's principle)

---

## Index Maintenance

### Monitoring

- Monitor index usage via `pg_stat_user_indexes`
- Remove unused indexes if query paths change
- Add indexes only when query paths require them

### Performance Validation

- All indexes must support p95 < 50ms target
- Validate with `EXPLAIN ANALYZE` on representative queries
- Document any exceptions with rationale

---

## Materialized View Indexes

### mv_realtime_revenue

#### idx_mv_realtime_revenue_tenant_id

**Materialized View**: `mv_realtime_revenue`  
**Columns**: `tenant_id`  
**Type**: UNIQUE BTREE  
**Query Path**: `GET /api/attribution/revenue/realtime?tenant_id=X`  
**Justification**: 
- Contract: `api-contracts/openapi/v1/attribution.yaml:12-29`
- Enables fast tenant-scoped queries
- Unique index ensures one row per tenant

**Performance Target**: p95 < 50ms

### mv_reconciliation_status

#### idx_mv_reconciliation_status_tenant_id

**Materialized View**: `mv_reconciliation_status`  
**Columns**: `tenant_id`  
**Type**: UNIQUE BTREE  
**Query Path**: `GET /api/reconciliation/status?tenant_id=X`  
**Justification**: 
- Contract: `api-contracts/openapi/v1/reconciliation.yaml:12-29`
- Enables fast tenant-scoped queries
- Unique index ensures one row per tenant

**Performance Target**: p95 < 50ms

### mv_allocation_summary

#### idx_mv_allocation_summary_key

**Materialized View**: `mv_allocation_summary`  
**Columns**: `(tenant_id, event_id, model_version)`  
**Type**: UNIQUE BTREE  
**Query Path**: Sum-equality validation queries (Phase 4B requirement)  
**Justification**: 
- Supports sum-equality validation per (tenant_id, event_id, model_version)
- Enables fast lookups for allocation balance checks
- Unique index ensures one row per event/model combination

**Performance Target**: p95 < 50ms

#### idx_mv_allocation_summary_drift

**Materialized View**: `mv_allocation_summary`  
**Columns**: `drift_cents`  
**Type**: BTREE (partial: `WHERE drift_cents > 1`)  
**Query Path**: Finding unbalanced allocations (Phase 4B requirement)  
**Justification**: 
- Supports queries: "Show me allocations with drift > 1 cent"
- Enables fast identification of sum-equality violations
- Partial index only indexes unbalanced allocations (efficient)

**Performance Target**: p95 < 50ms

---

## Cross-References

- **Migrations**: 
  - `alembic/versions/202511131115_add_core_tables.py` (core tables)
  - `alembic/versions/202511131232_enhance_allocation_schema.py` (Phase 4A indexes)
  - `alembic/versions/202511131240_add_sum_equality_validation.py` (Phase 4B MV indexes)
  - `alembic/versions/202511131250_enhance_revenue_ledger.py` (Phase 4C indexes)
- **DDL Specs**: `db/docs/specs/*_ddl_spec.sql`
- **Contract Endpoints**: `api-contracts/openapi/v1/attribution.yaml`, `api-contracts/openapi/v1/reconciliation.yaml`

