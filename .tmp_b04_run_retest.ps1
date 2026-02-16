$ErrorActionPreference = 'Stop'
$root = 'c:\Users\ayewhy\II SKELDIR II'
$backend = Join-Path $root 'backend'
$port = 8090
$env:PYTHONPATH='backend'
$env:TENANT_API_KEY_HEADER='X-Skeldir-Tenant-Key'
$env:DATABASE_URL='postgresql://app_user:app_user@127.0.0.1:5432/r3_b04_phase3'
$env:MIGRATION_DATABASE_URL='postgresql://postgres:postgres@127.0.0.1:5432/r3_b04_phase3'
$env:R3_ADMIN_DATABASE_URL='postgresql://postgres:postgres@127.0.0.1:5432/r3_b04_phase3'
$env:R3_RUNTIME_DATABASE_URL='postgresql://app_user:app_user@127.0.0.1:5432/r3_b04_phase3'
$env:R3_API_BASE_URL=("http://127.0.0.1:$port")
$env:R3_LADDER='50,250,1000'
$env:R3_CONCURRENCY='200'
$env:R3_TIMEOUT_S='10'
$env:R3_PERF_N='10000'
$env:R3_PERF_MAX_SECONDS='10'
$env:DATABASE_POOL_SIZE='20'
$env:DATABASE_MAX_OVERFLOW='0'
$env:DATABASE_POOL_TIMEOUT_SECONDS='3'
$env:DATABASE_POOL_TOTAL_CAP='30'
$env:INGESTION_FOLLOWUP_TASKS_ENABLED='false'
$env:CANDIDATE_SHA=('local-final-retest-' + (Get-Date -Format 'yyyyMMddHHmmssfff'))

$runStamp = Get-Date -Format 'yyyyMMddHHmmssfff'
$uvLog = Join-Path $root (".tmp_b04_uvicorn_retest_$runStamp.log")
$uvErr = Join-Path $root (".tmp_b04_uvicorn_retest_$runStamp.err.log")
$r3Log = Join-Path $root (".tmp_b04_r3_retest_$runStamp.log")

$uvicorn = Start-Process -FilePath python -ArgumentList '-m','uvicorn','app.main:app','--host','127.0.0.1','--port',$port,'--workers','2','--no-access-log' -WorkingDirectory $backend -RedirectStandardOutput $uvLog -RedirectStandardError $uvErr -PassThru

try {
  $ready = $false
  for ($i=0; $i -lt 120; $i++) {
    try {
      $resp = Invoke-WebRequest -Uri ("http://127.0.0.1:$port/health/ready") -UseBasicParsing -TimeoutSec 3
      if ($resp.StatusCode -eq 200) { $ready = $true; break }
    } catch {}
    Start-Sleep -Milliseconds 500
  }
  if (-not $ready) { throw 'uvicorn readiness failed' }

  Push-Location $root
  try {
    python scripts/r3/ingestion_under_fire.py *>&1 | Tee-Object -FilePath $r3Log
    $exitCode = $LASTEXITCODE
  } finally {
    Pop-Location
  }

  Write-Output "R3_EXIT_CODE=$exitCode"
  exit $exitCode
}
finally {
  if ($uvicorn -and -not $uvicorn.HasExited) {
    Stop-Process -Id $uvicorn.Id -Force
  }
}
