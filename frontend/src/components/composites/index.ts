/**
 * D2 Composite Component System — Authoritative Export Surface
 *
 * This is the CANONICAL import surface for all D2-authoritative composites.
 * All D2 composites must be exported through this barrel.
 *
 * Strategy: Authority Proxy Boundary (S2)
 * - Components remain in current file locations (dashboard/, error-banner/, root)
 * - This barrel re-exports from current paths
 * - Physical relocation deferred to D2-P1+
 * - Creates immediate enforcement handle with minimal churn
 *
 * Scope Authority: ../../../docs/forensics/D2_SCOPE.md
 * Last Updated: 2026-02-10 (D2-P0)
 */

// ============================================================================
// D2-P3 Normalized State Contract
// ============================================================================

/**
 * Normalized state union for all data-bearing D2 composites.
 * Every data-bearing composite accepts this as its `status` prop.
 * Substrate: RequestStatus (D1) handles non-success rendering.
 */
export type DataCompositeStatus = 'loading' | 'error' | 'empty' | 'success';

// ============================================================================
// D2-P3 Deterministic Fixtures (state reachability substrate)
// ============================================================================

export {
  activitySectionFixtures,
  dataConfidenceBarFixtures,
  userInfoCardFixtures,
  allDataBearingFixtures,
  stateKeys,
} from './fixtures';

// ============================================================================
// D2-Authoritative Composites (9 components)
// ============================================================================

// Activity & User Components
export { ActivitySection } from '@/components/dashboard/ActivitySection';
export { UserInfoCard } from '@/components/dashboard/UserInfoCard';

// Status & Confidence Indicators
export { default as DataConfidenceBar } from '@/components/dashboard/DataConfidenceBar';
export { default as ConfidenceScoreBadge } from '@/components/ConfidenceScoreBadge';

// Bulk Action Components
export { BulkActionModal } from '@/components/dashboard/BulkActionModal';
export { BulkActionToolbar } from '@/components/dashboard/BulkActionToolbar';

// Error Banner System
export { ErrorBanner } from '@/components/error-banner/ErrorBanner';
export { ErrorBannerContainer } from '@/components/error-banner/ErrorBannerContainer';
export { ErrorBannerProvider } from '@/components/error-banner/ErrorBannerProvider';

// ============================================================================
// End of D2 Export Surface
// ============================================================================

/**
 * ADMISSION RULES:
 *
 * A component may be added to this barrel ONLY if:
 * 1. ✅ Classified as D2-authoritative in D2_SCOPE.md
 * 2. ✅ Composes D1 atoms from @/components/ui/*
 * 3. ✅ Token compliant (zero hardcoded hex colors)
 * 4. ✅ Full state machine (if data-bearing)
 * 5. ✅ Accepts data via props (no hardcoded business logic)
 * 6. ✅ Reusable across 2+ contexts
 *
 * REJECTION CRITERIA:
 * ❌ Screen-specific components (ChannelPerformanceDashboard, etc.)
 * ❌ Domain-specific logic (reconciliation, verification, etc.)
 * ❌ Hardcoded API hooks (useChannelPerformance, etc.)
 * ❌ Token violations (hardcoded hex colors)
 *
 * To add a new D2 composite:
 * 1. Update D2_SCOPE.md with classification decision
 * 2. Add export to this barrel
 * 3. Run `npm run validate:d2-scope` to verify coherence
 */
