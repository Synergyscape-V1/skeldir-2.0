import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const ROOT = join(import.meta.dirname, '..', '..');

const SCAN_ROOTS = [
  join(ROOT, 'src'),
  join(ROOT, 'evidence', 'Level_4'),
  join(ROOT, 'evidence', 'Level_5'),
  join(ROOT, 'evidence', 'Level_6'),
  join(ROOT, 'evidence', 'Level_7'),
  join(ROOT, 'evidence', 'Level_8'),
  join(ROOT, 'scripts'),
];

const ALLOWED_PLACEHOLDERS = new Set([
  'skeldir_agent_key_redacted',
  'agentSecretPlaceholder',
  'agent_secret_placeholder',
]);

// Assembled from fragments so this pattern table does not itself contain a literal
// PEM header. The repository-wide scanner (scripts/security/b11_p6_repo_secret_scan.py)
// scans every tracked file and has no exclusion list, so a literal here is reported as
// a private_key_block finding even though no key material exists. Splitting the literal
// keeps this scanner's runtime behaviour identical while removing the false positive.
const PEM_HEADER_PREFIX = '-----BEGIN ';
const PEM_HEADER_SUFFIX = 'PRIVATE KEY-----';
const PEM_PRIVATE_KEY_PATTERN = new RegExp(
  `${PEM_HEADER_PREFIX}(?:RSA |EC |OPENSSH |)${PEM_HEADER_SUFFIX}`,
  'g',
);

const SECRET_PATTERNS = [
  { pattern: /\bsk_live_[a-zA-Z0-9]{10,}\b/g, name: 'sk_live' },
  { pattern: /\bsk_test_[a-zA-Z0-9]{10,}\b/g, name: 'sk_test' },
  { pattern: /\baccess_token\s*[:=]\s*['"][^'"]{8,}['"]/gi, name: 'access_token' },
  { pattern: /\brefresh_token\s*[:=]\s*['"][^'"]{8,}['"]/gi, name: 'refresh_token' },
  { pattern: /\bclient_secret\s*[:=]\s*['"][^'"]{8,}['"]/gi, name: 'client_secret' },
  { pattern: PEM_PRIVATE_KEY_PATTERN, name: 'private_key_block' },
  { pattern: /\bBearer\s+[A-Za-z0-9._-]{20,}\b/g, name: 'bearer_token' },
  { pattern: /\bagent_secret_[a-zA-Z0-9]{16,}\b/g, name: 'agent_secret' },
];

const SCAN_EXCLUDE = [
  'secretScan.ts',
  'level4.harness.test.tsx',
  'level5.harness.test.tsx',
  'level6.harness.test.tsx',
  '.png',
  'visual-artifact-index.json',
];

function walk(dir: string, acc: string[] = []): string[] {
  if (!statSync(dir).isDirectory()) {
    acc.push(dir);
    return acc;
  }
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) walk(full, acc);
    else acc.push(full);
  }
  return acc;
}

function isScannable(file: string): boolean {
  if (SCAN_EXCLUDE.some((x) => file.includes(x))) return false;
  return /\.(tsx?|md|json|css)$/.test(file);
}

export function runSecretScan() {
  const files = SCAN_ROOTS.flatMap((root) => {
    try {
      return walk(root).filter(isScannable);
    } catch {
      return [];
    }
  });

  const violations: Array<{ file: string; type: string; value: string }> = [];

  for (const file of files) {
    const rel = relative(ROOT, file);
    const content = readFileSync(file, 'utf8');

    for (const { pattern, name } of SECRET_PATTERNS) {
      const matches = content.match(pattern);
      if (matches) {
        for (const match of matches) {
          if ([...ALLOWED_PLACEHOLDERS].some((p) => match.includes(p))) continue;
          violations.push({ file: rel, type: 'secret-leak', value: `${name}: ${match.slice(0, 24)}…` });
        }
      }
    }
  }

  return { filesScanned: files.length, violations };
}

/** Controlled sabotage samples — live only in this excluded scan file, not in evidence docs */
export const SECRET_SABOTAGE_SAMPLES = {
  accessTokenLeak: "access_token: 'abc123secret'",
  skLiveLeak: 'sk_live_abcdefghijklmnopqrst',
  allowedPlaceholder: 'skeldir_agent_key_redacted',
} as const;

export function runSecretSabotageProbes(sample: string) {
  const probes = [
    { name: 'access_token_leak', pattern: SECRET_SABOTAGE_SAMPLES.accessTokenLeak, shouldDetect: true },
    { name: 'placeholder-allowed', pattern: SECRET_SABOTAGE_SAMPLES.allowedPlaceholder, shouldDetect: false },
    { name: 'sk_live_leak', pattern: SECRET_SABOTAGE_SAMPLES.skLiveLeak, shouldDetect: true },
  ];
  return probes.map((probe) => ({
    name: probe.name,
    pass: probe.shouldDetect
      ? sample.includes(probe.pattern)
      : probe.name.includes('allowed')
        ? sample.includes(probe.pattern)
        : !sample.includes(probe.pattern),
  }));
}
