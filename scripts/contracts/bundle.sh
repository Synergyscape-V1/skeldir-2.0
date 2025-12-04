#!/usr/bin/env bash
# Bundles OpenAPI specs into api-contracts/dist/openapi/v1 for CI workflows.
# Uses Redocly CLI to properly dereference all $ref references.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CONTRACTS_DIR="$REPO_ROOT/api-contracts"
DIST_DIR="$REPO_ROOT/api-contracts/dist/openapi/v1"

log() {
    printf '[bundle] %s\n' "$1"
}

log "Preparing output directory: $DIST_DIR"
rm -rf "$DIST_DIR"
mkdir -p "$DIST_DIR"

# Change to api-contracts directory for redocly config resolution
cd "$CONTRACTS_DIR"

# Check if redocly.yaml exists
if [ ! -f "redocly.yaml" ]; then
    log "ERROR: redocly.yaml not found in $CONTRACTS_DIR"
    exit 1
fi

# Bundle core contracts
log "Bundling core contracts..."
npx @redocly/cli bundle auth --config=redocly.yaml --output=dist/openapi/v1/auth.bundled.yaml --ext yaml --dereferenced
log "✓ auth.bundled.yaml"

npx @redocly/cli bundle attribution --config=redocly.yaml --output=dist/openapi/v1/attribution.bundled.yaml --ext yaml --dereferenced
log "✓ attribution.bundled.yaml"

npx @redocly/cli bundle reconciliation --config=redocly.yaml --output=dist/openapi/v1/reconciliation.bundled.yaml --ext yaml --dereferenced
log "✓ reconciliation.bundled.yaml"

npx @redocly/cli bundle export --config=redocly.yaml --output=dist/openapi/v1/export.bundled.yaml --ext yaml --dereferenced
log "✓ export.bundled.yaml"

npx @redocly/cli bundle health --config=redocly.yaml --output=dist/openapi/v1/health.bundled.yaml --ext yaml --dereferenced
log "✓ health.bundled.yaml"

# Bundle webhook contracts
log "Bundling webhook contracts..."
npx @redocly/cli bundle shopify_webhook --config=redocly.yaml --output=dist/openapi/v1/webhooks.shopify.bundled.yaml --ext yaml --dereferenced
log "✓ webhooks.shopify.bundled.yaml"

npx @redocly/cli bundle woocommerce_webhook --config=redocly.yaml --output=dist/openapi/v1/webhooks.woocommerce.bundled.yaml --ext yaml --dereferenced
log "✓ webhooks.woocommerce.bundled.yaml"

npx @redocly/cli bundle stripe_webhook --config=redocly.yaml --output=dist/openapi/v1/webhooks.stripe.bundled.yaml --ext yaml --dereferenced
log "✓ webhooks.stripe.bundled.yaml"

npx @redocly/cli bundle paypal_webhook --config=redocly.yaml --output=dist/openapi/v1/webhooks.paypal.bundled.yaml --ext yaml --dereferenced
log "✓ webhooks.paypal.bundled.yaml"

# Bundle LLM contracts
log "Bundling LLM contracts..."
npx @redocly/cli bundle llm_investigations --config=redocly.yaml --output=dist/openapi/v1/llm-investigations.bundled.yaml --ext yaml --dereferenced
log "✓ llm-investigations.bundled.yaml"

npx @redocly/cli bundle llm_budget --config=redocly.yaml --output=dist/openapi/v1/llm-budget.bundled.yaml --ext yaml --dereferenced
log "✓ llm-budget.bundled.yaml"

# Copy _common directory for reference (not bundled)
if [ -d "openapi/v1/_common" ]; then
    log "Copying _common directory for reference..."
    mkdir -p dist/openapi/v1/_common
    cp -r openapi/v1/_common/* dist/openapi/v1/_common/
    log "✓ _common directory"
fi

log "All 11 OpenAPI contracts bundled successfully."
log "Artifacts ready under api-contracts/dist/openapi/v1/."
