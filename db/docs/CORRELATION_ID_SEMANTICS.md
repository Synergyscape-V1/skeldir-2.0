# Correlation ID Semantics

This document defines how `correlation_id` propagates through the system and enables event stitching for forensic analysis.

## Overview

The `correlation_id` is a distributed tracing identifier that links related events across multiple tables and services. It enables forensic reconstruction of complete event flows from ingestion through processing to final allocation.

## Propagation in Ingest Boundary

### Source: X-Correlation-ID Header

**Contract**: `api-contracts/openapi/v1/_common/components.yaml:17-23`

**Header**: `X-Correlation-ID: string (uuid)`

**Requirement**: All webhook endpoints require `X-Correlation-ID` header (per contract)

### Ingest Flow

1. **Webhook Receipt**: Ingest service receives webhook with `X-Correlation-ID` header
2. **Validation**: Validate `X-Correlation-ID` is valid UUID format
3. **Propagation**: Store `correlation_id` in:
   - `attribution_events.correlation_id` (successful ingestion)
   - `dead_events.correlation_id` (failed ingestion)
4. **Downstream**: Propagate `correlation_id` to:
   - `attribution_allocations.correlation_id` (when allocations are created)
   - Future tables (e.g., `revenue_ledger`, audit logs)

## Event Stitching Narrative

### Successful Ingestion Flow

```
Webhook → attribution_events (correlation_id: abc-123)
         ↓
Attribution Processing → attribution_allocations (correlation_id: abc-123)
         ↓
Reconciliation → revenue_ledger (future: correlation_id: abc-123)
```

**Query Pattern**:
```sql
-- Find all events related to correlation_id
SELECT 'attribution_events' as source, id, occurred_at, revenue_cents
FROM attribution_events
WHERE correlation_id = 'abc-123'

UNION ALL

SELECT 'attribution_allocations' as source, id, created_at, allocated_revenue_cents
FROM attribution_allocations
WHERE correlation_id = 'abc-123'

UNION ALL

SELECT 'dead_events' as source, id, ingested_at, NULL
FROM dead_events
WHERE correlation_id = 'abc-123'
ORDER BY occurred_at, created_at, ingested_at;
```

### Failed Ingestion Flow

```
Webhook → Validation Failure → dead_events (correlation_id: abc-123)
```

**Query Pattern**:
```sql
-- Find failed ingestion for correlation_id
SELECT id, source, error_code, error_detail, ingested_at
FROM dead_events
WHERE correlation_id = 'abc-123';
```

## Reconstruction Rules for Forensic Analysis

### Rule 1: Complete Event Flow

**Query**: "Show me everything that happened for correlation_id X"

**Tables to Query**:
1. `attribution_events` - Successful event ingestion
2. `dead_events` - Failed event ingestion
3. `attribution_allocations` - Attribution model results
4. Future: `revenue_ledger` - Verified revenue

**Reconstruction**:
- Order by timestamps (`occurred_at`, `ingested_at`, `created_at`)
- Link via `correlation_id`
- Reconstruct complete flow: ingestion → processing → allocation → verification

### Rule 2: Error Tracing

**Query**: "Why did correlation_id X fail?"

**Tables to Query**:
1. `dead_events` - Error details (`error_code`, `error_detail`)
2. `attribution_events` - Check if event was later successfully ingested

**Reconstruction**:
- If `dead_events` has entry: Event failed at ingestion
- If `attribution_events` has entry: Event succeeded (may have been retried)
- Compare timestamps to understand retry flow

### Rule 3: Attribution Chain

**Query**: "Show me attribution chain for correlation_id X"

**Tables to Query**:
1. `attribution_events` - Source event
2. `attribution_allocations` - Channel allocations

**Reconstruction**:
- Start with `attribution_events` (source event)
- Join to `attribution_allocations` via `event_id`
- Filter by `correlation_id` to ensure attribution chain integrity

## Column Comments

All `correlation_id` columns have comments explaining their role in event stitching:

### attribution_events.correlation_id

**Comment**: "Correlation ID from X-Correlation-ID header. Purpose: Distributed tracing and event stitching across tables. Links attribution_events, dead_events, and future attribution_allocations. Data class: Non-PII."

**Usage**: Links successful event ingestion to downstream processing

### dead_events.correlation_id

**Comment**: "Correlation ID from X-Correlation-ID header. Purpose: Distributed tracing and event stitching across tables. Links dead_events, attribution_events, and future attribution_allocations. Data class: Non-PII."

**Usage**: Links failed event ingestion for error tracing

### attribution_allocations.correlation_id

**Comment**: "Correlation ID from X-Correlation-ID header. Purpose: Distributed tracing and event stitching across tables. Links attribution_allocations, attribution_events, and dead_events. Data class: Non-PII."

**Usage**: Links attribution model results to source events

## Nullability Strategy

**Nullable**: `correlation_id` is nullable in all tables

**Rationale**:
- Some sources may not provide `X-Correlation-ID` header
- Legacy events may not have correlation_id
- System-generated events may not have correlation_id

**Best Practice**: 
- Always provide `X-Correlation-ID` in webhook requests (per contract requirement)
- Application should generate UUID if header is missing
- Never leave `correlation_id` NULL for new events (application responsibility)

## Cross-References

- **Contract**: `api-contracts/openapi/v1/_common/components.yaml:17-23`
- **Tables**: `attribution_events`, `dead_events`, `attribution_allocations`
- **DDL Specs**: `db/docs/specs/*_ddl_spec.sql`
- **Migration**: `alembic/versions/202511131115_add_core_tables.py`




