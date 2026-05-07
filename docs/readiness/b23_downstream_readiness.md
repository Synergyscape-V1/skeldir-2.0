# B2.3 Downstream Readiness Contract

## B2.4 May Consume
B2.4 may consume the match verdict table (`b23_match_verdicts`), attribution-event FK (`attribution_event_id`), the tenant-scoped match-to-attribution join, match quality (`match_quality`), verified revenue fields, discrepancy fields, and exception state. Matched/post-match verdict states are guaranteed to carry `attribution_event_id` at the database boundary.

B2.4 may join `b23_match_verdicts` to `attribution_events` only by `(tenant_id, attribution_event_id)`. Cross-tenant joins are outside contract and must return zero rows under correct predicates.

## B2.6 May Consume
B2.6 may consume the `VERIFICATION_COVERAGE` callable/spec, matched webhook revenue, connected-platform denominator inputs, exception records (`b23_exception_records`), B2.3 SQL telemetry, and webhook failure telemetry.

The coverage primitive is a metric precondition only. It does not normalize vendors, reconcile bank transactions, or decide workflow state.

## Out Of Scope
The following remain explicitly out of B2.3-P6 scope: Bayesian fitting/convergence diagnostics, vendor normalization workflow, deterministic reconciliation stored procedures beyond the verification coverage primitive, dashboards, LLM explanation, frontend product UI, customer reporting expansion, and budget optimization.

## Deferral Register
| Deferred item | Owner phase | Reason | Required B2.3 input |
| --- | --- | --- | --- |
| Bayesian convergence diagnostics | B2.4 | Requires statistical model governance not owned by B2.3 | Tenant-scoped matched verdicts with attribution FKs |
| Vendor normalization workflow | B2.6 | Requires reconciliation-domain policy and source-specific rules | Verification coverage denominator/numerator contract |
| Bank/payment reconciliation matching | B2.6 | Requires transaction-domain workflow outside webhook matching | Matched webhook revenue and exception rows |
| Explanation surface | B2.7 | LLMs may explain only after deterministic truth is closed | API-readable confirmed verdicts and deterministic fields |
| Product dashboards/UI | Later product phase | UI consumption is downstream of API/product planning | Downstream readiness contract and generated API surface |
