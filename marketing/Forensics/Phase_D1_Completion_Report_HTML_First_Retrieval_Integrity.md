# Phase D1 Completion Report — HTML-First Retrieval Integrity

> **Superseded for gate closure:** Use **`Phase_D1_Corrective_Action_Completion_Report.md`** for the D1 corrective pass (content-source parity, JSON-LD validation, structural harness, bot fetch evidence, `/book-demo` containment). This file remains as the initial remediation narrative.

**Phase:** D1 — HTML-first retrieval integrity (marketing static export)  
**Worktree:** `marketing/`  
**Evidence baseline:** `Skeldir_Webpage_Discoverability_Audit_Report.md`, D0 route registry (`discoverability.routes.json`), D0 evidence freeze  
**Date:** 2026-05-21  

---

## 1. Verdict

**PASS** for D1 scope: indexable `marketing_static` routes produce meaningful HTML in the static export (`out/`), article detail pages no longer ship as loading shells, the resources hub exposes real anchors for every article, JSON-LD for articles appears in raw HTML, and `npm run discoverability:d1` plus `npm run discoverability:d1:negative-controls` succeed.

Out of scope for this report: backend Trust API, provider enablement, full sitemap/robots (D2), sitewide schema policy (D4), auth/noindex boundaries, commit/push governance (D10 unless explicitly authorized).

---

## 2. Scope Confirmation

This phase addressed **only** D1 — restoring **physical HTML retrievability** for public marketing knowledge surfaces under static export (`output: 'export'`).  

No B2.4 backend work, no Trust API runtime, no `aisuite`/budget/LLM cache, and no D2/D3/D4 completion claims were made beyond what D1 strictly requires (e.g. article-level `Article` JSON-LD in HTML where it was previously client-only).

---

## 3. Initial Findings (Pre-Remediation)

These findings came from the discoverability audit, the D1 directive hypotheses, and direct inspection of `marketing/` before remediation.

### 3.1 Article detail routes published absence, not knowledge

- **Observation:** Built files `out/resources/<slug>.html` contained essentially a **loading shell** (`animate-pulse`, “Loading…”) and **did not** contain article prose, semantic body headings, or platform strings visible in the audit (e.g. Meta, Stripe, ROAS) in the static body.
- **Mechanism:** `src/app/resources/[slug]/page.tsx` was a **Client Component** (`"use client"`). It resolved `params` via `useEffect` + `useState`, so the prerendered snapshot matched the **pre-slug** state. Static export therefore froze the wrong DOM.
- **Consequence:** Crawlers and retrieval bots that do not execute JavaScript received **no article** — only a shell — while humans with hydration saw the real article. That violates the D1 definition of “published knowledge.”

### 3.2 Article document surface was incorrectly client-scoped

- **Observation:** `ArticleHeader`, `ArticleContent*`, `TableOfContents`, and `RelatedArticles` carried `"use client"` even where the JSX was largely static. Article bodies did not reliably exist in **build-time HTML**.
- **Mechanism:** Modeling the **document** (title, body, TOC, metadata) inside the client tree aligned with hydration-first development, but conflicted with **HTML-first** retrieval under `output: 'export'`.

### 3.3 JSON-LD was not retrievable as raw HTML

- **Observation:** Article structured data was injected with `next/script` from the client article tree; audit pattern showed **no** `application/ld+json` in exported article HTML.
- **Mechanism:** Client-only execution path meant the serialized static HTML never contained the schema block.

### 3.4 Resources hub link graph was not crawler-realistic

- **Observation:** `ArticleCard` and `ResourcesHero` used **`router.push` / `onClick`** with `role="link"` instead of real `<a href>`. The hub’s static HTML did not expose a complete anchor set for all articles.
- **Mechanism:** UX was optimized for click cards; **retrieval physics** (anchor traversal, grep-able href graph) was not preserved in the export.

### 3.5 Dev vs. build: invalid Server/Client composition on `/resources`

- **Observation (post–D1 static fix):** `ResourcesPageClient` (client) **imported** server modules (`ResourcesHero`, `ArticleGrid`, `ArticleCard`). That violates App Router composition rules (server UI must be passed as **children/props** from a Server Component, not imported into a client module).
- **Effect:** `next build` could still succeed, but **`next dev` (Turbopack)** could present incorrect or fragile rendering for end users (hydration / tree boundary issues).
- **Remediation driver:** Treat this as a **first-class D1 follow-up** so local dev matches the integrity model of production static HTML.

---

## 4. Remediations Implemented

### 4.1 Article route: server-rendered, slug resolved at prerender time

**Change:** Replaced the client article page with an **async Server Component** that `await`s `params`, calls `getArticleBySlug`, and switches on slug to render the correct body component. Removed `useState` / `useEffect` slug gating and the loading placeholder.

