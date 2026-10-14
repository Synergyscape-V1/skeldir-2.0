# D6-b Target Page Completion — /about

## 1. Source Copy Used

- `c:\Users\ayewhy\Downloads\YMYL Content\skeldir-about-v1.md` (implemented with D6-b public-safety reframing in `marketing/src/app/about/page.tsx`)

## 2. Files Changed

| File | Change | Reason |
|---|---|---|
| `src/app/about/page.tsx` | Replaced noindex placeholder | Canonical public entity-definition page |
| `discoverability.about-surface-registry.json` | **New** | Positioning terms + proof routes + indexability |
| `ABOUT_SURFACE_REGISTRY.md` | **New** | Human-readable about registry |
| `scripts/discoverability/lib/d6-about-exposure.mjs` | **New** | D6-b scanners + D4 entity semantics drift |
| `discoverability.sitemap-manifest.json` | Updated | Added `/about` |
| `discoverability.routes.json` | Updated | Active indexable route |
| `scripts/discoverability/lib/d2-crawl-graph.mjs` | Updated | Removed `/about` from noindex + sitemap forbidden sets |
| `scripts/discoverability-d6-harness.mjs` | Updated | Gate **6p** |
| `scripts/discoverability-d6-negative-controls.mjs` | Updated | NC-D6-36/37 |

## 3. Public-Safety Changes

| Source concept | Final public framing | Mechanism/overclaim removed? |
|---|---|---|
| integer-cents reconciliation | precise financial reconciliation / precise monetary representation | **yes** |
| machine-readable trust record | structured trust outputs for human and system review | **yes** |
| full provenance/audit trail | verification status, evidence context, and auditability | **yes** |
| every query/record/output tenant scoped | tenant-scoped financial memory and privacy-preserving boundaries | **yes** |
| PII stripped/durable storage | minimize durable personal identifiers in reconciliation substrate | **yes** |
| deterministic computation engine | deterministic reconciliation over verified evidence | **yes** |
| connected systems / normalization | operator-authorized commerce and payment evidence | **yes** |
| configure reconciliation policy | verification scope through governed engagement | **yes** |

## 4. About Surface Registry

- **Registry path:** `marketing/discoverability.about-surface-registry.json`
- **Canonical entity definition:** financial-trust infrastructure for deterministic revenue verification; platform-reported vs independent evidence
- **Approved terms:** financial-trust infrastructure, deterministic revenue verification, verified revenue, tenant-scoped financial memory, AI explanation boundary, etc.
- **Disallowed terms:** AI attribution assistant (primary), analytics dashboard (primary), integer-cents reconciliation, etc.
- **Indexability:** true
- **Sitemap required:** true
- **Schema allowed:** WebPage
- **Proof routes:** methodology, revenue-verification, trust-envelope, security, privacy, api, docs, etc.
- **Last reviewed:** 2026-02-25
- **Owner:** Skeldir Growth

## 5. Static HTML Proof

From `marketing/out/about.html`:

```html
<h1>About Skeldir</h1>
<h2>Bottom Line Up Front</h2>
<h2>Key facts</h2>
<h2>What Skeldir Does</h2>
<h2>Principles That Govern Skeldir</h2>
<h2>Who Skeldir Serves</h2>
<h2>How Skeldir Differs From Analytics and Attribution Platforms</h2>
<h2>How Organizations Engage With Skeldir</h2>
<p>financial-trust infrastructure … deterministic revenue verification</p>
<p>not an analytics dashboard … not an AI attribution assistant</p>
<p>Last updated: February 2026</p>
```

## 6. Placeholder Theater Scan

```bash
grep -Ei "placeholder|coming soon|technical_disclosure_only" out/about.html
# → no matches in visible body (PASS)
```

## 7. Entity Semantics Scan

- D6 gate **6p** runs `validateD6EntitySemanticsDrift` against `entity-semantics-registry.json`
- **PASS** — no disallowed/high-risk primary positioning

## 8. IP Exposure Scan

```bash
grep -Ei "integer-cents|machine-readable trust record|full audit trail|PII is stripped|deterministic computation engine" out/about.html
# → no matches in visible body (PASS)
```

## 9. Absolute Guarantee Scan

```bash
grep -Ei "every output carries|every query|no PII|guaranteed|sovereign truth" out/about.html
# → no matches (PASS)
```

## 10. Proof-Link Graph

All required links present: `/methodology`, `/revenue-verification`, `/attribution-methodology`, `/discrepancy-taxonomy`, `/trust-envelope`, `/ai-boundary`, `/security`, `/privacy`, `/api`, `/docs`

## 11. Discoverability Regression

| Harness | Result |
|---|---|
| `npm run build` | **PASS** |
| `npm run discoverability:d2` | **PASS** — 58/0; `/about` canonical + sitemap |
| `npm run discoverability:d4` | **PASS** — 43/0; `/about` WebPage JSON-LD |
| `npm run discoverability:d6` (skip-build) | **PASS** — 138/0; gate **6p** |
| `npm run discoverability:d6:negative-controls` | **PASS** — 39/0 |

## 12. Verdict

**PASS**
