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
BUNDLED_DIR="api-contracts/dist/openapi/v1"
SCHEMAS_DIR="backend/app/schemas"
PYTHON_VERSION="3.11"

echo -e "${GREEN}Generating Pydantic models from bundled OpenAPI contracts...${NC}"

# Check if bundled files exist
if [ ! -d "$BUNDLED_DIR" ]; then
    echo -e "${RED}Error: Bundled contracts not found in $BUNDLED_DIR${NC}"
    echo -e "${YELLOW}Please run scripts/contracts/bundle.sh first to generate bundled artifacts.${NC}"
    exit 1
fi

# Check if datamodel-codegen is installed
if ! command -v datamodel-codegen &> /dev/null; then
    echo -e "${YELLOW}datamodel-codegen not found. Installing...${NC}"
    pip install -r backend/requirements-dev.txt
fi

# Create schemas directory if it doesn't exist
mkdir -p "$SCHEMAS_DIR"

# Generate models for each domain contract (using bundled files)
for domain in attribution auth reconciliation export; do
    BUNDLED_FILE="$BUNDLED_DIR/${domain}.bundled.yaml"
    if [ -f "$BUNDLED_FILE" ]; then
        echo -e "${GREEN}Generating models from ${domain}.bundled.yaml...${NC}"
        OUTPUT_FILE="$SCHEMAS_DIR/${domain}.py"
        CODEGEN_LOG="/tmp/codegen_${domain}.log"
        
        if datamodel-codegen \
            --input "$BUNDLED_FILE" \
            --output "$OUTPUT_FILE" \
            --target-python-version "$PYTHON_VERSION" \
            --use-annotated \
            --use-standard-collections \
            --use-schema-description \
            --use-field-description \
            --disable-timestamp \
            --input-file-type openapi 2>&1 | tee "$CODEGEN_LOG" | grep -q "Models not found"; then
            echo -e "${RED}ERROR: No models found in ${domain}.bundled.yaml${NC}"
            echo -e "${YELLOW}This indicates schemas are not properly componentized.${NC}"
            cat "$CODEGEN_LOG"
            exit 1
        fi
        
        # Post-generation validation
        if [ ! -f "$OUTPUT_FILE" ]; then
            echo -e "${RED}ERROR: $OUTPUT_FILE was not created${NC}"
            exit 1
        fi
        
        # Check file is non-trivial (contains actual class definitions)
        if ! grep -q "^class " "$OUTPUT_FILE"; then
            echo -e "${RED}ERROR: $OUTPUT_FILE contains no class definitions${NC}"
            cat "$OUTPUT_FILE"
            exit 1
        fi
        
        # Check file size > 100 bytes (not just stub comment)
        FILE_SIZE=$(wc -c < "$OUTPUT_FILE" 2>/dev/null || echo 0)
        if [ "$FILE_SIZE" -lt 100 ]; then
            echo -e "${RED}ERROR: $OUTPUT_FILE is too small ($FILE_SIZE bytes), likely a stub${NC}"
            exit 1
        fi
        
        CLASS_COUNT=$(grep -c "^class " "$OUTPUT_FILE" || echo 0)
        echo -e "${GREEN}✓ Generated $OUTPUT_FILE with $CLASS_COUNT classes${NC}"
        
        # Operational Gate P1: Validate critical classes exist for this domain
        case "$domain" in
            attribution)
                if ! grep -q "class RealtimeRevenueResponse" "$OUTPUT_FILE"; then
                    echo -e "${RED}ERROR: RealtimeRevenueResponse class missing from $OUTPUT_FILE${NC}"
                    echo -e "${YELLOW}This indicates the schema was removed from components/schemas${NC}"
                    exit 1
                fi
                ;;
            auth)
                for model in LoginRequest LoginResponse RefreshRequest RefreshResponse; do
                    if ! grep -q "class ${model}" "$OUTPUT_FILE"; then
                        echo -e "${RED}ERROR: ${model} class missing from $OUTPUT_FILE${NC}"
                        echo -e "${YELLOW}This indicates the schema was removed from components/schemas${NC}"
                        exit 1
                    fi
                done
                ;;
            reconciliation)
                if ! grep -q "class ReconciliationStatusResponse" "$OUTPUT_FILE"; then
                    echo -e "${RED}ERROR: ReconciliationStatusResponse class missing from $OUTPUT_FILE${NC}"
                    echo -e "${YELLOW}This indicates the schema was removed from components/schemas${NC}"
                    exit 1
                fi
                ;;
            export)
                if ! grep -q "class ExportRevenueResponse" "$OUTPUT_FILE"; then
                    echo -e "${RED}ERROR: ExportRevenueResponse class missing from $OUTPUT_FILE${NC}"
                    echo -e "${YELLOW}This indicates the schema was removed from components/schemas${NC}"
                    exit 1
                fi
                ;;
        esac
    else
        echo -e "${YELLOW}Warning: $BUNDLED_FILE not found, skipping...${NC}"
        echo -e "${YELLOW}Run scripts/contracts/bundle.sh to generate bundled artifacts.${NC}"
    fi
