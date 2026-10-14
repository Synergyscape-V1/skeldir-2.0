# Phase D0 Completion Report — App-Router-Aware Evidence Freeze and Public Surface Authority

**Date:** 2026-05-21  
**Authoritative codebase:** `marketing/`  
**Audit baseline:** `Skeldir_Webpage_Discoverability_Audit_Report.md`

---

## 1. Verdict

**FAIL** — Gate D0.7 (commit and push proof) is **not met**.

All D0 implementation artifacts, parity harness, and negative controls are complete and passing. Commit and push were **explicitly deferred** per user instruction: *"don't commit anything just yet so we can audit what you completed."*

Additionally, the local git topology is misconfigured (git root at `C:/Users/ayewhy` with zero commits on `master`), which must be resolved before a meaningful D0.7 gate pass.

**Sub-gate status:**


| Gate                                              | Status              |
| ------------------------------------------------- | ------------------- |
| D0.1 — Active source/deployment authority         | PASS                |
| D0.2 — App-Router-aware route resolution          | PASS                |
| D0.3 — Deprecated/review artifact classification  | PASS                |
| D0.4–D0.6 — Registry, inventory, physical surface | PASS                |
| D0.7 — Commit and push proof                      | **FAIL (deferred)** |
| D0.8 — Negative controls + clean harness          | PASS                |


---

## 2. Primary Branch and Commit

- **Current branch:** `master`
- **Remote HEAD:** `origin → https://github.com/Muk223/skeldir-2.0.git` (no commits on local branch; remote HEAD not resolvable locally)
- **Primary branch (recorded):** `master`
- **Commit hash:** *none — uncommitted working tree*
- **Push status:** **Not committed, not pushed** (deferred for user audit)

**Git topology warning:** Running `git status` from `marketing/` resolves to git root `C:/Users/ayewhy` (user home directory). This repo has no commits and lists unrelated home-directory paths as untracked. Production-deployed clone with proper scope: `skeldir-production-main-deploy-20260518/` on branch `codex/marketing-production-missing-lib` (remote: `Synergyscape-V1/skeldir-2.0.git`, commit `43921ca6`).

---

## 3. Artifacts Added or Modified


| Artifact                                             | Purpose                                  | Status   |
| ---------------------------------------------------- | ---------------------------------------- | -------- |
| `discoverability.routes.json`                        | Machine-readable route registry (v1.0.0) | Added    |
| `DISCOVERABILITY_ROUTE_REGISTRY.md`                  | Human-readable registry companion        | Added    |
| `DISCOVERABILITY_EVIDENCE_FREEZE.md`                 | Evidence freeze baseline                 | Added    |
| `DISCOVERABILITY_PHYSICAL_SURFACE_REPORT.md`         | Physical surface governance              | Added    |
| `scripts/discoverability-d0-inventory.mjs`           | App-Router-aware route inventory         | Added    |
| `scripts/discoverability-d0-harness.mjs`             | D0 parity harness (11 check groups)      | Added    |
| `scripts/discoverability-d0-negative-controls.mjs`   | Negative-control proof script            | Added    |
| `scripts/discoverability/lib/app-router-resolve.mjs` | Route normalization library              | Added    |
| `scripts/discoverability/lib/registry-schema.mjs`    | Registry field validation helpers        | Added    |
| `package.json`                                       | Wired `discoverability:d0`* npm scripts  | Modified |
| `Phase D0 Completion Report.md`                      | This report                              | Added    |


**Not modified (D1+ scope):** Article SSR, sitemap, robots.txt, canonical tags, JSON-LD, llms.txt, footer legal links, ArticleCard `<a href>` fixes.

---

## 4. Active Surface Evidence

- **Active source directory:** `marketing/`
- **Framework/version:** Next.js 16.1.1, React 19.2.3, Tailwind CSS v4
- **Rendering/export mode:** Static export (`output: 'export'` in `next.config.ts`)
- **Deployment target:** Netlify (`base=marketing`, `command=npm run build`, `publish=out`)
- **Publish directory:** `marketing/out/`
- **Public/static directory:** `marketing/public/`
- **Stale/non-authoritative directories:**
  - `skeldir-deploy-clean/`
  - `skeldir-favicon-clean/`
  - `skeldir-netlify-fix-20260430/`
  - `skeldir-2.0-clone/`
  - `skeldir-production-main-deploy-20260518/` (production clone; not the active dev tree)

---

## 5. App Router Route Semantics Handling

