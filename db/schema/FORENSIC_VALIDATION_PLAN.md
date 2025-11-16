# Forensic Validation Plan for B0.3 Schema Realignment
# Phases 4-8 Migration Validation Protocol

**Document Purpose**: Scientific, gate-driven validation protocol for Phases 4-8 schema migrations.

**Validation Philosophy**: Each phase must be empirically verified against specific exit criteria before proceeding to the next phase. This document provides SQL-based forensic tests to confirm schema compliance.

**Version**: 1.0.0  
**Date**: 2025-11-15  
**Status**: 🔬 VALIDATION PROTOCOL ACTIVE

---

## Table of Contents

1. [Phase 4: Tenants Table Validation](#phase-4-tenants-table-validation)
2. [Phase 5: Attribution Events Table Validation](#phase-5-attribution-events-table-validation)
3. [Phase 6: Attribution Allocations Table Validation](#phase-6-attribution-allocations-table-validation)
4. [Phase 7: Revenue Ledger Table Validation](#phase-7-revenue-ledger-table-validation)
5. [Phase 8: Dead Events & State Transitions Validation](#phase-8-dead-events--state-transitions-validation)
6. [Validation Execution Order](#validation-execution-order)
7. [Evidence Requirements](#evidence-requirements)

---

## Phase 4: Tenants Table Validation

### Migration Applied
`alembic/versions/202511151400_add_tenants_auth_columns.py`

### Exit Gates

#### Gate 4.1: Column Existence
**Test**: Verify both columns exist with correct types and nullability.

```sql
-- Test 4.1.1: Columns exist in table
SELECT column_name, data_type, character_maximum_length, is_nullable
FROM information_schema.columns
WHERE table_name = 'tenants'
  AND column_name IN ('api_key_hash', 'notification_email')
ORDER BY column_name;

-- Expected Result:
-- api_key_hash         | character varying | 255 | NO
-- notification_email   | character varying | 255 | NO
```

**PASS Criteria**: Both columns exist with VARCHAR(255) type and NOT NULL constraint.

#### Gate 4.2: UNIQUE Constraint on api_key_hash
**Test**: Verify UNIQUE constraint prevents duplicate API keys.

```sql
-- Test 4.2.1: Verify unique index exists
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'tenants'
  AND indexname = 'idx_tenants_api_key_hash';

-- Expected Result: Index exists with UNIQUE constraint

-- Test 4.2.2: Attempt to insert duplicate api_key_hash (should fail)
BEGIN;
INSERT INTO tenants (name, api_key_hash, notification_email)
VALUES ('Test Tenant 1', 'duplicate_key', 'test1@example.com');

INSERT INTO tenants (name, api_key_hash, notification_email)
VALUES ('Test Tenant 2', 'duplicate_key', 'test2@example.com');
-- Expected: ERROR: duplicate key value violates unique constraint
ROLLBACK;
```

**PASS Criteria**: Second insert fails with unique constraint violation error.

#### Gate 4.3: NOT NULL Constraints Enforced
**Test**: Verify NULL values are rejected.

```sql
-- Test 4.3.1: Attempt to insert NULL api_key_hash (should fail)
BEGIN;
INSERT INTO tenants (name, api_key_hash, notification_email)
VALUES ('Test Tenant', NULL, 'test@example.com');
-- Expected: ERROR: null value in column "api_key_hash" violates not-null constraint
ROLLBACK;

-- Test 4.3.2: Attempt to insert NULL notification_email (should fail)
BEGIN;
INSERT INTO tenants (name, api_key_hash, notification_email)
VALUES ('Test Tenant', 'test_key', NULL);
-- Expected: ERROR: null value in column "notification_email" violates not-null constraint
ROLLBACK;
```

**PASS Criteria**: Both inserts fail with not-null constraint violations.

#### Gate 4.4: Comments and Metadata
**Test**: Verify column comments are properly set.

```sql
-- Test 4.4.1: Verify column comments
SELECT col_description('tenants'::regclass, ordinal_position) as comment
FROM information_schema.columns
WHERE table_name = 'tenants'
  AND column_name IN ('api_key_hash', 'notification_email')
ORDER BY column_name;

-- Expected: Comments contain "INVARIANT: auth_critical" and purpose descriptions
```

**PASS Criteria**: Both columns have comments with INVARIANT tags.

### Phase 4 Sign-Off

**Validation Status**: ⬜ NOT STARTED | ⬜ IN PROGRESS | ⬜ COMPLETE  
**Validator Name**: ___________________________  
**Validation Date**: ___________________________  
**Exit Gates Passed**: __ / 4  
**Notes**: _______________________________________

---

## Phase 5: Attribution Events Table Validation

### Migration Applied
`alembic/versions/202511151410_realign_attribution_events.py`

### Exit Gates

#### Gate 5.1: All 10 Columns Exist
**Test**: Verify all new columns exist with correct types.

```sql
-- Test 5.1.1: Verify all 10 new columns
SELECT column_name, data_type, character_maximum_length, is_nullable
FROM information_schema.columns
WHERE table_name = 'attribution_events'
  AND column_name IN (
    'idempotency_key', 'event_type', 'channel', 'campaign_id',
    'conversion_value_cents', 'currency', 'event_timestamp',
    'processed_at', 'processing_status', 'retry_count'
  )
ORDER BY column_name;

-- Expected Result: All 10 columns exist with correct types
-- idempotency_key: VARCHAR(255) NOT NULL
-- event_type: VARCHAR(50) NOT NULL
-- channel: VARCHAR(100) NOT NULL
-- campaign_id: VARCHAR(255) NULL
-- conversion_value_cents: INTEGER NULL
-- currency: VARCHAR(3) NOT NULL
-- event_timestamp: TIMESTAMPTZ NOT NULL
-- processed_at: TIMESTAMPTZ NULL
-- processing_status: VARCHAR(20) NOT NULL
-- retry_count: INTEGER NOT NULL
```

**PASS Criteria**: All 10 columns exist with correct types and nullability.

#### Gate 5.2: idempotency_key UNIQUE Constraint
**Test**: Verify idempotency_key uniqueness enforced.

```sql
-- Test 5.2.1: Verify unique index exists
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'attribution_events'
  AND indexname = 'idx_events_idempotency';

-- Test 5.2.2: Attempt duplicate idempotency_key (should fail)
BEGIN;
INSERT INTO attribution_events (
  tenant_id, session_id, idempotency_key, event_type, channel,
  event_timestamp, raw_payload
) VALUES (
  gen_random_uuid(), gen_random_uuid(), 'test_idempotency_1',
  'purchase', 'google_search', now(), '{}'::jsonb
);

INSERT INTO attribution_events (
  tenant_id, session_id, idempotency_key, event_type, channel,
  event_timestamp, raw_payload
) VALUES (
  gen_random_uuid(), gen_random_uuid(), 'test_idempotency_1',
  'click', 'facebook', now(), '{}'::jsonb
);
-- Expected: ERROR: duplicate key value violates unique constraint
ROLLBACK;
```

**PASS Criteria**: Second insert fails with unique constraint violation.

#### Gate 5.3: session_id NOT NULL Enforced
**Test**: Verify session_id no longer accepts NULL.

```sql
-- Test 5.3.1: Attempt NULL session_id (should fail)
BEGIN;
INSERT INTO attribution_events (
  tenant_id, session_id, idempotency_key, event_type, channel,
  event_timestamp, raw_payload
) VALUES (
  gen_random_uuid(), NULL, 'test_idempotency_2',
  'purchase', 'google_search', now(), '{}'::jsonb
);
-- Expected: ERROR: null value in column "session_id" violates not-null constraint
ROLLBACK;
```

**PASS Criteria**: Insert fails with not-null constraint violation.

#### Gate 5.4: processing_status CHECK Constraint
**Test**: Verify invalid status values are rejected.

```sql
-- Test 5.4.1: Attempt invalid processing_status (should fail)
BEGIN;
INSERT INTO attribution_events (
  tenant_id, session_id, idempotency_key, event_type, channel,
  event_timestamp, processing_status, raw_payload
) VALUES (
  gen_random_uuid(), gen_random_uuid(), 'test_idempotency_3',
  'purchase', 'google_search', now(), 'invalid_status', '{}'::jsonb
);
-- Expected: ERROR: new row violates check constraint
ROLLBACK;

-- Test 5.4.2: Verify valid statuses accepted
BEGIN;
INSERT INTO attribution_events (
  tenant_id, session_id, idempotency_key, event_type, channel,
  event_timestamp, processing_status, raw_payload
) VALUES (
  gen_random_uuid(), gen_random_uuid(), 'test_idempotency_4',
  'purchase', 'google_search', now(), 'pending', '{}'::jsonb
),
(
  gen_random_uuid(), gen_random_uuid(), 'test_idempotency_5',
  'purchase', 'google_search', now(), 'processed', '{}'::jsonb
),
(
  gen_random_uuid(), gen_random_uuid(), 'test_idempotency_6',
  'purchase', 'google_search', now(), 'failed', '{}'::jsonb
);
-- Expected: SUCCESS - all three valid statuses accepted
ROLLBACK;
```

**PASS Criteria**: Invalid status rejected, all three valid statuses accepted.

#### Gate 5.5: Old Composite Indexes Dropped
**Test**: Verify old idempotency indexes are removed.

```sql
-- Test 5.5.1: Verify old indexes do not exist
SELECT indexname
FROM pg_indexes
WHERE tablename = 'attribution_events'
  AND indexname IN (
    'idx_attribution_events_tenant_external_event_id',
    'idx_attribution_events_tenant_correlation_id'
  );

-- Expected Result: 0 rows (both indexes dropped)
```

**PASS Criteria**: Both old composite indexes are gone.

#### Gate 5.6: New Canonical Indexes Exist
**Test**: Verify new indexes created.

```sql
-- Test 5.6.1: Verify canonical indexes exist
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'attribution_events'
  AND indexname IN (
    'idx_events_tenant_timestamp',
    'idx_events_processing_status'
  )
ORDER BY indexname;

-- Expected Result: Both indexes exist
-- idx_events_tenant_timestamp: (tenant_id, event_timestamp DESC)
-- idx_events_processing_status: (processing_status, processed_at) WHERE processing_status = 'pending'
```

**PASS Criteria**: Both canonical indexes exist with correct definitions.

### Phase 5 Sign-Off

**Validation Status**: ⬜ NOT STARTED | ⬜ IN PROGRESS | ⬜ COMPLETE  
**Validator Name**: ___________________________  
**Validation Date**: ___________________________  
**Exit Gates Passed**: __ / 6  
**Notes**: _______________________________________

---

## Phase 6: Attribution Allocations Table Validation

### Migration Applied
`alembic/versions/202511151420_add_allocations_statistical_fields.py`

### Exit Gates

#### Gate 6.1: All 9 Columns Exist
**Test**: Verify all statistical metadata columns exist.

```sql
-- Test 6.1.1: Verify all 9 new columns
SELECT column_name, data_type, numeric_precision, numeric_scale, is_nullable
FROM information_schema.columns
WHERE table_name = 'attribution_allocations'
  AND column_name IN (
    'model_type', 'confidence_score', 'credible_interval_lower_cents',
    'credible_interval_upper_cents', 'convergence_r_hat',
    'effective_sample_size', 'verified', 'verification_source',
    'verification_timestamp'
  )
ORDER BY column_name;

-- Expected Results:
-- model_type: VARCHAR(50) NOT NULL
-- confidence_score: NUMERIC(4,3) NOT NULL
-- credible_interval_lower_cents: INTEGER NULL
-- credible_interval_upper_cents: INTEGER NULL
-- convergence_r_hat: NUMERIC(5,4) NULL
-- effective_sample_size: INTEGER NULL
-- verified: BOOLEAN NOT NULL
-- verification_source: VARCHAR(50) NULL
-- verification_timestamp: TIMESTAMPTZ NULL
```

**PASS Criteria**: All 9 columns exist with correct types and nullability.

#### Gate 6.2: confidence_score CHECK Constraint
**Test**: Verify confidence_score bounds enforced.

```sql
-- Test 6.2.1: Attempt confidence_score > 1.0 (should fail)
BEGIN;
INSERT INTO attribution_allocations (
  tenant_id, event_id, model_type, channel_code,
  allocated_revenue_cents, confidence_score
) VALUES (
  gen_random_uuid(), gen_random_uuid(), 'test_model', 'google_search',
  1000, 1.5
);
-- Expected: ERROR: new row violates check constraint "ck_allocations_confidence_score"
ROLLBACK;

-- Test 6.2.2: Attempt confidence_score < 0.0 (should fail)
BEGIN;
INSERT INTO attribution_allocations (
  tenant_id, event_id, model_type, channel_code,
  allocated_revenue_cents, confidence_score
) VALUES (
  gen_random_uuid(), gen_random_uuid(), 'test_model', 'google_search',
  1000, -0.1
);
-- Expected: ERROR: new row violates check constraint
ROLLBACK;

-- Test 6.2.3: Valid confidence_score accepted (0.0, 0.5, 1.0)
BEGIN;
INSERT INTO attribution_allocations (
  tenant_id, event_id, model_type, channel_code,
  allocated_revenue_cents, confidence_score, verified
) VALUES (
  gen_random_uuid(), gen_random_uuid(), 'test_model', 'google_search',
  1000, 0.0, false
),
(
  gen_random_uuid(), gen_random_uuid(), 'test_model', 'google_search',
  1000, 0.5, false
),
(
  gen_random_uuid(), gen_random_uuid(), 'test_model', 'google_search',
  1000, 1.0, false
);
-- Expected: SUCCESS - all three valid scores accepted
ROLLBACK;
```

**PASS Criteria**: Values outside [0, 1] rejected, boundary values accepted.

#### Gate 6.3: Canonical Index with INCLUDE Clause
**Test**: Verify performance index created.

```sql
-- Test 6.3.1: Verify index exists with INCLUDE clause
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'attribution_allocations'
  AND indexname = 'idx_allocations_channel_performance';

-- Expected: Index exists with definition:
-- CREATE INDEX idx_allocations_channel_performance 
--   ON attribution_allocations (tenant_id, channel_code, created_at DESC) 
--   INCLUDE (allocated_revenue_cents, confidence_score)
```

**PASS Criteria**: Index exists with INCLUDE clause containing both revenue and confidence.

### Phase 6 Sign-Off

**Validation Status**: ⬜ NOT STARTED | ⬜ IN PROGRESS | ⬜ COMPLETE  
**Validator Name**: ___________________________  
**Validation Date**: ___________________________  
**Exit Gates Passed**: __ / 3  
**Notes**: _______________________________________

---

## Phase 7: Revenue Ledger Table Validation

### Migration Applied
`alembic/versions/202511151430_realign_revenue_ledger.py`

### Exit Gates

#### Gate 7.1: All 9 Columns Exist
**Test**: Verify all state machine columns exist.

```sql
-- Test 7.1.1: Verify all 9 new columns
SELECT column_name, data_type, character_maximum_length, is_nullable
FROM information_schema.columns
WHERE table_name = 'revenue_ledger'
  AND column_name IN (
    'transaction_id', 'order_id', 'state', 'previous_state',
    'amount_cents', 'currency', 'verification_source',
    'verification_timestamp', 'metadata'
  )
ORDER BY column_name;

-- Expected Results:
-- transaction_id: VARCHAR(255) NOT NULL
-- order_id: VARCHAR(255) NULL
-- state: VARCHAR(50) NOT NULL
-- previous_state: VARCHAR(50) NULL
-- amount_cents: INTEGER NOT NULL
-- currency: VARCHAR(3) NOT NULL
-- verification_source: VARCHAR(50) NOT NULL
-- verification_timestamp: TIMESTAMPTZ NOT NULL
-- metadata: JSONB NULL
```

**PASS Criteria**: All 9 columns exist with correct types and nullability.

#### Gate 7.2: transaction_id UNIQUE Constraint
**Test**: Verify transaction_id uniqueness enforced.

```sql
-- Test 7.2.1: Verify unique index exists
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'revenue_ledger'
  AND indexname = 'idx_revenue_ledger_transaction_id';

-- Test 7.2.2: Attempt duplicate transaction_id (should fail)
BEGIN;
INSERT INTO revenue_ledger (
  tenant_id, transaction_id, state, amount_cents, currency,
  verification_source, verification_timestamp
) VALUES (
  gen_random_uuid(), 'txn_duplicate_test', 'captured', 1000, 'USD',
  'test_source', now()
);

INSERT INTO revenue_ledger (
  tenant_id, transaction_id, state, amount_cents, currency,
  verification_source, verification_timestamp
) VALUES (
  gen_random_uuid(), 'txn_duplicate_test', 'captured', 2000, 'EUR',
  'test_source', now()
);
-- Expected: ERROR: duplicate key value violates unique constraint
ROLLBACK;
```

**PASS Criteria**: Second insert fails with unique constraint violation.

#### Gate 7.3: state CHECK Constraint
**Test**: Verify state enum enforced.

```sql
-- Test 7.3.1: Attempt invalid state (should fail)
BEGIN;
INSERT INTO revenue_ledger (
  tenant_id, transaction_id, state, amount_cents, currency,
  verification_source, verification_timestamp
) VALUES (
  gen_random_uuid(), 'txn_invalid_state', 'invalid_state', 1000, 'USD',
  'test_source', now()
);
-- Expected: ERROR: new row violates check constraint "ck_revenue_ledger_state_valid"
ROLLBACK;

-- Test 7.3.2: Verify all valid states accepted
BEGIN;
INSERT INTO revenue_ledger (
  tenant_id, transaction_id, state, amount_cents, currency,
  verification_source, verification_timestamp
) VALUES (
  gen_random_uuid(), 'txn_authorized', 'authorized', 1000, 'USD',
  'test_source', now()
),
(
  gen_random_uuid(), 'txn_captured', 'captured', 2000, 'USD',
  'test_source', now()
),
(
  gen_random_uuid(), 'txn_refunded', 'refunded', 3000, 'USD',
  'test_source', now()
),
(
  gen_random_uuid(), 'txn_chargeback', 'chargeback', 4000, 'USD',
  'test_source', now()
);
-- Expected: SUCCESS - all four valid states accepted
ROLLBACK;
```

**PASS Criteria**: Invalid state rejected, all four valid states accepted.

#### Gate 7.4: NOT NULL Constraints Enforced
**Test**: Verify required fields cannot be NULL.

```sql
-- Test 7.4.1: Attempt NULL transaction_id (should fail)
BEGIN;
INSERT INTO revenue_ledger (
  tenant_id, transaction_id, state, amount_cents, currency,
  verification_source, verification_timestamp
) VALUES (
  gen_random_uuid(), NULL, 'captured', 1000, 'USD',
  'test_source', now()
);
-- Expected: ERROR: null value violates not-null constraint
ROLLBACK;

-- Similar tests for: state, amount_cents, currency, 
-- verification_source, verification_timestamp
```

**PASS Criteria**: All NOT NULL constraints enforced.

#### Gate 7.5: Indexes Exist
**Test**: Verify state and tenant indexes created.

```sql
-- Test 7.5.1: Verify state indexes
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'revenue_ledger'
  AND indexname IN (
    'idx_revenue_ledger_state',
    'idx_revenue_ledger_tenant_state'
  )
ORDER BY indexname;

-- Expected: Both indexes exist
```

**PASS Criteria**: Both state indexes exist.

### Phase 7 Sign-Off

**Validation Status**: ⬜ NOT STARTED | ⬜ IN PROGRESS | ⬜ COMPLETE  
**Validator Name**: ___________________________  
**Validation Date**: ___________________________  
**Exit Gates Passed**: __ / 5  
**Notes**: _______________________________________

---

## Phase 8: Dead Events & State Transitions Validation

### Migration Applied
- `alembic/versions/202511151440_add_dead_events_retry_tracking.py`
- `alembic/versions/202511151450_create_revenue_state_transitions.py`

### Exit Gates - Part A: Dead Events

#### Gate 8a.1: All 9 Columns Exist in dead_events
**Test**: Verify retry tracking columns exist.

```sql
-- Test 8a.1.1: Verify all 9 new columns
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'dead_events'
  AND column_name IN (
    'event_type', 'error_type', 'error_message', 'error_traceback',
    'retry_count', 'last_retry_at', 'remediation_status',
    'remediation_notes', 'resolved_at'
  )
ORDER BY column_name;

-- Expected: All 9 columns exist with correct nullability
-- event_type: VARCHAR(50) NOT NULL
-- error_type: VARCHAR(100) NOT NULL
-- error_message: TEXT NOT NULL
-- error_traceback: TEXT NULL
-- retry_count: INTEGER NOT NULL
-- last_retry_at: TIMESTAMPTZ NULL
-- remediation_status: VARCHAR(20) NOT NULL
-- remediation_notes: TEXT NULL
-- resolved_at: TIMESTAMPTZ NULL
```

**PASS Criteria**: All 9 columns exist with correct types and nullability.

#### Gate 8a.2: remediation_status CHECK Constraint
**Test**: Verify remediation status enum enforced.

```sql
-- Test 8a.2.1: Attempt invalid remediation_status (should fail)
BEGIN;
INSERT INTO dead_events (
  tenant_id, event_type, raw_payload, error_type, error_message,
  remediation_status
) VALUES (
  gen_random_uuid(), 'purchase', '{}'::jsonb, 'validation_error',
  'Test error', 'invalid_status'
);
-- Expected: ERROR: new row violates check constraint
ROLLBACK;

-- Test 8a.2.2: Verify valid statuses accepted
BEGIN;
INSERT INTO dead_events (
  tenant_id, event_type, raw_payload, error_type, error_message,
  remediation_status
) VALUES (
  gen_random_uuid(), 'purchase', '{}'::jsonb, 'validation_error',
  'Test error', 'pending'
),
(
  gen_random_uuid(), 'purchase', '{}'::jsonb, 'validation_error',
  'Test error', 'in_progress'
),
(
  gen_random_uuid(), 'purchase', '{}'::jsonb, 'validation_error',
  'Test error', 'resolved'
),
(
  gen_random_uuid(), 'purchase', '{}'::jsonb, 'validation_error',
  'Test error', 'ignored'
);
-- Expected: SUCCESS - all four valid statuses accepted
ROLLBACK;
```

**PASS Criteria**: Invalid status rejected, all four valid statuses accepted.

#### Gate 8a.3: Remediation Index Exists
**Test**: Verify remediation queue index created.

```sql
-- Test 8a.3.1: Verify index exists
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'dead_events'
  AND indexname = 'idx_dead_events_remediation';

-- Expected: Index exists on (remediation_status, created_at DESC)
```

**PASS Criteria**: Remediation index exists.

### Exit Gates - Part B: Revenue State Transitions

#### Gate 8b.1: Table Exists with All Columns
**Test**: Verify revenue_state_transitions table created.

```sql
-- Test 8b.1.1: Verify table exists
SELECT table_name, table_type
FROM information_schema.tables
WHERE table_name = 'revenue_state_transitions';

-- Expected: Table exists

-- Test 8b.1.2: Verify all 6 columns
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'revenue_state_transitions'
ORDER BY ordinal_position;

-- Expected Results:
-- id: UUID NOT NULL
-- ledger_id: UUID NOT NULL
-- from_state: VARCHAR(50) NULL
-- to_state: VARCHAR(50) NOT NULL
-- reason: TEXT NULL
-- transitioned_at: TIMESTAMPTZ NOT NULL
```

**PASS Criteria**: Table exists with all 6 columns.

#### Gate 8b.2: Foreign Key to revenue_ledger
**Test**: Verify CASCADE delete behavior.

```sql
-- Test 8b.2.1: Verify FK constraint exists
SELECT conname, contype, confdeltype
FROM pg_constraint
WHERE conrelid = 'revenue_state_transitions'::regclass
  AND confrelid = 'revenue_ledger'::regclass;

-- Expected: FK constraint with CASCADE delete (confdeltype = 'c')

-- Test 8b.2.2: Test CASCADE delete behavior
BEGIN;
-- Insert test ledger entry
INSERT INTO revenue_ledger (
  tenant_id, transaction_id, state, amount_cents, currency,
  verification_source, verification_timestamp
) VALUES (
  gen_random_uuid(), 'txn_cascade_test', 'captured', 1000, 'USD',
  'test_source', now()
)
RETURNING id AS test_ledger_id \gset

-- Insert transition record
INSERT INTO revenue_state_transitions (
  ledger_id, from_state, to_state, reason
) VALUES (
  :'test_ledger_id', 'authorized', 'captured', 'Payment captured'
);

-- Verify transition exists
SELECT COUNT(*) FROM revenue_state_transitions WHERE ledger_id = :'test_ledger_id';
-- Expected: 1

-- Delete ledger entry
DELETE FROM revenue_ledger WHERE id = :'test_ledger_id';

-- Verify transition was CASCADE deleted
SELECT COUNT(*) FROM revenue_state_transitions WHERE ledger_id = :'test_ledger_id';
-- Expected: 0

ROLLBACK;
```

**PASS Criteria**: FK constraint exists with CASCADE delete working.

#### Gate 8b.3: Index Exists
**Test**: Verify ledger_id index created.

```sql
-- Test 8b.3.1: Verify index exists
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'revenue_state_transitions'
  AND indexname = 'idx_revenue_state_transitions_ledger_id';

-- Expected: Index exists on (ledger_id, transitioned_at DESC)
```

**PASS Criteria**: Index exists.

### Phase 8 Sign-Off

**Validation Status**: ⬜ NOT STARTED | ⬜ IN PROGRESS | ⬜ COMPLETE  
**Validator Name**: ___________________________  
**Validation Date**: ___________________________  
**Exit Gates Passed - Part A**: __ / 3  
**Exit Gates Passed - Part B**: __ / 3  
**Notes**: _______________________________________

---

## Validation Execution Order

### Prerequisites
1. Database connection with appropriate privileges
2. Alembic installed and configured
3. DATABASE_URL environment variable set

### Execution Steps

```bash
# Step 1: Apply Phase 4 migration
alembic upgrade 202511151400

# Step 2: Run Phase 4 forensic validation tests
psql $DATABASE_URL < forensic_tests_phase4.sql

# Step 3: Record Phase 4 validation evidence
# (Document results in Phase 4 Sign-Off section)

# Step 4: Apply Phase 5 migration
alembic upgrade 202511151410

# Step 5: Run Phase 5 forensic validation tests
psql $DATABASE_URL < forensic_tests_phase5.sql

# Step 6: Record Phase 5 validation evidence

# ... Continue for Phases 6, 7, 8 ...

# Final Step: Generate complete validation report
psql $DATABASE_URL < forensic_full_schema_validation.sql
```

### Gate-Driven Progress

**CRITICAL RULE**: Do not proceed to Phase N+1 until all exit gates for Phase N are PASSED.

---

## Evidence Requirements

### For Each Phase

1. **SQL Test Results**
   - Copy/paste of all test queries and their outputs
   - Screenshot or text export of pg_dump for affected tables
   - EXPLAIN ANALYZE results for index usage

2. **Constraint Verification**
   - Documented failed insert attempts (for constraint tests)
   - Error messages proving constraints are enforced

3. **Metadata Verification**
   - Column comments extracted via `\d+ tablename`
   - Index definitions via `\di+ indexname`

4. **Sign-Off**
   - Validator name and date
   - Exit gate pass/fail status
   - Notes on any anomalies or deviations

### Final Validation Report

After all phases complete, generate comprehensive report:

```sql
-- Generate complete schema validation report
\o schema_validation_report.txt

SELECT 'PHASE 4-8 VALIDATION REPORT' AS title;
SELECT 'Generated: ' || now() AS timestamp;

-- Table column counts
SELECT 'tenants: ' || COUNT(*) AS phase4_columns
FROM information_schema.columns WHERE table_name = 'tenants';

SELECT 'attribution_events: ' || COUNT(*) AS phase5_columns
FROM information_schema.columns WHERE table_name = 'attribution_events';

SELECT 'attribution_allocations: ' || COUNT(*) AS phase6_columns
FROM information_schema.columns WHERE table_name = 'attribution_allocations';

SELECT 'revenue_ledger: ' || COUNT(*) AS phase7_columns
FROM information_schema.columns WHERE table_name = 'revenue_ledger';

SELECT 'dead_events: ' || COUNT(*) AS phase8a_columns
FROM information_schema.columns WHERE table_name = 'dead_events';

SELECT 'revenue_state_transitions: ' || COUNT(*) AS phase8b_columns
FROM information_schema.columns WHERE table_name = 'revenue_state_transitions';

-- Constraint counts
SELECT COUNT(*) AS total_check_constraints
FROM information_schema.check_constraints;

-- Index counts
SELECT COUNT(*) AS total_indexes
FROM pg_indexes
WHERE schemaname = 'public';

\o
```

---

## Validation Complete Criteria

All phases (4-8) are considered COMPLETE when:

1. ✅ All migration files applied successfully
2. ✅ All exit gates passed for each phase
3. ✅ Evidence documented for each phase
4. ✅ Final validation report generated
5. ✅ Schema matches canonical specification (db/schema/canonical_schema.sql)
6. ✅ No unexpected schema drift detected

**Final Sign-Off**

**Lead Validator**: ___________________________  
**Date**: ___________________________  
**Status**: ⬜ APPROVED FOR PRODUCTION | ⬜ REQUIRES REMEDIATION  

---

**END OF FORENSIC VALIDATION PLAN**



