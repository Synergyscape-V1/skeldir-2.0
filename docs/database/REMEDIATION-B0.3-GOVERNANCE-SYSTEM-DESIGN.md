# B0.3 Unified Governance Framework: Schema Safety & Change Control Implementation

**Version:** 1.0.0  
**Date:** 2025-11-17  
**Status:** Implementation Document - Design Phase  
**Synthesis:** Version 1 (Jamie) Governance Framework + Version 2 (Schmidt) Empirical Validation

---

## Executive Summary

This document synthesizes **Version 1 (Jamie)**'s systematic governance philosophy with **Version 2 (Schmidt)**'s empirical validation mechanisms to create a unified governance framework. The framework establishes B0.3 schema foundation as the Single Source of Truth (SSOT) through both declarative governance standards and automated CI enforcement, ensuring schema safety is non-optional before B0.4 ingestion begins.

**Key Synthesis Points:**
- **Governance Definition (V1)** + **Empirical Validation (V2)** at every phase
- **Systematic Taxonomy (V1)** + **Concrete Remediation (V2)** for current drift
- **CI Structural Checks (V1)** + **Functional Enforcement (V2)** via existing scripts
- **Domain Constraints (V1)** + **Handoff Contract (V2)** for B0.4 alignment

**Deliverable**: This single Implementation Document consolidates all governance phases into one cohesive framework.

---

## Table of Contents

