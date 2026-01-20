param(
  [switch]$NoBuild
)

$ErrorActionPreference = "Stop"

function Wait-Docker {
  param([int]$TimeoutSeconds = 90)

  $dockerExe = "$Env:ProgramFiles\Docker\Docker\Docker Desktop.exe"
  if (Test-Path $dockerExe) {
    try {
      & docker ps *> $null
      if ($LASTEXITCODE -eq 0) { return }
    } catch {}

    Start-Process -FilePath $dockerExe | Out-Null
  }

  for ($i = 1; $i -le $TimeoutSeconds; $i++) {
    try {
      & docker ps *> $null
      if ($LASTEXITCODE -eq 0) { return }
    } catch {}
    Start-Sleep -Seconds 1
  }

  throw "Docker engine not available (docker ps never succeeded within ${TimeoutSeconds}s)."
}

Set-Location (Split-Path -Parent $PSScriptRoot) | Out-Null
Set-Location .. | Out-Null

Wait-Docker

$compose = @("compose", "-f", "docker-compose.e2e.yml")

if (-not $NoBuild) {
  & docker @compose build
}

& docker @compose up -d --remove-orphans
& docker @compose ps

