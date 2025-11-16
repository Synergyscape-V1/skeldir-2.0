# Schema Migration Pull Request

## Migration Details

- **Migration File**: `alembic/versions/YYYYMMDDHHMM_description.py`
- **Type**: [ ] Versioned DDL Change [ ] Repeatable Migration [ ] Extension Enablement
- **Description**: Brief description of schema changes

## Governance Compliance Checklist

### Style Guide Compliance
- [ ] Table/column names follow snake_case convention
- [ ] Primary key uses `id uuid PRIMARY KEY DEFAULT gen_random_uuid()`
- [ ] Timestamps use `timestamptz NOT NULL DEFAULT now()`
- [ ] Boolean columns use `is_*`/`has_*`/`can_*` prefixes
- [ ] Foreign keys use `{table}_id` naming
- [ ] Check constraints use `ck_{table}_{column}_{condition}` naming
- [ ] Indexes use `idx_{table}_{columns}` naming
- [ ] Revenue stored as `INTEGER` (cents), not `DECIMAL`/`FLOAT`
- [ ] JSONB columns have GIN indexes (if applicable)

### Contract Mapping Verification
- [ ] Type mappings follow `CONTRACT_TO_SCHEMA_MAPPING.md`
- [ ] Required contract fields are `NOT NULL` in database
- [ ] Enum handling follows rulebook (CHECK vs lookup table)
- [ ] Contract source referenced in migration comments

### Roles/GRANTs Applied
- [ ] `app_rw` role has appropriate grants
- [ ] `app_ro` role has appropriate grants
- [ ] `app_admin` role has appropriate grants (if applicable)
- [ ] Grants follow least-privilege principle

### RLS Policies Applied
- [ ] RLS enabled on all multi-tenant tables
- [ ] `tenant_isolation_policy` created using template pattern
- [ ] Policy uses `current_setting('app.current_tenant_id')::UUID`
- [ ] RLS policy documented in comments

### Comments Present on All Objects
- [ ] `COMMENT ON TABLE` for all tables (Purpose, Data Class, Ownership)
- [ ] `COMMENT ON COLUMN` for all columns (Purpose, Data Class)
- [ ] `COMMENT ON POLICY` for all RLS policies
- [ ] Comments follow minimum content requirements

### Migration Safety Checklist Reviewed
- [ ] Pre-migration checks completed (backup, timeouts)
- [ ] Post-migration checks planned (schema validation, index verification, RLS verification)
- [ ] Long-running operations use add-then-backfill-then-swap pattern (if applicable)
- [ ] Destructive changes approved (if applicable)

### Extension Allow-List Compliance
- [ ] No extensions used (or)
- [ ] Extension is in allow-list (`EXTENSION_ALLOWLIST.md`)
- [ ] Extension rationale documented
- [ ] Extension approved per environment policy

### Snapshot Drift Check Acknowledged
- [ ] Snapshot will be generated after migration
- [ ] Drift detection will be run
- [ ] Any drift will be resolved before merge

### Events Append-Only Verification
- [ ] `app_rw` has no UPDATE/DELETE on `attribution_events` (verify via `\dp attribution_events` or `SELECT grantee, privilege_type FROM information_schema.table_privileges WHERE table_name = 'attribution_events' AND grantee = 'app_rw'`)
- [ ] Guard trigger `trg_events_prevent_mutation` present (if implemented, verify via `SELECT * FROM pg_trigger WHERE tgname = 'trg_events_prevent_mutation'`)
- [ ] Any migration touching `attribution_events` preserves append-only GRANTs (no re-granting UPDATE/DELETE)
- [ ] Trigger not removed/weakened without ADR (verify ADR exists if trigger removed)
- [ ] Table COMMENT updated with append-only statement (verify via `SELECT obj_description('attribution_events'::regclass, 'pg_class')`)