1. [Phase 1: Canonical Schema Reconciliation & SSOT Enforcement](#phase-1-canonical-schema-reconciliation--ssot-enforcement)
2. [Phase 2: Migration Authoring Contract & Metadata Standard](#phase-2-migration-authoring-contract--metadata-standard)
3. [Phase 3: CI Schema Drift & Safety Checks (Structure-Level)](#phase-3-ci-schema-drift--safety-checks-structure-level)
4. [Phase 4: Migration Up/Down Safety & Data-Semantic Checks](#phase-4-migration-updown-safety--data-semantic-checks)
5. [Phase 5: Wire B0.3 Outputs as Hard Preconditions for B0.4](#phase-5-wire-b03-outputs-as-hard-preconditions-for-b04)
6. [Phase 6: Aggregate Approval Gate & System Alignment](#phase-6-aggregate-approval-gate--system-alignment)

---

## Phase 1: Canonical Schema Reconciliation & SSOT Enforcement

**Objective**: Eliminate "multiple truths" problem by fixing current drift and building automated CI enforcement to prevent future drift.

**Synthesis**: Combines V1's "Canonical Schema Definition" governance with V2's concrete reconciliation migration and CI automation.

### 1.1 Canonical Schema Definition (V1 Governance)

**Authoritative Schema Sources**:

The B0.3 schema foundation is defined by the following authoritative sources, in precedence order:

1. **Architecture Guide & ADRs** (`docs/architecture/adr/`)
   - Defines conceptual model, naming conventions, security semantics
   - Authority Level: Authoritative (Conceptual Spec)
   - Owner: Backend Schema Steward

2. **Alembic Migration Chain** (`alembic/versions/**`)
   - The only route that constructs a database a process may serve
   - Authority Level: **Authoritative (Construction Authority)**
   - Owner: Migration Author + Reviewer

3. **Canonical Structural Reference** (`db/schema/canonical_schema.sql`)
   - Declarative description of the tables, columns, constraints and RLS the
     migration chain produces; the subject of the drift detector
   - Authority Level: **Structural reference — never a construction route**
   - Owner: Backend Schema Steward
   - Evidence: Git hash + checksum recorded per release

4. **Canonical Schema YAML** (`db/schema/canonical_schema.yaml`)
   - Structured metadata mirror for tooling/tests
   - Authority Level: Structural reference (Metadata Mirror)
   - Owner: Data Platform Partner

5. **B0.3 Implementation Docs** (`docs/database/`)
   - RLS coverage, matviews, privacy/indexing/retention constraints
   - Authority Level: Informational (Supporting)
   - Owner: Assigned document authors

**Precedence Rule**: Architecture Guide & ADRs → Migrations → Canonical SQL → YAML → Docs

> **B2.5-P14 Corrective V correction.** This list previously ranked the canonical
> SQL as the *executable spec* and the migration chain as *derived*, and an
> independent audit read that ordering as licensing the canonical file as a
> supported production construction route. It cannot be one, and the reason is a
> property of the generator rather than of policy: the file is produced by
> `pg_dump --schema-only --no-owner --no-privileges`, so it has no vocabulary for
> grants or ownership, carries no governed seed rows, and leaves
> `alembic_version` empty. Measured on PostgreSQL 15 at head `202609061200`, a
> canonically-bootstrapped database restores the generic API principal's INSERT
> on the B2.8 relations, grants neither dedicated causal authority anything,
> leaves the issuer unable to append durable issuance history, and seeds zero of
> the twenty B2.7 narrative frames — it reconstitutes the defect the corrective
> closes and disables the fix, while matching structurally on every dimension
> (129 functions, 172 triggers). That is exactly what makes it a sound
> *reference* and an unsound *construction*.
>
> The ordering above is now enforced rather than described:
> `backend/app/core/construction_authority.py` refuses an unconstructed database
> at the readiness boundary, and
> `scripts/ci/assert_canonical_construction_authority.py` is merge-blocking and
> proves all four §10.1 conditions on two real universes, with its own negative
> control.

Any divergence between sources requires:
- ADR ID referenced in migration metadata
- Explicit entry in Schema Drift Table (see §1.2)
- Approval from Backend Schema Steward

**Exit Gate Evidence**:
- ✅ This section defines all sources
- ✅ Precedence policy documented
- ✅ Engineer can answer "what is the schema?" without ambiguity

### 1.2 Define Reconciliation Migration (V2 Remediation)

**Reconciliation Migration**: `alembic/versions/003_data_governance/202511171200_reconcile_b03_baseline.py`

**Purpose**: Resolve known drift between canonical schema and migration implementation.

**Known Drift Items Addressed**:

| Drift ID | Object | Canonical Truth | Migration State | Resolution |
|----------|--------|----------------|-----------------|------------|
| SCHEMA-DRIFT-001 | `idx_allocations_channel_performance` | Composite index on `(tenant_id, channel, created_at DESC)` with `INCLUDE (allocated_revenue_cents, confidence_score)` | Legacy single-column indexes; INCLUDE payload absent | ✅ Migration drops legacy variants and creates canonical composite index |
| SCHEMA-DRIFT-002 | `dead_events.remediation_status` | CHECK constraint with values: `('pending', 'in_progress', 'resolved', 'abandoned')` | Migration accepts `'ignored'` instead of `'abandoned'` | ✅ Migration replaces constraint to match canonical enum |

**Migration Verification**:

The reconciliation migration (`202511171200`) performs:

1. **Index Reconciliation**:
   ```sql
   DROP INDEX IF EXISTS idx_allocations_channel_performance;
   CREATE INDEX idx_allocations_channel_performance
   ON attribution_allocations (tenant_id, channel_code, created_at DESC)
   INCLUDE (allocated_revenue_cents, confidence_score);
   ```

2. **Constraint Reconciliation**:
   ```sql
   ALTER TABLE dead_events
   DROP CONSTRAINT IF EXISTS ck_dead_events_remediation_status_valid;
   ALTER TABLE dead_events
   ADD CONSTRAINT ck_dead_events_remediation_status_valid
   CHECK (remediation_status IN ('pending', 'in_progress', 'resolved', 'abandoned'));
   ```

**Validation Commands**:

- **Index Verification**: `psql -c "\di+ idx_allocations_channel_performance"` → expect INCLUDE columns
- **Constraint Verification**: 
  ```sql
  INSERT INTO dead_events (..., remediation_status) VALUES (..., 'abandoned'); -- succeeds
  INSERT INTO dead_events (..., remediation_status) VALUES (..., 'ignored');  -- fails
  ```

**Exit Gate Evidence**:
- ✅ Migration file exists and addresses documented drift
- ✅ Migration covers SCHEMA-DRIFT-001 and SCHEMA-DRIFT-002
- ⚠️ Additional drift items from `db/schema/schema_gap_catalogue.md` may require separate migrations

### 1.3 Define SSOT Enforcement CI Step (V2 + V1)

**CI Workflow**: `.github/workflows/schema-drift-check.yml` (currently commented out; must be activated)

**Implementation Design**:

The CI workflow must execute the following pipeline on any PR modifying `alembic/versions/**` or `db/schema/**`:

1. **Spin up ephemeral PostgreSQL container**
   - Use PostgreSQL 15 image
   - Create test database: `skeldir_test`

2. **Build Implementation Schema**
   - Run `alembic upgrade head` to apply all migrations
   - This creates the "Implementation Schema" from migration chain

3. **Generate Schema Snapshot**
   - Run `pg_dump --schema-only --no-owner --no-privileges` to create `implementation_schema.sql`
   - Normalize output (strip comments, whitespace, deterministic ordering)

4. **Normalize Canonical Schema**
   - Apply same normalization to `db/schema/canonical_schema.sql`
   - Produce `canonical_schema_normalized.sql`

5. **Compare Schemas**
   - Run `diff -u canonical_schema_normalized.sql implementation_schema.sql`
   - **CI step MUST fail if diff returns any differences**

**Normalization Rules**:
- Remove lines starting with `--` (comments)
- Collapse consecutive blank lines
- Preserve uppercase keywords as-is
- Ignore `OWNER TO`/`COMMENT ON` noise
- Order by table + object names for deterministic diffs

**Rationale**: Automated, non-optional gate that proves migrations match canonical spec, preventing future drift.

**Exit Gate Evidence**:
- ⚠️ CI workflow file exists but is commented out; must be activated
- ⚠️ Test run against current `main` branch demonstrates drift detection capability
- ⚠️ CI fails on PR with intentional drift (test case required)

**Activation Steps**:
1. Uncomment workflow in `.github/workflows/schema-drift-check.yml`
2. Test against current `main` branch (should pass if reconciliation migration is merged)
3. Create test PR with intentional drift to verify failure
4. Document test results in this section

---

## Phase 2: Migration Authoring Contract & Metadata Standard

**Objective**: Force every migration to carry machine- and human-readable intent tied to B0.3 invariants.

**Synthesis**: V1's metadata template + V2's linkage to B0.3 domains.

### 2.1 Define Migration Header Metadata Schema (V1)

**Standard Header Template**:

All migration files must include a metadata header (as Python docstring or YAML frontmatter) with the following required fields:

```python
"""
Migration Metadata Template

MIGRATION_ID: <revision_id>
TITLE: <short_description>
CHANGE_TYPE: <Table|Column|Constraint|Index|RLS|Matview|Partition>
RISK_LEVEL: <Low|Medium|High>
AFFECTED_TABLES: [<table1>, <table2>, ...]
TOUCHES_ANALYTICS_SURFACE: <Yes|No>
TOUCHES_RLS: <Yes|No>
TOUCHES_PRIVACY_OR_RETENTION: <Yes|No>
TOUCHES_AUDIT_OR_LEDGER: <Yes|No>
TOUCHES_OLAP_INDEXING: <Yes|No>
RELATED_B0.3_DOC_SECTION: <reference to Implementation Doc section>
ROLLBACK_STRATEGY: <narrative description>
FORWARD_ONLY: <Yes|No> [If Yes, justification required]
"""
```

**Field Definitions**:

- **MIGRATION_ID**: Matches Alembic revision ID (e.g., `202511171200`)
- **TITLE**: Short description (e.g., "Reconcile canonical index alignment")
- **CHANGE_TYPE**: One of: `Table`, `Column`, `Constraint`, `Index`, `RLS`, `Matview`, `Partition`
- **RISK_LEVEL**: 
  - **Low**: Add non-nullable column with default, add index, add matview, add RLS policy consistent with existing contract
  - **Medium**: Add column without default to large table, add FK, add new table used by ingestion
  - **High**: Drop column, drop table, change column type to narrower domain, drop/modify RLS, drop index used by P0 queries, changes affecting privacy/retention constraints
- **AFFECTED_TABLES**: List of table names (e.g., `['attribution_events', 'attribution_allocations']`)
- **TOUCHES_***: Boolean flags indicating which B0.3 domains are affected
- **RELATED_B0.3_DOC_SECTION**: Reference to relevant Implementation Doc (see §2.3)
- **ROLLBACK_STRATEGY**: Narrative describing how downgrade() handles data/schema reversal
- **FORWARD_ONLY**: If `Yes`, must include justification and separate rollback plan

**Example Migration Header**:

```python
"""
Migration Metadata

MIGRATION_ID: 202511171200
TITLE: Reconcile canonical index and constraint alignment
CHANGE_TYPE: Index, Constraint
RISK_LEVEL: Low
AFFECTED_TABLES: [attribution_allocations, dead_events]
TOUCHES_ANALYTICS_SURFACE: Yes
TOUCHES_RLS: No
TOUCHES_PRIVACY_OR_RETENTION: No
TOUCHES_AUDIT_OR_LEDGER: No
TOUCHES_OLAP_INDEXING: Yes
RELATED_B0.3_DOC_SECTION: docs/database/REMEDIATION-B0.3-OLAP-DESIGN.md §Phase 3
ROLLBACK_STRATEGY: Downgrade drops canonical index and restores legacy constraint enum values. Data preserved.
FORWARD_ONLY: No
"""
```

**Exit Gate Evidence**:
- ✅ Template documented in this section
- ✅ Example migration header provided above
- ⚠️ All existing migrations audited for compliance (gap list to be created)

### 2.2 Define Authoring Rules (V1)

**Minimal Migration Authoring Requirements**:

1. **Metadata Completion**: Every migration must fill out the header template (§2.1)
2. **Single-Purpose**: Migrations must be logically "small" and single-purpose (avoid multi-unrelated changes in one migration)
3. **Rollback Strategy**: Must describe rollback strategy—even for forward-only migrations (describe how to mitigate)

**Validation Script Concept**:

A validation script (e.g., `scripts/validate-migration-metadata.py`) should:
- Parse migration file for metadata header
- Verify all required fields are present
- Check that `TOUCHES_*` flags align with actual DDL changes
- Warn if `RISK_LEVEL` seems inconsistent with change type

**Exit Gate Evidence**:
- ✅ Rules documented in this section
- ⚠️ Validation script concept described (implementation pending)

### 2.3 Tie Metadata to B0.3 Domains (V1 + V2)

**Linkage Requirements**:

For any migration where `TOUCHES_* = Yes`, the migration metadata must reference the corresponding B0.3 Implementation Doc section:

| Domain Flag | Required Documentation Reference |
|-------------|--------------------------------|
| `TOUCHES_RLS = Yes` | Reference `docs/database/CHANNEL_GOVERNANCE_AUDITABILITY_IMPLEMENTATION.md` RLS section |
| `TOUCHES_PRIVACY_OR_RETENTION = Yes` | Reference privacy & retention Implementation Doc (`docs/database/pii-controls.md`) |
| `TOUCHES_OLAP_INDEXING = Yes` | Reference OLAP/indexing Implementation Doc (`docs/database/REMEDIATION-B0.3-OLAP-DESIGN.md`) |
| `TOUCHES_AUDIT_OR_LEDGER = Yes` | Reference auditability Implementation Doc (`docs/database/CHANNEL_GOVERNANCE_AUDITABILITY_IMPLEMENTATION.md`) |
| `TOUCHES_ANALYTICS_SURFACE = Yes` | Reference analytics surface documentation and privacy contracts |

**Example**:

If a migration modifies `attribution_events` (Analytics Surface), metadata must reference:
- `Analytics Table Contracts` in the Privacy & Retention doc
- `Query → Index Mapping` in the OLAP doc

**Exit Gate Evidence**:
- ✅ Linkage requirements documented in this section
- ✅ Example provided above

### 2.4 Prohibit Ad-Hoc Changes (V1)

**Explicit Policy**:

Any schema change must be represented as a migration with a complete metadata header. Direct SQL changes in prod/staging/local without migrations are **forbidden by policy**.

**Enforcement**:
- Schema owners must reject any PR that bypasses migration system
- Emergency changes (see `db/schema/CHANGE_CONTROL.md` §4) must still create retroactive migration
- All schema changes must flow through canonical spec first, then to implementation

**Runbook**: See `docs/database/RUNBOOK-MIGRATION-POLICY.md` (created in Phase 2)

**Exit Gate Evidence**:
- ✅ Policy documented in this section
- ✅ Runbook reference provided

---

## Phase 3: CI Schema Drift & Safety Checks (Structure-Level)

**Objective**: Make CI a hard gate against unsafe structural changes and schema drift.

**Synthesis**: V1's structural blocklist + V2's wiring of existing `validate-migration.sh` script.

### 3.1 Define CI Schema Check Workflow (V1)

**Conceptual Pipeline for PRs Containing Migrations**:

1. **Spin up ephemeral DB** seeded to canonical baseline (head of `main` migrations)
2. **Apply new migrations** from PR branch
3. **Dump resulting schema** (structure only)
4. **Run schema diff tooling** against canonical schema
5. **Evaluate diff** against change taxonomy

**Integration with Phase 1**:

This pipeline integrates with Phase 1's SSOT enforcement CI step (§1.3). The workflow should:
- Run SSOT drift check (canonical vs implementation)
- Run structural safety checks (prohibited changes)
- Run existing `validate-migration.sh` script (destructive DDL detection)

**Exit Gate Evidence**:
- ✅ Pipeline documented in this section
- ✅ Integration with Phase 1's SSOT enforcement described

### 3.2 Define Prohibited Structural Changes (V1)

**Structural Blocklist** (automatic PR failure):

The following changes are **prohibited** and must cause CI to fail:

1. **Dropping Tables**: 
   - Exception: Temporary tables with explicit approval and `# CI:DESTRUCTIVE_OK` bypass comment

2. **Dropping Columns on Core Tables**:
   - Core tables: `attribution_events`, `attribution_allocations`, `revenue_ledger`, `dead_events`, `revenue_state_transitions`, `tenants`, `reconciliation_runs`
   - Exception: With ADR reference and bypass comment

3. **Narrowing Data Types**:
   - On high-volume fields (e.g., `attribution_events.idempotency_key`)
   - On PII-sensitive fields (e.g., `tenants.api_key_hash`)
   - Example: `text` → `varchar(50)` on existing data

4. **Dropping RLS Policies**:
   - On tenant-scoped tables (all tables except `tenants` itself)
   - Exception: With architecture review approval

5. **Dropping Indexes**:
   - Indexes tagged as supporting P0 queries (see OLAP doc)
   - Example: `idx_events_processing_status`, `idx_allocations_channel_performance`

**CI Check Design**:

The CI check should:
- Parse schema diff output
- Match diff lines against blocklist patterns
- Fail if any prohibited pattern detected (unless bypass comment present)

**Exit Gate Evidence**:
- ✅ Blocklist documented in this section
- ⚠️ CI check design described (implementation pending)

### 3.3 Wire Existing Safety Script (V2)

**CI Job**: `.github/workflows/ci.yml` job `validate-migrations` (lines 147-197)

**Current State**: Job exists and executes `scripts/validate-migration.sh` for each modified migration file.

**Required Enhancements**:

1. **Ensure Failure on Non-Zero Exit**: CI step must fail if script returns non-zero exit code
2. **Document Bypass Mechanism**: `# CI:DESTRUCTIVE_OK` with ADR reference
3. **Test Plan**: 
   - Failed PR: Migration with destructive change (no bypass) → CI fails
   - Passed PR: Same migration with bypass comment → CI passes

**Bypass Comment Format**:

```python
op.drop_table('deprecated_table')  # CI:DESTRUCTIVE_OK - See ADR-015 for deprecation timeline
```

**Exit Gate Evidence**:
- ✅ CI workflow exists and is documented
- ⚠️ Test plan described (execution pending)
- ⚠️ CI logs demonstrating enforcement (pending test execution)

### 3.4 Integrate RLS & Critical Constraints (V1)

**RLS Policy Requirements**:

The following RLS policies **MUST exist** on certain tables:

| Table | Required RLS Policy |
|-------|---------------------|
| `attribution_events` | `tenant_isolation_policy` |
| `attribution_allocations` | `tenant_isolation_policy` |
| `revenue_ledger` | `tenant_isolation_policy` |
| `dead_events` | `tenant_isolation_policy` |
| `reconciliation_runs` | `tenant_isolation_policy` |

**Critical Constraints**:

The following constraints are considered **critical** and must be verified:

- `attribution_events.idempotency_key` UNIQUE constraint
- `revenue_ledger.transaction_id` UNIQUE constraint
- `dead_events.remediation_status` CHECK constraint (canonical enum values)
- `attribution_allocations.confidence_score` CHECK constraint (0.0-1.0)

**CI Check Design**:

After applying migrations, CI must:
1. Query `information_schema.table_constraints` and `information_schema.row_security` to verify RLS presence
2. Verify critical constraints still exist
3. Fail if any required RLS policy or constraint is missing
4. Fail if new table under "Analytics Surface" classification is missing RLS (if multi-tenant)

**Exit Gate Evidence**:
- ✅ RLS/constraint enforcement documented in this section
- ⚠️ CI check design described (implementation pending)

---

## Phase 4: Migration Up/Down Safety & Data-Semantic Checks

**Objective**: Ensure migrations can safely roll forward and back, and structural success doesn't hide semantic/data issues.

**Synthesis**: V1's up/down drift test + V2's empirical validation requirements.

### 4.1 Define Up/Down Drift Test (V1)

**CI Job Design for Up/Down Migration Validation**:

1. **Create ephemeral DB** at baseline (head of `main` migrations)
2. **Apply migrations up** to new head (PR branch)
3. **Apply downgrades back** to baseline
4. **Dump schema** at end
5. **Confirm final schema** matches original baseline exactly

**Acceptance Criteria**:
- Downgrade completes without manual intervention
- Final schema dump matches baseline schema dump (normalized diff = empty)
- No unexpected residuals (constraints, indexes, tables)

**Exit Gate Evidence**:
- ✅ Test design documented in this section
- ⚠️ CI job concept described (implementation pending)

### 4.2 Define Data-Semantic Checks (V1)

**Minimal CI Checks on Seeded Sample Dataset**:

For migrations touching data semantics, CI must verify on a seeded sample dataset:

1. **New Non-Nullable Columns with Default**:
   - Verify default behavior on existing rows
   - Query: `SELECT COUNT(*) FROM <table> WHERE <new_column> IS NULL;` → expect 0

2. **Backfills**:
   - Verify row counts match expectations
   - Verify basic invariants (e.g., no NULLs where not allowed)
   - Query: `SELECT COUNT(*) FROM <table> WHERE <backfilled_column> IS NULL;` → expect 0

3. **Privacy-Affecting Changes**:
   - Verify PII-labeled columns are not added to analytics tables
   - Analytics tables: `attribution_events`, `attribution_allocations`, `revenue_ledger`, `dead_events`
   - Check: No columns with `privacy_critical` invariant tag added to analytics tables

4. **RLS-Affecting Changes**:
   - Verify tenant-scoped queries still only see their tenant
   - Test: Set `app.current_tenant_id` to tenant A, query should not return tenant B data

**Sample Dataset Schema**:

The seeded dataset should include:
- Multiple tenants (at least 2)
- Sample rows in each tenant-scoped table
- Representative data patterns (NULLs, edge cases)

**Exit Gate Evidence**:
- ✅ Checks documented in this section
- ✅ Sample dataset schema concept described

### 4.3 Define Forward-Only Policy (V1)

**Forward-Only Migration Treatment**:

Some migrations might be intentionally forward-only (e.g., big data rewrites, irreversible transformations).

**Requirements**:
- Metadata must mark `FORWARD_ONLY = Yes`
- Must include justification in metadata
- Require **stronger review** (architecture review + technical lead approval)
- Must provide **plan** for rollback via separate migration or operational runbook

**Example Forward-Only Migration**:

```python
"""
Migration Metadata

MIGRATION_ID: 202511180000
TITLE: Backfill idempotency_key from external_event_id (irreversible)
CHANGE_TYPE: Column
RISK_LEVEL: Medium
FORWARD_ONLY: Yes
JUSTIFICATION: This migration backfills idempotency_key from external_event_id using COALESCE. The transformation is one-way because external_event_id may be NULL for some rows, making reverse mapping impossible. Rollback requires separate migration to drop idempotency_key column (data loss acceptable per ADR-012).
ROLLBACK_STRATEGY: Separate migration required. See docs/database/RUNBOOK-MIGRATION-POLICY.md §Forward-Only Rollback.
"""
```

**Exit Gate Evidence**:
- ✅ Policy documented in this section
- ✅ Example forward-only migration provided

### 4.4 Tie Semantic Checks to B0.3 Invariants (V1)

**Domain-Specific Semantic Checks**:

For migrations touching B0.3 domains, CI must verify domain-specific invariants:

**B0.3 Auditability Domain**:
- If migration touches `revenue_ledger` or `revenue_state_transitions`:
  - Verify trigger presence: `SELECT tgname FROM pg_trigger WHERE tgname = 'trg_revenue_state_audit';`
  - Verify trigger function exists and is attached

**B0.3 Privacy Domain**:
- If migration touches analytics tables:
  - Verify analytics contract compliance (no PII columns added)
  - Verify PII guardrail triggers still present: `SELECT tgname FROM pg_trigger WHERE tgname LIKE 'trg_%_pii_guardrail';`

**B0.3 OLAP/Index Domain**:
- If migration touches indexes:
  - Verify P0 query indexes still exist (from OLAP doc)
  - Verify index definitions match canonical spec

**B0.3 RLS Domain**:
- If migration touches tenant-scoped tables:
  - Verify RLS policies still attached (see §3.4)
  - Verify `app.current_tenant_id` GUC usage in policies

**Exit Gate Evidence**:
- ✅ Domain coverage documented in this section
- ⚠️ CI check design for each domain described (implementation pending)

---

## Phase 5: Wire B0.3 Outputs as Hard Preconditions for B0.4

**Objective**: Make B0.3 deliverables active constraints on B0.4-related schema changes.

**Synthesis**: V1's domain constraints + V2's B0.3 → B0.4 handoff contract.

### 5.1 Define B0.3 Protection Domains (V1)

**Protection Domains from B0.3 Implementation Docs**:

| Domain | Scope | Tables/Objects |
|--------|-------|----------------|
| **RLS Domain** | Tenant-scoped tables + RLS matrix | `attribution_events`, `attribution_allocations`, `revenue_ledger`, `dead_events`, `reconciliation_runs` |
| **Audit Domain** | Ledger + state transition tables | `revenue_ledger`, `revenue_state_transitions`, audit triggers |
| **OLAP/Index Domain** | Analytics fact tables + matviews + index set | `attribution_events`, `attribution_allocations`, `mv_realtime_revenue`, `mv_channel_performance`, P0 query indexes |
| **Privacy/Retention Domain** | Analytics surface tables, identity surfaces, retention matrix | Analytics tables, PII guardrail triggers, retention policies |

**Domain Mapping**:

Each domain maps to concrete enforcement rules:

- **RLS Domain**: All tenant-scoped tables must have `tenant_isolation_policy` RLS policy
- **Audit Domain**: `revenue_ledger.state` changes must trigger `revenue_state_transitions` inserts
- **OLAP/Index Domain**: P0 queries must use validated indexes (see OLAP doc)
- **Privacy/Retention Domain**: Analytics tables must not contain PII columns; 90-day retention enforced

**Exit Gate Evidence**:
- ✅ Domains documented in this section
- ✅ Tables/constraints/indexes mapped to each domain

### 5.2 Define Domain Constraints (V1)

**Schema Change Constraints Per Domain**:

**RLS Domain Constraints**:
- ❌ **Prohibited**: New multi-tenant analytics table without RLS definition and classification in B0.3 doc
- ❌ **Prohibited**: Removal/weakening of existing RLS without explicit architecture approval
- ✅ **Allowed**: Adding RLS policy consistent with existing contract

**Audit Domain Constraints**:
- ❌ **Prohibited**: Schema changes to `revenue_ledger` or `revenue_state_transitions` that break "no state change without history" guarantee
- ✅ **Required**: Any new ledger-like tables must specify auditability design
- ✅ **Required**: Audit triggers must be present for state-changing operations

**OLAP/Index Domain Constraints**:
- ❌ **Prohibited**: Dropping/changing indexes that serve P0 queries, unless OLAP doc is updated and SLOs revalidated
- ✅ **Required**: New indexes must be tied to documented queries
- ✅ **Required**: Index changes must reference OLAP doc query patterns

**Privacy/Retention Domain Constraints**:
- ❌ **Prohibited**: Addition of PII-bearing columns to analytics surfaces
- ❌ **Prohibited**: Change of retention class without updating retention matrix and enforcement design
- ✅ **Required**: Privacy-affecting changes must reference privacy Implementation Doc

**Examples**:

**Allowed Change**:
- Adding nullable `campaign_id` column to `attribution_events` (analytics_important, not PII)
- Risk Level: Low
- Domain: OLAP/Index (touches analytics surface)

**Prohibited Change**:
- Adding `email` column to `attribution_events` (PII in analytics table)
- Risk Level: High
- Domain: Privacy (violates analytics contract)

**Exit Gate Evidence**:
- ✅ Constraints documented in this section
- ✅ Examples of allowed vs. prohibited changes provided

### 5.3 Define Domain-Aware CI Policies (V1)

**CI Checks Triggered by Migration Metadata Flags**:

The CI schema check pipeline must:

1. **Read Migration Metadata Flags**: Parse `TOUCHES_RLS`, `TOUCHES_PRIVACY_OR_RETENTION`, etc.

2. **Trigger Domain-Specific Checks**:
   - If `TOUCHES_RLS = Yes`:
     - Verify RLS policies still attached to certain tables (see §3.4)
     - Verify no RLS policies were dropped without approval
   
   - If `TOUCHES_PRIVACY_OR_RETENTION = Yes`:
     - Verify no PII columns added to analytics tables
     - Verify retention classes still consistent with retention matrix
   
   - If `TOUCHES_AUDIT_OR_LEDGER = Yes`:
     - Verify audit triggers still present
     - Verify "no state change without history" guarantee maintained
   
   - If `TOUCHES_OLAP_INDEXING = Yes`:
     - Verify P0 query indexes still exist
     - Verify index definitions match canonical spec

3. **Fail on Violation**: CI must fail if domain constraints are violated

**Integration with Phase 3**:

Domain-aware checks integrate with Phase 3's structural safety checks (§3.2, §3.4). The workflow should:
- Run structural blocklist checks (Phase 3)
- Run domain-aware checks (Phase 5)
- Both must pass for PR to be mergeable

**Exit Gate Evidence**:
- ✅ CI policy design documented in this section
- ✅ Integration with Phase 3 CI checks described

### 5.4 Create B0.3 → B0.4 Handoff Contract (V2)

**Contract File**: `docs/handoffs/CONTRACT-B0.3_TO_B0.4.md`

**B0.3 Guarantees (The "Provide")**:

1. **Idempotency Guarantee**:
   - B0.3 provides a `UNIQUE` constraint on `(tenant_id, idempotency_key)` in `attribution_events`
   - The database **will** reject duplicate ingestion events via `UniqueViolation` error
   - Evidence: `CREATE UNIQUE INDEX idx_events_idempotency ON attribution_events (idempotency_key);`

2. **RLS Guarantee**:
   - B0.3 guarantees RLS is **functionally wired**
   - Any API-authenticated DB session **will** have its `app.current_tenant_id` set, enforcing tenant isolation
   - Evidence: RLS policies on all tenant-scoped tables; application middleware sets GUC

3. **Performance Guarantee**:
   - B0.3 provides the **validated** indexes from the Representative Query Workload (RQW)
   - Ingestion queries (Q2, Q4) **are guaranteed** to use `idx_events_processing_status` and `idx_events_idempotency`
   - Evidence: EXPLAIN ANALYZE outputs stored in OLAP doc; indexes match canonical spec

4. **Audit Guarantee**:
   - B0.3 guarantees that any `UPDATE` to `revenue_ledger.state` **will** be atomically recorded in `revenue_state_transitions` via database trigger
   - Evidence: Trigger `trg_revenue_state_audit` attached to `revenue_ledger`

5. **Privacy Guarantee**:
   - B0.3 guarantees that any `INSERT` with a PII key (e.g., 'email') in `raw_payload` **will be rejected** by the `trg_events_pii_guardrail` trigger
   - Evidence: Trigger function `fn_detect_pii_keys()` scans JSONB and raises exception

6. **Retention Guarantee**:
   - B0.3 guarantees that a daily automated job **will** prune analytics data older than 90 days
   - Evidence: Celery task or scheduled job (implementation pending)

**B0.4 Responsibilities (The "Consume")**:

1. **Idempotency**:
   - The B0.4 service **must** generate and supply a non-null `idempotency_key` for every event
   - It **must** handle `UniqueViolation` errors (idempotent retry logic)

2. **RLS**:
   - The B0.4 service **must** use the standard authenticated database session
   - It **must not** attempt to bypass the RLS wiring (e.g., superuser connections)

3. **Performance**:
   - The B0.4 service **must not** introduce new, un-indexed query patterns (e.g., `raw_payload @> ...`) without **first** triggering a B0.3 remediation to add the required GIN index (as per the OLAP remediation directive)

4. **Audit**:
   - The B0.4 service **must not** write to `revenue_state_transitions` directly
   - It **must only** `UPDATE revenue_ledger.state` and trust the trigger

5. **Privacy**:
   - The B0.4 service **should** perform application-level PII stripping, but it **must** rely on the B0.3 trigger as the final defense-in-depth

**Sign-Off Process**:

- B0.4 lead must review and sign this contract before B0.4 implementation begins
- Sign-off recorded in contract file with date and signature
- Any deviation from contract requires formal change-control process

**Exit Gate Evidence**:
- ✅ Contract file created (see separate file: `docs/handoffs/CONTRACT-B0.3_TO_B0.4.md`)
- ✅ All guarantees and responsibilities documented
- ⚠️ B0.4 lead sign-off process defined (execution pending)

---

## Phase 6: Aggregate Approval Gate & System Alignment

**Objective**: Ensure schema/migration safety is enforced and B0.3 outputs are wired as hard constraints into B0.4 planning.

**Synthesis**: V1's readiness checklist + V2's master remediation checklist.

### 6.1 Integrate All Phases into Implementation Document

**Document Structure**:

This Implementation Document consolidates all phases:

- ✅ Phase 1: Canonical schema & change taxonomy
- ✅ Phase 2: Migration metadata template and authoring rules
- ✅ Phase 3: CI schema drift & structural safety design
- ✅ Phase 4: Up/down drift and semantic checks
- ✅ Phase 5: B0.3 domain constraints & B0.4 preconditions

**Table of Contents**: See top of document.

**Exit Gate Evidence**:
- ✅ Single cohesive document with all sections
- ✅ Table of contents with phase mapping

### 6.2 Define Schema Safety & Change Control Ready Checklist

**Unified Readiness Checklist**:

**Governance & SSOT (Phase 1)**:
- [ ] Canonical schema sources defined and accepted
- [ ] Schema change taxonomy and risk levels documented
- [ ] Reconciliation migration `reconcile_b03_canonical_alignment.py` merged
- [ ] CI "Schema Drift Check" live and passing

**Migration Standards (Phase 2)**:
- [ ] Migration metadata template exists; all migrations must comply
- [ ] Authoring rules documented
- [ ] B0.3 domain linkage requirements defined
- [ ] `RUNBOOK-MIGRATION-POLICY.md` approved

**CI Safety (Phase 3)**:
- [ ] CI schema drift pipeline and prohibited structural changes defined
- [ ] CI "Safety Gate" (`validate-migration.sh`) live and passing
- [ ] RLS and critical constraint enforcement in CI designed

**Migration Validation (Phase 4)**:
- [ ] Up/down migration drift checks defined
- [ ] Minimal semantic checks defined
- [ ] Forward-only migration policy documented

**B0.3 Domain Constraints (Phase 5)**:
- [ ] B0.3 domains (RLS, Audit, OLAP, Privacy/Retention) mapped to enforcement rules
- [ ] Domain-aware CI policies designed
- [ ] B0.4 ingestion schema changes required to pass domain-aware checks
- [ ] `CONTRACT-B0.3_TO_B0.4.md` signed by B0.4 lead

**Integration with Other B0.3 Remediation**:

This checklist integrates with other B0.3 remediation directives:
- Functional Wiring (RLS E2E tests, Audit Trigger tests)
- Performance (OLAP indexes, EXPLAIN ANALYZE outputs)
- Privacy & Retention (PII Guardrail tests, Retention tasks)

**Exit Gate Evidence**:
- ✅ Checklist documented in this section
- ✅ Integration with other B0.3 remediation checklists described

### 6.3 Define Global Invariants

**Brief Invariants Summarizing Change Control**:

1. **"No schema change reaches main without declared metadata and CI schema checks."**
   - Every migration must have complete metadata header
   - CI must pass all structural and domain-aware checks

2. **"No migration may drop or weaken RLS/Privacy/Retention/Audit guarantees without documented exception & architecture approval."**
   - Prohibited changes require ADR reference
   - Architecture review required for high-risk changes

3. **"Any schema evolution for B0.4 ingestion must be reconciled with B0.3 implementation docs before being considered valid."**
   - B0.4 schema changes must reference B0.3 domains
   - Domain constraints must be verified in CI

**Exit Gate Evidence**:
- ✅ Invariants documented in this section

### 6.4 Explicitly Align with B0.4 Planning

**B0.4 Planning Alignment Statement**:

> "B0.4 planning assumes schema invariants from B0.3 are enforced in CI. Any ingestion design that requires breaking these invariants must go through a formal change-control process reflected in this document and the architecture guide."

**Implications**:

- B0.4 cannot "just add columns" outside this governance process
- B0.4 schema changes must pass domain-aware CI checks
- B0.4 must respect B0.3 guarantees (see Contract §5.4)

**Exit Gate Evidence**:
- ✅ Alignment documented in this section

---

## Validation Discipline & Exit Gates

### Phase-Level Exit Gates

Each phase must demonstrate:

1. **Governance Definition (V1)**: Written standards, taxonomy, rules
2. **Empirical Validation (V2)**: Testable requirements, CI enforcement, evidence artifacts
3. **Clear Progression Criteria**: Cannot advance until verified

### System-Level Exit Gates

All must be true before claiming schema safety is non-optional:

1. **Readability**: Any engineer can read this doc and answer:
   - Whether a planned change is allowed, under what risk level, and what approvals are needed
   - What CI checks it will face
   - Which B0.3 invariants must not be broken

2. **Enforcement**: Every class of unsafe schema operation is either:
   - Disallowed and caught by CI, or
   - Explicitly handled as rare exception with documented governance

3. **B0.4 Alignment**: B0.4 ingestion planning explicitly references this change-control framework; no path where ingestion "just adds columns" outside this process.

4. **Operational vs. Functional**: This document clearly enforces functional safety (migration is safe, reversible where needed, respects B0.3 constraints) via CI and governance, not just operational success (migration runs).

---

## Implementation Sequence

1. **Phase 1**: Fix current drift (reconciliation migration) + establish SSOT CI
2. **Phase 2**: Define metadata standard + audit existing migrations
3. **Phase 3**: Wire CI safety checks (existing script + new structural checks)
4. **Phase 4**: Define up/down and semantic validation
5. **Phase 5**: Map B0.3 domains + create handoff contract
6. **Phase 6**: Aggregate checklist + system alignment

**Dependencies**: Phases can be documented in parallel, but CI enforcement (Phase 3) depends on SSOT enforcement (Phase 1) being operational.

---

## Deliverable Artifacts

1. **Implementation Document**: This file (`docs/database/REMEDIATION-B0.3-GOVERNANCE-SYSTEM-DESIGN.md`)
2. **Migration Policy Runbook**: `docs/database/RUNBOOK-MIGRATION-POLICY.md`
3. **B0.3 → B0.4 Contract**: `docs/handoffs/CONTRACT-B0.3_TO_B0.4.md`
4. **CI Workflow Updates**: `.github/workflows/schema-drift-check.yml` (activate), `.github/workflows/ci.yml` (verify)

**Note**: This directive produces design and policy documents only. Code implementation (migrations, CI scripts) is documented but not committed in this phase.

---

**Document Status**: ✅ Complete - All phases documented  
**Next Steps**: Execute Phase 1 (activate CI workflow), Phase 2 (audit existing migrations), Phase 5 (create handoff contract)






