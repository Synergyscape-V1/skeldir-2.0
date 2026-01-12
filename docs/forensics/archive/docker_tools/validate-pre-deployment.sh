#!/bin/bash
# Pre-Deployment Integrity Validation Script
# Purpose: Verify all restructuring changes are complete before GitHub push
# Exit code: 0 = all validations pass, 1 = validation failure

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ERRORS=0
WARNINGS=0

echo "=========================================="
echo "Pre-Deployment Integrity Validation"
echo "=========================================="
echo ""

# Gate 1.1: Path Consistency Verification
echo "Gate 1.1: Path Consistency Verification"
echo "----------------------------------------"

# Check for old contract paths
OLD_CONTRACT_PATHS=$(grep -r "contracts/openapi/v1" --include="*.yml" --include="*.yaml" --include="*.md" --include="*.sh" --include="*.py" --include="*.json" . 2>/dev/null | grep -v "docs/forensics/archive" | grep -v "node_modules" | wc -l || echo "0")

if [ "$OLD_CONTRACT_PATHS" -gt 0 ]; then
    echo -e "${RED}✗ Found $OLD_CONTRACT_PATHS references to old contract paths${NC}"
    grep -r "contracts/openapi/v1" --include="*.yml" --include="*.yaml" --include="*.md" --include="*.sh" --include="*.py" --include="*.json" . 2>/dev/null | grep -v "docs/forensics/archive" | grep -v "node_modules" || true
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}✓ No references to old contract paths found${NC}"
fi

# Check for old migration paths
OLD_MIGRATION_PATHS=$(grep -r "alembic/versions/[^/]*\.py" --include="*.ini" --include="*.md" --include="*.sh" . 2>/dev/null | grep -v "001_core_schema\|002_pii_controls\|003_data_governance" | wc -l || echo "0")

if [ "$OLD_MIGRATION_PATHS" -gt 0 ]; then
    echo -e "${YELLOW}⚠ Found $OLD_MIGRATION_PATHS references to old migration paths${NC}"
    WARNINGS=$((WARNINGS + 1))
else
    echo -e "${GREEN}✓ Migration paths correctly reference grouped directories${NC}"
fi

echo ""

# Gate 1.2: Contract Integrity
echo "Gate 1.2: Contract Integrity"
echo "----------------------------------------"

# Check for broken $ref references
BROKEN_REFS=$(grep -r '\$ref.*\.\./\.\./\.\./_common' contracts/ 2>/dev/null | wc -l || echo "0")
LEGACY_REFS=$(grep -r '\$ref.*\.\./_common' contracts/ 2>/dev/null | grep -v "_common/v1" | wc -l || echo "0")

if [ "$BROKEN_REFS" -gt 0 ] || [ "$LEGACY_REFS" -gt 0 ]; then
    echo -e "${RED}✗ Found broken or legacy \$ref references${NC}"
    if [ "$BROKEN_REFS" -gt 0 ]; then
        echo "  Broken references (too many ../): $BROKEN_REFS"
    fi
    if [ "$LEGACY_REFS" -gt 0 ]; then
        echo "  Legacy references (not _common/v1): $LEGACY_REFS"
    fi
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}✓ All \$ref references point to _common/v1/${NC}"
fi

# Validate OpenAPI files exist
MISSING_CONTRACTS=0
for domain in attribution auth reconciliation export health; do
    if [ ! -f "contracts/${domain}/v1/${domain}.yaml" ]; then
        echo -e "${RED}✗ Missing contract: contracts/${domain}/v1/${domain}.yaml${NC}"
        MISSING_CONTRACTS=$((MISSING_CONTRACTS + 1))
    fi
done

for webhook in shopify stripe paypal woocommerce; do
    if [ ! -f "contracts/webhooks/v1/${webhook}.yaml" ]; then
        echo -e "${RED}✗ Missing contract: contracts/webhooks/v1/${webhook}.yaml${NC}"
        MISSING_CONTRACTS=$((MISSING_CONTRACTS + 1))
    fi
