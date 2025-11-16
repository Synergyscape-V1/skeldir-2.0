#!/bin/bash
# Phase 3 Validation Script
# Validates: Contract mapping rulebook, machine-readable YAML, worked example

set -e

echo "Validating Phase 3: Contract→Schema Mapping Rulebook..."

# Check 1: Type mappings in rulebook
RULEBOOK="db/docs/CONTRACT_TO_SCHEMA_MAPPING.md"
REQUIRED_TYPES=(
    "string\(uuid\)"
    "string\(date-time\)"
    "number\(float\)"
    "boolean"
    "integer"
)

for type in "${REQUIRED_TYPES[@]}"; do
    if ! grep -qE "$type" "$RULEBOOK"; then
        echo "FAIL: Rulebook missing type mapping: $type"
        exit 1
    fi
done
echo "✓ Rulebook contains all required type mappings"

# Check 2: Contract example references
if ! grep -qE "attribution\.yaml|reconciliation\.yaml|auth\.yaml" "$RULEBOOK"; then
    echo "FAIL: Rulebook missing contract file references"
    exit 1
fi
echo "✓ Rulebook references actual contract files"

# Check 3: Machine-readable YAML exists
YAML_FILE="db/docs/contract_schema_mapping.yaml"
if [ ! -f "$YAML_FILE" ]; then
    echo "FAIL: Machine-readable YAML not found"
    exit 1
fi

# Check YAML has types section (basic validation)
if ! grep -qE "^types:" "$YAML_FILE"; then
    echo "FAIL: YAML missing types section"
    exit 1
fi
echo "✓ Machine-readable YAML exists with types section"

# Check 4: Worked example content
EXAMPLE="db/docs/examples/realtime_revenue_mapping_example.md"
REQUIRED_EXAMPLE_ELEMENTS=(
    "total_revenue"
    "revenue_cents"
    "NOT NULL"
    "CREATE INDEX"
    "CREATE MATERIALIZED VIEW"
)

for element in "${REQUIRED_EXAMPLE_ELEMENTS[@]}"; do
    if ! grep -qE "$element" "$EXAMPLE"; then
        echo "FAIL: Worked example missing required element: $element"
        exit 1
    fi
done
echo "✓ Worked example demonstrates complete mapping"

# Check 5: Cross-references
if ! grep -qiE "style guide|RLS|row level security" "$RULEBOOK"; then
    echo "FAIL: Rulebook missing cross-references"
    exit 1
fi
echo "✓ Cross-references present"

echo "Phase 3: PASS"





