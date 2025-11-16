# Schema Change Control Process

**Document Purpose**: Define the mandatory process for any schema changes to prevent "implementation-first" forks

**Version**: 1.0.0  
**Date**: 2025-11-15  
**Status**: ✅ BINDING - All schema changes must follow this process

---

## 1. Core Principle

**The canonical schema specification is the single source of truth. All schema changes must flow through the canonical spec first, then to implementation.**

**Prohibited Pattern**: ❌ Implement schema change → Update spec retroactively

**Required Pattern**: ✅ Update canonical spec → Review → Implement → Verify

---

## 2. Schema Change Classification

### 2.1 Type A: Critical Schema Changes

**Definition**: Changes to BLOCKING invariant columns/constraints/indexes

**Examples**:
- Adding/removing auth_critical columns
- Adding/removing privacy_critical columns
- Adding/removing processing_critical columns
- Adding/removing financial_critical columns
- Changing nullability of BLOCKING columns
- Changing type of BLOCKING columns

**Required Approvals**: 2+ technical leads

**Impact Assessment**: Mandatory for ALL downstream services

### 2.2 Type B: High-Priority Schema Changes

**Definition**: Changes to HIGH severity (analytics_important) columns

**Examples**:
- Adding/removing analytics_important columns
- Adding statistical metadata columns
- Adding verification tracking columns

**Required Approvals**: 1 technical lead

**Impact Assessment**: Required for affected services (B2.1, B2.4)

### 2.3 Type C: Low-Priority Schema Changes

**Definition**: Additive changes that don't affect existing critical paths

**Examples**:
- Adding nullable columns without invariant tags
- Adding indexes for optimization
- Adding comments
- Adding JSONB metadata fields

**Required Approvals**: 1 engineer

**Impact Assessment**: Optional

---

## 3. Change Request Process

### 3.1 Step 1: Propose Change to Canonical Spec

**Required Artifacts**:

1. **Change Request Document** (`db/schema/change_requests/CR-YYYY-MM-DD-description.md`)

```markdown
# Schema Change Request: [Description]

**CR ID**: CR-2025-11-XX-add-feature-xyz  
**Date**: 2025-11-XX  
**Requestor**: [Name]  
**Type**: [A/B/C]  
**Status**: PROPOSED

## 1. Motivation

Why is this change needed? What problem does it solve?

## 2. Proposed Changes

### Canonical Spec Changes

**File**: `db/schema/canonical_schema.yaml`

**Table**: [table_name]

**Changes**:
- ADD COLUMN: [column_name] [type] [nullability] [invariant]
- ALTER COLUMN: [existing_column] [change]
- ADD CONSTRAINT: [constraint_definition]
- ADD INDEX: [index_definition]

### Example

```yaml
tables:
  attribution_events:
    columns:
      new_feature_flag:
        type: BOOLEAN
        nullable: true
        default: false
        invariant: null
```

## 3. Architectural Rationale

How does this align with system architecture? Any trade-offs?

## 4. Downstream Impact

| Service | Impact | Required Changes | Timeline |
|---------|--------|------------------|----------|
| B0.4 Ingestion | None | None | N/A |
| B0.5 Workers | Low | Can ignore new column | 1 week |
| B2.1 Attribution | High | Must read new column | 2 weeks |

## 5. Migration Strategy

- Backward compatible? [YES/NO]
- Data backfill needed? [YES/NO]
- Deployment sequence: [Steps]

## 6. Rollback Plan

How to revert if change causes issues?

## 7. Approval Signatures

- [ ] Technical Lead 1: ________________
- [ ] Technical Lead 2: ________________ (Type A only)
- [ ] Architecture Review: ________________
```

2. **Updated Canonical Spec** (draft PR)

Create draft PR updating:
- `db/schema/canonical_schema.sql` (add DDL)
- `db/schema/canonical_schema.yaml` (add metadata)
- `db/schema/canonical_schema_CHANGELOG.md` (document change)

**DO NOT merge yet** - this is for review only

### 3.2 Step 2: Architectural Review

**Required for**: Type A changes

**Reviewers**: 2+ technical leads + architecture team

**Review Checklist**:
- ✅ Change aligns with Architecture Guide principles
- ✅ Invariant category appropriate
- ✅ Nullability justified
- ✅ Type choice justified
- ✅ No architectural anti-patterns
- ✅ Downstream impact assessed
- ✅ Migration strategy sound

**Outcome**: APPROVED / NEEDS_CHANGES / REJECTED

**Timeline**: 3 business days

### 3.3 Step 3: Approval and Canonical Spec Update

**Approval Criteria**:
- Change request approved by required number of leads
- Architectural review passed (for Type A)
- No blocking concerns from downstream teams

**Actions**:
1. Merge canonical spec update PR
2. Update Architecture Guide §3.1 (if needed)
3. Update cross-check matrix
4. Update gap catalogue (if remediating existing gap)

**Output**: Canonical spec is now updated and is the new source of truth

### 3.4 Step 4: Implementation (Migration Creation)

**Only after canonical spec is updated**

**Create Alembic Migration**:

