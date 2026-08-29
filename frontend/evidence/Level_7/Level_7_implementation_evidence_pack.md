# Level 7 Implementation Evidence Pack

**Directive:** CRHAID Level 7 — Primary Tables and Ledger Surfaces  
**Corrective directive:** II CRHACAD Level 7 — Primary Tables and Ledger Surfaces (Iteration III)  
**Implementation root:** `c:\Users\ayewhy\Frontend_4\skeldir-ui`  
**Evidence cut:** 2026-06-28  
**Composite gate command:** `npm run audit:level7`

---

## 1. Final Verdict

**COMPLETE — Iteration III (II CRHACAD targeted remediation)**

Level 7 Pass I established six parent ledger routes, shared `ledger/` infrastructure, composite row DTOs, server-side query semantics, DOM/request bounds, claims reference implementation, Level 8 blocked detail UX, and L0–L6 regression safety. Pass I independent audit **REJECTED** six surface/substrate blockers. Iteration II closed those blockers (trust index authority, six-route shells, confidence/benchmark behavioral proof, 10k/50k bounds, URL canonicalizer, stale-row UI, 60-test harness).

Pass II independent audit **REJECTED** four behavioral-proof gaps: router URL navigation, out-of-order hook integration, 375px viewport constraint, and filter/pagination keyboard operations. Iteration III adds mounted router behavioral tests, claim-source delay injection for out-of-order proof, `matchMedia` 375px shim, and keyboard-first pagination/filter tests — without rebuilding Pass I/II substrate.

Falsifiable validation: `npm run audit:level7` exit **0** on 2026-06-28 after Iteration III remediation.

| Metric | Pass I | Iteration II | Iteration III |
|--------|--------|--------------|---------------|
| L7 harness tests | 19/19 | 60/60 | **70/70** |
| Composite harness (L1–L7 + redirectGuard) | 206/206 | 247/247 | **257/257** |
| L7 scope scan | 46 / 0 | 46 / 0 | **46 / 0** |
| Secret scan (incl. `evidence/Level_7/`) | 330 / 0 | 332 / 0 | **332 / 0** |
| Source integrity probes | — | 20/20 | **31/31** |
| Visual PNGs | 32 | 32 | **32** (regenerated) |
| Integrity probes (clean tree) | 4/4 | 4/4 | **4/4** |

**Level 8 advancement:** Permitted only after independent review confirms Pass II blockers F-L7-II-BLOCKER-01 through 04 are closed.

---

## 2. Independent Audit Intake (Pass II REJECT)

**Source:** `evidence/Level_7/Level_7_independent_forensic_audit_report.md`  
**Verdict:** REJECT — advancement to Level 8 prohibited until behavioral gates 05, 06, 09, 10 close.

### 2.1 Pass II blockers mapped to Iteration III corrective actions

| Blocker ID | Finding | CA | Remediation artifact |
|------------|---------|-----|----------------------|
| F-L7-II-BLOCKER-01 | URL navigation behaviors untested | CA-L7-III-01–04 | `level7.helpers.tsx` + router describe block: filter/sort/pagination→URL, Back/Forward, deep-link init, return-from-L8-blocked |
| F-L7-II-BLOCKER-02 | Out-of-order response safety unproven | CA-L7-III-05–06 | `setClaimsListDelayBySourceForTests`; mounted page test; transition guard test |
| F-L7-II-BLOCKER-03 | 375px viewport not constrained in harness | CA-L7-III-07 | `setMobileViewport375()` matchMedia mock + mobile disclosure/affordance keyboard |
| F-L7-II-BLOCKER-04 | Filter/pagination keyboard gaps | CA-L7-III-08–10 | Tab-to-filter + selectOptions; Enter/Space pagination (component + router) |
| Sabotage lag (Pass II) | CA-L7-III-11 | `runLevel7SourceIntegrityProbes` expanded to **31** behavioral string guards |

### 2.2 Pass I blockers (Iteration II — closed, retained)

All F-L7-BLOCKER-01 through 06 and URL/stale follow-ups remain green under Iteration III regression. No Pass I remediation was reverted.

---

## 3. Semantic Internalization (Level 7 Physics)

Level 7 parent ledger surfaces are **read-only truth inspection tables** — not detail screens, not Level 9 action hosts. System physics invariants:

