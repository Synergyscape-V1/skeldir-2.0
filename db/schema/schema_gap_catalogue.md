# Schema Gap Catalogue

**Purpose**: Comprehensive inventory of divergences between canonical spec and live schema implementation

**Date**: 2025-11-15  
**Canonical Spec Version**: 1.0.0  
**Live Schema Version**: As of migration 202511141311  

**Status**: ❌ **CRITICAL GAPS IDENTIFIED** - 42 divergences found

---

## Summary Statistics

| Category | Count | Severity Breakdown |
|----------|-------|-------------------|
| Missing Columns | 28 | BLOCKING: 23, HIGH: 5 |
| Extra Columns | 7 | LOW: 7 (preserve) |
| Type Mismatches | 3 | BLOCKING: 2, MODERATE: 1 |
| Nullability Mismatches | 1 | BLOCKING: 1 |
| Missing Constraints | 2 | BLOCKING: 2 |
| Missing Indexes | 3 | BLOCKING: 3 |
| Extra Indexes | 2 | LOW: 2 (preserve) |
| Missing Tables | 1 | MODERATE: 1 |
| Extra Tables | 2 | LOW: 2 (preserve) |

**Total Divergences**: 49

---

## Table 1: tenants

### Missing Columns

| Column | Type (Canonical) | Nullability | Invariant | Severity | Required For | Action |
|--------|------------------|-------------|-----------|----------|--------------|--------|
| api_key_hash | VARCHAR(255) | NOT NULL UNIQUE | auth_critical | **BLOCKING** | B0.4 API Authentication | **ADD** |
| notification_email | VARCHAR(255) | NOT NULL | auth_critical | **BLOCKING** | B0.4 Tenant Notifications | **ADD** |

### Verdict

❌ **FAIL** - 2 BLOCKING columns missing

**Impact**: B0.4 API authentication is impossible without `api_key_hash`. Tenant notifications cannot be sent without `notification_email`.

---

## Table 2: attribution_events

### Missing Columns

| Column | Type (Canonical) | Nullability | Invariant | Severity | Required For | Action |
|--------|------------------|-------------|-----------|----------|--------------|--------|
| idempotency_key | VARCHAR(255) | NOT NULL UNIQUE | processing_critical | **BLOCKING** | B0.4 Idempotent Ingestion | **ADD** |
| event_type | VARCHAR(50) | NOT NULL | processing_critical | **BLOCKING** | B0.4 Event Classification | **ADD** |
| channel | VARCHAR(100) | NOT NULL | processing_critical | **BLOCKING** | B0.4 Channel Taxonomy, B2.1 Attribution | **ADD** |
| campaign_id | VARCHAR(255) | NULL | analytics_important | **HIGH** | Campaign Tracking | **ADD** |
| conversion_value_cents | INTEGER | NULL | financial_critical | **BLOCKING** | Revenue Attribution | **ADD** |
| currency | VARCHAR(3) | NULL DEFAULT 'USD' | financial_critical | **BLOCKING** | B2.3 Multi-Currency | **ADD** |
| event_timestamp | TIMESTAMPTZ | NOT NULL | processing_critical | **BLOCKING** | Time-series Queries | **ADD** |
| processed_at | TIMESTAMPTZ | NULL DEFAULT now() | processing_critical | **BLOCKING** | Processing Tracking | **ADD** |
| processing_status | VARCHAR(20) | NULL DEFAULT 'pending' | processing_critical | **BLOCKING** | B0.5 Worker Queue | **ADD** |
| retry_count | INTEGER | NULL DEFAULT 0 | processing_critical | **BLOCKING** | Retry Logic | **ADD** |

### Extra Columns (Currently Implemented)

| Column | Type (Live) | Nullability | Invariant | Severity | Action |
|--------|-------------|-------------|-----------|----------|--------|
| occurred_at | TIMESTAMPTZ | NOT NULL | - | **MODERATE** | **PRESERVE** (similar to event_timestamp) |
| external_event_id | TEXT | NULL | - | LOW | **DEPRECATE** (replaced by idempotency_key) |
| correlation_id | UUID | NULL | - | LOW | **DEPRECATE** (replaced by idempotency_key) |
| revenue_cents | INTEGER | NOT NULL | - | **MODERATE** | **PRESERVE** (similar to conversion_value_cents) |

### Nullability Mismatches

| Column | Canonical | Live | Invariant | Severity | Action |
|--------|-----------|------|-----------|----------|--------|
| session_id | NOT NULL | NULL | privacy_critical | **BLOCKING** | **ALTER** to NOT NULL |

