# Phase D2 Corrective Action Completion Report

**Artifact:** Crawl graph and index control (D2-C) — mechanism consistency after prior D2 pass  
**Repository:** `Synergyscape-V1/skeldir-2.0` (workspace: Skeldir Webpage / `marketing`)  
**Branch:** `feat/discoverability-remediation`  
**Corrective commits:** `3234b54`, `bed9656`  

---

## 1. Verdict

**PASS** — local mechanical objectives, harness, negative controls, registry alignment, and push of the corrective branch to `origin`.

**INCOMPLETE** — production post-deploy curl proof and merge-to-`main` CI gate are **operator-attached** items (not re-run for this document unless noted in repo CI logs).

**Rationale:** The rejected D2 state conflated **`robots.txt` Disallow**, **sitemap omission**, and **HTML `noindex`**. That is remediated in code and enforced by an upgraded harness. Production URLs must be re-curled after deploy; GitHub Actions status must be captured after PR/merge per org policy.

---

## 2. Scope Confirmation

This document describes **Phase D2 corrective action only** (crawl vs index control consistency, `/implementations/*`, `/book-demo`, sitemap/robots/canonical regression, harness + negative controls, registry, supporting script guard).

**No claims:** D3, D4, D5, D9 completion.

---

## 3. Corrected Mechanism Model

### 3.1 Initial findings (conceptual errors in the prior pass)

1. **`Disallow` + HTML `noindex` as one “deindex story”** for the same URL — crawlers that obey `robots.txt` may **never fetch** the page, so they **never observe** `<meta name="robots" content="noindex">` (Google Search guidance: `noindex` requires access unless URL-only risk is explicitly accepted and documented).

2. **Sitemap exclusion for `/book-demo`** treated as sufficient **index** control while the route remained **linked** from indexable pages (footer, CTAs). **Sitemap does not prevent discovery** via internal links.

### 3.2 Remediated model (enforced in repo)

| Mechanism | Role |
|-----------|------|
| **`robots.txt`** | **Crawl permission.** Must not block URLs whose index exclusion depends on **fetched** HTML `noindex` (unless crawl-blocked URL-only index risk is explicitly chosen and documented). |
| **Sitemap** | **Inclusion / discovery hint** for indexable canonical URLs. **Not** a substitute for `noindex` on linked non-indexable routes. |
| **Canonical** | **Preferred URL** among duplicates. Does not replace `noindex` for defective or transactional pages. |
| **`noindex` (meta)** | **Index exclusion** read from **fetched** HTML. **Requires crawlability** for obeying crawlers. |

---

## 4. Files Changed

| File | Change | Reason |
|------|--------|--------|
| `marketing/public/implementations/**` | Removed from repo | **Strategy A:** internal review artifacts must not ship in static export; removes the disallow+noindex paradox class for those URLs. |
| `marketing/src/app/robots.ts` | No `Disallow` for `/implementations/` or `/book-demo`; comments document crawlability law | Meta-noindex surfaces must remain fetchable. |
| `marketing/src/app/book-demo/layout.tsx` | `robots: { index: false, follow: true, googleBot: { … } }`; canonical to `/book-demo` | **Containment B:** defective but linked page is noindex+follow, crawlable, not sitemap-only “containment.” |
| `marketing/scripts/discoverability/lib/d2-crawl-graph.mjs` | `validateRobotsDoesNotBlockMetaNoindexRoutes`, `META_NOINDEX_PUBLIC_PATHS`, `validateBookDemoDefectiveRequiresNoindex`, `validateShippedImplementationAgentsHaveNoindex`, `htmlHasNoindexFollow`; `validateRobotsPolicy` rejects `/book-demo` and `/implementations` disallows | Mechanism-aware validation. |
| `marketing/scripts/discoverability-d2-harness.mjs` | `[3b]` robots vs meta-noindex paths; `[6]` auth/thank-you noindex, `out/implementations` absent, book-demo defective noindex | Main D2 gate cannot pass old contradictions. |
| `marketing/scripts/discoverability-d2-negative-controls.mjs` | NC-D2-X1 through NC-D2-X6 | Negative controls prove validators fire. |
| `marketing/scripts/discoverability-d0-harness.mjs` | `removed_public_surface` handling for agent routes | D0 parity when artifacts removed. |
| `marketing/discoverability.routes.json` | Agent routes removed/surface status; book-demo and thank-you registry fields aligned with layouts | Registry matches built behavior. |
| `marketing/scripts/validate-solution-articulation-iterations.mjs` | Skip with exit 0 if `public/implementations` missing | Avoid hard fail after public mount removal. |

