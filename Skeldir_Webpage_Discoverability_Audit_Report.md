# Skeldir Webpage Discoverability Audit Report

**Audit date:** Wednesday, May 20, 2026  
**Audit scope:** `c:\Users\ayewhy\Skeldir Webpage\marketing\` (primary); production host `https://skeldir.com` (runtime verification)  
**Audit mode:** Read-only — no remediation code authored  
**Presumption:** Guilty until proven innocent  

---

## 1. Executive Verdict

- **Overall verdict: FAIL.** The site fails the audit on the order-1 fundamentals (raw-HTML renderability, sitemap, robots.txt, canonical), not just on the order-7 polish layers.
- **Highest-risk confirmed gap:** Every public article detail page on `https://skeldir.com/resources/<slug>` returns 30 KB of static HTML whose entire body is `<div class="animate-pulse text-gray-400">Loading...</div>`. The article body, JSON-LD, TOC, author block, and related links exist only after client-side hydration. This was reproduced on the live production host with `Googlebot Smartphone`, `OAI-SearchBot`, `Claude-SearchBot`, `PerplexityBot`, and `GPTBot` user agents.
- **Most likely root cause:** `src/app/resources/[slug]/page.tsx` is declared `"use client"` and resolves `params` with `useEffect(() => params.then(setSlug))`, so the first server-rendered snapshot always returns the `slug === null` fallback. The article body components (`ArticleContent.tsx` and siblings) are also `"use client"`. The page therefore renders no indexable text at build time, even though `generateStaticParams` produces an HTML file per slug.
- **Recommended remediation sequence (no code authored here):**
  1. Convert the article detail route to a server component that statically renders the article body, header, JSON-LD, and TOC into HTML at build time; the only `"use client"` islands should be `ReadingProgressBar`, `BackToTop`, and `SocialShare`.
  2. Restore `src/app/sitemap.ts` and `src/app/robots.ts` (both existed in the `skeldir-favicon-clean` clone, both were dropped from the current `marketing/`); have them emit `/sitemap.xml` and `/robots.txt` covering `/`, `/product`, `/pricing`, `/agencies`, `/resources`, `/resources/<slug>`, plus a `Sitemap:` line.
  3. Make resource-grid article cards real `<a href>` anchors (currently `<article role="link" tabindex="0" onClick={router.push}>`), and route the footer Privacy/Terms/GDPR/Status/Docs/API/About/Careers/Blog/Press links away from `/resources`.
  4. Add `<link rel="canonical">`, Organization + Product + BreadcrumbList JSON-LD to commercial pages and `Article` JSON-LD into static article HTML.
  5. Add `noindex` on `/Login`, `/signup`, `/book-demo/thank-you`, plus dedicated `/privacy` and `/security` routes (footer and `/book-demo` already link to a non-existent `/privacy`).
  6. After raw-HTML retrievability is fixed, layer in `/llms.txt`, EAV-E/BLUF article framing, sameAs entity linking, and AI-referral measurement.

---

## 2. Repository Orientation

- **Framework:** Next.js 16.1.1 (App Router) on React 19.2.3, Tailwind v4. Single primary marketing codebase at `c:\Users\ayewhy\Skeldir Webpage\marketing\` (most recent edits 2026-05-20). Multiple stale clones (`skeldir-deploy-clean`, `skeldir-favicon-clean`, `skeldir-netlify-fix-20260430`, `skeldir-2.0-clone`, `skeldir-production-main-deploy-20260518`) are not the active code.
- **Rendering mode:** Static export (SSG). `marketing/next.config.ts` sets `output: 'export'`, `images.unoptimized = true`. Every `"use client"` page therefore renders a single fixed HTML snapshot at build time — the initial-state shell, not the populated state.
- **Deployment target:** Netlify. `skeldir-production-main-deploy-20260518/netlify.toml`: `base = "marketing"`, `command = "npm run build"`, `publish = "out"`. No `_headers`, no `_redirects`, no edge functions, no middleware.
- **Public/static directory:** `marketing/public/` (icons, images, videos). Build output: `marketing/out/`.
- **Route inventory (from `src/app/`):**
  - Indexable marketing: `/`, `/product`, `/pricing`, `/agencies`, `/resources`, `/resources/<slug>` (4 slugs: `why-your-attribution-numbers-never-match`, `roas-is-not-a-number-its-a-range`, `attribution-methods-answer-different-questions`, `confidently-defend-budget-shift`).
  - Transactional / auth: `/book-demo`, `/book-demo/thank-you`, `/Login` (capital L), `/signup`.
  - Implementation review surfaces: `/implementations/agent-a..agent-e/` (static `index.html` + screenshots, present in `marketing/public/implementations/`).
  - Missing despite being linked from footer/form: `/privacy`, `/security`, `/status`, `/about`, `/careers`, `/blog`, `/press`, `/docs`, `/api`, `/trust-envelope`.
- **SEO/metadata system:** Next.js Metadata API. Root `layout.tsx` exports a `metadataBase`, title, description, OG/Twitter title/description, icons. Per-route `Metadata` only on `/agencies` (page) and `/resources/<slug>` (layout). `/`, `/product`, `/pricing`, `/book-demo`, `/Login`, `/signup` rely entirely on root metadata. **No JSON-LD is emitted in static HTML on any page** (the only JSON-LD is injected via a client-side `<Script>` inside the article CSR shell and never runs before hydration).
- **Analytics system:** None. No `gtag`, no GA4 measurement ID, no Plausible, no PostHog, no Segment in `marketing/src/`**.
- **Robots/sitemap/llms files:** **All four are 404 in production.** `marketing/public/` has no `robots.txt`, no `sitemap.xml`, no `llms.txt`, no `llms-full.txt`, no `_headers`, no `_redirects`. `next-sitemap` is not installed. `src/app/sitemap.ts` and `src/app/robots.ts` exist in the older `skeldir-favicon-clean` clone but have been deleted from current `marketing/`.

### Step 0.1 — Stack and rendering mode (commands)


| Command / inspection   | Result                                                                                           |
| ---------------------- | ------------------------------------------------------------------------------------------------ |
| `pwd`                  | `C:\Users\ayewhy\Skeldir Webpage`                                                                |
| Primary `package.json` | `marketing/package.json` — Next.js 16.1.1, `output: 'export'` via `next.config.ts`               |
| `netlify.toml`         | `skeldir-production-main-deploy-20260518/netlify.toml` — `base = "marketing"`, `publish = "out"` |
| Rendering              | SSG (static export), not SSR/CSR-only SPA                                                        |
| Deployment             | Netlify (`Server: Netlify` on live `curl -I https://skeldir.com/`)                               |


### Step 0.2 — Route inventory (commands)


