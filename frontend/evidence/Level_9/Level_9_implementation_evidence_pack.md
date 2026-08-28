# Level 9 Implementation Evidence Pack

**Directive:** II CRHACAD Level 9 — Export, Verification, and Consequence-Bearing Flows  
**Prior corrective directives:** CRHACAD Level 9 Iteration I (substrate) · Iteration II (mounted behavioral proof)  
**Independent audit intake:** `evidence/Level_9/Level_9_independent_forensic_audit_report.md` (Pass II REJECT — durability / browser clipboard gates)  
**Implementation root:** `c:\Users\ayewhy\Frontend_4\skeldir-ui`  
**Evidence cut:** 2026-06-29  
**Composite gate command:** `npm run audit:level9` (includes `audit:level9:browser`)

---

## 1. Final Verdict

**COMPLETE — Iteration III (durability, navigation recovery, real-browser clipboard)**

Pass II closed mounted behavioral gaps (84 harness tests, composite 399/399) but **REJECTED** on three non-negotiable gates: reload-survivable idempotency, route-unmount recovery, and real-browser clipboard activation — plus partial failure-matrix, Back/resubmit, and Escape coverage.

Iteration III implements **sessionStorage-backed action durability**, **mount recovery in `useGovernedAction`**, **stable fingerprint idempotency keys**, **clipboard write with NotAllowedError staging + retry**, **12 additional mounted tests** (84 → **96**), and a **Playwright Chromium/WebKit browser audit** integrated into the composite gate.

Falsifiable validation: `npm run audit:level9` exit **0** on 2026-06-29 after Iteration III remediation (`audit-level9-iii-final.log`).

| Metric | Iteration II | Iteration III |
|--------|--------------|---------------|
| `npm run audit:level9` | exit 0 (no browser) | **exit 0** (incl. browser) |
| L9 harness tests | 84/84 | **96/96** |
| Composite harness (L1–L9 + redirectGuard) | 399/399 | **411/411** |
| L8 harness (regression) | 58/58 | **58/58** |
| L9 scope scan | 28 files / 0 violations | **31 files / 0 violations** |
| L9 source integrity probes | 18/18 | **24/24** |
| L9 source sabotage probes | 0 triggered (clean) | **0 triggered (clean)** |
| Browser clipboard audit | not run | **PASS** (Chromium + WebKit) |
| Visual PNGs | 10 | **10** (regenerated) |

---

## 2. Semantic Internalization (II CRHACAD Physics)

Level 9 consequence-bearing flows are **stateful physical processes**, not one-shot UI callbacks. Completion requires proof that:

1. **Idempotency survives process amnesia** — hard refresh clears module memory but session registry retains pending/completed action fingerprints.
2. **Navigation does not orphan pending work** — route unmount during pending restores `aria-busy` pending phase on return via durable registry.
3. **Clipboard is a real browser capability** — canonical JSON is written via `navigator.clipboard.writeText` in Chromium; WebKit verified via success outcome + canonical preview fallback when read is denied.
4. **Clipboard denial is recoverable** — `NotAllowedError` stages payload in sessionStorage; second click delivers without re-fetching canonical JSON.
5. **Failure matrix is outcome-complete** — `timeout`, `partial_failure`, `conflict_stale_object`, network retry, Escape on destructive vs standard modals.
6. **Trust hierarchy unchanged** — export/share ≠ new truth; signature = integrity only; budget = proposal only.

---

## 3. Pass II Independent Audit Intake → Iteration III Mapping

**Source:** `evidence/Level_9/Level_9_independent_forensic_audit_report.md` (Pass II REJECT)

| Pass II blocker | Gate | Iteration III corrective action | Proof artifact |
|-----------------|------|--------------------------------|----------------|
| In-memory idempotency only; counter keys | Gate 08 | `actionRegistry.ts` (sessionStorage); `buildActionFingerprint`; `simulateHardRefreshForTests`; stable `generateIdempotencyKey` | Harness: hard refresh preserves completed + pending registry |
| React-local phase/outcome only | Gate 09 | `useGovernedAction` mount recovery from registry; fingerprint on all flows | Harness: route unmount during pending recovers pending |
| jsdom clipboard mock only | Gate 10 | `bounds.ts` clipboard write + staging; `TrustEnvelopeActions` write path; `scripts/run-level9-browser-audit.ts` | `npm run audit:level9:browser` PASS; harness NotAllowedError retry |
| Missing timeout/partial_failure/stale mounted | Gate 06 | `timeout`/`partial_failure` test modes; budget `stale` mounted | Harness failure-matrix III tests |
| No Back/resubmit test | Gate 07 | Memory router history Back → forward → resubmit | Harness `history back during confirmation` |
| No Escape test | Gate 16 | Destructive ignores Escape; standard modal closes | Harness Escape tests |
| Trust copy clipboard not proven in browser | Gate 10 | Browser audit reads clipboard (Chromium) / canonical preview (WebKit) | `evidence/Level_9/browser/clipboard-*.json` |

