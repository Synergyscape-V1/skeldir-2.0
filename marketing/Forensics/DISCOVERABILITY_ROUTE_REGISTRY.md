# Skeldir Discoverability Route Registry

## Purpose

This document is the human-readable companion to `discoverability.routes.json`. Together they form the **D0 public-surface authority** — the single source of truth for every URL, static artifact, and missing-but-linked route that Skeldir's marketing deployment exposes to crawlers, AI retrieval bots, and human visitors.

D0 does not fix discoverability. D0 makes the discoverability surface explicit, testable, and safe to remediate in phases D1–D10.

**Registry version:** 2.0.0 (D0 corrective)  
**Repo scope:** See `D0_REPO_SCOPE_RESOLUTION.md`

---

## Required vs Implemented Fields (v2)

D0 distinguishes **future obligations** from **current guarantees**:

| Field pair | Meaning |
|---|---|
| `sitemap_required` / `sitemap_implemented` | Whether route belongs in sitemap vs whether sitemap.xml exists and includes it |
| `canonical_required` / `canonical_implemented` | Whether canonical tag is planned vs present in static HTML |
| `jsonld_required` / `jsonld_implemented` | Whether JSON-LD is planned vs present in static HTML |
| `noindex_required` / `noindex_implemented` | Whether noindex is planned vs present in static HTML |

For most active routes today: `*_required=true/false` as appropriate, `*_implemented=false` (no sitemap, most pages lack canonical/JSON-LD/noindex in production HTML).

---

## Static API Docs vs Runtime Trust API

| Surface | Route / ID | Type | Static export? |
|---|---|---|---|
| Static API documentation page | `/api` | `api_docs`, `docs_static` | Yes — must be a static page under `marketing/`, **not** `app/api` route handlers |
| Trust API runtime | `infra-trust-api-runtime` | `runtime_api_external`, `external_backend` | **No** — lives in Python/FastAPI backend (`backend/app/trust/api.py`), accessed via reverse proxy or separate API domain |

Harness rule: FAIL if `marketing/src/app/api/**` exists without explicit static-export-compatible classification.

---

## Route Truth Hierarchy

Authoritative order (highest to lowest):

1. `marketing/out/**/*.html` — deployed static export truth
2. Next build-derived artifacts (when available)
3. `articlesData.ts` + `generateStaticParams` — generated article instances
4. Source route scan (`src/app/**/page.tsx`) — intent evidence
5. `app-router-resolve.mjs` — **advisory normalization helper only**

---

## Article Pattern vs Generated Instances

| Entry | Route | Type |
|---|---|---|
| Pattern | `/resources/[slug]` | `article_pattern` — `generated_instances_policy: auto_discovered` |
| Instance | `/resources/why-your-attribution-numbers-never-match` | `article` — `generated_from: /resources/[slug]`, `content_id: why-your-attribution-numbers-never-match` |

Harness syncs instances from `articlesData.ts` and `out/resources/*.html`. New/removed/renamed slugs produce actionable failure messages.

---

## Active Public Surface

| Property | Value |
|---|---|
| Active source directory | `marketing/` |
| Framework | Next.js 16.1.1 (App Router) |
| React version | 19.2.3 |
| CSS framework | Tailwind CSS v4 |
| Rendering/export mode | Static export (`output: 'export'`) |
| Deployment target | Netlify |
| Publish directory | `marketing/out/` |
| Public/static directory | `marketing/public/` |
| Production host | `https://skeldir.com` |
| Primary branch | `master` (local repo at `C:\Users\ayewhy\Skeldir Webpage`) |
| Git remote | `origin → https://github.com/Muk223/skeldir-2.0.git` |
| Production-deployed clone | `skeldir-production-main-deploy-20260518` (remote: `Synergyscape-V1/skeldir-2.0.git`, branch: `codex/marketing-production-missing-lib`) |

---

## Route Classes

| Class | Description | Indexability | Examples |
|---|---|---|---|
| `commercial` | Revenue-generating marketing pages | `indexable` | `/`, `/product`, `/pricing`, `/agencies` |
| `resource_hub` | Content hub / listing page | `indexable` | `/resources` |
| `article` | Individual knowledge/evidence article | `indexable` | `/resources/why-your-attribution-numbers-never-match` |
| `transactional` | Conversion/booking flows | `indexable_candidate` (book-demo) or `nonindex` (thank-you) | `/book-demo`, `/book-demo/thank-you` |
| `auth` | Authentication surfaces | `nonindex` | `/Login`, `/signup` |
| `legal` | Privacy, terms, security, GDPR | `indexable` (when implemented) | `/privacy`, `/security` |
| `docs` | Documentation pages | `indexable` (when implemented) | `/docs` |
| `api_docs` | Static API documentation page | `missing_required` (planned static page) | `/api` |
| `runtime_api_external` | Backend Trust API infrastructure | N/A — not a marketing route | `infra-trust-api-runtime` |
| `article_pattern` | Dynamic article route pattern | N/A — pattern entry | `/resources/[slug]` |
| `review_artifact` | Storybook/implementation comparisons | `nonindex` | `/implementations/agent-a` |
| `static_asset_surface` | Public directory static files | `nonindex` | `/implementations/population-manifest.json` |
| `missing_required` | Linked but non-existent routes | N/A | `/privacy`, `/status`, `/about`, `/careers`, etc. |
| `external` | Outbound links (not served by Skeldir) | N/A | `https://linkedin.com/company/skeldir` |
| `error` | Error/fallback pages | `nonindex` | `/404`, `/_not-found` |

