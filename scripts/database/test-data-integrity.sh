#!/bin/bash
# Test Data Integrity Controls
#
# Purpose: Test RLS, immutability, and sum-equality controls
# Usage: ./test-data-integrity.sh [DATABASE_URL]
#
# Expected Behavior:
# - RLS: Cross-tenant data access blocked
# - Immutability: UPDATE/DELETE on attribution_events fails
# - Sum-equality: Invalid allocation sum fails

set -euo pipefail

DATABASE_URL="${1:-${DATABASE_URL:-}}"

if [ -z "$DATABASE_URL" ]; then
    echo "Error: DATABASE_URL not provided"
    echo "Usage: $0 [DATABASE_URL]"
    exit 1
fi

echo "=========================================="
echo "Data Integrity Controls Validation"
echo "=========================================="
echo ""

# Create test tenants
echo "Step 1: Creating test tenants..."
TENANT_1=$(psql "$DATABASE_URL" -t -c "INSERT INTO tenants (id, name) VALUES (gen_random_uuid(), 'test_tenant_1') RETURNING id;" | xargs)
TENANT_2=$(psql "$DATABASE_URL" -t -c "INSERT INTO tenants (id, name) VALUES (gen_random_uuid(), 'test_tenant_2') RETURNING id;" | xargs)
echo "Created tenant 1: $TENANT_1"
echo "Created tenant 2: $TENANT_2"
echo ""

# Create test event for tenant 1
echo "Step 2: Creating test event for tenant 1..."
EVENT_ID=$(psql "$DATABASE_URL" -t -c "INSERT INTO attribution_events (tenant_id, occurred_at, raw_payload, revenue_cents) VALUES ('$TENANT_1'::uuid, NOW(), '{\"order_id\": \"test-123\"}'::jsonb, 10000) RETURNING id;" | xargs)
echo "Created event: $EVENT_ID"
echo ""

# Test 1: RLS - Cross-tenant access blocked
echo "Test 1: RLS - Cross-tenant data access (should be BLOCKED)"
echo "Setting tenant context to tenant 1..."
psql "$DATABASE_URL" -c "SET app.current_tenant_id = '$TENANT_1'; SELECT COUNT(*) FROM attribution_events WHERE id = '$EVENT_ID'::uuid;" > /dev/null 2>&1
echo "Setting tenant context to tenant 2..."
TENANT_2_COUNT=$(psql "$DATABASE_URL" -t -c "SET app.current_tenant_id = '$TENANT_2'; SELECT COUNT(*) FROM attribution_events WHERE id = '$EVENT_ID'::uuid;" | xargs)
if [ "$TENANT_2_COUNT" -eq 0 ]; then
    echo "✅ PASS: RLS correctly blocked cross-tenant data access"
else
    echo "❌ FAIL: RLS did not block cross-tenant data access"
    exit 1
fi
echo ""

# Test 2: Immutability - UPDATE blocked
echo "Test 2: Immutability - UPDATE on attribution_events (should FAIL)"
echo "Command: UPDATE attribution_events SET revenue_cents = 2000 WHERE id = '$EVENT_ID'::uuid;"
echo ""
if psql "$DATABASE_URL" -c "UPDATE attribution_events SET revenue_cents = 2000 WHERE id = '$EVENT_ID'::uuid;" 2>&1 | grep -q "immutability\|prevent_mutation"; then
    echo "✅ PASS: Immutability trigger correctly blocked UPDATE"
else
    echo "❌ FAIL: Immutability trigger did not block UPDATE"
    exit 1
fi
echo ""

# Test 3: Immutability - DELETE blocked
echo "Test 3: Immutability - DELETE on attribution_events (should FAIL)"
echo "Command: DELETE FROM attribution_events WHERE id = '$EVENT_ID'::uuid;"
echo ""
if psql "$DATABASE_URL" -c "DELETE FROM attribution_events WHERE id = '$EVENT_ID'::uuid;" 2>&1 | grep -q "immutability\|prevent_mutation"; then
    echo "✅ PASS: Immutability trigger correctly blocked DELETE"
else
    echo "❌ FAIL: Immutability trigger did not block DELETE"
    exit 1
fi
echo ""

# Test 4: Sum-equality - Invalid allocation sum fails
echo "Test 4: Sum-equality - Invalid allocation sum (should FAIL)"
echo "Creating allocations that don't sum to event revenue..."
echo "Event revenue: 10000 cents"
echo "Allocations: 5000 + 4000 = 9000 cents (should fail)"
echo ""
if psql "$DATABASE_URL" -c "
    INSERT INTO attribution_allocations (tenant_id, event_id, channel_code, allocated_revenue_cents, confidence_score)
    VALUES 
        ('$TENANT_1'::uuid, '$EVENT_ID'::uuid, 'organic', 5000, 0.5),
        ('$TENANT_1'::uuid, '$EVENT_ID'::uuid, 'paid', 4000, 0.5);
" 2>&1 | grep -q "sum.*equality\|allocation.*sum"; then
    echo "✅ PASS: Sum-equality validation correctly blocked invalid allocation sum"
else
    echo "❌ FAIL: Sum-equality validation did not block invalid allocation sum"
    exit 1
fi
echo ""

# Test 5: Sum-equality - Valid allocation sum succeeds
echo "Test 5: Sum-equality - Valid allocation sum (should SUCCEED)"
echo "Creating allocations that sum to event revenue..."
echo "Event revenue: 10000 cents"
echo "Allocations: 6000 + 4000 = 10000 cents (should succeed)"
echo ""
if psql "$DATABASE_URL" -c "
    INSERT INTO attribution_allocations (tenant_id, event_id, channel_code, allocated_revenue_cents, confidence_score)
    VALUES 
        ('$TENANT_1'::uuid, '$EVENT_ID'::uuid, 'organic', 6000, 0.6),
        ('$TENANT_1'::uuid, '$EVENT_ID'::uuid, 'paid', 4000, 0.4);
" > /dev/null 2>&1; then
    echo "✅ PASS: Sum-equality validation allowed valid allocation sum"
else
    echo "❌ FAIL: Sum-equality validation blocked valid allocation sum"
    exit 1
fi
echo ""

# Cleanup
echo "Cleaning up test data..."
psql "$DATABASE_URL" -c "DELETE FROM attribution_allocations WHERE tenant_id = '$TENANT_1'::uuid;" > /dev/null 2>&1 || true
psql "$DATABASE_URL" -c "DELETE FROM attribution_events WHERE tenant_id = '$TENANT_1'::uuid;" > /dev/null 2>&1 || true
psql "$DATABASE_URL" -c "DELETE FROM tenants WHERE id IN ('$TENANT_1'::uuid, '$TENANT_2'::uuid);" > /dev/null 2>&1 || true
echo ""

echo "=========================================="
echo "✅ All data integrity validation tests passed"
echo "=========================================="

