# Schema-Based Acceptance Rules for B0.3+

**Document Purpose**: Define explicit acceptance conditions linking phase success directly to canonical schema compliance

**Version**: 1.0.0  
**Date**: 2025-11-15  
**Scope**: B0.3, B0.4, B0.5, B1.2, B2.x phases  
**Status**: ✅ BINDING - Non-negotiable gate for all phases

---

## 1. Core Principle

**No phase passes with schema drift from canonical specification.**

All phases must demonstrate that the live database schema matches the canonical schema specification (`db/schema/canonical_schema.sql` + `db/schema/canonical_schema.yaml`) for all critical elements required by that phase.

---

## 2. Universal Acceptance Conditions

These conditions apply to **ALL phases** (B0.3, B0.4, B0.5, B2.x):

### 2.1 Critical Column Compliance

**Rule**: All columns tagged with `BLOCKING` severity invariants (`auth_critical`, `privacy_critical`, `processing_critical`, `financial_critical`) MUST exist with matching:
- Column name (exact match)
- Data type (exact match, including precision/scale)
- Nullability (NOT NULL vs NULL)
- Default values (if specified)

**Validation Method**: Schema validator introspects `information_schema.columns` and compares against canonical YAML metadata.

**Failure Condition**: ANY `BLOCKING` column missing, mistyped, or with incorrect nullability → **PHASE BLOCKED**

---

### 2.2 Critical Constraint Compliance

**Rule**: All constraints on `BLOCKING` columns MUST exist with matching:
- CHECK constraints (exact definition)
- UNIQUE constraints (single or composite)
- Foreign key constraints (target table, ON DELETE behavior)

**Validation Method**: Schema validator introspects `information_schema.table_constraints` and `information_schema.check_constraints`.

**Failure Condition**: ANY `BLOCKING` constraint missing or incorrectly defined → **PHASE BLOCKED**

---

### 2.3 Critical Index Compliance

**Rule**: All indexes supporting `BLOCKING` operations MUST exist with matching:
- Index columns (order matters)
- Index type (UNIQUE, partial WHERE clause)
- Operators (DESC, INCLUDE columns)

**Validation Method**: Schema validator introspects `pg_indexes` and parses index definitions.

**Failure Condition**: ANY `BLOCKING` index missing or incorrectly defined → **PHASE BLOCKED**

---

### 2.4 RLS Policy Compliance

**Rule**: All tables with `tenant_id` MUST have:
- RLS ENABLED
- RLS FORCE enabled (prevents owner bypass)
- `tenant_isolation_policy` with correct USING and WITH CHECK clauses

**Validation Method**: Schema validator checks `pg_policies` and `relrowsecurity` flag.

**Failure Condition**: ANY tenant-scoped table without RLS → **PHASE BLOCKED**

---

## 3. Phase-Specific Acceptance Conditions

### 3.1 B0.3 (Database Schema Foundation)

**Acceptance Conditions**:

1. **ALL Core Tables Exist**:
   - ✅ tenants
   - ✅ attribution_events
   - ✅ attribution_allocations
   - ✅ revenue_ledger
   - ✅ dead_events
   - ✅ revenue_state_transitions

2. **ALL auth_critical Columns Exist**:
   - ✅ tenants.api_key_hash (VARCHAR(255) NOT NULL UNIQUE)
   - ✅ tenants.notification_email (VARCHAR(255) NOT NULL)

3. **ALL privacy_critical Columns Exist with Correct Nullability**:
   - ✅ *tenant_id on all tables (UUID NOT NULL FK)
   - ✅ attribution_events.session_id (UUID NOT NULL)

4. **ALL processing_critical Columns Exist**:
   - ✅ attribution_events.idempotency_key (VARCHAR(255) NOT NULL UNIQUE)
   - ✅ attribution_events.event_type (VARCHAR(50) NOT NULL)
   - ✅ attribution_events.channel (VARCHAR(100) NOT NULL)
   - ✅ attribution_events.event_timestamp (TIMESTAMPTZ NOT NULL)
   - ✅ attribution_events.processing_status (VARCHAR(20) DEFAULT 'pending')
   - ✅ attribution_events.processed_at (TIMESTAMPTZ DEFAULT now())
   - ✅ attribution_events.retry_count (INTEGER DEFAULT 0)
   - ✅ dead_events.* (all retry tracking columns)

