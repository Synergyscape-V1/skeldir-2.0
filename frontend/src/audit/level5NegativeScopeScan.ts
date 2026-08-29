import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { detectInvalidSignatureJsonLeak } from '../operationalAudit/artifactIntegrity';
import {
  detectHealthDomainConflation,
  validateHealthDomainSeparation,
} from '../operationalAudit/healthDomain';
import { MAX_DOM_TABLE_ROWS } from '../operationalAudit/pagination';

const ROOT = join(import.meta.dirname, '..', '..');

const SCAN_DIRS = [
  join(ROOT, 'src', 'app'),
  join(ROOT, 'src', 'operationalAudit'),
  join(ROOT, 'src', 'components', 'operational'),
  join(ROOT, 'src', 'components', 'audit'),
];

const ALLOWED_REFERENCE_FILES = new Set([
  'level5NegativeScopeScan.ts',
  'navigation.ts',
  'ShellFallbackPanel.tsx',
  'copy.ts',
  'level4NegativeScopeScan.ts',
  'level3NegativeScopeScan.ts',
  'level2NegativeScopeScan.ts',
]);

const REQUIRED_L5_ROUTES = [
  'path="audit/*"',
  'path="diagnostics"',
  'AuditLedgerRoute',
  'OperationalDiagnosticsRoute',
];

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
  ...L7_ROUTE_PATHS,
  'path="/settings/billing"',
];

const FORBIDDEN_L6_PLUS_SURFACES = [
  'Generate first TrustEnvelope',
  'TrustEnvelope detail',
  'verified revenue trend',
  'priority queue',
  'recent TrustEnvelopes',
  'claim ledger',
  'Export verified report',
  'Verify signature',
  'audit export',
  'reconstruction export',
  'Budget Simulation detail',
  'Exception Queue',
  'Command Center dashboard',
  'Trust Command Center content',
];

const FORBIDDEN_FETCH_IN_UI = [
  'AuditLedgerPage.tsx',
  'AuditArtifactDrawer.tsx',
  'OperationalDiagnosticsPage.tsx',
];

const FORBIDDEN_ACTIONS = [
  'exportAudit',
  'verifySignature',
  'exportArtifact',
  'reconstructAudit',
  'TrustEnvelopeDetail',
  'TrustHashBlock',
];

function walk(dir: string, acc: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) walk(full, acc);
    else if (/\.(tsx|ts|css)$/.test(entry)) acc.push(full);
  }
  return acc;
}

export function runLevel5NegativeScopeScan() {
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

    for (const route of FORBIDDEN_L6_PLUS_ROUTES) {
      if (L7_ROUTE_PATHS.includes(route) && ALLOWED_L7_FILES.has(basename)) continue;
      if (route === 'path="/settings/billing"' && ALLOWED_L11_FILES.has(basename)) continue;
      if (content.includes(route)) {
        violations.push({ file: rel, type: 'level6-plus-route', value: route });
      }
    }

    for (const term of FORBIDDEN_L6_PLUS_SURFACES) {
      if (
        content.toLowerCase().includes(term.toLowerCase()) &&
        !ALLOWED_REFERENCE_FILES.has(basename) &&
        !ALLOWED_L7_FILES.has(basename)
      ) {
        violations.push({ file: rel, type: 'level6-plus-surface', value: term });
      }
    }

    for (const action of FORBIDDEN_ACTIONS) {
      if (content.includes(action) && !ALLOWED_L7_FILES.has(basename)) {
        violations.push({ file: rel, type: 'forbidden-action', value: action });
      }
    }

    if (FORBIDDEN_FETCH_IN_UI.includes(basename) && content.includes('fetch(')) {
      violations.push({ file: rel, type: 'fetch-in-l5-ui', value: 'fetch(' });
    }
  }

  return { filesScanned: files.length, violations };
}

export function assertLevel5RoutesExist(): { ok: boolean; missing: string[] } {
  const shellRoutes = readFileSync(join(ROOT, 'src', 'app', 'routes', 'ShellRoutes.tsx'), 'utf8');
  const app = readFileSync(join(ROOT, 'src', 'app', 'App.tsx'), 'utf8');
  const shellBrand = readFileSync(
    join(ROOT, 'src', 'components', 'shell', 'ShellBrand', 'ShellBrand.tsx'),
    'utf8',
  );
  const topHeader = readFileSync(
    join(ROOT, 'src', 'components', 'shell', 'TopHeader', 'TopHeader.tsx'),
    'utf8',
  );
  const combined = shellRoutes + app + shellBrand + topHeader;
  const missing = REQUIRED_L5_ROUTES.filter((token) => !combined.includes(token));
  return { ok: missing.length === 0, missing };
}

