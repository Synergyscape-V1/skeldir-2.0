# run_alembic.ps1
# B0.5.4.0: Standardized Alembic invocation wrapper
#
# Purpose: Ensures alembic runs with correct working directory and DATABASE_URL format
#
# Usage:
#   .\scripts\run_alembic.ps1 current
#   .\scripts\run_alembic.ps1 upgrade head
#   .\scripts\run_alembic.ps1 history
#
# Requirements:
#   - Must be run from repo root
#   - DATABASE_URL environment variable must use sync driver (postgresql://)
#
# See: docs/backend/ALEMBIC_DETERMINISM.md for details

param(
    [Parameter(Mandatory=$true, ValueFromRemainingArguments=$true)]
    [string[]]$AlembicArgs
)

$ErrorActionPreference = "Stop"

# Validate running from repo root
if (-not (Test-Path ".\alembic.ini")) {
    Write-Error "ERROR: alembic.ini not found. This script must be run from the repository root."
    exit 1
}

# Policy P1-A: migrations run with a migration role that bypasses RLS
$migrationDatabaseUrl = $env:MIGRATION_DATABASE_URL
if (-not $migrationDatabaseUrl) {
    Write-Error "ERROR: MIGRATION_DATABASE_URL is not set."
    Write-Host "Policy P1-A requires migrations to run as a migration role (BYPASSRLS/superuser)."
    Write-Host "Set MIGRATION_DATABASE_URL to a sync Postgres URL, e.g.:"
    Write-Host "  `$env:MIGRATION_DATABASE_URL='postgresql://migration_role:password@localhost:5432/skeldir_validation'"
    exit 1
}

# Validate migration connection uses sync driver
if ($migrationDatabaseUrl -match "postgresql\+asyncpg://") {
    Write-Error "ERROR: MIGRATION_DATABASE_URL uses async driver (postgresql+asyncpg://)"
    Write-Host "Alembic requires sync driver format: postgresql://user:pass@host:port/dbname"
    Write-Host ""
    Write-Host "Current: $migrationDatabaseUrl"
    Write-Host "Example: postgresql://migration_role:password@localhost:5432/skeldir_validation"
    exit 1
}

if ($migrationDatabaseUrl -notmatch "^postgresql://") {
    Write-Warning "WARNING: MIGRATION_DATABASE_URL does not start with 'postgresql://'"
    Write-Host "Expected format: postgresql://user:pass@host:port/dbname"
    Write-Host "Current: $migrationDatabaseUrl"
}

$originalDatabaseUrl = $env:DATABASE_URL
$env:DATABASE_URL = $migrationDatabaseUrl

# Run alembic with validated environment
Write-Host "Running: alembic $AlembicArgs" -ForegroundColor Cyan
Write-Host "Working Directory: $(Get-Location)" -ForegroundColor Gray
Write-Host "Policy: P1-A (migration role with BYPASSRLS/superuser privileges)" -ForegroundColor Gray
Write-Host "MIGRATION_DATABASE_URL: $($migrationDatabaseUrl -replace ':[^:@]+@', ':****@')" -ForegroundColor Gray
Write-Host ""

$exitCode = 0
try {
    & alembic @AlembicArgs
    $exitCode = $LASTEXITCODE
}
finally {
    if ($null -ne $originalDatabaseUrl) {
        $env:DATABASE_URL = $originalDatabaseUrl
    } else {
        Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
    }
}

if ($exitCode -ne 0) {
    Write-Error "Alembic command failed with exit code $exitCode"
    exit $exitCode
}
