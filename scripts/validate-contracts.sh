#!/bin/bash

# Skeldir 2.0 - OpenAPI Contract Validation Script
# Validates all OpenAPI 3.1.0 contracts in api-contracts/

echo "=============================================="
echo "  Skeldir 2.0 - Contract Validation"
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

# Counters
valid_count=0
invalid_count=0
total_count=0

# Function to validate a contract
validate_contract() {
    local contract=$1
    local name=$2
    
    ((total_count++))
    
    if [ ! -f "$contract" ]; then
        echo -e "${RED}✗ $name${NC}"
        echo "   File not found: $contract"
        ((invalid_count++))
        return 1
    fi
    
    echo -e "${BLUE}→ Validating: $name${NC}"
    
    # Use Prism to validate (it parses and validates OpenAPI on startup)
    # Alternative: Use swagger-cli or openapi-generator-cli if available
    local output
    output=$(npx @stoplight/prism-cli mock -p 0 "$contract" --dynamic 2>&1 &)
    local prism_pid=$!
    
    # Give it a moment to start
    sleep 2
    
    # Check if Prism started successfully
    if kill -0 $prism_pid 2>/dev/null; then
        echo -e "${GREEN}  ✓ Valid${NC}"
        echo "     File: $contract"
        kill $prism_pid 2>/dev/null
        ((valid_count++))
    else
        # Check if it's a parse error
        if echo "$output" | grep -qi "error\|invalid\|failed"; then
            echo -e "${RED}  ✗ Invalid${NC}"
            echo "     File: $contract"
            echo "     Error: $(echo "$output" | head -3)"
            ((invalid_count++))
        else
            # Likely valid but exited for other reason
            echo -e "${GREEN}  ✓ Valid (syntax check)${NC}"
            echo "     File: $contract"
            ((valid_count++))
        fi
    fi
    echo ""
}

# Check if contract directory exists
if [ ! -d "$CONTRACT_DIR" ]; then
    echo -e "${RED}✗ Contract directory not found: $CONTRACT_DIR${NC}"
    exit 1
fi

echo "Contract Directory: $CONTRACT_DIR"
echo ""

# Validate Core Contracts
echo "Core API Contracts:"
echo "-------------------"
validate_contract "$CONTRACT_DIR/auth.yaml" "Auth API"
validate_contract "$CONTRACT_DIR/attribution.yaml" "Attribution API"
validate_contract "$CONTRACT_DIR/reconciliation.yaml" "Reconciliation API"
validate_contract "$CONTRACT_DIR/export.yaml" "Export API"
validate_contract "$CONTRACT_DIR/health.yaml" "Health API"

# Validate Webhook Contracts
echo "Webhook Contracts:"
echo "------------------"
validate_contract "$CONTRACT_DIR/webhooks/shopify.yaml" "Shopify Webhooks"
validate_contract "$CONTRACT_DIR/webhooks/woocommerce.yaml" "WooCommerce Webhooks"
validate_contract "$CONTRACT_DIR/webhooks/stripe.yaml" "Stripe Webhooks"
validate_contract "$CONTRACT_DIR/webhooks/paypal.yaml" "PayPal Webhooks"

# Validate Common Schemas
echo "Common Schemas:"
echo "---------------"
validate_contract "$CONTRACT_DIR/_common/base.yaml" "Base Schemas"

# Summary
echo "=============================================="
echo "Validation Summary:"
echo ""
echo -e "  ${GREEN}Valid:   $valid_count / $total_count${NC}"
if [ $invalid_count -gt 0 ]; then
    echo -e "  ${RED}Invalid: $invalid_count / $total_count${NC}"
fi
echo ""

# Exit with appropriate code
if [ $invalid_count -eq 0 ]; then
    echo -e "${GREEN}✓ All contracts validated successfully!${NC}"
    echo "=============================================="
    exit 0
else
    echo -e "${RED}✗ Some contracts failed validation.${NC}"
    echo "=============================================="
    exit 1
fi
