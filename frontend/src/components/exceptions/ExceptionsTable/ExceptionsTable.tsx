import { useMemo } from 'react';
import { CompactLedgerRow } from '../../ledger/CompactLedgerRow/CompactLedgerRow';
import { Table, type TableColumn, type TablePagination } from '../../layout/Table/Table';
import { EXCEPTIONS_PAGE_COPY } from '../../../exceptions/copy';
import { useTimedTableLoading } from '../../../lib/loading';
import type { ExceptionQueueRowDTO } from '../../../ledger/types';
import {
  ExceptionActionCell,
  ExceptionAffectedObjectCell,
  ExceptionAuditEventCell,
  ExceptionCategoryCell,
  ExceptionCreatedAgeCell,
  ExceptionPolicyCell,
  ExceptionSeverityCell,
  ExceptionStatusCell,
  ExceptionSummaryCell,
} from './ExceptionsTableCells';
import styles from './ExceptionsTable.module.css';
import shared from '../../../styles/shared.module.css';

export interface ExceptionsTableProps {
  rows: ExceptionQueueRowDTO[];
  totalCount: number;
  loading?: boolean;
  updating?: boolean;
  error?: string;
  empty?: boolean;
  filteredEmpty?: boolean;
  onClearFilters?: () => void;
  onReview: (row: ExceptionQueueRowDTO, trigger: HTMLButtonElement) => void;
  pagination?: TablePagination;
  onRetry?: () => void;
}