done

if [ "$MISSING_CONTRACTS" -eq 0 ]; then
    echo -e "${GREEN}✓ All required contracts present${NC}"
else
    ERRORS=$((ERRORS + MISSING_CONTRACTS))
fi

echo ""

# Gate 1.3: Navigation Validation
echo "Gate 1.3: Navigation Validation"
echo "----------------------------------------"

# Check critical documentation exists
CRITICAL_DOCS=(
    "docs/database/pii-controls.md"
    "docs/database/schema-governance.md"
    "docs/architecture/service-boundaries.md"
    "docs/architecture/contract-ownership.md"
    "docs/operations/pii-control-evidence.md"
    "docs/operations/data-governance-evidence.md"
    "docs/operations/incident-response.md"
)

MISSING_DOCS=0
for doc in "${CRITICAL_DOCS[@]}"; do
    if [ ! -f "$doc" ]; then
        echo -e "${RED}✗ Missing critical documentation: $doc${NC}"
        MISSING_DOCS=$((MISSING_DOCS + 1))
    fi
done

if [ "$MISSING_DOCS" -eq 0 ]; then
    echo -e "${GREEN}✓ All critical documentation present${NC}"
else
    ERRORS=$((ERRORS + MISSING_DOCS))
fi

# Check README links
if [ -f "README.md" ]; then
    README_LINKS=$(grep -o '\[.*\]([^)]*)' README.md | wc -l || echo "0")
    echo -e "${GREEN}✓ README.md contains $README_LINKS documentation links${NC}"
else
    echo -e "${RED}✗ README.md missing${NC}"
    ERRORS=$((ERRORS + 1))
fi

echo ""

# Gate 1.4: Build Readiness
echo "Gate 1.4: Build Readiness"
echo "----------------------------------------"

# Check Dockerfiles exist and parse
DOCKERFILES=(
    "backend/app/ingestion/Dockerfile"
    "backend/app/attribution/Dockerfile"
    "backend/app/auth/Dockerfile"
    "backend/app/webhooks/Dockerfile"
)

MISSING_DOCKERFILES=0
for dockerfile in "${DOCKERFILES[@]}"; do
    if [ ! -f "$dockerfile" ]; then
        echo -e "${RED}✗ Missing Dockerfile: $dockerfile${NC}"
        MISSING_DOCKERFILES=$((MISSING_DOCKERFILES + 1))
    else
        # Basic syntax check (check for FROM directive)
        if ! grep -q "^FROM" "$dockerfile"; then
            echo -e "${RED}✗ Invalid Dockerfile (no FROM): $dockerfile${NC}"
            MISSING_DOCKERFILES=$((MISSING_DOCKERFILES + 1))
        else
            echo -e "${GREEN}✓ Valid Dockerfile: $dockerfile${NC}"
        fi
    fi
done

if [ "$MISSING_DOCKERFILES" -eq 0 ]; then
    echo -e "${GREEN}✓ All Dockerfiles present and valid${NC}"
else
    ERRORS=$((ERRORS + MISSING_DOCKERFILES))
fi

# Check docker-compose files
if [ ! -f "docker-compose.component-dev.yml" ]; then
    echo -e "${RED}✗ Missing docker-compose.component-dev.yml${NC}"
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}✓ docker-compose.component-dev.yml present${NC}"
fi

echo ""

# Summary
echo "=========================================="
echo "Validation Summary"
echo "=========================================="
echo -e "Errors: ${RED}$ERRORS${NC}"
echo -e "Warnings: ${YELLOW}$WARNINGS${NC}"
echo ""

if [ "$ERRORS" -eq 0 ]; then
    echo -e "${GREEN}✓ All pre-deployment validations passed${NC}"
    echo "Repository is ready for GitHub deployment"
    exit 0
else
    echo -e "${RED}✗ Pre-deployment validation failed${NC}"
    echo "Fix errors before proceeding with deployment"
    exit 1
fi

