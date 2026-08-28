import { Table, type TableColumn, type TablePagination } from '../../layout/Table/Table';
import { TRUST_ENVELOPE_INDEX_COLUMN_KEYS, TRUST_ENVELOPE_INDEX_COPY } from '../../../trustIndex/copy';
import { LOADING_COPY } from '../../../lib/copy';
import { useTimedTableLoading } from '../../../lib/loading';
import type { TrustEnvelopeIndexRowDTO } from '../../../ledger/types';
import {
  TrustIndexAttributionModelCell,
  TrustIndexAuditCell,
  TrustIndexClaimSourceCell,
  TrustIndexClaimTimeCell,
  TrustIndexClaimedRevenueCell,
  TrustIndexConfidenceCell,
  TrustIndexDifferenceCell,
  TrustIndexMatchVerdictCell,
  TrustIndexPolicyAuthorityCell,
  TrustIndexVerifiedRevenueCell,
} from './TrustEnvelopeIndexTableCells';
import styles from './TrustEnvelopeIndexTable.module.css';
import shared from '../../../styles/shared.module.css';

export interface TrustEnvelopeIndexTableProps {
  rows: TrustEnvelopeIndexRowDTO[];
  loading?: boolean;
  updating?: boolean;
  error?: string;
  empty?: boolean;
  filteredEmpty?: boolean;
  onClearFilters?: () => void;
  pagination?: TablePagination;
  sortKey?: string;
  sortDirection?: 'asc' | 'desc';
  density?: 'standard' | 'dense';
  readOnly?: boolean;
  onRetry?: () => void;
}

export { TRUST_ENVELOPE_INDEX_COLUMN_KEYS };

export function buildTrustEnvelopeIndexColumns({
  updating,
  readOnly,
  tableStyles,
}: {
  updating?: boolean;
  readOnly?: boolean;
  tableStyles: typeof styles;
}): TableColumn<TrustEnvelopeIndexRowDTO>[] {
  const disabled = updating || readOnly;

  return [
    {
      key: 'claimTime',
      colClassName: tableStyles.colClaimTime,
      header: TRUST_ENVELOPE_INDEX_COPY.table.claimTime,
      render: (row) => <TrustIndexClaimTimeCell row={row} />,
    },
    {
      key: 'claimSource',
      colClassName: tableStyles.colClaimSource,
      header: TRUST_ENVELOPE_INDEX_COPY.table.claimSource,
      render: (row) => <TrustIndexClaimSourceCell row={row} />,
    },
    {
      key: 'claimedRevenue',
      colClassName: tableStyles.colClaimedRevenue,
      header: TRUST_ENVELOPE_INDEX_COPY.table.claimedRevenue,
      render: (row) => <TrustIndexClaimedRevenueCell row={row} />,
    },
    {
      key: 'verifiedRevenue',
      colClassName: tableStyles.colVerifiedRevenue,
      header: TRUST_ENVELOPE_INDEX_COPY.table.verifiedRevenue,
      render: (row) => <TrustIndexVerifiedRevenueCell row={row} />,
    },
    {
      key: 'difference',
      colClassName: tableStyles.colDifference,
      cellClassName: tableStyles.cellDifference,
      header: TRUST_ENVELOPE_INDEX_COPY.table.difference,
      render: (row) => <TrustIndexDifferenceCell row={row} />,
    },
    {
      key: 'matchVerdict',
      colClassName: tableStyles.colMatchVerdict,
      header: TRUST_ENVELOPE_INDEX_COPY.table.matchVerdict,
      render: (row) => <TrustIndexMatchVerdictCell row={row} />,
    },
    {
      key: 'attributionModel',
      colClassName: tableStyles.colAttributionModel,
      header: TRUST_ENVELOPE_INDEX_COPY.table.attributionModel,
      render: (row) => <TrustIndexAttributionModelCell row={row} />,
    },
    {
      key: 'confidence',
      colClassName: tableStyles.colConfidence,
      header: TRUST_ENVELOPE_INDEX_COPY.table.confidence,
      render: (row) => <TrustIndexConfidenceCell row={row} />,
    },
    {
      key: 'policyAuthority',
      colClassName: tableStyles.colPolicyAuthority,
      header: TRUST_ENVELOPE_INDEX_COPY.table.policyAuthority,
      render: (row) => <TrustIndexPolicyAuthorityCell row={row} />,
    },
    {
      key: 'audit',
      colClassName: tableStyles.colAudit,
      header: TRUST_ENVELOPE_INDEX_COPY.table.audit,
      render: (row) => <TrustIndexAuditCell row={row} disabled={disabled} />,
    },
  ];
}

