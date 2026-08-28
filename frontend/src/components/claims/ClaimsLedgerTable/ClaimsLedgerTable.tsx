import { CompactLedgerRow } from '../../ledger/CompactLedgerRow/CompactLedgerRow';
import { Table, type TableColumn, type TablePagination } from '../../layout/Table/Table';
import { CLAIMS_LEDGER_PAGE_COPY } from '../../../claims/copy';
import { LEDGER_COPY } from '../../../ledger/copy';
import { useTimedTableLoading } from '../../../lib/loading';
import type { ClaimLedgerRowDTO } from '../../../ledger/types';
import { useMemo } from 'react';
import {
  AttributionModelCell,
  AuditOpenCell,
  CampaignClassCell,
  ClaimedRevenueCell,
  ClaimPlatformSourceCell,
  ClaimsLedgerConfidenceCell,
  ClaimTimeCell,
  CommerceRailCell,
  DifferenceCell,
  MatchVerdictCell,
  PolicyAuthorityCell,
  VerifiedRevenueCell,
} from './ClaimsLedgerTableCells';
import styles from './ClaimsLedgerTable.module.css';
import shared from '../../../styles/shared.module.css';

export interface ClaimsLedgerTableProps {
  rows: ClaimLedgerRowDTO[];
  loading?: boolean;
  updating?: boolean;
  error?: string;
  empty?: boolean;
  filteredEmpty?: boolean;
  onClearFilters?: () => void;
  onRowActivate?: (row: ClaimLedgerRowDTO) => void;
  pagination?: TablePagination;
  onRetry?: () => void;
}

export const CLAIMS_LEDGER_COLUMNS: TableColumn<ClaimLedgerRowDTO>[] = [
  { key: 'claimTime', header: 'Claim time', render: (row) => <ClaimTimeCell row={row} /> },
  {
    key: 'claimSource',
    header: 'Claim source (platform)',
    render: (row) => <ClaimPlatformSourceCell row={row} />,
  },
  {
    key: 'campaignClass',
    header: 'Campaign class',
    render: (row) => <CampaignClassCell row={row} />,
  },
  {
    key: 'commerceRail',
    header: 'Commerce rail',
    render: (row) => <CommerceRailCell row={row} />,
  },
  { key: 'claimedRevenue', header: 'Claimed revenue', render: (row) => <ClaimedRevenueCell row={row} /> },
  { key: 'verifiedRevenue', header: 'Verified revenue', render: (row) => <VerifiedRevenueCell row={row} /> },
  { key: 'difference', header: 'Difference', render: (row) => <DifferenceCell row={row} /> },
  { key: 'matchVerdict', header: 'Match verdict', render: (row) => <MatchVerdictCell row={row} /> },
  { key: 'attributionModel', header: 'Attribution model', render: (row) => <AttributionModelCell row={row} /> },
  {
    key: 'confidence',
    header: 'Confidence',
    render: (row) => <ClaimsLedgerConfidenceCell confidence={row.confidence} />,
  },
  { key: 'policyAuthority', header: 'Policy authority', render: (row) => <PolicyAuthorityCell row={row} /> },
  { key: 'audit', header: 'Audit', render: (row) => <AuditOpenCell row={row} /> },
];

function claimsColumnClassName(key: string, tableStyles: typeof styles): string | undefined {
  switch (key) {
    case 'claimTime':
      return tableStyles.colClaimTime;
    case 'claimSource':
      return tableStyles.colClaimSource;
    case 'campaignClass':
      return tableStyles.colCampaignClass;
    case 'commerceRail':
      return tableStyles.colCommerceRail;
    case 'claimedRevenue':
      return tableStyles.colClaimedRevenue;
    case 'verifiedRevenue':
      return tableStyles.colVerifiedRevenue;
    case 'difference':
      return tableStyles.colDifference;
    case 'matchVerdict':
      return tableStyles.colMatchVerdict;
    case 'attributionModel':
      return tableStyles.colAttributionModel;
    case 'confidence':
      return tableStyles.colConfidence;
    case 'policyAuthority':
      return tableStyles.colPolicyAuthority;
    case 'audit':
      return tableStyles.colAudit;
    default:
      return undefined;
  }
}

