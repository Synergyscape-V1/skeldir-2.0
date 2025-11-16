# Idempotency Strategy

This document defines the idempotency key strategy for event ingestion across all webhook sources.

## Overview

Idempotency ensures that duplicate webhook deliveries do not result in duplicate events in the database. Each webhook source provides different identifiers that can be used for idempotency.

## Strategy by Source

### Shopify

**Source**: `api-contracts/openapi/v1/webhooks/shopify.yaml`

**Idempotency Key**: `external_event_id` (Shopify order ID)

**Strategy**: 
- Shopify provides a unique order ID in each webhook payload
- Use `external_event_id` field to store the Shopify order ID
- Enforce uniqueness via `UNIQUE (tenant_id, external_event_id)` constraint
- Format: Text (e.g., "1234567890")

**Implementation**:
```sql
CREATE UNIQUE INDEX idx_attribution_events_tenant_external_event_id 
    ON attribution_events (tenant_id, external_event_id) 
    WHERE external_event_id IS NOT NULL;
```

### Stripe

**Source**: `api-contracts/openapi/v1/webhooks/stripe.yaml`

**Idempotency Key**: `correlation_id` (Stripe payment intent ID)

**Strategy**:
- Stripe provides payment intent ID in webhook payload
- Use `correlation_id` field to store the Stripe payment intent ID
- Enforce uniqueness via `UNIQUE (tenant_id, correlation_id)` constraint (when `external_event_id` is NULL)
- Format: UUID

**Implementation**:
```sql
CREATE UNIQUE INDEX idx_attribution_events_tenant_correlation_id 
    ON attribution_events (tenant_id, correlation_id) 
    WHERE correlation_id IS NOT NULL AND external_event_id IS NULL;
```

### PayPal

**Source**: `api-contracts/openapi/v1/webhooks/paypal.yaml`

**Idempotency Key**: `external_event_id` (PayPal transaction ID)

**Strategy**:
- PayPal provides a unique transaction ID in each webhook payload
- Use `external_event_id` field to store the PayPal transaction ID
- Enforce uniqueness via `UNIQUE (tenant_id, external_event_id)` constraint
- Format: Text (e.g., "TXN-1234567890")

**Implementation**:
```sql
CREATE UNIQUE INDEX idx_attribution_events_tenant_external_event_id 
    ON attribution_events (tenant_id, external_event_id) 
    WHERE external_event_id IS NOT NULL;
```

### WooCommerce

**Source**: `api-contracts/openapi/v1/webhooks/woocommerce.yaml`

**Idempotency Key**: `external_event_id` (WooCommerce order ID)

**Strategy**:
- WooCommerce provides a unique order ID in each webhook payload
- Use `external_event_id` field to store the WooCommerce order ID
- Enforce uniqueness via `UNIQUE (tenant_id, external_event_id)` constraint
- Format: Integer (stored as text)

**Implementation**:
```sql
CREATE UNIQUE INDEX idx_attribution_events_tenant_external_event_id 
    ON attribution_events (tenant_id, external_event_id) 
    WHERE external_event_id IS NOT NULL;
```

## Constraint Design

### Partial Unique Indexes

We use **partial unique indexes** (with `WHERE` clauses) to handle the different idempotency strategies:

1. **Primary Strategy**: `UNIQUE (tenant_id, external_event_id)` when `external_event_id` is present
   - Used by: Shopify, PayPal, WooCommerce
   - Covers majority of webhook sources

2. **Fallback Strategy**: `UNIQUE (tenant_id, correlation_id)` when `external_event_id` is NULL
   - Used by: Stripe
   - Only applies when `external_event_id` is not available

### Rationale

- **Partial indexes** allow different sources to use different idempotency keys without conflicts
- **Tenant isolation** ensures idempotency is scoped per tenant (same event ID can exist for different tenants)
- **Fallback mechanism** handles sources that don't provide `external_event_id` (e.g., Stripe uses correlation_id)

## Error Handling

When a duplicate event is detected:

1. **Database Constraint Violation**: Unique constraint violation is raised
2. **Application Handling**: Application should catch the constraint violation and:
   - Return 200 OK (idempotent success)
   - Log the duplicate attempt
   - Do not create a new event record

## Cross-Reference

- **Table**: `attribution_events`
- **Migration**: `alembic/versions/202511131115_add_core_tables.py`
- **DDL Spec**: `db/docs/specs/attribution_events_ddl_spec.sql`




