import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { assertBoundedDetailRequestCount } from '../detail/requestCounter';
import { validateClaimDetailDto, validateTrustEnvelopeDetailDto } from '../detail/detailDtoValidation';
import { DETAIL_COPY } from '../detail/copy';
import { baseClaimRow } from '../claims/claimsClient';

const ROOT = join(import.meta.dirname, '..', '..');

const SCAN_DIRS = [
  join(ROOT, 'src', 'detail'),
  join(ROOT, 'src', 'claims', 'claimDetailClient.ts'),
  join(ROOT, 'src', 'trustIndex', 'trustEnvelopeDetailClient.ts'),
  join(ROOT, 'src', 'channels', 'channelDetailClient.ts'),
  join(ROOT, 'src', 'exceptions', 'exceptionDetailClient.ts'),
  join(ROOT, 'src', 'budget', 'budgetSimulationDetailClient.ts'),
  join(ROOT, 'src', 'components', 'claims', 'ClaimDetailPage'),
  join(ROOT, 'src', 'components', 'trust', 'TrustEnvelopeOperatorView'),
  join(ROOT, 'src', 'components', 'channels', 'ChannelInlineExpansion'),
  join(ROOT, 'src', 'components', 'channels', 'ChannelsOverviewPage'),
  join(ROOT, 'src', 'components', 'budget', 'BudgetSimulationDetailPage'),
  join(ROOT, 'src', 'components', 'exceptions', 'ExceptionDetailModal'),
  join(ROOT, 'src', 'components', 'detail'),
  join(ROOT, 'src', 'ledger', 'DetailNavigationAffordance.tsx'),
  join(ROOT, 'src', 'app', 'routes', 'LedgerRoutes.tsx'),
];

const ALLOWED_REFERENCE_FILES = new Set([
  'level8NegativeScopeScan.ts',
  'level7NegativeScopeScan.ts',
  'copy.ts',
  'Level9BlockedAffordance.tsx',
  'ClaimDetailPage.tsx',
  'ExportReportButton.tsx',
  'BudgetSimulationDetailPage.tsx',
  'ExceptionDetailDrawer.tsx',
  'ExceptionDetailModal.tsx',
]);

const FORBIDDEN_L9_EXECUTABLE = [
  'exportVerifiedReport(',
  'copyApiResponse(',
  'copyTrustEnvelopeJson(',
  'exportArtifact(',
  'verifySignature(',
  'submitBudgetProposal(',
  'acknowledgeException(',
  'requestMoreEvidence(',
  'markDisputed(',
  'suppressSimilarAlerts(',
  'createProposal(',
];

const FORBIDDEN_L10_SURFACES = [
  'Command Center dashboard',
  'Trust Command Center content',
  'verified revenue trend',
  'priority queue',
  'recent TrustEnvelopes',
];

const FORBIDDEN_FETCH_IN_UI = [
  'ClaimDetailPage.tsx',
  'ExportReportButton.tsx',
  'ChannelInlineExpansion.tsx',
  'BudgetSimulationDetailPage.tsx',
  'ExceptionDetailDrawer.tsx',
  'ExceptionDetailModal.tsx',
];

const FORBIDDEN_FORENSIC_MARKETER_DETAIL = [
  'TrustEnvelopeJsonViewer',
  'TrustHashBlock',
  'TrustEnvelopeDetailProvenancePanel',
  'TrustEnvelopeDetailAuditSignaturePanel',
  'copyTrustEnvelopeJson',
  'verifySignature',
  'provenanceChain',
  'jsonContract',
  'data-trust-json-column',
  'View Cryptographic Proofs',
];

const FORBIDDEN_TRUST_DETAIL_DESTINATION = [
  'TrustEnvelopeDetailPage',
  'path="trust/:envelopeId"',
  '/app/trust/${',
  'TrustEnvelopeJsonViewer',
  'TrustHashBlock',
  'verifySignature(',
] as const;

const MARKETER_DETAIL_FILES = new Set([
  'ClaimDetailPage.tsx',
  'ExportReportButton.tsx',
  'TrustEnvelopeDetailAuditPanel.tsx',
]);

