import { AuthorityBadge } from '../../trust/AuthorityBadge/AuthorityBadge';
import { BUDGET_SIMULATION_COPY } from '../../../budget/copy';
import type { BudgetSimulationResultDTO } from '../../../budget/budgetSimulationTypes';
import { formatBpsAsPercentOneDecimal, formatMoneyMinorDisplay } from '../../../lib/money';
import styles from './PolicyImpactCard.module.css';

export interface PolicyImpactCardProps {
  result: BudgetSimulationResultDTO;
}

export function PolicyImpactCard({ result }: PolicyImpactCardProps) {
  const {
    currencyCode,
    currentBlendedRoasBps,
    currentTotalRevenueMinor,
    projectedBlendedRoasBps,
    projectedTotalRevenueMinor,
    expectedRevenueLiftBps,
    blendedCacChangeBps,
    spendDeltaBps,
    confidenceInterval,
    sensitivityRange,
    impactAuthority,
  } = result;

  const roasDeltaPrefix = expectedRevenueLiftBps >= 0 ? '+' : '';
  const cacDeltaPrefix = blendedCacChangeBps >= 0 ? '+' : '';
  const spendDeltaPrefix = spendDeltaBps >= 0 ? '+' : '';

  const roasPositive = expectedRevenueLiftBps >= 0;
  const cacPositive = blendedCacChangeBps >= 0;
  const spendPositive = spendDeltaBps >= 0;

  return (
    <section
      className={styles.panel}
      aria-label={BUDGET_SIMULATION_COPY.expectedImpact.title}
      data-policy-impact-card
    >
      <div className={styles.headerRow}>
        <h3 className={styles.title}>{BUDGET_SIMULATION_COPY.expectedImpact.title}</h3>
        <AuthorityBadge authority={impactAuthority} size="table" />
      </div>

      {/* Primary: Baseline vs Projected ROAS */}
      <div className={styles.primaryComparison}>
        <div className={styles.baselineBlock}>
          <span className={styles.metricLabel}>Current ROAS</span>
          <span className={styles.metricValue}>
            {formatBpsAsPercentOneDecimal(currentBlendedRoasBps)}
          </span>
          <span className={styles.metricSublabel}>
            {formatMoneyMinorDisplay(currentTotalRevenueMinor, currencyCode)} revenue
          </span>
        </div>

        <div className={styles.arrowIndicator} aria-hidden="true">
          →
        </div>

        <div className={styles.projectedBlock}>
          <span className={styles.metricLabel}>Projected ROAS</span>
          <span className={styles.metricValue}>
            {formatBpsAsPercentOneDecimal(projectedBlendedRoasBps)}
          </span>
          <span className={styles.metricSublabel}>
            {formatMoneyMinorDisplay(projectedTotalRevenueMinor, currencyCode)} revenue
          </span>
        </div>
      </div>

      {/* Secondary: Delta Display */}
      <div className={styles.deltaRow}>
        <div className={styles.deltaMetric}>
          <span className={styles.deltaLabel}>Revenue Impact</span>
          <span className={[styles.deltaValue, roasPositive ? styles.positive : styles.negative].join(' ')}>
            {roasDeltaPrefix}
            {formatBpsAsPercentOneDecimal(expectedRevenueLiftBps)}
          </span>
        </div>

        <div className={styles.deltaMetric}>
          <span className={styles.deltaLabel}>CAC Change</span>
          <span className={[styles.deltaValue, cacPositive ? styles.positive : styles.negative].join(' ')}>
            {cacDeltaPrefix}
            {formatBpsAsPercentOneDecimal(blendedCacChangeBps)}
          </span>
        </div>

        <div className={styles.deltaMetric}>
          <span className={styles.deltaLabel}>Spend Delta</span>
          <span className={[styles.deltaValue, spendPositive ? styles.positive : styles.negative].join(' ')}>
            {spendDeltaPrefix}
            {formatBpsAsPercentOneDecimal(spendDeltaBps)}
          </span>
        </div>
      </div>

      {/* Tertiary: Confidence Interval (when available) */}
      {confidenceInterval && (
        <div className={styles.confidenceSection}>
          <div className={styles.confidenceHeader}>
            <span className={styles.confidenceLabel}>95% Confidence Interval</span>
            <AuthorityBadge authority={confidenceInterval.authority} size="table" />
          </div>
          <div className={styles.confidenceRange}>
            <span className={styles.confidenceBound}>
              {formatBpsAsPercentOneDecimal(confidenceInterval.lowerBps)}
            </span>
            <span className={styles.confidenceSeparator} aria-hidden="true">
              —
            </span>
            <span className={styles.confidenceBound}>
              {formatBpsAsPercentOneDecimal(confidenceInterval.upperBps)}
            </span>
          </div>
          <p className={styles.confidenceNote}>
            Revenue lift may vary within this range based on model uncertainty.
          </p>
        </div>
      )}

      {/* Quaternary: Sensitivity Range (when available) */}
      {sensitivityRange && (
        <div className={styles.sensitivitySection}>
          <div className={styles.sensitivityHeader}>
            <span className={styles.sensitivityLabel}>Sensitivity Range</span>
            <AuthorityBadge authority={sensitivityRange.authority} size="table" />
          </div>
          <div className={styles.sensitivityRange}>
            <div className={styles.sensitivityBound}>
              <span className={styles.sensitivityBoundLabel}>Optimistic</span>
              <span className={styles.sensitivityBoundValue}>
                {formatBpsAsPercentOneDecimal(sensitivityRange.optimisticBps)}
              </span>
            </div>
            <div className={styles.sensitivityBound}>
              <span className={styles.sensitivityBoundLabel}>Pessimistic</span>
              <span className={styles.sensitivityBoundValue}>
                {formatBpsAsPercentOneDecimal(sensitivityRange.pessimisticBps)}
              </span>
            </div>
          </div>
          <p className={styles.sensitivityNote}>
            Scenario sensitivity to model assumptions and market conditions.
          </p>
        </div>
      )}

      <p className={styles.caption}>{BUDGET_SIMULATION_COPY.expectedImpact.caption}</p>
    </section>
  );
}
