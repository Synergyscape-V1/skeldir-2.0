# Audit Trail FK Impact Analysis

**Document Version**: 1.0  
**Date**: 2025-11-16  
**Purpose**: Comprehensive impact analysis for changing `attribution_allocations.event_id` FK from `ON DELETE CASCADE` to `ON DELETE SET NULL`

---

## Executive Summary

This document provides a forensic analysis of all code paths, schema elements, and architectural assumptions impacted by changing the `attribution_allocations.event_id` foreign key constraint from `ON DELETE CASCADE` to `ON DELETE SET NULL`. This change is critical for preserving the financial audit trail when attribution events are deleted.

---

## Section 1: Schema Comparison (Gate 1.1 Evidence)

### 1.1 Canonical vs Implemented Schema

**Canonical Specification** (`db/schema/canonical_schema.sql` line 167):
```sql
-- CANONICAL (INTENDED)
event_id UUID REFERENCES attribution_events(id) ON DELETE SET NULL,
-- Nullable: YES
-- ON DELETE: SET NULL
-- Rationale: Preserve allocations for audit trail even when event is deleted
```

**Implemented Schema** (`alembic/versions/202511131115_add_core_tables.py` line 197):
```sql
-- IMPLEMENTED (CURRENT)
event_id uuid NOT NULL REFERENCES attribution_events(id) ON DELETE CASCADE,
-- Nullable: NO (NOT NULL constraint)
-- ON DELETE: CASCADE
-- Impact: Deleting event deletes all allocations, destroying audit trail
```

### 1.2 Schema Discrepancy Summary

| Property | Canonical | Implemented | Impact |
|----------|-----------|-------------|---------|
| Nullability | NULLABLE | NOT NULL | Must alter column to nullable |
| ON DELETE | SET NULL | CASCADE | Must drop and recreate FK constraint |
| Audit Preservation | YES | NO | Current schema destroys audit trail |
| GDPR Compliance | Partial (financial preserved) | Full deletion (no audit) | Risk: Loss of financial history |

---

## Section 2: Code Path Analysis (Gate 1.1 Evidence)

### 2.1 Materialized Views Using `event_id`

**Critical Finding**: 1 materialized view uses INNER JOIN

