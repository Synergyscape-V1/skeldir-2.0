import type { AuthorityClass } from '../../../lib/types';
import { DiscrepancyIndicator } from '../../trust/DiscrepancyIndicator/DiscrepancyIndicator';
import { FinancialValue } from '../FinancialValue/FinancialValue';
import { parseMoneyMinor, subtractMoneyMinor } from '../../../lib/money';
import shared from '../../../styles/shared.module.css';
import styles from './ClaimComparisonCard.module.css';

export interface ClaimComparisonCardProps {
  claimedRevenueMinor?: bigint | string | null;
  verifiedRevenueMinor?: bigint | string | null;
  currencyCode?: string;
  claimedAuthority?: AuthorityClass | string;
  verifiedAuthority?: AuthorityClass | string;
  backendDifferenceMinor?: bigint | string | null;
}

type DifferenceSeverity = 'within_tolerance' | 'flagged' | 'rejected';

function classifyDifference(diffMinor: bigint): DifferenceSeverity {
  const abs = diffMinor < 0n ? -diffMinor : diffMinor;
  if (abs === 0n) return 'within_tolerance';
  if (abs <= 100n) return 'flagged';
  return 'rejected';
}

export function ClaimComparisonCard({
  claimedRevenueMinor,
  verifiedRevenueMinor,
  currencyCode,
  claimedAuthority = 'probabilistic',
  verifiedAuthority = 'deterministic',
  backendDifferenceMinor,
}: ClaimComparisonCardProps) {
  const claimed = parseMoneyMinor(claimedRevenueMinor);
  const verified = parseMoneyMinor(verifiedRevenueMinor);

  if (!claimed.ok) {
    return (
      <div className={shared.errorState} role="alert">
        Claimed revenue: {claimed.error}
      </div>
    );
  }

  if (!verified.ok) {
    return (
      <div className={shared.errorState} role="alert">
        Verified revenue: {verified.error}
      </div>
    );
  }

  const computedDiff = subtractMoneyMinor(claimed.value, verified.value);

  if (backendDifferenceMinor !== undefined && backendDifferenceMinor !== null) {
    const backend = parseMoneyMinor(backendDifferenceMinor);
    if (!backend.ok) {
      return (
        <div className={shared.errorState} role="alert">
          backendDifferenceMinor: {backend.error}
        </div>
      );
    }
    if (backend.value !== computedDiff) {
      return (
        <div className={shared.errorState} role="alert">
          Backend difference mismatch. Expected {computedDiff.toString()} minor units.
        </div>
      );
    }
  }

  const severity = classifyDifference(computedDiff);
  const diffDisplay = computedDiff.toString();

  return (
    <section className={styles.card} aria-label="Claim revenue comparison">
      <h3 className={styles.title}>Platform claim vs verified revenue</h3>
      <div className={styles.grid}>
        <FinancialValue
          label="Platform claim"
          amountMinor={claimedRevenueMinor!}
          currencyCode={currencyCode}
          authority={claimedAuthority}
        />
        <FinancialValue
          label="Verified revenue"
          amountMinor={verifiedRevenueMinor!}
          currencyCode={currencyCode}
          authority={verifiedAuthority}
        />
      </div>
      <div className={[styles.difference, styles[severity]].join(' ')} role="status">
        <span className={styles.diffLabel}>Difference (minor units)</span>
        <span className={styles.diffValue} data-field="difference_minor">
          {diffDisplay}
        </span>
        <span className={styles.diffHint}>
          Computed with exact integer arithmetic. No frontend floating-point truth.
        </span>
      </div>
    </section>
  );
}

export { subtractMoneyMinor, parseMoneyMinor };

export interface ClaimComparisonTableDeltaProps {
  claimedRevenueMinor: bigint | string;
  verifiedRevenueMinor: bigint | string;
  discrepancyRateBps: number;
  discrepancyClass: 'within_tolerance' | 'flagged' | 'material' | 'unknown';
  backendDifferenceMinor?: bigint | string | null;
}

export function ClaimComparisonTableDelta({
  claimedRevenueMinor,
  verifiedRevenueMinor,
  discrepancyRateBps,
  discrepancyClass,
  backendDifferenceMinor,
  currencyCode = 'USD',
}: ClaimComparisonTableDeltaProps & { currencyCode?: string }) {
  return (
    <DiscrepancyIndicator
      claimedRevenueMinor={claimedRevenueMinor}
      verifiedRevenueMinor={verifiedRevenueMinor}
      discrepancyAmountMinor={backendDifferenceMinor ?? undefined}
      discrepancyRateBps={discrepancyRateBps}
      discrepancyClass={discrepancyClass}
      currencyCode={currencyCode}
      variant="table"
    />
  );
}
