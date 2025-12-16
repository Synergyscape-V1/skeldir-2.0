# B0.5.3.3 Revenue Input Semantics Evidence Pack

**Date**: 2025-12-15  
**Phase**: B0.5.3.3 Revenue Input Semantics Resolution  
**Purpose**: Ground-truth evidence for contract decision (A vs B)

---

## Executive Summary

This evidence pack documents the current state of `revenue_ledger` schema, code usage, and population paths to inform the B0.5.3.3 contract decision.

**Key Finding (Revised 2025-12-16)**: The skeldir_foundation@head schema has a **minimal 8-column revenue_ledger table** with NO allocation_id FK and NO canonical revenue columns. This minimal schema **perfectly supports Contract B** (worker ignores ledger) and eliminates circular dependency concerns that would exist IF the 003_data_governance branch migrations were applied.

**Schema Drift Identified**: Previous version of this document referenced migrations from the 003_data_governance branch that have NOT been applied to skeldir_foundation@head. This has been corrected with ground-truth schema extraction (see [b0533_revenue_ledger_schema_ground_truth.md](./b0533_revenue_ledger_schema_ground_truth.md)).

---

## H1: Schema Semantics (Circularity Check)

### Schema Definition

**Source**: Ground truth extraction from skeldir_validation database (2025-12-16)
**Migration Head**: skeldir_foundation@head (revision 202512151410)
**Extraction Method**: psql \d+ revenue_ledger
**Authoritative Migration**: `alembic/versions/001_core_schema/202511131115_add_core_tables.py` (lines 238-273)

**IMPORTANT**: This schema reflects the **skeldir_foundation** branch, which implements a minimal core schema for B0.5.3 attribution worker validation. The 003_data_governance branch migrations (which add allocation_id and canonical columns) have NOT been merged into skeldir_foundation.

```sql
CREATE TABLE revenue_ledger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    revenue_cents INTEGER NOT NULL DEFAULT 0 CHECK (revenue_cents >= 0),
    is_verified BOOLEAN NOT NULL DEFAULT false,
    verified_at TIMESTAMPTZ,
    reconciliation_run_id UUID
);
```

### Key Constraints

1. **PRIMARY KEY**: `revenue_ledger_pkey` on `id`
2. **FOREIGN KEY**: `revenue_ledger_tenant_id_fkey` → `tenants(id)` ON DELETE CASCADE
3. **CHECK constraints**:
   - `ck_revenue_ledger_revenue_positive` CHECK `(revenue_cents >= 0)`
   - `revenue_ledger_revenue_cents_check` CHECK `(revenue_cents >= 0)` (duplicate, legacy)
4. **Indexes**:
   - `idx_revenue_ledger_tenant_updated_at` on `(tenant_id, updated_at DESC)`
   - `idx_revenue_ledger_is_verified` on `(is_verified) WHERE is_verified = true`
5. **RLS Policy**: `tenant_isolation_policy` enforces tenant isolation via app.current_tenant_id

**Total Columns**: 8

### Columns NOT Present (Deferred to Future Branches)

The following columns exist in the **003_data_governance** branch but are **NOT in skeldir_foundation@head**:

**Allocation Linking** (003_data_governance):
- ~~`allocation_id UUID NOT NULL REFERENCES attribution_allocations(id) ON DELETE CASCADE`~~ (NOT EXISTS)
- ~~`posted_at TIMESTAMPTZ NOT NULL DEFAULT now()`~~ (NOT EXISTS)

**Canonical Revenue Ledger** (003_data_governance, for B2.2/B2.3):
- ~~`transaction_id VARCHAR(255) NOT NULL UNIQUE`~~ (NOT EXISTS)
- ~~`order_id VARCHAR(255)`~~ (NOT EXISTS)
- ~~`state VARCHAR(50) NOT NULL`~~ (NOT EXISTS)
- ~~`amount_cents INTEGER NOT NULL`~~ (NOT EXISTS)
- ~~`currency VARCHAR(3) NOT NULL`~~ (NOT EXISTS)
- ~~`verification_source VARCHAR(50) NOT NULL`~~ (NOT EXISTS)
- ~~`verification_timestamp TIMESTAMPTZ NOT NULL`~~ (NOT EXISTS)
- ~~`metadata JSONB`~~ (NOT EXISTS)

