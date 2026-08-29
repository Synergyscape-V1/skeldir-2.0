import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import {
  claimsConfidenceLedgerSabotageFixture,
  scanClaimsConfidenceLedger,
} from '../audit/claimsConfidenceLedgerScan';
import { baseClaimRow } from '../claims/claimsClient';
import {
  formatConfidenceIntervalLabel,
  resolveClaimsConfidenceDisposition,
  resolveClaimsConfidenceLedgerProjection,
} from '../claims/confidenceLedgerDisplay';
import { ClaimsLedgerTable } from '../components/claims/ClaimsLedgerTable/ClaimsLedgerTable';

function renderClaimsRow(index: number) {
  const row = baseClaimRow(index);
  return render(
    <MemoryRouter>
      <ClaimsLedgerTable
        rows={[row]}
        pagination={{ totalCount: 1, offset: 0, pageSize: 10, hasMore: false }}
      />
    </MemoryRouter>,
  );
}

describe('CRHAID 4 — Revenue claims confidence column remediation', () => {
  describe('Positive controls', () => {
    it('resolver maps B2.4 reason codes to distinct dispositions', () => {
      expect(
        resolveClaimsConfidenceDisposition({ status: 'unavailable', reason: 'cold_start_insufficient_data' }),
      ).toBe('cold_start');
      expect(
        resolveClaimsConfidenceDisposition({ status: 'unavailable', reason: 'worker_failure' }),
      ).toBe('worker_failure');
      expect(
        resolveClaimsConfidenceDisposition({ status: 'unavailable', reason: 'refit_locked' }),
      ).toBe('refit_locked');
      expect(
        resolveClaimsConfidenceDisposition({
          status: 'available',
          intervalLower: 0.55,
          intervalUpper: 0.68,
          qualitativeState: 'Wide posterior',
        }),
      ).toBe('available_wide');
      expect(
        resolveClaimsConfidenceDisposition({
          status: 'available',
          intervalLower: 0.88,
          intervalUpper: 0.96,
          qualitativeState: 'Exact bucket',
        }),
      ).toBe('available_exact');
    });

    it('available rows show numeric interval with Probabilistic TrustChip badge', () => {
      const { container } = renderClaimsRow(1);
      const cell = container.querySelector('[data-claims-confidence-cell]');
      expect(cell?.textContent).toMatch(/82–94%/);
      expect(cell?.textContent).toMatch(/Probabilistic/);
      expect(cell?.textContent).not.toMatch(/Low confidence/i);
      expect(cell?.getAttribute('data-claims-confidence-disposition')).toBe('available_stable');
      expect(cell?.getAttribute('data-claims-confidence-authority')).toBe('probabilistic');
      expect(cell?.getAttribute('title')).toMatch(/Posterior 82–94%/);

      const badge = within(cell as HTMLElement).getByRole('status', { name: /Probabilistic/i });
      expect(badge).toHaveAttribute('data-trust-chip', 'true');
      expect(badge.className).toMatch(/toneProbabilistic|chip/);
    });

    it('cold start and worker failure rows are distinguishable in the ledger', () => {
      const { container: cold } = renderClaimsRow(30);
      const coldCell = cold.querySelector('[data-claims-confidence-cell]');
      expect(coldCell?.textContent).toBe('Cold start');
      expect(coldCell?.getAttribute('data-claims-confidence-disposition')).toBe('cold_start');
      expect(coldCell?.getAttribute('title')).toMatch(/cold start/i);
      expect(coldCell?.getAttribute('data-claims-confidence-authority')).toBeNull();

      const { container: worker } = renderClaimsRow(10);
      const workerCell = worker.querySelector('[data-claims-confidence-cell]');
      expect(workerCell?.textContent).toBe('Worker failure');
      expect(workerCell?.getAttribute('data-claims-confidence-disposition')).toBe('worker_failure');
      expect(workerCell?.getAttribute('title')).toMatch(/worker failure/i);
    });

    it('available intervals use probabilistic tone metadata with TrustChip authority badge', () => {
      const stable = renderClaimsRow(1).container.querySelector('[data-claims-confidence-cell]');
      expect(stable?.getAttribute('data-claims-confidence-color-tone')).toBe('probabilistic');
      expect(stable?.textContent).toMatch(/82–94%/);
      expect(stable?.textContent).toMatch(/Probabilistic/);
      expect(stable?.textContent).not.toMatch(/wide|exact/i);
      expect(within(stable as HTMLElement).getByRole('status', { name: /Probabilistic/i })).toHaveAttribute(
        'data-trust-chip',
      );

      const wide = renderClaimsRow(7).container.querySelector('[data-claims-confidence-cell]');
      expect(wide?.getAttribute('data-claims-confidence-color-tone')).toBe('probabilistic');
      expect(wide?.textContent).toMatch(/55–68%/);
      expect(wide?.textContent).toMatch(/Probabilistic/);

      const cold = renderClaimsRow(30).container.querySelector('[data-claims-confidence-cell]');
      expect(cold?.getAttribute('data-claims-confidence-color-tone')).toBe('info');
      expect(cold?.className).toMatch(/confidenceTextInfo/);

      const worker = renderClaimsRow(10).container.querySelector('[data-claims-confidence-cell]');
      expect(worker?.getAttribute('data-claims-confidence-color-tone')).toBe('error');
      expect(worker?.className).toMatch(/confidenceTextError/);
    });

    it('disagreement posterior shows interval only — context lives in tooltip', () => {
      const projection = resolveClaimsConfidenceLedgerProjection(baseClaimRow(7).confidence);
      expect(projection.shortLabel).toBe('55–68%');
      expect(projection.shortLabel).not.toMatch(/wide|exact/i);
      expect(projection.title).toMatch(/model disagreement/i);
      expect(formatConfidenceIntervalLabel(0.55, 0.68)).toBe('55–68%');
    });

    it('does not mount full DataUnavailablePanel inside confidence column', () => {
      renderClaimsRow(30);
      const table = screen.getByRole('table', { name: /Forensic line-item ledger/i });
      expect(within(table).getByText('Cold start')).toBeInTheDocument();
      expect(document.querySelector('[role="region"][aria-label^="Unavailable data"]')).toBeNull();
    });

    it('static integrity scan passes on live sources', () => {
      expect(scanClaimsConfidenceLedger()).toEqual([]);
    });
  });

  describe('Negative controls', () => {
    it('rejects collapsed Bayesian badge, success-tone available intervals, and missing probabilistic authority', () => {
      const violations = scanClaimsConfidenceLedger(claimsConfidenceLedgerSabotageFixture());
      expect(violations.some((v) => v.rule === 'collapsed-bayesian-badge')).toBe(true);
      expect(violations.some((v) => v.rule === 'missing-confidence-title')).toBe(true);
      expect(violations.some((v) => v.rule === 'missing-cold-start-disposition')).toBe(true);
      expect(violations.some((v) => v.rule === 'missing-color-tone-attribute')).toBe(true);
      expect(violations.some((v) => v.rule === 'missing-confidence-text-tones')).toBe(true);
      expect(violations.some((v) => v.rule === 'forbidden-confidence-prefix-labels')).toBe(true);
      expect(violations.some((v) => v.rule === 'uniform-synthetic-confidence')).toBe(true);
      expect(violations.some((v) => v.rule === 'missing-inline-probabilistic-authority')).toBe(true);
      expect(violations.some((v) => v.rule === 'available-interval-success-tone')).toBe(true);
      expect(violations.some((v) => v.rule === 'missing-probabilistic-trust-chip')).toBe(true);
    });
  });

  describe('Meta-negative control', () => {
    it('harness is non-vacuous: sabotage fails while live passes', () => {
      expect(scanClaimsConfidenceLedger()).toEqual([]);
      expect(scanClaimsConfidenceLedger(claimsConfidenceLedgerSabotageFixture()).length).toBeGreaterThan(0);
    });
  });
});