| Source                          | Routes found                                                                                                                           |
| ------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `marketing/src/app/**/page.tsx` | `/`, `/product`, `/pricing`, `/agencies`, `/resources`, `/resources/[slug]`, `/book-demo`, `/book-demo/thank-you`, `/Login`, `/signup` |
| `marketing/out/` build          | Same routes as static HTML; 4 article slugs under `out/resources/`                                                                     |
| Not found in repo               | `/docs`, `/trust-envelope`, `/api`, `/security`, `/privacy` (as routes)                                                                |


### Step 0.3 — Build and raw HTML inspection


| Artifact                                                      | Size (bytes) | Notes                                                             |
| ------------------------------------------------------------- | ------------ | ----------------------------------------------------------------- |
| `out/index.html`                                              | 166,356      | Hero copy present; no canonical, no JSON-LD                       |
| `out/product.html`                                            | 166,969      | No canonical, no JSON-LD                                          |
| `out/resources.html`                                          | 56,853       | Canonical present; 1 `<a href>` to article; 3 cards `role="link"` |
| `out/resources/why-your-attribution-numbers-never-match.html` | 30,936       | Body = `Loading...` only                                          |
| Live article (Googlebot UA)                                   | 30,329       | Same `Loading...` shell                                           |


---

## 3. Hypothesis Results Matrix


| Hypothesis                                                     | Status                    | Priority | Evidence (short)                                                                                                                                                                                                                                                                                                                                       | Fix Owner          |
| -------------------------------------------------------------- | ------------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------ |
| H-A01 — Resource articles are CSR-shell HTML                   | **Confirmed**             | P0       | `marketing/out/resources/why-your-attribution-numbers-never-match.html` body = `Loading...`; live `curl -A "Googlebot Smartphone" https://skeldir.com/resources/why-your-attribution-numbers-never-match` returns the same 30 KB shell                                                                                                                 | Frontend           |
| H-A02 — Article content populated only via JS                  | **Confirmed**             | P0       | `src/app/resources/[slug]/page.tsx` is `"use client"` with `useState/useEffect(params.then(setSlug))`; `ArticleContent*.tsx` are `"use client"`; static export emits the initial-state shell                                                                                                                                                           | Frontend           |
| H-A03 — Crawl-critical nav uses click handlers, not `<a href>` | **Confirmed**             | P0       | `src/components/resources/ArticleCard.tsx` uses `onClick={() => router.push(...)}` with `role="link"`; live `/resources` HTML contains only 1 article `<a href>` and 4 `role="link"` CSR-only nodes                                                                                                                                                    | Frontend           |
| H-A04 — Sitemap absent/incomplete                              | **Confirmed**             | P0       | `curl https://skeldir.com/sitemap.xml` → 404; no `sitemap.ts` in current `marketing/src/app/`; no `next-sitemap` in `package.json`                                                                                                                                                                                                                     | Infra + Frontend   |
| H-A05 — Canonical missing/inconsistent                         | **Confirmed**             | P0       | `out/index.html`, `out/product.html`, `out/pricing.html`, `out/agencies.html`, `out/book-demo.html`, `out/Login.html`, `out/signup.html`: zero `rel="canonical"` tags; live homepage also lacks canonical; `?utm_source=test` returns 200 with no canonical pointer                                                                                    | Frontend           |
| H-A06 — robots.txt missing or blocking                         | **Confirmed (absent)**    | P0       | `curl https://skeldir.com/robots.txt` → 404; no `public/robots.txt` and no `robots.ts` in current codebase                                                                                                                                                                                                                                             | Infra + Frontend   |
| H-A07 — JSON-LD absent from raw HTML                           | **Confirmed**             | P1       | Zero `application/ld+json` occurrences in any built HTML page; article `<Script>` JSON-LD lives inside `"use client"` tree and is never present at first paint                                                                                                                                                                                         | Frontend           |
| H-A08 — Mobile-first content parity                            | **Partially confirmed**   | P1       | `book-demo` page hides the entire trust-logos column on mobile (`display: none !important`); homepage mobile preview matches desktop body text; article mobile parity is moot because article body is absent for all viewports                                                                                                                         | Frontend           |
| H-A09 — Core Web Vitals risks in build                         | **Inconclusive (likely)** | P1       | Hero `<img>` has dimensions + `fetchPriority="high"` + preload (good); biggest chunk 223 KB; multiple `"use client"` islands inflate JS; no Lighthouse run available in this environment                                                                                                                                                               | Frontend           |
| H-A10 — YMYL trust scaffolding absent                          | **Confirmed**             | P1       | Articles do show author + read-time + `publishDate` in the layout metadata, but only client-rendered after hydration; no `lastReviewed`, no methodology page, no `limitations` section; legal pages `/privacy`, `/security`, `/gdpr` do not exist as routes                                                                                            | Content            |
| H-A11 — Buyer-query coverage thin                              | **Confirmed**             | P1       | Only 4 articles in `articles[]` (`src/data/articlesData.ts`); no Meta-vs-Stripe page, no Shopify reconciliation page, no view-through window page, no platform-specific discrepancy pages                                                                                                                                                              | Content            |
| H-B01 — AI bot policy missing                                  | **Confirmed**             | P0       | No `robots.txt` at all → no policy for OAI-SearchBot, Claude-SearchBot, PerplexityBot, GPTBot, Google-Extended, CCBot; no `_headers` and no WAF blocking observed                                                                                                                                                                                      | Infra              |
| H-B02 — AI crawlers receive degraded HTML                      | **Confirmed**             | P0       | All five UAs (`OAI-SearchBot`, `Claude-SearchBot`, `PerplexityBot`, `GPTBot`, `Googlebot Smartphone`) received identical 30,329-byte `Loading...` shell for the article URL                                                                                                                                                                            | Frontend           |
| H-B03 — llms.txt / llms-full.txt absent                        | **Confirmed (absent)**    | P2       | `curl https://skeldir.com/llms.txt` → 404, `/llms-full.txt` → 404; no `public/llms*.txt` in repo                                                                                                                                                                                                                                                       | Growth + Frontend  |
| H-B04 — EAV-E / BLUF structure absent                          | **Partially confirmed**   | P1       | Articles open with narrative ("You open Skeldir and see it..."), no BLUF, no key-facts box, no Entity-Attribute-Value-Evidence blocks; product page is animation-heavy not claim-evidence-heavy                                                                                                                                                        | Content            |
| H-B05 — Entity definition inconsistent                         | **Confirmed**             | P1       | Site-wide title says "Verified Ad Revenue for AI-Native Stacks"; hero says "Every ad dollar traced…"; product page brands itself "Decision intelligence for smarter ad spend"; agencies says "Bayesian confidence ranges for multi-client portfolios"; nowhere is Skeldir defined as deterministic revenue-verification / TrustEnvelope infrastructure | Growth + Content   |
| H-B06 — TrustEnvelope/Trust API not publicly documented        | **Confirmed**             | P1       | "TrustEnvelope" appears only once in homepage marketing copy; no `/trust-envelope`, no `/docs`, no `/api`, no schema for Trust API, no integer-cents/provenance/policy-authority explainer                                                                                                                                                             | Content + Frontend |
| H-B07 — Content library is a blog, not an evidence library     | **Confirmed**             | P1       | 4 thought-leadership articles in `articles[]`; no methodology page, no discrepancy taxonomy, no deterministic-vs-probabilistic explainer, no platform-specific reconciliation pages, no audit checklist, no benchmark methodology                                                                                                                      | Content            |
| H-B08 — Freshness signals missing                              | **Partially confirmed**   | P1       | Articles include `publishDate` in `articlesData.ts` and emit `article:published_time` meta tag (but visible date and `dateModified` are not in static HTML because the body is CSR); homepage and product page have no `dateModified` at all; no sitemap means no `lastmod`                                                                            | Frontend + Content |
| H-B09 — External entity-linking (sameAs) absent                | **Confirmed**             | P2       | Zero `sameAs` occurrences in `marketing/src/`**; LinkedIn/Twitter/Instagram links exist in footer as visible `<a>` only, not in Organization JSON-LD; no Crunchbase reference, no Wikidata QID                                                                                                                                                         | Frontend + Growth  |
| H-B10 — No AI-assistant referral measurement                   | **Confirmed**             | P2       | No analytics library installed; no `utm_source=chatgpt.com` parsing; no `document.referrer` capture; no Search Console verification mechanism present in the codebase                                                                                                                                                                                  | Analytics          |
| H-SUPP-01 — Auth/transactional routes pollute crawl surface    | **Confirmed**             | P0       | `/Login`, `/signup`, `/book-demo`, `/book-demo/thank-you` are all `output: 'export'` static HTML, present in `out/`, with no `noindex` meta and no `X-Robots-Tag` header; `/Login` is mis-capitalized (case-sensitive URL); `book-demo.html` static body is just a spinner                                                                             | Frontend           |
| H-SUPP-02 — Public claims lack proof boundary                  | **Confirmed**             | P1       | Hero claims "Every ad dollar traced, verified to the source"; book-demo page links to `/privacy` which 404s; no `/security`, no methodology page; "TrustEnvelope" mentioned without spec; no PII/tenant-isolation explainer                                                                                                                            | Content + Frontend |


