import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const ROOT = join(import.meta.dirname, '..', '..');

const SCAN_DIRS = [
  join(ROOT, 'src', 'app'),
  join(ROOT, 'src', 'governance'),
  join(ROOT, 'src', 'components', 'governance'),
];

const ALLOWED_REFERENCE_FILES = new Set([
  'level4NegativeScopeScan.ts',
  'secretScan.ts',
  'navigation.ts',
  'ShellFallbackPanel.tsx',
  'copy.ts',
  'PolicySettingsComponents.tsx',
]);

const REQUIRED_L4_ROUTES = [
  'settings/team',
  'settings/policy',
  'TeamSettingsRoute',
  'PolicySettingsRoute',
];

const FORBIDDEN_AGENT_ACCESS_TOKENS = [
  'path="agents"',
  'AgentAccessRoute',
  '/app/agents',
  'agent-access',
  'data-agent-access-page',
  'AgentAccessPage',
  'AgentKeyCreationModal',
];

const ALLOWED_L5_ALIAS_FILES = new Set(['App.tsx', 'OperationalAuditAliases.tsx']);

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
  'level11NegativeScopeScan.ts',
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

const FORBIDDEN_L4_PREMATURE_SURFACES = [
  'Audit Ledger',
  'Audit Artifact Drawer',
  'All systems operational',
  'Confidence degraded',
  'Trust API paused',
  'Generate first TrustEnvelope',
  'first deterministic TrustEnvelope',
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
  'audit activity strip',
  'channel trust table',
];

const FORBIDDEN_FETCH_IN_UI = [
  'TeamSettingsPage.tsx',
  'PolicyConfigureModal.tsx',
  'PolicySettingsPage.tsx',
];

const FORBIDDEN_ACTION_EXECUTION = [
  'executeBudgetAction',
  'submitBudgetProposal',
  'exportVerifiedReport',
  'verifySignature',
  'suppressException',
];

function walk(dir: string, acc: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) walk(full, acc);
    else if (/\.(tsx|ts|css)$/.test(entry)) acc.push(full);
  }
  return acc;
}

export function runLevel4NegativeScopeScan() {
  const files = SCAN_DIRS.flatMap((dir) => walk(dir, []));
  const violations: Array<{ file: string; type: string; value: string }> = [];

  for (const file of files) {
    const rel = relative(ROOT, file);
    if (rel.includes('.test.')) continue;
    const basename = rel.split(/[/\\]/).pop() ?? rel;
    const content = readFileSync(file, 'utf8');

    if (basename === 'App.tsx' && content.includes('/audit')) {
      continue;
    }

    for (const route of FORBIDDEN_L6_PLUS_ROUTES) {
      if (L7_ROUTE_PATHS.includes(route) && ALLOWED_L7_FILES.has(basename)) continue;
      if (route === 'path="/settings/billing"' && ALLOWED_L11_FILES.has(basename)) continue;
      if (content.includes(route)) {
        violations.push({ file: rel, type: 'level6-plus-route', value: route });
      }
    }

    if (ALLOWED_L5_ALIAS_FILES.has(basename) && content.includes('/audit')) {
      /* alias-only reference permitted */
    }

    for (const term of FORBIDDEN_L4_PREMATURE_SURFACES) {
      if (
        content.toLowerCase().includes(term.toLowerCase()) &&
        !ALLOWED_REFERENCE_FILES.has(basename) &&
        !ALLOWED_L7_FILES.has(basename)
      ) {
        violations.push({ file: rel, type: 'premature-surface', value: term });
      }
    }

    for (const action of FORBIDDEN_ACTION_EXECUTION) {
      if (content.includes(action)) {
        violations.push({ file: rel, type: 'action-execution', value: action });
      }
    }

    if (FORBIDDEN_FETCH_IN_UI.includes(basename) && content.includes('fetch(')) {
      violations.push({ file: rel, type: 'fetch-in-governance-ui', value: 'fetch(' });
    }
  }

  return { filesScanned: files.length, violations };
}

export function assertLevel4RoutesExist(): { ok: boolean; missing: string[] } {
  const shellRoutes = readFileSync(join(ROOT, 'src', 'app', 'routes', 'ShellRoutes.tsx'), 'utf8');
  const app = readFileSync(join(ROOT, 'src', 'app', 'App.tsx'), 'utf8');
  const combined = shellRoutes + app;
  const missing = REQUIRED_L4_ROUTES.filter((token) => !combined.includes(token));
  return { ok: missing.length === 0, missing };
}

export function assertLevel4AgentAccessAbsent(): { ok: boolean; present: string[] } {
  const shellRoutes = readFileSync(join(ROOT, 'src', 'app', 'routes', 'ShellRoutes.tsx'), 'utf8');
  const app = readFileSync(join(ROOT, 'src', 'app', 'App.tsx'), 'utf8');
  const navigation = readFileSync(join(ROOT, 'src', 'shell', 'navigation.ts'), 'utf8');
  const aliases = readFileSync(join(ROOT, 'src', 'app', 'routes', 'GovernanceAliases.tsx'), 'utf8');
  const combined = [shellRoutes, app, navigation, aliases].join('\n');
  const present = FORBIDDEN_AGENT_ACCESS_TOKENS.filter((token) => combined.includes(token));
  return { ok: present.length === 0, present };
}

export function assertLevel4ComponentsExist(): { ok: boolean; missing: string[] } {
  const required = [
    'src/governance/governanceClient.ts',
    'src/components/governance/TeamSettingsPage/TeamSettingsPage.tsx',
    'src/components/governance/PolicySettingsPage/PolicySettingsPage.tsx',
    'src/components/governance/Level4RouteGuard/Level4RouteGuard.tsx',
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

export function runLevel4SabotageProbes(sourceSample: string) {
  const probes: Array<{ name: string; pattern: string; shouldDetect: boolean }> = [
    { name: 'audit-route', pattern: 'path="/audit"', shouldDetect: true },
    { name: 'claims-route', pattern: 'path="/claims"', shouldDetect: true },
    { name: 'health-strip', pattern: 'All systems operational', shouldDetect: true },
    { name: 'team-route-allowed', pattern: 'settings/team', shouldDetect: false },
    { name: 'agents-route-absent', pattern: 'path="agents"', shouldDetect: true },
    { name: 'agent-access-nav-absent', pattern: 'agent-access', shouldDetect: true },
    { name: 'fetch-in-modal-sabotage', pattern: 'fetch(', shouldDetect: true },
  ];
  return probes.map((probe) => ({
    name: probe.name,
    pass: sourceSample.includes(probe.pattern) === probe.shouldDetect,
    detected: sourceSample.includes(probe.pattern),
    expected: probe.shouldDetect,
  }));
}