---

## 4. Root-Cause Determinations (Iteration III)

| RC | Hypothesis | Result | Disposition |
|----|------------|--------|-------------|
| RC-L9-III-01 | Pass II idempotency was memory-only | **CONFIRMED** | sessionStorage registry + stable fingerprints |
| RC-L9-III-02 | Pending registry blocked clipboard retry | **CONFIRMED** | `clearIdempotencyPending` clears registry entry |
| RC-L9-III-03 | Nested MemoryRouter broke Playwright specimens | **CONFIRMED** | `Level8LedgerSpecimens` → auth seed + `Navigate` to `/app/*` |
| RC-L9-III-04 | Clipboard success recorded before write | **CONFIRMED** | Copy JSON idempotency finalized only after clipboard OK |
| RC-L9-III-05 | WebKit lacks clipboard-write permission API | **CONFIRMED** | Engine-specific context; WebKit fallback verification |

---

## 5. Files Changed (Iteration III delta)

| Area | Files |
|------|-------|
| Durable registry | `src/actions/actionRegistry.ts` — **new** sessionStorage map, pending/completed/failed |
| Idempotency | `src/actions/idempotency.ts` — registry sync, stable keys, `simulateHardRefreshForTests`, outcome recording |
| Hook recovery | `src/actions/useGovernedAction.ts` — fingerprint options, mount recovery, permission/policy outcome registration |
| Clipboard | `src/actions/bounds.ts` — `copyTextBounded` NotAllowedError, staging helpers |
| Trust copy UI | `src/actions/TrustEnvelopeActions.tsx` — clipboard write + staged retry; deferred idempotency finalize |
| Flow wiring | `ClaimExportFlow.tsx`, `AuditExportFlow.tsx`, `BudgetProposalFlow.tsx`, `ExceptionActionControls.tsx` — fingerprints |
| Client modes | `claimExportClient.ts` — `timeout`, `partial_failure`; replay key uses fingerprint |
| Trust client | `trustEnvelopeActionClient.ts` — copy JSON defers idempotency success until clipboard |
| Copy | `src/actions/copy.ts` — `clipboardDeniedReady` |
| Browser audit | `scripts/run-level9-browser-audit.ts` — **new** Chromium + WebKit |
| Package | `package.json` — `audit:level9:browser` in composite `audit:level9` |
| Specimens | `src/dev/Level8LedgerSpecimens.tsx` — remove nested Router; redirect to app routes |
| Scope/sabotage | `src/audit/level9NegativeScopeScan.ts` — III integrity + sabotage probes |
| Harness | `src/test/level9.harness.test.tsx` — **+12 tests** (84 → **96**) |
| Browser evidence | `evidence/Level_9/browser/clipboard-chromium.json`, `clipboard-webkit.json` |

---

## 6. Commands Executed

```text
npm run audit:level9
```

Decomposed stages (all **PASS**, exit 0 — `audit-level9-iii-final.log`):

```text
npm run build
npm run audit:level0 … audit:level8:scope
npm run audit:level9:scope    → 31 files / 0 violations; markers 20/20
vitest run L1–L9 harness     → 411/411 pass (96 L9, 58 L8)
npm run audit:level9:browser → PASS (chromium + webkit)
npm run evidence:visual:level9 → 10 PNGs
```

Standalone verification:

```text
npx vitest run src/test/level9.harness.test.tsx  → 96/96
npm run audit:level9:browser                     → PASS
```

---

## 7. Durability & Idempotency (Gate 08 / 09)

### 7.1 Stable fingerprint keys

```text
idem_{tenantId}:{objectType}:{objectId}:{actionKind}:{policyVersion}
```

