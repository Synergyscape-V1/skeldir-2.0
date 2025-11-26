#!/bin/bash

# Skeldir Attribution Intelligence - Mock Server Startup Script
# Starts all 10 Prism mock servers on ports 4010-4019

set -e

echo "🚀 Starting Skeldir Mock Servers (Prism)"
echo "========================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Contract files directory
CONTRACTS_DIR="docs/api/contracts"

# Function to start a mock server
start_mock_server() {
  local contract_file=$1
  local port=$2
  local name=$3
  
  if [ ! -f "$CONTRACTS_DIR/$contract_file" ]; then
    echo -e "${YELLOW}⚠️  SKIP: $name${NC}"
    echo "   Missing: $CONTRACTS_DIR/$contract_file"
    echo "   Status: Awaiting backend team delivery"
    echo ""
    return
  fi
  
  echo -e "${GREEN}✓ Starting: $name (port $port)${NC}"
  npx prism mock "$CONTRACTS_DIR/$contract_file" -p $port > /dev/null 2>&1 &
  echo "   PID: $!"
  echo "   URL: http://localhost:$port"
  echo ""
}

# Start all 10 mock servers (updated configuration per backend specification)
echo "Starting mock servers..."
echo ""

start_mock_server "attribution.yaml" 4010 "Attribution API"
start_mock_server "health.yaml" 4011 "Health Monitoring API"
start_mock_server "export.yaml" 4012 "Export API"
start_mock_server "reconciliation.yaml" 4013 "Reconciliation API"
start_mock_server "errors.yaml" 4014 "Error Logging API"
start_mock_server "auth.yaml" 4015 "Authentication API"
start_mock_server "webhooks/shopify.yaml" 4016 "Shopify Webhooks"
start_mock_server "webhooks/woocommerce.yaml" 4017 "WooCommerce Webhooks"
start_mock_server "webhooks/stripe.yaml" 4018 "Stripe Webhooks"
start_mock_server "webhooks/paypal.yaml" 4019 "PayPal Webhooks"

echo "========================================"
echo -e "${GREEN}Mock servers configuration complete!${NC}"
echo ""
echo "Available servers:"
echo "  • Attribution API:       http://localhost:4010"
echo "  • Health Monitoring:     http://localhost:4011"
echo "  • Export API:           http://localhost:4012"
echo "  • Reconciliation API:   http://localhost:4013"
echo "  • Error Logging API:    http://localhost:4014"
echo "  • Authentication API:   http://localhost:4015"
echo "  • Shopify Webhooks:     http://localhost:4016"
echo "  • WooCommerce Webhooks: http://localhost:4017"
echo "  • Stripe Webhooks:      http://localhost:4018"
echo "  • PayPal Webhooks:      http://localhost:4019"
echo ""
echo "Press Ctrl+C to stop all servers"
echo ""

# Keep script running
wait