---

## 4. Track A — Google Search Discoverability Findings

### H-A01 — Public knowledge routes are CSR shells rather than indexable HTML

- **Assertion:** At least one high-value public route, especially `/resources/why-your-attribution-numbers-never-match`, returns an initial HTML shell containing only loading state or minimal app scaffolding instead of article content.
- **Status:** **Confirmed gap**
- **Files inspected:** `marketing/out/resources/*.html`, `marketing/src/app/resources/[slug]/page.tsx`, `marketing/src/components/article/ArticleContent.tsx`, `live-audit/live-article-googlebot.html`
- **Commands run:**
  - `Select-String -Pattern 'Loading|animate-pulse' -Path marketing/out/resources/*.html`
  - `curl.exe -s -L -A "Googlebot Smartphone" https://skeldir.com/resources/why-your-attribution-numbers-never-match`
- **Runtime URLs tested:** `https://skeldir.com/resources/why-your-attribution-numbers-never-match`
- **Evidence snippets:**

Static build (`marketing/out/resources/why-your-attribution-numbers-never-match.html`, 30,936 bytes). The entire `<body>` after the header:

```html
<div class="min-h-screen flex items-center justify-center bg-white">
  <div class="animate-pulse text-gray-400">Loading...</div>
</div>
```

All 4 article HTML files (`attribution-methods-answer-different-questions.html`, `confidently-defend-budget-shift.html`, `roas-is-not-a-number-its-a-range.html`, `why-your-attribution-numbers-never-match.html`) match `animate-pulse` and `Loading...` and contain none of the article body strings (no "Meta Ads", no "Sixteen", no "Stripe", no article `<h2>` body).

Live production:

```text
curl -A "Googlebot Smartphone" https://skeldir.com/resources/why-your-attribution-numbers-never-match
size: 30329 bytes
body contains: <div class="animate-pulse text-gray-400">Loading...</div>
does NOT contain: "Meta Ads revenue is 16%"
```

- **Evidence of falsification (not met):** Raw HTML would need article title, body text, headings, metadata, canonical tag, and no placeholder-only loading state.
- **Risk explanation:** Googlebot may eventually render JS and see the article on subsequent passes, but snippet selection, freshness signals, structured data, and first-impression indexing happen against this 30 KB Loading shell. AI search bots that do not execute JS will only ever see "Loading...".
- **Priority:** P0
- **Fix owner:** Frontend

---

### H-A02 — Resource articles are populated only after client-side JavaScript execution

- **Assertion:** Resource-detail pages rely on client-side fetch, route state, local arrays, or hydration to populate primary content.
- **Status:** **Confirmed gap**
- **Files inspected:** `marketing/src/app/resources/[slug]/page.tsx`, `marketing/src/app/resources/[slug]/layout.tsx`, `marketing/src/components/article/ArticleContent.tsx`, `marketing/src/data/articlesData.ts`, `marketing/src/content/Article 1_ Why Your Attribution Numbers Never Match.md`
- **Commands run:** Source read; `grep "use client|useEffect|useState" marketing/src/app/resources`
- **Runtime URLs tested:** N/A (source + static build sufficient)
- **Evidence snippets:**

`marketing/src/app/resources/[slug]/page.tsx`:

```tsx
"use client";
// ...
export default function ArticlePage({ params }: ArticlePageProps) {
    const [slug, setSlug] = useState<string | null>(null);

    useEffect(() => {
        params.then((p) => setSlug(p.slug));
    }, [params]);

    if (!slug) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-white">
                <div className="animate-pulse text-gray-400">Loading...</div>
            </div>
        );
    }
```

The `<Script id="article-jsonld" type="application/ld+json">` JSON-LD is emitted *inside* this client tree, so it never appears in initial HTML. The four `ArticleContent*.tsx` components are `"use client"` and contain the body as hardcoded JSX (not from markdown). The source markdown in `src/content/Article 1_ Why Your Attribution Numbers Never Match.md` is unused by the runtime.

- **Evidence of falsification (not met):** Article content would need to exist in statically generated Markdown/MDX/HTML or be server-rendered into the initial response.
- **Risk explanation:** With `output: 'export'`, Next.js renders only the initial client state at build time, which is permanently the loading screen.
- **Priority:** P0
- **Fix owner:** Frontend

---

### H-A03 — Crawl-critical navigation is not exposed through real href links

- **Assertion:** Important routes are navigated through buttons, click handlers, React state, or router-only constructs that are not discoverable as raw `<a href="">` links.
- **Status:** **Confirmed gap**
- **Files inspected:** `marketing/src/components/resources/ArticleCard.tsx`, `marketing/src/components/resources/ArticleGrid.tsx`, `marketing/src/components/resources/ResourcesHero.tsx`, `marketing/src/components/layout/Footer.tsx`, `marketing/src/components/layout/Navigation.tsx`, `marketing/out/resources.html`, live `https://skeldir.com/resources`
- **Commands run:**
  - `grep` / `Select-String` on `out/resources.html` for `<a href="/resources/`
  - `curl.exe -s -L https://skeldir.com/resources`
