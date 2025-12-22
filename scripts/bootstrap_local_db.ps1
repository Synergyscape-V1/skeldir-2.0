# Bootstrap Local PostgreSQL for Skeldir Development (Windows)
#
# Purpose: Create database roles and skeldir_validation database with correct
# privileges for local development and testing. Mirrors CI workflow bootstrap.
#
# Requirements:
# - PostgreSQL 15+ installed locally and running
# - psql.exe in PATH
# - postgres superuser password known
#
# Usage:
#   .\scripts\bootstrap_local_db.ps1 -PostgresPassword "your_postgres_password"
#
# Idempotency: Safe to run multiple times - uses CREATE IF NOT EXISTS patterns

param(
    [Parameter(Mandatory=$false)]
    [string]$PostgresPassword = "postgres",

    [Parameter(Mandatory=$false)]
    [string]$PostgresHost = "localhost",

    [Parameter(Mandatory=$false)]
    [int]$PostgresPort = 5432,

    [Parameter(Mandatory=$false)]
    [switch]$DropExisting
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Skeldir Local DB Bootstrap (Windows)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Set PostgreSQL password environment variable for psql
$env:PGPASSWORD = $PostgresPassword

# Connection string base
$psqlBase = "psql -h $PostgresHost -p $PostgresPort -U postgres"

# Step 1: Drop existing database if requested
if ($DropExisting) {
    Write-Host "[1/7] Dropping existing skeldir_validation database (if exists)..." -ForegroundColor Yellow
    & psql -h $PostgresHost -p $PostgresPort -U postgres -c "DROP DATABASE IF EXISTS skeldir_validation;" 2>$null
    Write-Host "      Database dropped (if it existed)" -ForegroundColor Green
} else {
    Write-Host "[1/7] Skipping database drop (use -DropExisting to wipe)" -ForegroundColor Gray
}

# Step 2: Create app_user role (idempotent)
Write-Host "[2/7] Creating app_user role..." -ForegroundColor Yellow
& psql -h $PostgresHost -p $PostgresPort -U postgres -c @"
DO `$`$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'app_user') THEN
        CREATE USER app_user WITH PASSWORD 'app_user';
        RAISE NOTICE 'Created role app_user';
    ELSE
        RAISE NOTICE 'Role app_user already exists';
    END IF;
END
`$`$;
"@
if ($LASTEXITCODE -ne 0) {
    Write-Host "      ERROR: Failed to create app_user role" -ForegroundColor Red
    exit 1
}
Write-Host "      app_user role ensured" -ForegroundColor Green

# Step 3: Create app_rw role (idempotent)
Write-Host "[3/7] Creating app_rw role..." -ForegroundColor Yellow
& psql -h $PostgresHost -p $PostgresPort -U postgres -c @"
DO `$`$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'app_rw') THEN
        CREATE USER app_rw WITH PASSWORD 'app_rw';
        RAISE NOTICE 'Created role app_rw';
    ELSE
        RAISE NOTICE 'Role app_rw already exists';
    END IF;
END
`$`$;
"@
if ($LASTEXITCODE -ne 0) {
    Write-Host "      ERROR: Failed to create app_rw role" -ForegroundColor Red
    exit 1
}
Write-Host "      app_rw role ensured" -ForegroundColor Green

# Step 4: Create app_ro role (idempotent)
Write-Host "[4/7] Creating app_ro role..." -ForegroundColor Yellow
& psql -h $PostgresHost -p $PostgresPort -U postgres -c @"
DO `$`$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'app_ro') THEN
        CREATE USER app_ro WITH PASSWORD 'app_ro';
        RAISE NOTICE 'Created role app_ro';
    ELSE
        RAISE NOTICE 'Role app_ro already exists';
    END IF;
END
`$`$;
"@
if ($LASTEXITCODE -ne 0) {
    Write-Host "      ERROR: Failed to create app_ro role" -ForegroundColor Red
    exit 1
}
Write-Host "      app_ro role ensured" -ForegroundColor Green

# Step 5: Create skeldir_validation database (idempotent)
Write-Host "[5/7] Creating skeldir_validation database..." -ForegroundColor Yellow
# Try to create database - will error if exists, which we ignore
& psql -h $PostgresHost -p $PostgresPort -U postgres -c "CREATE DATABASE skeldir_validation OWNER app_user;" 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "      Created skeldir_validation database" -ForegroundColor Green
} else {
    # Check if it already exists
    $dbExists = & psql -h $PostgresHost -p $PostgresPort -U postgres -t -c "SELECT 1 FROM pg_database WHERE datname = 'skeldir_validation';" 2>$null
    if ($dbExists -match "1") {
        Write-Host "      skeldir_validation database already exists" -ForegroundColor Green
    } else {
        Write-Host "      ERROR: Failed to create skeldir_validation database" -ForegroundColor Red
        exit 1
    }
}

# Step 6: Grant database privileges
Write-Host "[6/7] Granting database privileges..." -ForegroundColor Yellow
& psql -h $PostgresHost -p $PostgresPort -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE skeldir_validation TO app_user;" 2>$null
Write-Host "      Database privileges granted to app_user" -ForegroundColor Green

# Step 7: Grant schema privileges
Write-Host "[7/7] Granting schema privileges..." -ForegroundColor Yellow
& psql -h $PostgresHost -p $PostgresPort -U postgres -d skeldir_validation -c "GRANT ALL ON SCHEMA public TO app_user;" 2>$null
& psql -h $PostgresHost -p $PostgresPort -U postgres -d skeldir_validation -c "GRANT ALL ON SCHEMA public TO app_rw;" 2>$null
& psql -h $PostgresHost -p $PostgresPort -U postgres -d skeldir_validation -c "GRANT USAGE ON SCHEMA public TO app_ro;" 2>$null
Write-Host "      Schema privileges granted" -ForegroundColor Green

# Step 8: Define custom GUC parameters for RLS (required for migrations)
Write-Host "[8/8] Defining custom GUC parameters..." -ForegroundColor Yellow
# Use a placeholder UUID for migration purposes (RLS policies reference this)
# The actual tenant_id is set at runtime by the application
& psql -h $PostgresHost -p $PostgresPort -U postgres -d skeldir_validation -c "ALTER DATABASE skeldir_validation SET app.current_tenant_id = '00000000-0000-0000-0000-000000000000';" 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "      Custom GUC app.current_tenant_id defined (placeholder UUID)" -ForegroundColor Green
} else {
    Write-Host "      WARNING: Failed to define custom GUC (may require reconnect)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Bootstrap Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Roles created:" -ForegroundColor Cyan
Write-Host "  - app_user (owner, full privileges)" -ForegroundColor White
Write-Host "  - app_rw (read-write access)" -ForegroundColor White
Write-Host "  - app_ro (read-only access)" -ForegroundColor White
Write-Host ""
Write-Host "Database: skeldir_validation" -ForegroundColor Cyan
Write-Host "  Owner: app_user" -ForegroundColor White
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Run migrations: alembic upgrade heads" -ForegroundColor White
Write-Host "  2. Verify schema: psql -U app_user -d skeldir_validation -c '\dt'" -ForegroundColor White
Write-Host "  3. Run tests: pytest backend/tests/test_b0532_window_idempotency.py -v" -ForegroundColor White
Write-Host ""

# Verification query
Write-Host "Verification:" -ForegroundColor Cyan
& psql -h $PostgresHost -p $PostgresPort -U postgres -d skeldir_validation -c "SELECT rolname FROM pg_roles WHERE rolname IN ('app_user','app_rw','app_ro') ORDER BY rolname;"

# Cleanup environment variable
$env:PGPASSWORD = $null
