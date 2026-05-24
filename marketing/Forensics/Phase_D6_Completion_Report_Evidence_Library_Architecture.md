# Phase D6 Completion Report — Evidence Library Architecture

## 1. Verdict

| Closure tier | Verdict | Notes |
| --- | --- | --- |
| **D6 local (engineering)** | **PASS** | Evidence library hub, core + optional evidence routes, buyer-query matrix + JSON, evidence-library registry + JSON, D6/D5 harnesses and D6 negative controls pass locally after `npm run build`. D2 and D3 harnesses were also executed successfully in this workspace. |
| **D6 remote CI (`feat/discoverability-remediation`)** | **FAIL (at time of last verification)** | Latest GitHub Actions run for head **`9d417bfc`** completed with **failure** in **`discoverability:d4:negative-controls`** (NC-D4-04 golden home fixture vs JSON-in-`<head>` contract). Root cause and fix path are documented in §16.2. |
| **D6 production-final** | **BLOCKED_BY_GLOBAL_RELEASE** | No mergeable PR to `origin/main` (unrelated histories). Deploy-preview and production-equivalent curl proof not attached. |

**Scope:** D6 only. No D8/D9/D10 production claims.

---

## 2. Scope confirmation

- D6 deliverables: query-addressable evidence library, matrices/registries, static BLUF/EAV-E-shaped evidence pages, D5 proof links (not forked definitions), capability-honesty gates, platform anti-spam similarity, harnesses `discoverability:d6` + `:negative-controls`, crawl/sitemap/schema/bot integration per directive.
- Explicitly out of scope for “production-final”: resolving unrelated `main` history, attach deploy preview, production curls — tracked only as global gates.

---

## 3. Global release blocker status

| Gate | State |
| --- | --- |
| **Local / remote branch** | `feat/discoverability-remediation` on `https://github.com/Synergyscape-V1/skeldir-2.0`. Branch tip at last documentation update: **`9d417bfc`** (includes D6 stack + follow-on CI fixes). |
| **Mainline integration** | **BLOCKED:** `gh pr create --base main` returns GraphQL *“branch has no history in common with main”*. There is **no merge-base** with `origin/main` from this lineage without an explicit integration strategy (subtree, re-home repo, or org-approved history reconciliation). |
| **CI (feature branch)** | Workflow **`.github/workflows/marketing-discoverability.yml`** runs D2 → D3 → D4 → D5 → D6 (+ negative controls). After remediations in §16, D2/D3/D4 main harness and D5/D6 steps progressed; **D4 negative controls still fail on remote** until **`discoverability-d4-negative-controls.mjs`** golden fixture is aligned with the JSON-LD-in-`<head>` validator (see §16.2). Run ID examined: **26342205879** (`9d417bfc`). |
| **CI (`main`)** | **Not applicable / not proven** — no PR to `main`. |
| **Deploy preview** | Not attached; not proven here. |
| **Production-final blocked?** | **yes** |

**Git author note:** Commits on the workstation used one-off `git -c user.name=… -c user.email=…` because no default `user.name` / `user.email` was configured. Repository `git config` was **not** modified.

---

## 4. Files changed (summary table)