`generateIdempotencyKey` is deterministic — repeated calls produce identical keys (harness `stable idempotency key` test).

### 7.2 Session registry

`actionRegistry.ts` persists `pending | completed | failed` entries in `sessionStorage` (`skeldir_l9_action_registry_v1`).

`markIdempotencyPending` → `registerActionPending`; `recordIdempotencySuccess` / `registerActionOutcome` → completed/failed with full `GovernedActionOutcome`.

### 7.3 Hard refresh simulation

`simulateHardRefreshForTests()` clears in-memory `Set`/`Map` only — registry survives.

| Test | Proof |
|------|-------|
| Completed outcome survives refresh | Unmount/remount → `[data-level9-outcome-status="success"]` without re-execute |
| Pending survives refresh | Delayed export → refresh → `aria-busy="true"` restored |
| Route unmount during pending | Navigate audit → return claim → pending restored |

### 7.4 Back / resubmit (Gate 07)

Memory router: open confirmation on claim → `navigate(-1)` to audit → `navigate(1)` → confirm export → success. Modal does not trap stale confirmation state.

---

## 8. Real-Browser Clipboard (Gate 10)

### 8.1 Product path

1. `copyTrustEnvelopeJson` builds canonical JSON (not DOM-derived).
2. `copyTextBounded` writes to `navigator.clipboard`.
3. On `NotAllowedError`: stage in sessionStorage, show `clipboardDeniedReady`, clear pending registry for retry.
4. Second click: staged payload write without duplicate canonical fetch.

### 8.2 Harness proof

`copyTextBounded` spy: denied → `artifact_unavailable` + ready copy → second click → `success`.

### 8.3 Browser audit (`npm run audit:level9:browser`)

| Engine | Verification |
|--------|--------------|
| Chromium | `navigator.clipboard.readText()` contains `"semantic_truth_hash"` and `"provenance_chain"` |
| WebKit | Success outcome + canonical preview content (clipboard-read restricted by engine) |

Entry: `/dev/level8-specimens?fixture=level9-trust-actions` → redirects to `/app/trust/env_0001` with seeded owner auth.

---

## 9. Failure Matrix Completion (Gate 06)

| Status | Iteration III mounted proof |
|--------|----------------------------|
| `timeout` | Claim export + `setClaimExportTestMode('timeout')` |
| `partial_failure` | Claim export + `partial_failure` (no false artifact line) |
| `conflict_stale_object` | Budget proposal + `setBudgetProposalTestMode('stale')` |
| Network retry | `network_error` then reset mode → second confirm → `success` |
| `artifact_unavailable` (clipboard) | NotAllowedError staged retry path |

Prior Iteration II matrix entries retained (network_error, audit_write_failed, replay, signature_failed, scope_denied, permission_denied, etc.).

---

## 10. Modal Escape (Gate 16)

| Modal type | Behavior | Mounted proof |
|------------|----------|---------------|
| Destructive (claim export confirm) | Escape ignored per `Modal.tsx` | Confirmation panel remains after `{Escape}` |
| Standard (`GovernedActionControl` destructive=false) | Escape calls `onCancel` | `onCancel` invoked on Escape |

---

## 11. Adversarial Audit (Self + Pass II Cross-Check)

### 11.1 Attacks performed

| Attack | Expected | Observed |
|--------|----------|----------|
| Remove `actionRegistry.ts` sessionStorage | Integrity probe `registry-session-storage` fails | **Detected** |
| Remove hard-refresh harness describe | `missing-hard-refresh-harness` sabotage fires | **Detected** |
| Remove browser script | `missing-browser-audit-script` fires | **Detected** |
| Revert to counter-based idempotency keys | Stable key test fails; replay drift | **Detected** |
| Leave registry pending after clipboard deny | Second click → replay_rejected | **Fixed** — `clearIdempotencyPending` clears registry |
| Nested Router in specimens | Playwright root empty / Router error | **Fixed** — redirect pattern |
| Poison: DOM `querySelector` + clipboard in actions | `dom-copy-json-in-actions` fires | **Detected** (product-only scan) |
| Full `npm run audit:level9` after remediation | Exit 0 | **PASS** |
| L8 harness regression | 58/58 | **PASS** (154 with L9 in spot check) |

### 11.2 Pass II gate re-verdict (implementation posture)

