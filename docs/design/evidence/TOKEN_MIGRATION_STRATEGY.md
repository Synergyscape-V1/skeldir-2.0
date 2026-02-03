# Token Migration Strategy
**Document**: Migration Plan for Competing Token Sources
**Version**: 1.0
**Date**: 2026-02-03
**Status**: READY FOR EXECUTION

---

## Purpose

This document defines the phased migration strategy from the current non-conformant token system to the canonical D0-conformant token system.

**Critical Constraint**: Cannot migrate all at once without breaking the application. Must be phased.

---

## Current State Analysis

### Competing Token Sources Identified (V2 findings)

1. **`src/index.css`** — 100+ CSS variables using non-conformant naming
   - Examples: `--primary`, `--secondary`, `--muted` (should be `--color-primary`, etc.)
   - Status: ACTIVE - Currently consumed by all components

2. **`src/assets/brand/colors.css`** — 60+ brand-specific variables
   - Examples: `--brand-alice`, `--brand-jordy`, `--spacing-xs`
   - Status: ACTIVE - Imported by `src/index.css`

3. **Component files** — Hardcoded values in 47 files
   - 29 files with raw hex values
   - 18 files with raw rgba values
   - Status: ACTIVE - Direct usage in TSX/CSS

---

## Migration Phases

### Phase 1: Canonical Token Layer (COMPLETE - D0-P1)

**Status**: ✅ COMPLETE

**Deliverables**:
- [x] 4 JSON token exports created (`skeldir-tokens-*.json`)
- [x] 91 tokens defined and validated
- [x] Taxonomy reference documentation created
- [x] Validation scripts operational

**Outcome**: Canonical token layer exists but is NOT yet consumed by the application.

---

### Phase 2: CSS Variable Scaffolding (D0-P2 - NOT IN SCOPE FOR D0-P1)

**Status**: DEFERRED to D0-P2

**Actions**:
1. Add D0-conformant CSS variables to `src/index.css` alongside existing variables
2. Map canonical tokens to CSS variables
3. DO NOT remove existing variables yet (breaking change)

**Example**:
```css
/* src/index.css */
:root {
  /* NEW: D0-conformant tokens */
  --color-primary: hsl(213, 74%, 63%);
  --color-primary-hover: hsl(213, 74%, 55%);

  /* OLD: Keep for backwards compatibility during migration */
  --primary: 217 91% 42%;
  --primary-foreground: 0 0% 100%;
}
```

**Validation**: Run `node scripts/validate-tokens.mjs` to ensure new tokens pass.

---

### Phase 3: Tailwind Config Update (D0-P2 - NOT IN SCOPE FOR D0-P1)

**Status**: DEFERRED to D0-P2

**Actions**:
1. Update `tailwind.config.js` to reference D0-conformant variables
2. Add utility classes for new tokens
3. Keep old utility classes for backwards compatibility

**Example**:
```javascript
// tailwind.config.js
export default {
  theme: {
    extend: {
      colors: {
        // NEW: D0-conformant
        primary: {
          DEFAULT: 'var(--color-primary)',
          hover: 'var(--color-primary-hover)',
          foreground: 'var(--color-primary-foreground)',
        },

        // OLD: Keep for backwards compatibility
        'old-primary': 'hsl(var(--primary))',
      },
    },
  },
};
```

**Validation**: Run `npm run build` to ensure Tailwind config is valid.

---

### Phase 4: Component Migration (D1/D2 - NOT IN SCOPE FOR D0-P1)

**Status**: DEFERRED to D1/D2 (Atomic Components phase)

**Actions**:
1. Migrate components file-by-file to use D0 tokens
2. Replace hardcoded hex/rgba with token references
3. Update Tailwind class usage to D0 utilities
4. Test each component after migration

**Priority Order**:
1. Core UI components (buttons, inputs, cards)
2. Layout components (headers, sidebars)
3. Page-level components
4. Feature-specific components

**Per-Component Checklist**:
- [ ] Replace hardcoded colors with `var(--color-*)` or Tailwind utilities
- [ ] Replace hardcoded spacing with `var(--space-*)` or Tailwind spacing
- [ ] Replace hardcoded shadows with `var(--shadow-*)`
- [ ] Update tests if component snapshots change
- [ ] Visual regression test

---

### Phase 5: Deprecation & Cleanup (D3+ - NOT IN SCOPE FOR D0-P1)

**Status**: DEFERRED to post-D2

**Actions**:
1. Remove old CSS variables from `src/index.css`
2. Remove `src/assets/brand/colors.css` import (if fully migrated)
3. Remove old Tailwind utilities
4. Run ESLint with strict "no raw values" rule
5. Final validation sweep

**Validation**: Run all validators with strict mode:
- `node scripts/validate-tokens.mjs --verbose`
- `node scripts/validate-contrast.mjs`
- `npm run lint` (should have 0 errors)

