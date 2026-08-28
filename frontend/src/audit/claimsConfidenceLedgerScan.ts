import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const ROOT = join(import.meta.dirname, '..', '..');

function read(rel: string): string {
  return readFileSync(join(ROOT, rel), 'utf8');
}

export interface ClaimsConfidenceLedgerViolation {
  file: string;
  rule: string;
  detail: string;
}

/**
 * B2.4 confidence column: reason-coded dispositions with interval labels, probabilistic
 * authority markers on available posteriors, and title tooltips — not a collapsed uniform
 * "Low confidence" Bayesian badge, and never success/deterministic green for available intervals.
 */
export function scanClaimsConfidenceLedger(sourceOverride?: {
  cellsTsx?: string;
  displayTs?: string;
  clientTs?: string;
  cellsCss?: string;
  copyTs?: string;
}): ClaimsConfidenceLedgerViolation[] {
  const violations: ClaimsConfidenceLedgerViolation[] = [];
  const cellsTsx =
    sourceOverride?.cellsTsx ??
    read('src/components/claims/ClaimsLedgerTable/ClaimsLedgerTableCells.tsx');
  const displayTs =
    sourceOverride?.displayTs ?? read('src/claims/confidenceLedgerDisplay.ts');
  const clientTs = sourceOverride?.clientTs ?? read('src/claims/claimsClient.ts');
  const cellsCss =
    sourceOverride?.cellsCss ??
    read('src/components/claims/ClaimsLedgerTable/ClaimsLedgerTableCells.module.css');
  const copyTs = sourceOverride?.copyTs ?? read('src/claims/copy.ts');

  if (/BayesianStatusBadge/.test(cellsTsx) && /ClaimsLedgerConfidenceCell/.test(cellsTsx)) {
    violations.push({
      file: 'ClaimsLedgerTableCells.tsx',
      rule: 'collapsed-bayesian-badge',
      detail: 'Confidence column must not collapse to uniform BayesianStatusBadge labels',
    });
  }

  if (!/data-claims-confidence-disposition/.test(cellsTsx)) {
    violations.push({
      file: 'ClaimsLedgerTableCells.tsx',
      rule: 'missing-disposition-attribute',
      detail: 'Confidence cell must expose data-claims-confidence-disposition for B2.4 triage',
    });
  }

  if (!/title=\{projection\.title\}/.test(cellsTsx)) {
    violations.push({
      file: 'ClaimsLedgerTableCells.tsx',
      rule: 'missing-confidence-title',
      detail: 'Confidence cell must expose full B2.4 explanation in title tooltip',
    });
  }

  if (/DataUnavailablePanel/.test(cellsTsx)) {
    violations.push({
      file: 'ClaimsLedgerTableCells.tsx',
      rule: 'full-unavailable-panel-in-column',
      detail: 'Table confidence column must not mount DataUnavailablePanel',
    });
  }

  if (!/AuthorityBadge/.test(cellsTsx) || !/authority="probabilistic"/.test(cellsTsx)) {
    violations.push({
      file: 'ClaimsLedgerTableCells.tsx',
      rule: 'missing-inline-probabilistic-authority',
      detail:
        'Available confidence intervals must render an inline AuthorityBadge authority="probabilistic"',
    });
  }

  if (!/data-claims-confidence-authority="probabilistic"/.test(cellsTsx)) {
    violations.push({
      file: 'ClaimsLedgerTableCells.tsx',
      rule: 'missing-confidence-authority-attribute',
      detail: 'Available confidence cells must expose data-claims-confidence-authority="probabilistic"',
    });
  }

  if (!/case 'cold_start'/.test(displayTs)) {
    violations.push({
      file: 'confidenceLedgerDisplay.ts',
      rule: 'missing-cold-start-disposition',
      detail: 'Resolver must distinguish cold_start from other unavailable causes',
    });
  }

  if (!displayTs.includes('worker_failure')) {
    violations.push({
      file: 'confidenceLedgerDisplay.ts',
      rule: 'missing-worker-failure-disposition',
      detail: 'Resolver must distinguish worker_failure from cold start',
    });
  }

  if (!displayTs.includes('refit_locked')) {
    violations.push({
      file: 'confidenceLedgerDisplay.ts',
      rule: 'missing-refit-locked-disposition',
      detail: 'Resolver must expose refit_locked state',
    });
  }

  if (!displayTs.includes('available_wide')) {
    violations.push({
      file: 'confidenceLedgerDisplay.ts',
      rule: 'missing-wide-posterior-disposition',
      detail: 'Resolver must expose wide posterior / model disagreement separately from unavailable',
    });
  }

  // Available posteriors must use the probabilistic register — never success/deterministic green.
  const toneFn = displayTs.match(/function colorToneForDisposition[\s\S]*?\n\}/)?.[0] ?? '';
  if (/case 'available_exact':[\s\S]*?return 'success'/.test(toneFn)) {
    violations.push({
      file: 'confidenceLedgerDisplay.ts',
      rule: 'available-interval-success-tone',
      detail:
        'available_exact/available_stable must use probabilistic tone — never success/deterministic green',
    });
  }

  if (
    !/case 'available_exact':\s*\n\s*case 'available_stable':\s*\n\s*case 'available_wide':\s*\n\s*return 'probabilistic'/.test(
      toneFn,
    )
  ) {
    violations.push({
      file: 'confidenceLedgerDisplay.ts',
      rule: 'available-interval-not-probabilistic-tone',
      detail: 'All available interval dispositions must resolve to probabilistic color tone',
    });
  }

  if (!/buildClaimConfidence/.test(clientTs) || /qualitativeState: 'Moderate uncertainty'/.test(clientTs)) {
    violations.push({
      file: 'claimsClient.ts',
      rule: 'uniform-synthetic-confidence',
      detail: 'Synthetic fixture must vary B2.4 confidence states across rows',
    });
  }

  if (!/data-claims-confidence-color-tone/.test(cellsTsx)) {
    violations.push({
      file: 'ClaimsLedgerTableCells.tsx',
      rule: 'missing-color-tone-attribute',
      detail: 'Confidence cell must expose data-claims-confidence-color-tone for color-coded triage',
    });
  }

  if (/composes: chip/.test(cellsTsx)) {
    violations.push({
      file: 'ClaimsLedgerTableCells.tsx',
      rule: 'confidence-badge-chrome',
      detail: 'Confidence column must compose AuthorityBadge TrustChip — not raw chip CSS',
    });
  }

  const confidenceCellFn =
    cellsTsx.match(/export function ClaimsLedgerConfidenceCell[\s\S]*?(?=^export function)/m)?.[0] ??
    cellsTsx.match(/export function ClaimsLedgerConfidenceCell[\s\S]*/)?.[0] ??
    '';

  if (/appearance="text"/.test(confidenceCellFn)) {
    violations.push({
      file: 'ClaimsLedgerTableCells.tsx',
      rule: 'confidence-authority-text-not-chip',
      detail:
        'Available confidence AuthorityBadge must use table TrustChip badge chrome (same substrate as ExecutiveReliabilityBadge) — not appearance="text"',
    });
  }

  if (
    !/AuthorityBadge authority="probabilistic" \{\.\.\.PRODUCT_TABLE_CHIP_PROPS\}/.test(confidenceCellFn) &&
    !/authority="probabilistic"[\s\S]{0,80}PRODUCT_TABLE_CHIP_PROPS/.test(confidenceCellFn)
  ) {
    violations.push({
      file: 'ClaimsLedgerTableCells.tsx',
      rule: 'missing-probabilistic-trust-chip',
      detail: 'Available confidence rows must mount AuthorityBadge with PRODUCT_TABLE_CHIP_PROPS (TrustChip)',
    });
  }

  if (/Exact ·|Wide ·|availableExactShort|availableWideShort/.test(copyTs)) {
    violations.push({
      file: 'copy.ts',
      rule: 'forbidden-confidence-prefix-labels',
      detail: 'Visible confidence labels must not prefix intervals with Exact or Wide — color carries disposition',
    });
  }

  if (!/confidenceTextSuccess/.test(cellsCss) || !/confidenceTextError/.test(cellsCss)) {
    violations.push({
      file: 'ClaimsLedgerTableCells.module.css',
      rule: 'missing-confidence-text-tones',
      detail: 'Confidence cell must define text-only success and error tone classes',
    });
  }

  if (!/confidenceCell/.test(cellsCss)) {
    violations.push({
      file: 'ClaimsLedgerTableCells.module.css',
      rule: 'missing-confidence-cell-layout',
      detail: 'Confidence cell must define stacked layout for interval + authority marker',
    });
  }

  return violations;
}

