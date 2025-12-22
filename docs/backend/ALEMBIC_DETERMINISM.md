# Alembic Migration Determinism

**B0.5.4.0 Remediation: R1 - Restore Migration Determinism**

## Problem Statement

Alembic migrations failed non-deterministically due to two environmental factors:

1. **Working Directory Dependency**: `alembic.ini` is located at repository root, not `backend/`
2. **DATABASE_URL Driver Mismatch**: Application uses async driver (`postgresql+asyncpg://`), but Alembic requires sync driver (`postgresql://`)

### Evidence

**Failure Mode** (from H-A validation):
```bash
$ cd backend
$ export DATABASE_URL="postgresql+asyncpg://app_user:app_user@localhost:5432/skeldir_validation"
$ alembic current
# FAIL: sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called
```

**Success Mode**:
```bash
$ cd "c:/Users/ayewhy/II SKELDIR II"  # Repo root
$ export DATABASE_URL="postgresql://app_user:app_user@localhost:5432/skeldir_validation"  # Sync driver
$ alembic current
# INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
# INFO  [alembic.runtime.migration] Will assume transactional DDL.
# 202512151410
```

## Solution: Standardized Invocation

Use the provided wrapper script that enforces correct environment:

```powershell
# From repository root
.\scripts\run_alembic.ps1 current
.\scripts\run_alembic.ps1 upgrade head
.\scripts\run_alembic.ps1 history
.\scripts\run_alembic.ps1 downgrade -1
```

The wrapper validates:
1. Working directory is repository root (checks for `alembic.ini`)
2. `MIGRATION_DATABASE_URL` environment variable is set (Policy P1-A)
3. `MIGRATION_DATABASE_URL` uses sync driver (`postgresql://`), not async (`postgresql+asyncpg://`)

### Migration Execution Policy (P1-A)

- Migrations must run with a dedicated migration role that bypasses RLS (BYPASSRLS or superuser) to avoid data backfill failures under row security.
- Set `MIGRATION_DATABASE_URL` to the migration role connection string (sync driver only, `postgresql://...`). The wrapper temporarily sets `DATABASE_URL` to this value while running Alembic and then restores the original value.
- Example:

  ```powershell
  $env:MIGRATION_DATABASE_URL='postgresql://migration_role:password@localhost:5432/skeldir_validation'
  .\scripts\run_alembic.ps1 upgrade head
  ```

## Manual Invocation Requirements

If invoking `alembic` directly (not via wrapper script):

1. **Working Directory**: Must be repository root
   ```bash
   cd "c:/Users/ayewhy/II SKELDIR II"
   ```

2. **DATABASE_URL Format**: Must use sync driver
   ```bash
   # CORRECT (sync driver)
   export DATABASE_URL="postgresql://app_user:app_user@localhost:5432/skeldir_validation"

   # WRONG (async driver - will fail)
   export DATABASE_URL="postgresql+asyncpg://app_user:app_user@localhost:5432/skeldir_validation"
   ```

3. **Run Alembic**:
   ```bash
   alembic current
   alembic upgrade head
   alembic history
   ```

## Why Two Different DATABASE_URL Formats?

- **Application Runtime** (`backend/app/`): Uses SQLAlchemy AsyncEngine with `postgresql+asyncpg://` for async I/O
- **Alembic Migrations** (`alembic/`): Uses SQLAlchemy sync engine with `postgresql://` for schema DDL

This is standard practice in async SQLAlchemy projects. The two engines connect to the same database but use different drivers.

## CI/CD Integration

For CI pipelines, ensure:

```yaml
- name: Run Alembic Migrations
  working-directory: .  # Repository root
  env:
    DATABASE_URL: postgresql://postgres:postgres@localhost:5432/test_db  # Sync driver
  run: alembic upgrade head
```

## Troubleshooting

### Error: "No 'script_location' key found in configuration"
**Cause**: Running from wrong directory (likely `backend/` instead of repo root)
**Fix**: `cd` to repository root where `alembic.ini` exists

### Error: "greenlet_spawn has not been called"
**Cause**: Using async driver in DATABASE_URL
**Fix**: Change `postgresql+asyncpg://` to `postgresql://`

### Error: "could not connect to server"
**Cause**: Database not running or wrong connection details
**Fix**: Verify database is running and DATABASE_URL credentials are correct

## Related Documentation

- [B0.5.4.0 Drift Remediation Evidence](../evidence/b0540-drift-remediation-preflight-evidence.md)
- [Alembic Configuration](../../alembic.ini)
- [Migration Versions](../../alembic/versions/)
