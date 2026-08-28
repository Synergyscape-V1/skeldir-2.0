import type { TrendPoint } from './types';
import { buildDailyVerifiedRevenueMinor } from './trendSyntheticData';
import {
  TREND_CHART_REFERENCE_DAY_COUNT,
  TREND_CHART_REFERENCE_END,
  TREND_CHART_REFERENCE_START,
  addUtcDays,
  formatIsoDateUtc,
  parseIsoDateUtc,
} from '../components/commandCenter/VerifiedRevenueChart/verifiedRevenueChartGeometry';

/** B2.10 pre-calculated snapshot cadence — must match backend window computation. */
export const B210_SNAPSHOT_CADENCE_HOURS = 24;

/** Demonstration gap: snapshot computation failed — line must break. */
export const B210_UNAVAILABLE_SNAPSHOT_DATE = '2026-06-10';

/** Demonstration zero-claims window — plotted at $0.00 baseline. */
export const B210_ZERO_SNAPSHOT_DATE = '2026-05-25';

/** Header benchmark context — average platform over-claim for the trend window. */
export const B210_CLAIMED_DISCREPANCY_BPS_BASE = 940;

/**
 * Derive platform-claimed revenue above verified truth with day-level texture.
 * Claims track the macro trend but stay materially higher (never lockstep).
 */
export function buildPlatformClaimedRevenueMinor(
  verifiedRevenueMinor: bigint,
  dayIndex: number,
): bigint {
  const bps =
    B210_CLAIMED_DISCREPANCY_BPS_BASE +
    (dayIndex % 7) * 55 -
    (dayIndex % 5) * 40 +
    (dayIndex % 3) * 32;
  const effectiveBps = Math.max(820, Math.min(1380, bps));
  const benchmarkDelta = (verifiedRevenueMinor * BigInt(effectiveBps)) / 10000n;
  const claimRipple = (benchmarkDelta * BigInt((dayIndex % 5) - 2)) / 10n;
  return verifiedRevenueMinor + benchmarkDelta + claimRipple;
}

export function snapshotWindowBoundsForDate(dateIso: string): {
  windowStartAt: string;
  windowEndAt: string;
} {
  const start = parseIsoDateUtc(dateIso);
  const end = addUtcDays(start, 1);
  return {
    windowStartAt: start.toISOString(),
    windowEndAt: end.toISOString(),
  };
}

function buildSnapshotPoint(
  dateIso: string,
  dayIndex: number,
  status: TrendPoint['status'],
  unavailableReason?: string,
): TrendPoint {
  const { windowStartAt, windowEndAt } = snapshotWindowBoundsForDate(dateIso);
  const verifiedRevenueMinor =
    status === 'unavailable' ? 0n : status === 'zero' ? 0n : buildDailyVerifiedRevenueMinor(dayIndex);
  const claimedRevenueMinor =
    status === 'available' && verifiedRevenueMinor > 0n
      ? buildPlatformClaimedRevenueMinor(verifiedRevenueMinor, dayIndex)
      : undefined;

  return {
    windowStartAt,
    windowEndAt,
    date: dateIso,
    status,
    verifiedRevenueMinor,
    authority: 'deterministic',
    sourceSurface: 'b210_revenue_snapshot',
    sourceField: 'verified_revenue_minor',
    unavailableReason,
    claimedRevenueMinor,
  };
}

/** Canonical B2.10 snapshot series for the Command Center trend window. */
export function buildB210RevenueSnapshotSeries(): TrendPoint[] {
  const start = parseIsoDateUtc(TREND_CHART_REFERENCE_START);
  return Array.from({ length: TREND_CHART_REFERENCE_DAY_COUNT }, (_, dayIndex) => {
    const dateIso = formatIsoDateUtc(addUtcDays(start, dayIndex));
    if (dateIso === B210_UNAVAILABLE_SNAPSHOT_DATE) {
      return buildSnapshotPoint(
        dateIso,
        dayIndex,
        'unavailable',
        'Window computation timed out',
      );
    }
    if (dateIso === B210_ZERO_SNAPSHOT_DATE) {
      return buildSnapshotPoint(dateIso, dayIndex, 'zero');
    }
    return buildSnapshotPoint(dateIso, dayIndex, 'available');
  });
}

/** Minimal snapshot point for harness overrides. */
export function makeTrendPointFixture(
  overrides: Partial<TrendPoint> & Pick<TrendPoint, 'date' | 'verifiedRevenueMinor'>,
): TrendPoint {
  const { windowStartAt, windowEndAt } = snapshotWindowBoundsForDate(overrides.date);
  const status =
    overrides.status ?? (overrides.verifiedRevenueMinor === 0n ? 'zero' : 'available');
  return {
    authority: 'deterministic',
    sourceSurface: 'b210_revenue_snapshot',
    sourceField: 'verified_revenue_minor',
    ...overrides,
    windowStartAt,
    windowEndAt,
    status,
  };
}

export function buildB210RevenueSnapshotSeriesRange(
  startIso: string = TREND_CHART_REFERENCE_START,
  endIso: string = TREND_CHART_REFERENCE_END,
): TrendPoint[] {
  return buildB210RevenueSnapshotSeries().filter(
    (point) => point.date >= startIso && point.date <= endIso,
  );
}
