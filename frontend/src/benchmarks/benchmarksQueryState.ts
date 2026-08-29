import type { BenchmarksFilters } from './benchmarksClient';
import { BENCHMARK_DEFAULT_DATE_FROM, BENCHMARK_DEFAULT_DATE_TO } from './benchmarksFixtures';
import {
  BENCHMARKS_DEFAULT_PAGE_SIZE,
  BENCHMARKS_MAX_PAGE_SIZE,
  normalizeBenchmarksPageSize,
} from './benchmarksPagination';

export const ALLOWED_BENCHMARK_SORT_KEYS = ['catalogOrder', 'benchmarkName', 'lastRefreshed', 'rawBenchmark'] as const;
export const ALLOWED_BENCHMARK_EVIDENCE = [
  'live_empirical',
  'tenant_longitudinal',
  'historical_prior',
  'public_prior',
  'unavailable',
] as const;
export const ALLOWED_BENCHMARK_COVERAGE = ['exact', 'broad', 'tenant_only', 'prior', 'insufficient'] as const;
export const ALLOWED_BENCHMARK_ACTIONABILITY = ['simulate', 'observe_only_until_stable', 'blocked'] as const;

function readParam(params: URLSearchParams, key: string): string | undefined {
  const value = params.get(key);
  return value && value.length > 0 ? value : undefined;
}

function readListParam(params: URLSearchParams, key: string): string[] | undefined {
  const values = params.getAll(key);
  if (!values.length) return undefined;
  return values;
}

function isValidIsoDate(value: string): boolean {
  return /^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(Date.parse(value));
}

export function buildBenchmarksQueryKey(filters: BenchmarksFilters): string {
  return JSON.stringify({
    dateFrom: filters.dateFrom ?? null,
    dateTo: filters.dateTo ?? null,
    channelId: filters.channelId ?? null,
    platformIds: filters.platformIds ?? null,
    commerceSourceIds: filters.commerceSourceIds ?? null,
    evidenceClass: filters.evidenceClass ?? null,
    coverageClass: filters.coverageClass ?? null,
    actionability: filters.actionability ?? null,
    sortKey: filters.sortKey ?? 'catalogOrder',
    sortDirection: filters.sortDirection ?? 'asc',
    offset: filters.offset ?? 0,
    pageSize: filters.pageSize ?? BENCHMARKS_DEFAULT_PAGE_SIZE,
  });
}

export function parseBenchmarksFilters(search: string): BenchmarksFilters {
  const raw = search.startsWith('?') ? search.slice(1) : search;
  const params = new URLSearchParams(raw);

  const dateFrom = readParam(params, 'dateFrom');
  const dateTo = readParam(params, 'dateTo');
  const channelId = readParam(params, 'channelId');
  const platformIds = readListParam(params, 'platformId');
  const commerceSourceIds = readListParam(params, 'commerceSourceId');

  const evidenceClassRaw = readParam(params, 'evidenceClass');
  const evidenceClass = ALLOWED_BENCHMARK_EVIDENCE.includes(
    evidenceClassRaw as (typeof ALLOWED_BENCHMARK_EVIDENCE)[number],
  )
    ? (evidenceClassRaw as BenchmarksFilters['evidenceClass'])
    : undefined;

  const coverageClassRaw = readParam(params, 'coverageClass');
  const coverageClass = ALLOWED_BENCHMARK_COVERAGE.includes(
    coverageClassRaw as (typeof ALLOWED_BENCHMARK_COVERAGE)[number],
  )
    ? (coverageClassRaw as BenchmarksFilters['coverageClass'])
    : undefined;

  const actionabilityRaw = readParam(params, 'actionability');
  const actionability = ALLOWED_BENCHMARK_ACTIONABILITY.includes(
    actionabilityRaw as (typeof ALLOWED_BENCHMARK_ACTIONABILITY)[number],
  )
    ? (actionabilityRaw as BenchmarksFilters['actionability'])
    : undefined;

  const sortKeyRaw = readParam(params, 'sortKey') ?? 'catalogOrder';
  const sortKey = ALLOWED_BENCHMARK_SORT_KEYS.includes(sortKeyRaw as (typeof ALLOWED_BENCHMARK_SORT_KEYS)[number])
    ? sortKeyRaw
    : 'catalogOrder';

  const sortDirectionRaw = readParam(params, 'sortDirection') ?? 'asc';
  const sortDirection = sortDirectionRaw === 'desc' ? 'desc' : 'asc';

  const offsetRaw = readParam(params, 'offset');
  let offset = 0;
  if (offsetRaw) {
    const parsed = Number.parseInt(offsetRaw, 10);
    if (Number.isFinite(parsed) && parsed >= 0) offset = parsed;
  }

  const pageSizeRaw = readParam(params, 'pageSize');
  let pageSize = BENCHMARKS_DEFAULT_PAGE_SIZE;
  if (pageSizeRaw) {
    const parsed = Number.parseInt(pageSizeRaw, 10);
    if (Number.isFinite(parsed) && parsed >= 1 && parsed <= BENCHMARKS_MAX_PAGE_SIZE) {
      pageSize = normalizeBenchmarksPageSize(parsed);
    }
  }

  return {
    dateFrom: dateFrom && isValidIsoDate(dateFrom) ? dateFrom : undefined,
    dateTo: dateTo && isValidIsoDate(dateTo) ? dateTo : undefined,
    channelId,
    platformIds,
    commerceSourceIds,
    evidenceClass,
    coverageClass,
    actionability,
    sortKey,
    sortDirection: sortDirection as 'asc' | 'desc',
    offset,
    pageSize,
  };
}

