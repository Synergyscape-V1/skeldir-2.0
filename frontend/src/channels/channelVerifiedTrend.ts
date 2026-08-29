import type { ChannelInlineTrendPoint } from './channelInlineFixtures';
import { CHANNEL_INLINE_COPY } from './channelInlineCopy';
import { formatBpsAsPercentOneDecimal } from '../lib/money';

/** Honest bar height percent — no artificial floor. Zero → 0 (caller may render hairline). */
export function channelTrendBarHeightPct(valueMinor: bigint, maxMinor: bigint): number {
  if (maxMinor <= 0n || valueMinor <= 0n) return 0;
  return Number((valueMinor * 100n) / maxMinor);
}

export function channelTrendMaxMinor(points: ChannelInlineTrendPoint[]): bigint {
  return points.reduce(
    (acc, point) => (point.verifiedRevenueMinor > acc ? point.verifiedRevenueMinor : acc),
    0n,
  );
}

export type ChannelTrendYTickKey = 'max' | 'mid' | 'zero';

export interface ChannelTrendYTick {
  key: ChannelTrendYTickKey;
  valueMinor: bigint;
}

/** Exactly 0 / mid / max — domain matches bar scale (no nice-rounding). */
export function channelTrendYTicks(maxMinor: bigint): ChannelTrendYTick[] {
  if (maxMinor <= 0n) {
    return [{ key: 'zero', valueMinor: 0n }];
  }
  const ticks: ChannelTrendYTick[] = [
    { key: 'max', valueMinor: maxMinor },
    { key: 'mid', valueMinor: maxMinor / 2n },
    { key: 'zero', valueMinor: 0n },
  ];
  const seen = new Set<string>();
  return ticks.filter((tick) => {
    const id = tick.valueMinor.toString();
    if (seen.has(id)) return false;
    seen.add(id);
    return true;
  });
}


/** Map fixture codes like W1 → Wk 1 for display. */
export function channelTrendPeriodLabel(period: string): string {
  const match = /^W(\d+)$/i.exec(period.trim());
  if (match) return `Wk ${match[1]}`;
  return period;
}

export type ChannelTrendDeltaTone = 'success' | 'error' | 'neutral';

export interface ChannelTrendDelta {
  label: string;
  tone: ChannelTrendDeltaTone;
  /** Signed change in basis points vs prior period; null when undefined. */
  changeBps: number | null;
}

/**
 * Week-over-week change from integer minor units.
 * Bps = ((current - prior) * 10000) / prior — no float money math.
 */
export function channelTrendDeltaVsPrior(
  currentMinor: bigint,
  priorMinor: bigint | null,
): ChannelTrendDelta {
  if (priorMinor === null) {
    return { label: CHANNEL_INLINE_COPY.trend.deltaFirst, tone: 'neutral', changeBps: null };
  }
  if (priorMinor === 0n) {
    if (currentMinor === 0n) {
      return { label: CHANNEL_INLINE_COPY.trend.deltaFlat, tone: 'neutral', changeBps: 0 };
    }
    return { label: CHANNEL_INLINE_COPY.trend.deltaFromZero, tone: 'success', changeBps: null };
  }
  const changeBps = Number(((currentMinor - priorMinor) * 10000n) / priorMinor);
  if (changeBps === 0) {
    return { label: CHANNEL_INLINE_COPY.trend.deltaFlat, tone: 'neutral', changeBps: 0 };
  }
  const absLabel = formatBpsAsPercentOneDecimal(Math.abs(changeBps));
  if (changeBps > 0) {
    return {
      label: CHANNEL_INLINE_COPY.trend.deltaUp(absLabel),
      tone: 'success',
      changeBps,
    };
  }
  return {
    label: CHANNEL_INLINE_COPY.trend.deltaDown(absLabel),
    tone: 'error',
    changeBps,
  };
}
