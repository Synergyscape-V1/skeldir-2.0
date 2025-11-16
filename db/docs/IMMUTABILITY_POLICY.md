# Immutability Policy for Revenue Ledger

**Document Version**: 1.0  
**Date**: 2025-11-13  
**Purpose**: Define immutability policy for revenue_ledger table

---

## Policy Statement

**`revenue_ledger` rows are immutable** - once a ledger entry is created, it cannot be updated in place. Corrections must be made via new ledger entries (additive corrections) or through an admin-gated path.

---

## Rationale

Revenue ledger entries represent **auditable financial records**. Immutability ensures:
1. **Audit Trail Integrity**: Historical ledger entries cannot be modified, preserving audit trail
2. **Reconciliation Accuracy**: Reconciliation processes can rely on ledger entries not changing
3. **Regulatory Compliance**: Financial records must be immutable for regulatory compliance
4. **Deterministic Accounting**: Immutability supports deterministic revenue accounting

---

## Implementation

### Database-Level Enforcement (Required)

**GRANT Policy** (Target State - Phase 2.5):
- `app_rw` role: `SELECT`, `INSERT` only (no `UPDATE` or `DELETE`)
- `app_ro` role: `SELECT` only
- `app_admin` role: `SELECT`, `INSERT` (no `UPDATE` or `DELETE`, or highly restricted if needed)
- `migration_owner` role: Full privileges (for emergency repairs only, with audit trail requirement)

**Current State** (Phase 2.2):
- `app_rw` role: `SELECT`, `INSERT`, `UPDATE`, `DELETE` (from `alembic/versions/202511131121_add_grants.py:71`)
- **Gap**: UPDATE/DELETE privileges must be revoked in hardening migration (Phase 2.5)

**Guard Trigger** (Phase 2.6):
- Function: `fn_ledger_prevent_mutation()`
- Trigger: `BEFORE UPDATE OR DELETE ON revenue_ledger FOR EACH ROW`
- Behavior: Raises exception for UPDATE/DELETE attempts (except `migration_owner` with audit requirement)
- Rationale: Defense-in-depth beyond GRANTs; prevents unauthorized or accidental modification

**Note**: Both GRANT revocation and guard trigger are required for complete DB-level enforcement. GRANTs are the first line of defense; triggers provide defense-in-depth.

### Correction Patterns

#### Pattern 1: Additive Corrections (Recommended)

Create a new ledger entry to correct an error:

```sql
-- Original (incorrect) entry
INSERT INTO revenue_ledger (tenant_id, revenue_cents, is_verified, posted_at)
VALUES ('...', 10000, true, now());

-- Correction entry (additive)
INSERT INTO revenue_ledger (tenant_id, revenue_cents, is_verified, posted_at)
VALUES ('...', -500, true, now()); -- Negative entry to correct

-- Net result: 10000 - 500 = 9500 (corrected amount)
```

#### Pattern 2: Admin-Gated Corrections (Emergency Only)

For extraordinary corrections requiring in-place modification:

1. Admin reviews incorrect entry
2. Admin uses `migration_owner` role (not `app_rw` or `app_admin`)
3. Admin creates correction entry (additive) OR performs in-place correction
4. Admin documents correction reason in audit log
5. Correction entry linked to original via metadata
6. All such actions must be recorded in an audit log

**Use Cases for Emergency Path**:
- Data corruption requiring in-place correction
- Catastrophic data fix under formal runbook
- Extraordinary conditions only

**Audit Requirement**: All emergency repairs must be logged and auditable. The `migration_owner` role exception in the guard trigger requires explicit audit trail documentation.

---

## Exceptions

**Emergency Repair Path** (via `migration_owner` only):
- **Condition**: Data corruption requiring in-place correction, with audit trail
- **Process**: 
  1. Admin reviews incorrect entry
  2. Admin uses `migration_owner` role (bypasses guard trigger)
  3. Admin performs correction with audit log entry
  4. Correction documented and approved by Backend Lead + Product Owner
- **Audit Trail**: All emergency repairs must be logged and auditable

**No Other Exceptions**: Immutability is absolute for application roles (`app_rw`, `app_ro`, `app_admin`). There are no other exceptions to this policy.

---

## Migration Impact

**Existing Data**: If `revenue_ledger` contains existing data, immutability policy applies retroactively. Existing rows cannot be updated.

**Future Migrations**: Any migration that attempts to UPDATE `revenue_ledger` must be reviewed and approved by Backend Lead + Product Owner.

---

## Cross-References

- **Table**: `revenue_ledger`
- **Migration**: `alembic/versions/202511131250_enhance_revenue_ledger.py`
- **GRANT Policy**: See `db/docs/ROLES_AND_GRANTS.md`


