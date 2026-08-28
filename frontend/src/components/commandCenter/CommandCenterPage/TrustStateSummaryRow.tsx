import { Link } from 'react-router-dom';

import type {
  CommandCenterAggregate,
  FinancialTruthSummaryMetric,
  SupervisoryHealthSummaryMetric,
  SummaryMetric,
} from '../../../commandCenter/types';

import { formatMoneyMinorDisplayWithCents } from '../../../lib/money';

import { COMMAND_CENTER_CHIP_PROPS } from '../../../commandCenter/commandCenterChipProps';

import { IconArrowUpRight, IconTrendDown, IconTrendNeutral, IconTrendUp } from '../../icons/StatusIcons';
import { AuthorityBadge } from '../../trust/AuthorityBadge/AuthorityBadge';

import shared from '../../../styles/shared.module.css';

import styles from './CommandCenterSubcomponents.module.css';

function SummaryTrendIcon({ direction }: { direction: 'positive' | 'negative' | 'neutral' }) {
  const className = styles.summaryTrendIcon;
  if (direction === 'positive') return <IconTrendUp className={className} />;
  if (direction === 'negative') return <IconTrendDown className={className} />;
  return <IconTrendNeutral className={className} />;
}

function TileDrillDown({ metric }: { metric: SummaryMetric }) {
  return (
    <div className={styles.summaryActionFooter}>
      <Link
        to={metric.drillDownHref}
        className={[styles.summaryDrillDown, shared.focusVisible].join(' ')}
        data-summary-drilldown={metric.id}
      >
        <span>{metric.drillDownLabel}</span>
        <IconArrowUpRight className={styles.summaryDrillDownChevron} />
      </Link>
    </div>
  );
}

function FinancialTruthTile({ metric }: { metric: FinancialTruthSummaryMetric }) {
  const valueText =
    metric.valueMinor !== undefined && metric.currencyCode
      ? formatMoneyMinorDisplayWithCents(metric.valueMinor, metric.currencyCode)
      : (metric.displayValue ?? '—');

  const isCurrencyLong =
    metric.valueMinor !== undefined && metric.currencyCode && valueText.length > 20;

  return (
    <article
      className={styles.summaryCard}
      data-summary-metric={metric.id}
      data-summary-tile-kind="financial_truth"
      data-source-surface={metric.sourceSurface}
    >
      <div className={styles.summaryBody}>
        <div className={styles.summaryTopRow}>
          <span className={styles.summaryLabel}>{metric.label}</span>
          {metric.id === 'verified_revenue' ? (
            <span className={styles.summaryChip}>
              <AuthorityBadge authority={metric.authority} {...COMMAND_CENTER_CHIP_PROPS} />
            </span>
          ) : null}
        </div>

        <span
          className={isCurrencyLong ? styles.metricValueLong : styles.metricValue}
          data-summary-metric-value={metric.id}
        >
          {valueText}
        </span>

        {metric.subLabel ? <span className={styles.summarySubLabel}>{metric.subLabel}</span> : null}

        {metric.trendLabel ? (
          <span
            className={[
              styles.trendRow,
              metric.trendDirection === 'positive'
                ? styles.trendPositive
                : metric.trendDirection === 'negative'
                  ? styles.trendNegative
                  : styles.trendNeutral,
            ].join(' ')}
            data-summary-trend={metric.id}
          >
            <SummaryTrendIcon
              direction={
                metric.trendDirection === 'positive'
                  ? 'positive'
                  : metric.trendDirection === 'negative'
                    ? 'negative'
                    : 'neutral'
              }
            />
            <span>{metric.trendLabel}</span>
          </span>
        ) : null}
      </div>

      <TileDrillDown metric={metric} />
    </article>
  );
}

function SupervisoryHealthTile({ metric }: { metric: SupervisoryHealthSummaryMetric }) {
  const valueClassName = [
    styles.supervisoryMetricValue,
    metric.valueTone === 'warning'
      ? styles.supervisoryMetricValueWarning
      : metric.valueTone === 'error'
        ? styles.supervisoryMetricValueError
        : metric.valueTone === 'success'
          ? styles.supervisoryMetricValueSuccess
          : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <article
      className={styles.summaryCard}
      data-summary-metric={metric.id}
      data-summary-tile-kind="supervisory_health"
      data-source-surface={metric.sourceSurface}
    >
      <div className={styles.summaryBody}>
        <div className={styles.summaryTopRow}>
          <span className={styles.summaryLabel}>{metric.label}</span>
        </div>

        <span className={valueClassName} data-summary-metric-value={metric.id}>
          {metric.displayValue}
        </span>

        {metric.subLabel ? <span className={styles.summarySubLabel}>{metric.subLabel}</span> : null}
      </div>

      <TileDrillDown metric={metric} />
    </article>
  );
}

function SummaryCard({ metric }: { metric: SummaryMetric }) {
  if (metric.tileKind === 'financial_truth') {
    return <FinancialTruthTile metric={metric} />;
  }
  return <SupervisoryHealthTile metric={metric} />;
}

/** Routine retrospective metrics — always rendered in the subordinate SummaryPlane. */
function isSummaryPlaneMetric(metric: SummaryMetric): metric is FinancialTruthSummaryMetric {
  return metric.tileKind === 'financial_truth';
}

/** Action-required supervisory metrics — rendered in the dominant TriagePlane. */
function isTriagePlaneMetric(metric: SummaryMetric): metric is SupervisoryHealthSummaryMetric {
  return metric.tileKind === 'supervisory_health';
}

export function TrustStateSummaryRow({ aggregate }: { aggregate: CommandCenterAggregate }) {
  const triageMetrics = aggregate.summaryMetrics.filter(isTriagePlaneMetric);
  const summaryMetrics = aggregate.summaryMetrics.filter(isSummaryPlaneMetric);
  const hasBlockers = triageMetrics.length > 0;

  return (
    <section data-trust-state-summary-row className={styles.bifurcatedSummarySection}>
      <div className={styles.summaryPlane} data-summary-plane="active">
        <div className={styles.summaryGrid}>
          {summaryMetrics.map((metric) => (
            <SummaryCard key={metric.id} metric={metric} />
          ))}
        </div>
      </div>

      {hasBlockers ? (
        <div className={styles.triagePlane} data-triage-plane aria-live="assertive">
          <div className={styles.triagePlaneGrid}>
            {triageMetrics.map((metric) => (
              <SupervisoryHealthTile key={metric.id} metric={metric} />
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}
