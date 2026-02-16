# D2 Composite Component System — Authoritative Scope Manifest

**Status**: LOCKED (D2-P0)
**Date**: 2026-02-10
**Authority**: This document is the single source of truth for D2 scope classification
**Exit Gate**: All observed candidates must be classified as `D2` or `NON_D2` with zero "unclassified" entries

---

## 1. D2 Scope Definition & Admission Criteria

### What is D2-Authoritative?

A component is classified as **D2-authoritative** (reusable composite) if it meets ALL criteria:

1. **Composition Pattern**: Composes D1 atoms into a reusable pattern (not raw div/spans)
2. **Data via Props**: Accepts data through props (not hardcoded to specific API hooks or business logic)
3. **Context Independence**: Can be used across multiple screens/contexts (not tied to one specific screen)
4. **Generic Intent**: Represents a general UI pattern (modal, card, status indicator), not domain-specific business logic

### What is NOT D2? (Screen-Specific / Feature-Level)

Components classified as **NON_D2** typically:

- Hardcoded to specific business domains (channels, reconciliation, verification)
- Tied to specific API hooks or data fetching logic
- Contain screen-specific titles, content, or navigation
- Meant for single-use in a specific dashboard context

---

## 2. Observed vs Expected Inventory

### Observed D2 Candidates (30 total)

Exhaustive inventory from forensic evidence (D2_COMPOSITE_COMPONENT_SYSTEM_CONTEXT.md):

#### Dashboard Folder (`src/components/dashboard/`)
1. ActivitySection.tsx
2. BulkActionModal.tsx
3. BulkActionToolbar.tsx
4. ChannelPerformanceDashboard.tsx
5. DataConfidenceBar.tsx
6. DataIntegrityMonitor.tsx
7. DataReconciliationStatus.tsx
8. DataReconciliationStatusHeader.tsx
9. MathematicalValidationCallout.tsx
10. ModelComparisonChart.tsx
11. PlatformCard.tsx
12. PlatformVarianceCard.tsx
13. PlatformVarianceGrid.tsx
14. PlatformVarianceGridNew.tsx
15. RevenueOverview.tsx
16. SidebarPrimaryContent.tsx
17. SidebarUtilitiesContent.tsx
18. UserInfoCard.tsx
19. VerificationFlowIndicator.tsx
20. VerificationShowcase.tsx
21. VerificationToast.tsx

#### Error Banner Folder (`src/components/error-banner/`)
22. ErrorBanner.tsx
23. ErrorBannerContainer.tsx
24. ErrorBannerProvider.tsx
25. ErrorBannerContext.tsx

#### Root Level (`src/components/`)
26. ConfidenceScoreBadge.tsx
27. ConfidenceTooltip.tsx
28. DashboardShell.tsx
29. DualRevenueCard.tsx
30. EmptyState.tsx

---

## 3. Authoritative Classification (Zero Unclassified Entries)

### D2-Authoritative Composites (9 components)

| Component | Location | Rationale | State Machine | Token Compliance |
|-----------|----------|-----------|---------------|------------------|
| **ActivitySection** | dashboard/ | Generic activity list with full state machine (loading/error/empty/success), accepts data via props, uses RequestStatus | ✅ Full | ✅ Clean |
| **UserInfoCard** | dashboard/ | Generic user profile card pattern, reusable across contexts | ⚠️ Partial | ✅ Clean |
| **DataConfidenceBar** | dashboard/ | Generic confidence/status indicator pattern | ⚠️ Partial | ✅ Clean |
| **BulkActionModal** | dashboard/ | Generic modal pattern for bulk actions | ⚠️ Partial | 🔍 Needs audit |
| **BulkActionToolbar** | dashboard/ | Generic toolbar pattern for bulk operations | ⚠️ Partial | 🔍 Needs audit |
| **ErrorBanner** | error-banner/ | Generic error banner pattern, RFC 7807 compliant | ⚠️ Partial | 🔍 Needs audit |
| **ErrorBannerContainer** | error-banner/ | Supporting container for error banner system | N/A | 🔍 Needs audit |
| **ErrorBannerProvider** | error-banner/ | Context provider for error banner state | N/A | 🔍 Needs audit |
| **ConfidenceScoreBadge** | root | Generic confidence score badge indicator | N/A | 🔍 Needs audit |

**Total D2-Authoritative**: 9 components

### NON_D2 — Screen-Specific / Feature-Level Components (21 components)

