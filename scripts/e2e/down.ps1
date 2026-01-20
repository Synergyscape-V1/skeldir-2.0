param(
  [switch]$KeepVolumes
)

$ErrorActionPreference = "Stop"

Set-Location (Split-Path -Parent $PSScriptRoot) | Out-Null
Set-Location .. | Out-Null

$compose = @("compose", "-f", "docker-compose.e2e.yml")
$args = @("down", "--remove-orphans")
if (-not $KeepVolumes) {
  $args += @("--volumes")
}

& docker @compose @args

