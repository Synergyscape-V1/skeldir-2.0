import { beforeEach, describe, expect, it } from 'vitest';
import { renderDetailRouter, resetLevel9HarnessState, seedShellAuth, createDetailShellRouter } from './level9.helpers';
import { waitForCommandCenterLoaded } from './level10.helpers';
import {
  claimDetailRedesignSabotageFixture,
  scanClaimDetailRedesign,
} from '../audit/claimDetailRedesignScan';
import { resetClaimDetailTestMode } from '../claims/claimDetailClient';
import { waitFor } from '@testing-library/react';

function renderClaimDetail(claimId = 'claim_0004') {
  const router = createDetailShellRouter([`/app/claims/${claimId}`]);
  return { ...renderDetailRouter(router), router };
}

async function waitForClaimDetailLoaded() {
  await waitFor(() => expect(document.querySelector('[data-claim-detail-loaded]')).toBeTruthy());
}

beforeEach(() => {
  resetLevel9HarnessState();
  resetClaimDetailTestMode();
});

describe('CRHAID 1 — Claim Detail Overview DNA redesign — scope & DNA', () => {
  it('static compliance scan passes on live sources', () => {
    expect(scanClaimDetailRedesign()).toEqual([]);
  });

  it('renders Overview tile DNA with financial_truth tiles and no legacy hero', async () => {
    seedShellAuth();
    renderClaimDetail('claim_0004');
    await waitForClaimDetailLoaded();

    expect(document.querySelector('[data-claim-aesthetic="overview-tile"]')).toBeTruthy();
    expect(document.querySelector('[data-claim-aesthetic="cfo-brief"]')).toBeNull();

    const tiles = Array.from(document.querySelectorAll('[data-summary-tile-kind="financial_truth"]'));
    expect(tiles.length).toBeGreaterThanOrEqual(3);

    expect(document.querySelector('[data-claim-detail-header]')).toBeTruthy();
    expect(document.querySelector('[data-page-interface-header]')).toBeTruthy();
  });
});

describe('CRHAID 1 — behavior preserved (negative-scope: do not break trust contract)', () => {
  it('keeps verdict and discrepancy behavior intact without decorative authority chips', async () => {
    seedShellAuth();
    renderClaimDetail('claim_0004');
    await waitForClaimDetailLoaded();

    expect(document.querySelector('[data-claim-verdict]')).toBeTruthy();
    expect(document.querySelector('[data-claim-verdict]')?.getAttribute('data-claim-verdict')).toBe(
      'discrepancy',
    );

    // Confirmed-revenue AuthorityBadge retained; platform-claim + discrepancy tiles stay chip-free.
    expect(
      document.querySelector('[data-claim-detail-header] [data-trust-chip]'),
    ).toBeNull();
    expect(
      document.querySelector(
        '[data-summary-metric="claim_claimed"] [aria-label*="Source authority"]',
      ),
    ).toBeNull();
    expect(
      document.querySelector(
        '[data-summary-metric="claim_verified"] [aria-label*="Source authority"]',
      ),
    ).toBeTruthy();
    expect(
      document.querySelector(
        '[data-summary-metric="claim_difference"] [aria-label*="Source authority"]',
      ),
    ).toBeNull();
    expect(
      document.querySelector('[data-claim-detail-summary] [data-executive-reliability]'),
    ).toBeNull();

    // Gap magnitude lives in the tile only — context strip removed.
    expect(document.querySelector('[data-delta-variant="tile"]')).toBeTruthy();
    expect(document.querySelector('[data-claim-delta-context]')).toBeNull();
    expect(document.querySelector('[data-delta-variant="context"]')).toBeNull();

    expect(document.querySelector('[data-data-reliability-gate]')).toBeTruthy();
  });

  it('executive action panel is absent from claim detail', async () => {
    seedShellAuth();
    renderClaimDetail('claim_0004');
    await waitForClaimDetailLoaded();

    expect(document.querySelector('[data-claim-action-panel]')).toBeNull();
    expect(document.querySelector('[data-claim-negative-boundary]')).toBeNull();
    expect(document.querySelector('[data-claim-evidence-export]')).toBeNull();
  });

  it('gap tile remains magnitude-only; context strip is absent', async () => {
    seedShellAuth();
    renderClaimDetail('claim_0004');
    await waitForClaimDetailLoaded();

    const gapTile = document.querySelector('[data-summary-metric="claim_difference"]');
    expect(gapTile).toBeTruthy();
    expect(document.querySelector('[data-claim-delta-context]')).toBeNull();
    expect(document.querySelector('[data-variance-policy-gate]')).toBeNull();
    expect(document.querySelector('[data-variance-review-cta]')).toBeNull();

    // Tile must NOT contain the former strip's verbose variance/policy prose.
    expect(gapTile?.textContent).not.toMatch(/Exceeds \d+% (variance )?threshold/i);
    expect(gapTile?.textContent).not.toMatch(/Action blocked/i);
  });

  it('preserves attribution + events sections as Overview cards', async () => {
    seedShellAuth();
    renderClaimDetail('claim_0004');
    await waitForClaimDetailLoaded();

    expect(document.querySelector('[data-claim-attribution-section]')).toBeTruthy();
    expect(document.querySelector('[data-claim-events-section]')).toBeTruthy();
    expect(document.querySelector('[data-claim-event-row]')).toBeTruthy();
    expect(document.querySelector('[data-claim-event-status]')).toBeTruthy();
  });

  it('preserves unverified panel + exclude action for unverified fixtures', async () => {
    seedShellAuth();
    renderClaimDetail('claim_0011');
    await waitForClaimDetailLoaded();
    expect(document.querySelector('[data-claim-unverified-panel]')).toBeTruthy();
    expect(document.querySelector('[data-claim-exclude-budget]')).toBeTruthy();
  });
});

describe('CRHAID 1 — negative controls (simulated sabotage)', () => {
  it('sabotage reintroducing legacy hero + forbidden aesthetic is detected', () => {
    const violations = scanClaimDetailRedesign(claimDetailRedesignSabotageFixture());
    expect(violations.some((v) => v.rule === 'legacy-cfo-brief-marker')).toBe(true);
    expect(violations.some((v) => v.rule === 'D-no-gradient')).toBe(true);
    expect(violations.some((v) => v.rule === 'D-no-side-border-accent')).toBe(true);
    expect(violations.some((v) => v.rule === 'overview-header-grammar')).toBe(true);
  });
});

describe('CRHAID 1 — meta-negative control (harness non-vacuous)', () => {
  it('live sources pass while sabotage fails', () => {
    expect(scanClaimDetailRedesign()).toEqual([]);
    expect(scanClaimDetailRedesign(claimDetailRedesignSabotageFixture()).length).toBeGreaterThan(0);
  });
});