| Area | Representative paths | Reason |
| --- | --- | --- |
| Evidence UI + types | `src/components/discoverability/EvidenceLibraryDocument.tsx`, `src/types/evidenceLibrary.ts` | Shared evidence page contract (BLUF, key facts, claim/evidence table, capability block, methodology, limitations, owner, last reviewed, related proof). |
| Evidence content | `src/data/evidenceLibraryCatalog.ts` | Single catalog for hub + slugs; distinct copy per platform pair; internal link mini-syntax to D5 routes. |
| Evidence routes | `src/app/resources/evidence/page.tsx`, `src/app/resources/evidence/[slug]/page.tsx` | Static hub + SSG detail pages + metadata / JSON-LD. |
| Resources hub | `src/app/resources/page.tsx`, `ResourcesPageClient.tsx` | Evidence Library entry strip + link into `/resources/evidence`. |
| Sitemap + route registry | `discoverability.sitemap-manifest.json`, `discoverability.routes.json` | Indexable D6 URLs registered consistently. |
| D4 schema | `scripts/discoverability/lib/d4-structured-data.mjs` | `CollectionPage` for evidence hub; `WebPage` (+ breadcrumbs) for nested evidence; articles unchanged. |
| D4 post-build | `scripts/d4-move-jsonld-to-head.mjs` | After `next build`, hoists body JSON-LD into `<head>` for static export contract (CI must ship this file — see §16). |
| D0 governance | `scripts/discoverability/lib/registry-schema.mjs` | Reserved slug **`evidence`**: `out/resources/evidence.html` is the D6 hub, not an `articlesData` article instance. |
| D6 artifacts | `BUYER_QUERY_CONTENT_MATRIX.md`, `discoverability.buyer-query-matrix.json`, `EVIDENCE_LIBRARY_REGISTRY.md`, `discoverability.evidence-library-registry.json`, `discoverability.d6-similarity-overrides.json` | Human + machine registries; similarity override file for future pair justifications. |
| D6 harness | `scripts/discoverability/lib/d6-evidence-library.mjs`, `discoverability-d6-harness.mjs`, `discoverability-d6-negative-controls.mjs`, `package.json` | `npm run discoverability:d6` + negative controls. |
| D5 proof surface (required for D6 links + sitemap coherence) | `src/app/methodology/`, `ai-boundary/`, `revenue-verification/`, `attribution-methodology/`, `discrepancy-taxonomy/`, `TrustProofPage.tsx`, `LegalPlaceholderPage.tsx`, `src/lib/schema/trustProof.ts`, updates to `api`, `docs`, `trust-envelope`, legal placeholders, `discoverability.claim-proof-registry.json`, `D5_CLAIM_PROOF_REGISTRY.md`, D5 harness scripts | D6 evidence pages must cite live proof authorities; sitemap manifest lists D5 indexable routes; D2/D5 gates expect built HTML. |
| D2 policy | `scripts/discoverability/lib/d2-crawl-graph.mjs` | Remove `/trust-envelope`, `/docs`, `/api` from sitemap “forbidden” set when those URLs are indexable per manifest; align `META_NOINDEX_PUBLIC_PATHS` with actual `noindex` policy. |
| Footer | `src/components/layout/Footer.tsx` | D5.1 policy: required labels (including **Methodology**, **TrustEnvelope**) wired to canonical hrefs. |
| CI | `.github/workflows/marketing-discoverability.yml` | Runs D5 + D6 gates on `marketing/**` changes. |

**Commit chain (newest first):** `9d417bfc` (D5 routes + D2 alignment + Footer), `3b68d12b` (add `d4-move-jsonld-to-head.mjs`), `05e54147` (this report — earlier revision), `2d30fe2c` (D6 evidence library + matrices + harnesses).

---

## 5. Buyer query matrix summary

Authoritative tables live in:

- `marketing/BUYER_QUERY_CONTENT_MATRIX.md`
- `marketing/discoverability.buyer-query-matrix.json`

**Shape:** **19** entries covering the directive’s minimum buyer/agent questions and **nine** `query_category` buckets (`platform_discrepancy`, `revenue_verification`, `finance_audit`, `attribution_methodology`, `trust_envelope`, `confidence_semantics`, `privacy_boundary`, `ai_boundary`, `benchmark_methodology`). Each row includes `query`, `query_category`, `buyer_role`, `search_intent`, `agent_retrieval_intent`, `canonical_route`, `route_status`, `proof_routes`, `claim_registry_refs`, `priority` (P0/P1/P2), `owner`, `last_reviewed`.

---

## 6. Evidence library registry summary

- `marketing/EVIDENCE_LIBRARY_REGISTRY.md`
- `marketing/discoverability.evidence-library-registry.json`

**15** registry rows: **hub** `/resources/evidence` + **14** evidence slugs (core + optional platform/reconciliation pages). Fields include `route`, `cluster`, `primary_query`, `secondary_queries`, `proof_authority_routes`, `content_status`, `indexable`, `sitemap_required`, `schema_type`, `owner`, `last_reviewed`, `similarity_group`.

---

## 7. Evidence route coverage

All `D6_CORE_EVIDENCE_ROUTES` (and optional slugs in the catalog) produce static HTML with the harness-required sections and headings, including **BLUF**, **Key Facts**, **Claim / Evidence Table**, capability status block, **How Skeldir Treats This**, **Methodology**, **What This Does Not Prove**, **Limitations**, **Related Proof Pages**, **Related Buyer Questions**, **Last Reviewed**, **Owner**, and at least one `href="/…"` to D5 proof authorities — verified by `npm run discoverability:d6`.

---

## 8. D5 proof boundary integration

