# CRHAID 1 — Open Exceptions CTA Navigation Remediation — Evidence Pack

**Final Verdict: PASS**

**Authority:** Approved Phase 1 Retranslated Design Specification (operator: "Proceed with the implementation and remediation")  
**Directive ID:** DIR-20260713-OPEN-EXCEPTIONS-CTA  
**Destination (reasoned default):** `/app/exceptions` (bare path; no severity filter deep-link)

**Harness:** `src/test/openExceptionsCta.harness.test.tsx`  
**Scan:** `src/audit/openExceptionsCtaScan.ts`  
**Related:** `src/test/summaryMetrics.test.ts`, `src/test/commandCenterRedesign.harness.test.tsx`

---

## Phase 2 Implementation Directive (executed)

### PILLAR 1 — Negative-Scope Mandate
- No Command Center visual redesign / tile chrome changes
- No Priority Queue modal / header "Review issues" retargeting
- No Exceptions queue page changes
- No filtered deep-link (`severity=critical…`) — deferred unless operator requests
- No sibling summary tile href changes

### PILLAR 2 — Tripartite Intent
- **Technical:** `summaryDrilldown.open_exceptions.href` → `/app/exceptions`; `buildOpenExceptionsMetric` consumes that href
- **Architectural:** Single source of truth in `copy.ts`; tile `sourceSurface: 'exceptions_queue'` now matches destination
- **Operational:** Static scan reject Overview self-loop; concurrent DOM navigation harness; fail-closed on sabotage

### PILLAR 3 — Hypothesis Ledger
| ID | Hypothesis | Resolution |
|----|------------|------------|
| H-UI-01 | Dead loop caused by `href: '/app'` + `PRIORITY_QUEUE_ANCHOR` | **Confirmed** — both removed/corrected |
| H-UI-02 | Exceptions route is `/app/exceptions` under AppShell | **Confirmed** — DOM lands on `[data-exceptions-page]` |
| H-UI-03 | Zero trust-issues state must not reintroduce self-loop | **Confirmed** — still `/app/exceptions` |
| H-UI-04 | Existing redesign harness asserted `/app` | **Confirmed** — expectation updated |

### PILLAR 4 — Disposition Matrix
| Tile state | CTA destination |
|------------|-----------------|
| Critical discrepancies > 0 | `/app/exceptions` |
| 0 Trust Issues | `/app/exceptions` |
| Overview self `/app` | **FAIL CLOSED** — scan violation |

### PILLAR 5 — Concurrent Enforcement Harness
- **Positive:** copy/metrics href; DOM `data-summary-drilldown="open_exceptions"`; click navigates to `/app/exceptions` + exceptions page marker; live scan empty
- **Negative:** sabotage fixture with `/app` triggers `overview-self-loop` (+ legacy anchor / copy-source rules)
- **Meta-negative:** sabotage run produces confirmed non-empty violations while live scan stays clean

### PILLAR 6 — Exit Gates

| Gate | Method | Output | Verdict |
|------|--------|--------|---------|
| G-01 Href contract | Static copy audit + unit | `href === '/app/exceptions'` | **PASS** |
| G-02 Metrics consume copy | Code + scan rule | `summaryDrilldown.open_exceptions.href` wired | **PASS** |
| G-03 DOM affordance | Query `data-summary-drilldown` | `href="/app/exceptions"` | **PASS** |
| G-04 Navigation exit | userEvent click + router | pathname `/app/exceptions`; not `/app` | **PASS** |
| G-05 Page arrival | Wait for marker | `[data-exceptions-page]` present | **PASS** |
| G-06 Zero-count path | buildSummaryMetrics([]) | drillDownHref `/app/exceptions` | **PASS** |
| G-07 Negative-scope | Diff review | No chrome/modal/exceptions-page edits | **PASS** |
| G-08 Harness non-vacuity | Sabotage scan | overview-self-loop triggered | **PASS** |
| G-09 Hypothesis resolution | Ledger above | All H-UI-01..04 confirmed | **PASS** |
| G-10 Final | All gates | — | **PASS** |

---

## Code delta (scope)

| File | Change |
|------|--------|
| `src/commandCenter/copy.ts` | `open_exceptions.href` → `/app/exceptions` |
| `src/commandCenter/summaryMetrics.ts` | Consume copy href; remove `PRIORITY_QUEUE_ANCHOR` |
| `src/audit/openExceptionsCtaScan.ts` | New integrity + sabotage scan |
| `src/test/openExceptionsCta.harness.test.tsx` | New pos/neg/meta-neg harness |
| `src/test/summaryMetrics.test.ts` | Expect `/app/exceptions` |
| `src/test/commandCenterRedesign.harness.test.tsx` | Expect `/app/exceptions` |

---

## Harness run (executed)

```
npx vitest run src/test/openExceptionsCta.harness.test.tsx src/test/summaryMetrics.test.ts src/test/commandCenterRedesign.harness.test.tsx
→ Test Files  3 passed (3)
→ Tests      25 passed (25)
```