#### Materialized View: `mv_allocation_summary`
- **File**: `alembic/versions/202511131240_add_sum_equality_validation.py` lines 95-102
- **Current Implementation**:
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
  INNER JOIN attribution_events e ON aa.event_id = e.id  -- ⚠️ ASSUMES NON-NULL
  GROUP BY aa.tenant_id, aa.event_id, aa.model_version, e.revenue_cents;
  ```
- **Assumes Non-Null**: YES (INNER JOIN will exclude rows with `event_id IS NULL`)
- **Impact**: Allocations with NULL `event_id` will be excluded from sum-equality validation
- **Required Change**: Change to `LEFT JOIN`, handle NULL `event_revenue_cents`
- **Priority**: CRITICAL (regression prevention)

### 2.2 Test Scripts Using `event_id`

#### Test: `db/tests/test_sum_equality.sql`
- **Lines Using event_id**: 38, 46, 60, 70, 108, 130, 131
- **Usage Pattern**: `WHERE event_id = '...'` (equality checks)
- **Assumes Non-Null**: YES (all queries assume event_id exists)
- **Impact**: Test will need to handle NULL case scenarios
- **Required Change**: Add test cases for NULL `event_id` behavior

#### Test: `db/tests/test_foreign_keys.sql`
- **Line Using event_id**: 93
- **Usage Pattern**: `WHERE event_id = '...'` (FK validation)
- **Assumes Non-Null**: YES
- **Impact**: Test validates CASCADE behavior, must validate SET NULL instead
- **Required Change**: Update test to verify SET NULL behavior

### 2.3 Schema Specification Files

#### Spec: `db/docs/specs/attribution_allocations_ddl_spec.sql`
- **Line 15**: `event_id uuid NOT NULL REFERENCES attribution_events(id) ON DELETE CASCADE`
- **Status**: Outdated, conflicts with canonical schema
- **Required Change**: Update to match canonical (nullable + SET NULL)

#### Spec: `db/schema/live_schema_snapshot.sql`
- **Line 91**: `event_id UUID NOT NULL REFERENCES attribution_events(id) ON DELETE CASCADE`
- **Status**: Reflects current (incorrect) implementation
- **Required Change**: Will be updated after migration

### 2.4 Indexes Using `event_id`

**Index**: `idx_attribution_allocations_event_id`
- **File**: `alembic/versions/202511131115_add_core_tables.py` line 219
- **Definition**: `CREATE INDEX idx_attribution_allocations_event_id ON attribution_allocations (event_id)`
- **Impact of Nullability**: PostgreSQL B-tree indexes include NULL values, index remains functional
- **Required Change**: NONE (index works with NULL values)

**Index**: `idx_attribution_allocations_tenant_event_model_channel`
- **File**: `db/schema/live_schema_snapshot.sql` line 134
- **Definition**: UNIQUE composite index including `event_id`
- **Impact of Nullability**: NULL values are treated as distinct in UNIQUE indexes
- **Required Change**: NONE (multiple allocations with NULL `event_id` are allowed)

### 2.5 Check Constraints Using `event_id`

**Finding**: No CHECK constraints reference `event_id`

### 2.6 Triggers Using `event_id`

**Finding**: No triggers directly reference `event_id` column

---

## Section 3: Deletion Entry Point Analysis (Gate 1.1 Evidence)

### 3.1 Application-Level Deletion Paths

**Finding**: No application code exists yet (B0.4 ingestion service not implemented)

**Future Consideration**: B0.4 ingestion service MUST NOT implement event deletion endpoints

### 3.2 Database-Level Deletion Controls

#### GRANT Policy
- **File**: `alembic/versions/202511141200_revoke_events_update_delete.py` line 53
- **Policy**: `REVOKE UPDATE, DELETE ON TABLE attribution_events FROM app_rw`
- **Status**: ✅ ACTIVE
- **Effect**: Application role (`app_rw`) CANNOT delete events
- **Verification**: See Phase 4 empirical test

#### Guard Trigger
- **File**: `alembic/versions/202511141201_add_events_guard_trigger.py`
- **Trigger**: `trg_events_prevent_mutation` (BEFORE UPDATE OR DELETE)
- **Function**: `fn_events_prevent_mutation()`
- **Effect**: Raises exception for UPDATE/DELETE attempts (except `migration_owner`)
- **Status**: ✅ ACTIVE (defense-in-depth)
- **Verification**: See Phase 4 empirical test

### 3.3 Administrative Deletion Paths

**Only Path**: `migration_owner` role via direct SQL
- **Use Case**: Emergency data corrections, maintenance operations
- **Frequency**: Rare (should be documented and audited)
- **Protection**: After FK fix, allocations will survive with `event_id = NULL`

### 3.4 GDPR / Privacy Deletion Paths

**Current Approach**: Tenant-level CASCADE deletion
- **Cascade Chain**: `DELETE FROM tenants` → `attribution_events` → `attribution_allocations`
- **Effect**: Complete data erasure (GDPR compliance)
- **Impact of FK Change**: NONE (tenant FK still uses CASCADE as intended)

**Recommended GDPR Path for Events** (not tenant-level):
- **Method**: Anonymize PII fields, do NOT hard-delete row
- **Rationale**: Preserves audit trail while removing personal data
- **Implementation**: Not required for this phase (events have no PII per `EVENTS_IMMUTABILITY_POLICY.md`)

---

## Section 4: Architectural Assumptions Verification

### 4.1 Assumption: Events are Immutable

**Source**: `db/docs/EVENTS_IMMUTABILITY_POLICY.md`
- **Policy**: Events cannot be updated or deleted by application roles
- **Enforcement**: GRANTs (no UPDATE/DELETE) + Guard trigger
- **Status**: ✅ VERIFIED (see Section 3.2)
- **Impact**: Events should never be deleted in normal operations, so FK change is defensive

### 4.2 Assumption: No Soft-Delete Column

**Analysis**: Searched for `deleted_at` column in `attribution_events`
- **Result**: No soft-delete column exists
- **Implication**: Hard deletes are the only deletion mechanism
- **Decision**: Soft-delete NOT required for Phase 2-3 (existing controls sufficient)
- **Rationale**: FK SET NULL provides audit preservation; soft-delete would be redundant

### 4.3 Assumption: Allocations Must Outlive Events

**Source**: Canonical schema and product vision
- **Requirement**: Financial allocations are immutable audit trail
- **Current State**: VIOLATED (CASCADE deletes allocations)
- **Fix**: Change FK to SET NULL (this implementation)

---

## Section 5: Impact Summary (Gate 1.1 Complete)

### 5.1 Files Requiring Changes

| File | Change Type | Priority |
|------|-------------|----------|
| `alembic/versions/YYYYMMDD_realign_allocations_fk.py` | NEW MIGRATION | CRITICAL |
| `alembic/versions/YYYYMMDD_fix_mv_allocation_summary.py` | NEW MIGRATION | CRITICAL |
| `db/docs/specs/attribution_allocations_ddl_spec.sql` | UPDATE SPEC | MEDIUM |
| `db/tests/test_sum_equality.sql` | ADD NULL TEST CASES | MEDIUM |
| `db/tests/test_foreign_keys.sql` | UPDATE FK TEST | MEDIUM |
| `db/tests/test_audit_trail_preservation.sql` | NEW TEST | CRITICAL |

### 5.2 Queries Assuming Non-Null `event_id`

**Total Found**: 1 materialized view, 2 test scripts
- **Critical**: `mv_allocation_summary` (INNER JOIN must become LEFT JOIN)
- **Medium**: Test scripts (need NULL test cases)

### 5.3 Deletion Entry Points

**Application-Level**: NONE (B0.4 not implemented)
**Database-Level**: `migration_owner` only (GRANTs + trigger enforce)
**GDPR**: Tenant-level CASCADE (unaffected by FK change)

---

## Section 6: Risk Assessment

### 6.1 Risks Mitigated by FK Change

1. **Audit Trail Loss**: CASCADE currently destroys financial history when events deleted
2. **Compliance Risk**: Loss of allocation records may violate financial record-keeping requirements
3. **Reconciliation Failure**: Missing allocations break revenue reconciliation

### 6.2 Risks Introduced by FK Change

1. **NULL `event_id` Handling**: Queries must handle NULL case (mitigated by Phase 3)
2. **Validation Degradation**: Sum-equality validation cannot verify NULL `event_id` allocations (acceptable tradeoff)
3. **Reporting Gaps**: Reports may need to explain "event removed" status (acceptable)

### 6.3 Risk Mitigation Plan

- **Phase 2**: Fix FK constraint (eliminate audit trail loss)
- **Phase 3**: Fix INNER JOIN to LEFT JOIN (prevent reporting gaps)
- **Phase 4**: Verify deletion controls (ensure events rarely deleted)
- **Phase 5**: Empirical validation (prove allocations survive)

---

## Section 7: Exit Gate Verification

### Gate 1.1: All Code Paths Identified ✅

**Evidence**: Section 2 provides comprehensive inventory of:
- 1 materialized view (INNER JOIN identified)
- 2 test scripts
- 3 schema specification files
- 2 indexes (verified NULL-compatible)
- 0 check constraints
- 0 triggers directly using `event_id`

### Gate 1.2: Deletion Protocol Defined ✅

**Evidence**: Section 3 + Companion document `AUDIT_TRAIL_DELETION_SEMANTICS.md`

### Gate 1.3: LEFT JOIN Requirement Specified ✅

**Evidence**: Section 2.1 explicitly requires LEFT JOIN for `mv_allocation_summary`

---

## Conclusion

This impact analysis provides complete evidence for Phase 1 exit gates. All code paths using `event_id` have been identified and classified. The critical finding is the `mv_allocation_summary` materialized view using INNER JOIN, which MUST be changed to LEFT JOIN in Phase 3.

**Phase 1 Status**: ✅ COMPLETE (all exit gates passed)

**Next Phase**: Proceed to Phase 2 (Schema Migration - FK Realignment)



