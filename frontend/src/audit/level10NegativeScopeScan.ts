import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import {
  MAX_AUDIT_CHIPS,
  MAX_CHANNEL_ROWS,
  MAX_PRIORITY_ROWS,
  MAX_RECENT_ENVELOPES,
  MAX_TREND_POINTS,
  createCommandCenterClient,
  resolvePrimaryAction,
} from '../commandCenter/commandCenterClient';
import { sortPriorityIssues, validatePriorityOrder } from '../commandCenter/prioritySeverity';
import { SUPERVISORY_PROJECTION_SOURCE } from '../commandCenter/supervisoryProjectionClient';
import type { PriorityIssue } from '../commandCenter/types';

const ROOT = join(import.meta.dirname, '..', '..');

const SCAN_DIRS = [
  join(ROOT, 'src', 'commandCenter'),
  join(ROOT, 'src', 'components', 'commandCenter'),
  join(ROOT, 'src', 'app', 'routes', 'ShellRoutes.tsx'),
  join(ROOT, 'evidence', 'Level_10'),
];

const FORBIDDEN_L11 = [
  '/settings/billing',
  'BillingPage',
  'NotFoundRoute',
  'RouteRecoveryPage',
  'billing recovery surface',
  'route-recovery surface',
  'plan gating',
];

const FORBIDDEN_L9_BYPASS = [
  'exportVerifiedReport(',
  'submitBudgetProposal(',
  'acknowledgeException(',
  'suppressSimilarAlerts(',
];

const REQUIRED_L10_MARKERS = [
  'CommandCenterPage',
  'data-command-center-page',
  'data-trust-state-summary-row',
  'data-priority-queue-open',
  'data-priority-queue-modal',
  'data-verified-revenue-trend',
  'data-channel-trust-table',
  'data-recent-trust-envelopes',
  'data-audit-activity-strip',
  'data-command-center-primary-action',
  'data-command-center-health-banner',
  'data-top-priority-issue',
  'data-command-center-empty-tenant',
  'data-channel-table-scroll-wrap',
  'data-viewer-read-only-supervisory',
  'data-priority-action-href',
  'canUseCommandCenterSupervisoryActions',
  'AuthorityBadge',
  'PolicyAuthorityPill',
  'DataUnavailablePanel',
  'commandCenterClient',
  'resolvePrimaryAction',
  'Trust API read failed. No financial truth was changed.',
];

function walk(target: string, acc: string[] = []): string[] {
  if (!statSync(target).isDirectory()) {
    acc.push(target);
    return acc;
  }
  for (const entry of readdirSync(target)) {
    const full = join(target, entry);
    if (statSync(full).isDirectory()) walk(full, acc);
    else if (/\.(tsx|ts|md|json)$/.test(entry)) acc.push(full);
  }
  return acc;
}

export function runLevel10NegativeScopeScan() {
  const files = SCAN_DIRS.flatMap((dir) => {
    try {
      return walk(dir, []);
    } catch {
      return [];
    }
  });
  const violations: Array<{ file: string; type: string; value: string }> = [];

  for (const file of files) {
    const rel = relative(ROOT, file);
    if (rel.includes('.test.')) continue;
    const content = readFileSync(file, 'utf8');

    if (/\.(tsx|ts)$/.test(file) && rel.includes('commandCenter')) {
      for (const term of FORBIDDEN_L11) {
        if (content.includes(term)) {
          violations.push({ file: rel, type: 'level11-leakage', value: term });
        }
      }
      for (const term of FORBIDDEN_L9_BYPASS) {
        if (content.includes(term)) {
          violations.push({ file: rel, type: 'level9-bypass', value: term });
        }
      }
    }
  }

  return { filesScanned: files.length, violations };
}

export function assertLevel10ComponentsExist() {
  const ccDir = join(ROOT, 'src', 'components', 'commandCenter');
  const paths = [
    join(ROOT, 'src', 'components', 'commandCenter', 'CommandCenterPage', 'CommandCenterPage.tsx'),
    join(ROOT, 'src', 'commandCenter', 'commandCenterClient.ts'),
    join(ROOT, 'src', 'commandCenter', 'copy.ts'),
    join(ROOT, 'src', 'app', 'routes', 'ShellRoutes.tsx'),
    ...walk(ccDir, []),
  ];
  const combined = [...new Set(paths)].map((p) => readFileSync(p, 'utf8')).join('\n');
  const missing = REQUIRED_L10_MARKERS.filter((m) => !combined.includes(m));
  return { ok: missing.length === 0, missing };
}

