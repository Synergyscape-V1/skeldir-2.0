import { useMemo, type ReactNode } from 'react';
import { Table, type TableColumn, type TablePagination } from '../../layout/Table/Table';
import { CHANNELS_OVERVIEW_COPY } from '../../../channels/copy';
import { useTimedTableLoading } from '../../../lib/loading';
import type { ChannelOverviewRowDTO } from '../../../ledger/types';
import { CHANNELS_PAGE_SIZE_OPTIONS } from '../../../channels/channelsPagination';
import { RevenueReliabilityColumnHeader } from '../../trust/RevenueReliabilityColumnHeader/RevenueReliabilityColumnHeader';
import {
  ChannelsRevenueReliabilityCell,
  ChannelsAttributionChannelCell,
  ChannelsBayesianCell,
  ChannelsClaimSourceCell,
  ChannelsClaimedRevenueCell,
  ChannelsDiscrepancyCell,
  ChannelsOpenCell,
  ChannelsPolicyCell,
  ChannelsVerifiedRevenueCell,
} from './ChannelsOverviewTableCells';
import cellStyles from './ChannelsOverviewTableCells.module.css';
import styles from './ChannelsOverviewTable.module.css';
import shared from '../../../styles/shared.module.css';

export interface ChannelsOverviewTableProps {
  rows: ChannelOverviewRowDTO[];
  loading?: boolean;
  updating?: boolean;
  error?: string;
  empty?: boolean;
  filteredEmpty?: boolean;
  onClearFilters?: () => void;
  onRowActivate?: (row: ChannelOverviewRowDTO) => void;
  expandedChannelId?: string | null;
  renderExpandedRow?: (row: ChannelOverviewRowDTO) => ReactNode;
  pagination?: TablePagination;
  sortKey?: string;
  sortDirection?: 'asc' | 'desc';
  onSortChange?: (sortKey: string) => void;
  pageSize?: number;
  onPageSizeChange?: (pageSize: number) => void;
  onRetry?: () => void;
}

