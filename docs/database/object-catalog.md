# Database Object Catalog

**Purpose**: Comprehensive catalog of all database functions, triggers, and materialized views with their purposes, signatures, invocation patterns, and dependencies.

**Last Updated**: 2025-11-16

## Functions

### PII Controls

#### `fn_detect_pii_keys(payload JSONB) RETURNS BOOLEAN`

**Purpose**: Fast key-based PII detection using PostgreSQL `?` operator

**Signature**: `fn_detect_pii_keys(payload JSONB) RETURNS BOOLEAN`

**Properties**: `IMMUTABLE`, <1ms overhead per call

**PII Key Blocklist** (13 keys):
- `email`, `email_address`
- `phone`, `phone_number`
- `ssn`, `social_security_number`
- `ip_address`, `ip`
- `first_name`, `last_name`, `full_name`
- `address`, `street_address`

**Invocation Pattern**:
```sql
SELECT fn_detect_pii_keys('{"email": "test@test.com"}'::jsonb);
-- Returns: TRUE

SELECT fn_detect_pii_keys('{"order_id": "123"}'::jsonb);
-- Returns: FALSE
```

**Dependencies**: None (standalone function)

**Migration**: `alembic/versions/002_pii_controls/202511161200_add_pii_guardrail_triggers.py`

**See Also**: `docs/database/pii-controls.md`

---

#### `fn_enforce_pii_guardrail() RETURNS TRIGGER`

**Purpose**: Trigger function that raises EXCEPTION if PII detected

**Signature**: `fn_enforce_pii_guardrail() RETURNS TRIGGER`

**Behavior**:
- For `attribution_events` and `dead_events`: Check `NEW.raw_payload`
- For `revenue_ledger`: Check `NEW.metadata` (only if NOT NULL)
- If PII key found: RAISE EXCEPTION with `ERRCODE = '23514'` (check_violation)

**Error Message Format**:
```
PII key detected in {table_name}.{column_name}. 
Ingestion blocked by database policy (Layer 2 guardrail). 
Key found: {detected_key}. 
Reference: ADR-003-PII-Defense-Strategy.md. 
Action: Remove PII key from payload before retry.
```

**Invocation Pattern**: Automatic (trigger function, not called directly)

**Dependencies**: `fn_detect_pii_keys()`

**Migration**: `alembic/versions/002_pii_controls/202511161200_add_pii_guardrail_triggers.py`

**See Also**: `docs/database/pii-controls.md`

---

#### `fn_scan_pii_contamination() RETURNS INTEGER`

**Purpose**: Batch scanning function that checks all three JSONB surfaces for PII keys and records findings

**Signature**: `fn_scan_pii_contamination() RETURNS INTEGER`

**Return Value**: Integer count of PII findings detected (0 = clean, >0 = contamination detected)

**Algorithm**:
- Scans `attribution_events.raw_payload`
- Scans `dead_events.raw_payload`
- Scans `revenue_ledger.metadata` (where NOT NULL)
- Inserts findings into `pii_audit_findings` table
- Returns total finding count

**Invocation Pattern**:
```sql
SELECT fn_scan_pii_contamination();
-- Returns: INTEGER (finding count)
```

**Performance**: Batch operation, intended for periodic scheduled execution (not per-transaction)

**Security**: Does NOT log actual PII values, only record IDs and key names

**Dependencies**: `fn_detect_pii_keys()`, `pii_audit_findings` table

**Migration**: `alembic/versions/002_pii_controls/202511161210_add_pii_audit_table.py`

**See Also**: `docs/database/pii-controls.md`, `scripts/database/run-audit-scan.sh`

---

### Data Integrity Controls

#### `check_allocation_sum() RETURNS TRIGGER`

**Purpose**: Validates that allocations sum to event revenue per `(event_id, model_version)` with ±1 cent tolerance

**Signature**: `check_allocation_sum() RETURNS TRIGGER`