- **Runtime URLs tested:** `https://skeldir.com/resources`
- **Evidence snippets:**

`marketing/src/components/resources/ArticleCard.tsx`:

```tsx
export function ArticleCard({ article }: ArticleCardProps) {
    const router = useRouter();
    const handleClick = () => {
        router.push(`/resources/${article.slug}`);
    };
    return (
        <article
            onClick={handleClick}
            role="link"
            tabIndex={0}
            // no <a href>
```

`marketing/out/resources.html`: only **1** `<a href="/resources/why-your-attribution-numbers-never-match">` (featured hero from `ResourcesHero.tsx`); the other three article cards are `role="link"` divs.

Live `https://skeldir.com/resources`: **1** anchor + **4** `role="link"` elements.

Footer (`marketing/src/components/layout/Footer.tsx`) has real `<a href>` links, but many funnel to `/resources`: Privacy Policy → `/resources`, Terms of Service → `/resources`, GDPR → `/resources`, Careers/Blog/Press/Documentation/API Reference/Status → `/resources`, About → `/agencies`. No anchors to `/privacy`, `/security`, `/docs`, `/api`.

- **Evidence of falsification (not met):** Homepage and resources hub would need static `<a href>` links to all crawl-critical pages.
- **Risk explanation:** Googlebot follows `<a href>` links to discover URLs. 3 of 4 articles are unreachable through static crawl from the index page; legal pages do not exist and footer entries point to the wrong surface.
- **Priority:** P0
- **Fix owner:** Frontend

---

### H-A04 — XML sitemap is absent, incomplete, stale, or missing resource-detail URLs

- **Assertion:** The repository does not generate or serve a complete sitemap containing all public commercial, resource, methodology, and article routes with accurate `lastmod`.
- **Status:** **Confirmed gap**
- **Files inspected:** `marketing/package.json`, `marketing/public/`**, `marketing/src/app/`**, `skeldir-favicon-clean/marketing/src/app/sitemap.ts` (historical), live `/sitemap.xml`
- **Commands run:**
  - `find` / `Glob **/sitemap`*
  - `curl.exe -s -o nul -w "%{http_code}" -L https://skeldir.com/sitemap.xml`
- **Runtime URLs tested:** `https://skeldir.com/sitemap.xml` → **404**
- **Evidence snippets:**

```text
curl https://skeldir.com/sitemap.xml → HTTP 404
marketing/public/ → no sitemap.xml
marketing/src/app/ → no sitemap.ts (deleted from current tree; existed in skeldir-favicon-clean dated 2026-04-14)
package.json → no next-sitemap dependency
```

- **Evidence of falsification (not met):** `/sitemap.xml` would return 200, include all public routes, exclude auth/dashboard routes, and contain accurate `lastmod`.
- **Risk explanation:** No sitemap means Google relies on link-graph discovery alone — broken by H-A03 and stub footer routes.
- **Priority:** P0
- **Fix owner:** Infra + Frontend

---

### H-A05 — Canonical architecture is missing or inconsistent

- **Assertion:** Public pages do not emit self-consistent canonical URLs in raw HTML.
- **Status:** **Confirmed gap**
- **Files inspected:** `marketing/src/app/**/page.tsx`, `marketing/src/app/resources/layout.tsx`, `marketing/src/app/resources/[slug]/layout.tsx`, all `marketing/out/*.html`, live homepage and product URLs
- **Commands run:**
  - Meta/link extraction from each `out/*.html`
  - `curl.exe` on `https://skeldir.com/product` and `https://skeldir.com/product/`
  - `curl.exe` on `https://skeldir.com/product?utm_source=test`
- **Runtime URLs tested:** `https://skeldir.com/`, `https://skeldir.com/product`, `https://skeldir.com/product/`, `https://skeldir.com/product?utm_source=test`
- **Evidence snippets:**


| Page                        | `rel="canonical"` count             | JSON-LD |
| --------------------------- | ----------------------------------- | ------- |
| `out/index.html`            | 0                                   | 0       |
| `out/product.html`          | 0                                   | 0       |
| `out/pricing.html`          | 0                                   | 0       |
| `out/agencies.html`         | 0                                   | 0       |
| `out/book-demo.html`        | 0                                   | 0       |
| `out/Login.html`            | 0                                   | 0       |
| `out/signup.html`           | 0                                   | 0       |
| `out/resources.html`        | 1 (`https://skeldir.com/resources`) | 0       |
| `out/resources/<slug>.html` | 1 each                              | 0       |


Live homepage: no canonical. `/product` and `/product/` both return 200 with identical body hash; trailing-slash variant returns `301` to `/product` (good). `?utm_source=test` returns **200** with no canonical hint.

- **Evidence of falsification (not met):** Each public page would have one self-referential HTTPS canonical; tracking parameters would not create separate canonical surfaces.
- **Priority:** P0
- **Fix owner:** Frontend

---

### H-A06 — Robots.txt either blocks valuable crawl surfaces or fails to reference the sitemap

- **Assertion:** `robots.txt` is absent, not served from root, blocks public resources, or omits sitemap location.
- **Status:** **Confirmed gap (absent, not blocking)**
- **Files inspected:** `marketing/public/`**, `marketing/src/app/`**, live `/robots.txt`
- **Commands run:** `curl.exe -L https://skeldir.com/robots.txt`
- **Runtime URLs tested:** `https://skeldir.com/robots.txt` → **404**
- **Evidence snippets:** No `public/robots.txt`; no `robots.ts` in current codebase. Fail-open for crawlers, but no `Sitemap:` line and no AI-bot policy.
- **Evidence of falsification (not met):** Root-served `robots.txt` allowing public marketing/resource pages and referencing `/sitemap.xml`.
- **Priority:** P0
- **Fix owner:** Infra + Frontend

---

### H-A07 — JSON-LD structured data is absent from raw HTML

- **Assertion:** Homepage, product, resource, and article pages do not include server-visible JSON-LD blocks.
- **Status:** **Confirmed gap**
- **Files inspected:** `marketing/out/**/*.html`, `marketing/src/app/resources/[slug]/page.tsx`
- **Commands run:** `Select-String -Pattern 'application/ld\+json' marketing/out/**/*.html` → zero matches
- **Runtime URLs tested:** N/A (build output definitive)
- **Evidence snippets:** The only JSON-LD code path is client-side `<Script>` inside `"use client"` article page; never in static HTML.
- **Evidence of falsification (not met):** Raw HTML would contain valid JSON-LD appropriate to page type, not injected only after hydration.
- **Priority:** P1
- **Fix owner:** Frontend

---

### H-A08 — Mobile-first content parity is broken

