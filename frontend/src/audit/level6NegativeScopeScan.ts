import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { validateEnvelopeSummary } from '../firstTrustEnvelope/firstTrustEnvelopeClient';
import {
  FORBIDDEN_SUMMARY_FIELDS,
  MAX_SUMMARY_PAYLOAD_BYTES,
  createOversizedSummaryFixture,
  detectForbiddenSummaryFields,
  hasProbabilisticConfidenceShape,
  isNakedScalarConfidence,
  measureSerializedPayloadBytes,
  validateSummaryTransportBoundary,
} from '../firstTrustEnvelope/summaryValidation';

const ROOT = join(import.meta.dirname, '..', '..');

const SCAN_DIRS = [
  join(ROOT, 'src', 'firstTrustEnvelope'),
  join(ROOT, 'src', 'components', 'onboarding', 'GenerateFirstTrustEnvelopeStep'),
  join(ROOT, 'src', 'components', 'onboarding', 'FirstTrustEnvelopeSummary'),
  join(ROOT, 'src', 'components', 'onboarding', 'AddHumansOrAgentsStep'),
  join(ROOT, 'src', 'components', 'onboarding', 'OnboardingWizard'),
  join(ROOT, 'src', 'components', 'onboarding', 'OnboardingProgressRail'),
  join(ROOT, 'src', 'components', 'onboarding', 'OnboardingMobileProgressAccordion'),
];

const ALLOWED_REFERENCE_FILES = new Set([
  'level6NegativeScopeScan.ts',
  'level5NegativeScopeScan.ts',
  'level4NegativeScopeScan.ts',
  'ShellFallbackPanel.tsx',
  'navigation.ts',
  'copy.ts',
]);

const REQUIRED_L6_ARTIFACTS = [
  'firstTrustEnvelopeClient.ts',
  'GenerateFirstTrustEnvelopeStep.tsx',
  'FirstTrustEnvelopeSummary.tsx',
  'AddHumansOrAgentsStep.tsx',
  'step5StateMachine.ts',
];

const FORBIDDEN_L7_PLUS_ROUTES = [
  'path="/claims"',
  'path="/trust/',
  'path="/channels"',
  'path="/benchmarks"',
  'path="/budget"',
  'path="/exceptions"',
  'path="/settings/billing"',
];

const FORBIDDEN_L7_PLUS_SURFACES = [
  'TrustEnvelope detail',
  'TrustEnvelope list',
  'Revenue Claims Ledger',
  'Command Center dashboard',
  'verified revenue trend',
  'recent TrustEnvelopes',
  'copy API response',
  'export artifact',
  'verify signature',
  'audit reconstruction export',
  'Budget Simulation detail',
  'Exception Queue',
];

const FORBIDDEN_STEP5_DETAIL = [
  'TrustEnvelopeJsonViewer',
  'TrustHashBlock',
  'copyApiResponse',
  'exportArtifact',
  'verifySignature',
  'copyTrustEnvelopeJson',
  'ClaimDetailTabs',
];

const FORBIDDEN_FETCH_IN_UI = [
  'GenerateFirstTrustEnvelopeStep.tsx',
  'FirstTrustEnvelopeSummary.tsx',
  'AddHumansOrAgentsStep.tsx',
];

function walk(dir: string, acc: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) walk(full, acc);
    else if (/\.(tsx|ts|css)$/.test(entry)) acc.push(full);
  }
  return acc;
}

export function runLevel6NegativeScopeScan() {
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

    for (const route of FORBIDDEN_L7_PLUS_ROUTES) {
      if (content.includes(route)) {
        violations.push({ file: rel, type: 'level7-plus-route', value: route });
      }
    }

    for (const term of FORBIDDEN_L7_PLUS_SURFACES) {
      if (
        content.toLowerCase().includes(term.toLowerCase()) &&
        !ALLOWED_REFERENCE_FILES.has(basename)
      ) {
        violations.push({ file: rel, type: 'level7-plus-surface', value: term });
      }
    }

    for (const detail of FORBIDDEN_STEP5_DETAIL) {
      if (content.includes(detail)) {
        violations.push({ file: rel, type: 'step5-detail-leak', value: detail });
      }
    }

    if (FORBIDDEN_FETCH_IN_UI.includes(basename) && content.includes('fetch(')) {
      violations.push({ file: rel, type: 'fetch-in-l6-ui', value: 'fetch(' });
    }
  }

  return { filesScanned: files.length, violations };
}

