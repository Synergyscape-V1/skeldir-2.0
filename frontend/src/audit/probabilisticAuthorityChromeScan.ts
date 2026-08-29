import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const ROOT = join(import.meta.dirname, '..', '..');
const SRC = join(ROOT, 'src');

export interface ProbabilisticAuthorityChromeViolation {
  file: string;
  rule: string;
  detail: string;
}

function walkTsxFiles(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    const st = statSync(full);
    if (st.isDirectory()) {
      if (entry === 'node_modules' || entry === 'dist' || entry === 'test') continue;
      walkTsxFiles(full, out);
      continue;
    }
    if (/\.(tsx|ts)$/.test(entry) && !entry.endsWith('.test.tsx') && !entry.endsWith('.test.ts')) {
      out.push(full);
    }
  }
  return out;
}

/**
 * System-wide: the authority class label "Probabilistic" must never render as densified
 * text — only TrustChip badge chrome via AuthorityBadge (or equivalent data-trust-chip).
 */
export function scanProbabilisticAuthorityChrome(sourceOverride?: {
  files?: Array<{ path: string; content: string }>;
}): ProbabilisticAuthorityChromeViolation[] {
  const violations: ProbabilisticAuthorityChromeViolation[] = [];

  const files =
    sourceOverride?.files ??
    walkTsxFiles(SRC).map((full) => ({
      path: relative(ROOT, full).replace(/\\/g, '/'),
      content: readFileSync(full, 'utf8'),
    }));

  const badgeSource =
    files.find((f) => f.path.endsWith('components/trust/AuthorityBadge/AuthorityBadge.tsx'))
      ?.content ?? readFileSync(join(SRC, 'components/trust/AuthorityBadge/AuthorityBadge.tsx'), 'utf8');

  if (
    !/if \(resolved === 'probabilistic'\)/.test(badgeSource) ||
    !/trustChipClassNames\('probabilistic'\)/.test(badgeSource)
  ) {
    violations.push({
      file: 'AuthorityBadge.tsx',
      rule: 'missing-probabilistic-chip-force',
      detail:
        'AuthorityBadge must early-return TrustChip chrome for authority === probabilistic (no text/size escape)',
    });
  }

  if (!/data-authority-class=\{resolved\}/.test(badgeSource) && !/data-authority-class/.test(badgeSource)) {
    violations.push({
      file: 'AuthorityBadge.tsx',
      rule: 'missing-authority-class-attr',
      detail: 'Table TrustChip AuthorityBadge must expose data-authority-class for forensic scans',
    });
  }

  for (const file of files) {
    if (file.path.includes('AuthorityBadge/AuthorityBadge.tsx')) continue;
    if (file.path.includes('audit/')) continue;

    // Call-site: AuthorityBadge probabilistic must not request appearance="text"
    const probabilisticTextCall =
      /<AuthorityBadge\b[^>]*authority=["']probabilistic["'][^>]*appearance=["']text["'][^>]*\/?>/.test(
        file.content,
      ) ||
      /<AuthorityBadge\b[^>]*appearance=["']text["'][^>]*authority=["']probabilistic["'][^>]*\/?>/.test(
        file.content,
      ) ||
      /authority=["']probabilistic["'][\s\S]{0,120}appearance=["']text["']/.test(file.content);

    if (probabilisticTextCall) {
      violations.push({
        file: file.path,
        rule: 'probabilistic-authority-text-appearance',
        detail:
          'Do not pass appearance="text" for AuthorityBadge authority="probabilistic" — TrustChip is mandatory',
      });
    }
  }

  return violations;
}

export function probabilisticAuthorityChromeSabotageFixture(): {
  files: Array<{ path: string; content: string }>;
} {
  const badgePath = 'src/components/trust/AuthorityBadge/AuthorityBadge.tsx';
  const indexPath =
    'src/components/trustIndex/TrustEnvelopeIndexTable/TrustEnvelopeIndexTableCells.tsx';
  const liveBadge = readFileSync(join(ROOT, badgePath), 'utf8');
  const liveIndex = readFileSync(join(ROOT, indexPath), 'utf8');

  return {
    files: [
      {
        path: badgePath,
        content: liveBadge
          .replace(
            /\/\/ Canonical chrome:[\s\S]*?if \(resolved === 'probabilistic'\) \{[\s\S]*?\n  \}\n\n/,
            '',
          )
          .replace(/\s*data-authority-class=\{resolved\}\n/, '\n'),
      },
      {
        path: indexPath,
        content: liveIndex.replace(
          /<AuthorityBadge authority="probabilistic" \{\.\.\.TRUST_INDEX_AUTHORITY_CHIP\} \/>/,
          '<AuthorityBadge authority="probabilistic" {...TRUST_INDEX_AUTHORITY_CHIP} appearance="text" />',
        ),
      },
    ],
  };
}
