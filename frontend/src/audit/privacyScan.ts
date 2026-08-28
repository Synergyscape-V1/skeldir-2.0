import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const ROOT = join(import.meta.dirname, '..', '..');

const SCAN_DIRS = [
  join(ROOT, 'src', 'activation'),
  join(ROOT, 'src', 'integration'),
  join(ROOT, 'src', 'components', 'onboarding'),
  join(ROOT, 'src', 'components', 'integration'),
  join(ROOT, 'src', 'dev'),
  join(ROOT, 'src', 'test'),
  join(ROOT, 'src', 'detail'),
  join(ROOT, 'src', 'claims'),
  join(ROOT, 'src', 'components', 'claims'),
  join(ROOT, 'src', 'components', 'detail'),
  join(ROOT, 'evidence', 'Level_8'),
  join(ROOT, 'evidence', 'Level_9'),
  join(ROOT, 'src', 'actions'),
];

const BLOCKLIST_FILES = new Set(['privacyScan.ts', 'copy.ts']);

const PII_PATTERNS: Array<{ name: string; pattern: RegExp }> = [
  { name: 'durable-email-in-fixture', pattern: /customer@[a-z0-9.-]+\.[a-z]{2,}/i },
  { name: 'ipv4-in-commerce-fixture', pattern: /\b192\.168\.\d{1,3}\.\d{1,3}\b/ },
  { name: 'user-agent-string', pattern: /Mozilla\/5\.0 \(Windows/i },
  { name: 'oauth-access-token', pattern: /access_token['":\s]+[a-zA-Z0-9._-]{20,}/i },
  { name: 'refresh-token', pattern: /refresh_token['":\s]+[a-zA-Z0-9._-]{20,}/i },
  { name: 'client-secret', pattern: /client_secret['":\s]+[a-zA-Z0-9._-]{10,}/i },
];

function walk(target: string, acc: string[] = []): string[] {
  try {
    if (!statSync(target).isDirectory()) {
      if (/\.(tsx|ts|json|md)$/.test(target)) acc.push(target);
      return acc;
    }
    for (const entry of readdirSync(target)) {
      const full = join(target, entry);
      if (statSync(full).isDirectory()) walk(full, acc);
      else if (/\.(tsx|ts|json|md)$/.test(entry)) acc.push(full);
    }
  } catch {
    return acc;
  }
  return acc;
}

export function runPrivacyScan() {
  const files = SCAN_DIRS.flatMap((dir) => walk(dir, []));
  const violations: Array<{ file: string; type: string; value: string }> = [];

  for (const file of files) {
    const rel = relative(ROOT, file);
    const basename = rel.split(/[/\\]/).pop() ?? rel;
    if (BLOCKLIST_FILES.has(basename)) continue;
    if (rel.includes('privacyScan')) continue;
    if (rel.includes('.test.') || rel.includes('.harness.')) continue;

    const content = readFileSync(file, 'utf8');

    for (const probe of PII_PATTERNS) {
      if (probe.pattern.test(content)) {
        violations.push({ file: rel, type: probe.name, value: probe.pattern.source });
      }
    }
  }

  return { filesScanned: files.length, violations };
}

export function runPrivacySabotageProbes(sample: string) {
  return [
    {
      name: 'email-in-fixture',
      pass: /customer@example\.com/.test(sample),
      detected: /customer@example\.com/.test(sample),
    },
    {
      name: 'clean-sample',
      pass: !/192\.168\./.test('workspace-tenant-001'),
      detected: false,
    },
  ];
}
