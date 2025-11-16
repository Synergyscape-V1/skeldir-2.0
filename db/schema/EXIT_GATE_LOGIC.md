# Exit Gate Logic for Schema Compliance

**Document Purpose**: Define gate logic for B0.3, B0.4, B0.5, and B2.x phases that enforces canonical schema compliance

**Version**: 1.0.0  
**Date**: 2025-11-15  
**Status**: ✅ BINDING - Non-negotiable for phase progression

---

## 1. Core Gate Principle

**No phase may be marked complete or progress to the next phase unless the schema compliance validator passes with zero BLOCKING divergences for that phase's required elements.**

This is a **hard gate** - no manual overrides, no exceptions, no "technical debt acceptance."

---

## 2. Gate Execution Workflow

```
Phase Work → Completion Claimed → Run Validator → Analyze Results → Gate Decision
                                       ↓                ↓              ↓
                                   Exit Code       Divergences    PASS/FAIL
                                   (0, 1, or 2)    (JSON report)
```

### 2.1 Gate Execution Trigger Points

**When to Run Validator**:
1. **Before** marking phase as complete (manual trigger)
2. **Before** merging any migration PR (CI/CD trigger)
3. **After** applying any schema changes (post-migration trigger)
4. **During** phase review (audit trigger)

### 2.2 Gate Executor Roles

| Trigger Point | Executor | Environment |
|---------------|----------|-------------|
| Manual completion check | Developer | Local or test DB |
| PR merge gate | CI/CD pipeline | Test DB (ephemeral) |
| Post-migration verification | Deploy script | Staging/Production DB |
| Phase audit | QA/Reviewer | Any environment |

---

## 3. B0.3 Exit Gate Logic

### 3.1 Required Conditions

**Phase Name**: B0.3 (Database Schema Foundation)

**Required for Gate Pass**:
1. All 5 core tables exist (tenants, attribution_events, attribution_allocations, revenue_ledger, dead_events)
2. revenue_state_transitions table exists
3. ALL `auth_critical` columns present with correct type/nullability (2 columns)
4. ALL `privacy_critical` columns present with correct nullability (1 nullability fix)
5. ALL `processing_critical` columns present (13 columns)
6. ALL `financial_critical` columns present (10 columns)
7. ALL BLOCKING indexes exist (6 indexes)
8. ALL BLOCKING constraints exist (3 constraints)
9. ALL RLS policies enabled and correct

**Total BLOCKING Elements**: 28 columns + 1 table + 6 indexes + 3 constraints + 5 RLS policies = 43 elements

### 3.2 Validator Execution

```bash
# Run validator against test database after all corrective migrations
python scripts/validate-schema-compliance.py \
  --database-url postgresql://localhost:5432/skeldir_test \
  --output b0_3_validation_results.json \
  --verbose
```

### 3.3 Gate Decision Logic

```python
def b0_3_gate_decision(validation_results: dict) -> GateDecision:
    """
    B0.3 exit gate logic.
    
    PASS if:
    - exit_code == 0 (no divergences)
    - OR exit_code == 2 (only HIGH severity, no BLOCKING)
    
    FAIL if:
    - exit_code == 1 (one or more BLOCKING divergences)
    """
    if validation_results["exit_code"] == 1:
        blocking_count = validation_results["summary"]["blocking"]
        return GateDecision(
            status="FAIL",
            reason=f"{blocking_count} BLOCKING divergences found",
            required_action="Apply corrective migrations to resolve all BLOCKING issues",
            blocking_issues=filter_blocking(validation_results["divergences"])
        )
    
    elif validation_results["exit_code"] == 2:
        high_count = validation_results["summary"]["high"]
        return GateDecision(
            status="WARN_PASS",
            reason=f"{high_count} HIGH divergences found but no BLOCKING issues",
            required_action="Document HIGH severity gaps and plan remediation",
            notes="B0.3 passes but with degraded analytics capabilities"
        )
    
    else:
        return GateDecision(
            status="PASS",
            reason="Zero critical divergences",
            required_action="Proceed to B0.4"
        )
```

### 3.4 Gate Evidence Requirements

**To mark B0.3 as complete, provide**:
1. ✅ Validator output JSON showing exit_code = 0 or 2
2. ✅ `pg_dump --schema-only` snapshot showing all required tables/columns
3. ✅ Smoke test results (10+ tests) showing required operations work
4. ✅ Phase reviewer sign-off

**Gate Status**: B0.3 **BLOCKED** until all 4 evidence items provided and validator passes.

---

## 4. B0.4 Exit Gate Logic

### 4.1 Required Conditions

**Phase Name**: B0.4 (Ingestion Service)

**Prerequisite**: B0.3 must PASS

