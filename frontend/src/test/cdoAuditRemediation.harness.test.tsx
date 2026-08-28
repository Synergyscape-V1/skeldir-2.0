import { describe, expect, it, beforeEach } from 'vitest';
import { screen, waitFor, fireEvent } from '@testing-library/react';
import { axe, toHaveNoViolations } from 'jest-axe';
import { exportVerifiedReport, resetClaimExportTestMode } from '../actions/claimExportClient';
import { getDefaultTrustEnvelopeDetailClient } from '../trustIndex/trustEnvelopeDetailClient';
import { renderMountedTrustEnvelopeDrawer } from './level8.helpers';
import { renderShell, seedShellAuth } from './level9.helpers';
import { resolveClaimLedgerExecutiveReliability } from '../trust/executiveDataReliability';

expect.extend(toHaveNoViolations);

describe('CDO Audit 1/2 — channels overview revenue reliability UI', () => {
  beforeEach(() => seedShellAuth('owner'));

  it('positive: channels table renders Revenue Reliability badges instead of raw agreement text', async () => {
    renderShell('/app/channels');
    await waitFor(() => expect(document.querySelector('[data-revenue-reliability]')).toBeTruthy());
    expect(screen.getByRole('columnheader', { name: /Revenue Reliability/i })).toBeInTheDocument();
    expect(screen.queryByText('96.2%')).not.toBeInTheDocument();
    const badges = document.querySelectorAll('[data-revenue-reliability]');
    expect(badges.length).toBeGreaterThan(0);
    badges.forEach((node) => {
      expect(node.textContent?.toLowerCase()).toMatch(/robust|mixed|fragile/);
    });
  });

  it('positive: revenue reliability header info portals a designed tooltip on hover', async () => {
    renderShell('/app');
    await waitFor(() => expect(document.querySelector('[data-revenue-reliability-header-info]')).toBeTruthy());
    const info = document.querySelector('[data-revenue-reliability-header-info]') as HTMLButtonElement;
    expect(document.querySelector('[data-revenue-reliability-header-tooltip]')).toBeNull();
    fireEvent.mouseEnter(info);
    await waitFor(() =>
      expect(document.querySelector('[data-revenue-reliability-header-tooltip]')).toBeTruthy(),
    );
    const tip = document.querySelector('[data-revenue-reliability-header-tooltip]');
    expect(tip?.parentElement).toBe(document.body);
    expect(tip?.textContent).toMatch(/budget decisions/i);
    expect(tip?.textContent).not.toMatch(/attribution model/i);
    fireEvent.mouseLeave(info);
    await waitFor(() =>
      expect(document.querySelector('[data-revenue-reliability-header-tooltip]')).toBeNull(),
    );
  });

  it('positive: Revenue Reliability header exposes both words — Reliability is never truncated', async () => {
    renderShell('/app/channels');
    await waitFor(() =>
      expect(document.querySelector('[data-revenue-reliability-column-header]')).toBeTruthy(),
    );
    const header = document.querySelector('[data-revenue-reliability-column-header]');
    expect(header?.textContent).toMatch(/Revenue Reliability/);
    const label = document.querySelector('[data-revenue-reliability-label]') as HTMLElement;
    expect(label?.textContent?.trim()).toBe('Revenue Reliability');
    // Label must not use ellipsis clipping — both words remain in the text node.
    expect(getComputedStyle(label).textOverflow).not.toBe('ellipsis');
    expect(getComputedStyle(label).overflowWrap).not.toBe('anywhere');
  });

  it('negative: human UI contains no model agreement column label', async () => {
    renderShell('/app/channels');
    await waitFor(() => expect(document.querySelector('[data-revenue-reliability]')).toBeTruthy());
    expect(screen.queryByText(/Model agreement/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Attribution model agreement/i)).not.toBeInTheDocument();
  });
});

describe('CDO Audit remediation — TrustEnvelope detail gate', () => {
  beforeEach(() => seedShellAuth('owner'));

  it('positive: verified envelope renders Verified executive badge', async () => {
    renderMountedTrustEnvelopeDrawer('env_0001');
    await waitFor(() =>
      expect(document.querySelector('[data-data-reliability-gate="verified"]')).toBeTruthy(),
    );
    expect(document.querySelector('[data-executive-reliability="verified"]')).toBeTruthy();
    expect(document.querySelector('[data-data-reliability-alert]')).toBeNull();
  });

  it('negative: provisional envelope renders Estimated gate with export lock', async () => {
    renderMountedTrustEnvelopeDrawer('env_0002');
    await waitFor(() =>
      expect(document.querySelector('[data-data-reliability-gate="estimated"]')).toBeTruthy(),
    );
    expect(document.querySelector('[data-data-reliability-export-allowed="false"]')).toBeTruthy();
    expect(document.querySelector('[data-data-reliability-alert]')).toBeTruthy();
    expect(screen.getByRole('link', { name: /Repair source connection/i })).toBeInTheDocument();
  });

  it('negative: stale unmatched envelope renders Pending gate', async () => {
    renderMountedTrustEnvelopeDrawer('env_0003');
    await waitFor(() =>
      expect(document.querySelector('[data-data-reliability-gate="pending"]')).toBeTruthy(),
    );
    expect(document.querySelector('[data-data-reliability-simulator-allowed="false"]')).toBeTruthy();
  });

  it('meta-negative: detail client never hardcodes deterministic badge on degraded fixtures', async () => {
    const outcome = await getDefaultTrustEnvelopeDetailClient().getTrustEnvelopeDetail(
      'tenant_test_001',
      'env_0002',
    );
    expect(outcome.kind).toBe('loaded');
    if (outcome.kind !== 'loaded') return;
    expect(outcome.detail.deterministicTruth.matchVerdictStatus).toBe('matched_provisional');
  });
});

