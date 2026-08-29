import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import {
  MAX_EXPORT_PREVIEW_DOM_NODES,
} from '../actions/bounds';
import { buildCanonicalTrustEnvelopeJson } from '../actions/idempotency';
import { exportVerifiedReport } from '../actions/claimExportClient';
import { resetIdempotencyStoreForTests } from '../actions/idempotency';
import { buildMinimalTrustEnvelopeJsonContract } from '../trustIndex/trustEnvelopeJsonContract';

const ROOT = join(import.meta.dirname, '..', '..');

const SCAN_DIRS = [
  join(ROOT, 'src', 'actions'),
  join(ROOT, 'src', 'components', 'claims', 'ClaimDetailPage'),
  join(ROOT, 'src', 'components', 'trust', 'TrustEnvelopeOperatorView'),
  join(ROOT, 'src', 'actions', 'ExportReportButton.tsx'),
  join(ROOT, 'src', 'components', 'budget', 'BudgetSimulationDetailPage'),
  join(ROOT, 'src', 'components', 'exceptions', 'ExceptionDetailModal'),
  join(ROOT, 'src', 'components', 'audit', 'AuditLedgerPage'),
  join(ROOT, 'evidence', 'Level_9'),
];

const FORBIDDEN_L10_L11 = [
  'Trust Command Center content',
  'priority queue',
  'verified revenue trend',
  'channel trust table summary',
  'recent TrustEnvelopes aggregate strip',
  'billing recovery surface',
  'route-recovery surface',
  'Command Center dashboard',
];

const REQUIRED_L9_MARKERS = [
  'ClaimExportFlow',
  'ExportReportButton',
  'AuditExportFlow',
  'BudgetProposalFlow',
  'ExceptionActionControls',
  'data-level9-action',
  'data-claim-export-flow',
  'data-trust-envelope-actions',
  'data-audit-export-flow',
  'data-budget-proposal-flow',
  'data-exception-action-controls',
  'exportVerifiedReport',
  'exportArtifact',
  'exportAuditReconstruction',
  'submitBudgetProposal',
  'acknowledgeException',
  'MAX_EXPORT_PREVIEW_BYTES',
  'artifact integrity',
];

const FORBIDDEN_TRUST_DETAIL_DESTINATION = [
  'TrustEnvelopeDetailPage',
  'path="trust/:envelopeId"',
  '/app/trust/${',
  'TrustEnvelopeJsonViewer',
  'TrustHashBlock',
  'verifySignature(',
] as const;

