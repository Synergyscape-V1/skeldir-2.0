# Pre-Deployment Integrity Validation Script (PowerShell)
# Purpose: Verify all restructuring changes are complete before GitHub push
# Exit code: 0 = all validations pass, 1 = validation failure

$ErrorActionPreference = "Stop"

$Errors = 0
$Warnings = 0

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Pre-Deployment Integrity Validation" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Gate 1.1: Path Consistency Verification
Write-Host "Gate 1.1: Path Consistency Verification" -ForegroundColor Yellow
Write-Host "----------------------------------------" -ForegroundColor Yellow

# Check for old contract paths
$OldContractPaths = Get-ChildItem -Path . -Recurse -Include *.yml,*.yaml,*.md,*.sh,*.py,*.json | 
    Select-String -Pattern "contracts/openapi/v1" | 
    Where-Object { $_.Path -notlike "*\docs\archive\*" -and $_.Path -notlike "*\node_modules\*" }

if ($OldContractPaths.Count -gt 0) {
    Write-Host "✗ Found $($OldContractPaths.Count) references to old contract paths" -ForegroundColor Red
    $OldContractPaths | ForEach-Object { Write-Host "  $($_.Path):$($_.LineNumber)" -ForegroundColor Red }
    $Errors++
} else {
    Write-Host "✓ No references to old contract paths found" -ForegroundColor Green
}

Write-Host ""

# Gate 1.2: Contract Integrity
Write-Host "Gate 1.2: Contract Integrity" -ForegroundColor Yellow
Write-Host "----------------------------------------" -ForegroundColor Yellow

# Check for broken $ref references
$BrokenRefs = Get-ChildItem -Path contracts -Recurse -Include *.yaml | 
    Select-String -Pattern '\$ref.*\.\./\.\./\.\./_common' -ErrorAction SilentlyContinue

$LegacyRefs = Get-ChildItem -Path contracts -Recurse -Include *.yaml | 
    Select-String -Pattern '\$ref.*\.\./_common' -ErrorAction SilentlyContinue | 
    Where-Object { $_.Line -notmatch "_common/v1" }

if ($BrokenRefs.Count -gt 0 -or $LegacyRefs.Count -gt 0) {
    Write-Host "✗ Found broken or legacy `$ref references" -ForegroundColor Red
    if ($BrokenRefs.Count -gt 0) {
        Write-Host "  Broken references (too many ../): $($BrokenRefs.Count)" -ForegroundColor Red
    }
    if ($LegacyRefs.Count -gt 0) {
        Write-Host "  Legacy references (not _common/v1): $($LegacyRefs.Count)" -ForegroundColor Red
    }
    $Errors++
} else {
    Write-Host "✓ All `$ref references point to _common/v1/" -ForegroundColor Green
}

# Validate OpenAPI files exist
$MissingContracts = 0
$Domains = @("attribution", "auth", "reconciliation", "export", "health")
foreach ($domain in $Domains) {
    $contractPath = "contracts\$domain\v1\$domain.yaml"
    if (-not (Test-Path $contractPath)) {
        Write-Host "✗ Missing contract: $contractPath" -ForegroundColor Red
        $MissingContracts++
    }
}

$Webhooks = @("shopify", "stripe", "paypal", "woocommerce")
foreach ($webhook in $Webhooks) {
    $contractPath = "contracts\webhooks\v1\$webhook.yaml"
    if (-not (Test-Path $contractPath)) {
        Write-Host "✗ Missing contract: $contractPath" -ForegroundColor Red
        $MissingContracts++
    }
}

if ($MissingContracts -eq 0) {
    Write-Host "✓ All required contracts present" -ForegroundColor Green
} else {
    $Errors += $MissingContracts
}

Write-Host ""

# Gate 1.3: Navigation Validation
Write-Host "Gate 1.3: Navigation Validation" -ForegroundColor Yellow
Write-Host "----------------------------------------" -ForegroundColor Yellow

$CriticalDocs = @(
    "docs\database\pii-controls.md",
    "docs\database\schema-governance.md",
    "docs\architecture\service-boundaries.md",
    "docs\architecture\contract-ownership.md",
    "docs\operations\pii-control-evidence.md",
    "docs\operations\data-governance-evidence.md",
    "docs\operations\incident-response.md"
)

$MissingDocs = 0
foreach ($doc in $CriticalDocs) {
    if (-not (Test-Path $doc)) {
        Write-Host "✗ Missing critical documentation: $doc" -ForegroundColor Red
        $MissingDocs++
    }
}

if ($MissingDocs -eq 0) {
    Write-Host "✓ All critical documentation present" -ForegroundColor Green
} else {
    $Errors += $MissingDocs
}

if (Test-Path "README.md") {
    $readmeLinks = (Select-String -Path README.md -Pattern '\[.*\]\([^)]*\)').Count
    Write-Host "✓ README.md contains $readmeLinks documentation links" -ForegroundColor Green
} else {
    Write-Host "✗ README.md missing" -ForegroundColor Red
    $Errors++
}

Write-Host ""

# Gate 1.4: Build Readiness
Write-Host "Gate 1.4: Build Readiness" -ForegroundColor Yellow
Write-Host "----------------------------------------" -ForegroundColor Yellow

$Dockerfiles = @(
    "backend\app\ingestion\Dockerfile",
    "backend\app\attribution\Dockerfile",
    "backend\app\auth\Dockerfile",
    "backend\app\webhooks\Dockerfile"
)

$MissingDockerfiles = 0
foreach ($dockerfile in $Dockerfiles) {
    if (-not (Test-Path $dockerfile)) {
        Write-Host "✗ Missing Dockerfile: $dockerfile" -ForegroundColor Red
        $MissingDockerfiles++
    } else {
        $content = Get-Content $dockerfile -Raw
        if ($content -notmatch "^FROM") {
            Write-Host "✗ Invalid Dockerfile (no FROM): $dockerfile" -ForegroundColor Red
            $MissingDockerfiles++
        } else {
            Write-Host "✓ Valid Dockerfile: $dockerfile" -ForegroundColor Green
        }
    }
}

if ($MissingDockerfiles -eq 0) {
    Write-Host "✓ All Dockerfiles present and valid" -ForegroundColor Green
} else {
    $Errors += $MissingDockerfiles
}

if (-not (Test-Path "docker-compose.component-dev.yml")) {
    Write-Host "✗ Missing docker-compose.component-dev.yml" -ForegroundColor Red
    $Errors++
} else {
    Write-Host "✓ docker-compose.component-dev.yml present" -ForegroundColor Green
}

Write-Host ""

# Summary
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Validation Summary" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
$errorColor = if ($Errors -eq 0) { "Green" } else { "Red" }
$warningColor = if ($Warnings -eq 0) { "Green" } else { "Yellow" }
Write-Host "Errors: $Errors" -ForegroundColor $errorColor
Write-Host "Warnings: $Warnings" -ForegroundColor $warningColor
Write-Host ""

if ($Errors -eq 0) {
    Write-Host "✓ All pre-deployment validations passed" -ForegroundColor Green
    Write-Host "Repository is ready for GitHub deployment" -ForegroundColor Green
    exit 0
} else {
    Write-Host "✗ Pre-deployment validation failed" -ForegroundColor Red
    Write-Host "Fix errors before proceeding with deployment" -ForegroundColor Red
    exit 1
}

