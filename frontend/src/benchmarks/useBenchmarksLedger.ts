import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { getAuthState } from '../auth/sessionStore';
import { getCurrentUserRole } from '../governance/governanceStore';
import { canViewBenchmarks } from '../ledger/permissions';
import { LEDGER_COPY } from '../ledger/copy';
import type { BenchmarkRowDTO } from '../ledger/types';
import { getDefaultBenchmarksClient } from './benchmarksClient';
import { BENCHMARKS_DEFAULT_PAGE_SIZE } from './benchmarksPagination';
import { buildBenchmarksQueryKey, parseBenchmarksFilters } from './benchmarksQueryState';

export function useBenchmarksLedger(search: string) {
  const filters = useMemo(() => parseBenchmarksFilters(search), [search]);
  const queryKey = useMemo(() => buildBenchmarksQueryKey(filters), [filters]);
  const [rows, setRows] = useState<BenchmarkRowDTO[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);
  const [error, setError] = useState<string>();
  const [permissionDenied, setPermissionDenied] = useState(false);
  const [empty, setEmpty] = useState(false);
  const [filteredEmpty, setFilteredEmpty] = useState(false);
  const [queryId, setQueryId] = useState('');
  const [lastRefreshedAt, setLastRefreshedAt] = useState<string>();
  const activeQueryKeyRef = useRef(queryKey);
  const abortRef = useRef<AbortController | null>(null);
  const rowsRef = useRef(rows);
  rowsRef.current = rows;
  const role = getCurrentUserRole();
  const offset = filters.offset ?? 0;
  const pageSize = filters.pageSize ?? BENCHMARKS_DEFAULT_PAGE_SIZE;

  const refresh = useCallback(async () => {
    const { tenant } = getAuthState();
    if (!tenant) {
      setLoading(false);
      return;
    }
    if (!canViewBenchmarks(role)) {
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
      const outcome = await getDefaultBenchmarksClient().listBenchmarks(
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
        setTotalCount(0);
        setHasMore(false);
        setQueryId(outcome.queryId ?? '');
        return;
      }
      if (outcome.kind === 'loaded') {
        setRows(outcome.rows);
        setTotalCount(outcome.totalCount);
        setHasMore(outcome.hasMore);
        setQueryId(outcome.queryId);
        setLastRefreshedAt(outcome.rows[0]?.lastRefreshed);
      }
    } catch {
      if (!controller.signal.aborted) {
        setError(LEDGER_COPY.trustApiError);
      }
    } finally {
      if (!controller.signal.aborted && activeQueryKeyRef.current === requestKey) {
        setLoading(false);
        setUpdating(false);
      }
    }
  }, [filters, offset, pageSize, queryKey, role]);

  useEffect(() => {
    void refresh();
    return () => abortRef.current?.abort();
  }, [refresh]);

  return {
    filters,
    rows,
    totalCount,
    hasMore,
    loading,
    updating,
    error,
    permissionDenied,
    empty,
    filteredEmpty,
    queryId,
    lastRefreshedAt,
    offset,
    pageSize,
    refresh,
  };
}
