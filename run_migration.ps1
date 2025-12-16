$env:DATABASE_URL = "postgresql://app_user:app_user@localhost:5432/skeldir_validation"

# First, upgrade to core_schema parent
Write-Host "Step 1: Upgrading to core_schema parent (202511131121)..." -ForegroundColor Yellow
alembic upgrade 202511131121

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Core schema upgrade failed" -ForegroundColor Red
    exit 1
}

# Then upgrade to skeldir_foundation head
Write-Host "Step 2: Upgrading to skeldir_foundation@head..." -ForegroundColor Yellow
alembic upgrade skeldir_foundation@head

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Skeldir foundation upgrade failed" -ForegroundColor Red
    exit 1
}

Write-Host "SUCCESS: All migrations applied" -ForegroundColor Green