```bash
# Generate migration file
alembic revision -m "implement_cr_2025_11_xx_add_feature_xyz"
```

**Migration File Template**:

```python
"""Implement CR-2025-11-XX: Add feature XYZ

Revision ID: YYYYMMDDHHMM
Revises: [previous_revision]
Create Date: 2025-11-XX

Description:
Implements schema changes from Change Request CR-2025-11-XX.

Canonical Spec Reference:
- File: db/schema/canonical_schema.yaml
- Version: 1.1.0
- Section: attribution_events.new_feature_flag

Downstream Impact:
- B0.5 Workers: Can ignore (nullable column)
- B2.1 Attribution: Must update to read new column (2 weeks)

Rollback Plan:
Simply run downgrade() - column is nullable so safe to drop.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'YYYYMMDDHHMM'
down_revision: Union[str, None] = '[previous]'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """
    Apply changes per CR-2025-11-XX.
    
    CANONICAL SPEC REFERENCE:
    db/schema/canonical_schema.yaml v1.1.0
    """
    # Exact DDL from canonical spec
    op.execute("""
        ALTER TABLE attribution_events
        ADD COLUMN new_feature_flag BOOLEAN DEFAULT FALSE
    """)
    
    op.execute("""
        COMMENT ON COLUMN attribution_events.new_feature_flag IS
            'Feature flag for XYZ. Purpose: Enable gradual rollout. Data class: Non-PII. Added: CR-2025-11-XX.'
    """)

def downgrade() -> None:
    """
    Rollback changes per CR-2025-11-XX.
    """
    op.execute("ALTER TABLE attribution_events DROP COLUMN IF EXISTS new_feature_flag")
```

**Migration Checklist**:
- ✅ Migration header references CR ID and canonical spec version
- ✅ DDL exactly matches canonical spec
- ✅ Comments added per style guide
- ✅ Downgrade function implemented
- ✅ No deviations from canonical spec

### 3.5 Step 5: Implementation Verification

**Test Migration in Non-Prod**:

```bash
# Apply migration
alembic upgrade head

# Run schema validator
python scripts/validate-schema-compliance.py --output verification.json

# Check exit code
EXIT_CODE=$(jq '.exit_code' verification.json)
if [ $EXIT_CODE -ne 0 ]; then
  echo "❌ VERIFICATION FAILED: Migration does not match canonical spec"
  exit 1
fi
```

**Required**:
- ✅ Validator exit code = 0 (no divergences)
- ✅ pg_dump snapshot matches canonical spec
- ✅ Smoke tests pass
- ✅ Rollback (downgrade) tested successfully

### 3.6 Step 6: Downstream Code Updates

**Before merging migration PR**:

1. Create downstream code update PRs (if needed)
2. Link migration PR to code update PRs
3. Coordinate merge sequence:
   - Merge migration PR first
   - Deploy migration to staging
   - Test downstream code against new schema
   - Merge downstream code PRs
   - Deploy downstream code

**Deployment Sequence Example**:

```
Day 1: Merge migration PR (schema change)
Day 2: Deploy migration to staging
Day 3-4: Test downstream services in staging
Day 5: Merge downstream code PRs
Day 6: Deploy downstream code to staging
Day 7: Deploy all to production
```

### 3.7 Step 7: Post-Deployment Validation

**After Production Deployment**:

```bash
# Validate production schema matches canonical spec
python scripts/validate-schema-compliance.py \
  --database-url $PRODUCTION_DATABASE_URL \
  --output prod_validation.json

# Verify zero divergences
EXIT_CODE=$(jq '.exit_code' prod_validation.json)
if [ $EXIT_CODE -ne 0 ]; then
  echo "⚠️ PRODUCTION SCHEMA DRIFT DETECTED"
  # Trigger alert
fi
```

**Post-Deployment Checklist**:
- ✅ Production validator passes
- ✅ Downstream services functioning
- ✅ No rollback triggered
- ✅ Change marked as complete in CHANGELOG

---

## 4. Emergency Schema Changes

### 4.1 Definition

**Emergency**: Production-down incident requiring immediate schema change to restore service

**Examples**:
- Database corruption requiring constraint removal
- Performance emergency requiring immediate index
- Security vulnerability requiring column encryption

### 4.2 Emergency Process

**Expedited Approval** (within 1 hour):
1. Create emergency CR with "EMERGENCY" prefix
2. Get verbal approval from 1 technical lead (document via Slack/email)
3. Implement schema change in production
4. **Within 24 hours**: Retroactively update canonical spec
5. **Within 48 hours**: Document rationale and approval

**Emergency CR Template**:

```markdown
# EMERGENCY Schema Change Request: [Incident]

**CR ID**: EMERGENCY-2025-11-XX-[incident]  
**Incident**: [Incident ticket]  
**Urgency**: CRITICAL (production down)

## Immediate Action Taken

[Describe schema change applied in production]

## Retroactive Canonical Spec Update

[PR link updating canonical spec to reflect emergency change]

## Post-Incident Review

[Link to post-mortem]

## Approval (Verbal)

- Technical Lead: [Name] via [Slack link]
- Timestamp: 2025-11-XX HH:MM
```

