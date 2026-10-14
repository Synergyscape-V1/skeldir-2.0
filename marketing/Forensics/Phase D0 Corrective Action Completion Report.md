# Phase D0 Corrective Action Completion Report

**Date:** 2026-05-21  
**Scope:** Discoverability D0 — Evidence Freeze and Public Surface Authority  
**Registry version:** 2.0.0  
**Commit/push:** Deferred to D10 (per user instruction)

---

## 1. Verdict

**PASS** — All corrective D0 gates (C-D0.1 through C-D0.7) are met on local proof state. D10 commit/push remains deferred; git scope is documented and D1 worktree is identified.

---

## 2. Scope Confirmation

This work is **Skeldir Discoverability D0** only. No backend provider enablement, `aisuite`, budget breakers, LLM provider routing, cache, or distillation capture was touched.

---

## 3. Repo Scope Resolution

- **working directory:** `C:\Users\ayewhy\Skeldir Webpage\marketing`
- **git root:** `C:/Users/ayewhy` (mis-scoped — encompasses user home; no commits on `master`)
- **current branch:** `master` (zero commits)
- **remote:** `origin → https://github.com/Muk223/skeldir-2.0.git`
- **production deploy source:** Netlify `base=marketing`, `publish=out` (from `skeldir-production-main-deploy-20260518/netlify.toml`); production clone on `Synergyscape-V1/skeldir-2.0.git`, branch `codex/marketing-production-missing-lib`, commit `43921ca6`
- **authoritative D1 worktree:** `C:\Users\ayewhy\Skeldir Webpage\marketing\` — D0 artifacts exist here; D1 must modify this tree
- **unresolved repo/deploy unknowns:** Which GitHub org Netlify production deploys from; correct git re-scope before D10; remote HEAD unset locally

Full evidence: `D0_REPO_SCOPE_RESOLUTION.md`

---

## 4. Artifacts Provided


| File                                                   | Status                                         |
| ------------------------------------------------------ | ---------------------------------------------- |
| `discoverability.routes.json`                          | Updated v2.0.0                                 |
| `DISCOVERABILITY_ROUTE_REGISTRY.md`                    | Updated                                        |
| `DISCOVERABILITY_EVIDENCE_FREEZE.md`                   | Existing baseline (see repo scope addendum)    |
| `DISCOVERABILITY_PHYSICAL_SURFACE_REPORT.md`           | Corrected risk language                        |
| `D0_REPO_SCOPE_RESOLUTION.md`                          | **New**                                        |
| `scripts/discoverability-d0-inventory.mjs`             | Updated — route truth hierarchy output         |
| `scripts/discoverability-d0-harness.mjs`               | Rewritten — v2 corrective checks               |
| `scripts/discoverability-d0-negative-controls.mjs`     | Rewritten — 15 negative controls               |
| `scripts/discoverability/lib/app-router-resolve.mjs`   | Unchanged — advisory only                      |
| `scripts/discoverability/lib/registry-schema.mjs`      | Rewritten — required/implemented validation    |
| `scripts/discoverability/lib/route-truth.mjs`          | **New**                                        |
| `scripts/discoverability/lib/content-slugs.mjs`        | **New**                                        |
| `scripts/discoverability/lib/import-boundary-scan.mjs` | **New**                                        |
| `scripts/discoverability/migrate-registry-to-v2.mjs`   | **New** — one-shot migration (already applied) |
| `package.json`                                         | `discoverability:d0`* scripts wired            |
| `Phase D0 Corrective Action Completion Report.md`      | This report                                    |


---

## 5. Corrected Registry Semantics

### `/api` (static docs)

```json
{
  "id": "route-api-docs",
  "logical_route": "/api",
  "route_type": "api_docs",
  "physical_surface": "docs_static",
  "runtime_api": false,
  "static_export_compatible": true,
  "status": "missing_required",
  "sitemap_required": true,
  "sitemap_implemented": false
}
```

### Trust API runtime (external infrastructure)

```json
{
  "id": "infra-trust-api-runtime",
  "route_type": "runtime_api_external",
  "physical_surface": "external_backend",
  "runtime_api": true,
  "static_export_compatible": false,
  "must_not_be_implemented_under": "marketing/src/app/api",
  "target_backend": "backend/app/trust/api.py",
  "routing_requirement": "reverse_proxy_or_separate_api_domain"
}
```

### `/trust-envelope`

```json
{
  "logical_route": "/trust-envelope",
  "route_type": "missing_required",
  "physical_surface": "docs_static",
  "static_export_compatible": true,
  "runtime_api": false,
  "jsonld_required": true,
  "jsonld_implemented": false
}
```

### `/book-demo`

```json
{
  "indexability_class": "indexable_candidate",
  "status": "active_defective_until_static_body_verified",
  "sitemap_required": false,
  "sitemap_implemented": false,
  "canonical_required": true,
  "canonical_implemented": false,
  "legal_link_required": true,
  "legal_link_implemented": false,
  "approval_required": "growth/legal"
}
```

### `/resources/[slug]` (pattern)

```json
{
  "id": "route-article-pattern",
  "route_type": "article_pattern",
  "source_of_truth": "src/data/articlesData.ts + generateStaticParams",
  "generated_instances_policy": "auto_discovered"
}
```

### Concrete article slug example

```json
{
  "id": "route-article-generated-why-your-attribution-numbers-never-match",
  "logical_route": "/resources/why-your-attribution-numbers-never-match",
  "route_type": "article",
  "generated_from": "/resources/[slug]",
  "content_id": "why-your-attribution-numbers-never-match",
  "status": "active_defective",
  "sitemap_required": true,
  "sitemap_implemented": false
}
```

---

## 6. Physical Surface Correction

- **previous claim:** "Physical split required now: No"
- **corrected claim:** "Physical split required during D0: **not established**. Current condition: shared static export and shared `_next/static/chunks`. Risk level: **structural isolation risk, not yet proven breach**."
- **isolation status per route class:**


| Route class            | Isolation status |
| ---------------------- | ---------------- |
| `marketing_static`     | `inconclusive`   |
| `auth_static`          | `risk`           |
| `transactional_static` | `inconclusive`   |
| `review_public_static` | `safe`           |


- **evidence:** Import boundary scan of `src/app/**/page.tsx`; no backend/token/dashboard-provider imports in marketing_static pages; auth pages import `@/components/auth/`*
- **deferred split trigger:** Before authenticated dashboard, Trust API runtime, or tenant-aware app surfaces ship

---

## 7. Route Truth Hierarchy


| Priority | Source                                     | Role                                                                                |
| -------- | ------------------------------------------ | ----------------------------------------------------------------------------------- |
| 1        | `marketing/out/**/*.html`                  | Deployed static export truth — harness check [9]                                    |
| 2        | Next build artifacts                       | Compiler-derived (when available)                                                   |
| 3        | `articlesData.ts` + `generateStaticParams` | Generated article instance source — harness check [7]                               |
| 4        | Source route scan                          | Intent evidence — harness check [4]                                                 |
| 5        | `app-router-resolve.mjs`                   | **Advisory normalization only** — registry sets `resolver_authority: advisory_only` |


Inventory output (`npm run discoverability:d0:inventory`) separates `source_intent_routes`, `generated_content_instances`, `exported_out_routes`, `registry_routes`, and `unknown_or_ambiguous_routes`.

---

## 8. Harness and Negative Controls

- **commands:**
  ```bash
  npm run discoverability:d0
  npm run discoverability:d0:negative-controls
  npm run discoverability:d0:inventory
  ```
- **clean pass:**
  ```
  ✅ D0 PARITY HARNESS: PASS (89 checks passed, 0 warnings, 0 failures)
  ✅ D0 NEGATIVE CONTROLS: PASS (15 checks passed, 0 failures)
  ```
- **negative controls and failure proof:**


| Control    | Violation simulated                            | Result                   |
| ---------- | ---------------------------------------------- | ------------------------ |
| NC-1       | Unregistered source route                      | FAIL detected            |
| NC-2       | Unregistered static artifact                   | FAIL detected            |
| NC-5       | Missing `sitemap_implemented`                  | FAIL detected            |
| NC-8       | `marketing/src/app/api/`** under static export | FAIL detected            |
| NC-9/10/11 | New/removed/renamed article slug               | Actionable FAIL messages |
| NC-12      | `/book-demo` clean indexable                   | FAIL detected            |
| NC-15      | Clean production state                         | PASS                     |


---

## 9. Remaining Unknowns


| Unknown                                | Owner          | Required By               |
| -------------------------------------- | -------------- | ------------------------- |
| Netlify production GitHub org/branch   | Infrastructure | D10                       |
| Git re-scope (home directory git root) | Infrastructure | D10                       |
| Per-route webpack chunk coupling       | Frontend       | Before auth/app expansion |
| `www.skeldir.com` alias behavior       | Infrastructure | D2                        |
| Production Netlify WAF/bot rules       | Infrastructure | D3                        |


---

## 10. D1 Readiness Statement

**D1 may begin** on `C:\Users\ayewhy\Skeldir Webpage\marketing\`.

**Allowed D1 scope:** `marketing_static` routes only — HTML-first retrieval repair for:

- `/resources/[slug]` article instances (4 slugs)
- `/resources` hub
- `/`, `/product`, `/pricing`, `/agencies` where body integrity gaps exist

**Not allowed in D1:**

- Implementing Trust API under `marketing/src/app/api`
- Promoting `/book-demo` to sitemap eligibility
- Auth/transactional physical app split (deferred)
- Backend provider enablement work

**D10 handoff:** Fix git scope, confirm deploy remote, commit D0 v2 artifacts, run harness post-commit.