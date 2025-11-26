#!/bin/bash

# Skeldir 2.0 - Mockoon Health Check Script
# Validates all 5 Mockoon mock servers are running and responding

set -e

echo "🔍 Mockoon Health Check"
echo "======================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Track overall health
ALL_HEALTHY=true

# Function to check a single service
check_service() {
  local name=$1
  local port=$2
  local endpoint=$3
  
  echo -n "Checking $name (port $port)... "
  
  if curl -s -f -m 5 "http://localhost:$port$endpoint" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ HEALTHY${NC}"
  else
    echo -e "${RED}✗ UNHEALTHY${NC}"
    ALL_HEALTHY=false
  fi
}

# Check all 5 frontend-facing services
echo "Checking services:"
echo ""

check_service "Authentication  " 4010 "/api/auth/verify"
check_service "Attribution     " 4011 "/api/attribution/revenue/realtime"
check_service "Reconciliation  " 4012 "/api/reconciliation/status"
check_service "Export          " 4013 "/api/export/json"
check_service "Health Monitoring" 4014 "/api/health"

echo ""
echo "======================="

if [ "$ALL_HEALTHY" = true ]; then
  echo -e "${GREEN}✓ All services healthy${NC}"
  echo ""
  exit 0
else
  echo -e "${RED}✗ Some services unhealthy${NC}"
  echo ""
  echo "Troubleshooting:"
  echo "  1. Check if servers are running: ps aux | grep mockoon"
  echo "  2. Restart servers: npm run mocks:stop && npm run mocks:start"
  echo "  3. Check port availability: lsof -i :4010-4014"
  echo ""
  exit 1
fi
