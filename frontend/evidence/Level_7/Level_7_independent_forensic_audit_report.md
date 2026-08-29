# Independent Audit Report — Level 7 Primary Tables and Ledger Surfaces Iteration III

**Audit type:** Adversarial forensic independent audit — Level 7 Pass III (corrective-action forensic re-audit)  
**Repository:** `c:\Users\ayewhy\Frontend_4\skeldir-ui`  
**Audit date:** 2026-06-29  
**Directive:** Context-Robust Hypothesis-Anchored Independent Audit Directive — Level 7 Iteration III Corrective-Action Forensic Re-Audit  
**Auditor posture:** Implementation evidence pack treated as unverified hypotheses; all claims independently reproduced or refuted  

---

## 1. Final Verdict

**ACCEPT**

```
PHASE STATUS:  COMPLETE
ADVANCEMENT:   PERMITTED to Level 8 planning
```

---

## 2. Verdict Rationale

All four Pass II blockers (F-L7-II-BLOCKER-01 through F-L7-II-BLOCKER-04) are independently remediated with **mounted router behavioral proof**, not parser-only or source-string substitutes. `npm run audit:level7` exits **0**. Level 7 harness **70/70**; composite **257/257**. Pass I/II substrate remains green: six route shells, trust index authority table, confidence/benchmark component tests, 10k/50k request invariance, negative scope **50/0**, secret scan **336/0** including `evidence/Level_7/`, **32** PNG visual artifacts.

Iteration III adds `level7.helpers.tsx` with `createClaimsShellRouter`, `setMobileViewport375`, and mounted `RouterProvider` tests proving filter/sort/pagination→URL mutation, Back/Forward restoration, deep-link hydration, return-from-L8-blocked-detail query preservation, filter keyboard→URL+rows, pagination Space→URL, mounted out-of-order safety via `setClaimsListDelayBySourceForTests`, query-transition disabling controls, and 375px `matchMedia` mobile path with keyboard disclosure. Vacuous parallel-client out-of-order test removed.

All 12 Iteration III exit gates pass. Minor count deltas vs evidence pack (scope 50 vs 46, secret 336 vs 332, source integrity 30 vs 31) are non-blocking reproducibility observations. Conditional acceptance is forbidden; none is warranted.

---

## 3. Local Environment

| Field | Value |
|-------|-------|
| Repo path | `c:\Users\ayewhy\Frontend_4\skeldir-ui` |
| Node | v22.22.0 |
| npm | 11.6.2 |
| OS | Windows 10.0.26200 |
| Router | `react-router-dom` v7 (`createMemoryRouter` + `RouterProvider` in behavioral tests) |

### Commands executed

| Command | Exit | Result |
|---------|------|--------|
| `npm run audit:level7` (full composite) | **0** | Build + L0–L6 regression + L7 scope + **257/257** tests + **32** PNG capture |
| `npx vitest run src/test/level7.harness.test.tsx` | 0 | **70/70** pass |
| `npx vitest run` (L1–L7 harness files) | 0 | **257/257** pass |
| `runLevel7NegativeScopeScan()` (independent) | — | **50** files, **0** violations |
| `runSecretScan()` (independent) | — | **336** files, **0** violations |
| `runLevel7IntegrityProbes()` (independent) | — | **4/4** pass |
| `runLevel7SourceIntegrityProbes()` (independent) | — | **30/30** pass |
| PNG count on disk | — | **32** in `evidence/Level_7/visual/` |

---

## 4. Corrective Blocker Review

### F-L7-II-BLOCKER-01 — URL navigation behaviors untested

| Field | Value |
|-------|-------|
| **Prior blocker** | No Back/Forward, filter→URL, refresh/deep-link, or return-from-detail behavioral tests |
| **Claimed remediation** | CA-L7-III-01–04: `level7.helpers.tsx` + router describe block |
| **Independent result** | **Remediated.** Mounted tests: `filter change mutates router search query`; `sort change mutates router search query`; `pagination Enter mutates router search offset`; `history back restores claims query state A`; `history forward restores claims query state B`; `deep-link initialization hydrates controls rows and query metadata`; `return from blocked detail preserves ledger query params`. All assert `router.state.location.search` and control values via `RouterProvider`. |

