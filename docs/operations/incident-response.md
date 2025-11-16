# Incident Response Playbooks

**Purpose**: Operational playbooks for PII detection, data integrity violations, and forensic analysis.

**Last Updated**: 2025-11-16

## PII Detection Incident Response

### Severity Levels

| Severity | Condition | Response Time | Escalation |
|----------|-----------|---------------|------------|
| **CRITICAL** | >10 findings in single audit run | 15 minutes (page) | On-Call Engineer + Security Team |
| **HIGH** | >0 findings in production | 1 hour | Security Team + Backend Lead |
| **MEDIUM** | High guardrail rejection rate (>100/hour) | 4 hours | Backend Team |

### Playbook: PII Contamination Detected

**Trigger**: Alert `PII_Audit_Contamination_Detected` or `PII_Audit_Mass_Contamination`

**Step 1: Immediate Assessment**

```sql
-- Query recent findings
SELECT 
    table_name,
    column_name,
    detected_key,
    COUNT(*) as finding_count,
    MIN(detected_at) as first_detected,
    MAX(detected_at) as last_detected
FROM pii_audit_findings
WHERE detected_at > NOW() - INTERVAL '1 hour'
GROUP BY table_name, column_name, detected_key
ORDER BY finding_count DESC;
```

**Step 2: Identify Affected Records**

```sql
-- Get affected record IDs
SELECT 
    record_id,
    table_name,
    detected_key,
    detected_at
FROM pii_audit_findings
WHERE detected_at > NOW() - INTERVAL '1 hour'
ORDER BY detected_at DESC;
```

**Step 3: Determine Root Cause**

**Check Layer 1 (B0.4 Application)**:
- Review application logs for PII stripping errors
- Verify B0.4 deployment status
- Check if PII stripping logic was disabled or misconfigured

**Check Layer 2 (Database Guardrail)**:
- Verify triggers are active: `SELECT * FROM pg_trigger WHERE tgname LIKE 'trg_pii_guardrail%';`
- Check if `migration_owner` role was used to bypass triggers
- Review database logs for trigger execution errors

**Step 4: Immediate Remediation**

**If Layer 1 Failure**:
1. Stop ingestion service if contamination is ongoing
2. Fix PII stripping logic
3. Redeploy B0.4 service
4. Resume ingestion

**If Layer 2 Bypass**:
1. Identify who/how triggers were bypassed
2. Review `migration_owner` role usage logs
3. Restore trigger enforcement
4. Investigate why bypass occurred

**Step 5: Data Remediation**

```sql
-- Delete contaminated records (use record_id from findings)
-- WARNING: Only delete after confirming records are contaminated
-- Backup records before deletion for forensic analysis

DELETE FROM attribution_events 
WHERE id IN (
    SELECT record_id FROM pii_audit_findings 
    WHERE table_name = 'attribution_events' 
      AND detected_at > NOW() - INTERVAL '1 hour'
);

-- Similar for dead_events and revenue_ledger
```

**Step 6: Post-Incident**

1. **Document Incident**: Create incident report with:
   - Root cause analysis
   - Affected records count
   - Remediation steps taken
   - Prevention measures

2. **Update ADR-003**: If new PII key category discovered, update blocklist

3. **Review Process**: Quarterly review of incident patterns

---

## Data Integrity Violation Response

### Playbook: Sum-Equality Violation

**Trigger**: Error from `check_allocation_sum()` trigger

**Step 1: Identify Violation**

```sql
-- Query allocation summary for unbalanced allocations
SELECT 
    tenant_id,
    event_id,
    model_version,
    total_allocated_cents,
    event_revenue_cents,
    drift_cents,
    is_balanced
FROM mv_allocation_summary
WHERE is_balanced = false
ORDER BY ABS(drift_cents) DESC;
```

**Step 2: Root Cause Analysis**

**Possible Causes**:
- Application bug in allocation calculation
- Race condition in concurrent allocation writes
- Manual database intervention bypassing validation

**Step 3: Remediation**

**Option A: Correct Allocations** (if application bug):
1. Fix allocation calculation logic
2. Delete incorrect allocations
3. Re-run attribution model to generate correct allocations

**Option B: Adjust Event Revenue** (if event revenue incorrect):
1. Create correction event with negative revenue
2. Link via correlation_id to original event
3. Re-run attribution model

**Step 4: Prevention**

- Review allocation calculation code
- Add integration tests for sum-equality
- Monitor `mv_allocation_summary` for drift

---

### Playbook: Immutability Violation Attempt

**Trigger**: Error from `fn_events_prevent_mutation()` or `fn_ledger_prevent_mutation()`

