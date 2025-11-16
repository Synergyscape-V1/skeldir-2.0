# Skeldir API Contracts

This directory contains OpenAPI 3.1.0 specifications for all Skeldir Attribution Intelligence API endpoints.

## Structure

```
api-contracts/
├── openapi/
│   └── v1/
│       ├── _common/              # Shared components (security, headers, errors, pagination)
│       ├── auth.yaml             # Authentication endpoints
│       ├── attribution.yaml      # Attribution and revenue endpoints
│       ├── reconciliation.yaml  # Reconciliation pipeline status
│       ├── export.yaml          # Data export endpoints
│       ├── health.yaml           # Health check endpoints
│       └── webhooks/            # Webhook ingestion endpoints
│           ├── shopify.yaml
│           ├── woocommerce.yaml
│           ├── stripe.yaml
│           └── paypal.yaml
├── baselines/                    # Version baselines for breaking change detection
│   └── v1.0.0/
└── README.md                     # This file
```

## Usage

### Viewing Contracts

Contracts can be viewed using:
- **Redoc**: `redocly preview-docs api-contracts/openapi/v1/auth.yaml`
- **Swagger UI**: `swagger-ui-serve api-contracts/openapi/v1/auth.yaml`
- **VS Code**: Install "OpenAPI (Swagger) Editor" extension

### Generating Pydantic Models

Generate Python Pydantic models from contracts:

```bash
bash scripts/generate-models.sh
```

This generates models in `app/schemas/` directory.

### Validating Contracts

Validate all contracts:

```bash
openapi-generator-cli validate -i api-contracts/openapi/v1/*.yaml
```

Or use the CI workflow which validates on every push/PR.

## Versioning

Contracts follow semantic versioning (`major.minor.patch`):
- **Major**: Breaking changes (require migration guide)
- **Minor**: Additive changes (new endpoints, optional fields)
- **Patch**: Documentation updates, non-breaking fixes

Current version: **1.0.0**

## Breaking Change Policy

1. Breaking changes require major version bump
2. Migration guide must be published 30 days before deployment
3. CI automatically detects breaking changes via `oasdiff breaking`
4. Baseline comparisons stored in `baselines/` directory

## Common Components

All contracts reference shared components from `_common/`:
- **Security**: BearerAuth (JWT)
- **Headers**: X-Correlation-ID, rate limit headers
- **Errors**: RFC7807 Problem schema with Skeldir extensions
- **Pagination**: Cursor-based pagination parameters and envelope

## Privacy & Security

- All webhook endpoints include explicit PII-stripping statements
- Session-scoped data only (no cross-session tracking)
- Tenant isolation enforced via `tenant_id` in all authenticated responses
- HMAC signature validation required for all webhooks

## Prism Mock Servers

Each contract includes Prism mock server URLs for frontend development:
- Auth: `http://localhost:4010`
- Attribution: `http://localhost:4011`
- Reconciliation: `http://localhost:4012`
- Export: `http://localhost:4013`
- Health: `http://localhost:4014`
- Webhooks: `http://localhost:4015-4018`

## CI/CD

Contracts are automatically validated on every push/PR via GitHub Actions:
- OpenAPI structural validation
- Breaking change detection
- Semantic versioning enforcement
- Pydantic model generation

## Support

For questions about API contracts:
- See architecture guide for design decisions
- Check `MIGRATION_TEMPLATE.md` for breaking change documentation
- Review phase validation logs (`PHASE_*_VALIDATION.md`) for implementation details