export function ExceptionsTable({
  rows,
  totalCount,
  loading,
  updating = false,
  error,
  empty,
  filteredEmpty,
  onClearFilters,
  onReview,
  pagination,
  onRetry,
}: ExceptionsTableProps) {
  const columns: TableColumn<ExceptionQueueRowDTO>[] = useMemo(
    () => [
      {
        key: 'severity',
        colClassName: styles.colSeverity,
        header: EXCEPTIONS_PAGE_COPY.table.severity,
        render: (row) => <ExceptionSeverityCell row={row} />,
      },
      {
        key: 'category',
        colClassName: styles.colCategory,
        header: EXCEPTIONS_PAGE_COPY.table.category,
        render: (row) => <ExceptionCategoryCell row={row} />,
      },
      {
        key: 'summary',
        colClassName: styles.colSummary,
        header: EXCEPTIONS_PAGE_COPY.table.summary,
        render: (row) => <ExceptionSummaryCell row={row} />,
      },
      {
        key: 'affectedObject',
        colClassName: styles.colAffectedObject,
        header: EXCEPTIONS_PAGE_COPY.table.affectedObject,
        render: (row) => <ExceptionAffectedObjectCell row={row} />,
      },
      {
        key: 'policyAuthority',
        colClassName: styles.colPolicy,
        header: EXCEPTIONS_PAGE_COPY.table.policyAuthority,
        render: (row) => <ExceptionPolicyCell row={row} />,
      },
      {
        key: 'lastAuditEvent',
        colClassName: styles.colAuditEvent,
        header: EXCEPTIONS_PAGE_COPY.table.lastAuditEvent,
        render: (row) => <ExceptionAuditEventCell row={row} />,
      },
      {
        key: 'createdAge',
        colClassName: styles.colCreatedAge,
        header: EXCEPTIONS_PAGE_COPY.table.createdAge,
        render: (row) => <ExceptionCreatedAgeCell row={row} />,
      },
      {
        key: 'status',
        colClassName: styles.colStatus,
        header: EXCEPTIONS_PAGE_COPY.table.status,
        render: (row) => <ExceptionStatusCell row={row} />,
      },
      {
        key: 'action',
        colClassName: styles.colAction,
        header: EXCEPTIONS_PAGE_COPY.table.action,
        render: (row) => (
          <ExceptionActionCell row={row} disabled={updating} onReview={onReview} />
        ),
      },
    ],
    [onReview, updating],
  );

  const initialLoad = !!(loading && rows.length === 0);
  const timedLoading = useTimedTableLoading(initialLoad, {
    progressCopy: EXCEPTIONS_PAGE_COPY.table.loadingProgress,
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
  const total = stalePagination?.totalCount ?? totalCount;

  return (
    <>
      <section
        className={styles.tableCard}
        data-exceptions-table
        data-exceptions-results
        data-query-updating={updating ? 'true' : undefined}
        aria-busy={updating ? 'true' : undefined}
        aria-labelledby="exceptions-results-heading"
      >
        <div className={styles.tableHeader}>
          <h2 id="exceptions-results-heading" className={styles.sectionTitle}>
            {EXCEPTIONS_PAGE_COPY.table.sectionTitle}
          </h2>
          <button type="button" className={styles.overflowMenu} aria-label="Table actions">
            ⋮
          </button>
        </div>

        {updating ? (
          <p className={styles.updatingBanner} role="status" aria-live="polite" data-exceptions-updating>
            {EXCEPTIONS_PAGE_COPY.table.updating}
          </p>
        ) : null}

        <div
          className={[styles.tableWrapDense, updating ? styles.staleRows : ''].filter(Boolean).join(' ')}
          data-ledger-desktop
        >
          <Table
            caption={EXCEPTIONS_PAGE_COPY.table.caption}
            captionVisibility="visuallyHidden"
            columns={columns}
            rows={rows}
            state={state}
            progressCopy={timedLoading?.progressCopy}
            onRetry={timedLoading?.onRetry}
            errorMessage={error}
            emptyTitle={EXCEPTIONS_PAGE_COPY.table.empty}
            emptyDescription={filteredEmpty ? EXCEPTIONS_PAGE_COPY.table.filteredEmpty : undefined}
            onClearFilters={onClearFilters}
            getRowKey={(row) => row.exceptionId}
            density="dense"
            variant="embedded"
            showPagination={false}
          />
        </div>

        {stalePagination && total > 0 ? (
          <div className={styles.paginationFooter} data-exceptions-pagination>
            <span className={styles.pageInfo}>
              {EXCEPTIONS_PAGE_COPY.pagination.range(pageStart, pageEnd, total)}
            </span>
            <div className={styles.pageControls}>
              <button
                type="button"
                className={[styles.pageButton, shared.focusVisible].join(' ')}
                onClick={stalePagination.onPrevious}
                disabled={stalePagination.disabled || stalePagination.offset <= 0}
                aria-label={EXCEPTIONS_PAGE_COPY.pagination.previous}
              >
                ←
              </button>
              <button
                type="button"
                className={[styles.pageButton, shared.focusVisible].join(' ')}
                onClick={stalePagination.onNext}
                disabled={stalePagination.disabled || !stalePagination.hasMore}
                aria-label={EXCEPTIONS_PAGE_COPY.pagination.next}
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
                key={row.exceptionId}
                rowKey={row.exceptionId}
                identity={<ExceptionSeverityCell row={row} />}
                status={<ExceptionStatusCell row={row} />}
                primaryFields={[
                  {
                    key: 'summary',
                    label: EXCEPTIONS_PAGE_COPY.table.summary,
                    value: <ExceptionSummaryCell row={row} />,
                  },
                  {
                    key: 'category',
                    label: EXCEPTIONS_PAGE_COPY.table.category,
                    value: <ExceptionCategoryCell row={row} />,
                  },
                  {
                    key: 'affectedObject',
                    label: EXCEPTIONS_PAGE_COPY.table.affectedObject,
                    value: <ExceptionAffectedObjectCell row={row} />,
                  },
                ]}
                secondaryFields={[
                  {
                    key: 'policyAuthority',
                    label: EXCEPTIONS_PAGE_COPY.table.policyAuthority,
                    value: <ExceptionPolicyCell row={row} />,
                  },
                  {
                    key: 'lastAuditEvent',
                    label: EXCEPTIONS_PAGE_COPY.table.lastAuditEvent,
                    value: <ExceptionAuditEventCell row={row} />,
                  },
                  {
                    key: 'createdAge',
                    label: EXCEPTIONS_PAGE_COPY.table.createdAge,
                    value: <ExceptionCreatedAgeCell row={row} />,
                  },
                  {
                    key: 'action',
                    label: EXCEPTIONS_PAGE_COPY.table.action,
                    value: <ExceptionActionCell row={row} disabled={updating} onReview={onReview} />,
                  },
                ]}
              />
            ))
          : null}
      </div>
    </>
  );
}
