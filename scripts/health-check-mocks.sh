#!/bin/bash

# Skeldir 2.0 - Mock Server Health Check Script
# Validates all 9 Prism mock servers are responding

echo "=============================================="
echo "  Skeldir 2.0 - Mock Server Health Check"
echo "=============================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
healthy_count=0
unhealthy_count=0
total_count=0

# Function to check a service endpoint
check_service() {
    local name=$1
    local port=$2
    local endpoint=$3
    local method=${4:-GET}
    
    ((total_count++))
    
    echo -e "${BLUE}→ Checking: $name (port $port)${NC}"
    
    local url="http://localhost:$port$endpoint"
    local response
    local http_code
    
    # Make request with correlation ID header
    if [ "$method" == "POST" ]; then
        response=$(curl -s -o /dev/null -w "%{http_code}" \
            -X POST \
            -H "X-Correlation-ID: $(uuidgen 2>/dev/null || echo 'health-check-uuid')" \
            -H "Content-Type: application/json" \
            -d '{}' \
            --max-time 5 \
            "$url" 2>/dev/null)
    else
        response=$(curl -s -o /dev/null -w "%{http_code}" \
            -H "X-Correlation-ID: $(uuidgen 2>/dev/null || echo 'health-check-uuid')" \
            --max-time 5 \
            "$url" 2>/dev/null)
    fi
    
    http_code=$response
    
    # Check response code
    if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 500 ]; then
        echo -e "${GREEN}  ✓ Healthy (HTTP $http_code)${NC}"
        echo "    URL: $url"
        ((healthy_count++))
    elif [ "$http_code" == "000" ]; then
        echo -e "${RED}  ✗ Unreachable (Connection refused)${NC}"
        echo "    URL: $url"
        ((unhealthy_count++))
    else
        echo -e "${RED}  ✗ Unhealthy (HTTP $http_code)${NC}"
        echo "    URL: $url"
        ((unhealthy_count++))
    fi
    echo ""
}

# Check Frontend-Facing Services
echo "Frontend Services (ports 4010-4014):"
echo "-------------------------------------"
check_service "Auth" 4010 "/api/auth/verify"
check_service "Attribution" 4011 "/api/attribution/revenue/realtime"
check_service "Reconciliation" 4012 "/api/reconciliation/status"
check_service "Export" 4013 "/api/export/csv"
check_service "Health" 4014 "/api/health"

# Check Webhook Services
echo "Webhook Services (ports 4015-4018):"
echo "------------------------------------"
check_service "Shopify Webhooks" 4015 "/webhooks/shopify/orders/create" "POST"
check_service "WooCommerce Webhooks" 4016 "/webhooks/woocommerce/order/created" "POST"
check_service "Stripe Webhooks" 4017 "/webhooks/stripe/charge/succeeded" "POST"
check_service "PayPal Webhooks" 4018 "/webhooks/paypal/payment/sale/completed" "POST"

# Summary
echo "=============================================="
echo "Health Check Summary:"
echo ""
echo -e "  ${GREEN}Healthy:   $healthy_count / $total_count${NC}"
if [ $unhealthy_count -gt 0 ]; then
    echo -e "  ${RED}Unhealthy: $unhealthy_count / $total_count${NC}"
fi
echo ""

# Calculate percentage and exit code
if [ $total_count -gt 0 ]; then
    percentage=$((healthy_count * 100 / total_count))
    echo "  Health: $percentage%"
fi

echo ""

# Exit with appropriate code
if [ $unhealthy_count -eq 0 ]; then
    echo -e "${GREEN}✓ All mock servers operational!${NC}"
    echo "=============================================="
    exit 0
else
    echo -e "${RED}✗ Some mock servers are not responding.${NC}"
    echo ""
    echo "Troubleshooting:"
    echo "  1. Start mock servers: ./scripts/start-mocks-prism.sh"
    echo "  2. Check logs: tail -f /tmp/skeldir-mocks/prism_<port>.log"
    echo "  3. Verify contracts: ./scripts/validate-contracts.sh"
    echo "=============================================="
    exit 1
fi
