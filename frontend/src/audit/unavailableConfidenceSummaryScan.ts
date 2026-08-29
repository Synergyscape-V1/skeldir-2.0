import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const ROOT = join(import.meta.dirname, '..', '..');

function read(rel: string): string {
  return readFileSync(join(ROOT, rel), 'utf8');
}

export interface UnavailableConfidenceSummaryViolation {
  file: string;
  rule: string;
  detail: string;
}

/**
 * Static integrity: Unavailable confidence tile must explain cause class and isolate via filter CTA.
 */
export function scanUnavailableConfidenceSummary(sourceOverride?: {
  summaryRowTsx?: string;
  summaryTs?: string;
  copyTs?: string;
}): UnavailableConfidenceSummaryViolation[] {
  const violations: UnavailableConfidenceSummaryViolation[] = [];
  const summaryRowTsx =
    sourceOverride?.summaryRowTsx ??
    read('src/components/trustIndex/TrustEnvelopeIndexSummaryRow/TrustEnvelopeIndexSummaryRow.tsx');
  const summaryTs = sourceOverride?.summaryTs ?? read('src/trustIndex/trustIndexSummary.ts');
  const copyTs = sourceOverride?.copyTs ?? read('src/trustIndex/copy.ts');

  if (/benchmark\.status\s*===\s*['"]unavailable['"]/.test(summaryTs) && /unavailableConfidence/.test(summaryTs)) {
    violations.push({
      file: 'src/trustIndex/trustIndexSummary.ts',
      rule: 'confidence-count-ors-benchmark',
      detail: 'Unavailable confidence count must not OR in benchmark-only unavailable rows',
    });
  }

  if (!summaryTs.includes('unavailableConfidenceCauses')) {
    violations.push({
      file: 'src/trustIndex/trustIndexSummary.ts',
      rule: 'missing-cause-breakdown',
      detail: 'Summary must expose unavailableConfidenceCauses for supervisor framing',
    });
  }

  if (!summaryRowTsx.includes('data-unavailable-confidence-meta')) {
    violations.push({
      file: 'TrustEnvelopeIndexSummaryRow.tsx',
      rule: 'missing-cause-meta',
      detail: 'Tile must render cause-class explanation meta',
    });
  }

  if (!summaryRowTsx.includes('data-summary-drilldown="unavailable_confidence"')) {
    violations.push({
      file: 'TrustEnvelopeIndexSummaryRow.tsx',
      rule: 'missing-isolate-cta',
      detail: 'Tile must expose isolate/clear drill-down CTA when count > 0',
    });
  }

  if (!summaryRowTsx.includes('buildUnavailableConfidenceIsolateHref')) {
    violations.push({
      file: 'TrustEnvelopeIndexSummaryRow.tsx',
      rule: 'missing-isolate-href-builder',
      detail: 'CTA must target confidenceAvailability=unavailable via query builder',
    });
  }

  if (!copyTs.includes('viewUnavailableConfidence') || !copyTs.includes('unavailableConfidenceColdStartMeta')) {
    violations.push({
      file: 'src/trustIndex/copy.ts',
      rule: 'missing-supervisor-copy',
      detail: 'Copy must include isolate CTA and cold-start vs intervention meta',
    });
  }

  if (/Deterministic verification remains active\./.test(copyTs) && /unavailableConfidenceMixedMeta[\s\S]{0,200}Deterministic/.test(copyTs)) {
    violations.push({
      file: 'src/trustIndex/copy.ts',
      rule: 'meta-copy-too-dense',
      detail: 'Visible meta must stay single-line; deterministic boundary belongs in title, not meta body',
    });
  }

  if (summaryRowTsx.includes('unavailableConfidenceBenchmarkCount')) {
    violations.push({
      file: 'TrustEnvelopeIndexSummaryRow.tsx',
      rule: 'legacy-benchmark-or-field',
      detail: 'Legacy unavailableConfidenceBenchmarkCount must not remain on the tile',
    });
  }

  return violations;
}

export function unavailableConfidenceSummarySabotageFixture(): {
  summaryRowTsx: string;
  summaryTs: string;
  copyTs: string;
} {
  return {
    summaryRowTsx: `
      <span className={styles.value}>{summary.unavailableConfidenceBenchmarkCount}</span>
    `,
    summaryTs: `
      if (row.confidence.status === 'unavailable' || row.benchmark.status === 'unavailable') {
        unavailableConfidenceCount += 1;
      }
    `,
    copyTs: `summary: { unavailableConfidence: 'Unavailable confidence' },`,
  };
}