**Verification Commands**:
```sql
-- Verify app_rw GRANTs (should show SELECT, INSERT only, no UPDATE/DELETE)
SELECT grantee, privilege_type 
FROM information_schema.table_privileges 
WHERE table_name = 'attribution_events' AND grantee = 'app_rw';

-- Verify trigger exists (if implemented)
SELECT * FROM pg_trigger WHERE tgname = 'trg_events_prevent_mutation';

-- Verify table COMMENT contains append-only statement
SELECT obj_description('attribution_events'::regclass, 'pg_class');
```

### Ledger Immutability Verification
- [ ] `app_rw` has no UPDATE/DELETE on `revenue_ledger` (verify via `\dp revenue_ledger` or `SELECT grantee, privilege_type FROM information_schema.table_privileges WHERE table_name = 'revenue_ledger' AND grantee = 'app_rw'`)
- [ ] Guard trigger `trg_ledger_prevent_mutation` present (if implemented, verify via `SELECT * FROM pg_trigger WHERE tgname = 'trg_ledger_prevent_mutation'`)
- [ ] Any migration touching `revenue_ledger` preserves immutability GRANTs (no re-granting UPDATE/DELETE)
- [ ] Trigger not removed/weakened without ADR (verify ADR exists if trigger removed)
- [ ] CHECK constraints on `revenue_cents` and traceability (allocation_id/correlation_id) remain intact
- [ ] Table COMMENT updated with immutability statement (verify via `SELECT obj_description('revenue_ledger'::regclass, 'pg_class')`)

**Verification Commands**:
```sql
-- Verify app_rw GRANTs (should show SELECT, INSERT only, no UPDATE/DELETE)
SELECT grantee, privilege_type 
FROM information_schema.table_privileges 
WHERE table_name = 'revenue_ledger' AND grantee = 'app_rw';

-- Verify trigger exists (if implemented)
SELECT * FROM pg_trigger WHERE tgname = 'trg_ledger_prevent_mutation';

-- Verify table COMMENT contains immutability statement
SELECT obj_description('revenue_ledger'::regclass, 'pg_class');

-- Verify CHECK constraints exist
SELECT conname, contype 
FROM pg_constraint 
  WHERE conrelid = 'revenue_ledger'::regclass 
  AND contype = 'c';
```

### Channel Taxonomy Verification
- [ ] New channels must be added via `channel_taxonomy` table (verify no hard-coded channel strings in allocations or read models)
- [ ] Any new channel requires an update to `channel_mapping.yaml` (verify mapping file updated if new channels added)
- [ ] FK constraint to `channel_taxonomy.code` present (if touching `attribution_allocations.channel_code`, verify via `SELECT conname, contype FROM pg_constraint WHERE conrelid = 'attribution_allocations'::regclass AND contype = 'f'`)
- [ ] No CHECK constraints on channel values (verify CHECK constraint removed, replaced by FK)
- [ ] Contract alignment: If exposing channel fields, verify they reference `channel_taxonomy.code` semantics

**Verification Commands**:
```sql
-- Verify FK constraint exists (if channel_code column exists)
SELECT conname, contype 
FROM pg_constraint 
WHERE conrelid = 'attribution_allocations'::regclass 
  AND contype = 'f'
  AND conname LIKE '%channel%';

-- Verify no CHECK constraint on channel (should be removed)
SELECT conname, contype 
FROM pg_constraint 
WHERE conrelid = 'attribution_allocations'::regclass 
  AND contype = 'c'
  AND conname LIKE '%channel%';

-- Verify channel_taxonomy table exists
SELECT tablename FROM pg_tables WHERE tablename = 'channel_taxonomy';
```

## Testing

- [ ] Migration tested locally
- [ ] Rollback tested (`alembic downgrade -1`)
- [ ] Dry-run reviewed (`alembic upgrade --sql head`)
- [ ] Multi-environment test completed (dev, test)

## Documentation

- [ ] Migration comments explain change and rationale
- [ ] Contract mapping documented (if applicable)
- [ ] Data dictionary will be updated (post-merge)
- [ ] ERD will be updated (post-merge)

## Approval

- [ ] Self-review completed
- [ ] Peer review completed
- [ ] Backend Lead approval (required)
- [ ] Product Owner approval (required for destructive changes)

---

**Reviewer Notes**: Add any additional comments or concerns here.


