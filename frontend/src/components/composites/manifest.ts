/**
 * D2 Authoritative Component Manifest
 *
 * Machine-readable inventory of all D2-authoritative composites.
 * This is the SINGLE SOURCE OF TRUTH the harness iterates over.
 * Completeness is verified at runtime by comparing manifest entries
 * against actual barrel exports.
 *
 * Authority: docs/forensics/D2_SCOPE.md
 * Barrel:    src/components/composites/index.ts
 */

export interface D2ManifestEntry {
  /** Display name (matches component export) */
  name: string;
  /** Export name in the barrel (index.ts) */
  exportName: string;
  /** Component classification */
  category: 'data-bearing' | 'static' | 'infrastructure';
  /** Whether this composite has fixture-driven 4-state rendering */
  isDataBearing: boolean;
  /** Key in allDataBearingFixtures — only for data-bearing composites */
  fixtureKey?: string;
  /** How the harness renders this composite */
  renderMode: 'inline' | 'modal' | 'provider' | 'container';
  /** Brief description */
  description: string;
  /** D1 atoms consumed */
  d1Dependencies: string[];
  /** D2-P1 bypass exception ID, if any */
  bypassException?: string;
}

export const D2_MANIFEST: D2ManifestEntry[] = [
  {
    name: 'ActivitySection',
    exportName: 'ActivitySection',
    category: 'data-bearing',
    isDataBearing: true,
    fixtureKey: 'ActivitySection',
    renderMode: 'inline',
    description: 'Activity list with loading/empty/error/success state machine',
    d1Dependencies: ['Card', 'CardContent', 'CardHeader', 'CardTitle', 'CardDescription'],
  },
  {
    name: 'UserInfoCard',
    exportName: 'UserInfoCard',
    category: 'data-bearing',
    isDataBearing: true,
    fixtureKey: 'UserInfoCard',
    renderMode: 'inline',
    description: 'User profile card with status-driven rendering',
    d1Dependencies: ['Card', 'CardContent', 'CardHeader', 'CardTitle', 'CardDescription'],
  },
  {
    name: 'DataConfidenceBar',
    exportName: 'DataConfidenceBar',
    category: 'data-bearing',
    isDataBearing: true,
    fixtureKey: 'DataConfidenceBar',
    renderMode: 'inline',
    description: 'Confidence indicator with tooltip and trend',
    d1Dependencies: ['Tooltip', 'TooltipContent', 'TooltipProvider', 'TooltipTrigger', 'Badge'],
  },
  {
    name: 'ConfidenceScoreBadge',
    exportName: 'ConfidenceScoreBadge',
    category: 'static',
    isDataBearing: false,
    renderMode: 'inline',
    description: 'Animated score badge with tier-based glass UI',
    d1Dependencies: [],
    bypassException: 'EXC-001',
  },
  {
    name: 'BulkActionModal',
    exportName: 'BulkActionModal',
    category: 'static',
    isDataBearing: false,
    renderMode: 'modal',
    description: 'Bulk action dialog with form fields',
    d1Dependencies: ['Dialog', 'Button', 'Input', 'Textarea', 'Label', 'Alert'],
    bypassException: 'EXC-003',
  },
  {
    name: 'BulkActionToolbar',
    exportName: 'BulkActionToolbar',
    category: 'static',
    isDataBearing: false,
    renderMode: 'inline',
    description: 'Bulk operation toolbar with action buttons',
    d1Dependencies: ['Button', 'Separator'],
  },
  {
    name: 'ErrorBanner',
    exportName: 'ErrorBanner',
    category: 'static',
    isDataBearing: false,
    renderMode: 'inline',
    description: 'Animated error banner with auto-dismiss and focus management',
    d1Dependencies: ['Button'],
    bypassException: 'EXC-002',
  },
  {
    name: 'ErrorBannerContainer',
    exportName: 'ErrorBannerContainer',
    category: 'infrastructure',
    isDataBearing: false,
    renderMode: 'container',
    description: 'Container rendering active error banners from context',
    d1Dependencies: [],
  },
  {
    name: 'ErrorBannerProvider',
    exportName: 'ErrorBannerProvider',
    category: 'infrastructure',
    isDataBearing: false,
    renderMode: 'provider',
    description: 'Context provider for error banner state management',
    d1Dependencies: [],
  },
];

/** All D2 component export names for inventory verification */
export const D2_COMPONENT_NAMES = D2_MANIFEST.map((e) => e.exportName);

/** Total count of D2-authoritative composites */
export const D2_TOTAL_COUNT = D2_MANIFEST.length;
