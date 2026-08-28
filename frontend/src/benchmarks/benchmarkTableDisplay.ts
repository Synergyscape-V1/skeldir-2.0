import type { BenchmarkRowDTO } from '../ledger/types';
import { BENCHMARKS_COPY } from './copy';

export function isBenchmarkValueUnavailable(row: BenchmarkRowDTO): boolean {
  if (row.evidenceClass === 'unavailable') return true;
  if (row.benchmark.status === 'unavailable' || row.benchmark.status === 'suppressed') return true;
  if (!row.rawBenchmark && !row.decisionSafeBenchmark) return true;
  return false;
}

export function hasEstimatorTransition(row: BenchmarkRowDTO): boolean {
  return row.sourceTransition || row.comparability === 'source_changed';
}

export function resolveTableActionability(row: BenchmarkRowDTO): BenchmarkRowDTO['actionability'] {
  if (hasEstimatorTransition(row)) {
    return 'observe_only_until_stable';
  }
  return row.actionability;
}

/** Budget Simulation must not select segments during estimator transition or when blocked. */
export function canSelectBenchmarkForSimulation(row: BenchmarkRowDTO): boolean {
  if (hasEstimatorTransition(row)) return false;
  return resolveTableActionability(row) === 'simulate';
}

export function unavailableBenchmarkTooltip(): string {
  return BENCHMARKS_COPY.table.unavailableSegmentCopy;
}

export function hasVisibleSuppressionReason(row: BenchmarkRowDTO): boolean {
  if (row.suppressionReasonCode) return true;
  if (!row.suppressionReason) return false;
  return row.suppressionReason !== BENCHMARKS_COPY.table.unavailableSegmentCopy;
}

export function suppressionReasonTooltip(
  code: BenchmarkRowDTO['suppressionReasonCode'],
  fallbackReason?: string,
): string {
  if (code && BENCHMARKS_COPY.suppression.tooltips[code]) {
    return BENCHMARKS_COPY.suppression.tooltips[code];
  }
  return fallbackReason ?? BENCHMARKS_COPY.suppression.defaultTooltip;
}

export function decisionSafeAdjustmentTooltip(row: BenchmarkRowDTO): string | undefined {
  if (row.adjustmentReason) return row.adjustmentReason;
  if (hasEstimatorTransition(row)) {
    return BENCHMARKS_COPY.table.decisionSafeTransitionAdjustment;
  }
  if (row.coverageClass === 'broad' && row.rollupLevel) {
    return BENCHMARKS_COPY.table.decisionSafeRollupAdjustment(row.rollupLevel);
  }
  if (row.rawBenchmark && row.decisionSafeBenchmark && row.rawBenchmark !== row.decisionSafeBenchmark) {
    return BENCHMARKS_COPY.table.decisionSafePrivacyBlend;
  }
  return undefined;
}

export function coverageRollupTooltip(row: BenchmarkRowDTO): string | undefined {
  if (row.coverageClass !== 'broad') return undefined;
  if (row.rollupLevel) {
    return BENCHMARKS_COPY.table.rollupTooltip(row.rollupLevel);
  }
  return BENCHMARKS_COPY.table.rollupTooltipDefault;
}
