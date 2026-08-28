import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const ROOT = join(import.meta.dirname, '..', '..');

function read(rel: string): string {
  return readFileSync(join(ROOT, rel), 'utf8');
}

export interface TrustEnvelopeConfidenceAuthorityViolation {
  file: string;
  rule: string;
  detail: string;
}

/**
 * TrustEnvelope Detail confidence panel: available credible interval and posterior support
 * must carry inline Probabilistic AuthorityBadge markers in the reserved chip slots.
 */
export function scanTrustEnvelopeConfidenceAuthority(sourceOverride?: {
  panelTsx?: string;
}): TrustEnvelopeConfidenceAuthorityViolation[] {
  const violations: TrustEnvelopeConfidenceAuthorityViolation[] = [];
  const panelTsx =
    sourceOverride?.panelTsx ??
    read(
      'src/components/trust/TrustEnvelopeOperatorView/TrustEnvelopeDetailConfidencePanel.tsx',
    );

  if (!/AuthorityBadge/.test(panelTsx)) {
    violations.push({
      file: 'TrustEnvelopeDetailConfidencePanel.tsx',
      rule: 'missing-authority-badge',
      detail: 'Confidence panel must import and render AuthorityBadge',
    });
  }

  if (!/authority="probabilistic"/.test(panelTsx)) {
    violations.push({
      file: 'TrustEnvelopeDetailConfidencePanel.tsx',
      rule: 'missing-probabilistic-authority',
      detail: 'Available confidence values must use AuthorityBadge authority="probabilistic"',
    });
  }

  if (!/data-trust-envelope-confidence-authority="credible-interval"/.test(panelTsx)) {
    violations.push({
      file: 'TrustEnvelopeDetailConfidencePanel.tsx',
      rule: 'missing-credible-interval-authority-slot',
      detail: 'Credible interval fieldValueWithChip must mount a probabilistic authority marker',
    });
  }

  if (!/data-trust-envelope-confidence-authority="posterior-support"/.test(panelTsx)) {
    violations.push({
      file: 'TrustEnvelopeDetailConfidencePanel.tsx',
      rule: 'missing-posterior-support-authority-slot',
      detail: 'Posterior support fieldValueWithChip must mount a probabilistic authority marker',
    });
  }

  // Empty chip slot regression: fieldValueWithChip with only a bare value span.
  if (
    /fieldValueWithChip[\s\S]*?data-trust-envelope-credible-interval[\s\S]*?<\/dd>/.test(panelTsx) &&
    !/data-trust-envelope-credible-interval[\s\S]*?AuthorityBadge[\s\S]*?data-trust-envelope-posterior-support/.test(
      panelTsx,
    )
  ) {
    violations.push({
      file: 'TrustEnvelopeDetailConfidencePanel.tsx',
      rule: 'empty-chip-slot-regression',
      detail: 'fieldValueWithChip reserved for credible interval must not render value without AuthorityBadge',
    });
  }

  return violations;
}

export function trustEnvelopeConfidenceAuthoritySabotageFixture(): { panelTsx: string } {
  const live = read(
    'src/components/trust/TrustEnvelopeOperatorView/TrustEnvelopeDetailConfidencePanel.tsx',
  );

  return {
    panelTsx: live
      .replace(/import \{ AuthorityBadge \} from '\.\.\/AuthorityBadge\/AuthorityBadge';\n/, '')
      .replace(
        /<span data-trust-envelope-confidence-authority="credible-interval">[\s\S]*?<\/span>/,
        '',
      )
      .replace(
        /<span data-trust-envelope-confidence-authority="posterior-support">[\s\S]*?<\/span>/,
        '',
      ),
  };
}