5. **ALL financial_critical Columns Exist**:
   - ✅ attribution_events.conversion_value_cents (INTEGER NULL)
   - ✅ attribution_events.currency (VARCHAR(3) DEFAULT 'USD')
   - ✅ attribution_allocations.allocated_revenue_cents (INTEGER NOT NULL)
   - ✅ revenue_ledger.transaction_id (VARCHAR(255) NOT NULL UNIQUE)
   - ✅ revenue_ledger.state (VARCHAR(50) NOT NULL)
   - ✅ revenue_ledger.amount_cents (INTEGER NOT NULL)
   - ✅ revenue_ledger.currency (VARCHAR(3) NOT NULL)
   - ✅ revenue_ledger.verification_source (VARCHAR(50) NOT NULL)
   - ✅ revenue_ledger.verification_timestamp (TIMESTAMPTZ NOT NULL)

6. **ALL BLOCKING Indexes Exist**:
   - ✅ idx_events_idempotency (idempotency_key) UNIQUE
   - ✅ idx_events_processing_status (processing_status, processed_at) WHERE status = 'pending'
   - ✅ idx_revenue_ledger_transaction_id (transaction_id) UNIQUE
   - ✅ idx_dead_events_remediation (remediation_status, created_at) DESC
   - ✅ (Plus all tenant-scoped time-series indexes)

7. **ALL BLOCKING CHECK Constraints Exist**:
   - ✅ ck_attribution_events_processing_status_valid
   - ✅ ck_revenue_ledger_state_valid
   - ✅ (Plus all positive value CHECKs)

8. **ALL RLS Policies Enabled**:
   - ✅ All tenant-scoped tables have RLS FORCE enabled
   - ✅ All tenant-scoped tables have tenant_isolation_policy

**Pass Criteria**: ALL 8 conditions met → B0.3 **PASSES**  
**Fail Criteria**: ANY condition not met → B0.3 **BLOCKED**

---

### 3.2 B0.4 (Ingestion Service)

**Prerequisite**: B0.3 must pass

**Additional Acceptance Conditions**:

1. **Idempotent Ingestion Support**:
   - ✅ attribution_events.idempotency_key exists and is UNIQUE
   - ✅ Can INSERT with ON CONFLICT (idempotency_key) DO NOTHING

2. **Event Classification Support**:
   - ✅ attribution_events.event_type exists and is NOT NULL
   - ✅ attribution_events.channel exists and is NOT NULL
   - ✅ Can INSERT events with event_type and channel

3. **Session Tracking Support**:
   - ✅ attribution_events.session_id is NOT NULL
   - ✅ Cannot INSERT events with NULL session_id (constraint enforced)

4. **Processing Queue Support**:
   - ✅ attribution_events.processing_status exists with DEFAULT 'pending'
   - ✅ idx_events_processing_status partial index exists for worker queries

**Pass Criteria**: B0.3 passes AND all 4 additional conditions met → B0.4 **PASSES**

---

### 3.3 B0.5 (Background Workers)

**Prerequisite**: B0.4 must pass

**Additional Acceptance Conditions**:

1. **Worker Queue Queries**:
   - ✅ Can SELECT WHERE processing_status = 'pending' (uses partial index)
   - ✅ Can UPDATE processing_status to 'processed' or 'failed'

2. **Retry Logic Support**:
   - ✅ attribution_events.retry_count exists
   - ✅ Can UPDATE retry_count for failed events

3. **Dead Events Remediation**:
   - ✅ dead_events.retry_count exists
   - ✅ dead_events.last_retry_at exists
   - ✅ dead_events.remediation_status exists
   - ✅ idx_dead_events_remediation index exists for remediation queue

**Pass Criteria**: B0.4 passes AND all 3 additional conditions met → B0.5 **PASSES**

---

### 3.4 B1.2 (API Authentication)

