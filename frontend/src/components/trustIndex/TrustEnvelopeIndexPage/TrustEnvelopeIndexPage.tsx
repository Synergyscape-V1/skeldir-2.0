import { useEffect, useMemo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { PageSurface } from '../../layout/PageSurface/PageSurface';
import { LEDGER_COPY } from '../../../ledger/copy';
import {
  parseCanonicalTrustIndexQuery,
  trustIndexFiltersToSearchParams,
} from '../../../trustIndex/trustIndexQueryState';
import { useTrustIndexLedger } from '../../../trustIndex/useTrustIndexLedger';
import { useTrustIndexKillSwitch } from '../../../trustIndex/useTrustIndexKillSwitch';
import { TRUST_ENVELOPE_INDEX_COPY } from '../../../trustIndex/copy';
import { TrustEnvelopeIndexFilters } from '../TrustEnvelopeIndexFilters/TrustEnvelopeIndexFilters';
import { TrustEnvelopeIndexSummaryRow } from '../TrustEnvelopeIndexSummaryRow/TrustEnvelopeIndexSummaryRow';
import { TrustEnvelopeIndexSortToggle } from '../TrustEnvelopeIndexSortToggle/TrustEnvelopeIndexSortToggle';
import { TrustEnvelopeIndexTable } from '../TrustEnvelopeIndexTable/TrustEnvelopeIndexTable';
import { TrustEnvelopeIndexPageHeader } from './TrustEnvelopeIndexPageHeader';
import styles from './TrustEnvelopeIndexPage.module.css';

export function TrustEnvelopeIndexPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const canonical = useMemo(() => parseCanonicalTrustIndexQuery(location.search), [location.search]);
  const killSwitchActive = useTrustIndexKillSwitch();

  useEffect(() => {
    if (!canonical.isCanonical) {
      navigate(
        { pathname: '/app/trust', search: canonical.canonicalSearch.replace(/^\?/, '') },
        { replace: true },
      );
    }
  }, [canonical.canonicalSearch, canonical.isCanonical, navigate]);

  const ledger = useTrustIndexLedger(canonical.canonicalSearch || location.search);
  const readOnly = killSwitchActive;

  const handleFilterChange = (next: typeof ledger.filters) => {
    const params = trustIndexFiltersToSearchParams({ ...next, offset: 0 });
    const search = params.toString();
    navigate({ pathname: '/app/trust', search: search ? `?${search}` : '' });
  };

  const clearFilters = () => navigate('/app/trust');

  const goToNextPage = () => {
    if (!ledger.hasMore || ledger.updating) return;
    const params = trustIndexFiltersToSearchParams({
      ...ledger.filters,
      offset: ledger.offset + ledger.pageSize,
    });
    navigate({ pathname: '/app/trust', search: `?${params.toString()}` });
  };

  const goToPreviousPage = () => {
    if (ledger.updating) return;
    const params = trustIndexFiltersToSearchParams({
      ...ledger.filters,
      offset: Math.max(0, ledger.offset - ledger.pageSize),
    });
    const search = params.toString();
    navigate({ pathname: '/app/trust', search: search ? `?${search}` : '' });
  };

  const latestEnvelopeId = ledger.rows[0]?.envelopeId ?? null;

  if (ledger.permissionDenied) {
    return <div data-trust-index-page role="alert">{LEDGER_COPY.permissionDenied}</div>;
  }

  return (
    <PageSurface
      className={styles.page}
      data-trust-index-page
      data-page-content-rail
      {...(ledger.queryId ? { 'data-query-id': ledger.queryId } : {})}
    >
      <TrustEnvelopeIndexPageHeader
        lastUpdatedAt={ledger.lastUpdatedAt}
        latestEnvelopeId={latestEnvelopeId}
        loading={ledger.loading || ledger.updating}
        readOnly={readOnly}
      />
      {killSwitchActive ? (
        <div
          className={styles.killSwitchBanner}
          role="alert"
          aria-live="assertive"
          data-trust-index-kill-switch-banner
        >
          {TRUST_ENVELOPE_INDEX_COPY.killSwitchBanner}
        </div>
      ) : null}
      <TrustEnvelopeIndexSummaryRow
        summary={ledger.summary}
        filters={ledger.filters}
        loading={ledger.loading}
      />
      <TrustEnvelopeIndexFilters
        filters={ledger.filters}
        onChange={handleFilterChange}
        onClearAll={clearFilters}
        disabled={ledger.updating || readOnly}
      />
      <div className={styles.tableShell} data-trust-index-table-shell>
        <div className={styles.tableTabStrip}>
          <TrustEnvelopeIndexSortToggle
            filters={ledger.filters}
            onFilterChange={handleFilterChange}
            loading={ledger.loading}
            disabled={ledger.updating || readOnly}
          />
        </div>
        <TrustEnvelopeIndexTable
          rows={ledger.rows}
          loading={ledger.loading}
          updating={ledger.updating}
          error={ledger.error}
          empty={ledger.empty}
          filteredEmpty={ledger.filteredEmpty}
          onClearFilters={clearFilters}
          readOnly={readOnly}
          onRetry={() => void ledger.refresh()}
          pagination={{
            totalCount: ledger.totalCount,
            offset: ledger.offset,
            pageSize: ledger.pageSize,
            hasMore: ledger.hasMore,
            disabled: ledger.updating,
            onPrevious: goToPreviousPage,
            onNext: goToNextPage,
          }}
        />
      </div>
    </PageSurface>
  );
}
