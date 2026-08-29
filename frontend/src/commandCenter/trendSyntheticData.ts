/** Synthetic trend totals for claims fixtures — kept out of chart geometry to avoid client import cycles. */

export const VERIFIED_REVENUE_AXIS_MIN_MINOR = 1_000_000n;
export const VERIFIED_REVENUE_AXIS_MAX_MINOR = 4_000_000n;

const VERIFIED_REVENUE_TREND_KNOTS: ReadonlyArray<{ day: number; minor: bigint }> = [
  { day: 0, minor: 1_050_000n },
  { day: 7, minor: 1_360_000n },
  { day: 14, minor: 1_440_000n },
  { day: 18, minor: 1_430_000n },
  { day: 22, minor: 1_270_000n },
  { day: 28, minor: 1_700_000n },
  { day: 35, minor: 2_140_000n },
  { day: 42, minor: 2_090_000n },
  { day: 48, minor: 2_060_000n },
  { day: 51, minor: 2_358_000n },
  { day: 54, minor: 2_655_000n },
  { day: 57, minor: 2_953_000n },
  { day: 60, minor: 3_250_000n },
];

export function interpolateVerifiedRevenueTrendMinor(dayIndex: number): bigint {
  const clampedDay = Math.max(0, Math.min(dayIndex, VERIFIED_REVENUE_TREND_KNOTS.at(-1)!.day));

  for (let index = 0; index < VERIFIED_REVENUE_TREND_KNOTS.length - 1; index += 1) {
    const left = VERIFIED_REVENUE_TREND_KNOTS[index]!;
    const right = VERIFIED_REVENUE_TREND_KNOTS[index + 1]!;
    if (clampedDay < left.day || clampedDay > right.day) continue;

    const span = right.day - left.day;
    if (span === 0) return left.minor;

    const offset = clampedDay - left.day;
    const delta = right.minor - left.minor;
    return left.minor + (delta * BigInt(offset)) / BigInt(span);
  }

  return VERIFIED_REVENUE_TREND_KNOTS.at(-1)!.minor;
}

function buildDailyVerifiedRevenueRippleMinor(dayIndex: number): bigint {
  const rippleMagnitude =
    BigInt(dayIndex % 7) * 8_000n +
    BigInt(dayIndex % 5) * 5_000n +
    BigInt(dayIndex % 3) * 3_000n;
  const rippleSign = dayIndex % 2 === 0 ? 1n : -1n;
  const microWobble = dayIndex % 4 === 0 ? 12_000n : -10_000n;
  return rippleSign * rippleMagnitude + microWobble;
}

/** Deterministic daily total — uneven macro trend plus gentle day-level angular ripple. */
export function buildDailyVerifiedRevenueMinor(dayIndex: number): bigint {
  const trendBase = interpolateVerifiedRevenueTrendMinor(dayIndex);
  const value = trendBase + buildDailyVerifiedRevenueRippleMinor(dayIndex);
  const min = VERIFIED_REVENUE_AXIS_MIN_MINOR;
  const max = VERIFIED_REVENUE_AXIS_MAX_MINOR - 50_000n;
  if (value < min) return min;
  if (value > max) return max;
  return value;
}
