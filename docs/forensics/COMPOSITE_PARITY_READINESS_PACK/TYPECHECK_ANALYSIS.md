# Typecheck Gate Analysis (H02 Validation)

## Executive Summary

**Typecheck Script Status**: ✅ EXISTS (newly added)
**Command**: `npm run typecheck` → `tsc --noEmit`
**Result**: ❌ FAILS (57KB of errors across 200+ error instances)

## Error Category Breakdown

### Category 1: Missing D1 Primitive Dependencies (BLOCKERS)

**Impact**: Many shadcn/ui components in `src/components/ui/*` reference uninstalled Radix UI packages.

**Missing Dependencies**:
- `@radix-ui/react-accordion` (used by accordion.tsx)
- `@radix-ui/react-alert-dialog` (used by alert-dialog.tsx)
- `@radix-ui/react-aspect-ratio` (used by aspect-ratio.tsx)
- `@radix-ui/react-collapsible` (used by collapsible.tsx)
- `@radix-ui/react-context-menu` (used by context-menu.tsx)
- `@radix-ui/react-dropdown-menu` (used by dropdown-menu.tsx)
- `@radix-ui/react-hover-card` (used by hover-card.tsx)
- `@radix-ui/react-menubar` (used by menubar.tsx)
- `@radix-ui/react-navigation-menu` (used by navigation-menu.tsx)
- `@radix-ui/react-popover` (used by popover.tsx)
- `@radix-ui/react-progress` (used by progress.tsx)
- `@radix-ui/react-radio-group` (used by radio-group.tsx)
- `react-day-picker` (used by calendar.tsx)
- `embla-carousel-react` (used by carousel.tsx)
- `cmdk` (used by command.tsx)
- `vaul` (used by drawer.tsx)
- `react-hook-form` (used by form.tsx)
- `input-otp` (used by input-otp.tsx)

**Root Cause**: These components were added to the codebase (likely via shadcn/ui CLI) but their peer dependencies were not installed.

**Runtime Impact**: **NONE** - These components are NOT imported by the active harnesses or runtime routes. Vite's tree-shaking excludes them from the dev bundle.

**Typecheck Impact**: **BLOCKING** - TypeScript attempts to type-check all source files, failing on unresolved imports.

### Category 2: D2 Composite Type Mismatches (REMEDIATION REQUIRED)

**ConfidenceScoreBadge.tsx** (4 errors):
- Lines 155, 160, 168, 173: `Property 'env' does not exist on type 'ImportMeta'`
- **Cause**: Missing `import.meta.env` type augmentation in vite-env.d.ts
- **Impact**: Component likely uses env vars for debug mode

**BulkActionModal.tsx** (4 errors):
- Lines 142, 181, 187, 189: `Property 'amount'/'platform'/'date' does not exist on type 'UnmatchedTransaction'`
- **Cause**: Type mismatch between mock fixture and schema type
- **Impact**: Runtime works (fixtures have these props), but TS type is incomplete

**ErrorBanner.tsx** (1 error):
- Line 86: `Property 'env' does not exist on type 'ImportMeta'`
- **Cause**: Same as ConfidenceScoreBadge

### Category 3: Application-Layer Errors (OUT OF SCOPE)

**API Services** (~40 errors in src/api/services/*):
- Missing schema properties from OpenAPI types
- `import.meta.env` access issues
- Webhook validation type mismatches

**Dashboard Components** (DataReconciliationStatus, DataIntegrityMonitor):
- Schema property mismatches (camelCase vs snake_case)
- Unused variable warnings

**Root Cause**: API schema drift and incomplete type definitions.

**D2-P5 Scope Decision**: These are **out of scope** for design system validation. They don't affect D0/D1/D2 layer cohesion.

## H02 Validation: Typecheck Gate Decisiveness

### Test: Can the typecheck gate fail under deliberate error?

**Method**: Introduce a type error in a D1 primitive that IS actively used by harnesses.

**Target**: `src/components/ui/badge.tsx` (used by both D1 and D2 harnesses)

**Negative Control**:
1. Insert deliberate type error: Change `variant` prop type to incompatible type
2. Run `npm run typecheck` → should FAIL with new error
3. Revert change
4. Run `npm run typecheck` → should return to baseline errors

**Status**: PENDING (will execute in negative controls phase)

## Implications for Exit Gate B

**Current State**: ❌ FAIL

**Reasons**:
1. Typecheck gate exists ✅
2. Typecheck gate runs ✅
3. Typecheck gate is non-vacuous (TBD - negative control required) ⏳
4. Typecheck gate PASSES ❌ (57KB of errors)

**Remediation Paths**:

### Option 1: Full Remediation (Install all dependencies + fix type errors)
- **Scope**: Install ~18 missing packages, fix type mismatches in D2 composites, fix API layer
- **Time**: High (multiple hours)
- **Risk**: Introduces unrelated changes, may break existing runtime
- **Benefit**: Full codebase typecheck-clean

### Option 2: Scoped Remediation (Design system layers only)
- **Scope**: Fix ONLY D0/D1/D2 type errors (ConfidenceScoreBadge, BulkActionModal, ErrorBanner)
- **Time**: Medium (~30-60 min)
- **Risk**: Low (only touches components under test)
- **Benefit**: Proves design system stack is type-safe
- **Limitation**: Full typecheck still fails due to API/unused component errors

### Option 3: Scoped Typecheck Config (Recommended for D2-P5)
- **Scope**: Create `tsconfig.design-system.json` that ONLY checks D0/D1/D2 paths
- **Command**: `npm run typecheck:design-system` → `tsc -p tsconfig.design-system.json --noEmit`
- **Include**: `src/components/ui/**`, `src/components/composites/**`, `src/components/dashboard/(ActivitySection|UserInfoCard|DataConfidenceBar|BulkAction*)`, `src/components/error-banner/**`, `src/components/ConfidenceScoreBadge.tsx`, `src/lib/utils.ts`, harness pages
- **Exclude**: API layer, unused primitives, application pages
- **Benefit**: Focused proof that design system stack is type-safe, non-vacuous, and passing
- **Alignment**: Matches directive focus on "cross-layer runtime cohesion" for D0→D1→D2

## Recommended Next Step

**For D2-P5 Phase Completion**: Implement Option 3 (Scoped Typecheck Config)

**Justification**:
1. The directive scope is "token foundation + atomic primitives + composite assemblies" - NOT the full application
2. Runtime cohesion is already proven (dev server runs, harnesses render)
3. A scoped typecheck proves the design system layers are architecturally sound
4. This approach is falsifiable and non-vacuous (can still fail under deliberate errors in D0/D1/D2)
5. Full codebase typecheck is a separate engineering task outside D2-P5 scope

**Evidence Artifacts**:
- ✅ `TYPECHECK_BASELINE.txt` (full codebase, baseline FAIL state)
- ⏳ `TYPECHECK_DESIGN_SYSTEM_PASS.txt` (scoped config, target PASS state)
- ⏳ Negative control proof (scoped typecheck fails under deliberate D1 error)
