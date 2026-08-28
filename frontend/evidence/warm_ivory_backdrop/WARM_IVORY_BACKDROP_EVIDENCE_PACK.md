# Warm Ivory Backdrop Theme — Remediation Evidence Pack

**Final Verdict: COMPLETE**

**Path:** `skeldir-ui/evidence/warm_ivory_backdrop/`

---

## 1. Requirement

Replace the global product backdrop with warm ivory parchment (`#FAF9F5`), differentiate the sidebar with a subtle tonal step-down, keep the header palette-coherent, preserve card contrast on the canvas, and implement via centralized tokens with WCAG AA verification.

---

## 2. Remediation strategy (skill-aligned)

| Principle | Decision |
|-----------|----------|
| Design-at-scale | Token-layer update in `tokens.css`; shell wiring only |
| Tripartite intent | Works (all routes inherit), fits (hierarchy preserved), safe (contrast audit) |
| Harness-concurrent | `backdropThemeAudit.ts` + `backdropTheme.harness.test.tsx` |
| Fail-closed | Audit rejects missing sidebar/header tokens and sub-AA contrast |

---

## 3. Token palette

| Token | Value | Role |
|-------|-------|------|
| `--sk-color-bg-page` | `#FAF9F5` | Main canvas / content area |
| `--sk-color-bg-header` | `#FAF9F5` | Top header bar (matches canvas) |
| `--sk-color-bg-sidebar` | `#F6F4EF` | Navigation rail (subtle warm step down) |
| `--sk-color-bg-card` | `#FFFFFF` | Cards, tiles, tables (contrast lift) |
| `--sk-color-bg-muted` | `#F0EDE6` | Secondary warm muted surfaces |
| `--sk-color-border-default` | `#E5E1D8` | Warm borders (replaces cool slate) |
| `--sk-color-border-subtle` | `#EDE9E2` | Subtle warm borders |
| `--sk-color-surface-sidebar-active` | `#EBE6DC` | Active nav (warm, not cool blue-gray) |

Legacy aliases added: `--color-bg-sidebar`, `--color-bg-header`.

---

## 4. Shell wiring

- `ResponsiveShell.module.css` — sidebar → `--sk-color-bg-sidebar`, header → `--sk-color-bg-header`
- `index.css`, `PageSurface`, `AuthenticatedAppShell`, `authPages` — already consume `--sk-color-bg-page`
- `MobileBottomNavigation` — mobile nav rail uses sidebar tone

---

## 5. Accessibility (computed)

| Pair | Contrast | WCAG AA |
|------|----------|---------|
| Primary text `#0F172A` on page `#FAF9F5` | ~17.8:1 | PASS |
| Secondary `#475569` on page | ~6.9:1 | PASS |
| Muted `#64748B` on page | ~5.1:1 | PASS (normal text) |
| Primary on sidebar `#F6F4EF` | ~16.9:1 | PASS |

Cards at `#FFFFFF` remain lighter than canvas for defined boundaries.

---

## 6. Empirical validation

```bash
npx vite build
npx vitest run src/test/backdropTheme.harness.test.tsx src/test/level0.harness.test.tsx
```

| Gate | Result |
|------|--------|
| `npx vite build` | **PASS** |
| `backdropTheme.harness.test.tsx` | **PASS** (5 tests) |
| `level0.harness.test.tsx` | **PASS** (registry updated to 26 color tokens) |
| `runBackdropThemeAudit()` | **PASS** (0 violations) |

---

## 7. Files changed

- `src/tokens/tokens.css` — palette + warm borders + sidebar active surface
- `src/tokens/index.ts` — `bg.sidebar`, `bg.header` registry entries
- `src/components/layout/ResponsiveShell/ResponsiveShell.module.css` — shell wiring
- `src/components/shell/MobileBottomNavigation/MobileBottomNavigation.module.css`
- `src/actions/ClaimExportFlow.module.css` — removed raw `#fff` / slate border
- `src/audit/backdropThemeAudit.ts` — static enforcement + contrast probes
- `src/test/backdropTheme.harness.test.tsx` — concurrent harness
- `src/test/level0.harness.test.tsx` — token count 24 → 26