**Files:** `src/app/resources/[slug]/page.tsx`

**Why:** Ensures the static export snapshot includes the full article for every `generateStaticParams` instance (still declared on `src/app/resources/[slug]/layout.tsx`).

### 4.2 Article JSON-LD in raw HTML

**Change:** Inlined a literal `<script type="application/ld+json">` with `dangerouslySetInnerHTML` on the **server** article page (no client `Script` dependency for the schema payload).

**Files:** `src/app/resources/[slug]/page.tsx`

**Why:** Guarantees `application/ld+json` appears in **view-source** and offline artifact inspection.

### 4.3 Article document components: server-compatible

**Change:** Removed `"use client"` from document components where interactivity was not required. Replaced mouse-driven underline behavior on external citations with **CSS** (`hover:underline`) where needed so server components do not attach event handlers.

**Files:**  
`ArticleHeader.tsx`, `RelatedArticles.tsx`, `ArticleContent.tsx`, `ArticleContent2.tsx`, `ArticleContent3.tsx`, `ArticleContent4.tsx`

**Why:** Primary article chrome and body must not depend on client-only execution to exist in HTML.

### 4.4 Table of contents: server-rendered, no scroll-spy dependency for retrieval

**Change:** Reimplemented `TableOfContents` as a **server component**: native `href="#id"` links; desktop sticky nav; mobile disclosure via **`<details>` / `<summary>`** (no React state).

**Files:** `src/components/article/TableOfContents.tsx`

**Why:** TOC text and anchors must appear in static HTML; scroll spy is non-essential for retrieval and previously forced a client boundary.

### 4.5 Client islands only for non-document interactions

**Retained as client components:** `ReadingProgressBar`, `SocialShare`, `BackToTop`.

**Why:** Matches the D1 allowance list; keeps motion/share UX without owning the document body.

### 4.6 Resources hub: real anchors and complete href graph

**Change:**  
- `ArticleCard`: wraps content in **`next/link`** to `/resources/<slug>` (real `href`).  
- `ResourcesHero`: wraps the hero in **`Link`**; removed `useRouter` / `onClick` shell.  
- `ArticleGrid`: removed `styled-jsx` + `"use client"`; Tailwind grid only (server).  
- `src/app/resources/page.tsx`: retained an **sr-only** `<nav>` listing **all** articles with literal `<a href>` so the export always contains the full anchor set even when the visible grid is filtered client-side.

**Files:**  
`ArticleCard.tsx`, `ResourcesHero.tsx`, `ArticleGrid.tsx`, `src/app/resources/page.tsx`

**Why:** Satisfies D1 link-graph requirements and audit grep expectations.

### 4.7 `/resources` Server/Client composition fix (dev integrity)

**Change:**  
- **Server** `page.tsx` builds **per-category React trees** (`ResourcesHero` + `ArticleGrid` / spacer) and passes them as `sections` into the client island.  
- **Client** `ResourcesPageClient.tsx` only holds category state and renders `{sections[activeCategory]}`.  
- **Server** `resources/layout.tsx` defines **Manrope** (`--font-manrope`) and wraps children; the client header uses `font-family: var(--font-manrope), …` instead of calling `next/font` inside `"use client"`.

**Files:**  
`src/app/resources/page.tsx`, `src/app/resources/ResourcesPageClient.tsx`, `src/app/resources/layout.tsx`

**Why:** Aligns with Next.js App Router composition rules so **Turbopack dev** and static export share the same integrity model.

### 4.8 D1 harness and negative controls

**Change:** Added validators and npm scripts so D1 is **machine-checkable** and **non-vacuous**.

**Files:**  
`scripts/discoverability/lib/d1-html-retrieval.mjs`  
`scripts/discoverability-d1-harness.mjs`  
`scripts/discoverability-d1-negative-controls.mjs`  
`package.json` (`discoverability:d1`, `discoverability:d1:negative-controls`)

**Why:** Encode D0 registry filtering (`marketing_static` + `indexable`), article body heuristics, hub anchor checks, and forbidden `"use client"` locations for the article document surface.

---

## 5. Hypothesis Results (Directive Crosswalk)

