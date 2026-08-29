import type { ClaimDetailDTO } from '../../../detail/types';
import { CLAIM_DETAIL_COPY } from '../../../claims/claimDetailCopy';
import {
  formatMoneyMinorDisplay,
} from '../../../claims/claimDetailDisplay';
import { resolveClaimExecutiveReliability } from '../../../trust/executiveDataReliability';
import { ContextualizedDeltaBlock } from '../ContextualizedDeltaBlock/ContextualizedDeltaBlock';
import { DataReliabilityGate } from '../../trust/DataReliabilityGate/DataReliabilityGate';
import { COMMAND_CENTER_CHIP_PROPS } from '../../../commandCenter/commandCenterChipProps';
import { AuthorityBadge } from '../../trust/AuthorityBadge/AuthorityBadge';
import summary from '../../../styles/summaryTile.module.css';
import styles from './ClaimDetailFinancialSummary.module.css';

export interface ClaimDetailFinancialSummaryProps {
  data: ClaimDetailDTO;
  claimId: string;
}

export function ClaimDetailFinancialSummary({ data, claimId }: ClaimDetailFinancialSummaryProps) {
  const claimedDisplay = formatMoneyMinorDisplay(data.claimedRevenueMinor, data.currencyCode);
  const verifiedDisplay = formatMoneyMinorDisplay(data.verifiedRevenueMinor, data.currencyCode);
  const reliability = resolveClaimExecutiveReliability(data);

  return (
    <section
      className={styles.hero}
      aria-label="Claim financial summary"
      data-claim-detail-summary
      data-claim-detail-tiles
      data-claim-id={claimId}
    >
      <div className={[summary.grid, styles.summaryGrid].join(' ')} data-claim-money-strip>
        <article
          className={summary.card}
          data-summary-metric="claim_claimed"
          data-summary-tile-kind="financial_truth"
          data-source-surface="claim_detail"
        >
          <div className={summary.body}>
            <div className={styles.labelStack}>
              <span className={summary.label}>{CLAIM_DETAIL_COPY.financialSummary.claimedLabel}</span>
              <span className={summary.meta}>{CLAIM_DETAIL_COPY.financialSummary.claimedSublabel}</span>
            </div>
            <span
              className={summary.value}
              data-summary-metric-value="claim_claimed"
            >
              {claimedDisplay}
            </span>
          </div>
        </article>

        <article
          className={summary.card}
          data-summary-metric="claim_verified"
          data-summary-tile-kind="financial_truth"
          data-source-surface="claim_detail"
        >
          <div className={summary.body}>
            <div className={summary.topRow}>
              <div className={styles.labelStack}>
                <span className={summary.label}>{CLAIM_DETAIL_COPY.financialSummary.verifiedLabel}</span>
                <span className={summary.meta}>{CLAIM_DETAIL_COPY.financialSummary.verifiedSublabel}</span>
              </div>
              <span className={summary.chip}>
                <AuthorityBadge authority="deterministic" {...COMMAND_CENTER_CHIP_PROPS} />
              </span>
            </div>
            <DataReliabilityGate
              resolution={reliability}
              amountDisplay={verifiedDisplay}
              label={undefined}
              showInlineAlert={reliability.reliability !== 'verified'}
              showReliabilityBadge={false}
              variant="compact"
            />
          </div>
        </article>

        <article
          className={[summary.card, styles.gapTile].join(' ')}
          data-summary-metric="claim_difference"
          data-summary-tile-kind="financial_truth"
          data-source-surface="claim_detail"
        >
          <div className={summary.body}>
            <div className={summary.topRow}>
              <span className={summary.label}>{CLAIM_DETAIL_COPY.financialSummary.differenceLabel}</span>
            </div>
            <ContextualizedDeltaBlock data={data} showReviewCta={false} variant="tile" />
          </div>
        </article>
      </div>
    </section>
  );
}

