# D2-P3 Evidence Pack: State Machine Contract for Data-Bearing Composites

**Investigation Date**: 2026-02-10
**Environment**: Local Windows IDE (local-only, no git operations)
**Working Directory**: `c:\Users\ayewhy\II SKELDIR II\frontend`
**Directive Anchor**: D2-P3 — loading/empty/error/populated state contract

---

## Executive Summary

D2-P3 establishes a **normalized state contract** for all data-bearing D2 composites, ensuring every composite that depends on external data deterministically renders **loading / empty / error / populated** states via the `RequestStatus` D1 substrate.

**Before D2-P3**: 1 of 3 data-bearing composites had full state coverage. The other 2 assumed populated state only.

**After D2-P3**: 3 of 3 data-bearing composites have full 4-state coverage via the normalized contract. Deterministic fixtures exist for harness consumption.

---

## 1. Hypothesis Validation Summary

### H3.0 — "Data-bearing" set is not formally decidable

**Status**: RESOLVED

**Evidence**: The D2-authoritative set (9 composites, per D2-P0/D2_SCOPE.md) was classified into data-bearing vs non-data-bearing using the operational definition:

> "Data-bearing" if the composite depends on external data lifecycle (accepts a dataset that can be loading/empty/error, or represents a request lifecycle status indicator occupying section-level screen real estate).

**DATA-BEARING (3)**:

| Component | Rationale |
|-----------|-----------|
| **ActivitySection** | Accepts `data: ActivityItem[]` + explicit `status` prop. Request lifecycle composite. |
| **DataConfidenceBar** | Receives confidence metrics from backend verification service. Section-level status indicator. |
| **UserInfoCard** | Receives user profile data from authentication/API. Profile card with data lifecycle. |

**NON-DATA-BEARING (6)**:

| Component | Rationale |
|-----------|-----------|
| **ConfidenceScoreBadge** | Display-only indicator. Single `score: number` with null graceful degradation ("—"). Parent owns data lifecycle. |
| **BulkActionModal** | User-initiated action modal. Receives pre-selected data (already resolved). No async lifecycle. |
| **BulkActionToolbar** | Selection toolbar with `isProcessing` action state. Not a data-fetch lifecycle. |
| **ErrorBanner** | IS the error display infrastructure itself. Does not have its own data lifecycle. |
| **ErrorBannerContainer** | Container rendering banner list from context. Layout component. |
| **ErrorBannerProvider** | Context provider. Infrastructure, not data-bearing. |

### H3.1 — Most composites implicitly assume populated state

**Status**: CONFIRMED (pre-remediation), RESOLVED (post-remediation)

**Pre-remediation matrix**:

| Component | Loading | Empty | Error | Populated |
|-----------|---------|-------|-------|-----------|
| ActivitySection | ✅ | ✅ | ✅ | ✅ |
| DataConfidenceBar | ❌ | ❌ | ❌ | ✅ |
| UserInfoCard | ❌ | ❌ | ❌ | ✅ |

**Post-remediation matrix**:

| Component | Loading | Empty | Error | Populated |
|-----------|---------|-------|-------|-----------|
| ActivitySection | ✅ | ✅ | ✅ | ✅ |
| DataConfidenceBar | ✅ | ✅ | ✅ | ✅ |
| UserInfoCard | ✅ | ✅ | ✅ | ✅ |

### H3.2 — RequestStatus pattern exists but is not the enforced contract

**Status**: CONFIRMED (pre-remediation), RESOLVED (post-remediation)

**Investigation findings**:
- `RequestStatus` lives at `src/components/ui/request-status.tsx` (D1 atom)
- It handles all 4 states: `loading | success | empty | error`
- Features: skeleton variants (`text`, `avatar`, `card`, `activityList`), animated transitions, ARIA live regions, retry button for error state
- Pre-remediation: only ActivitySection used it
- Post-remediation: all 3 data-bearing composites use it as their non-success render substrate

### H3.3 — State reachability is not deterministic

**Status**: CONFIRMED (pre-remediation), RESOLVED (post-remediation)

