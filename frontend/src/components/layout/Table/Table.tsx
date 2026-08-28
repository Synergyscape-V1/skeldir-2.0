import { Fragment, type KeyboardEvent, type ReactNode } from 'react';
import { ERROR_COPY, LOADING_COPY } from '../../../lib/copy';
import { enforceDomRowCap as capDomRows, MAX_DOM_TABLE_ROWS } from '../../../operationalAudit/pagination';
import { EmptyState } from '../EmptyState/EmptyState';
import { ErrorBanner } from '../ErrorBanner/ErrorBanner';
import { Skeleton } from '../Skeleton/Skeleton';
import shared from '../../../styles/shared.module.css';
import styles from './Table.module.css';

export interface TableColumn<T> {
  key: string;
  header: ReactNode;
  render: (row: T) => ReactNode;
  colClassName?: string;
  headerClassName?: string;
  cellClassName?: string;
}

export type TableState =
  | 'loading_under_2s'
  | 'loading_over_2s'
  | 'loading_over_8s'
  | 'empty'
  | 'filtered_empty'
  | 'populated'
  | 'error'
  | 'permission_denied';

export interface TablePagination {
  totalCount: number;
  offset: number;
  pageSize: number;
  hasMore: boolean;
  onPrevious?: () => void;
  onNext?: () => void;
  disabled?: boolean;
}

export interface TableCursorPagination {
  loadedCount: number;
  hasMore: boolean;
  onLoadMore?: () => void;
  disabled?: boolean;
  loadedCountLabel?: string;
  loadMoreLabel?: string;
  loadingMoreLabel?: string;
}

export interface TableProps<T> {
  caption: string;
  captionVisibility?: 'visible' | 'visuallyHidden';
  columns: TableColumn<T>[];
  rows?: T[];
  state?: TableState;
  density?: 'dense' | 'standard';
  variant?: 'standalone' | 'embedded';
  showPagination?: boolean;
  progressCopy?: string;
  onRetry?: () => void;
  onClearFilters?: () => void;
  onRowActivate?: (row: T) => void;
  emptyTitle?: string;
  emptyDescription?: string;
  errorMessage?: string;
  getRowKey: (row: T) => string;
  pagination?: TablePagination;
  cursorPagination?: TableCursorPagination;
  loadingMore?: boolean;
  enforceDomRowCap?: boolean;
  getRowClassName?: (row: T) => string | undefined;
  /** When set with renderExpandedRow, inserts a full-width expansion row under the matching key. */
  expandedRowKey?: string | null;
  renderExpandedRow?: (row: T) => ReactNode;
}

