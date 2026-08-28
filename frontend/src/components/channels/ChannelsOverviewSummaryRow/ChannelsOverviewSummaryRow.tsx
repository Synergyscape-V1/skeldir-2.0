import { Link } from 'react-router-dom';
import type { ChannelOverviewSummary } from '../../../ledger/types';
import { formatMoneyMinorDisplay } from '../../../lib/money';
import { CHANNELS_OVERVIEW_COPY } from '../../../channels/copy';
import { buildChannelExpandHref } from '../../../channels/channelExpandHref';
import { COMMAND_CENTER_CHIP_PROPS, COMMAND_CENTER_POLICY_CHIP_PROPS } from '../../../commandCenter/commandCenterChipProps';
import { formatDiscrepancySummaryRate } from '../../../channels/channelsSummary';
import { AuthorityBadge } from '../../trust/AuthorityBadge/AuthorityBadge';
import { PolicyAuthorityPill } from '../../trust/PolicyAuthorityPill/PolicyAuthorityPill';
import { IconArrowUpRight } from '../../icons/StatusIcons';
import shared from '../../../styles/shared.module.css';
import styles from './ChannelsOverviewSummaryRow.module.css';

export interface ChannelsOverviewSummaryRowProps {
  summary: ChannelOverviewSummary;
  loading?: boolean;
}

function TileDrillDown({ href, metricId }: { href: string; metricId: string }) {
  return (
    <div className={styles.actionFooter}>
      <Link
        to={href}
        className={[styles.drillDown, shared.focusVisible].join(' ')}
        data-summary-drilldown={metricId}
      >
        <span>{CHANNELS_OVERVIEW_COPY.summary.openChannel}</span>
        <IconArrowUpRight className={styles.drillDownChevron} />
      </Link>
    </div>
  );
}

export function ChannelsOverviewSummaryRow({ summary, loading = false }: ChannelsOverviewSummaryRowProps) {
  const highestDisplay = formatMoneyMinorDisplay(summary.highestVerifiedRevenueMinor, summary.currencyCode);
  const bestActionDisplay = formatMoneyMinorDisplay(summary.bestActionReadyRevenueMinor, summary.currencyCode);

  return (
    <section
      className={styles.section}
      data-channels-summary-row
      aria-busy={loading ? 'true' : undefined}
      aria-label="Channel trust summary"
    >
      <div className={styles.grid}>
        <article className={styles.card} data-summary-metric="highest_verified_revenue">
          <div className={styles.body}>
            <div className={styles.topRow}>
              <span className={styles.label}>{CHANNELS_OVERVIEW_COPY.summary.highestVerifiedRevenue}</span>
              <span className={styles.chip}>
                <AuthorityBadge authority="deterministic" {...COMMAND_CENTER_CHIP_PROPS} />
              </span>
            </div>
            {summary.highestVerifiedRevenueChannelName ? (
              <span className={styles.channelName}>{summary.highestVerifiedRevenueChannelName}</span>
            ) : null}
            <span className={styles.value} data-summary-metric-value="highest_verified_revenue">
              {highestDisplay}
            </span>
            {summary.highestVerifiedRevenueDeltaLabel ? (
              <span className={[styles.meta, styles.metaSuccess].join(' ')}>
                {summary.highestVerifiedRevenueDeltaLabel}
              </span>
            ) : null}
          </div>
          {summary.highestVerifiedRevenueChannelId ? (
            <TileDrillDown
              href={buildChannelExpandHref(summary.highestVerifiedRevenueChannelId)}
              metricId="highest_verified_revenue"
            />
          ) : null}
        </article>

        <article className={styles.card} data-summary-metric="largest_discrepancy">
          <div className={styles.body}>
            <div className={styles.topRow}>
              <span className={styles.label}>{CHANNELS_OVERVIEW_COPY.summary.largestDiscrepancy}</span>
              <span className={styles.chip}>
                <AuthorityBadge authority="deterministic" {...COMMAND_CENTER_CHIP_PROPS} />
              </span>
            </div>
            {summary.largestDiscrepancyChannelName ? (
              <span className={styles.channelName}>{summary.largestDiscrepancyChannelName}</span>
            ) : null}
            <span
              className={[styles.value, styles.valueError].join(' ')}
              data-summary-metric-value="largest_discrepancy"
            >
              {formatDiscrepancySummaryRate(summary.largestDiscrepancyRateBps)}
            </span>
            {summary.largestDiscrepancyComparisonLabel ? (
              <span className={styles.meta}>{summary.largestDiscrepancyComparisonLabel}</span>
            ) : null}
          </div>
          {summary.largestDiscrepancyChannelId ? (
            <TileDrillDown
              href={buildChannelExpandHref(summary.largestDiscrepancyChannelId)}
              metricId="largest_discrepancy"
            />
          ) : null}
        </article>

        <article className={styles.card} data-summary-metric="lowest_confidence">
          <div className={styles.body}>
            <div className={styles.topRow}>
              <span className={styles.label}>{CHANNELS_OVERVIEW_COPY.summary.lowestConfidence}</span>
              <span className={styles.chip}>
                <AuthorityBadge authority="unavailable" {...COMMAND_CENTER_CHIP_PROPS} />
              </span>
            </div>
            {summary.lowestConfidenceChannelName ? (
              <span className={styles.channelName}>{summary.lowestConfidenceChannelName}</span>
            ) : null}
            <span
              className={[styles.value, styles.valueWarning].join(' ')}
              data-summary-metric-value="lowest_confidence"
            >
              {CHANNELS_OVERVIEW_COPY.summary.confidenceDegraded}
            </span>
            <span className={styles.meta}>{summary.lowestConfidenceLabel}</span>
          </div>
          {summary.lowestConfidenceChannelId ? (
            <TileDrillDown
              href={buildChannelExpandHref(summary.lowestConfidenceChannelId)}
              metricId="lowest_confidence"
            />
          ) : null}
        </article>

        <article className={styles.card} data-summary-metric="best_action_ready">
          <div className={styles.body}>
            <div className={styles.topRow}>
              <span className={styles.label}>{CHANNELS_OVERVIEW_COPY.summary.bestActionReady}</span>
              {summary.bestActionReadyPolicyAuthority ? (
                <span className={styles.chip}>
                  <PolicyAuthorityPill
                    state={summary.bestActionReadyPolicyAuthority}
                    {...COMMAND_CENTER_POLICY_CHIP_PROPS}
                  />
                </span>
              ) : null}
            </div>
            {summary.bestActionReadyChannelName ? (
              <span className={styles.channelName}>{summary.bestActionReadyChannelName}</span>
            ) : null}
            <span className={styles.value} data-summary-metric-value="best_action_ready">
              {bestActionDisplay}
            </span>
            {summary.bestActionReadyBenchmarkLabel ? (
              <span className={[styles.meta, styles.metaSuccess].join(' ')}>
                {summary.bestActionReadyBenchmarkLabel}
              </span>
            ) : null}
          </div>
          {summary.bestActionReadyChannelId ? (
            <TileDrillDown
              href={buildChannelExpandHref(summary.bestActionReadyChannelId)}
              metricId="best_action_ready"
            />
          ) : null}
        </article>
      </div>
    </section>
  );
}
