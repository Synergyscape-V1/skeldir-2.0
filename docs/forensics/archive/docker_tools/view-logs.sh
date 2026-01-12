#!/bin/bash
# View logs for mock services

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Docker is running
if ! docker ps > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running${NC}"
    exit 1
fi

SERVICE=$1

if [ -z "$SERVICE" ]; then
    echo "Usage: $0 [service-name|all]"
    echo ""
    echo "Available services:"
    echo "  auth, attribution, reconciliation, export, health"
    echo "  webhooks-shopify, webhooks-woocommerce, webhooks-stripe, webhooks-paypal"
    echo "  all (shows last 100 lines of all services)"
    exit 1
fi

if [ "$SERVICE" = "all" ]; then
    echo -e "${GREEN}Showing last 100 lines of all services...${NC}"
    docker-compose -f docker-compose.yml logs --tail=100
    exit 0
fi

# Map service names to container names
case "$SERVICE" in
    auth)
        CONTAINER="skeldir-mock-auth"
        ;;
    attribution)
        CONTAINER="skeldir-mock-attribution"
        ;;
    reconciliation)
        CONTAINER="skeldir-mock-reconciliation"
        ;;
    export)
        CONTAINER="skeldir-mock-export"
        ;;
    health)
        CONTAINER="skeldir-mock-health"
        ;;
    webhooks-shopify|shopify)
        CONTAINER="skeldir-mock-webhooks-shopify"
        ;;
    webhooks-woocommerce|woocommerce)
        CONTAINER="skeldir-mock-webhooks-woocommerce"
        ;;
    webhooks-stripe|stripe)
        CONTAINER="skeldir-mock-webhooks-stripe"
        ;;
    webhooks-paypal|paypal)
        CONTAINER="skeldir-mock-webhooks-paypal"
        ;;
    *)
        echo -e "${RED}Error: Unknown service: $SERVICE${NC}"
        echo "Available services: auth, attribution, reconciliation, export, health, webhooks-shopify, webhooks-woocommerce, webhooks-stripe, webhooks-paypal, all"
        exit 1
        ;;
esac

# Check if container exists
if ! docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo -e "${RED}Error: Container $CONTAINER not found${NC}"
    exit 1
fi

echo -e "${GREEN}Following logs for $SERVICE ($CONTAINER)...${NC}"
echo "Press Ctrl+C to stop"
docker-compose -f docker-compose.yml logs -f "$SERVICE"