export function Table<T>({
  caption,
  captionVisibility = 'visible',
  columns,
  rows = [],
  state = 'populated',
  density = 'standard',
  variant = 'standalone',
  showPagination = true,
  progressCopy,
  onRetry,
  onClearFilters,
  onRowActivate,
  emptyTitle,
  emptyDescription,
  errorMessage,
  getRowKey,
  pagination,
  cursorPagination,
  loadingMore,
  enforceDomRowCap = true,
  getRowClassName,
  expandedRowKey = null,
  renderExpandedRow,
}: TableProps<T>) {
  if (!caption) {
    return (
      <div className={shared.errorState} role="alert">
        {ERROR_COPY.missingRequiredProp('caption')}
      </div>
    );
  }

  if (state === 'error') {
    return <ErrorBanner variant="error" message={errorMessage ?? ERROR_COPY.trustApiReadFailed} />;
  }

  if (state === 'permission_denied') {
    return <ErrorBanner variant="permission_denied" />;
  }

  if (state.startsWith('loading')) {
    return (
      <div className={styles.wrapper} aria-busy="true">
        <Skeleton rows={3} variant="row" />
        {(state === 'loading_over_2s' || state === 'loading_over_8s') && (
          <p className={styles.progress} aria-live="polite">
            {progressCopy ?? 'Still loading verified trust state…'}
          </p>
        )}
        {state === 'loading_over_8s' && onRetry ? (
          <button type="button" className={[styles.retry, shared.focusVisible].join(' ')} onClick={onRetry}>
            {LOADING_COPY.retry}
          </button>
        ) : null}
        {state === 'loading_over_8s' && !onRetry ? (
          <div className={shared.errorState} role="alert">
            {ERROR_COPY.missingRequiredProp('onRetry')}
          </div>
        ) : null}
      </div>
    );
  }

  if (state === 'empty') {
    return (
      <EmptyState
        title={emptyTitle ?? 'No data'}
        description={emptyDescription}
        variant="default"
      />
    );
  }

  if (state === 'filtered_empty') {
    return (
      <EmptyState
        title={emptyTitle ?? 'No claims match these filters.'}
        description={emptyDescription ?? 'Clear filters.'}
        variant="filtered"
        onClearFilters={onClearFilters}
      />
    );
  }

  const rowHeightClass = density === 'dense' ? styles.rowDense : styles.rowStandard;
  const boundedRows = enforceDomRowCap ? capDomRows(rows) : rows;
  const pageStart = pagination ? pagination.offset + 1 : 1;
  const pageEnd = pagination
    ? pagination.offset + boundedRows.length
    : boundedRows.length;

  const handleRowKeyDown = (event: KeyboardEvent<HTMLTableRowElement>, row: T) => {
    if (event.key === 'Enter' && onRowActivate) {
      onRowActivate(row);
    }
  };

  const embedded = variant === 'embedded';
  const wrapperClass = embedded ? styles.wrapperEmbedded : styles.wrapper;
  const tableClass = embedded ? styles.tableEmbedded : styles.table;

  return (
    <div className={wrapperClass}>
      <table
        className={tableClass}
        data-table-row-count={boundedRows.length}
        data-table-max-rows={MAX_DOM_TABLE_ROWS}
        data-table-variant={variant}
      >
        <caption
          className={[styles.caption, captionVisibility === 'visuallyHidden' ? shared.srOnly : '']
            .filter(Boolean)
            .join(' ')}
        >
          {caption}
        </caption>
        {columns.some((col) => col.colClassName) ? (
          <colgroup>
            {columns.map((col) => (
              <col key={col.key} className={col.colClassName} />
            ))}
          </colgroup>
        ) : null}
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col.key} scope="col" className={col.headerClassName}>
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {boundedRows.map((row) => {
            const rowKey = getRowKey(row);
            const isExpanded = Boolean(renderExpandedRow && expandedRowKey && expandedRowKey === rowKey);
            return (
              <Fragment key={rowKey}>
                <tr
                  className={[
                    rowHeightClass,
                    onRowActivate ? styles.interactive : '',
                    isExpanded ? styles.rowExpanded : '',
                    getRowClassName?.(row) ?? '',
                  ]
                    .filter(Boolean)
                    .join(' ')}
                  {...(onRowActivate ? { 'data-table-row-interactive': true } : {})}
                  {...(isExpanded ? { 'data-table-row-expanded-trigger': true } : {})}
                  tabIndex={onRowActivate ? 0 : undefined}
                  onKeyDown={(e) => handleRowKeyDown(e, row)}
                  onClick={onRowActivate ? () => onRowActivate(row) : undefined}
                  aria-expanded={renderExpandedRow ? isExpanded : undefined}
                >
                  {columns.map((col) => (
                    <td key={col.key} className={col.cellClassName}>
                      {col.render(row)}
                    </td>
                  ))}
                </tr>
                {isExpanded && renderExpandedRow ? (
                  <tr className={styles.expandedRow} data-table-expanded-row={rowKey}>
                    <td colSpan={columns.length} className={styles.expandedCell}>
                      {renderExpandedRow(row)}
                    </td>
                  </tr>
                ) : null}
              </Fragment>
            );
          })}
        </tbody>
      </table>
      {pagination && showPagination ? (
        <nav className={styles.pagination} aria-label="Table pagination" data-table-pagination>
          <span className={styles.pageInfo}>
            {pagination.totalCount === 0
              ? 'No rows'
              : `Showing ${pageStart}–${pageEnd} of ${pagination.totalCount}`}
          </span>
          <div className={styles.pageControls}>
            <button
              type="button"
              className={[styles.pageButton, shared.focusVisible].join(' ')}
              onClick={pagination.onPrevious}
              disabled={pagination.disabled || pagination.offset <= 0}
              aria-label="Previous page"
            >
              Previous
            </button>
            <button
              type="button"
              className={[styles.pageButton, shared.focusVisible].join(' ')}
              onClick={pagination.onNext}
              disabled={pagination.disabled || !pagination.hasMore}
              aria-label="Next page"
            >
              Next
            </button>
          </div>
        </nav>
      ) : null}
      {cursorPagination ? (
        <nav
          className={styles.pagination}
          aria-label="Audit timeline pagination"
          data-table-cursor-pagination
        >
          <span className={styles.pageInfo} data-loaded-count={cursorPagination.loadedCount}>
            {cursorPagination.loadedCount}{' '}
            {cursorPagination.loadedCountLabel ?? 'rows loaded'}
          </span>
          {cursorPagination.hasMore ? (
            <button
              type="button"
              className={[styles.pageButton, shared.focusVisible].join(' ')}
              onClick={cursorPagination.onLoadMore}
              disabled={cursorPagination.disabled || loadingMore}
              aria-busy={loadingMore || undefined}
              data-load-more
            >
              {loadingMore
                ? (cursorPagination.loadingMoreLabel ?? 'Loading more…')
                : (cursorPagination.loadMoreLabel ?? 'Load more')}
            </button>
          ) : null}
        </nav>
      ) : null}
    </div>
  );
}
