# Immutability Policy for Attribution Events

**Document Version**: 1.0  
**Date**: 2025-11-13  
**Purpose**: Define immutability policy for attribution_events table

---

## Policy Statement

**`attribution_events` rows are immutable** - once an event is created, it cannot be updated or deleted by application roles. Events are facts and must remain append-only. Corrections must be made via new events (linked via `correlation_id` or correction flag), not in-place edits.

---

## Rationale

Attribution events represent **immutable facts** about revenue-generating events. Immutability ensures:

1. **Audit Trail Integrity**: Historical events cannot be modified, preserving complete audit trail
2. **Idempotency Preservation**: Idempotency constraints become meaningless if events can be modified or deleted
3. **Reconciliation Accuracy**: Allocation and ledger state can be reconciled against immutable event history
4. **Deterministic Attribution**: Immutability supports deterministic, replayable attribution calculations
5. **Regulatory Compliance**: Event logs must be immutable for regulatory compliance and dispute resolution

**Source-of-Truth Principles**:
- "Append-only event stream" (from backend architecture)
- "Deterministic, replayable attribution" (from B0.3 objective)

---

## Allowed Operations

**INSERT**: New events that pass idempotency & validation checks
- Events must pass idempotency constraints (UNIQUE on `tenant_id, external_event_id` or `tenant_id, correlation_id`)
- Events must pass validation checks (e.g., `revenue_cents >= 0`)
- Events must have valid `tenant_id` (FK to `tenants` table)

**SELECT**: Read access for all application roles
- `app_rw`: SELECT allowed (for normal operations)
- `app_ro`: SELECT allowed (for reporting and analytics)

---

## Disallowed Operations

**UPDATE**: Not allowed for application roles (`app_rw`, `app_ro`)
- Events cannot be modified in place
- Corrections must be made via new events (see Correction Model below)

**DELETE**: Not allowed for application roles (`app_rw`, `app_ro`)
- Events cannot be deleted
- Historical events must be preserved for audit trail

---

## Correction Model

Corrections must be represented as **new events**, not in-place edits. Two patterns are supported:

### Pattern 1: Correction Events (Recommended)

Create a new event linked to the original via `correlation_id`:

```sql
-- Original (incorrect) event
INSERT INTO attribution_events (tenant_id, occurred_at, revenue_cents, correlation_id, raw_payload)
VALUES ('...', '2025-11-13 10:00:00', 10000, 'corr-123', '{"order_id": "12345"}');

-- Correction event (linked via correlation_id)
INSERT INTO attribution_events (tenant_id, occurred_at, revenue_cents, correlation_id, raw_payload)
VALUES ('...', '2025-11-13 10:05:00', -500, 'corr-123', '{"order_id": "12345", "correction": true, "original_event_id": "evt-123"}');

-- Net result: 10000 - 500 = 9500 (corrected amount)
```

**Benefits**:
- Preserves audit trail (both original and correction events)
- Maintains idempotency (each event is idempotent)
- Enables reconciliation (corrections are visible in event history)

### Pattern 2: Correction Flag (Alternative)

Create a new event with a correction flag in `raw_payload`:

```sql
-- Correction event with flag
INSERT INTO attribution_events (tenant_id, occurred_at, revenue_cents, correlation_id, raw_payload)
VALUES ('...', '2025-11-13 10:05:00', -500, 'corr-123', '{"correction": true, "original_event_id": "evt-123", "reason": "Price adjustment"}');
```

**Benefits**:
- Explicit correction flag for easier identification
- Can include correction reason in `raw_payload`

---

## Enforcement Mechanisms

### Database-Level Enforcement

**GRANT Policy** (Phase 1.3):
- `app_rw` role: `SELECT`, `INSERT` only (no `UPDATE` or `DELETE`)
- `app_ro` role: `SELECT` only
- `migration_owner` role: Full access (for emergency repairs only)

**Guard Trigger** (Phase 1.4):
- Function: `fn_events_prevent_mutation()`
- Trigger: `trg_events_prevent_mutation` (BEFORE UPDATE OR DELETE)
- Behavior: Raises exception for UPDATE/DELETE attempts (except `migration_owner`)
- Rationale: Defense-in-depth beyond GRANTs

### Application-Level Enforcement

**Code Review**: Application code must not attempt UPDATE/DELETE on `attribution_events`
- PR checklist enforces append-only verification (Phase 1.5)
- Code review must verify no UPDATE/DELETE operations

**PR Checklist**: Events Append-Only Verification section (Phase 1.5)
- Verifies `app_rw` has no UPDATE/DELETE on `attribution_events`
- Verifies guard trigger present (if implemented)
- Verifies any migration touching `attribution_events` preserves append-only GRANTs
- Verifies trigger not removed/weakened without ADR

---

## Exceptions

**Emergency Repairs** (via `migration_owner` only):
- **Condition**: Data corruption requiring in-place correction
- **Process**:
  1. Admin reviews incorrect event
  2. Admin creates correction event (additive) via normal INSERT
  3. If in-place correction absolutely required, use `migration_owner` role
  4. Admin documents correction reason and audit trail
  5. Correction must be approved by Backend Lead + Product Owner
- **Audit Trail**: All emergency repairs must be logged and auditable

**No Other Exceptions**: Immutability is absolute for application roles. There are no other exceptions to this policy.

---

## Migration Impact

**Existing Data**: If `attribution_events` contains existing data, immutability policy applies retroactively. Existing rows cannot be updated by application roles.

**Future Migrations**: Any migration that attempts to UPDATE `attribution_events` must be reviewed and approved by Backend Lead + Product Owner. Migrations that modify GRANTs must preserve append-only semantics.

**Table COMMENT Update**: Table COMMENT must explicitly state append-only semantics:
> "Stores attribution events for revenue tracking. Purpose: Event ingestion and attribution calculations. Data class: Non-PII (PII stripped from raw_payload). Ownership: Attribution service. RLS enabled for tenant isolation. **Append-only: No UPDATE/DELETE for app roles; corrections via new events only.**"

---

## Cross-References

- **Table**: `attribution_events`
- **Migration**: `alembic/versions/202511131115_add_core_tables.py:98-152`
- **GRANT Policy**: See `db/docs/ROLES_AND_GRANTS.md` and `B0.3_IMPLEMENTATION_COMPLETE.md` (Phase 1.3)
- **Guard Trigger**: See `B0.3_IMPLEMENTATION_COMPLETE.md` (Phase 1.4)
- **PR Checklist**: See `.github/PULL_REQUEST_TEMPLATE/schema-migration.md` (Events Append-Only Verification section)
- **Test Specification**: See `db/tests/test_events_append_only.sql`

---

**Policy Status**: ✅ **DEFINED** (Phase 1.2 complete)




