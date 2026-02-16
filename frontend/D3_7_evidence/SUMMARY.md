# D3.7 Template Integration Baseline — Evidence Summary

## D3.7 Corrective Action (2026-02-13) — Certification Integrity Restoration

**Previous state:** SUMMARY claimed "CanonicalDataTable works" while Storybook failed at runtime.
**Empirically observed:** `npm run build-storybook` failed with Rollup resolution error.

**Root cause:** `@radix-ui/react-select` was missing. `shadcn-theme.stories.tsx` imports Select from
`@/components/ui/select`, which requires this package. The select primitive existed but its Radix
dependency was never installed.

**Fix applied:** Added `@radix-ui/react-select: ^2.1.4` to package.json.

**Verification:**
- `npm run build-storybook` → **PASS** (canonical-data-table.stories chunk built)
- D3.7 files → 0 TypeScript errors
- Evidence pack: debug_curl_output.txt, debug_vite_log.txt, canonical_table_fix.diff, typecheck_d37_scope.txt

**screenshot_proof.png:** Manual capture required — run `npm run storybook`, open Tables/CanonicalDataTable, capture rendered table.

---

## Exit Gate 1: Deterministic Installation Integrity

| Dependency | Required | Installed | Status |
|------------|----------|-----------|--------|
| @tremor/react | 3.x.x | 3.18.7 | PASS |
| @tanstack/react-table | 8.x.x | 8.21.3 | PASS |
| lucide-react | 0.x.x | 0.309.0 | PASS |
| recharts | any | 2.15.4 | PASS |
| react-hook-form | any | 7.71.1 | PASS |
| zod | any | 4.3.6 | PASS |
| @hookform/resolvers | any | 5.2.2 | PASS |

### shadcn Primitive Inventory (18/18)

All required primitives present in `src/components/ui/`:
button, input, card, dialog, select, form, table, tabs, accordion,
alert, badge, progress, skeleton, tooltip, avatar, checkbox,
radio-group, switch

**Corrective note:** select.tsx required `@radix-ui/react-select`; added 2026-02-13.

## Exit Gate 2: Token-True Theme Integration (No Drift)

### Alpha Semantics Decision
- **Branch taken**: D0 tokens already provide HSL channels (e.g., `--primary: 217 91% 42%`)
- Direct mapping used — no hex-to-HSL conversion needed
- Tailwind's `hsl(var(--primary))` syntax supports opacity modifiers natively

### Theme Mapping Status
- `src/index.css`: All 11 required shadcn CSS variables mapped to enterprise D0 tokens
- Stale `@layer base` duplicate block removed (was conflicting with enterprise values)
- `tailwind.config.js`: Tremor theme keys added:
  - tremor-brand → hsl(var(--primary)) [D0 primary]
  - tremor-background → hsl(var(--background)) [D0 background]
  - tremor-content → hsl(var(--foreground)) [D0 foreground]
  - tremor-ring → hsl(var(--primary)) [D0 primary]

### Adaptation Note
- shadcn was already initialized with style "new-york", baseColor "slate"
- Re-initializing would break 50+ existing components
- All verification checks (TS, CSS variables, @/* alias, no prefix) PASS
- The theme token mapping is style-agnostic — enterprise D0 values override defaults

## Exit Gate 3: Canonical Integration Baseline + Quality Gates

### Integration Deliverables
| Artifact | Path | Status |
|----------|------|--------|
| Canonical DataTable | src/components/tables/CanonicalDataTable.tsx | Created |
| DataTable Story | src/stories/canonical-data-table.stories.tsx | Created |
| shadcn Theme Story | src/stories/shadcn-theme.stories.tsx | Created |
| Tremor Theme Story | src/stories/tremor-theme.stories.tsx | Created |
| Icon Usage Guide | src/components/icons/README.md | Created |

### Quality Gates
| Gate | Result |
|------|--------|
| type-check (D3.7 files) | 0 errors |
| type-check (total, pre-existing) | 328 errors (all pre-existing, none from D3.7) |
| Verifier (40 checks) | 40/40 PASS |
| Non-vacuity demo | FAIL when button.tsx removed, PASS when restored |

### Storybook Configuration
- Storybook v10.2.8 installed with React + Vite framework
- addon-a11y configured (set to "error" mode for CI)
- Preview imports `src/index.css` so D0 tokens are active in all stories
- Dark mode toggle via Storybook toolbar (decorator applies `.dark` class)

## Evidence Files in This Bundle

| File | Contents |
|------|----------|
| dep_versions.txt | npm list output for all required deps |
| typecheck_d37_files.txt | Type errors from D3.7 files (empty = 0 errors) |
| typecheck_total_errors.txt | Total pre-existing error count |
| verifier_pass.txt | Verifier output showing 40/40 PASS |
| verifier_fail.txt | Verifier output showing FAIL (non-vacuity demo) |
| D3_7_template_baseline_local_patch.diff | Full local diff of all changes |
| **debug_curl_output.txt** | HTTP/path diagnostic notes (curl skipped; build revealed cause) |
| **debug_vite_log.txt** | Vite error trace: @radix-ui/react-select resolution failure |
| **canonical_table_fix.diff** | Fix: add @radix-ui/react-select to package.json |
| **typecheck_d37_scope.txt** | D3.7 files have 0 TypeScript errors |
| **screenshot_proof_instructions.md** | Instructions for manual screenshot capture |

## Storybook Visual Verification

To validate visually (screenshots not capturable in CLI):
```
npm run storybook
```
Then check:
1. Tables/CanonicalDataTable → sorting, filter, pagination work
2. Theme/shadcn Theme Verification → toggle light/dark, tab through for focus rings
3. Theme/Tremor Theme Verification → toggle light/dark, charts render correctly
4. a11y panel on each story → 0 critical violations
