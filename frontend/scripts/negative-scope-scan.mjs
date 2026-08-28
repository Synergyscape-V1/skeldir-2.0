#!/usr/bin/env node
/**
 * Negative scope scan — ensures no excluded product routes or API calls in Level 0.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const ROOT = join(import.meta.dirname, '..');
const SRC = join(ROOT, 'src');

const FORBIDDEN_ROUTES = [
  '/login',
  '/signup',
  '/onboarding',
  '/app',
  '/claims',
  '/trust/',
  '/channels',
  '/benchmarks',
  '/budget',
  '/exceptions',
  '/audit',
  '/agents',
  '/integrations',
  '/settings/policy',
  '/settings/team',
  '/settings/billing',
  'Command Center',
  'LoginForm',
  'SignUpForm',
  'GitHubOAuth',
];

const FORBIDDEN_API = [
  'fetch(',
  'axios',
  'Trust API',
  '/api/trust',
  '/api/auth',
  'useQuery',
  'useSWR',
];

function walk(dir, acc = []) {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) walk(full, acc);
    else if (/\.(tsx|ts)$/.test(entry)) acc.push(full);
  }
  return acc;
}

export function runNegativeScopeScan() {
  const files = walk(SRC, []);
  const violations = [];

  for (const file of files) {
    const rel = relative(ROOT, file);
    const content = readFileSync(file, 'utf8');

    for (const term of FORBIDDEN_ROUTES) {
      if (content.includes(term) && !rel.includes('level0.harness.test')) {
        // Allow mentions in comments only — check if in string literal for routes
        if (new RegExp(`['\`"]${term.replace('/', '\\/')}`).test(content)) {
          violations.push({ file: rel, type: 'forbidden-route', value: term });
        }
      }
    }

    for (const api of FORBIDDEN_API) {
      if (content.includes(api) && !rel.endsWith('.test.tsx') && !rel.includes('copy.ts')) {
        violations.push({ file: rel, type: 'forbidden-api', value: api });
      }
    }
  }

  return { filesScanned: files.length, violations };
}

if (process.argv[1]?.includes('negative-scope-scan')) {
  const result = runNegativeScopeScan();
  console.log(JSON.stringify(result, null, 2));
  process.exit(result.violations.length ? 1 : 0);
}
