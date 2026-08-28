import { Link } from 'react-router-dom';
import type { ClaimDetailDTO } from '../../../detail/types';
import { DiscrepancyIndicator } from '../../trust/DiscrepancyIndicator/DiscrepancyIndicator';
import { VariancePolicyGate } from '../../trust/VariancePolicyGate/VariancePolicyGate';
import { CLAIM_DETAIL_COPY } from '../../../claims/claimDetailCopy';
import shared from '../../../styles/shared.module.css';
import styles from './ContextualizedDeltaBlock.module.css';

export interface ContextualizedDeltaBlockProps {
  data: Pick<
    ClaimDetailDTO,
    | 'claimedRevenueMinor'
    | 'verifiedRevenueMinor'
    | 'discrepancyAmountMinor'
    | 'discrepancyRateBps'
    | 'discrepancyClass'
    | 'currencyCode'
    | 'claimRef'
  >;
  showReviewCta?: boolean;
  /**
   * tile    — compact value-only rendering for the Overview summary tile (amount + percent).
   * context — verbose threshold + policy-gate prose + review CTA, rendered below the tile grid.
   * full    — legacy composite (default, retained for safety).
   */
  variant?: 'tile' | 'context' | 'full';
}

export function ContextualizedDeltaBlock({
  data,
  showReviewCta = true,
  variant = 'full',
}: ContextualizedDeltaBlockProps) {
  const breached = data.discrepancyClass === 'flagged' || data.discrepancyClass === 'material';

  if (variant === 'tile') {
    return (
      <div
        className={styles.root}
        data-contextualized-delta-block
        data-delta-variant="tile"
        data-summary-metric="claim_difference"
        data-summary-tile-kind="financial_truth"
        data-source-surface="claim_detail"
        data-discrepancy-backend
      >
        <DiscrepancyIndicator
          claimedRevenueMinor={data.claimedRevenueMinor}
          verifiedRevenueMinor={data.verifiedRevenueMinor}
          discrepancyAmountMinor={data.discrepancyAmountMinor}
          discrepancyRateBps={data.discrepancyRateBps}
          discrepancyClass={data.discrepancyClass}
          currencyCode={data.currencyCode}
          variant="hero"
          showBadge={false}
          showThresholdContext={false}
        />
      </div>
    );
  }

  if (variant === 'context') {
    return (
      <div
        className={[styles.root, styles.context].join(' ')}
        data-contextualized-delta-block
        data-delta-variant="context"
        data-discrepancy-backend
      >
        <DiscrepancyIndicator
          claimedRevenueMinor={data.claimedRevenueMinor}
          verifiedRevenueMinor={data.verifiedRevenueMinor}
          discrepancyAmountMinor={data.discrepancyAmountMinor}
          discrepancyRateBps={data.discrepancyRateBps}
          discrepancyClass={data.discrepancyClass}
          currencyCode={data.currencyCode}
          variant="hero"
          showBadge={false}
          showThresholdContext
        />

        <VariancePolicyGate
          claimedRevenueMinor={data.claimedRevenueMinor}
          verifiedRevenueMinor={data.verifiedRevenueMinor}
          discrepancyAmountMinor={data.discrepancyAmountMinor}
          discrepancyRateBps={data.discrepancyRateBps}
          discrepancyClass={data.discrepancyClass}
          currencyCode={data.currencyCode}
        />

        {showReviewCta && breached ? (
          <Link
            to={`/app/exceptions?claimRef=${encodeURIComponent(data.claimRef)}`}
            className={[styles.reviewCta, shared.focusVisible].join(' ')}
            data-variance-review-cta
          >
            Review Discrepancy
          </Link>
        ) : null}
      </div>
    );
  }

  return (
    <div
      className={styles.root}
      data-contextualized-delta-block
      data-summary-metric="claim_difference"
      data-summary-tile-kind="financial_truth"
      data-source-surface="claim_detail"
      data-discrepancy-backend
    >
      <span className={styles.label}>{CLAIM_DETAIL_COPY.financialSummary.differenceLabel}</span>

      <DiscrepancyIndicator
        claimedRevenueMinor={data.claimedRevenueMinor}
        verifiedRevenueMinor={data.verifiedRevenueMinor}
        discrepancyAmountMinor={data.discrepancyAmountMinor}
        discrepancyRateBps={data.discrepancyRateBps}
        discrepancyClass={data.discrepancyClass}
        currencyCode={data.currencyCode}
        variant="hero"
        showBadge
        showThresholdContext={breached}
      />

      <VariancePolicyGate
        claimedRevenueMinor={data.claimedRevenueMinor}
        verifiedRevenueMinor={data.verifiedRevenueMinor}
        discrepancyAmountMinor={data.discrepancyAmountMinor}
        discrepancyRateBps={data.discrepancyRateBps}
        discrepancyClass={data.discrepancyClass}
        currencyCode={data.currencyCode}
      />

      {showReviewCta && breached ? (
        <Link
          to={`/app/exceptions?claimRef=${encodeURIComponent(data.claimRef)}`}
          className={[styles.reviewCta, shared.focusVisible].join(' ')}
          data-variance-review-cta
        >
          Review Discrepancy
        </Link>
      ) : null}
    </div>
  );
}