### F-L7-II-BLOCKER-02 — Out-of-order response safety unproven

| Field | Value |
|-------|-------|
| **Prior blocker** | Vacuous parallel `listClaims` client test; no hook/page integration |
| **Claimed remediation** | CA-L7-III-05–06: `setClaimsListDelayBySourceForTests`; mounted page test; transition guard test |
| **Independent result** | **Remediated.** `mounted claims page ignores late stale response when filter changes quickly`: meta_ads delayed 450ms → switch google_ads → wait 550ms → URL and row cells remain google_ads. `query transition disables pagination and detail affordances while updating`: `[data-ledger-updating]` + disabled Next/detail during delay. Vacuous parallel-client test **removed**. Hook retains `activeQueryKeyRef` + `AbortController`. |

### F-L7-II-BLOCKER-03 — 375px viewport not constrained in harness

| Field | Value |
|-------|-------|
| **Prior blocker** | Component tests at default jsdom width only |
| **Claimed remediation** | CA-L7-III-07: `setMobileViewport375()` matchMedia mock |
| **Independent result** | **Remediated.** `375px viewport activates mobile ledger path with keyboard disclosure`: `innerWidth=375`, `matchMedia('max-width: 767px').matches=true`, `[data-ledger-mobile]` + `[data-compact-ledger-row]`, disclosure Enter, blocked-detail Enter, no `[data-level8-blocked-route]` leak. |

### F-L7-II-BLOCKER-04 — Filter and pagination keyboard gaps

| Field | Value |
|-------|-------|
| **Prior blocker** | Filter label only; pagination click-only |
| **Claimed remediation** | CA-L7-III-08–10: Tab-to-filter + selectOptions; Enter/Space pagination |
| **Independent result** | **Remediated.** Component: `pagination previous/next keyboard Enter and Space activation`. Router: `pagination keyboard Space changes URL offset on mounted page`. Filter: `filter keyboard operation updates URL and rows` (Tab to claim-source combobox + selectOptions → URL + row cells). Blocked detail: Enter activation retained. |

---

## 5. Gate Results

| Gate | Result | Evidence | Failure reason |
|------|--------|----------|----------------|
| 01 — Composite Reproduction | **PASS** | `audit:level7` exit 0; 70/70 L7; 257/257 composite; 32 PNG | — |
| 02 — Existing Substrate Preservation | **PASS** | Six shells, trust authority, confidence/benchmark, 10k/50k, L0–L6 green | — |
| 03 — URL Mutation and Canonical Query State | **PASS** | Mounted filter/sort/pagination→`location.search` tests | — |
| 04 — Navigation Persistence | **PASS** | Back/Forward, deep-link init, return-from-L8-blocked tests | — |
| 05 — Out-of-Order Response Safety | **PASS** | Mounted delay-by-source test; URL+rows remain B after A late | — |
| 06 — Query Transition Safety | **PASS** | Updating banner; disabled pagination/detail during transition | — |
| 07 — 375px Responsive Ledger Behavior | **PASS** | `setMobileViewport375` + matchMedia + mobile path keyboard tests | — |
| 08 — Keyboard Accessibility | **PASS** | Enter/Space pagination; Tab+filter; Enter detail/disclosure | — |
| 09 — Negative Scope | **PASS** | Scope 50/0; L8 blocked; L9 disabled | — |
| 10 — Privacy/Secret/Evidence Safety | **PASS** | `evidence/Level_7` in SCAN_ROOTS; 336/0 | — |
| 11 — Non-Vacuous Harness | **PASS** | 30 source integrity + 4 integrity probes; sabotage on trust omission | — |
| 12 — Evidence Pack Reproducibility | **PASS** | 70/70, 257/257, 32 PNG reproduce | Scope 50 vs claimed 46; secret 336 vs 332; integrity 30 vs 31 (non-blocking) |

**Gate tally:** 12 PASS · 0 FAIL · 0 INCONCLUSIVE — BLOCKING

---

## 6. Hypothesis Results