**Step 1: Identify Attempt**

```sql
-- Check database logs for mutation attempts
-- Pattern: "attribution_events is append-only; updates and deletes are not allowed"
```

**Step 2: Determine Source**

- Application code attempting UPDATE/DELETE
- Manual database intervention
- Misconfigured service role

**Step 3: Remediation**

**If Application Bug**:
1. Fix application code to use correction events instead of UPDATE
2. Deploy fix
3. Document correction pattern

**If Manual Intervention**:
1. Review who performed operation
2. Verify authorization
3. Document why manual intervention was needed
4. Consider if correction event pattern should have been used

---

### Playbook: RLS Violation (Cross-Tenant Access)

**Trigger**: Application error or security audit finding

**Step 1: Verify RLS Enforcement**

```sql
-- Test tenant isolation
SET app.current_tenant_id = 'tenant-1-uuid';
SELECT COUNT(*) FROM attribution_events;  -- Should return tenant-1 data only

SET app.current_tenant_id = 'tenant-2-uuid';
SELECT COUNT(*) FROM attribution_events;  -- Should return tenant-2 data only (no tenant-1 data)
```

**Step 2: Check RLS Policies**

```sql
-- Verify RLS is enabled
SELECT tablename, rowsecurity 
FROM pg_tables 
WHERE schemaname = 'public' 
  AND tablename IN ('attribution_events', 'revenue_ledger', 'attribution_allocations');

-- Verify policies exist
SELECT * FROM pg_policies 
WHERE tablename IN ('attribution_events', 'revenue_ledger', 'attribution_allocations');
```

**Step 3: Remediation**

**If RLS Disabled**:
1. Enable RLS: `ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;`
2. Verify policies are active
3. Test tenant isolation

**If Policy Missing**:
1. Create tenant isolation policy
2. Test tenant isolation
3. Document policy creation

---

## Forensic Analysis Playbook

### Purpose

Conduct forensic analysis of security incidents, data integrity violations, or system anomalies.

### Step 1: Evidence Collection

**Database Logs**:
```sql
-- Query PII audit findings
SELECT * FROM pii_audit_findings 
WHERE detected_at BETWEEN '2025-11-16 10:00:00' AND '2025-11-16 11:00:00'
ORDER BY detected_at DESC;

-- Query allocation summary for drift
SELECT * FROM mv_allocation_summary 
WHERE is_balanced = false 
  AND created_at BETWEEN '2025-11-16 10:00:00' AND '2025-11-16 11:00:00';
```

**Application Logs**:
- Check correlation IDs for request tracing
- Review error logs for trigger rejections
- Check service health logs

**Database State**:
```sql
-- Verify trigger status
SELECT * FROM pg_trigger WHERE tgname LIKE 'trg_%';

-- Verify function status
SELECT * FROM pg_proc WHERE proname LIKE 'fn_%' OR proname LIKE 'check_%';
```

### Step 2: Timeline Reconstruction

**Create Timeline**:
1. Identify incident start time (first finding/error)
2. Map events chronologically:
   - PII findings timestamps
   - Application errors
   - Database trigger rejections
   - Service deployments

**Correlation**:
- Use `correlation_id` to trace requests across services
- Map database operations to application requests

### Step 3: Root Cause Analysis

**Questions to Answer**:
1. What was the immediate cause? (trigger rejection, audit finding, etc.)
2. What was the underlying cause? (application bug, misconfiguration, etc.)
3. Why did controls fail? (Layer 1 failure, Layer 2 bypass, etc.)
4. What could have prevented this? (better testing, monitoring, etc.)

### Step 4: Impact Assessment

**Data Impact**:
- Number of affected records
- PII categories exposed
- Time window of exposure

**System Impact**:
- Service availability
- Performance degradation
- User impact

### Step 5: Remediation Plan

**Immediate**:
- Stop ongoing contamination
- Isolate affected systems
- Begin data remediation

**Short-term**:
- Fix root cause
- Deploy fixes
- Restore normal operations

**Long-term**:
- Update controls
- Improve monitoring
- Enhance testing

### Step 6: Documentation

**Incident Report Template**:
- Executive Summary
- Timeline
- Root Cause Analysis
- Impact Assessment
- Remediation Steps
- Prevention Measures
- Lessons Learned

---

## Related Documentation

- **PII Controls**: `docs/database/pii-controls.md`
- **Data Governance**: `docs/database/schema-governance.md`
- **Monitoring**: `monitoring/prometheus/pii-metrics.yml`
- **Alerts**: `monitoring/alerts/pii-alerts.yml`

