# D6-b Target Page Completion — /careers

## 1. Source Copy Used

- `c:\Users\ayewhy\Downloads\YMYL Content\skeldir-careers -v1.md` (implemented with D6-b public-safety reframing in `marketing/src/app/careers/page.tsx`)

## 2. Files Changed

| File | Change | Reason |
|---|---|---|
| `src/app/careers/page.tsx` | Replaced noindex placeholder | Talent-inquiry page, not a job board |
| `discoverability.careers-registry.json` | **New** | Hiring state + contact + schema policy |
| `CAREERS_SURFACE_REGISTRY.md` | **New** | Human-readable careers registry |
| `discoverability.public-contacts.json` | Updated | `careers` contact type → engineering@skeldir.com |
| `PUBLIC_CONTACT_REGISTRY.md` | Updated | Careers row documented |
| `scripts/discoverability/lib/d6-careers-exposure.mjs` | **New** | D6-b scanners + registry alignment |
| `discoverability.sitemap-manifest.json` | Updated | Added `/careers` |
| `discoverability.routes.json` | Updated | Active indexable route |
| `scripts/discoverability/lib/d2-crawl-graph.mjs` | Updated | Removed `/careers` from sitemap forbidden set |
| `scripts/discoverability-d6-harness.mjs` | Updated | Gate **6m** + Footer link checks |
| `scripts/discoverability-d6-negative-controls.mjs` | Updated | NC-D6-30/31 |

## 3. Public-Safety Changes

| Source concept | Final public framing | Mechanism/overclaim removed? |
|---|---|---|
| cryptographic signing and verification | integrity-preserving systems or verifiable records | **yes** |
| row-level security and tenant isolation | tenant-scoped systems and privacy-preserving architecture | **yes** |
| canonical serialization and hashing | canonical data handling and reproducible system behavior | **yes** |
| CI as adjudication | testable engineering workflows and falsifiable quality gates | **yes** |
| every direct inquiry reviewed | review relevant direct inquiries when aligned with needs | **yes** |
| direct engineering contact | engineering@skeldir.com via approved `careers` contact registry entry | **yes** |

## 4. Careers Registry

- **Registry path:** `marketing/discoverability.careers-registry.json`
- **Current hiring state:** `talent_inquiry_only`
- **Active roles count:** 0
- **Public roles:** _(none)_
- **Contact channel:** `engineering@skeldir.com`
- **Contact approved:** true
- **Last reviewed:** 2026-02-25
- **Owner:** Skeldir Engineering

## 5. Contact Registry

- **Registry path:** `marketing/discoverability.public-contacts.json`
- **Rendered contacts:** `engineering@skeldir.com` only
- **Approved contacts:** `careers` + `security_engineering` entries for same email
- **Unapproved contacts removed?:** yes

## 6. Static HTML Proof

From `marketing/out/careers.html`:

```html
<h1>Careers</h1>
<h2>Bottom Line Up Front</h2>
<h2>Key facts</h2>
<h2>What We Value</h2>
<h2>How We Hire</h2>
<h2>How to Express Interest</h2>
<h2>Scope and Trust Boundary</h2>
<h2>Contact</h2>
<p>engineering@skeldir.com</p>
<p>not a job board … no public roles …</p>
```

## 7. Placeholder Theater Scan

```bash
grep -Ei "placeholder|coming soon|technical_disclosure_only" out/careers.html
# → no matches (PASS)
```

## 8. Implementation Leakage Scan

```bash
grep -Ei "row-level security|RLS|cryptographic signing|canonical serialization|CI as adjudication" out/careers.html
# → no matches (PASS)
```

## 9. Hiring Overclaim Scan

```bash
grep -Ei "we are hiring|apply now|submit your resume|competitive salary|remote-first" out/careers.html
# → no matches (PASS)
```

## 10. JobPosting Schema Scan

```bash
grep -Ei "JobPosting|employmentType|baseSalary" out/careers.html
# → no matches (PASS)
```

## 11. Footer/Nav Link Proof

- `Footer.tsx`: `Careers` → `/careers` ✓
- `Careers` → `/resources` not present ✓

## 12. Discoverability Regression

| Harness | Result |
|---|---|
| `npm run build` | **PASS** |
| `npm run discoverability:d2` (skip-build) | **PASS** |
| `npm run discoverability:d6` (skip-build) | **PASS** — 132/0; gate **6m** |
| `npm run discoverability:d6:negative-controls` | **PASS** — 33/0 |

## 13. Verdict

**PASS**
