# Migration Safety Checklist

This document defines safety procedures for database migrations.

## Pre-Migration Checks

### 1. Backup Verification

**Requirement**: Verify backup exists and is recent (within 24 hours for production)

**Procedure**:
- Check backup system status
- Verify backup can be restored (test restore in staging)
- Document backup location and restore procedure

**Production**: Mandatory before any migration

### 2. Lock Timeout Configuration

**Requirement**: Set `lock_timeout = '30s'` to prevent long-running locks

**Procedure**:
```sql
SET lock_timeout = '30s';
```

**Rationale**: Prevents migrations from holding locks indefinitely, causing application timeouts.

### 3. Statement Timeout Configuration

**Requirement**: Set `statement_timeout = '5min'` for long-running operations

**Procedure**:
```sql
SET statement_timeout = '5min';
```

**Rationale**: Prevents migrations from running indefinitely, allows monitoring and intervention.

## Post-Migration Checks

### 1. Schema Validation

**Requirement**: Verify schema changes are applied correctly

**Procedure**:
- Compare actual schema to expected schema (via `\d` or `pg_dump --schema-only`)
- Verify all tables, columns, indexes, constraints exist
- Verify RLS policies are enabled (if applicable)

### 2. Index Usage Verification

**Requirement**: Verify indexes are created and usable

**Procedure**:
- Check index existence: `SELECT * FROM pg_indexes WHERE tablename = 'table_name';`
- Verify index usage: `EXPLAIN ANALYZE SELECT ...` (check for index scans)
- Verify index statistics: `ANALYZE table_name;`

### 3. RLS Policy Verification

**Requirement**: Verify RLS policies are active and correct

**Procedure**:
- Check RLS enabled: `SELECT tablename, rowsecurity FROM pg_tables WHERE tablename = 'table_name';`
- Verify policy exists: `SELECT * FROM pg_policies WHERE tablename = 'table_name';`
- Test tenant isolation: Query as different tenants, verify data isolation

## Long-Running Operations Guidance

### Add-Then-Backfill-Then-Swap Pattern (Zero-Downtime)

**Use Case**: Adding NOT NULL column to existing table with data

**Pattern**:
1. **Add Column** (nullable): `ALTER TABLE table_name ADD COLUMN new_column INTEGER NULL;`
2. **Backfill Data**: `UPDATE table_name SET new_column = <default_value> WHERE new_column IS NULL;`
3. **Add NOT NULL Constraint**: `ALTER TABLE table_name ALTER COLUMN new_column SET NOT NULL;`
4. **Add Default**: `ALTER TABLE table_name ALTER COLUMN new_column SET DEFAULT <default_value>;`

**Rationale**: Prevents table locks during backfill, enables zero-downtime migrations.

**Example**:
```sql
-- Step 1: Add nullable column
ALTER TABLE attribution_events ADD COLUMN processing_status VARCHAR(20) NULL;

-- Step 2: Backfill existing rows
UPDATE attribution_events SET processing_status = 'processed' WHERE processing_status IS NULL;

-- Step 3: Add NOT NULL constraint
ALTER TABLE attribution_events ALTER COLUMN processing_status SET NOT NULL;

-- Step 4: Add default for new rows
ALTER TABLE attribution_events ALTER COLUMN processing_status SET DEFAULT 'pending';
```

## Destructive-Change Approval Policy

**Destructive Changes Require Approval**:
- DROP TABLE
- DROP COLUMN
- DROP INDEX (if heavily used)
- ALTER COLUMN TYPE (data conversion required)
- TRUNCATE TABLE

**Approval Matrix**:
- **Dev/Staging**: Backend Lead approval
- **Production**: Backend Lead + Product Owner approval

**Procedure**:
1. Document destructive change in migration comments
2. Create ADR if change is significant
3. Obtain approval before merging PR
4. Schedule migration during maintenance window (if production)

## Environment-Specific Procedures

### Local Development

**Requirements**:
- Backup not required (can recreate database)
- Timeouts optional (for faster iteration)
- Approval not required (developer discretion)

### CI/CD

**Requirements**:
- Backup not required (test database)
- Timeouts recommended (prevent CI timeouts)
- Approval not required (automated testing)

### Staging

**Requirements**:
- Backup recommended (before major changes)
- Timeouts required (prevent staging downtime)
- Backend Lead approval (for destructive changes)

### Production

**Requirements**:
- Backup mandatory (before any migration)
- Timeouts required (prevent production downtime)
- Backend Lead + Product Owner approval (for destructive changes)
- Maintenance window (for major changes)

## Dry-Run Procedure

**Always run dry-run before applying migrations**:

```bash
# Generate SQL without applying
alembic upgrade --sql head

# Review generated SQL
# Verify:
# - No unexpected DDL
# - Timeouts are set
# - Rollback is safe
# - No data loss
```

**Rationale**: Dry-run reveals migration behavior without risk.

## Rollback Procedure

**Before applying migration, verify rollback works**:

```bash
# Test rollback locally
alembic upgrade head
alembic downgrade -1

# Verify database state is restored
# Verify no data loss
```

**Rationale**: Ensures rollback capability before production deployment.

## Emergency Procedures

**If migration fails in production**:

1. **Stop Migration**: Cancel migration if possible
2. **Assess Impact**: Determine what changes were applied
3. **Rollback**: Run `alembic downgrade -1` if safe
4. **Restore Backup**: If rollback is not safe, restore from backup
5. **Document**: Document failure and remediation steps

**Contact**: Backend Lead + DevOps Lead for production migration failures





