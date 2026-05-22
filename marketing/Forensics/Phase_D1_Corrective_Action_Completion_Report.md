# Phase D1 Corrective Action Completion Report

**Subtitle:** HTML-first retrieval integrity — content evolution & structural proof  
**Worktree:** `marketing/`  
**Date:** 2026-05-21  

---

## 1. Verdict

**PASS** — D1 corrective gates satisfied for `marketing_static` article surfaces: no loading shells, registry-driven article bodies aligned to `articlesData.ts`, TOC and `generateStaticParams` parity, JSON-LD parse + metadata consistency + `<` sanitization, resource hub anchors, `/book-demo` sitemap containment, structural negative controls, and empirical multi–User-Agent fetches against a local static server serving `out/`.

---

## 2. Scope Confirmation

This work is **D1 corrective only** (retrieval integrity under content evolution). No D2 sitemap/robots rollout, no D4 sitewide schema program, no Trust API or backend work.

**`/book-demo`:** **Contained, not repaired.** Registry still shows `indexable_candidate`, `transactional_static`, `sitemap_required: false`, `sitemap_implemented: false`, `status: active_defective_until_static_body_verified`. The D1 harness asserts `sitemap_required` is not `true` and that `sitemap_implemented` is not `true` while the route remains defective (negative control NC-11 proves the guard fires if policy regresses).

---

## 3. Source-of-Truth Map

| Slug | Metadata source | Static param | Body source | Renderer | Built HTML | Registry instance | JSON-LD |
|------|-----------------|--------------|-------------|----------|------------|-------------------|---------|
| `why-your-attribution-numbers-never-match` | `src/data/articlesData.ts` | `articles.map` in `[slug]/layout.tsx` → `generateStaticParams` | `ArticleContent` module | `articleBodyRegistry.tsx` → `ArticleContent` | `out/resources/why-your-attribution-numbers-never-match.html` | `route-article-generated-why-your-attribution-numbers-never-match` | Inlined `<script type="application/ld+json">` in article page |
| `roas-is-not-a-number-its-a-range` | same | same | `ArticleContent2` | `articleBodyRegistry.tsx` | `out/resources/roas-is-not-a-number-its-a-range.html` | `route-article-generated-roas-is-not-a-number-its-a-range` | same |
| `attribution-methods-answer-different-questions` | same | same | `ArticleContent3` | `articleBodyRegistry.tsx` | `out/resources/attribution-methods-answer-different-questions.html` | `route-article-generated-attribution-methods-answer-different-questions` | same |
| `confidently-defend-budget-shift` | same | same | `ArticleContent4` | `articleBodyRegistry.tsx` | `out/resources/confidently-defend-budget-shift.html` | `route-article-generated-confidently-defend-budget-shift` | same |

**TOC:** `TableOfContents.tsx` exposes `ARTICLE_TOC_GENERATORS` keyed by the same four slugs; a runtime parity assert matches `articles` from `articlesData.ts`.

**Body registry:** `articleBodyRegistry.tsx` exports `articleBodyRegistry` and calls `assertArticleBodyRegistryParity` at module load — **build fails** if `articlesData` slugs and registry keys diverge (missing fifth article body, or stale extra key).

---

## 4. Route Architecture

**`[slug]/page.tsx` strategy**

- Async **Server Component**; `await params`; `getArticleBySlug(slug)` for metadata; **`getArticleBodyComponent(slug)`** from `articleBodyRegistry` for the body component; `notFound()` if metadata or body is missing.
- **No** `switch (slug)` / **no** inline slug-to-component import map in the route file (grep guard in `discoverability:d1`).

**Switch / if-chain present?** **No** (removed).

**Generic `ArticleTemplate(article)` from Markdown?** **Not yet** — bodies remain TSX modules (large existing documents). D1 corrective accepts the **explicit registry** pattern per directive Outcome A option (2), with **machine-enforced parity** to the metadata source of truth.

**Renderer registry present?** **Yes** — `src/data/articleBodyRegistry.tsx`.

**Exhaustiveness / parity proof**

1. Runtime: `assertArticleBodyRegistryParity` (registry keys ↔ `articles` slugs).
2. Runtime: `assertTocRegistryParity` in `TableOfContents.tsx`.
3. Harness: `validateArticleBodyRegistrySourceParity`, `validateTocSlugSourceParity`, `validateGenerateStaticParamsUsesArticles` (`npm run discoverability:d1:content-parity` or section `[3]` of `discoverability:d1`).
4. Harness: `validateRegistryArticleInstances` ↔ `parseArticleSlugsFromContent` (section `[4]`).

Adding a **fifth article** to `articlesData.ts` without updating `articleBodyRegistry` and `ARTICLE_TOC_GENERATORS` causes a **compile-time / module-load failure**, not a silent wrong body.

---

## 5. Files Changed