export function runLevel10IntegrityProbes() {
  const client = createCommandCenterClient();
  const issues: PriorityIssue[] = [
    {
      id: 'b',
      severity: 'integration_degraded',
      title: 'b',
      explanation: 'b',
      subjectRef: 'integration_health',
      policyAuthority: 'blocked',
      actionLabel: 'b',
      actionHref: '/app/integrations',
      sourceLink: '/app/integrations',
    },
    {
      id: 'a',
      severity: 'policy_approval_required',
      title: 'a',
      explanation: 'a',
      subjectRef: 'sim_0001',
      policyAuthority: 'approval_required',
      actionLabel: 'a',
      actionHref: '/app/settings/policy',
      sourceLink: '/app/settings/policy',
    },
  ];
  const sorted = sortPriorityIssues(issues);
  return [
    { name: 'priority-sort', ok: sorted[0]?.severity === 'policy_approval_required' },
    { name: 'priority-validate', ok: validatePriorityOrder(sorted) },
    { name: 'bounds-priority', ok: MAX_PRIORITY_ROWS === 10 },
    { name: 'bounds-channels', ok: MAX_CHANNEL_ROWS === 5 },
    { name: 'bounds-envelopes', ok: MAX_RECENT_ENVELOPES === 25 },
    { name: 'bounds-audit', ok: MAX_AUDIT_CHIPS === 4 },
    { name: 'bounds-trend', ok: MAX_TREND_POINTS === 61 },
    {
      name: 'primary-action-review',
      ok: resolvePrimaryAction({
        tenantId: 't',
        lastUpdatedAt: new Date().toISOString(),
        freshness: 'fresh',
        healthState: 'operational',
        trustApiReadFailed: false,
        killSwitchActive: false,
        hasTrustEnvelope: true,
        latestEnvelopeId: 'env_0001',
        summaryMetrics: [],
        priorityIssues: sorted,
        trendPoints: [],
        channelRows: [],
        recentEnvelopes: [],
        recentEnvelopesSignalWindow: '24h',
        auditActivity: [],
        openExceptionsCount: 0,
        claimsReconciledCount: 0,
        sourceTrace: {},
      }).kind === 'review_issues',
    },
    { name: 'client-factory', ok: typeof client.fetchAggregate === 'function' },
  ];
}

export function runLevel10SabotageProbes(sourceSample: string) {
  return [
    {
      name: 'missing-authority-badge',
      triggered: sourceSample.includes('summaryMetrics') && !sourceSample.includes('AuthorityBadge'),
    },
    {
      name: 'claimed-as-verified-trend',
      triggered: /claimedRevenueMinor[\s\S]*verified revenue trend/i.test(sourceSample),
    },
    {
      name: 'multiple-primary-actions',
      triggered: (sourceSample.match(/data-command-center-primary-action/g) ?? []).length > 2,
    },
    {
      name: 'level11-billing-route',
      triggered: sourceSample.includes('path="settings/billing"'),
    },
    {
      name: 'level9-direct-export',
      triggered: sourceSample.includes('exportVerifiedReport('),
    },
    {
      name: 'dashboard-invented-truth',
      triggered: /verifiedTotal\s*=/.test(sourceSample) && sourceSample.includes('CommandCenterPage'),
    },
    {
      name: 'missing-source-trace',
      triggered: sourceSample.includes('fetchAggregate') && !sourceSample.includes('sourceTrace'),
    },
    {
      name: 'priority-client-sort-bypass',
      triggered: sourceSample.includes('priorityIssues') && sourceSample.includes('.sort(') && sourceSample.includes('CommandCenterPage'),
    },
  ];
}


