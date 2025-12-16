$env:DATABASE_URL = "postgresql://app_user:app_user@localhost:5432/skeldir_validation"

Write-Host "Applying new migration 202512151410 (add allocation model versioning)..." -ForegroundColor Yellow
alembic upgrade 202512151410

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Migration failed" -ForegroundColor Red
    exit 1
}

Write-Host "SUCCESS: Migration applied" -ForegroundColor Green
