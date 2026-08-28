import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { assertBoundedRequestCount, getLedgerRequestCount } from '../ledger/requestCounter';
import { detectForbiddenListFields, FORBIDDEN_LIST_ENVELOPE_FIELDS } from '../ledger/listDtoValidation';
import { executeServerQuery, createSyntheticDataset } from '../ledger/queryEngine';
import { MAX_DOM_TABLE_ROWS } from '../operationalAudit/pagination';

const ROOT = join(import.meta.dirname, '..', '..');

const SCAN_DIRS = [
  join(ROOT, 'src', 'claims'),
  join(ROOT, 'src', 'trustIndex'),
  join(ROOT, 'src', 'channels'),
  join(ROOT, 'src', 'benchmarks'),
  join(ROOT, 'src', 'exceptions'),
  join(ROOT, 'src', 'budget'),
  join(ROOT, 'src', 'ledger'),
  join(ROOT, 'src', 'components', 'claims'),
  join(ROOT, 'src', 'components', 'trustIndex'),
  join(ROOT, 'src', 'components', 'channels'),
  join(ROOT, 'src', 'components', 'benchmarks'),
  join(ROOT, 'src', 'components', 'exceptions'),
  join(ROOT, 'src', 'components', 'budget'),
  join(ROOT, 'src', 'components', 'ledger'),
  join(ROOT, 'src', 'app', 'routes'),
];

const ALLOWED_REFERENCE_FILES = new Set([
  'level7NegativeScopeScan.ts',
  'level6NegativeScopeScan.ts',
  'level5NegativeScopeScan.ts',
  'navigation.ts',
  'ShellFallbackPanel.tsx',
  'copy.ts',
  'ExceptionsQueuePage.tsx',
  'LedgerRoutes.tsx',
  'ClaimDetailPage.tsx',
  'ExportReportButton.tsx',
  'TrustEnvelopeOperatorDrawer.tsx',
  'ChannelInlineExpansion.tsx',
  'BudgetSimulationDetailPage.tsx',
  'ExceptionDetailDrawer.tsx',
  'ExceptionDetailModal.tsx',
  'Level9BlockedAffordance.tsx',
]);

const REQUIRED_L7_ROUTES = [
  'path="claims"',
  'path="trust"',
  'path="channels"',
  'path="exceptions"',
  'path="budget"',
  'ClaimsLedgerPage',
  'TrustEnvelopeIndexPage',
  'ChannelsOverviewPage',
  'ExceptionsQueuePage',
  'BudgetInputPage',
];

const FORBIDDEN_L8_PLUS_SURFACES = [
  'Command Center dashboard',
  'Trust Command Center content',
  'verified revenue trend',
  'priority queue',
  'recent TrustEnvelopes',
  'TrustEnvelopeJsonViewer',
  'TrustHashBlock',
  'TrustEnvelopeDetailProvenancePanel',
  'TrustEnvelopeDetailAuditSignaturePanel',
  'copyTrustEnvelopeJson',
  'data-trust-json-column',
  'ClaimDetailTabs',
  'Evidence workbench',
  'View Cryptographic Proofs',
];

const FORBIDDEN_L9_ACTIONS = [
  'exportVerifiedReport(',
  'verifySignature(',
  'copyApiResponse(',
  'submitBudgetProposal(',
  'acknowledgeException(',
  'markDisputed(',
  'createProposal(',
  'exportAudit(',
  'reconstructAudit(',
];

const FORBIDDEN_FETCH_IN_UI = [
  'ClaimsLedgerPage.tsx',
  'TrustEnvelopeIndexPage.tsx',
  'ChannelsOverviewPage.tsx',
  'BenchmarksPage.tsx',
  'ExceptionsQueuePage.tsx',
  'BudgetInputPage.tsx',
  'ClaimsLedgerTable.tsx',
];

function walk(dir: string, acc: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) walk(full, acc);
    else if (/\.(tsx|ts|css)$/.test(entry)) acc.push(full);
  }
  return acc;
}

export function runLevel7NegativeScopeScan() {
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

    for (const term of FORBIDDEN_L8_PLUS_SURFACES) {
      if (content.includes(term) && !ALLOWED_REFERENCE_FILES.has(basename)) {
        violations.push({ file: rel, type: 'level8-plus-surface', value: term });
      }
    }

    for (const action of FORBIDDEN_L9_ACTIONS) {
      if (content.includes(action)) {
        violations.push({ file: rel, type: 'level9-action', value: action });
      }
    }

    if (/\bparseFloat\s*\(/.test(content) && !rel.includes('money.ts')) {
      violations.push({ file: rel, type: 'float-arithmetic', value: 'parseFloat' });
    }
  }

  return { filesScanned: files.length, violations };
}

export function assertLevel7RoutesExist() {
  const shellRoutes = readFileSync(join(ROOT, 'src', 'app', 'routes', 'ShellRoutes.tsx'), 'utf8');
  const ledgerRoutes = readFileSync(join(ROOT, 'src', 'app', 'routes', 'LedgerRoutes.tsx'), 'utf8');
  const combined = shellRoutes + ledgerRoutes;
  const missing = REQUIRED_L7_ROUTES.filter((r) => !combined.includes(r));
  return { ok: missing.length === 0, missing };
}

