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

# Validate DATABASE_URL is set
if (-not $env:DATABASE_URL) {
    Write-Error "ERROR: DATABASE_URL environment variable is not set."
    Write-Host "Example: `$env:DATABASE_URL='postgresql://app_user:app_user@localhost:5432/skeldir_validation'"
    exit 1
}

# Validate DATABASE_URL uses sync driver
if ($env:DATABASE_URL -match "postgresql\+asyncpg://") {
    Write-Error "ERROR: DATABASE_URL uses async driver (postgresql+asyncpg://)"
    Write-Host "Alembic requires sync driver format: postgresql://user:pass@host:port/dbname"
    Write-Host ""
    Write-Host "Current: $env:DATABASE_URL"
    Write-Host "Example: postgresql://app_user:app_user@localhost:5432/skeldir_validation"
    exit 1
}

if ($env:DATABASE_URL -notmatch "^postgresql://") {
    Write-Warning "WARNING: DATABASE_URL does not start with 'postgresql://'"
    Write-Host "Expected format: postgresql://user:pass@host:port/dbname"
    Write-Host "Current: $env:DATABASE_URL"
}

# Run alembic with validated environment
Write-Host "Running: alembic $AlembicArgs" -ForegroundColor Cyan
Write-Host "Working Directory: $(Get-Location)" -ForegroundColor Gray
Write-Host "DATABASE_URL: $($env:DATABASE_URL -replace ':[^:@]+@', ':****@')" -ForegroundColor Gray
Write-Host ""

& alembic @AlembicArgs

if ($LASTEXITCODE -ne 0) {
    Write-Error "Alembic command failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}
