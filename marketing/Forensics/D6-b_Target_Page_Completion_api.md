# D6-b Target Page Completion — /api

## 1. Source Copy Used

- `c:\Users\ayewhy\Downloads\YMYL Content\skeldir-API -v1.md` (implemented with D6-b public-safety reframing in `marketing/src/app/api/page.tsx`)

## 2. Files Changed

| File | Change | Reason |
|---|---|---|
| `src/app/api/page.tsx` | Replaced leaky API concept page | Designed-absence API access boundary |
| `discoverability.api-surface-registry.json` | **New** | Access model + contact + indexability |
| `API_SURFACE_REGISTRY.md` | **New** | Human-readable API surface registry |
| `discoverability.public-contacts.json` | Updated | `integration` contact type → sales@skeldir.com |
| `PUBLIC_CONTACT_REGISTRY.md` | Updated | Integration row documented |
| `scripts/discoverability/lib/d6-api-exposure.mjs` | **New** | D6-b scanners + registry alignment |
| `scripts/discoverability/lib/d5-trust-proof.mjs` | Updated | `/api` public boundary review-status exception |
| `discoverability.routes.json` | Updated | Evidence notes for D6-b boundary page |
| `scripts/discoverability-d6-harness.mjs` | Updated | Gate **6n** |
| `scripts/discoverability-d6-negative-controls.mjs` | Updated | NC-D6-32/33 |

## 3. Public-Safety Changes

| Source concept | Final public framing | Mechanism/contract detail removed? |
|---|---|---|
| machine-callable contract | governed programmatic access surface / boundary | **yes** |
| deterministic value in integer minor units | precise monetary representation | **yes** |
| enumerated verification status | bounded verification status | **yes** |
| evidence provenance reference set | verification context (no field names) | **yes** |
| semantic/artifact integrity metadata | integrity context categories not listed | **yes** |
| response contains | What API access represents / What context accompanies programmatic output | **yes** |
| operational decision boundary | downstream use governed by policy and agreement scope | **yes** |

## 4. API Surface Registry

- **Registry path:** `marketing/discoverability.api-surface-registry.json`
- **Public API reference available:** false
- **Public endpoint details rendered:** false
- **Access model:** agreement_required
- **Authorized integrator only:** true
- **Contact channel:** sales@skeldir.com
- **Last reviewed:** 2026-02-25
- **Owner:** Skeldir Product Engineering

## 5. Contact Registry

- **Registry path:** `marketing/discoverability.public-contacts.json`
- **Rendered contacts:** `sales@skeldir.com` only
- **Approved contacts:** `sales` + `integration` entries for same email
- **Unapproved contacts removed?:** yes (no api@ / integrations@ / engineering@ on page)

## 6. Static HTML Proof

From `marketing/out/api.html`:

```html
<h1>API</h1>
<h2>Bottom Line Up Front</h2>
<h2>Key facts</h2>
<h2>What API access represents</h2>
<h2>What context accompanies programmatic output</h2>
<h2>How agents consume Skeldir output responsibly</h2>
<h2>How access is governed</h2>
<h2>Current operational boundaries</h2>
<p>public API access boundary … authorized integrators under agreement</p>
<p>sales@skeldir.com</p>
<p>Last updated: February 2026</p>
```

## 7. Placeholder Theater Scan

```bash
grep -Ei "coming soon|placeholder|technical_disclosure_only|Owner_Skeldir" out/api.html
# → no matches (PASS)
```

## 8. API Contract Leakage Scan

```bash
grep -Ei "OpenAPI|Swagger|GET /|POST /|Bearer token|rate limit|endpoint URL|payload schema" out/api.html
# → no matches (PASS)
```

## 9. TrustEnvelope Response-Shape Leakage Scan

```bash
grep -Ei "semantic truth hash|artifact hash|evidence reference set|integer minor units|TrustEnvelope contract|policy object" out/api.html
# → no matches (PASS)
```

## 10. Registry Alignment Proof

Registry: `public_api_reference_available: false`, `access_model: agreement_required`, `contact_channel: sales@skeldir.com`.

Built HTML includes: authorized integrator, agreement, concrete endpoint, authentication details, verification context, deterministic value, verification status, advisory.

## 11. Proof-Link Graph

```bash
grep -E 'href="/trust-envelope"|href="/methodology"|href="/revenue-verification"|href="/ai-boundary"|href="/security"|href="/docs"|href="/privacy"' out/api.html
# → all seven links present (PASS)
```

## 12. Discoverability Regression

| Harness | Result |
|---|---|
| `npm run build` | **PASS** |
| `npm run discoverability:d5` (skip-build) | **PASS** — 73/0 |
| `npm run discoverability:d6` (skip-build) | **PASS** — 134/0; gate **6n** |
| `npm run discoverability:d6:negative-controls` | **PASS** — 35/0 |
| `npm run discoverability:d2` | **PASS** — 57/0 |

## 13. Verdict

**PASS**
