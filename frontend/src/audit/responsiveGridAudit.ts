import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const ROOT = join(import.meta.dirname, '..', '..');

const SUBSTRATE_FILE = 'src/styles/responsiveGrid.module.css';

const GRID_SURFACE_FILES = [
  'src/components/commandCenter/CommandCenterPage/CommandCenterSubcomponents.module.css',
  'src/components/commandCenter/CommandCenterPage/CommandCenterPage.module.css',
  'src/components/channels/ChannelsOverviewSummaryRow/ChannelsOverviewSummaryRow.module.css',
  'src/components/trustIndex/TrustEnvelopeIndexSummaryRow/TrustEnvelopeIndexSummaryRow.module.css',
  'src/components/trustIndex/TrustEnvelopeIndexPage/TrustEnvelopeIndexPage.module.css',
  'src/components/trust/TrustEnvelopeOperatorView/TrustEnvelopeDetailPage.module.css',
  'src/components/benchmarks/BenchmarksFilters/BenchmarksFilters.module.css',
  'src/components/channels/ChannelsOverviewFilters/ChannelsOverviewFilters.module.css',
  'src/components/trustIndex/TrustEnvelopeIndexFilters/TrustEnvelopeIndexFilters.module.css',
  'src/components/claims/ClaimsLedgerFilters/ClaimsLedgerFilters.module.css',
  'src/components/claims/ClaimsLedgerPage/ClaimsLedgerPage.module.css',
  'src/components/integration/IntegrationGroup/IntegrationGroup.module.css',
] as const;

const FORBIDDEN_TILE_SHRINK = /repeat\(\s*4\s*,\s*minmax\(\s*0\s*,\s*1fr\s*\)\)/;
const FORBIDDEN_PAIR_SHRINK = /repeat\(\s*2\s*,\s*minmax\(\s*0\s*,\s*1fr\s*\)\)/;
const FORBIDDEN_TRIPLE_SHRINK = /repeat\(\s*3\s*,\s*minmax\(\s*0\s*,\s*1fr\s*\)\)/;
const REQUIRED_AUTO_FIT = /auto-fit,\s*minmax\(\s*min\(\s*100%/;

export interface ResponsiveGridViolation {
  file: string;
  check: string;
  detail: string;
}

export function runResponsiveGridAudit() {
  const violations: ResponsiveGridViolation[] = [];
  const substrate = readFileSync(join(ROOT, SUBSTRATE_FILE), 'utf8');

  if (!substrate.includes('repeat(auto-fit, minmax(min(100%')) {
    violations.push({
      file: SUBSTRATE_FILE,
      check: 'substrate-auto-fit',
      detail: 'responsive grid substrate must use auto-fit minmax(min(100%, ...))',
    });
  }

  if (!/--sk-grid-tile-min-width/.test(substrate)) {
    violations.push({
      file: SUBSTRATE_FILE,
      check: 'substrate-tile-min-token',
      detail: 'substrate must reference --sk-grid-tile-min-width',
    });
  }

  for (const file of GRID_SURFACE_FILES) {
    const content = readFileSync(join(ROOT, file), 'utf8');
    const usesSubstrate = /composes:\s*\w+\s+from\s+['"].*responsiveGrid\.module\.css['"]/.test(content);
    const hasAutoFit = REQUIRED_AUTO_FIT.test(content);
    const hasForbiddenShrink =
      FORBIDDEN_TILE_SHRINK.test(content) ||
      FORBIDDEN_PAIR_SHRINK.test(content) ||
      FORBIDDEN_TRIPLE_SHRINK.test(content);

    if (hasForbiddenShrink && !usesSubstrate && !hasAutoFit) {
      violations.push({
        file,
        check: 'forbidden-zero-min-grid',
        detail: 'fixed minmax(0,1fr) grids must use responsiveGrid substrate',
      });
    }
  }

  const pageCss = readFileSync(
    join(ROOT, 'src/components/commandCenter/CommandCenterPage/CommandCenterPage.module.css'),
    'utf8',
  );
  if (!/composes:\s*supervisoryGrid/.test(pageCss) && !/minmax\(var\(--sk-grid-trend-panel-min-width\)/.test(
    readFileSync(join(ROOT, SUBSTRATE_FILE), 'utf8'),
  )) {
    violations.push({
      file: 'src/components/commandCenter/CommandCenterPage/CommandCenterPage.module.css',
      check: 'supervisory-min-width-enforced',
      detail: 'supervisory row must enforce trend/channel panel minimum widths',
    });
  }

  return { violations, filesScanned: GRID_SURFACE_FILES.length + 2 };
}