export function assertLevel6ComponentsExist(): { ok: boolean; missing: string[] } {
  const requiredPaths = [
    'src/firstTrustEnvelope/firstTrustEnvelopeClient.ts',
    'src/firstTrustEnvelope/step5StateMachine.ts',
    'src/components/onboarding/GenerateFirstTrustEnvelopeStep/GenerateFirstTrustEnvelopeStep.tsx',
    'src/components/onboarding/FirstTrustEnvelopeSummary/FirstTrustEnvelopeSummary.tsx',
    'src/components/onboarding/AddHumansOrAgentsStep/AddHumansOrAgentsStep.tsx',
  ];
  const missing = requiredPaths.filter((file) => {
    try {
      statSync(join(ROOT, file));
      return false;
    } catch {
      return true;
    }
  });
  return { ok: missing.length === 0, missing };
}

export function runLevel6SabotageProbes(sourceSample: string) {
  const probes: Array<{ name: string; pattern: string; shouldDetect: boolean }> = [
    { name: 'claims-route', pattern: 'path="/claims"', shouldDetect: true },
    { name: 'trust-route', pattern: 'path="/trust/', shouldDetect: true },
    { name: 'export-artifact', pattern: 'exportArtifact', shouldDetect: true },
    { name: 'verify-signature', pattern: 'verifySignature', shouldDetect: true },
    { name: 'copy-api-response', pattern: 'copyApiResponse', shouldDetect: true },
    { name: 'trust-envelope-json-viewer', pattern: 'TrustEnvelopeJsonViewer', shouldDetect: true },
    { name: 'broad-default-scope', pattern: 'propose_action', shouldDetect: true },
    { name: 'step5-allowed', pattern: 'Generate first TrustEnvelope', shouldDetect: false },
    {
      name: 'audit-link-allowed',
      pattern: 'buildTrustEnvelopeAuditReferenceHref',
      shouldDetect: false,
    },
    { name: 'fetch-in-step5-sabotage', pattern: 'fetch(', shouldDetect: true },
    { name: 'platform-claim-as-truth', pattern: 'platform claim is verified revenue', shouldDetect: true },
    { name: 'raw-backend-stack', pattern: 'Internal Server Error at', shouldDetect: true },
    { name: 'raw-envelope-field', pattern: 'rawEnvelope', shouldDetect: true },
    { name: 'signed-payload-field', pattern: 'signedPayload', shouldDetect: true },
    { name: 'envelope-json-field', pattern: 'envelopeJson', shouldDetect: true },
    { name: 'naked-confidence-scalar', pattern: 'Confidence: 94%', shouldDetect: true },
    { name: 'uniform-row-only-summary', pattern: 'className={styles.row}', shouldDetect: true },
    { name: 'authority-tier-allowed', pattern: 'data-authority-tier', shouldDetect: false },
    { name: 'payload-budget-allowed', pattern: 'MAX_SUMMARY_PAYLOAD_BYTES', shouldDetect: false },
  ];
  return probes.map((probe) => ({
    name: probe.name,
    pass: sourceSample.includes(probe.pattern) === probe.shouldDetect,
    detected: sourceSample.includes(probe.pattern),
    expected: probe.shouldDetect,
  }));
}

