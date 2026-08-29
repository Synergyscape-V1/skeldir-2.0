# Level 8 Implementation Evidence Pack

**Directive:** CRHAID Level 8 — Detail Screens and Drawers  
**Corrective directive:** CRHACAD Level 8 — Detail Screens and Drawers (Iteration II)  
**Independent audit intake:** `evidence/Level_8/Level_8_independent_forensic_audit_report.md` (Pass I REJECT)  
**Implementation root:** `c:\Users\ayewhy\Frontend_4\skeldir-ui`  
**Evidence cut:** 2026-06-29  
**Composite gate command:** `npm run audit:level8`

---

## 1. Final Verdict

**COMPLETE — Iteration II (CRHACAD targeted behavioral remediation)**

Pass I established a credible Level 8 substrate (real routes, typed DTOs, five detail surfaces, L9 blocked affordances, L0–L7 regression green). Pass I independent audit **REJECTED** seven exit gates for lack of **mounted behavioral proof** (state matrix breadth, multi-surface parent context, 375px coverage, drawer focus trap, JSON boundedness/search, stale-detail safety, budget blocked-submit harness).

Iteration II closes those gaps with mounted harness tests, bounded/virtualized JSON viewer, document-capture focus trap, canonical return links, and expanded sabotage/integrity probes — without rebuilding Pass I substrate.

Falsifiable validation: `npm run audit:level8` exit **0** on 2026-06-29 after Iteration II remediation.

| Metric | Pass I | Iteration II |
|--------|--------|--------------|
| L8 harness tests | 27/27 | **58/58** |
| Composite harness (L1–L8 + redirectGuard) | 284/284 | **315/315** |
| L7 harness (regression) | 70/70 | **70/70** |
| L8 scope scan | 31 / 0 | **31 / 0** |
| L8 source integrity probes | 13/13 | **23/23** |
| L8 runtime integrity probes | 5/5 | **5/5** |
| Visual PNGs | 28 | **28** (regenerated) |

---

## 2. Semantic Internalization (CRHACAD Physics)

Iteration II internalized that Level 8 completion requires **production-state behavioral proof**, not happy-path route activation alone.

### 2.1 Correct invariants enforced

1. **Detail state matrix** — every fail-closed state must render safe copy via `DetailStateView`; no raw backend errors; retry where applicable.
2. **Multi-surface parent context** — claims, trust, channel, and budget parent→detail→back must preserve route (and claims query where applicable).
3. **Direct deep-link safe return** — canonical parent `Link` href (`/app/claims`, `/app/trust`, etc.); never blind `navigate(-1)` without trusted `parentSearch` state.
4. **Drawer accessibility** — Tab/Shift+Tab wrap-around; background isolation; Escape close; focus restore to invoking row.
5. **375px all surface classes** — trust, channel, budget, exception drawer — not claims-only.
6. **Mounted workbench keyboard** — claim detail tabs (not isolated `Tabs` only); JSON viewer search/collapse keyboard.
7. **Bounded JSON inspection** — virtualized line window; full-model search index; oversize fallback; DOM node caps.
8. **Stale-detail safety** — late response for object A cannot overwrite active object B on mounted route.
9. **L9 deferral behavioral proof** — budget submit blocked affordance toast-only on click and keyboard.

---

## 3. Independent Audit Intake (Pass I REJECT)

**Source:** `evidence/Level_8/Level_8_independent_forensic_audit_report.md`  
**Verdict:** REJECT — 7 FAIL gates (08, 09, 10, 11, 12, 13, 16)

### 3.1 Blocker → corrective action mapping

| Blocker ID | Finding | CA | Iteration II artifact |
|------------|---------|-----|----------------------|
| F-L8-I-BLOCKER-01 | State matrix UI-thin (`not_found` only) | CA-L8-II-01 | `Detail state matrix (Iteration II)` describe — 9 mounted states |
| F-L8-I-BLOCKER-02 | Parent context claims-only | CA-L8-II-02 | Trust/channel/budget Back router tests |
| F-L8-I-BLOCKER-03 | 375px claims-only | CA-L8-II-04–06 | `375px multi-surface` describe — 4 surfaces |
| F-L8-I-BLOCKER-04 | Drawer focus trap absent | CA-L8-II-04–05 | `Drawer.tsx` document capture trap; queue focus-restore test |
| F-L8-I-BLOCKER-05 | Tab/JSON keyboard gaps | CA-L8-II-07, 09–10 | Mounted claim tab keyboard; JSON collapse keyboard |
| F-L8-I-BLOCKER-06 | Stale detail unproven | CA-L8-II-11 | `late claim A response` mounted router test |
| F-L8-I-BLOCKER-07 | Budget blocked submit source-only | CA-L8-II-13 | `Budget blocked submit` mounted test |

---

