# Audit Trail Deletion Semantics

**Document Version**: 1.0  
**Date**: 2025-11-16  
**Purpose**: Define precise deletion semantics for `attribution_events` and behavior of `attribution_allocations` when events are deleted

---

## Policy Statement (Gate 1.2 Evidence)

This document establishes the canonical deletion semantics for the `attribution_events` table and the resulting behavior for `attribution_allocations`. These semantics are enforced at the database schema level via the `event_id` foreign key constraint.

---

## Section 1: Event Deletion Paths

### 1.1 Normal Operations (Application Roles)

**Policy**: Events are **immutable** and **CANNOT** be deleted by application roles.

**Enforcement Mechanisms**:
1. **GRANT Policy**: `app_rw` role has NO DELETE privilege on `attribution_events`
   - Source: `alembic/versions/202511141200_revoke_events_update_delete.py` line 53
   - Command: `REVOKE UPDATE, DELETE ON TABLE attribution_events FROM app_rw`
2. **Guard Trigger**: `trg_events_prevent_mutation` blocks DELETE attempts
   - Source: `alembic/versions/202511141201_add_events_guard_trigger.py`
   - Behavior: Raises exception for DELETE (except `migration_owner` role)

**Rationale**: 
- Events are immutable facts (per `db/docs/EVENTS_IMMUTABILITY_POLICY.md`)
- Corrections must be made via new events (append-only log)
- Idempotency and audit trail require immutability

**Expected Frequency**: NEVER (enforcement prevents it)

### 1.2 GDPR / Privacy Compliance (Tenant-Level)

**Policy**: Tenant deletion triggers complete data erasure via CASCADE.

**Mechanism**: 
```sql
-- Tenant FK with CASCADE (CORRECT)
tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE
```

**Cascade Chain**:
```
DELETE FROM tenants WHERE id = '...'
  ↓ CASCADE
attribution_events (all tenant events deleted)
  ↓ CASCADE (current) → SET NULL (after fix)
attribution_allocations (behavior changes per fix)
```

**Behavior BEFORE Fix** (ON DELETE CASCADE):
- Tenant deletion → Events deleted → **Allocations deleted** (audit trail lost)

**Behavior AFTER Fix** (ON DELETE SET NULL):
- Tenant deletion → Events deleted → **Allocations preserved** with `event_id = NULL`
- **BUT**: Allocations will ALSO be deleted via their own `tenant_id` FK CASCADE
- **Net Result**: Tenant deletion still achieves complete erasure (GDPR compliant)

**Clarification**: The `event_id` FK change to SET NULL does NOT affect GDPR deletion:
- Both `attribution_events` and `attribution_allocations` have `tenant_id` FK with CASCADE
- Deleting tenant deletes BOTH tables independently
- The `event_id` SET NULL only matters when events are deleted INDIVIDUALLY (rare)

### 1.3 Maintenance Operations (Administrative)

**Policy**: Only `migration_owner` role can delete individual events for emergency repairs.

**Use Cases**:
- Data corruption requiring removal of specific events
- Test data cleanup in non-production environments
- Emergency incident response

**Authorization**: Requires approval from:
- Backend Lead
- Product Owner (for production)

**Allocation Behavior** (after FK fix):
- Event deleted → Allocations **survive** with `event_id = NULL`
- Allocations remain in financial audit trail
- Reports show "event removed" or "context unavailable"

**Expected Frequency**: RARE (< 1 per month, primarily in dev/staging)

**Audit Requirement**: All maintenance deletes must be logged and documented

---

## Section 2: Meaning of `event_id = NULL` (Gate 1.3 Evidence)

### 2.1 Semantic Definition

**When `event_id` is NULL**:
- The allocation is **financially valid** and **must be included** in all revenue totals
- The underlying event that triggered this allocation no longer exists (deleted or removed)
- The event context (channel, timestamp, session) is **no longer available** for explanation

**Analogy**: 
- The allocation is a "paid invoice" (must count toward revenue)
- The event is the "purchase order" (provides context, but may be purged)
- We keep the invoice even if we shred the purchase order

### 2.2 Reporting Semantics

**Financial Totals**: 
- **MUST** include allocations with `event_id = NULL`
- Revenue accounting must be complete regardless of event existence

**Attribution Explanation**:
- **CAN** show "Event removed" or "Details unavailable" for UI
- **CANNOT** fetch event details (event row deleted)
- **CAN** still show allocation-level metadata (channel, model, confidence)

**Example Report**:
```
Channel: google_search_paid
Allocated Revenue: $45.67
Confidence: 0.85
Event Details: [Removed for privacy/maintenance]
```

### 2.3 Validation Semantics

