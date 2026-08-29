import type { ChannelBayesianStatusKey, ChannelOverviewRowDTO } from '../ledger/types';
import { CHANNEL_INLINE_COPY } from './channelInlineCopy';

export type ChannelDataReliability = 'verified' | 'estimated' | 'pending';

export function resolveChannelDataReliability(row: ChannelOverviewRowDTO): ChannelDataReliability {
  if (row.confidence.status === 'unavailable' || row.bayesianStatusKey === 'degraded') {
    return 'estimated';
  }
  if (row.bayesianStatusKey === 'delayed' || row.bayesianStatusKey === 'low_confidence') {
    return 'pending';
  }
  if (row.bayesianStatusKey === 'healthy' && row.confidence.status === 'available') {
    return 'verified';
  }
  return 'estimated';
}

export function channelReliabilityLabel(reliability: ChannelDataReliability): string {
  if (reliability === 'verified') return CHANNEL_INLINE_COPY.reliability.verified;
  if (reliability === 'pending') return CHANNEL_INLINE_COPY.reliability.pending;
  return CHANNEL_INLINE_COPY.reliability.estimated;
}

export function channelReliabilityExplanation(reliability: ChannelDataReliability): string {
  if (reliability === 'verified') return CHANNEL_INLINE_COPY.confidence.verifiedExplain;
  if (reliability === 'pending') return CHANNEL_INLINE_COPY.confidence.pendingExplain;
  return CHANNEL_INLINE_COPY.confidence.estimatedExplain;
}

export function channelBenchmarkSentence(row: ChannelOverviewRowDTO): string {
  if (row.benchmark.status === 'unavailable' || row.benchmarkStatusKey === 'unavailable') {
    return CHANNEL_INLINE_COPY.benchmark.unavailable;
  }
  const position = row.benchmarkPositionLabel?.trim();
  if (position) return `${CHANNEL_INLINE_COPY.benchmark.prefix}: ${position}`;
  if (row.benchmark.decisionSafeBenchmark) {
    return `${CHANNEL_INLINE_COPY.benchmark.prefix}: ${row.benchmark.decisionSafeBenchmark}`;
  }
  return CHANNEL_INLINE_COPY.benchmark.unavailable;
}

export function channelDiscrepancyMinor(row: ChannelOverviewRowDTO): bigint {
  return row.verifiedRevenueMinor - row.claimedRevenueMinor;
}

/** Fail-closed: unknown bayesian keys never silently map to Verified. */
export function isKnownBayesianStatusKey(value: string): value is ChannelBayesianStatusKey {
  return (
    value === 'healthy' ||
    value === 'unavailable' ||
    value === 'delayed' ||
    value === 'low_confidence' ||
    value === 'degraded'
  );
}