**Behavior**:
- Calculates event revenue from `attribution_events.revenue_cents`
- Calculates allocated sum from `attribution_allocations.allocated_revenue_cents`
- Validates: `ABS(allocated_sum - event_revenue) <= 1` (tolerance: ±1 cent)
- Raises EXCEPTION if sum mismatch exceeds tolerance

**Error Message Format**:
```
Allocation sum mismatch: allocated={allocated_sum} expected={event_revenue} drift={drift_cents}
```

**Invocation Pattern**: Automatic (trigger function, not called directly)

**Dependencies**: `attribution_events` table, `attribution_allocations` table

**Migration**: `alembic/versions/003_data_governance/202511131240_add_sum_equality_validation.py`

**See Also**: `docs/database/schema-governance.md`, `scripts/database/test-data-integrity.sh`

---

#### `fn_events_prevent_mutation() RETURNS TRIGGER`

**Purpose**: Prevents UPDATE/DELETE operations on `attribution_events` table

**Signature**: `fn_events_prevent_mutation() RETURNS TRIGGER`

**Behavior**:
- Allows `migration_owner` role (for emergency repairs only)
- Blocks all other UPDATE/DELETE attempts with EXCEPTION

**Error Message Format**:
```
attribution_events is append-only; updates and deletes are not allowed. Use INSERT with correlation_id for corrections.
```

**Invocation Pattern**: Automatic (trigger function, not called directly)

**Dependencies**: None (standalone function)

**Migration**: `alembic/versions/003_data_governance/202511141201_add_events_guard_trigger.py`

**See Also**: `docs/database/schema-governance.md`, `db/docs/EVENTS_IMMUTABILITY_POLICY.md`

---

#### `fn_ledger_prevent_mutation() RETURNS TRIGGER`

**Purpose**: Prevents UPDATE/DELETE operations on `revenue_ledger` table

**Signature**: `fn_ledger_prevent_mutation() RETURNS TRIGGER`

**Behavior**:
- Allows `migration_owner` role (for emergency repairs only)
- Blocks all other UPDATE/DELETE attempts with EXCEPTION

**Error Message Format**:
```
revenue_ledger is append-only; updates and deletes are not allowed.
```

**Invocation Pattern**: Automatic (trigger function, not called directly)

**Dependencies**: None (standalone function)

**Migration**: `alembic/versions/003_data_governance/202511141301_add_ledger_guard_trigger.py`

**See Also**: `docs/database/schema-governance.md`

---

## Triggers

### PII Guardrail Triggers

#### `trg_pii_guardrail_attribution_events`

**Table**: `attribution_events`

**Purpose**: Block PII keys in `raw_payload` column

**Timing**: BEFORE INSERT

**Level**: FOR EACH ROW

**Function**: `fn_enforce_pii_guardrail()`

**Migration**: `alembic/versions/002_pii_controls/202511161200_add_pii_guardrail_triggers.py`

**See Also**: `docs/database/pii-controls.md`, `scripts/database/validate-pii-guardrails.sh`

---

#### `trg_pii_guardrail_dead_events`

**Table**: `dead_events`

**Purpose**: Block PII keys in `raw_payload` column

**Timing**: BEFORE INSERT

**Level**: FOR EACH ROW

**Function**: `fn_enforce_pii_guardrail()`

**Migration**: `alembic/versions/002_pii_controls/202511161200_add_pii_guardrail_triggers.py`

**See Also**: `docs/database/pii-controls.md`, `scripts/database/validate-pii-guardrails.sh`

---

#### `trg_pii_guardrail_revenue_ledger`

**Table**: `revenue_ledger`

**Purpose**: Block PII keys in `metadata` column (only if NOT NULL)

**Timing**: BEFORE INSERT

**Level**: FOR EACH ROW

**Function**: `fn_enforce_pii_guardrail()`

**Migration**: `alembic/versions/002_pii_controls/202511161200_add_pii_guardrail_triggers.py`

**See Also**: `docs/database/pii-controls.md`, `scripts/database/validate-pii-guardrails.sh`

---

### Data Integrity Triggers

#### `trg_check_allocation_sum`

**Table**: `attribution_allocations`

