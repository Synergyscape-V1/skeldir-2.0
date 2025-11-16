# Evidence Mapping: Capabilities to Validation Artifacts

**Purpose**: Direct links from system capabilities to their implementation artifacts, test protocols, and operational evidence.

**Last Updated**: 2025-11-16

## Overview

This document provides direct navigation from system capabilities to their empirical validation evidence. Each capability links to:
- Implementation artifacts (migration files, functions, triggers)
- Test protocols (validation scripts, SQL commands)
- Operational evidence (test results, monitoring configurations)

## PII Defense-in-Depth Controls

### Layer 2: Database Guardrail

**Capability**: PII key detection and blocking at database level

**Implementation Artifacts**:
- **Migration**: `alembic/versions/002_pii_controls/202511161200_add_pii_guardrail_triggers.py`
- **Function**: `fn_detect_pii_keys(payload JSONB)` - Returns TRUE if any PII key detected
- **Function**: `fn_enforce_pii_guardrail()` - Trigger function raising EXCEPTION on PII detection
- **Triggers**:
  - `trg_pii_guardrail_attribution_events` - BEFORE INSERT on `attribution_events`
  - `trg_pii_guardrail_dead_events` - BEFORE INSERT on `dead_events`
  - `trg_pii_guardrail_revenue_ledger` - BEFORE INSERT on `revenue_ledger`

**Test Protocols**:
- **Script**: `scripts/database/validate-pii-guardrails.sh`
- **Test Command**: 
  ```sql
  INSERT INTO attribution_events (tenant_id, occurred_at, raw_payload) 
  VALUES (gen_random_uuid(), NOW(), '{"email": "test@test.com"}'::jsonb);
  ```
- **Expected Result**: ERROR with message "PII key detected in attribution_events.raw_payload..."

**Operational Evidence**:
- **Document**: `docs/operations/pii-control-evidence.md`
- **Evidence Type**: SQL command output showing guardrail blocking

**Documentation**:
- **ADR**: `docs/architecture/adr/ADR-003-PII-Defense-Strategy.md`
- **Implementation Guide**: `docs/database/pii-controls.md`

### Layer 3: Audit & Monitoring

**Capability**: Periodic batch scanning for residual PII contamination

**Implementation Artifacts**:
- **Migration**: `alembic/versions/002_pii_controls/202511161210_add_pii_audit_table.py`
- **Table**: `pii_audit_findings` - Stores PII detection findings
- **Function**: `fn_scan_pii_contamination()` - Batch scanning function returning finding count
- **Indexes**:
  - `idx_pii_audit_findings_table_detected_at` on `(table_name, detected_at DESC)`
  - `idx_pii_audit_findings_detected_key` on `(detected_key)`

**Test Protocols**:
- **Script**: `scripts/database/run-audit-scan.sh`
- **Test Command**: 
  ```sql
  SELECT fn_scan_pii_contamination();
  SELECT * FROM pii_audit_findings ORDER BY detected_at DESC;
  ```
- **Expected Result**: Function returns integer count, findings recorded in table

**Operational Evidence**:
- **Document**: `docs/operations/pii-control-evidence.md`
- **Evidence Type**: SQL query outputs showing audit scan execution and findings

**Documentation**:
- **Implementation Guide**: `docs/database/pii-controls.md`
- **Monitoring Config**: `monitoring/prometheus/pii-metrics.yml`
- **Alert Config**: `monitoring/alerts/pii-alerts.yml`

## Data Integrity Controls

### Sum-Equality Invariant

**Capability**: Attribution allocations must sum to event revenue

**Implementation Artifacts**:
- **Migration**: `alembic/versions/003_data_governance/202511131240_add_sum_equality_validation.py`
- **Function**: `check_allocation_sum()` - Validates allocation sum equals event revenue
- **Trigger**: `trg_check_allocation_sum` - BEFORE INSERT/UPDATE on `attribution_allocations`
- **Materialized View**: `mv_allocation_summary` - Aggregates allocation sums for validation

**Test Protocols**:
- **Script**: `scripts/database/test-data-integrity.sh`
- **Test Command**: Attempt to create allocations that don't sum to event revenue
- **Expected Result**: ERROR with sum-equality violation message

**Operational Evidence**:
- **Document**: `docs/operations/data-governance-evidence.md`
- **Evidence Type**: SQL command output showing sum-equality validation

**Documentation**:
- **Specification**: `db/docs/SUM_EQUALITY_INVARIANT.md`
- **Implementation Guide**: `docs/database/schema-governance.md`

### Immutability Controls