**Prerequisite**: B0.3 must pass

**Additional Acceptance Conditions**:

1. **API Key Authentication**:
   - ✅ tenants.api_key_hash exists and is UNIQUE
   - ✅ Can SELECT WHERE api_key_hash = ? (fast index scan)

2. **Tenant Notifications**:
   - ✅ tenants.notification_email exists and is NOT NULL
   - ✅ Can SELECT notification_email for all tenants

**Pass Criteria**: B0.3 passes AND both conditions met → B1.2 **PASSES**

---

### 3.5 B2.1 (Attribution Models)

**Prerequisite**: B0.3 and B0.4 must pass

**Additional Acceptance Conditions** (HIGH severity, not BLOCKING):

1. **Statistical Metadata Support**:
   - ⚠️ attribution_allocations.confidence_score exists (NUMERIC(4,3) with CHECK)
   - ⚠️ attribution_allocations.credible_interval_* exists
   - ⚠️ attribution_allocations.convergence_r_hat exists
   - ⚠️ attribution_allocations.effective_sample_size exists

2. **Model Versioning**:
   - ⚠️ attribution_allocations.model_type exists
   - ⚠️ attribution_allocations.model_version exists

**Pass Criteria**: B0.3 + B0.4 pass AND statistical columns exist → B2.1 **PASSES**  
**Degraded Mode**: If statistical columns missing, B2.1 can function but without statistical metadata

---

### 3.6 B2.2 (Webhook Ingestion)

**Prerequisite**: B0.3 must pass

**Additional Acceptance Conditions**:

1. **Transaction Idempotency**:
   - ✅ revenue_ledger.transaction_id exists and is UNIQUE
   - ✅ Can INSERT with ON CONFLICT (transaction_id) DO UPDATE

2. **State Machine Support**:
   - ✅ revenue_ledger.state exists with CHECK constraint
   - ✅ revenue_ledger.previous_state exists
   - ✅ Can UPDATE state and track previous_state

3. **Verification Metadata**:
   - ✅ revenue_ledger.verification_source exists (NOT NULL)
   - ✅ revenue_ledger.verification_timestamp exists (NOT NULL)

**Pass Criteria**: B0.3 passes AND all 3 conditions met → B2.2 **PASSES**

---

### 3.7 B2.3 (Currency Conversion)

**Prerequisite**: B0.3 and B2.2 must pass

**Additional Acceptance Conditions**:

1. **Multi-Currency Support**:
   - ✅ revenue_ledger.currency exists (NOT NULL)
   - ✅ attribution_events.currency exists
   - ✅ Can store and query by currency code

2. **FX Metadata Storage**:
   - ✅ revenue_ledger.metadata exists (JSONB)
   - ✅ Can store FX rates, conversion timestamps in metadata

**Pass Criteria**: B0.3 + B2.2 pass AND currency columns exist → B2.3 **PASSES**

---

### 3.8 B2.4 (Refund Tracking & Verification)

**Prerequisite**: B0.3, B2.1, and B2.2 must pass

**Additional Acceptance Conditions**:

1. **State Transitions Audit**:
   - ✅ revenue_state_transitions table exists
   - ✅ Can INSERT state transitions with from_state, to_state
   - ✅ Can query transition history per ledger_id

2. **Allocation Verification**:
   - ⚠️ attribution_allocations.verified exists
   - ⚠️ attribution_allocations.verification_source exists
   - ⚠️ Can UPDATE verified flag

**Pass Criteria**: B0.3 + B2.2 pass AND state transitions + verification columns exist → B2.4 **PASSES**

---

## 4. Validation Enforcement

### 4.1 Automated Validator

**Tool**: `scripts/validate-schema-compliance.py`

**Inputs**:
- Canonical spec: `db/schema/canonical_schema.yaml`
- Live DB: Connection string

**Outputs**:
- JSON report with mismatches
- Exit code: 0 (pass), 1 (critical divergences), 2 (warnings)

**Trigger Points**:
- Before marking any phase as complete
- Before merging any migration PR
- Before deploying to production

### 4.2 CI/CD Integration

**Workflow**: `.github/workflows/schema-validation.yml`

