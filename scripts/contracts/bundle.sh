#!/usr/bin/env bash
# Bundles OpenAPI specs into api-contracts/dist/openapi/v1 for CI workflows.
# Uses Redocly CLI to dereference all $ref references.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CONTRACTS_DIR="$REPO_ROOT/api-contracts"
DIST_DIR="$REPO_ROOT/api-contracts/dist/openapi/v1"

log() {
    printf '[bundle] %s\n' "$1"
}

retry() {
    local attempts="$1"
    shift
    local i=1
    while [ "$i" -le "$attempts" ]; do
        if "$@"; then
            return 0
        fi
        log "attempt $i/$attempts failed: $*"
        i=$((i + 1))
        sleep 2
    done
    return 1
}

resolve_redocly() {
    if command -v redocly >/dev/null 2>&1; then
        command -v redocly
        return 0
    fi

    if [ -x "$CONTRACTS_DIR/node_modules/.bin/redocly" ]; then
        printf '%s\n' "$CONTRACTS_DIR/node_modules/.bin/redocly"
        return 0
    fi

    log "Installing Redocly CLI locally (single install; no repeated npx fetches)..."
    if ! retry 5 npm install --no-save --prefix "$CONTRACTS_DIR" @redocly/cli@2.19.2; then
        log "ERROR: failed to install @redocly/cli after retries"
        return 1
    fi

    printf '%s\n' "$CONTRACTS_DIR/node_modules/.bin/redocly"
}

bundle_one() {
    local cli="$1"
    local api_name="$2"
    local output_file="$3"
    "$cli" bundle "$api_name" --config=redocly.yaml --output="$output_file" --ext yaml --dereferenced
    log "ok $(basename "$output_file")"
}

log "Preparing output directory: $DIST_DIR"
rm -rf "$DIST_DIR"
mkdir -p "$DIST_DIR"

cd "$CONTRACTS_DIR"

if [ ! -f "redocly.yaml" ]; then
    log "ERROR: redocly.yaml not found in $CONTRACTS_DIR"
    exit 1
fi

REDOCLY_BIN="$(resolve_redocly)"
if [ ! -x "$REDOCLY_BIN" ]; then
    log "ERROR: redocly binary not executable at $REDOCLY_BIN"
    exit 1
fi

log "Using Redocly binary: $REDOCLY_BIN"

log "Bundling core contracts..."
bundle_one "$REDOCLY_BIN" auth dist/openapi/v1/auth.bundled.yaml
bundle_one "$REDOCLY_BIN" attribution dist/openapi/v1/attribution.bundled.yaml
bundle_one "$REDOCLY_BIN" revenue dist/openapi/v1/revenue.bundled.yaml
bundle_one "$REDOCLY_BIN" reconciliation dist/openapi/v1/reconciliation.bundled.yaml
bundle_one "$REDOCLY_BIN" export dist/openapi/v1/export.bundled.yaml
bundle_one "$REDOCLY_BIN" health dist/openapi/v1/health.bundled.yaml

log "Bundling webhook contracts..."
bundle_one "$REDOCLY_BIN" shopify_webhook dist/openapi/v1/webhooks.shopify.bundled.yaml
bundle_one "$REDOCLY_BIN" woocommerce_webhook dist/openapi/v1/webhooks.woocommerce.bundled.yaml
bundle_one "$REDOCLY_BIN" stripe_webhook dist/openapi/v1/webhooks.stripe.bundled.yaml
bundle_one "$REDOCLY_BIN" paypal_webhook dist/openapi/v1/webhooks.paypal.bundled.yaml

log "Bundling LLM contracts..."
bundle_one "$REDOCLY_BIN" llm_investigations dist/openapi/v1/llm-investigations.bundled.yaml
bundle_one "$REDOCLY_BIN" llm_budget dist/openapi/v1/llm-budget.bundled.yaml
bundle_one "$REDOCLY_BIN" llm_explanations dist/openapi/v1/llm-explanations.bundled.yaml

if [ -d "openapi/v1/_common" ]; then
    log "Copying _common directory for reference..."
    mkdir -p dist/openapi/v1/_common
    cp -r openapi/v1/_common/* dist/openapi/v1/_common/
    log "ok _common directory"
fi

log "All OpenAPI contracts bundled successfully."
log "Artifacts ready under api-contracts/dist/openapi/v1/."
