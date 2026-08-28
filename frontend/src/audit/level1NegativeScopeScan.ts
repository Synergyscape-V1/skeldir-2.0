import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const ROOT = join(import.meta.dirname, '..', '..');

const SCAN_DIRS = [
  join(ROOT, 'src', 'app'),
  join(ROOT, 'src', 'auth'),
  join(ROOT, 'src', 'components', 'auth'),
  join(ROOT, 'src', 'components', 'form'),
];

const BLOCKLIST_DEFINITION_FILES = new Set(['redirectGuard.ts', 'level1NegativeScopeScan.ts']);

const ALLOWED_GOVERNANCE_ALIAS_FILES = new Set(['App.tsx', 'GovernanceAliases.tsx']);
const ALLOWED_L5_ALIAS_FILES = new Set(['App.tsx', 'OperationalAuditAliases.tsx']);
const ALLOWED_L7_ALIAS_FILES = new Set(['App.tsx', 'LedgerAliases.tsx']);
const ALLOWED_L11_ALIAS_FILES = new Set(['App.tsx', 'GovernanceAliases.tsx']);

const L7_ROUTE_PATHS = [
  '/claims',
  '/trust/',
  '/channels',
  '/benchmarks',
  '/budget',
  '/exceptions',
];

const FORBIDDEN_ROUTE_PATHS = [
  ...L7_ROUTE_PATHS,
  '/settings/billing',
];

/** L4 routes allowed only in governance alias files — not in Level 1 auth surfaces */
const L4_ROUTE_PATHS = ['/settings/policy', '/settings/team'];

const FORBIDDEN_SURFACE_TERMS = [
  'Command Center',
  'Trust Command Center',
  'tenant selector',
  'system health strip',
];

const FORBIDDEN_FETCH_IN = ['LoginForm.tsx', 'SignUpForm.tsx'];

function walk(dir: string, acc: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) walk(full, acc);
    else if (/\.(tsx|ts)$/.test(entry)) acc.push(full);
  }
  return acc;
}

export function runLevel1NegativeScopeScan() {
  const files = SCAN_DIRS.flatMap((dir) => walk(dir, []));
  const violations: Array<{ file: string; type: string; value: string }> = [];

  for (const file of files) {
    const rel = relative(ROOT, file);
    if (rel.includes('.test.')) continue;

    const basename = rel.split(/[/\\]/).pop() ?? rel;
    if (BLOCKLIST_DEFINITION_FILES.has(basename)) continue;

    const content = readFileSync(file, 'utf8');

    for (const route of FORBIDDEN_ROUTE_PATHS) {
      if (L7_ROUTE_PATHS.includes(route) && ALLOWED_L7_ALIAS_FILES.has(basename)) continue;
      if (route === '/settings/billing' && ALLOWED_L11_ALIAS_FILES.has(basename)) continue;
      const pattern = new RegExp(`['\`"]${route.replace('/', '\\/')}`);
      if (pattern.test(content)) {
        violations.push({ file: rel, type: 'level2-plus-route', value: route });
      }
    }

    if (
      !ALLOWED_GOVERNANCE_ALIAS_FILES.has(basename) &&
      !ALLOWED_L5_ALIAS_FILES.has(basename) &&
      !ALLOWED_L7_ALIAS_FILES.has(basename)
    ) {
      for (const route of L4_ROUTE_PATHS) {
        const pattern = new RegExp(`['\`"]${route.replace('/', '\\/')}`);
        if (pattern.test(content)) {
          violations.push({ file: rel, type: 'level4-route-in-level1', value: route });
        }
      }
    }

    for (const term of FORBIDDEN_SURFACE_TERMS) {
      if (content.includes(term)) {
        violations.push({ file: rel, type: 'level2-plus-surface', value: term });
      }
    }

    for (const fragment of FORBIDDEN_FETCH_IN) {
      if (rel.endsWith(fragment) && content.includes('fetch(')) {
        violations.push({ file: rel, type: 'fetch-in-form-component', value: 'fetch(' });
      }
    }
  }

  return { filesScanned: files.length, violations };
}

export function assertLevel1RoutesExist(): { ok: boolean; missing: string[] } {
  const appFile = join(ROOT, 'src', 'app', 'App.tsx');
  const content = readFileSync(appFile, 'utf8');
  const required = ['/login', '/signup', '/auth', 'LoginPage', 'SignupPage', 'AuthInvitePage'];
  const missing = required.filter((token) => !content.includes(token));
  return { ok: missing.length === 0, missing };
}

export function assertLevel1ComponentsExist(): { ok: boolean; missing: string[] } {
  const requiredFiles = [
    'src/components/auth/LoginForm/LoginForm.tsx',
    'src/components/auth/SignUpForm/SignUpForm.tsx',
    'src/components/auth/BusinessEmailInput/BusinessEmailInput.tsx',
    'src/auth/authClient.ts',
    'src/auth/redirectGuard.ts',
    'src/components/auth/SessionBootstrapBoundary/SessionBootstrapBoundary.tsx',
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
