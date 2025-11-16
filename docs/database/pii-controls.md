# PII Defense-in-Depth Controls

**Status**: Implemented  
**Last Updated**: 2025-11-16  
**Owner**: Backend Engineering Team

## Overview

Skeldir Attribution Intelligence implements a **three-layer defense-in-depth strategy** to prevent PII (Personally Identifiable Information) from being persisted in the database. This document consolidates the architectural decision (ADR-003) and implementation details into a single authoritative reference.

**Core Principle**: Privacy-First architecture with zero persistent PII storage, enforced through multiple independent layers to eliminate single points of failure.

## Architecture Decision (ADR-003)

**Decision**: Multi-layer defense-in-depth strategy for PII risk mitigation across three layers:

1. **Layer 1 (Application)**: Primary defense via B0.4 ingestion service (future implementation)
2. **Layer 2 (Database)**: Secondary guardrail via PostgreSQL triggers (implemented)
3. **Layer 3 (Operations)**: Audit and monitoring via periodic scanning (implemented)

**Rationale**: Single application-layer defense creates unacceptable risk. Database-level guardrails provide defense-in-depth even if application layer fails.

**Reference**: See `docs/architecture/adr/ADR-003-PII-Defense-Strategy.md` for complete ADR.

## PII Scope Definition

The following PII categories are in scope for detection and blocking:

| PII Category | JSONB Keys (Blocklist) | Detection Method | Rationale |
|-------------|------------------------|------------------|-----------|
| Email addresses | `email`, `email_address` | Key presence (Layer 2)<br>Regex pattern (Layer 1) | High-signal: rarely legitimate in attribution metadata |
| Phone numbers | `phone`, `phone_number` | Key presence (Layer 2)<br>Regex pattern (Layer 1) | High-signal: no valid use case in revenue/event metadata |
| Government IDs | `ssn`, `social_security_number` | Key presence (Layer 2)<br>Pattern matching (Layer 1) | Absolute PII: zero tolerance |
| Personal names | `first_name`, `last_name`, `full_name` | Key presence (Layer 2) | High-signal: customer names not required for attribution |
| IP addresses | `ip_address`, `ip` | Key presence (Layer 2)<br>IPv4 pattern (Layer 1) | Privacy-First mandate: no IP persistence beyond rate limiting |
| Physical addresses | `address`, `street_address` | Key presence (Layer 2) | Geolocation should use city/region only |

**Total Blocklist**: 13 keys monitored across 3 database surfaces = 39 enforcement points.

## Protected Database Surfaces

Three JSONB columns accept arbitrary webhook data and require PII protection:

| Database Surface | Column | Type | Risk Level | Mitigation |
|------------------|--------|------|------------|------------|
| `attribution_events` | `raw_payload` | JSONB NOT NULL | **HIGH** | Layer 2 trigger + Layer 3 audit |
| `dead_events` | `raw_payload` | JSONB NOT NULL | **HIGH** | Layer 2 trigger + Layer 3 audit |
| `revenue_ledger` | `metadata` | JSONB nullable | **MEDIUM** | Layer 2 trigger + Layer 3 audit |

**Risk Rationale**:
- `attribution_events` / `dead_events`: Direct webhook payload ingestion → highest contamination risk
- `revenue_ledger`: Metadata supplemental field → lower risk but still requires protection

## Layer 1: Application Defense (B0.4 - Future)

**Responsibility**: B0.4 Ingestion Service (not yet implemented)

**Mechanism**: Context-aware PII stripping before any database write

**Implementation Requirements**:
1. **Key-based stripping**: Remove JSONB keys matching PII blocklist
2. **Pattern-based scanning**: Regex detection of PII patterns in JSONB values (email, phone, SSN)
3. **Rejection behavior**: Events with PII detected → route to `dead_events` with `error_code='PII_DETECTED'`

**Pattern Definitions**:
- Email: `[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}`
- Phone: `\+?\d[\d\-\s]{7,}`
- SSN: `\d{3}-\d{2}-\d{4}` or `\d{9}` (with context heuristics)

**Acceptance Criteria**: B0.4 must pass comprehensive test suite before production deployment.

**Status**: Contract defined, implementation pending.

## Layer 2: Database Guardrail (Implemented)

**Responsibility**: PostgreSQL trigger-based enforcement

**Mechanism**: "Best-effort" BEFORE INSERT triggers that block JSONB payloads containing obvious PII keys

### Database Objects

**Function: `fn_detect_pii_keys(payload JSONB)`**
- **Purpose**: Fast key-based PII detection using PostgreSQL `?` operator
- **Returns**: `BOOLEAN` (TRUE if any PII key detected)
- **Properties**: `IMMUTABLE`, <1ms overhead per call
- **Location**: `alembic/versions/002_pii_controls/202511161200_add_pii_guardrail_triggers.py`

