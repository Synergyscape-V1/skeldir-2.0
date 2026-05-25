# D6-b Target Page Completion — /privacy

## 1. Source Copy Used

- `c:\Users\ayewhy\Downloads\YMYL Content\skeldir-privacy -v1.md` (implemented with D6-b public-safety reframing in `marketing/src/app/privacy/page.tsx`)

## 2. Files Changed

| File | Change | Reason |
|---|---|---|
| `src/app/privacy/page.tsx` | Replaced legal placeholder | Public privacy posture page (noindex) |
| `discoverability.privacy-surface-registry.json` | **New** | Legal review state + indexability + contacts |
| `PRIVACY_SURFACE_REGISTRY.md` | **New** | Human-readable privacy registry |
| `discoverability.public-contacts.json` | Updated | `privacy` contact type → engineering@skeldir.com |
| `PUBLIC_CONTACT_REGISTRY.md` | Updated | Privacy row documented |
| `scripts/discoverability/lib/d6-privacy-exposure.mjs` | **New** | D6-b scanners + registry alignment |
| `scripts/discoverability/lib/d5-trust-proof.mjs` | Updated | D6-b `/privacy` posture gate (replaces legal_review_required theater) |
| `discoverability.routes.json` | Updated | Active noindex legal route |
| `discoverability.claim-proof-registry.json` | Updated | Security/PII claims proof to `/security` anchors |
| `D5_CLAIM_PROOF_REGISTRY.md` | Updated | Privacy posture documentation |
| `scripts/discoverability-d6-harness.mjs` | Updated | Gate **6o** |
| `scripts/discoverability-d6-negative-controls.mjs` | Updated | NC-D6-34/35 |
| `scripts/discoverability-d5-negative-controls.mjs` | Updated | NC-D5-10 privacy posture boundary |

## 3. Public-Safety Changes

| Source concept | Final public framing | Mechanism/overclaim removed? |
|---|---|---|
| authenticated webhook receivers | operator-authorized data through controlled integration paths | **yes** |
| HMAC/RSA verification | (not mentioned) | **yes** |
| no durable PII | reconciliation substrate designed to avoid retaining raw personal identifiers where not required | **yes** |
| row-level security | tenant-scoped access controls | **yes** |
| k-anonymity/dominance suppression | privacy-preserving aggregate controls | **yes** |
| legal review pending | designed-complete boundary via approved legal and operator channels | **yes** |

## 4. Privacy Surface Registry

- **Registry path:** `marketing/discoverability.privacy-surface-registry.json`
- **Public page type:** `privacy_posture`
- **Legal review status:** `pending`
- **Operator approved:** false
- **Indexability:** false (noindex)
- **Sitemap required:** false
- **Allowed claims:** privacy posture, data minimization, tenant-scoped records, etc.
- **Disallowed claims:** GDPR compliant, no PII, retention schedule, etc.
- **Last reviewed:** 2026-02-25
- **Owner:** Skeldir Operator + Legal

## 5. Contact Registry

- **Registry path:** `marketing/discoverability.public-contacts.json`
- **Rendered contacts:** `engineering@skeldir.com`, `security@skeldir.com`
- **Approved contacts:** `privacy`, `security_engineering`, `security` entries
- **Unapproved contacts removed?:** yes (no privacy@ / legal@ / dpo@)

## 6. Static HTML Proof

From `marketing/out/privacy.html`:

```html
<h1>Privacy</h1>
<h2>Bottom Line Up Front</h2>
<h2>Key facts</h2>
<h2>Privacy posture</h2>
<h2>Data Skeldir processes</h2>
<h2>Data minimization</h2>
<h2>Tenant-scoped data handling</h2>
<h2>Legal and operator documentation boundary</h2>
<h2>Contact</h2>
<p>public privacy posture summary, not a complete legal privacy policy</p>
<p>engineering@skeldir.com … security@skeldir.com</p>
<p>Last updated: February 2026</p>
<meta name="robots" content="noindex, follow">
```

## 7. Placeholder Theater Scan

```bash
grep -Ei "legal_review_required|undergoing review|placeholder|coming soon" out/privacy.html
# → no matches (PASS)
```

## 8. Privacy-Control IP Exposure Scan

```bash
grep -Ei "HMAC|RSA|webhook receiver|row-level security|k-anonymity" out/privacy.html
# → no matches (PASS)
```

## 9. Legal/Privacy Overclaim Scan

```bash
grep -Ei "GDPR compliant|no PII|no durable PII|retention schedule" out/privacy.html
# → no matches (PASS)
```

## 10. Registry/Indexability Alignment

- Registry: `legal_review_status: pending`, `indexability: false`, `sitemap_required: false`
- Built HTML: `noindex, follow`; `/privacy` excluded from sitemap manifest
- Canonical: `https://skeldir.com/privacy` present

## 11. Proof-Link Graph

```bash
grep -E 'href="/security"|href="/methodology"|href="/revenue-verification"|href="/trust-envelope"|href="/ai-boundary"|href="/gdpr"' out/privacy.html
# → all six links present (PASS)
```

## 12. Discoverability Regression

| Harness | Result |
|---|---|
| `npm run build` | **PASS** |
| `npm run discoverability:d5` (skip-build) | **PASS** — 73/0 |
| `npm run discoverability:d6` (skip-build) | **PASS** — 136/0; gate **6o** |
| `npm run discoverability:d6:negative-controls` | **PASS** — 37/0 |
| `npm run discoverability:d5:negative-controls` | **PASS** |
| `npm run discoverability:d2` | **PASS** — 57/0 |

## 13. Verdict

**PASS**