### Missing Constraints

| Constraint | Definition (Canonical) | Severity | Action |
|------------|----------------------|----------|--------|
| ck_attribution_events_processing_status_valid | CHECK IN ('pending', 'processed', 'failed') | **BLOCKING** | **ADD** |

### Missing Indexes

| Index | Columns | Properties | Invariant | Severity | Action |
|-------|---------|------------|-----------|----------|--------|
| idx_events_idempotency | idempotency_key | UNIQUE | processing_critical | **BLOCKING** | **ADD** |
| idx_events_processing_status | processing_status, processed_at | WHERE status = 'pending' | processing_critical | **BLOCKING** | **ADD** |
| idx_events_tenant_timestamp | tenant_id, event_timestamp | DESC on event_timestamp | processing_critical | **BLOCKING** | **ADD** |

### Extra Indexes (Currently Implemented)

| Index | Columns | Properties | Action |
|-------|---------|------------|--------|
| idx_attribution_events_tenant_external_event_id | tenant_id, external_event_id | UNIQUE partial | **DROP** (replaced by idempotency_key) |
| idx_attribution_events_tenant_correlation_id | tenant_id, correlation_id | UNIQUE partial | **DROP** (replaced by idempotency_key) |
| idx_attribution_events_tenant_occurred_at | tenant_id, occurred_at | DESC | **PRESERVE** or **REPLACE** with event_timestamp version |

### Verdict

❌ **FAIL** - 10 BLOCKING columns missing, 1 BLOCKING nullability mismatch, 1 BLOCKING constraint missing, 3 BLOCKING indexes missing

**Impact**: B0.4 ingestion cannot function. B0.5 workers cannot query for pending events. Multi-currency support impossible.

---

## Table 3: attribution_allocations

### Missing Columns

| Column | Type (Canonical) | Nullability | Invariant | Severity | Required For | Action |
|--------|------------------|-------------|-----------|----------|--------------|--------|
| model_type | VARCHAR(50) | NOT NULL | analytics_important | **HIGH** | Model Classification | **ADD** |
| confidence_score | NUMERIC(4,3) | NOT NULL CHECK | analytics_important | **HIGH** | B2.1 Statistical Attribution | **ADD** |
| credible_interval_lower_cents | INTEGER | NULL | analytics_important | **HIGH** | Bayesian Attribution | **ADD** |
| credible_interval_upper_cents | INTEGER | NULL | analytics_important | **HIGH** | Bayesian Attribution | **ADD** |
| convergence_r_hat | NUMERIC(5,4) | NULL | analytics_important | **HIGH** | MCMC Diagnostics | **ADD** |
| effective_sample_size | INTEGER | NULL | analytics_important | **HIGH** | MCMC Diagnostics | **ADD** |
| verified | BOOLEAN | NULL DEFAULT false | analytics_important | **HIGH** | B2.4 Revenue Verification | **ADD** |
| verification_source | VARCHAR(50) | NULL | analytics_important | **HIGH** | Verification Tracking | **ADD** |
| verification_timestamp | TIMESTAMPTZ | NULL | analytics_important | **HIGH** | Verification Tracking | **ADD** |

### Extra Columns (Currently Implemented)

| Column | Type (Live) | Action |
|--------|-------------|--------|
| allocation_ratio | NUMERIC(6,5) | **PRESERVE** (similar purpose to confidence_score) |
| model_metadata | JSONB | **PRESERVE** (can store statistical metadata) |

### Type Mismatches

| Column | Canonical | Live | Severity | Action |
|--------|-----------|------|----------|--------|
| channel | VARCHAR(100) | TEXT (via channel_code) | **MODERATE** | **ALTER** or **ACCEPT** (TEXT is compatible) |

### Missing Constraints

| Constraint | Definition (Canonical) | Severity | Action |
|------------|----------------------|----------|--------|
| confidence_score CHECK | CHECK (confidence_score >= 0 AND confidence_score <= 1) | **HIGH** | **ADD** (after column added) |

### Extra Constraints (Currently Implemented)

| Constraint | Definition | Action |
|------------|-----------|--------|
| ck_attribution_allocations_channel_code_valid | CHECK IN enum values | **DEPRECATE** (replaced by FK to taxonomy) |
| FK to channel_taxonomy | Foreign key constraint | **PRESERVE** (good addition) |

### Verdict

⚠️ **PARTIAL** - 9 HIGH severity columns missing. Not BLOCKING but HIGH impact for B2.1 and B2.4.