export function runLevel10SourceSabotageProbes() {
  const client = readFileSync(join(ROOT, 'src', 'commandCenter', 'commandCenterClient.ts'), 'utf8');
  const page = readFileSync(
    join(ROOT, 'src', 'components', 'commandCenter', 'CommandCenterPage', 'CommandCenterPage.tsx'),
    'utf8',
  );
  const harness = readFileSync(join(ROOT, 'src', 'test', 'level10.harness.test.tsx'), 'utf8');
  return [
    { name: 'missing-substrate-overrides', triggered: !client.includes('setCommandCenterSubstrateOverridesForTests') },
    { name: 'missing-health-banner', triggered: !page.includes('SystemHealthStatusBanner') },
    { name: 'missing-empty-tenant-panel', triggered: !page.includes('empty_tenant') },
    { name: 'missing-trust-retry-marker', triggered: !page.includes('data-command-center-retry') },
    { name: 'missing-loading-retry-marker', triggered: !page.includes('data-command-center-loading-retry') },
    { name: 'missing-top-priority-marker', triggered: !readFileSync(join(ROOT, 'src', 'components', 'commandCenter', 'PriorityQueueModal', 'PriorityQueueModal.tsx'), 'utf8').includes('data-top-priority-issue') },
    { name: 'missing-mounted-partial', triggered: !harness.includes('partial aggregate') },
    { name: 'missing-mounted-loading-retry', triggered: !harness.includes('loading retry') },
    { name: 'missing-mounted-confidence-degraded', triggered: !harness.includes('confidence_degraded') },
    { name: 'missing-mounted-empty-tenant', triggered: !harness.includes('empty tenant') },
    { name: 'missing-mounted-trust-retry', triggered: !harness.includes('Trust API retry') },
    { name: 'missing-mounted-integration-banner', triggered: !harness.includes('integration_attention') },
    { name: 'missing-substrate-mutation', triggered: !harness.includes('substrate mutation') },
    { name: 'missing-role-boundaries', triggered: !harness.includes('billing_only') || !harness.includes('viewer unsafe affordance') },
    { name: 'missing-view-latest-envelope', triggered: !harness.includes('view_latest_envelope') },
    { name: 'missing-unsorted-priority', triggered: !harness.includes('unsorted priority') },
    { name: 'missing-keyboard-enter-links', triggered: !harness.includes('keyboard Enter') },
    { name: 'missing-audit-event-id-href', triggered: !harness.includes('/app/audit/events/') },
    { name: 'missing-1280px-mounted', triggered: !harness.includes('1280px') },
    { name: 'missing-focus-order', triggered: !harness.includes('focus order') },
    { name: 'missing-channel-table-readability', triggered: !harness.includes('channel table has no horizontal scroll') },
    { name: 'missing-source-sabotage-call', triggered: !harness.includes('runLevel10SourceSabotageProbes') },
    { name: 'missing-trend-mutation-test', triggered: !harness.includes('trend mutation') },
    { name: 'missing-channel-mutation-test', triggered: !harness.includes('channel mutation') },
    { name: 'missing-health-mutation-test', triggered: !harness.includes('health mutation') },
    { name: 'missing-audit-mutation-test', triggered: !harness.includes('audit mutation') },
    { name: 'missing-trust-envelope-mutation-test', triggered: !harness.includes('TrustEnvelope mutation') },
    { name: 'missing-review-issues-mounted', triggered: !harness.includes('review_issues') },
    { name: 'missing-primary-queue-drawer-coupling', triggered: !harness.includes('data-priority-queue-open') && !harness.includes('opens review_issues drawer CTA') },
    { name: 'missing-viewer-unsafe-affordance', triggered: !harness.includes('viewer unsafe affordance') },
    { name: 'missing-audit-chip-keyboard-enter', triggered: !harness.includes('keyboard Enter activates audit chip') },
    { name: 'missing-audit-ledger-keyboard-enter', triggered: !harness.includes('keyboard Enter activates View Audit Ledger') },
  ];
}