**Additional Required for Gate Pass**:
1. B0.3 validator still passes (no regression)
2. Idempotent ingestion smoke test passes:
   ```python
   # Test: Can insert with idempotency_key
   result = await db.execute(
       "INSERT INTO attribution_events (tenant_id, idempotency_key, event_type, channel, session_id, event_timestamp, raw_payload) "
       "VALUES ($1, $2, $3, $4, $5, $6, $7) "
       "ON CONFLICT (idempotency_key) DO NOTHING RETURNING id",
       test_tenant_id, "test_idempotency_key", "purchase", "google_search", test_session_id, now(), {}
   )
   assert result is not None  # First insert succeeds
   
   result2 = await db.execute(...same INSERT...)
   assert result2 is None  # Duplicate rejected via ON CONFLICT
   ```
3. Event classification smoke test passes (can insert with event_type and channel)
4. Session tracking smoke test passes (cannot insert with NULL session_id)

### 4.2 Gate Decision Logic

```python
def b0_4_gate_decision(validation_results: dict, smoke_tests: dict) -> GateDecision:
    """
    B0.4 exit gate logic.
    
    PASS if:
    - B0.3 validator still passes (exit_code 0 or 2)
    - All 3 smoke tests pass
    
    FAIL if:
    - B0.3 regression (exit_code 1)
    - Any smoke test fails
    """
    if validation_results["exit_code"] == 1:
        return GateDecision(
            status="FAIL",
            reason="B0.3 schema regression detected",
            required_action="Fix schema regression before proceeding"
        )
    
    failed_tests = [t for t, result in smoke_tests.items() if not result["passed"]]
    if failed_tests:
        return GateDecision(
            status="FAIL",
            reason=f"Smoke tests failed: {', '.join(failed_tests)}",
            required_action="Fix failing smoke tests"
        )
    
    return GateDecision(status="PASS", reason="B0.4 requirements met")
```

### 4.3 Gate Evidence Requirements

1. ✅ B0.3 validator output (regression check)
2. ✅ 3 smoke test results (idempotency, classification, session tracking)
3. ✅ Phase reviewer sign-off

---

## 5. B0.5 Exit Gate Logic

### 5.1 Required Conditions

**Phase Name**: B0.5 (Background Workers)

**Prerequisite**: B0.4 must PASS

**Additional Required for Gate Pass**:
1. B0.3 + B0.4 validators still pass (no regression)
2. Worker queue smoke test passes:
   ```python
   # Test: Can query for pending events
   pending = await db.fetch(
       "SELECT * FROM attribution_events WHERE processing_status = 'pending' LIMIT 10"
   )
   assert len(pending) > 0
   ```
3. Retry logic smoke test passes (can update retry_count)
4. Dead events remediation smoke test passes (can query by remediation_status)

### 5.2 Gate Decision Logic

Similar to B0.4 but checks B0.3 + B0.4 + B0.5 specific smoke tests.

---

## 6. B2.x Exit Gate Logic

### 6.1 B2.1 (Attribution Models)

**Prerequisite**: B0.3 + B0.4 PASS

**Additional Required**:
- Can INSERT attribution_allocations with confidence_score (HIGH severity, not BLOCKING)
- Smoke test: Statistical metadata insertion

**Gate**: WARN_PASS allowed if statistical columns missing (degraded mode)

### 6.2 B2.2 (Webhook Ingestion)

**Prerequisite**: B0.3 PASS

**Additional Required**:
- revenue_ledger.transaction_id exists and is UNIQUE
- Smoke test: Transaction idempotency (ON CONFLICT)

**Gate**: FAIL if transaction_id missing (BLOCKING)

### 6.3 B2.3 (Currency Conversion)

**Prerequisite**: B0.3 + B2.2 PASS

**Additional Required**:
- revenue_ledger.currency exists (NOT NULL)
- Smoke test: Multi-currency insertion

**Gate**: FAIL if currency column missing (BLOCKING)

### 6.4 B2.4 (Refund Tracking)

**Prerequisite**: B0.3 + B2.2 PASS

**Additional Required**:
- revenue_ledger.state exists with CHECK constraint
- revenue_state_transitions table exists
- Smoke test: State transition recording

**Gate**: FAIL if state machine missing (BLOCKING)

---

## 7. Regression Prevention

### 7.1 Regression Gate

**Trigger**: Before EVERY phase completion

**Logic**: Run validators for ALL completed phases

**Example**: Before marking B2.2 complete, run:
```bash
# Validate B0.3 (no regression)
python scripts/validate-schema-compliance.py --phase b0.3

# Validate B0.4 (no regression)
python scripts/validate-schema-compliance.py --phase b0.4

# Validate B2.2 (current phase)
python scripts/validate-schema-compliance.py --phase b2.2
```

