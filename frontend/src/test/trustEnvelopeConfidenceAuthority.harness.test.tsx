import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import {
  scanTrustEnvelopeConfidenceAuthority,
  trustEnvelopeConfidenceAuthoritySabotageFixture,
} from '../audit/trustEnvelopeConfidenceAuthorityScan';
import { TrustEnvelopeDetailConfidencePanel } from '../components/trust/TrustEnvelopeOperatorView/TrustEnvelopeDetailConfidencePanel';
import type { TrustEnvelopeConfidenceData } from '../detail/types';

const AVAILABLE_CONFIDENCE: TrustEnvelopeConfidenceData = {
  status: 'available',
  intervalLower: 0.82,
  intervalUpper: 0.94,
  posteriorSupport: 0.91,
  modelFreshnessAt: '2026-07-16T14:00:00.000Z',
  boundaryNote:
    'Bayesian confidence is subordinate to deterministic verification. Interval is artifact-backed.',
  authority: 'probabilistic',
};

describe('TrustEnvelope Detail — confidence probabilistic authority remediation', () => {
  describe('Positive controls', () => {
    it('available credible interval and posterior support render inline Probabilistic AuthorityBadge', () => {
      const { container } = render(
        <TrustEnvelopeDetailConfidencePanel
          data={AVAILABLE_CONFIDENCE}
          referenceAt="2026-07-16T15:00:00.000Z"
        />,
      );

      const panel = container.querySelector('[data-trust-envelope-confidence-panel]');
      expect(panel).not.toBeNull();
      expect(panel?.getAttribute('data-trust-envelope-confidence-state')).toBe('available');

      const interval = container.querySelector('[data-trust-envelope-credible-interval]');
      expect(interval?.textContent).toBe('[0.82, 0.94]');

      const intervalAuthority = container.querySelector(
        '[data-trust-envelope-confidence-authority="credible-interval"]',
      );
      expect(intervalAuthority).not.toBeNull();
      expect(
        within(intervalAuthority as HTMLElement).getByRole('status', { name: /Probabilistic/i }),
      ).toBeInTheDocument();

      const posteriorAuthority = container.querySelector(
        '[data-trust-envelope-confidence-authority="posterior-support"]',
      );
      expect(posteriorAuthority).not.toBeNull();
      expect(
        within(posteriorAuthority as HTMLElement).getByRole('status', { name: /Probabilistic/i }),
      ).toBeInTheDocument();

      expect(screen.getAllByRole('status', { name: /Probabilistic/i }).length).toBeGreaterThanOrEqual(2);
    });

    it('unavailable state does not invent an interval with a Probabilistic badge', () => {
      render(
        <TrustEnvelopeDetailConfidencePanel
          data={{
            status: 'unavailable',
            reason: 'cold_start_insufficient_data',
            boundaryNote: 'Deterministic verification remains active.',
            authority: 'unavailable',
          }}
          referenceAt="2026-07-16T15:00:00.000Z"
        />,
      );

      expect(document.querySelector('[data-trust-envelope-credible-interval]')).toBeNull();
      expect(
        document.querySelector('[data-trust-envelope-confidence-authority="credible-interval"]'),
      ).toBeNull();
      expect(document.querySelector('[data-trust-envelope-confidence-state="unavailable"]')).not.toBeNull();
    });

    it('static integrity scan passes on live sources', () => {
      expect(scanTrustEnvelopeConfidenceAuthority()).toEqual([]);
    });
  });

  describe('Negative controls', () => {
    it('rejects empty chip slots without probabilistic AuthorityBadge', () => {
      const violations = scanTrustEnvelopeConfidenceAuthority(
        trustEnvelopeConfidenceAuthoritySabotageFixture(),
      );
      expect(violations.some((v) => v.rule === 'missing-authority-badge')).toBe(true);
      expect(violations.some((v) => v.rule === 'missing-credible-interval-authority-slot')).toBe(true);
      expect(violations.some((v) => v.rule === 'missing-posterior-support-authority-slot')).toBe(true);
    });
  });

  describe('Meta-negative control', () => {
    it('harness is non-vacuous: sabotage fails while live passes', () => {
      expect(scanTrustEnvelopeConfidenceAuthority()).toEqual([]);
      expect(
        scanTrustEnvelopeConfidenceAuthority(trustEnvelopeConfidenceAuthoritySabotageFixture()).length,
      ).toBeGreaterThan(0);
    });
  });
});
