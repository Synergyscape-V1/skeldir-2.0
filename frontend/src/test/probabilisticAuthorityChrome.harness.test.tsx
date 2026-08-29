import { render, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import {
  probabilisticAuthorityChromeSabotageFixture,
  scanProbabilisticAuthorityChrome,
} from '../audit/probabilisticAuthorityChromeScan';
import { AuthorityBadge } from '../components/trust/AuthorityBadge/AuthorityBadge';
import { TrustIndexConfidenceCell } from '../components/trustIndex/TrustEnvelopeIndexTable/TrustEnvelopeIndexTableCells';
import type { TrustEnvelopeIndexRowDTO } from '../ledger/types';

function baseIndexRow(overrides: Partial<TrustEnvelopeIndexRowDTO> = {}): TrustEnvelopeIndexRowDTO {
  return {
    envelopeId: 'env_test',
    subjectRef: 'claim_0001',
    subjectLabel: 'Claim 0001',
    subjectDetail: 'Meta Ads',
    claimTime: '2026-07-16T12:00:00.000Z',
    claimSource: 'meta_ads',
    claimedRevenueMinor: 11000n,
    verifiedRevenueMinor: 10000n,
    currencyCode: 'USD',
    discrepancyAmountMinor: -1000n,
    discrepancyRateBps: -909,
    discrepancyClass: 'flagged',
    matchVerdict: 'exact_match',
    verificationStatus: 'verified',
    revenueAuthority: 'deterministic',
    attributionModel: 'last_touch',
    attributionAuthority: 'deterministic',
    confidence: { status: 'available', intervalLower: 0.82, intervalUpper: 0.94 },
    benchmark: { status: 'unavailable' },
    auditRecordStatus: 'linked',
    policyAuthority: 'blocked',
    channelSource: 'meta_ads',
    auditReference: 'audit_ref_1',
    generationTimestamp: '2026-07-16T12:00:00.000Z',
    status: 'active',
    futureDetailAffordance: 'detail_blocked_level_8',
    ...overrides,
  };
}

describe('System-wide Probabilistic AuthorityBadge TrustChip chrome', () => {
  describe('Positive controls', () => {
    it('AuthorityBadge ignores appearance="text" for probabilistic — always TrustChip', () => {
      const { container } = render(
        <AuthorityBadge authority="probabilistic" size="table" appearance="text" />,
      );
      const chip = container.querySelector('[data-trust-chip]');
      expect(chip).not.toBeNull();
      expect(chip).toHaveAttribute('data-authority-class', 'probabilistic');
      expect(chip?.textContent).toBe('Probabilistic');
      expect(container.querySelector('[data-status-text]')).toBeNull();
    });

    it('Trust Index confidence available row mounts Probabilistic TrustChip', () => {
      const { container } = render(<TrustIndexConfidenceCell row={baseIndexRow()} />);
      const cell = container.querySelector('[data-trust-index-confidence]');
      expect(cell).not.toBeNull();
      const badge = within(cell as HTMLElement).getByRole('status', { name: /Probabilistic/i });
      expect(badge).toHaveAttribute('data-trust-chip', 'true');
      expect(badge).toHaveAttribute('data-authority-class', 'probabilistic');
    });

    it('Trust Index unavailable row mounts Unavailable TrustChip (paired chrome)', () => {
      const { container } = render(
        <TrustIndexConfidenceCell
          row={baseIndexRow({ confidence: { status: 'unavailable', reason: 'cold_start' } })}
        />,
      );
      const badge = within(
        container.querySelector('[data-trust-index-confidence]') as HTMLElement,
      ).getByRole('status', { name: /Unavailable/i });
      expect(badge).toHaveAttribute('data-trust-chip', 'true');
    });

    it('static integrity scan passes on live sources', () => {
      expect(scanProbabilisticAuthorityChrome()).toEqual([]);
    });
  });

  describe('Negative controls', () => {
    it('rejects missing chip-force and text appearance call sites', () => {
      const violations = scanProbabilisticAuthorityChrome(
        probabilisticAuthorityChromeSabotageFixture(),
      );
      expect(violations.some((v) => v.rule === 'missing-probabilistic-chip-force')).toBe(true);
      expect(violations.some((v) => v.rule === 'probabilistic-authority-text-appearance')).toBe(true);
    });
  });

  describe('Meta-negative control', () => {
    it('harness is non-vacuous: sabotage fails while live passes', () => {
      expect(scanProbabilisticAuthorityChrome()).toEqual([]);
      expect(
        scanProbabilisticAuthorityChrome(probabilisticAuthorityChromeSabotageFixture()).length,
      ).toBeGreaterThan(0);
    });
  });
});