| File | Change | Reason |
|------|--------|--------|
| `src/data/articleBodyRegistry.tsx` | **New** — slug → body component map + parity assert | Single renderer registry; no unguarded route switch |
| `src/app/resources/[slug]/page.tsx` | Use `getArticleBodyComponent`; JSON-LD `serializeArticleJsonLd` (`\u003c`); add `url` on Article schema | Registry-driven body; safe JSON-LD per Next.js guidance |
| `src/components/article/TableOfContents.tsx` | `ARTICLE_TOC_GENERATORS` + parity assert vs `articles` | TOC keys cannot drift from metadata slugs |
| `scripts/discoverability/lib/articles-metadata-from-source.mjs` | **New** — parse `articlesData.ts` for harness JSON-LD checks | Align JSON-LD with metadata without executing TS |
| `scripts/discoverability/lib/d1-article-source-parity.mjs` | **New** — source scans for registry, TOC, `generateStaticParams` | Structural parity beyond HTML string heuristics |
| `scripts/discoverability/lib/d1-html-retrieval.mjs` | JSON-LD extract/parse/validate; registry article parity; book-demo containment; forbid `use client` on registry | Gates D1-C2, D1-C3, D1-C4, D1-C6 |
| `scripts/discoverability-d1-harness.mjs` | Full pipeline: build, parity, registry, JSON-LD per article, grep anti-`switch(slug)`, in-process static `out/` server + multi-UA `fetch` | Empirical bot parity (D1-C7) |
| `scripts/discoverability-d1-content-parity.mjs` | **New** — fast source-only parity script | `npm run discoverability:d1:content-parity` |
| `scripts/discoverability-d1-negative-controls.mjs` | NC-8…NC-11 structural / JSON-LD / registry / book-demo | Non-vacuous harness (D1-C7) |
| `package.json` | Added `discoverability:d1:content-parity` | Callable parity gate |

`npm run discoverability:d1:jsonld` is **not** a separate script: JSON-LD validation runs for **each** article HTML in `discoverability:d1` section `[6]` (equivalent to Gate D1-C3).

---

## 6. Static Export Evidence

**Commands (executed; excerpted output below):**

```text
npm run build
npm run discoverability:d1
npm run discoverability:d1:negative-controls
npm run discoverability:d1:content-parity
```

**Build:** Next.js 16.1.1 static export — four `/resources/[slug]` routes listed as SSG.

**Article HTML (representative — `why-your-attribution-numbers-never-match.html`):**

- Contains **`<h1`** with visible article title (see built file; not a loading shell).
- Contains **multiple `<h2>` / `<h3>`** in the article body region.
- Contains article-specific strings such as **Meta**, **attribution**, **revenue** (full text in `out/resources/why-your-attribution-numbers-never-match.html`).
- **No** primary `animate-pulse` + `Loading...` shell (harness `[6]` HTML heuristics pass for all four articles).

**JSON-LD raw fragment (truncated from built HTML line 307):**

```text
<script type="application/ld+json">{"@context":"https://schema.org","@type":"Article","headline":"Why Your Attribution Numbers Never Match","description":"You open Skeldir and see it: Meta Ads revenue is 16% lower than what Meta claims. ...
```

---

## 7. JSON-LD Evidence

**Extraction method:** `extractJsonLdScriptInnerHtmls(html)` in `scripts/discoverability/lib/d1-html-retrieval.mjs` — regex on `<script type="application/ld+json">…</script>`.

**Serialization / sanitization:** `serializeArticleJsonLd` in `[slug]/page.tsx` applies `JSON.stringify(...).replace(/</g, "\\u003c")` before `dangerouslySetInnerHTML`, matching the Next.js JSON-LD pattern.

**Parse result:** `JSON.parse` on each article’s block succeeds (harness per-article step `[6]` second line).

**Field consistency:** `validateArticleJsonLdAgainstMetadata` asserts:

- `@type` includes `Article`
- `headline`, `description`, `datePublished` / `dateModified`, `author.name`, and canonical `url` / `mainEntityOfPage.@id` match parsed `articlesData.ts` metadata for that slug.

**Negative control:** NC-8 (invalid JSON) and NC-9 (headline mismatch) both produce expected failures.

---

## 8. Resource Hub Anchor Evidence

**Method:** `validateResourcesHubAnchors` requires every slug from `parseArticleSlugsFromContent` to appear as `href="/resources/<slug>"` in `out/resources.html`.

**Anchors (required set):**

- `/resources/why-your-attribution-numbers-never-match`
- `/resources/roas-is-not-a-number-its-a-range`
- `/resources/attribution-methods-answer-different-questions`
- `/resources/confidently-defend-budget-shift`

Harness `[7]`:** `all 4 article slugs appear as /resources/<slug> hrefs` (PASS).

---

## 9. Bot Retrieval Evidence