## 4. Root-Cause Determinations (Iteration II)

| RC | Hypothesis | Result | Disposition |
|----|------------|--------|-------------|
| RC-L8-II-01 | Happy-path routes mistaken for completion | **CONFIRMED** | 31 new mounted behavioral tests added |
| RC-L8-II-02 | Component tests substituted for workbench proof | **CONFIRMED** | Mounted claim tab + JSON keyboard tests |
| RC-L8-II-03 | Claims path over-proven vs other surfaces | **CONFIRMED** | Trust/channel/budget parent + 375px tests |
| RC-L8-II-04 | Async safeguards source-only | **CONFIRMED** | `setClaimDetailDelayByIdForTests` + mounted stale test |
| RC-L8-II-05 | L9 deferral scan-only for budget | **CONFIRMED** | Mounted blocked-submit toast test |
| RC-L8-II-06 | JSON viewer presentation not bounded subsystem | **CONFIRMED** | `jsonViewerBounds.ts`, virtualization, oversize fallback |
| RC-L8-II-07 | Return already canonical (Link not navigate(-1)) | **CONFIRMED** | Direct href tests added; no code change required |
| RC-L8-II-08 | Sabotage shallow vs CRHACAD risks | **CONFIRMED** | 12 new sabotage detectors; 10 new integrity probes |

---

## 5. Files Changed (Iteration II delta)

| Area | Files |
|------|-------|
| JSON bounds/search | `src/detail/jsonViewerBounds.ts`, `src/detail/jsonSearchIndex.ts` |
| JSON viewer | `src/components/detail/TrustEnvelopeJsonViewer/TrustEnvelopeJsonViewer.tsx` (+ CSS) |
| Drawer focus trap | `src/components/layout/Drawer/Drawer.tsx` |
| Tabs activation | `src/components/layout/Tabs/Tabs.tsx` (Arrow/Home/End activates tab) |
| Exception focus restore | `src/components/exceptions/ExceptionsQueuePage/ExceptionsQueuePage.tsx` |
| Channel bounded markers | `src/components/channels/ChannelDetailPage/ChannelDetailPage.tsx` |
| Claim client test hooks | `src/claims/claimDetailClient.ts` (delay-by-id, network_error, object_id_mismatch) |
| Harness | `src/test/level8.harness.test.tsx` — **31 new tests** (27 → **58**) |
| Integrity/sabotage | `src/audit/level8NegativeScopeScan.ts` — 23 source probes, 23 sabotage detectors |

Pass I substrate preserved unchanged except targeted enhancements above.

---

## 6. Commands Executed

```text
npm run audit:level8
```

Decomposed stages (all **PASS**, exit 0):

```text
npm run build
npm run audit:level0          → tokens 224/0, scope 27/0, financial 122/0
npm run audit:level1:scope    → 26 / 0
npm run audit:level2:scope    → 39 / 0
npm run audit:level3:scope    → 59 / 0
npm run audit:level3:privacy  → 76 / 0
npm run audit:level4:scope    → 49 / 0
npm run audit:level4:secret   → 373 / 0
npm run audit:level5:scope    → 51 / 0
npm run audit:level6:scope    → 21 / 0
npm run audit:level7:scope    → 67 / 0
npm run audit:level8:scope    → 31 / 0
vitest run L1–L8 harness     → 315/315 pass (58 L8, 70 L7)
npm run evidence:visual:level8 → 28 PNGs
```

---

## 7. Detail State Matrix Evidence (CA-L8-II-01)

| State | UI harness | Safe copy | Return link | Retry |
|-------|------------|-----------|-------------|-------|
| `permission_denied` | **PASS** | **PASS** | **PASS** | — |
| `schema_invalid` | **PASS** | **PASS** | **PASS** | — |
| `stale_version` | **PASS** | **PASS** | **PASS** | — |
| `corrupted_evidence` | **PASS** | **PASS** | **PASS** | — |
| `object_id_mismatch` | **PASS** | **PASS** | **PASS** | — |
| `network_error` | **PASS** | **PASS** | **PASS** | **PASS** (reload) |
| `scope_denied` | **PASS** | **PASS** | **PASS** | — |
| `long_loading` | **PASS** | long-loading copy | — | — |
| `not_found` | **PASS** (Pass I) | **PASS** | **PASS** | — |
| Trust `schema_invalid` | **PASS** | **PASS** | **PASS** | — |

Mechanism: `setClaimDetailTestMode` / `setTrustDetailTestMode('invalid_json')` / `setClaimDetailDelayForTests(2500)` with `data-detail-state` assertions.

---

## 8. Multi-Surface Parent Context (CA-L8-II-02)

| Flow | Proof |
|------|-------|
| Claims filtered ledger → detail → Back | **PASS** (Pass I) |
| Trust index → detail → Back | **PASS** |
| Channel overview → detail → Back | **PASS** |
| Budget input → detail → Back | **PASS** |

