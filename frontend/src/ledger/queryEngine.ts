import { DEFAULT_PAGE_SIZE, MAX_DOM_TABLE_ROWS, normalizePageWindow } from '../operationalAudit/pagination';
import type { LedgerPageParams, LedgerQueryMetadata } from './types';

export interface QueryEngineOptions<T> {
  items: T[];
  params: LedgerPageParams & { filters?: Record<string, string | undefined> };
  defaultSortKey: string;
  filterFn?: (item: T, filters: Record<string, string | undefined>, search?: string) => boolean;
  sortFn?: (a: T, b: T, key: string, direction: 'asc' | 'desc') => number;
  getSortValue?: (item: T, key: string) => string | number;
}

const VALID_SORT_KEYS = new Set([
  'date',
  'lastUpdated',
  'generationTimestamp',
  'createdAt',
  'lastRefreshed',
  'discrepancy',
  'discrepancyRateBps',
  'verificationStatus',
  'severity',
  'segmentName',
  'benchmarkName',
  'rawBenchmark',
  'catalogOrder',
  'channelName',
  'attributionChannel',
  'claimSource',
  'campaignClass',
  'commerceRail',
  'verifiedRevenue',
  'claimedRevenue',
  'attributionAgreement',
  'bayesianStatus',
  'benchmarkStatus',
  'policyAuthority',
  'trust_envelope_priority',
  'claimTime',
  'matchVerdict',
]);

export function createQueryId(
  surface: string,
  params: LedgerPageParams & { filters?: Record<string, string | undefined> },
): string {
  const payload = JSON.stringify({
    surface,
    offset: params.offset ?? 0,
    pageSize: params.pageSize ?? DEFAULT_PAGE_SIZE,
    sortKey: params.sortKey,
    sortDirection: params.sortDirection,
    search: params.search,
    filters: params.filters,
  });
  let hash = 0;
  for (let i = 0; i < payload.length; i++) {
    hash = (hash << 5) - hash + payload.charCodeAt(i);
    hash |= 0;
  }
  return `q_${surface}_${Math.abs(hash).toString(36)}`;
}

export type QueryEngineResult<T> =
  | { error: 'sort_invalid'; message: string }
  | { rows: T[]; metadata: LedgerQueryMetadata; cappedPageSize: boolean };

export function executeServerQuery<T>(surface: string, options: QueryEngineOptions<T>): QueryEngineResult<T> {
  const { items, params, defaultSortKey, filterFn, sortFn, getSortValue } = options;
  const { pageSize, offset } = normalizePageWindow({
    pageSize: params.pageSize,
    offset: params.offset,
  });

  const sortKey = params.sortKey ?? defaultSortKey;
  const sortDirection = params.sortDirection ?? 'desc';

  if (params.sortKey && !VALID_SORT_KEYS.has(params.sortKey)) {
    return { error: 'sort_invalid' as const, message: `Invalid sort key: ${params.sortKey}` };
  }

  const filters = params.filters ?? {};
  let working = [...items];

  if (filterFn) {
    working = working.filter((item) => filterFn(item, filters, params.search));
  } else if (params.search?.trim()) {
    const q = params.search.trim().toLowerCase();
    working = working.filter((item) => JSON.stringify(item).toLowerCase().includes(q));
  }

  const comparator =
    sortFn ??
    ((a, b, key, dir) => {
      const av = getSortValue ? getSortValue(a, key) : '';
      const bv = getSortValue ? getSortValue(b, key) : '';
      if (av < bv) return dir === 'asc' ? -1 : 1;
      if (av > bv) return dir === 'asc' ? 1 : -1;
      return 0;
    });

  working.sort((a, b) => comparator(a, b, sortKey, sortDirection));

  const totalCount = working.length;
  const rows = working.slice(offset, offset + pageSize);
  const hasMore = offset + rows.length < totalCount;

  const metadata: LedgerQueryMetadata = {
    pageSize,
    offset,
    totalCount,
    hasMore,
    appliedFilters: filters,
    appliedSort: { key: sortKey, direction: sortDirection },
    stableSortKey: `${sortKey}:${sortDirection}`,
    queryId: createQueryId(surface, params),
  };

  return { rows, metadata, cappedPageSize: pageSize <= MAX_DOM_TABLE_ROWS };
}

export function createSyntheticDataset<T>(factory: (index: number) => T, count: number): T[] {
  return Array.from({ length: count }, (_, i) => factory(i));
}
