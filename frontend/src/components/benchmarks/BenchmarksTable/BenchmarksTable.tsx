import { useMemo } from 'react';
import { Table, type TableColumn, type TablePagination } from '../../layout/Table/Table';
import { BENCHMARKS_COPY } from '../../../benchmarks/copy';
import { useTimedTableLoading } from '../../../lib/loading';
import type { BenchmarkRowDTO } from '../../../ledger/types';
import {
  BenchmarkActionabilityCell,
  BenchmarkComparabilityCell,
  BenchmarkCoverageCell,
  BenchmarkDecisionSafeValueCell,
  BenchmarkEvidenceCell,
  BenchmarkNameCell,
  BenchmarkRawValueCell,
  BenchmarkSuppressionCell,
} from './BenchmarksTableCells';
import styles from './BenchmarksTable.module.css';
import shared from '../../../styles/shared.module.css';

export interface BenchmarksTableProps {
  rows: BenchmarkRowDTO[];
  totalCount: number;
  loading?: boolean;
  updating?: boolean;
  error?: string;
  empty?: boolean;
  filteredEmpty?: boolean;
  onClearFilters?: () => void;
  onRowActivate?: (row: BenchmarkRowDTO) => void;
  pagination?: TablePagination;
  onRetry?: () => void;
}

export function BenchmarksTable({
  rows,
  totalCount,
  loading,
  updating = false,
  error,
  empty,
  filteredEmpty,
  onClearFilters,
  onRowActivate,
  pagination,
  onRetry,
}: BenchmarksTableProps) {
  const columns: TableColumn<BenchmarkRowDTO>[] = useMemo(
    () => [
      {
        key: 'benchmarkName',
        colClassName: styles.colBenchmarkName,
        header: BENCHMARKS_COPY.table.benchmarkName,
        render: (row) => <BenchmarkNameCell row={row} />,
      },
      {
        key: 'rawBenchmark',
        colClassName: styles.colRawBenchmark,
        header: BENCHMARKS_COPY.table.rawBenchmark,
        render: (row) => <BenchmarkRawValueCell row={row} />,
      },
      {
        key: 'decisionSafeBenchmark',
        colClassName: styles.colDecisionSafeBenchmark,
        header: BENCHMARKS_COPY.table.decisionSafeBenchmark,
        render: (row) => <BenchmarkDecisionSafeValueCell row={row} />,
      },
      {
        key: 'evidenceClass',
        colClassName: styles.colEvidenceClass,
        header: BENCHMARKS_COPY.table.evidenceClass,
        render: (row) => <BenchmarkEvidenceCell row={row} />,
      },
      {
        key: 'coverageClass',
        colClassName: styles.colCoverageClass,
        header: BENCHMARKS_COPY.table.coverageClass,
        render: (row) => <BenchmarkCoverageCell row={row} />,
      },
      {
        key: 'suppressionReason',
        colClassName: styles.colSuppressionReason,
        header: BENCHMARKS_COPY.table.suppressionReason,
        render: (row) => <BenchmarkSuppressionCell row={row} />,
      },
      {
        key: 'comparability',
        colClassName: styles.colComparability,
        header: BENCHMARKS_COPY.table.comparableToPrevious,
        render: (row) => <BenchmarkComparabilityCell row={row} />,
      },
      {
        key: 'actionability',
        colClassName: styles.colActionability,
        header: BENCHMARKS_COPY.table.actionability,
        render: (row) => <BenchmarkActionabilityCell row={row} />,
      },
    ],
    [styles],
  );

  const initialLoad = !!(loading && rows.length === 0);
  const timedLoading = useTimedTableLoading(initialLoad, {
    progressCopy: BENCHMARKS_COPY.table.loadingProgress,
    onRetry,
  });

  let state: import('../../layout/Table/Table').TableState = 'populated';
  if (error) state = 'error';
  else if (timedLoading) state = timedLoading.state;
  else if (filteredEmpty) state = 'filtered_empty';
  else if (empty) state = 'empty';

  const pageStart = pagination ? pagination.offset + 1 : 1;
  const pageEnd = pagination ? pagination.offset + rows.length : rows.length;
  const total = pagination?.totalCount ?? totalCount;

  return (
    <section
      className={styles.tableCard}
      data-benchmarks-results
      aria-labelledby="benchmark-results-heading"
    >
      <div className={styles.tableHeader}>
        <div className={styles.headerLeft}>
          <h2 id="benchmark-results-heading" className={styles.sectionTitle}>
            {BENCHMARKS_COPY.table.sectionTitle}
          </h2>
          <span className={styles.envelopeCount} data-benchmark-envelope-count>
            {BENCHMARKS_COPY.table.envelopeCount(totalCount)}
          </span>
        </div>
        <button type="button" className={styles.overflowMenu} aria-label="Table actions">
          ⋮
        </button>
      </div>

      {updating ? (
        <p className={styles.updatingBanner} role="status" aria-live="polite" data-benchmarks-updating>
          {BENCHMARKS_COPY.table.updating}
        </p>
      ) : null}

      <div className={[styles.tableWrapStandard, updating ? styles.staleRows : ''].filter(Boolean).join(' ')}>
        <Table
          caption={BENCHMARKS_COPY.table.caption}
          captionVisibility="visuallyHidden"
          columns={columns}
          rows={rows}
          state={state}
          progressCopy={timedLoading?.progressCopy}
          onRetry={timedLoading?.onRetry}
          errorMessage={error}
          emptyTitle={BENCHMARKS_COPY.table.empty}
          emptyDescription={filteredEmpty ? BENCHMARKS_COPY.table.filteredEmpty : undefined}
          onClearFilters={onClearFilters}
          onRowActivate={onRowActivate}
          getRowKey={(row) => row.benchmarkId}
          variant="embedded"
          showPagination={false}
        />
      </div>

      {pagination && total > 0 ? (
        <div className={styles.paginationFooter} data-benchmarks-pagination>
          <span className={styles.pageInfo}>
            {BENCHMARKS_COPY.pagination.range(pageStart, pageEnd, total)}
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
