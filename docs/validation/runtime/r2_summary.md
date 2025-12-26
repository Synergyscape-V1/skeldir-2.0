# R2 Data-Truth Hardening Validation Summary

## Mission Statement

Prove "truth is protected at runtime" with two simultaneous guarantees:
1. **DB prevents violations** (RLS + triggers + privileges)
2. **Application never attempts destructive writes** to immutable tables

## Exit Gates

| Gate | Description | Status |
|------|-------------|--------|
| EG-R2-0 | Evidence anchoring & closed-set declaration | PASS |
| EG-R2-1 | RLS forced + cross-tenant denial (DB-level proof) | PASS |
| EG-R2-2 | Tenant context discipline (API + Celery) | PASS |
| EG-R2-3 | PII defense-in-depth (DB trigger enforcement) | PASS |
| EG-R2-4 | DB immutability enforcement (UPDATE/DELETE denied) | PASS |
| EG-R2-5 | **Behavioral immutability audit (CLOSURE GATE)** | PASS |
| EG-R2-6 | **Combined adversarial probe (CLOSURE GATE)** | PASS |
| EG-R2-7 | Human-readable truth record | PASS |

### Passing Run Anchor

- **Run ID:** 20514240955
- **SHA:** e25126e
- **Status:** SUCCESS (All 8 gates passed)
- **Date:** 2025-12-26

## Closed Sets (Derived from canonical_schema.sql)

### Tenant-Scoped Tables (15 tables with RLS)

Tables with `ENABLE ROW LEVEL SECURITY` + `FORCE ROW LEVEL SECURITY` + `tenant_isolation_policy`:

1. `attribution_allocations`
2. `attribution_events`
3. `budget_optimization_jobs`
4. `channel_assignment_corrections`
5. `dead_events`
6. `explanation_cache`
7. `investigation_tool_calls`
8. `investigations`
9. `llm_api_calls`
10. `llm_monthly_costs`
11. `llm_validation_failures`
12. `pii_audit_findings`
13. `reconciliation_runs`
14. `revenue_ledger`
15. `revenue_state_transitions`

### Immutable Tables (2 tables with prevent_mutation triggers)

Tables protected by `BEFORE DELETE OR UPDATE` triggers:

1. `attribution_events` - `trg_events_prevent_mutation` -> `fn_events_prevent_mutation()`
2. `revenue_ledger` - `trg_ledger_prevent_mutation` -> `fn_ledger_prevent_mutation()`

### PII-Guarded Tables (3 tables with PII triggers)

Tables protected by `BEFORE INSERT` PII guardrail triggers:

1. `attribution_events` - `trg_pii_guardrail_attribution_events`
2. `dead_events` - `trg_pii_guardrail_dead_events`
3. `revenue_ledger` - `trg_pii_guardrail_revenue_ledger`

### PII Key Blocklist (13 keys)

Keys blocked by `fn_detect_pii_keys()`:

- `email`
- `email_address`
- `phone`
- `phone_number`
- `ssn`
- `social_security_number`
- `ip_address`
- `ip`
- `first_name`
- `last_name`
- `full_name`
- `address`
- `street_address`

## Tenant Context Discipline

### API Layer (`backend/app/core/tenant_context.py`)

- `derive_tenant_id_from_request()`: Derives tenant_id from JWT or API key
- `set_tenant_context_on_session()`: Uses `SET LOCAL app.current_tenant_id`
- `tenant_context_middleware()`: FastAPI middleware for automatic context injection

### Celery Layer (`backend/app/tasks/context.py`)

- `@tenant_task` decorator: Enforces tenant_id presence in all tasks
- `_set_tenant_guc_global()`: Sets GUC using shared engine
- Uses `SET LOCAL` semantics for transaction scoping

## Defense Layers

### Layer 1: Application Code
- Tenant ID derived from authenticated request
- Tenant context set before any DB operation
- No UPDATE/DELETE patterns on immutable tables

### Layer 2: Database Triggers
- PII guardrail triggers on INSERT
- Immutability triggers on UPDATE/DELETE
- Both fire BEFORE operation (not AFTER)

### Layer 3: RLS Policies
- All tenant-scoped tables have RLS ENABLE + FORCE
- Policy: `tenant_id = current_setting('app.current_tenant_id')::uuid`
- WITH CHECK clause ensures INSERT compliance

### Layer 4: Privilege Grants
- App role has SELECT, INSERT on immutable tables
- UPDATE, DELETE revoked (defense-in-depth)

## CI Workflow

File: `.github/workflows/r2-data-truth-hardening.yml`

Triggers:
- Push to main (paths: db/schema/**, backend/app/**)
- Manual dispatch

Uses:
- Digest-pinned Postgres: `postgres@sha256:b3968e348b48f1198cc6de6611d055dbad91cd561b7990c406c3fc28d7095b21`
- Canonical schema: `db/schema/canonical_schema.sql`

## Validation Evidence

Evidence artifacts are uploaded to GitHub Actions with 90-day retention:
- `R2_ENV_SNAPSHOT.json`: Environment provenance
- `CLOSED_SET_*.txt`: Derived closed sets
- `SCHEMA_FINGERPRINT.txt`: SHA256 of canonical schema
- `RLS_PROOF/*`: RLS verification logs
- `PII_PROOF/*`: PII trigger test logs
- `IMMUTABILITY_PROOF/*`: Immutability test logs
- `BEHAVIORAL_AUDIT/*`: Static analysis results
- `ADVERSARIAL_PROBE/*`: Attack simulation logs
- `R2_TRUTH_RECORD.md`: Human-readable summary

## Remediation Policy

If any gate fails:
1. DO NOT merge to main
2. Fix the issue in code/schema
3. Re-run the workflow
4. All 8 gates must pass for R2 COMPLETE

Closure gates (EG-R2-5, EG-R2-6) are mandatory - R2 cannot complete without both passing.

---

*Last updated: 2025-12-26 - R2 COMPLETE (Run 20514240955)*