---

## 5. `/implementations` Strategy

| Item | Answer |
|------|--------|
| **Chosen strategy** | **A — remove from public output** (preferred). |
| **Robots treatment** | **No** `Disallow: /implementations/`. No public tree, so no “blocked fetch + invisible noindex” story. |
| **Noindex / removal proof** | **`out/implementations/` absent** after `next build` (D2 harness `[6]`). No claim that Google “saw noindex” on non-exported URLs. |
| **Sitemap exclusion** | Locales under `/implementations` remain forbidden in sitemap validation. |
| **URL-only index risk accepted?** | **No** (explicit crawl-block strategy not chosen). |

---

## 6. `/book-demo` Strategy

| Item | Answer |
|------|--------|
| **Repaired or contained** | **Contained (B)** — not fully rebuilt as D1-grade static HTML in this corrective pass. |
| **Static HTML proof if repaired** | N/A. |
| **`noindex`, `follow` proof if contained** | `layout.tsx` sets `index: false`, `follow: true`. `validateBookDemoDefectiveRequiresNoindex` + `htmlHasNoindexFollow` on `out/book-demo.html` (noindex without nofollow; implicit follow allowed). |
| **Sitemap status** | **Excluded** (harness `[9]` + forbidden set in sitemap matcher). |
| **Robots status** | **`/book-demo` not disallowed.** |
| **Canonical status** | **Present:** `alternates.canonical` → `https://skeldir.com/book-demo`. |
| **Registry status** | `active_defective_until_static_body_verified`; `noindex_required` / `noindex_implemented` true; `sitemap_implemented` false. |

---

## 7. Sitemap / Robots / Canonical Regression Proof

- **Sitemap:** `out/sitemap.xml` matches `discoverability.sitemap-manifest.json` + article slugs (D2 harness `[2]`).
- **Robots:** `out/robots.txt` includes `Sitemap: https://skeldir.com/sitemap.xml`; no blanket `Disallow: /`; no `Disallow` for `/book-demo` or `/implementations`; sensitive fragment checks pass (`validateRobotsPolicy`).
- **Canonicals:** Each sitemap `loc` maps to an `out/` HTML file with exactly one `<link rel="canonical">` matching that URL (harness `[5]`).
- **Excluded routes:** Non-indexable / transactional / placeholder routes (including `/book-demo`, auth, placeholders) remain absent from sitemap per manifest + validator.

### 7.1 Route audit table (built product intent)

| route | linked from public indexable | in_sitemap | blocked_by_robots | has_meta_noindex | has_x_robots_noindex | crawlable (Googlebot-class) | index_exclusion_strategy | risk_status |
|-------|------------------------------|------------|-------------------|------------------|----------------------|-----------------------------|---------------------------|-------------|
| `/implementations/agent-a/` … `agent-e/` | No (not in export) | No | No | N/A | No | N/A | Removed from public output | Low (historical external links possible) |
| `/book-demo` | Yes | No | No | Yes | Not asserted | Yes | Meta noindex + follow | Controlled |
| `/book-demo/thank-you` | Indirect | No | No | Yes | Not asserted | Yes | Meta noindex + nofollow (layout) | Low |
| `/Login`, `/signup` | Yes | No | No | Yes | Not asserted | Yes | Meta noindex | Low |
| `/privacy`, `/terms`, `/gdpr`, `/security`, `/docs`, `/api`, `/trust-envelope`, `/status`, `/about`, `/careers`, `/press` | Mixed | No | No | Yes | Not asserted | Yes | Meta noindex placeholders | Medium (content depth outside D2 crawl-law) |

---

## 8. Harness Proof

### 8.1 `npm run discoverability:d2`

- **Expected result:** PASS (full `npm run build` + checks).
- **Sections:** `[3b]` meta-noindex routes not blocked by parsed `Disallow`; `[6]` Login/signup/thank-you noindex, no `out/implementations/`, defective `/book-demo` noindex; `[9]` `/book-demo` not in sitemap.