- **Assertion:** Important explanatory content is hidden, removed, or inaccessible on mobile layouts.
- **Status:** **Partially confirmed**
- **Files inspected:** `marketing/src/app/book-demo/page.tsx`, `marketing/src/components/layout/HeroSection.tsx`, `marketing/src/components/layout/Footer.tsx`
- **Commands run:** Source CSS inspection; no Playwright run in this environment
- **Runtime URLs tested:** N/A
- **Evidence snippets:** `book-demo/page.tsx` mobile CSS: `.value-prop-column div:has(.trust-logos) { display: none !important; }` — partner-logo strip removed from mobile DOM. Article body parity moot (H-A01).
- **Evidence of falsification (not met):** Core claims, article bodies, schema, headings remain present in mobile DOM without mandatory interaction.
- **Priority:** P1
- **Fix owner:** Frontend

---

### H-A09 — Core Web Vitals risks are visible in code and build output

- **Assertion:** The site contains likely LCP, CLS, or INP failures.
- **Status:** **Inconclusive / requires external production data (lab signals likely negative on JS weight)**
- **Files inspected:** `marketing/out/_next/static/chunks/`*, `marketing/src/app/layout.tsx`, `marketing/src/components/layout/HeroSection.tsx`
- **Commands run:** `Get-ChildItem out/_next -Recurse -Include *.js | Sort-Object Length -Descending`
- **Runtime URLs tested:** N/A (Lighthouse not run)
- **Evidence snippets:**
  - **Positives:** Hero `<img>` width/height, `fetchPriority="high"`, preload links in `layout.tsx`.
  - **Risks:** Top JS chunk 223,561 bytes; multiple client islands (HeroSection typewriter, DashboardStage, ReconciliationNetwork, IntegrationsShowcase, InteractiveDemo).
- **Evidence of falsification (not met):** Lab LCP ≤ 2.5s, INP < 200ms, CLS < 0.1 — not measured here.
- **Priority:** P1
- **Fix owner:** Frontend

---

### H-A10 — YMYL-adjacent trust scaffolding is absent from knowledge pages

- **Assertion:** Critical content pages do not show named author, credentials, publication/last-reviewed date, methodology, limitations, sources, and links to privacy/security.
- **Status:** **Confirmed gap**
- **Files inspected:** `marketing/src/data/articlesData.ts`, `marketing/src/components/article/ArticleHeader.tsx`, `marketing/src/app/resources/[slug]/layout.tsx`, `marketing/src/components/layout/Footer.tsx`
- **Commands run:** `rg "author|reviewed|methodology|limitations|privacy|security"` on `marketing/src`
- **Runtime URLs tested:** N/A
- **Evidence snippets:** `articlesData.ts` has `author`, `publishDate`, `readTimeMinutes` — rendered only post-hydration. No `lastReviewed`. No `/privacy`, `/security`, `/methodology`. Footer Privacy → `/resources`. Book-demo form links to `/privacy` (route does not exist).
- **Priority:** P1
- **Fix owner:** Content

---

### H-A11 — Buyer-query coverage is missing from route/content inventory

- **Assertion:** The site lacks pages answering actual buyer queries (Meta-vs-Stripe, Shopify reconciliation, finance-validating ROAS, etc.).
- **Status:** **Confirmed gap**
- **Files inspected:** `marketing/src/data/articlesData.ts`, `marketing/src/app/`**, `marketing/src/content/*.md`
- **Commands run:** Full route/content inventory
- **Evidence snippets:** Exactly 4 articles. No platform-specific reconciliation pages, no audit checklist, no TrustEnvelope spec, no view-through/attribution-window explainer for finance buyers.
- **Priority:** P1
- **Fix owner:** Content

---

## 5. Track B — AI Agent Discoverability Findings

### H-B01 — AI retrieval bots are blocked, conflated, or unmanaged

- **Assertion:** The codebase lacks an explicit bot policy distinguishing search/retrieval bots from training bots.
- **Status:** **Confirmed gap**
- **Files inspected:** `marketing/`**, live `/robots.txt`, `netlify.toml`
- **Commands run:** `rg "OAI-SearchBot|GPTBot|Claude-SearchBot|PerplexityBot|Google-Extended"` → no matches
- **Runtime URLs tested:** `https://skeldir.com/robots.txt` → 404
- **Evidence snippets:** No robots.txt, no `_headers`, no WAF rules in repo. Netlify serves site with no bot differentiation.
- **Priority:** P0
- **Fix owner:** Infra

---

### H-B02 — AI crawlers receive empty or degraded HTML compared with browser users

- **Assertion:** OAI-SearchBot, Claude-SearchBot, and PerplexityBot receive the same empty shell as a no-JS crawler.
- **Status:** **Confirmed gap**
- **Files inspected:** `live-audit/live-article-*.html` (per-UA captures)
- **Commands run:**

```powershell
foreach ($ua in @('OAI-SearchBot','Claude-SearchBot','PerplexityBot','GPTBot','Googlebot Smartphone')) {
  curl.exe -s -L -A $ua "https://skeldir.com/resources/why-your-attribution-numbers-never-match" -o ...
}
```

- **Runtime URLs tested:** `https://skeldir.com/resources/why-your-attribution-numbers-never-match`
- **Evidence snippets:**


| User-Agent           | Size (bytes) | Loading shell | Article body text |
| -------------------- | ------------ | ------------- | ----------------- |
| OAI-SearchBot        | 30,329       | Yes           | No                |
| Claude-SearchBot     | 30,329       | Yes           | No                |
| PerplexityBot        | 30,329       | Yes           | No                |
| GPTBot               | 30,329       | Yes           | No                |
| Googlebot Smartphone | 30,329       | Yes           | No                |


- **Priority:** P0
- **Fix owner:** Frontend

---

### H-B03 — llms.txt / llms-full.txt is absent or incorrectly positioned

- **Assertion:** The codebase does not provide `/llms.txt` and `/llms-full.txt`.
- **Status:** **Confirmed gap (absent)**
- **Files inspected:** `marketing/public/`**, live endpoints
- **Commands run:** `curl` on `/llms.txt`, `/llms-full.txt` → both 404
- **Priority:** P2 (do not elevate above HTML-first retrieval fixes per Final Priority Rule)
- **Fix owner:** Growth + Frontend

---

### H-B04 — Public content lacks EAV-E / BLUF machine-extractable structure

- **Assertion:** Critical pages use broad brand claims instead of Entity-Attribute-Value-Evidence structure.
- **Status:** **Partially confirmed**
- **Files inspected:** `ArticleContent.tsx`, `product/page.tsx`, `HeroSection.tsx`
- **Evidence snippets:** Article 1 opens narratively: *"You open Skeldir and see it: Meta Ads revenue is 16% lower…"* No BLUF, no key-facts box, no EAV-E rows.
- **Priority:** P1
- **Fix owner:** Content

---

### H-B05 — Skeldir's entity definition is inconsistent or underspecified across metadata

