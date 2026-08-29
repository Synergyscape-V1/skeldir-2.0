import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const ROOT = join(import.meta.dirname, '..', '..');

const FORBIDDEN_COPY = ['Comparable_to_previous_value', 'continue_onboarding'];

const REQUIRED_MARKERS = [
  'data-command-center-urgency',
  'data-summary-drilldown',
  'data-discrepancy-badge',
  'data-verified-revenue-chart',
  'data-trend-accessible-summary',
  'data-command-center-last-updated',
  'NavIcon',
  'ShellBrand',
  'NotificationBell',
  'VerifiedRevenueChart',
];

function read(rel: string) {
  return readFileSync(join(ROOT, rel), 'utf8');
}

export function runCommandCenterRedesignNegativeScopeScan() {
  const files = [
    'src/components/commandCenter/CommandCenterPage/CommandCenterPage.tsx',
    'src/components/commandCenter/CommandCenterPage/TrustStateSummaryRow.tsx',
    'src/components/commandCenter/PriorityQueueModal/PriorityQueueModal.tsx',
    'src/components/commandCenter/CommandCenterPage/ChannelTrustTableCard.tsx',
    'src/components/commandCenter/CommandCenterPage/VerifiedRevenueTrendCard.tsx',
    'src/components/commandCenter/CommandCenterPage/CommandCenterSubcomponents.tsx',
    'src/components/commandCenter/StatusBadges/StatusBadges.tsx',
    'src/components/commandCenter/VerifiedRevenueChart/VerifiedRevenueChart.tsx',
    'src/commandCenter/commandCenterClient.ts',
    'src/commandCenter/copy.ts',
    'src/components/shell/AuthenticatedAppShell/AuthenticatedAppShell.tsx',
    'src/components/shell/SidebarNavigation/SidebarNavigation.tsx',
    'src/components/shell/NotificationBell/NotificationBell.tsx',
    'src/components/shell/ShellBrand/ShellBrand.tsx',
    'src/components/shell/TopHeader/TopHeader.tsx',
  ];
  const combined = files.map((f) => read(f)).join('\n');
  const violations: Array<{ type: string; value: string }> = [];

  for (const term of FORBIDDEN_COPY) {
    if (combined.includes(term)) {
      violations.push({ type: 'forbidden-copy', value: term });
    }
  }

  const missing = REQUIRED_MARKERS.filter((m) => !combined.includes(m));
  for (const m of missing) {
    violations.push({ type: 'missing-marker', value: m });
  }

  if (!combined.includes('priorityDrawerTitle')) {
    violations.push({ type: 'copy-regression', value: 'priorityDrawerTitle' });
  }

  return { filesScanned: files.length, violations };
}

export function runCommandCenterRedesignSabotageProbes(sourceSample: string) {
  return [
    {
      name: 'raw-internal-variable',
      triggered: sourceSample.includes('Comparable_to_previous_value'),
    },
    {
      name: 'channel-claimed-revenue-platform-claim-pill',
      triggered: sourceSample.includes('PlatformClaimLabel'),
    },
    {
      name: 'missing-urgency-marker',
      triggered: sourceSample.includes('priorityIssues.length') && !sourceSample.includes('data-command-center-urgency'),
    },
    {
      name: 'missing-summary-drilldown',
      triggered: sourceSample.includes('summaryMetrics') && !sourceSample.includes('data-summary-drilldown'),
    },
    {
      name: 'bps-only-discrepancy',
      triggered:
        /discrepancyRateBps[\s\S]{0,120}\)/.test(sourceSample) &&
        !sourceSample.includes('data-channel-trust-discrepancy-tier') &&
        !sourceSample.includes('DiscrepancyBadge'),
    },
    {
      name: 'app-frame-active-nav',
      triggered: /activeNavId.*app-frame/.test(sourceSample),
    },
    {
      name: 'missing-chart-component',
      triggered: sourceSample.includes('data-verified-revenue-trend') && !sourceSample.includes('VerifiedRevenueChart'),
    },
  ];
}

export function runCommandCenterRedesignIntegrityProbes() {
  const copy = read('src/commandCenter/copy.ts');
  const client = read('src/commandCenter/commandCenterClient.ts');
  const channelCard = read('src/components/commandCenter/CommandCenterPage/ChannelTrustTableCard.tsx');
  const summaryRow = read('src/components/commandCenter/CommandCenterPage/TrustStateSummaryRow.tsx');

  return [
    { name: 'priority-drawer-title', ok: copy.includes('priorityDrawerTitle') },
    { name: 'no-snake-case-copy', ok: !client.includes('Comparable_to_previous') },
    { name: 'claimed-revenue-money-only', ok: !channelCard.includes('PlatformClaimLabel') },
    { name: 'summary-drilldown-slots', ok: summaryRow.includes('data-summary-drilldown') },
    { name: 'summary-tile-kind-split', ok: summaryRow.includes('data-summary-tile-kind') },
    { name: 'trend-window-30', ok: copy.includes('Last 30 days') },
    { name: 'humanized-timestamp-hook', ok: read('src/components/commandCenter/CommandCenterPage/CommandCenterSubcomponents.tsx').includes('formatRelativeUpdatedTime') },
  ];
}