export function TrustEnvelopeIndexTable({
  rows,
  loading,
  updating = false,
  error,
  empty,
  filteredEmpty,
  onClearFilters,
  pagination,
  density = 'dense',
  readOnly = false,
  onRetry,
}: TrustEnvelopeIndexTableProps) {
  const columns = buildTrustEnvelopeIndexColumns({
    updating,
    readOnly,
    tableStyles: styles,
  });

  const initialLoad = !!(loading && rows.length === 0);
  const timedLoading = useTimedTableLoading(initialLoad, { progressCopy: LOADING_COPY.progress, onRetry });

  let state: import('../../layout/Table/Table').TableState = 'populated';
  if (error) state = 'error';
  else if (timedLoading) state = timedLoading.state;
  else if (filteredEmpty) state = 'filtered_empty';
  else if (empty) state = 'empty';

  const pageStart = pagination ? pagination.offset + 1 : 1;
  const pageEnd = pagination ? pagination.offset + rows.length : rows.length;
  const total = pagination?.totalCount ?? rows.length;

  return (
    <section
      className={styles.tableCard}
      data-trust-index-table
      data-query-updating={updating ? 'true' : undefined}
      data-trust-index-read-only={readOnly ? 'true' : undefined}
      aria-labelledby="trust-envelope-index-table-heading"
    >
      <div className={styles.tableHeader}>
        <h2 id="trust-envelope-index-table-heading" className={styles.sectionTitle}>
          {TRUST_ENVELOPE_INDEX_COPY.table.sectionTitle}
        </h2>
        <button type="button" className={styles.overflowMenu} aria-label="Table actions" disabled={readOnly}>
          ⋮
        </button>
      </div>
      {updating ? (
        <p className={styles.updatingBanner} role="status" aria-live="polite">
          {TRUST_ENVELOPE_INDEX_COPY.table.updating}
        </p>
      ) : null}
      <div
        className={[
          density === 'dense' ? styles.tableWrapDense : styles.tableWrapStandard,
          updating ? styles.staleRows : '',
        ]
          .filter(Boolean)
          .join(' ')}
      >
        <Table
          caption={TRUST_ENVELOPE_INDEX_COPY.table.caption}
          captionVisibility="visuallyHidden"
          columns={columns}
          rows={rows}
          state={state}
          progressCopy={timedLoading?.progressCopy}
          onRetry={timedLoading?.onRetry}
          errorMessage={error}
          emptyTitle={TRUST_ENVELOPE_INDEX_COPY.table.empty}
          emptyDescription={filteredEmpty ? TRUST_ENVELOPE_INDEX_COPY.table.filteredEmpty : undefined}
          onClearFilters={onClearFilters}
          getRowKey={(r) => r.envelopeId}
          density={density}
          variant="embedded"
          showPagination={false}
        />
      </div>
      {pagination && total > 0 ? (
        <div className={styles.paginationFooter} data-trust-index-pagination>
          <span className={styles.pageInfo}>
            {TRUST_ENVELOPE_INDEX_COPY.table.paginationRange(pageStart, pageEnd, total)}
          </span>
          <div className={styles.pageControls}>
            <button
              type="button"
              className={[styles.pageButton, shared.focusVisible].join(' ')}
              onClick={pagination.onPrevious}
              disabled={pagination.disabled || pagination.offset <= 0}
              aria-label="Previous page"
            >
              ←
            </button>
            <button
              type="button"
              className={[styles.pageButton, shared.focusVisible].join(' ')}
              onClick={pagination.onNext}
              disabled={pagination.disabled || !pagination.hasMore}
              aria-label="Next page"
            >
              →
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}