- **Assertion:** Titles, meta descriptions, OG tags, and hero copy do not consistently define Skeldir as deterministic revenue-verification / financial-trust infrastructure.
- **Status:** **Confirmed gap**
- **Files inspected:** `siteMetadata.ts`, `page.tsx`, `HeroSection.tsx`, `agencies/page.tsx`, `book-demo/page.tsx`, `Footer.tsx`
- **Evidence snippets:**
  - Root title: `"Skeldir — Verified Ad Revenue for AI-Native Stacks"`
  - Product visible H1: `"Decision intelligence for smarter ad spend"`
  - Agencies description: `"Bayesian confidence ranges for multi-client portfolios"`
  - No consistent TrustEnvelope / deterministic / machine-callable evidence definition
- **Priority:** P1
- **Fix owner:** Growth + Content

---

### H-B06 — TrustEnvelope and Trust API concepts are not exposed as public machine-readable documentation

- **Assertion:** Marketing mentions TrustEnvelope/MCP but provides no indexable spec pages.
- **Status:** **Confirmed gap**
- **Files inspected:** `marketing/src/`**, `marketing/out/`**
- **Evidence snippets:** `grep TrustEnvelope` in `src` → 0 matches. Brief mention may appear in built homepage marketing copy only. No `/trust-envelope`, `/api`, `/docs`, no `get_trust_envelope`, `verify_revenue_claim`, provenance/confidence semantics pages.
- **Priority:** P1
- **Fix owner:** Content + Frontend

---

### H-B07 — Content library is a blog, not an evidence library

- **Assertion:** Resources section is thought leadership, not durable expert-owned evidence pages.
- **Status:** **Confirmed gap**
- **Files inspected:** `articlesData.ts`, `src/content/*.md`
- **Evidence snippets:** 4 articles only; categories `'Attribution' | 'Budget Planning'`; no methodology, taxonomy, platform reconciliation, audit checklist routes.
- **Priority:** P1
- **Fix owner:** Content

---

### H-B08 — Freshness signals are not machine-readable

- **Assertion:** Public pages lack visible and machine-readable `datePublished`, `dateModified`, `lastReviewed`.
- **Status:** **Partially confirmed**
- **Files inspected:** `[slug]/layout.tsx`, `ArticleHeader.tsx`, built article HTML `<head>`
- **Evidence snippets:** Article `<head>` includes `<meta property="article:published_time" content="2026-01-25"/>`. No `dateModified` in static HTML. No sitemap `lastmod`. Visible "Last updated" only post-hydration (unavailable to crawlers).
- **Priority:** P1
- **Fix owner:** Frontend + Content

---

### H-B09 — External entity-linking scaffolding is absent

- **Assertion:** The site lacks sameAs/entity links in schema.
- **Status:** **Confirmed gap**
- **Files inspected:** `Footer.tsx`, full `marketing/` grep
- **Evidence snippets:** `sameAs` → 0 occurrences. Visible footer links: LinkedIn, X, Instagram — not in JSON-LD.
- **Priority:** P2
- **Fix owner:** Frontend + Growth

---

### H-B10 — Measurement plumbing cannot distinguish AI-assistant discovery traffic

- **Assertion:** No analytics capable of preserving/identifying AI assistant referrals.
- **Status:** **Confirmed gap**
- **Files inspected:** `marketing/src/`**
- **Evidence snippets:** No gtag, GA4, Plausible, PostHog, Segment. Footer has outbound "Ask AI" links to ChatGPT/Claude/Gemini/Perplexity/Grok with pre-filled prompts — useful outbound, no inbound measurement.
- **Priority:** P2
- **Fix owner:** Analytics

---

## 6. Supplemental Findings

### H-SUPPLEMENTAL-01 — Authenticated app routes pollute or conflict with marketing crawl surface

- **Assertion:** The same frontend exposes login/signup/onboarding flows to crawlers without proper noindex/canonical separation.
- **Status:** **Confirmed gap**
- **Files inspected:** `marketing/src/app/Login/page.tsx`, `signup/page.tsx`, `book-demo/page.tsx`, `book-demo/thank-you/page.tsx`, `marketing/out/{Login,signup,book-demo}.html`
- **Commands run:** Static HTML inspection for `noindex`, `canonical`, body content
- **Runtime URLs tested:** Built artifacts (production would mirror)
- **Evidence snippets:**
  - `/Login` (capital L) — static HTML 26,963 bytes, H1 `"Login to get started with Skeldir"`, **no noindex**
  - `/signup` — static HTML 26,938 bytes, **no noindex**
  - `/book-demo` — `"use client"` + Suspense spinner; static HTML has spin animation, **no H1 headline** in shell
  - `/book-demo/thank-you` — client redirect to `/` after 5s, **no noindex**
- **Why it matters specifically to Skeldir:** Marketing and app onboarding share one static export build. Crawlers can index login/signup shells alongside commercial pages without separation.
- **Priority:** P0
- **Fix owner:** Frontend

---

### H-SUPPLEMENTAL-02 — Public claims expose deterministic-financial assertions without public proof boundary

- **Assertion:** Marketing claims verified/deterministic revenue without methodology, limitations, privacy boundary, or TrustEnvelope evidence semantics.
- **Status:** **Confirmed gap**
- **Files inspected:** `HeroSection.tsx`, `book-demo/page.tsx`, `Footer.tsx`, `AGENTS.md` (product ruleset — not surfaced on site)
- **Evidence snippets:**
  - Hero: `"Every ad dollar traced, verified to the source—So your AI Agents and teams execute from confirmed truth."` — no proof link
  - Book-demo: `"agree to our Privacy Policy"` → `href="/privacy"` — **route does not exist**
  - Footer Privacy/Terms/GDPR → `/resources` (not legal pages)
  - `AGENTS.md` describes integer-cents, RLS, no-PII, HMAC webhooks — **none surfaced on marketing pages**
- **Why it matters specifically to Skeldir:** Product identity depends on deterministic evidence and tenant isolation. Marketing financial trust without proof artifacts is an SEO trust deficit and legal exposure (form references missing Privacy Policy).
- **Priority:** P1
- **Fix owner:** Content + Frontend

---

## 7. Priority Remediation Backlog

> Code changes are **not** authored in this audit. Ordered per Final Priority Rule: raw HTML → links/sitemap/canonical/robots → bot access → structured data → YMYL → buyer-query → measurement → llms.txt.

### P0 — Blocking discoverability failures

