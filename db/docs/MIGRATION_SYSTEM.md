# Migration System Documentation

## Tool Choice: Alembic

**Rationale**: Alembic is the standard migration tool for SQLAlchemy-based Python applications. It provides:
- Version control for database schema changes
- Rollback capability
- Environment-aware configuration
- Integration with SQLAlchemy models (when implemented)

**Alternatives Considered**:
- **Flyway**: Java-based, requires separate tooling
- **Liquibase**: XML/YAML-based, more verbose
- **Manual SQL scripts**: No versioning, no rollback, error-prone

**Tradeoffs**:
- **Alembic**: Python-native, integrates with SQLAlchemy, requires Python environment
- We choose Alembic for Python ecosystem integration and SQLAlchemy compatibility

## Naming Convention

Migration files follow the pattern: `YYYYMMDDHHMM_descriptive_slug.py`

Examples:
- `202511121302_baseline.py` - Initial baseline migration
- `202511121400_add_tenants_table.py` - Add tenants table
- `202511121500_add_attribution_events_table.py` - Add attribution events table

**Rationale**: Timestamp prefix ensures chronological ordering and prevents naming conflicts.

## Baseline Stamp Policy

The baseline migration (`202511121302_baseline.py`) represents the zero-state schema (empty database).

**Stamping a Fresh Environment**:
```bash
# Set DATABASE_URL environment variable
export DATABASE_URL="postgresql://user:password@localhost:5432/skeldir"

# Stamp the baseline
alembic stamp head
```

This creates the `alembic_version` table and sets the current revision to `baseline`, indicating that the database is at the baseline state (no domain tables yet).

## Version Graph Policy

**Linear Graph Only**: All migrations must form a linear chain. No branching or merging is allowed.

**Rationale**: 
- Linear history is easier to understand and audit
- Prevents complex merge conflicts in migrations
- Ensures deterministic migration path

**Enforcement**: 
- Alembic will detect and prevent multiple heads
- PR review must verify linear history
- `alembic check` command validates migration graph

## Environment Setup

### Local Development

1. Set `DATABASE_URL` environment variable:
   ```bash
   export DATABASE_URL="postgresql://user:password@localhost:5432/skeldir_dev"
   ```

2. Verify connection:
   ```bash
   alembic current
   ```

3. Apply baseline (if fresh database):
   ```bash
   alembic stamp head
   ```

### CI/CD

1. Set `DATABASE_URL` from CI secrets
2. Run migrations:
   ```bash
   alembic upgrade head
   ```

### Staging/Production

1. Set `DATABASE_URL` from environment secrets
2. **Always** run dry-run first:
   ```bash
   alembic upgrade --sql head
   ```
3. Review generated SQL
4. Apply migrations:
   ```bash
   alembic upgrade head
   ```

## Migration Workflow

1. **Create Migration**:
   ```bash
   alembic revision -m "descriptive_slug"
   ```

2. **Edit Migration**: Add upgrade/downgrade operations in the generated file

3. **Self-Review**: Verify migration follows style guide and governance rules

4. **Test Locally**: Apply migration to local database and verify

5. **Create PR**: Submit migration for peer review

6. **Peer Review**: Another developer reviews for correctness and compliance

7. **Approval**: Backend Lead approves migration

8. **Apply**: Migration is applied to target environment

## Rollback Policy

**All migrations must be reversible**. The `downgrade()` function must undo all changes made by `upgrade()`.

**Rationale**: 
- Enables recovery from problematic migrations
- Supports rollback during deployments
- Ensures migration safety

**Testing**: 
- Test rollback locally before PR submission
- Verify `alembic downgrade -1` works correctly

## Migration Templates

Templates are available in `/db/migrations/templates/`:
- `versioned_migration.py.template` - For versioned DDL changes
- `repeatable_migration.py.template` - For repeatable migrations (roles, RLS, policies)
- `enable_extension.py.template` - For enabling PostgreSQL extensions

## Safety Considerations

- **No Hardcoded Credentials**: All database connections use `DATABASE_URL` environment variable
- **Dry-Run First**: Always run `alembic upgrade --sql head` before applying migrations
- **Backup Before Production**: Always backup production database before applying migrations
- **Review Process**: All migrations require peer review and approval

See `MIGRATION_SAFETY_CHECKLIST.md` for detailed safety procedures.