| ID | Hypothesis | Result | Notes |
|----|------------|--------|------|
| H-D1-01 | Article pages export as shells | **Validated** pre-fix; **refuted** post-fix | No primary `Loading…` / `animate-pulse` shell in `out/resources/*.html` after remediation |
| H-D1-02 | Client route + effect-driven slug | **Validated** pre-fix; **refuted** post-fix | Server `await params`; static params remain on `[slug]/layout.tsx` |
| H-D1-03 | Article body wrongly client-only | **Validated** pre-fix; **refuted** post-fix | Document components server-compatible; islands limited |
| H-D1-04 | JSON-LD inside client tree | **Validated** pre-fix; **refuted** post-fix | `application/ld+json` present in built article HTML |
| H-D1-05 | Hub lacks real anchors | **Validated** pre-fix; **refuted** post-fix | Cards, hero, and sr-only nav emit `/resources/<slug>` hrefs |
| H-D1-06 | Other marketing routes shell risk | **Partially addressed** | `/product` remains a large client page but **prerenders** substantive HTML; harness passes commercial routes in `out/` |
| H-D1-07 | Route class noise | **Handled in harness** | D1 checks filter D0 registry fields; non–`marketing_static` / non-indexable routes do not fail D1 |

---

## 6. Server / Client Boundary (Post-Remediation)

| Surface | Role |
|---------|------|
| `src/app/resources/[slug]/page.tsx` | **Server** — document assembly, JSON-LD |
| `ArticleHeader`, `ArticleContent*`, `TableOfContents`, `RelatedArticles` | **Server** |
| `ArticleCard`, `ArticleGrid`, `ResourcesHero` | **Server** |
| `src/app/resources/page.tsx` | **Server** — builds `sections` prop |
| `ResourcesPageClient`, `CategoryFilter` | **Client** — category UI only |
| `ReadingProgressBar`, `SocialShare`, `BackToTop` | **Client** — allowed islands |
| `Footer` | **Client** (pre-existing; not a D1 article-document defect) |

---

## 7. Static Export and Harness Proof

**Commands:**

```bash
cd marketing
npm run build
npm run discoverability:d1
npm run discoverability:d1:negative-controls
```

**Expectation:** Build completes; D1 harness passes all D0-classified `marketing_static` + `indexable` routes in `out/` (excluding the `article_pattern` registry row); negative controls fail on synthetic violations and pass on the clean tree’s `use client` boundary scan.

**Article HTML:** Each `out/resources/<slug>.html` includes `<h1>`, multiple `<h2>` / `<h3>`, substantial visible text, author/read-time markers, publish date formatting, and `application/ld+json`.

**Resources hub:** `out/resources.html` includes **four** distinct `href="/resources/<slug>"` values covering all slugs from `articlesData.ts`.

**Optional live multi-UA check:** Set `D1_LIVE_URL` to a deployed origin and re-run `npm run discoverability:d1`; the harness can `fetch` the same article path under several bot user agents. For static hosting, raw files are **UA-independent** by definition.

---

## 8. Bot Parity Statement (Static Export)

Static export serves **one physical HTML file per URL**. The deployment does not branch on `User-Agent` for document generation. Therefore, **normal curl, Googlebot Smartphone, OAI-SearchBot, Claude-SearchBot, and PerplexityBot** receive the **same** HTML bytes as long as they request the same URL from the same host configuration.

Live verification against a running preview server is optional; artifact inspection of `out/` is the authoritative D1 truth surface for Netlify-style static hosting.

---

## 9. Remaining Unknowns

1. **Git topology:** As noted in `DISCOVERABILITY_EVIDENCE_FREEZE.md`, the observed git root may encompass more than `marketing/`; **commit/branch status** should be confirmed in the user’s canonical repo before D10 claims.  
2. **`/product` depth:** Still a large client page; D1 harness passes current `out/product.html`, but a future phase could further split interactive stages from static-readable marketing copy if retrieval requirements tighten.

---

## 10. D2 Readiness

D2 may proceed on **sitemap, robots, canonical consistency, and indexability boundaries** now that D1 has restored **raw retrievability** for the D1-authorized marketing article and hub surfaces. D1 intentionally does **not** assert sitemap or full-site schema completion.

---

## 11. Files Touched (Summary)

| Area | Files |
|------|--------|
| Article route & JSON-LD | `src/app/resources/[slug]/page.tsx` |
| Article document | `src/components/article/ArticleHeader.tsx`, `ArticleContent*.tsx`, `TableOfContents.tsx`, `RelatedArticles.tsx` |
| Resources hub | `src/components/resources/ArticleCard.tsx`, `ArticleGrid.tsx`, `ResourcesHero.tsx`, `src/app/resources/page.tsx`, `ResourcesPageClient.tsx`, `src/app/resources/layout.tsx` |
| D1 automation | `scripts/discoverability/lib/d1-html-retrieval.mjs`, `scripts/discoverability-d1-harness.mjs`, `scripts/discoverability-d1-negative-controls.mjs`, `package.json` |

---

## 12. Commit / Push Status (Governance)

Per current instructions, **no commit or push was performed** as part of documenting this report unless explicitly requested elsewhere. If governance still routes commits to D10, treat this document plus the working tree diff as **commit-ready evidence** pending D10.

---

*End of Phase D1 Completion Report — HTML-First Retrieval Integrity.*
