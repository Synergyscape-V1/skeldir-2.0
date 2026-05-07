# B2.3-P6 Verification Coverage Specification

## Metric
`VERIFICATION_COVERAGE` is the deterministic B2.3 metric primitive that B2.6 may consume as a precondition. It is not a reconciliation workflow.

## Definition
Numerator: matched webhook revenue in integer minor units for supported connected commerce platforms.

Denominator: connected-platform revenue in integer minor units for supported commerce platforms only.

Formula: `matched_webhook_revenue_minor / connected_platform_revenue_minor * 100`.

Example: connected-platform revenue of `$80,000` and matched webhook revenue of `$76,000` yields `95.00%`, not `76%`; unsupported or offline business revenue is excluded from the denominator.

## Scope
Tenant scope is mandatory. Rows for other tenants are ignored before aggregation.

Supported platforms are `shopify`, `stripe`, `paypal`, and `woocommerce`. Unsupported rails such as bank wires, manual invoices, cash, ACH imports, marketplace settlements without a supported commerce connection, and ad-attributed order estimates are excluded from both numerator and denominator.

The reconciliation window is half-open: `window_start <= occurred_at < window_end`. Consumers must pass an explicit window.

Currency basis is integer minor units. P6 supports `USD`; mixed-currency aggregation is forbidden until a later governed currency policy exists.

Rounding is deterministic decimal arithmetic using `ROUND_HALF_UP` to two percentage decimals.

Zero denominator behavior is defined as `0.00%` with `zero_denominator = true`. It does not imply failure and must not be treated as evidence of poor verification.

## Callable Semantics
Production code exposes:

- `backend.app.revenue_verification.verification_coverage.VERIFICATION_COVERAGE.compute(...)`
- `backend.app.revenue_verification.verification_coverage.compute_verification_coverage(...)`

The callable accepts already-available B2.3/B2.2 revenue rows and returns numerator, denominator, percentage, tenant, currency, window, and zero-denominator flag. It performs no external API calls, no LLM calls, no vendor normalization, no bank transaction matching, no dashboard work, and no stored reconciliation workflow.
