import { useEffect, useMemo, useState } from 'react';
import { COMMAND_CENTER_COPY } from '../../../commandCenter/copy';
import {
  RECENT_ENVELOPES_SNAPSHOT_ROW_COUNT,
  recentSignalWindowLabel,
} from '../../../commandCenter/recentEnvelopesConstants';
import type { CommandCenterAggregate } from '../../../commandCenter/types';
import { IconChevronRight } from '../../icons/StatusIcons';
import shared from '../../../styles/shared.module.css';
import styles from './CommandCenterSubcomponents.module.css';
import {
  RecentEnvelopeInteractiveRow,
  RecentEnvelopeMatchVerdictCell,
  RecentEnvelopePolicyCell,
  RecentEnvelopeSubjectCell,
  RecentEnvelopeTrustSignalCell,
  RecentEnvelopeVerifiedRevenueCell,
} from './RecentTrustEnvelopesCells';

const COL = COMMAND_CENTER_COPY.recentEnvelopeTableColumns;
const PAGE_SIZE = RECENT_ENVELOPES_SNAPSHOT_ROW_COUNT;

function RecentEnvelopeTablePager({
  pageIndex,
  totalPages,
  totalRows,
  onPrevious,
  onNext,
}: {
  pageIndex: number;
  totalPages: number;
  totalRows: number;
  onPrevious: () => void;
  onNext: () => void;
}) {
  const start = pageIndex * PAGE_SIZE + 1;
  const end = Math.min(totalRows, (pageIndex + 1) * PAGE_SIZE);
  const pagerCopy = COMMAND_CENTER_COPY.recentEnvelopesPager;

  return (
    <nav
      className={styles.recentEnvelopeTablePager}
      aria-label={pagerCopy.label}
      data-recent-envelope-table-pager
    >
      <span className={styles.recentEnvelopeTablePagerStatus} data-recent-envelope-table-page-status>
        {pagerCopy.pageStatus(start, end, totalRows)}
      </span>
      <div className={styles.recentEnvelopeTablePagerButtons}>
        <button
          type="button"
          className={[styles.recentEnvelopeTablePagerButton, shared.focusVisible].join(' ')}
          onClick={onPrevious}
          disabled={pageIndex <= 0}
          aria-label={pagerCopy.previous}
          data-recent-envelope-table-prev
        >
          <IconChevronRight className={styles.recentEnvelopeTablePagerIconPrevious} />
        </button>
        <button
          type="button"
          className={[styles.recentEnvelopeTablePagerButton, shared.focusVisible].join(' ')}
          onClick={onNext}
          disabled={pageIndex >= totalPages - 1}
          aria-label={pagerCopy.next}
          data-recent-envelope-table-next
        >
          <IconChevronRight className={styles.recentEnvelopeTablePagerIconNext} />
        </button>
      </div>
    </nav>
  );
}

export function RecentTrustEnvelopesCard({ aggregate }: { aggregate: CommandCenterAggregate }) {
  const windowLabel = recentSignalWindowLabel(aggregate.recentEnvelopesSignalWindow);
  const [pageIndex, setPageIndex] = useState(0);

  const rows = aggregate.recentEnvelopes;
  // Integer ceiling division for a page count (not a money path):
  // (n + PAGE_SIZE - 1) divided exactly, after removing the remainder.
  const pageSpan = rows.length + PAGE_SIZE - 1;
  const totalPages = Math.max(1, (pageSpan - (pageSpan % PAGE_SIZE)) / PAGE_SIZE);

  useEffect(() => {
    setPageIndex((current) => Math.min(current, totalPages - 1));
  }, [rows.length, totalPages]);

  const visibleRows = useMemo(
    () => rows.slice(pageIndex * PAGE_SIZE, pageIndex * PAGE_SIZE + PAGE_SIZE),
    [rows, pageIndex],
  );

  return (
    <section data-recent-trust-envelopes className={[styles.tableCard, styles.section].join(' ')}>
      <div className={styles.channelTrustTableHeader}>
        <h2 className={styles.sectionTitle}>{COMMAND_CENTER_COPY.recentEnvelopes}</h2>
        <div className={styles.recentEnvelopeTableHeaderActions}>
          <p className={styles.envelopeWindowMeta} data-recent-envelopes-window>
            {windowLabel}
          </p>
          {rows.length > PAGE_SIZE ? (
            <RecentEnvelopeTablePager
              pageIndex={pageIndex}
              totalPages={totalPages}
              totalRows={rows.length}
              onPrevious={() => setPageIndex((current) => Math.max(0, current - 1))}
              onNext={() => setPageIndex((current) => Math.min(totalPages - 1, current + 1))}
            />
          ) : null}
        </div>
      </div>

      {rows.length === 0 ? (
        <p className={styles.emptyState}>No TrustEnvelopes yet.</p>
      ) : (
        <div
          className={[styles.channelTableWrap, styles.envelopeTableWrap].join(' ')}
          data-envelope-table-scroll-wrap
          data-channel-table-scroll-wrap
        >
          <table
            className={[styles.channelTable, styles.envelopeTable, styles.recentEnvelopeTable].join(' ')}
          >
            <colgroup>
              <col className={styles.colRecentSubject} />
              <col className={styles.colRecentVerifiedRevenue} />
              <col className={styles.colRecentMatchVerdict} />
              <col className={styles.colRecentPolicy} />
              <col className={styles.colRecentSignal} />
            </colgroup>
            <thead>
              <tr>
                <th scope="col">{COL.subjectRef}</th>
                <th scope="col">{COL.verifiedRevenue}</th>
                <th scope="col">{COL.matchVerdict}</th>
                <th scope="col">{COL.policyAuthority}</th>
                <th scope="col">{COL.trustSignal}</th>
              </tr>
            </thead>
            <tbody data-recent-envelope-table-page={pageIndex}>
              {visibleRows.map((row) => (
                <RecentEnvelopeInteractiveRow key={row.envelopeId} row={row}>
                  <td className={styles.colRecentSubjectCell}>
                    <RecentEnvelopeSubjectCell row={row} />
                  </td>
                  <td className={styles.colRecentVerifiedRevenueCell}>
                    <RecentEnvelopeVerifiedRevenueCell row={row} />
                  </td>
                  <td className={styles.colRecentMatchVerdictCell}>
                    <RecentEnvelopeMatchVerdictCell row={row} />
                  </td>
                  <td className={styles.colRecentPolicyCell}>
                    <RecentEnvelopePolicyCell row={row} />
                  </td>
                  <td className={styles.colRecentSignalCell}>
                    <RecentEnvelopeTrustSignalCell row={row} />
                  </td>
                </RecentEnvelopeInteractiveRow>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