export function runLevel10SourceIntegrityProbes() {
  const harness = readFileSync(join(ROOT, 'src', 'test', 'level10.harness.test.tsx'), 'utf8');
  const client = readFileSync(join(ROOT, 'src', 'commandCenter', 'commandCenterClient.ts'), 'utf8');
  const base = runLevel10IntegrityProbes();
  return [
    ...base,
    { name: 'harness-partial-state', ok: harness.includes('partial aggregate') },
    { name: 'harness-loading-retry', ok: harness.includes('loading retry') },
    { name: 'harness-confidence-degraded', ok: harness.includes('confidence_degraded') },
    { name: 'harness-empty-tenant', ok: harness.includes('empty tenant') },
    { name: 'harness-trust-retry', ok: harness.includes('Trust API retry') },
    { name: 'harness-integration-banner', ok: harness.includes('integration_attention') },
    { name: 'harness-substrate-mutation', ok: harness.includes('substrate mutation') },
    { name: 'harness-role-boundaries', ok: harness.includes('billing_only') && harness.includes('viewer unsafe affordance') },
    { name: 'harness-view-latest-envelope', ok: harness.includes('view_latest_envelope') },
    { name: 'harness-unsorted-priority', ok: harness.includes('unsorted priority') },
    { name: 'harness-keyboard-enter', ok: harness.includes('keyboard Enter') },
    { name: 'harness-audit-event-id', ok: harness.includes('/app/audit/events/') },
    { name: 'harness-1280px', ok: harness.includes('1280px') },
    { name: 'harness-focus-order', ok: harness.includes('focus order') },
    { name: 'harness-channel-table-readability', ok: harness.includes('channel table has no horizontal scroll') },
    { name: 'harness-source-sabotage', ok: harness.includes('runLevel10SourceSabotageProbes') },
    { name: 'client-substrate-overrides', ok: client.includes('setCommandCenterSubstrateOverridesForTests') },
    { name: 'client-priority-sort', ok: client.includes('sortPriorityIssues') },
    { name: 'supervisory-projection-source', ok: client.includes(SUPERVISORY_PROJECTION_SOURCE) },
    { name: 'no-frontend-priority-assembly', ok: !client.includes('buildPriorityIssues') },
    { name: 'harness-trend-mutation', ok: harness.includes('trend mutation') },
    { name: 'harness-channel-mutation', ok: harness.includes('channel mutation') },
    { name: 'harness-health-mutation', ok: harness.includes('health mutation') },
    { name: 'harness-audit-mutation', ok: harness.includes('audit mutation') },
    { name: 'harness-trust-envelope-mutation', ok: harness.includes('TrustEnvelope mutation') },
    { name: 'harness-review-issues', ok: harness.includes('review_issues') },
    { name: 'harness-primary-queue-drawer', ok: harness.includes('opens review_issues drawer CTA') || harness.includes('data-priority-queue-open') },
    { name: 'harness-viewer-unsafe-affordance', ok: harness.includes('viewer unsafe affordance') },
    { name: 'harness-audit-chip-keyboard', ok: harness.includes('keyboard Enter activates audit chip') },
    { name: 'harness-audit-ledger-keyboard', ok: harness.includes('keyboard Enter activates View Audit Ledger') },
    { name: 'client-trend-mutation-seam', ok: client.includes('trendVerifiedBonus') && client.includes('trendPointsOverride') },
    { name: 'client-channel-override-seam', ok: client.includes('channelRowsOverride') },
    { name: 'client-audit-override-seam', ok: client.includes('auditActivityOverride') },
    { name: 'client-envelope-override-seam', ok: client.includes('recentEnvelopesOverride') },
    { name: 'viewer-permissions-module', ok: readFileSync(join(ROOT, 'src', 'commandCenter', 'permissions.ts'), 'utf8').includes('canUseCommandCenterSupervisoryActions') },
  ];
}

export function runLevel10NegativeScopeScanCli() {
  const scan = runLevel10NegativeScopeScan();
  const components = assertLevel10ComponentsExist();
  const probes = runLevel10IntegrityProbes();
  if (scan.violations.length > 0) {
    console.error('Level 10 scope violations:', scan.violations);
    process.exit(1);
  }
  if (!components.ok) {
    console.error('Missing Level 10 markers:', components.missing);
    process.exit(1);
  }
  const failedProbe = probes.find((p) => !p.ok);
  if (failedProbe) {
    console.error('Level 10 integrity probe failed:', failedProbe.name);
    process.exit(1);
  }
  console.log(`Level 10 scope scan: ${scan.filesScanned} files, 0 violations`);
  console.log(`Level 10 markers: ${REQUIRED_L10_MARKERS.length - components.missing.length}/${REQUIRED_L10_MARKERS.length}`);
  console.log(`Level 10 integrity probes: ${probes.filter((p) => p.ok).length}/${probes.length}`);
}

if (import.meta.url === `file://${process.argv[1]?.replace(/\\/g, '/')}`) {
  runLevel10NegativeScopeScanCli();
}
