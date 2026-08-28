import { useEffect, useMemo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { PageSurface } from '../../layout/PageSurface/PageSurface';
import { PermissionDeniedPanel } from '../../governance/PermissionDeniedPanel/PermissionDeniedPanel';
import { claimsFiltersToSearchParams, parseCanonicalClaimsQuery } from '../../../claims/parseClaimsFilters';
import { buildActiveClaimsFilterChips, clearClaimsFilterChip } from '../../../claims/claimsFilterConfig';
import { useClaimsLedger } from '../../../claims/useClaimsLedger';
import type { ClaimsFilters } from '../../../claims/claimsClient';
import { ClaimsLedgerFilters } from '../ClaimsLedgerFilters/ClaimsLedgerFilters';
import { ClaimsLedgerTable } from '../ClaimsLedgerTable/ClaimsLedgerTable';
import { ClaimsLedgerPageHeader } from './ClaimsLedgerPageHeader';
import { ClaimsScopeBanner } from '../ClaimsScopeBanner/ClaimsScopeBanner';
import styles from './ClaimsLedgerPage.module.css';

export function ClaimsLedgerPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const canonical = useMemo(() => parseCanonicalClaimsQuery(location.search), [location.search]);

  useEffect(() => {
    if (!canonical.isCanonical) {
      navigate(
        { pathname: '/app/claims', search: canonical.canonicalSearch.replace(/^\?/, '') },
        { replace: true },
      );
    }
  }, [canonical.canonicalSearch, canonical.isCanonical, navigate]);

  const ledger = useClaimsLedger(canonical.canonicalSearch || location.search);

  const handleFilterChange = (next: ClaimsFilters) => {
    const params = claimsFiltersToSearchParams({ ...next, offset: 0 });
    const search = params.toString();
    navigate({ pathname: '/app/claims', search: search ? `?${search}` : '' });
  };

  const goToNextPage = () => {
    if (!ledger.hasMore || ledger.updating) return;
    const params = claimsFiltersToSearchParams({
      ...ledger.filters,
      offset: ledger.offset + ledger.pageSize,
    });
    navigate({ pathname: '/app/claims', search: `?${params.toString()}` });
  };

  const goToPreviousPage = () => {
    if (ledger.updating) return;
    const params = claimsFiltersToSearchParams({
      ...ledger.filters,
      offset: Math.max(0, ledger.offset - ledger.pageSize),
    });
    const search = params.toString();
    navigate({ pathname: '/app/claims', search: search ? `?${search}` : '' });
  };

  const clearFilters = () => navigate('/app/claims');

  if (ledger.permissionDenied) {
    return (
      <PageSurface>
        <PermissionDeniedPanel />
      </PageSurface>
    );
  }

  return (
    <PageSurface
      className={styles.ClaimsLedgerPage}
      data-claims-ledger-page
      {...(ledger.queryId ? { 'data-query-id': ledger.queryId } : {})}
    >
      <ClaimsLedgerPageHeader filters={ledger.filters} />
      <ClaimsScopeBanner
        activeFilters={buildActiveClaimsFilterChips(ledger.filters)}
        onRemoveFilter={(key) =>
          handleFilterChange(
            clearClaimsFilterChip(ledger.filters, key as Parameters<typeof clearClaimsFilterChip>[1]),
          )
        }
        onClearAll={clearFilters}
        totalCount={ledger.totalCount}
      />
      <div data-page-content-rail>
      <ClaimsLedgerFilters
        filters={ledger.filters}
        onChange={handleFilterChange}
      />
      <ClaimsLedgerTable
        rows={ledger.rows}
        loading={ledger.loading}
        updating={ledger.updating}
        error={ledger.error}
        empty={ledger.empty}
        filteredEmpty={ledger.filteredEmpty}
        onClearFilters={clearFilters}
        onRowActivate={(row) => navigate(`/app/claims/${row.claimRef}`)}
        onRetry={() => void ledger.refresh()}
        pagination={{
          totalCount: ledger.totalCount,
          offset: ledger.offset,
          pageSize: ledger.pageSize,
          hasMore: ledger.hasMore,
          onNext: goToNextPage,
          onPrevious: goToPreviousPage,
          disabled: ledger.updating,
        }}
      />
      </div>
    </PageSurface>
  );
}
