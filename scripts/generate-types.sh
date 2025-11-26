#!/bin/bash

# Wave 2: Type Generation Script
# Generates TypeScript types from OpenAPI contracts

set -e

echo "🔧 Generating TypeScript types from OpenAPI contracts..."
echo ""

# Create output directory
mkdir -p client/src/types/api

# Generate types for each service
echo "Generating auth types..."
npx openapi-typescript external/contracts/openapi/v1/auth.yaml -o client/src/types/api/auth.ts

echo "Generating attribution types..."
npx openapi-typescript external/contracts/openapi/v1/attribution.yaml -o client/src/types/api/attribution.ts

echo "Generating reconciliation types..."
npx openapi-typescript external/contracts/openapi/v1/reconciliation.yaml -o client/src/types/api/reconciliation.ts

echo "Generating export types..."
npx openapi-typescript external/contracts/openapi/v1/export.yaml -o client/src/types/api/export.ts

echo "Generating health types..."
npx openapi-typescript external/contracts/openapi/v1/health.yaml -o client/src/types/api/health.ts

echo "Generating error types..."
npx openapi-typescript external/contracts/openapi/v1/errors.yaml -o client/src/types/api/errors.ts

echo ""
echo "✅ Type generation complete!"
echo "   Types available in client/src/types/api/"
