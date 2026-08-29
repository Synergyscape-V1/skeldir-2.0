import { Link } from 'react-router-dom';

import { COMMAND_CENTER_COPY } from '../../../commandCenter/copy';

import type { CommandCenterAggregate } from '../../../commandCenter/types';

import { COMMAND_CENTER_CHIP_PROPS } from '../../../commandCenter/commandCenterChipProps';

import { AuthorityBadge } from '../../trust/AuthorityBadge/AuthorityBadge';

import { VerifiedRevenueChart } from '../VerifiedRevenueChart/VerifiedRevenueChart';

import styles from './CommandCenterSubcomponents.module.css';

export function VerifiedRevenueTrendCard({ aggregate }: { aggregate: CommandCenterAggregate }) {
  const hasTrend = aggregate.trendPoints.length > 0 && !aggregate.trendUnavailable;

  return (
    <section
      data-verified-revenue-trend
      className={[styles.chartCard, styles.chartCardCompact, styles.section].join(' ')}
      aria-label={COMMAND_CENTER_COPY.verifiedRevenueTrend}
    >
      <div className={styles.chartHeader}>
        <div className={styles.chartHeaderPrimary}>
          <h2 className={styles.sectionTitle}>{COMMAND_CENTER_COPY.verifiedRevenueTrend}</h2>
          <p className={styles.meta}>{COMMAND_CENTER_COPY.verifiedRevenueTrendSubtitle}</p>
        </div>
        <div className={styles.chartMeta} data-trend-authority-corner>
          <AuthorityBadge authority="deterministic" {...COMMAND_CENTER_CHIP_PROPS} />
          <span className={styles.meta}>{COMMAND_CENTER_COPY.trendWindowLabel}</span>
        </div>
      </div>

      <p className={hasTrend ? styles.srOnlySummary : styles.meta} data-trend-accessible-summary>
        {hasTrend
          ? `${COMMAND_CENTER_COPY.verifiedRevenueTrend}: ${aggregate.trendPoints.length} daily B2.10 snapshot windows, ${COMMAND_CENTER_COPY.trendWindowLabel.toLowerCase()}.`
          : COMMAND_CENTER_COPY.trendEmptyTitle}
      </p>

      {hasTrend ? (
        <div className={styles.chartPlotRegion}>
          <VerifiedRevenueChart
            points={aggregate.trendPoints}
            showClaimedOverlay={aggregate.trendMeta?.claimedOverlayEnabled ?? false}
          />
        </div>
      ) : (
        <div className={styles.trendEmpty} data-trend-unavailable>
          <p className={styles.trendEmptyTitle}>{COMMAND_CENTER_COPY.trendEmptyTitle}</p>
          <p className={styles.meta}>{aggregate.trendUnavailable?.reason ?? COMMAND_CENTER_COPY.trendEmptyBody}</p>
          <Link to="/app/integrations" className={styles.drillDown}>
            {COMMAND_CENTER_COPY.trendEmptyAction}
          </Link>
        </div>
      )}
    </section>
  );
}
