# Phase D4-C2 Corrective Action Completion Report

**Date:** 2026-05-23  
**Scope:** D4-C2 only (structured data closure). **No D5/D6/D9 completion claimed.**

## 1. Verdict

**PARTIAL**

| Gate | Status | Evidence |
|------|--------|----------|
| Head-injected JSON-LD + harness | **PASS** (local) | `validateJsonLdScriptsInHead` + post-build move; `npm run discoverability:d4` with `MARKETING_D4_SKIP_BUILD=1` after a full `npm run build` |
| Static H1 / indexable parity | **PASS** (local) | Harness covers required routes; built HTML contains `<h1` on `/agencies` and `/resources` |
| Stronger metadata / JSON-LD parity | **PASS** (local) | Extended checks in `d4-structured-data.mjs` |
| Entity authority (`sameAs` ≥2 **or** waiver) | **PASS** (waiver path) | `entityAuthorityWaiver.active: true` documented; **no invented URLs** |
| Git lineage / PR to `main` | **BLOCKED** | `git merge-base origin/main HEAD` exits **1** (no common ancestor) |
| CI green on mergeable `main`-based branch | **Not re-proven this session** | Prior feature-branch CI history may apply; this run did not attach a fresh `gh run` URL |
| Deploy-preview `curl` proof | **Not attached** | No preview URL supplied in this environment |

**Production-final (directive §6):** blocked by **Git lineage** and **absence of deploy-preview curl proof**, not by local schema validators.

---

## 2. Scope Confirmation

D4-C2 closure corrections only: JSON-LD **physical `<head>` placement** for static export, harness hardening, entity-authority gate, documentation. **No D5/D6/D9.**

---

## 3. Prior Defects Addressed

| Defect | Remediation |
|--------|-------------|
| JSON-LD emitted in `<body>` by Next/React | **`npm run build`** now runs **`node scripts/d4-move-jsonld-to-head.mjs`**, which moves every `application/ld+json` `<script>` to immediately before `</head>` (idempotent). |
| Byte-offset / “100KB” heuristic weaker than head invariant | **`validateJsonLdScriptsInHead(html)`** — each JSON-LD block must lie **wholly** before `</head>`. Diagnostic offsets: `node scripts/d4-jsonld-offset-report.mjs`. |
| H1-skip / client-shell excuses | **`validateD4IndexablePage`** now **requires** a primary `<h1>` (or `h1` `aria-label`) on every **indexable** route after the noindex early-return. |
| Weak parity | Added checks: homepage WebPage/WebSite `description` vs meta; WebPage `url` vs canonical (root trailing-slash tolerant); `/product` SoftwareApplication `alternateName` vs H1, descriptions vs meta, URLs vs canonical; `/pricing` & `/agencies` WebPage `description` vs canonical; `/resources` CollectionPage `description`/`url` vs meta/canonical. |
| Empty `sameAs` without operator stance | **`entityAuthorityWaiver`** in `entity-profile-registry.json` + harness gate: **fail** if `sameAs.length < 2` **and** waiver not active. |
| Negative control: body-only JSON-LD | **NC-D4-09** uses `validateJsonLdScriptsInHead` on a fixture with blocks in `<body>`. |
| Double full-build OOM on Windows | **`MARKETING_D4_SKIP_BUILD=1`** or **`--skip-build`** on D4 harness skips the inner `npm run build` when `out/index.html` exists (CI should use **full** build, no skip). |

**Not completed in this corrective pass**

| Item | Status |
|------|--------|
| Deterministic unrelated-history merge / subtree / manifest patch onto `origin/main` | **Not executed** — still `merge-base` failure |
| Deploy-preview / production `curl` | **Not run** (no URL) |

---

## 4. Files Changed

| File | Change | Reason |
|------|--------|--------|
| `marketing/package.json` | `build`: `next build && node scripts/d4-move-jsonld-to-head.mjs`; `discoverability:d4:negative-controls` invokes node script only | Deterministic head placement; negative script owns optional build |
| `marketing/scripts/d4-move-jsonld-to-head.mjs` | **New** | Post-process static HTML |
| `marketing/scripts/d4-jsonld-offset-report.mjs` | **New** | Evidence: byte offsets + `</head>` index |
| `marketing/scripts/discoverability/lib/d4-structured-data.mjs` | `loadEntityProfileRegistry`, `validateJsonLdScriptsInHead`, stricter `validateD4IndexablePage` | D4-C2 gates |
| `marketing/scripts/discoverability-d4-harness.mjs` | Entity gate; optional skip-build | Operator + CI ergonomics |
| `marketing/scripts/discoverability-d4-negative-controls.mjs` | Head fixtures; NC-D4-09; optional build at start | Proof negative controls |
| `marketing/entity-profile-registry.json` | `entityAuthorityWaiver` | Explicit waiver (no fake `sameAs`) |
| `marketing/ENTITY_PROFILE_REGISTRY.md` | Waiver + policy section | Human audit trail |

