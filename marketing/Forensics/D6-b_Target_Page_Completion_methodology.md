# D6-b Target Page Completion — /methodology

## 1. Source Copy Used

- `c:\Users\ayewhy\Downloads\YMYL Content\skeldir-methodology-page-v1.md` (implemented in `marketing/src/app/methodology/page.tsx`)

## 2. Files Changed

| File | Change | Reason |
|---|---|---|
| `src/app/methodology/page.tsx` | Rewritten | Full v1 copy: BLUF, five facts, architectural sections, proof links, limitations |
| `src/components/discoverability/TrustProofPage.tsx` | Extended | `presentation="public"` hides Owner/Status badges; BLUF + five-facts + related proof blocks |
| `scripts/discoverability/lib/d6-methodology-exposure.mjs` | **New** | D6-b forbidden IP/placeholder patterns + required section/link markers |
| `scripts/discoverability/lib/d5-trust-proof.mjs` | Updated | `/methodology` accepts professional disclosure boundary (Last updated + technical disclosure + not a contract) without snake_case status badge |
| `scripts/discoverability-d6-harness.mjs` | Updated | Gate **6d** runs `validateD6MethodologyExposure` on built HTML |
| `scripts/discoverability-d6-negative-controls.mjs` | Updated | NC-D6-12 (internal token), NC-D6-13 (match kernel leakage) |

## 3. Public Presentation Changes

- Owner/status public badges removed? **yes** (`presentation="public"` — no Owner/Status `<dl>` in static HTML)
- Last updated present? **yes** (`Last updated: February 2026` in header)
- Informational/non-contract boundary retained professionally? **yes** (prose: technical disclosure for informational use; not a contract)

Registry fields (`owner`, `status: technical_disclosure_only`) remain in source for D5/D6 registries only; they are **not** rendered in public HTML.

## 4. Static HTML Proof

From `marketing/out/methodology.html` after `npm run build`:

```html
<h1 class="text-3xl md:text-4xl font-semibold leading-tight mb-4">How Skeldir Produces Verified Revenue Truth</h1>
<p class="text-sm text-slate-600 mb-4"><span class="font-medium text-slate-800">Last updated:</span> February 2026</p>
<p class="text-sm text-slate-600 leading-relaxed border-l-2 border-slate-200 pl-4">This page is technical disclosure for informational use. It is not a contract, service-level agreement, or legal commitment.</p>
<h2 id="bottom-line-up-front-heading" …>Bottom Line Up Front</h2>
<p>Skeldir reconciles platform-reported ad revenue against verified commerce and payment evidence using a deterministic process…</p>
<h2 id="five-methodology-facts-heading" …>Five things that are true about this methodology</h2>
<ul class="list-disc pl-6 space-y-3 text-slate-700"><li>Every authoritative revenue figure originates from verified commerce…</li>…</ul>
<h2 id="deterministic-reconciliation-heading" …>How deterministic reconciliation works</h2>
<h2 id="verified-evidence-heading" …>What counts as verified evidence</h2>
<h2 id="attribution-models-heading" …>What attribution models prove — and what do they not prove</h2>
<h2 id="discrepancy-classification-heading" …>How discrepancies are classified</h2>
<h2 id="limitations-heading" …>Limitations</h2>
<h2 id="related-proof-pages-heading" …>Related proof pages</h2>
<a class="underline text-slate-900" href="/revenue-verification">Revenue verification — commerce and payment evidence</a>
<a … href="/attribution-methodology">…</a>
<a … href="/discrepancy-taxonomy">…</a>
<a … href="/ai-boundary">…</a>
```

## 5. IP Exposure Scan

```bash
grep -Ei "match kernel|source_snapshot_hash|semantic truth hash construction|artifact hash construction|Bayesian model internals|matching threshold" out/methodology.html
# → no matches (exit 0)
```

Harness: `validateD6MethodologyExposure` — **PASS**

## 6. Placeholder Theater Scan

```bash
grep -Ei "technical_disclosure_only|legal_review_required|Owner_Skeldir_Product_Engineering|coming soon|under construction|placeholder" out/methodology.html
# → no matches (exit 0)
```

Negative controls NC-D6-12 / NC-D6-13 — **PASS**

## 7. Discoverability Regression

| Harness | Result |
|---|---|
| `npm run build` | **PASS** |
| `npm run discoverability:d4:negative-controls` | **PASS** (11/11) |
| `npm run discoverability:d4` (skip-build) | **PASS** (methodology in indexable set) |
| `npm run discoverability:d5` (skip-build) | **PASS** (71 passes; `/methodology` concepts + baseline) |
| `npm run discoverability:d6` (skip-build) | **PASS** (117 passes; gate **6d** methodology OK) |
| `npm run discoverability:d6:negative-controls` | **PASS** (15/15) |
| `npm run discoverability:d1` | Not re-run this session (full build; prior branch state includes static `/methodology` in D1 route matrix) |
| `npm run discoverability:d2` | Not re-run this session (sitemap manifest already lists `/methodology`) |

## 8. Verdict

**PASS** — `/methodology` is a complete, indexable, static proof page with v1 copy, professional public presentation, D6-b exposure gates, and D4/D5/D6 harness green on current `out/`.

Production-final status for the site overall remains governed by the global release blocker (mainline CI, deploy preview, production curls).
