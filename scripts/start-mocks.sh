#!/bin/bash

# Skeldir 2.0 - Mockoon Mock Server Startup Script
# Starts all 5 Mockoon mock servers on ports 4010-4014
# NOTE: Webhook services (4015-4018) are NOT started - they are backend-only

set -e

echo "🚀 Starting Skeldir 2.0 Mockoon Mock Servers"
echo "=============================================="
echo ""
echo "Migration: Prism → Mockoon"
echo "Services: 5 frontend-facing APIs only"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Mockoon environment files directory
MOCKOON_DIR="mockoon/environments"

# Function to start a Mockoon server
start_mockoon_server() {
  local env_file=$1
  local port=$2
  local name=$3
  
  if [ ! -f "$MOCKOON_DIR/$env_file" ]; then
    echo -e "${RED}✗ ERROR: $name${NC}"
    echo "   Missing: $MOCKOON_DIR/$env_file"
    echo "   Status: Environment file not found"
    echo ""
    return 1
  fi
  
  echo -e "${GREEN}✓ Starting: $name (port $port)${NC}"
  npx mockoon-cli start --data "$MOCKOON_DIR/$env_file" --port $port > /dev/null 2>&1 &
  local pid=$!
  echo "   PID: $pid"
  echo "   URL: http://localhost:$port"
  echo ""
}

# Start all 5 mock servers (frontend-facing only)
echo "Starting Mockoon servers..."
echo ""

start_mockoon_server "auth.json" 4010 "Authentication Service"
start_mockoon_server "attribution.json" 4011 "Attribution Service"
start_mockoon_server "reconciliation.json" 4012 "Reconciliation Service"
start_mockoon_server "export.json" 4013 "Export Service"
start_mockoon_server "health.json" 4014 "Health Monitoring Service"

echo "=============================================="
echo -e "${GREEN}✓ Mockoon servers started successfully!${NC}"
echo ""
echo "Available services:"
echo "  • Authentication:    http://localhost:4010"
echo "  • Attribution:       http://localhost:4011"
echo "  • Reconciliation:    http://localhost:4012"
echo "  • Export:            http://localhost:4013"
echo "  • Health Monitoring: http://localhost:4014"
echo ""
echo -e "${YELLOW}NOTE: Webhook ports (4015-4018) NOT started${NC}"
echo "      (Backend receives webhooks, frontend does NOT call them)"
echo ""
echo "Health check: npm run mocks:health"
echo "Stop servers:  npm run mocks:stop"
echo ""
echo "Press Ctrl+C to stop all servers"
echo ""

# Keep script running
wait
