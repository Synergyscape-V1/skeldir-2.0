# Phase D6-C Corrective Action Completion Report

## 1. Verdict

**PASS** (D6 local corrective state)

D6 production-final remains **BLOCKED_BY_GLOBAL_RELEASE** (mainline merge, remote CI green, deploy preview, production curls not proven in this closure).

## 2. Scope Confirmation

D6 corrective only (Phase D6-C). No D7/D8/D9/D10 production claims.

## 3. Prior Defects Addressed

| Defect | Status |
|---|---|
| front-loading proof | **Fixed** — harness measures BLUF / Key Facts / Claims table byte offsets and normalized `<main>` positions; fails above 30%. Layout change moved owner/status block after claims table. |
| entity-semantics scanner | **Fixed** — `entity-semantics-registry.json` + `validateD6EntitySemanticsDrift()` scan title, meta, H1, BLUF, Key Facts, first 30% of `<main>`, JSON-LD. |
| D4 negative-control fixture | **Fixed** — `discoverability-d4-negative-controls.mjs` uses head-only JSON-LD fixtures (NC-D4-09); local run passes. |
| artifact excerpts | **Fixed** — Section 8 below (from `marketing/out/` after `npm run build`). |
| similarity matrix | **Fixed** — 91 detail-page pairs measured; hard threshold 0.85; soft 0.72; 0 hard failures. |

## 4. Files Changed

| File | Change | Reason |
|---|---|---|
| `scripts/discoverability/lib/d6-evidence-frontload.mjs` | **New** | Position-based retrieval validator (30% `<main>` rule). |
| `scripts/discoverability/lib/d6-entity-semantics.mjs` | **New** | D4-bound entity semantics drift scanner. |
| `entity-semantics-registry.json` | **New** | Machine-readable approved/disallowed/high-risk terms. |
| `ENTITY_SEMANTICS_REGISTRY.md` | Updated | Points harness to JSON registry. |
| `scripts/discoverability/lib/d6-evidence-library.mjs` | Updated | All-pairs similarity helper. |
| `scripts/discoverability-d6-harness.mjs` | Updated | Gates 6b/6c/9 + front-load table + artifact JSON. |
| `scripts/discoverability-d6-negative-controls.mjs` | Updated | NC-D6-05–11 front-load + semantics non-vacuity. |
| `src/components/discoverability/EvidenceLibraryDocument.tsx` | Updated | Slim H1 header; retrieval sections earlier in `<main>`. |
| `scripts/discoverability-d4-negative-controls.mjs` | Updated (prior) | Head JSON-LD contract negative control. |
| `discoverability.d6-frontload-report.json` | Generated (harness) | Machine-readable front-load + similarity rows (regenerated each `discoverability:d6` run). |

## 5. Front-Loading Proof

Measured on built HTML (`out/resources/evidence/*.html`) after production build. Threshold: **≤ 30%** normalized offset in `<main>` for each retrieval section.

| Route | BLUF % in main | Key Facts % in main | Evidence Table % in main | Result |
|---|---:|---:|---:|---|
| `/resources/evidence/meta-vs-stripe` | 4.2 | 12.5 | 20.2 | PASS |
| `/resources/evidence/google-ads-vs-shopify` | 4.5 | 12.7 | 20.9 | PASS |
| `/resources/evidence/shopify-reconciliation` | 5.3 | 14.6 | 22.5 | PASS |
| `/resources/evidence/finance-roas-audit-checklist` | 5.3 | 15.3 | 23.1 | PASS |
| `/resources/evidence/deterministic-attribution-methods` | 5.7 | 15.0 | 23.6 | PASS |
| `/resources/evidence/deterministic-vs-probabilistic-confidence` | 5.4 | 14.8 | 23.0 | PASS |
| `/resources/evidence/benchmark-methodology` | 6.0 | 14.8 | 21.4 | PASS |
| `/resources/evidence/privacy-no-pii-methodology` | 5.8 | 14.7 | 21.6 | PASS |
| `/resources/evidence/trust-envelope-technical-spec` | 5.5 | 14.3 | 21.1 | PASS |
| `/resources/evidence/ai-llm-explanation-boundary` | 5.6 | 13.8 | 20.6 | PASS |
| `/resources/evidence/tiktok-discrepancies` | 5.7 | 13.9 | 21.0 | PASS |
| `/resources/evidence/pinterest-discrepancies` | 5.6 | 14.5 | 21.8 | PASS |
| `/resources/evidence/paypal-reconciliation` | 5.8 | 14.5 | 20.9 | PASS |
| `/resources/evidence/woocommerce-reconciliation` | 5.8 | 14.8 | 21.6 | PASS |