function SortHeader({
  label,
  sortKey,
  activeSortKey,
  sortDirection,
  onSortChange,
}: {
  label: ReactNode;
  sortKey: string;
  activeSortKey?: string;
  sortDirection?: 'asc' | 'desc';
  onSortChange?: (sortKey: string) => void;
}) {
  const active = activeSortKey === sortKey;
  return (
    <button
      type="button"
      className={[cellStyles.sortableHeader, shared.focusVisible].join(' ')}
      aria-sort={active ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'}
      onClick={() => onSortChange?.(sortKey)}
      data-channels-sort={sortKey}
    >
      <span>{label}</span>
      {active ? (
        <span className={cellStyles.sortIndicator} aria-hidden>
          {sortDirection === 'asc' ? '↑' : '↓'}
        </span>
      ) : (
        <span className={cellStyles.sortIndicator} aria-hidden>
          ↕
        </span>
      )}
    </button>
  );
}

export function ChannelsOverviewTable({
  rows,
  loading,
  updating = false,
  error,
  empty,
  filteredEmpty,
  onClearFilters,
  onRowActivate,
  expandedChannelId = null,
  renderExpandedRow,
  pagination,
  sortKey,
  sortDirection,
  onSortChange,
  pageSize,
  onPageSizeChange,
  onRetry,
}: ChannelsOverviewTableProps) {
  const columns: TableColumn<ChannelOverviewRowDTO>[] = useMemo(
    () => [
      {
        key: 'attributionChannel',
        colClassName: styles.colAttributionChannel,
        cellClassName: styles.cellAttributionChannel,
        header: (
          <SortHeader
            label={CHANNELS_OVERVIEW_COPY.table.attributionChannel}
            sortKey="attributionChannel"
            activeSortKey={sortKey}
            sortDirection={sortDirection}
            onSortChange={onSortChange}
          />
        ),
        render: (row) => (
          <ChannelsAttributionChannelCell
            row={row}
            expanded={expandedChannelId === row.channelId}
            onToggle={onRowActivate}
          />
        ),
      },
      {
        key: 'claimSource',
        colClassName: styles.colClaimSource,
        cellClassName: styles.cellClaimSource,
        header: (
          <SortHeader
            label={CHANNELS_OVERVIEW_COPY.table.claimSource}
            sortKey="claimSource"
            activeSortKey={sortKey}
            sortDirection={sortDirection}
            onSortChange={onSortChange}
          />
        ),
        render: (row) => <ChannelsClaimSourceCell row={row} />,
      },
      {
        key: 'verifiedRevenue',
        colClassName: styles.colVerifiedRevenue,
        header: (
          <SortHeader
            label={CHANNELS_OVERVIEW_COPY.table.verifiedRevenue}
            sortKey="verifiedRevenue"
            activeSortKey={sortKey}
            sortDirection={sortDirection}
            onSortChange={onSortChange}
          />
        ),
        render: (row) => <ChannelsVerifiedRevenueCell row={row} />,
      },
      {
        key: 'claimedRevenue',
        colClassName: styles.colClaimedRevenue,
        header: (
          <SortHeader
            label={CHANNELS_OVERVIEW_COPY.table.claimedRevenue}
            sortKey="claimedRevenue"
            activeSortKey={sortKey}
            sortDirection={sortDirection}
            onSortChange={onSortChange}
          />
        ),
        render: (row) => <ChannelsClaimedRevenueCell row={row} />,
      },
      {
        key: 'discrepancyRate',
        colClassName: styles.colDiscrepancy,
        header: CHANNELS_OVERVIEW_COPY.table.discrepancyRate,
        render: (row) => <ChannelsDiscrepancyCell row={row} />,
      },
      {
        key: 'revenueReliability',
        colClassName: styles.colAttribution,
        header: (
          <SortHeader
            label={<RevenueReliabilityColumnHeader />}
            sortKey="attributionAgreement"
            activeSortKey={sortKey}
            sortDirection={sortDirection}
            onSortChange={onSortChange}
          />
        ),
        render: (row) => <ChannelsRevenueReliabilityCell row={row} />,
      },
      {
        key: 'bayesianStatus',
        colClassName: styles.colBayesian,
        header: (
          <SortHeader
            label={CHANNELS_OVERVIEW_COPY.table.bayesianStatus}
            sortKey="bayesianStatus"
            activeSortKey={sortKey}
            sortDirection={sortDirection}
            onSortChange={onSortChange}
          />
        ),
        render: (row) => <ChannelsBayesianCell row={row} />,
      },
      {
        key: 'policyAuthority',
        colClassName: styles.colPolicy,
        header: (
          <SortHeader
            label={CHANNELS_OVERVIEW_COPY.table.actionAuthority}
            sortKey="policyAuthority"
            activeSortKey={sortKey}
            sortDirection={sortDirection}
            onSortChange={onSortChange}
          />
        ),
        render: (row) => <ChannelsPolicyCell row={row} />,
      },
      {
        key: 'open',
        colClassName: styles.colOpen,
        header: <span className={cellStyles.srOnly}>{CHANNELS_OVERVIEW_COPY.table.open}</span>,
        render: (row) => (
          <ChannelsOpenCell
            row={row}
            disabled={updating}
            expanded={expandedChannelId === row.channelId}
            onToggle={onRowActivate}
          />
        ),
      },
    ],
    [expandedChannelId, onRowActivate, onSortChange, sortDirection, sortKey, updating, styles],
  );

  const initialLoad = !!(loading && rows.length === 0);
  const timedLoading = useTimedTableLoading(initialLoad, {
    progressCopy: CHANNELS_OVERVIEW_COPY.table.loadingProgress,
    onRetry,
  });

  let state: import('../../layout/Table/Table').TableState = 'populated';
  if (error) state = 'error';
  else if (timedLoading) state = timedLoading.state;
  else if (filteredEmpty) state = 'filtered_empty';
  else if (empty) state = 'empty';

  const pageStart = pagination ? pagination.offset + 1 : 1;
  const pageEnd = pagination ? pagination.offset + rows.length : rows.length;
  const total = pagination?.totalCount ?? rows.length;

  return (
    <section className={styles.tableCard} data-channels-trust-table>
      <div className={styles.tableHeader}>
        <h2 className={styles.sectionTitle}>{CHANNELS_OVERVIEW_COPY.table.sectionTitle}</h2>
        <button type="button" className={styles.overflowMenu} aria-label="Table actions">
          ⋮
        </button>
      </div>
      {updating ? (
        <p className={styles.updatingBanner} role="status" aria-live="polite" data-channels-updating>
          {CHANNELS_OVERVIEW_COPY.table.updating}
        </p>
      ) : null}
      <div className={[styles.tableWrapStandard, updating ? styles.staleRows : ''].filter(Boolean).join(' ')}>
        <Table
          caption={CHANNELS_OVERVIEW_COPY.table.caption}
          captionVisibility="visuallyHidden"
          columns={columns}
          rows={rows}
          state={state}
          progressCopy={timedLoading?.progressCopy}
          onRetry={timedLoading?.onRetry}
          errorMessage={error}
          emptyTitle={CHANNELS_OVERVIEW_COPY.table.empty}
          emptyDescription={filteredEmpty ? CHANNELS_OVERVIEW_COPY.table.filteredEmpty : undefined}
          onClearFilters={onClearFilters}
          onRowActivate={onRowActivate}
          expandedRowKey={expandedChannelId}
          renderExpandedRow={renderExpandedRow}
          getRowKey={(row) => row.channelId}
          variant="embedded"
          showPagination={false}
        />
      </div>
      {pagination && total > 0 ? (
        <div className={styles.paginationFooter} data-channels-pagination>
          <label className={styles.pageSizeField}>
            <span>{CHANNELS_OVERVIEW_COPY.table.rowsPerPage}</span>
            <select
              className={[styles.pageSizeSelect, shared.focusVisible].join(' ')}
              value={pageSize ?? pagination.pageSize}
              disabled={pagination.disabled}
              aria-label={CHANNELS_OVERVIEW_COPY.table.rowsPerPage}
              onChange={(event) => onPageSizeChange?.(Number.parseInt(event.target.value, 10))}
            >
              {CHANNELS_PAGE_SIZE_OPTIONS.map((size) => (
                <option key={size} value={size}>
                  {size}
                </option>
              ))}
            </select>
          </label>
          <span className={styles.pageInfo}>
            {CHANNELS_OVERVIEW_COPY.pagination.range(pageStart, pageEnd, total)}
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
