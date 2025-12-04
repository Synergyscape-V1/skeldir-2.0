#!/usr/bin/env bash
set -euo pipefail

# SKELDIR B0.2 Mock Starter
# Aligned with 12-contract registry

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DIST_DIR="$REPO_ROOT/api-contracts/dist/openapi/v1"

echo "Starting Prism mock servers from $DIST_DIR..."

start_mock() {
    local name=$1
    local port=$2
    local file=$3

    # Handle .yaml to .bundled.yaml conversion; flatten nested paths for dist output
    local bundle="${file%.yaml}.bundled.yaml"
    bundle="${bundle//\//.}"

    if [ -f "$DIST_DIR/$bundle" ]; then
        echo "Starting $name on $port..."
        npx prism mock "$DIST_DIR/$bundle" -p "$port" -h 0.0.0.0 > /dev/null 2>&1 &
    else
        echo "ERROR: Bundle $bundle not found for $name"
    fi
}

# Core
start_mock "auth" 4010 "auth.yaml"
start_mock "attribution" 4011 "attribution.yaml"
start_mock "reconciliation" 4014 "reconciliation.yaml"
start_mock "export" 4015 "export.yaml"
start_mock "health" 4016 "health.yaml"

# Webhooks
start_mock "shopify" 4020 "webhooks/shopify.yaml"
start_mock "stripe" 4021 "webhooks/stripe.yaml"
start_mock "woocommerce" 4022 "webhooks/woocommerce.yaml"
start_mock "paypal" 4023 "webhooks/paypal.yaml"

# LLM (B0.2 Extension)
start_mock "llm-investigations" 4024 "llm-investigations.yaml"
start_mock "llm-budget" 4025 "llm-budget.yaml"
start_mock "llm-explanations" 4026 "llm-explanations.yaml"

echo "All mocks started in background."
