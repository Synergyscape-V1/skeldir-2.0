# D6-b Target Page Completion — /attribution-methodology

## 1. Source Copy Used

- `c:\Users\ayewhy\Downloads\YMYL Content\skeldir-attribution_methodology -v1.md` (implemented with D6-b public-safety reframing in `marketing/src/app/attribution-methodology/page.tsx`)

## 2. Files Changed

| File | Change | Reason |
|---|---|---|
| `src/app/attribution-methodology/page.tsx` | Rewritten | v1 concepts, IP-safe framing, public presentation, proof-link graph, `#bounded-questions` anchor preserved |
| `scripts/discoverability/lib/d6-attribution-methodology-exposure.mjs` | **New** | D6-b forbidden leakage + separation markers + structure |
| `scripts/discoverability/lib/d5-trust-proof.mjs` | Updated | Public boundary satisfies D5 review-status without snake_case badge |
| `scripts/discoverability-d6-harness.mjs` | Updated | Gate **6g** |
| `scripts/discoverability-d6-negative-controls.mjs` | Updated | NC-D6-18/19 |

## 3. Public-Safety Changes

| Source concept | Final public framing | Mechanism removed? |
|---|---|---|
| window length | Documented assumption categories: time scope, touchpoint treatment, inclusion boundaries | **yes** |
| touchpoint weighting | Touchpoint treatment (generic category) | **yes** |
| eligibility rules | Inclusion boundaries (generic category) | **yes** |
| exclusions | Inclusion boundaries (generic category) | **yes** |
| named attribution models | Different approaches can emphasize positions or timing (not listed) | **yes** |
| reproduce model output | Reviewer understands which assumptions shaped output and where limits apply | **yes** |
| separate record/reference language | Attribution output presented separately from verified revenue value | **yes** |

## 4. Static HTML Proof

From `marketing/out/attribution-methodology.html`:

```html
<h1>Attribution Methodology</h1>
<p>Last updated: February 2026</p>
<h2>Key facts</h2>
<h2>What attribution models answer</h2>
<h2>What assumptions mean at a public level</h2>
<h2>Why attribution models are bounded</h2>
<h2>Why attribution is not causality</h2>
<h2>How attribution output relates to deterministic revenue</h2>
<p>verified revenue … deterministic … model-derived … distributes credit … causal lift … controlled experimentation … incrementality</p>
<h2>Limitations</h2>
<p>Current limitations. …</p>
<a href="/methodology">…</a>
<a href="/revenue-verification">…</a>
<a href="/discrepancy-taxonomy">…</a>
```

## 5. IP Exposure Scan

```bash
grep -Ei "reproduce the model output|first-touch|window length|weighting logic|decay function" out/attribution-methodology.html
# → no matches (PASS)
```

## 6. Placeholder Theater Scan

```bash
grep -Ei "technical_disclosure_only|Owner_Skeldir|placeholder|coming soon" out/attribution-methodology.html
# → no matches (PASS)
```

## 7. Proof-Link Graph

- `/methodology` ✓
- `/revenue-verification` ✓
- `/discrepancy-taxonomy` ✓
- `/ai-boundary` ✓
- `/trust-envelope` ✓

## 8. Discoverability Regression

| Harness | Result |
|---|---|
| `npm run build` | **PASS** |
| `npm run discoverability:d5` (skip-build) | **PASS** — 71/0; `#bounded-questions` for D5-CLAIM-008 |
| `npm run discoverability:d6` (skip-build) | **PASS** — 120/0; gate **6g** |
| `npm run discoverability:d6:negative-controls` | **PASS** — 21/19 |

## 9. Verdict

**PASS**