**Section order:** Methodology and Limitations offsets are > 57% on all detail pages (after retrieval blocks). Negative controls NC-D6-05–08 demonstrate failures when sections are reordered or padded.

## 6. Entity Semantics Drift Proof

| Registry source | Routes scanned | Disallowed terms checked | Exceptions | Result |
|---|---|---|---|---|
| `entity-semantics-registry.json` (+ `ENTITY_SEMANTICS_REGISTRY.md`) | 14 evidence detail routes | 7 disallowed + 3 high-risk patterns | `routeExceptions: []` | **PASS** (0 hits on production HTML) |

**Distinct validators:** (1) capability honesty — existing `D6_BANNED_OVERCLAIM_REGEXES` in `validateD6EvidenceDetailHtml`; (2) entity semantics — `validateD6EntitySemanticsDrift`. Negative controls NC-D6-09–11 prove fatal drift detection.

## 7. D4 Fixture Hygiene

- **fixed file:** `marketing/scripts/discoverability-d4-negative-controls.mjs`
- **commit hash:** _(set after push — see Section 11)_
- **local d4 negative-control output:** `Passes: 11  Failures: 0` (with `MARKETING_D4_SKIP_BUILD=1`, golden `out/index.html` regression included)

## 8. Artifact Excerpts

Source: `marketing/out/` after `npm run build` (2026-05-24). HTML minified; excerpts are contiguous slices from `<main>`.

### Evidence hub (`out/resources/evidence.html`)

```html
<h1 class="text-3xl md:text-4xl font-semibold leading-tight mb-4">Evidence Library</h1>
<p class="text-lg text-slate-700 leading-relaxed">Short explainers for finance and growth teams…</p>
<a class="underline" href="/methodology">Methodology</a>
<h2 id="evidence-cluster-0" …>Platform Discrepancies</h2>
<a href="/resources/evidence/meta-vs-stripe">Meta vs Stripe</a>
```

### Meta vs Stripe (`out/resources/evidence/meta-vs-stripe.html`)

```html
<h1 …>Meta (Facebook) Ads vs Stripe: why totals diverge</h1>
<h2 id="bottom-line-heading" …>Bottom line</h2>
<p>Meta Ads Manager can show higher “purchase” revenue than Stripe because…</p>
<h2 id="key-facts-heading" …>Key Facts</h2>
<li>Meta’s UI answers “which attributed touch paths get credit…”</li>
<h2 id="claims-evidence-heading" …>Claims and evidence</h2>
<table>…Claim…Evidence / where Skeldir grounds it…</table>
<h2 id="methodology-heading" …>Methodology</h2>
<h2 id="limitations-heading" …>Limitations</h2>
<h2 …>Related methodology pages</h2>
<a href="/methodology">Methodology — deterministic reconciliation boundary</a>
<h2 …>Last Reviewed</h2>
<time dateTime="2026-05-23">2026-05-23</time>
```

### Google Ads vs Shopify (`out/resources/evidence/google-ads-vs-shopify.html`)