| Hypothesis | Result | Evidence | Risk |
|------------|--------|----------|------|
| H-AUDIT-L7-III-01 — Composite proof green | **Confirmed** | exit 0; 257/257; 32 PNG | False completion |
| H-AUDIT-L7-III-02 — Substrate intact | **Confirmed** | L0–L6 green; Pass I/II regressions in harness | Regression |
| H-AUDIT-L7-III-03 — Router URL mutation behavioral | **Confirmed** | Mounted filter/sort/pagination URL tests | Parser-only proof |
| H-AUDIT-L7-III-04 — Back/Forward restores state | **Confirmed** | `router.navigate(-1)` / `navigate(1)` + control assertions | Memory-only state |
| H-AUDIT-L7-III-05 — Deep-link initialization | **Confirmed** | Complex URL → controls + `[data-query-id]` + rows | Unit parser only |
| H-AUDIT-L7-III-06 — Return from blocked detail | **Confirmed** | History stack ledger→detail→back preserves search | Query loss |
| H-AUDIT-L7-III-07 — Out-of-order mounted UI | **Confirmed** | Delayed meta_ads; google_ads wins after 550ms | Client-only test |
| H-AUDIT-L7-III-08 — Query transition non-authoritative | **Confirmed** | Updating banner; disabled controls; stale CSS | Interactive stale rows |
| H-AUDIT-L7-III-09 — 375px mobile constrained | **Confirmed** | matchMedia mock at 375px; mobile DOM + keyboard | Screenshot-only |
| H-AUDIT-L7-III-10 — Keyboard accessibility | **Confirmed** | Enter/Space pagination; Tab+filter; Enter affordances | Click-only |
| H-AUDIT-L7-III-11 — Negative scope intact | **Confirmed** | Scope clean; L8/L9 blocked | Leakage |
| H-AUDIT-L7-III-12 — Privacy/secret boundary | **Confirmed** | 336 files / 0 violations | Evidence exclusion |
| H-AUDIT-L7-III-13 — Harness non-vacuous III | **Confirmed** | 30 source probes; behavioral test strings in harness | Shallow sabotage |

---

## 7. Existing Substrate Preservation Evidence

| Control | Pass I/II artifact | Iteration III status |
|---------|-------------------|----------------------|
| Six parent routes | `LedgerRoutes.tsx` + shell `it.each` | **Green** |
| Trust index authority | `TrustEnvelopeIndexTable` | **Green** — source probes + shell test |
| ConfidenceCell / BenchmarkCell | Component harness tests | **Green** — retained |
| 10k/50k request bounds | Four harness tests | **Green** |
| Query canonicalizer | `parseCanonicalClaimsQuery` unit tests | **Green** — retained |
| Blocked L8 detail | `data-level8-blocked-route` | **Green** |
| Six-surface permission_denied | billing_only matrix | **Green** |
| L0–L6 regression | Composite audit stages | **Green** |

---

## 8. Router URL Mutation Evidence

| Interaction | Test | Assertion |
|-------------|------|-----------|
| Filter change | `filter change mutates router search query` | `routerSearch(router).contains('claimSource=meta_ads')`; combobox value |
| Sort change | `sort change mutates router search query` | `sort=discrepancy&sortDir=desc` in search |
| Pagination | `pagination Enter mutates router search offset` | `{Enter}` on Next → `offset=25` |
| Filter keyboard + rows | `filter keyboard operation updates URL and rows` | Tab to combobox; selectOptions → URL + `meta_ads` in table cells |

All tests mount `AppShellRoutes` under `createMemoryRouter` + `RouterProvider` — not parser isolation.

---

## 9. Back/Forward Evidence

| Step | Test | Result |
|------|------|--------|
| A → meta_ads | `history back restores claims query state A` | selectOptions meta_ads → URL contains meta_ads |
| B → google_ads | Same test continues | selectOptions google_ads → URL contains google_ads |
| Back to A | `router.navigate(-1)` | URL + combobox restore meta_ads |
| Forward to B | `history forward restores claims query state B` | `router.navigate(1)` → google_ads restored |

---

## 10. Deep-Link / Refresh-Style Initialization Evidence

