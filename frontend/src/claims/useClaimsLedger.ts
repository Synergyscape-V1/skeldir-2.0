import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { getAuthState } from '../auth/sessionStore';
import { getCurrentUserRole } from '../governance/governanceStore';
import { canViewClaims } from '../ledger/permissions';
import { normalizeClaimsPageSize } from './claimsPagination';
import { getDefaultClaimsLedgerClient } from './claimsClient';
import { buildClaimsQueryKey, parseClaimsFilters } from './parseClaimsFilters';
import type { ClaimLedgerRowDTO } from '../ledger/types';
import { LEDGER_COPY } from '../ledger/copy';

export function useClaimsLedger(search: string) {
  const filters = useMemo(() => parseClaimsFilters(search), [search]);
  const queryKey = useMemo(() => buildClaimsQueryKey(filters), [filters]);
  const [rows, setRows] = useState<ClaimLedgerRowDTO[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);
  const [error, setError] = useState<string | undefined>();
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
  const pageSize = normalizeClaimsPageSize(filters.pageSize);

  const refresh = useCallback(async () => {
    const { tenant } = getAuthState();
    if (!tenant) {
      setLoading(false);
      return;
    }
    if (!canViewClaims(role)) {
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
      const outcome = await getDefaultClaimsLedgerClient().listClaims(
        tenant.tenantId,
        { ...filters, offset, pageSize },
        controller.signal,
      );

      if (controller.signal.aborted || activeQueryKeyRef.current !== requestKey) {
        return;
      }

      if (outcome.kind === 'permission_denied') {
        setPermissionDenied(true);
        setRows([]);
        return;
      }
      if (
        outcome.kind === 'trust_api_error' ||
        outcome.kind === 'network_error' ||
        outcome.kind === 'unknown_error' ||
        outcome.kind === 'schema_invalid' ||
        outcome.kind === 'sort_invalid' ||
        outcome.kind === 'query_invalid'
      ) {
        setError(outcome.kind === 'trust_api_error' ? LEDGER_COPY.trustApiError : outcome.message);
        return;
      }
      if (outcome.kind === 'empty') {
        setEmpty(true);
        setFilteredEmpty(false);
        setRows([]);
        setTotalCount(0);
        setHasMore(false);
        setQueryId(outcome.queryId);
        return;
      }
      if (outcome.kind === 'filtered_empty') {
        setFilteredEmpty(true);
        setEmpty(false);
        setRows([]);
        setTotalCount(0);
        setHasMore(false);
        setQueryId(outcome.queryId);
        return;
      }
      if (outcome.kind === 'loaded' || outcome.kind === 'partial') {
        setEmpty(false);
        setFilteredEmpty(false);
        setRows(outcome.rows);
        setTotalCount(outcome.totalCount);
        setHasMore(outcome.hasMore);
        setQueryId(outcome.queryId);
      }
    } catch {
      if (controller.signal.aborted || activeQueryKeyRef.current !== requestKey) return;
      setError(LEDGER_COPY.networkError);
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
    rows,
    filters,
    queryKey,
    loading,
    updating,
    error,
    permissionDenied,
    empty,
    filteredEmpty,
    totalCount,
    offset,
    pageSize,
    hasMore,
    queryId,
    refresh,
  };
}