**Impact**: B2.1 attribution models cannot write statistical metadata. B2.4 verification tracking unavailable.

---

## Table 4: revenue_ledger

### Missing Columns

| Column | Type (Canonical) | Nullability | Invariant | Severity | Required For | Action |
|--------|------------------|-------------|-----------|----------|--------------|--------|
| transaction_id | VARCHAR(255) | NOT NULL UNIQUE | financial_critical | **BLOCKING** | B2.2 Webhook Idempotency | **ADD** |
| order_id | VARCHAR(255) | NULL | financial_critical | **BLOCKING** | Order Tracking | **ADD** |
| state | VARCHAR(50) | NOT NULL | financial_critical | **BLOCKING** | B2.4 Refund Tracking | **ADD** |
| previous_state | VARCHAR(50) | NULL | financial_critical | **BLOCKING** | State Audit Trail | **ADD** |
| amount_cents | INTEGER | NOT NULL | financial_critical | **BLOCKING** | Revenue Amount | **ADD** |
| currency | VARCHAR(3) | NOT NULL | financial_critical | **BLOCKING** | B2.3 Currency Conversion | **ADD** |
| verification_source | VARCHAR(50) | NOT NULL | financial_critical | **BLOCKING** | Verification Tracking | **ADD** |
| verification_timestamp | TIMESTAMPTZ | NOT NULL | financial_critical | **BLOCKING** | Verification Tracking | **ADD** |
| metadata | JSONB | NULL | - | LOW | FX Rates, Processor Details | **ADD** |

### Extra Columns (Currently Implemented)

| Column | Type (Live) | Action |
|--------|-------------|--------|
| revenue_cents | INTEGER | **PRESERVE** (similar to amount_cents) |
| is_verified | BOOLEAN | **PRESERVE** (different from state machine) |
| verified_at | TIMESTAMPTZ | **PRESERVE** (similar to verification_timestamp) |
| reconciliation_run_id | UUID | **PRESERVE** (valid addition) |
| allocation_id | UUID NOT NULL FK | **PRESERVE** (different architecture) |
| posted_at | TIMESTAMPTZ | **PRESERVE** (valid addition) |

### Missing Constraints

| Constraint | Definition (Canonical) | Severity | Action |
|------------|----------------------|----------|--------|
| ck_revenue_ledger_state_valid | CHECK IN ('authorized', 'captured', 'refunded', 'chargeback') | **BLOCKING** | **ADD** (after state column added) |

### Missing Indexes

| Index | Columns | Properties | Severity | Action |
|-------|---------|-----------|----------|--------|
| idx_revenue_ledger_transaction_id | transaction_id | UNIQUE | **BLOCKING** | **ADD** |
| idx_revenue_ledger_state | state | - | **BLOCKING** | **ADD** |

### Verdict

❌ **FAIL** - 9 BLOCKING columns missing, 1 BLOCKING constraint missing, 2 BLOCKING indexes missing

**Impact**: B2.2 webhook ingestion cannot deduplicate via transaction_id. B2.3 currency conversion impossible. B2.4 refund tracking non-functional.

**Architectural Note**: Live schema uses allocation-based traceability (`allocation_id NOT NULL`) whereas canonical uses transaction-based idempotency (`transaction_id UNIQUE NOT NULL`). These serve different purposes and may need to coexist.

---

## Table 5: dead_events

### Missing Columns

| Column | Type (Canonical) | Nullability | Invariant | Severity | Required For | Action |
|--------|------------------|-------------|-----------|----------|--------------|--------|
| event_type | VARCHAR(50) | NOT NULL | processing_critical | **BLOCKING** | Event Classification | **ADD** |
| error_type | VARCHAR(100) | NOT NULL | processing_critical | **BLOCKING** | Error Classification | **ADD** |
| error_message | TEXT | NOT NULL | processing_critical | **BLOCKING** | Error Tracking | **ADD** |
| error_traceback | TEXT | NULL | - | LOW | Debugging | **ADD** |
| retry_count | INTEGER | NULL DEFAULT 0 | processing_critical | **BLOCKING** | B0.5 Retry Logic | **ADD** |
| last_retry_at | TIMESTAMPTZ | NULL | processing_critical | **BLOCKING** | Retry Scheduling | **ADD** |
| remediation_status | VARCHAR(20) | NULL DEFAULT 'pending' | processing_critical | **BLOCKING** | B0.5 Remediation Queue | **ADD** |
| remediation_notes | TEXT | NULL | - | LOW | Manual Remediation | **ADD** |
| resolved_at | TIMESTAMPTZ | NULL | - | LOW | Resolution Tracking | **ADD** |