**Capability**: Prevent UPDATE/DELETE on immutable tables

**Implementation Artifacts**:
- **Events Immutability**:
  - **Migration**: `alembic/versions/003_data_governance/202511141201_add_events_guard_trigger.py`
  - **Function**: `fn_events_prevent_mutation()` - Raises EXCEPTION on UPDATE/DELETE
  - **Trigger**: `trg_events_prevent_mutation` - BEFORE UPDATE OR DELETE on `attribution_events`
- **Ledger Immutability**:
  - **Migration**: `alembic/versions/003_data_governance/202511141301_add_ledger_guard_trigger.py`
  - **Function**: `fn_ledger_prevent_mutation()` - Raises EXCEPTION on UPDATE/DELETE
  - **Trigger**: `trg_ledger_prevent_mutation` - BEFORE UPDATE OR DELETE on `revenue_ledger`

**Test Protocols**:
- **Script**: `scripts/database/test-data-integrity.sh`
- **Test Commands**:
  ```sql
  -- Attempt UPDATE
  UPDATE attribution_events SET revenue_cents = 2000 WHERE id = '...';
  -- Expected: ERROR with immutability message
  
  -- Attempt DELETE
  DELETE FROM attribution_events WHERE id = '...';
  -- Expected: ERROR with immutability message
  ```

**Operational Evidence**:
- **Document**: `docs/operations/data-governance-evidence.md`
- **Evidence Type**: SQL command outputs showing UPDATE/DELETE blocked

**Documentation**:
- **Policy**: `db/docs/EVENTS_IMMUTABILITY_POLICY.md`
- **Implementation Guide**: `docs/database/schema-governance.md`

### Row-Level Security (RLS)

**Capability**: Tenant isolation via RLS policies

**Implementation Artifacts**:
- **Migration**: `alembic/versions/001_core_schema/202511131120_add_rls_policies.py`
- **Policies**: Tenant isolation policies on all tenant-scoped tables
- **Pattern**: `USING (tenant_id = current_setting('app.current_tenant_id')::UUID)`

**Test Protocols**:
- **Script**: `scripts/database/test-data-integrity.sh`
- **Test Command**: 
  ```sql
  -- Set tenant context
  SET app.current_tenant_id = 'tenant-1-uuid';
  SELECT * FROM attribution_events;  -- Returns tenant-1 data only
  
  -- Change tenant context
  SET app.current_tenant_id = 'tenant-2-uuid';
  SELECT * FROM attribution_events;  -- Returns tenant-2 data only (no tenant-1 data)
  ```

**Operational Evidence**:
- **Document**: `docs/operations/data-governance-evidence.md`
- **Evidence Type**: SQL query outputs showing cross-tenant access blocked

**Documentation**:
- **RLS Template**: `db/migrations/templates/rls_policy.py.template`
- **Implementation Guide**: `docs/database/schema-governance.md`

## Idempotency Controls

**Capability**: Prevent duplicate event ingestion

**Implementation Artifacts**:
- **Migration**: `alembic/versions/001_core_schema/202511131115_add_core_tables.py`
- **Indexes**:
  - `idx_attribution_events_tenant_external_event_id` - UNIQUE on `(tenant_id, external_event_id)` WHERE external_event_id IS NOT NULL
  - `idx_attribution_events_tenant_correlation_id` - UNIQUE on `(tenant_id, correlation_id)` WHERE correlation_id IS NOT NULL AND external_event_id IS NULL

**Test Protocols**:
- **Test Command**: 
  ```sql
  -- First INSERT succeeds
  INSERT INTO attribution_events (tenant_id, external_event_id, occurred_at, raw_payload) 
  VALUES ('tenant-uuid', 'order-123', NOW(), '{}'::jsonb);
  
  -- Duplicate INSERT fails
  INSERT INTO attribution_events (tenant_id, external_event_id, occurred_at, raw_payload) 
  VALUES ('tenant-uuid', 'order-123', NOW(), '{}'::jsonb);
  -- Expected: ERROR duplicate key violation
  ```

**Documentation**:
- **Strategy**: `db/docs/IDEMPOTENCY_STRATEGY.md`
- **Implementation Guide**: `docs/database/schema-governance.md`

## API Contracts

### Attribution API

**Capability**: Attribution revenue and allocation endpoints

**Implementation Artifacts**:
- **Contract**: `contracts/attribution/v1/attribution.yaml`
- **Baseline**: `contracts/attribution/baselines/v1.0.0/attribution.yaml`
- **Backend Component**: `backend/app/attribution/` (planned)

