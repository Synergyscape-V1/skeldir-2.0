import { describe, expect, it } from 'vitest';
import { BENCHMARKS_FIXTURES } from '../benchmarks/benchmarksFixtures';
import {
  canSelectBenchmarkForSimulation,
  hasEstimatorTransition,
  isBenchmarkValueUnavailable,
  resolveTableActionability,
} from '../benchmarks/benchmarkTableDisplay';

describe('benchmarkTableDisplay — CRHAID 1 enforcement', () => {
  const transitionRow = BENCHMARKS_FIXTURES.find(
    (row) => row.benchmarkId === 'bench_meta_paid_search_transition',
  )!;
  const suppressedRow = BENCHMARKS_FIXTURES.find((row) => row.benchmarkId === 'bench_snapchat')!;
  const simulateRow = BENCHMARKS_FIXTURES.find((row) => row.benchmarkId === 'bench_meta_paid_social')!;

  it('flags estimator transition rows', () => {
    expect(hasEstimatorTransition(transitionRow)).toBe(true);
    expect(hasEstimatorTransition(simulateRow)).toBe(false);
  });

  it('downgrades actionability during estimator transition', () => {
    expect(resolveTableActionability(transitionRow)).toBe('observe_only_until_stable');
  });

  it('blocks budget simulation selection during estimator transition', () => {
    expect(canSelectBenchmarkForSimulation(transitionRow)).toBe(false);
    expect(canSelectBenchmarkForSimulation(simulateRow)).toBe(true);
  });

  it('marks suppressed segments unavailable with explicit copy path', () => {
    expect(isBenchmarkValueUnavailable(suppressedRow)).toBe(true);
  });
});