| Gate | Pass II | Iteration III |
|------|---------|---------------|
| 08 Reload-survivable idempotency | FAIL | **PASS** |
| 09 Route-unmount recovery | FAIL | **PASS** |
| 10 Real-browser clipboard | FAIL | **PASS** |
| 06 Failure matrix (timeout/partial/stale/retry) | PARTIAL | **PASS** |
| 07 Back/resubmit | FAIL | **PASS** |
| 16 Modal Escape | PARTIAL | **PASS** |

---

## 12. Exit Gate Verdicts (CRHACAD EG-L9-1 … EG-L9-15 + III extensions)

| Gate | Verdict | Evidence |
|------|---------|----------|
| EG-L9-1 Composite gate | **PASS** | §6 — exit 0 incl. browser |
| EG-L9-2 Prior substrate | **PASS** | L8 58/58 in 411 composite |
| EG-L9-3 Mounted flow execution | **PASS** | Iteration II §8 retained |
| EG-L9-4 Mounted policy/permission/scope | **PASS** | Iteration II §9 retained |
| EG-L9-5 Mounted failure matrix | **PASS** | §9 |
| EG-L9-6 Idempotency/replay | **PASS** | §7 + Iteration II §11 |
| EG-L9-7 Exception completeness | **PASS** | Iteration II §12 retained |
| EG-L9-8 Trust signature/copy | **PASS** | §8 browser + II §13 |
| EG-L9-9 Audit/budget governance | **PASS** | Iteration II §14 retained |
| EG-L9-10 Artifact boundedness | **PASS** | Iteration II §15 retained |
| EG-L9-11 Accessibility/mobile | **PASS** | Iteration II §16 retained |
| EG-L9-12 Kill switch/degraded | **PASS** | Iteration II §17 retained |
| EG-L9-13 Negative scope/privacy | **PASS** | 31/0 scope; privacy/secret 0 |
| EG-L9-14 Non-vacuous harness | **PASS** | 96 mounted + sabotage |
| EG-L9-15 Evidence reproducibility | **PASS** | §6 logs |
| **EG-L9-16** Durability/browser (III) | **PASS** | §7–§8, §11 |

---

## 13. Visual Evidence

**Directory:** `evidence/Level_9/visual/` — 10 PNGs + `visual-artifact-index.json`  
**Browser:** `evidence/Level_9/browser/` — clipboard audit artifacts

Visual artifacts supplement mounted harness and browser audit; behavioral tests remain primary proof.

---

## 14. Remaining Risks / Forward Obligations

| Risk | Severity | Notes |
|------|----------|-------|
| Action clients remain fixture-backed | Medium | Wire to real API preserving `GovernedActionOutcome` + registry |
| WebKit clipboard read restricted | Low | Write path exercised; read verified via canonical preview fallback |
| `approval_required` exception policy | Low | CRHAID non-final-execute semantics — future policy tightening |
| sessionStorage cleared on tab close | Low | Acceptable L9 durability scope per directive (hard refresh / navigation) |

**Forward obligation:** Level 10 advancement remains **PROHIBITED** until independent Pass III acceptance.

---

## 15. Acceptance Standard Cross-Check

```text
✓ npm run audit:level9 exits 0 (411/411 + browser + visual)
✓ Levels 0–8 green
✓ sessionStorage action registry + stable fingerprint idempotency
✓ Hard refresh + route unmount pending recovery mounted
✓ Clipboard write in product; NotAllowedError staged retry mounted
✓ Playwright Chromium/WebKit browser clipboard audit PASS
✓ timeout / partial_failure / stale_object_conflict / network retry mounted
✓ Back/resubmit + Escape behavior mounted
✓ All Iteration II behavioral proofs retained (96 L9 tests superset of 84)
✓ No Level 10/11 leakage
```

**Level_9 = COMPLETE** (Iteration III — II CRHACAD durability, navigation, and browser clipboard gates).  
Independent forensic audit intake: pending Pass III re-run against this pack.

---

## Appendix A — Iteration II Summary (retained baseline)

Iteration II delivered 84 mounted tests, scope-scan correction, source sabotage on real files, execute-through-success for five flow classes, exception×5, signature matrix, artifact DOM bounds, focus trap, 375px, kill-switch matrix. See git history and prior pack revision for full II detail; Iteration III extends without removing II proofs.