const FORBIDDEN_COPY = [
  'budget applied',
  'auto-optimize',
  'guaranteed lift',
  'spend updated',
  'claim verified solely because signature passed',
  'financial truth verified',
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

export function runLevel9NegativeScopeScan() {
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

    for (const term of FORBIDDEN_L10_L11) {
      if (content.includes(term)) {
        violations.push({ file: rel, type: 'level10-11-leakage', value: term });
      }
    }

    // Forbidden live UI copy applies to product source only — not evidence markdown.
    if (/\.(tsx|ts)$/.test(file) && !rel.includes('level9NegativeScopeScan')) {
      for (const term of FORBIDDEN_COPY) {
        const negated = new RegExp(`(?<!no )${term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`, 'i');
        if (negated.test(content)) {
          violations.push({ file: rel, type: 'forbidden-copy', value: term });
        }
      }
    }

    if (rel.includes('ClaimDetailPage') && content.includes('Level9BlockedAffordance')) {
      violations.push({ file: rel, type: 'level8-blocked-leak', value: 'Level9BlockedAffordance' });
    }

    if (
      rel.startsWith('src\\components') &&
      !rel.includes('TrustEnvelopeOperatorView') &&
      !rel.includes('trustIndex') &&
      !rel.endsWith('level9NegativeScopeScan.ts')
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

  const exportClient = readFileSync(join(ROOT, 'src', 'actions', 'trustEnvelopeActionClient.ts'), 'utf8');
  if (/semanticTruthHash:\s*['"][^'"]+['"]/.test(exportClient) || /artifactHash:\s*['"][^'"]+['"]/.test(exportClient)) {
    violations.push({ file: 'trustEnvelopeActionClient.ts', type: 'export-hash-leak', value: 'non-empty hash field' });
  }

  const boundsContent = readFileSync(join(ROOT, 'src', 'actions', 'bounds.ts'), 'utf8');
  if (!boundsContent.includes('MAX_EXPORT_PREVIEW_BYTES') || !boundsContent.includes('32_768')) {
    violations.push({ file: 'bounds.ts', type: 'missing-bound', value: 'MAX_EXPORT_PREVIEW_BYTES' });
  }

  return { filesScanned: files.length, violations };
}

export function assertLevel9FlowsExist() {
  const paths = [
    join(ROOT, 'src', 'actions', 'claimExportClient.ts'),
    join(ROOT, 'src', 'actions', 'trustEnvelopeActionClient.ts'),
    join(ROOT, 'src', 'actions', 'auditExportClient.ts'),
    join(ROOT, 'src', 'actions', 'budgetProposalClient.ts'),
    join(ROOT, 'src', 'actions', 'exceptionActionClient.ts'),
    join(ROOT, 'src', 'actions', 'copy.ts'),
    join(ROOT, 'src', 'actions', 'ClaimExportFlow.tsx'),
    join(ROOT, 'src', 'actions', 'TrustEnvelopeActions.tsx'),
    join(ROOT, 'src', 'actions', 'trustEnvelopeActionClient.ts'),
    join(ROOT, 'src', 'actions', 'copy.ts'),
    join(ROOT, 'src', 'actions', 'AuditExportFlow.tsx'),
    join(ROOT, 'src', 'actions', 'BudgetProposalFlow.tsx'),
    join(ROOT, 'src', 'actions', 'ExceptionActionControls.tsx'),
    join(ROOT, 'src', 'actions', 'GovernedActionControl.tsx'),
    join(ROOT, 'src', 'components', 'claims', 'ClaimDetailPage', 'ClaimDetailPage.tsx'),
    join(ROOT, 'src', 'actions', 'ExportReportButton.tsx'),
    join(ROOT, 'src', 'components', 'trust', 'TrustEnvelopeOperatorView', 'TrustEnvelopeOperatorDrawer.tsx'),
    join(ROOT, 'src', 'components', 'audit', 'AuditLedgerPage', 'AuditLedgerPage.tsx'),
    join(ROOT, 'src', 'components', 'budget', 'BudgetSimulationDetailPage', 'BudgetSimulationDetailPage.tsx'),
    join(ROOT, 'src', 'components', 'exceptions', 'ExceptionDetailModal', 'ExceptionDetailModal.tsx'),
  ];
  const combined = paths.map((p) => readFileSync(p, 'utf8')).join('\n');
  const missing = REQUIRED_L9_MARKERS.filter((m) => !combined.includes(m));
  return { ok: missing.length === 0, missing };
}

export function runLevel9SabotageProbes(sourceSample: string) {
  return [
    { name: 'missing-audit-on-success', triggered: sourceSample.includes('status: success') && !sourceSample.includes('auditEventId') },
    { name: 'missing-artifact-on-export', triggered: sourceSample.includes('exportVerifiedReport') && sourceSample.includes('artifactRef: undefined') },
    { name: 'dom-copy-json', triggered: /document\.querySelector[\s\S]*clipboard/.test(sourceSample) },
    { name: 'budget-spend-mutation', triggered: /spend updated|budget applied/i.test(sourceSample) },
    { name: 'signature-truth-overclaim', triggered: /claim verified solely because signature/i.test(sourceSample) },
    { name: 'level10-command-center', triggered: sourceSample.includes('Trust Command Center content') },
    { name: 'missing-idempotency', triggered: sourceSample.includes('performExceptionAction') && !sourceSample.includes('idempotencyKey') },
    { name: 'policy-bypass-direct-submit', triggered: sourceSample.includes('onClick={onExecute}') && !sourceSample.includes('validatePolicyBeforeSubmit') },
    { name: 'unbounded-export-preview', triggered: sourceSample.includes('export preview') && !sourceSample.includes('MAX_EXPORT_PREVIEW') },
  ];
}

export function runLevel9SourceSabotageProbes() {
  const governed = readFileSync(join(ROOT, 'src', 'actions', 'GovernedActionControl.tsx'), 'utf8');
  const claimFlow = readFileSync(join(ROOT, 'src', 'actions', 'ClaimExportFlow.tsx'), 'utf8');
  const harness = readFileSync(join(ROOT, 'src', 'test', 'level9.harness.test.tsx'), 'utf8');
  const combined = [governed, claimFlow, harness].join('\n');
  return [
    { name: 'missing-outcome-status-attr', triggered: !governed.includes('data-level9-outcome-status') },
    { name: 'missing-pending-aria-busy', triggered: !governed.includes('aria-busy') },
    { name: 'missing-idempotency-pending-ref', triggered: !readFileSync(join(ROOT, 'src', 'actions', 'useGovernedAction.ts'), 'utf8').includes('pendingRef') },
    { name: 'missing-mounted-execute-success', triggered: !harness.includes('Mounted execute-through-success') },
    { name: 'missing-mounted-failure-matrix', triggered: !harness.includes('Mounted failure state matrix') },
    { name: 'missing-mounted-idempotency', triggered: !harness.includes('Mounted idempotency') },
    { name: 'missing-mounted-375px', triggered: !harness.includes('375px') },
    { name: 'missing-exception-five-actions', triggered: !harness.includes('exception action %s executes') },
    { name: 'missing-focus-trap-test', triggered: !harness.includes('focus trap wraps') },
    { name: 'missing-session-registry', triggered: !readFileSync(join(ROOT, 'src', 'actions', 'actionRegistry.ts'), 'utf8').includes('sessionStorage') },
    { name: 'missing-hard-refresh-harness', triggered: !harness.includes('hard refresh preserves completed outcome') },
    { name: 'missing-route-unmount-harness', triggered: !harness.includes('route unmount during pending') },
    { name: 'missing-back-resubmit-harness', triggered: !harness.includes('history back during confirmation') },
    { name: 'missing-escape-harness', triggered: !harness.includes('destructive confirmation modal ignores Escape') },
    { name: 'missing-browser-audit-script', triggered: !readFileSync(join(ROOT, 'scripts', 'run-level9-browser-audit.ts'), 'utf8').includes('clipboard.readText') },
    { name: 'dom-copy-json-in-actions', triggered: /document\.querySelector[\s\S]*clipboard/.test([governed, claimFlow, readFileSync(join(ROOT, 'src', 'actions', 'TrustEnvelopeActions.tsx'), 'utf8')].join('\n')) },
    { name: 'budget-spend-mutation-in-ui', triggered: /(?<!no )spend updated/i.test(claimFlow) && !claimFlow.includes('No spend') },
  ];
}

export function runLevel9SourceIntegrityProbes() {
  const bounds = readFileSync(join(ROOT, 'src', 'actions', 'bounds.ts'), 'utf8');
  const harness = readFileSync(join(ROOT, 'src', 'test', 'level9.harness.test.tsx'), 'utf8');
  return [
    { name: 'bounds-export-preview', ok: bounds.includes('32_768') },
    { name: 'bounds-dom-nodes', ok: bounds.includes('MAX_EXPORT_PREVIEW_DOM_NODES') },
    { name: 'bounds-copy-json', ok: bounds.includes('65_536') },
    { name: 'bounds-download', ok: bounds.includes('1_048_576') },
    { name: 'harness-mounted-claim-success', ok: harness.includes('claim export confirms') },
    { name: 'harness-mounted-trust-export', ok: harness.includes('TrustEnvelope export report') },
    { name: 'harness-mounted-audit-export', ok: harness.includes('audit export confirms') },
    { name: 'harness-mounted-budget-proposal', ok: harness.includes('budget proposal confirms') },
    { name: 'harness-exception-five-actions', ok: harness.includes('exception action %s executes') },
    { name: 'harness-mounted-idempotency', ok: harness.includes('double-click confirm') },
    { name: 'harness-mounted-failure-matrix', ok: harness.includes('Mounted failure state matrix') },
    { name: 'harness-kill-switch-matrix', ok: harness.includes('Kill switch and degraded state') },
    { name: 'harness-focus-trap', ok: harness.includes('focus trap wraps') },
    { name: 'harness-375px-flows', ok: harness.includes('375px') && harness.includes('action flow remains usable') },
    { name: 'harness-sabotage-source', ok: harness.includes('runLevel9SourceSabotageProbes') },
    { name: 'harness-artifact-dom-bounded', ok: harness.includes('assertPreviewDomBounded') },
    { name: 'harness-iteration-iii-durability', ok: harness.includes('Durability, navigation, clipboard (Iteration III)') },
    { name: 'harness-hard-refresh', ok: harness.includes('hard refresh preserves completed outcome') },
    { name: 'harness-route-unmount', ok: harness.includes('route unmount during pending') },
    { name: 'export-no-forensic-hashes', ok: readFileSync(join(ROOT, 'src', 'actions', 'trustEnvelopeActionClient.ts'), 'utf8').includes("semanticTruthHash: ''") && readFileSync(join(ROOT, 'src', 'actions', 'trustEnvelopeActionClient.ts'), 'utf8').includes("artifactHash: ''") },
    { name: 'bounds-clipboard-denied', ok: bounds.includes('NotAllowedError') },
    { name: 'canonical-json-sort', ok: buildCanonicalTrustEnvelopeJson(buildMinimalTrustEnvelopeJsonContract({
      provenanceChain: [
        {
          timestamp: '2026-07-02T13:00:00Z',
          eventType: 'Later',
          source: 's',
          result: 'r',
          evidenceReference: 'EV-B',
        },
        {
          timestamp: '2026-07-02T12:00:00Z',
          eventType: 'Earlier',
          source: 's',
          result: 'r',
          evidenceReference: 'EV-A',
        },
      ],
    })).includes('"eventType": "Earlier"') },
  ];
}

export async function runLevel9ClientProbe() {
  resetIdempotencyStoreForTests();
  const outcome = await exportVerifiedReport('tenant_test_001', 'claim_0001', 'v_claim_0001_1');
  return {
    ok: outcome.status === 'success' && Boolean(outcome.auditEventId) && Boolean(outcome.artifactRef),
    outcome,
  };
}

export function runLevel9NegativeScopeScanCli() {
  const scan = runLevel9NegativeScopeScan();
  const flows = assertLevel9FlowsExist();
  if (scan.violations.length > 0) {
    console.error('Level 9 scope violations:', scan.violations);
    process.exit(1);
  }
  if (!flows.ok) {
    console.error('Missing Level 9 markers:', flows.missing);
    process.exit(1);
  }
  console.log(`Level 9 scope scan: ${scan.filesScanned} files, 0 violations`);
  console.log(`Level 9 flow markers: ${REQUIRED_L9_MARKERS.length - flows.missing.length}/${REQUIRED_L9_MARKERS.length}`);
}

if (import.meta.url === `file://${process.argv[1]?.replace(/\\/g, '/')}`) {
  runLevel9NegativeScopeScanCli();
}
