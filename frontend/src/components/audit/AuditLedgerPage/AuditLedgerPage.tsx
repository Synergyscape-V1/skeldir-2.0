import { useCallback, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { PageSurface } from '../../layout/PageSurface/PageSurface';
import { Typography } from '../../layout/Typography/Typography';
import { OPERATIONAL_AUDIT_COPY } from '../../../operationalAudit/copy';
import {
  auditFiltersToSearchParams,
  stripModeIncompatibleAuditFilters,
} from '../../../operationalAudit/parseAuditFilters';
import { useAuditLedger } from '../../../operationalAudit/useOperationalAudit';
import type { AuditEvent } from '../../../operationalAudit/types';
import type { AuditFilters } from '../../../operationalAudit/parseAuditFilters';
import type { AuditLogMode } from '../../../operationalAudit/types';
import { filtersForLogModeChange, getDefaultForensicTriageFilters } from '../../../operationalAudit/auditFilterConfig';
import { resolveForensicEventDetailPath } from '../../../operationalAudit/forensicExecutiveDisplay';
import { PermissionDeniedPanel } from '../../governance/PermissionDeniedPanel/PermissionDeniedPanel';
import { AuditLogModeSwitch } from '../AuditLogModeSwitch/AuditLogModeSwitch';
import { AuditLedgerFilters } from '../AuditLedgerFilters/AuditLedgerFilters';
import { AuditLedgerTable } from '../AuditLedgerTable/AuditLedgerTable';
import styles from './AuditLedgerPage.module.css';

export function AuditLedgerPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const {
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
    refresh,
    loadMore,
  } = useAuditLedger(location.search);

  const navigateWithFilters = useCallback(
    (next: AuditFilters) => {
      const params = auditFiltersToSearchParams(next);
      navigate({
        pathname: '/app/audit',
        search: params.toString() ? `?${params.toString()}` : '',
      });
    },
    [navigate],
  );

  const handleLogModeChange = useCallback(
    (mode: AuditLogMode) => {
      const next = stripModeIncompatibleAuditFilters(filtersForLogModeChange(filters, mode), mode);
      navigateWithFilters(next);
    },
    [filters, navigateWithFilters],
  );

  const handleApplyFilters = useCallback(
    (next: AuditFilters) => {
      navigateWithFilters({ ...next, logMode });
    },
    [logMode, navigateWithFilters],
  );

  const clearFilters = useCallback(() => {
    navigateWithFilters(
      logMode === 'forensic_log' ? getDefaultForensicTriageFilters() : { logMode },
    );
  }, [logMode, navigateWithFilters]);

  const handleOpenForensic = useCallback(
    (event: AuditEvent) => {
      if (logMode !== 'forensic_log') return;
      navigate(resolveForensicEventDetailPath(event.eventId));
    },
    [logMode, navigate],
  );

  useEffect(() => {
    if (logMode !== 'forensic_log' || !filters.eventId) return;
    const suffix = filters.openDrawer ? '?technical=true' : '';
    navigate(`${resolveForensicEventDetailPath(filters.eventId)}${suffix}`, { replace: true });
  }, [filters.eventId, filters.openDrawer, logMode, navigate]);

  const activeFilters = { ...filters, logMode };

  if (permissionDenied) {
    return (
      <PageSurface>
        <PermissionDeniedPanel />
      </PageSurface>
    );
  }

  return (
    <PageSurface data-audit-ledger-page>
      <header className={styles.header}>
        <Typography variant="h2">{OPERATIONAL_AUDIT_COPY.auditPageTitle}</Typography>
        <p className={styles.description}>{OPERATIONAL_AUDIT_COPY.auditPageDescription}</p>
      </header>
      <AuditLogModeSwitch value={logMode} onChange={handleLogModeChange} />
      <AuditLedgerFilters
        logMode={logMode}
        filters={activeFilters}
        onApply={handleApplyFilters}
        onClear={clearFilters}
      />
      <AuditLedgerTable
        logMode={logMode}
        events={events}
        loading={loading}
        loadingMore={loadingMore}
        error={error}
        permissionDenied={permissionDenied}
        empty={empty}
        filteredEmpty={filteredEmpty}
        onOpenForensic={handleOpenForensic}
        onClearFilters={clearFilters}
        onRetry={() => void refresh()}
        cursorPagination={{
          loadedCount: events.length,
          hasMore,
          onLoadMore: loadMore,
          disabled: loading || loadingMore,
          loadedCountLabel: OPERATIONAL_AUDIT_COPY.auditLoadedCountLabel,
          loadMoreLabel: OPERATIONAL_AUDIT_COPY.auditLoadMore,
          loadingMoreLabel: OPERATIONAL_AUDIT_COPY.auditLoadingMore,
        }}
      />
    </PageSurface>
  );
}
