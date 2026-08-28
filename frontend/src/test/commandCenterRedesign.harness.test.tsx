import { beforeEach, describe, expect, it } from 'vitest';
import { within } from '@testing-library/react';
import { runCommandCenterRedesignIntegrityProbes,
  runCommandCenterRedesignNegativeScopeScan,
  runCommandCenterRedesignSabotageProbes,
} from '../audit/commandCenterRedesignNegativeScopeScan';
import {
  buildVerifiedRevenueAxisTickMinors,
  buildReferenceTrendPoints,
  formatVerifiedRevenueAxisLabel,
  TREND_CHART_REFERENCE_DAY_COUNT,
  VERIFIED_REVENUE_CHART_HEIGHT,
  VERIFIED_REVENUE_CHART_PRESERVE_ASPECT_RATIO,
  VERIFIED_REVENUE_CHART_WIDTH,
} from '../components/commandCenter/VerifiedRevenueChart/verifiedRevenueChartGeometry';
import { MIN_TREND_DAYS, MAX_TREND_POINTS } from '../commandCenter/trendConstants';
import { COMMAND_CENTER_COPY } from '../commandCenter/copy';
import {
  setCommandCenterSubstrateOverridesForTests,
  setCommandCenterTestMode,
} from '../commandCenter/commandCenterClient';
import {
  renderCommandCenter,
  resetLevel10HarnessState,
  seedShellAuth,
  waitForCommandCenterLoaded,
  screen,
} from './level10.helpers';

beforeEach(() => {
  resetLevel10HarnessState();
});

describe('Command Center Redesign Harness — scope', () => {
  it('redesign negative scope scan passes', () => {
    expect(runCommandCenterRedesignNegativeScopeScan().violations).toEqual([]);
  });

  it('integrity probes pass', () => {
    const probes = runCommandCenterRedesignIntegrityProbes();
    expect(probes.every((p) => p.ok)).toBe(true);
  });
});