**Purpose**: Enforce sum-equality invariant: allocations must sum to event revenue per `(event_id, model_version)` with ±1 cent tolerance

**Timing**: AFTER INSERT OR UPDATE OR DELETE

**Level**: FOR EACH ROW

**Function**: `check_allocation_sum()`

**Migration**: `alembic/versions/003_data_governance/202511131240_add_sum_equality_validation.py`

**See Also**: `docs/database/schema-governance.md`, `scripts/database/test-data-integrity.sh`

---

#### `trg_events_prevent_mutation`

**Table**: `attribution_events`

**Purpose**: Prevent UPDATE/DELETE operations (defense-in-depth immutability enforcement)

**Timing**: BEFORE UPDATE OR DELETE

**Level**: FOR EACH ROW

**Function**: `fn_events_prevent_mutation()`

**Migration**: `alembic/versions/003_data_governance/202511141201_add_events_guard_trigger.py`

**See Also**: `docs/database/schema-governance.md`, `scripts/database/test-data-integrity.sh`

---

#### `trg_ledger_prevent_mutation`

**Table**: `revenue_ledger`

**Purpose**: Prevent UPDATE/DELETE operations (defense-in-depth immutability enforcement)

**Timing**: BEFORE UPDATE OR DELETE

**Level**: FOR EACH ROW

**Function**: `fn_ledger_prevent_mutation()`

**Migration**: `alembic/versions/003_data_governance/202511141301_add_ledger_guard_trigger.py`

**See Also**: `docs/database/schema-governance.md`, `scripts/database/test-data-integrity.sh`

---

## Materialized Views

### Revenue Aggregation

#### `mv_realtime_revenue`

**Purpose**: Aggregates realtime revenue data for GET `/api/attribution/revenue/realtime` endpoint

**Query**:
```sql
SELECT 
    rl.tenant_id,
    COALESCE(SUM(rl.revenue_cents), 0) / 100.0 AS total_revenue,
    BOOL_OR(rl.is_verified) AS verified,
    EXTRACT(EPOCH FROM (now() - MAX(rl.updated_at)))::INTEGER AS data_freshness_seconds
FROM revenue_ledger rl
GROUP BY rl.tenant_id
```

**Indexes**:
- `idx_mv_realtime_revenue_tenant_id` (UNIQUE on `tenant_id`)

**Refresh Policy**: CONCURRENTLY with TTL-based refresh (30-60s)

**Invocation Pattern**:
```sql
SELECT * FROM mv_realtime_revenue WHERE tenant_id = '...';
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_realtime_revenue;
```

**Dependencies**: `revenue_ledger` table

**Migration**: `alembic/versions/001_core_schema/202511131119_add_materialized_views.py`

**See Also**: `docs/architecture/evidence-mapping.md`

---

#### `mv_daily_revenue_summary`

**Purpose**: Pre-aggregates daily revenue metrics from `revenue_ledger` with state-based filtering for dashboard KPIs

**Query**:
```sql
SELECT
    tenant_id,
    DATE_TRUNC('day', verification_timestamp) AS revenue_date,
    state,
    currency,
    SUM(amount_cents) AS total_amount_cents,
    COUNT(*) AS transaction_count
FROM revenue_ledger
WHERE state IN ('captured', 'refunded', 'chargeback')
GROUP BY tenant_id, DATE_TRUNC('day', verification_timestamp), state, currency
```

**Indexes**:
- `idx_mv_daily_revenue_summary_unique` (UNIQUE on `tenant_id, revenue_date, state, currency`)

**Refresh Policy**: CONCURRENTLY daily

**Invocation Pattern**:
```sql
SELECT * FROM mv_daily_revenue_summary 
WHERE tenant_id = '...' 
  AND revenue_date >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY revenue_date DESC;
```

**Dependencies**: `revenue_ledger` table

**Migration**: `alembic/versions/003_data_governance/202511151510_add_mv_daily_revenue_summary.py`

**See Also**: `docs/architecture/evidence-mapping.md`

---

### Attribution Analytics

#### `mv_allocation_summary`