**Test Protocols**:
- **Mock Server**: `docker-compose.yml` - Attribution service on port 4011
- **Integration Tests**: `tests/frontend-integration.spec.ts`
- **Client Generation**: `scripts/generate-models.sh`

**Operational Evidence**:
- **Client Validation**: Python and TypeScript clients generated and validated
- **Response Parity**: Mock server responses match contract specifications

**Documentation**:
- **Contract Ownership**: `docs/architecture/contract-ownership.md`
- **API Evolution**: `docs/architecture/api-evolution.md`

### Webhook Contracts

**Capability**: Webhook ingestion endpoints (Shopify, WooCommerce, Stripe, PayPal)

**Implementation Artifacts**:
- **Contracts**: 
  - `contracts/webhooks/v1/shopify.yaml`
  - `contracts/webhooks/v1/woocommerce.yaml`
  - `contracts/webhooks/v1/stripe.yaml`
  - `contracts/webhooks/v1/paypal.yaml`
- **Backend Component**: `backend/app/webhooks/` (planned)

**Test Protocols**:
- **Mock Servers**: `docker-compose.yml` - Webhook services on ports 4015-4018
- **HMAC Validation**: Per `.cursor/rules:481` - All webhooks require HMAC signature validation

**Documentation**:
- **Contract Ownership**: `docs/architecture/contract-ownership.md`
- **Service Boundaries**: `docs/architecture/service-boundaries.md`

### Auth API

**Capability**: Authentication and authorization endpoints

**Implementation Artifacts**:
- **Contract**: `contracts/auth/v1/auth.yaml`
- **Backend Component**: `backend/app/auth/` (planned)

**Test Protocols**:
- **Mock Server**: `docker-compose.yml` - Auth service on port 4010
- **Integration Tests**: `tests/frontend-integration.spec.ts`

**Documentation**:
- **Contract Ownership**: `docs/architecture/contract-ownership.md`

## Database Objects Catalog

### Functions

| Function | Purpose | Migration | Invocation Pattern |
|----------|---------|-----------|-------------------|
| `fn_detect_pii_keys(payload JSONB)` | PII key detection | `002_pii_controls/202511161200_add_pii_guardrail_triggers.py` | `SELECT fn_detect_pii_keys('{"email": "test@test.com"}'::jsonb);` |
| `fn_enforce_pii_guardrail()` | PII guardrail enforcement | `002_pii_controls/202511161200_add_pii_guardrail_triggers.py` | Trigger function (automatic) |
| `fn_scan_pii_contamination()` | PII audit scanning | `002_pii_controls/202511161210_add_pii_audit_table.py` | `SELECT fn_scan_pii_contamination();` |
| `check_allocation_sum()` | Sum-equality validation | `003_data_governance/202511131240_add_sum_equality_validation.py` | Trigger function (automatic) |
| `fn_events_prevent_mutation()` | Events immutability | `003_data_governance/202511141201_add_events_guard_trigger.py` | Trigger function (automatic) |
| `fn_ledger_prevent_mutation()` | Ledger immutability | `003_data_governance/202511141301_add_ledger_guard_trigger.py` | Trigger function (automatic) |

### Triggers

| Trigger | Table | Purpose | Migration |
|---------|-------|---------|-----------|
| `trg_pii_guardrail_attribution_events` | `attribution_events` | Block PII keys in raw_payload | `002_pii_controls/202511161200_add_pii_guardrail_triggers.py` |
| `trg_pii_guardrail_dead_events` | `dead_events` | Block PII keys in raw_payload | `002_pii_controls/202511161200_add_pii_guardrail_triggers.py` |
| `trg_pii_guardrail_revenue_ledger` | `revenue_ledger` | Block PII keys in metadata | `002_pii_controls/202511161200_add_pii_guardrail_triggers.py` |
| `trg_check_allocation_sum` | `attribution_allocations` | Validate sum-equality invariant | `003_data_governance/202511131240_add_sum_equality_validation.py` |
| `trg_events_prevent_mutation` | `attribution_events` | Prevent UPDATE/DELETE | `003_data_governance/202511141201_add_events_guard_trigger.py` |
| `trg_ledger_prevent_mutation` | `revenue_ledger` | Prevent UPDATE/DELETE | `003_data_governance/202511141301_add_ledger_guard_trigger.py` |

### Materialized Views

