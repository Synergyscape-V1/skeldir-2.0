#!/bin/bash

# Docker-based Mock Server Startup Script
# Starts all 10 Prism mock servers using Docker Compose

set -e

echo "🐳 Starting Mock Servers with Docker Compose"
echo "=============================================="
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
  echo "❌ Error: Docker is not running"
  echo "   Please start Docker and try again"
  exit 1
fi

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
  echo "❌ Error: docker-compose is not installed"
  echo "   Install: https://docs.docker.com/compose/install/"
  exit 1
fi

# Start mock servers
echo "📦 Pulling Prism image..."
docker-compose -f docker-compose.mock.yml pull

echo ""
echo "🚀 Starting 10 mock servers (ports 4010-4019)..."
docker-compose -f docker-compose.mock.yml up -d

echo ""
echo "⏳ Waiting for servers to be ready..."
sleep 3

echo ""
echo "✅ Mock servers started successfully!"
echo ""
echo "Available servers:"
echo "  • Attribution API:       http://localhost:4010"
echo "  • Health Monitoring:     http://localhost:4011"
echo "  • Export API:           http://localhost:4012"
echo "  • Reconciliation API:   http://localhost:4013"
echo "  • Error Logging API:    http://localhost:4014"
echo "  • Authentication API:   http://localhost:4015"
echo "  • Shopify Webhooks:     http://localhost:4016"
echo "  • WooCommerce Webhooks: http://localhost:4017"
echo "  • Stripe Webhooks:      http://localhost:4018"
echo "  • PayPal Webhooks:      http://localhost:4019"
echo ""
echo "Commands:"
echo "  • Check status:  docker-compose -f docker-compose.mock.yml ps"
echo "  • View logs:     docker-compose -f docker-compose.mock.yml logs -f"
echo "  • Stop servers:  docker-compose -f docker-compose.mock.yml down"
echo "  • Health check:  node scripts/mock-health-check.js"
echo ""