const REQUIRED_L8_MARKERS = [
  'ClaimDetailPage',
  'ChannelInlineExpansion',
  'BudgetSimulationDetailPage',
  'ExceptionDetailDrawer',
  'ExceptionDetailModal',
  'path="claims/:claimId"',
  'path="trust"',
  'path="channels/:channelId"',
  'path="budget/:simulationId"',
  'data-claim-detail-page',
  'data-claim-trust-envelope-drawer',
  'data-channel-inline-expansion',
  'data-budget-detail-page',
  'data-exception-detail-drawer',
  'data-exception-detail-modal',
  'TrustEnvelopeOperatorDrawer',
  'data-trust-envelope-audit-panel',
  'data-claim-attribution-section',
  'data-claim-detail-loaded',
  'buildChannelExpandHref',
];

function walk(target: string, acc: string[] = []): string[] {
  if (!statSync(target).isDirectory()) {
    acc.push(target);
    return acc;
  }
  for (const entry of readdirSync(target)) {
    const full = join(target, entry);
    if (statSync(full).isDirectory()) walk(full, acc);
    else if (/\.(tsx|ts|css)$/.test(entry)) acc.push(full);
  }
  return acc;
}

export function runLevel8NegativeScopeScan() {
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
    const basename = rel.split(/[/\\]/).pop() ?? rel;
    const content = readFileSync(file, 'utf8');

    if (basename.endsWith('.tsx') && FORBIDDEN_FETCH_IN_UI.includes(basename) && /\bfetch\s*\(/.test(content)) {
      violations.push({ file: rel, type: 'fetch-in-ui', value: basename });
    }

    for (const term of FORBIDDEN_L10_SURFACES) {
      if (content.includes(term) && !ALLOWED_REFERENCE_FILES.has(basename)) {
        violations.push({ file: rel, type: 'level10-leakage', value: term });
      }
    }

    for (const action of FORBIDDEN_L9_EXECUTABLE) {
      if (content.includes(action) && !ALLOWED_REFERENCE_FILES.has(basename)) {
        violations.push({ file: rel, type: 'level9-executable', value: action });
      }
    }

    if (/\bradar\s*chart\b/i.test(content) || content.includes('RadarChart')) {
      violations.push({ file: rel, type: 'causal-chart', value: 'radar chart' });
    }

    if (/\bcausal\s+lift\b/i.test(content) && !content.includes('do not prove causal lift')) {
      violations.push({ file: rel, type: 'causal-lift-claim', value: 'causal lift' });
    }

    if (/\bparseFloat\s*\(/.test(content) && !rel.includes('money.ts')) {
      violations.push({ file: rel, type: 'float-arithmetic', value: 'parseFloat' });
    }

    if (MARKETER_DETAIL_FILES.has(basename)) {
      for (const term of FORBIDDEN_FORENSIC_MARKETER_DETAIL) {
        if (content.includes(term)) {
          violations.push({ file: rel, type: 'forensic-ui-leak', value: term });
        }
      }
    }

    if (
      rel.startsWith('src\\components') &&
      !rel.includes('TrustEnvelopeOperatorView') &&
      !ALLOWED_REFERENCE_FILES.has(basename)
    ) {
      for (const term of FORBIDDEN_TRUST_DETAIL_DESTINATION) {
        if (content.includes(term)) {
          violations.push({ file: rel, type: 'trust-detail-destination', value: term });
        }
      }
    }
  }

  const ledgerRoutes = readFileSync(join(ROOT, 'src', 'app', 'routes', 'LedgerRoutes.tsx'), 'utf8');
  if (ledgerRoutes.includes('trust/:envelopeId')) {
    violations.push({ file: 'LedgerRoutes.tsx', type: 'trust-detail-route', value: 'trust/:envelopeId' });
  }

  if (ledgerRoutes.includes('Level8BlockedDetailPage')) {
    violations.push({ file: 'LedgerRoutes.tsx', type: 'blocked-shell', value: 'Level8BlockedDetailPage' });
  }

  return { filesScanned: files.length, violations };
}

export function assertLevel8RoutesExist() {
  const paths = [
    join(ROOT, 'src', 'app', 'routes', 'LedgerRoutes.tsx'),
    join(ROOT, 'src', 'components', 'claims', 'ClaimDetailPage', 'ClaimDetailPage.tsx'),
    join(ROOT, 'src', 'components', 'claims', 'ClaimDetailPage', 'AttributionBreakdownPanel.tsx'),
    join(ROOT, 'src', 'components', 'trust', 'TrustEnvelopeOperatorView', 'TrustEnvelopeOperatorDrawer.tsx'),
    join(ROOT, 'src', 'components', 'trust', 'TrustEnvelopeOperatorView', 'TrustEnvelopeDetailAuditPanel.tsx'),
    join(ROOT, 'src', 'components', 'channels', 'ChannelInlineExpansion', 'ChannelInlineExpansion.tsx'),
    join(ROOT, 'src', 'components', 'channels', 'ChannelsOverviewPage', 'ChannelsOverviewPage.tsx'),
    join(ROOT, 'src', 'components', 'budget', 'BudgetSimulationDetailPage', 'BudgetSimulationDetailPage.tsx'),
    join(ROOT, 'src', 'components', 'exceptions', 'ExceptionDetailModal', 'ExceptionDetailModal.tsx'),
  ];
  const combined = paths.map((p) => readFileSync(p, 'utf8')).join('\n');
  const missing = REQUIRED_L8_MARKERS.filter((m) => !combined.includes(m));
  return { ok: missing.length === 0, missing };
}

export function runLevel8SabotageProbes(sourceSample: string) {
  return [
    { name: 'level8-blocked-shell', triggered: sourceSample.includes('Level8BlockedDetailPage') },
    {
      name: 'claim-detail-has-tabs',
      triggered:
        sourceSample.includes('ClaimDetailPage') &&
        (sourceSample.includes("id: 'evidence'") ||
          sourceSample.includes("id: 'summary'") ||
          /from ['"].*Tabs\/Tabs['"]/.test(sourceSample)),
    },
    {
      name: 'claim-detail-missing-executive-page',
      triggered:
        sourceSample.includes('ClaimDetailPage') &&
        !sourceSample.includes('data-claim-detail-mode') &&
        !sourceSample.includes('ClaimDetailUnverifiedPanel'),
    },
    {
      name: 'claim-detail-jargon-leak',
      triggered:
        sourceSample.includes('ClaimDetailPage') &&
        (/Bayesian|semantic truth hash|PolicyAuthorityPill|AuthorityBadge|incrementality|coverage class/i.test(
          sourceSample,
        ) ||
          sourceSample.includes('TrustEnvelopeOperatorDrawer')),
    },
    { name: 'trust-detail-route-absent', triggered: sourceSample.includes('path="trust/:envelopeId"') || sourceSample.includes('TrustEnvelopeDetailPage') },
    { name: 'forensic-provenance-leak', triggered: sourceSample.includes('TrustEnvelopeDetailPage') && sourceSample.includes('provenanceChain') },
    { name: 'forensic-json-column-leak', triggered: sourceSample.includes('TrustEnvelopeDetailPage') && sourceSample.includes('data-trust-json-column') },
    { name: 'verify-signature-executes', triggered: /verifySignature\s*\(/.test(sourceSample) },
    { name: 'export-executes', triggered: /exportVerifiedReport\s*\(/.test(sourceSample) },
    { name: 'budget-submit-executes', triggered: /submitBudgetProposal\s*\(/.test(sourceSample) },
    { name: 'exception-mutation', triggered: /acknowledgeException\s*\(/.test(sourceSample) },
    { name: 'radar-chart', triggered: /RadarChart|radar chart/i.test(sourceSample) },
    { name: 'panel-n-plus-one-fetch', triggered: /useEffect[\s\S]*fetch/.test(sourceSample) && sourceSample.includes('DetailPage') },
    { name: 'command-center-leak', triggered: sourceSample.includes('Command Center dashboard') },
    { name: 'missing-state-matrix', triggered: sourceSample.includes('level8.harness.test') && !sourceSample.includes('Detail state matrix (Iteration II)') },
    { name: 'missing-trust-parent-back', triggered: sourceSample.includes('level8.harness.test') && !sourceSample.includes('channel overview expand deep-link') },
    { name: 'unsafe-history-back-return', triggered: /DetailReturnLink[\s\S]*navigate\s*\(\s*-1/.test(sourceSample) },
    { name: 'missing-canonical-fallback-test', triggered: sourceSample.includes('level8.harness.test') && !sourceSample.includes('uses canonical parent href') },
    { name: 'missing-drawer-focus-trap', triggered: sourceSample.includes('Drawer.tsx') && !sourceSample.includes('getFocusableElements') },
    { name: 'missing-375px-multi-surface', triggered: sourceSample.includes('level8.harness.test') && !sourceSample.includes('375px multi-surface') },
    { name: 'missing-claim-executive-harness', triggered: sourceSample.includes('level8.harness.test') && !sourceSample.includes('Claim detail executive page') },
    { name: 'missing-audit-panel', triggered: sourceSample.includes('TrustEnvelopeDetailPage') && !sourceSample.includes('TrustEnvelopeDetailAuditPanel') },
    { name: 'missing-audit-reference-harness', triggered: sourceSample.includes('level8.harness.test') && !sourceSample.includes('audit panel exposes audit reference link') },
    { name: 'missing-stale-detail-mounted', triggered: sourceSample.includes('level8.harness.test') && !sourceSample.includes('late claim A response') },
    { name: 'missing-budget-blocked-submit', triggered: sourceSample.includes('level8.harness.test') && !sourceSample.includes('budget detail exposes governed proposal flow control') },
    { name: 'forensic-hash-block-leak', triggered: sourceSample.includes('TrustEnvelopeDetailPage') && sourceSample.includes('TrustHashBlock') },
  ];
}

export function runLevel8SourceIntegrityProbes(): Array<{ name: string; ok: boolean }> {
  const claimPage = readFileSync(
    join(ROOT, 'src', 'components', 'claims', 'ClaimDetailPage', 'ClaimDetailPage.tsx'),
    'utf8',
  );
  const claimAttributionPanel = readFileSync(
    join(ROOT, 'src', 'components', 'claims', 'ClaimDetailPage', 'AttributionBreakdownPanel.tsx'),
    'utf8',
  );
  const claimEventsPanel = readFileSync(
    join(ROOT, 'src', 'components', 'claims', 'ClaimDetailPage', 'ClaimDetailEventsPanel.tsx'),
    'utf8',
  );
  const claimUnverifiedPanel = readFileSync(
    join(ROOT, 'src', 'components', 'claims', 'ClaimDetailPage', 'ClaimDetailUnverifiedPanel.tsx'),
    'utf8',
  );
  const claimFinancialSummary = readFileSync(
    join(ROOT, 'src', 'components', 'claims', 'ClaimDetailPage', 'ClaimDetailFinancialSummary.tsx'),
    'utf8',
  );
  const operatorDrawer = readFileSync(
    join(ROOT, 'src', 'components', 'trust', 'TrustEnvelopeOperatorView', 'TrustEnvelopeOperatorDrawer.tsx'),
    'utf8',
  );
  const exportReportButton = readFileSync(
    join(ROOT, 'src', 'actions', 'ExportReportButton.tsx'),
    'utf8',
  );
  const channelInline = readFileSync(
    join(ROOT, 'src', 'components', 'channels', 'ChannelInlineExpansion', 'ChannelInlineExpansion.tsx'),
    'utf8',
  );
  const channelsOverview = readFileSync(
    join(ROOT, 'src', 'components', 'channels', 'ChannelsOverviewPage', 'ChannelsOverviewPage.tsx'),
    'utf8',
  );
  const deterministicTruthPanel = readFileSync(
    join(
      ROOT,
      'src',
      'components',
      'trust',
      'TrustEnvelopeOperatorView',
      'TrustEnvelopeDetailDeterministicTruthPanel.tsx',
    ),
    'utf8',
  );
  const attributionPanel = readFileSync(
    join(
      ROOT,
      'src',
      'components',
      'trust',
      'TrustEnvelopeOperatorView',
      'TrustEnvelopeDetailAttributionPanel.tsx',
    ),
    'utf8',
  );
  const confidencePanel = readFileSync(
    join(
      ROOT,
      'src',
      'components',
      'trust',
      'TrustEnvelopeOperatorView',
      'TrustEnvelopeDetailConfidencePanel.tsx',
    ),
    'utf8',
  );
  const benchmarkPanel = readFileSync(
    join(
      ROOT,
      'src',
      'components',
      'trust',
      'TrustEnvelopeOperatorView',
      'TrustEnvelopeDetailBenchmarkPanel.tsx',
    ),
    'utf8',
  );
  const policyAuthorityPanel = readFileSync(
    join(
      ROOT,
      'src',
      'components',
      'trust',
      'TrustEnvelopeOperatorView',
      'TrustEnvelopeDetailPolicyAuthorityPanel.tsx',
    ),
    'utf8',
  );
  const auditPanel = readFileSync(
    join(
      ROOT,
      'src',
      'components',
      'trust',
      'TrustEnvelopeOperatorView',
      'TrustEnvelopeDetailAuditPanel.tsx',
    ),
    'utf8',
  );
  const operatorContent = readFileSync(
    join(ROOT, 'src', 'components', 'trust', 'TrustEnvelopeOperatorView', 'TrustEnvelopeOperatorContent.tsx'),
    'utf8',
  );
  const harness = readFileSync(join(ROOT, 'src', 'test', 'level8.harness.test.tsx'), 'utf8');
  const exceptionModal = readFileSync(
    join(ROOT, 'src', 'components', 'exceptions', 'ExceptionDetailModal', 'ExceptionDetailModal.tsx'),
    'utf8',
  );

  return [
    { name: 'claim-no-tabs', ok: !claimPage.includes('<Tabs') && !claimPage.includes("id: 'evidence'") },
    { name: 'claim-executive-mode', ok: claimPage.includes('data-claim-detail-mode') && claimPage.includes('ClaimDetailUnverifiedPanel') },
    { name: 'claim-attribution-channels', ok: claimAttributionPanel.includes('data-claim-attribution-section') && claimAttributionPanel.includes('data-claim-attribution-breakdown') && claimPage.includes('AttributionBreakdownPanel') },
    { name: 'claim-events-section', ok: claimEventsPanel.includes('data-claim-events-section') && claimPage.includes('ClaimDetailEventsPanel') },
    { name: 'claim-unverified-exclude', ok: claimUnverifiedPanel.includes('data-claim-exclude-budget') && claimUnverifiedPanel.includes('CLAIM_DETAIL_COPY.unverified.excludeButton') },
    { name: 'claim-executive-summary', ok: claimFinancialSummary.includes('data-claim-detail-summary') && claimFinancialSummary.includes('data-claim-verdict') && claimPage.includes('ClaimDetailFinancialSummary') },
    { name: 'claim-no-authority-badge', ok: !claimFinancialSummary.includes('AuthorityBadge') && !claimPage.includes('AuthorityBadge') },
    { name: 'claim-no-trust-drawer', ok: !claimPage.includes('TrustEnvelopeOperatorDrawer') && !claimPage.includes('data-claim-trust-record-trigger') },
    { name: 'trust-no-json-viewer', ok: !operatorContent.includes('TrustEnvelopeJsonViewer') },
    { name: 'trust-no-json-column', ok: !operatorContent.includes('data-trust-json-column') },
    { name: 'trust-audit-panel', ok: operatorContent.includes('TrustEnvelopeDetailAuditPanel') },
    { name: 'trust-inline-export', ok: operatorDrawer.includes('ExportReportButton') && exportReportButton.includes('Export report') && !exportReportButton.includes('Verify signature') },
    { name: 'export-no-forensic-hashes', ok: readFileSync(join(ROOT, 'src', 'actions', 'trustEnvelopeActionClient.ts'), 'utf8').includes("semanticTruthHash: ''") && readFileSync(join(ROOT, 'src', 'actions', 'trustEnvelopeActionClient.ts'), 'utf8').includes("artifactHash: ''") },
    { name: 'channel-inline-expansion', ok: channelInline.includes('data-channel-inline-expansion') && channelsOverview.includes('ChannelInlineExpansion') },
    { name: 'channel-no-model-table', ok: !channelInline.includes('data-channel-model-table') && !channelInline.includes('modelComparison') },
    { name: 'channel-no-trustenvelope-list', ok: !channelInline.includes('TrustEnvelope') && !channelInline.includes('relatedEnvelopes') },
    { name: 'channel-executive-campaigns', ok: channelInline.includes('data-channel-inline-campaigns') },
    { name: 'deterministic-truth-panel', ok: deterministicTruthPanel.includes('data-trust-envelope-deterministic-truth-panel') },
    { name: 'deterministic-truth-claim-comparison', ok: deterministicTruthPanel.includes('comparisonSection') && deterministicTruthPanel.includes('comparisonGrid') },
    { name: 'attribution-panel', ok: attributionPanel.includes('data-trust-envelope-attribution-panel') },
    { name: 'attribution-boundary-note', ok: attributionPanel.includes('data-trust-envelope-attribution-boundary') },
    { name: 'confidence-panel', ok: confidencePanel.includes('data-trust-envelope-confidence-panel') },
    { name: 'confidence-probabilistic-chips', ok: confidencePanel.includes('data-trust-envelope-credible-interval') && confidencePanel.includes('data-trust-envelope-posterior-support') && confidencePanel.includes('AuthorityBadge') && confidencePanel.includes('authority="probabilistic"') && confidencePanel.includes('data-trust-envelope-confidence-authority="credible-interval"') && confidencePanel.includes('data-trust-envelope-confidence-authority="posterior-support"') },
    { name: 'benchmark-panel', ok: benchmarkPanel.includes('data-trust-envelope-benchmark-panel') },
    { name: 'benchmark-two-column-grid', ok: benchmarkPanel.includes('fieldGrid') && benchmarkPanel.includes('data-trust-envelope-suppression-reason') },
    { name: 'policy-authority-panel', ok: policyAuthorityPanel.includes('data-trust-envelope-policy-authority-panel') },
    { name: 'policy-authority-action-grid', ok: policyAuthorityPanel.includes('data-trust-envelope-allowed-actions') && policyAuthorityPanel.includes('data-trust-envelope-blocked-actions') },
    { name: 'audit-panel-marker', ok: auditPanel.includes('data-trust-envelope-audit-panel') },
    { name: 'audit-reference-link', ok: auditPanel.includes('AuditReferenceLink') && auditPanel.includes('data-trust-envelope-audit-reference') },
    { name: 'audit-panel-no-hashes', ok: !auditPanel.includes('formatTrustEnvelopeHashDisplay') && !auditPanel.includes('TrustHashBlock') },
    { name: 'drawer-focus-trap', ok: readFileSync(join(ROOT, 'src', 'components', 'layout', 'Drawer', 'Drawer.tsx'), 'utf8').includes('getFocusableElements') },
    {
      name: 'exception-detail-modal-shell',
      ok:
        exceptionModal.includes("from '../../layout/Modal/Modal'") &&
        !exceptionModal.includes("from '../../layout/Drawer/Drawer'") &&
        exceptionModal.includes('data-exception-detail-modal') &&
        exceptionModal.includes('data-exception-detail-drawer'),
    },
    {
      name: 'exception-detail-issue-card-dna',
      ok:
        exceptionModal.includes('data-exception-detail-issue') &&
        !exceptionModal.includes('WarningSignalIcon') &&
        exceptionModal.includes('ExceptionActionControls'),
    },
    { name: 'harness-claim-detail', ok: harness.includes('data-claim-detail-loaded') },
    { name: 'harness-parent-context', ok: harness.includes('return from claim detail preserves ledger query') },
    { name: 'harness-claim-executive', ok: harness.includes('Claim detail executive page') },
    { name: 'harness-state-matrix', ok: harness.includes('Detail state matrix (Iteration II)') },
    { name: 'harness-stale-detail', ok: harness.includes('late claim A response') },
    { name: 'harness-budget-blocked-submit', ok: harness.includes('budget detail exposes governed proposal flow control') },
    { name: 'harness-375px-multi', ok: harness.includes('375px multi-surface') },
    { name: 'harness-audit-panel', ok: harness.includes('audit panel exposes audit reference link') },
    { name: 'harness-deterministic-truth-panel', ok: harness.includes('deterministic truth panel exposes hero revenue') },
    { name: 'harness-attribution-panel', ok: harness.includes('attribution model panel exposes lettered title') },
    { name: 'harness-confidence-panel', ok: harness.includes('confidence metadata panel exposes lettered title') },
    { name: 'harness-benchmark-panel', ok: harness.includes('benchmark metadata folds inside confidence panel') },
    { name: 'harness-policy-authority-panel', ok: harness.includes('policy authority panel exposes lettered title') },
    { name: 'harness-channel-inline-expansion', ok: harness.includes('Channel inline expansion (CDO remediation)') },
    { name: 'harness-level9-deferred', ok: harness.includes('Level 8 detail substrate preserved') || harness.includes('data-claim-detail-loaded') },
    { name: 'harness-exception-modal', ok: harness.includes('Exception modal') && harness.includes('data-exception-detail-modal') },
    { name: 'detail-navigation-affordance', ok: readFileSync(join(ROOT, 'src', 'ledger', 'DetailNavigationAffordance.tsx'), 'utf8').includes('data-detail-affordance="navigate"') },
  ];
}

export function runLevel8IntegrityProbes() {
  const results: Array<{ name: string; ok: boolean }> = [];
  const row = baseClaimRow(0);
  const detail = {
    claimId: row.claimRef,
    tenantId: 'tenant_1',
    claimSource: row.claimSource,
    claimRef: row.claimRef,
    verificationStatus: row.verificationStatus,
    claimedRevenueMinor: row.claimedRevenueMinor,
    verifiedRevenueMinor: row.verifiedRevenueMinor,
    currencyCode: row.currencyCode,
    discrepancyAmountMinor: row.discrepancyAmountMinor,
    discrepancyRateBps: row.discrepancyRateBps,
    discrepancyClass: row.discrepancyClass,
    commerceEvidenceSource: row.commerceSource,
    defaultAttributionModel: 'last-touch',
    paidAttribution: [
      {
        platform: row.claimSource,
        campaignClass: 'paid_social',
        amountMinor: (row.verifiedRevenueMinor * 76n) / 100n,
        channelId: `ch_paid_social__${row.claimSource}`,
      },
    ],
    journeyOrigins: [
      {
        commerceRail: 'direct',
        amountMinor: row.verifiedRevenueMinor - (row.verifiedRevenueMinor * 76n) / 100n,
      },
    ],
    claimEvents: [
      {
        id: 'evt_1',
        label: 'Ad set 101, Oct 12',
        occurredAt: '2026-10-12T14:00:00Z',
        claimedMinor: row.claimedRevenueMinor,
        matchStatus: 'matched' as const,
      },
    ],
    policyAuthority: row.policyAuthority,
    confidence: row.confidence,
    benchmark: { status: 'unavailable' as const, reason: 'none' },
    attribution: {
      selectedModel: 'last_touch',
      agreementTier: 'moderate',
      modelAssumption: 'heuristic',
      causalStatus: 'correlational',
      negativeBoundaryCopy: DETAIL_COPY.modelComparisonBoundary,
    },
    audit: {
      auditReference: row.auditReference,
      accessEvents: [],
    },
    incrementalityBoundaryCopy: DETAIL_COPY.incrementalityBoundary,
    summaryCopy: 'summary',
    verifiedNarrative: 'verified narrative',
    evidenceSteps: [
      {
        plainLabel: 'Claim received',
        timestamp: '2026-06-01T10:00:00Z',
        evidenceRef: 'evt_1',
      },
    ],
    technicalIdentifiers: {
      envelopeId: 'env_1',
      tenantIdHash: 'hash_1',
    },
    auditSecuredAt: row.lastUpdated,
    versionStamp: 'v1',
  };
  results.push({
    name: 'claim-dto-validation',
    ok: validateClaimDetailDto(detail, row.claimRef, 'tenant_1').ok,
  });

  const operatorView = {
    envelopeId: 'env_0001',
    canonicalEnvelopeId: 'tenv_01JZA72J4M1WKH7RNPY5Q2A7S',
    tenantId: 'tenant_1',
    status: 'issued' as const,
    createdAt: '2026-07-02T13:24:00Z',
    auditReference: 'AUD-2026-07-02-004182',
    subject: {
      subjectType: 'Revenue Claim Envelope',
      subjectIdentifier: 'subj_rc_2026_q2_meta_us_retargeting',
      relatedClaimId: 'claim_0001',
      relatedClaimHref: '/app/claims/claim_0001',
      relatedChannelLabel: 'Meta Ads · Retargeting',
      relatedChannelHref: '/app/channels/ch_1',
      sourceSystem: 'Shopify · Stripe · Meta',
      timeWindowLabel: '2026-06-01 → 2026-06-30 (UTC)',
    },
    deterministicTruth: {
      verifiedRevenueMinor: 48_231_684n,
      claimedRevenueMinor: 50_190_420n,
      differenceMinor: -1_958_736n,
      differenceRateBps: -390,
      currencyCode: 'USD',
      matchVerdictStatus: 'verified' as const,
      commerceEvidenceSource: 'Shopify settled orders + Stripe captured payments',
    },
    attribution: {
      selectedModel: 'Position-Based 40/20/40',
      modelFamily: 'Deterministic heuristic',
      modelAgreementTier: 'Moderate agreement',
      allocationChannel: 'Meta Ads',
      allocationPercent: 41.8,
      allocationAuthority: 'deterministic' as const,
      boundaryNote: 'Attribution models are deterministic heuristics and do not prove causal lift.',
    },
    confidence: {
      status: 'available' as const,
      intervalLower: 1.12,
      intervalUpper: 1.27,
      posteriorSupport: 0.91,
      modelFreshnessAt: '2026-07-02T13:06:00Z',
      authority: 'probabilistic' as const,
      boundaryNote: 'Confidence is advisory and cannot create financial truth.',
    },
    benchmark: {
      status: 'available' as const,
      rawBenchmark: '3.4x ROAS',
      decisionSafeBenchmark: '3.1x ROAS',
      benchmarkAuthority: 'benchmark' as const,
      sourceClass: 'Peer cohort',
      coverageClass: 'US DTC Fashion • n=128',
      suppressionReason: null,
      comparableToPrevious: true,
      actionability: 'Advisory only',
    },
    policyAuthority: {
      state: 'approval_required' as const,
      explanation: 'This envelope may be inspected and exported. Consequence-bearing actions require certification.',
      allowedActions: ['Inspect trust object', 'Export signed artifact', 'Open related claim'],
      blockedActions: ['Auto-execute budget changes', 'Submit spend changes'],
      auditRequirement: 'All consequence-bearing actions are written to the Audit Ledger.',
    },
    versionStamp: 'v_env_0001_1',
  };
  results.push({
    name: 'operator-view-validation',
    ok: validateTrustEnvelopeDetailDto(operatorView, 'env_0001', 'tenant_1').ok,
  });
  results.push({
    name: 'operator-view-missing-audit-reference',
    ok: !validateTrustEnvelopeDetailDto({ ...operatorView, auditReference: '' }, 'env_0001', 'tenant_1').ok,
  });

  const bounded = assertBoundedDetailRequestCount();
  results.push({ name: 'detail-request-bounded', ok: bounded.ok });

  return results;
}

export async function runLevel8ClientProbe() {
  const { createClaimDetailClient } = await import('../claims/claimDetailClient');
  const client = createClaimDetailClient();
  const outcome = await client.getClaimDetail('tenant_1', 'claim_0001');
  return { name: 'claim-detail-client-loaded', ok: outcome.kind === 'loaded' };
}

export function runLevel8NegativeScopeScanCli() {
  const scan = runLevel8NegativeScopeScan();
  const routes = assertLevel8RoutesExist();
  if (!routes.ok) {
    scan.violations.push({
      file: 'routes',
      type: 'missing-l8-marker',
      value: routes.missing.join(', '),
    });
  }
  return scan;
}