**Sum-Equality Validation**:
- **CANNOT** validate allocations with `event_id = NULL` (no event revenue to compare)
- Validation status: `is_balanced = NULL`, `drift_cents = NULL`
- These allocations are **excluded** from validation but **included** in totals

**Reconciliation**:
- Allocations with `event_id = NULL` are flagged as "unverifiable"
- Reconciliation reports must account for unverifiable allocations
- Threshold: If > 5% of allocations are unverifiable, raise alert

---

## Section 3: Join Semantics (Gate 1.3 Evidence)

### 3.1 Required Join Type: LEFT JOIN

**Policy**: All queries joining `attribution_allocations` to `attribution_events` **MUST use LEFT JOIN**.

**Rationale**:
- `event_id` is nullable after FK fix
- INNER JOIN would exclude allocations with `event_id = NULL`
- Financial totals would be **understated** (incorrect)

**Correct Pattern**:
```sql
SELECT 
    aa.id,
    aa.allocated_revenue_cents,
    e.event_timestamp,  -- May be NULL
    e.channel           -- May be NULL
FROM attribution_allocations aa
LEFT JOIN attribution_events e ON aa.event_id = e.id  -- ✅ CORRECT
WHERE aa.tenant_id = '...'
```

**Incorrect Pattern**:
```sql
-- ❌ WRONG: Excludes allocations with event_id = NULL
FROM attribution_allocations aa
INNER JOIN attribution_events e ON aa.event_id = e.id
```

### 3.2 NULL Handling in Queries

**Event Fields May Be NULL**:
```sql
SELECT 
    aa.allocated_revenue_cents,
    COALESCE(e.event_timestamp, 'Unknown') AS event_timestamp,
    COALESCE(e.channel, aa.channel_code) AS channel  -- Fallback to allocation's channel
FROM attribution_allocations aa
LEFT JOIN attribution_events e ON aa.event_id = e.id
```

**Aggregation Queries**:
```sql
-- Revenue totals (allocations with NULL event_id MUST be included)
SELECT 
    aa.tenant_id,
    SUM(aa.allocated_revenue_cents) AS total_revenue,  -- ✅ Includes NULL event_id
    COUNT(aa.event_id) AS events_with_context,         -- Counts non-NULL event_id
    COUNT(*) - COUNT(aa.event_id) AS events_removed    -- Counts NULL event_id
FROM attribution_allocations aa
GROUP BY aa.tenant_id
```

### 3.3 Materialized View Pattern

**Standard Pattern** (after Phase 3 fix):
```sql
CREATE MATERIALIZED VIEW mv_allocation_summary AS
SELECT 
    aa.tenant_id,
    aa.event_id,  -- May be NULL
    aa.model_version,
    SUM(aa.allocated_revenue_cents) AS total_allocated_cents,
    e.revenue_cents AS event_revenue_cents,  -- NULL when event deleted
    CASE 
        WHEN e.revenue_cents IS NULL THEN NULL  -- Cannot validate
        ELSE (SUM(aa.allocated_revenue_cents) = e.revenue_cents)
    END AS is_balanced,
    CASE 
        WHEN e.revenue_cents IS NULL THEN NULL
        ELSE ABS(SUM(aa.allocated_revenue_cents) - e.revenue_cents)
    END AS drift_cents
FROM attribution_allocations aa
LEFT JOIN attribution_events e ON aa.event_id = e.id  -- ✅ LEFT JOIN
GROUP BY aa.tenant_id, aa.event_id, aa.model_version, e.revenue_cents;
```

---

## Section 4: Event Deletion Protocol

### 4.1 Decision Tree

```
Event needs to be removed?
│
├─ Is this tenant-level GDPR deletion?
│  └─ YES → DELETE FROM tenants WHERE id = '...'
│           (CASCADE handles everything)
│
├─ Is this individual event for privacy?
│  └─ YES → DO NOT DELETE event
│           → Instead: Anonymize PII fields (if any)
│           → Set flag: raw_payload = '{"deleted": true}'
│           → Reason: No PII in events per privacy policy
│
└─ Is this emergency maintenance?
   └─ YES → Requires approval (Backend Lead + Product Owner)
           → Execute as migration_owner:
              DELETE FROM attribution_events WHERE id = '...'
           → Result: Allocations survive with event_id = NULL
           → Action: Document in incident log
```

### 4.2 GDPR Right-to-Erasure

**Scope**: Tenant-level deletion only
**Command**: `DELETE FROM tenants WHERE id = '{tenant_id}'`
**Effect**: Complete data erasure (events + allocations + all tenant data)
**Compliance**: GDPR Article 17, CCPA

