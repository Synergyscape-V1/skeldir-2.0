import type { TrustEnvelopeDetailDTO } from '../../../detail/types';
import { TRUST_ENVELOPE_DETAIL_COPY } from '../../../trustIndex/trustEnvelopeDetailCopy';
import { formatTrustEnvelopeMoneyMinorDisplay } from '../../../trustIndex/trustEnvelopeDetailDisplay';
import { resolveTrustEnvelopeExecutiveReliability } from '../../../trust/executiveDataReliability';
import { DataReliabilityGate } from '../DataReliabilityGate/DataReliabilityGate';
import { PolicyAuthorityPill } from '../PolicyAuthorityPill/PolicyAuthorityPill';
import styles from './TrustEnvelopeDetailPage.module.css';

export interface TrustEnvelopeDetailVerdictSummaryProps {
  detail: TrustEnvelopeDetailDTO;
}

export function TrustEnvelopeDetailVerdictSummary({ detail }: TrustEnvelopeDetailVerdictSummaryProps) {
  const verifiedDisplay = formatTrustEnvelopeMoneyMinorDisplay(
    detail.deterministicTruth.verifiedRevenueMinor,
  );
  const reliabilityResolution = resolveTrustEnvelopeExecutiveReliability({
    matchVerdictStatus: detail.deterministicTruth.matchVerdictStatus,
    confidence: detail.confidence,
    extractionFreshness: detail.deterministicTruth.extractionFreshness,
  });

  return (
    <section
      className={styles.verdictSummarySection}
      data-trust-room="decision-cockpit"
      data-trust-envelope-decision-verdict
      aria-label={TRUST_ENVELOPE_DETAIL_COPY.cockpit.ariaLabel}
    >
      <div className={styles.verdictSummaryGrid}>
        <article
          className={styles.verdictSummaryCard}
          data-trust-envelope-cockpit-verified-revenue-tile
        >
          <DataReliabilityGate
            resolution={reliabilityResolution}
            amountDisplay={verifiedDisplay}
            label={TRUST_ENVELOPE_DETAIL_COPY.cockpit.verifiedRevenue}
            showInlineAlert={reliabilityResolution.reliability !== 'verified'}
          />
        </article>

        <article className={styles.verdictSummaryCard} data-trust-envelope-cockpit-policy>
          <div className={styles.verdictSummaryTopRow}>
            <span className={styles.verdictSummaryLabel}>
              {TRUST_ENVELOPE_DETAIL_COPY.cockpit.policyAuthority}
            </span>
          </div>
          <div className={styles.verdictPolicyValue}>
            <PolicyAuthorityPill
              state={detail.policyAuthority.state}
              showIcon={false}
              size="table"
              appearance="text"
            />
          </div>
          <p className={styles.verdictSummaryMeta}>{detail.policyAuthority.explanation}</p>
        </article>
      </div>
    </section>
  );
}