- **Route groups handled:** Yes — `(groupName)` segments excluded from URLs. Proof: harness check 11 + negative control NC-3. Current codebase has **zero** route groups.
- **Parallel routes handled:** Yes — `@slot` segments excluded from URLs. Proof: harness check 11 + negative control NC-4. Current codebase has **zero** parallel slots.
- **Intercepting routes handled:** Yes — `(.)`, `(..)`, `(...)` recognized and excluded; none present in codebase. Marked `unknown_requires_resolution` if encountered without build cross-check.
- **Dynamic routes handled:** Yes — `/resources/[slug]` registered as pattern; 4 concrete slugs expanded via `generateStaticParams()` and cross-checked against `out/resources/*.html`.
- **Static export output cross-check:** Yes — harness check 3 validates every `out/**/*.html` against registry (19 HTML files classified).
- **Unknown route semantics:** None unresolved for current codebase structure.

---

## 6. Route Registry Summary


| Route                                                       | Source Path                                 | Resolved URL                                                | Physical Surface     | Indexability     | Owner          | Sitemap | Noindex | JSON-LD | Status           |
| ----------------------------------------------------------- | ------------------------------------------- | ----------------------------------------------------------- | -------------------- | ---------------- | -------------- | ------- | ------- | ------- | ---------------- |
| `/`                                                         | `src/app/page.tsx`                          | `/`                                                         | marketing_static     | indexable        | frontend       | yes     | no      | yes     | active           |
| `/product`                                                  | `src/app/product/page.tsx`                  | `/product`                                                  | marketing_static     | indexable        | frontend       | yes     | no      | yes     | active           |
| `/pricing`                                                  | `src/app/pricing/page.tsx`                  | `/pricing`                                                  | marketing_static     | indexable        | growth         | yes     | no      | yes     | active           |
| `/agencies`                                                 | `src/app/agencies/page.tsx`                 | `/agencies`                                                 | marketing_static     | indexable        | growth         | yes     | no      | yes     | active           |
| `/resources`                                                | `src/app/resources/page.tsx`                | `/resources`                                                | marketing_static     | indexable        | content        | yes     | no      | yes     | active           |
| `/resources/why-your-attribution-numbers-never-match`       | `src/app/resources/[slug]/page.tsx`         | `/resources/why-your-attribution-numbers-never-match`       | marketing_static     | indexable        | content        | yes     | no      | yes     | active_defective |
| `/resources/roas-is-not-a-number-its-a-range`               | `src/app/resources/[slug]/page.tsx`         | `/resources/roas-is-not-a-number-its-a-range`               | marketing_static     | indexable        | content        | yes     | no      | yes     | active_defective |
| `/resources/attribution-methods-answer-different-questions` | `src/app/resources/[slug]/page.tsx`         | `/resources/attribution-methods-answer-different-questions` | marketing_static     | indexable        | content        | yes     | no      | yes     | active_defective |
| `/resources/confidently-defend-budget-shift`                | `src/app/resources/[slug]/page.tsx`         | `/resources/confidently-defend-budget-shift`                | marketing_static     | indexable        | content        | yes     | no      | yes     | active_defective |
| `/book-demo`                                                | `src/app/book-demo/page.tsx`                | `/book-demo`                                                | transactional_static | indexable*       | growth         | yes     | no      | no      | active           |
| `/book-demo/thank-you`                                      | `src/app/book-demo/thank-you/page.tsx`      | `/book-demo/thank-you`                                      | transactional_static | nonindex         | growth         | no      | yes     | no      | active           |
| `/Login`                                                    | `src/app/Login/page.tsx`                    | `/Login`                                                    | auth_static          | nonindex         | frontend       | no      | yes     | no      | active           |
| `/signup`                                                   | `src/app/signup/page.tsx`                   | `/signup`                                                   | auth_static          | nonindex         | frontend       | no      | yes     | no      | active           |
| `/implementations/agent-a`                                  | `public/implementations/agent-a/index.html` | `/implementations/agent-a`                                  | review_public_static | nonindex         | frontend       | no      | yes     | no      | active           |
| `/implementations/agent-b`                                  | `public/implementations/agent-b/index.html` | `/implementations/agent-b`                                  | review_public_static | nonindex         | frontend       | no      | yes     | no      | active           |
| `/implementations/agent-c`                                  | `public/implementations/agent-c/index.html` | `/implementations/agent-c`                                  | review_public_static | nonindex         | frontend       | no      | yes     | no      | active           |
| `/implementations/agent-d`                                  | `public/implementations/agent-d/index.html` | `/implementations/agent-d`                                  | review_public_static | nonindex         | frontend       | no      | yes     | no      | active           |
| `/implementations/agent-e`                                  | `public/implementations/agent-e/index.html` | `/implementations/agent-e`                                  | review_public_static | nonindex         | frontend       | no      | yes     | no      | active           |
| `/404`                                                      | `out/404.html`                              | `/404`                                                      | marketing_static     | nonindex         | frontend       | no      | yes     | no      | active           |
| `/privacy`                                                  | *missing*                                   | `/privacy`                                                  | missing_required     | missing_required | legal          | planned | planned | planned | missing_required |
| `/security`                                                 | *missing*                                   | `/security`                                                 | missing_required     | missing_required | legal          | planned | planned | planned | missing_required |
| `/status`                                                   | *missing*                                   | `/status`                                                   | missing_required     | missing_required | infrastructure | planned | planned | no      | missing_required |
| `/about`                                                    | *missing*                                   | `/about`                                                    | missing_required     | missing_required | growth         | planned | planned | yes     | missing_required |
| `/careers`                                                  | *missing*                                   | `/careers`                                                  | missing_required     | missing_required | growth         | planned | planned | no      | missing_required |
| `/blog`                                                     | *missing*                                   | `/blog`                                                     | missing_required     | missing_required | content        | planned | planned | yes     | missing_required |
| `/press`                                                    | *missing*                                   | `/press`                                                    | missing_required     | missing_required | growth         | planned | planned | no      | missing_required |
| `/docs`                                                     | *missing*                                   | `/docs`                                                     | missing_required     | missing_required | content        | planned | planned | yes     | missing_required |
| `/api`                                                      | *missing*                                   | `/api`                                                      | missing_required     | missing_required | content        | planned | planned | yes     | missing_required |
| `/trust-envelope`                                           | *missing*                                   | `/trust-envelope`                                           | missing_required     | missing_required | content        | planned | planned | yes     | missing_required |


 `/book-demo` is classified **indexable** by explicit business decision (lead-gen landing page). Thank-you, auth, and review artifacts are **nonindex** with `noindex_required=true` obligations recorded for D2 implementation.

