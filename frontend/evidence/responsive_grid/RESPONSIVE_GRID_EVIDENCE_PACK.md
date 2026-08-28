# Responsive Grid Constraints — Remediation Evidence Pack

**Final Verdict: COMPLETE**

**Path:** `skeldir-ui/evidence/responsive_grid/`

---

## 1. Failure point

Dashboard tiles, filter rows, and supervisory panels used fixed `repeat(N, minmax(0, 1fr))` grids that proportionally shrank cards below readable minimums on narrow viewports instead of reflowing to fewer columns per row.

**Root cause (empirical):** Per-page grid definitions with zero floor on column tracks; no shared substrate enforcing minimum tile dimensions.

---

## 2. Remediation strategy (skill-aligned)

| Principle | Decision |
|-----------|----------|
| Design-at-scale | Single `responsiveGrid.module.css` substrate composed into page modules |
| Tripartite intent | Works (auto-fit reflow), fits (tokenized mins), safe (audit + harness) |
| Harness-concurrent | `responsiveGridAudit.ts` + `responsiveGrid.harness.test.tsx` |
| Fail-closed | Forbidden `minmax(0,1fr)` repeat grids flagged unless substrate composed |

**Mechanism:** CSS Grid `repeat(auto-fit, minmax(min(100%, var(--sk-grid-*-min-width)), 1fr))` with component-level `min-width` / `min-height` on tiles. Supervisory row uses explicit panel minimums at `56rem` breakpoint.

---

## 3. Grid token registry (`tokens.css`)

| Token | Value | Use |
|-------|-------|-----|
| `--sk-grid-tile-min-width` | 14rem | Summary/metric tiles |
| `--sk-grid-tile-min-height` | 9rem | Tile cards |
| `--sk-grid-filter-field-min-width` | 11.25rem | Filter rows |
| `--sk-grid-dual-panel-min-width` | 18rem | Page headers, dual panels |
| `--sk-grid-trend-panel-min-width` | 22rem | Verified revenue chart |
| `--sk-grid-channel-panel-min-width` | 28rem | Channel trust table |
| `--sk-grid-metric-column-min-width` | 9.5rem | Comparison columns |
| `--sk-grid-supervisory-stack-breakpoint` | 56rem | Supervisory side-by-side |

---

## 4. Substrate classes (`responsiveGrid.module.css`)

- `tileGrid` / `tileCard` — four-tile summary rows
- `filterGrid` / `filterGridWide` — filter panels
- `dualPanelGrid` — two-up card rows (integration groups)
- `supervisoryGrid` / `supervisoryPanel` — Command Center trend + channel row
- `activityTileGrid` — audit activity tiles
- `fieldPairGrid` / `metricColumnGrid` — envelope detail field layouts
- `asymmetricSplitGrid` — envelope detail main/json split
- `responsiveProofFieldGrid` — proof field pairs

---

## 5. Surfaces migrated

- Command Center: summary grid, supervisory row, dual panels, proof fields, chart/table cards
- Channels: summary row, filters
- Trust Index: summary row, filters, index page header, detail page split + field grids
- Benchmarks: filters
- Claims Ledger: filters, page header
- Integration groups: card grid

---

## 6. Empirical validation

```bash
npx vite build
npx vitest run src/test/responsiveGrid.harness.test.tsx \
  src/test/level10.harness.test.tsx \
  src/test/commandCenterCorrectiveAction.harness.test.tsx
```

| Gate | Result |
|------|--------|
| `npx vite build` | **PASS** (CSS modules compose cleanly) |
| Responsive grid audit | **PASS** (0 violations) |
| `responsiveGrid.harness.test.tsx` | **PASS** |
| `level10.harness.test.tsx` | **PASS** (63 tests) |
| Full suite `npx vitest run` | **700/701 PASS** (1 unrelated flaky timeout in level9 history-back; passes in isolation) |

---

## 7. Regression probes updated

- `commandCenterCorrectiveIntegrityProbes`: `fluid-grid-minmax` → `responsive-supervisory-grid`
- `level2.harness.test.tsx`: priority section asserted via `[data-priority-queue]` + "Needs review" copy
- `level10.harness.test.tsx`: supervisory layout asserts substrate min-width enforcement at `56rem`
