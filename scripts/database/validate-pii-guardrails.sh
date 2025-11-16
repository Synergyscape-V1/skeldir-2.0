#!/bin/bash
# Validate PII Guardrail Triggers
#
# Purpose: Test PII guardrail blocking behavior (Layer 2)
# Usage: ./validate-pii-guardrails.sh [DATABASE_URL]
#
# Expected Behavior:
# - INSERT with PII key → ERROR with detailed message
# - INSERT with PII in value → SUCCESS (expected limitation)
# - NULL metadata → SUCCESS (allowed)

set -euo pipefail

DATABASE_URL="${1:-${DATABASE_URL:-}}"

if [ -z "$DATABASE_URL" ]; then
    echo "Error: DATABASE_URL not provided"
    echo "Usage: $0 [DATABASE_URL]"
    exit 1
fi

echo "=========================================="
echo "PII Guardrail Validation Test"
echo "=========================================="
echo ""

# Create test tenant
echo "Step 1: Creating test tenant..."
TENANT_ID=$(psql "$DATABASE_URL" -t -c "INSERT INTO tenants (id, name) VALUES (gen_random_uuid(), 'test_tenant_pii_validation') RETURNING id;" | xargs)
echo "Created tenant: $TENANT_ID"
echo ""

# Test 1: INSERT with PII key (should fail)
echo "Test 1: INSERT with PII key 'email' (should FAIL)"
echo "Command: INSERT INTO attribution_events (tenant_id, occurred_at, raw_payload) VALUES ('$TENANT_ID', NOW(), '{\"order_id\": \"123\", \"email\": \"test@test.com\"}'::jsonb);"
echo ""
if psql "$DATABASE_URL" -c "INSERT INTO attribution_events (tenant_id, occurred_at, raw_payload) VALUES ('$TENANT_ID'::uuid, NOW(), '{\"order_id\": \"123\", \"email\": \"test@test.com\"}'::jsonb);" 2>&1 | grep -q "PII key detected"; then
    echo "✅ PASS: PII guardrail correctly blocked INSERT with PII key"
else
    echo "❌ FAIL: PII guardrail did not block INSERT with PII key"
    exit 1
fi
echo ""

# Test 2: INSERT with PII in value (should succeed - expected limitation)
echo "Test 2: INSERT with PII in value (should SUCCEED - expected limitation)"
echo "Command: INSERT INTO attribution_events (tenant_id, occurred_at, raw_payload) VALUES ('$TENANT_ID', NOW(), '{\"order_id\": \"123\", \"notes\": \"contact test@test.com\"}'::jsonb);"
echo ""
if psql "$DATABASE_URL" -c "INSERT INTO attribution_events (tenant_id, occurred_at, raw_payload) VALUES ('$TENANT_ID'::uuid, NOW(), '{\"order_id\": \"123\", \"notes\": \"contact test@test.com\"}'::jsonb);" > /dev/null 2>&1; then
    echo "✅ PASS: INSERT with PII in value succeeded (expected limitation)"
else
    echo "❌ FAIL: INSERT with PII in value failed (unexpected)"
    exit 1
fi
echo ""

# Test 3: INSERT into revenue_ledger with PII in metadata (should fail)
echo "Test 3: INSERT into revenue_ledger with PII in metadata (should FAIL)"
echo "Command: INSERT INTO revenue_ledger (tenant_id, transaction_id, amount_cents, currency, state, verification_source, verification_timestamp, metadata) VALUES ('$TENANT_ID', 'tx_test_123', 1000, 'USD', 'captured', 'test', NOW(), '{\"processor\": \"stripe\", \"email\": \"test@test.com\"}'::jsonb);"
echo ""
if psql "$DATABASE_URL" -c "INSERT INTO revenue_ledger (tenant_id, transaction_id, amount_cents, currency, state, verification_source, verification_timestamp, metadata) VALUES ('$TENANT_ID'::uuid, 'tx_test_123', 1000, 'USD', 'captured', 'test', NOW(), '{\"processor\": \"stripe\", \"email\": \"test@test.com\"}'::jsonb);" 2>&1 | grep -q "PII key detected"; then
    echo "✅ PASS: PII guardrail correctly blocked INSERT into revenue_ledger.metadata with PII key"
else
    echo "❌ FAIL: PII guardrail did not block INSERT into revenue_ledger.metadata with PII key"
    exit 1
fi
echo ""

# Test 4: INSERT into revenue_ledger with NULL metadata (should succeed)
echo "Test 4: INSERT into revenue_ledger with NULL metadata (should SUCCEED)"
echo "Command: INSERT INTO revenue_ledger (tenant_id, transaction_id, amount_cents, currency, state, verification_source, verification_timestamp, metadata) VALUES ('$TENANT_ID', 'tx_null_metadata_124', 1000, 'USD', 'captured', 'test', NOW(), NULL);"
echo ""
if psql "$DATABASE_URL" -c "INSERT INTO revenue_ledger (tenant_id, transaction_id, amount_cents, currency, state, verification_source, verification_timestamp, metadata) VALUES ('$TENANT_ID'::uuid, 'tx_null_metadata_124', 1000, 'USD', 'captured', 'test', NOW(), NULL);" > /dev/null 2>&1; then
    echo "✅ PASS: INSERT with NULL metadata succeeded (allowed)"
else
    echo "❌ FAIL: INSERT with NULL metadata failed (unexpected)"
    exit 1
fi
echo ""

# Cleanup
echo "Cleaning up test data..."
psql "$DATABASE_URL" -c "DELETE FROM revenue_ledger WHERE tenant_id = '$TENANT_ID'::uuid;" > /dev/null 2>&1 || true
psql "$DATABASE_URL" -c "DELETE FROM attribution_events WHERE tenant_id = '$TENANT_ID'::uuid;" > /dev/null 2>&1 || true
psql "$DATABASE_URL" -c "DELETE FROM tenants WHERE id = '$TENANT_ID'::uuid;" > /dev/null 2>&1 || true
echo ""

echo "=========================================="
echo "✅ All PII guardrail validation tests passed"
echo "=========================================="