export function assertLevel5ComponentsExist(): { ok: boolean; missing: string[] } {
  const required = [
    'src/operationalAudit/operationalAuditClient.ts',
    'src/components/audit/AuditLedgerPage/AuditLedgerPage.tsx',
    'src/components/audit/AuditArtifactDrawer/AuditArtifactDrawer.tsx',
    'src/components/operational/OperationalDiagnosticsPage/OperationalDiagnosticsPage.tsx',
    'src/components/operational/Level5RouteGuard/Level5RouteGuard.tsx',
  ];
  const missing = required.filter((file) => {
    try {
      statSync(join(ROOT, file));
      return false;
    } catch {
      return true;
    }
  });
  return { ok: missing.length === 0, missing };
}

export function runLevel5SabotageProbes(sourceSample: string) {
  const probes: Array<{ name: string; pattern: string; shouldDetect: boolean }> = [
    { name: 'claims-route', pattern: 'path="/claims"', shouldDetect: true },
    { name: 'trust-route', pattern: 'path="/trust/', shouldDetect: true },
    { name: 'export-audit', pattern: 'exportAudit', shouldDetect: true },
    { name: 'verify-signature', pattern: 'verifySignature', shouldDetect: true },
    { name: 'trust-envelope-detail', pattern: 'TrustEnvelope detail', shouldDetect: true },
    { name: 'audit-route-allowed', pattern: 'path="audit/*"', shouldDetect: false },
    { name: 'health-operational-allowed', pattern: 'All systems operational', shouldDetect: false },
    { name: 'fetch-in-page-sabotage', pattern: 'fetch(', shouldDetect: true },
    { name: 'unbounded-rows-map', pattern: 'rows.map((row)', shouldDetect: true },
    { name: 'json-under-invalid-signature', pattern: 'data-artifact-json-preview', shouldDetect: true },
    { name: 'health-domain-conflation', pattern: 'verified revenue trend', shouldDetect: true },
    { name: 'drawer-without-selection', pattern: 'data-drawer-without-selection', shouldDetect: true },
  ];
  return probes.map((probe) => ({
    name: probe.name,
    pass: sourceSample.includes(probe.pattern) === probe.shouldDetect,
    detected: sourceSample.includes(probe.pattern),
    expected: probe.shouldDetect,
  }));
}

export function runLevel5IntegritySabotageProbes() {
  const tableSource = readFileSync(join(ROOT, 'src', 'components', 'layout', 'Table', 'Table.tsx'), 'utf8');
  const drawerSource = readFileSync(
    join(ROOT, 'src', 'components', 'audit', 'AuditArtifactDrawer', 'AuditArtifactDrawer.tsx'),
    'utf8',
  );
  const clientSource = readFileSync(
    join(ROOT, 'src', 'operationalAudit', 'operationalAuditClient.ts'),
    'utf8',
  );

  return [
    {
      name: 'invalid-signature-json-leak-detector',
      pass:
        detectInvalidSignatureJsonLeak(true, true) === true &&
        detectInvalidSignatureJsonLeak(true, false) === false,
    },
    {
      name: 'health-confidence-domain-clean',
      pass: validateHealthDomainSeparation('confidence_degraded').length === 0,
    },
    {
      name: 'health-api-paused-domain-clean',
      pass: validateHealthDomainSeparation('api_paused').length === 0,
    },
    {
      name: 'health-integration-domain-clean',
      pass: validateHealthDomainSeparation('integration_attention').length === 0,
    },
    {
      name: 'health-conflation-sabotage-detects',
      pass: detectHealthDomainConflation(
        'confidence_degraded',
        'Trust API is offline due to outage',
      ),
    },
    {
      name: 'table-enforces-dom-row-cap',
      pass: tableSource.includes('enforceDomRowCap') && tableSource.includes('MAX_DOM_TABLE_ROWS'),
    },
    {
      name: 'table-pagination-present',
      pass: tableSource.includes('data-table-pagination') && tableSource.includes('pagination'),
    },
    {
      name: 'client-pagination-slice',
      pass: clientSource.includes('slicePage'),
    },
    {
      name: 'drawer-without-selection-guard',
      pass: drawerSource.includes('data-drawer-without-selection') && drawerSource.includes('!eventId && open'),
    },
    {
      name: 'invalid-signature-fixture-present',
      pass: clientSource.includes('aud_006'),
    },
    {
      name: 'max-dom-rows-cap-constant',
      pass: MAX_DOM_TABLE_ROWS === 25,
    },
  ];
}