export function runLevel6IntegritySabotageProbes() {
  const step5Source = readFileSync(
    join(ROOT, 'src', 'components', 'onboarding', 'GenerateFirstTrustEnvelopeStep', 'GenerateFirstTrustEnvelopeStep.tsx'),
    'utf8',
  );
  const summarySource = readFileSync(
    join(ROOT, 'src', 'components', 'onboarding', 'FirstTrustEnvelopeSummary', 'FirstTrustEnvelopeSummary.tsx'),
    'utf8',
  );
  const clientSource = readFileSync(
    join(ROOT, 'src', 'firstTrustEnvelope', 'firstTrustEnvelopeClient.ts'),
    'utf8',
  );
  const stateMachineSource = readFileSync(
    join(ROOT, 'src', 'firstTrustEnvelope', 'step5StateMachine.ts'),
    'utf8',
  );

  const sampleEnvelope = {
    envelopeId: 'trust_envelope_01',
    subjectRef: 'commerce_event_01',
    verifiedRevenueMinor: 100n,
    currencyCode: 'USD',
    revenueAuthority: 'deterministic' as const,
    attributionModel: 'last_touch',
    attributionAuthority: 'deterministic' as const,
    confidenceStatus: 'unavailable' as const,
    policyAuthority: 'blocked' as const,
    auditEventId: 'aud_te_001',
    generatedAt: new Date().toISOString(),
  };

  const summaryValidationSource = readFileSync(
    join(ROOT, 'src', 'firstTrustEnvelope', 'summaryValidation.ts'),
    'utf8',
  );

  const availableConfidence = {
    envelopeId: 'trust_envelope_01',
    subjectRef: 'commerce_event_01',
    verifiedRevenueMinor: 100n,
    currencyCode: 'USD',
    revenueAuthority: 'deterministic' as const,
    attributionModel: 'last_touch',
    attributionAuthority: 'deterministic' as const,
    confidenceStatus: 'available' as const,
    confidenceAuthority: 'probabilistic' as const,
    confidenceReason: 'Posterior available.',
    confidenceMethodOrContext: 'tenant posterior',
    intervalLower: 0.1,
    intervalUpper: 0.2,
    credibleInterval: '10% – 20%',
    sampleOrSourceContext: 'commerce_event_01',
    policyAuthority: 'blocked' as const,
    auditEventId: 'aud_te_001',
    generatedAt: new Date().toISOString(),
  };

  const nakedConfidence = {
    ...availableConfidence,
    confidenceMethodOrContext: undefined,
    intervalLower: undefined,
    intervalUpper: undefined,
    credibleInterval: undefined,
    sampleOrSourceContext: undefined,
  };

  const oversizedFixture = createOversizedSummaryFixture();
  const forbiddenFixture = { ...sampleEnvelope, rawEnvelope: '{}' };

  return [
    {
      name: 'envelope-validation-requires-audit',
      pass: validateEnvelopeSummary(sampleEnvelope) && !validateEnvelopeSummary({ ...sampleEnvelope, auditEventId: '' }),
    },
    {
      name: 'step5-no-fetch',
      pass: !step5Source.includes('fetch('),
    },
    {
      name: 'summary-has-authority-badge',
      pass: summarySource.includes('AuthorityBadge') && summarySource.includes('FinancialValue'),
    },
    {
      name: 'summary-has-policy-pill',
      pass: summarySource.includes('PolicyAuthorityPill'),
    },
    {
      name: 'summary-has-audit-link',
      pass: summarySource.includes('buildTrustEnvelopeAuditReferenceHref'),
    },
    {
      name: 'summary-no-json-viewer',
      pass: !summarySource.includes('TrustEnvelopeJsonViewer'),
    },
    {
      name: 'client-has-idempotency-path',
      pass: clientSource.includes('idempotencyKey'),
    },
    {
      name: 'state-machine-has-ready-state',
      pass: stateMachineSource.includes('ready_to_generate'),
    },
    {
      name: 'state-machine-has-waiting-event',
      pass: stateMachineSource.includes('waiting_for_verified_commerce_event'),
    },
    {
      name: 'attribution-not-financial-truth-copy',
      pass: summarySource.includes('attributionNote') || summarySource.includes('Model output'),
    },
    {
      name: 'summary-has-authority-tiers',
      pass:
        summarySource.includes('data-authority-tier="deterministic-primary"') &&
        summarySource.includes('data-authority-tier="probabilistic-subordinate"') &&
        summarySource.includes('data-authority-tier="audit-reference"'),
    },
    {
      name: 'summary-no-uniform-row-only',
      pass: !summarySource.includes('className={styles.row}'),
    },
    {
      name: 'summary-no-naked-confidence-scalar',
      pass: !summarySource.includes('Confidence: 94%') && !summarySource.match(/>\s*available\s*</),
    },
    {
      name: 'payload-budget-constant-defined',
      pass: summaryValidationSource.includes(`MAX_SUMMARY_PAYLOAD_BYTES = ${MAX_SUMMARY_PAYLOAD_BYTES}`),
    },
    {
      name: 'forbidden-fields-rejected',
      pass: detectForbiddenSummaryFields(forbiddenFixture).includes('rawEnvelope'),
    },
    {
      name: 'oversized-payload-rejected',
      pass: !validateSummaryTransportBoundary(oversizedFixture).ok,
    },
    {
      name: 'probabilistic-confidence-shape-required',
      pass:
        hasProbabilisticConfidenceShape(availableConfidence) &&
        !hasProbabilisticConfidenceShape(nakedConfidence) &&
        isNakedScalarConfidence(nakedConfidence),
    },
    {
      name: 'state-machine-has-payload-oversized-phase',
      pass: stateMachineSource.includes('generation_payload_oversized'),
    },
    {
      name: 'state-machine-has-schema-invalid-phase',
      pass: stateMachineSource.includes('generation_schema_invalid'),
    },
    {
      name: 'forbidden-field-list-complete',
      pass: FORBIDDEN_SUMMARY_FIELDS.includes('rawEnvelope') && FORBIDDEN_SUMMARY_FIELDS.includes('signedPayload'),
    },
    {
      name: 'oversized-measurement-exceeds-budget',
      pass: measureSerializedPayloadBytes(oversizedFixture) > MAX_SUMMARY_PAYLOAD_BYTES,
    },
  ];
}