---

## 7. Physical Surface Governance

- **Marketing static routes:** `/`, `/product`, `/pricing`, `/agencies`, `/resources`, 4 article slugs
- **Transactional static routes:** `/book-demo`, `/book-demo/thank-you`
- **Auth/static routes:** `/Login`, `/signup`
- **Review/public static artifacts:** `/implementations/agent-a` through `/implementations/agent-e` (standalone HTML in `public/`, not Next.js pages)
- **Shared layouts/providers discovered:**
  - Single root layout (`src/app/layout.tsx`) — Server Component with `<NavigationWrapper />` on all routes
  - Nested layouts: `resources/layout.tsx`, `resources/[slug]/layout.tsx`
  - No shared React context providers in root layout
- **Shared chunks or bundle-coupling evidence:** Inconclusive without detailed chunk-map analysis. All Next.js routes share `_next/static/chunks` from single static export. `bundle_isolation_required: defer_to_later_phase` recorded for auth/transactional routes.
- **Physical split required now:** No
- **Physical split recommended later:** Yes — route groups `(marketing)`, `(transactional)`, `(auth)` recommended before authenticated app surfaces ship
- **Inconclusive items:** Detailed per-route chunk coupling; production Netlify WAF/bot rules; `www.skeldir.com` alias behavior

---

## 8. Hypothesis Results


