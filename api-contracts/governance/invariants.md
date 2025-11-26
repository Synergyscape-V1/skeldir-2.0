# Skeldir API Contract Invariants

## Version Control
- **Contract Version**: 2.0.0
- **OpenAPI Specification**: 3.1.0
- **Last Updated**: 2025-11-26

## Invariant Rules

### 1. Port Assignment Invariants
| Service | Port | Invariant |
|---------|------|-----------|
| Auth | 4010 | FIXED - Authentication must be on lowest port |
| Attribution | 4011 | FIXED - Core attribution service |
| Reconciliation | 4012 | FIXED - Reconciliation status |
| Export | 4013 | FIXED - Data export functionality |
| Health | 4014 | FIXED - Health monitoring (no auth required for basic) |
| Shopify Webhooks | 4015 | FIXED - First webhook provider |
| WooCommerce Webhooks | 4016 | FIXED - Second webhook provider |
| Stripe Webhooks | 4017 | FIXED - Third webhook provider |
| PayPal Webhooks | 4018 | FIXED - Fourth webhook provider |

### 2. Header Invariants
- **X-Correlation-ID**: Required on ALL requests (UUID v4 format)
- **Authorization**: Required on protected endpoints (Bearer token format)
- **If-None-Match**: Optional for cacheable endpoints (ETag validation)

### 3. Response Format Invariants
- **Error Responses**: Must conform to RFC7807 Problem Details schema
- **Success Responses**: Must include `correlation_id` field
- **Content-Type**: `application/json` for data, `application/problem+json` for errors

### 4. Authentication Invariants
- **Token Format**: JWT with HS256 signing
- **Access Token TTL**: 3600 seconds (1 hour)
- **Refresh Token TTL**: 604800 seconds (7 days)
- **Token Rotation**: Required on refresh

### 5. Caching Invariants
- **Realtime Revenue**: 30-second cache TTL
- **ETag Support**: Required for all GET endpoints
- **304 Not Modified**: Must be implemented for cached resources

### 6. Rate Limiting Invariants
- **Default Limit**: 100 requests per minute
- **Retry-After Header**: Must be included with 429 responses
- **Rate Limit Reset**: Rolling window

## Breaking Change Policy

### Prohibited Changes (Without Major Version Bump)
1. Removing required fields from responses
2. Adding new required fields to requests
3. Changing field types
4. Changing port assignments
5. Removing endpoints
6. Changing authentication requirements

### Allowed Changes (Minor Version)
1. Adding optional response fields
2. Adding optional request parameters
3. Adding new endpoints
4. Expanding enum values (with caution)
5. Improving error messages

## Validation Requirements

### Pre-Commit Checks
1. All contracts must pass OpenAPI 3.1.0 validation
2. No breaking changes without version bump
3. All new endpoints must have example responses
4. All error responses must follow RFC7807

### CI/CD Gates
1. Contract validation in pipeline
2. Breaking change detection
3. SDK regeneration on contract changes
4. Mock server compatibility verification
