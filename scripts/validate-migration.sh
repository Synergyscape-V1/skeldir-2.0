#!/bin/bash
#
# scripts/validate-migration.sh
# CI Safety Validator: Detects high-risk, destructive DDL in Alembic migrations
#
# Purpose:
#   This script performs STATIC ANALYSIS on migration files to detect destructive
#   operations that could cause data loss if deployed automatically through CI/CD.
#
# Usage:
#   ./scripts/validate-migration.sh <path_to_migration_file.py>
#
# Exit Codes:
#   0 - PASS: No destructive patterns found
#   1 - FAIL: Destructive patterns detected (or invalid usage)
#
# Bypass Mechanism:
#   Lines containing '# CI:DESTRUCTIVE_OK' are excluded from pattern matching,
#   allowing intentional destructive operations with explicit acknowledgment.
#
# Example:
#   op.drop_table('deprecated_table')  # CI:DESTRUCTIVE_OK - See ADR-015
#
# References:
#   - B0.3_MV_VALIDATOR_IMPLEMENTATION.md (Phase VAL-1, VAL-2)
#   - db/docs/adr/ADR-002-migration-discipline.md
#

set -e

# ============================================================================
# Input Validation
# ============================================================================

if [ -z "$1" ]; then
    echo "ERROR: No migration file provided"
    echo "Usage: $0 <migration_file>"
    echo ""
    echo "Example:"
    echo "  $0 alembic/versions/202511151500_add_mv_channel_performance.py"
    exit 1
fi

MIGRATION_FILE="$1"

if [ ! -f "$MIGRATION_FILE" ]; then
    echo "ERROR: Migration file not found: $MIGRATION_FILE"
    exit 1
fi

# ============================================================================
# Destructive Pattern Detection
# ============================================================================

echo "--- [CI Safety Validator] Analyzing: $MIGRATION_FILE ---"

# List of high-risk, destructive patterns
# These patterns indicate operations that permanently delete data or schema objects
DESTRUCTIVE_PATTERNS=(
    "DROP TABLE"
    "DROP COLUMN"
    "DROP DATABASE"
    "DROP SCHEMA"
    "TRUNCATE"
    "DELETE FROM.*WHERE.*1.*=.*1"
    "ALTER TABLE.*DROP CONSTRAINT"
    "op.drop_table"
    "op.drop_column"
)

FOUND_DESTRUCTIVE=0
DETECTED_PATTERNS=()

for pattern in "${DESTRUCTIVE_PATTERNS[@]}"; do
    # Filter out lines with bypass comment, then check for pattern (case-insensitive)
    if grep -v "# CI:DESTRUCTIVE_OK" "$MIGRATION_FILE" | grep -iE "$pattern" > /dev/null 2>&1; then
        echo "⛔️ DANGER: Destructive pattern found: '$pattern'"
        FOUND_DESTRUCTIVE=1
        DETECTED_PATTERNS+=("$pattern")
    fi
done

# ============================================================================
# Report Results
# ============================================================================

if [ "$FOUND_DESTRUCTIVE" -eq 1 ]; then
    echo "---"
    echo "⛔️ VALIDATION FAILED: This migration contains destructive operations."
    echo ""
    echo "Detected patterns:"
    for pattern in "${DETECTED_PATTERNS[@]}"; do
        echo "  - $pattern"
    done
    echo ""
    echo "This CI check prevents accidental data loss from automated deployments."
    echo ""
    echo "If this destructive operation is intentional:"
    echo "  1. Document the reason in an ADR (Architecture Decision Record)"
    echo "  2. Add a '# CI:DESTRUCTIVE_OK' comment to the destructive line"
    echo "  3. Include ADR reference in the comment"
    echo ""
    echo "Example:"
    echo "  op.drop_table('deprecated_table')  # CI:DESTRUCTIVE_OK - See ADR-015 for deprecation timeline"
    echo "---"
    exit 1
else
    echo "✅ VALIDATION PASSED: No destructive patterns found."
    echo "---"
    exit 0
fi