done

# Generate models for webhook contracts (using bundled files)
for webhook in shopify woocommerce stripe paypal; do
    BUNDLED_FILE="$BUNDLED_DIR/webhooks.${webhook}.bundled.yaml"
    if [ -f "$BUNDLED_FILE" ]; then
        echo -e "${GREEN}Generating models from webhooks.${webhook}.bundled.yaml...${NC}"
        OUTPUT_FILE="$SCHEMAS_DIR/webhooks_${webhook}.py"
        CODEGEN_LOG="/tmp/codegen_webhooks_${webhook}.log"
        
        if datamodel-codegen \
            --input "$BUNDLED_FILE" \
            --output "$OUTPUT_FILE" \
            --target-python-version "$PYTHON_VERSION" \
            --use-annotated \
            --use-standard-collections \
            --use-schema-description \
            --use-field-description \
            --disable-timestamp \
            --input-file-type openapi 2>&1 | tee "$CODEGEN_LOG" | grep -q "Models not found"; then
            echo -e "${RED}ERROR: No models found in webhooks.${webhook}.bundled.yaml${NC}"
            echo -e "${YELLOW}This indicates schemas are not properly componentized.${NC}"
            cat "$CODEGEN_LOG"
            exit 1
        fi
        
        # Post-generation validation
        if [ ! -f "$OUTPUT_FILE" ]; then
            echo -e "${RED}ERROR: $OUTPUT_FILE was not created${NC}"
            exit 1
        fi
        
        # Check file is non-trivial (contains actual class definitions)
        if ! grep -q "^class " "$OUTPUT_FILE"; then
            echo -e "${RED}ERROR: $OUTPUT_FILE contains no class definitions${NC}"
            cat "$OUTPUT_FILE"
            exit 1
        fi
        
        # Check file size > 100 bytes (not just stub comment)
        FILE_SIZE=$(wc -c < "$OUTPUT_FILE" 2>/dev/null || echo 0)
        if [ "$FILE_SIZE" -lt 100 ]; then
            echo -e "${RED}ERROR: $OUTPUT_FILE is too small ($FILE_SIZE bytes), likely a stub${NC}"
            exit 1
        fi
        
        CLASS_COUNT=$(grep -c "^class " "$OUTPUT_FILE" || echo 0)
        echo -e "${GREEN}✓ Generated $OUTPUT_FILE with $CLASS_COUNT classes${NC}"
        
        # Operational Gate P1: Validate critical webhook classes exist
        case "$webhook" in
            shopify)
                for model in ShopifyOrderCreateRequest WebhookAcknowledgement; do
                    if ! grep -q "class ${model}" "$OUTPUT_FILE"; then
                        echo -e "${RED}ERROR: ${model} class missing from $OUTPUT_FILE${NC}"
                        echo -e "${YELLOW}This indicates the schema was removed from components/schemas${NC}"
                        exit 1
                    fi
                done
                ;;
            woocommerce)
                for model in WooCommerceOrderCreateRequest WebhookAcknowledgement; do
                    if ! grep -q "class ${model}" "$OUTPUT_FILE"; then
                        echo -e "${RED}ERROR: ${model} class missing from $OUTPUT_FILE${NC}"
                        echo -e "${YELLOW}This indicates the schema was removed from components/schemas${NC}"
                        exit 1
                    fi
                done
                ;;
            stripe)
                for model in StripeChargeSucceededRequest WebhookAcknowledgement; do
                    if ! grep -q "class ${model}" "$OUTPUT_FILE"; then
                        echo -e "${RED}ERROR: ${model} class missing from $OUTPUT_FILE${NC}"
                        echo -e "${YELLOW}This indicates the schema was removed from components/schemas${NC}"
                        exit 1
                    fi
                done
                ;;
            paypal)
                for model in PayPalSaleCompletedRequest WebhookAcknowledgement; do
                    if ! grep -q "class ${model}" "$OUTPUT_FILE"; then
                        echo -e "${RED}ERROR: ${model} class missing from $OUTPUT_FILE${NC}"
                        echo -e "${YELLOW}This indicates the schema was removed from components/schemas${NC}"
                        exit 1
                    fi
                done
                ;;
        esac
    else
        echo -e "${YELLOW}Warning: $BUNDLED_FILE not found, skipping...${NC}"
        echo -e "${YELLOW}Run scripts/contracts/bundle.sh to generate bundled artifacts.${NC}"
    fi