export function claimsConfidenceLedgerSabotageFixture(): {
  cellsTsx: string;
  displayTs: string;
  clientTs: string;
  cellsCss?: string;
  copyTs?: string;
} {
  const liveCells = read('src/components/claims/ClaimsLedgerTable/ClaimsLedgerTableCells.tsx');
  const liveDisplay = read('src/claims/confidenceLedgerDisplay.ts');
  const liveClient = read('src/claims/claimsClient.ts');

  return {
    cellsTsx: liveCells
      .replace(
        /export function ClaimsLedgerConfidenceCell[\s\S]*?^}/m,
        `export function ClaimsLedgerConfidenceCell({ confidence }: { confidence: ConfidenceShape }) {
  return (
    <BayesianStatusBadge
      status={confidenceToBayesianStatus(confidence)}
      {...SUPERVISORY_TABLE_STATUS_TEXT}
    />
  );
}`,
      )
      .replace(/title=\{projection\.title\}/, 'title={undefined}'),
    displayTs: liveDisplay
      .replace(/case 'cold_start'/g, "case 'removed'")
      .replace(
        /case 'available_exact':\s*\n\s*case 'available_stable':\s*\n\s*case 'available_wide':\s*\n\s*return 'probabilistic';/,
        `case 'available_exact':
    case 'available_stable':
      return 'success';
    case 'available_wide':
      return 'probabilistic';`,
      ),
    clientTs: liveClient.replace(
      /function buildClaimConfidence[\s\S]*?^}/m,
      `function buildClaimConfidence(): ConfidenceShape {
  return {
    status: 'available',
    intervalLower: 0.82,
    intervalUpper: 0.94,
    qualitativeState: 'Moderate uncertainty',
  };
}`,
    ),
    cellsCss: read('src/components/claims/ClaimsLedgerTable/ClaimsLedgerTableCells.module.css').replace(
      /confidenceTextSuccess[\s\S]*$/,
      '',
    ),
    copyTs: read('src/claims/copy.ts').replace(
      'availableIntervalShort: (interval: string) => interval,',
      "availableIntervalShort: (interval: string) => `Wide · ${interval}`,",
    ),
  };
}