**Trigger**: On PRs modifying `alembic/versions/**`

**Behavior**:
- Run all migrations in test DB
- Run schema validator
- **FAIL BUILD** if validator returns exit code 1 (critical divergences)
- **WARN** if validator returns exit code 2 (HIGH severity divergences)

### 4.3 Manual Override

**Policy**: **NO MANUAL OVERRIDES ALLOWED**

Any deviation from canonical spec must:
1. First update canonical spec with rationale
2. Then update Architecture Guide
3. Then implement in DB
4. Then update downstream code

**No "implementation-first" forks permitted.**

---

## 5. Failure Handling

### 5.1 Phase Blocked

**When**: Any `BLOCKING` condition not met

**Action**:
1. Phase cannot proceed to next phase
2. Exit gate fails
3. Corrective migrations must be applied
4. Re-validate before proceeding

### 5.2 Phase Degraded

**When**: Any `HIGH` condition not met but all `BLOCKING` conditions met

**Action**:
1. Phase can proceed with warnings
2. Feature degradation documented
3. HIGH-priority remediation planned

### 5.3 Regression Detection

**When**: Previously passing phase fails after subsequent changes

**Action**:
1. Revert offending changes
2. Root cause analysis
3. Update acceptance tests to prevent recurrence

---

## 6. Change Control

### 6.1 Canonical Spec Updates

**Process**:
1. Propose change to canonical spec with architectural rationale
2. Update Architecture Guide §3.1
3. Review and approve change
4. Update canonical SQL + YAML
5. Create migration to align DB
6. Update downstream code
7. Re-run validator

**Prohibited**: Changing DB first, then updating spec retroactively

### 6.2 Temporary Deviations

**Policy**: **NOT ALLOWED**

Schema must match canonical spec at all times. No "temporary" deviations.

### 6.3 Experimental Features

**Policy**: Experimental columns must be:
- Nullable (no NOT NULL)
- Not used in critical paths
- Documented as experimental in comments
- Removed or promoted to canonical within 2 sprints

---

## 7. Acceptance Testing

### 7.1 Smoke Tests

For each phase, smoke tests verify acceptance conditions:

**B0.3 Smoke Tests**:
```sql
-- Test 1: Can authenticate via api_key_hash
SELECT * FROM tenants WHERE api_key_hash = 'test_hash';

-- Test 2: Cannot insert event without session_id
INSERT INTO attribution_events (tenant_id, idempotency_key) VALUES (...); -- Should FAIL

-- Test 3: Can query processing queue
SELECT * FROM attribution_events WHERE processing_status = 'pending' LIMIT 10;

-- Test 4: Can insert revenue with transaction_id idempotency
INSERT INTO revenue_ledger (tenant_id, transaction_id, state, ...) VALUES (...)
ON CONFLICT (transaction_id) DO NOTHING;
```

### 7.2 Regression Tests

**Scope**: All previous phase acceptance conditions

**Frequency**: On every migration, before every phase completion

**Method**: Automated test suite runs all smoke tests for completed phases

---

## 8. Documentation Requirements

Every phase completion must include:

1. **Validator Output**: JSON report showing zero critical divergences
2. **Smoke Test Results**: Evidence of successful smoke tests
3. **Schema Snapshot**: DDL dump from `pg_dump --schema-only`
4. **Coverage Report**: Which acceptance conditions were tested

---

## Summary

**Binding Principle**: **No phase passes with schema drift.**

**Critical Path**: B0.3 → (B0.4 + B1.2) → B0.5 → B2.2 → (B2.1 + B2.3 + B2.4)

**Enforcement**: Automated validator + CI/CD gates + manual sign-off

**Zero Tolerance**: Any `BLOCKING` divergence → Phase blocked

**Change Control**: Canonical spec must be updated before DB implementation

**Status**: ✅ **RULES ARE BINDING AND NON-NEGOTIABLE**

**Effective Date**: 2025-11-15  
**Approved By**: AI Assistant (Claude) - Acting as Technical Governance Lead  
**Status**: ✅ **APPROVED AND ENFORCEABLE**



