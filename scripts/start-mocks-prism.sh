#!/bin/bash

# Skeldir 2.0 - Native Prism Mock Server Startup Script
# Process-based approach (NO DOCKER)
# Starts all 9 Prism mock servers on ports 4010-4018

set -e

echo "=============================================="
echo "  Skeldir 2.0 - Prism Mock Server Startup"
echo "  Process-Based Approach (No Docker)"
echo "=============================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Contract directory
CONTRACT_DIR="api-contracts/openapi/v1"

# PID file directory
PID_DIR="/tmp/skeldir-mocks"
mkdir -p "$PID_DIR"

# Function to check if a port is in use
check_port() {
    local port=$1
    if lsof -i :$port > /dev/null 2>&1; then
        return 0  # Port is in use
    else
        return 1  # Port is free
    fi
}

# Function to start a Prism mock server
start_prism_server() {
    local contract=$1
    local port=$2
    local name=$3
    local pid_file="$PID_DIR/prism_$port.pid"
    
    # Check if contract file exists
    if [ ! -f "$contract" ]; then
        echo -e "${RED}✗ ERROR: $name${NC}"
        echo "   Missing: $contract"
        return 1
    fi
    
    # Check if port is already in use
    if check_port $port; then
        echo -e "${YELLOW}⚠ WARNING: $name (port $port) already in use${NC}"
        echo "   Skipping startup - service may already be running"
        return 0
    fi
    
    # Start Prism mock server in background
    echo -e "${BLUE}→ Starting: $name (port $port)${NC}"
    npx @stoplight/prism-cli mock -h 0.0.0.0 -p $port "$contract" > "$PID_DIR/prism_$port.log" 2>&1 &
    local pid=$!
    echo $pid > "$pid_file"
    
    # Wait briefly and verify process started
    sleep 1
    if kill -0 $pid 2>/dev/null; then
        echo -e "${GREEN}✓ Started: $name${NC}"
        echo "   PID: $pid"
        echo "   URL: http://localhost:$port"
    else
        echo -e "${RED}✗ Failed to start: $name${NC}"
        return 1
    fi
    echo ""
}

# Pre-flight checks
echo "Pre-flight Checks:"
echo "------------------"

# Check if Prism is available
if ! command -v npx &> /dev/null; then
    echo -e "${RED}✗ npx not found - Node.js required${NC}"
    exit 1
fi

echo -e "${GREEN}✓ npx available${NC}"

# Check Prism version
PRISM_VERSION=$(npx @stoplight/prism-cli --version 2>/dev/null || echo "unknown")
echo -e "${GREEN}✓ Prism CLI version: $PRISM_VERSION${NC}"

# Check contract directory
if [ ! -d "$CONTRACT_DIR" ]; then
    echo -e "${RED}✗ Contract directory not found: $CONTRACT_DIR${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Contract directory exists${NC}"
echo ""

# Start Frontend-Facing Mock Servers (ports 4010-4014)
echo "Starting Frontend-Facing Services:"
echo "-----------------------------------"
start_prism_server "$CONTRACT_DIR/auth.yaml" 4010 "Auth Service"
start_prism_server "$CONTRACT_DIR/attribution.yaml" 4011 "Attribution Service"
start_prism_server "$CONTRACT_DIR/reconciliation.yaml" 4012 "Reconciliation Service"
start_prism_server "$CONTRACT_DIR/export.yaml" 4013 "Export Service"
start_prism_server "$CONTRACT_DIR/health.yaml" 4014 "Health Service"

# Start Backend-Only Webhook Mock Servers (ports 4015-4018)
echo "Starting Webhook Services (Backend-Only):"
echo "------------------------------------------"
start_prism_server "$CONTRACT_DIR/webhooks/shopify.yaml" 4015 "Shopify Webhooks"
start_prism_server "$CONTRACT_DIR/webhooks/woocommerce.yaml" 4016 "WooCommerce Webhooks"
start_prism_server "$CONTRACT_DIR/webhooks/stripe.yaml" 4017 "Stripe Webhooks"
start_prism_server "$CONTRACT_DIR/webhooks/paypal.yaml" 4018 "PayPal Webhooks"

echo "=============================================="
echo -e "${GREEN}✓ All Prism mock servers started!${NC}"
echo ""
echo "Frontend Services:"
echo "  • Auth:           http://localhost:4010"
echo "  • Attribution:    http://localhost:4011"
echo "  • Reconciliation: http://localhost:4012"
echo "  • Export:         http://localhost:4013"
echo "  • Health:         http://localhost:4014"
echo ""
echo "Webhook Services (Backend-Only):"
echo "  • Shopify:        http://localhost:4015"
echo "  • WooCommerce:    http://localhost:4016"
echo "  • Stripe:         http://localhost:4017"
echo "  • PayPal:         http://localhost:4018"
echo ""
echo -e "${BLUE}Management Commands:${NC}"
echo "  Stop all:    ./scripts/stop-mocks-prism.sh"
echo "  Health check: ./scripts/health-check-mocks.sh"
echo "  View logs:   tail -f $PID_DIR/prism_<port>.log"
echo ""
echo "=============================================="
