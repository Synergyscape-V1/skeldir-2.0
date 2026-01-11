#!/bin/bash
# End-to-end integration test for OpenAPI → Pydantic pipeline

set -e

echo "=== Integration Test: OpenAPI → Pydantic Pipeline ==="

# Clean slate
rm -rf api-contracts/dist
# Preserve hand-written schemas; only remove generated stubs if present.
find backend/app/schemas -maxdepth 1 -type f -name "generated_*.py" -delete

# Step 1: Bundle contracts
echo -e "\n[1/5] Bundling contracts..."
bash scripts/contracts/bundle.sh

# Verify bundled files exist
BUNDLE_COUNT=$(find api-contracts/dist/openapi/v1 -name "*.bundled.yaml" | wc -l)
if [ "$BUNDLE_COUNT" -ne 9 ]; then
    echo "ERROR: Expected 9 bundles, found $BUNDLE_COUNT"
    exit 1
fi
echo "✓ Bundling successful ($BUNDLE_COUNT bundles)"

# Step 2: Validate bundles
echo -e "\n[2/5] Validating bundled contracts..."
for bundle in api-contracts/dist/openapi/v1/*.bundled.yaml; do
    npx @openapitools/openapi-generator-cli validate -i "$bundle"
done
echo "✓ All bundles valid"

# Step 3: Generate models
echo -e "\n[3/5] Generating Pydantic models..."
bash scripts/generate-models.sh
echo "✓ Model generation successful"

# Step 4: Validate model structures
echo -e "\n[4/5] Validating model structures..."
python scripts/validate_model_usage.py
echo "✓ Model structures valid"

# Step 5: Run model tests
echo -e "\n[5/5] Running model unit tests..."
cd backend
pytest tests/test_generated_models.py -v
cd ..
echo "✓ Model tests pass"

echo -e "\n=== Integration Test PASSED ==="





