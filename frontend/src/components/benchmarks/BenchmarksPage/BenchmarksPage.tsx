import { useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { PageSurface } from '../../layout/PageSurface/PageSurface';
import { PermissionDeniedPanel } from '../../governance/PermissionDeniedPanel/PermissionDeniedPanel';
import { ErrorBanner } from '../../layout/ErrorBanner/ErrorBanner';
import {
  benchmarksDefaultFilters,
  benchmarksFiltersToSearchParams,
  parseCanonicalBenchmarksQuery,
} from '../../../benchmarks/benchmarksQueryState';
import { useBenchmarksLedger } from '../../../benchmarks/useBenchmarksLedger';
import type { BenchmarksFilters } from '../../../benchmarks/benchmarksClient';
import type { BenchmarkRowDTO } from '../../../ledger/types';
import { LEDGER_COPY } from '../../../ledger/copy';
import { BenchmarksPageHeader } from './BenchmarksPageHeader';
import { BenchmarksBoundaryBanner } from './BenchmarksBoundaryBanner';
import { BenchmarksFilters as BenchmarksFiltersPanel } from '../BenchmarksFilters/BenchmarksFilters';
import { BenchmarksTable } from '../BenchmarksTable/BenchmarksTable';
import { BenchmarkSourceDetailDrawer } from '../BenchmarkSourceDetailDrawer/BenchmarkSourceDetailDrawer';
import styles from './BenchmarksPage.module.css';

export function BenchmarksPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const canonical = useMemo(() => parseCanonicalBenchmarksQuery(location.search), [location.search]);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedBenchmarkId, setSelectedBenchmarkId] = useState<string | null>(null);
  const triggerRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!location.search) {
      const defaults = benchmarksDefaultFilters();
      const params = benchmarksFiltersToSearchParams(defaults);
      navigate({ pathname: '/app/benchmarks', search: `?${params.toString()}` }, { replace: true });
      return;
    }
    if (!canonical.isCanonical) {
      navigate(
        { pathname: '/app/benchmarks', search: canonical.canonicalSearch.replace(/^\?/, '') },
        { replace: true },
      );
    }
  }, [canonical.canonicalSearch, canonical.isCanonical, location.search, navigate]);

  const ledger = useBenchmarksLedger(canonical.canonicalSearch || location.search);

  const handleFilterChange = (next: BenchmarksFilters) => {
    const params = benchmarksFiltersToSearchParams({ ...next, offset: 0 });
    const search = params.toString();
    navigate({ pathname: '/app/benchmarks', search: search ? `?${search}` : '' });
  };

  const clearFilters = () => {
    const params = benchmarksFiltersToSearchParams(benchmarksDefaultFilters());
    navigate({ pathname: '/app/benchmarks', search: `?${params.toString()}` });
  };

  const goToNextPage = () => {
    if (!ledger.hasMore || ledger.updating) return;
    const params = benchmarksFiltersToSearchParams({
      ...ledger.filters,
      offset: ledger.offset + ledger.pageSize,
    });
    navigate({ pathname: '/app/benchmarks', search: `?${params.toString()}` });
  };

  const goToPreviousPage = () => {
    if (ledger.updating) return;
    const params = benchmarksFiltersToSearchParams({
      ...ledger.filters,
      offset: Math.max(0, ledger.offset - ledger.pageSize),
    });
    navigate({ pathname: '/app/benchmarks', search: `?${params.toString()}` });
  };

  const openDrawer = (row: BenchmarkRowDTO, trigger?: HTMLElement | null) => {
    triggerRef.current = trigger ?? null;
    setSelectedBenchmarkId(row.benchmarkId);
    setDrawerOpen(true);
  };

  if (ledger.permissionDenied) {
    return (
      <PageSurface data-benchmarks-page>
        <PermissionDeniedPanel />
      </PageSurface>
    );
  }

  return (
    <PageSurface
      className={styles.page}
      data-benchmarks-page
      {...(ledger.queryId ? { 'data-query-id': ledger.queryId } : {})}
    >
      <BenchmarksPageHeader />
      <BenchmarksBoundaryBanner />

      <BenchmarksFiltersPanel
        filters={ledger.filters}
        onChange={handleFilterChange}
        onClearAll={clearFilters}
        disabled={ledger.updating}
      />

      {ledger.error ? (
        <ErrorBanner variant="error" message={ledger.error ?? LEDGER_COPY.trustApiError} />
      ) : null}

      <BenchmarksTable
        rows={ledger.rows}
        totalCount={ledger.totalCount}
        loading={ledger.loading}
        updating={ledger.updating}
        error={ledger.error}
        empty={ledger.empty}
        filteredEmpty={ledger.filteredEmpty}
        onClearFilters={clearFilters}
        onRowActivate={(row) => openDrawer(row)}
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

      <BenchmarkSourceDetailDrawer
        benchmarkId={selectedBenchmarkId}
        open={drawerOpen}
        onClose={() => {
          setDrawerOpen(false);
          setSelectedBenchmarkId(null);
        }}
        triggerRef={triggerRef}
      />
    </PageSurface>
  );
}