done

# Pydantic v2 compatibility patch (regex -> pattern)
python - <<'PYEOF'
from pathlib import Path
SCHEMAS_DIR = Path("backend/app/schemas")
for path in SCHEMAS_DIR.glob("*.py"):
    text = path.read_text()
    if "regex=" in text:
        path.write_text(text.replace("regex=", "pattern="))
        print(f"Patched regex->pattern in {path}")
PYEOF

# Create __init__.py if it doesn't exist
if [ ! -f "$SCHEMAS_DIR/__init__.py" ]; then
    echo -e "${GREEN}Creating $SCHEMAS_DIR/__init__.py...${NC}"
    cat > "$SCHEMAS_DIR/__init__.py" << 'EOF'
"""
Pydantic models generated from bundled OpenAPI contracts.

These models are auto-generated from api-contracts/dist/openapi/v1/*.bundled.yaml files.
Do not edit manually. Regenerate using scripts/generate-models.sh after contract changes.
Note: Bundled artifacts are generated from source specs via scripts/contracts/bundle.sh.
"""

# Import all models for easy access
from .attribution import *
from .auth import *
from .reconciliation import *
from .export import *
from .webhooks_shopify import *
from .webhooks_stripe import *
from .webhooks_paypal import *
from .webhooks_woocommerce import *

# If import fails, the error should propagate (no try/except suppression)

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

# Add import sanity check
echo -e "${GREEN}Running import sanity check...${NC}"
python - << 'PYEOF'
import sys
import importlib

modules = [
    "backend.app.schemas.attribution",
    "backend.app.schemas.auth",
    "backend.app.schemas.reconciliation",
    "backend.app.schemas.export",
    "backend.app.schemas.webhooks_shopify",
    "backend.app.schemas.webhooks_woocommerce",
    "backend.app.schemas.webhooks_stripe",
    "backend.app.schemas.webhooks_paypal",
]

failed = []
for module_name in modules:
    try:
        importlib.import_module(module_name)
        print(f"[OK] {module_name} imports successfully")
    except Exception as e:
        print(f"[FAIL] {module_name} failed: {e}")
        failed.append(module_name)

if failed:
    print(f"\nERROR: {len(failed)} module(s) failed import validation")
    sys.exit(1)
print("\n[OK] All generated modules import successfully")
PYEOF

if [ $? -ne 0 ]; then
    echo -e "${RED}ERROR: Import sanity check failed${NC}"
    exit 1
fi

echo -e "${GREEN}Model generation completed successfully!${NC}"