export function benchmarksDefaultFilters(): BenchmarksFilters {
  return {
    dateFrom: BENCHMARK_DEFAULT_DATE_FROM,
    dateTo: BENCHMARK_DEFAULT_DATE_TO,
    platformIds: ['meta', 'google', 'email'],
    commerceSourceIds: ['shopify', 'stripe'],
    sortKey: 'catalogOrder',
    sortDirection: 'asc',
    offset: 0,
    pageSize: BENCHMARKS_DEFAULT_PAGE_SIZE,
  };
}

export function benchmarksFiltersToSearchParams(filters: BenchmarksFilters): URLSearchParams {
  const params = new URLSearchParams();
  if (filters.dateFrom) params.set('dateFrom', filters.dateFrom);
  if (filters.dateTo) params.set('dateTo', filters.dateTo);
  if (filters.channelId) params.set('channelId', filters.channelId);
  filters.platformIds?.forEach((id) => params.append('platformId', id));
  filters.commerceSourceIds?.forEach((id) => params.append('commerceSourceId', id));
  if (filters.evidenceClass) params.set('evidenceClass', filters.evidenceClass);
  if (filters.coverageClass) params.set('coverageClass', filters.coverageClass);
  if (filters.actionability) params.set('actionability', filters.actionability);
  if (filters.sortKey && filters.sortKey !== 'catalogOrder') params.set('sortKey', filters.sortKey);
  if (filters.sortDirection && filters.sortDirection !== 'asc') params.set('sortDirection', filters.sortDirection);
  if (filters.offset) params.set('offset', String(filters.offset));
  if (filters.pageSize && filters.pageSize !== BENCHMARKS_DEFAULT_PAGE_SIZE) {
    params.set('pageSize', String(filters.pageSize));
  }
  return params;
}

export function parseCanonicalBenchmarksQuery(search: string): {
  filters: BenchmarksFilters;
  canonicalSearch: string;
  isCanonical: boolean;
} {
  const parsed = parseBenchmarksFilters(search);
  const canonicalParams = benchmarksFiltersToSearchParams(parsed);
  const canonicalSearch = canonicalParams.toString();
  const raw = search.startsWith('?') ? search.slice(1) : search;
  const rawParams = new URLSearchParams(raw);
  rawParams.sort();
  const sortedRaw = [...rawParams.entries()].sort(([a], [b]) => a.localeCompare(b));
  const sortedCanonical = [...canonicalParams.entries()].sort(([a], [b]) => a.localeCompare(b));
  const isCanonical = JSON.stringify(sortedRaw) === JSON.stringify(sortedCanonical);

  return {
    filters: parsed,
    canonicalSearch: canonicalSearch ? `?${canonicalSearch}` : '',
    isCanonical,
  };
}
