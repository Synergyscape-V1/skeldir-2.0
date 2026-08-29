import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { beforeEach, describe, expect, it } from 'vitest';
import {
  buildReferenceTrendPoints,
  buildVerifiedRevenueChartGeometry,
} from '../components/commandCenter/VerifiedRevenueChart/verifiedRevenueChartGeometry';
import {
  B210_UNAVAILABLE_SNAPSHOT_DATE,
  B210_ZERO_SNAPSHOT_DATE,
  buildB210RevenueSnapshotSeries,
} from '../commandCenter/revenueSnapshotFixtures';
import { getDefaultCommandCenterClient } from '../commandCenter/commandCenterClient';
import { createMockTenant } from '../auth/authClient';
import { resetLevel10HarnessState, seedShellAuth, renderCommandCenter, waitForCommandCenterLoaded } from './level10.helpers';

const ROOT = join(import.meta.dirname, '..', '..');

function readClientSource() {
  return readFileSync(join(ROOT, 'src/commandCenter/commandCenterClient.ts'), 'utf8');
}

beforeEach(() => {
  resetLevel10HarnessState();
});

describe('Verified Revenue Trend CRHAID harness', () => {
  it('positive control: trend loads from B2.10 snapshot client, not claims aggregation', async () => {
    const client = getDefaultCommandCenterClient();
    const outcome = await client.fetchAggregate(createMockTenant().tenantId);
    expect(outcome.kind).toBe('loaded');
    if (outcome.kind !== 'loaded') return;
    expect(outcome.aggregate.sourceTrace.trend).toBe('b210_revenue_snapshots');
    expect(outcome.aggregate.trendPoints[0]?.sourceSurface).toBe('b210_revenue_snapshot');
    expect(readClientSource()).not.toContain('buildTrendFromClaims');
    expect(readClientSource()).not.toContain('fetchClaimsForTrend');
  });

  it('positive control: missing snapshot breaks the line and renders gap marker', () => {
    const geometry = buildVerifiedRevenueChartGeometry(buildReferenceTrendPoints());
    expect(geometry.lineSegments.length).toBeGreaterThan(1);
    expect(geometry.gapMarkers.some((marker) => marker.point.date === B210_UNAVAILABLE_SNAPSHOT_DATE)).toBe(
      true,
    );
  });

  it('positive control: zero-claims snapshot remains visible at baseline', () => {
    const geometry = buildVerifiedRevenueChartGeometry(buildReferenceTrendPoints());
    const zeroCoord = geometry.coords.find((coord) => coord.point.date === B210_ZERO_SNAPSHOT_DATE);
    expect(zeroCoord?.point.status).toBe('zero');
    expect(zeroCoord?.point.verifiedRevenueMinor).toBe(0n);
    const zeroTick = geometry.yTicks.find((tick) => tick.label === '0K');
    expect(zeroCoord?.y).toBe(zeroTick?.y);
  });

  it('positive control: platform claim overlay sits materially above verified revenue', () => {
    const points = buildB210RevenueSnapshotSeries().filter(
      (point) => point.status === 'available' && point.claimedRevenueMinor != null,
    );
    expect(points.length).toBeGreaterThan(10);
    for (const point of points) {
      const verified = Number(point.verifiedRevenueMinor);
      const claimed = Number(point.claimedRevenueMinor!);
      const gapBps = ((claimed - verified) / verified) * 10_000;
      expect(gapBps).toBeGreaterThanOrEqual(650);
      expect(gapBps).toBeLessThanOrEqual(1_700);
    }
    const geometry = buildVerifiedRevenueChartGeometry(buildReferenceTrendPoints());
    expect(geometry.claimedLineSegments.length).toBeGreaterThan(0);
  });

  it('positive control: benchmark bps stay off-chart and out of card header', async () => {
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    expect(document.querySelector('[data-trend-benchmark-header]')).toBeFalsy();
    expect(document.querySelector('[data-trend-claimed-line-segment]')).toBeTruthy();
    const chart = document.querySelector('[data-verified-revenue-chart]');
    expect(chart?.textContent).not.toMatch(/%|bps/);
  });

  it('negative control: sabotaged single-segment line across gap fails segment count', () => {
    const geometry = buildVerifiedRevenueChartGeometry(buildReferenceTrendPoints());
    const sabotagedSegmentCount = 1;
    expect(geometry.lineSegments.length).toBeGreaterThan(sabotagedSegmentCount);
  });

  it('meta-negative control: claims-ledger trend source is absent from client', () => {
    const source = readClientSource();
    expect(source.includes("trend: 'claims_ledger'")).toBe(false);
  });
});
