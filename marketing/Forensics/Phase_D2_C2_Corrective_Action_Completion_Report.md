# Phase D2-C2 Corrective Action Completion Report

**Scope:** Crawl graph, index control, static-export guardrails, and centralized URL authority (follow-up to D2-C).  
**Repository:** `Synergyscape-V1/skeldir-2.0`  
**Integration target:** `main` (protected branch — merge via PR + required checks).

---

## 1. Verdict

**PARTIAL (engineering complete; merge/CI evidence operator-verified)**

| Gate | State |
|------|--------|
| Local build + `npm run discoverability:d2` | **PASS** |
| `npm run discoverability:d2:negative-controls` (incl. NC-D2-C2-01–07) | **PASS** |
| `npm run discoverability:d1` (regression after `d1-html-retrieval` → `readCrawlUrlAuthority`) | **PASS** |
| Merge to `main` + green required checks | **BLOCKED** — GitHub: *“feat/discoverability-remediation has no history in common with main”* (`gh pr create` cannot open a normal PR). Reconcile histories with `main`, then PR + attach `gh run list` / checks URLs. |

---

## 2. Scope Confirmation

This document is **D2-C2 only**. No D3/D4/D5/D9 completion is claimed.

---

## 3. Corrected Route State Machine

| State | Sitemap | robots crawl | `noindex` | Self-canonical | Notes |
|-------|---------|--------------|-----------|----------------|-------|
| **Indexable** | Yes | Allowed | No | Yes (one per URL) | Commercial + articles. |
| **Contained defective** (`/book-demo`) | No | Allowed | `noindex,follow` | **No** (D2-C2) | Avoid canonical + noindex mixed signal. |
| **Transactional noindex** (e.g. thank-you) | No | Allowed | yes | May keep canonical for URL stability (separate route). |
| **Removed** (`/implementations/*` public) | No | N/A | N/A | Absent from `out/` | Strategy A from D2-C. |

---

## 4. `/book-demo` Control State

| Field | Value |
|-------|--------|
| **Repaired or contained** | **Contained** — still client-heavy; not D1-repaired in this pass. |
| **noindex / follow proof** | `metadata.robots` in `src/app/book-demo/layout.tsx`; harness `validateBookDemoDefectiveRequiresNoindex`. |
| **Sitemap status** | **Excluded**; `validateBookDemoSitemapContainment` + harness `[9]`. |
| **Robots status** | **Not disallowed**; meta-noindex crawlability preserved. |
| **Canonical status** | **Removed** — no `alternates.canonical` on defective `/book-demo` (D2-C2). |
| **Canonical exception?** | **No** — `canonical_exception_justification: null` in registry. |
| **Registry** | `canonical_url: null`, `canonical_required: false`, `canonical_implemented: false`, `noindex_implemented: true`, `status: active_defective_until_static_body_verified`. |

**Control-state table**

| route | status | repaired_static_html | in_sitemap | robots_disallowed | meta_noindex | follow_state | canonical_present | canonical_exception_justification | registry | harness |
|-------|--------|----------------------|------------|-------------------|--------------|--------------|-------------------|-----------------------------------|----------|---------|
| `/book-demo` | defective | no | no | no | yes | follow | **no** | null | aligned | PASS |

---

## 5. Sitemap Static-Export Guard

| Item | Value |
|------|--------|
| **`src/app/sitemap.ts` `dynamic`** | `export const dynamic = "error"` |
| **`src/app/robots.ts` `dynamic`** | `export const dynamic = "error"` |
| **Request-time / nondeterministic API scan** | `validateSitemapSourceStringStaticSafe` / `validateSitemapSourceStaticSafe` forbid `next/headers`, `cookies()`, `headers()`, `draftMode()`, `connection()`, `unstable_*`, `cache: 'no-store'`, `Date.now`, and literal `https://skeldir.com` in `sitemap.ts`. |
| **Build output** | `out/sitemap.xml` generated (harness `[2]`). |
| **Deploy/preview** | **Attach** post-merge `curl` to your Netlify / production origin. |

---

## 6. Central URL Authority

| Item | Detail |
|------|--------|
| **Module** | `marketing/src/lib/crawlUrls.ts` |
| **Exports** | `SITE_ORIGIN`, `TRAILING_SLASH`, `normalizePath`, `canonicalUrl`, `sitemapUrl`, `robotsSitemapUrl`, `routeToOutputPath`, `assertTrailingSlashPolicy` |
| **`siteCrawl.ts`** | Re-exports from `crawlUrls`; `absoluteUrl` → `canonicalUrl` alias for backward compatibility. |
| **Consumers (this pass)** | `sitemap.ts`, `robots.ts`, `layout.tsx` (`metadataBase`), `resources/layout.tsx`, `resources/[slug]/layout.tsx`, `resources/[slug]/page.tsx` (JSON-LD + share URL), `d2-crawl-graph.mjs` (`readCrawlUrlAuthority`), `d1-html-retrieval.mjs` (JSON-LD expected URL). |
| **`TRAILING_SLASH`** | `false` — harness enforces no trailing `/` on non-root sitemap locs; canonical hrefs on sitemap pages checked for same policy. |
| **Unauthorized literal origin** | Blocked in `sitemap.ts` / `robots.ts` source by harness; negative **NC-D2-C2-06**. |

---

## 7. Harness Proof

**Commands**

