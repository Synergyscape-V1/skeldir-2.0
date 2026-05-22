# Phase D2 Completion Report — Crawl Graph and Index Control

## 1. Verdict

**PASS** for Phase D2 scope (local build + harness evidence). Production deployment was not re-verified in this session.

## 2. Scope Confirmation

This report covers **Phase D2 only** (sitemap, robots, canonical alignment, noindex boundaries, internal link hygiene, review-artifact governance, D2 harness + negative controls, canonical Git root). **No** completion is claimed for D3 bot-policy expansion beyond minimal `robots.txt`, D4 schema programs, D5 trust copy, D6 evidence library, D8 analytics, D9 `llms.txt`, or backend Trust API work.

## 3. Git / Branch Governance

| Item | Value |
|------|--------|
| Canonical repo root | `c:\Users\ayewhy\Skeldir Webpage` |
| Remote | Not added in-repo by default; registry metadata references `https://github.com/Muk223/skeldir-2.0.git` |
| Primary branch (initial) | `feat/discoverability-remediation` (repo created with `-b`; no `main`/`master` commits in this root) |
| Feature branch | `feat/discoverability-remediation` |
| D0 commit | *Not isolated*: prior D0/D1 work had no Git root under `Skeldir Webpage`; see note below |
| D1 commit | *Same note* |
| D1 corrective commit | *Same note* |
| D2 commit | Single integration commit records D2 + registry fixes + repo scaffolding |
| Main untouched | **Yes** — no `main`/`master` branch created in this new root |
| D10 merge gate | Remains future integration; this branch is the merge candidate |

**Note on atomic D0/D1/D2 commits:** A parent `.git` at `C:\Users\ayewhy` caused Git to treat the user profile as the repository root. A new canonical `.git` was created under `Skeldir Webpage` (see `REPO_AUTHORITY_RESOLUTION.md`). Historically interleaved D0/D1 source could not be split into four clean commits without rewriting history that never existed at this root; governance is satisfied by **feature-branch-only** commits going forward.

## 4. Files Changed (summary)

| Area | Files | Reason |
|------|--------|--------|
| Sitemap | `discoverability.sitemap-manifest.json`, `src/app/sitemap.ts` | Deterministic eligible URL set + Next sitemap route |
| Robots | `src/app/robots.ts` | Root `robots.txt`, sitemap line, public crawl, `/implementations/` disallow, explicit retrieval UA allows |
| Canonicals | `src/lib/siteCrawl.ts`, `src/app/page.tsx`, `src/app/pricing/page.tsx`, `src/app/agencies/page.tsx`, `src/app/product/layout.tsx`, `src/app/book-demo/layout.tsx` | One self-referential canonical per indexable commercial URL |
| Noindex | `Login/page.tsx`, `signup/page.tsx`, `book-demo/thank-you/layout.tsx`, `not-found.tsx`, placeholder routes under `src/app/{privacy,terms,gdpr,security,status,about,careers,press,docs,api,trust-envelope}/` | Pollution boundary for auth, transactional success, 404, and legal/docs placeholders |
| Footer | `src/components/layout/Footer.tsx` | Truthful internal link graph (no legal/docs/API → `/resources`) |
| Review artifacts | `public/implementations/agent-*/index.html` | `noindex,nofollow` meta |
| Registry | `discoverability.routes.json` | Phase bump; `route-terms` + `route-gdpr` for D0 parity |
| Harness | `scripts/discoverability/lib/d2-crawl-graph.mjs`, `discoverability-d2-harness.mjs`, `discoverability-d2-negative-controls.mjs`, `package.json` | `npm run discoverability:d2` + negative controls |
| Repo | `c:\Users\ayewhy\Skeldir Webpage\.gitignore`, `REPO_AUTHORITY_RESOLUTION.md` | Canonical repo hygiene |

## 5. Route Classification Inputs

