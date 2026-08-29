import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const ROOT = join(import.meta.dirname, '..', '..');

const BRAND_TEXT = 'Skeldir';

function read(rel: string) {
  return readFileSync(join(ROOT, rel), 'utf8');
}

export function scanVisibleBrandTextOutsideLockup(html: string): string[] {
  const violations: string[] = [];
  if (/<h1[^>]*>[\s\S]*?Skeldir/i.test(html) && html.includes('data-shell-header')) {
    violations.push('visible-h1-skeldir-in-header');
  }
  return violations;
}

export function runCommandCenterCorrectiveBrandScan(source: string) {
  const violations: string[] = [];
  if (source.includes('ShellBrand') && source.includes('<h1') && source.includes('Skeldir')) {
    violations.push('shell-brand-renders-skeldir-h1');
  }
  if (!source.includes('data-shell-brand')) {
    violations.push('missing-shell-brand-marker');
  }
  return violations;
}

export function runCommandCenterCorrectiveSabotageProbes(sourceSample: string) {
  return [
    {
      name: 'duplicate-brand-skeldir',
      triggered:
        sourceSample.includes('data-shell-brand') &&
        sourceSample.includes('<h1') &&
        sourceSample.includes('Skeldir'),
    },
    {
      name: 'missing-trend-available-fixture',
      triggered:
        sourceSample.includes('Level10CommandCenterSpecimens') &&
        !sourceSample.includes('command-center-trend-available'),
    },
    {
      name: 'missing-keyboard-traversal-harness',
      triggered: !sourceSample.includes('commandCenterCorrectiveAction.harness'),
    },
    {
      name: 'summary-metric-downgrade',
      triggered: /metricValueLong[\s\S]{0,80}font-size:\s*var\(--font-size-h3\)/.test(sourceSample),
    },
    {
      name: 'missing-lower-proof-markers',
      triggered:
        sourceSample.includes('RecentTrustEnvelopesCard') && !sourceSample.includes('data-recent-envelope-row-link'),
    },
    {
      name: 'fixed-grid-columns-sabotage',
      triggered: /grid-template-columns:\s*464px/.test(sourceSample),
    },
  ];
}

export function runCommandCenterCorrectiveIntegrityProbes() {
  const shell = read('src/components/shell/AuthenticatedAppShell/AuthenticatedAppShell.tsx');
  const shellBrand = read('src/components/shell/ShellBrand/ShellBrand.tsx');
  const topHeader = read('src/components/shell/TopHeader/TopHeader.tsx');
  const specimens = read('src/dev/Level10CommandCenterSpecimens.tsx');
  const summaryCss = read('src/components/commandCenter/CommandCenterPage/CommandCenterSubcomponents.module.css');
  const recent = read('src/components/commandCenter/CommandCenterPage/RecentTrustEnvelopesCard.tsx');
  const recentCells = read('src/components/commandCenter/CommandCenterPage/RecentTrustEnvelopesCells.tsx');
  const audit = read('src/components/commandCenter/CommandCenterPage/AuditActivityStrip.tsx');
  const pageCss = read('src/components/commandCenter/CommandCenterPage/CommandCenterPage.module.css');

  return [
    { name: 'shell-brand-no-route-title', ok: !shellBrand.includes('<h1') },
    { name: 'top-header-no-route-title', ok: !topHeader.includes('<h1') },
    { name: 'shell-header-no-page-title-prop', ok: !shell.includes('pageTitle={resolvedTitle}') },
    { name: 'trend-available-fixture', ok: specimens.includes('command-center-trend-available') },
    { name: 'empty-tenant-fixture', ok: specimens.includes('command-center-empty-tenant') },
    { name: 'stale-fixture', ok: specimens.includes('command-center-stale') },
    { name: 'health-degraded-fixture', ok: specimens.includes('command-center-health-degraded') },
    {
      name: 'summary-long-value-h2',
      ok:
        summaryCss.includes('.metricValueLong') &&
        (summaryCss.includes('font-size: var(--font-size-h2)') ||
          (summaryCss.includes('composes: value') &&
            read('src/styles/summaryTile.module.css').includes('font-size: var(--font-size-h2)'))),
    },
    {
      name: 'responsive-supervisory-grid',
      ok:
        pageCss.includes('composes: supervisoryGrid') ||
        pageCss.includes('proofSurfaceTopRow') ||
        read('src/styles/responsiveGrid.module.css').includes('--sk-grid-trend-panel-min-width'),
    },
    { name: 'envelope-reconstruction-link', ok: recentCells.includes('data-recent-envelope-row-link') },
    { name: 'audit-actor-label', ok: audit.includes('data-audit-actor-label') },
    { name: 'nested-trend-empty-radius-zero', ok: summaryCss.includes('.trendEmpty') && summaryCss.includes('border-radius: 0') },
    {
      name: 'envelope-table-fits-aligned-column',
      ok:
        summaryCss.includes('.envelopeTableWrap') &&
        summaryCss.includes('overflow-x: visible') &&
        !summaryCss.includes('min-width: 36rem') &&
        summaryCss.includes('.envelopeTable') &&
        summaryCss.includes('table-layout: fixed'),
    },
    {
      name: 'proof-surface-band-alignment',
      ok:
        pageCss.includes('proofSurfaceBand') &&
        pageCss.includes('proofEnvelopesSlot') &&
        pageCss.includes('proofChannelSlot') &&
        pageCss.includes('grid-column: 1 / -1'),
    },
  ];
}

export function buildRadiusNestingAuditTable() {
  const cardRadius = '5px';
  const cardPadding = '24px';
  const nestedAlignedRadius = '0px';
  return [
    {
      surface: 'summaryCard',
      outerRadius: cardRadius,
      paddingGap: cardPadding,
      innerSurface: 'proofSurfaceRow (lower cards)',
      innerRadius: nestedAlignedRadius,
      classification: 'A-nested-aligned',
      rule: 'inner = max(0, outer - padding)',
    },
    {
      surface: 'chartCard',
      outerRadius: cardRadius,
      paddingGap: cardPadding,
      innerSurface: 'trendEmpty',
      innerRadius: nestedAlignedRadius,
      classification: 'A-nested-aligned',
      rule: 'inner = max(0, outer - padding)',
    },
    {
      surface: 'summaryCard',
      outerRadius: cardRadius,
      paddingGap: cardPadding,
      innerSurface: 'DiscrepancyBadge / AuthorityBadge',
      innerRadius: '5px (--radius-sm)',
      classification: 'B-independent-primitive',
      rule: 'approved pill/badge token',
    },
    {
      surface: 'primaryButton',
      outerRadius: '5px (--radius-sm)',
      paddingGap: 'n/a',
      innerSurface: 'n/a',
      innerRadius: 'n/a',
      classification: 'B-independent-primitive',
      rule: 'CTA control primitive',
    },
  ];
}
