import { getCurrentUserRole } from '../governance/governanceStore';
import { canViewBenchmarks } from '../ledger/permissions';
import { incrementLedgerRequest, resetLedgerRequestCounter } from '../ledger/requestCounter';
import { executeServerQuery } from '../ledger/queryEngine';
import { LEDGER_COPY } from '../ledger/copy';
import type {
  BenchmarkActionability,
  BenchmarkCoverageClass,
  BenchmarkEvidenceClass,
  BenchmarkRowDTO,
  LedgerListOutcome,
} from '../ledger/types';
import { BENCHMARKS_FIXTURES } from './benchmarksFixtures';
import { BENCHMARKS_DEFAULT_PAGE_SIZE } from './benchmarksPagination';

const CATALOG_ORDER = new Map(BENCHMARKS_FIXTURES.map((row, index) => [row.benchmarkId, index]));

export interface BenchmarksFilters {
  dateFrom?: string;
  dateTo?: string;
  channelId?: string;
  platformIds?: string[];
  commerceSourceIds?: string[];
  evidenceClass?: BenchmarkEvidenceClass;
  coverageClass?: BenchmarkCoverageClass;
  actionability?: BenchmarkActionability;
  sortKey?: string;
  sortDirection?: 'asc' | 'desc';
  offset?: number;
  pageSize?: number;
}

export interface BenchmarksClient {
  listBenchmarks(
    tenantId: string,
    filters: BenchmarksFilters,
    signal?: AbortSignal,
  ): Promise<LedgerListOutcome<BenchmarkRowDTO>>;
}

function matchesFilters(row: BenchmarkRowDTO, filters: BenchmarksFilters): boolean {
  if (filters.channelId && row.channelId !== filters.channelId) return false;
  if (filters.platformIds?.length && (!row.platformId || !filters.platformIds.includes(row.platformId))) {
    return false;
  }
  if (
    filters.commerceSourceIds?.length &&
    (!row.commerceSourceId || !filters.commerceSourceIds.includes(row.commerceSourceId))
  ) {
    return false;
  }
  if (filters.evidenceClass && row.evidenceClass !== filters.evidenceClass) return false;
  if (filters.coverageClass && row.coverageClass !== filters.coverageClass) return false;
  if (filters.actionability && row.actionability !== filters.actionability) return false;
  return true;
}

let syntheticBenchmarks = [...BENCHMARKS_FIXTURES];

export function setSyntheticBenchmarksDataset(rows: BenchmarkRowDTO[]): void {
  syntheticBenchmarks = [...rows];
}

export function resetSyntheticBenchmarksDataset(): void {
  syntheticBenchmarks = [...BENCHMARKS_FIXTURES];
}

export function createBenchmarksClient(dataset = syntheticBenchmarks): BenchmarksClient {
  return {
    async listBenchmarks(_tenantId, filters, signal) {
      if (signal?.aborted) {
        return { kind: 'network_error', message: LEDGER_COPY.trustApiError };
      }

      resetLedgerRequestCounter();
      incrementLedgerRequest('benchmarks');

      if (!canViewBenchmarks(getCurrentUserRole())) {
        return { kind: 'permission_denied', message: LEDGER_COPY.permissionDenied };
      }

      const filtered = dataset.filter((row) => matchesFilters(row, filters));
      const result = executeServerQuery<BenchmarkRowDTO>('benchmarks', {
        items: filtered,
        params: {
          ...filters,
          sortKey: filters.sortKey ?? 'catalogOrder',
          sortDirection: filters.sortDirection ?? 'asc',
          offset: filters.offset,
          pageSize: filters.pageSize ?? BENCHMARKS_DEFAULT_PAGE_SIZE,
        },
        defaultSortKey: 'catalogOrder',
        filterFn: () => true,
        getSortValue: (row, key) => {
          if (key === 'catalogOrder') return CATALOG_ORDER.get(row.benchmarkId) ?? 999;
          if (key === 'lastRefreshed') return row.lastRefreshed;
          if (key === 'rawBenchmark') return row.rawBenchmark ?? '';
          return row.benchmarkName;
        },
      });

      if ('error' in result) {
        return { kind: result.error, message: result.message } as const;
      }

      if (result.metadata.totalCount === 0) {
        const hasFilters =
          filters.channelId ||
          filters.evidenceClass ||
          filters.coverageClass ||
          filters.actionability ||
          filters.platformIds?.length ||
          filters.commerceSourceIds?.length;
        return hasFilters
          ? { kind: 'filtered_empty', rows: [], ...result.metadata }
          : { kind: 'empty', rows: [], ...result.metadata };
      }

      return { kind: 'loaded', rows: result.rows, ...result.metadata };
    },
  };
}

let defaultClient: BenchmarksClient | null = null;

export function getDefaultBenchmarksClient(): BenchmarksClient {
  if (!defaultClient) defaultClient = createBenchmarksClient();
  return defaultClient;
}

export function resetDefaultBenchmarksClient(): void {
  defaultClient = null;
}
