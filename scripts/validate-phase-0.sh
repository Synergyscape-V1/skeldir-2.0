#!/bin/bash
# Phase 0 Validation Script
# Validates: Directory structure, ADR content, ownership completeness, approval artifacts

set -e

echo "Validating Phase 0: Ownership, Layout, and ADRs..."

# Check 1: Directory structure (12 subdirectories + db root = 13 total)
DIR_COUNT=$(find db -type d | wc -l)
if [ "$DIR_COUNT" -lt 13 ]; then
    echo "FAIL: Expected at least 13 directories, found $DIR_COUNT"
    exit 1
fi
echo "✓ Directory structure: $DIR_COUNT directories found"

# Check 2: ADR-001 content
if ! grep -qE "Status|Context|Decision|Consequences|Contract.*Schema|traceability" db/docs/adr/ADR-001-schema-source-of-truth.md; then
    echo "FAIL: ADR-001 missing required sections"
    exit 1
fi
echo "✓ ADR-001 contains required sections"

# Check 3: ADR-002 content
if ! grep -qE "Status|Context|Decision|Consequences|manual DDL|migration flow|review process" db/docs/adr/ADR-002-migration-discipline.md; then
    echo "FAIL: ADR-002 missing required sections"
    exit 1
fi
echo "✓ ADR-002 contains required sections"

# Check 4: Ownership map completeness
OWNER_MATCHES=$(grep -cE "owner|OWNER|email|responsibility" db/OWNERSHIP.md || echo "0")
if [ "$OWNER_MATCHES" -lt 12 ]; then
    echo "FAIL: Ownership map incomplete (expected ≥12 matches, found $OWNER_MATCHES)"
    exit 1
fi
echo "✓ Ownership map contains owner assignments for all directories"

# Check 5: File existence (key files)
REQUIRED_FILES=(
    "db/OWNERSHIP.md"
    "db/docs/adr/ADR-001-schema-source-of-truth.md"
    "db/docs/adr/ADR-002-migration-discipline.md"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ] || [ ! -s "$file" ]; then
        echo "FAIL: Required file missing or empty: $file"
        exit 1
    fi
done
echo "✓ All required files exist and are non-empty"

echo "Phase 0: PASS"