1. **URL is authoritative query state** for claims — filters, sort, offset must round-trip through `location.search`, survive Back/Forward, deep-link, and return-from-blocked-detail.
2. **Server-side query semantics** — global sort/filter before pagination; DOM capped at `MAX_DOM_TABLE_ROWS`; request count bounded at 10k/50k.
3. **Financial authority separation** — verified revenue is deterministic; platform claims are labeled; confidence/benchmarks are shaped or explicitly unavailable — never naked scalars.
4. **Query transition truth** — during `updating`, stale rows are non-authoritative (dimmed, `pointer-events: none`, disabled pagination/detail).
5. **Out-of-order safety** — late responses for superseded query keys must not mutate UI or URL.
6. **375px mobile path** — compact rows with label/value association and keyboard-operable disclosure; Level 8 detail remains blocked.

Iteration III closes the gap between *implemented* invariants (Pass II source) and *behaviorally proven* invariants (Pass II audit rejection).

---

## 4. Root-Cause Determinations (Iteration III)

| RC | Hypothesis | Result | Disposition |
|----|------------|--------|-------------|
| RC-L7-III-01 | Parser tests substitute for router physics | **CONFIRMED** | Mounted `createMemoryRouter` behavioral suite added |
| RC-L7-III-02 | Parallel client calls prove hook safety | **CONFIRMED** | Vacuous test replaced with page + `setClaimsListDelayBySourceForTests` |
| RC-L7-III-03 | Mobile DOM presence implies 375px path | **CONFIRMED** | `matchMedia` mock at 375px width in harness |
| RC-L7-III-04 | Click pagination satisfies keyboard gate | **CONFIRMED** | Enter/Space tests at component and router levels |
| RC-L7-III-05 | Integrity probes lagged behavioral markers | **CONFIRMED** | 11 new source-integrity string guards |

---

## 5. Local Environment

| Field | Value |
|-------|-------|
| OS | Windows 10.0.26200 |
| Node | via project `package.json` toolchain |
| Package manager | npm |
| Browser (visual) | Playwright Chromium |
| Dev server port (L7 visual) | 5203 |

---

## 6. Commands Executed (Iteration III)

```text
npm run audit:level7
```

Decomposed stages (all **PASS**, exit 0):

```text
npm run build
npm run audit:level0          → tokens 210/0, scope 26/0, financial 114/0, harness 36/36
npm run audit:level1:scope    → 26 / 0
npm run audit:level2:scope    → 39 / 0
npm run audit:level3:scope    → 59 / 0
npm run audit:level3:privacy  → 54 / 0
npm run audit:level4:scope    → 49 / 0
npm run audit:level4:secret   → 332 / 0
npm run audit:level5:scope    → 51 / 0
npm run audit:level6:scope    → 21 / 0
npm run audit:level7:scope    → 46 / 0
vitest run L1–L7 harness     → 257/257 pass (70 L7)
npm run evidence:visual:level7 → 32 PNGs
```

---

## 7. Files Changed (Iteration III delta)

| Area | Files |
|------|-------|
| Router test helpers | `src/test/level7.helpers.tsx` (new) — `createClaimsShellRouter`, `setMobileViewport375`, `waitForClaimsTableRows` |
| Delay injection | `src/claims/claimsClient.ts` — `setClaimsListDelayBySourceForTests` keyed by `claimSource` |
| Harness | `src/test/level7.harness.test.tsx` — **10 new tests** (60 → **70**); vacuous parallel-client test **removed** |
| Integrity | `src/audit/level7NegativeScopeScan.ts` — 11 new `runLevel7SourceIntegrityProbes` behavioral guards |

Pass I/II substrate unchanged except delay hook extension.

---

## 8. Router URL Behavioral Evidence (CA-L7-III-01–04)

| Behavior | Test | Method | Result |
|----------|------|--------|--------|
| Filter → URL | `filter change mutates router search query` | `createMemoryRouter` + `selectOptions` → `router.state.location.search` | **PASS** |
| Sort → URL | `sort change mutates router search query` | Sort combobox → `sort=discrepancy&sortDir=desc` | **PASS** |
| Pagination → URL | `pagination Enter mutates router search offset` | Focus Next + `{Enter}` → `offset=25` | **PASS** |
| Back restores A | `history back restores claims query state A` | A=meta_ads → B=google_ads → `navigate(-1)` | **PASS** |
| Forward restores B | `history forward restores claims query state B` | `navigate(1)` after back | **PASS** |
| Deep-link init | `deep-link initialization hydrates controls rows and query metadata` | Complex URL → control values + `[data-query-id]` + rows | **PASS** |
| Return from L8 blocked | `return from blocked detail preserves ledger query params` | History stack ledger→detail→back | **PASS** |