| Component | Location | Rationale |
|-----------|----------|-----------|
| **ChannelPerformanceDashboard** | dashboard/ | Hardcoded to channel attribution domain, uses specific `useChannelPerformance` hook, screen-specific titles |
| **DataIntegrityMonitor** | dashboard/ | Screen-specific monitoring dashboard for platform integrity |
| **DataReconciliationStatus** | dashboard/ | Large reconciliation dashboard, screen-specific |
| **DataReconciliationStatusHeader** | dashboard/ | Header specific to reconciliation screen |
| **MathematicalValidationCallout** | dashboard/ | Domain-specific callout for validation logic |
| **ModelComparisonChart** | dashboard/ | Chart specific to model comparison screen |
| **PlatformCard** | dashboard/ | Platform-specific card with hardcoded color map, domain logic |
| **PlatformVarianceCard** | dashboard/ | Variance-specific card, domain logic |
| **PlatformVarianceGrid** | dashboard/ | Variance grid layout, screen-specific |
| **PlatformVarianceGridNew** | dashboard/ | Refactored variance grid, still screen-specific |
| **RevenueOverview** | dashboard/ | Revenue-specific overview, domain logic |
| **SidebarPrimaryContent** | dashboard/ | Sidebar content specific to dashboard navigation |
| **SidebarUtilitiesContent** | dashboard/ | Sidebar utilities specific to dashboard |
| **VerificationFlowIndicator** | dashboard/ | Verification flow specific indicator |
| **VerificationShowcase** | dashboard/ | Verification showcase screen-specific |
| **VerificationToast** | dashboard/ | Verification-specific toast notifications |
| **ErrorBannerContext** | error-banner/ | Supporting infrastructure (not a composite, just context definition) |
| **ConfidenceTooltip** | root | Confidence-specific tooltip (borderline, but domain-specific) |
| **DashboardShell** | root | Shell/layout specific to dashboard screens |
| **DualRevenueCard** | root | Revenue comparison card, domain-specific (borderline) |
| **EmptyState** | root | Hardcoded to "No Platforms Connected", screen-specific text and links |

**Total NON_D2**: 21 components

---

## 4. D2 Physical Boundary Authority

### Canonical Import Surface

**Path**: `src/components/composites/index.ts`

All D2-authoritative composites MUST be exported through this barrel. This is the single canonical import surface for D2.

**Strategy**: Authority Proxy Boundary (S2)
- D2 composites remain in current file locations initially
- Barrel re-exports from current paths
- Physical relocation deferred to later phases (D2-P1+)
- This creates immediate enforcement handle with minimal churn

### Folder Structure

```
src/components/composites/
├── index.ts              # Authoritative barrel export (D2 canonical surface)
└── README.md             # D2 admission rules and scope policy
```

Future phases may introduce:
```
src/components/composites/
├── molecules/            # Simple compositions (2-3 D1 atoms)
├── organisms/            # Complex compositions (multiple molecules + atoms)
└── index.ts
```

---

## 5. Admission Rules (How New Composites Enter D2)

### Admission Checklist

A component may be admitted to D2 only if:

1. ✅ **D1 Composition**: Composes D1 atoms from `@/components/ui/*` (no raw div bypasses)
2. ✅ **Token Compliance**: Uses D0 tokens (HSL custom properties or Tailwind utilities, zero hardcoded hex colors)
3. ✅ **State Machine**: Data-bearing composites must implement full state machine (loading/error/empty/success)
4. ✅ **Prop-Driven**: Accepts data via props, no hardcoded business logic or API hooks
5. ✅ **Reusability Intent**: Demonstrable use in 2+ contexts OR clear generic pattern (modal, card, toolbar)
6. ✅ **Export Authority**: Added to `src/components/composites/index.ts` barrel

### Rejection Criteria

A component is rejected from D2 if:

- ❌ Hardcoded to specific business domain (channels, reconciliation, verification)
- ❌ Uses specific API hooks (useChannelPerformance, useReconciliation, etc.)
- ❌ Contains screen-specific navigation or titles
- ❌ Token violations (hardcoded hex colors, inline styles)
- ❌ Single-use intent (built for one specific screen)

---

## 6. Current D2 Inventory Status

### Summary

- **Total Observed Candidates**: 30
- **D2-Authoritative**: 9 (30%)
- **NON_D2 (Screen-Specific)**: 21 (70%)
- **Unclassified**: 0 (0%) ✅

### Exit Gate 1 Status: **PASS** ✅

All observed candidates are classified with explicit rationale. Scope is decidable.

---

## 7. Known Technical Debt in D2-Authoritative Set

### Token Violations (Must Fix in D2-P2)

Components requiring token remediation:
- **BulkActionModal**: Needs audit
- **BulkActionToolbar**: Needs audit
- **ErrorBanner**: Needs audit
- **ConfidenceScoreBadge**: Needs audit

### State Machine Gaps (Must Fix in D2-P3)

Components requiring full state machine implementation:
- **UserInfoCard**: Only models populated state
- **DataConfidenceBar**: Partial state handling
- **BulkActionModal**: Needs loading/error states
- **BulkActionToolbar**: Needs disabled/loading states
- **ErrorBanner**: Partial error state modeling

### D1 Composition Integrity (Must Audit in D2-P1)

All D2 composites must be audited for:
- Zero raw div/span bypasses (must use D1 Card, Button, Badge, etc.)
- Consistent import patterns from `@/components/ui/*`
- No external UI library bypasses

---

## 8. Appendix: Classification Edge Cases & Decisions

### Borderline Cases

**DualRevenueCard** — Classified as NON_D2
- Rationale: Revenue-specific domain logic, likely hardcoded to revenue comparison context
- Could be promoted to D2 if refactored to generic "dual metric card" with data props