| Materialized View | Purpose | Migration | Refresh Pattern |
|-------------------|---------|-----------|-----------------|
| `mv_realtime_revenue` | Realtime revenue aggregation | `001_core_schema/202511131119_add_materialized_views.py` | CONCURRENTLY with 30-60s TTL |
| `mv_reconciliation_status` | Reconciliation status per tenant | `001_core_schema/202511131119_add_materialized_views.py` | CONCURRENTLY with 30-60s TTL |
| `mv_allocation_summary` | Allocation sum validation | `003_data_governance/202511131240_add_sum_equality_validation.py` | CONCURRENTLY on demand |
| `mv_channel_performance` | Channel performance analytics | `003_data_governance/202511151500_add_mv_channel_performance.py` | CONCURRENTLY daily |
| `mv_daily_revenue_summary` | Daily revenue aggregation | `003_data_governance/202511151510_add_mv_daily_revenue_summary.py` | CONCURRENTLY daily |

**Complete Catalog**: See `docs/database/object-catalog.md` for comprehensive database object documentation.

## Validation Scripts

### PII Controls

**Script**: `scripts/database/validate-pii-guardrails.sh`
- **Purpose**: Test PII guardrail blocking behavior
- **Tests**: INSERT with PII key (should fail), INSERT with PII in value (should succeed)
- **Evidence Output**: SQL command outputs showing ERROR messages

**Script**: `scripts/database/run-audit-scan.sh`
- **Purpose**: Execute PII audit scan and verify findings
- **Tests**: Audit scan execution, findings query, findings structure validation
- **Evidence Output**: SQL query outputs showing function execution and findings

### Data Integrity

**Script**: `scripts/database/test-data-integrity.sh`
- **Purpose**: Test all data integrity controls
- **Tests**: 
  - Sum-equality invariant validation
  - Immutability trigger blocking
  - RLS tenant isolation
- **Evidence Output**: SQL command outputs for all three validations

## Monitoring & Alerting

### Prometheus Metrics

**Configuration**: `monitoring/prometheus/pii-metrics.yml`
- **Metrics**: 
  - `pii_guardrail.reject_count` (Counter)
  - `pii_audit.findings_count` (Gauge)
  - `pii_audit.scan_duration_ms` (Histogram)

**Validation**: `promtool check config prometheus.yml` succeeds

### Grafana Dashboards

**Configuration**: `monitoring/grafana/pii-dashboard.json`
- **Dashboard**: PII audit findings over time, guardrail rejection rates
- **Validation**: Dashboard loads in Grafana without errors

### Alert Rules

**Configuration**: `monitoring/alerts/pii-alerts.yml`
- **Alerts**:
  - `PII_Audit_Contamination_Detected`
  - `PII_Audit_Mass_Contamination`
  - `PII_Guardrail_High_Reject_Rate`
- **Validation**: `promtool check rules pii-alerts.yml` succeeds

## CI/CD Validation

### Contract Validation

**Workflow**: `.github/workflows/contract-validation.yml`
- **Purpose**: Validate OpenAPI contract syntax and structure
- **Validation**: All contracts pass `openapi-generator-cli validate`

### Migration Validation

**Workflow**: `.github/workflows/ci.yml` (validate-migrations job)
- **Purpose**: Validate migration safety and linearity
- **Script**: `scripts/validate-migration.sh`
- **Validation**: All migrations pass safety checks

### Schema Drift Detection

**Workflow**: `.github/workflows/schema-drift-check.yml` (commented, not active)
- **Purpose**: Detect schema drift between migrations and actual database
- **Validation**: Schema snapshots match migration-generated schema

## Navigation Quick Reference

**From Repository Root**:

1. **PII Controls** (≤3 clicks):
   - Root → `docs/database/pii-controls.md`
   - Root → `docs/architecture/evidence-mapping.md` → PII Defense-in-Depth Controls

2. **Schema Governance** (≤3 clicks):
   - Root → `docs/database/schema-governance.md`
   - Root → `docs/architecture/evidence-mapping.md` → Data Integrity Controls

3. **API Contracts** (≤3 clicks):
   - Root → `contracts/attribution/v1/attribution.yaml`
   - Root → `docs/architecture/evidence-mapping.md` → API Contracts

4. **Operational Evidence** (≤3 clicks):
   - Root → `docs/operations/pii-control-evidence.md`
   - Root → `docs/operations/data-governance-evidence.md`

## Related Documentation

- **PII Controls**: `docs/database/pii-controls.md`
- **Schema Governance**: `docs/database/schema-governance.md`
- **Database Object Catalog**: `docs/database/object-catalog.md`
- **Service Boundaries**: `docs/architecture/service-boundaries.md`
- **Contract Ownership**: `docs/architecture/contract-ownership.md`