| Control | Test | Result |
|---------|------|--------|
| Complex URL load | `deep-link initialization hydrates controls rows and query metadata` | URL: `claimSource=meta_ads&verificationStatus=partial&sort=discrepancy&sortDir=desc&offset=25&pageSize=25` |
| Control hydration | Same | claimSource, verification, sort combobox values match |
| Query metadata | Same | `[data-query-id]` present |
| Rows rendered | Same | `waitForClaimsTableRows()` pass |
| No raw error | Same | No schema_invalid/query_invalid text |

Refresh-style behavior is equivalent to direct navigation to bookmarked URL — covered by this mounted initialization test.

---

## 11. Return-from-Blocked-Detail Evidence

| Step | Test | Result |
|------|------|--------|
| Start | `return from blocked detail preserves ledger query params` | Initial index 1 at `/app/claims/claim_0001` with ledger URL in history |
| Blocked panel | Same | `[data-level8-blocked-route]` present |
| Back | `router.navigate(-1)` | pathname `/app/claims`; search retains `claimSource=meta_ads&sort=discrepancy` |
| Controls restored | Same | claimSource combobox `meta_ads`; table rows render |

---

## 12. Query Transition Evidence

| Control | Test | Result |
|---------|------|--------|
| Updating banner | `shows updating banner when table is in transition` | `[data-ledger-updating]` + `aria-live="polite"` |
| Pagination disabled | Same + transition test | Next page disabled during `updating` |
| Detail disabled | Same | Blocked detail affordance disabled |
| Stale row dimming | Source | `.staleRows` CSS + `pointer-events: none` on claims/trust tables |
| Live transition | `query transition disables pagination and detail affordances while updating` | meta_ads delay 600ms → updating banner → controls disabled → clears after resolve |

---

## 13. Out-of-Order Response Evidence

| Scenario step | Test implementation | Result |
|---------------|---------------------|--------|
| Query A (meta_ads) starts delayed | `setClaimsListDelayBySourceForTests({ meta_ads: 450 })` | Delay injected in client before query |
| Query B (google_ads) starts | Rapid `selectOptions` google_ads after meta_ads | URL switches to google_ads |
| B resolves first | `waitFor` URL + google_ads cells | UI shows google_ads |
| A resolves late (+550ms) | `setTimeout(550)` after B visible | URL still google_ads; search does not contain meta_ads |
| Rows remain B | Cell text assertion | No meta_ads-only authoritative rows |
| Detail re-enabled | After settle | Detail button not disabled |

Hook guard: `useClaimsLedger` lines 63–65 ignore responses when `activeQueryKeyRef.current !== requestKey` or aborted.

---

## 14. 375px Mobile Ledger Evidence

| Control | Method | Result |
|---------|--------|--------|
| Viewport constraint | `setMobileViewport375()` — width 375, height 812 | **PASS** |
| matchMedia mobile | `window.matchMedia('(max-width: 767px)').matches === true` | **PASS** |
| Mobile path active | `[data-ledger-mobile]` + `[data-compact-ledger-row]` | **PASS** |
| Disclosure keyboard | Enter on "Show additional row fields" → `aria-expanded=true` | **PASS** |
| Blocked detail keyboard | Enter on detail affordance → Level 8 copy | **PASS** |
| No L8 leak | `[data-level8-blocked-route]` falsy after mobile interaction | **PASS** |
| Component-level compact row | Prior Iteration II identity/label/disclosure tests | **PASS** — retained |

---

## 15. Keyboard Accessibility Evidence

| Requirement | Test | Method |
|-------------|------|--------|
| Pagination Enter | `pagination previous/next keyboard Enter and Space activation` | `{Enter}` on Next → `onNext` called |
| Pagination Space | Same + router test | `{Space}` / `' '` on Previous → URL offset cleared |
| Filter Tab + change | `filter keyboard operation updates URL and rows` | Tab until combobox focused; selectOptions |
| Blocked detail Enter | `blocked future detail keyboard activation` | Enter → Level 8 explanation |
| Compact disclosure Enter | `disclosure toggles via keyboard` + 375px test | Enter toggles expanded |
| Updating announced | `shows updating banner when table is in transition` | `role="status"` + `aria-live="polite"` |