export function runLevel7SabotageProbes(sourceSample: string) {
  const detectors: Array<{ name: string; triggered: boolean }> = [];
  detectors.push({
    name: 'n-plus-one-useEffect-in-row',
    triggered: /useEffect\s*\([\s\S]*fetch/.test(sourceSample),
  });
  detectors.push({
    name: 'current-page-only-sort',
    triggered: /rows\.sort\(/.test(sourceSample) && !sourceSample.includes('executeServerQuery'),
  });
  detectors.push({
    name: 'fetch-all-then-filter',
    triggered: /fetchAll/.test(sourceSample) || /getAllClaims/.test(sourceSample),
  });
  detectors.push({
    name: 'full-envelope-in-list',
    triggered: FORBIDDEN_LIST_ENVELOPE_FIELDS.some((f) => sourceSample.includes(`${f}:`)),
  });
  detectors.push({
    name: 'claim-as-verified-truth',
    triggered: /Platform claim[\s\S]*authority="deterministic"/.test(sourceSample),
  });
  detectors.push({
    name: 'frontend-float-discrepancy',
    triggered: /parseFloat/.test(sourceSample) && !sourceSample.includes('money.ts'),
  });
  detectors.push({
    name: 'naked-confidence-scalar',
    triggered: /Confidence:\s*\d+%/.test(sourceSample),
  });
  detectors.push({
    name: 'export-action-leakage',
    triggered: FORBIDDEN_L9_ACTIONS.some((a) => sourceSample.includes(a)),
  });
  detectors.push({
    name: 'trust-index-missing-financial-value',
    triggered: sourceSample.includes('TrustEnvelopeIndexPage') && !sourceSample.includes('TrustIndexVerifiedRevenueCell'),
  });
  detectors.push({
    name: 'trust-index-missing-confidence-cell',
    triggered: sourceSample.includes('TrustEnvelopeIndex') && !sourceSample.includes('TrustIndexConfidenceCell'),
  });
  detectors.push({
    name: 'trust-index-missing-policy-pill',
    triggered: sourceSample.includes('TrustEnvelopeIndex') && !sourceSample.includes('PolicyAuthorityPill'),
  });
  detectors.push({
    name: 'trust-index-missing-audit-reference',
    triggered:
      sourceSample.includes('TrustEnvelopeIndex') &&
      !sourceSample.includes('buildTrustEnvelopeAuditReferenceHref'),
  });
  detectors.push({
    name: 'query-state-memory-only',
    triggered: /useState\([^)]*filters/.test(sourceSample) && !sourceSample.includes('useLocation'),
  });
  detectors.push({
    name: 'missing-stale-response-guard',
    triggered: sourceSample.includes('useClaimsLedger') && !sourceSample.includes('activeQueryKeyRef'),
  });
  detectors.push({
    name: 'missing-url-canonicalizer',
    triggered: sourceSample.includes('ClaimsLedgerPage') && !sourceSample.includes('parseCanonicalClaimsQuery'),
  });
  detectors.push({
    name: 'missing-query-updating-state',
    triggered: sourceSample.includes('ClaimsLedgerTable') && !sourceSample.includes('data-query-updating'),
  });
  return detectors;
}

export function runLevel7SourceIntegrityProbes(): Array<{ name: string; ok: boolean }> {
  const trustTable = readFileSync(
    join(ROOT, 'src', 'components', 'trustIndex', 'TrustEnvelopeIndexTable', 'TrustEnvelopeIndexTable.tsx'),
    'utf8',
  );
  const trustCells = readFileSync(
    join(ROOT, 'src', 'components', 'trustIndex', 'TrustEnvelopeIndexTable', 'TrustEnvelopeIndexTableCells.tsx'),
    'utf8',
  );
  const harness = readFileSync(join(ROOT, 'src', 'test', 'level7.harness.test.tsx'), 'utf8');
  const shellRoutes = readFileSync(join(ROOT, 'src', 'app', 'routes', 'ShellRoutes.tsx'), 'utf8');
  const claimsHook = readFileSync(join(ROOT, 'src', 'claims', 'useClaimsLedger.ts'), 'utf8');
  const queryState = readFileSync(join(ROOT, 'src', 'ledger', 'claimsQueryState.ts'), 'utf8');

  return [
    { name: 'trust-index-verified-revenue', ok: trustCells.includes('TrustIndexVerifiedRevenueCell') },
    { name: 'trust-index-confidence-cell', ok: trustCells.includes('TrustIndexConfidenceCell') },
    { name: 'trust-index-policy-pill', ok: trustCells.includes('PolicyAuthorityPill') },
    { name: 'trust-index-claimed-revenue', ok: trustCells.includes('TrustIndexClaimedRevenueCell') },
    { name: 'trust-index-difference-cell', ok: trustCells.includes('DiscrepancyIndicator') },
    {
      name: 'trust-index-forensic-audit-reference',
      ok: trustCells.includes('buildTrustEnvelopeAuditReferenceHref'),
    },
    { name: 'trust-index-audit-open', ok: trustCells.includes('data-trust-index-audit-open') },
    { name: 'trust-index-ten-columns', ok: trustTable.includes('TRUST_ENVELOPE_INDEX_COLUMN_KEYS') },
    { name: 'harness-shell-channels', ok: harness.includes('/app/channels') },
    { name: 'harness-benchmark-redirect', ok: harness.includes('benchmarks/*') || shellRoutes.includes('benchmarks/*') },
    { name: 'harness-shell-exceptions', ok: harness.includes('/app/exceptions') },
    { name: 'harness-shell-budget', ok: harness.includes('/app/budget') },
    { name: 'harness-10k-request-count', ok: harness.includes('10000') },
    { name: 'harness-50k-request-count', ok: harness.includes('50000') },
    { name: 'harness-url-query-persistence', ok: harness.includes('parseCanonicalClaimsQuery') },
    { name: 'harness-confidence-cell-tests', ok: harness.includes('ConfidenceCell') },
    { name: 'harness-benchmark-cell-tests', ok: harness.includes('BenchmarkCell') },
    { name: 'harness-mobile-compact-row', ok: harness.includes('CompactLedgerRow') },
    { name: 'harness-pagination-keyboard', ok: harness.includes('keyboard Enter and Space activation') },
    { name: 'harness-stale-response', ok: harness.includes('mounted claims page ignores late stale response') },
    { name: 'harness-url-mutation-behavioral', ok: harness.includes('filter change mutates router search query') },
    { name: 'harness-back-forward', ok: harness.includes('history back restores claims query state') },
    { name: 'harness-deep-link-initialization', ok: harness.includes('deep-link initialization hydrates controls') },
    { name: 'harness-return-from-detail', ok: harness.includes('return from claim detail preserves ledger query') || harness.includes('return from blocked detail preserves ledger query') },
    { name: 'harness-out-of-order-hook-integration', ok: harness.includes('setClaimsListDelayBySourceForTests') },
    { name: 'harness-375px-viewport', ok: harness.includes('375px viewport activates mobile ledger path') },
    { name: 'harness-filter-keyboard', ok: harness.includes('filter keyboard operation updates URL') },
    { name: 'harness-pagination-keyboard-router', ok: harness.includes('pagination keyboard Space changes URL offset') },
    { name: 'harness-row-enter-affordance', ok: harness.includes('detail affordance keyboard activation') || harness.includes('detail navigation keyboard activation') },
    { name: 'harness-query-transition-guard', ok: harness.includes('query transition disables pagination') },
    { name: 'claims-query-key-guard', ok: claimsHook.includes('activeQueryKeyRef') },
    { name: 'claims-query-canonicalizer', ok: queryState.includes('parseCanonicalClaimsQuery') },
    { name: 'claims-updating-state', ok: claimsHook.includes('setUpdating') },
  ];
}

export function runLevel7IntegrityProbes() {
  const results: Array<{ name: string; ok: boolean }> = [];

  const items = createSyntheticDataset((i) => ({ id: i, value: 1000 - i }), 100);
  const page1 = executeServerQuery('probe', {
    items,
    params: { offset: 0, pageSize: 25, sortKey: 'date', sortDirection: 'desc' },
    defaultSortKey: 'date',
    getSortValue: (row) => row.value,
  });
  const globalHigh = executeServerQuery('probe', {
    items,
    params: { offset: 0, pageSize: 25, sortKey: 'date', sortDirection: 'desc' },
    defaultSortKey: 'date',
    getSortValue: (row) => row.value,
  });
  results.push({
    name: 'global-sort-high-value-on-page-1',
    ok: !('error' in page1) && !('error' in globalHigh) && page1.rows[0]?.value === 1000,
  });

  const domCap = executeServerQuery('probe', {
    items: createSyntheticDataset((i) => ({ id: i }), 50000),
    params: { offset: 0, pageSize: 25 },
    defaultSortKey: 'id',
    getSortValue: (row) => row.id,
  });
  results.push({
    name: 'dom-bounded-page-size',
    ok: !('error' in domCap) && domCap.rows.length <= MAX_DOM_TABLE_ROWS,
  });

  const bounded = assertBoundedRequestCount();
  results.push({ name: 'request-count-bounded', ok: bounded.ok });

  const forbidden = detectForbiddenListFields({ fullEnvelope: {}, envelopeId: 'x' }, FORBIDDEN_LIST_ENVELOPE_FIELDS);
  results.push({ name: 'forbidden-list-fields-detected', ok: forbidden.length > 0 });

  return results;
}

export function runLevel7NegativeScopeScanCli() {
  const scan = runLevel7NegativeScopeScan();
  const routes = assertLevel7RoutesExist();
  if (!routes.ok) {
    scan.violations.push({
      file: 'routes',
      type: 'missing-route',
      value: routes.missing.join(', '),
    });
  }
  return scan;
}
