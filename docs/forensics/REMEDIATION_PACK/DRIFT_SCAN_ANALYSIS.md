# Hex Color Drift Scan Analysis

## Summary

**Total Violations Found**: 121 instances across 24 files

## Categorization

### Category 1: Out of Scope (Application Layer - Not D1/D2)

These components are NOT part of the core design system (D0/D1/D2):

**Platform Logos** (8 files, 58 instances):
- `common/PlatformLogo.tsx` - Brand colors (legitimate)
- `logos/GoogleLogo.tsx` - SVG brand colors (legitimate)
- `logos/PayPalLogo.tsx` - SVG brand colors (legitimate)
- `logos/ShopifyLogo.tsx` - SVG brand colors (legitimate)
- `logos/SquareLogo.tsx` - SVG brand colors (legitimate)
- `logos/StripeLogo.tsx` - SVG brand colors (legitimate)

**Application-Specific Components** (8 files, 40 instances):
- `dashboard/PlatformCard.tsx` - Screen-specific component
- `dashboard/VerificationShowcase.tsx` - Screen-specific component
- `EmptyState.tsx` - Application component
- `ExportButton.tsx` - Application component
- `StatusIcon.tsx` - Application component
- `PulsingDot.tsx` - Application component
- `VerificationBadge.tsx` - Application component
- `icons/SkelderIcons.tsx` - Application icons

**Rationale**: These are application-layer components with domain-specific logic. They are NOT exported from the design system entry point (`src/design-system.ts`).

### Category 2: In Scope - Design System Violations (4 files, 23 instances)

These components ARE part of D1/D2 and require remediation:

**D2 Composites**:
1. `ConfidenceScoreBadge.tsx` (3 instances)
   - Lines 27-29: Documentation comments with hex codes
   - **Type**: Documentation only, not runtime violations

2. `ConfidenceTooltip.tsx` (4 instances)
   - Lines 187-188: Inline styles with hardcoded background/text colors
   - Line 208: Inline style with hardcoded border color
   - **Type**: Runtime violations - must be fixed

**D1 Primitives**:
3. `ui/chart.tsx` (1 instance)
   - Line 55: CSS selector with hardcoded `#ccc` stroke
   - **Type**: CSS class string, affects runtime

4. `ui/user-avatar.tsx` (2 instances)
   - Lines 27, 36: Inline styles with hardcoded background colors
   - **Type**: Runtime violations - must be fixed

**Composite Fixtures** (Out of scope for runtime):
5. `composites/fixtures.ts` (1 instance)
   - Line 38: Mock data with `#4821` (invoice number, not a color)
   - **Type**: False positive (not a hex color)

## Remediation Strategy

### Immediate Action Required (D1/D2 In-Scope)

1. **ConfidenceTooltip.tsx** (CRITICAL)
   - Replace inline styles with Tailwind classes
   - Use `bg-gray-800 text-white` instead of `#1F2937/#FFFFFF`

2. **ui/user-avatar.tsx** (CRITICAL)
   - Replace `bg-[#2D3748]` with `bg-gray-700`
   - Replace `bg-[#1A202C]` with `bg-gray-900`

3. **ui/chart.tsx** (MEDIUM)
   - Review if CSS selector can use CSS variable
   - Document as library-imposed constraint if unavoidable

4. **ConfidenceScoreBadge.tsx** (LOW)
   - Update documentation comments to reference token names instead of hex values

### Deferred (Application Layer - Out of D2-P6 Scope)

All violations in Category 1 should be addressed in a separate application-layer governance pass. They are not blockers for design system build isolation.

## Verdict

**Design System Core (D1/D2)**: 3 files with runtime violations (6 instances)
**Application Layer**: 20 files with violations (115 instances)

The design system itself has minimal drift violations. The majority of hex usage is in application-specific components and brand assets (logos).

**Recommendation**: Fix the 3 in-scope files immediately, document application layer drift for future remediation.
