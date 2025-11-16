#!/bin/bash
# Run PII Audit Scan
#
# Purpose: Execute PII audit scan and verify findings
# Usage: ./run-audit-scan.sh [DATABASE_URL]
#
# Expected Behavior:
# - Function executes: SELECT fn_scan_pii_contamination();
# - Findings recorded: SELECT COUNT(*) FROM pii_audit_findings;
# - Findings have correct structure (table_name, column_name, detected_key, record_id)

set -euo pipefail

DATABASE_URL="${1:-${DATABASE_URL:-}}"

if [ -z "$DATABASE_URL" ]; then
    echo "Error: DATABASE_URL not provided"
    echo "Usage: $0 [DATABASE_URL]"
    exit 1
fi

echo "=========================================="
echo "PII Audit Scan Execution"
echo "=========================================="
echo ""

# Execute audit scan
echo "Step 1: Executing audit scan function..."
echo "Command: SELECT fn_scan_pii_contamination();"
echo ""
FINDING_COUNT=$(psql "$DATABASE_URL" -t -c "SELECT fn_scan_pii_contamination();" | xargs)
echo "Audit scan returned: $FINDING_COUNT findings"
echo ""

# Query findings
echo "Step 2: Querying audit findings..."
echo "Command: SELECT COUNT(*) FROM pii_audit_findings;"
echo ""
TOTAL_FINDINGS=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM pii_audit_findings;" | xargs)
echo "Total findings in table: $TOTAL_FINDINGS"
echo ""

# Verify findings structure
if [ "$TOTAL_FINDINGS" -gt 0 ]; then
    echo "Step 3: Verifying findings structure..."
    echo "Command: SELECT table_name, column_name, detected_key, record_id FROM pii_audit_findings LIMIT 5;"
    echo ""
    psql "$DATABASE_URL" -c "SELECT table_name, column_name, detected_key, record_id, detected_at FROM pii_audit_findings ORDER BY detected_at DESC LIMIT 5;"
    echo ""
    
    # Verify required columns exist
    COLUMN_CHECK=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM information_schema.columns WHERE table_name = 'pii_audit_findings' AND column_name IN ('table_name', 'column_name', 'detected_key', 'record_id', 'detected_at');" | xargs)
    if [ "$COLUMN_CHECK" -eq 5 ]; then
        echo "✅ PASS: All required columns exist in pii_audit_findings table"
    else
        echo "❌ FAIL: Missing required columns in pii_audit_findings table"
        exit 1
    fi
else
    echo "Step 3: No findings detected (clean database)"
    echo "✅ PASS: Audit scan executed successfully, no PII contamination found"
fi
echo ""

echo "=========================================="
echo "✅ PII audit scan validation complete"
echo "=========================================="
echo ""
echo "Summary:"
echo "  - Function executed: ✅"
echo "  - Findings count: $FINDING_COUNT"
echo "  - Total findings in table: $TOTAL_FINDINGS"
if [ "$TOTAL_FINDINGS" -gt 0 ]; then
    echo "  - Findings structure: ✅ Valid"
fi

