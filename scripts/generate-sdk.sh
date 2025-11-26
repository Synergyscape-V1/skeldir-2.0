#!/bin/bash

# Skeldir Attribution Intelligence - SDK Generation Script
# Generates TypeScript SDK from all available OpenAPI contracts

set -e

echo "🔧 Generating TypeScript SDK from OpenAPI Contracts"
echo "===================================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

CONTRACTS_DIR="docs/api/contracts"
OUTPUT_DIR="client/src/api/generated"

# Check if contracts directory exists
if [ ! -d "$CONTRACTS_DIR" ]; then
  echo -e "${RED}Error: Contracts directory not found: $CONTRACTS_DIR${NC}"
  exit 1
fi

# Count available contracts
CONTRACT_COUNT=$(ls -1 $CONTRACTS_DIR/*.yaml 2>/dev/null | wc -l)

if [ "$CONTRACT_COUNT" -eq 0 ]; then
  echo -e "${RED}Error: No OpenAPI contracts found in $CONTRACTS_DIR${NC}"
  echo "Please ensure OpenAPI .yaml files are present in the contracts directory."
  exit 1
fi

echo "Found $CONTRACT_COUNT OpenAPI contract(s):"
ls -1 $CONTRACTS_DIR/*.yaml | xargs -n 1 basename
echo ""

# Remove existing generated SDK
if [ -d "$OUTPUT_DIR" ]; then
  echo "Removing existing SDK..."
  rm -rf "$OUTPUT_DIR"
fi

# Generate SDK from primary contract (attribution.yaml)
PRIMARY_CONTRACT="$CONTRACTS_DIR/attribution.yaml"

if [ -f "$PRIMARY_CONTRACT" ]; then
  echo -e "${GREEN}Generating SDK from attribution.yaml...${NC}"
  
  npx openapi-typescript-codegen \
    --input "$PRIMARY_CONTRACT" \
    --output "$OUTPUT_DIR" \
    --client fetch \
    --name SkelAttributionClient
  
  echo -e "${GREEN}✓ SDK generated successfully${NC}"
  echo ""
else
  echo -e "${RED}Error: Primary contract not found: $PRIMARY_CONTRACT${NC}"
  exit 1
fi

# TODO: When multiple contracts are available, merge them or generate separate clients
# For now, we only support attribution.yaml

echo "===================================================="
echo -e "${GREEN}SDK Generation Complete${NC}"
echo ""
echo "Generated files:"
echo "  • Client: $OUTPUT_DIR/SkelAttributionClient.ts"
echo "  • Models: $OUTPUT_DIR/models/"
echo "  • Services: $OUTPUT_DIR/services/"
echo ""
echo "Next steps:"
echo "  1. Review generated types in $OUTPUT_DIR/models/"
echo "  2. Update sdk-client.ts integration layer if needed"
echo "  3. Run tests: npm test"
echo "  4. Replace useApiClient calls with SDK methods"
echo ""
