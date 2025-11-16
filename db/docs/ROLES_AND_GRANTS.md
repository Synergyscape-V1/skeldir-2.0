# Roles and Grants Documentation

This document defines the database role model and least-privilege access patterns.

## Role Model

### app_rw (Read-Write Application Role)

**Purpose**: Read-write access for application (tenant-scoped queries)

**Capabilities**:
- SELECT, INSERT, UPDATE, DELETE on tenant-scoped tables
- Access limited by RLS policies (tenant isolation enforced)
- Cannot modify schema (no CREATE, ALTER, DROP)

**Usage**: Application service connections for normal operations

**Least-Privilege**: Only grants necessary for application operations, tenant-scoped via RLS

### app_ro (Read-Only Application Role)

**Purpose**: Read-only access for application (reporting, analytics)

**Capabilities**:
- SELECT on tenant-scoped tables
- Access limited by RLS policies (tenant isolation enforced)
- Cannot modify data or schema

**Usage**: Read-only service connections for reporting and analytics

**Least-Privilege**: Only SELECT grants, tenant-scoped via RLS

### app_admin (Administrative Operations Role)

**Purpose**: Administrative operations (limited)

**Capabilities**:
- SELECT, INSERT, UPDATE, DELETE on administrative tables
- Limited administrative operations (e.g., configuration updates)
- Cannot modify schema or RLS policies

**Usage**: Administrative service connections for configuration and management

**Least-Privilege**: Only grants necessary for administrative operations

### migration_owner (Migration Execution Role)

**Purpose**: Migration execution (superuser or equivalent)

**Capabilities**:
- Full database access for migration execution
- Can CREATE, ALTER, DROP tables, indexes, policies
- Can modify RLS policies
- Can create roles and grants

**Usage**: Alembic migration execution (via CI/CD or manual)

**Least-Privilege**: Only used during migration execution, not for application connections

## Least-Privilege Matrix

| Role | SELECT | INSERT | UPDATE | DELETE | CREATE | ALTER | DROP | RLS Modify |
|------|--------|--------|--------|--------|--------|-------|------|------------|
| app_rw | ✅ (RLS) | ✅ (RLS) | ✅ (RLS) | ✅ (RLS) | ❌ | ❌ | ❌ | ❌ |
| app_ro | ✅ (RLS) | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| app_admin | ✅ (admin) | ✅ (admin) | ✅ (admin) | ✅ (admin) | ❌ | ❌ | ❌ | ❌ |
| migration_owner | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

**Legend**:
- ✅ = Allowed
- ❌ = Forbidden
- (RLS) = Tenant-scoped via Row-Level Security
- (admin) = Administrative tables only

## GRANT Template for Tenant-Scoped Tables

**Standard Pattern**:
```sql
-- Grant to application read-write role
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE attribution_events TO app_rw;

-- Grant to application read-only role
GRANT SELECT ON TABLE attribution_events TO app_ro;

-- Grant usage on sequence (if using serial IDs)
GRANT USAGE, SELECT ON SEQUENCE attribution_events_id_seq TO app_rw;
```

**Rationale**: 
- `app_rw` needs full CRUD for normal operations
- `app_ro` needs only SELECT for reporting
- RLS policies enforce tenant isolation (no need for table-level tenant filtering)

## Role Creation Template

**Repeatable Migration Pattern**:
```sql
-- Create roles if not exists
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_rw') THEN
        CREATE ROLE app_rw;
    END IF;
    
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_ro') THEN
        CREATE ROLE app_ro;
    END IF;
    
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_admin') THEN
        CREATE ROLE app_admin;
    END IF;
END
$$;
```

**Rationale**: Repeatable migrations ensure roles exist across all environments.

## Security Considerations

1. **No Public Access**: Revoke default PUBLIC grants on all tables
2. **RLS Enforcement**: All tenant-scoped tables must have RLS enabled
3. **Role Rotation**: Roles should be rotated periodically (via repeatable migrations)
4. **Audit Logging**: All role changes should be logged for auditability

## Cross-References

- **RLS Template**: See `db/migrations/templates/rls_policy.py.template` for RLS policy patterns
- **Migration Templates**: See `db/migrations/templates/repeatable_migration.py.template` for role creation patterns