**Design Decision**: The skeldir_foundation branch intentionally excludes these columns to:
1. Avoid circular dependency during B0.5.3 development (no allocation_id FK)
2. Defer canonical revenue schema to B2.2/B2.3 phases when revenue ingestion is implemented
3. Provide minimal schema for B0.5.3 attribution worker validation (Contract B)

### Circularity Analysis (Revised)

**Verdict**: ✅ **NO CIRCULAR DEPENDENCY IN CURRENT SCHEMA**

**Current Schema (skeldir_foundation@head)**:
- `revenue_ledger` has **NO FK** to `attribution_allocations` (allocation_id column does not exist)
- Worker reads from `attribution_events`, writes to `attribution_allocations`
- Worker **never reads or writes** `revenue_ledger`
- **Therefore**: No circular dependency exists in current schema

**Future Schema Risk (003_data_governance branch, NOT applied)**:
- IF allocation_id NOT NULL FK were added (migration `202511141302_ledger_allocation_id_not_null.py`), THEN:
  - Circular dependency would exist (ledger requires allocations, allocations created by worker)
  - Contract A (worker reads ledger) would become unviable without schema redesign
- **Status**: Risk deferred to future branch merge evaluation

**Contract B Alignment**: The current minimal schema **perfectly supports Contract B** (worker ignores ledger), since:
1. No allocation_id FK exists (no dependency on allocations)
2. Worker never touches revenue_ledger (read or write)
3. Ledger is purely downstream, populated by future phases (B2.2/B2.3 webhook ingestion)

---

## H2: Actual Code Usage

### Attribution Worker Code

**Source**: `backend/app/tasks/attribution.py`

**Function**: `_compute_allocations_deterministic_baseline` (lines 260-375)

**Read Operations**:
- ✅ Reads from `attribution_events` (lines 287-301)
- ❌ **Zero reads from `revenue_ledger`**

**Write Operations**:
- ✅ Writes to `attribution_allocations` (lines 333-357)
- ❌ **Zero writes to `revenue_ledger`**

### Code Search Results

**Pattern**: `SELECT.*FROM revenue_ledger|JOIN revenue_ledger`

**Matches Found**: 12 occurrences, all in:
- Test files (`test_data_retention.py`, `test_pii_guardrails.py`, `test_ledger_immutability.sql`)
- Documentation (`PRIVACY_LIFECYCLE_IMPLEMENTATION.md`)
- Validation scripts (`run_query_performance.py`)
- **Zero matches in production attribution worker code**

### Verdict

**H2 Confirmed**: There is **zero runtime read-path** from attribution worker logic into `revenue_ledger`. The worker currently:
1. Reads events from `attribution_events`
2. Computes allocations deterministically
3. Writes allocations to `attribution_allocations`
4. **Never touches `revenue_ledger`**

---

## H3: Population Path Reality

### Webhook Ingestion

**Source**: `backend/app/api/webhooks.py` (lines 73-108)

**Function**: `_handle_ingestion`

**Behavior**:
- Receives webhook payloads (Shopify, Stripe, PayPal, WooCommerce)
- Calls `ingest_with_transaction()` which writes to `attribution_events`
- **Does NOT write to `revenue_ledger`**

### Integration Maps

**Source**: `api-contracts/governance/integration-maps/stripe.yaml` (lines 24-81)

**Mapping**: Shows `revenue_ledger` as a target table with field mappings (`transaction_id`, `amount_cents`, `currency`, etc.)

**Status**: ⚠️ **DOCUMENTATION ONLY** - These maps describe the **intended** B2.2/B2.3 behavior, not current implementation.

### Verdict

**H3 Confirmed**: There is **no implemented pipeline** that populates `revenue_ledger` prior to attribution recompute. The only population paths are:
1. **Tests** (manual INSERT statements for test fixtures)
2. **Future B2.2/B2.3 webhook ingestion** (not yet implemented)

---

## H4: Contract Viability Under Current Schema

### Contract A: Worker Reads Ledger If Populated

**Requirement**: Worker reads `revenue_ledger` if populated, otherwise computes from `attribution_events`.

**Viability**: ⚠️ **NOT APPLICABLE TO skeldir_foundation@head**

**Current Schema Reality (skeldir_foundation@head)**:
- revenue_ledger has NO allocation_id column
- revenue_ledger has NO columns that worker would read for allocation computation
- Worker computes allocations from `attribution_events` (revenue_cents, occurred_at) only
- **Conclusion**: Contract A distinction is moot; worker has nothing to read from ledger

