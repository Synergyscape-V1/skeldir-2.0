import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const ROOT = join(import.meta.dirname, '..', '..');

const SCAN_DIRS = [
  join(ROOT, 'src', 'app'),
  join(ROOT, 'src', 'activation'),
  join(ROOT, 'src', 'integration'),
  join(ROOT, 'src', 'components', 'onboarding'),
  join(ROOT, 'src', 'components', 'integration'),
];

const BLOCKLIST_DEFINITION_FILES = new Set([
  'level3NegativeScopeScan.ts',
  'privacyScan.ts',
  'OnboardingProgressRail.tsx',
  'copy.ts',
]);

const ALLOWED_REFERENCE_FILES = new Set([
  'OnboardingProgressRail.tsx',
  'copy.ts',
  'level3NegativeScopeScan.ts',
  'ShellFallbackPanel.tsx',
  'navigation.ts',
]);

const ALLOWED_L7_FILES = new Set([
  'App.tsx',
  'LedgerAliases.tsx',
  'LedgerRoutes.tsx',
  'Level8BlockedDetailPage.tsx',
  'BlockedDetailAffordance.tsx',
  'copy.ts',
]);

const ALLOWED_L11_FILES = new Set([
  'App.tsx',
  'GovernanceAliases.tsx',
  'ShellRoutes.tsx',
  'GovernanceRoutes.tsx',
]);

const L7_ROUTE_PATHS = [
  'path="/claims"',
  'path="/trust/',
  'path="/channels"',
  'path="/benchmarks"',
  'path="/budget"',
  'path="/exceptions"',
];

const FORBIDDEN_L6_PLUS_ROUTES = [
  'path="/settings/billing"',
  ...L7_ROUTE_PATHS,
];

const FORBIDDEN_PREMATURE_SURFACES = [
  'Generate first TrustEnvelope',
  'first deterministic TrustEnvelope generated',
  'Add humans or agents',
  'Create agent key',
  'Policy settings',
  'Audit Ledger',
  'All systems operational',
  'Confidence degraded',
  'Trust API paused',
  '/audit?filter=system_health',
  'verified revenue trend',
  'priority queue',
  'recent TrustEnvelopes',
  'claim ledger',
  'TrustEnvelope detail',
  'artifact hash',
  'semantic truth hash',
  'signature hash',
  'Export verified report',
  'Verify signature',
  'Budget Simulation detail',
  'Exception Queue',
];

const FORBIDDEN_FETCH_IN_UI = [
  'IntegrationSourceCard.tsx',
  'CommerceSourceCard.tsx',
  'ClaimSourceCard.tsx',
  'TrustWorkspaceStep.tsx',
  'CommerceTruthStep.tsx',
  'ClaimSourcesStep.tsx',
  'PrivacyBoundaryStep.tsx',
  'OnboardingWizard.tsx',
];

function walk(dir: string, acc: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) walk(full, acc);
    else if (/\.(tsx|ts|css)$/.test(entry)) acc.push(full);
  }
  return acc;
}

export function runLevel3NegativeScopeScan() {
  const files = SCAN_DIRS.flatMap((dir) => walk(dir, []));
  const violations: Array<{ file: string; type: string; value: string }> = [];

  for (const file of files) {
    const rel = relative(ROOT, file);
    if (rel.includes('.test.')) continue;

    const basename = rel.split(/[/\\]/).pop() ?? rel;
    if (BLOCKLIST_DEFINITION_FILES.has(basename) && !rel.includes('components')) continue;

    const content = readFileSync(file, 'utf8');

    for (const route of FORBIDDEN_L6_PLUS_ROUTES) {
      if (L7_ROUTE_PATHS.includes(route) && ALLOWED_L7_FILES.has(basename)) continue;
      if (route === 'path="/settings/billing"' && ALLOWED_L11_FILES.has(basename)) continue;
      if (content.includes(route)) {
        violations.push({ file: rel, type: 'level6-plus-route', value: route });
      }
    }

    for (const term of FORBIDDEN_PREMATURE_SURFACES) {
      if (
        content.toLowerCase().includes(term.toLowerCase()) &&
        !ALLOWED_REFERENCE_FILES.has(basename) &&
        !ALLOWED_L7_FILES.has(basename)
      ) {
        violations.push({ file: rel, type: 'premature-trust-surface', value: term });
      }
    }

    if (FORBIDDEN_FETCH_IN_UI.includes(basename) && content.includes('fetch(')) {
      violations.push({ file: rel, type: 'fetch-in-level3-ui', value: 'fetch(' });
    }
  }

  return { filesScanned: files.length, violations };
}

export function assertLevel3RoutesExist(): { ok: boolean; missing: string[] } {
  const shellRoutes = readFileSync(join(ROOT, 'src', 'app', 'routes', 'ShellRoutes.tsx'), 'utf8');
  const app = readFileSync(join(ROOT, 'src', 'app', 'App.tsx'), 'utf8');
  const required = [
    'onboarding/step/:step',
    'OnboardingWizard',
    'IntegrationsPage',
    'integrations',
    '/onboarding/*',
    '/integrations/*',
  ];
  const combined = shellRoutes + app;
  const missing = required.filter((token) => !combined.includes(token));
  return { ok: missing.length === 0, missing };
}

export function assertLevel3ComponentsExist(): { ok: boolean; missing: string[] } {
  const requiredFiles = [
    'src/components/onboarding/OnboardingWizard/OnboardingWizard.tsx',
    'src/components/onboarding/TrustWorkspaceStep/TrustWorkspaceStep.tsx',
    'src/components/onboarding/CommerceTruthStep/CommerceTruthStep.tsx',
    'src/components/onboarding/ClaimSourcesStep/ClaimSourcesStep.tsx',
    'src/components/onboarding/PrivacyBoundaryStep/PrivacyBoundaryStep.tsx',
    'src/components/integration/IntegrationSourceCard/IntegrationSourceCard.tsx',
    'src/components/integration/CommerceSourceCard/CommerceSourceCard.tsx',
    'src/components/integration/ClaimSourceCard/ClaimSourceCard.tsx',
    'src/integration/integrationClient.ts',
    'src/activation/activationStore.ts',
    'src/components/onboarding/Level3RouteGuard/Level3RouteGuard.tsx',
  ];
  const missing = requiredFiles.filter((file) => {
    try {
      statSync(join(ROOT, file));
      return false;
    } catch {
      return true;
    }
  });
  return { ok: missing.length === 0, missing };
}

export function runLevel3SabotageProbes(sourceSample: string) {
  const probes: Array<{ name: string; pattern: string; shouldDetect: boolean }> = [
    { name: 'claims-route', pattern: 'path="/claims"', shouldDetect: true },
    { name: 'health-strip', pattern: 'All systems operational', shouldDetect: true },
    { name: 'trust-envelope-preview', pattern: 'TrustEnvelope detail', shouldDetect: true },
    { name: 'verified-revenue-trend', pattern: 'verified revenue trend', shouldDetect: true },
    { name: 'fetch-in-card', pattern: 'IntegrationSourceCard', shouldDetect: false },
    { name: 'onboarding-allowed', pattern: 'onboarding/step/:step', shouldDetect: false },
  ];

  return probes.map((probe) => ({
    name: probe.name,
    pass: sourceSample.includes(probe.pattern) === probe.shouldDetect,
    detected: sourceSample.includes(probe.pattern),
    expected: probe.shouldDetect,
  }));
}
