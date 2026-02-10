#!/usr/bin/env bash
# Generate frontend API TypeScript types from canonical bundled OpenAPI artifacts.
# Source of truth: api-contracts/dist/openapi/v1/*.bundled.yaml

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BUNDLES_DIR="$REPO_ROOT/api-contracts/dist/openapi/v1"
OUTPUT_DIR="$REPO_ROOT/frontend/src/types/api"

if [[ ! -d "$BUNDLES_DIR" ]]; then
  echo "[frontend-typegen] Missing bundles directory: $BUNDLES_DIR"
  echo "[frontend-typegen] Run scripts/contracts/bundle.sh first."
  exit 1
fi

mkdir -p "$OUTPUT_DIR"

generate() {
  local input_bundle="$1"
  local output_file="$2"
  local input_path="$BUNDLES_DIR/$input_bundle"
  local output_path="$OUTPUT_DIR/$output_file"

  if [[ ! -f "$input_path" ]]; then
    echo "[frontend-typegen] Missing bundle: $input_path"
    exit 1
  fi

  echo "[frontend-typegen] $input_bundle -> $output_file"
  npx --yes openapi-typescript@7.10.1 "$input_path" -o "$output_path"
}

generate "auth.bundled.yaml" "auth.ts"
generate "attribution.bundled.yaml" "attribution.ts"
generate "reconciliation.bundled.yaml" "reconciliation.ts"
generate "export.bundled.yaml" "export.ts"
generate "health.bundled.yaml" "health.ts"
generate "llm-investigations.bundled.yaml" "llm-investigations.ts"
generate "llm-budget.bundled.yaml" "llm-budget.ts"
generate "llm-explanations.bundled.yaml" "llm-explanations.ts"
generate "webhooks.shopify.bundled.yaml" "webhooks-shopify.ts"
generate "webhooks.stripe.bundled.yaml" "webhooks-stripe.ts"
generate "webhooks.woocommerce.bundled.yaml" "webhooks-woocommerce.ts"
generate "webhooks.paypal.bundled.yaml" "webhooks-paypal.ts"

echo "[frontend-typegen] Completed. Updated files in $OUTPUT_DIR"
