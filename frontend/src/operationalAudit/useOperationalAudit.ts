import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { getAuthState } from '../auth/sessionStore';
import { getCurrentUserRole } from '../governance/governanceStore';
import { getDefaultOperationalAuditClient } from './operationalAuditClient';
import {
  isOperationalAuditError,
  mapOperationalAuditError,
} from './operationalAuditOutcomeMapping';
import { parseAuditFilters } from './parseAuditFilters';
import { resolveAuditLogMode } from './auditLogMode';
import { resolveForensicAuditFilters } from './forensicBusinessTriage';
import { canViewAudit } from './permissions';
import { AUDIT_LEDGER_BATCH_SIZE, DEFAULT_PAGE_SIZE } from './pagination';
import type { AuditEvent, AuditFilters } from './types';

function filterSignature(filters: AuditFilters): string {
  const { cursor: _cursor, offset: _offset, openDrawer: _drawer, ...rest } = filters;
  return JSON.stringify(rest);
}

export function useAuditLedger(search: string) {
  const filters = useMemo(
    () => resolveForensicAuditFilters(parseAuditFilters(search)),
    [search],
  );
  const logMode = resolveAuditLogMode(filters);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [nextCursor, setNextCursor] = useState<string | undefined>();
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | undefined>();
  const [permissionDenied, setPermissionDenied] = useState(false);
  const [empty, setEmpty] = useState(false);
  const [filteredEmpty, setFilteredEmpty] = useState(false);
  const role = getCurrentUserRole();
  const pageSize = filters.pageSize ?? AUDIT_LEDGER_BATCH_SIZE;
  const filterKey = useMemo(() => filterSignature(filters), [filters]);
  const lastFilterKey = useRef(filterKey);

  const applyOutcome = useCallback(
    (outcome: Awaited<ReturnType<ReturnType<typeof getDefaultOperationalAuditClient>['listAuditEvents']>>, append: boolean) => {
      if (isOperationalAuditError(outcome)) {
        if (outcome.kind === 'permission_denied') setPermissionDenied(true);
        setError(mapOperationalAuditError(outcome));
        return;
      }
      if (outcome.kind === 'audit_empty') {
        setEmpty(true);
        setEvents([]);
        setHasMore(false);
        setNextCursor(undefined);
        return;
      }
      if (outcome.kind === 'audit_filtered_empty') {
        setFilteredEmpty(true);
        setEvents([]);
        setHasMore(false);
        setNextCursor(undefined);
        return;
      }
      setEvents((current) => (append ? [...current, ...outcome.events] : outcome.events));
      setHasMore(outcome.hasMore);
      setNextCursor(outcome.nextCursor);
    },
    [],
  );

  const refresh = useCallback(
    async (options?: { cursor?: string; append?: boolean }) => {
      const { tenant } = getAuthState();
      if (!tenant) {
        setLoading(false);
        return;
      }
      if (!canViewAudit(role)) {
        setPermissionDenied(true);
        setLoading(false);
        return;
      }

      const append = options?.append ?? false;
      if (append) {
        setLoadingMore(true);
      } else {
        setLoading(true);
      }
      setError(undefined);
      setPermissionDenied(false);
      setEmpty(false);
      setFilteredEmpty(false);

      try {
        const client = getDefaultOperationalAuditClient();
        const outcome = await client.listAuditEvents(tenant.tenantId, {
          ...filters,
          cursor: options?.cursor,
          pageSize,
        });
        applyOutcome(outcome, append);
      } catch {
        setError('Audit service unavailable. Try again shortly.');
      } finally {
        setLoading(false);
        setLoadingMore(false);
      }
    },
    [applyOutcome, filters, pageSize, role],
  );

  useEffect(() => {
    const filterChanged = lastFilterKey.current !== filterKey;
    lastFilterKey.current = filterKey;
    if (filterChanged) {
      setEvents([]);
      setNextCursor(undefined);
    }
    void refresh({ append: false });
  }, [filterKey, refresh]);

  const loadMore = useCallback(() => {
    if (!hasMore || !nextCursor || loadingMore) return;
    void refresh({ cursor: nextCursor, append: true });
  }, [hasMore, loadingMore, nextCursor, refresh]);

  return {
    events,
    filters,
    logMode,
    loading,
    loadingMore,
    error,
    permissionDenied,
    empty,
    filteredEmpty,
    hasMore,
    nextCursor,
    pageSize,
    refresh: () => refresh({ append: false }),
    loadMore,
  };
}

