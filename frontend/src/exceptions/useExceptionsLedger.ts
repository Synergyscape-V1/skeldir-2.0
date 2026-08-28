import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { getAuthState } from '../auth/sessionStore';
import { getCurrentUserRole } from '../governance/governanceStore';
import { canViewExceptions } from '../ledger/permissions';
import { LEDGER_COPY } from '../ledger/copy';
import type {
  ExceptionCategoryCounts,
  ExceptionOverviewSummary,
  ExceptionQueueRowDTO,
} from '../ledger/types';
import { getDefaultExceptionsClient } from './exceptionsClient';
import { buildExceptionsQueryKey, parseExceptionsFilters } from './exceptionsQueryState';
import {
  computeExceptionCategoryCounts,
  computeExceptionOverviewSummary,
  emptyExceptionCategoryCounts,
  emptyExceptionOverviewSummary,
} from './exceptionsSummary';
import {
  adjustExceptionCategoryCountsForMarketer,
} from '../benchmarks/benchmarkMarketingVisibility';
import { EXCEPTIONS_DEFAULT_PAGE_SIZE } from './exceptionsPagination';

export function useExceptionsLedger(search: string) {
  const filters = useMemo(() => parseExceptionsFilters(search), [search]);
  const queryKey = useMemo(() => buildExceptionsQueryKey(filters), [filters]);
  const [rows, setRows] = useState<ExceptionQueueRowDTO[]>([]);
  const [summary, setSummary] = useState<ExceptionOverviewSummary>(emptyExceptionOverviewSummary());
  const [categoryCounts, setCategoryCounts] = useState<ExceptionCategoryCounts>(emptyExceptionCategoryCounts());
  const [totalCount, setTotalCount] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);
  const [error, setError] = useState<string>();
  const [permissionDenied, setPermissionDenied] = useState(false);
  const [empty, setEmpty] = useState(false);
  const [filteredEmpty, setFilteredEmpty] = useState(false);
  const [queryId, setQueryId] = useState('');
  const activeQueryKeyRef = useRef(queryKey);
  const abortRef = useRef<AbortController | null>(null);
  const rowsRef = useRef(rows);
  rowsRef.current = rows;
  const role = getCurrentUserRole();
  const offset = filters.offset ?? 0;
  const pageSize = filters.pageSize ?? EXCEPTIONS_DEFAULT_PAGE_SIZE;

  const refresh = useCallback(async () => {
    const { tenant } = getAuthState();
    if (!tenant) {
      setLoading(false);
      return;
    }
    if (!canViewExceptions(role)) {
      setPermissionDenied(true);
      setLoading(false);
      return;
    }

    const requestKey = queryKey;
    activeQueryKeyRef.current = requestKey;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    const hadRows = rowsRef.current.length > 0;
    if (hadRows) setUpdating(true);
    else setLoading(true);
    setError(undefined);
    setPermissionDenied(false);

    try {
      const outcome = await getDefaultExceptionsClient().listExceptions(
        tenant.tenantId,
        { ...filters, offset, pageSize },
        controller.signal,
      );

      if (controller.signal.aborted || activeQueryKeyRef.current !== requestKey) return;

      setEmpty(false);
      setFilteredEmpty(false);

      if (outcome.kind === 'permission_denied') {
        setPermissionDenied(true);
        setRows([]);
        return;
      }
      if (outcome.kind === 'sort_invalid' || outcome.kind === 'network_error') {
        setError(outcome.message ?? LEDGER_COPY.trustApiError);
        return;
      }

      if (outcome.summary) setSummary(outcome.summary);
      else setSummary(computeExceptionOverviewSummary(rowsRef.current));
      if (outcome.categoryCounts) {
        setCategoryCounts(adjustExceptionCategoryCountsForMarketer(outcome.categoryCounts));
      } else {
        setCategoryCounts(
          adjustExceptionCategoryCountsForMarketer(computeExceptionCategoryCounts(rowsRef.current)),
        );
      }

      if (outcome.kind === 'empty') {
        setEmpty(true);
        setRows([]);
        setTotalCount(0);
        setHasMore(false);
        setQueryId(outcome.queryId ?? '');
        return;
      }
      if (outcome.kind === 'filtered_empty') {
        setFilteredEmpty(true);
        setRows([]);
        setTotalCount(outcome.totalCount ?? 0);
        setHasMore(false);
        setQueryId(outcome.queryId ?? '');
        return;
      }

      if (outcome.kind !== 'loaded' && outcome.kind !== 'partial') {
        return;
      }

      setRows(outcome.rows);
      setTotalCount(outcome.totalCount ?? outcome.rows.length);
      setHasMore(outcome.hasMore ?? false);
      setQueryId(outcome.queryId ?? '');
    } finally {
      if (activeQueryKeyRef.current === requestKey) {
        setLoading(false);
        setUpdating(false);
      }
    }
  }, [filters, offset, pageSize, queryKey, role]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return {
    rows,
    summary,
    categoryCounts,
    filters,
    totalCount,
    hasMore,
    loading,
    updating,
    error,
    permissionDenied,
    empty,
    filteredEmpty,
    queryId,
    offset,
    pageSize,
    refresh,
  };
}
