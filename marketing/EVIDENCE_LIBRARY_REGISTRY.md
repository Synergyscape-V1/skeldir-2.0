# Evidence Library Registry (D6)

Authoritative JSON: `discoverability.evidence-library-registry.json`.

Each record includes `route`, `cluster`, `primary_query`, `secondary_queries`, `proof_authority_routes`, `content_status`, `indexable`, `sitemap_required`, `schema_type` (`CollectionPage` for the hub, `WebPage` for evidence detail), `owner`, `last_reviewed`, `review_cadence`, and `similarity_group` for anti-spam grouping.

D6 evidence pages are **retrieval layers** that cite D5 proof routes; they do not fork canonical definitions on `/methodology`, `/revenue-verification`, `/trust-envelope`, `/ai-boundary`, or `/discrepancy-taxonomy`.
