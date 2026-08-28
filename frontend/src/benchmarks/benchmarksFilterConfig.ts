import type { BenchmarksFilters } from './benchmarksClient';
import {
  BENCHMARK_ACTIONABILITY_OPTIONS,
  BENCHMARK_CHANNEL_OPTIONS,
  BENCHMARK_COMMERCE_OPTIONS,
  BENCHMARK_COVERAGE_OPTIONS,
  BENCHMARK_DEFAULT_DATE_FROM,
  BENCHMARK_DEFAULT_DATE_TO,
  BENCHMARK_EVIDENCE_OPTIONS,
  BENCHMARK_PLATFORM_OPTIONS,
} from './benchmarksFixtures';
import { BENCHMARKS_COPY } from './copy';
import type {
  BenchmarkActionability,
  BenchmarkCoverageClass,
  BenchmarkEvidenceClass,
} from '../ledger/types';

export type BenchmarkFilterChipKey =
  | 'dateRange'
  | 'channel'
  | 'platform'
  | 'commerceSource'
  | 'evidenceClass'
  | 'coverageClass'
  | 'actionability';

export interface BenchmarkFilterChip {
  key: BenchmarkFilterChipKey;
  label: string;
}

function labelFor<T extends { id: string; label: string }>(options: readonly T[], id?: string): string | undefined {
  if (!id) return undefined;
  return options.find((option) => option.id === id)?.label ?? id;
}

export function buildActiveBenchmarkFilterChips(filters: BenchmarksFilters): BenchmarkFilterChip[] {
  const chips: BenchmarkFilterChip[] = [];

  if (filters.dateFrom === BENCHMARK_DEFAULT_DATE_FROM && filters.dateTo === BENCHMARK_DEFAULT_DATE_TO) {
    chips.push({ key: 'dateRange', label: 'Q2 2026' });
  } else if (filters.dateFrom || filters.dateTo) {
    chips.push({
      key: 'dateRange',
      label: `${filters.dateFrom ?? '…'} – ${filters.dateTo ?? '…'}`,
    });
  }

  if (filters.platformIds?.length) {
    for (const platformId of filters.platformIds) {
      const label = labelFor(BENCHMARK_PLATFORM_OPTIONS, platformId);
      if (label) chips.push({ key: 'platform', label });
    }
  }

  if (filters.commerceSourceIds?.length) {
    for (const commerceSourceId of filters.commerceSourceIds) {
      const label = labelFor(BENCHMARK_COMMERCE_OPTIONS, commerceSourceId);
      if (label) chips.push({ key: 'commerceSource', label });
    }
  }

  if (filters.channelId) {
    const label = labelFor(BENCHMARK_CHANNEL_OPTIONS, filters.channelId);
    if (label) chips.push({ key: 'channel', label });
  }

  if (filters.evidenceClass) {
    const label = labelFor(BENCHMARK_EVIDENCE_OPTIONS, filters.evidenceClass);
    if (label) chips.push({ key: 'evidenceClass', label });
  }

  if (filters.coverageClass) {
    const label = labelFor(BENCHMARK_COVERAGE_OPTIONS, filters.coverageClass);
    if (label) chips.push({ key: 'coverageClass', label });
  }

  if (filters.actionability) {
    const label = labelFor(BENCHMARK_ACTIONABILITY_OPTIONS, filters.actionability);
    if (label) chips.push({ key: 'actionability', label });
  }

  return chips;
}

export function hasActiveBenchmarkFilters(filters: BenchmarksFilters): boolean {
  return buildActiveBenchmarkFilterChips(filters).length > 0;
}

export function clearBenchmarkFilterChip(
  filters: BenchmarksFilters,
  chipKey: BenchmarkFilterChipKey,
  chipLabel?: string,
): BenchmarksFilters {
  switch (chipKey) {
    case 'dateRange':
      return { ...filters, dateFrom: undefined, dateTo: undefined, offset: 0 };
    case 'channel':
      return { ...filters, channelId: undefined, offset: 0 };
    case 'platform':
      if (!chipLabel) return { ...filters, platformIds: undefined, offset: 0 };
      return {
        ...filters,
        platformIds: filters.platformIds?.filter(
          (id) => labelFor(BENCHMARK_PLATFORM_OPTIONS, id) !== chipLabel,
        ),
        offset: 0,
      };
    case 'commerceSource':
      if (!chipLabel) return { ...filters, commerceSourceIds: undefined, offset: 0 };
      return {
        ...filters,
        commerceSourceIds: filters.commerceSourceIds?.filter(
          (id) => labelFor(BENCHMARK_COMMERCE_OPTIONS, id) !== chipLabel,
        ),
        offset: 0,
      };
    case 'evidenceClass':
      return { ...filters, evidenceClass: undefined, offset: 0 };
    case 'coverageClass':
      return { ...filters, coverageClass: undefined, offset: 0 };
    case 'actionability':
      return { ...filters, actionability: undefined, offset: 0 };
    default:
      return filters;
  }
}

export const BENCHMARK_FILTER_LABELS = {
  evidenceClass: Object.fromEntries(BENCHMARK_EVIDENCE_OPTIONS.map((o) => [o.id, o.label])) as Record<
    BenchmarkEvidenceClass,
    string
  >,
  coverageClass: Object.fromEntries(BENCHMARK_COVERAGE_OPTIONS.map((o) => [o.id, o.label])) as Record<
    BenchmarkCoverageClass,
    string
  >,
  actionability: Object.fromEntries(BENCHMARK_ACTIONABILITY_OPTIONS.map((o) => [o.id, o.label])) as Record<
    BenchmarkActionability,
    string
  >,
  platformDisplay: (ids?: string[]) => {
    if (!ids?.length) return BENCHMARKS_COPY.filters.allPlatforms;
    if (ids.length === 1) return labelFor(BENCHMARK_PLATFORM_OPTIONS, ids[0]) ?? ids[0];
    return ids.map((id) => labelFor(BENCHMARK_PLATFORM_OPTIONS, id) ?? id).join(', ');
  },
  commerceDisplay: (ids?: string[]) => {
    if (!ids?.length) return BENCHMARKS_COPY.filters.allCommerceSources;
    if (ids.length === 1) return labelFor(BENCHMARK_COMMERCE_OPTIONS, ids[0]) ?? ids[0];
    return ids.map((id) => labelFor(BENCHMARK_COMMERCE_OPTIONS, id) ?? id).join(' + ');
  },
};