Mechanism: `createDetailShellRouter` with history index 1 → `router.navigate(-1)` → pathname restored.

---

## 9. Direct Deep-Link Safe Return (CA-L8-II-03)

`DetailReturnLink` uses canonical `Link` href via `buildParentReturnLink` — **not** `navigate(-1)`.

| Direct load | Expected href | Harness |
|-------------|---------------|---------|
| `/app/claims/claim_0001` | `/app/claims` | **PASS** |
| `/app/trust/env_0001` | `/app/trust` | **PASS** |
| `/app/channels/ch_1` | `/app/channels` | **PASS** |
| `/app/budget/sim_0001` | `/app/budget` | **PASS** |
| Click return navigates to canonical parent | router pathname `/app/claims` | **PASS** |

---

## 10. Exception Drawer Accessibility (CA-L8-II-04–05)

| Control | Proof |
|---------|-------|
| Initial focus in drawer (close button) | **PASS** |
| Tab wrap-around (last → close) | **PASS** |
| Shift+Tab wrap-around (close → last) | **PASS** |
| 12 consecutive Tabs stay inside drawer | **PASS** |
| Escape closes drawer | **PASS** |
| Focus restores to invoking Inspect button | **PASS** |

Implementation: `Drawer.tsx` document-capture `keydown` trap with `getFocusableElements`; `ExceptionsQueuePage` captures click target as `triggerRef`.

---

## 11. 375px Multi-Surface Evidence (CA-L8-II-06)

| Surface | Harness |
|---------|---------|
| Claim detail (compact row → detail) | **PASS** (Pass I) |
| TrustEnvelope detail | **PASS** |
| Channel detail | **PASS** |
| Budget simulation detail | **PASS** |
| Exception drawer + blocked L9 | **PASS** |

Mechanism: `setMobileViewport375()` from `level8.helpers.tsx`.

---

## 12. Mounted Claim Tab Keyboard (CA-L8-II-07)

| Control | Proof |
|---------|-------|
| ArrowRight → Evidence tab `aria-selected=true` | **PASS** |
| Evidence panel `data-claim-tab="evidence"` visible | **PASS** |
| End → Audit tab active + panel visible | **PASS** |

`Tabs.tsx` updated: arrow/Home/End keys call `onChange` (automatic activation).

---

## 13. TrustEnvelope JSON Boundedness (CA-L8-II-08)

Declared limits (`src/detail/jsonViewerBounds.ts`):

| Constant | Value |
|----------|-------|
| `MAX_INLINE_JSON_BYTES` | 65,536 |
| `MAX_RENDERED_JSON_DOM_NODES` | 200 |
| `MAX_VISIBLE_JSON_LINES` | 48 |

| Control | Proof |
|---------|-------|
| Large fixture DOM nodes ≤ cap | **PASS** |
| Visible lines ≤ `MAX_VISIBLE_JSON_LINES` | **PASS** |
| Oversize payload → `data-json-oversize-fallback` | **PASS** |
| Oversize shows blocked L9 copy/export | **PASS** |

---

## 14. Full-Model JSON Search (CA-L8-II-09)

| Control | Proof |
|---------|-------|
| Off-screen marker absent from initial DOM | **PASS** |
| Search finds off-screen match (`1 match`) | **PASS** |
| Enter navigates virtual window to marker line | **PASS** |
| DOM nodes remain bounded after navigation | **PASS** |

Mechanism: `findJsonLineMatches` over full line array; `computeVirtualWindowStart` scrolls viewport.

---

## 15. JSON Viewer Keyboard (CA-L8-II-10)

| Control | Proof |
|---------|-------|
| Search input keyboard-focusable | **PASS** |
| Collapse toggle Space/Enter | **PASS** |
| Expand restores `#trust-envelope-json-lines` | **PASS** |

---

## 16. Stale Detail In-Flight Safety (CA-L8-II-11)

Scenario (mounted router):

1. Navigate to `claim_0001` with 900ms delay  
2. Navigate to `claim_0002` before A resolves  
3. B loads (`google_ads claim claim_0002`)  
4. Wait 1000ms for late A  
5. B remains authoritative; A title absent  

**PASS**

Mechanism: `useDetailFetch` `activeRef` + `AbortController`; `setClaimDetailDelayByIdForTests`.

---

## 17. Budget Blocked-Submit (CA-L8-II-13)

| Control | Proof |
|---------|-------|
| `data-level9-blocked-action` on submit | **PASS** |
| Click → toast/status "deferred to Level 9" | **PASS** |
| Keyboard Enter → blocked explanation | **PASS** |
| No proposal mutation | **PASS** (toast-only `Level9BlockedAffordance`) |

---

## 18. Mounted Boundedness (CA-L8-II-14)

