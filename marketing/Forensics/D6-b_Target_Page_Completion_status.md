# D6-b Target Page Completion — /status

## 1. Source Copy Used

- `c:\Users\ayewhy\Downloads\YMYL Content\skeldir-status -v1.md` (implemented with D6-b designed-absence reframing in `marketing/src/app/status/page.tsx`)

## 2. Files Changed

| File | Change | Reason |
|---|---|---|
| `src/app/status/page.tsx` | Replaced noindex placeholder | Designed-absence status page aligned to registry |
| `discoverability.status-registry.json` | **New** | Machine-readable operational state + approved claims |
| `STATUS_SURFACE_REGISTRY.md` | **New** | Human-readable registry mirror |
| `scripts/discoverability/lib/d6-status-exposure.mjs` | **New** | D6-b placeholder/overclaim/registry gates |
| `discoverability.sitemap-manifest.json` | Updated | Added `/status` |
| `discoverability.routes.json` | Updated | Indexable + sitemap + JSON-LD |
| `scripts/discoverability/lib/d2-crawl-graph.mjs` | Updated | Removed `/status` from noindex + sitemap forbidden sets |
| `scripts/discoverability-d6-harness.mjs` | Updated | Gate **6k** |
| `scripts/discoverability-d6-negative-controls.mjs` | Updated | NC-D6-26/27 |

## 3. Designed-Absence Treatment

| Source concept | Final public framing | Placeholder risk removed? |
|---|---|---|
| fully operational | No active incidents / no degradations currently reported | **yes** |
| no active incidents | Explicit: No active incidents are currently reported | **yes** |
| manually verified status | Manually verified public status declaration; not automated real-time feed | **yes** |
| direct operator communication | Affected operators + support@skeldir.com | **yes** |
| service scope | Operator-facing reconciliation, ingestion, trust-output availability | **yes** |

## 4. Operational Claim Registry

- **Registry path:** `marketing/discoverability.status-registry.json`
- **Approved operational claims:** no active incidents; no service degradations currently reported; manual status declaration; not an automated real-time feed; affected operators; scheduled maintenance
- **Status update mode:** `manual`
- **Active incidents:** _(none)_
- **Scheduled maintenance:** _(none)_
- **Owner:** Skeldir Infrastructure
- **Last reviewed:** 2026-02-25

## 5. Static HTML Proof

From `marketing/out/status.html`:

```html
<h1>Status</h1>
<h2>Key facts</h2>
<h2>Current status</h2>
<h2>Active incidents</h2>
<p>No active incidents are currently reported.</p>
<h2>Scheduled maintenance</h2>
<p>No scheduled maintenance is currently listed.</p>
<h2>How operational events are communicated</h2>
<p>manually verified … not an automated real-time</p>
<h2>Report an issue</h2>
<p>support@skeldir.com</p>
<p>Last updated: February 2026</p>
```

## 6. Placeholder Theater Scan

```bash
grep -Ei "placeholder|coming soon|technical_disclosure_only" out/status.html
# → no matches (PASS)
```

## 7. Operational Overclaim Scan

```bash
grep -Ei "fully operational|all systems operational|processing normally|99\\.9|SLA|uptime guarantee" out/status.html
# → no matches (PASS)
```

## 8. Link Graph

- `/security` ✓
- `/privacy` ✓
- `/methodology` ✓
- `/trust-envelope` ✓
- `/docs` ✓

## 9. Discoverability Regression

| Harness | Result |
|---|---|
| `npm run build` | **PASS** |
| `npm run discoverability:d2` (skip-build) | **PASS** — `/status` in sitemap |
| `npm run discoverability:d6` (skip-build) | **PASS** — 125/0; gate **6k** |
| `npm run discoverability:d6:negative-controls` | **PASS** — 29/0 |

## 10. Verdict

**PASS**