```bash
cd marketing
npm run discoverability:d2
npm run discoverability:d2:negative-controls
npm run discoverability:d1
```

**Last successful run (local):** D2 harness **30** passes; D2 negative controls **21** passes (includes **NC-D2-C2-01** through **NC-D2-C2-07**).

**New / tightened checks**

- **`readCrawlUrlAuthority`** — parses `SITE_ORIGIN` / `TRAILING_SLASH` from `src/lib/crawlUrls.ts`.
- **Manifest origin** must equal crawl authority.
- **Static sitemap/robots source** contract + no literal `https://skeldir.com` in those files.
- **`validateRobotsSitemapUrlMatchesAuthority`** — exact `Sitemap:` URL vs authority.
- **`validateSitemapLocPathsNoTrailingSlashExceptRoot`** — trailing-slash law on `<loc>`s.
- **`validateSitemapLocCanonicalPathAlignment`** — loc vs canonical path + trailing consistency.
- **`validateBookDemoDefectiveNoSelfCanonical`** — defective + noindex + no exception ⇒ zero canonical links.
- **CI / main:** `assertDiscoverabilityGitBranchPolicy` returns early when `GITHUB_ACTIONS` or `CI` is true so **merge to `main` does not fail the harness solely on branch name**.

**Negative controls (D2-C2)**

| ID | Behavior |
|----|----------|
| NC-D2-C2-01 | Defective `/book-demo` HTML with `<link rel="canonical">` → `validateBookDemoDefectiveNoSelfCanonical` fails |
| NC-D2-C2-02 | Sitemap loc `…/product/` → trailing policy fails |
| NC-D2-C2-03 | Loc with trailing vs canonical without → alignment fails |
| NC-D2-C2-04 | Wrong `Sitemap:` host → `validateRobotsSitemapUrlMatchesAuthority` fails |
| NC-D2-C2-05 | Synthetic `sitemap` source with `cookies()` → static scan fails |
| NC-D2-C2-06 | Literal `https://skeldir.com` in synthetic sitemap source → fails |
| NC-D2-C2-07 | `robots` source with `dynamic = "force-static"` only → fails (must be `error`) |

---

## 8. Artifact Excerpts

**Note:** Run after `npm run build` in `marketing/`.

```bash
# Examples — adjust paths if needed
type out\sitemap.xml | more
type out\robots.txt
findstr /i "canonical noindex" out\book-demo.html
findstr /i "canonical" out\product.html
findstr /i "canonical" out\resources\why-your-attribution-numbers-never-match.html
```

**Expected**

- `out/book-demo.html`: **no** `<link rel="canonical"`; **yes** `noindex` + effective follow semantics.
- `out/sitemap.xml`: `<loc>` URLs under `SITE_ORIGIN` with no stray trailing slash on non-root paths.
- `out/robots.txt`: `Sitemap: https://skeldir.com/sitemap.xml` (from `robotsSitemapUrl()`).

---

## 9. Git / CI / Deploy Proof

| Field | Record here after PR |
|-------|------------------------|
| **remote** | `origin` → `https://github.com/Synergyscape-V1/skeldir-2.0.git` |
| **branch** | `feat/discoverability-remediation` (source of D2-C2 commits) → merge **into** `main` |
| **commit (D2-C2)** | `494a07f` — `fix(discoverability): D2-C2 URL authority and defective-route coherence` |
| **push** | **Done** — `origin/feat/discoverability-remediation` updated (`bed9656..494a07f`). **PR to `main`:** not created (see Verdict table). |
| **CI** | `gh run list --workflow=<name> --branch main` or PR checks URL |
| **Deploy / preview origin** | Netlify / production — attach `curl` transcripts |

**Falsifiable validation you asked for:** After PR is merged to `main`, capture:

```bash
git checkout main && git pull origin main
git log -1 --oneline
gh run list --branch main --limit 5
```

---

## 10. Remaining Unknowns

- Exact **GitHub required check** names and whether `discoverability:d2` runs on `main` in your workflow YAML (add if missing).
- **Production** behavior post-deploy (cache, `robots.txt` routing on Netlify).

---

## 11. D3 Readiness

- **Local / repo invariants:** D2-C2 remediations are in place and harnessed.
- **Production-gated D3:** Still **blocked** until deploy curl proof is attached.
- **Release-gated D3:** **Blocked** until this work is **merged to `main`** and **required checks are green** — complete the PR step and paste CI URLs into this section.

---

## Appendix — Initial findings → remediations

| Hypothesis | Remediation |
|------------|-------------|
| H-D2-C2-01 Self-canonical on defective noindexed `/book-demo` | Removed `alternates.canonical` from `book-demo/layout.tsx`; registry canonical fields cleared; `validateBookDemoDefectiveNoSelfCanonical`. |
| H-D2-C2-02 Harness allowed contradiction | Added harness `[6]` check + **NC-D2-C2-01**. |
| H-D2-C2-03 `sitemap.ts` not static-hardened | `dynamic = "error"` on `sitemap.ts` and `robots.ts`; `validateSitemapSourceStaticSafe` + string helper for NCs. |
| H-D2-C2-04 URL construction duplicated | Introduced `src/lib/crawlUrls.ts`; harness reads origin from file; sitemap manifest must match; resources JSON-LD uses `canonicalUrl` / `SITE_ORIGIN`. |
| H-D2-C2-05 Release proof | This report + **you** complete merge + CI + deploy curls. |

---

*End of report.*