**Gate Decision**: If ANY prior phase regresses (exit_code 1), current phase **BLOCKED**.

### 7.2 Regression Test Matrix

| Current Phase | Must Validate | Regression Tolerance |
|---------------|---------------|---------------------|
| B0.4 | B0.3 | Zero (any regression blocks) |
| B0.5 | B0.3, B0.4 | Zero |
| B2.2 | B0.3 | Zero |
| B2.3 | B0.3, B2.2 | Zero |
| B2.4 | B0.3, B2.2 | Zero |

---

## 8. CI/CD Gate Integration

### 8.1 Pull Request Gate

**Workflow**: `.github/workflows/schema-validation.yml`

**Trigger**: On PR modifying `alembic/versions/**`

**Steps**:
1. Spin up test PostgreSQL
2. Apply all migrations (`alembic upgrade head`)
3. Run schema validator
4. Parse exit code

**Gate Decision**:
```yaml
- name: Check exit code
  run: |
    EXIT_CODE=$(jq '.exit_code' validation_results.json)
    if [ $EXIT_CODE -eq 1 ]; then
      echo "❌ FAIL: BLOCKING divergences found"
      exit 1
    elif [ $EXIT_CODE -eq 2 ]; then
      echo "⚠️ WARN: HIGH divergences found (non-blocking)"
      exit 0
    else
      echo "✅ PASS: No critical divergences"
      exit 0
    fi
```

**PR Merge Policy**: Cannot merge if exit code = 1

### 8.2 Deployment Gate

**Trigger**: Before deploying migrations to staging/production

**Script**: `scripts/pre-deploy-validation.sh`

```bash
#!/bin/bash
# Pre-deployment schema validation gate

set -e

echo "Running schema compliance validation..."

python scripts/validate-schema-compliance.py \
  --database-url $DATABASE_URL \
  --output pre_deploy_validation.json \
  --verbose

EXIT_CODE=$(jq '.exit_code' pre_deploy_validation.json)

if [ $EXIT_CODE -eq 1 ]; then
  echo "❌ DEPLOYMENT BLOCKED: BLOCKING divergences found"
  exit 1
elif [ $EXIT_CODE -eq 2 ]; then
  echo "⚠️ WARNING: HIGH divergences found (deployment allowed but degraded)"
  exit 0
else
  echo "✅ Deployment approved: Schema is compliant"
  exit 0
fi
```

---

## 9. Manual Gate Override

**Policy**: **NO MANUAL OVERRIDES PERMITTED**

Any attempt to bypass gate must:
1. First update canonical spec with architectural rationale
2. Get approval from 2+ technical leads
3. Document exception in EXCEPTIONS.md
4. Create ticket to remediate within 1 sprint

**Exception Log**: `db/schema/EXCEPTIONS.md`

**Exception Template**:
```markdown
## Exception: [Description]

**Date**: 2025-11-XX
**Approved By**: [Name1], [Name2]
**Reason**: [Architectural rationale]
**Affected Elements**: [List of divergences]
**Remediation Ticket**: [TICKET-XXX]
**Remediation Deadline**: [Date]
```

---

## 10. Gate Status Tracking

### 10.1 Gate Status Dashboard

**Location**: `db/schema/GATE_STATUS.md` (auto-generated)

**Format**:
```markdown
# Schema Compliance Gate Status

Last Updated: 2025-11-15 10:45:00

| Phase | Status | Last Validated | Exit Code | Divergences (B/H/M/L) | Next Action |
|-------|--------|----------------|-----------|---------------------|-------------|
| B0.3 | ❌ BLOCKED | 2025-11-15 | 1 | 28/10/3/1 | Apply corrective migrations |
| B0.4 | ⏸️ WAITING | N/A | N/A | N/A | B0.3 must pass first |
| B0.5 | ⏸️ WAITING | N/A | N/A | N/A | B0.4 must pass first |
| B2.2 | ⏸️ WAITING | N/A | N/A | N/A | B0.3 must pass first |
```

### 10.2 Gate Status Updates

**Update Triggers**:
- After validator run
- After migration application
- After phase completion claim
- Daily (automated)

---

## Summary

**Core Principle**: No phase progression without schema compliance

**Enforcement**: Automated validator + CI/CD gates + manual sign-off

**Regression Prevention**: Validate all prior phases before current phase completion

**Override Policy**: No manual overrides without architectural rationale and remediation plan

**Evidence Required**: Validator JSON + smoke tests + pg_dump snapshot + reviewer sign-off

**Status**: ✅ **EXIT GATE LOGIC DEFINED AND BINDING**

**Effective Date**: 2025-11-15  
**Approved By**: AI Assistant (Claude) - Acting as Technical Governance Lead



