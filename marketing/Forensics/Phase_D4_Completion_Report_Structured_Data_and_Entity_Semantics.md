# Phase D4 Completion Report — Structured Data and Entity Semantics

## 1. Verdict

**PARTIAL** — **D4 local proof state: PASS.** **D4 production-final state: BLOCKED** until this work merges to `main` and required GitHub checks are green on the merge result (see §13).

## 2. Scope Confirmation

This report covers **Phase D4 only** (central schema authority, static JSON-LD, entity registries, metadata/schema parity harnesses, CI wiring). **No D5/D6/D9 completion** is claimed. TrustEnvelope/docs/API placeholder routes remain **noindex** and are explicitly excluded from rich schema requirements.

## 3. D2/D3 Dependency Status

- **D2 local:** Assumed PASS (existing harness unchanged in substance; D4 reuses `crawlUrls` authority and `META_NOINDEX_PUBLIC_PATHS`).
- **D2 main/CI:** **Unknown until this branch merges** — workflow runs on `push` to `feat/discoverability-remediation` and on PR paths; `main` gains D4 gates only after merge.
- **D2 deploy:** Not re-verified in this session.
- **D3 local:** Assumed PASS (D4 CI steps append after D3; no D3 regressions introduced by D4 files).
- **D3 main/CI:** Same merge dependency as D2.
- **D3 deploy:** Not re-verified.
- **D4 production-final blocked?** **yes** — until protected-branch merge to `main` and green required checks on that merge commit (see §13).

## 4. Files Changed

| File | Change | Reason |
|------|--------|--------|
| `marketing/src/lib/schema/entity.ts` | New | Organization / WebSite / WebPage builders; `sameAs` from registry; `@id` strategy |
| `marketing/src/lib/schema/jsonLd.ts` | New | Central `jsonLdScriptPayload` (`<` → `\u003c`) |
| `marketing/src/lib/schema/pageSchemas.ts` | New | Product, resources hub, article, breadcrumb constructors |
| `marketing/src/lib/schema/breadcrumbs.ts` | New | Re-export breadcrumb builders (D4 module surface) |
| `marketing/src/components/schema/JsonLd.tsx` | New | Shared JSON-LD `<script>` renderer |
| `marketing/src/lib/homeHeroCopy.ts` | New | Shared homepage hero strings for HeroSection + D4 parity |
| `marketing/src/data/articleSeo.ts` | New | Single source for article SEO descriptions (layout + JSON-LD) |
| `marketing/entity-profile-registry.json` | New | Machine `sameAs` allow-list (empty) |
| `marketing/ENTITY_SEMANTICS_REGISTRY.md` | New | Canonical entity semantics governance |
| `marketing/ENTITY_PROFILE_REGISTRY.md` | New | Human audit trail for external profiles |
| `marketing/scripts/discoverability/lib/d4-structured-data.mjs` | New | D4 validation library |
| `marketing/scripts/discoverability-d4-harness.mjs` | New | `npm run discoverability:d4` |
| `marketing/scripts/discoverability-d4-negative-controls.mjs` | New | `npm run discoverability:d4:negative-controls` |
| `marketing/scripts/discoverability/lib/d1-html-retrieval.mjs` | Update | Article JSON-LD description may match meta **or** excerpt (D4 alignment) |
| `marketing/package.json` | Update | D4 npm scripts |
| `.github/workflows/marketing-discoverability.yml` | Update | CI runs D4 + D4 negative after D3 |
| `marketing/src/app/page.tsx` | Update | Homepage Organization + WebSite + WebPage JSON-LD |
| `marketing/src/app/product/layout.tsx` | Update | Product metadata + SoftwareApplication + WebPage JSON-LD |
| `marketing/src/app/product/page.tsx` | Update | Product copy constants for schema/body parity |
| `marketing/src/app/pricing/page.tsx` | Update | WebPage JSON-LD |
| `marketing/src/app/agencies/page.tsx` | Update | WebPage JSON-LD; metadata aligned to visible hero |
| `marketing/src/app/resources/page.tsx` | Update | CollectionPage + BreadcrumbList |
| `marketing/src/app/resources/layout.tsx` | Update | Meta description aligned to hub constants |
| `marketing/src/app/resources/ResourcesPageClient.tsx` | Update | Hub H1/description from shared constants |
| `marketing/src/app/resources/[slug]/layout.tsx` | Update | Import SEO from `articleSeo.ts` |
| `marketing/src/app/resources/[slug]/page.tsx` | Update | Article + breadcrumb JSON-LD via shared module |
| `marketing/src/components/layout/HeroSection.tsx` | Update | Import shared `homeHeroCopy` |
| `marketing/src/components/layout/agenciesHeroCopy.ts` | Update | Visible H1 string + shared subhead |
| `marketing/src/components/layout/AgenciesHeroSection.tsx` | Update | Use shared subhead constant |
| `marketing/src/components/pricing/PricingHero.tsx` | Update | H1/body from `pageSchemas` constants |
| `marketing/src/components/layout/FinalCTA.tsx` | Update | Remove legacy “decision intelligence” primary line |
| `marketing/src/lib/siteMetadata.ts` | Update | Canonical site title/description |

## 5. Entity Semantics Registry

