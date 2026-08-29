import { describe, expect, it, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {
  resolveChannelDataReliability,
  channelBenchmarkSentence,
  channelDiscrepancyMinor,
} from '../channels/channelInlineDisplay';
import { buildChannelExpandHref, readChannelExpandId } from '../channels/channelExpandHref';
import { CHANNELS_OVERVIEW_FIXTURES } from '../channels/channelsFixtures';
import { renderShell, seedShellAuth } from './level9.helpers';

describe('Channel Detail CDO remediation — display helpers', () => {
  it('maps healthy+available confidence to Verified reliability', () => {
    const row = CHANNELS_OVERVIEW_FIXTURES[0];
    expect(resolveChannelDataReliability(row)).toBe('verified');
  });

  it('maps unavailable confidence to Estimated (never invents Verified)', () => {
    const row = CHANNELS_OVERVIEW_FIXTURES.find((r) => r.confidence.status === 'unavailable');
    expect(row).toBeTruthy();
    expect(resolveChannelDataReliability(row!)).toBe('estimated');
  });

  it('computes discrepancy in integer minor units', () => {
    const row = CHANNELS_OVERVIEW_FIXTURES[1];
    expect(channelDiscrepancyMinor(row)).toBe(row.verifiedRevenueMinor - row.claimedRevenueMinor);
  });

  it('benchmark sentence never uses epistemological section copy', () => {
    const row = CHANNELS_OVERVIEW_FIXTURES[0];
    expect(channelBenchmarkSentence(row)).toMatch(/vs\. Market:/i);
  });

  it('expand href builders round-trip', () => {
    const href = buildChannelExpandHref('ch_paid_search__google_ads', '?sortKey=verifiedRevenue');
    expect(href).toContain('/app/channels?');
    expect(href).toContain('expand=ch_paid_search__google_ads');
    expect(readChannelExpandId(href.split('?')[1] ?? '')).toBe('ch_paid_search__google_ads');
  });
});

describe('Channel Detail CDO remediation — mounted expansion', () => {
  beforeEach(() => seedShellAuth('owner'));

  it('positive: expansion renders executive defense-first core', async () => {
    renderShell('/app/channels?expand=ch_paid_social__meta_ads');
    await waitFor(() =>
      expect(document.querySelector('[data-channel-inline-expansion="ch_paid_social__meta_ads"]')).toBeTruthy(),
    );
    expect(document.querySelector('[data-channel-inline-deck="defense"]')).toBeTruthy();
    expect(document.querySelector('[data-channel-inline-section="revenue"]')).toBeTruthy();
    expect(document.querySelector('[data-channel-money="verified"]')).toBeTruthy();
    expect(document.querySelector('[data-channel-inline-campaigns]')).toBeTruthy();
    expect(document.querySelector('[data-channel-inline-trend]')).toBeTruthy();
    expect(document.querySelector('[data-channel-trend-state="default"]')).toBeTruthy();
    expect(document.querySelector('[data-channel-trend-delta]')).toBeTruthy();
    expect(document.querySelector('[data-channel-trend-axes]')).toBeTruthy();
    expect(document.querySelector('[data-channel-trend-y-axis]')).toBeTruthy();
    expect(document.querySelector('[data-channel-trend-y-tick="max"]')).toBeTruthy();
    expect(document.querySelector('[data-channel-trend-y-tick="zero"]')).toBeTruthy();
    expect(document.querySelectorAll('[data-channel-trend-x-tick]').length).toBeGreaterThanOrEqual(2);
    expect(document.querySelectorAll('[data-channel-trend-bar]').length).toBeGreaterThanOrEqual(2);
    expect(document.querySelector('[data-channel-inline-deck="context"]')).toBeTruthy();
    expect(screen.getByRole('link', { name: /Review \d+ claims?/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Hold spend/i })).toBeDisabled();
    expect(document.querySelector('[data-channel-hold-reason]')).toBeTruthy();
    // Warning only for material discrepancy — Paid Social is flagged, not material
    expect(document.querySelector('[data-channel-inline-platform-warning]')).toBeNull();
    // No duplicate confidence section
    expect(screen.queryByText(/^Confidence:/i)).not.toBeInTheDocument();
  });

  it('negative: model comparison / TrustEnvelope / confidence interval absent', async () => {
    renderShell('/app/channels?expand=ch_paid_search__google_ads');
    await waitFor(() => expect(document.querySelector('[data-channel-inline-expansion]')).toBeTruthy());
    expect(document.querySelector('[data-channel-model-table]')).toBeNull();
    expect(document.querySelector('[data-channel-trust-envelope-expansion]')).toBeNull();
    expect(screen.queryByText(/Related TrustEnvelopes/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Attribution models are deterministic heuristics/i)).not.toBeInTheDocument();
  });

  it('meta-negative: row toggle collapses expansion (harness can fail on stuck expand)', async () => {
    const user = userEvent.setup();
    renderShell('/app/channels?expand=ch_paid_search__google_ads');
    await waitFor(() =>
      expect(
        document.querySelector('[data-channel-inline-expansion="ch_paid_search__google_ads"]'),
      ).toBeTruthy(),
    );
    const open = document.querySelector(
      '[data-channel-open="ch_paid_search__google_ads"]',
    ) as HTMLButtonElement;
    await user.click(open);
    await waitFor(() =>
      expect(
        document.querySelector('[data-channel-inline-expansion="ch_paid_search__google_ads"]'),
      ).toBeNull(),
    );
  });

  it('legacy /channels/:id path redirects into expand deep-link', async () => {
    const { router } = renderShell('/app/channels/ch_paid_search__google_ads');
    await waitFor(() => expect(router.state.location.pathname).toBe('/app/channels'));
    await waitFor(() => expect(router.state.location.search).toContain('expand=ch_paid_search__google_ads'));
    await waitFor(() => expect(document.querySelector('[data-channel-inline-expansion]')).toBeTruthy());
  });
});