describe('CDO Audit remediation — export permission gate', () => {
  beforeEach(() => {
    seedShellAuth('owner');
    resetClaimExportTestMode();
  });

  it('blocks verified export when claim reliability is Estimated', async () => {
    const outcome = await exportVerifiedReport(
      'tenant_test_001',
      'claim_0005',
      'v_claim_0005_1',
    );
    expect(outcome.status).toBe('blocked_by_policy');
    expect(outcome.safeUserCopy).toMatch(/estimated data/i);
  });
});

describe('CDO Audit 1/2 — DiscrepancyIndicator remediation', () => {
  beforeEach(() => seedShellAuth('owner'));

  it('positive: claims ledger difference cell surfaces dollar, percent, and badge', async () => {
    renderShell('/app/claims');
    await waitFor(() => expect(document.querySelector('[data-discrepancy-indicator]')).toBeTruthy());
    const indicator = document.querySelector('[data-difference-cell="flagged"]');
    expect(indicator).toBeTruthy();
    expect(indicator?.querySelector('[data-discrepancy-amount]')).toBeTruthy();
    expect(indicator?.querySelector('[data-discrepancy-percent]')?.textContent).toMatch(
      /^\d+\.\d{2}% of claim$/,
    );
    expect(indicator?.getAttribute('aria-label')).toMatch(/of claimed revenue/);
    expect(indicator?.querySelector('[data-discrepancy-badge="flagged"]')).toBeTruthy();
  });

  it('positive: claim detail gap tile exposes magnitude without redundant context strip', async () => {
    renderShell('/app/claims/claim_0004');
    await waitFor(() =>
      expect(document.querySelector('[data-delta-variant="tile"]')).toBeTruthy(),
    );
    expect(document.querySelector('[data-discrepancy-percent]')?.textContent).toMatch(
      /of claimed revenue/,
    );
    expect(document.querySelector('[data-summary-metric="claim_difference"] [data-discrepancy-badge]')).toBeNull();
    expect(document.querySelector('[data-claim-delta-context]')).toBeNull();
    expect(document.querySelector('[data-variance-policy-gate]')).toBeNull();
  });

  it('negative: claim detail no longer surfaces the redundant variance strip CTA', async () => {
    renderShell('/app/claims/claim_0004');
    await waitFor(() => expect(document.querySelector('[data-claim-detail-loaded]')).toBeTruthy());
    expect(document.querySelector('[data-variance-gate-locked="true"]')).toBeNull();
    expect(document.querySelector('[data-variance-review-cta]')).toBeNull();
    expect(screen.queryByRole('link', { name: /Review Discrepancy/i })).not.toBeInTheDocument();
  });

  it('meta-negative: no raw dollar-only difference cells without percent context', async () => {
    renderShell('/app/claims');
    await waitFor(() => expect(document.querySelector('[data-discrepancy-indicator]')).toBeTruthy());
    const indicators = document.querySelectorAll('[data-discrepancy-indicator]');
    expect(indicators.length).toBeGreaterThan(0);
    indicators.forEach((node) => {
      expect(node.querySelector('[data-discrepancy-percent]')).toBeTruthy();
    });
  });
});

describe('CDO Audit 1/2 — Discrepancy override on synthesized trust badge', () => {
  beforeEach(() => seedShellAuth('owner'));

  it('positive: flagged claim ledger row renders red Discrepancy badge in Verified Revenue cell', async () => {
    renderShell('/app/claims');
    await waitFor(() => expect(document.querySelector('[data-verified-revenue-cell]')).toBeTruthy());
    const badges = document.querySelectorAll('[data-executive-reliability="discrepancy"]');
    expect(badges.length).toBeGreaterThan(0);
    badges.forEach((node) => {
      expect(node.textContent?.toLowerCase()).toMatch(/discrepancy/);
    });
  });

  it('negative: matched_confirmed + converged + flagged discrepancy never renders Verified', async () => {
    renderShell('/app/claims');
    await waitFor(() => expect(document.querySelector('[data-verified-revenue-cell]')).toBeTruthy());
    const verifiedBadges = document.querySelectorAll('[data-executive-reliability="verified"]');
    verifiedBadges.forEach((node) => {
      const cell = node.closest('[data-verified-revenue-cell]');
      expect(cell?.querySelector('[data-discrepancy-badge="flagged"]')).toBeNull();
    });
  });

  it('meta-negative: resolver honors flagged discrepancy even when match would otherwise be Verified', () => {
    const resolution = resolveClaimLedgerExecutiveReliability({
      matchVerdict: 'within_tolerance',
      confidence: { status: 'available' },
      verificationStatus: 'verified',
      discrepancyClass: 'flagged',
    });
    expect(resolution.reliability).toBe('discrepancy');
    expect(resolution.allowsVerifiedExport).toBe(false);
  });
});

describe('CDO Audit 1/2 — commercial polish: accessibility gate', () => {
  beforeEach(() => seedShellAuth('owner'));

  it('axe: Claims Ledger with Discrepancy badges has no violations', async () => {
    const { container } = renderShell('/app/claims');
    await waitFor(() => expect(document.querySelector('[data-executive-reliability="discrepancy"]')).toBeTruthy());
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('axe: TrustEnvelope detail gate has no violations', async () => {
    const { container } = renderMountedTrustEnvelopeDrawer('env_0002');
    await waitFor(() =>
      expect(document.querySelector('[data-data-reliability-gate="estimated"]')).toBeTruthy(),
    );
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
