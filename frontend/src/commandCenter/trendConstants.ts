import type { TrendPoint } from './types';
import { snapshotWindowBoundsForDate } from './revenueSnapshotFixtures';

export const MIN_TREND_DAYS = 15;
export const MAX_TREND_POINTS = 61;

/** @deprecated B2.10 snapshots are authoritative — retained for legacy harness imports only. */
export function fillTrendCalendarWindow(byDay: Map<string, bigint>): TrendPoint[] {
  if (byDay.size === 0) return [];

  const sorted = [...byDay.entries()].sort(([a], [b]) => a.localeCompare(b));
  const windowDays = Math.max(MIN_TREND_DAYS, MAX_TREND_POINTS);

  return sorted.slice(-windowDays).map(([date, verifiedRevenueMinor]) => {
    const { windowStartAt, windowEndAt } = snapshotWindowBoundsForDate(date);
    return {
      windowStartAt,
      windowEndAt,
      date,
      status: verifiedRevenueMinor === 0n ? ('zero' as const) : ('available' as const),
      verifiedRevenueMinor,
      authority: 'deterministic' as const,
      sourceSurface: 'b210_revenue_snapshot' as const,
      sourceField: 'verified_revenue_minor' as const,
    };
  });
}