describe('Command Center Redesign Harness — positive controls', () => {
  it('renders Review issues CTA and humanized timestamp (no inline Critical incidents queue)', async () => {
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    expect(document.querySelector('[data-priority-queue]')).toBeNull();
    expect(document.querySelector('[data-priority-queue-open]')).toBeTruthy();
    expect(screen.getByRole('button', { name: COMMAND_CENTER_COPY.reviewIssues(3) })).toBeInTheDocument();
    expect(document.querySelector('[data-command-center-last-updated]')).toBeTruthy();
    expect(document.querySelector('[data-command-center-last-updated]')?.textContent).not.toMatch(
      /\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/,
    );
    expect(document.querySelector('[data-command-center-header] h1')).toBeTruthy();
  });

  it('shows urgency copy when issues exist', async () => {
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    expect(document.querySelector('[data-command-center-urgency]')).toBeTruthy();
  });

  it('summary cards expose drill-down links in directive order', async () => {
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    const ids = ['verified_revenue', 'claims_reconciled', 'action_authority', 'open_exceptions'];
    for (const id of ids) {
      expect(document.querySelector(`[data-summary-drilldown="${id}"]`)).toBeTruthy();
    }
  });

  it('summary tiles use financial vs supervisory treatments', async () => {
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    expect(
      document.querySelector('[data-summary-metric="verified_revenue"]')?.getAttribute('data-summary-tile-kind'),
    ).toBe('financial_truth');
    expect(
      document.querySelector('[data-summary-metric="claims_reconciled"]')?.getAttribute('data-summary-tile-kind'),
    ).toBe('financial_truth');
    expect(
      document.querySelector('[data-summary-metric="action_authority"]')?.getAttribute('data-summary-tile-kind'),
    ).toBe('supervisory_health');
    expect(
      document.querySelector('[data-summary-metric="open_exceptions"]')?.getAttribute('data-summary-tile-kind'),
    ).toBe('supervisory_health');
    expect(document.querySelector('[data-summary-drilldown="verified_revenue"]')?.getAttribute('href')).toContain(
      'verificationStatus=verified',
    );
    expect(document.querySelector('[data-summary-drilldown="claims_reconciled"]')?.getAttribute('href')).toContain(
      'verificationStatus=unverified',
    );
    expect(document.querySelector('[data-summary-drilldown="open_exceptions"]')?.getAttribute('href')).toBe(
      '/app/exceptions',
    );
    expect(document.body.textContent).toContain('Of connected commerce revenue');
  });

  it('claimed revenue column shows money only without platform claim pill', async () => {
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    expect(document.querySelector('[data-channel-trust-table] [data-platform-claim-label]')).toBeFalsy();
  });

  it('discrepancy renders color-coded percent without legacy status badge', async () => {
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    expect(document.querySelector('[data-channel-trust-discrepancy-tier]')).toBeTruthy();
    expect(document.querySelector('[data-discrepancy-badge]')).toBeFalsy();
    const row = document.querySelector('[data-channel-trust-row]');
    expect(row?.textContent).toMatch(/%|N\/A/);
  });

  it('verified revenue chart or unavailable state is present', async () => {
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    const chart = document.querySelector('[data-verified-revenue-chart]');
    const unavailable = document.querySelector('[data-trend-unavailable]');
    expect(chart || unavailable).toBeTruthy();
    expect(document.querySelector('[data-trend-accessible-summary]')).toBeTruthy();
  });

  it('renders x-axis labels in the chart at runtime with scale alignment', async () => {
    seedShellAuth();
    setCommandCenterSubstrateOverridesForTests({ trendPointsOverride: buildReferenceTrendPoints() });
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    const chart = document.querySelector('[data-verified-revenue-chart]');
    const labels = chart?.querySelectorAll('[data-trend-x-axis-label]');
    expect(labels?.length).toBe(13);
  });

  it('verified revenue chart renders reference window with fixed 10K-40K axis', async () => {
    seedShellAuth();
    setCommandCenterSubstrateOverridesForTests({ trendPointsOverride: buildReferenceTrendPoints() });
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    const chart = document.querySelector('[data-verified-revenue-chart]');
    expect(chart).toBeTruthy();
    expect(chart?.getAttribute('data-chart-engine')).toBe('d3');
    expect(Number(chart?.getAttribute('data-trend-day-count'))).toBe(TREND_CHART_REFERENCE_DAY_COUNT);
    expect(MAX_TREND_POINTS).toBeGreaterThanOrEqual(MIN_TREND_DAYS);
    const svg = chart?.querySelector('svg');
    expect(svg?.getAttribute('viewBox')).toBe(`0 0 ${VERIFIED_REVENUE_CHART_WIDTH} ${VERIFIED_REVENUE_CHART_HEIGHT}`);
    expect(svg?.getAttribute('preserveAspectRatio')).toBe(VERIFIED_REVENUE_CHART_PRESERVE_ASPECT_RATIO);
    const lineSegments = chart?.querySelectorAll('[data-trend-line-segment]');
    expect(lineSegments && lineSegments.length).toBeGreaterThanOrEqual(1);
    const linePath = lineSegments?.[0]?.getAttribute('d') ?? '';
    expect(linePath).toMatch(/^M[\d.-]+,[\d.-]+/);
    expect(linePath).toContain('L');
    expect(linePath).not.toMatch(/[CQSTcqst]/);
    expect(Number(chart?.getAttribute('data-trend-gap-count'))).toBeGreaterThanOrEqual(1);
    const axisLabels = [...(chart?.querySelectorAll('text') ?? [])].map((node) => node.textContent ?? '');
    expect(axisLabels).toContain('0K');
    expect(axisLabels.some((label) => label.endsWith('K'))).toBe(true);
    expect(axisLabels.filter((label) => label.startsWith('May')).length).toBeGreaterThanOrEqual(2);
    expect(axisLabels.filter((label) => label.startsWith('Jun')).length).toBeGreaterThanOrEqual(4);
    expect(axisLabels).not.toContain('USD');
    const ticks = buildVerifiedRevenueAxisTickMinors();
    expect(ticks).toHaveLength(7);
    expect(formatVerifiedRevenueAxisLabel(ticks[0]!)).toBe('10K');
    expect(formatVerifiedRevenueAxisLabel(ticks[ticks.length - 1]!)).toBe('40K');
    expect(chart?.querySelector('[data-plot-hit-area]')).toBeTruthy();
    const tooltip = chart?.querySelector('[role="tooltip"]');
    expect(tooltip).toBeFalsy();
  });

  it('no raw internal variables in rendered copy', async () => {
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    expect(document.body.textContent).not.toContain('Comparable_to_previous_value');
  });

  it('empty priority state removes inline queue and keeps claims reachable from proof surfaces', async () => {
    seedShellAuth();
    setCommandCenterTestMode('no_priority');
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    expect(document.querySelector('[data-priority-queue]')).toBeNull();
    expect(document.querySelector('[data-view-all-claims]')).toBeNull();
    expect(document.querySelector('[data-command-center-primary-action]')?.getAttribute('data-primary-action-kind')).toBe(
      'view_latest_envelope',
    );
  });
});

describe('Command Center Redesign Harness — negative controls (simulated sabotage)', () => {
  it('sabotage probes detect meaningful violations without mutating source', () => {
    const clean = [
      'data-command-center-urgency',
      'data-summary-drilldown',
      'DiscrepancyBadge',
      'VerifiedRevenueChart',
    ].join('\n');
    const sabotaged = `claimedRevenueMinor
PlatformClaimLabel
${clean
      .replace('data-command-center-urgency', '')
      .replace('data-summary-drilldown', '')}
Comparable_to_previous_value=false
priorityIssues.length`;

    const cleanProbes = runCommandCenterRedesignSabotageProbes(clean);
    const sabotagedProbes = runCommandCenterRedesignSabotageProbes(sabotaged);

    expect(cleanProbes.every((p) => !p.triggered)).toBe(true);
    expect(sabotagedProbes.filter((p) => p.triggered).map((p) => p.name)).toEqual(
      expect.arrayContaining([
        'raw-internal-variable',
        'channel-claimed-revenue-platform-claim-pill',
        'missing-urgency-marker',
      ]),
    );
  });
});
