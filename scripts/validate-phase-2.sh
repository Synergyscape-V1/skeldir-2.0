#!/bin/bash
# Phase 2 Validation Script
# Validates: Style guide content, lint rules content, example DDL

set -e

echo "Validating Phase 2: Schema Style Guide & Linting..."

# Check 1: Style guide content
STYLE_GUIDE="db/docs/SCHEMA_STYLE_GUIDE.md"
REQUIRED_STYLE_ELEMENTS=(
    "snake_case"
    "id uuid"
    "created_at timestamptz"
    "is_|has_|can_"
    "tenant_id"
    "ck_"
    "idx_"
    "COMMENT ON"
    "INTEGER.*cents"
    "JSONB"
)

for element in "${REQUIRED_STYLE_ELEMENTS[@]}"; do
    if ! grep -qE "$element" "$STYLE_GUIDE"; then
        echo "FAIL: Style guide missing required element: $element"
        exit 1
    fi
done
echo "✓ Style guide contains all required conventions"

# Check 2: Lint rules content
LINT_RULES="db/docs/DDL_LINT_RULES.md"
REQUIRED_LINT_ELEMENTS=(
    "forbid.*comments"
    "forbid.*data"
    "NOT NULL"
    "tenant_id.*multi-tenant"
    "RLS.*tag"
    "forbid.*DECIMAL"
    "time-series.*index"
)

for element in "${REQUIRED_LINT_ELEMENTS[@]}"; do
    if ! grep -qiE "$element" "$LINT_RULES"; then
        echo "FAIL: Lint rules missing required element: $element"
        exit 1
    fi
done
echo "✓ Lint rules contain all required rules"

# Check 3: Example DDL content
EXAMPLE_DDL="db/docs/examples/example_table_ddl.sql"
REQUIRED_DDL_ELEMENTS=(
    "CREATE TABLE"
    "id uuid"
    "tenant_id"
    "created_at"
    "updated_at"
    "COMMENT ON"
    "CREATE POLICY"
)

for element in "${REQUIRED_DDL_ELEMENTS[@]}"; do
    if ! grep -qE "$element" "$EXAMPLE_DDL"; then
        echo "FAIL: Example DDL missing required element: $element"
        exit 1
    fi
done
echo "✓ Example DDL contains all required elements"

# Check 4: Cross-references
if ! grep -qiE "contract.*mapping|mapping.*rulebook" "$STYLE_GUIDE"; then
    echo "FAIL: Style guide missing contract mapping reference"
    exit 1
fi
if ! grep -qiE "RLS.*template|row level security.*template" "$LINT_RULES"; then
    echo "FAIL: Lint rules missing RLS template reference"
    exit 1
fi
echo "✓ Cross-references present"

echo "Phase 2: PASS"