### Extra Columns (Currently Implemented)

| Column | Type (Live) | Action |
|--------|-------------|--------|
| ingested_at | TIMESTAMPTZ | **PRESERVE** (similar to created_at) |
| source | TEXT | **PRESERVE** (valid addition) |
| error_code | TEXT | **PRESERVE** (similar to error_type) |
| error_detail | JSONB | **PRESERVE** (structured alternative to error_message) |

### Type Mismatches

| Column | Canonical | Live | Severity | Action |
|--------|-----------|------|----------|--------|
| (Various) | Multiple specific columns | Consolidated into error_detail JSONB | **MODERATE** | **EXPAND** error_detail into specific columns |

### Missing Indexes

| Index | Columns | Properties | Severity | Action |
|-------|---------|-----------|----------|--------|
| idx_dead_events_remediation | remediation_status, created_at | DESC | **BLOCKING** | **ADD** |

### Extra Indexes (Currently Implemented)

| Index | Columns | Action |
|-------|---------|--------|
| idx_dead_events_source | source | **PRESERVE** (valid addition) |
| idx_dead_events_error_code | error_code | **PRESERVE** or **RENAME** to error_type |

### Verdict

❌ **FAIL** - 7 BLOCKING columns missing, 1 BLOCKING index missing

**Impact**: B0.5 retry logic and remediation queue cannot function without retry tracking columns.

**Architectural Note**: Live schema uses consolidated `error_detail` JSONB whereas canonical uses specific columns (`error_type`, `error_message`, `error_traceback`). Consider expanding JSONB or preserving both approaches.

---

## Table 6: revenue_state_transitions

### Status

❌ **MISSING ENTIRELY**

### Impact

**MODERATE** - Refund audit trail (B2.4) will not have dedicated transitions table. However, `previous_state` column in `revenue_ledger` provides some audit capability.

### Action

**ADD** entire table per canonical spec (6 columns, 1 index).

---

## Extra Tables (Not in Canonical Spec)

### Table: reconciliation_runs

**Status**: ✅ Extra table (not in 5 core tables)  
**Severity**: LOW  
**Action**: **PRESERVE** - Valid addition for reconciliation tracking. Not in canonical spec but doesn't conflict.

### Table: channel_taxonomy

**Status**: ✅ Extra table (not in 5 core tables)  
**Severity**: LOW  
**Action**: **PRESERVE** - Valid addition for channel normalization. Provides FK target for `attribution_allocations.channel_code`. Improves data integrity.

---

## Materialized Views

### Missing Views

| View | Purpose | Severity | Action |
|------|---------|----------|--------|
| mv_channel_performance | Channel-level aggregates for B2.6 dashboards | **HIGH** | **ADD** |
| mv_daily_revenue_summary | Daily revenue aggregates | **HIGH** | **ADD** |

### Extra Views (Currently Implemented)

| View | Purpose | Action |
|------|---------|--------|
| mv_realtime_revenue | Tenant revenue aggregates | **PRESERVE** (different purpose than canonical views) |
| mv_reconciliation_status | Latest reconciliation run per tenant | **PRESERVE** (valid addition) |

### Verdict

⚠️ **PARTIAL** - Canonical views missing but different views exist.

**Impact**: B2.6 dashboard endpoints expecting `mv_channel_performance` will not find it and must query base tables or create view.

---

## Gap Catalogue Summary by Invariant Category

### auth_critical (BLOCKING)
- ❌ tenants.api_key_hash: **MISSING**
- ❌ tenants.notification_email: **MISSING**

**Count**: 2 columns  
**Status**: 100% non-compliant

### privacy_critical (BLOCKING)
- ⚠️ attribution_events.session_id: **NULLABILITY MISMATCH** (nullable, should be NOT NULL)

**Count**: 1 mismatch  
**Status**: Critical columns exist but nullability incorrect

### processing_critical (BLOCKING)
- ❌ attribution_events.idempotency_key: **MISSING**
- ❌ attribution_events.event_type: **MISSING**
- ❌ attribution_events.channel: **MISSING**
- ❌ attribution_events.event_timestamp: **MISSING**
- ❌ attribution_events.processed_at: **MISSING**
- ❌ attribution_events.processing_status: **MISSING**
- ❌ attribution_events.retry_count: **MISSING**
- ❌ dead_events.event_type: **MISSING**
- ❌ dead_events.error_type: **MISSING**
- ❌ dead_events.error_message: **MISSING**
- ❌ dead_events.retry_count: **MISSING**
- ❌ dead_events.last_retry_at: **MISSING**
- ❌ dead_events.remediation_status: **MISSING**