| Control | Proof |
|---------|-------|
| Tab switch does not increase `getDetailRequestCount()` | **PASS** |
| Channel related claims ≤ 25 (`data-related-claim-row`) | **PASS** |
| Channel related envelopes ≤ 25 | **PASS** |
| JSON viewer DOM cap (see §13) | **PASS** |

---

## 19. Sabotage-Control Evidence (CA-L8-II-15)

### 19.1 Source integrity probes — 23/23 PASS

New Iteration II guards include: `harness-state-matrix`, `harness-trust-parent-back`, `harness-stale-detail`, `harness-budget-blocked-submit`, `harness-375px-multi`, `harness-claim-tab-keyboard`, `harness-json-offscreen-search`, `json-dom-bounds`, `json-full-model-search`, `drawer-focus-trap`.

### 19.2 Sabotage detectors — 23 probes

Poison sample triggers export/blocked-shell/radar (Pass I). New detectors fire when harness strings removed: `missing-state-matrix`, `missing-trust-parent-back`, `missing-canonical-fallback-test`, `missing-drawer-focus-trap`, `missing-375px-multi-surface`, `missing-claim-tab-keyboard`, `missing-json-dom-bounds`, `missing-offscreen-json-search`, `missing-stale-detail-mounted`, `missing-budget-blocked-submit`, `unbounded-json-render`.

Clean `ClaimDetailPage.tsx` sample → **0** triggers. Clean harness → integrity probes **23/23**.

### 19.3 Self-adversarial attacks performed

| Attack | Expected | Observed |
|--------|----------|----------|
| Remove state matrix describe block | `harness-state-matrix` fails | **Detected** |
| Remove trust parent Back test | `harness-trust-parent-back` fails | **Detected** |
| Remove JSON DOM bounds from viewer | `json-dom-bounds` fails | **Detected** |
| Revert Drawer focus trap | `drawer-focus-trap` fails | **Detected** |
| Remove stale detail test | `harness-stale-detail` fails | **Detected** |
| Wire `navigate(-1)` in DetailReturnLink | `unsafe-history-back-return` sabotage fires | **Not present** |
| Full `audit:level8` after remediation | Exit 0 | **PASS** |

---

## 20. Exit Gate Verdicts (CRHACAD EG-L8-1 … EG-L8-15)

| Gate | Verdict | Evidence |
|------|---------|----------|
| EG-L8-1 Prior substrate preserved | **PASS** | §6; L7 70/70 |
| EG-L8-2 Detail state matrix behavioral | **PASS** | §7 |
| EG-L8-3 Multi-surface parent context | **PASS** | §8 |
| EG-L8-4 Direct deep-link safe return | **PASS** | §9 |
| EG-L8-5 Exception drawer accessibility | **PASS** | §10 |
| EG-L8-6 Multi-surface 375px | **PASS** | §11 |
| EG-L8-7 Mounted detail keyboard | **PASS** | §12, §15 |
| EG-L8-8 Bounded virtualized JSON | **PASS** | §13 |
| EG-L8-9 Full-model JSON search | **PASS** | §14 |
| EG-L8-10 Stale detail in-flight | **PASS** | §16 |
| EG-L8-11 Budget blocked-submit | **PASS** | §17 |
| EG-L8-12 Mounted boundedness | **PASS** | §18 |
| EG-L8-13 Negative scope / privacy | **PASS** | §6 scans 0 violations |
| EG-L8-14 Non-vacuous harness | **PASS** | §19 |
| EG-L8-15 Evidence reproducibility | **PASS** | §6, §21 |

---

## 21. Visual Evidence

**Directory:** `evidence/Level_8/visual/` — **28 PNGs** + `visual-artifact-index.json`  
Regenerated after Iteration II (layout unchanged; behavioral harness is primary proof).

---

## 22. Remaining Risks / Forward Obligations

| Item | Owner | Notes |
|------|-------|-------|
| HTTP transport for detail APIs | B2.5+ | Mock clients; validation boundary preserved |
| Independent third-party re-audit | Reviewer | Implementer evidence; confirm Iteration II closes Pass I blockers |
| Level 9 executable flows | L9 | Replace blocked affordances with gated mutations |
| JSON viewer scroll UX on very large contracts | L8+ | Virtual window proven; UX polish optional |

---

## 23. Reproduction

```bash
cd skeldir-ui
npm run audit:level8
```

Expected: build success; all scope/privacy/secret scans 0 violations; **315** harness tests pass (**58** Level 8, **70** Level 7); **23/23** source integrity probes; **28** visual PNGs.

---

## 24. Evidence Self-Scan Confirmation

Synthetic identifiers only. No raw emails, IPs, tokens, or webhook payloads embedded. Reproducible via `npm run audit:level8` from `skeldir-ui/`.
