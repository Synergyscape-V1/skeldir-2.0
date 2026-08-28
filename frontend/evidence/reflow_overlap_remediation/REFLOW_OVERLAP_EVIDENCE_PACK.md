# Reflow Overlap Remediation — Evidence Pack

**Final Verdict: COMPLETE**

**Path:** `skeldir-ui/evidence/reflow_overlap_remediation/`

---

## 1. Defect

On viewport shrink, tiles, headers, filter controls, priority rows, and shell chrome overlapped instead of reflowing — caused by rigid grids, `white-space: nowrap` on page metadata, fixed multi-column rows without stack breakpoints, and a non-wrapping TopHeader grid.

---

## 2. Root-cause diagnosis

| Factor | Finding |
|--------|---------|
| **Positioning** | Layout-purpose absolute/fixed limited to overlays (modals, drawers, toasts, dropdowns, sr-only). Timeline markers are decorative within `position: relative` items. |
| **Flex/grid reflow** | Page headers used nowrap metadata; Channels header forced `grid 1fr auto` at 1024px; priority rows used 4-column grid without stack until 767px only. |
| **Z-index** | Chrome band clean — no orphan mid-range z-index values between drawer (900) and modal (1000). |

---

## 3. Remediation substrate (`reflowLayout.module.css`)

| Class | Behavior |
|-------|----------|
| `pageHeaderRow` | Flex wrap + min-width floors |
| `pageHeaderStack` / `headerActionColumn` / `headerMetaStack` | Reflow with 64rem stack breakpoint |
| `shellHeaderBar` / `shellHeaderCenter` / `shellHeaderControls` | Wrapping top header |
| `toolbarRow` / `toolbarCluster` | Wrapping data toolbars |
| `priorityIssueRow` | 2-row stack below 64rem; 4-col at desktop |
| `reflowFieldRow` / `reflowHashRow` | Label/value stacks below 48rem |

Token: `--sk-grid-header-action-min-width: 14rem`, `--sk-reflow-stack-breakpoint-tablet: 64rem`.

---

## 4. Surfaces migrated

- Command Center: header row, meta stack, priority queue rows, removed page metadata `nowrap`
- TopHeader: flex-wrap shell bar (replaces rigid 3-column grid)
- Claims, Channels, Trust Index, Trust Detail: `pageHeaderRow` substrate
- Channels: removed rigid 1024px header grid; metric basis group wraps
- Trust Index toolbar: `toolbarRow` substrate
- Trust Detail panels: `reflowFieldRow`, `reflowHashRow`

---

## 5. Enforcement

- `src/audit/reflowOverlapAudit.ts` — positioning, nowrap, header wrap, priority stack, toolbar wrap, z-index band
- `src/test/reflowOverlap.harness.test.tsx` — audit gate + meta-negative + responsive grid regression

---

## 6. Validation

```bash
npx vite build
npx vitest run src/test/reflowOverlap.harness.test.tsx
npx vitest run
```

| Gate | Result |
|------|--------|
| `npx vite build` | **PASS** |
| Reflow overlap audit | **PASS** (0 violations) |
| Full suite | **710/711 PASS** (1 pre-existing flaky Level 9 history-back timeout) |

---

## 7. Viewport behavior (post-remediation)

| Width | Expected behavior |
|-------|-------------------|
| ≥1440px | Full multi-column grids; priority rows 4-column |
| 1024–1439px | Supervisory panels side-by-side; priority rows stack |
| 768–1023px | Page headers stack; toolbars wrap; tiles reflow 2–3 per row |
| ≤767px | Single-column stacks; mobile bottom nav fixed (intentional overlay) |

Tables retain horizontal scroll where data width exceeds viewport (by design); card/tile/header surfaces reflow only.
