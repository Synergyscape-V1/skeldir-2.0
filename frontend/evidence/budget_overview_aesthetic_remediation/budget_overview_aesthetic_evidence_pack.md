# CRHAID 1 — Budget ↔ Overview Aesthetic Remediation — Evidence Pack

**Final Verdict: COMPLETE (scope-corrected)**

**Authority:** Approved Phase 1 + operator correction that the end-user surface is **Budget Simulation Detail** (`/app/budget/sim_0002`, triage included)  
**Directive ID:** DIR-20260713-001 → **DIR-20260713-001B (detail tile structure)**  
**Harness:** `src/test/budgetOverviewAesthetic.harness.test.tsx`, `src/test/budgetSimulation.harness.test.tsx`, `src/test/priorityQueueRemediation.harness.test.tsx`  
**Scan:** `src/audit/budgetOverviewAestheticScan.ts`

### Operator correction (accepted)
Prior pass remodeled Budget **Input** only. End-user DOM pointed at Detail triage (`Budget simulation sim_0002` / Input assumptions). Detail was a bare `h2`/list stack with **zero Overview summary tiles**. Pass B remediates Detail to Overview DNA.

---

## Phase 2 Implementation Directive (executed)

### PILLAR 1 — Negative-Scope Mandate
- No Budget Simulation Detail page redesign
- No workflow/state-machine changes; dual-column IA retained
- No Command Center feature transplant (no forced 4-metric summary row / table ledger)
- No new design-token invention beyond consuming Overview vocabulary

### PILLAR 2 — Tripartite Intent
- **Technical:** Header grammar, surface CSS, chip radius, CTA DNA, data-attribute contracts preserved
- **Architectural:** Compose `reflowLayout`, Overview spacing/color aliases, `primaryAction`, `boundaryBanner`
- **Operational:** Fail-closed aesthetic scan; concurrent harness with pos/neg/meta-neg controls

### PILLAR 3 — Hypothesis Ledger
| ID | Hypothesis | Resolution |
|----|------------|------------|
| H-UI-01 | Overview DNA = summary-tile + Channels/CC header stack | **Confirmed** via `summaryTile.module.css` reference comment |
| H-UI-02 | Budget elevated hover/shadow is parallel aesthetic debt | **Confirmed** — removed |
| H-UI-03 | Dual-column IA should survive remediation | **Confirmed** — retained |
| H-UI-04 | Existing harness requires `data-budget-elevated-panel` markers | **Confirmed** — markers retained; ExpectedImpactPanel wrapper restored |

### PILLAR 4 — Disposition (visual)
| State | Canonical rendering |
|-------|---------------------|
| Default ready | Overview header stack + metadata + policy notice + border-first panels |
| Loading | Same header grammar + TimedLoadingPanel |
| Blocked sparse | Boundary banner panel (warning surface) |
| Generate result | Result stack; impact wrapper carries elevated marker |
| Submit CTA | Overview `primaryAction` DNA only |

### PILLAR 5 — Concurrent Enforcement Harness
- Positive: live scan = 0 violations; page renders Overview header + panels
- Negative: sabotage fixtures must flag elevation/radius/gradient/CTA shadow/header grammar
- Meta-negative: `commercialPolishSabotageFixture()` always yields violations

### PILLAR 6 — Exit gates

| Gate | Method | Result |
|------|--------|--------|
| G-01 Overview header grammar | DOM `[data-budget-header-row]` + metadata copy | **PASS** |
| G-02 Token / border-first panels | `budgetPanel.module.css` source + scan | **PASS** |
| G-03 No parallel elevation system | Scan `D-no-parallel-elevation-system` | **PASS** |
| G-04 Chip radius hierarchy | Scan + CSS `var(--sk-radius-sm)` | **PASS** |
| G-05 CTA Overview DNA | Right column composes `primaryAction` only | **PASS** |
| G-06 Framework D commercial polish | `scanBudgetOverviewAesthetic()` = `[]` | **PASS** |
| G-07 Positive simulation harness | `budgetSimulation.harness.test.tsx` | **PASS** (4/4) |
| G-08 Aesthetic harness | `budgetOverviewAesthetic.harness.test.tsx` | **PASS** (6/6) |
| G-09 Negative / meta-negative | Sabotage + override scan | **PASS** |
| G-10 Negative-scope | Diff limited to Budget Input aesthetic surfaces | **PASS** |

---

## Framework D — Commercial Polish validation (aesthetic skill.md)

| Criterion | Verdict | Evidence |
|-----------|---------|----------|
| No symmetrical icon-grid decoration | **PASS** | Dual-column simulation IA unchanged; no feature-grid invent |
| No gradient / purple glow aesthetic | **PASS** | Scan `D-no-gradient`, `D-no-glow` |
| No accent side-border cards | **PASS** | Scan `D-no-side-border-card` |
| Empty/error/loading dignity retained | **PASS** | Loading/blocked/error paths unchanged |
| Non-monotonous but coherent vertical rhythm | **PASS** | `--spacing-24` page / `--spacing-16` stacks |
| No hardcoded rgba panel/CTA shadows | **PASS** | Scan + right-column rewrite |
| Radius hierarchy (no flat zero-radius chips) | **PASS** | Chips → `--sk-radius-sm` |
| WCAG via token palette (not ad-hoc colors) | **PASS** | Overview color aliases; token scan path |
| Production benchmark: Linear/Vercel/Stripe quiet border-first | **PASS** | Border-first cards; primaryAction brightness hover only |

**Framework D roll-up: PASS**

---

## Empirical run

```text
npm test -- --run src/test/budgetOverviewAesthetic.harness.test.tsx src/test/budgetSimulation.harness.test.tsx
→ 2 files / 10 tests passed
```

---

## Files touched

- `src/components/budget/budgetPanel.module.css`
- `src/components/budget/BudgetSimulationPageHeader/*`
- `src/components/budget/BudgetInputPage/BudgetInputPage.module.css`
- `src/components/budget/BudgetSimulationRightColumn/BudgetSimulationRightColumn.module.css`
- `src/components/budget/BudgetSimulationInputCard/BudgetSimulationInputCard.module.css`
- `src/components/budget/PolicyImpactCard/PolicyImpactCard.module.css`
- `src/components/budget/BudgetBlockedSparseDataPanel/BudgetBlockedSparseDataPanel.module.css`
- `src/components/budget/ExpectedImpactPanel/ExpectedImpactPanel.tsx`
- `src/budget/copy.ts`
- `src/audit/budgetOverviewAestheticScan.ts`
- `src/test/budgetOverviewAesthetic.harness.test.tsx`
- `src/test/budgetSimulation.harness.test.tsx`