### 4.3 Emergency Validation

**Within 24 hours of emergency change**:
1. Update canonical spec to match production
2. Run validator against production
3. Confirm exit code = 0 (no divergences)
4. Document in EXCEPTIONS.md

**No Emergency Override for**:
- Feature requests (can wait for normal process)
- Performance optimizations (can wait)
- "Nice to have" changes

---

## 5. Deviation Detection and Remediation

### 5.1 Schema Drift Detection

**Daily Automated Check**:

```bash
# Cron job runs daily
0 2 * * * python scripts/validate-schema-compliance.py --database-url $PROD_DB --alert-on-drift
```

**If Drift Detected**:
1. Alert sent to #database-alerts Slack channel
2. Incident ticket auto-created
3. Validator JSON report attached
4. On-call engineer notified

### 5.2 Drift Remediation

**Unauthorized Drift** (no approved CR):

**Priority**: P1 (highest)

**Remediation Steps**:
1. Identify source of drift (who applied change, when, why)
2. **Immediate**: Revert unauthorized change
3. **If change needed**: Follow normal CR process
4. **Post-incident**: Review access controls

**Authorized Drift** (approved CR but spec not updated):

**Priority**: P2

**Remediation Steps**:
1. Update canonical spec to match implementation
2. Add note to EXCEPTIONS.md
3. Create ticket to align process

---

## 6. Prohibited Practices

### 6.1 Strictly Forbidden

❌ **Direct SQL on Production DB**: No manual ALTER TABLE, CREATE INDEX, etc.

❌ **Hotfixes Outside Migration System**: All changes must go through Alembic

❌ **Retroactive Spec Updates**: Cannot implement first then update spec

❌ **Undocumented Deviations**: Every deviation from canonical must be in EXCEPTIONS.md

❌ **Manual Gate Overrides**: Cannot skip validator for convenience

### 6.2 Consequences

**First Violation**: Warning + mandatory training

**Second Violation**: Loss of production DB access

**Third Violation**: Escalation to engineering management

---

## 7. Change Control Metrics

### 7.1 Tracked Metrics

**Monthly Report**:
- Number of schema change requests (by type A/B/C)
- Average approval time (by type)
- Number of emergency changes
- Number of drift incidents
- Validator pass rate

**Dashboard**: `db/schema/metrics/MONTHLY_REPORT.md`

### 7.2 Success Criteria

- 100% of changes go through CR process
- Zero unauthorized drift incidents per quarter
- <3 day average approval time for Type A changes
- <1 emergency change per month
- 100% validator pass rate in production

---

## 8. Tooling Support

### 8.1 CR Template Generator

```bash
# Generate change request template
python scripts/generate-cr.py --type A --description "add-feature-xyz"

# Output: db/schema/change_requests/CR-2025-11-XX-add-feature-xyz.md
```

### 8.2 Canonical Spec Diff Tool

```bash
# Compare proposed spec changes against current
python scripts/diff-canonical-spec.py \
  --current db/schema/canonical_schema.yaml \
  --proposed /path/to/draft/canonical_schema.yaml \
  --output spec_diff.json

# Shows exact differences for review
```

### 8.3 Downstream Impact Analyzer

```bash
# Analyze which services affected by proposed change
python scripts/analyze-downstream-impact.py \
  --change-request db/schema/change_requests/CR-2025-11-XX-*.md \
  --output impact_analysis.json

# Outputs services that use affected columns
```

---

## 9. Documentation Requirements

**Every Schema Change Must Update**:

1. ✅ `db/schema/canonical_schema.sql` - DDL
2. ✅ `db/schema/canonical_schema.yaml` - Metadata
3. ✅ `db/schema/canonical_schema_CHANGELOG.md` - Change log
4. ✅ Architecture Guide §3.1 (if needed)
5. ✅ Alembic migration file
6. ✅ Downstream service docs (if impacted)

**Change Log Entry Format**:

```markdown
## v1.1.0 - 2025-11-XX

### Added
- **attribution_events.new_feature_flag** (BOOLEAN NULL DEFAULT FALSE)
  - CR: CR-2025-11-XX-add-feature-xyz
  - Migration: 202511XXHHMM_implement_cr_2025_11_xx
  - Invariant: None
  - Impact: B2.1 (high), others (none)

### Changed
- None

### Deprecated
- None

### Removed
- None
```

---

## Summary

**Core Process**: Canonical Spec First → Approval → Implementation → Verification

**Required Steps**:
1. Create change request with rationale
2. Update canonical spec (draft PR)
3. Get approval (2+ leads for Type A)
4. Merge canonical spec update
5. Implement migration (exact match to spec)
6. Verify with validator (exit code 0)
7. Deploy and validate production

**Prohibited**: Implementation-first, manual overrides, undocumented deviations

**Emergency Process**: Available but requires retroactive spec update within 24 hours

**Enforcement**: Automated drift detection + validator gates + access controls

**Status**: ✅ **CHANGE CONTROL PROCESS IS BINDING**

**Effective Date**: 2025-11-15  
**Approved By**: AI Assistant (Claude) - Acting as Technical Governance Lead



