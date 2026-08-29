import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';
import { waitFor } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { render } from '@testing-library/react';
import {
  scanUnavailableConfidenceSummary,
  unavailableConfidenceSummarySabotageFixture,
} from '../audit/unavailableConfidenceSummaryScan';
import { createMockSession, createMockTenant } from '../auth/authClient';
import { clearSession, establishTenant, resetAuthStateForTests, setBootstrapReady } from '../auth/sessionStore';
import { AppShellRoutes } from '../app/routes/ShellRoutes';
import { resetGovernanceStateForTests, setCurrentUserRole } from '../governance/governanceStore';
import { TRUST_ENVELOPE_INDEX_COPY } from '../trustIndex/copy';
import {
  computeTrustIndexSummary,
  classifyUnavailableConfidenceCause,
  isConfidenceUnavailable,
} from '../trustIndex/trustIndexSummary';
import {
  createTrustIndexClient,
  resetDefaultTrustIndexClient,
  type TrustIndexFilters,
} from '../trustIndex/trustIndexClient';
import {
  buildUnavailableConfidenceIsolateHref,
  buildClearConfidenceAvailabilityHref,
} from '../trustIndex/trustIndexQueryState';
import {
  resolveUnavailableConfidenceDisposition,
  unavailableConfidenceMetaCopy,
} from '../trustIndex/unavailableConfidenceSummaryPresentation';
import type { TrustEnvelopeIndexRowDTO } from '../ledger/types';

function seedAuth() {
  establishTenant(createMockSession(), createMockTenant());
  setBootstrapReady();
  setCurrentUserRole('owner');
  resetDefaultTrustIndexClient();
}

function renderTrust(path = '/app/trust') {
  const router = createMemoryRouter([{ path: '/app/*', element: <AppShellRoutes /> }], {
    initialEntries: [path],
  });
  return { ...render(<RouterProvider router={router} />), router };
}

function stubRow(
  partial: Partial<TrustEnvelopeIndexRowDTO> & Pick<TrustEnvelopeIndexRowDTO, 'confidence'>,
): TrustEnvelopeIndexRowDTO {
  return {
    envelopeId: partial.envelopeId ?? 'env_test',
    subjectRef: 'subj_test',
    subjectLabel: 'Subject',
    subjectDetail: 'Detail',
    claimTime: '2026-06-01T00:00:00.000Z',
    claimSource: 'meta_ads',
    claimedRevenueMinor: 100n,
    verifiedRevenueMinor: 100n,
    currencyCode: 'USD',
    discrepancyAmountMinor: 0n,
    discrepancyRateBps: 0,
    discrepancyClass: 'none',
    verificationStatus: 'verified',
    matchVerdict: 'matched',
    revenueAuthority: 'deterministic',
    attributionModel: 'last_touch',
    attributionAuthority: 'deterministic',
    confidence: partial.confidence,
    benchmark: partial.benchmark ?? { status: 'unavailable' },
    auditRecordStatus: 'linked',
    policyAuthority: 'blocked',
    channelSource: 'meta_ads',
    auditReference: 'aud_test',
    generationTimestamp: '2026-06-01T00:00:00.000Z',
    status: 'active',
    futureDetailAffordance: 'detail_blocked_level_8',
  };
}

beforeEach(() => {
  resetAuthStateForTests();
  resetGovernanceStateForTests();
  clearSession();
  resetDefaultTrustIndexClient();
});