**Function: `fn_enforce_pii_guardrail()`**
- **Purpose**: Trigger function that raises EXCEPTION if PII detected
- **Returns**: `TRIGGER`
- **Behavior**: 
  - For `attribution_events` and `dead_events`: Check `NEW.raw_payload`
  - For `revenue_ledger`: Check `NEW.metadata` (only if NOT NULL)
  - If PII key found: RAISE EXCEPTION with `ERRCODE = '23514'` (check_violation)
- **Error Message Format**:
  ```
  PII key detected in {table_name}.{column_name}. 
  Ingestion blocked by database policy (Layer 2 guardrail). 
  Key found: {detected_key}. 
  Reference: ADR-003-PII-Defense-Strategy.md. 
  Action: Remove PII key from payload before retry.
  ```

**Triggers**:
- `trg_pii_guardrail_attribution_events` - BEFORE INSERT on `attribution_events`
- `trg_pii_guardrail_dead_events` - BEFORE INSERT on `dead_events`
- `trg_pii_guardrail_revenue_ledger` - BEFORE INSERT on `revenue_ledger`

**Timing**: BEFORE INSERT (blocks write before it reaches storage)  
**Level**: FOR EACH ROW (per-row granularity)

### Explicit Limitations

This layer is "best-effort" and **intentionally scoped to key-based detection only**. It does NOT perform semantic analysis or value-based PII detection.

**Examples**:
- ✅ **BLOCKS**: `{"email": "user@example.com"}` (PII key detected)
- ❌ **ALLOWS**: `{"notes": "contact user@example.com"}` (PII in value, not key)

**Rationale**: Full semantic parsing of arbitrary JSONB values is computationally expensive and unsuitable for high-throughput INSERT triggers. Key-based detection provides 80% protection with <1ms overhead per INSERT.

### Validation

**Test Protocol**: See `scripts/database/validate-pii-guardrails.sh` for operational validation.

**Expected Behavior**:
- INSERT with PII key → ERROR with detailed message
- INSERT with PII in value → SUCCESS (expected limitation)
- NULL metadata → SUCCESS (allowed)

## Layer 3: Audit & Monitoring (Implemented)

**Responsibility**: Database audit procedures + operational monitoring

**Mechanism**: Periodic batch scanning of JSONB surfaces to detect residual PII contamination

### Database Objects

**Table: `pii_audit_findings`**
- **Purpose**: Store PII detection findings from periodic scans
- **Schema**:
  ```sql
  CREATE TABLE pii_audit_findings (
      id BIGSERIAL PRIMARY KEY,
      table_name TEXT NOT NULL,
      column_name TEXT NOT NULL,
      record_id UUID NOT NULL,
      detected_key TEXT NOT NULL,
      sample_snippet TEXT,
      detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
  );
  ```
- **Data Class**: Non-PII (contains record IDs and key names only, NOT actual PII values)
- **Location**: `alembic/versions/002_pii_controls/202511161210_add_pii_audit_table.py`

**Function: `fn_scan_pii_contamination()`**
- **Purpose**: Batch scanning function that checks all three JSONB surfaces for PII keys
- **Returns**: `INTEGER` (count of PII findings detected)
- **Algorithm**: Scans `attribution_events.raw_payload`, `dead_events.raw_payload`, `revenue_ledger.metadata`
- **Performance**: Batch operation, intended for periodic scheduled execution (not per-transaction)
- **Security**: Does NOT log actual PII values, only record IDs and key names

**Indexes**:
- `idx_pii_audit_findings_table_detected_at` on `(table_name, detected_at DESC)` - For table-scoped queries
- `idx_pii_audit_findings_detected_key` on `(detected_key)` - For PII category reporting

### Operational Schedule

| Environment | Frequency | Rationale |
|-------------|-----------|-----------|
| Local Dev | Manual (on-demand) | Developer-triggered when testing PII stripping |
| CI/CD | Per test suite run | Validate PII controls in integration tests |
| Staging | Daily (off-peak) | Daily validation before prod deployment |
| Production | Hourly or Daily | Based on ingestion volume (recommend starting with daily) |

### Validation

**Test Protocol**: See `scripts/database/run-audit-scan.sh` for operational validation.

**Expected Behavior**:
- Clean database: Function returns 0 (no findings)
- Contaminated database: Function returns count > 0, findings recorded in `pii_audit_findings`

## Accepted Risks

The following risks are explicitly accepted and documented:

1. **PII in JSONB Values**: `{"notes": "email is user@test.com"}` → NOT blocked by Layer 2
   - **Mitigation**: Layer 1 pattern scanning + Layer 3 audit