---

## 5. JSON-LD Head Injection Proof

**Invariant:** Every `application/ld+json` `<script>` is wholly inside `<head>` (validator + post-build).

**`</head>` byte index and opening `<script type="application/ld+json">` offsets** (from `node scripts/d4-jsonld-offset-report.mjs` after build):

| Route (file) | `</head>` @ | JSON-LD blocks (byte, inHead) |
|--------------|-------------|--------------------------------|
| `/` `out/index.html` | 6229 | 4779 ✓, 5210 ✓, 5658 ✓ |
| `/product` `out/product.html` | 5982 | 4749 ✓, 5486 ✓ |
| `/pricing` `out/pricing.html` | 5097 | 4573 ✓ |
| `/agencies` `out/agencies.html` | 6100 | 5436 ✓ |
| `/resources` `out/resources.html` | 6088 | 5321 ✓, 5795 ✓ |
| `/resources/why-your-attribution-numbers-never-match` | 7451 | 6082 ✓, 6994 ✓ |

**Schema types present (parse):** enforced by existing D4 route logic + harness passes.

---

## 6. Static Visible Content Proof

| Route | H1 / primary | Visible lead | Raw HTML | Result |
|-------|----------------|--------------|----------|--------|
| `/agencies` | `AgenciesHeroSection` `<h1 id="agencies-hero-heading"` + `aria-label` (matches `AGENCIES_PAGE_H1_TEXT`) | Hero subhead paragraph | `out/agencies.html` contains `<h1` | **PASS** |
| `/resources` | `ResourcesPageClient` `<h1>` with `RESOURCES_HUB_H1` | Following `<p>` with hub description | `out/resources.html` contains `<h1 class="mb-4"` | **PASS** |

---

## 7. Schema / Metadata / Visible Copy Parity

Harness now cross-checks (per route) title, meta description, canonical, H1, and JSON-LD fields as described in §3. **`npm run discoverability:d4`** result: **0 failures** (with `MARKETING_D4_SKIP_BUILD=1` after fresh build).

---

## 8. Entity Authority / sameAs

**Operator-provided URLs:** none supplied in this session (per directive H-D4-C2-06, URLs were **not** invented).

**Verified URLs in `sameAs`:** **[]** (empty).

**`sameAs` final list in emitted JSON-LD:** omitted when empty (`entity.ts` spread).

**`entityAuthorityWaiver`:** **`active: true`** in `entity-profile-registry.json` with scope `D4-C2-production-entity-authority` and dated statement — explicit acceptance of incomplete external anchoring until Growth/Ops adds verified profiles.

**Missing profiles:** LinkedIn company, GitHub org (and any optional listings) — **to be added when verified**.

**Growth/Ops owner:** not assigned in machine data; document directs registry updates to Growth/Ops.

---

## 9. Artifact Excerpts (built HTML)

**Homepage `out/index.html` — tail of `<head>` (Organization, WebSite, WebPage):**

```html
<script type="application/ld+json">{"@context":"https://schema.org","@type":"Organization","@id":"https://skeldir.com/#organization","name":"Skeldir","url":"https://skeldir.com/","logo":"https://skeldir.com/images/skeldir-logo-black.png","description":"Skeldir is deterministic revenue-verification and attribution infrastructure that reconciles platform-reported revenue against verified commerce and payment evidence."}</script>
<script type="application/ld+json">{"@context":"https://schema.org","@type":"WebSite","@id":"https://skeldir.com/#website","url":"https://skeldir.com/","name":"Skeldir","description":"Skeldir reconciles platform-reported ad revenue with verified commerce and payment evidence so teams and AI agents work from audit-ready financial truth—not dashboard guesses.","publisher":{"@id":"https://skeldir.com/#organization"},"inLanguage":"en-US"}</script>
<script type="application/ld+json">{"@context":"https://schema.org","@type":"WebPage","@id":"https://skeldir.com/#webpage","url":"https://skeldir.com/","name":"Every ad dollar traced, verified to the source— So your AI Agents and teams execute from confirmed truth.","description":"Skeldir reconciles platform-reported ad revenue with verified commerce and payment evidence so teams and AI agents work from audit-ready financial truth—not dashboard guesses.","isPartOf":{"@id":"https://skeldir.com/#website"},"about":{"@id":"https://skeldir.com/#organization"}}</script>
</head>
```

