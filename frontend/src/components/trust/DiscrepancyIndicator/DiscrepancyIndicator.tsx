import { DiscrepancyBadge } from '../../commandCenter/StatusBadges/StatusBadges';
import { parseMoneyMinor, subtractMoneyMinor } from '../../../lib/money';
import {
  resolveDiscrepancyPresentation,
  type DiscrepancyPresentationInput,
} from '../../../claims/discrepancySemantics';
import type { DiscrepancyClass } from '../../../ledger/types';
import shared from '../../../styles/shared.module.css';
import styles from './DiscrepancyIndicator.module.css';

/**
 * Component-boundary props. The domain type `DiscrepancyPresentationInput` keeps money
 * strictly `bigint` (money is integer minor units). This component sits at the transport
 * boundary and parses its money inputs with `parseMoneyMinor`, which accepts `bigint` or a
 * decimal string and explicitly rejects `number`. The money fields are therefore widened
 * here to the transport shape rather than casting at each call site, which would let a
 * string flow into a money path unchecked.
 */
export interface DiscrepancyIndicatorProps
  extends Omit<
    DiscrepancyPresentationInput,
    'claimedRevenueMinor' | 'verifiedRevenueMinor' | 'discrepancyAmountMinor'
  > {
  claimedRevenueMinor: bigint | string;
  verifiedRevenueMinor: bigint | string;
  discrepancyAmountMinor?: bigint | string | null;
  variant?: 'table' | 'hero';
  showBadge?: boolean;
  showThresholdContext?: boolean;
}

export function DiscrepancyIndicator({
  claimedRevenueMinor,
  verifiedRevenueMinor,
  discrepancyAmountMinor,
  discrepancyRateBps,
  discrepancyClass,
  currencyCode,
  variant = 'table',
  showBadge = true,
  showThresholdContext,
}: DiscrepancyIndicatorProps) {
  const claimed = parseMoneyMinor(claimedRevenueMinor);
  const verified = parseMoneyMinor(verifiedRevenueMinor);

  if (!claimed.ok || !verified.ok) {
    return (
      <span className={shared.errorState} role="alert" data-discrepancy-indicator-error>
        Comparison unavailable
      </span>
    );
  }

  const computedDiff = subtractMoneyMinor(claimed.value, verified.value);

  if (discrepancyAmountMinor !== undefined && discrepancyAmountMinor !== null) {
    const backend = parseMoneyMinor(discrepancyAmountMinor);
    if (!backend.ok || backend.value !== computedDiff) {
      return (
        <span className={shared.errorState} role="alert" data-discrepancy-indicator-error>
          Backend difference mismatch
        </span>
      );
    }
  }

  const presentation = resolveDiscrepancyPresentation({
    claimedRevenueMinor: claimed.value,
    verifiedRevenueMinor: verified.value,
    discrepancyAmountMinor: computedDiff,
    discrepancyRateBps,
    discrepancyClass,
    currencyCode,
  });

  if ('error' in presentation) {
    return (
      <span className={shared.errorState} role="alert" data-discrepancy-indicator-error>
        {presentation.error}
      </span>
    );
  }

  const toneClass =
    presentation.severityTone === 'success'
      ? styles.toneSuccess
      : presentation.severityTone === 'warning'
        ? styles.toneWarning
        : presentation.severityTone === 'error'
          ? styles.toneError
          : styles.toneNeutral;

  const isTable = variant === 'table';
  const renderThreshold =
    showThresholdContext ?? (!isTable && discrepancyClass !== 'within_tolerance');

  if (isTable) {
    return (
      <div
        className={[styles.root, styles.table, toneClass].join(' ')}
        data-discrepancy-indicator
        data-discrepancy-class={discrepancyClass as DiscrepancyClass}
        data-difference-cell={discrepancyClass}
        title={presentation.tooltip}
        role="status"
        aria-label={`${presentation.amountDisplay}, ${presentation.percentOfClaimedLabel}, ${presentation.badgeLabel}`}
      >
        <span className={styles.amount} data-discrepancy-amount>
          {presentation.amountDisplay}
        </span>
        <span className={styles.percent} data-discrepancy-percent>
          {presentation.compactPercentLabel}
        </span>
        {showBadge ? (
          <span
            className={styles.statusText}
            data-discrepancy-badge={presentation.badgeStatus}
            data-status-text
          >
            {presentation.compactBadgeLabel}
          </span>
        ) : null}
      </div>
    );
  }

  return (
    <div
      className={[styles.root, styles.hero, toneClass].join(' ')}
      data-discrepancy-indicator
      data-discrepancy-class={discrepancyClass as DiscrepancyClass}
      data-difference-cell={discrepancyClass}
      title={presentation.tooltip}
      role="status"
      aria-label={`${presentation.amountDisplay}, ${presentation.percentOfClaimedLabel}, ${presentation.badgeLabel}`}
    >
      <span className={styles.amount} data-discrepancy-amount>
        {presentation.amountDisplay}
      </span>
      <span className={styles.percent} data-discrepancy-percent>
        {presentation.percentOfClaimedLabel}
      </span>
      {renderThreshold ? (
        <span className={styles.thresholdContext} data-discrepancy-threshold-context>
          {presentation.thresholdContextLabel}
        </span>
      ) : null}
      {showBadge ? (
        <div className={styles.badgeRow}>
          <DiscrepancyBadge status={presentation.badgeStatus} table variant="chip" />
        </div>
      ) : null}
    </div>
  );
}