export function useAuditArtifact(eventId: string | null) {
  const [artifact, setArtifact] = useState<
    import('./types').AuditArtifact | undefined
  >();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | undefined>();
  const [unavailable, setUnavailable] = useState(false);
  const [corrupted, setCorrupted] = useState(false);
  const [invalidSignature, setInvalidSignature] = useState(false);
  const [accessDenied, setAccessDenied] = useState(false);
  const role = getCurrentUserRole();

  const load = useCallback(async () => {
    if (!eventId) return;
    const { tenant } = getAuthState();
    if (!tenant) return;
    setLoading(true);
    setError(undefined);
    setUnavailable(false);
    setCorrupted(false);
    setInvalidSignature(false);
    setAccessDenied(false);
    setArtifact(undefined);
    try {
      const client = getDefaultOperationalAuditClient();
      const outcome = await client.getAuditArtifact(tenant.tenantId, eventId);
      if (isOperationalAuditError(outcome)) {
        if (outcome.kind === 'permission_denied') setAccessDenied(true);
        setError(mapOperationalAuditError(outcome));
        return;
      }
      switch (outcome.kind) {
        case 'artifact_loaded':
          setArtifact(outcome.artifact);
          break;
        case 'artifact_unavailable':
          setUnavailable(true);
          setError(outcome.reason);
          break;
        case 'artifact_corrupted':
          setCorrupted(true);
          setError(outcome.reason);
          break;
        case 'artifact_signature_invalid':
          setInvalidSignature(true);
          setError(outcome.reason);
          break;
        case 'artifact_access_denied':
          setAccessDenied(true);
          break;
      }
    } catch {
      setError('Artifact service unavailable. Try again shortly.');
    } finally {
      setLoading(false);
    }
  }, [eventId, role]);

  useEffect(() => {
    if (eventId) void load();
  }, [eventId, load]);

  return {
    artifact,
    loading,
    error,
    unavailable,
    corrupted,
    invalidSignature,
    accessDenied,
    reload: load,
  };
}

export function useOperationalDiagnostics() {
  const [payload, setPayload] = useState<
    import('./types').OperationalDiagnosticsPayload | undefined
  >();
  const [dlqEvents, setDlqEvents] = useState<import('./types').DLQEvent[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [offset, setOffset] = useState(0);
  const [pageSize] = useState(DEFAULT_PAGE_SIZE);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | undefined>();
  const [permissionDenied, setPermissionDenied] = useState(false);
  const [empty, setEmpty] = useState(false);
  const role = getCurrentUserRole();

  const refresh = useCallback(async () => {
    const { tenant } = getAuthState();
    if (!tenant) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(undefined);
    setPermissionDenied(false);
    setEmpty(false);
    try {
      const client = getDefaultOperationalAuditClient();
      const outcome = await client.getDiagnostics(tenant.tenantId, { offset, pageSize });
      if (isOperationalAuditError(outcome)) {
        if (outcome.kind === 'permission_denied') setPermissionDenied(true);
        setError(mapOperationalAuditError(outcome));
        return;
      }
      if (outcome.kind === 'diagnostics_empty') {
        setEmpty(true);
        setDlqEvents([]);
        setTotalCount(0);
        setHasMore(false);
        return;
      }
      setPayload(outcome.payload);
      setDlqEvents(outcome.dlqEvents);
      setTotalCount(outcome.totalCount);
      setHasMore(outcome.hasMore);
    } catch {
      setError('Diagnostics service unavailable. Try again shortly.');
    } finally {
      setLoading(false);
    }
  }, [offset, pageSize, role]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const goToNextPage = useCallback(() => {
    if (hasMore) setOffset((current) => current + pageSize);
  }, [hasMore, pageSize]);

  const goToPreviousPage = useCallback(() => {
    setOffset((current) => Math.max(0, current - pageSize));
  }, [pageSize]);

  return {
    payload,
    dlqEvents,
    loading,
    error,
    permissionDenied,
    empty,
    totalCount,
    offset,
    pageSize,
    hasMore,
    goToNextPage,
    goToPreviousPage,
    refresh,
  };
}

export function useSystemHealth() {
  const [state, setState] = useState<import('./types').SystemHealthState>('loading');
  const [error, setError] = useState<string | undefined>();

  const refresh = useCallback(async () => {
    const { tenant } = getAuthState();
    if (!tenant) {
      setState('fetch_failed');
      return;
    }
    setState('loading');
    setError(undefined);
    try {
      const client = getDefaultOperationalAuditClient();
      const outcome = await client.getSystemHealth(tenant.tenantId);
      if (isOperationalAuditError(outcome)) {
        setState('fetch_failed');
        setError(mapOperationalAuditError(outcome));
        return;
      }
      switch (outcome.kind) {
        case 'health_operational':
          setState('operational');
          break;
        case 'health_confidence_degraded':
          setState('confidence_degraded');
          break;
        case 'health_api_paused':
          setState('api_paused');
          break;
        case 'health_integration_attention':
          setState('integration_attention');
          break;
        case 'health_unknown':
          setState('unknown');
          break;
        case 'health_fetch_failed':
          setState('fetch_failed');
          break;
        default:
          setState('unknown');
      }
    } catch {
      setState('fetch_failed');
      setError('Health service unavailable.');
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { state, error, refresh };
}

export type { AuditFilters };
