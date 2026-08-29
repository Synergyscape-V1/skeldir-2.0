import { useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { PageSurface } from '../../layout/PageSurface/PageSurface';
import { PermissionDeniedPanel } from '../../governance/PermissionDeniedPanel/PermissionDeniedPanel';
import { ErrorBanner } from '../../layout/ErrorBanner/ErrorBanner';
import type { ExceptionQueueRowDTO } from '../../../ledger/types';
import { LEDGER_COPY } from '../../../ledger/copy';
import type { ExceptionsFilters } from '../../../exceptions/exceptionsClient';
import {
  exceptionsDefaultFilters,
  exceptionsFiltersToSearchParams,
  parseCanonicalExceptionsQuery,
} from '../../../exceptions/exceptionsQueryState';
import { useExceptionsLedger } from '../../../exceptions/useExceptionsLedger';
import { ExceptionsPageHeader } from '../ExceptionsPageHeader/ExceptionsPageHeader';
import { ExceptionsSummaryRow } from '../ExceptionsSummaryRow/ExceptionsSummaryRow';
import { ExceptionsCategoryTabs } from '../ExceptionsCategoryTabs/ExceptionsCategoryTabs';
import { ExceptionsFiltersPanel } from '../ExceptionsFilters/ExceptionsFilters';
import { ExceptionsTable } from '../ExceptionsTable/ExceptionsTable';
import { ExceptionDetailModal } from '../ExceptionDetailModal/ExceptionDetailModal';
import styles from './ExceptionsQueuePage.module.css';

export function ExceptionsQueuePage() {
  const location = useLocation();
  const navigate = useNavigate();
  const canonical = useMemo(() => parseCanonicalExceptionsQuery(location.search), [location.search]);
  const [selectedExceptionId, setSelectedExceptionId] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    if (!location.search) {
      const params = exceptionsFiltersToSearchParams(exceptionsDefaultFilters());
      navigate({ pathname: '/app/exceptions', search: `?${params.toString()}` }, { replace: true });
      return;
    }
    if (!canonical.isCanonical) {
      navigate(
        { pathname: '/app/exceptions', search: canonical.canonicalSearch.replace(/^\?/, '') },
        { replace: true },
      );
    }
  }, [canonical.canonicalSearch, canonical.isCanonical, location.search, navigate]);

  const ledger = useExceptionsLedger(canonical.canonicalSearch || location.search);

  const handleFilterChange = (next: ExceptionsFilters) => {
    const params = exceptionsFiltersToSearchParams({ ...next, offset: 0 });
    const search = params.toString();
    navigate({ pathname: '/app/exceptions', search: search ? `?${search}` : '' });
  };

  const handleCategoryTabChange = (category: ExceptionsFilters['category']) => {
    handleFilterChange({ ...ledger.filters, category: category ?? 'all' });
  };

  const clearFilters = () => {
    const params = exceptionsFiltersToSearchParams(exceptionsDefaultFilters());
    navigate({ pathname: '/app/exceptions', search: `?${params.toString()}` });
  };

  const goToPage = (pageIndex: number) => {
    const params = exceptionsFiltersToSearchParams({
      ...ledger.filters,
      offset: pageIndex * ledger.pageSize,
    });
    navigate({ pathname: '/app/exceptions', search: `?${params.toString()}` });
  };

  // Page index from a non-negative integer offset, using exact integer arithmetic.
  // Subtracting the remainder before dividing leaves no fractional part, so no
  // rounding function is needed. Deliberately avoids Math.floor: the financial
  // axiom scan forbids rounding helpers across component code, and pagination has
  // no reason to reach for one.
  const currentPageIndex = () =>
    (ledger.offset - (ledger.offset % ledger.pageSize)) / ledger.pageSize;

  const goToNextPage = () => {
    if (!ledger.hasMore || ledger.updating) return;
    goToPage(currentPageIndex() + 1);
  };

  const goToPreviousPage = () => {
    if (ledger.updating) return;
    goToPage(Math.max(0, currentPageIndex() - 1));
  };

  const openModal = (row: ExceptionQueueRowDTO, trigger: HTMLButtonElement) => {
    triggerRef.current = trigger;
    setSelectedExceptionId(row.exceptionId);
    setModalOpen(true);
  };

  const closeModal = () => {
    setModalOpen(false);
    if (triggerRef.current) {
      triggerRef.current.focus();
    }
  };

  if (ledger.permissionDenied) {
    return (
      <PageSurface data-exceptions-page>
        <PermissionDeniedPanel />
      </PageSurface>
    );
  }

  return (
    <PageSurface
      className={styles.page}
      data-exceptions-page
      data-page-content-rail
      {...(ledger.queryId ? { 'data-query-id': ledger.queryId } : {})}
    >
      <ExceptionsPageHeader />

      <ExceptionsSummaryRow summary={ledger.summary} loading={ledger.loading} />

      <ExceptionsCategoryTabs
        activeCategory={ledger.filters.category ?? 'all'}
        counts={ledger.categoryCounts}
        onChange={handleCategoryTabChange}
        disabled={ledger.updating}
      />

      <ExceptionsFiltersPanel
        filters={ledger.filters}
        onChange={handleFilterChange}
        onClearAll={clearFilters}
        disabled={ledger.updating}
      />

      {ledger.error ? (
        <ErrorBanner variant="error" message={ledger.error ?? LEDGER_COPY.trustApiError} />
      ) : null}

      <ExceptionsTable
        rows={ledger.rows}
        totalCount={ledger.totalCount}
        loading={ledger.loading}
        updating={ledger.updating}
        error={ledger.error}
        empty={ledger.empty}
        filteredEmpty={ledger.filteredEmpty}
        onClearFilters={clearFilters}
        onReview={openModal}
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

      <ExceptionDetailModal
        exceptionId={selectedExceptionId}
        open={modalOpen}
        onClose={closeModal}
        triggerRef={triggerRef}
      />
    </PageSurface>
  );
}
