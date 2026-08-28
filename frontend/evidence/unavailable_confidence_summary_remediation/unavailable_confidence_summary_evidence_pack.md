# CRHAID 2 — Unavailable Confidence Summary Remediation — Evidence Pack

**Final Verdict: PASS** (density correction applied)

**Authority:** Operator directive to determine optimal approach from skill + memory bank and implement  
**Directive ID:** DIR-20260713-UNAVAILABLE-CONFIDENCE-SUMMARY  
**Approach locked:** Confidence-only count · cause-class meta · `N / total` ratio · in-page isolate CTA via `confidenceAvailability=unavailable`

**Density correction (operator DOM):** Visible meta was multi-line wrap (`62 cold start · 14 need review. Deterministic…`) ballooning the tile; filtered value showed tautological `76 / 76`. Fixed to single-line ellipsis meta, short peer-density copy, deterministic boundary in `title` only, count-only value when already isolated, shortened CTA labels.

**Harness:** `src/test/unavailableConfidenceSummary.harness.test.tsx`  
**Scan:** `src/audit/unavailableConfidenceSummaryScan.ts`  
**Related:** `src/test/level7.harness.test.tsx` (summary metric contract)

---

## Optimal approach (skill + foundation)

| Lens | Choice |
|------|--------|
| Goal-directed | One click isolates affected envelopes; meta answers “expected vs intervene” without sidebar discovery |
| Affordance | Supervisory drill-down DNA from `summaryTile` (Overview reference) |
| Truth invariants | Count is confidence-only (not confidence∪benchmark); every state restates deterministic verification remains active |
| Cold-start rule | Cold-start-dominant framing is calm/expected — not exception-queue noise |
| Fail-closed | Missing cause breakdown / missing CTA / benchmark-OR count = scan FAIL |

---

## Phase 2 Implementation Directive (executed)

### PILLAR 1 — Negative-Scope Mandate
- No TrustEnvelope table column redesign
- No Exceptions queue routing for cold-start (forbidden by context invariants)
- No new filter enum / reason-code filter (uses existing `confidenceAvailability`)
- No Command Center / sibling ledger remediations
- No visual redesign of the other three summary tiles beyond composing shared footer DNA on the unavailable tile

### PILLAR 2 — Tripartite Intent
- **Technical:** Cause breakdown + disposition meta + isolate/clear href builders
- **Architectural:** Single presentation module + summary composition; Overview drill-down tokens
- **Operational:** Pos/neg/meta-neg harness; disposition attribute for forensic reads

### PILLAR 3 — Hypothesis Ledger
| ID | Hypothesis | Resolution |
|----|------------|------------|
| H-UI-01 | Label lied when count ORd benchmark | **Confirmed** — confidence-only count |
| H-UI-02 | Row reasons map to cold_start / computation | **Confirmed** |
| H-UI-03 | Existing filter is sufficient CTA target | **Confirmed** |
| H-UI-04 | Zero-count needs calm meta, no CTA | **Confirmed** |

### PILLAR 4 — Disposition Matrix
| Causes | Disposition | Value tone | Meta | CTA |
|--------|-------------|------------|------|-----|
| count = 0 | zero | default | success calm | none |
| cold only (or dominant) | cold_start_dominant | default | expected cold-start | isolate |
| computation only (or dominant) | computation_dominant | warning | may need review | isolate |
| cold + computation | mixed | warning | `N cold · M need review` | isolate |
| other | other | default | mixed reasons | isolate |
| filter already unavailable | any with count>0 | as above | as above | clear filter |

### PILLAR 5 — Concurrent Enforcement Harness
- **Positive:** confidence-only math; meta copy; href builders; DOM ratio+meta+CTA→filter; live scan empty
- **Negative:** sabotage fixture fails (benchmark-OR, missing meta/CTA/copy, legacy field)
- **Meta-negative:** sabotage non-empty while live empty

### PILLAR 6 — Exit Gates

| Gate | Method | Output | Verdict |
|------|--------|--------|---------|
| G-01 Confidence-only count | Unit against stub rows | 2 of 3 (benchmark-only ignored) | **PASS** |
| G-02 Cause breakdown | Causes sum = count | cold+computation+other | **PASS** |
| G-03 Meta explains expected vs intervene | Disposition copy | cold-start vs mixed strings | **PASS** |
| G-04 Ratio display | DOM | `N / total` | **PASS** |
| G-05 Isolate CTA | Click + router | `confidenceAvailability=unavailable` | **PASS** |
| G-06 Filter control sync | Select value | `unavailable` | **PASS** |
| G-07 Negative-scope | Diff | No table/exceptions scope creep | **PASS** |
| G-08 Harness non-vacuity | Sabotage scan | violations > 0 | **PASS** |
| G-09 Final | All gates | — | **PASS** |

---

## Code delta (scope)

| File | Change |
|------|--------|
| `src/ledger/types.ts` | `unavailableConfidenceCount` + causes breakdown |
| `src/trustIndex/trustIndexSummary.ts` | Confidence-only compute + classifiers |
| `src/trustIndex/unavailableConfidenceSummaryPresentation.ts` | Disposition → meta/tone |
| `src/trustIndex/trustIndexQueryState.ts` | Isolate + clear href builders |
| `src/trustIndex/copy.ts` | Supervisor meta + CTA copy |
| `src/components/trustIndex/TrustEnvelopeIndexSummaryRow/*` | Ratio, meta, CTA |
| `src/components/trustIndex/TrustEnvelopeIndexPage/TrustEnvelopeIndexPage.tsx` | Pass filters |
| `src/audit/unavailableConfidenceSummaryScan.ts` | Integrity + sabotage |
| `src/test/unavailableConfidenceSummary.harness.test.tsx` | Pos/neg/meta-neg |
| `src/test/level7.harness.test.tsx` | Metric id + contract wait |

---

## Harness run (executed)

```
npx vitest run src/test/unavailableConfidenceSummary.harness.test.tsx
→ Test Files  1 passed (1)
→ Tests      8 passed (8)
```