**Adversarial note:** Parser unit tests alone cannot satisfy this gate; all above mount `AppShellRoutes` under `RouterProvider`.

---

## 9. Out-of-Order / Transition Safety Evidence (CA-L7-III-05–06)

| Control | Test | Result |
|---------|------|--------|
| Mounted out-of-order | `mounted claims page ignores late stale response when filter changes quickly` | meta_ads delayed 450ms → switch google_ads → wait 550ms → URL and rows remain google_ads | **PASS** |
| Updating banner + SR | `shows updating banner when table is in transition` | `[data-ledger-updating]` + `aria-live="polite"` | **PASS** |
| Pagination disabled | Same + `query transition disables pagination and detail affordances while updating` | Next page + detail buttons disabled during delay | **PASS** |
| Detail disabled | `disabled` on affordance during `updating` | **PASS** |
| Vacuous client test | Parallel `Promise.all` on client | **REMOVED** |

Delay hook: `setClaimsListDelayBySourceForTests({ meta_ads: N })` exercises `useClaimsLedger` + `activeQueryKeyRef` + `AbortController` through the real page flow.

---

## 10. 375px Mobile Evidence (CA-L7-III-07)

| Control | Method | Result |
|---------|--------|--------|
| Viewport constraint | `setMobileViewport375()` — `innerWidth=375`, `matchMedia('max-width: 767px').matches=true` | **PASS** |
| Mobile path active | `375px viewport activates mobile ledger path with keyboard disclosure` | `[data-compact-ledger-row]` + disclosure Enter + blocked detail Enter | **PASS** |
| No L8 leak in disclosure | Assert no `[data-level8-blocked-route]` inside mobile disclosure | **PASS** |
| Component-level compact row | Prior Iteration II `CompactLedgerRow` tests retained | **PASS** |

---

## 11. Keyboard Accessibility Evidence (CA-L7-III-08–10)

| Requirement | Test | Result |
|-------------|------|--------|
| Pagination Enter/Space (component) | `pagination previous/next keyboard Enter and Space activation` | Focus + `{Enter}` / `{Space}` — not click | **PASS** |
| Pagination keyboard (router) | `pagination keyboard Space changes URL offset on mounted page` | Space on Previous → offset cleared | **PASS** |
| Filter Tab + change + URL | `filter keyboard operation updates URL and rows` | Tab until claim-source focused → `selectOptions` → URL + row source cells | **PASS** |
| Row affordance Enter | `blocked future detail keyboard activation` | Enter → Level 8 blocked copy | **PASS** |
| Updating announced | `role="status"` on `[data-ledger-updating]` | **PASS** |

---

## 12. Retained Iteration II Evidence (regression green)

The following remain **PASS** under Iteration III composite audit without regression:

- Six parent routes shell-tested (`/app/claims`, `/trust`, `/channels`, `/benchmarks`, `/exceptions`, `/budget`)
- Trust index authority rendering (`TrustEnvelopeIndexTable` — FinancialValue, ConfidenceCell, PolicyAuthorityPill, audit link, BlockedDetailAffordance)
- ConfidenceCell / BenchmarkCell behavioral states
- 10k/50k request-count bounds (claims + trust index)
- URL canonicalizer (`parseCanonicalClaimsQuery`) unit tests
- 14 sabotage detectors on injected samples
- 32 visual PNGs at 375/768/1024/1440

---

## 13. Negative-Scope / Privacy / Secret

| Scan | Violations |
|------|------------|
| Level 7 scope (46 files) | 0 |
| Financial | 0 |
| Token | 0 |
| Privacy (L3) | 0 |
| Secret (332 files incl. evidence) | 0 |

---

## 14. Sabotage-Control Evidence (CA-L7-III-11)

### 14.1 Integrity probes (clean tree)

`runLevel7IntegrityProbes()` — **4/4 PASS**