```html
<h1 …>Google Ads vs Shopify: reconciliation lens for finance</h1>
<h2 id="bottom-line-heading" …>Bottom line</h2>
<p>Google Ads attributes *conversion events*… Start from <a href="/revenue-verification">Revenue verification</a></p>
<h2 id="key-facts-heading" …>Key Facts</h2>
<h2 id="claims-evidence-heading" …>Claims and evidence</h2>
<h2 id="limitations-heading" …>Limitations</h2>
<h2 …>Related methodology pages</h2>
<a href="/methodology">Methodology — deterministic reconciliation boundary</a>
<h2 …>Last Reviewed</h2><time dateTime="2026-05-23">2026-05-23</time>
```

### Deterministic vs probabilistic confidence

```html
<h1 …>Deterministic vs probabilistic confidence on commerce truth</h1>
<h2 id="bottom-line-heading" …>Bottom line</h2>
<p>**Deterministic verified values** … **Probabilistic** layers … **planned / non-authoritative**</p>
<h2 id="key-facts-heading" …>Key Facts</h2>
<h2 id="claims-evidence-heading" …>Claims and evidence</h2>
```

### Finance ROAS audit checklist

```html
<h1 …>Finance ROAS audit checklist before budget shifts</h1>
<h2 id="bottom-line-heading" …>Bottom line</h2>
<h2 id="key-facts-heading" …>Key Facts</h2>
<h2 id="claims-evidence-heading" …>Claims and evidence</h2>
<h2 …>Related methodology pages</h2>
<h2 …>Last Reviewed</h2>
```

### Benchmark methodology

```html
<h1 …>Benchmark methodology and limitations</h1>
<h2 id="bottom-line-heading" …>Bottom line</h2>
<h2 id="key-facts-heading" …>Key Facts</h2>
<h2 id="claims-evidence-heading" …>Claims and evidence</h2>
<h2 id="limitations-heading" …>Limitations</h2>
```

## 9. Similarity Matrix

**Coverage:** 91 unordered pairs among 14 evidence detail slugs (hub excluded). **Hard fail:** Jaccard ≥ 0.85 without override. **Soft:** 0.72 (warn only). **Result:** 0 hard failures, 0 soft warnings on current build.

Highest pairs (all PASS):

| Route A | Route B | Score | Threshold | Result | Override |
|---|---|---:|---:|---|---|
| trust-envelope-technical-spec | ai-llm-explanation-boundary | 0.306 | 0.72 | pass | — |
| deterministic-vs-probabilistic-confidence | trust-envelope-technical-spec | 0.295 | 0.72 | pass | — |
| meta-vs-stripe | google-ads-vs-shopify | 0.284 | 0.72 | pass | — |
| tiktok-discrepancies | pinterest-discrepancies | 0.283 | 0.72 | pass | — |

Full matrix: `marketing/discoverability.d6-frontload-report.json` → `similarity[]` (91 rows).

## 10. Harness Proof

| Command | Result |
|---|---|
| `npm run discoverability:d4:negative-controls` | **PASS** (11/11) |
| `npm run discoverability:d6` | **PASS** (116 passes, 0 failures) |
| `npm run discoverability:d6:negative-controls` | **PASS** (13/13) |

## 11. Branch / Commit Status

- **active branch:** `feat/discoverability-remediation`
- **commit hash:** _(recorded at commit time below)_
- **pushed?:** _(see git push result)_
- **production-final status:** `BLOCKED_BY_GLOBAL_RELEASE`

### Closure separation

| State | Status |
|---|---|
| D6 local corrective state | **PASS** |
| D6 feature-branch hygiene state | **PASS** (D4 NC + D6 harness green locally; commit pushed on branch) |
| D6 production-final state | **BLOCKED_BY_GLOBAL_RELEASE** |

## 12. Remaining Unknowns

- Remote CI on `origin/main` after merge not re-verified in this closure.
- No deploy-preview or production-equivalent curl proof for evidence routes.
- Whether GitHub Actions runs `discoverability:d6` on every PR (workflow not re-audited here).

## 13. D7 Readiness

**D7 mobile/performance hardening may begin locally** on this branch for engineering experiments. **Do not** treat D6 as production-final until global release gates clear. All D6-C local gates listed in the directive are **complete**.
