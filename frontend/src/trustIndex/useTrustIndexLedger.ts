import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { getAuthState } from '../auth/sessionStore';
import { getCurrentUserRole } from '../governance/governanceStore';
import { canViewTrustIndex } from '../ledger/permissions';
import type { TrustEnvelopeIndexRowDTO, TrustEnvelopeIndexSummary } from '../ledger/types';
import { TRUST_INDEX_DEFAULT_PAGE_SIZE } from './trustIndexQueryState';
import { getDefaultTrustIndexClient } from './trustIndexClient';
import { buildTrustIndexQueryKey, parseTrustIndexFilters } from './parseTrustIndexFilters';
import { emptyTrustIndexSummary } from './trustIndexSummary';

export function useTrustIndexLedger(search: string) {
  const filters = useMemo(() => parseTrustIndexFilters(search), [search]);
  const queryKey = useMemo(() => buildTrustIndexQueryKey(filters), [filters]);
  const [rows, setRows] = useState<TrustEnvelopeIndexRowDTO[]>([]);
  const [summary, setSummary] = useState<TrustEnvelopeIndexSummary>(emptyTrustIndexSummary());
  const [totalCount, setTotalCount] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);
  const [error, setError] = useState<string>();
  const [permissionDenied, setPermissionDenied] = useState(false);
  const [empty, setEmpty] = useState(false);
  const [filteredEmpty, setFilteredEmpty] = useState(false);
  const [queryId, setQueryId] = useState('');
  const [lastUpdatedAt, setLastUpdatedAt] = useState<string>();
  const activeQueryKeyRef = useRef(queryKey);
  const abortRef = useRef<AbortController | null>(null);
  const rowsRef = useRef(rows);
  rowsRef.current = rows;
  const role = getCurrentUserRole();
  const offset = filters.offset ?? 0;
  const pageSize = filters.pageSize ?? TRUST_INDEX_DEFAULT_PAGE_SIZE;

  const refresh = useCallback(async () => {
    const { tenant } = getAuthState();
    if (!tenant) {
      setLoading(false);
      return;
    }
    if (!canViewTrustIndex(role)) {
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
      const outcome = await getDefaultTrustIndexClient().listEnvelopes(
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
      if (outcome.kind === 'payload_oversized') {
        setError('TrustEnvelope list payload rejected.');
        return;
      }
      if (outcome.kind === 'empty') {
        setEmpty(true);
        setRows([]);
        setTotalCount(0);
        setHasMore(false);
        setSummary(outcome.summary ?? emptyTrustIndexSummary());
        setLastUpdatedAt(new Date().toISOString());
        return;
      }
      if (outcome.kind === 'filtered_empty') {
        setFilteredEmpty(true);
        setRows([]);
        setTotalCount(0);
        setHasMore(false);
        setSummary(outcome.summary ?? emptyTrustIndexSummary());
        setLastUpdatedAt(new Date().toISOString());
        return;
      }
      if (outcome.kind === 'loaded') {
        setRows(outcome.rows);
        setTotalCount(outcome.totalCount);
        setHasMore(outcome.hasMore);
        setSummary(outcome.summary ?? emptyTrustIndexSummary());
        setQueryId(outcome.queryId);
        setLastUpdatedAt(new Date().toISOString());
      } else if ('message' in outcome) {
        setError(outcome.message);
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
    queryKey,
    queryId,
    rows,
    summary,
    totalCount,
    hasMore,
    loading,
    updating,
    error,
    permissionDenied,
    empty,
    filteredEmpty,
    lastUpdatedAt,
    offset,
    pageSize,
    refresh,
  };
}