---

## App Router Normalization Rules

The following Next.js App Router conventions apply to route resolution. Any registry tool or manual classification MUST follow these rules:

1. **Route groups** `(groupName)` — Excluded from the URL path. `src/app/(marketing)/pricing/page.tsx` resolves to `/pricing`, NOT `/(marketing)/pricing`. **Current status: No route groups exist in this codebase.**

2. **Parallel route slots** `@slotName` — Do NOT become URL segments. `@modal/page.tsx` does not create `/@modal`. **Current status: No parallel routes exist.**

3. **Intercepting routes** `(.)`, `(..)`, `(...)` — Route-segment-relative, not filesystem-relative. **Current status: Not used.**

4. **Dynamic segments** `[param]` — Become URL parameters. `resources/[slug]/page.tsx` → `/resources/:slug`. **Current status: One dynamic segment exists (`[slug]`).**

5. **Catch-all segments** `[...slug]` and `[[...slug]]` — **Not used.**

6. **Metadata routes** (`sitemap.ts`, `robots.ts`, `manifest.ts`) — **All missing from current codebase.** Only `manifest.webmanifest` exists as a static file.

7. **Route handlers** (`route.ts`) — **None exist.** Book-demo form uses Netlify Forms (`data-netlify="true"`).

8. **Static files in `public/`** — Served at root URL path. `public/implementations/agent-a/index.html` → `/implementations/agent-a/index.html`.

---

## Physical Surface Classes

| Class | Description | Routes |
|---|---|---|
| `marketing_static` | Statically exported marketing pages sharing root layout | `/`, `/product`, `/pricing`, `/agencies`, `/resources`, `/resources/*` |
| `transactional_static` | Statically exported conversion/booking pages sharing root layout | `/book-demo`, `/book-demo/thank-you` |
| `auth_static` | Statically exported authentication UI pages sharing root layout | `/Login`, `/signup` |
| `review_public_static` | Standalone HTML files in `public/implementations/` — NOT Next.js pages | `/implementations/agent-a` through `/implementations/agent-e` |
| `missing_required` | Routes that do not exist but are linked from the site | `/privacy`, `/security`, `/status`, `/about`, `/careers`, `/blog`, `/press`, `/docs`, `/api`, `/trust-envelope` |
| `external` | Outbound URLs not served by Skeldir | LinkedIn, X, Instagram, Cal.com, AI chat links |

**Critical physical-surface observation:** ALL Next.js routes (marketing, transactional, and auth) share a **single root layout** (`src/app/layout.tsx`). There are no route groups providing layout separation. The root layout renders `<NavigationWrapper />` on every page including Login and signup. Footer is NOT in the root layout but imported per-page.

---

## Unresolved Unknowns

| Unknown | Owner | Resolution Required By |
|---|---|---|
| Production Netlify dashboard WAF/bot rules | Infrastructure | Before D3 |
| Whether `www.skeldir.com` exists as separate surface | Infrastructure | Before D2 |
| Google Search Console index coverage | Growth | Before D8 |
| Bing Webmaster Tools status | Growth | Before D8 |
| Cal.com booking attribution/UTM forwarding | Growth | Before D8 |
| Whether production analytics exist outside codebase | Analytics | Before D8 |
| Bundle chunk sharing analysis (inconclusive without detailed chunk map) | Frontend | Defer to later phase |

---

## Owner Model

| Owner | Responsibility |
|---|---|
| `frontend` | Page components, layouts, metadata, client/server rendering, route structure |
| `content` | Article body, evidence pages, methodology, trust documentation |
| `growth` | SEO strategy, entity definition, content planning, analytics |
| `legal` | Privacy policy, terms, security, GDPR compliance |
| `infrastructure` | Deployment, Netlify config, DNS, WAF, bot management |
| `analytics` | Measurement, referral tracking, Search Console |

---

## Relationship to D1–D10 Phases

| Phase | Depends on D0 for |
|---|---|
| D1 — HTML Retrieval | Route registry identifies which pages need SSR conversion |
| D2 — Crawl Graph | Registry defines sitemap inclusions, canonical targets, noindex boundaries |
| D3 — Bot Policy | Registry classifies which surfaces bots should access |
| D4 — Schema/Entity | Registry maps JSON-LD requirements per route type |
| D5 — Trust Proof | Registry identifies missing legal/trust routes |
| D6 — Evidence Library | Registry establishes content gap inventory |
| D7 — CWV | Registry identifies pages needing performance audit |
| D8 — Observability | Registry is the baseline for coverage measurement |
| D9 — B2A Layer | Registry defines what `llms.txt` should reference |
| D10 — CI Governance | Registry is the source of truth for parity tests |

---

*Generated: 2026-05-21 | Phase: D0 | Status: Evidence Freeze*