---

## D0-P1 Scope: What's In and What's Out

### IN SCOPE for D0-P1 (Complete):
- ✅ Define canonical token taxonomy
- ✅ Create 4 JSON token exports
- ✅ Implement validation scripts
- ✅ Document migration strategy (this document)

### OUT OF SCOPE for D0-P1 (Deferred):
- ❌ Actually migrating CSS variables
- ❌ Actually migrating components
- ❌ Removing old token sources
- ❌ Breaking changes to existing code

**Rationale**: D0-P1 establishes the "single source of truth" as a deliverable, not as a replacement. Replacement happens in later phases.

---

## Risk Mitigation

### Risk: Breaking the Application During Migration

**Mitigation**: Dual-layer approach
- Keep old tokens active during migration
- Add new tokens alongside old tokens
- Migrate components gradually
- Only remove old tokens after 100% migration

### Risk: Naming Conflicts

**Mitigation**: Prefix strategy
- Old tokens: Keep current names (`--primary`, `--brand-*`)
- New tokens: Use D0 names (`--color-primary`, etc.)
- No overlap, no conflicts

### Risk: Lost Context from Brand Colors

**Mitigation**: Semantic mapping
- `--brand-tufts` maps to `--color-primary`
- `--brand-alice` maps to `--color-background-muted`
- Document mappings in migration guide

---

## Engineer Handoff for Future Phases

### For D0-P2 (CSS Variable Scaffolding):

**Task**: Add D0-conformant CSS variables to `src/index.css`

**Input**: `docs/design/tokens/skeldir-tokens-*.json` (canonical source)

**Output**: CSS variables in `src/index.css` following D0 naming

**Example**:
```css
:root {
  /* From skeldir-tokens-color.json */
  --color-primary: hsl(213, 74%, 63%);
  --color-primary-hover: hsl(213, 74%, 55%);
  --color-success: hsl(142, 76%, 36%);

  /* From skeldir-tokens-spacing.json */
  --space-1: 4px;
  --space-2: 8px;
  --space-4: 16px;

  /* etc... */
}
```

**Validation**: `node scripts/validate-tokens.mjs` must pass.

### For D1/D2 (Component Migration):

**Task**: Migrate components to use D0 tokens

**Checklist per component**:
1. Find all hardcoded values (hex, rgba, px for spacing)
2. Replace with D0 token references
3. Test component visually
4. Update snapshots if needed

**Tools**:
- ESLint will warn about hardcoded values
- Validation script will catch violations

---

## Success Criteria

### D0-P1 Success (CURRENT PHASE):
- [x] Canonical tokens defined (91 tokens)
- [x] JSON exports created and validated
- [x] Migration strategy documented
- [x] No breaking changes to existing code

### Future Phase Success:
- [ ] All components use D0 tokens (D1/D2)
- [ ] Zero hardcoded values in code (D2/D3)
- [ ] Old token sources removed (D3+)
- [ ] ESLint strict mode passes (D3+)

---

## Appendix: Token Mapping Reference

### Brand Color → D0 Token Mapping

| Current Brand Token | D0 Canonical Token | Notes |
|---------------------|-------------------|-------|
| `--brand-alice` (Alice Blue #E9F5FF) | `--color-background-muted` | Light background |
| `--brand-jordy` (Jordy Blue #93BFEF) | `--color-chart-1` | Data visualization |
| `--brand-tufts` (Tufts Blue #468BE6) | `--color-primary` | Primary action color |
| `--brand-cool-black` (#092F64) | `--color-text-primary` | Dark text |
| `--brand-success` (#16A34A) | `--color-success` | Success state |
| `--brand-warning` (#F59E0B) | `--color-warning` | Warning state |
| `--brand-error` (#F97316) | `--color-error` | Error state |
| `--brand-critical` (#B91C1C) | `--color-destructive` | Destructive actions |

### Spacing → D0 Token Mapping

| Current Spacing Token | D0 Canonical Token | Value |
|-----------------------|-------------------|-------|
| `--spacing-xs` (0.5rem / 8px) | `--space-2` | 8px |
| `--spacing-sm` (0.75rem / 12px) | `--space-3` | 12px |
| `--spacing-md` (1rem / 16px) | `--space-4` | 16px |
| `--spacing-lg` (1.5rem / 24px) | `--space-6` | 24px |
| `--spacing-xl` (2rem / 32px) | `--space-8` | 32px |
| `--spacing-2xl` (3rem / 48px) | `--space-12` | 48px |

---

**Document Status**: READY FOR D0-P2+ EXECUTION
**D0-P1 Status**: COMPLETE (migration strategy defined but NOT executed)
**Next Action**: D0-P2 CSS Variable Scaffolding (when initiated)