**Individual Event GDPR**: NOT APPLICABLE
- Events contain NO PII (per `PRIVACY-NOTES.md`)
- `raw_payload` is pre-stripped of PII by B0.4 ingestion
- No individual event deletion needed for privacy

### 4.3 Maintenance Deletion Procedure

**Prerequisites**:
1. Identify event(s) requiring deletion
2. Document business justification
3. Obtain approval from Backend Lead + Product Owner (production only)
4. Verify allocations exist and will be preserved

**Execution** (as `migration_owner`):
```sql
-- Step 1: Record allocation count before deletion
SELECT COUNT(*) FROM attribution_allocations WHERE event_id = '{event_id}';
-- Record this count: ________

-- Step 2: Execute deletion
DELETE FROM attribution_events WHERE id = '{event_id}';

-- Step 3: Verify allocations preserved with NULL event_id
SELECT COUNT(*) FROM attribution_allocations WHERE id IN (
    SELECT id FROM attribution_allocations WHERE event_id IS NULL
);
-- Verify count matches Step 1

-- Step 4: Document in audit log
INSERT INTO maintenance_log (action, table_name, record_id, justification, performed_by)
VALUES ('DELETE', 'attribution_events', '{event_id}', '{reason}', current_user);
```

**Post-Deletion Verification**:
- Allocations exist: `SELECT COUNT(*) FROM attribution_allocations WHERE event_id IS NULL AND tenant_id = '...'`
- Financial totals unchanged: Compare pre/post deletion revenue sums
- Materialized view refreshes: `REFRESH MATERIALIZED VIEW CONCURRENTLY mv_allocation_summary;`

---

## Section 5: Allocation Lifecycle Examples

### Example 1: Normal Lifecycle (Event Never Deleted)

```
T0: Event created
    attribution_events: { id: 'evt-1', revenue_cents: 10000, ... }

T1: Attribution model runs
    attribution_allocations: [
        { event_id: 'evt-1', channel: 'google', allocated_revenue_cents: 6000 },
        { event_id: 'evt-1', channel: 'facebook', allocated_revenue_cents: 4000 }
    ]

T2+: Allocations remain linked to event
    event_id: 'evt-1' (populated)
    Reporting: Full event context available
```

### Example 2: Event Deleted (Maintenance)

```
T0: Event created (same as Example 1)

T1: Attribution model runs (same as Example 1)

T2: Event deleted by migration_owner
    DELETE FROM attribution_events WHERE id = 'evt-1';

T3: Allocations survive with NULL event_id
    attribution_allocations: [
        { event_id: NULL, channel: 'google', allocated_revenue_cents: 6000 },
        { event_id: NULL, channel: 'facebook', allocated_revenue_cents: 4000 }
    ]
    
T4: Reporting shows "event removed"
    Revenue Total: $100.00 (correct, includes allocations)
    Event Context: "Details unavailable (event removed)"
```

### Example 3: Tenant Deleted (GDPR)

```
T0: Event created (same as Example 1)

T1: Attribution model runs (same as Example 1)

T2: Tenant deleted
    DELETE FROM tenants WHERE id = 'tenant-1';
    
    CASCADE chain:
    1. attribution_events deleted (tenant_id FK CASCADE)
    2. attribution_allocations deleted (tenant_id FK CASCADE)
    
    Note: event_id FK SET NULL does NOT fire because:
    - Allocations are deleted via their own tenant_id FK
    - Event deletion happens simultaneously, not sequentially

T3: Complete erasure
    attribution_events: [] (all tenant events gone)
    attribution_allocations: [] (all tenant allocations gone)
    Compliance: GDPR Article 17 satisfied
```

---

## Section 6: Exit Gate Verification

### Gate 1.2: Deletion Protocol Defined ✅

**Evidence**: 
- Section 1: All deletion paths documented (normal, GDPR, maintenance)
- Section 4: Decision tree and procedures provided
- Authorization requirements specified

### Gate 1.3: LEFT JOIN Requirement Specified ✅

**Evidence**:
- Section 3.1: LEFT JOIN policy explicitly stated
- Section 3.2: NULL handling patterns provided
- Section 3.3: Materialized view pattern with LEFT JOIN

---

## Conclusion

This document provides complete deletion semantics for the audit trail FK realignment. All deletion paths are documented, `event_id = NULL` semantics are defined, and LEFT JOIN requirements are specified.

**Integration**: This document complements `AUDIT_TRAIL_FK_IMPACT_ANALYSIS.md` and completes Phase 1 requirements.

**Phase 1 Status**: ✅ COMPLETE (all exit gates passed)

**Next Phase**: Proceed to Phase 2 (Schema Migration - FK Realignment)



