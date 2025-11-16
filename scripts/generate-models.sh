#!/bin/bash
# Pydantic Model Generation Script
# Generates Pydantic v2 models from OpenAPI contracts using datamodel-codegen

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
CONTRACTS_DIR="contracts"
SCHEMAS_DIR="backend/app/schemas"
PYTHON_VERSION="3.11"

echo -e "${GREEN}Generating Pydantic models from OpenAPI contracts...${NC}"

# Check if datamodel-codegen is installed
if ! command -v datamodel-codegen &> /dev/null; then
    echo -e "${YELLOW}datamodel-codegen not found. Installing...${NC}"
    pip install datamodel-code-generator[openapi] pydantic>=2.0.0
fi

# Create schemas directory if it doesn't exist
mkdir -p "$SCHEMAS_DIR"

# Generate models for each domain contract
for domain in attribution auth reconciliation export; do
    CONTRACT_FILE="$CONTRACTS_DIR/${domain}/v1/${domain}.yaml"
    if [ -f "$CONTRACT_FILE" ]; then
        echo -e "${GREEN}Generating models from ${domain}.yaml...${NC}"
        if datamodel-codegen \
            --input "$CONTRACT_FILE" \
            --output "$SCHEMAS_DIR/${domain}.py" \
            --target-python-version "$PYTHON_VERSION" \
            --use-annotated \
            --use-standard-collections \
            --use-schema-description \
            --use-field-description \
            --disable-timestamp \
            --input-file-type openapi 2>&1 | grep -q "Models not found"; then
            echo -e "${YELLOW}No models found in ${domain}.yaml (inline schemas), skipping...${NC}"
            # Create placeholder file to satisfy CI check
            echo "# No models generated - ${domain}.yaml uses inline schemas" > "$SCHEMAS_DIR/${domain}.py"
        else
            echo -e "${GREEN}✓ Generated $SCHEMAS_DIR/${domain}.py${NC}"
        fi
    else
        echo -e "${YELLOW}Warning: $CONTRACT_FILE not found, skipping...${NC}"
    fi
done

# Generate models for webhook contracts
for webhook in shopify stripe paypal woocommerce; do
    CONTRACT_FILE="$CONTRACTS_DIR/webhooks/v1/${webhook}.yaml"
    if [ -f "$CONTRACT_FILE" ]; then
        echo -e "${GREEN}Generating models from ${webhook}.yaml...${NC}"
        if datamodel-codegen \
            --input "$CONTRACT_FILE" \
            --output "$SCHEMAS_DIR/webhooks_${webhook}.py" \
            --target-python-version "$PYTHON_VERSION" \
            --use-annotated \
            --use-standard-collections \
            --use-schema-description \
            --use-field-description \
            --disable-timestamp \
            --input-file-type openapi 2>&1 | grep -q "Models not found"; then
            echo -e "${YELLOW}No models found in ${webhook}.yaml (inline schemas), skipping...${NC}"
            # Create placeholder file to satisfy CI check
            echo "# No models generated - ${webhook}.yaml uses inline schemas" > "$SCHEMAS_DIR/webhooks_${webhook}.py"
        else
            echo -e "${GREEN}✓ Generated $SCHEMAS_DIR/webhooks_${webhook}.py${NC}"
        fi
    else
        echo -e "${YELLOW}Warning: $CONTRACT_FILE not found, skipping...${NC}"
    fi
done

# Create __init__.py if it doesn't exist
if [ ! -f "$SCHEMAS_DIR/__init__.py" ]; then
    echo -e "${GREEN}Creating $SCHEMAS_DIR/__init__.py...${NC}"
    cat > "$SCHEMAS_DIR/__init__.py" << 'EOF'
"""
Pydantic models generated from OpenAPI contracts.

These models are auto-generated from contracts/openapi/v1/*.yaml files.
Do not edit manually. Regenerate using scripts/generate-models.sh after contract changes.
"""

# Import all models for easy access
try:
    from .attribution import *
    from .auth import *
    from .reconciliation import *
    from .export import *
    from .webhooks_shopify import *
    from .webhooks_stripe import *
    from .webhooks_paypal import *
    from .webhooks_woocommerce import *
except ImportError:
    # Models not yet generated
    pass

__all__ = [
    # Attribution models
    # Auth models
    # Reconciliation models
    # Export models
    # Webhook models
    # Add other model exports as they are generated
]
EOF
    echo -e "${GREEN}✓ Created $SCHEMAS_DIR/__init__.py${NC}"
fi

echo -e "${GREEN}Model generation completed successfully!${NC}"