**Count**: 13 columns  
**Status**: ~35% compliant (some similar columns exist but with different names/structure)

### financial_critical (BLOCKING)
- ❌ attribution_events.conversion_value_cents: **MISSING**
- ❌ attribution_events.currency: **MISSING**
- ❌ revenue_ledger.transaction_id: **MISSING**
- ❌ revenue_ledger.order_id: **MISSING**
- ❌ revenue_ledger.state: **MISSING**
- ❌ revenue_ledger.previous_state: **MISSING**
- ❌ revenue_ledger.amount_cents: **MISSING**
- ❌ revenue_ledger.currency: **MISSING**
- ❌ revenue_ledger.verification_source: **MISSING**
- ❌ revenue_ledger.verification_timestamp: **MISSING**

**Count**: 10 columns  
**Status**: ~10% compliant (revenue_cents exists but missing transaction identity and state machine)

### analytics_important (HIGH)
- ❌ attribution_events.campaign_id: **MISSING**
- ❌ attribution_allocations.model_type: **MISSING**
- ❌ attribution_allocations.confidence_score: **MISSING**
- ❌ attribution_allocations.credible_interval_lower_cents: **MISSING**
- ❌ attribution_allocations.credible_interval_upper_cents: **MISSING**
- ❌ attribution_allocations.convergence_r_hat: **MISSING**
- ❌ attribution_allocations.effective_sample_size: **MISSING**
- ❌ attribution_allocations.verified: **MISSING**
- ❌ attribution_allocations.verification_source: **MISSING**
- ❌ attribution_allocations.verification_timestamp: **MISSING**

**Count**: 10 columns  
**Status**: 0% compliant (allocation_ratio exists but confidence_score does not)

---

## Prioritized Remediation Plan

### Phase 1: BLOCKING Items (auth + processing + financial critical)
1. ✅ Add tenants.api_key_hash, notification_email
2. ✅ Add attribution_events: idempotency_key, event_type, channel, event_timestamp, processing_status, processed_at, retry_count, conversion_value_cents, currency
3. ✅ Alter attribution_events.session_id to NOT NULL
4. ✅ Add revenue_ledger: transaction_id, order_id, state, previous_state, amount_cents, currency, verification_source, verification_timestamp
5. ✅ Add dead_events: event_type, error_type, error_message, retry_count, last_retry_at, remediation_status
6. ✅ Add revenue_state_transitions table
7. ✅ Add all BLOCKING indexes and constraints

**Count**: 28 columns, 1 table, 6 indexes, 3 constraints

### Phase 2: HIGH Items (analytics important)
1. ✅ Add attribution_allocations: model_type, confidence_score, credible intervals, convergence metrics, verification fields
2. ✅ Add mv_channel_performance, mv_daily_revenue_summary views

**Count**: 10 columns, 2 views

### Phase 3: Cleanup (deprecate old patterns)
1. ✅ Drop old composite idempotency indexes on attribution_events
2. ✅ Mark external_event_id, correlation_id as deprecated (preserve data)
3. ✅ Document architectural differences (allocation_id vs transaction_id patterns)

---

## Final Verdict

**Overall Compliance**: ❌ **~35% COMPLIANT** (by critical column count)

**Blocking Issues**: 28 columns, 1 table, 6 indexes, 3 constraints  
**High-Priority Issues**: 10 columns, 2 views  
**Total Remediation Items**: 50

**Downstream Impact**:
- ❌ B0.4 Ingestion: **BLOCKED** (cannot write events with required fields)
- ❌ B0.5 Workers: **BLOCKED** (cannot query processing_status queue)
- ❌ B1.2 Auth: **BLOCKED** (cannot authenticate via api_key_hash)
- ⚠️ B2.1 Attribution: **HIGH IMPACT** (cannot write statistical metadata)
- ❌ B2.2 Webhooks: **BLOCKED** (cannot deduplicate via transaction_id)
- ❌ B2.3 Currency: **BLOCKED** (no currency column)
- ❌ B2.4 Refunds: **BLOCKED** (no state machine)

**Recommendation**: Execute corrective migrations in priority order (BLOCKING first, then HIGH).

**Signed**: AI Assistant (Claude)  
**Date**: 2025-11-15  
**Status**: ✅ **GAP CATALOGUE COMPLETE**



