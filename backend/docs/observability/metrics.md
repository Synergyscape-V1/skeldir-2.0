# Metrics Reference and Cardinality (B0.4.7.1)

## Metric Families

- `events_ingested_total{tenant_id,vendor,event_type,error_type}`  
  - Counts successful ingestions (error_type="none").
  - Cardinality: tenant_id = number of tenants; vendor ∈ {shopify,stripe,paypal,woocommerce}; event_type ∈ small enum (e.g., purchase, refund); error_type fixed set.

- `events_duplicate_total{tenant_id,vendor,event_type,error_type}`  
  - Counts duplicates detected via idempotency (error_type="duplicate").
  - Cardinality controlled as above.

- `events_dlq_total{tenant_id,vendor,event_type,error_type}`  
  - Counts DLQ routed events (error_type classified).
  - Cardinality controlled as above.

- `ingestion_duration_seconds{tenant_id,vendor,event_type,error_type}` (histogram)  
  - Latency distribution per ingestion attempt.
  - Buckets: 0.05, 0.1, 0.25, 0.5, 1, 2, 5 seconds.

## Cardinality Expectations
- `tenant_id`: bounded by tenant count; required for isolation.
- `vendor`: fixed set of four.
- `event_type`: fixed small set; introducing new values requires review.
- `error_type`: fixed enum (none, duplicate, validation_error, etc.).
- No free-form labels; avoid adding payload-derived labels without review.

## Security / Exposure
- `/metrics` is intended for internal use only; restrict via network/ingress controls (VPC, allowlists). No app-level auth is enforced.

## Regression Policy
- Adding new labels or high-cardinality values requires review to avoid metric explosion.
- Tests assert presence of required labels and parsability; failures indicate drift.