**Resolution**: Every data-bearing composite now:
1. Accepts a `status: 'loading' | 'error' | 'empty' | 'success'` prop (deterministic, no networking required)
2. Has exported fixtures in `src/components/composites/fixtures.ts` providing complete props for each state
3. Exposes `data-status` attribute on root element for inspection

### H3.4 — Ad-hoc state handling is scattered and inconsistent

**Status**: CONFIRMED (pre-remediation), RESOLVED (post-remediation)

**Resolution**: A normalized `DataCompositeStatus` type is exported from `src/components/composites/index.ts`. All data-bearing composites consume the same status union and delegate non-success rendering to `RequestStatus`.

---

## 2. State Coverage Matrix (Post-Remediation)

| # | Component | Loading | Empty | Error | Populated | Contract | Substrate |
|---|-----------|---------|-------|-------|-----------|----------|-----------|
| 1 | **ActivitySection** | ✅ | ✅ | ✅ | ✅ | `status` prop | `RequestStatus` |
| 2 | **DataConfidenceBar** | ✅ | ✅ | ✅ | ✅ | `status` prop | `RequestStatus` |
| 3 | **UserInfoCard** | ✅ | ✅ | ✅ | ✅ | `status` prop | `RequestStatus` |

**Coverage**: 3/3 = **100%**

---

## 3. Code Citations (File Paths + Line Ranges)

### ActivitySection (pre-existing, no changes needed)
- **File**: `src/components/dashboard/ActivitySection.tsx`
- **Status prop**: L11 (`status: 'loading' | 'error' | 'empty' | 'success'`)
- **Success branch**: L28 (`status === 'success' && data.length > 0`)
- **Error branch**: L39-43 (via RequestStatus spread)
- **Empty branch**: L44-47 (via RequestStatus spread)
- **Loading branch**: L48-50 (via RequestStatus spread)

### DataConfidenceBar (remediated in D2-P3)
- **File**: `src/components/dashboard/DataConfidenceBar.tsx`
- **Status prop**: L18 (`status: 'loading' | 'error' | 'empty' | 'success'`)
- **onRetry prop**: L33 (`onRetry: () => void`)
- **Non-success early return**: L161-191 (RequestStatus with status-specific messages)
- **data-status attribute**: L171, L201
- **Success branch**: L193+ (original populated render)

### UserInfoCard (remediated in D2-P3)
- **File**: `src/components/dashboard/UserInfoCard.tsx`
- **Status prop**: L11 (`status: 'loading' | 'error' | 'empty' | 'success'`)
- **onRetry prop**: L16 (`onRetry: () => void`)
- **data-status attribute**: L24
- **Success branch**: L36-60 (original populated render)
- **Non-success branch**: L62-76 (RequestStatus with status-specific messages)

---

## 4. Normalized Contract Architecture

### Type Definition
```typescript
// src/components/composites/index.ts
export type DataCompositeStatus = 'loading' | 'error' | 'empty' | 'success';
```

### Contract Pattern (consistent across all data-bearing composites)
```
Props: { status: DataCompositeStatus, onRetry: () => void, ...domainData }
  |
  +-- status !== 'success' --> <RequestStatus status={status} ... />
  |
  +-- status === 'success' --> <populated render with domainData />
```

### Substrate
- **RequestStatus** (`src/components/ui/request-status.tsx`, D1 atom)
- Provides: skeleton loading, error icon + retry button, empty icon + message
- Features: animated transitions, ARIA live regions, `data-testid` attributes
- Skeleton variants: `text`, `avatar`, `card`, `activityList`

---

## 5. Deterministic Fixtures (State Reachability)

**File**: `src/components/composites/fixtures.ts`

Each data-bearing composite has 4 fixture objects:

| Fixture Set | Keys | Harness-Ready |
|-------------|------|---------------|
| `activitySectionFixtures` | `loading`, `empty`, `error`, `populated` | ✅ |
| `dataConfidenceBarFixtures` | `loading`, `empty`, `error`, `populated` | ✅ |
| `userInfoCardFixtures` | `loading`, `empty`, `error`, `populated` | ✅ |

