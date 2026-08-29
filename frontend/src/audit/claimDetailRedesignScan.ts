import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const ROOT = join(import.meta.dirname, '..', '..');

const CLAIM_DETAIL_FILES = [
  'src/components/claims/ClaimDetailPage/ClaimDetailPage.tsx',
  'src/components/claims/ClaimDetailPage/ClaimDetailHeader.tsx',
  'src/components/claims/ClaimDetailPage/ClaimDetailFinancialSummary.tsx',
  'src/components/claims/ClaimDetailPage/AttributionBreakdownPanel.tsx',
  'src/components/claims/ClaimDetailPage/ClaimDetailEventsPanel.tsx',
  'src/components/claims/ClaimDetailPage/ClaimDetailUnverifiedPanel.tsx',
  'src/components/claims/ClaimDetailPage/ClaimDetailPage.module.css',
  'src/components/claims/ClaimDetailPage/ClaimDetailHeader.module.css',
  'src/components/claims/ClaimDetailPage/ClaimDetailFinancialSummary.module.css',
];

function read(rel: string): string {
  return readFileSync(join(ROOT, rel), 'utf8');
}

export interface ClaimDetailRedesignViolation {
  file: string;
  rule: string;
  detail: string;
}

/**
 * CRHAID 1 static compliance scan — Claim Detail moved to Overview tile DNA.
 * Verifies the new surface composes the product-wide tile/card substrate and
 * does NOT reintroduce the legacy CFO-brief hero grammar or aesthetic DNA that
 * the redesign explicitly replaces.
 */
export function scanClaimDetailRedesign(
  sourceOverride?: Record<string, string>,
): ClaimDetailRedesignViolation[] {
  const violations: ClaimDetailRedesignViolation[] = [];
  const get = (rel: string) => sourceOverride?.[rel] ?? read(rel);
  const combined = CLAIM_DETAIL_FILES.map((f) => `[[${f}]]\n${get(f)}`).join('\n');

  // Positive control — Overview tile DNA is composed.
  if (!combined.includes('summaryTile.module.css')) {
    violations.push({
      file: 'ClaimDetailPage',
      rule: 'overview-tile-composition',
      detail: 'Claim Detail must compose summaryTile.module.css (Overview tile DNA)',
    });
  }
  if (!combined.includes('data-summary-tile-kind="financial_truth"')) {
    violations.push({
      file: 'ClaimDetailFinancialSummary',
      rule: 'financial-truth-tile-markers',
      detail: 'Financial summary tiles must expose data-summary-tile-kind="financial_truth"',
    });
  }
  if (!combined.includes('data-claim-detail-header') || !combined.includes('data-page-interface-header')) {
    violations.push({
      file: 'ClaimDetailHeader',
      rule: 'overview-header-grammar',
      detail: 'Claim Detail header must use reflowLayout page header grammar (data-claim-detail-header + data-page-interface-header)',
    });
  }
  if (!combined.includes('data-claim-aesthetic="overview-tile"')) {
    violations.push({
      file: 'ClaimDetailPage',
      rule: 'aesthetic-marker',
      detail: 'Loaded executive page must carry data-claim-aesthetic="overview-tile"',
    });
  }

  // Negative control — executive action panel removed from this surface.
  if (combined.includes('ClaimDetailActionPanel') || combined.includes('data-claim-action-panel')) {
    violations.push({
      file: 'ClaimDetailPage',
      rule: 'no-executive-action-panel',
      detail: 'ClaimDetailActionPanel / data-claim-action-panel must not remain on claim detail',
    });
  }

  // Negative control — legacy CFO-brief hero grammar removed.
  if (combined.includes('cfo-brief')) {
    violations.push({
      file: 'ClaimDetailPage',
      rule: 'legacy-cfo-brief-marker',
      detail: 'Legacy data-claim-aesthetic="cfo-brief" must be removed',
    });
  }
  if (/\.moneyStrip|\.moneyCell|\.moneyDivider|\.moneyArrow|\.moneyLabel|\.moneyValue|\.moneyHint|\.gapCell\b|\.gapValue|\.gapAmount|\.gapPercent|\.heroHeader|\.titleRow\b|\.titleBlock/.test(combined)) {
    violations.push({
      file: 'ClaimDetailPage',
      rule: 'legacy-hero-css-classes',
      detail: 'Legacy hero CSS classes (moneyStrip/moneyCell/moneyDivider/heroHeader/titleRow/titleBlock) must not remain',
    });
  }

  // Negative control — aesthetic DNA divergences from Overview (border-first, no decoration).
  if (/linear-gradient|radial-gradient/i.test(combined)) {
    violations.push({
      file: 'ClaimDetailPage',
      rule: 'D-no-gradient',
      detail: 'Gradient aesthetic detected — Overview DNA is flat/border-first',
    });
  }
  if (/glow|drop-shadow\(/i.test(combined)) {
    violations.push({
      file: 'ClaimDetailPage',
      rule: 'D-no-glow',
      detail: 'Glow / drop-shadow decoration detected — diverges from Overview DNA',
    });
  }
  if (/box-shadow:\s*[^;]*rgba\(/i.test(combined)) {
    violations.push({
      file: 'ClaimDetailPage',
      rule: 'D-no-hardcoded-rgba-shadow',
      detail: 'Hardcoded rgba box-shadow — Overview surfaces are border-first',
    });
  }
  if (/--sk-font-family-display/.test(combined) && !/ClaimsLedgerPageHeader/.test(combined)) {
    // 72 Display family is reserved for Command Center; Claim Detail uses Inter.
    violations.push({
      file: 'ClaimDetailPage',
      rule: 'D-no-display-font',
      detail: 'Claim Detail must use Inter (--sk-font-family-inter), not the 72 Display family',
    });
  }
  if (/border-left:\s*[^;]*solid/i.test(combined) && /3px|2px/.test(combined)) {
    violations.push({
      file: 'ClaimDetailPage',
      rule: 'D-no-side-border-accent',
      detail: 'Side-accent border cards diverge from Overview border-first tile DNA',
    });
  }

  return violations;
}

/** Sabotage fixture: reintroduces the legacy hero grammar + a forbidden aesthetic. */
export function claimDetailRedesignSabotageFixture(): Record<string, string> {
  const page = read('src/components/claims/ClaimDetailPage/ClaimDetailPage.tsx').replace(
    'data-claim-aesthetic="overview-tile"',
    'data-claim-aesthetic="cfo-brief"',
  );
  const summary = read('src/components/claims/ClaimDetailPage/ClaimDetailFinancialSummary.module.css')
    .replace(/\.hero \{[^}]*\}/s, '.hero { background: linear-gradient(90deg, #7c3aed, #4f46e5); }')
    .concat('\n.gapTile { border-left: 3px solid #7c3aed; }\n');
  return {
    'src/components/claims/ClaimDetailPage/ClaimDetailPage.tsx': page,
    'src/components/claims/ClaimDetailPage/ClaimDetailFinancialSummary.module.css': summary,
    'src/components/claims/ClaimDetailPage/ClaimDetailHeader.tsx': read(
      'src/components/claims/ClaimDetailPage/ClaimDetailHeader.tsx',
    ).replace('data-claim-detail-header', 'data-claim-detail-legacy-header'),
  };
}
