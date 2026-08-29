import type { ClaimDetailDTO } from '../../../detail/types';
import { CLAIM_DETAIL_COPY } from '../../../claims/claimDetailCopy';
import {
  claimSourceLabel,
  formatShortClaimRef,
  resolveClaimExecutiveVerdict,
} from '../../../claims/claimDetailDisplay';
import shared from '../../../styles/shared.module.css';
import reflow from '../../../styles/reflowLayout.module.css';
import styles from './ClaimDetailHeader.module.css';

export interface ClaimDetailHeaderProps {
  data: ClaimDetailDTO;
}

export function ClaimDetailHeader({ data }: ClaimDetailHeaderProps) {
  const platform = claimSourceLabel(data.claimSource);
  const shortRef = formatShortClaimRef(data.claimRef);
  const verdict = resolveClaimExecutiveVerdict(data);
  const isMatch = verdict === 'verified';
  const verdictLabel = isMatch
    ? CLAIM_DETAIL_COPY.verdict.verified
    : CLAIM_DETAIL_COPY.verdict.discrepancy;

  return (
    <header
      className={[reflow.pageHeaderRow, styles.header, shared.focusVisible].join(' ')}
      data-claim-detail-header
      data-page-interface-header
    >
      <div className={[reflow.pageHeaderStack, styles.headerStack].join(' ')}>
        <h1
          className={[styles.title, shared.focusVisible].join(' ')}
          title={data.claimRef}
          data-claim-detail-title
        >
          <span className={styles.titlePrimary}>{platform} Claim</span>
          <span className={styles.titleRef} data-claim-detail-title-ref>
            #{shortRef}
          </span>
        </h1>
        <p className={styles.pageQuestion}>{CLAIM_DETAIL_COPY.pageQuestion}</p>
      </div>

      <div className={[reflow.headerActionColumn, styles.headerActionColumn].join(' ')}>
        <span
          className={isMatch ? styles.verdictMatch : styles.verdictGap}
          data-claim-verdict={verdict}
          role="status"
          aria-label={`${CLAIM_DETAIL_COPY.verdict.label}: ${verdictLabel}`}
        >
          <span className={styles.verdictLabel}>{CLAIM_DETAIL_COPY.verdict.label}</span>
          <span className={styles.verdictValue}>{verdictLabel}</span>
        </span>
      </div>
    </header>
  );
}