### 8.2 `npm run discoverability:d2:negative-controls`

- **Expected result:** PASS.
- **NC-D2-X1:** noindex route blocked by robots → errors detected.  
- **NC-D2-X2:** `Disallow: /implementations/` in robots → `validateRobotsPolicy` fails.  
- **NC-D2-X3:** defective `/book-demo` HTML without noindex → fails.  
- **NC-D2-X4:** `Disallow: /book-demo` → `validateRobotsPolicy` fails.  
- **NC-D2-X5:** sitemap includes `https://skeldir.com/book-demo` → `validateSitemapMatchesExpected` fails.  
- **NC-D2-X6:** temp shipped `implementations/agent-a/index.html` without noindex → `validateShippedImplementationAgentsHaveNoindex` fails.

---

## 9. Production / Deploy-Preview Proof

| Item | Status |
|------|--------|
| Post-deploy origin | **Attach** `curl.exe -I` / `curl.exe -L` transcripts for `https://skeldir.com/robots.txt`, `sitemap.xml`, `/book-demo`, `/Login`, `/signup`, `/book-demo/thank-you`, and `/implementations/agent-a/` (expect removal 404 or redirect). |
| This document | Does not substitute for live curl after the D2-C commit is deployed. |

**Statements**

- **D2 local proof state:** PASS (when harness commands are run successfully on a clean tree).
- **D2 production proof state:** NOT VERIFIED IN THIS FILE — attach after deploy.
- **D3 production-gated work:** Blocked until deploy proof is attached if program requires it.

---

## 10. Git / CI Proof

| Field | Value |
|-------|--------|
| Canonical remote | `origin` → `https://github.com/Synergyscape-V1/skeldir-2.0.git` |
| Primary branch (GitHub default) | `main` |
| Feature branch | `feat/discoverability-remediation` |
| Corrective commits | `3234b54`, `bed9656` |
| Push status | Branch tracks `origin/feat/discoverability-remediation` at time of report authorship |
| CI status | **Attach** `gh run list` / PR checks after CI runs |
| Merge gate | Open PR to `main` (or org integration branch), green checks, merge per policy |

---

## 11. Remaining Unknowns

- Live production responses after CDN/host deploy for `robots.txt`, `sitemap.xml`, and HTML routes.
- Search index cleanup for any legacy `/implementations/*` URLs.
- Confirm no unintended unstaged edits (e.g. `marketing/src/app/signup/page.tsx`) before merge.

---

## 12. D3 Readiness

- **From crawl-control and test harness perspective:** D3 may proceed in repo development terms.
- **From production + merge-gate perspective:** Attach deploy curl proof and CI green on the required integration branch before calling the **release** portion of D2 “closed.”

---

## Appendix A — Executive summary (findings → remediations)

| Initial finding | Remediation |
|-----------------|-------------|
| `/implementations/*`: combined `Disallow` + HTML `noindex` “proof” | Removed `public/implementations/**`; removed robots disallow for that path; harness requires absent `out/implementations/`; NCs for disallow and shipped-without-noindex. |
| `/book-demo`: sitemap-only containment while linked and defective | `noindex` + `follow` in `book-demo/layout.tsx`; no robots disallow; `validateBookDemoDefectiveRequiresNoindex`; NCs for missing noindex, disallow, and sitemap pollution. |
| Harness passed contradictory mechanics | Added `[3b]`, rewrote `[6]`, added NC-D2-X1–X6. |
| Scripts assumed `public/implementations` | Validation script skips when mount absent (`bed9656`). |

---

## Appendix B — Verification commands

```bash
cd marketing
npm run discoverability:d2
npm run discoverability:d2:negative-controls
```

Post-deploy (example):

```bash
curl.exe -I https://skeldir.com/sitemap.xml
curl.exe -L https://skeldir.com/sitemap.xml
curl.exe -I https://skeldir.com/robots.txt
curl.exe -L https://skeldir.com/robots.txt
curl.exe -L https://skeldir.com/book-demo
curl.exe -L https://skeldir.com/implementations/agent-a/
```

---

*End of report.*
