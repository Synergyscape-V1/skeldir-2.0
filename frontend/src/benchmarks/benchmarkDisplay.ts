import type {
  BenchmarkActionability,
  BenchmarkCoverageClass,
  BenchmarkEvidenceClass,
  BenchmarkRowDTO,
} from '../ledger/types';
import {
  BENCHMARK_ACTIONABILITY_OPTIONS,
  BENCHMARK_COVERAGE_OPTIONS,
  BENCHMARK_EVIDENCE_OPTIONS,
} from './benchmarksFixtures';

export function evidenceClassLabel(value: BenchmarkEvidenceClass | string): string {
  return BENCHMARK_EVIDENCE_OPTIONS.find((option) => option.id === value)?.label ?? 'Invalid evidence class';
}

export function coverageClassLabel(value: BenchmarkCoverageClass | string): string {
  const raw =
    BENCHMARK_COVERAGE_OPTIONS.find((option) => option.id === value)?.label ?? 'Invalid coverage class';
  if (raw.startsWith('Invalid')) return raw;
  const readable = raw.replace(/_/g, ' ');
  return readable.charAt(0).toUpperCase() + readable.slice(1);
}

export function actionabilityLabel(value: BenchmarkActionability | string): string {
  const raw =
    BENCHMARK_ACTIONABILITY_OPTIONS.find((option) => option.id === value)?.label ??
    'Invalid actionability state';
  if (raw.startsWith('Invalid')) return raw;
  const readable = raw.replace(/_/g, ' ');
  return readable.charAt(0).toUpperCase() + readable.slice(1);
}

export function comparabilityLabel(value: BenchmarkRowDTO['comparability']): string {
  switch (value) {
    case 'comparable':
      return 'Comparable';
    case 'not_comparable':
      return 'Not comparable';
    case 'source_changed':
      return 'Source changed';
    case 'unavailable':
      return 'Unavailable';
    default:
      return 'Invalid comparability state';
  }
}

export function formatBenchmarkValue(value?: string): string {
  if (!value) return 'N/A';
  return value;
}

export function minutesSinceRefresh(iso: string): number {
  const delta = Date.now() - Date.parse(iso);
  if (!Number.isFinite(delta) || delta < 0) return 0;
  return Math.max(1, Math.round(delta / 60_000));
}

export function isValidEvidenceClass(value: string): value is BenchmarkEvidenceClass {
  return BENCHMARK_EVIDENCE_OPTIONS.some((option) => option.id === value);
}

export function isValidCoverageClass(value: string): value is BenchmarkCoverageClass {
  return BENCHMARK_COVERAGE_OPTIONS.some((option) => option.id === value);
}

export function isValidActionability(value: string): value is BenchmarkActionability {
  return BENCHMARK_ACTIONABILITY_OPTIONS.some((option) => option.id === value);
}
