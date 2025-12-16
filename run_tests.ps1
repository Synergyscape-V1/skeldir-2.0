$env:DATABASE_URL = "postgresql://app_user:app_user@localhost:5432/skeldir_validation"
$env:PYTHONPATH = "C:\Users\ayewhy\II SKELDIR II\backend"

Write-Host "Running B0.5.3.2 window idempotency tests..." -ForegroundColor Yellow
cd backend
pytest tests/test_b0532_window_idempotency.py -v

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: B0.5.3.2 tests failed" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Running B0.5.2 queue topology and DLQ tests..." -ForegroundColor Yellow
pytest tests/test_b052_queue_topology_and_dlq.py -v

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: B0.5.2 tests failed" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "SUCCESS: All tests passed" -ForegroundColor Green