**ConfidenceTooltip** — Classified as NON_D2
- Rationale: Confidence-specific tooltip, likely contains domain-specific formatting
- Could be promoted to D2 if refactored to generic tooltip pattern

**PlatformCard** — Classified as NON_D2
- Rationale: Hardcoded color map for platform statuses, domain-specific
- Evidence shows token violations (hardcoded hex colors)
- Could be promoted to D2 if refactored to generic status card with prop-driven colors

### Reclassification Process

Components may be reclassified from NON_D2 → D2 only if:
1. Refactored to meet all admission criteria
2. Token violations remediated
3. Full state machine implemented (if data-bearing)
4. Demonstrated reusability in 2+ contexts
5. Approved via scope manifest update (requires evidence)

---

## 9. D2-P1 Bypass Exception Registry

The following bypasses are **explicitly permitted** with documented rationale. Any bypass NOT listed here is a **FAIL** for Exit Gate P1-B.

### EXC-001: ConfidenceScoreBadge — Full D1 Bypass (Badge + Tooltip)

**Component**: `ConfidenceScoreBadge.tsx`
**Bypassed D1 Atoms**: Badge, Tooltip
**Status**: EXCEPTION — architectural divergence

**Rationale**: ConfidenceScoreBadge requires capabilities that fundamentally exceed D1 Badge and D1 Tooltip:

1. **Animated count-up** (0→score via requestAnimationFrame, 600ms ease-out cubic) — D1 Badge has no animation support
2. **IntersectionObserver integration** — triggers animation only when visible in viewport; D1 Badge is a static element
3. **Glass UI with backdrop blur** — uses `backdrop-filter: blur()`, computed `rgba()` backgrounds, and `linear-gradient()` overlays; D1 Badge supports only variant-based color schemes
4. **Tier-dot indicator** — secondary animated sub-element with pulse animation for high-confidence scores; no D1 Badge equivalent
5. **Custom ConfidenceTooltip** (NON_D2 import) — implements viewport-aware positioning intelligence and tier-specific content; D1 Tooltip wraps Radix with fixed positioning

Wrapping D1 Badge would require overriding every aspect of its rendering, making the wrapper the actual component. The D1 Badge contract (static colored label) is architecturally incompatible with this component's requirements.

**Scope of exception**: Full component. No partial D1 adoption is feasible without architectural mismatch.

### EXC-002: ErrorBanner — Structural D1 Bypass (Alert shell)

**Component**: `ErrorBanner.tsx`
**Bypassed D1 Atom**: Alert (for banner structure only)
**Status**: EXCEPTION — architectural divergence

**Rationale**: ErrorBanner is a **floating, animated, auto-dismissing notification** with:
- CSS keyframe entrance/exit animations (`bannerSlideIn`/`bannerSlideOut`)
- Auto-dismiss timer with severity-based duration
- Focus management (captures focus on mount, restores on dismiss)
- Stacked positioning system (`position: fixed`, z-index 9999, index-based offset)
- Escape key handling scoped to banner focus context

D1 Alert is a **static, inline, non-interactive** element (`role="alert"`, no dismiss, no animation, no positioning). Using Alert as the ErrorBanner shell would require overriding its role, position, animation, and interactivity — effectively replacing the entire component.

**Partial remediation applied**: Close button and action button now use D1 `Button` atom (remediated in D2-P1).

### EXC-003: BulkActionModal — Native `<select>` Element

**Component**: `BulkActionModal.tsx`
**Bypassed D1 Atom**: Select (Radix)
**Status**: EXCEPTION — UX fidelity

**Rationale**: The "Assign to Team Member" dropdown uses a native HTML `<select>` element. D1 Select wraps Radix Select, which renders a **fully custom dropdown** (portal, keyboard navigation, custom styling). Native `<select>` provides **OS-native UX** (platform-consistent appearance, mobile optimization, accessibility built-in). For a 3-option dropdown in a modal context, native `<select>` is the appropriate choice.

**Note**: All other BulkActionModal elements (Dialog, Button, Input, Textarea, Label, Alert) were remediated to use D1 atoms in D2-P1.

---

## 10. Scope Lock Enforcement

### Mechanical Verification

Scope lock is enforced via:
- `scripts/validate-d2-scope.mjs` — Validates manifest ↔ barrel export coherence
- `scripts/validate-d2-composition.mjs` — Validates D1 atom composition integrity (D2-P1)
- Local dev route `/d2/scope` (future) — Visual inventory and state matrix

### Drift Detection

Drift is detected when:
- New component created in `src/components/dashboard/` without scope classification
- Import from D2 composite occurs outside of `@/components/composites` barrel
- Manifest entry exists but barrel export is missing (or vice versa)
- D2 composite imports from forbidden tiers (pages/screens/features)
- D2 composite uses raw HTML elements when equivalent D1 atom exists (without exception tag)

---

**End of Scope Manifest**

**Certification**: This manifest represents the authoritative D2 scope classification as of 2026-02-10. All 30 observed candidates are classified with zero unclassified entries. Scope is decidable and locked for D2-P0.