| Hypothesis                                                  | Validated / Refuted / Expanded            | Evidence                                                                                                     |
| ----------------------------------------------------------- | ----------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| H-D0-01 — Stale clone authority risk                        | **Validated**                             | Multiple clone directories exist; evidence freeze records authoritative `marketing/` vs stale clones         |
| H-D0-02 — No route registry exists                          | **Refuted**                               | `discoverability.routes.json` + markdown companion now exist with 29 route entries                           |
| H-D0-03 — App Router routes mis-mapped by naive FS scan     | **Validated (risk confirmed, mitigated)** | No route groups/slots in codebase today; normalization library + harness prove correct handling              |
| H-D0-04 — Review artifacts ungoverned                       | **Validated (pre-D0)**                    | 5 `/implementations/agent-`* artifacts registered as `review_artifact`, `nonindex`, `noindex_required=true`  |
| H-D0-05 — Missing-but-linked routes untracked               | **Validated (pre-D0)**                    | 10 missing routes (`/privacy`, `/security`, etc.) registered as `missing_required`                           |
| H-D0-06 — Auth/transactional routes lack noindex obligation | **Validated (pre-D0)**                    | `/Login`, `/signup`, thank-you, implementations have `noindex_required=true`; production lacks tags (D2 fix) |
| H-D0-07 — No automated D0 validation                        | **Refuted**                               | Inventory, harness, negative-controls scripts + npm commands added                                           |
| H-D0-08 — Registry parity decays silently                   | **Mitigated**                             | Harness fails on unregistered source/build/public routes (proven by NC-1, NC-2)                              |
| H-D0-09 — Marketing/auth/transactional co-located           | **Validated**                             | Single root layout; physical surface metadata recorded per route                                             |
| H-D0-10 — No route-group physical intent                    | **Validated**                             | No `(marketing)`/`(auth)` groups; future split recommended, not performed                                    |
| H-D0-11 — Branch/deployment authority ambiguous             | **Validated**                             | Two GitHub orgs, misconfigured local git root, production clone on different remote                          |
| H-D0-12 — Route ownership absent                            | **Refuted**                               | Every registry entry has `owner` field (frontend, content, growth, legal, infrastructure)                    |


---

## 9. Harness Proof

- **Command:** `npm run discoverability:d0`
- **Final pass output:**

```
✅ D0 PARITY HARNESS: PASS (77 checks passed, 0 failures)
```

Check groups passed: registry exists, source route parity (10), build output parity (19), public static HTML parity (5), missing-linked routes (10), indexable field completeness (10), nonindex obligations (9), App Router ambiguity (2), review artifact governance (5), physical surface metadata (4), route group normalization proof (2).

- **Negative-control failures (expected violations detected):**
  - **unregistered source route:** `/__d0-negative-test__` → not in registry → FAIL detected ✓
  - **unregistered static artifact:** `/implementations/__fixture__` → not in registry → FAIL detected ✓
  - **route group normalization:** `(marketing)/pricing/page.tsx` → `/pricing` (not `/(marketing)/pricing`) ✓
  - **parallel slot normalization:** `@modal/page.tsx` → `/`; `@analytics` excluded ✓
  - **missing physical_surface:** `physical_surface: null` on indexable route → validation errors ✓
  - **missing noindex_required:** `/Login` and `/book-demo/thank-you` with `noindex_required: false` → validation errors ✓
  - **missing canonical_url:** indexable route with null canonical → validation errors ✓
  - **clean-state confirmation:** production harness re-run → PASS ✓

**Negative controls command:** `npm run discoverability:d0:negative-controls` → **PASS (11 checks)**

---

## 10. Remaining Unknowns


| Unknown                                                 | Owner          | Resolution Required By |
| ------------------------------------------------------- | -------------- | ---------------------- |
| Correct git repo scope for `marketing/` commits         | Infrastructure | Before D0.7 retry      |
| Which GitHub org/branch Netlify production deploys from | Infrastructure | Before D0.7 retry      |
| Production Netlify WAF/bot rules                        | Infrastructure | Before D3              |
| `www.skeldir.com` separate surface                      | Infrastructure | Before D2              |
| Google Search Console / Bing index coverage             | Growth         | Before D8              |
| Per-route chunk sharing analysis                        | Frontend       | Defer to later phase   |
| Cal.com booking UTM forwarding                          | Growth         | Before D8              |


---

## 11. D1 Readiness Statement

**D1 can begin** once Gate D0.7 is satisfied (artifacts committed and pushed to the empirically verified primary branch in a properly scoped git repository).

The route authority control plane is in place:

- Every source route, build artifact, and public static HTML is classified
- Missing-but-linked routes are tracked with owners
- Auth, transactional, and review surfaces have explicit noindex obligations for D2
- Article routes are flagged `active_defective` with CSR root cause documented
- Parity harness will catch registry drift

**D1 first action:** Convert `/resources/[slug]` from client-only slug resolution to static/server rendering so article body appears in exported HTML (Gate D1.1–D1.4). Do not start until user approves post-D0 audit and commit.

---

## Audit Checklist for User Review

Before committing, verify:

1. `discoverability.routes.json` — 29 routes, `/book-demo` indexability decision acceptable
2. `npm run discoverability:d0` — exits 0
3. `npm run discoverability:d0:negative-controls` — exits 0
4. `npm run discoverability:d0:inventory` — lists 10 source routes, 5 public HTML, 19 build outputs
5. No D1 remediation code changes mixed into this diff
6. Git repo scope fixed before commit (recommend initializing git in `Skeldir Webpage/marketing/` or workspace root, not user home)