- **D0 registry:** `discoverability.routes.json` (v2.0.0, phase `D2-corrective`)
- **D1 article slug source:** `src/data/articlesData.ts` (also parsed by harness without executing TS)
- **Included in sitemap:** `/`, `/product`, `/pricing`, `/agencies`, `/resources`, all `/resources/{slug}` from `articlesData`
- **Excluded:** auth, transactional success, placeholders, `/book-demo`, review artifacts, `missing_required` surfaces not promoted to indexable
- **Missing-required handling:** Still tracked as obligations in registry where applicable; **not** linked as live indexable pages from the footer; placeholders are **noindex** and **not** in the sitemap
- **`/book-demo` status:** Remains **contained** (registry `sitemap_required=false`, not listed in sitemap); static body still primarily client-driven — repair remains a later phase if promoted

## 6. Sitemap Evidence

- **Generation:** Next.js App Router `src/app/sitemap.ts` (static export → `out/sitemap.xml`)
- **Manifest:** `discoverability.sitemap-manifest.json` lists static paths; articles merged from `articlesData`
- **XML:** Parsed by D2 harness; requires sitemap 0.9 xmlns, `<loc>` entries, `<lastmod>` per URL
- **lastmod:** Hub pages use manifest `hubLastmod` (UTC noon); articles use `publishDate` from `articlesData`
- **Local proof:** `npm run discoverability:d2` (rebuild + file reads)
- **Production:** Not re-curled in this session after changes

## 7. Robots Evidence

- **Generation:** `src/app/robots.ts` → `out/robots.txt`
- **Sitemap line:** `Sitemap: https://skeldir.com/sitemap.xml`
- **Retrieval bots:** Explicit `Allow: /` rows for common retrieval user agents (see `robots.ts`); broad training-crawler policy remains **D3**
- **Sensitive-path leak check:** Harness rejects bodies containing `node_modules`, `.git`, `.env`, etc.

## 8. Canonical Evidence

Harness verifies **exactly one** `<link rel="canonical">` per sitemap URL in the mapped `out/*.html` file, normalized to match the sitemap loc (origin + path).

## 9. Noindex / Pollution Boundary

| Route | Sitemap | Proof |
|-------|---------|--------|
| `/Login`, `/signup` | Excluded | `robots` metadata `noindex` on pages |
| `/book-demo/thank-you` | Excluded | `book-demo/thank-you/layout.tsx` noindex |
| `/404` (not-found) | Excluded | `not-found.tsx` noindex |
| `/implementations/*` | Excluded | HTML `<meta name="robots">` + `Disallow: /implementations/` in `robots.txt` |
| Placeholder legal/docs | Excluded | Each placeholder exports `robots: { index: false, follow: false }` |

## 10. Internal Link Graph Evidence

- **Footer legal:** Privacy → `/privacy`; Terms → `/terms`; GDPR → `/gdpr`; Security → `/security`
- **Support / company:** Documentation → `/docs`; API Reference → `/api`; Status → `/status`; About → `/about`; Careers → `/careers`; Press → `/press`; “Insights” → `/resources` (truthful hub label for article content)
- **Book-demo:** Existing `/privacy` href now resolves to a real **noindex** placeholder route (not a 404)

Harness checks built `out/index.html` for the old anti-pattern (`Privacy Policy` / `API Reference` / `Documentation` pointing at `/resources`).

## 11. Harness Proof

Commands:

```bash
npm run discoverability:d2
npm run discoverability:d2:negative-controls
npm run discoverability:d0
npm run discoverability:d1
```

- **D2 main:** PASS (22 checks in last successful run)
- **D2 negative controls:** PASS (detects malformed XML, sitemap drift, bad robots, footer `/resources` regression, etc.)
- **D0 / D1:** PASS after adding `route-terms` and `route-gdpr` to the registry

## 12. Remaining Unknowns

- Live `https://skeldir.com` was not re-fetched after local changes (Netlify deploy out of scope here).
- Whether `skeldir-2.0` GitHub default branch is `main` vs `master` was not validated against this new local root.

## 13. Commit / Push Status

- **Branch:** `feat/discoverability-remediation` (initial branch at new root)
- **Commits:** See `git log` after agent commit (single integration commit expected)
- **Pushed:** **No** (no `git push` performed)

## 14. D3 Readiness Statement

**D3 may begin** after merge/deploy planning. D3 should expand deliberate **bot-class** policy (including training/bulk crawlers) beyond the minimal explicit allows in `robots.ts`, add any production header strategy if required, and reconcile live crawl logs with the registry.