**Approach:** After `npm run build`, the harness starts an **in-process HTTP server** rooted at `out/`, maps `/resources/<slug>` → `out/resources/<slug>.html`, and issues **`fetch()`** with distinct `User-Agent` headers (equivalent to the directive’s multi-UA curl against a static preview).

**Captured harness output (2026-05-21 run):**

```text
[10] Local static server bot-style fetch (in-process out/, port 4811)
  ✅ PASS: local fetch UA="curl/8.0": article body markers present (len=216906)
  ✅ PASS: local fetch UA="Googlebot Smartphone": article body markers present (len=216906)
  ✅ PASS: local fetch UA="OAI-SearchBot": article body markers present (len=216906)
  ✅ PASS: local fetch UA="Claude-SearchBot": article body markers present (len=216906)
  ✅ PASS: local fetch UA="PerplexityBot": article body markers present (len=216906)
```

**Interpretation:** Response **length and markers are identical** across UAs (expected for static files). No UA-specific shell.

**Optional production / staging fetch:** set `D1_LIVE_URL` and re-run `npm run discoverability:d1` for section `[11]` (network).

---

## 10. Harness and Negative Controls

**Commands**

```bash
cd marketing
npm run discoverability:d1
npm run discoverability:d1:negative-controls
npm run discoverability:d1:content-parity
```

**Clean pass (representative `discoverability:d1` tail):**

```text
Passes: 28  Failures: 0
```

**Structural negative controls (new):**

| ID | Scenario | Expected |
|----|-----------|----------|
| NC-8 | Malformed JSON-LD | Parse failure |
| NC-9 | Headline ≠ metadata | Mismatch error |
| NC-10 | Registry missing article slugs | Parity errors |
| NC-11 | `/book-demo` `sitemap_required: true` while defective | Containment error |

**Harness script bodies (authoritative):**

- `scripts/discoverability-d1-harness.mjs`
- `scripts/discoverability-d1-negative-controls.mjs`
- `scripts/discoverability-d1-content-parity.mjs`
- `scripts/discoverability/lib/d1-html-retrieval.mjs`
- `scripts/discoverability/lib/d1-article-source-parity.mjs`
- `scripts/discoverability/lib/articles-metadata-from-source.mjs`

---

## 11. `/book-demo` Status

| Field | Value (registry) |
|-------|------------------|
| **Repaired or contained** | **Contained** |
| **indexability_class** | `indexable_candidate` |
| **physical_surface** | `transactional_static` |
| **sitemap_required** | `false` |
| **sitemap_implemented** | `false` |
| **D2 implication** | Sitemap harness must not emit `/book-demo` until HTML + policy gates are cleared; D1 harness blocks `sitemap_required: true` on this route in its current defective class |

---

## 12. Commit / Push Status

- **D1 local proof state:** **PASS** (see harness transcripts above).
- **D1 branch proof state:** **DEFERRED TO D10** (no commit/push requested in-session; local git topology may not isolate `marketing/` — see `DISCOVERABILITY_EVIDENCE_FREEZE.md`).
- **commit-ready diff:** available under `marketing/` (registry, route, TOC, harnesses, reports).
- **primary branch:** unresolved for this workspace snapshot — confirm in canonical repo before production-final claims.

---

## 13. D2 Readiness

**D2 may begin** for sitemap generation, robots policy, canonical consistency across routes, `/book-demo` static HTML repair or explicit `noindex`, and registry updates when transactional pages become sitemap-eligible.

D1 **does not** claim sitemap implementation or `/book-demo` HTML repair.

---

## 14. Initial Findings vs Corrective Remediations (Executive)

| Finding | Remediation |
|-----------|-------------|
| H-D1-C01 — Unguarded `switch(slug)` in `[slug]/page.tsx` | **Registry** `articleBodyRegistry.tsx` + `getArticleBodyComponent`; route file grep-ban on `switch(slug)` |
| H-D1-C02 — Metadata / body drift | Runtime asserts (registry + TOC) + harness source scans + registry article rows vs slugs |
| H-D1-C03 — Harness only string-deep | Added **structural** checks (registry, TOC, `generateStaticParams`, JSON-LD parse, book-demo policy, anti-switch grep) + negative controls NC-8…NC-11 |
| H-D1-C04 — JSON-LD unvalidated | Parse + field parity vs parsed `articlesData`; raw `<` ban in script inner text; `\u003c` serialization |
| H-D1-C05 — `/book-demo` risk | Registry containment assertions + NC-11 |
| H-D1-C06 — Report lacked artifacts | This report embeds command excerpts, HTML/JSON-LD fragments, and points to harness source |
| H-D1-C07 — Bot parity theoretical only | In-process static server + multi-UA `fetch` with logged evidence |

---

*End of Phase D1 Corrective Action Completion Report.*