**Purpose**: Aggregates allocation sums per `(tenant_id, event_id, model_version)` for sum-equality validation

**Query**:
```sql
SELECT 
    aa.tenant_id,
    aa.event_id,
    aa.model_version,
    SUM(aa.allocated_revenue_cents) AS total_allocated_cents,
    e.revenue_cents AS event_revenue_cents,
    (SUM(aa.allocated_revenue_cents) = e.revenue_cents) AS is_balanced,
    ABS(SUM(aa.allocated_revenue_cents) - e.revenue_cents) AS drift_cents
FROM attribution_allocations aa
INNER JOIN attribution_events e ON aa.event_id = e.id
GROUP BY aa.tenant_id, aa.event_id, aa.model_version, e.revenue_cents
```

**Indexes**:
- `idx_mv_allocation_summary_key` (UNIQUE on `tenant_id, event_id, model_version`)
- `idx_mv_allocation_summary_drift` (Partial index on `drift_cents` WHERE `drift_cents > 1`)

**Refresh Policy**: CONCURRENTLY on demand

**Invocation Pattern**:
```sql
SELECT * FROM mv_allocation_summary 
WHERE tenant_id = '...' 
  AND is_balanced = false;
```

**Dependencies**: `attribution_allocations` table, `attribution_events` table

**Migration**: `alembic/versions/003_data_governance/202511131240_add_sum_equality_validation.py`

**See Also**: `docs/database/schema-governance.md`

---

#### `mv_channel_performance`

**Purpose**: Pre-aggregates channel performance metrics with 90-day rolling window

**Query**:
```sql
SELECT
    tenant_id,
    channel_code,
    DATE_TRUNC('day', created_at) AS allocation_date,
    COUNT(DISTINCT event_id) AS total_conversions,
    SUM(allocated_revenue_cents) AS total_revenue_cents,
    AVG(confidence_score) AS avg_confidence_score,
    COUNT(*) AS total_allocations
FROM attribution_allocations
WHERE created_at >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY tenant_id, channel_code, DATE_TRUNC('day', created_at)
```

**Indexes**:
- `idx_mv_channel_performance_unique` (UNIQUE on `tenant_id, channel_code, allocation_date`)

**Refresh Policy**: CONCURRENTLY daily

**Invocation Pattern**:
```sql
SELECT * FROM mv_channel_performance 
WHERE tenant_id = '...' 
  AND allocation_date >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY total_revenue_cents DESC;
```

**Dependencies**: `attribution_allocations` table

**Migration**: `alembic/versions/003_data_governance/202511151500_add_mv_channel_performance.py`

**See Also**: `docs/architecture/evidence-mapping.md`

---

### Reconciliation

#### `mv_reconciliation_status`

**Purpose**: Provides latest reconciliation status per tenant for GET `/api/reconciliation/status` endpoint

**Query**:
```sql
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
    AND rr.last_run_at = latest.max_last_run_at
```

**Indexes**:
- `idx_mv_reconciliation_status_tenant_id` (UNIQUE on `tenant_id`)

**Refresh Policy**: CONCURRENTLY with TTL-based refresh (30-60s)

**Invocation Pattern**:
```sql
SELECT * FROM mv_reconciliation_status WHERE tenant_id = '...';
```

**Dependencies**: `reconciliation_runs` table

**Migration**: `alembic/versions/001_core_schema/202511131119_add_materialized_views.py`

**See Also**: `docs/architecture/evidence-mapping.md`

---

## Summary Statistics

**Total Functions**: 6
- PII Controls: 3
- Data Integrity: 3

**Total Triggers**: 6
- PII Guardrail: 3
- Data Integrity: 3

**Total Materialized Views**: 5
- Revenue Aggregation: 2
- Attribution Analytics: 2
- Reconciliation: 1

**Total Database Objects**: 17

## Related Documentation

- **Evidence Mapping**: `docs/architecture/evidence-mapping.md`
- **PII Controls**: `docs/database/pii-controls.md`
- **Schema Governance**: `docs/database/schema-governance.md`
- **Validation Scripts**: `scripts/database/`

