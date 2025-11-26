# Skeldir API Contracts

This directory contains the OpenAPI 3.1.0 contract specifications for the Skeldir Attribution Intelligence Platform.

## Directory Structure

```
api-contracts/
├── openapi/v1/
│   ├── _common/
│   │   └── base.yaml          # Shared schemas, parameters, responses
│   ├── auth.yaml              # Authentication API (port 4010)
│   ├── attribution.yaml       # Attribution API (port 4011)
│   ├── reconciliation.yaml    # Reconciliation API (port 4012)
│   ├── export.yaml            # Export API (port 4013)
│   ├── health.yaml            # Health API (port 4014)
│   └── webhooks/
│       ├── shopify.yaml       # Shopify webhooks (port 4015)
│       ├── woocommerce.yaml   # WooCommerce webhooks (port 4016)
│       ├── stripe.yaml        # Stripe webhooks (port 4017)
│       └── paypal.yaml        # PayPal webhooks (port 4018)
├── governance/
│   ├── integration-map.json   # Service port mappings and dependencies
│   └── invariants.md          # Contract rules and breaking change policy
├── baselines/v1.0.0/          # Frozen contract baselines
└── README.md                  # This file
```

## Service Port Assignments

| Service | Port | Description |
|---------|------|-------------|
| Auth | 4010 | Authentication and authorization |
| Attribution | 4011 | Realtime revenue and attribution data |
| Reconciliation | 4012 | Platform sync status |
| Export | 4013 | Data export (CSV, JSON, Excel) |
| Health | 4014 | System health monitoring |
| Shopify Webhooks | 4015 | Shopify order/checkout events |
| WooCommerce Webhooks | 4016 | WooCommerce order events |
| Stripe Webhooks | 4017 | Stripe payment events |
| PayPal Webhooks | 4018 | PayPal payment events |

## Frontend vs Backend Services

### Frontend-Facing (ports 4010-4014)
These services are consumed directly by the frontend application:
- **Auth**: Login, logout, token refresh
- **Attribution**: Revenue metrics, channel data
- **Reconciliation**: Platform connection status
- **Export**: Data downloads
- **Health**: System status (no auth required for basic check)

### Backend-Only (ports 4015-4018)
Webhook endpoints are backend-only. The frontend does NOT consume these directly:
- Webhooks are received by the backend from external platforms
- Frontend displays processed webhook data via the Attribution/Reconciliation APIs

## Quick Start

### Validate Contracts
```bash
./scripts/validate-contracts.sh
```

### Start Mock Servers (Process-Based)
```bash
./scripts/start-mocks-prism.sh
```

### Stop Mock Servers
```bash
./scripts/stop-mocks-prism.sh
```

### Health Check
```bash
./scripts/health-check-mocks.sh
```

## Contract Development Guidelines

### Required Headers
Every request must include:
- `X-Correlation-ID`: UUID v4 for distributed tracing

Protected endpoints additionally require:
- `Authorization`: Bearer token

Cacheable endpoints support:
- `If-None-Match`: ETag for cache validation

### Error Responses
All errors follow RFC7807 Problem Details format:
```json
{
  "type": "https://api.skeldir.com/problems/authentication-failed",
  "title": "Authentication Failed",
  "status": 401,
  "detail": "The provided JWT token has expired.",
  "instance": "/api/attribution/revenue/realtime",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2025-11-26T14:32:00Z"
}
```

### Breaking Change Policy
See `governance/invariants.md` for the complete policy on contract changes.

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 2.0.0 | 2025-11-26 | Process-based mock servers, port standardization |
| 1.0.0 | 2025-10-15 | Initial contract specifications |