1. **Convert `/resources/<slug>` to server-rendered HTML.** Remove `"use client"` from `src/app/resources/[slug]/page.tsx`, replace `useEffect(params.then(setSlug))` with `const { slug } = await params`, statically inline article body, header, JSON-LD, and TOC; keep only `ReadingProgressBar`, `BackToTop`, `SocialShare` as client islands. (H-A01, H-A02, H-B02, H-A07, H-B08)
2. **Restore `/sitemap.xml` and `/robots.txt`.** Reintroduce `src/app/sitemap.ts` and `src/app/robots.ts`; enumerate `/`, `/product`, `/pricing`, `/agencies`, `/resources`, all `/resources/<slug>` with accurate `lastModified`. Robots must include `Sitemap:` line, allow retrieval bots on public surfaces, disallow `/Login`, `/signup`, `/book-demo`. (H-A04, H-A06, H-B01)
3. **Make resource grid cards real anchors.** Replace `ArticleCard.tsx` `<article onClick role="link">` with `<Link href={...}>`. (H-A03)
4. **Fix footer route map.** Create `/privacy`, `/security`, `/status`, `/docs`, `/api`, `/about`, etc., or remove dead entries — stop routing legal links to `/resources`. (H-A03, H-SUPP-02)
5. **Add canonicals on every commercial route.** `/`, `/product`, `/pricing`, `/agencies`, `/book-demo` via `alternates.canonical`. (H-A05)
6. **Add `robots: noindex` to `/Login`, `/signup`, `/book-demo/thank-you`.** Rename `/Login` → `/login` with redirect. (H-SUPP-01)
7. **Allow AI search bots explicitly in `robots.txt`** with separate stanzas; document training-bot stance for `GPTBot`, `ClaudeBot`, `CCBot`. (H-B01)

### P1 — Trust and machine-readability failures

1. **Emit static JSON-LD** — Organization (`/`), SoftwareApplication (`/product`), BreadcrumbList, Article (each slug); include `sameAs` where profiles exist. (H-A07, H-B09)
2. **Create trust pages:** `/privacy`, `/security`, `/methodology`, `/trust-envelope`, `/api` or `/docs`. Link from footer and hero claims. (H-A10, H-B05, H-B06, H-SUPP-02)
3. **Add `lastReviewed` + visible "Last updated" + `dateModified`** in static HTML and Article JSON-LD. (H-B08)
4. **BLUF + Key Facts + EAV-E** on critical pages and article openings. (H-B04, H-B05)
5. **Article methodology/limitations/sources** sections. (H-A10)
6. **Evidence-library route scaffolding** — platform reconciliation, TrustEnvelope spec, finance audit checklist, etc. (H-A11, H-B07)
7. **Fix metadata on `/pricing` and `/book-demo`** — page-specific titles/descriptions/canonicals. (H-A05, H-B05)
8. **Restore mobile trust logos on `/book-demo`** — do not `display: none` partner logos. (H-A08)

### P2 — Enhancement / strategic infrastructure

1. **Lighthouse / PSI** on `/`, `/product`, `/resources/<slug>` after HTML fix. (H-A09)
2. **Privacy-respecting analytics** with AI-referrer UTM mapping (`chatgpt.com`, `claude.ai`, `perplexity.ai`, etc.). (H-B10)
3. **Search Console + Bing Webmaster** verification and sitemap submission. (Operational)
4. `**/llms.txt` and `/llms-full.txt`** — secondary to HTML fixes. (H-B03)
5. **Organization `sameAs` schema** — LinkedIn, X, Instagram, Crunchbase/Wikidata if available. (H-B09)
6. **Align "Ask AI" footer prompts** with canonical Skeldir definition. (H-B05)

---

## 8. Unknowns Requiring Production Data

- **Google Search Console index coverage** — how many `/resources/<slug>` URLs are indexed vs `Crawled - currently not indexed` vs `Discovered - currently not indexed`.
- **Netlify / server logs** — UA distribution on `/resources/`*; proportion of AI bots vs Googlebot.
- **WAF / bot-management rules** at Netlify dashboard — not visible in `netlify.toml`.
- **Production GA4 / analytics** — not in codebase; may exist outside repo.
- **Rich Results Test** — post-fix validation for Article/Organization schema.
- `**www.skeldir.com` and staging hosts** — only `skeldir.com` probed.
- **Bingbot / IndexNow** — no IndexNow key configured.
- **Cal.com booking funnel attribution** — Netlify forms on `/book-demo`; UTM forwarding into Cal bookings unverified.

---

## 9. Evidence Appendix

### A. Smoking-gun: article page is a "Loading..." shell

**Live production, `Googlebot Smartphone` UA:**

```text
curl -L -A "Googlebot Smartphone" https://skeldir.com/resources/why-your-attribution-numbers-never-match
size: 30329 bytes
body: <div class="min-h-screen flex items-center justify-center bg-white">
        <div class="animate-pulse text-gray-400">Loading...</div>
      </div>
Loading present:       True
"Meta Ads revenue is 16%" present: False
```

**Same result for:** `OAI-SearchBot`, `Claude-SearchBot`, `PerplexityBot`, `GPTBot` — identical 30,329-byte response, all `Loading=True`, `ArticleText=False`.

**Locally built file** `marketing/out/resources/why-your-attribution-numbers-never-match.html` (line ~307 in rendered output):

```html
</style></header><div class="min-h-screen flex items-center justify-center bg-white"><div class="animate-pulse text-gray-400">Loading...</div></div><!--$--><!--/$-->
```

**Root cause** `marketing/src/app/resources/[slug]/page.tsx` (lines 79–99):

```tsx
export default function ArticlePage({ params }: ArticlePageProps) {
    const [slug, setSlug] = useState<string | null>(null);

    useEffect(() => {
        params.then((p) => setSlug(p.slug));
    }, [params]);

    if (!slug) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-white">
                <div class="animate-pulse text-gray-400">Loading...</div>
            </div>
        );
    }
```

---

### B. Missing crawl infrastructure (live)

```text
curl -s -o nul -w "robots.txt: %{http_code}" -L https://skeldir.com/robots.txt   → 404
curl -s -o nul -w "sitemap.xml: %{http_code}" -L https://skeldir.com/sitemap.xml  → 404
curl -s -o nul -w "llms.txt: %{http_code}" -L https://skeldir.com/llms.txt         → 404
curl -s -o nul -w "llms-full.txt: %{http_code}" -L https://skeldir.com/llms-full.txt→ 404
```

---

### C. Canonical / JSON-LD audit across built pages


| Page                          | `rel="canonical"` | JSON-LD blocks | `og:image` | `og:url` |
| ----------------------------- | ----------------- | -------------- | ---------- | -------- |
| `out/index.html`              | 0                 | 0              | NO         | NO       |
| `out/product.html`            | 0                 | 0              | NO         | NO       |
| `out/pricing.html`            | 0                 | 0              | NO         | NO       |
| `out/agencies.html`           | 0                 | 0              | NO         | NO       |
| `out/book-demo.html`          | 0                 | 0              | NO         | NO       |
| `out/Login.html`              | 0                 | 0              | NO         | NO       |
| `out/signup.html`             | 0                 | 0              | NO         | NO       |
| `out/resources.html`          | 1                 | 0              | YES        | YES      |
| `out/resources/*.html` (each) | 1                 | 0              | YES        | YES      |


---

### D. Resource grid is not crawlable

**Built `out/resources.html`:**

