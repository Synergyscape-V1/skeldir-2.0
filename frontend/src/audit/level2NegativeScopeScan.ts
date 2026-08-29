import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const ROOT = join(import.meta.dirname, '..', '..');

const SCAN_DIRS = [
  join(ROOT, 'src', 'app'),
  join(ROOT, 'src', 'components', 'shell'),
  join(ROOT, 'src', 'shell'),
];

const BLOCKLIST_DEFINITION_FILES = new Set([
  'level2NegativeScopeScan.ts',
  'navigation.ts',
  'ShellFallbackPanel.tsx',
]);

const ALLOWED_NAV_LABEL_FILES = new Set(['navigation.ts', 'copy.ts', 'ShellFallbackPanel.tsx']);

const ALLOWED_L5_HEALTH_FILES = new Set([
  'copy.ts',
  'level5NegativeScopeScan.ts',
  'healthDomain.ts',
]);

const ALLOWED_L7_ALIAS_FILES = new Set(['App.tsx', 'LedgerAliases.tsx']);

const ALLOWED_L11_ALIAS_FILES = new Set([
  'App.tsx',
  'GovernanceAliases.tsx',
  'ShellRoutes.tsx',
  'GovernanceRoutes.tsx',
]);

const L7_PRODUCT_ROUTES = [
  'path="/claims"',
  'path="/trust/',
  'path="/channels"',
  'path="/benchmarks"',
  'path="/budget"',
  'path="/exceptions"',
];

const FORBIDDEN_PRODUCT_ROUTES = [
  'path="/settings/billing"',
  ...L7_PRODUCT_ROUTES,
];

const FORBIDDEN_HEALTH_TERMS = [
  'All systems operational',
  'Confidence degraded',
  'Trust API paused',
  'Integration attention needed',
  '/audit?filter=system_health',
  'system health strip',
  'status pill',
];

const FORBIDDEN_DASHBOARD_TERMS = [
  'trust state summary row',
  'priority queue',
  'verified revenue trend',
  'channel trust table',
  'recent TrustEnvelopes',
  'audit activity strip',
  'Overview dashboard',
  'Trust Command Center dashboard',
];

const FORBIDDEN_DOWNSTREAM_SURFACES = [
  'onboarding wizard',
  'commerce source connected',
  'export verified report',
  'signature verification',
  'agent key creation',
  'DLQ diagnostics',
];

function walk(dir: string, acc: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) walk(full, acc);
    else if (/\.(tsx|ts|css)$/.test(entry)) acc.push(full);
  }
  return acc;
}

export function runLevel2NegativeScopeScan() {
  const files = SCAN_DIRS.flatMap((dir) => walk(dir, []));
  const violations: Array<{ file: string; type: string; value: string }> = [];

  for (const file of files) {
    const rel = relative(ROOT, file);
    if (rel.includes('.test.')) continue;

    const basename = rel.split(/[/\\]/).pop() ?? rel;
    if (BLOCKLIST_DEFINITION_FILES.has(basename)) continue;

    const content = readFileSync(file, 'utf8');

    for (const route of FORBIDDEN_PRODUCT_ROUTES) {
      if (L7_PRODUCT_ROUTES.includes(route) && ALLOWED_L7_ALIAS_FILES.has(basename)) continue;
      if (route === 'path="/settings/billing"' && ALLOWED_L11_ALIAS_FILES.has(basename)) continue;
      if (content.includes(route)) {
        violations.push({ file: rel, type: 'level3-plus-product-route', value: route });
      }
    }

    for (const term of FORBIDDEN_HEALTH_TERMS) {
      if (content.includes(term) && !ALLOWED_L5_HEALTH_FILES.has(basename)) {
        violations.push({ file: rel, type: 'premature-health-semantics', value: term });
      }
    }

    for (const term of FORBIDDEN_DASHBOARD_TERMS) {
      if (content.toLowerCase().includes(term.toLowerCase())) {
        violations.push({ file: rel, type: 'premature-dashboard-semantics', value: term });
      }
    }

    for (const term of FORBIDDEN_DOWNSTREAM_SURFACES) {
      if (content.toLowerCase().includes(term.toLowerCase()) && !ALLOWED_NAV_LABEL_FILES.has(basename)) {
        violations.push({ file: rel, type: 'downstream-surface-implementation', value: term });
      }
    }

    if (rel.endsWith('.tsx') && content.includes('fetch(') && rel.includes('components/shell')) {
      violations.push({ file: rel, type: 'fetch-in-shell-component', value: 'fetch(' });
    }
  }

  return { filesScanned: files.length, violations };
}

export function assertLevel2RoutesExist(): { ok: boolean; missing: string[] } {
  const appFile = join(ROOT, 'src', 'app', 'App.tsx');
  const content = readFileSync(appFile, 'utf8');
  const required = ['/app/*', 'AppShellRoutes'];
  const missing = required.filter((token) => !content.includes(token));
  return { ok: missing.length === 0, missing };
}

export function assertLevel2ComponentsExist(): { ok: boolean; missing: string[] } {
  const requiredFiles = [
    'src/components/shell/AuthenticatedAppShell/AuthenticatedAppShell.tsx',
    'src/components/shell/SidebarNavigation/SidebarNavigation.tsx',
    'src/components/shell/SidebarAccount/SidebarAccount.tsx',
    'src/components/shell/ShellBrand/ShellBrand.tsx',
    'src/components/shell/TopHeader/TopHeader.tsx',
    'src/components/shell/MobileBottomNavigation/MobileBottomNavigation.tsx',
    'src/components/shell/MoreNavigationSheet/MoreNavigationSheet.tsx',
    'src/components/shell/ShellAccessGuard/ShellAccessGuard.tsx',
    'src/components/shell/ShellFallbackPanel/ShellFallbackPanel.tsx',
    'src/components/shell/RouteContainer/RouteContainer.tsx',
    'src/app/routes/ShellRoutes.tsx',
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

export function assertNoHealthStripInShellSource(): boolean {
  const scan = runLevel2NegativeScopeScan();
  return !scan.violations.some((v) => v.type === 'premature-health-semantics');
}

export function assertNoDashboardInShellSource(): boolean {
  const scan = runLevel2NegativeScopeScan();
  return !scan.violations.some((v) => v.type === 'premature-dashboard-semantics');
}

/** Sabotage probes — each must detect injected violation strings */
export function runLevel2SabotageProbes(sourceSample: string) {
  const probes: Array<{ name: string; pattern: RegExp | string; shouldDetect: boolean }> = [
    { name: 'health-strip', pattern: 'All systems operational', shouldDetect: true },
    { name: 'dashboard-trend', pattern: 'verified revenue trend', shouldDetect: true },
    { name: 'claims-route', pattern: 'path="/claims"', shouldDetect: true },
    { name: 'onboarding-route-allowed', pattern: 'path="/onboarding"', shouldDetect: false },
    { name: 'clean-shell', pattern: 'All systems operational', shouldDetect: false },
  ];

  return probes.map((probe) => {
    const detected =
      typeof probe.pattern === 'string'
        ? sourceSample.includes(probe.pattern)
        : probe.pattern.test(sourceSample);
    return {
      name: probe.name,
      pass: detected === probe.shouldDetect,
      detected,
      expected: probe.shouldDetect,
    };
  });
}