export function ClaimsLedgerTable({
  rows,
  loading,
  updating = false,
  error,
  empty,
  filteredEmpty,
  onClearFilters,
  onRowActivate,
  pagination,
  onRetry,
}: ClaimsLedgerTableProps) {
  const columns: TableColumn<ClaimLedgerRowDTO>[] = useMemo(
    () =>
      CLAIMS_LEDGER_COLUMNS.map((column) => ({
        ...column,
        colClassName: claimsColumnClassName(column.key, styles),
        cellClassName:
          column.key === 'claimSource'
            ? styles.cellClaimSource
            : column.key === 'campaignClass'
              ? styles.cellCampaignClass
              : column.key === 'commerceRail'
                ? styles.cellCommerceRail
                : column.key === 'difference'
                  ? styles.cellDifference
                  : column.key === 'confidence'
                    ? styles.cellConfidence
                    : column.key === 'audit'
                      ? styles.cellAudit
                      : undefined,
        headerClassName: column.key === 'confidence' ? styles.colConfidence : undefined,
        render: (row) => {
          if (column.key === 'audit') {
            return <AuditOpenCell row={row} disabled={updating} />;
          }
          return column.render(row);
        },
      })),
    [updating, styles],
  );

  const initialLoad = !!(loading && rows.length === 0);
  const timedLoading = useTimedTableLoading(initialLoad, {
    progressCopy: LEDGER_COPY.loadingProgress,
    onRetry,
  });

  let state: import('../../layout/Table/Table').TableState = 'populated';
  if (error) state = 'error';
  else if (timedLoading) state = timedLoading.state;
  else if (filteredEmpty) state = 'filtered_empty';
  else if (empty) state = 'empty';

  const stalePagination = pagination
    ? { ...pagination, disabled: updating || pagination.disabled }
    : undefined;

  const pageStart = stalePagination ? stalePagination.offset + 1 : 1;
  const pageEnd = stalePagination ? stalePagination.offset + rows.length : rows.length;
  const total = stalePagination?.totalCount ?? rows.length;

  return (
    <>
      <section
        className={styles.tableCard}
        data-claims-ledger-table
        data-query-updating={updating ? 'true' : undefined}
        aria-busy={updating ? 'true' : undefined}
        aria-labelledby="claims-ledger-table-heading"
      >
        <div className={styles.tableHeader}>
          <h2 id="claims-ledger-table-heading" className={styles.sectionTitle}>
            {CLAIMS_LEDGER_PAGE_COPY.table.sectionTitle}
          </h2>
          <button type="button" className={styles.overflowMenu} aria-label="Table actions">
            ⋮
          </button>
        </div>
        {updating ? (
          <p className={styles.updatingBanner} role="status" aria-live="polite" data-ledger-updating>
            {CLAIMS_LEDGER_PAGE_COPY.table.updating}
          </p>
        ) : null}
        <div className={[styles.tableWrapDense, updating ? styles.staleRows : ''].filter(Boolean).join(' ')} data-ledger-desktop>
          <Table
            caption={CLAIMS_LEDGER_PAGE_COPY.table.caption}
            captionVisibility="visuallyHidden"
            columns={columns}
            rows={rows}
            state={state}
            progressCopy={timedLoading?.progressCopy}
            onRetry={timedLoading?.onRetry}
            errorMessage={error}
            emptyTitle={LEDGER_COPY.emptyClaims}
            emptyDescription={filteredEmpty ? LEDGER_COPY.emptyClaimsFiltered : undefined}
            onClearFilters={onClearFilters}
            onRowActivate={onRowActivate}
            getRowKey={(row) => row.claimRef}
            density="dense"
            variant="embedded"
            showPagination={false}
          />
        </div>
        {stalePagination && total > 0 ? (
          <div className={styles.paginationFooter} data-claims-pagination>
            <span className={styles.pageInfo}>
              {CLAIMS_LEDGER_PAGE_COPY.table.paginationRange(pageStart, pageEnd, total)}
            </span>
            <div className={styles.pageControls}>
              <button
                type="button"
                className={[styles.pageButton, shared.focusVisible].join(' ')}
                onClick={stalePagination.onPrevious}
                disabled={stalePagination.disabled || stalePagination.offset <= 0}
                aria-label="Previous page"
              >
                ←
              </button>
              <button
                type="button"
                className={[styles.pageButton, shared.focusVisible].join(' ')}
                onClick={stalePagination.onNext}
                disabled={stalePagination.disabled || !stalePagination.hasMore}
                aria-label="Next page"
              >
                →
              </button>
            </div>
          </div>
        ) : null}
      </section>
      <div className={[styles.mobileList, updating ? styles.staleRows : ''].filter(Boolean).join(' ')} data-ledger-mobile>
        {!loading && !error
          ? rows.map((row) => (
              <CompactLedgerRow
                key={row.claimRef}
                rowKey={row.claimRef}
                identity={<ClaimTimeCell row={row} />}
                status={<MatchVerdictCell row={row} />}
                primaryFields={[
                  { key: 'claimSource', label: 'Claim source (platform)', value: <ClaimPlatformSourceCell row={row} /> },
                  { key: 'campaignClass', label: 'Campaign class', value: <CampaignClassCell row={row} /> },
                  { key: 'commerceRail', label: 'Commerce rail', value: <CommerceRailCell row={row} /> },
                  { key: 'claimedRevenue', label: 'Claimed revenue', value: <ClaimedRevenueCell row={row} /> },
                  { key: 'verifiedRevenue', label: 'Verified revenue', value: <VerifiedRevenueCell row={row} /> },
                  { key: 'difference', label: 'Difference', value: <DifferenceCell row={row} /> },
                ]}
                secondaryFields={[
                  {
                    key: 'attributionModel',
                    label: 'Attribution model',
                    value: <AttributionModelCell row={row} />,
                  },
                  {
                    key: 'confidence',
                    label: 'Confidence',
                    value: <ClaimsLedgerConfidenceCell confidence={row.confidence} />,
                  },
                  {
                    key: 'policyAuthority',
                    label: 'Policy authority',
                    value: <PolicyAuthorityCell row={row} />,
                  },
                  {
                    key: 'audit',
                    label: 'Audit',
                    value: <AuditOpenCell row={row} disabled={updating} />,
                  },
                ]}
              />
            ))
          : null}
      </div>
    </>
  );
}
