# D6-b Target Page Completion — /press

## 1. Source Copy Used

- `c:\Users\ayewhy\Downloads\YMYL Content\skeldir-press -v1.md` (implemented with D6-b public-safety reframing in `marketing/src/app/press/page.tsx`)

## 2. Files Changed

| File | Change | Reason |
|---|---|---|
| `src/app/press/page.tsx` | Replaced noindex placeholder | Designed-absence press boundary page |
| `discoverability.public-contacts.json` | **New** | Approved public email channels |
| `PUBLIC_CONTACT_REGISTRY.md` | **New** | Human-readable contact registry |
| `discoverability.press-registry.json` | **New** | Indexability + approved media claims |
| `scripts/discoverability/lib/d6-press-exposure.mjs` | **New** | D6-b placeholder/IP/media/contact gates |
| `discoverability.sitemap-manifest.json` | Updated | Added `/press` |
| `discoverability.routes.json` | Updated | Active indexable route |
| `scripts/discoverability/lib/d2-crawl-graph.mjs` | Updated | Removed `/press` from noindex + sitemap forbidden |
| `scripts/discoverability-d6-harness.mjs` | Updated | Gate **6l** |
| `scripts/discoverability-d6-negative-controls.mjs` | Updated | NC-D6-28/29 |

## 3. Designed-Absence Treatment

| Source concept | Final public framing | Placeholder risk removed? |
|---|---|---|
| no marketing briefs | No press kits, roadmaps, or speculative product materials | **yes** |
| no roadmap commentary | No commentary on speculative future states or roadmap timing | **yes** |
| no speculative future states | Declined unpublished/unannounced/speculative requests | **yes** |
| inquiry routing | Press / engineering / sales channels + proof-page grounding | **yes** |
| technical disclosures as source | Published methodology and proof surfaces as primary record | **yes** |

## 4. Contact Registry

- **Registry path:** `marketing/discoverability.public-contacts.json`
- **Rendered contacts:** press@skeldir.com, engineering@skeldir.com, sales@skeldir.com, security@skeldir.com (referenced)
- **Approved contacts:** all `@skeldir.com` addresses in registry with `publicly_rendered: true`
- **Unapproved contacts removed?:** yes — page only uses registry-backed emails

## 5. Static HTML Proof

From `marketing/out/press.html`:

```html
<h1>Press</h1>
<h2>Bottom Line Up Front</h2>
<h2>Key facts</h2>
<h2>Technical disclosures as primary source</h2>
<h2>Inquiry routing and verification</h2>
<h2>Scope of public information</h2>
<h2>Contact</h2>
<p>press@skeldir.com … engineering@skeldir.com … sales@skeldir.com</p>
<p>Last updated: February 2026</p>
```

## 6. Placeholder Theater Scan

```bash
grep -Ei "placeholder|coming soon|technical_disclosure_only" out/press.html
# → no matches (PASS)
```

## 7. IP Exposure Scan

```bash
grep -Ei "TrustEnvelope contracts|enumerated contract fields|field schema|payload schema" out/press.html
# → no matches (PASS)
```

Negative boundary only: “does not publicly disclose internal architecture, implementation modules…”

## 8. Unsupported Media Claim Scan

```bash
grep -Ei "market leader|fastest-growing|award-winning|as seen in" out/press.html
# → no matches (PASS)
```

## 9. Proof-Link Graph

- `/methodology` ✓
- `/revenue-verification` ✓
- `/attribution-methodology` ✓
- `/discrepancy-taxonomy` ✓
- `/trust-envelope` ✓
- `/ai-boundary` ✓
- `/security` ✓
- `/status` ✓

## 10. Discoverability Regression

| Harness | Result |
|---|---|
| `npm run build` | **PASS** |
| `npm run discoverability:d2` (skip-build) | **PASS** |
| `npm run discoverability:d6` (skip-build) | **PASS** — 128/0; gate **6l** |
| `npm run discoverability:d6:negative-controls` | **PASS** — 31/0 |

## 11. Verdict

**PASS**
