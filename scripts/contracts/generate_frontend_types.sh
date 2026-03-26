#!/usr/bin/env bash
# Generate frontend API TypeScript types from canonical bundled OpenAPI artifacts.
# Source of truth: api-contracts/dist/openapi/v1/*.bundled.yaml

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BUNDLES_DIR="$REPO_ROOT/api-contracts/dist/openapi/v1"
OUTPUT_DIR="$REPO_ROOT/frontend/src/types/api"
RELATIVE_BUNDLES_DIR="api-contracts/dist/openapi/v1"
RELATIVE_OUTPUT_DIR="frontend/src/types/api"

if [[ ! -d "$BUNDLES_DIR" ]]; then
  echo "[frontend-typegen] Missing bundles directory: $BUNDLES_DIR"
  echo "[frontend-typegen] Run scripts/contracts/bundle.sh first."
  exit 1
fi

rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"

install_openapi_typescript() {
  local repo_root="$1"
  local version="7.10.1"
  for attempt in 1 2 3 4 5 6 7 8 9 10; do
    if npm install --no-save --prefix "$repo_root" "openapi-typescript@${version}"; then
      return 0
    fi
    if [[ "$attempt" -eq 10 ]]; then
      echo "[frontend-typegen] Failed to install openapi-typescript@${version} after 10 attempts"
      return 1
    fi
    sleep 3
  done
}

install_openapi_typescript "$REPO_ROOT"
OPENAPI_TYPESCRIPT_BIN="$REPO_ROOT/node_modules/.bin/openapi-typescript"
if [[ ! -x "$OPENAPI_TYPESCRIPT_BIN" ]]; then
  echo "[frontend-typegen] Missing generator binary: $OPENAPI_TYPESCRIPT_BIN"
  exit 1
fi

generate() {
  local input_bundle="$1"
  local output_file="$2"
  local input_path="$RELATIVE_BUNDLES_DIR/$input_bundle"
  local output_path="$RELATIVE_OUTPUT_DIR/$output_file"

  if [[ ! -f "$REPO_ROOT/$input_path" ]]; then
    echo "[frontend-typegen] Missing bundle: $REPO_ROOT/$input_path"
    exit 1
  fi

  echo "[frontend-typegen] $input_bundle -> $output_file"
  (
    cd "$REPO_ROOT"
    "$OPENAPI_TYPESCRIPT_BIN" "$input_path" -o "$output_path"
  )
}

generate "auth.bundled.yaml" "auth.ts"
generate "attribution.bundled.yaml" "attribution.ts"
generate "reconciliation.bundled.yaml" "reconciliation.ts"
generate "export.bundled.yaml" "export.ts"
generate "privacy.bundled.yaml" "privacy.ts"
generate "health.bundled.yaml" "health.ts"
generate "llm-investigations.bundled.yaml" "llm-investigations.ts"
generate "llm-budget.bundled.yaml" "llm-budget.ts"
generate "llm-explanations.bundled.yaml" "llm-explanations.ts"
generate "webhooks.shopify.bundled.yaml" "webhooks-shopify.ts"
generate "webhooks.stripe.bundled.yaml" "webhooks-stripe.ts"
generate "webhooks.woocommerce.bundled.yaml" "webhooks-woocommerce.ts"
generate "webhooks.paypal.bundled.yaml" "webhooks-paypal.ts"

cat > "$OUTPUT_DIR/index.ts" <<'TS'
export type { paths as AuthPaths, operations as AuthOperations, components as AuthComponents } from "./auth";
export type { paths as AttributionPaths, operations as AttributionOperations, components as AttributionComponents } from "./attribution";
export type { paths as ReconciliationPaths, operations as ReconciliationOperations, components as ReconciliationComponents } from "./reconciliation";
export type { paths as ExportPaths, operations as ExportOperations, components as ExportComponents } from "./export";
export type { paths as PrivacyPaths, operations as PrivacyOperations, components as PrivacyComponents } from "./privacy";
export type { paths as HealthPaths, operations as HealthOperations, components as HealthComponents } from "./health";
export type { paths as LlmInvestigationsPaths, operations as LlmInvestigationsOperations, components as LlmInvestigationsComponents } from "./llm-investigations";
export type { paths as LlmBudgetPaths, operations as LlmBudgetOperations, components as LlmBudgetComponents } from "./llm-budget";
export type { paths as LlmExplanationsPaths, operations as LlmExplanationsOperations, components as LlmExplanationsComponents } from "./llm-explanations";
export type { paths as WebhooksShopifyPaths, operations as WebhooksShopifyOperations, components as WebhooksShopifyComponents } from "./webhooks-shopify";
export type { paths as WebhooksStripePaths, operations as WebhooksStripeOperations, components as WebhooksStripeComponents } from "./webhooks-stripe";
export type { paths as WebhooksWoocommercePaths, operations as WebhooksWoocommerceOperations, components as WebhooksWoocommerceComponents } from "./webhooks-woocommerce";
export type { paths as WebhooksPaypalPaths, operations as WebhooksPaypalOperations, components as WebhooksPaypalComponents } from "./webhooks-paypal";
TS

echo "[frontend-typegen] Completed. Updated files in $OUTPUT_DIR"
