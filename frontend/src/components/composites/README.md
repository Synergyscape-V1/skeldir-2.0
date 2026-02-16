# D2 Composite Component System

**Status**: D2-P0 Complete ✅
**Authority**: This is the canonical import surface for all D2-authoritative composites
**Scope Manifest**: `../../../docs/forensics/D2_SCOPE.md`

---

## Overview

This folder represents the **D2 layer** of the design system: reusable composite components that combine D1 atoms into higher-level UI patterns.

**Strategy**: Authority Proxy Boundary (S2)
- Components remain in current file locations (dashboard/, error-banner/, root)
- This barrel re-exports from current paths
- Physical relocation deferred to D2-P1+
- Creates immediate enforcement handle with minimal churn

---

## Usage

### Import from Barrel (Canonical)

```tsx
import { ActivitySection, UserInfoCard, ErrorBanner } from '@/components/composites';
```

**Note**: During D2-P0, legacy imports from original paths are still valid but will be migrated in D2-P1:
```tsx
// Legacy (still works, will be refactored in D2-P1):
import { ActivitySection } from '@/components/dashboard/ActivitySection';
```

---

## D2-Authoritative Components (9)

### Activity & User Components
- **ActivitySection** — Generic activity list with full state machine (loading/error/empty/success)
- **UserInfoCard** — User profile card pattern

### Status & Confidence Indicators
- **DataConfidenceBar** — Confidence/status indicator pattern
- **ConfidenceScoreBadge** — Confidence score badge indicator

### Bulk Action Components
- **BulkActionModal** — Modal pattern for bulk actions
- **BulkActionToolbar** — Toolbar pattern for bulk operations

### Error Banner System
- **ErrorBanner** — RFC 7807 compliant error banner pattern
- **ErrorBannerContainer** — Container for error banner system
- **ErrorBannerProvider** — Context provider for error banner state

---

## Admission Rules

A component may be added to this barrel **ONLY** if:

1. ✅ **D1 Composition**: Composes D1 atoms from `@/components/ui/*` (no raw div bypasses)
2. ✅ **Token Compliance**: Uses D0 tokens (HSL custom properties or Tailwind utilities, zero hardcoded hex colors)
3. ✅ **State Machine**: Data-bearing composites must implement full state machine (loading/error/empty/success)
4. ✅ **Prop-Driven**: Accepts data via props, no hardcoded business logic or API hooks
5. ✅ **Reusability Intent**: Demonstrable use in 2+ contexts OR clear generic pattern
6. ✅ **Classified in Scope Manifest**: Added to `D2_SCOPE.md` with explicit rationale

### Rejection Criteria

A component is **rejected** from D2 if:

- ❌ Hardcoded to specific business domain (channels, reconciliation, verification)
- ❌ Uses specific API hooks (useChannelPerformance, useReconciliation, etc.)
- ❌ Contains screen-specific navigation or titles
- ❌ Token violations (hardcoded hex colors, inline styles)
- ❌ Single-use intent (built for one specific screen)

---

## Testing & Verification

### D2 Composites Harness (Visual State Matrix)

**Route**: `/d2/composites`

Visit this route in your browser to see all D2 composites with interactive state demonstrations:
- **Data-bearing composites**: ActivitySection, UserInfoCard, DataConfidenceBar
  - Toggle between all 4 states: loading / empty / error / populated
  - Verify token compliance (Tailwind classes, no hardcoded hex colors)
  - Test interactivity (retry buttons, etc.)
- **Non-data-bearing composites**: ConfidenceScoreBadge
  - Static showcase of variants and tiers

**Usage**:
```bash
npm run dev
# Navigate to http://localhost:5180/d2/composites
```

**State Toggle**: Use the state selector buttons at the top to switch between loading, empty, error, and populated states for all data-bearing composites simultaneously.

### D2 Boundary Coherence Validation

To verify D2 scope manifest ↔ barrel export coherence:

```bash
npm run validate:d2-scope
```

This validates:
1. All scope manifest components are exported in barrel
2. All barrel exports are declared in scope manifest
3. All component files exist at declared paths

**Non-vacuous**: The validator fails under real violations (tested with negative control).

---

## Next Phases

### D2-P1 — Composition Integrity
- Import surface adoption (enforce barrel imports codebase-wide)
- D1 composition audit (no raw div bypasses)
- Dependency bill of materials

### D2-P2 — Token Compliance
- Fix hardcoded hex colors in all D2 composites
- Replace inline styles with D0 tokens
- Add drift sentinel scan for D2 layer

### D2-P3 — State Machine Enforcement ✅ COMPLETE
- ✅ Full state machine for all data-bearing composites (ActivitySection, UserInfoCard, DataConfidenceBar)
- ✅ RequestStatus pattern implemented universally
- ✅ `/d2/composites` proof harness route built and functional
- ✅ Deterministic fixtures created for all states (loading/empty/error/populated)

---

## Documentation

- **Scope Manifest**: `docs/forensics/D2_SCOPE.md` — Authoritative classification of all D2 candidates
- **Evidence Pack**: `docs/forensics/D2_P0_EVIDENCE.md` — Complete D2-P0 remediation evidence
- **Validator Script**: `scripts/validate-d2-scope.mjs` — Boundary coherence validator

---

**Last Updated**: 2026-02-10 (D2-P0)
