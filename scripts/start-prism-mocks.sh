#!/usr/bin/env bash
# Start all Prism mock servers for B0.2 validation
#
# Usage: bash scripts/start-prism-mocks.sh
# Stop: pkill -f prism

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONTRACTS_DIR="$REPO_ROOT/api-contracts/openapi/v1"

echo "Starting Prism mock servers from $CONTRACTS_DIR..."

# Check if Prism is installed
if ! command -v prism &> /dev/null; then
    echo "ERROR: Prism CLI not found"
    echo "Install with: npm install -g @stoplight/prism-cli"
    exit 1
fi

# Start core API mocks
prism mock "$CONTRACTS_DIR/auth.yaml" --port 4010 &
echo "✓ Auth API mock started on port 4010"

prism mock "$CONTRACTS_DIR/attribution.yaml" --port 4011 &
echo "✓ Attribution API mock started on port 4011"

prism mock "$CONTRACTS_DIR/reconciliation.yaml" --port 4014 &
echo "✓ Reconciliation API mock started on port 4014"

prism mock "$CONTRACTS_DIR/export.yaml" --port 4015 &
echo "✓ Export API mock started on port 4015"

prism mock "$CONTRACTS_DIR/health.yaml" --port 4016 &
echo "✓ Health API mock started on port 4016"

# Start webhook mocks
prism mock "$CONTRACTS_DIR/webhooks/shopify.yaml" --port 4020 &
echo "✓ Shopify Webhooks mock started on port 4020"

prism mock "$CONTRACTS_DIR/webhooks/stripe.yaml" --port 4021 &
echo "✓ Stripe Webhooks mock started on port 4021"

prism mock "$CONTRACTS_DIR/webhooks/woocommerce.yaml" --port 4022 &
echo "✓ WooCommerce Webhooks mock started on port 4022"

prism mock "$CONTRACTS_DIR/webhooks/paypal.yaml" --port 4023 &
echo "✓ PayPal Webhooks mock started on port 4023"

echo ""
echo "✅ All Prism mocks started successfully"
echo ""
echo "Ports:"
echo "  4010: Auth"
echo "  4011: Attribution"
echo "  4014: Reconciliation"
echo "  4015: Export"
echo "  4016: Health"
echo "  4020-4023: Webhooks (Shopify, Stripe, WooCommerce, PayPal)"
echo ""
echo "Stop all mocks: pkill -f prism"
echo "Test health: curl http://localhost:4016/api/health"
