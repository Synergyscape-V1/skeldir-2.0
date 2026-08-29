import type { TrendPoint } from './types';

export function formatTrendWindowLabel(point: TrendPoint): string {
  const start = new Date(point.windowStartAt);
  const month = start.toLocaleString('en-US', { month: 'short', timeZone: 'UTC' });
  const day = start.getUTCDate();
  return `${month} ${day} Window`;
}

export function buildTrendDrillDownHref(point: TrendPoint): string {
  const params = new URLSearchParams();
  params.set('dateFrom', point.date);
  params.set('dateTo', point.date);
  params.set('windowStart', point.windowStartAt);
  params.set('windowEnd', point.windowEndAt);
  params.set('trendDrill', '1');
  params.set('trendWindowLabel', formatTrendWindowLabel(point));
  return `/app/claims?${params.toString()}`;
}