| D5 proof authority (examples) | Role for D6 |
| --- | --- |
| `/methodology`, `/revenue-verification`, `/attribution-methodology`, `/discrepancy-taxonomy`, `/ai-boundary`, `/trust-envelope`, `/security`, `/api`, `/docs` | Linked from every evidence page’s “Related Proof Pages” / catalog `relatedProof`; registry `proof_authority_routes` records the mapping. D6 copy states it does **not** redefine D5 terms. |

---

## 9. Future-capability honesty boundary

- Evidence pages include an explicit **capability status** block (labels such as *Currently public*, *Planned*, *Unavailable*, *Partially implemented*, *operator/legal review required*).
- Harness enforces absence of disallowed “live capability” phrasing unless paired with approved capability semantics (e.g. guards around “live API”, blocks on treating Bayesian/cross-tenant benchmarks as authoritative, blocks blanket “we collect no PII”, etc. — see `d6-evidence-library.mjs`).

---

## 10. Similarity / no-spam evidence

| Pair | Metric | Threshold | Result |
| --- | --- | --- | --- |
| Meta vs Stripe × Google Ads vs Shopify | De-boilerplated token Jaccard | soft **0.72** / hard **0.85** | **~0.31** — PASS |
| Overrides | `discoverability.d6-similarity-overrides.json` | `pair_overrides` | **[]** (no manual justification required at this time) |

*Directive asked for a matrix: the harness currently enforces the highest-risk pair explicitly; additional pairs can be added to the harness/registry if product requires broader automated pairwise gates.*

---

## 11. Crawl / sitemap / schema integration

- **Route registry:** D6 paths recorded in `discoverability.routes.json`.
- **Sitemap manifest:** D6 + D5 indexable paths in `discoverability.sitemap-manifest.json`; consumed by `src/app/sitemap.ts`.
- **Canonical:** D2 harness checks built `out/**/*.html` canonical alignment for every sitemap `loc`.
- **JSON-LD:** Evidence hub → `CollectionPage` + `BreadcrumbList`; evidence detail → `WebPage` + `BreadcrumbList` (D4 branch). Post-build `d4-move-jsonld-to-head.mjs` moves blocks into `<head>` for export HTML.
- **Bot policy:** No regression introduced for indexable evidence URLs under the existing `discoverability.bot-policy.json` + `robots.ts` contract.

---

## 12. Harness proof

### 12.1 Local (workspace)

| Command | Result |
| --- | --- |
| `npm run discoverability:d6` | **PASS** |
| `npm run discoverability:d6:negative-controls` | **PASS** |
| `npm run discoverability:d0` | **PASS** (post `evidence` slug governance) |
| `npm run discoverability:d1` | **PASS** |
| `MARKETING_D4_SKIP_BUILD=1 npm run discoverability:d4` | **PASS** |
| `MARKETING_D5_SKIP_BUILD=1 npm run discoverability:d5` | **PASS** (1× informational WARN: production-final separation) |
| `npm run discoverability:d5:negative-controls` | **PASS** |
| `npm run discoverability:d2` | **PASS** (includes full `npm run build`) |
| `npm run discoverability:d3` | **PASS** (`D3_LIVE_URL` live fetch skipped unless set) |

**Not re-run in the latest short session:** `discoverability:d2:negative-controls`, `discoverability:d3:negative-controls`, full `discoverability:d4` without skip (CI runs full build + D4 NC).

### 12.2 Remote CI (GitHub Actions, `feat/discoverability-remediation`)

| Step | Result on run **26342205879** (`9d417bfc`) |
| --- | --- |
| D2 | **PASS** (after D5 routes + D2 forbidden-set fix) |
| D3 + D3 NC | **PASS** (per job progression; failure occurred later) |
| D4 harness | **PASS** |
| **D4 negative controls** | **FAIL** — NC-D4-04 “golden home fixture” JSON-LD placement vs `validateJsonLdScriptsInHead` / `validateD4IndexablePage` (see §16.2) |
| D5 / D6 | Not reached in that run after D4 NC failure |

---

## 13. Artifact excerpts (local static export)

After `npm run build`, inspect under `marketing/out/`:

