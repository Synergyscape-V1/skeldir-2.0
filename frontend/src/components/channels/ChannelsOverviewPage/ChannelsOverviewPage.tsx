import { useEffect, useMemo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { PageSurface } from '../../layout/PageSurface/PageSurface';
import { PermissionDeniedPanel } from '../../governance/PermissionDeniedPanel/PermissionDeniedPanel';
import { ErrorBanner } from '../../layout/ErrorBanner/ErrorBanner';
import {
  appendChannelsExpandParam,
  channelsFiltersToSearchParams,
  parseCanonicalChannelsQuery,
} from '../../../channels/channelsQueryState';
import {
  mergeExpandIntoSearch,
  readChannelExpandId,
  withChannelExpandParam,
} from '../../../channels/channelExpandHref';
import { useChannelsLedger } from '../../../channels/useChannelsLedger';
import type { ChannelsFilters } from '../../../channels/channelsClient';
import type { ChannelOverviewRowDTO } from '../../../ledger/types';
import { ChannelsOverviewPageHeader } from './ChannelsOverviewPageHeader';
import { ChannelsOverviewSummaryRow } from '../ChannelsOverviewSummaryRow/ChannelsOverviewSummaryRow';
import { ChannelsOverviewFilters } from '../ChannelsOverviewFilters/ChannelsOverviewFilters';
import { ChannelsOverviewTable } from '../ChannelsOverviewTable/ChannelsOverviewTable';
import { ChannelInlineExpansion } from '../ChannelInlineExpansion/ChannelInlineExpansion';
import { LEDGER_COPY } from '../../../ledger/copy';
import styles from './ChannelsOverviewPage.module.css';

export function ChannelsOverviewPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const canonical = useMemo(() => parseCanonicalChannelsQuery(location.search), [location.search]);
  const expandChannelId = useMemo(() => readChannelExpandId(location.search), [location.search]);

  useEffect(() => {
    if (!canonical.isCanonical) {
      navigate(
        { pathname: '/app/channels', search: canonical.canonicalSearch.replace(/^\?/, '') },
        { replace: true },
      );
    }
  }, [canonical.canonicalSearch, canonical.isCanonical, navigate]);

  const ledger = useChannelsLedger(canonical.canonicalSearch || location.search);

  const navigateWithFilters = (next: ChannelsFilters, expandId: string | null = expandChannelId) => {
    const params = appendChannelsExpandParam(channelsFiltersToSearchParams(next), expandId);
    const search = params.toString();
    navigate({ pathname: '/app/channels', search: search ? `?${search}` : '' });
  };

  const handleFilterChange = (next: ChannelsFilters) => {
    navigateWithFilters({ ...next, offset: 0 }, expandChannelId);
  };

  const handleMetricBasisChange = (metricBasis: ChannelsFilters['metricBasis']) => {
    handleFilterChange({ ...ledger.filters, metricBasis });
  };

  const handleSortChange = (sortKey: string) => {
    const nextDirection =
      ledger.filters.sortKey === sortKey && ledger.filters.sortDirection === 'desc' ? 'asc' : 'desc';
    handleFilterChange({
      ...ledger.filters,
      sortKey,
      sortDirection: ledger.filters.sortKey === sortKey ? nextDirection : 'desc',
    });
  };

  const handlePageSizeChange = (pageSize: number) => {
    handleFilterChange({ ...ledger.filters, pageSize, offset: 0 });
  };

  const goToNextPage = () => {
    if (!ledger.hasMore || ledger.updating) return;
    navigateWithFilters({
      ...ledger.filters,
      offset: ledger.offset + ledger.pageSize,
    });
  };

  const goToPreviousPage = () => {
    if (ledger.updating) return;
    navigateWithFilters({
      ...ledger.filters,
      offset: Math.max(0, ledger.offset - ledger.pageSize),
    });
  };

  const clearFilters = () => {
    navigate({
      pathname: '/app/channels',
      search: withChannelExpandParam('', expandChannelId).replace(/^\?/, ''),
    });
  };

  const toggleExpand = (row: ChannelOverviewRowDTO) => {
    const nextExpand = expandChannelId === row.channelId ? null : row.channelId;
    const base = channelsFiltersToSearchParams(ledger.filters).toString();
    navigate({
      pathname: '/app/channels',
      search: mergeExpandIntoSearch(base ? `?${base}` : '', nextExpand).replace(/^\?/, ''),
    });
  };

  if (ledger.permissionDenied) {
    return (
      <PageSurface data-channels-page>
        <PermissionDeniedPanel />
      </PageSurface>
    );
  }

  return (
    <PageSurface
      className={styles.page}
      data-channels-page
      {...(ledger.queryId ? { 'data-query-id': ledger.queryId } : {})}
      {...(expandChannelId ? { 'data-channel-expand': expandChannelId } : {})}
    >
      <ChannelsOverviewPageHeader
        metricBasis={ledger.filters.metricBasis ?? 'verified'}
        onMetricBasisChange={handleMetricBasisChange}
        disabled={ledger.loading || ledger.updating}
      />

      <ChannelsOverviewSummaryRow summary={ledger.summary} loading={ledger.loading} />

      <ChannelsOverviewFilters
        filters={ledger.filters}
        onChange={handleFilterChange}
        onClearAll={clearFilters}
        disabled={ledger.updating}
      />

      {ledger.error ? (
        <ErrorBanner variant="error" message={ledger.error ?? LEDGER_COPY.trustApiError} />
      ) : null}

      <ChannelsOverviewTable
        rows={ledger.rows}
        loading={ledger.loading}
        updating={ledger.updating}
        error={undefined}
        empty={ledger.empty}
        filteredEmpty={ledger.filteredEmpty}
        onClearFilters={clearFilters}
        expandedChannelId={expandChannelId}
        onRowActivate={toggleExpand}
        renderExpandedRow={(row) => <ChannelInlineExpansion row={row} />}
        sortKey={ledger.filters.sortKey}
        sortDirection={ledger.filters.sortDirection}
        onSortChange={handleSortChange}
        pageSize={ledger.pageSize}
        onPageSizeChange={handlePageSizeChange}
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
    </PageSurface>
  );
}
