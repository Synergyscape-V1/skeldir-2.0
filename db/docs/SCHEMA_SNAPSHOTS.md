# Schema Snapshots & Drift Detection

This document defines the process for creating schema snapshots and detecting drift.

## Snapshot Format

**Tool**: `pg_dump --schema-only`

**Command**:
```bash
pg_dump --schema-only --no-owner --no-privileges \
    -h localhost -U user -d skeldir \
    > db/snapshots/schema_YYYYMMDD_HHMMSS.sql
```

**Options**:
- `--schema-only`: Only schema, no data
- `--no-owner`: Exclude ownership information (reduces diff noise)
- `--no-privileges`: Exclude privilege information (reduces diff noise)

**Rationale**: Schema-only snapshots enable comparison without data, and excluding owner/privileges reduces diff noise.

## Naming Convention

**Pattern**: `schema_YYYYMMDD_HHMMSS.sql`

**Examples**:
- `schema_20251112_130200.sql` - Snapshot from 2025-11-12 13:02:00
- `schema_20251112_140000.sql` - Snapshot from 2025-11-12 14:00:00

**Rationale**: Timestamp prefix enables chronological ordering and identification.

## Snapshot Frequency

**Per Release**: Create snapshot before and after each release

**Before Major Migrations**: Create snapshot before applying major migrations (e.g., table additions, column type changes)

**After Major Migrations**: Create snapshot after applying major migrations to establish new baseline

**Rationale**: Snapshots enable rollback and drift detection.

## Diff Tool and Ignore Rules

### Tool Selection

**Options**:
- `sqldef`: Schema diff tool (recommended)
- `migra`: PostgreSQL migration tool
- `text diff`: Simple text comparison with ignore rules

**Recommended**: `sqldef` or `migra` for structured diff analysis

### Ignore Rules

**Ignore the following differences** (reduce diff noise):
- Owner differences: `--no-owner` flag in pg_dump
- Privilege order: `--no-privileges` flag in pg_dump
- Comment formatting: Minor whitespace differences
- Index order: Index creation order (functionally equivalent)

**Example Ignore Rules** (for text diff):
```bash
# Ignore owner lines
grep -v "^-- Owner:" schema_*.sql

# Ignore privilege lines
grep -v "^-- Privileges:" schema_*.sql

# Ignore comment formatting differences
# (handled by diff tool configuration)
```

**Rationale**: Ignore rules focus diff on meaningful schema changes, not formatting or metadata.

## Drift Detection Process

### Manual Rehearsal Procedure

**Step 1: Generate Snapshot from Migrations**
```bash
# Apply migrations to fresh database
alembic upgrade head

# Generate snapshot
pg_dump --schema-only --no-owner --no-privileges \
    -h localhost -U user -d skeldir \
    > db/snapshots/schema_from_migrations.sql
```

**Step 2: Compare with Last Blessed Snapshot**
```bash
# Compare snapshots
diff db/snapshots/schema_20251112_130200.sql \
     db/snapshots/schema_from_migrations.sql

# Or use sqldef/migra for structured diff
sqldef diff schema_20251112_130200.sql schema_from_migrations.sql
```

**Step 3: Analyze Differences**
- **Expected Changes**: Differences from new migrations (should match migration files)
- **Unexpected Changes**: Differences not in migrations (drift detected)
- **Formatting Only**: Differences in formatting only (ignore)

**Step 4: Resolve Drift**
- If drift detected: Investigate source (manual DDL, migration errors, etc.)
- Fix drift: Create migration to align schema
- Re-validate: Re-run drift detection

### CI Integration (Future)

**Workflow**: `.github/workflows/schema-drift-check.yml` (commented, not active)

**Spec**:
1. Generate snapshot from migrations (apply to fresh database)
2. Compare against last blessed snapshot
3. Fail CI if unexpected differences detected
4. Pass CI if differences match expected migrations

**Rationale**: Automated drift detection prevents schema drift from going unnoticed.

## Snapshot Storage

**Location**: `/db/snapshots/`

**Version Control**: Snapshots are committed to version control

**Retention**: Keep snapshots for last 10 releases (older snapshots can be archived)

**Rationale**: Version-controlled snapshots enable historical comparison and rollback.

## Blessed Snapshots

**Definition**: Snapshots that represent the "known good" schema state

**When to Bless**:
- After successful release deployment
- After major migration completion
- After drift resolution

**Procedure**:
1. Generate snapshot after successful deployment
2. Commit snapshot to version control
3. Tag snapshot as "blessed" (via commit message or tag)
4. Use blessed snapshot as baseline for future drift detection

**Rationale**: Blessed snapshots provide authoritative baseline for drift detection.