| Artifact | Path |
| --- | --- |
| Evidence hub | `out/resources/evidence.html` |
| Meta vs Stripe | `out/resources/evidence/meta-vs-stripe.html` |
| Google Ads vs Shopify | `out/resources/evidence/google-ads-vs-shopify.html` |
| Deterministic vs probabilistic confidence | `out/resources/evidence/deterministic-vs-probabilistic-confidence.html` |
| Finance ROAS audit checklist | `out/resources/evidence/finance-roas-audit-checklist.html` |
| Benchmark methodology | `out/resources/evidence/benchmark-methodology.html` |

Excerpts are intentionally not pasted here at full length; they are deterministic build outputs and should be quoted from `out/` for audit defensibility.

---

## 14. Remaining unknowns (fact-bound)

1. **`main` integration:** Unrelated histories block PR creation until the org selects an integration approach.
2. **D4 NC on CI:** Until **`marketing/scripts/discoverability-d4-negative-controls.mjs`** on the default branch matches the JSON-LD-in-`<head>` contract (see §16.2), **`npm run discoverability:d4:negative-controls`** may fail in CI even when local D4 main harness passes with skip flags.
3. **Production / preview URLs:** No live URL list or curl transcript is claimed in this document.

---

## 15. D7 readiness

**Local engineering:** **Yes** — D6 evidence routes are static, registered, sitemap-backed, schema-shaped under D4, and gated locally by D6 harnesses.

**Production / mobile / performance hardening (D7):** Proceed only with awareness that **production-final** closure remains blocked on global gates; also resolve **D4 negative controls on CI** so the discoverability workflow is fully green on the integration branch.

---

## 16. Initial findings and remediations (evidence trail)

### 16.1 Finding: post-build JSON-LD hoist script missing from git

- **Symptom (CI):** `next build` succeeded, then `node scripts/d4-move-jsonld-to-head.mjs` failed with **`MODULE_NOT_FOUND`** on GitHub Actions.
- **Root cause:** `package.json` `build` invoked the script, but the file was not in the tracked tree.
- **Remediation:** Committed **`marketing/scripts/d4-move-jsonld-to-head.mjs`** (`3b68d12b`).

### 16.2 Finding: D2 “forbidden sitemap URL” contradicted D5/D6 manifest + D4 NC golden fixture drift

- **Symptom (CI):** D2 failed: sitemap listed `https://skeldir.com/trust-envelope`, `/docs`, `/api` but validator treated them as forbidden.
- **Root cause:** `validateSitemapMatchesExpected` in **`d2-crawl-graph.mjs`** still listed those paths in `forbiddenExact` while the sitemap manifest marked them indexable for D5.
- **Remediation:** Committed D2 policy update + **full D5 static proof routes and claim registry** + Footer wiring + D5 harnesses (`9d417bfc`). D2 then passed locally and progressed on CI.

- **Symptom (CI, follow-on):** **`discoverability:d4:negative-controls`** failed NC-D4-04: *“golden home fixture … JSON-LD script must be wholly inside `<head>`”*.
- **Root cause:** Committed **`discoverability-d4-negative-controls.mjs`** still used a **`headBase` template that closed `</head>` before JSON-LD**, while `validateD4IndexablePage` now enforces JSON-LD-in-head (consistent with `d4-move-jsonld-to-head.mjs` and D4 main harness). A corrected version exists **locally as unstaged changes** to that file (refactor `headBase` to accept `inner`, move golden JSON-LD into `<head>`, add NC-D4-09 body-json-ld case, fix article/pricing fixtures).
- **Remediation status:** **Documented; not landed on remote at time of this report revision.** Next step is to **`git add` + commit + push** `marketing/scripts/discoverability-d4-negative-controls.mjs` (and re-run / watch `marketing-discoverability`).

### 16.3 Finding: B1.4-P3 / merge-to-`main` / “green main CI” cannot be asserted

- **Symptom:** `gh pr create --base main` fails (no common ancestor).
- **Remediation:** Not a D6 content change — requires repository integration decision at org level.

---

### B1.4-P3 closure statement

**B1.4-P3 is not satisfied:** there is no falsifiable proof of merge to **`main`** via protected workflow, nor **green `main` CI**, nor deploy-preview / production curls, from this lineage.

**What is satisfied with local falsifiability:** D6 architecture + registries + static pages + local harness matrix described in §12.1.

**Next engineering commits (minimal):** land **`discoverability-d4-negative-controls.mjs`** fix for CI D4 NC; then re-run `gh run watch` on `marketing-discoverability` for `feat/discoverability-remediation`. **Next org actions:** reconcile `main` history or adopt new canonical remote; then PR + merge + attach preview + production verification.