---

## 16. Negative Scope Evidence

| Surface class | In L7 product code? |
|---------------|---------------------|
| Detail screens | Blocked shells only (`Level8BlockedDetailPage`) |
| Export / verify / copy API | Absent — scope + sabotage clean |
| Budget proposal / exception actions | Disabled buttons only |
| Command Center | Absent — shell tests assert no heading |
| Billing recovery | Redirect guard blocked |
| L7 scope scan | **50 files, 0 violations** |

---

## 17. Privacy / Secret / Evidence Safety

| Field | Value |
|-------|-------|
| Scan roots | `src/`, `evidence/Level_4/` through `Level_7/`, `scripts/` |
| Files scanned | **336** |
| Violations | **0** |
| Evidence self-scan | Level 7 pack and visual index included |

---

## 18. Visual Evidence

| Field | Value |
|-------|-------|
| Artifact count | **32** PNG |
| Viewports | mobile (375), tablet (768), desktop (1280), wide (1440) |
| Post-III specimens | trust-index-loaded authority-labeled; claims-loaded with query meta |

Visual support supplements behavioral gates; behavioral tests are primary proof for Pass III.

---

## 19. Prior Phase Regression Evidence

| Phase | Result |
|-------|--------|
| Level 0 | 36/36; tokens 210/0; financial 114/0 |
| Level 1 | Scope clean |
| Level 2 | Scope clean |
| Level 3 | Scope + privacy clean |
| Level 4 | Scope + secret clean |
| Level 5 | Scope 51/0 |
| Level 6 | Scope 21/0; 38/38 harness |

---

## 20. Harness Non-Vacuousness Evidence

### Runtime integrity probes — 4/4 PASS

Global sort, 50k DOM bound, request bounded, forbidden list fields.

### Source integrity probes — 30/30 PASS

Trust index authority (5), six-route shells (4), 10k/50k (2), behavioral harness markers (11), hook/query guards (3), transition guard (1), plus pagination/confidence/benchmark/mobile markers.

Evidence pack claimed 31/31; independent count **30** — all pass on clean tree.

### String sabotage

Injected sample triggers ≥5 detectors; trust-index omission triggers `trust-index-missing-financial-value` and `trust-index-missing-confidence-cell`; clean tree 0 triggered.

---

## 21. Critical Findings

No blockers remain. Non-blocking observations:

### OBS-L7-III-01 — Scan/probe count deltas vs evidence pack

| Field | Value |
|-------|-------|
| **Severity** | Informational |
| **Evidence** | Scope **50** vs claimed 46; secret **336** vs claimed 332; source integrity **30** vs claimed 31 |
| **Consequence** | None — all scans 0 violations; all probes pass |

### OBS-L7-III-02 — Dedicated browser refresh (F5) not isolated

| Field | Value |
|-------|-------|
| **Severity** | Informational |
| **Evidence** | Deep-link initialization test covers refresh-equivalent URL hydration; no separate `location.reload()` test |
| **Consequence** | None — router re-mount from URL is the same initialization path |

---

## 22. Completion Determination

Level 7 is **empirically complete** under the Iteration III corrective-action standard.

The existing ledger substrate remains intact across Pass I, II, and III. All six parent surfaces are guarded, shell-tested, state-tested, query-correct, and authority-labeled. URL-persistent query state is proven through mounted `RouterProvider` behavior. Back/Forward, deep-link initialization, and return-from-blocked-detail preserve ledger context. Query transitions prevent stale rows from appearing authoritative. Out-of-order responses cannot overwrite newer results through mounted page flow with source-keyed delay injection. 375px mobile behavior is proven under `matchMedia` constraint. Filters, pagination, and row/detail affordances are keyboard-operable. No Level 8/9/10 surfaces leak. Levels 0–6 remain green.

```
PHASE STATUS:  COMPLETE
ADVANCEMENT:   PERMITTED
```

---

## 23. Required Remediation Before Acceptance

Not applicable — verdict is **ACCEPT**.

---

*End of independent forensic audit — Level 7 Pass III.*
