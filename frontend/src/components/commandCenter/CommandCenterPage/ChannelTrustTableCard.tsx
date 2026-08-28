import { useMemo, useState } from 'react';

import { channelTrustRowsForAxis } from '../../../commandCenter/commandCenterChannelFixtures';
import { channelTrustTableHeaderKeys, channelTrustTableHeaderLabel } from '../../../commandCenter/channelTrustTableDisplay';
import { COMMAND_CENTER_COPY } from '../../../commandCenter/copy';
import type { CommandCenterAggregate, ChannelTrustGroupBy } from '../../../commandCenter/types';
import { DataUnavailablePanel } from '../../trust/DataUnavailablePanel/DataUnavailablePanel';
import { RevenueReliabilityColumnHeader } from '../../trust/RevenueReliabilityColumnHeader/RevenueReliabilityColumnHeader';
import {
  ChannelTrustAxisCell,
  ChannelTrustDiscrepancyCell,
  ChannelTrustGroupByToggle,
  ChannelTrustInteractiveRow,
  ChannelTrustRevenueReliabilityCell,
  ChannelTrustPolicyCell,
  ChannelTrustVerifiedRevenueCell,
} from './ChannelTrustTableCells';
import styles from './CommandCenterSubcomponents.module.css';

export function ChannelTrustTableCard({ aggregate }: { aggregate: CommandCenterAggregate }) {
  const [groupBy, setGroupBy] = useState<ChannelTrustGroupBy>('platform');

  const rows = useMemo(() => {
    if (aggregate.channelRows.length === 0) return [];
    if (groupBy === 'platform') return aggregate.channelRows;
    return channelTrustRowsForAxis(groupBy);
  }, [aggregate.channelRows, groupBy]);

  const headerKeys = channelTrustTableHeaderKeys(groupBy);

  return (
    <div className={styles.channelTrustShell} data-channel-trust-shell>
      <div className={styles.channelTrustTabStrip}>
        <ChannelTrustGroupByToggle groupBy={groupBy} onChange={setGroupBy} />
      </div>

      <section
        data-channel-trust-table
        className={[styles.tableCard, styles.section, styles.channelTrustSection].join(' ')}
      >
        <h2 className={styles.sectionTitle}>{COMMAND_CENTER_COPY.channelTrustTable}</h2>

        {aggregate.channelRows.length === 0 ? (
          <DataUnavailablePanel
            variant="partial_data"
            reason="Channel aggregate unavailable."
            whatStillWorks="Channel overview ledger remains authoritative."
          />
        ) : (
          <div className={styles.channelTableWrap} data-channel-table-scroll-wrap>
            <table className={styles.channelTable}>
              <colgroup>
                <col className={styles.colAxis} />
                <col className={styles.colVerifiedRevenue} />
                <col className={styles.colDiscrepancy} />
                <col className={styles.colRevenueReliability} />
                <col className={styles.colPolicy} />
              </colgroup>
              <thead>
                <tr>
                  {headerKeys.map((headerKey) => (
                    <th
                      key={headerKey}
                      scope="col"
                      className={headerKey === 'axis' ? styles.colAxisHeader : undefined}
                    >
                      {headerKey === 'revenueReliability' ? (
                        <RevenueReliabilityColumnHeader />
                      ) : (
                        channelTrustTableHeaderLabel(headerKey, groupBy)
                      )}
                    </th>
                  ))}
                </tr>
              </thead>

              <tbody>
                {rows.map((row) => (
                  <ChannelTrustInteractiveRow key={`${groupBy}-${row.rowId}`} row={row} groupBy={groupBy}>
                    <td className={styles.colAxisCell}>
                      <ChannelTrustAxisCell row={row} groupBy={groupBy} rowNavigateViaRow />
                    </td>
                    <td>
                      <ChannelTrustVerifiedRevenueCell row={row} />
                    </td>
                    <td className={styles.colDiscrepancyCell}>
                      <ChannelTrustDiscrepancyCell row={row} />
                    </td>
                    <td>
                      <ChannelTrustRevenueReliabilityCell row={row} />
                    </td>
                    <td>
                      <ChannelTrustPolicyCell row={row} />
                    </td>
                  </ChannelTrustInteractiveRow>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