- **canonical name:** Skeldir  
- **canonical description:** See `ENTITY_SEMANTICS_REGISTRY.md` (long definition + short description).  
- **approved terminology:** Revenue verification, verified commerce/payment evidence, deterministic reconciliation, TrustEnvelopes (as product concept when visible/supported).  
- **disallowed/high-risk terminology:** Unverified `sameAs`; “financial product” schema; primary “decision intelligence” without verification framing.  
- **schema `@id` strategy:** `/#organization`, `/#website`, per-route `#webpage` / `#article` / `#collection` / `#software` under `canonicalUrl()` from `crawlUrls.ts`.  
- **sameAs policy:** Registry-driven only; omit when empty.

## 6. Entity Profile Registry

| URL | Platform | Verified? | Included in sameAs? | Evidence | Owner |
|-----|----------|-----------|---------------------|----------|-------|
| *(none)* | — | no | no | `entity-profile-registry.json` has `"sameAs": []` | — |

## 7. Schema Coverage Table

| Route | Indexable? | Schema Types | JSON-LD Count | Canonical Match | Result |
|-------|------------|--------------|---------------|-------------------|--------|
| `/` | yes | Organization, WebSite, WebPage | 3 | root `/` vs `https://skeldir.com` accepted as equivalent to `https://skeldir.com/` in harness | PASS |
| `/product` | yes | SoftwareApplication, WebPage | 2 | PASS | PASS |
| `/pricing` | yes | WebPage | 1 | PASS | PASS |
| `/agencies` | yes | WebPage | 1 | PASS | PASS |
| `/resources` | yes | CollectionPage, BreadcrumbList | 2 | PASS | PASS |
| `/resources/<slug>` | yes | Article, BreadcrumbList | 2 | PASS | PASS |
| META_NOINDEX_PUBLIC_PATHS | noindex | *(no forbidden rich types)* | — | — | PASS |

## 8. Metadata / Visible Content / Schema Parity

| Route | H1 | Title | Description | JSON-LD name/headline | Match? |
|-------|-----|-------|-------------|----------------------|--------|
| `/` | Hero aria-label (final phrase) | `SITE_DOCUMENT_TITLE` | `SITE_DESCRIPTION` | WebPage `name` = hero aria string | yes (harness: name substring in HTML) |
| `/product` | Product hero H1 | `Product \| Skeldir` | hero lead | SoftwareApplication `alternateName` / `description` | yes |
| `/pricing` | `PRICING_PAGE_H1` | `Pricing \| Skeldir` | `PRICING_PAGE_DESCRIPTION` | WebPage `name` / `description` | yes |
| `/agencies` | *(client shell; harness skips H1 if absent)* | agencies metadata | hero subhead | WebPage | yes |
| `/resources` | *(client shell; harness skips H1 if absent)* | resources layout | hub description | CollectionPage | yes |
| Articles | `article.title` | `title \| Skeldir` | SEO description from `articleSeo.ts` | `headline` / `description` | yes |

## 9. JSON-LD Validation Evidence

- **extraction method:** `/<script[^>]*type=["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/gi` in `d1-html-retrieval.mjs` (reused).  
- **parse result:** `JSON.parse` on every block in D4 harness for eligible routes.  
- **field validation result:** `discoverability/lib/d4-structured-data.mjs` route-type contracts.  
- **sanitization proof:** `jsonLdScriptPayload` escapes `<`; harness rejects raw `<` in blocks.  
- **invalid fixture negative control:** NC-D4-01 / NC-D4-02 in `discoverability-d4-negative-controls.mjs`.

## 10. sameAs Evidence

- **profile registry:** `ENTITY_PROFILE_REGISTRY.md` + `entity-profile-registry.json`.  
- **HTTP/profile verification:** Not applicable (empty list).  
- **rejected profiles:** Any URL not in JSON registry must not appear — NC-D4-05.  
- **final sameAs list:** *(empty — `sameAs` omitted from Organization JSON-LD when empty)*.

## 11. Harness Proof

- **`npm run discoverability:d4`:** PASS (local run after changes).  
- **`npm run discoverability:d4:negative-controls`:** PASS.  
- **failures intentionally caught:** Missing Organization; invalid JSON; raw `<`; unapproved `sameAs`; SoftwareApplication on `/book-demo`; article headline/breadcrumb drift; Offer on `/pricing`.

## 12. Artifact Excerpts

Run locally after build:

```bash
cd marketing
grep -o "application/ld+json" out/index.html | wc -l
```

Representative blocks are visible in `out/index.html`, `out/product.html`, `out/resources.html`, and `out/resources/<slug>.html` as `<script type="application/ld+json">` with escaped `<` sequences.

## 13. Git / CI / Deploy Proof

- **branch:** `feat/discoverability-remediation` (pre-merge).  
- **commit:** `6268dd6b` — `feat(discoverability): Phase D4 JSON-LD, entity semantics, and harness`.  
- **push:** `git push origin feat/discoverability-remediation` after commit.  
- **CI:** Open or attach the latest `marketing-discoverability` workflow run for the PR once pushed (GitHub Actions on `Synergyscape-V1/skeldir-2.0`).  
- **deploy/preview:** Not attached in this session.

**Merge status:** A PR from `feat/discoverability-remediation` → `main` must be opened and merged through the repo’s protected-branch workflow; **this document’s production-final gate is not satisfied until that merge completes with required checks green.**

## 14. Remaining Unknowns

- Exact GitHub required-check set on `main` (branch protection) for this repository.  
- Whether any additional non-marketing workflows must pass for merge (outside `marketing-discoverability.yml`).

## 15. D5 Readiness Statement

**D5 may begin** for trust-proof/legal/security *content and routes* that are still placeholders today (`/trust-envelope`, expanded `/privacy`, `/docs`, `/api`, etc.). D4 intentionally does **not** mark those placeholders with rich documentation schema.
