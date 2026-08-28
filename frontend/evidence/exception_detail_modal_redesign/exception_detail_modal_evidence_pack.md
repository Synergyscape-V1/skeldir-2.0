# Exception Detail → Modal DNA — Evidence Pack

**Final Verdict: COMPLETE**

**Authority:** Approved implementation plan `exception_modal_redesign_b0f271f5`  
**Governance:** `memory-bank/skill/design-implementation-skill.md`, CRHAID six pillars  
**Evidence pack path:** `skeldir-ui/evidence/exception_detail_modal_redesign/`  
**Component:** `src/components/exceptions/ExceptionDetailModal/ExceptionDetailModal.tsx`

---

## Phase 0 — Implementation brief (executed)

| Item | Resolution |
|------|------------|
| Terminal user goal | Review a single exception under the same supervisory modal DNA as Priority Queue issues |
| Shell | `Modal` `size="wide"` — no `Drawer` |
| Content DNA | PriorityQueue issue card: severity lead + pill row + title + explanation |
| Actions | Full `ExceptionActionControls` in trailing body section (not single-row CTA) |
| States | loading → `TimedLoadingPanel`; error → `ErrorBanner` + retry; loaded → card + meta + review + actions; missing id → fail closed |
| Compatibility | Dual markers `data-exception-detail-modal` + `data-exception-detail-drawer`; deprecated `ExceptionDetailDrawer` alias |

### Negative scope (held)

- No Modal primitive API expansion
- No PriorityQueue / Command Center edits
- No ExceptionActionControls policy changes
- No new exception route
- No queue-page redesign beyond open/close wiring

### Hypothesis responses

| Hypothesis | Implementation response |
|---|---|
| H-UI-EX-01 Harness/scan breakage | Dual markers + `ExceptionDetailDrawer` alias; L8/L9 paths updated to `ExceptionDetailModal/` |
| H-UI-EX-02 Modal lacks Drawer state/footer | Body-local `TimedLoadingPanel` / `ErrorBanner` / trailing actions |
| H-UI-EX-03 Five actions ≠ single CTA | Actions remain governed stack below card; no third-column CTA |

---

## Exit gates

| Gate | Method | Actual output | Result |
|------|--------|---------------|--------|
| G-01 No Drawer in exception detail | Source integrity probe `exception-detail-modal-shell` | Modal import present; Drawer import absent | **PASS** |
| G-02 Modal wide chrome | Open from exceptions table → `[data-modal-panel]` | Present; `[data-drawer-panel]` null | **PASS** |
| G-03 Issue-card DNA | Probe `exception-detail-issue-card-dna` + DOM `[data-exception-detail-issue]` | WarningSignalIcon lead + issue card + actions | **PASS** |
| G-04 Five governed actions | Harness waits `[data-exception-action-controls]` | Controls present after load | **PASS** |
| G-05 Loading / error / loaded | Code path: TimedLoadingPanel when loading; ErrorBanner when error; body when loaded; missing id → `ERROR_COPY.missingRequiredProp` | Disposition matrix implemented | **PASS** |
| G-06 A11y focus / Escape | L8 a11y harness | Trap wraps Tab; Escape restores trigger; Close modal label | **PASS** |
| G-07 L8/L9 markers | `assertLevel8RoutesExist` / `assertLevel9FlowsExist` | `{ ok: true, missing: [] }` | **PASS** |
| G-08 Meta-negative | Probe fails if Drawer reintroduced or modal marker removed | `exception-detail-modal-shell` / `harness-exception-modal` encode that invariant | **PASS** |
| G-09 Title ref DNA | Open modal → `[data-exception-detail-title-ref]` | Footnote monospace `#0001` (ClaimDetailHeader titleRef tokens); full id on `title` attr | **PASS** |

---

## Harness evidence (method + output)

```text
npm test -- src/test/exceptions.harness.test.tsx src/test/level8.harness.test.tsx -t "Exception|exception"
→ Test Files  2 passed | Tests  11 passed | 60 skipped

npm test -- src/test/level9.harness.test.tsx -t "exception"
→ Test Files  1 passed | Tests  7 passed | 77 skipped

assertLevel8RoutesExist() → { ok: true, missing: [] }
assertLevel9FlowsExist() → { ok: true, missing: [] }
runLevel8SourceIntegrityProbes() exception probes:
  exception-detail-modal-shell → ok: true
  exception-detail-issue-card-dna → ok: true
  harness-exception-modal → ok: true
```

---

## Files touched

- `src/components/exceptions/ExceptionDetailModal/*` (new; replaces Drawer folder)
- `src/components/exceptions/ExceptionsQueuePage/ExceptionsQueuePage.tsx`
- `src/audit/level7NegativeScopeScan.ts`
- `src/audit/level8NegativeScopeScan.ts`
- `src/audit/level9NegativeScopeScan.ts`
- `src/test/exceptions.harness.test.tsx`
- `src/test/level8.harness.test.tsx`
- `src/test/level9.helpers.tsx`