2. **Blocklist Incompleteness**: New PII keys may emerge
   - **Mitigation**: Periodic audit review + ADR amendment

3. **migration_owner Bypass**: Superuser can bypass triggers
   - **Mitigation**: Role restriction + audit logging

## Operational Procedures

### Audit Scan Execution

```bash
# Execute audit scan
psql $DATABASE_URL -c "SELECT fn_scan_pii_contamination();"

# Query findings
psql $DATABASE_URL -c "SELECT * FROM pii_audit_findings ORDER BY detected_at DESC LIMIT 100;"
```

### Incident Response

When PII contamination is detected:

1. **Immediate**: Query `pii_audit_findings` to identify affected records
2. **Investigation**: Check which PII keys are leaking
3. **Remediation**: 
   - If Layer 1 (B0.4) failure: Fix PII stripping logic, redeploy
   - If Layer 2 (trigger) bypass: Investigate who/how triggers were bypassed
   - Delete contaminated records (use `record_id` from findings table)
4. **Root Cause**: Document in incident report, update ADR-003 if new PII key category discovered

See `docs/operations/incident-response.md` for complete playbook.

## Monitoring & Alerting

### Metrics

| Metric Name | Type | Source | Purpose |
|-------------|------|--------|---------|
| `pii_guardrail.reject_count` | Counter | Database trigger | Count of Layer 2 guardrail rejections |
| `pii_audit.findings_count` | Gauge | Audit scan function | Count of PII contamination findings |
| `pii_audit.distinct_records` | Gauge | Audit findings table | Count of distinct contaminated records |
| `pii_audit.findings_by_key` | Counter | Audit findings table | Breakdown of findings by PII type |
| `pii_audit.scan_duration_ms` | Histogram | Audit scan function | Execution time of audit scan |

### Alert Thresholds

| Alert Name | Condition | Severity | Response Time |
|------------|-----------|----------|---------------|
| `PII_Audit_Contamination_Detected` | `pii_audit.findings_count > 0` in production | HIGH | 1 hour |
| `PII_Audit_Mass_Contamination` | `pii_audit.findings_count > 10` in single audit run | CRITICAL | 15 minutes (page) |
| `PII_Guardrail_High_Reject_Rate` | `pii_guardrail.reject_count > 100` in 1 hour | MEDIUM | 4 hours |
| `PII_Audit_Scan_Failed` | Audit scan function returns error or takes >5 minutes | MEDIUM | 4 hours |
| `PII_Audit_Scan_Overdue` | No audit scan in last 48 hours (production) | LOW | Next business day |

See `monitoring/alerts/pii-alerts.yml` for Prometheus alert configuration.

## Governance

### Non-Negotiable Constraints

The following actions are **FORBIDDEN** without ADR amendment:

- ❌ Dropping PII guardrail triggers
- ❌ Dropping PII detection functions
- ❌ Modifying PII key blocklist (must be synchronized across Layer 1, Layer 2, and ADR-003)
- ❌ Bypassing Layer 2 guardrail (B0.4 MUST NOT use `migration_owner` role for normal ingestion writes)

### Periodic Review

**Quarterly PII Control Review**:
1. Audit findings analysis
2. Blocklist update assessment
3. Performance review
4. Incident review

**Annual Compliance Audit**:
- External auditor review of PII controls
- Evidence: All empirical validation outputs
- Evidence: 12 months of `pii_audit_findings` history (must be zero in production)

## Implementation Evidence

### Migration Files

- **Layer 2**: `alembic/versions/002_pii_controls/202511161200_add_pii_guardrail_triggers.py`
- **Layer 3**: `alembic/versions/002_pii_controls/202511161210_add_pii_audit_table.py`

### Validation Scripts

- **PII Guardrail**: `scripts/database/validate-pii-guardrails.sh`
- **Audit Scan**: `scripts/database/run-audit-scan.sh`

### Operational Evidence

- **PII Guardrail Evidence**: `docs/operations/pii-control-evidence.md`
- **Data Governance Evidence**: `docs/operations/data-governance-evidence.md`

## References

- **ADR-003**: `docs/architecture/adr/ADR-003-PII-Defense-Strategy.md` - Complete architectural decision
- **Database Object Catalog**: `docs/database/object-catalog.md` - All functions, triggers, and tables
- **Evidence Mapping**: `docs/architecture/evidence-mapping.md` - Links to validation artifacts
- **Incident Response**: `docs/operations/incident-response.md` - PII detection response playbook

## Related Documentation

- **Privacy-First Architecture**: `PRIVACY-NOTES.md`
- **Schema Governance**: `docs/database/schema-governance.md`
- **Migration System**: `db/docs/MIGRATION_SYSTEM.md`