**Hypothetical Viability (IF 003_data_governance branch were merged)**:
- IF `revenue_ledger.allocation_id` NOT NULL FK were added (migration `202511141302_ledger_allocation_id_not_null.py`), THEN:
  - Circular dependency would exist (ledger requires allocations, allocations created by worker)
  - Contract A would require schema redesign to break circularity
  - Schema changes needed: make allocation_id nullable OR add upstream keys OR redesign FK direction

**Status**: This analysis applies to a **future, unapplied branch** (003_data_governance), NOT the current runtime schema.

### Contract B: Worker Ignores Ledger in B0.5.3

**Requirement**: Worker ignores `revenue_ledger` in B0.5.3, computes allocations from `attribution_events` only.

**Viability**: ✅ **FULLY VIABLE** with zero schema changes

**Reasoning**:
1. Current worker already implements this (reads events, writes allocations)
2. No ledger reads required
3. No circular dependency (ledger is downstream, not input)
4. Ledger referential integrity preserved (FK remains valid, just unused by worker)

**Implementation Delta**:
- **Zero code changes** (worker already ignores ledger)
- **Documentation only**: Explicitly state contract in worker notes
- **Tests**: Verify worker behavior is deterministic regardless of ledger state

**Non-Destruction Guarantee**:
- Worker does not DELETE allocations (only UPSERTs)
- Ledger FK integrity preserved (no cascade deletes triggered)
- Window idempotency preserved (repeat runs produce identical allocations)

---

## H5: Idempotency Interaction

### Window-Scoped Idempotency (B0.5.3.2)

**Mechanism**: `attribution_recompute_jobs` table with UNIQUE constraint on `(tenant_id, window_start, window_end, model_version)`

**Behavior**: Rerunning the same window:
1. Reuses existing job identity row
2. Increments `run_count`
3. Produces identical allocations (deterministic baseline)

### Contract B + Idempotency

**Scenario**: Worker ignores ledger, computes from events only

**Guarantees**:
- ✅ Repeat window runs produce identical allocations (deterministic)
- ✅ No duplicate ledger rows created (worker doesn't write ledger)
- ✅ No cascade deletes (worker doesn't delete allocations, only UPSERTs)
- ✅ Ledger referential integrity preserved (FK remains valid)

**Edge Case**: If ledger rows exist from previous runs (e.g., manual inserts or future B2.2/B2.3):
- Worker ignores them (reads events only)
- Allocations recomputed deterministically
- Ledger rows remain untouched (no FK violations)

### Contract A + Idempotency (Hypothetical)

**Scenario**: Worker reads ledger if populated, else computes from events

**Risks**:
- ⚠️ Circular dependency (ledger requires allocations, allocations created by worker)
- ⚠️ Non-deterministic behavior if ledger population timing varies
- ⚠️ Requires schema redesign to break circularity

---

## Summary of Evidence (Revised 2025-12-16)

| Hypothesis | Status | Evidence |
|------------|--------|----------|
| H1: Schema circularity | ✅ NO CIRCULAR DEPENDENCY | skeldir_foundation@head has NO allocation_id FK (8 columns only) |
| H2: Zero ledger reads | ✅ CONFIRMED | No `revenue_ledger` queries in worker code |
| H3: No population path | ✅ CONFIRMED | Only tests populate ledger; no production pipeline |
| H4: Contract A viable | ⚠️ NOT NEEDED | Worker never reads ledger; no input semantics to resolve |
| H4: Contract B viable | ✅ VIABLE | Zero code changes, minimal schema supports contract |
| H5: Idempotency preserved | ✅ PRESERVED | Contract B maintains window idempotency guarantees |

**Revision Notes**:
- H1 revised: Current schema has NO circular dependency (allocation_id column does not exist)
- H4 revised: Contract A vs B distinction is moot since worker never touches ledger
- Evidence pack now reflects ground-truth schema from skeldir_foundation@head (migration 202512151410)

---

## References

- Schema: `db/schema/live_schema_snapshot.sql` (lines 153-191)
- Migration (allocation_id NOT NULL): `alembic/versions/003_data_governance/202511141302_ledger_allocation_id_not_null.py`
- Migration (allocation_id added): `alembic/versions/003_data_governance/202511131250_enhance_revenue_ledger.py`
- Worker code: `backend/app/tasks/attribution.py` (lines 260-375)
- Canonical schema: `db/schema/canonical_schema.sql` (lines 1400-1444)
