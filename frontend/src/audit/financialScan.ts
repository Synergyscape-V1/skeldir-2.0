import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const ROOT = join(import.meta.dirname, '..', '..');
const SCAN_DIRS = [join(ROOT, 'src', 'components'), join(ROOT, 'src', 'dev')];

const FORBIDDEN_PATTERNS: Array<{ pattern: RegExp; type: string }> = [
  { pattern: /\bparseFloat\s*\(/, type: 'parseFloat' },
  { pattern: /\bNumber\s*\(/, type: 'Number()' },
  { pattern: /\.toFixed\s*\(/, type: 'toFixed' },
  { pattern: /\bMath\.(round|floor|ceil)\s*\(/, type: 'Math rounding' },
  { pattern: /\bIntl\.NumberFormat\s*\(/, type: 'Intl.NumberFormat' },
];

const ALLOWED_FILES = [
  'src/lib/money.ts',
  'src/components/financial/FinancialValue/FinancialValue.tsx',
  'src/components/financial/ClaimComparisonCard/ClaimComparisonCard.tsx',
  'src/components/commandCenter/VerifiedRevenueChart/verifiedRevenueChartGeometry.ts',
];

function walk(dir: string, acc: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) walk(full, acc);
    else if (/\.(tsx|ts)$/.test(entry) && !entry.endsWith('.test.ts') && !entry.endsWith('.test.tsx'))
      acc.push(full);
  }
  return acc;
}

export function runFinancialScan() {
  const files = SCAN_DIRS.flatMap((d) => walk(d, []));
  const violations: Array<{ file: string; type: string; match: string }> = [];

  for (const file of files) {
    const rel = relative(ROOT, file).replace(/\\/g, '/');
    const allowed = ALLOWED_FILES;
    if (allowed.some((a) => rel === a || rel.endsWith(a))) continue;

    const content = readFileSync(file, 'utf8');
    for (const { pattern, type } of FORBIDDEN_PATTERNS) {
      const match = content.match(pattern);
      if (match) {
        violations.push({ file: rel, type, match: match[0] });
      }
    }
  }

  return { filesScanned: files.length, violations };
}