**Programmatic access**:
```typescript
import { allDataBearingFixtures, stateKeys } from '@/components/composites';
// allDataBearingFixtures.ActivitySection.loading → complete props for loading state
// stateKeys → ['loading', 'empty', 'error', 'populated']
```

---

## 6. Negative Control (Non-Vacuity Proof)

**Method**: Created a mutant of UserInfoCard with empty/error branches replaced by `false`:
```
mutant = content
  .replace(/status === 'error'/g, 'false /* mutant: error removed */')
  .replace(/status === 'empty'/g, 'false /* mutant: empty removed */');
```

**Result**:
```
  PASS: loading branch
  FAIL: empty branch
  FAIL: error branch
  PASS: success branch

NEGATIVE CONTROL CONFIRMED: Verification correctly detected missing state branches.
```

The verification method is **non-vacuous**: it would catch a composite that omits any state branch.

---

## 7. Build Verification

| Check | Result |
|-------|--------|
| `npx vite build` | ✅ PASS (1642 modules, 4.51s) |
| `npm run lint` | ✅ PASS (0 errors, 252 warnings — all pre-existing) |
| `npx tsc --noEmit` (modified files) | ✅ PASS (0 errors in changed files) |
| `node scripts/validate-d2-scope.mjs` | ✅ PASS (9/9 components, all invariants hold) |

---

## 8. Exit Gate Assessment

### Exit Gate P3-A — State machine coverage = 100% for data-bearing

**Status**: ✅ PASS

**Evidence**: Post-remediation matrix shows ✅ in all four columns for all 3 data-bearing composites. No composite assumes populated-only.

### Exit Gate P3-B — No ad-hoc state handling

**Status**: ✅ PASS

**Evidence**: All 3 data-bearing composites use the normalized `DataCompositeStatus` type and delegate non-success rendering to `RequestStatus`. No scattered `if (isLoading)` without matching empty/error equivalents exists in any data-bearing composite.

### Exit Gate P3-C — Deterministic reachability substrate exists

**Status**: ✅ PASS

**Evidence**: Every data-bearing composite accepts a `status` prop that deterministically selects the render branch. Exported fixtures in `src/components/composites/fixtures.ts` provide complete props for each state. The upcoming `/d2/composites` harness can consume these fixtures via `import { allDataBearingFixtures, stateKeys } from '@/components/composites'`.

---

## 9. Files Modified (Local Only)

| File | Change |
|------|--------|
| `src/components/dashboard/DataConfidenceBar.tsx` | Added `status` + `onRetry` props, `RequestStatus` import, non-success early return branch, `data-status` attr |
| `src/components/dashboard/UserInfoCard.tsx` | Added `status` + `onRetry` props, `RequestStatus` import, success/non-success branching, `data-status` attr |
| `src/components/composites/index.ts` | Added `DataCompositeStatus` type export, fixture re-exports |
| `src/components/composites/fixtures.ts` | **NEW** — Deterministic state fixtures for all data-bearing composites |
| `docs/forensics/D2_P3_EVIDENCE.md` | **NEW** — This evidence pack |

---

## 10. Root Cause Validation

| Root Cause Hypothesis | Status |
|-----------------------|--------|
| R3.1 — No enforced "data-bearing composite contract" | ✅ CONFIRMED and RESOLVED. `DataCompositeStatus` type + `RequestStatus` substrate now enforced. |
| R3.2 — Tiering confusion (D1 vs D2 vs ui/) | ✅ CONFIRMED and RESOLVED. `RequestStatus` is correctly tiered at D1 (`ui/`), consumed by D2. |
| R3.3 — UX requirements not encoded in D2 components | ✅ CONFIRMED and RESOLVED. Loading/empty/error branches with user-facing messages now present. |
| R3.4 — Lack of state matrix made gaps invisible | ✅ CONFIRMED and RESOLVED. This evidence pack IS the state matrix. |

---

**Certification**: All evidence gathered and changes applied locally. No git operations performed. All claims are falsifiable via the verification commands documented above.