- 1 article `<a href="/resources/why-your-attribution-numbers-never-match">` (featured hero).
- 3 article cards as `<article role="link" tabindex="0">` — `onClick={router.push}`, not anchors.

**Source** `marketing/src/components/resources/ArticleCard.tsx`:

```tsx
const handleClick = () => {
    router.push(`/resources/${article.slug}`);
};
return (
    <article onClick={handleClick} role="link" tabIndex={0} ...>
```

---

### E. Footer link map (from `marketing/src/components/layout/Footer.tsx`)


| Visible label    | Current `href` | Correctness                          |
| ---------------- | -------------- | ------------------------------------ |
| Plans            | `/pricing`     | OK                                   |
| Request Demo     | `/book-demo`   | OK                                   |
| Features         | `/product`     | OK                                   |
| Security         | `/product`     | Wrong — `/security` does not exist   |
| Status           | `/resources`   | Wrong                                |
| About            | `/agencies`    | Misleading — `/about` does not exist |
| Careers          | `/resources`   | Wrong                                |
| Blog             | `/resources`   | Accidental only                      |
| Press            | `/resources`   | Wrong                                |
| Documentation    | `/resources`   | Wrong                                |
| API Reference    | `/resources`   | Wrong                                |
| Privacy Policy   | `/resources`   | Wrong + legal risk                   |
| Terms of Service | `/resources`   | Wrong + legal risk                   |
| GDPR             | `/resources`   | Wrong + legal risk                   |


**Book-demo form** references `/privacy` (does not exist):

```tsx
<a href="/privacy">Privacy Policy</a>
```

---

### F. Built JS chunk sizes (top 10)

```text
223561  marketing/out/_next/static/chunks/249261e921aeebba.js
118981  marketing/out/_next/static/chunks/4996e17848c1e596.js
112594  marketing/out/_next/static/chunks/a6dad97d9634a72d.js
110015  marketing/out/_next/static/chunks/40a883cd7dc268d8.js
 74910  marketing/out/_next/static/chunks/a744efded731f30f.js
 69377  marketing/out/_next/static/chunks/e6f5ea6d276be356.css
 62483  marketing/out/_next/static/chunks/fcd126b58a78c5ce.js
 50004  marketing/out/_next/static/chunks/503dfde16dae85d8.js
 49606  marketing/out/_next/static/chunks/6d44db26cb0aa02a.js
 47560  marketing/out/_next/static/chunks/661f8ad143316771.css
```

---

### G. Pages declared `"use client"` (initial-snapshot risk surface)


| File                                                                 | Risk                                                           |
| -------------------------------------------------------------------- | -------------------------------------------------------------- |
| `src/app/resources/page.tsx`                                         | Client; initial state still emits article cards in HTML        |
| `src/app/resources/[slug]/page.tsx`                                  | **Produces Loading shell**                                     |
| `src/app/book-demo/page.tsx`                                         | Suspense fallback = spinner shell                              |
| `src/app/book-demo/thank-you/page.tsx`                               | Client redirect                                                |
| `src/app/product/page.tsx`                                           | Entire page client component                                   |
| `src/components/article/ArticleContent{,2,3,4}.tsx`                  | Client-only body                                               |
| `HeroSection.tsx`, `InteractiveDemo.tsx`, `DashboardStage.tsx`, etc. | Client; static HTML still includes initial render for homepage |


---

### H. Stack confirmation

- `marketing/package.json` → Next.js 16.1.1, React 19.2.3
- `marketing/next.config.ts` → `output: 'export'`, `images.unoptimized: true`
- `skeldir-production-main-deploy-20260518/netlify.toml` → `base = "marketing"`, `publish = "out"`, `npm run build`
- Live headers: `Server: Netlify`, `Cache-Control: public,max-age=0,must-revalidate`

---

### I. Article page `<head>` metadata (present despite empty body)

Extracted from `marketing/out/resources/why-your-attribution-numbers-never-match.html`:

```html
<meta name="description" content="Understand why Meta Ads, Google Ads, and your verified revenue never match. Learn the 5 mechanisms driving attribution discrepancies and how to defend your measurement system."/>
<meta name="author" content="Amulya Puri"/>
<meta name="keywords" content="attribution discrepancy,marketing attribution,revenue verification,Meta Ads,Google Ads,ROAS,measurement,analytics"/>
<meta name="robots" content="index, follow"/>
<meta property="og:title" content="Why Your Attribution Numbers Never Match"/>
<meta property="og:url" content="https://skeldir.com/resources/why-your-attribution-numbers-never-match"/>
<meta property="og:type" content="article"/>
<meta property="article:published_time" content="2026-01-25"/>
<link rel="canonical" href="https://skeldir.com/resources/why-your-attribution-numbers-never-match"/>
```

**Note:** Head metadata is crawlable; **body content is not** — creating a high-risk "thin / soft-404" indexing pattern.

---

### J. Live-audit artifacts preserved in workspace


| File                                            | Purpose                             |
| ----------------------------------------------- | ----------------------------------- |
| `live-audit/live-home.html`                     | Production homepage snapshot        |
| `live-audit/live-agencies.html`                 | Production agencies snapshot        |
| `live-audit/live-pricing.html`                  | Production pricing snapshot         |
| `live-audit/live-article-googlebot.html`        | Article URL as Googlebot Smartphone |
| `live-audit/live-article-OAI-SearchBot.html`    | Article URL as OAI-SearchBot        |
| `live-audit/live-article-Claude-SearchBot.html` | Article URL as Claude-SearchBot     |
| `live-audit/live-article-PerplexityBot.html`    | Article URL as PerplexityBot        |
| `live-audit/live-resources.html`                | Production resources hub            |


---

## Final Priority Rule (applied)

Investigation and severity ordering used in this report:

1. Raw HTML renderability of all public knowledge pages
2. Route/link/sitemap/canonical/robots integrity
3. Bot access and WAF/deployment blocking
4. Structured data and entity metadata
5. YMYL trust scaffolding and evidence-library content
6. Buyer-query coverage
7. Measurement
8. llms.txt / llms-full.txt

---

## Net assessment

The Skeldir webpage's failure mode is **fundamental, not cosmetic**. It renders its most important earned-trust surfaces (`/resources/<slug>`) as a **"Loading..."** spinner in static HTML to every crawler tested — Googlebot, OAI-SearchBot, Claude-SearchBot, PerplexityBot, GPTBot — while simultaneously serving **no `robots.txt`**, **no `sitemap.xml`**, **no canonical tags** on commercial pages, **no JSON-LD** anywhere in static HTML, **no privacy/security pages**, and a **footer whose legal links route to a content library**. Fix rendering, sitemap, anchors, canonicals, and noindex first. Defer llms.txt, sameAs polish, and AI-referral analytics until order-1 fundamentals retrieve correct HTML.

---

*End of report. No remediation code was authored. All hypothesis statuses are falsifiable from the file paths, command outputs, and URL probes documented above.*