describe('CRHAID 2 — Unavailable confidence summary remediation', () => {
  describe('Positive controls', () => {
    it('counts confidence-unavailable only and classifies causes (ignores benchmark-only)', () => {
      const rows = [
        stubRow({
          envelopeId: 'a',
          confidence: { status: 'unavailable', reason: 'cold_start_insufficient_data' },
          benchmark: { status: 'available', evidenceClass: 'live_empirical' },
        }),
        stubRow({
          envelopeId: 'b',
          confidence: { status: 'unavailable', reason: 'bayesian_timeout' },
        }),
        stubRow({
          envelopeId: 'c',
          confidence: {
            status: 'available',
            authority: 'probabilistic',
            intervalLower: 0.7,
            intervalUpper: 0.9,
          },
          benchmark: { status: 'unavailable' },
        }),
      ];

      expect(isConfidenceUnavailable(rows[0].confidence)).toBe(true);
      expect(classifyUnavailableConfidenceCause(rows[0].confidence)).toBe('cold_start');
      expect(classifyUnavailableConfidenceCause(rows[1].confidence)).toBe('computation');

      const summary = computeTrustIndexSummary(rows);
      expect(summary.unavailableConfidenceCount).toBe(2);
      expect(summary.unavailableConfidenceCauses).toEqual({
        coldStart: 1,
        computation: 1,
        other: 0,
      });
      expect(summary.totalCount).toBe(3);
    });

    it('frames cold-start-dominant vs mixed dispositions with single-line meta', () => {
      const cold = resolveUnavailableConfidenceDisposition(10, {
        coldStart: 10,
        computation: 0,
        other: 0,
      });
      expect(cold).toBe('cold_start_dominant');
      expect(unavailableConfidenceMetaCopy(cold, { coldStart: 10, computation: 0, other: 0 })).toBe(
        'Mostly expected cold start',
      );
      expect(unavailableConfidenceMetaCopy(cold, { coldStart: 10, computation: 0, other: 0 })).not.toMatch(
        /Deterministic verification remains active/,
      );

      const mixed = resolveUnavailableConfidenceDisposition(5, {
        coldStart: 3,
        computation: 2,
        other: 0,
      });
      expect(mixed).toBe('mixed');
      expect(unavailableConfidenceMetaCopy(mixed, { coldStart: 3, computation: 2, other: 0 })).toBe(
        '3 cold start · 2 need review',
      );
    });

    it('isolate CTA href sets confidenceAvailability=unavailable', () => {
      const filters: TrustIndexFilters = { policyAuthority: 'blocked', offset: 20, pageSize: 10 };
      const href = buildUnavailableConfidenceIsolateHref(filters);
      expect(href).toContain('/app/trust?');
      expect(href).toContain('confidenceAvailability=unavailable');
      expect(href).toContain('policyAuthority=blocked');
      expect(href).not.toContain('offset=');

      const cleared = buildClearConfidenceAvailabilityHref({
        ...filters,
        confidenceAvailability: 'unavailable',
      });
      expect(cleared).not.toContain('confidenceAvailability=');
      expect(cleared).toContain('policyAuthority=blocked');
    });

    it('DOM tile shows ratio, cause meta, and isolate CTA that filters the ledger', async () => {
      const user = userEvent.setup();
      seedAuth();
      const { router } = renderTrust('/app/trust');

      await waitFor(() => {
        const count = Number(
          document
            .querySelector('[data-unavailable-confidence-count]')
            ?.getAttribute('data-unavailable-confidence-count'),
        );
        expect(count).toBeGreaterThan(0);
      });

      const tile = document.querySelector('[data-summary-metric="unavailable_confidence"]');
      expect(tile).toBeTruthy();

      const value = document.querySelector('[data-summary-metric-value="unavailable_confidence"]');
      expect(value?.textContent).toMatch(/\d+\s*\/\s*\d+/);

      const meta = document.querySelector('[data-unavailable-confidence-meta]');
      expect(meta?.textContent).toBeTruthy();
      expect(meta?.textContent?.length ?? 0).toBeLessThanOrEqual(48);
      expect(meta?.getAttribute('title')).toContain('Deterministic verification remains active');
      expect(meta?.className).toMatch(/metaSingleLine/);

      const cta = document.querySelector(
        '[data-summary-drilldown="unavailable_confidence"][data-unavailable-confidence-cta="isolate"]',
      );
      expect(cta?.getAttribute('href')).toContain('confidenceAvailability=unavailable');
      expect(cta?.textContent).toContain(TRUST_ENVELOPE_INDEX_COPY.summary.viewUnavailableConfidence);

      await user.click(cta as HTMLElement);
      await waitFor(() => {
        expect(router.state.location.search).toContain('confidenceAvailability=unavailable');
      });

      await waitFor(() => {
        const select = document.querySelector(
          '[data-trust-index-filters] select[aria-label="Confidence availability"]',
        ) as HTMLSelectElement | null;
        expect(select?.value).toBe('unavailable');
      });
    });

    it('static integrity scan passes on live sources', () => {
      expect(scanUnavailableConfidenceSummary()).toEqual([]);
    });
  });

  describe('Negative controls', () => {
    it('rejects benchmark-OR count, missing meta, and missing CTA', () => {
      const violations = scanUnavailableConfidenceSummary(unavailableConfidenceSummarySabotageFixture());
      expect(violations.some((v) => v.rule === 'confidence-count-ors-benchmark')).toBe(true);
      expect(violations.some((v) => v.rule === 'missing-cause-meta')).toBe(true);
      expect(violations.some((v) => v.rule === 'missing-isolate-cta')).toBe(true);
      expect(violations.some((v) => v.rule === 'missing-supervisor-copy')).toBe(true);
      expect(violations.some((v) => v.rule === 'legacy-benchmark-or-field')).toBe(true);
    });
  });

  describe('Meta-negative control', () => {
    it('harness is non-vacuous: sabotage fails while live passes', () => {
      expect(scanUnavailableConfidenceSummary()).toEqual([]);
      const sabotaged = scanUnavailableConfidenceSummary(unavailableConfidenceSummarySabotageFixture());
      expect(sabotaged.length).toBeGreaterThan(0);
    });
  });

  describe('Synthetic dataset sanity', () => {
    it('fixture index produces both cold-start and computation classes', async () => {
      seedAuth();
      const client = createTrustIndexClient();
      const full = await client.listEnvelopes('tenant_test', {});
      expect(full.kind).toBe('loaded');
      if (full.kind !== 'loaded') return;
      const summary = full.summary;
      expect(summary).toBeTruthy();
      expect(summary!.unavailableConfidenceCount).toBeGreaterThan(0);
      expect(
        summary!.unavailableConfidenceCauses.coldStart +
          summary!.unavailableConfidenceCauses.computation +
          summary!.unavailableConfidenceCauses.other,
      ).toBe(summary!.unavailableConfidenceCount);
      expect(summary!.unavailableConfidenceCauses.coldStart).toBeGreaterThan(0);
      expect(summary!.unavailableConfidenceCauses.computation).toBeGreaterThan(0);
    });
  });
});
