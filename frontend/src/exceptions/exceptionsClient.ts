import { getCurrentUserRole } from '../governance/governanceStore';
import { canViewExceptions } from '../ledger/permissions';
import { incrementLedgerRequest, resetLedgerRequestCounter } from '../ledger/requestCounter';
import { executeServerQuery } from '../ledger/queryEngine';
import { LEDGER_COPY } from '../ledger/copy';
import type {
  ExceptionCategory,
  ExceptionCategoryCounts,
  ExceptionOverviewSummary,
  ExceptionQueueRowDTO,
  ExceptionSeverity,
  LedgerListOutcome,
} from '../ledger/types';
import type { PolicyAuthorityState } from '../lib/types';
import {
  matchesPolicyAuthorityFilter,
  matchesSourceObjectFilter,
} from './exceptionsFilterConfig';
import { CANONICAL_EXCEPTION_FIXTURES } from './exceptionsFixtures';
import {
  computeExceptionCategoryCounts,
  computeExceptionOverviewSummary,
} from './exceptionsSummary';
import { filterMarketerVisibleExceptions } from '../benchmarks/benchmarkMarketingVisibility';

export interface ExceptionsFilters {
  dateFrom?: string;
  dateTo?: string;
  category?: ExceptionCategory | 'all';
  severity?: ExceptionSeverity | 'all';
  status?: ExceptionQueueRowDTO['status'] | 'all';
  policyAuthority?: PolicyAuthorityState | 'all';
  sourceObject?: string | 'all';
  search?: string;
  sortKey?: string;
  sortDirection?: 'asc' | 'desc';
  offset?: number;
  pageSize?: number;
}

export type ExceptionsListResult = LedgerListOutcome<ExceptionQueueRowDTO>;

export type ExceptionsListOutcome = ExceptionsListResult & {
  summary?: ExceptionOverviewSummary;
  categoryCounts?: ExceptionCategoryCounts;
};

export interface ExceptionsClient {
  listExceptions(
    tenantId: string,
    filters: ExceptionsFilters,
    signal?: AbortSignal,
  ): Promise<ExceptionsListOutcome>;
}

const SEVERITY_RANK: Record<ExceptionSeverity, number> = {
  critical: 0,
  warning: 1,
  info: 2,
};

function matchesSearch(row: ExceptionQueueRowDTO, search?: string): boolean {
  if (!search?.trim()) return true;
  const needle = search.trim().toLowerCase();
  return [
    row.exceptionId,
    row.summary,
    row.affectedObjectLabel,
    row.auditReference,
    row.lastAuditEvent,
    row.subject,
    row.source,
  ].some((value) => value.toLowerCase().includes(needle));
}

function matchesDateRange(row: ExceptionQueueRowDTO, dateFrom?: string, dateTo?: string): boolean {
  if (!dateFrom && !dateTo) return true;
  const created = new Date(row.createdAt).getTime();
  if (Number.isNaN(created)) return false;
  if (dateFrom) {
    const from = new Date(`${dateFrom}T00:00:00.000Z`).getTime();
    if (created < from) return false;
  }
  if (dateTo) {
    const to = new Date(`${dateTo}T23:59:59.999Z`).getTime();
    if (created > to) return false;
  }
  return true;
}

export function createExceptionsClient(dataset = CANONICAL_EXCEPTION_FIXTURES): ExceptionsClient {
  return {
    async listExceptions(_tenantId, filters) {
      resetLedgerRequestCounter();
      incrementLedgerRequest('exceptions');
      if (!canViewExceptions(getCurrentUserRole())) {
        return { kind: 'permission_denied', message: LEDGER_COPY.permissionDenied };
      }

      const marketerDataset = filterMarketerVisibleExceptions(dataset);
      const summary = computeExceptionOverviewSummary(marketerDataset);
      const categoryCounts = computeExceptionCategoryCounts(marketerDataset);

      const result = executeServerQuery<ExceptionQueueRowDTO>('exceptions', {
        items: marketerDataset,
        params: {
          ...filters,
          filters: {
            category: filters.category && filters.category !== 'all' ? filters.category : undefined,
            severity: filters.severity && filters.severity !== 'all' ? filters.severity : undefined,
            status: filters.status && filters.status !== 'all' ? filters.status : undefined,
          },
          search: filters.search,
          sortKey: filters.sortKey ?? 'createdAt',
          sortDirection: filters.sortDirection ?? 'desc',
          offset: filters.offset,
          pageSize: filters.pageSize,
        },
        defaultSortKey: 'createdAt',
        filterFn: (row, f, search) => {
          if (f.category && row.category !== f.category) return false;
          if (f.severity && row.severity !== f.severity) return false;
          if (f.status && row.status !== f.status) return false;
          if (!matchesPolicyAuthorityFilter(row, filters.policyAuthority)) return false;
          if (!matchesSourceObjectFilter(row, filters.sourceObject)) return false;
          if (!matchesDateRange(row, filters.dateFrom, filters.dateTo)) return false;
          if (!matchesSearch(row, search)) return false;
          return true;
        },
        getSortValue: (row, key) => {
          if (key === 'createdAt' || key === 'date') return row.createdAt;
          if (key === 'severity') return SEVERITY_RANK[row.severity];
          if (key === 'category') return row.category;
          if (key === 'status') return row.status;
          return row.exceptionId;
        },
      });

      if ('error' in result) {
        return { kind: result.error, message: result.message } as const;
      }
      if (result.metadata.totalCount === 0) {
        const emptyResult =
          filters.search ||
          filters.severity !== 'all' ||
          filters.category !== 'all' ||
          filters.status !== 'all' ||
          filters.policyAuthority !== 'all' ||
          filters.sourceObject !== 'all'
            ? { kind: 'filtered_empty' as const, rows: [] as [], ...result.metadata, summary, categoryCounts }
            : { kind: 'empty' as const, rows: [] as [], ...result.metadata, summary, categoryCounts };
        return emptyResult;
      }
      return { kind: 'loaded', rows: result.rows, ...result.metadata, summary, categoryCounts };
    },
  };
}

let defaultClient: ExceptionsClient | null = null;
export function getDefaultExceptionsClient(): ExceptionsClient {
  if (!defaultClient) defaultClient = createExceptionsClient();
  return defaultClient;
}
export function resetDefaultExceptionsClient(): void {
  defaultClient = null;
}