### 14.2 Source integrity probes (clean tree)

`runLevel7SourceIntegrityProbes()` — **31/31 PASS**

New behavioral guards (fail if removed from harness):

- `harness-url-mutation-behavioral`
- `harness-back-forward`
- `harness-deep-link-initialization`
- `harness-return-from-detail`
- `harness-out-of-order-hook-integration`
- `harness-375px-viewport`
- `harness-filter-keyboard`
- `harness-pagination-keyboard-router`
- `harness-row-enter-affordance`
- `harness-query-transition-guard`
- `harness-pagination-keyboard` (Enter/Space marker)

### 14.3 String sabotage

`runLevel7SabotageProbes(sabotage)` — ≥5 detectors on dirty sample; **0** on clean tree.

---

## 15. Adversarial Audit Methodology — Iteration III

### 15.1 Intake

1. Read II CRHACAD directive §7 CA-L7-III-01 through 11 and Pass II REJECT report blockers F-L7-II-BLOCKER-01–04.
2. Classify gaps as **behavioral proof** failures (implementation present, harness absent).
3. Preserve Pass I/II substrate; add only falsifiable mounted tests and integrity string guards.

### 15.2 Self-adversarial attacks performed

| Attack | Expected failure mode | Observed |
|--------|----------------------|----------|
| Remove router describe block | Source integrity probes 31→fail | **Detected** (probe strings) |
| Restore vacuous `Promise.all` client test | `harness-out-of-order-hook-integration` fails | **Detected** |
| Revert pagination to click-only | `harness-pagination-keyboard` fails | **Detected** |
| Remove 375px mock | `harness-375px-viewport` fails | **Detected** |
| Filter state in `useState` only (no URL) | `query-state-memory-only` sabotage fires | **PASS** (not present) |
| Rapid meta_ads→google_ads with delayed meta | UI shows google after meta resolves late | **PASS** (mounted test) |
| Navigate to L8 blocked detail and back | Query params preserved | **PASS** |
| Deep-link with invalid sort | Canonical redirect (Pass II) + deep-link hydration (III) | **PASS** |
| Run full `audit:level7` after changes | Exit 0 | **PASS** |

### 15.3 Independent audit anticipation

Pass II rejected because Gates **05** (375px), **06** (keyboard), **09** (URL navigation), **10** (out-of-order) lacked mounted proof. Iteration III maps each gate to at least one dedicated harness test and one source-integrity string guard. A reviewer removing any test without updating probes should fail `source integrity probes pass on clean tree` in the L7 harness.

---

## 16. Exit Gate Verdicts (Iteration III)

| Gate | Verdict | Evidence |
|------|---------|----------|
| EG-L7-1 Substrate preserved | **PASS** | §7, L0–L6 green |
| EG-L7-5 Responsive 375px physics | **PASS** | §10 |
| EG-L7-6 Interaction keyboard | **PASS** | §11 |
| EG-L7-9 URL navigation behaviors | **PASS** | §8 |
| EG-L7-10 Out-of-order / transition | **PASS** | §9 |
| EG-L7-11 Sabotage / integrity | **PASS** | §14 |
| EG-L7-12 Evidence reproducibility | **PASS** | §6, §17 |
| All Pass I/II gates | **PASS** | §12 (regression) |

---

## 17. Remaining Risks / Forward Obligations

| Item | Owner | Notes |
|------|-------|-------|
| HTTP transport for ledger APIs | B2.5+ | Mock clients; boundary validation preserved |
| Trust/channels filter URL parity | L7+ | Claims is reference for full URL canonicalizer |
| Level 8 detail screens | L8 | Routes remain blocked shells |
| Independent re-audit of Iteration III | Reviewer | Implementer evidence; third-party confirmation before L8 |

---

## 18. Reproduction

```bash
cd skeldir-ui
npm run audit:level7
```

Expected: build success; all scope/privacy/secret scans 0 violations; **257** harness tests pass (**70** Level 7); **31/31** source integrity probes; **32** visual PNGs in `evidence/Level_7/visual/`.

---

## 19. Evidence Self-Scan Confirmation

This pack uses placeholder identifiers only. No raw emails, IPs, tokens, or webhook payloads embedded. Reproducible via `npm run audit:level7` from `skeldir-ui/`.
