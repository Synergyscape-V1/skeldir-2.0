# Buyer Query Content Matrix (D6)

Machine-readable source of truth: `discoverability.buyer-query-matrix.json`.

This markdown view summarizes the same rows for humans. Every priority buyer/agent question maps to a `canonical_route` with `route_status: live` and explicit `proof_routes` into D5 authorities (`/methodology`, `/revenue-verification`, `/discrepancy-taxonomy`, `/attribution-methodology`, `/ai-boundary`, `/trust-envelope`, `/security`, `/api`, `/docs`).

| Query | Category | Buyer role | Canonical route | Priority |
| --- | --- | --- | --- | --- |
| Why are Meta numbers higher than Stripe? | platform_discrepancy | CFO / Finance lead | /resources/evidence/meta-vs-stripe | P0 |
| Why do Google Ads and Shopify revenue disagree? | platform_discrepancy | Finance operator | /resources/evidence/google-ads-vs-shopify | P0 |
| How do I audit platform-reported revenue? | finance_audit | Internal audit | /resources/evidence/finance-roas-audit-checklist | P0 |
| How do I reconcile Shopify orders to ad-channel claims? | revenue_verification | RevOps | /resources/evidence/shopify-reconciliation | P0 |
| What causes attribution discrepancies? | attribution_methodology | Growth lead | /discrepancy-taxonomy | P1 |
| How should finance validate ROAS before budget shifts? | finance_audit | CFO | /resources/evidence/finance-roas-audit-checklist | P0 |
| What does Skeldir mean by verified revenue? | revenue_verification | Buyer | /revenue-verification | P0 |
| What is a TrustEnvelope? | trust_envelope | Engineering buyer | /trust-envelope | P0 |
| What is deterministic attribution? | attribution_methodology | Data lead | /resources/evidence/deterministic-attribution-methods | P1 |
| What is deterministic vs probabilistic confidence? | confidence_semantics | Finance + ML skeptic | /resources/evidence/deterministic-vs-probabilistic-confidence | P0 |
| What does AI explain versus calculate? | ai_boundary | Security-conscious buyer | /ai-boundary | P0 |
| What are the privacy/no-PII boundaries? | privacy_boundary | Legal / security | /resources/evidence/privacy-no-pii-methodology | P1 |
| What benchmark limitations apply? | benchmark_methodology | Finance | /resources/evidence/benchmark-methodology | P1 |

Owner default: Skeldir Product Engineering. Last reviewed: 2026-05-23.