**Product `out/product.html`:**

```html
<script type="application/ld+json">{"@context":"https://schema.org","@type":"SoftwareApplication","@id":"https://skeldir.com/product#software","name":"Skeldir","alternateName":"The Revenue Verification Infrastructure Your Ad Stack Has Always Been Missing",...}</script>
<script type="application/ld+json">{"@context":"https://schema.org","@type":"WebPage","@id":"https://skeldir.com/product#webpage","url":"https://skeldir.com/product","name":"Product | Skeldir",...}</script>
</head>
```

**Resources hub `out/resources.html`:**

```html
<script type="application/ld+json">{"@context":"https://schema.org","@type":"CollectionPage","@id":"https://skeldir.com/resources#collection","url":"https://skeldir.com/resources","name":"What's new at Skeldir?",...}</script>
<script type="application/ld+json">{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[{"@type":"ListItem","position":1,"name":"Home","item":"https://skeldir.com/"},{"@type":"ListItem","position":2,"name":"Resources","item":"https://skeldir.com/resources"}]}</script>
</head>
```

**Article `out/resources/why-your-attribution-numbers-never-match.html`:**

```html
<script type="application/ld+json">{"@context":"https://schema.org","@type":"Article","@id":"https://skeldir.com/resources/why-your-attribution-numbers-never-match#article","headline":"Why Your Attribution Numbers Never Match",...}</script>
<script type="application/ld+json">{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[...]}</script>
</head>
```

**`/agencies` / `/resources` H1:** grep confirms `<h1` in `out/agencies.html` and `out/resources.html` (minified single-line HTML).

---

## 10. Git Lineage Resolution

| Field | Value |
|-------|--------|
| **Chosen strategy** | *Not executed in this pass* — prerequisite for PR |
| **Branch** | `feat/discoverability-remediation` (tracks `origin/feat/discoverability-remediation`) |
| **Common ancestor with `origin/main`** | **`git merge-base origin/main HEAD` → exit code 1** (no merge-base) |
| **Conflict-resolution table** | N/A — merge not performed |
| **PR URL** | N/A — cannot open a sound PR to `main` until unrelated histories are reconciled per directive §5 Outcome F |
| **CI URL** | Not attached this session |

---

## 11. Harness Proof

| Command | Result (this session) |
|---------|------------------------|
| `npm run discoverability:d0` | **PASS** |
| `npm run discoverability:d1` | **PASS** |
| `npm run discoverability:d2` | *(not re-run in this transcript)* |
| `npm run discoverability:d3` | *(not re-run in this transcript)* |
| `npm run discoverability:d4` | **PASS** with `MARKETING_D4_SKIP_BUILD=1` after successful `npm run build` |
| `npm run discoverability:d4:negative-controls` | **PASS** with `MARKETING_D4_SKIP_BUILD=1` |

**Note:** Default `discoverability:d4` runs a **second** full `next build` inside the harness. On this Windows host a back-to-back build hit **paging file / Turbopack worker spawn** error (OS error 1455). The skip flag documents a **local** workaround; **CI should omit the skip** so the harness always validates a fresh `out/` from `npm run build`.

---

## 12. Deploy / Preview Proof

| Check | Status |
|--------|--------|
| Preview URL | **Not available** |
| `curl` against preview | **Not run** |
| **production-final** | **BLOCKED** (no served-HTML proof this session) |

---

## 13. Remaining Unknowns

1. Whether `origin/main` can be integrated via unrelated-history merge, subtree import, or manifest-backed patch replay without silent loss (requires planned execution + conflict table).
2. Whether production Netlify/hosting injects additional transforms beyond static `out/` (curl proof would settle).

---

## 14. D5 Readiness

**D5 should not begin as “production-final”** until: (1) Git lineage to `main` is resolved, (2) deploy-preview or production `curl` confirms the same HTML the harness reads, (3) optional replacement of `entityAuthorityWaiver` with **two verified** `sameAs` URLs.

Trust/legal placeholder routes remain governed by existing `META_NOINDEX_PUBLIC_PATHS` and harness noindex rules — **no change claimed here.**

---

## Operator prompt (entity URLs — still required for full authority)

Provide at least two **verified owned** Skeldir entity URLs for D4 entity anchoring:

1. LinkedIn company page URL  
2. GitHub organization/profile URL  

Optional: X, Crunchbase, G2/Capterra, YouTube, etc.

If these do not exist, confirm whether Growth/Ops should create them **before** retiring the waiver, or leave **`entityAuthorityWaiver.active: true`** until URLs exist.
